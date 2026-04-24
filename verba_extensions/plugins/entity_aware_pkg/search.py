
from typing import Optional, Dict, Any, List, Tuple
from wasabi import msg
from goldenverba.components.chunk import Chunk
from verba_extensions.compatibility.weaviate_imports import Filter, WEAVIATE_V4
import json
import re

def get_config_value(config, key, default=None):
    if key not in config: return default
    item = config[key]
    if item is None: return default
    if hasattr(item, 'value'): return item.value if item.value is not None else default
    if isinstance(item, dict): return item.get('value', default)
    return item


async def _execute_cascade_search(self, chunks: List[Any], query: str, config: Dict[str, Any]) -> List[Any]:
    """
    Executa a Fase 2 do Cascade Mode (Premium Reranking).
    
    Args:
        chunks: Candidatos da Fase 1 (Fast Recall) - Weaviate objects
        query: Query original
        config: Configuração do retriever (contendo config do reranker)
        
    Returns:
        Chunks reordenados e cortados pelo Reranker Top K (Wrapped to look like Weaviate objects)
    """
    try:
        from verba_extensions.plugins.reranker import RerankerPlugin
        from goldenverba.components.chunk import Chunk
        import json
        
        reranker = RerankerPlugin()
        
        # Atualizar config do reranker com os valores atuais do retriever
        reranker_config = {}
        for key, value in config.items():
            reranker_config[key] = value
        
        # Definir top_k final (default 5 ou configurado)
        final_top_k = int(get_config_value(config, "Reranker Top K", 5))
        if final_top_k <= 0:
            final_top_k = 5 # Safety fallback
            
        msg.info(f"  🌊 Cascade Phase 2: Reranking {len(chunks)} chunks -> Top {final_top_k}...")
        
        # 1. Converter Weaviate objects para Chunk objects
        chunk_objects = []
        for c in chunks:
            # Weaviate objects usually have properties attribute
            if hasattr(c, "properties"):
                props = c.properties
                content = props.get("content", "")
                doc_uuid = props.get("doc_uuid", "")
                chunk_id = props.get("chunk_id", 0)
                
                # Tentar extrair meta
                meta = {}
                if "meta" in props:
                    try:
                        meta = json.loads(props["meta"]) if isinstance(props["meta"], str) else props["meta"]
                    except:
                        pass
                        
                # Criar Chunk object
                chunk_obj = Chunk(
                    content=content,
                    chunk_id=chunk_id,
                    content_without_overlap=content # Assume full content for simplicity
                )
                chunk_obj.doc_uuid = doc_uuid
                chunk_obj.uuid = str(c.uuid) if hasattr(c, "uuid") else None
                chunk_obj.meta = meta
                
                # Adicionar metadados adicionais ao meta se disponível
                if "chunk_lang" in props:
                    chunk_obj.chunk_lang = props["chunk_lang"]
                if "chunk_date" in props:
                    chunk_obj.chunk_date = props["chunk_date"]
                
                chunk_objects.append(chunk_obj)
            else:
                # Já é Chunk object ou incompatível
                if isinstance(c, Chunk):
                    chunk_objects.append(c)
        
        if not chunk_objects:
            msg.warn("  ⚠️ Cascade Phase 2: Nenhum chunk válido para rerank.")
            return chunks
        
        # Executar reranking
        reranked_chunks = await reranker.rerank(
            chunks=chunk_objects,
            query=query,
            config=reranker_config
        )
        
        # Cortar para top K
        reranked_chunks = reranked_chunks[:final_top_k]
        
        # 2. Converter de volta para formato compatível com EntityAwareRetriever (Weaviate-like wrapper)
        # EntityAwareRetriever espera objetos com .properties e .metadata.score
        
        class WeaviateChunkWrapper:
            def __init__(self, chunk, score):
                self.uuid = chunk.uuid
                self.properties = {
                    "content": chunk.content,
                    "doc_uuid": chunk.doc_uuid,
                    "chunk_id": chunk.chunk_id,
                    "meta": json.dumps(chunk.meta) if isinstance(chunk.meta, dict) else chunk.meta
                }
                if chunk.chunk_lang:
                    self.properties["chunk_lang"] = chunk.chunk_lang
                if chunk.chunk_date:
                    self.properties["chunk_date"] = chunk.chunk_date

                # Adicionar properties que estavam no meta de volta ao properties
                # (Importante para filtros downstream que olham properties)
                if chunk.meta:
                     for k, v in chunk.meta.items():
                         if k not in self.properties:
                             self.properties[k] = v

                # Metadata wrapper for score
                class MetaWrapper:
                    def __init__(self, s):
                        self.score = s
                
                self.metadata = MetaWrapper(score)
        
        final_results = []
        for i, rc in enumerate(reranked_chunks):
            # Score: tentar pegar do meta ou usar sintético
            score = 0.99 - (i * 0.01) 
            if rc.meta and "score" in rc.meta:
                try:
                    score = float(rc.meta["score"])
                except:
                    pass
            
            final_results.append(WeaviateChunkWrapper(rc, score))
        
        msg.good(f"  ✅ Cascade Phase 2 concluída: {len(final_results)} chunks retornados")
        return final_results
        
    except ImportError as e:
        msg.warn(f"RerankerPlugin não encontrado ou erro: {e}. Pulando Cascade Phase 2.")
        return chunks
    except Exception as e:
        msg.warn(f"Erro no Cascade Reranking: {e}")
        import traceback
        traceback.print_exc()
        return chunks


async def _execute_two_phase_search(
    self,
    client,
    weaviate_manager,
    embedder: str,
    query: str,
    search_query: str,
    vector: List[float],
    entity_ids: List[str],
    entity_texts: List[str],
    semantic_terms: List[str],
    detected_frameworks: List[str],
    detected_companies: List[str],
    detected_sectors: List[str],
    combined_filter,
    lang_filter,
    temporal_filter,
    framework_filter,
    limit_mode: str,
    limit: int,
    labels: List[str],
    document_uuids: List[str],
    rewritten_alpha: float,
    enable_query_expansion: bool,
    enable_multi_vector: bool,
    vectors_to_search: List[str],
    cache_ttl: int,
    debug_info: Dict[str, Any],
    rag_config: Optional[Dict[str, Any]] = None
) -> List[Any]:
    """
    Executa Two-Phase Search:
    Fase 1: Filtro por entidades (subespaço)
    Fase 2: Multi-vector search dentro do subespaço filtrado
    """
    
    try:
        # FASE 1: Filtro por Entidades (Subespaço)
        msg.info(f"  🔍 Fase 1: Filtrando por entidades...")
        
        # Construir filtro de entidades para Fase 1
        phase1_filter = None
        filters_list = []
        
        if entity_ids:
            # Usar entity_ids (formato ent:*)
            phase1_entity_filter = Filter.by_property("section_entity_ids").contains_any(entity_ids)
            filters_list.append(phase1_entity_filter)
            msg.info(f"    Filtro por entity_ids: {entity_ids}")
        elif entity_texts:
            # Usar entity_texts (modo inteligente)
            # Buscar em entities_local_ids ou entity_mentions
            phase1_entity_filter = Filter.by_property("entities_local_ids").contains_any(entity_texts)
            filters_list.append(phase1_entity_filter)
            msg.info(f"    Filtro por entity_texts: {entity_texts}")
        
        # Adicionar outros filtros (temporal, framework)
        if temporal_filter:
            filters_list.append(temporal_filter)
        if framework_filter:
            filters_list.append(framework_filter)
        
        if filters_list:
            if len(filters_list) == 1:
                phase1_filter = filters_list[0]
            else:
                phase1_filter = Filter.all_of(filters_list)
        
        # Busca ampla na Fase 1 (apenas para obter subespaço)
        # Não precisa ser muito restritiva, apenas identificar chunks com entidades
        phase1_limit = min(limit * 3, 100)  # Buscar mais chunks para ter subespaço maior
        
        normalized = weaviate_manager._normalize_embedder_name(embedder)
        collection_name = weaviate_manager.embedding_table.get(embedder, f"VERBA_Embedding_{normalized}")
        
        # Busca simples na Fase 1 (apenas para obter subespaço)
        # Usar busca híbrida básica com filtro de entidades
        phase1_chunks = await weaviate_manager.hybrid_chunks_with_filter(
            client=client,
            embedder=embedder,
            query=search_query,
            vector=vector,
            limit_mode=limit_mode,
            limit=phase1_limit,
            labels=labels,
            document_uuids=document_uuids,
            filters=phase1_filter,
            alpha=0.4,  # Mais BM25 na Fase 1 (foco em entidades)
        )
        
        if not phase1_chunks:
            msg.warn(f"    Fase 1: Nenhum chunk encontrado com entidades (Query: '{search_query}', Labels: {labels})")
            return []
        
        msg.good(f"    Fase 1: {len(phase1_chunks)} chunks no subespaço")
        debug_info["two_phase_search"]["phase1_results"] = len(phase1_chunks)
        
        # Extrair UUIDs dos chunks da Fase 1 para filtrar na Fase 2
        phase1_uuids = [str(chunk.uuid) for chunk in phase1_chunks if hasattr(chunk, 'uuid')]
        
        if not phase1_uuids:
            msg.warn(f"    Fase 1: Nenhum UUID extraído")
            return []
        
        # FASE 2: Multi-Vector Search dentro do Subespaço
        msg.info(f"  🎯 Fase 2: Multi-vector search dentro do subespaço ({len(phase1_uuids)} chunks)...")
        
        # Query Expansion (Fase 2: Temas)
        expanded_queries_phase2 = [search_query]  # Fallback
        
        if enable_query_expansion:
            try:
                from verba_extensions.plugins.query_expander import QueryExpanderPlugin
                query_expander = QueryExpanderPlugin(cache_ttl_seconds=cache_ttl)
                expanded_queries_phase2 = await query_expander.expand_query_for_themes(search_query, use_cache=True)
                msg.info(f"    Query Expansion (Fase 2): {len(expanded_queries_phase2)} variações")
                debug_info["query_expansion_phase2"] = expanded_queries_phase2
            except Exception as e:
                msg.debug(f"    Query Expansion não disponível: {str(e)}")
        
        # Usar primeira variação expandida (ou query original)
        phase2_query = expanded_queries_phase2[0] if expanded_queries_phase2 else search_query
        
        # Construir filtro para Fase 2: subespaço (UUIDs da Fase 1) + outros filtros
        phase2_filter_list = [
            Filter.by_property("uuid").contains_any(phase1_uuids)
        ]
        
        if temporal_filter:
            phase2_filter_list.append(temporal_filter)
        if framework_filter:
            phase2_filter_list.append(framework_filter)
        
        phase2_filter = Filter.all_of(phase2_filter_list) if len(phase2_filter_list) > 1 else phase2_filter_list[0]
        
        # Multi-Vector Search ou Single Named Vector na Fase 2
        # Se tem 2+ vetores, usar multi-vector search
        # Se tem 1 vetor, usar target_vector na busca híbrida
        if enable_multi_vector and len(vectors_to_search) >= 2:
            try:
                from verba_extensions.plugins.multi_vector_searcher import MultiVectorSearcher
                from goldenverba.components.managers import EmbeddingManager
                
                # Gerar embedding da query
                embedding_manager = EmbeddingManager()
                
                if rag_config:
                    # Usar vectorize_query que já lida com config corretamente
                    query_vector_phase2 = await embedding_manager.vectorize_query(
                        embedder=embedder,
                        content=phase2_query,
                        rag_config=rag_config
                    )
                else:
                    # Fallback: usar método direto (pode não ter config correto)
                    if embedder not in embedding_manager.embedders:
                        raise Exception(f"Embedder {embedder} não encontrado")
                    
                    embedder_obj = embedding_manager.embedders[embedder]
                    embedder_config = {}
                    query_embeddings = await embedder_obj.vectorize(embedder_config, [phase2_query])
                    if not query_embeddings or len(query_embeddings) == 0:
                        raise Exception("Falha ao gerar embedding da query")
                    query_vector_phase2 = query_embeddings[0]
            except Exception as e:
                msg.warn(f"Erro ao vetorizar query para multi-vector search: {str(e)}. Realizando fallback para single-vector.")
                enable_multi_vector = False
                query_vector_phase2 = vector # Use the default vector from parameters
                
            # Configurar fusion type
            # Usa safe_config_to_dict caso self.config ainda seja um objeto (defensive)
            config_dict = safe_config_to_dict(self.config)
            relative_score_config = config_dict.get("Enable Relative Score Fusion", {})
            
            if isinstance(relative_score_config, dict):
                enable_relative_score = relative_score_config.get("value", True)
            elif hasattr(relative_score_config, 'value'):
                enable_relative_score = relative_score_config.value
            else:
                enable_relative_score = True
                
            fusion_type = "RELATIVE_SCORE" if enable_relative_score else "RRF"
            
            # Configurar query_properties para BM25 boosting
            query_properties = ["content", "title^2"]  # Boost de título

            # Validar e gerar vetores especializados (384d vs 1024d)
            query_vectors = {}
            try:
                if embedder in embedding_manager.embedders:
                    emb_obj = embedding_manager.embedders[embedder]
                    # Se for HybridConsultingEmbedder ou similar com suporte a named vectors
                    if hasattr(emb_obj, 'vectorize_named_query'):
                        msg.info("    Gerando vetores especializados (MiniLM)...")
                        minilm_vec = emb_obj.vectorize_named_query(phase2_query)
                        if minilm_vec:
                            for v_name in ["concept_vec", "sector_vec", "company_vec"]:
                                query_vectors[v_name] = minilm_vec
                            msg.info(f"    Vetores especializados gerados ({len(minilm_vec)}d)")
            except Exception as e_named:
                msg.warn(f"Erro ao gerar vetores named: {e_named}")
                    # Executar multi-vector search
            try:
                multi_vector_searcher = MultiVectorSearcher()
                result = await multi_vector_searcher.search_multi_vector(
                    client=client,
                    collection_name=collection_name,
                    query=phase2_query,
                    query_vector=query_vector_phase2,
                    vectors=vectors_to_search,
                    query_vectors=query_vectors,
                    filters=phase2_filter,
                    limit=limit,
                    alpha=rewritten_alpha,
                    fusion_type=fusion_type,
                    query_properties=query_properties
                )
                
                if result and result.get("results"):
                    # Converter resultados dict para objetos Weaviate
                    # Buscar chunks completos pelos UUIDs retornados
                    phase2_uuids = [r.get("_uuid") for r in result["results"] if r.get("_uuid")]
                    
                    if phase2_uuids:
                        # Buscar objetos completos do Weaviate
                        collection = client.collections.get(collection_name)
                        phase2_objects = await collection.query.fetch_objects(
                            filters=Filter.by_property("uuid").contains_any(phase2_uuids)
                        )
                        
                        if phase2_objects and hasattr(phase2_objects, 'objects'):
                            phase2_chunks = phase2_objects.objects
                            msg.good(f"    Fase 2: {len(phase2_chunks)} chunks retornados")
                            
                            # FASE 3: Cascade Reranking (Premium)
                            if self.config.get("Reranker Preset", {}).get("value") == "consulting_frameworks":
                                try:
                                    from verba_extensions.utils.reranker import CascadeReranker
                                    
                                    rerank_top_k = self.config.get("Reranker Top K", {}).get("value", 5)
                                    if rerank_top_k > 0:
                                        msg.info(f"  💎 Fase 3: Reranking Top-{rerank_top_k} results via Voyage...")
                                        reranker = CascadeReranker()
                                        phase2_chunks = await reranker.rerank(
                                            query=phase2_query,
                                            chunks=phase2_chunks,
                                            top_k=rerank_top_k
                                        )
                                except ImportError:
                                    msg.warn("    Fase 3: Reranker module not found")
                                except Exception as e:
                                    msg.warn(f"    Fase 3: Reranking failed ({str(e)}), returning original order")

                            debug_info["two_phase_search"]["phase2_results"] = len(phase2_chunks)
                            debug_info["two_phase_search"]["fusion_type"] = fusion_type
                            
                            return phase2_chunks
                        else:
                            msg.warn(f"    Fase 2: Não foi possível buscar objetos completos")
                    else:
                        msg.warn(f"    Fase 2: Nenhum UUID extraído dos resultados")
                else:
                    msg.warn(f"    Fase 2: Multi-vector não retornou resultados")
            except Exception as e:
                msg.warn(f"    Fase 2: Erro em multi-vector search: {str(e)}")
        
        # Fallback: busca híbrida simples na Fase 2
        # Se tem apenas 1 named vector relevante, usar target_vector
        target_vector_phase2 = None
        if len(vectors_to_search) == 1:
            target_vector_phase2 = vectors_to_search[0]
            msg.info(f"    Fase 2: Usando target_vector único: {target_vector_phase2}")
        
        phase2_chunks = await weaviate_manager.hybrid_chunks_with_filter(
            client=client,
            embedder=embedder,
            query=phase2_query,
            vector=vector,
            limit_mode=limit_mode,
            limit=limit,
            labels=labels,
            document_uuids=document_uuids,
            filters=phase2_filter,
            alpha=rewritten_alpha,
            target_vector=target_vector_phase2,  # Named vector único (se aplicável)
        )
        
        if phase2_chunks:
            msg.good(f"    Fase 2: {len(phase2_chunks)} chunks retornados (fallback)")
            debug_info["two_phase_search"]["phase2_results"] = len(phase2_chunks)
        if phase2_chunks and len(phase2_chunks) > 0:
            msg.good(f"    Fase 2: {len(phase2_chunks)} chunks retornados via Multi-Vector")
            return phase2_chunks
        else:
            msg.warn(f"    Fase 2: Nenhum chunk retornado (Multi-Vector retornou vazio)")
            return []
            
    except Exception as e:
        msg.warn(f"  Erro em Two-Phase Search: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


async def _execute_two_phase_search_document_level(
    self,
    client,
    weaviate_manager,
    embedder: str,
    query: str,
    search_query: str,
    vector: List[float],
    entity_ids: List[str],
    entity_texts: List[str],
    semantic_terms: List[str],
    detected_frameworks: List[str],
    detected_companies: List[str],
    detected_sectors: List[str],
    combined_filter,
    lang_filter,
    temporal_filter,
    framework_filter,
    limit_mode: str,
    limit: int,
    labels: List[str],
    document_uuids: List[str],
    rewritten_alpha: float,
    enable_query_expansion: bool,
    enable_multi_vector: bool,
    vectors_to_search: List[str],
    cache_ttl: int,
    debug_info: Dict[str, Any],
    rag_config: Optional[Dict[str, Any]] = None
) -> List[Any]:
    """
    Executa Two-Phase Search com filtro por DOCUMENTOS (não chunks):
    Fase 1: Encontra documentos que contêm entidades (subespaço documental)
    Fase 2: Busca semanticamente dentro de TODOS os chunks desses documentos
    
    Vantagens:
    - ✅ Mantém contexto completo dos documentos
    - ✅ Evita fragmentação artificial
    - ✅ Preserva relacionamentos entre chunks
    - ✅ Melhor para evitar contaminação de documentos irrelevantes
    """
    
    try:
        from verba_extensions.utils.document_entity_filter import (
            get_documents_by_multiple_entities
        )
        from verba_extensions.compatibility.weaviate_imports import Filter
        
        # FASE 1: Filtrar DOCUMENTOS que contêm entidades (não chunks)
        msg.info(f"  🔍 Fase 1 (Document-Level): Filtrando documentos por entidades...")
        
        normalized = weaviate_manager._normalize_embedder_name(embedder)
        collection_name = weaviate_manager.embedding_table.get(embedder, f"VERBA_Embedding_{normalized}")
        
        # Coletar todas as entidades para buscar documentos
        entities_to_search = []
        
        if entity_ids:
            entities_to_search.extend(entity_ids)
            msg.info(f"    Buscando documentos com entity_ids: {entity_ids}")
        
        if entity_texts:
            # entity_texts podem ser nomes de entidades ou IDs
            # Tentar usar ambos
            entities_to_search.extend(entity_texts)
            msg.info(f"    Buscando documentos com entity_texts: {entity_texts}")
        
        if not entities_to_search:
            msg.warn(f"    Fase 1: Nenhuma entidade detectada para filtrar documentos")
            return []
        
        # Buscar documentos que contêm QUALQUER uma das entidades
        # (documento pode ter Apple OU Microsoft, não precisa ter ambas)
        phase1_doc_uuids = await get_documents_by_multiple_entities(
            client=client,
            collection_name=collection_name,
            entity_ids=entities_to_search,
            require_all=False,  # Documento precisa ter QUALQUER entidade, não todas
            limit=1000  # Buscar até 1000 chunks para extrair documentos
        )
        
        if not phase1_doc_uuids:
            msg.warn(f"    Fase 1: Nenhum documento encontrado com entidades {entities_to_search}")
            return []
        
        msg.good(f"    Fase 1: {len(phase1_doc_uuids)} documentos no subespaço")
        debug_info["two_phase_search"]["phase1_results"] = len(phase1_doc_uuids)
        debug_info["two_phase_search"]["filter_level"] = "document"
        
        # Combinar com document_uuids já filtrados (se houver)
        if document_uuids:
            phase1_doc_uuids = list(set(phase1_doc_uuids) & set(document_uuids))
            if not phase1_doc_uuids:
                msg.warn(f"    Fase 1: Nenhum documento após combinar com filtros existentes")
                return []
            msg.info(f"    Fase 1: {len(phase1_doc_uuids)} documentos após combinar com filtros")
        
        # 🎯 NOVO: Identificar chunks específicos que mencionam entidades para boost de proximidade
        # Isso ajuda a encontrar chunks adjacentes que podem conter o assunto pesquisado
        entity_chunk_positions = {}  # {doc_uuid: [chunk_ids]}
        try:
            collection = client.collections.get(collection_name)
            
            # Buscar chunks que mencionam as entidades nos documentos filtrados
            entity_chunk_filter_list = [
                Filter.by_property("doc_uuid").contains_any(phase1_doc_uuids)
            ]
            
            if entity_ids:
                entity_filter = Filter.by_property("section_entity_ids").contains_any(entity_ids)
                entity_chunk_filter_list.append(entity_filter)
            elif entity_texts:
                entity_filter = Filter.by_property("entities_local_ids").contains_any(entity_texts)
                entity_chunk_filter_list.append(entity_filter)
            
            if len(entity_chunk_filter_list) > 1:
                entity_chunk_filter = Filter.all_of(entity_chunk_filter_list)
            else:
                entity_chunk_filter = entity_chunk_filter_list[0] if entity_chunk_filter_list else None
            
            if entity_chunk_filter:
                entity_chunks_response = await collection.query.fetch_objects(
                    filters=entity_chunk_filter,
                    limit=500,  # Buscar até 500 chunks com entidades
                    return_properties=["doc_uuid", "chunk_id"]
                )
                
                # Agrupar por documento
                for chunk_obj in entity_chunks_response.objects:
                    doc_uuid = str(chunk_obj.properties.get("doc_uuid", ""))
                    chunk_id = chunk_obj.properties.get("chunk_id")
                    
                    if doc_uuid and chunk_id is not None:
                        try:
                            chunk_id_int = int(float(chunk_id))  # Converter para int
                            if doc_uuid not in entity_chunk_positions:
                                entity_chunk_positions[doc_uuid] = []
                            entity_chunk_positions[doc_uuid].append(chunk_id_int)
                        except (ValueError, TypeError):
                            continue  # Ignorar chunk_id inválido
                
                # Remover duplicatas e ordenar
                for doc_uuid in entity_chunk_positions:
                    entity_chunk_positions[doc_uuid] = sorted(list(set(entity_chunk_positions[doc_uuid])))
                
                if entity_chunk_positions:
                    total_entity_chunks = sum(len(ids) for ids in entity_chunk_positions.values())
                    msg.info(f"    📍 Identificados {total_entity_chunks} chunks com entidades em {len(entity_chunk_positions)} documentos (para boost de proximidade)")
        except Exception as e:
            msg.debug(f"    Aviso: Não foi possível identificar chunks com entidades para boost de proximidade: {str(e)}")
            entity_chunk_positions = {}
        
        # FASE 2: Busca Semântica dentro de TODOS os chunks dos documentos filtrados
        msg.info(f"  🎯 Fase 2: Busca semântica em TODOS os chunks dos {len(phase1_doc_uuids)} documentos...")
        
        # Query Expansion (Fase 2: Temas)
        expanded_queries_phase2 = [search_query]  # Fallback
        
        if enable_query_expansion:
            try:
                from verba_extensions.plugins.query_expander import QueryExpanderPlugin
                query_expander = QueryExpanderPlugin(cache_ttl_seconds=cache_ttl)
                expanded_queries_phase2 = await query_expander.expand_query_for_themes(search_query, use_cache=True)
                msg.info(f"    Query Expansion (Fase 2): {len(expanded_queries_phase2)} variações")
                debug_info["query_expansion_phase2"] = expanded_queries_phase2
            except Exception as e:
                msg.debug(f"    Query Expansion não disponível: {str(e)}")
        
        # Usar primeira variação expandida (ou query original)
        phase2_query = expanded_queries_phase2[0] if expanded_queries_phase2 else search_query
        
        # Construir filtro para Fase 2: documentos filtrados + outros filtros
        phase2_filter_list = [
            Filter.by_property("doc_uuid").contains_any(phase1_doc_uuids)  # ← Filtra por DOCUMENTOS!
        ]
        
        if temporal_filter:
            phase2_filter_list.append(temporal_filter)
        if framework_filter:
            phase2_filter_list.append(framework_filter)
        if lang_filter:
            phase2_filter_list.append(lang_filter)
        
        phase2_filter = Filter.all_of(phase2_filter_list) if len(phase2_filter_list) > 1 else phase2_filter_list[0]
        
        # Multi-Vector Search ou Single Named Vector na Fase 2
        if enable_multi_vector and len(vectors_to_search) >= 2:
            try:
                from verba_extensions.plugins.multi_vector_searcher import MultiVectorSearcher
                from goldenverba.components.managers import EmbeddingManager
                
                # Gerar embedding da query
                embedding_manager = EmbeddingManager()
                
                if rag_config:
                    query_vector_phase2 = await embedding_manager.vectorize_query(
                        embedder=embedder,
                        content=phase2_query,
                        rag_config=rag_config
                    )
                else:
                    if embedder not in embedding_manager.embedders:
                        raise Exception(f"Embedder {embedder} não encontrado")
                    
                    embedder_obj = embedding_manager.embedders[embedder]
                    embedder_config = {}
                    query_embeddings = await embedder_obj.vectorize(embedder_config, [phase2_query])
                    if not query_embeddings or len(query_embeddings) == 0:
                        raise Exception("Falha ao gerar embedding da query")
                    query_vector_phase2 = query_embeddings[0]
            except Exception as e:
                msg.warn(f"Erro ao vetorizar query para multi-vector search: {str(e)}. Realizando fallback para single-vector.")
                enable_multi_vector = False
                query_vector_phase2 = vector # Use the default vector from parameters
                
                # Configurar fusion type
                enable_relative_score = get_config_value(self.config, "Enable Relative Score Fusion", True)
                fusion_type = "RELATIVE_SCORE" if enable_relative_score else "RRF"
                
                # Configurar query_properties para BM25 boosting
                query_properties = ["content", "title^2"]
                
                # Executar multi-vector search
                multi_vector_searcher = MultiVectorSearcher()
                result = await multi_vector_searcher.search_multi_vector(
                    client=client,
                    collection_name=collection_name,
                    query=phase2_query,
                    query_vector=query_vector_phase2,
                    vectors=vectors_to_search,
                    filters=phase2_filter,
                    limit=limit,
                    alpha=rewritten_alpha,
                    fusion_type=fusion_type,
                    query_properties=query_properties
                )
                
                if result and result.get("results"):
                    phase2_uuids = [r.get("_uuid") for r in result["results"] if r.get("_uuid")]
                    
                    if phase2_uuids:
                        collection = client.collections.get(collection_name)
                        phase2_objects = await collection.query.fetch_objects(
                            filters=Filter.by_property("uuid").contains_any(phase2_uuids)
                        )
                        
                        if phase2_objects and hasattr(phase2_objects, 'objects'):
                            phase2_chunks = phase2_objects.objects
                            
                            # 🎯 APLICAR BOOST DE PROXIMIDADE também no multi-vector
                            if entity_chunk_positions:
                                boosted_chunks = self._apply_proximity_boost(
                                    phase2_chunks, 
                                    entity_chunk_positions,
                                    proximity_window=2
                                )
                                phase2_chunks = boosted_chunks[:limit]  # Limitar ao número solicitado
                                msg.info(f"    📍 Boost de proximidade aplicado (multi-vector)")
                            
                            msg.good(f"    Fase 2: {len(phase2_chunks)} chunks retornados (multi-vector)")
                            debug_info["two_phase_search"]["phase2_results"] = len(phase2_chunks)
                            debug_info["two_phase_search"]["fusion_type"] = fusion_type
                            if entity_chunk_positions:
                                debug_info["two_phase_search"]["proximity_boost_applied"] = True
                            
                            return phase2_chunks
            except Exception as e:
                msg.warn(f"    Fase 2: Erro em multi-vector search: {str(e)}")
        
        # Fallback: busca híbrida simples na Fase 2
        target_vector_phase2 = None
        if len(vectors_to_search) == 1:
            target_vector_phase2 = vectors_to_search[0]
            msg.info(f"    Fase 2: Usando target_vector único: {target_vector_phase2}")
        
        # Busca híbrida normal dentro dos documentos filtrados
        # Aumentar limit temporariamente para ter mais chunks para aplicar boost de proximidade
        phase2_limit = limit * 2 if entity_chunk_positions else limit  # Buscar mais se temos chunks com entidades
        
        phase2_chunks = await weaviate_manager.hybrid_chunks_with_filter(
            client=client,
            embedder=embedder,
            query=phase2_query,
            vector=vector,
            limit_mode=limit_mode,
            limit=phase2_limit,
            labels=labels,
            document_uuids=phase1_doc_uuids,  # ← Filtrar por documentos, não por UUIDs de chunks
            filters=phase2_filter,
            alpha=rewritten_alpha,
            target_vector=target_vector_phase2,
        )
        
        if phase2_chunks:
            # 🎯 APLICAR BOOST DE PROXIMIDADE: Priorizar chunks adjacentes aos que mencionam entidades
            if entity_chunk_positions:
                boosted_chunks = self._apply_proximity_boost(
                    phase2_chunks, 
                    entity_chunk_positions,
                    proximity_window=2  # Considerar chunks ±2 posições
                )
                phase2_chunks = boosted_chunks
                
                # Limitar ao número original solicitado
                phase2_chunks = phase2_chunks[:limit]
                
                # Log apenas se houver boost aplicado
                if len(boosted_chunks) != len(phase2_chunks):
                    msg.info(f"    📍 Boost de proximidade aplicado: priorizou chunks próximos aos que mencionam entidades")
            
            msg.good(f"    Fase 2: {len(phase2_chunks)} chunks retornados dos {len(phase1_doc_uuids)} documentos")
            debug_info["two_phase_search"]["phase2_results"] = len(phase2_chunks)
            if entity_chunk_positions:
                debug_info["two_phase_search"]["proximity_boost_applied"] = True
            return phase2_chunks
        else:
            msg.warn(f"    Fase 2: Nenhum chunk retornado")
            return []
            
    except Exception as e:
        msg.warn(f"  Erro em Two-Phase Search (Document-Level): {str(e)}")
        import traceback
        traceback.print_exc()
        return []

