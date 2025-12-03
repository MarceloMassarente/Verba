"""
Integração: Hook no import_document para capturar passage_uuids
e disparar ETL A2 após importação

⚠️ PATCH/MONKEY PATCH - Documentado em verba_extensions/patches/README_PATCHES.md

Este é um monkey patch que modifica WeaviateManager.import_document() sem alterar código original.
Ao atualizar Verba, verificar se método ainda existe e reaplicar se necessário.

Aplicado via: verba_extensions/startup.py (durante inicialização)
"""

import os
import json
from typing import List, Dict, Set, Optional, Any
from wasabi import msg

# Track ETL executions to prevent duplicates
_etl_executions_in_progress: Set[str] = set()

# Store logger per doc_uuid for ETL completion notifications
_logger_registry: Dict[str, any] = {}  # doc_uuid -> LoggerManager


async def _map_framework_properties_to_weaviate(
    client,
    collection_name: str,
    chunk_properties: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Mapeia propriedades de framework do chunk.meta para propriedades do Weaviate.
    
    Se collection tem propriedades de framework, adiciona diretamente.
    Caso contrário, salva em meta JSON como fallback.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection
        chunk_properties: Propriedades do chunk (de chunk.to_json())
    
    Returns:
        Propriedades atualizadas com frameworks
    """
    try:
        from verba_extensions.integration.schema_validator import collection_has_framework_properties
        
        # Verifica se collection tem propriedades de framework
        has_framework_props = await collection_has_framework_properties(client, collection_name)
        
        # Extrai meta do chunk
        meta_str = chunk_properties.get("meta", "{}")
        try:
            meta = json.loads(meta_str) if isinstance(meta_str, str) else (meta_str or {})
        except:
            meta = {}
        
        # Extrai frameworks do meta
        frameworks = meta.get("frameworks", [])
        companies = meta.get("companies", [])
        sectors = meta.get("sectors", [])
        framework_confidence = meta.get("framework_confidence", 0.0)
        
        if has_framework_props:
            # Collection tem propriedades de framework - adiciona diretamente
            chunk_properties["frameworks"] = frameworks
            chunk_properties["companies"] = companies
            chunk_properties["sectors"] = sectors
            chunk_properties["framework_confidence"] = framework_confidence
        else:
            # Fallback: salva em meta JSON (já está lá, mas garante que está)
            if frameworks or companies or sectors:
                meta["frameworks"] = frameworks
                meta["companies"] = companies
                meta["sectors"] = sectors
                meta["framework_confidence"] = framework_confidence
                chunk_properties["meta"] = json.dumps(meta)
        
        return chunk_properties
        
    except Exception as e:
        # Erro não crítico - retorna propriedades originais
        msg.debug(f"[Framework-Mapping] Erro ao mapear frameworks (não crítico): {str(e)}")
        return chunk_properties


async def _map_v019_properties_to_weaviate(
    client,
    collection_name: str,
    chunk_properties: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Mapeia propriedades V019 do chunk.meta para propriedades do Weaviate.
    
    Se collection tem propriedades V019, adiciona diretamente.
    Caso contrário, salva em meta JSON como fallback.
    
    Propriedades V019:
    - semantic_bridge_quality: Qualidade da ponte semântica (0.0-1.0)
    - slide_position: Posição no deck (opening, diagnostic, etc.)
    - slide_type: Tipo do slide (complex, simple, metadata)
    - pattern_genetics: Array de componentes atômicos
    - reusability_score: Score de reusabilidade (0-100)
    - visual_archetype: Arquétipo visual (pyramid, matrix, etc.)
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection
        chunk_properties: Propriedades do chunk (de chunk.to_json())
    
    Returns:
        Propriedades atualizadas com V019
    """
    try:
        from verba_extensions.integration.schema_validator import collection_has_v019_properties
        
        # Verifica se collection tem propriedades V019
        has_v019_props = await collection_has_v019_properties(client, collection_name)
        
        if not has_v019_props:
            # Collection não tem propriedades V019 - não faz nada (metadata fica em meta JSON)
            return chunk_properties
        
        # Extrai meta do chunk
        meta_str = chunk_properties.get("meta", "{}")
        try:
            meta = json.loads(meta_str) if isinstance(meta_str, str) else (meta_str or {})
        except:
            meta = {}
        
        # Extrai propriedades V019 do meta
        # Pode vir de slides_metadata ou diretamente do meta
        semantic_bridge_quality = meta.get("semantic_bridge_quality")
        slide_position = meta.get("slide_position")
        slide_type = meta.get("slide_type")
        pattern_genetics = meta.get("pattern_genetics", [])
        reusability_score = meta.get("reusability_score")
        visual_archetype = meta.get("visual_archetype")
        
        # Se não encontrou diretamente, tenta extrair de slides_metadata
        # (para chunks que correspondem a slides específicos)
        if not any([semantic_bridge_quality, slide_position, slide_type, pattern_genetics, reusability_score, visual_archetype]):
            slides_metadata = meta.get("slides_metadata", [])
            if slides_metadata and len(slides_metadata) > 0:
                # Usa metadata do primeiro slide (para chunks únicos)
                # Para chunks múltiplos, o metadata já deveria estar no nível do chunk
                first_slide = slides_metadata[0]
                semantic_bridge_quality = first_slide.get("semantic_bridge_quality")
                slide_position = first_slide.get("slide_position")
                slide_type = first_slide.get("slide_type")
                pattern_genetics = first_slide.get("pattern_genetics", [])
                reusability_score = first_slide.get("reusability_score")
                visual_archetype = first_slide.get("visual_archetype")
        
        # Adiciona propriedades V019 diretamente (collection já foi verificada)
        if semantic_bridge_quality is not None:
            chunk_properties["semantic_bridge_quality"] = float(semantic_bridge_quality)
        if slide_position:
            chunk_properties["slide_position"] = str(slide_position)
        if slide_type:
            chunk_properties["slide_type"] = str(slide_type)
        if pattern_genetics:
            chunk_properties["pattern_genetics"] = pattern_genetics if isinstance(pattern_genetics, list) else [pattern_genetics]
        if reusability_score is not None:
            chunk_properties["reusability_score"] = float(reusability_score)
        if visual_archetype:
            chunk_properties["visual_archetype"] = str(visual_archetype)
        
        return chunk_properties
        
    except Exception as e:
        # Erro não crítico - retorna propriedades originais
        msg.debug(f"[V019-Mapping] Erro ao mapear propriedades V019 (não crítico): {str(e)}")
        return chunk_properties

def cleanup_etl_state(doc_uuid: str):
    """
    Limpa estado global de ETL para garantir que próximos imports não sejam afetados.
    Chamado no finally block para garantir execução mesmo com exceção.
    """
    try:
        _etl_executions_in_progress.discard(doc_uuid)
        _logger_registry.pop(doc_uuid, None)
    except Exception:
        pass  # Silently ignore cleanup errors

def patch_weaviate_manager():
    """
    Aplica patch no WeaviateManager.import_document para capturar passage_uuids
    e disparar ETL via hook
    """
    try:
        from goldenverba.components import managers
        
        # Guarda método original
        original_import = managers.WeaviateManager.import_document
        
        async def patched_import_document(
            self,
            client,
            document: "Document",
            embedder: str,
        ):
            """Importa documento e captura passage_uuids para ETL"""
            # VERIFICAÇÃO DE SAÚDE: Garante que cliente está pronto
            try:
                if not await client.is_ready():
                    msg.warn("[ETL-HEALTH] ⚠️ Cliente não está pronto para import - tentando reconectar")
                    if hasattr(client, 'connect'):
                        try:
                            await client.connect()
                            if await client.is_ready():
                                msg.good("[ETL-HEALTH] ✅ Reconexão bem-sucedida")
                            else:
                                msg.warn("[ETL-HEALTH] ⚠️ Cliente reconectado mas ainda não ready")
                        except Exception as e:
                            msg.warn(f"[ETL-HEALTH] ⚠️ Erro ao reconectar: {str(e)[:100]}")
            except Exception as e:
                msg.warn(f"[ETL-HEALTH] ⚠️ Erro ao verificar saúde do cliente: {str(e)[:100]}")
            
            # Verifica se ETL está habilitado ANTES de importar
            # Padrão: True (ETL sempre ativo por padrão, a menos que explicitamente desabilitado)
            enable_etl = document.meta.get("enable_etl", True) if hasattr(document, 'meta') and document.meta else True
            
            # Tenta obter logger do document.meta (passado temporariamente por process_single_document)
            logger = document.meta.get("_temp_logger") if hasattr(document, 'meta') and document.meta else None
            file_id = document.meta.get("file_id") if hasattr(document, 'meta') and document.meta else None
            
            # Remove logger de document.meta IMEDIATAMENTE após usar para evitar problemas de serialização
            # (não deve estar presente quando documento for serializado em JSON)
            if hasattr(document, 'meta') and document.meta:
                document.meta.pop('_temp_logger', None)
            
            # Se não há meta ou não tem enable_etl, assume True (ETL universal)
            if not hasattr(document, 'meta') or not document.meta:
                enable_etl = True
            elif "enable_etl" not in document.meta:
                # Se não especificado, assume True para aplicar ETL universalmente
                enable_etl = True
            
            # Importa Filter antes (necessário para recuperação)
            try:
                from weaviate.classes.query import Filter
            except ImportError:
                # Fallback para v3 - usa estrutura de filtro v3
                Filter = None
            
            # Helper para verificar se cliente está conectado
            def _is_client_connected(client):
                """Verifica se cliente está conectado de forma segura"""
                try:
                    # Tenta acessar uma propriedade que só existe se conectado
                    # Se o cliente está fechado, isso lançará uma exceção
                    _ = client.collections
                    return True
                except (AttributeError, RuntimeError, Exception) as e:
                    error_str = str(e).lower()
                    if "closed" in error_str or "not connected" in error_str or "disconnect" in error_str:
                        return False
                    # Outros erros podem indicar problema diferente, mas assumimos desconectado
                    return False
            
            # Helper para obter novo cliente se necessário
            async def _get_working_client():
                """Obtém cliente funcionando, reconecta automaticamente se necessário"""
                if _is_client_connected(client):
                    return client
                
                # Cliente fechado - tenta reconectar usando credenciais do ambiente ou manager
                msg.warn("[ETL-POST] Cliente fechado, tentando reconectar automaticamente...")
                try:
                    # Tenta obter credenciais de várias fontes
                    deployment = os.getenv("DEFAULT_DEPLOYMENT", "Custom")
                    
                    # Prioridade: WEAVIATE_HTTP_HOST (Railway interno) > WEAVIATE_URL_VERBA > other
                    http_host = os.getenv("WEAVIATE_HTTP_HOST")
                    url = os.getenv("WEAVIATE_URL_VERBA")
                    
                    # Se temos WEAVIATE_HTTP_HOST (Railway), usa ele com configuração Custom
                    if http_host:
                        url = http_host
                        deployment = "Custom"
                        port = os.getenv("WEAVIATE_HTTP_PORT", "8080")
                    else:
                        port = os.getenv("WEAVIATE_PORT", "8080")
                    
                    key = os.getenv("WEAVIATE_API_KEY_VERBA", "")
                    
                    if not url:
                        msg.warn("[ETL-POST] Não foi possível determinar URL do Weaviate para reconexão")
                        return None
                    
                    # Reconecta usando o manager
                    from goldenverba.components import managers
                    weaviate_manager = managers.WeaviateManager()
                    
                    # Tenta reconectar baseado no deployment type
                    if deployment == "Custom":
                        new_client = await weaviate_manager.connect_to_custom(url, key, port)
                    elif deployment == "Weaviate":
                        new_client = await weaviate_manager.connect_to_cluster(url, key)
                    else:
                        msg.warn(f"[ETL-POST] Deployment type '{deployment}' não suportado para reconexão automática")
                        return None
                    
                    # Verifica se conectou
                    if new_client:
                        # Cliente v4 já está conectado, mas verificamos
                        try:
                            if hasattr(new_client, 'connect'):
                                await new_client.connect()
                            if await new_client.is_ready():
                                msg.good("[ETL-POST] ✅ Reconectado automaticamente com sucesso")
                                return new_client
                        except Exception as e:
                            msg.warn(f"[ETL-POST] Cliente reconectado mas não está pronto: {str(e)}")
                    
                    return None
                except Exception as e:
                    msg.warn(f"[ETL-POST] Erro ao tentar reconectar: {str(e)}")
                    return None
            
            # Mapeia frameworks e V019 para propriedades do Weaviate ANTES de importar
            # Verifica se collection tem propriedades de framework e V019
            embedder_collection_name = self.embedding_table.get(embedder)
            has_framework_props = False
            has_v019_props = False
            has_named_vectors = False
            if embedder_collection_name:
                try:
                    from verba_extensions.integration.schema_validator import (
                        collection_has_framework_properties,
                        collection_has_v019_properties
                    )
                    has_framework_props = await collection_has_framework_properties(client, embedder_collection_name)
                    has_v019_props = await collection_has_v019_properties(client, embedder_collection_name)
                    
                    # Verifica se collection tem named vectors
                    try:
                        collection = client.collections.get(embedder_collection_name)
                        config = await collection.config.get()
                        has_named_vectors = hasattr(config, 'vector_config') and config.vector_config is not None
                    except:
                        pass
                except Exception as e:
                    msg.debug(f"[Mapping] Erro ao verificar propriedades (não crítico): {str(e)}")
            
            # Chama método original (NÃO retorna doc_uuid - método original não retorna)
            # Precisamos buscar doc_uuid após o import
            doc_uuid = None
            try:
                # Patch temporário: intercepta criação de DataObjects para mapear frameworks e named vectors
                from weaviate.collections.classes.data import DataObject
                original_data_object_init = DataObject.__init__
                
                # Armazena resultado da verificação para usar no patch
                _has_framework_props = has_framework_props
                _has_v019_props = has_v019_props
                _has_named_vectors = has_named_vectors
                _embedder_collection_name = embedder_collection_name
                
                def patched_data_object_init(self, *args, **kwargs):
                    """Patch DataObject para mapear frameworks, V019 e named vectors antes de inserir"""
                    # Chama init original
                    original_data_object_init(self, *args, **kwargs)
                    
                    # Se collection tem propriedades de framework, mapeia de meta para properties
                    if _has_framework_props and hasattr(self, 'properties') and self.properties:
                        try:
                            # Mapeia frameworks de meta para propriedades diretas
                            meta_str = self.properties.get("meta", "{}")
                            try:
                                meta = json.loads(meta_str) if isinstance(meta_str, str) else (meta_str or {})
                            except:
                                meta = {}
                            
                            frameworks = meta.get("frameworks", [])
                            companies = meta.get("companies", [])
                            sectors = meta.get("sectors", [])
                            framework_confidence = meta.get("framework_confidence", 0.0)
                            
                            # Adiciona diretamente às properties (collection já foi verificada)
                            if frameworks or companies or sectors or framework_confidence > 0:
                                self.properties["frameworks"] = frameworks
                                self.properties["companies"] = companies
                                self.properties["sectors"] = sectors
                                self.properties["framework_confidence"] = framework_confidence
                        except Exception as e:
                            msg.debug(f"[Framework-Mapping] Erro ao mapear em DataObject (não crítico): {str(e)}")
                    
                    # Se collection tem propriedades V019, mapeia de meta para properties
                    if _has_v019_props and hasattr(self, 'properties') and self.properties:
                        try:
                            # Mapeia propriedades V019 de meta para propriedades diretas
                            meta_str = self.properties.get("meta", "{}")
                            try:
                                meta = json.loads(meta_str) if isinstance(meta_str, str) else (meta_str or {})
                            except:
                                meta = {}
                            
                            # Extrai propriedades V019
                            semantic_bridge_quality = meta.get("semantic_bridge_quality")
                            slide_position = meta.get("slide_position")
                            slide_type = meta.get("slide_type")
                            pattern_genetics = meta.get("pattern_genetics", [])
                            reusability_score = meta.get("reusability_score")
                            visual_archetype = meta.get("visual_archetype")
                            
                            # Se não encontrou diretamente, tenta extrair de slides_metadata
                            if not any([semantic_bridge_quality, slide_position, slide_type, pattern_genetics, reusability_score, visual_archetype]):
                                slides_metadata = meta.get("slides_metadata", [])
                                if slides_metadata and len(slides_metadata) > 0:
                                    first_slide = slides_metadata[0]
                                    semantic_bridge_quality = first_slide.get("semantic_bridge_quality")
                                    slide_position = first_slide.get("slide_position")
                                    slide_type = first_slide.get("slide_type")
                                    pattern_genetics = first_slide.get("pattern_genetics", [])
                                    reusability_score = first_slide.get("reusability_score")
                                    visual_archetype = first_slide.get("visual_archetype")
                            
                            # Adiciona diretamente às properties (collection já foi verificada)
                            if semantic_bridge_quality is not None:
                                self.properties["semantic_bridge_quality"] = float(semantic_bridge_quality)
                            if slide_position:
                                self.properties["slide_position"] = str(slide_position)
                            if slide_type:
                                self.properties["slide_type"] = str(slide_type)
                            if pattern_genetics:
                                self.properties["pattern_genetics"] = pattern_genetics if isinstance(pattern_genetics, list) else [pattern_genetics]
                            if reusability_score is not None:
                                self.properties["reusability_score"] = float(reusability_score)
                            if visual_archetype:
                                self.properties["visual_archetype"] = str(visual_archetype)
                        except Exception as e:
                            msg.debug(f"[V019-Mapping] Erro ao mapear V019 em DataObject (não crítico): {str(e)}")
                    
                    # Named vectors: adiciona textos especializados às properties
                    # (os vetores serão adicionados antes de criar o DataObject)
                    if _has_named_vectors and hasattr(self, 'properties') and self.properties:
                        try:
                            # Extrai textos especializados do meta
                            meta_str = self.properties.get("meta", "{}")
                            try:
                                meta = json.loads(meta_str) if isinstance(meta_str, str) else (meta_str or {})
                            except:
                                meta = {}
                            
                            # Se já tem concept_text, sector_text, company_text no meta, usa eles
                            # Caso contrário, extrai do conteúdo
                            if "concept_text" in meta:
                                self.properties["concept_text"] = meta["concept_text"]
                            if "sector_text" in meta:
                                self.properties["sector_text"] = meta["sector_text"]
                            if "company_text" in meta:
                                self.properties["company_text"] = meta["company_text"]
                        except Exception as e:
                            msg.debug(f"[Named-Vectors] Erro ao mapear textos especializados (não crítico): {str(e)}")
                
                # Aplica patch temporário
                DataObject.__init__ = patched_data_object_init
                
                # Se tem named vectors, gera embeddings adicionais usando o mesmo embedder do Verba
                # BYOV mode: Verba gera embeddings, Weaviate apenas armazena
                if has_named_vectors and hasattr(document, 'chunks') and document.chunks:
                    try:
                        from verba_extensions.utils.vector_extractor import get_vector_extractor
                        vector_extractor = get_vector_extractor()
                        
                        # Obtém instância do embedder para gerar embeddings (mesmo usado para default)
                        from goldenverba.components import managers
                        embedding_manager = managers.EmbeddingManager()
                        
                        if embedder not in embedding_manager.embedders:
                            msg.warn(f"[Named-Vectors] Embedder '{embedder}' não encontrado - named vectors não serão gerados")
                        else:
                            embedder_instance = embedding_manager.embedders[embedder]
                            msg.info(f"[Named-Vectors] 🎯 Gerando embeddings para named vectors usando {embedder} (BYOV)")
                            
                            # Extrai textos especializados e gera embeddings para cada chunk
                            for chunk_idx, chunk in enumerate(document.chunks):
                                try:
                                    # Extrai textos especializados
                                    if not hasattr(chunk, 'meta') or not chunk.meta:
                                        chunk.meta = {}
                                    
                                    texts = vector_extractor.extract_all_texts(chunk)
                                    chunk.meta["concept_text"] = texts["concept_text"]
                                    chunk.meta["sector_text"] = texts["sector_text"]
                                    chunk.meta["company_text"] = texts["company_text"]
                                    
                                    # Gera embeddings para cada texto especializado usando o mesmo embedder
                                    # Isso mantém consistência: mesmo modelo usado para default e named vectors
                                    named_vectors = {
                                        "default": chunk.vector  # Vetor padrão já existe
                                    }
                                    
                                    # Gera embedding para concept_vec
                                    # Sempre cria named vector (usa default se texto vazio)
                                    if texts["concept_text"]:
                                        try:
                                            # Usa vectorize (não embed) - método correto da interface Embedding
                                            concept_embeddings = await embedder_instance.vectorize(
                                                config,
                                                [texts["concept_text"]]
                                            )
                                            named_vectors["concept_vec"] = concept_embeddings[0]
                                        except Exception as e:
                                            msg.debug(f"[Named-Vectors] Erro ao gerar concept_vec para chunk {chunk_idx}: {str(e)}")
                                            # Fallback: usa vetor padrão
                                            named_vectors["concept_vec"] = chunk.vector
                                    else:
                                        # Texto vazio: usa vetor padrão como fallback
                                        named_vectors["concept_vec"] = chunk.vector
                                    
                                    # Gera embedding para sector_vec
                                    # Sempre cria named vector (usa default se texto vazio)
                                    if texts["sector_text"]:
                                        try:
                                            # Usa vectorize (não embed) - método correto da interface Embedding
                                            sector_embeddings = await embedder_instance.vectorize(
                                                config,
                                                [texts["sector_text"]]
                                            )
                                            named_vectors["sector_vec"] = sector_embeddings[0]
                                        except Exception as e:
                                            msg.debug(f"[Named-Vectors] Erro ao gerar sector_vec para chunk {chunk_idx}: {str(e)}")
                                            # Fallback: usa vetor padrão
                                            named_vectors["sector_vec"] = chunk.vector
                                    else:
                                        # Texto vazio: usa vetor padrão como fallback
                                        named_vectors["sector_vec"] = chunk.vector
                                    
                                    # Gera embedding para company_vec
                                    # Sempre cria named vector (usa default se texto vazio)
                                    if texts["company_text"]:
                                        try:
                                            # Usa vectorize (não embed) - método correto da interface Embedding
                                            company_embeddings = await embedder_instance.vectorize(
                                                config,
                                                [texts["company_text"]]
                                            )
                                            named_vectors["company_vec"] = company_embeddings[0]
                                        except Exception as e:
                                            msg.debug(f"[Named-Vectors] Erro ao gerar company_vec para chunk {chunk_idx}: {str(e)}")
                                            # Fallback: usa vetor padrão
                                            named_vectors["company_vec"] = chunk.vector
                                    else:
                                        # Texto vazio: usa vetor padrão como fallback
                                        named_vectors["company_vec"] = chunk.vector
                                    
                                    # Armazena named vectors no chunk para uso no DataObject
                                    chunk._named_vectors = named_vectors
                                    
                                    # Também armazena em dict global usando uuid ou content como chave
                                    chunk_key = getattr(chunk, 'uuid', None) or (chunk.content[:100] if hasattr(chunk, 'content') else f"chunk_{chunk_idx}")
                                    _chunk_named_vectors[chunk_key] = named_vectors
                                    
                                except Exception as e:
                                    msg.warn(f"[Named-Vectors] Erro ao processar chunk {chunk_idx} (não crítico): {str(e)}")
                                    # Fallback: chunk sem named vectors (usa apenas default)
                                    if hasattr(chunk, 'vector'):
                                        chunk._named_vectors = {"default": chunk.vector}
                            
                            msg.good(f"[Named-Vectors] ✅ Embeddings gerados para {len([c for c in document.chunks if hasattr(c, '_named_vectors')])} chunks (BYOV)")
                            
                    except Exception as e:
                        msg.warn(f"[Named-Vectors] Erro ao gerar embeddings para named vectors (não crítico): {str(e)}")
                        import traceback
                        msg.debug(f"[Named-Vectors] Traceback: {traceback.format_exc()}")
                
                # Para named vectors, modifica temporariamente os chunks para usar dict de named vectors
                # Isso permite que o código original funcione sem modificações
                original_chunk_vectors = {}
                if has_named_vectors and hasattr(document, 'chunks'):
                    # Armazena vectors originais e substitui temporariamente por dict de named vectors
                    for chunk in document.chunks:
                        if hasattr(chunk, '_named_vectors') and chunk._named_vectors:
                            original_chunk_vectors[id(chunk)] = chunk.vector
                            # Substitui temporariamente chunk.vector por dict de named vectors
                            chunk.vector = chunk._named_vectors
                            msg.debug(f"[Named-Vectors] Chunk {id(chunk)} usando named vectors")
                
                try:
                    await original_import(self, client, document, embedder)
                finally:
                    # Restaura vectors originais dos chunks
                    for chunk in document.chunks:
                        chunk_id = id(chunk)
                        if chunk_id in original_chunk_vectors:
                            chunk.vector = original_chunk_vectors[chunk_id]
                    
                    # Restaura método original
                    DataObject.__init__ = original_data_object_init
                # Método original não retorna doc_uuid, então buscamos pelo título
                if Filter is not None:
                    try:
                        import asyncio
                        # Verifica se cliente ainda está conectado após import
                        if not _is_client_connected(client):
                            msg.warn("[ETL-POST] Cliente fechado após import - tentando reconectar...")
                            working_client = await _get_working_client()
                            if not working_client:
                                msg.warn("[ETL-POST] Não foi possível reconectar - doc_uuid não será obtido")
                                doc_uuid = None
                            else:
                                client = working_client
                        
                        if _is_client_connected(client):
                            # Tenta buscar doc_uuid com retry (pode levar um pouco para o Weaviate commit)
                            document_collection = client.collections.get(self.document_collection_name)
                            doc_uuid = None
                            max_retries = 3
                            for attempt in range(max_retries):
                                if attempt > 0:
                                    await asyncio.sleep(0.2)  # Delay entre tentativas
                                
                                results = await document_collection.query.fetch_objects(
                                    filters=Filter.by_property("title").equal(document.title),
                                    limit=1
                                )
                                if results.objects:
                                    doc_uuid = str(results.objects[0].uuid)
                                    msg.info(f"[ETL-POST] ✅ doc_uuid obtido após import (tentativa {attempt + 1}): {doc_uuid[:50]}...")
                                    break
                            
                            if not doc_uuid:
                                msg.warn(f"[ETL-POST] ⚠️ Documento '{document.title}' não encontrado após {max_retries} tentativas - ETL não será executado")
                            else:
                                # Armazena logger para uso no hook ETL (já vem do document.meta)
                                if logger is not None:
                                    _logger_registry[doc_uuid] = logger
                                    temp_doc_uuid_for_logger = doc_uuid
                        else:
                            msg.warn("[ETL-POST] Cliente não conectado - não é possível buscar doc_uuid")
                    except Exception as recovery_error:
                        error_str = str(recovery_error).lower()
                        if "closed" in error_str or "not connected" in error_str:
                            msg.warn("[ETL-POST] ⚠️ Cliente fechado durante busca de doc_uuid - ETL não será executado")
                        else:
                            msg.warn(f"[ETL-POST] ⚠️ Erro ao buscar doc_uuid após import: {str(recovery_error)}")
            except Exception as import_error:
                # Se falhar, tenta recuperar doc_uuid pela busca do documento
                # (alguns chunks podem ter sido inseridos mesmo com erro)
                error_str = str(import_error).lower()
                msg.warn(f"[ETL-POST] Import teve erro: {str(import_error)[:100]}")
                
                # Verifica se o cliente está conectado antes de tentar recuperar
                if Filter is not None and _is_client_connected(client):
                    try:
                        # Tenta buscar documento pelo nome para recuperar doc_uuid
                        document_collection = client.collections.get(self.document_collection_name)
                        results = await document_collection.query.fetch_objects(
                            filters=Filter.by_property("title").equal(document.title),
                            limit=1
                        )
                        if results.objects:
                            doc_uuid = str(results.objects[0].uuid)
                            msg.info(f"[ETL-POST] Recuperado doc_uuid após erro: {doc_uuid[:50]}...")
                    except Exception as recovery_error:
                        # Se o erro for de cliente fechado, não tenta recuperar
                        recovery_str = str(recovery_error).lower()
                        if "closed" in recovery_str or "not connected" in recovery_str:
                            msg.warn("[ETL-POST] Cliente fechado durante recuperação, não foi possível recuperar doc_uuid")
                        else:
                            msg.warn(f"[ETL-POST] Não foi possível recuperar doc_uuid: {str(recovery_error)}")
                elif not _is_client_connected(client):
                    msg.warn("[ETL-POST] Cliente não está conectado, não é possível recuperar doc_uuid")
                # Re-raise para não mascarar o erro original
                raise import_error
            
            # Se ETL habilitado e doc_uuid obtido, dispara ETL
            msg.info(f"[ETL-POST] Verificando ETL pós-chunking: enable_etl={enable_etl}, doc_uuid={'present' if doc_uuid else 'None'}")
            if enable_etl and doc_uuid:
                try:
                    import asyncio
                    
                    # Verifica se cliente está conectado antes de tentar ETL
                    working_client = await _get_working_client()
                    if not working_client:
                        msg.warn("[ETL-POST] Cliente não conectado - ETL pós-chunking será pulado (chunks já foram importados)")
                        msg.warn("[ETL-POST] ETL pode ser executado manualmente mais tarde ou após reconexão")
                    else:
                        client = working_client
                        msg.info(f"[ETL-POST] ETL A2 habilitado - buscando chunks importados para doc_uuid: {doc_uuid[:50]}...")
                        embedder_collection_name = self.embedding_table.get(embedder)
                        if embedder_collection_name:
                            try:
                                embedder_collection = client.collections.get(embedder_collection_name)
                                
                                # Pequeno delay para garantir que chunks foram inseridos
                                await asyncio.sleep(0.2)
                                
                                # Busca passages por doc_uuid
                                msg.info(f"[ETL] Buscando passages no Weaviate após import...")
                                passages = await embedder_collection.query.fetch_objects(
                                    filters=Filter.by_property("doc_uuid").equal(doc_uuid),
                                    limit=10000
                                )
                                
                                passage_uuids = [str(p.uuid) for p in passages.objects]
                                
                                if passage_uuids:
                                    # Verifica se ETL já está em execução para este doc_uuid
                                    # Usa lock thread-safe para evitar race conditions
                                    if doc_uuid not in _etl_executions_in_progress:
                                        # Marca como em execução ANTES de iniciar task
                                        _etl_executions_in_progress.add(doc_uuid)
                                        
                                        msg.info(f"[ETL] ✅ {len(passage_uuids)} chunks encontrados - executando ETL A2 (NER + Section Scope) em background")
                                        # Dispara ETL via hook (async, não bloqueia import)
                                        from verba_extensions.hooks import global_hooks
                                        tenant = os.getenv("WEAVIATE_TENANT")
                                        
                                        # Executa em background para não bloquear
                                        async def run_etl_hook():
                                            # Obtém cliente novamente dentro da task (pode ter fechado)
                                            # Usa retry com reconexão automática
                                            hook_client = None
                                            max_retries = 3
                                            for retry in range(max_retries):
                                                hook_client = await _get_working_client()
                                                if hook_client:
                                                    break
                                                if retry < max_retries - 1:
                                                    await asyncio.sleep(1)  # Aguarda antes de tentar novamente
                                                    msg.info(f"[ETL] Tentando reconectar (tentativa {retry + 2}/{max_retries})...")
                                            
                                            if not hook_client:
                                                msg.warn("[ETL] ⚠️ Não foi possível reconectar após múltiplas tentativas - ETL será pulado")
                                                msg.warn("[ETL] Chunks já foram importados com sucesso, mas ETL pós-chunking não será executado")
                                                # Limpa estado do ETL
                                                cleanup_etl_state(doc_uuid)
                                                return
                                            
                                            msg.info(f"[ETL] 🚀 Iniciando ETL A2 em background para {len(passage_uuids)} chunks")
                                            try:
                                                # Passa logger via kwargs para o hook poder notificar conclusão
                                                etl_logger = _logger_registry.get(doc_uuid)
                                                await global_hooks.execute_hook_async(
                                                    'import.after',
                                                    hook_client,
                                                    doc_uuid,
                                                    passage_uuids,
                                                    tenant=tenant,
                                                    enable_etl=True,
                                                    collection_name=embedder_collection_name,  # Passa nome da collection
                                                    logger=etl_logger,  # Passa logger para notificação
                                                    file_id=file_id  # Para notificação
                                                )
                                                msg.good(f"[ETL] ✅ ETL A2 concluído para {len(passage_uuids)} chunks")
                                            except Exception as etl_error:
                                                error_str = str(etl_error).lower()
                                                # Categoriza erros para logging apropriado
                                                if "closed" in error_str or "not connected" in error_str or "disconnect" in error_str:
                                                    msg.warn(f"[ETL] ⚠️ ETL A2 falhou: cliente desconectado durante execução (não crítico)")
                                                elif any(keyword in error_str for keyword in [
                                                    "property", "schema", "field", "missing", "not found",
                                                    "does not exist", "unknown property", "attributeerror"
                                                ]):
                                                    # Erros de schema/propriedades - são esperados e não críticos
                                                    msg.info(f"[ETL] ⚠️ ETL A2 pulado: schema/propriedade não encontrada (não crítico)")
                                                else:
                                                    # Outros erros - logar mas não falhar
                                                    import traceback
                                                    msg.warn(f"[ETL] ⚠️ ETL A2 falhou (não crítico): {type(etl_error).__name__}: {str(etl_error)[:200]}")
                                                    # Log traceback apenas para erros não esperados
                                                    if "schema" not in error_str and "property" not in error_str:
                                                        msg.warn(f"[ETL] Traceback: {traceback.format_exc()[:500]}")
                                            finally:
                                                # Remove da lista de execuções em progresso
                                                # Usa cleanup_etl_state para garantir limpeza completa
                                                cleanup_etl_state(doc_uuid)
                                        
                                        asyncio.create_task(run_etl_hook())
                                    else:
                                        # ETL já está em execução para este doc_uuid (evita execução duplicada)
                                        msg.info(f"[ETL] ℹ️ ETL já está em execução para este doc_uuid")
                                else:
                                    msg.warn(f"[ETL] ⚠️ Nenhum chunk encontrado para doc_uuid {doc_uuid[:50]}... - ETL não será executado")
                            except Exception as collection_error:
                                error_str = str(collection_error).lower()
                                if "closed" in error_str or "not connected" in error_str:
                                    msg.warn("[ETL-POST] Cliente fechado durante busca de chunks - ETL não será executado")
                                else:
                                    raise
                                
                except Exception as e:
                    # Não falha o import se ETL der erro
                    import traceback
                    error_str = str(e).lower()
                    # Categoriza erros para logging apropriado
                    if "closed" in error_str or "not connected" in error_str or "disconnect" in error_str:
                        msg.warn("[ETL-POST] Cliente desconectado - ETL pós-chunking não executado (não crítico)")
                    elif any(keyword in error_str for keyword in [
                        "property", "schema", "field", "missing", "not found",
                        "does not exist", "unknown property", "attributeerror"
                    ]):
                        # Erros de schema/propriedades - são esperados e não críticos
                        msg.info("[ETL-POST] ETL A2 pulado: schema/propriedade não encontrada (não crítico)")
                    else:
                        # Outros erros - logar mas não falhar
                        msg.warn(f"[ETL-POST] ETL A2 não executado (não crítico): {type(e).__name__}: {str(e)[:200]}")
                        # Log traceback apenas para erros não esperados
                        if "schema" not in error_str and "property" not in error_str:
                            msg.warn(f"[ETL-POST] Traceback: {traceback.format_exc()[:500]}")
            else:
                if not enable_etl:
                    msg.info(f"[ETL-POST] ETL pós-chunking não habilitado (enable_etl=False)")
                if not doc_uuid:
                    msg.warn(f"[ETL-POST] ETL pós-chunking não executado (doc_uuid não disponível)")
        
        # Substitui método (monkey patch)
        managers.WeaviateManager.import_document = patched_import_document
        
        msg.info("✅ Hook ETL A2 integrado no WeaviateManager")
        return True
        
    except Exception as e:
        msg.warn(f"Erro ao aplicar hook ETL: {str(e)}")
        return False


def patch_verba_manager():
    """
    Patch adicional no VerbaManager se necessário
    """
    try:
        from goldenverba import verba_manager
        
        # Aqui podemos adicionar outros patches se necessário
        # Por enquanto, o patch no WeaviateManager é suficiente
        
        return True
    except Exception as e:
        msg.warn(f"Erro no patch VerbaManager: {str(e)}")
        return False
