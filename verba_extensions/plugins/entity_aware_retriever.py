"""
Plugin: Entity-Aware Retriever
Retriever que usa filtros entity-aware para evitar contaminação

=== ARQUITETURA ===

ENTIDADE (spaCy NER) vs SEMÂNTICA (Vector Search):

1. ENTIDADE
   - O QUÊ: Coisas com identidade única (Apple, Steve Jobs, São Paulo)
   - COMO: spaCy extrai menções, Gazetteer mapeia para entity_id
   - BENEFÍCIO: WHERE filter (rápido, preciso)
   - LIMITAÇÃO: Só funciona com nomes conhecidos
   - EXEMPLO: "apple" → entity_id="Q123"

2. SEMÂNTICA
   - O QUÊ: Significado e contexto (inovação, visão, disruptivo)
   - COMO: Embedding model converte em vetor
   - BENEFÍCIO: Captura conceitos abstratos
   - LIMITAÇÃO: Pode trazer resultados sem entidade esperada
   - EXEMPLO: "inovação" → vetor [0.234, 0.891, ...]

3. HÍBRIDO (IDEAL - O QUE IMPLEMENTAMOS)
   - Combina: entity_filter AND semantic_search
   - QUERY: "apple e inovação"
   - FLUXO:
     1. Extrai entidade: Apple → entity_id="Q123"
     2. Extrai semanticamente: "inovação" → busca vetorial
     3. Aplica WHERE: chunks.entity_id = "Q123" (FILTRA)
     4. Dentro desses chunks, busca: "inovação" (SEMANTICAMENTE)
     5. Retorna: chunks sobre Apple que mencionam inovação
"""

from goldenverba.components.interfaces import Retriever
from goldenverba.components.types import InputConfig
from goldenverba.components.chunk import Chunk
from verba_extensions.compatibility.weaviate_imports import Filter, WEAVIATE_V4
from typing import Optional, Dict, Any, List
from wasabi import msg


class EntityAwareRetriever(Retriever):
    """
    Retriever que combina filtros entity-aware com busca semântica.
    
    Fluxo:
    1. Extrai entidades da query (spaCy + Gazetteer)
    2. Aplica WHERE filter no Weaviate (rápido!)
    3. Dentro dos resultados, faz busca semântica (relevância)
    4. Retorna chunks filtrados + relevantes
    
    Exemplo:
    Query: "descreva o que se fala sobre a Apple e Inovação"
    ├─ Entidade: Apple → entity_id="Q123"
    ├─ Semântica: "inovação" → vetor
    ├─ WHERE: entities = "Q123" (FILTRA)
    ├─ Vector search: "inovação" (DENTRO dos resultados)
    └─ Resultado: chunks sobre Apple que falam de inovação
    """
    
    def __init__(self):
        super().__init__()
        self.description = "Entity-Aware Retriever com busca semântica"
        self.name = "EntityAware"
        
        self.config["Search Mode"] = InputConfig(
            type="dropdown",
            value="Hybrid Search",
            description="Search mode to use.",
            values=["Hybrid Search"],
        )
        self.config["Limit Mode"] = InputConfig(
            type="dropdown",
            value="Autocut",
            description="Method for limiting results",
            values=["Autocut", "Fixed"],
        )
        self.config["Limit/Sensitivity"] = InputConfig(
            type="number",
            value=1,
            description="Limit value or sensitivity",
            values=[],
        )
        self.config["Chunk Window"] = InputConfig(
            type="number",
            value=1,
            description="Number of surrounding chunks",
            values=[],
        )
        self.config["Alpha"] = InputConfig(
            type="text",
            value="0.6",
            description="Hybrid search alpha (0.0=keyword, 1.0=vector). Use decimal format (e.g., 0.6)",
            values=[],
        )
        self.config["Enable Entity Filter"] = InputConfig(
            type="bool",
            value=True,
            description="Enable entity-aware pre-filtering",
            values=[],
        )
        self.config["Enable Semantic Search"] = InputConfig(
            type="bool",
            value=True,
            description="Enable semantic search within filtered results",
            values=[],
        )
        self.config["Enable Language Filter"] = InputConfig(
            type="bool",
            value=True,
            description="Enable automatic language filtering based on query language",
            values=[],
        )
        self.config["Enable Query Rewriting"] = InputConfig(
            type="bool",
            value=False,
            description="Enable LLM-based query rewriting for better search results",
            values=[],
        )
        self.config["Query Rewriter Cache TTL"] = InputConfig(
            type="number",
            value=3600,
            description="Cache TTL in seconds for query rewriting (default: 3600)",
            values=[],
        )
        self.config["Enable Temporal Filter"] = InputConfig(
            type="bool",
            value=True,
            description="Enable automatic temporal filtering based on dates in query",
            values=[],
        )
        self.config["Date Field Name"] = InputConfig(
            type="text",
            value="chunk_date",
            description="Name of the date field in Weaviate (default: chunk_date)",
            values=[],
        )
    
    async def retrieve(
        self,
        client,
        query: str,
        vector: List[float],
        config: Dict,
        weaviate_manager,
        embedder: str,
        labels: List[str],
        document_uuids: List[str],
        rag_config: Optional[Dict[str, Any]] = None,  # RAG config completo (para Query Builder usar generator)
    ):
        """
        Retrieval com filtros entity-aware + busca semântica
        
        Fluxo:
        1. Parse query para separar entidades de conceitos
        2. Se tem entidades: aplica WHERE filter
        3. Dentro dos filtrados: faz busca semântica
        4. Retorna chunks ordenados por relevância
        """
        from goldenverba.components.retriever.WindowRetriever import WindowRetriever
        from verba_extensions.plugins.query_parser import parse_query
        
        msg.info(f"EntityAwareRetriever processando: '{query}'")
        
        # CONFIG
        search_mode = config["Search Mode"].value
        limit_mode = config["Limit Mode"].value
        limit = int(config["Limit/Sensitivity"].value)
        alpha_value = config["Alpha"].value
        alpha = float(alpha_value) if isinstance(alpha_value, str) else float(alpha_value)
        
        # DEBUG INFO: Coletar informações de debug para exibir ao usuário (DEPOIS de definir alpha)
        debug_info = {
            "original_query": query,
            "rewritten_query": None,
            "query_builder_used": False,
            "query_rewriter_used": False,
            "entities_detected": [],
            "semantic_terms": [],
            "filters_applied": {},
            "alpha_used": alpha,
            "search_mode": None,
            "explanation": None,
        }
        enable_entity_filter = config.get("Enable Entity Filter", {}).value if isinstance(config.get("Enable Entity Filter"), InputConfig) else True
        enable_semantic = config.get("Enable Semantic Search", {}).value if isinstance(config.get("Enable Semantic Search"), InputConfig) else True
        enable_query_rewriting = config.get("Enable Query Rewriting", {}).value if isinstance(config.get("Enable Query Rewriting"), InputConfig) else False
        cache_ttl = int(config.get("Query Rewriter Cache TTL", {}).value) if isinstance(config.get("Query Rewriter Cache TTL"), InputConfig) else 3600
        enable_temporal_filter = config.get("Enable Temporal Filter", {}).value if isinstance(config.get("Enable Temporal Filter"), InputConfig) else True
        date_field_name = config.get("Date Field Name", {}).value if isinstance(config.get("Date Field Name"), InputConfig) else "chunk_date"
        
        # 0. QUERY BUILDING (antes de parsing) - QueryBuilder inteligente com schema
        rewritten_query = query
        rewritten_alpha = alpha
        query_filters_from_builder = {}
        
        # Tentar QueryBuilder primeiro (mais inteligente, conhece schema)
        try:
            from verba_extensions.plugins.query_builder import QueryBuilderPlugin
            builder = QueryBuilderPlugin(cache_ttl_seconds=cache_ttl)
            
            # Obter collection name
            normalized = weaviate_manager._normalize_embedder_name(embedder)
            collection_name = weaviate_manager.embedding_table.get(embedder, f"VERBA_Embedding_{normalized}")
            
            # Usar RAG config passado como parâmetro (mesmo do chat)
            # Construir query conhecendo schema
            strategy = await builder.build_query(
                user_query=query,
                client=client,
                collection_name=collection_name,
                use_cache=True,
                validate=False,  # Não precisa validar aqui, já está executando
                auto_detect_aggregation=True,  # NOVO: detecta agregações automaticamente
                rag_config=rag_config,  # Passar RAG config para usar generator configurado (mesmo do chat)
                labels=labels,  # Passar labels para calcular idioma dominante apenas dos documentos filtrados
                document_uuids=document_uuids  # Passar document_uuids para calcular idioma dominante apenas dos documentos filtrados
            )
            
            # NOVO: Verificar se é agregação e executar se for
            if strategy.get("is_aggregation", False):
                msg.info("  Query builder: detectou agregação, executando via GraphQL")
                
                aggregation_info = strategy.get("aggregation_info")
                if aggregation_info and "error" not in aggregation_info:
                    try:
                        import json
                        
                        # Executar agregação
                        raw_results = await aggregation_info["execute"]()
                        
                        # Parsear resultados
                        parsed_results = aggregation_info["parse"](raw_results)
                        
                        # Formatar resultados para retorno
                        # Retornar lista vazia de chunks e contexto com resultados de agregação
                        context = f"Resultados de agregação:\n{json.dumps(parsed_results, indent=2, ensure_ascii=False)}"
                        
                        msg.good(f"  Agregação executada com sucesso: {aggregation_info.get('aggregation_type', 'unknown')}")
                        
                        # Retornar chunks vazios e contexto com resultados
                        return ([], context)
                        
                    except Exception as e:
                        msg.warn(f"  Erro ao executar agregação: {str(e)}")
                        # Continua com query normal como fallback
                        import traceback
                        traceback.print_exc()
            
            # Usar semantic_query para busca vetorial
            rewritten_query = strategy.get("semantic_query", query)
            
            # Verificar se a query foi realmente expandida
            if rewritten_query == query:
                msg.warn(f"  ⚠️ Query builder retornou query idêntica - pode estar usando fallback ou LLM não expandiu")
            else:
                msg.good(f"  ✅ Query builder expandiu: '{query}' → '{rewritten_query[:100]}...'")
            
            debug_info["rewritten_query"] = rewritten_query
            debug_info["query_builder_used"] = True
            
            # Aplicar alpha sugerido
            suggested_alpha = strategy.get("alpha")
            if suggested_alpha is not None and 0.0 <= suggested_alpha <= 1.0:
                rewritten_alpha = float(suggested_alpha)
                debug_info["alpha_used"] = rewritten_alpha
                msg.info(f"  Query builder: alpha ajustado para {rewritten_alpha}")
            
            # Extrair filtros do builder (se houver)
            query_filters_from_builder = strategy.get("filters", {})
            builder_entities = query_filters_from_builder.get("entities", [])
            if builder_entities:
                debug_info["entities_detected"] = builder_entities
                msg.info(f"  Query builder: entidades detectadas: {builder_entities}")
            
            # Log explanation
            explanation = strategy.get("explanation", "")
            if explanation:
                debug_info["explanation"] = explanation
                msg.info(f"  Query builder: {explanation}")
            
        except ImportError:
            # Fallback para QueryRewriter (mais simples, não conhece schema)
            if enable_query_rewriting:
                try:
                    from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin
                    rewriter = QueryRewriterPlugin(cache_ttl_seconds=cache_ttl)
                    strategy = await rewriter.rewrite_query(query, use_cache=True)
                    
                    # Usar semantic_query para busca vetorial
                    rewritten_query = strategy.get("semantic_query", query)
                    debug_info["rewritten_query"] = rewritten_query
                    debug_info["query_rewriter_used"] = True
                    
                    # Aplicar alpha sugerido
                    suggested_alpha = strategy.get("alpha")
                    if suggested_alpha is not None and 0.0 <= suggested_alpha <= 1.0:
                        rewritten_alpha = float(suggested_alpha)
                        debug_info["alpha_used"] = rewritten_alpha
                        msg.info(f"  Query rewriting: alpha ajustado para {rewritten_alpha}")
                    
                    # Log intent se disponível
                    intent = strategy.get("intent", "search")
                    debug_info["intent"] = intent
                    msg.info(f"  Query rewriting: intent={intent}")
                    
                except Exception as e:
                    msg.warn(f"  Erro no query rewriting (não crítico): {str(e)}")
                    # Continua com query original
        except Exception as e:
            msg.warn(f"  Erro no query builder (não crítico): {str(e)}")
            # Fallback para QueryRewriter se disponível
            if enable_query_rewriting:
                try:
                    from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin
                    rewriter = QueryRewriterPlugin(cache_ttl_seconds=cache_ttl)
                    strategy = await rewriter.rewrite_query(query, use_cache=True)
                    rewritten_query = strategy.get("semantic_query", query)
                    suggested_alpha = strategy.get("alpha")
                    if suggested_alpha is not None and 0.0 <= suggested_alpha <= 1.0:
                        rewritten_alpha = float(suggested_alpha)
                except:
                    pass
        
        # 1. PARSE QUERY (usar rewritten_query se disponível)
        # Se QueryBuilder forneceu entidades, usar elas primeiro
        builder_entities = query_filters_from_builder.get("entities", [])
        
        parse_query_text = rewritten_query if enable_query_rewriting or rewritten_query != query else query
        parsed = parse_query(parse_query_text)
        parsed_entity_ids = [e["entity_id"] for e in parsed["entities"] if e["entity_id"]]
        semantic_terms = parsed["semantic_concepts"]
        
        # Combinar entidades do builder e do parser (priorizar builder)
        entity_ids = builder_entities if builder_entities else parsed_entity_ids
        
        msg.info(f"  🔍 Entidades detectadas: {entity_ids} (builder: {builder_entities}, parser: {parsed_entity_ids})")
        msg.info(f"  🔍 Conceitos semânticos: {semantic_terms}")
        
        # Se não há entidades, avisar que filtros restritivos serão ignorados
        if not entity_ids:
            msg.info(f"  ⚠️ NENHUMA entidade detectada - filtros restritivos serão ignorados para busca mais ampla")
        
        # Atualizar debug info com entidades e termos semânticos
        if not debug_info["entities_detected"]:
            debug_info["entities_detected"] = entity_ids
        debug_info["semantic_terms"] = semantic_terms
        
        # 2. CONSTRÓI FILTRO DE ENTIDADE (WHERE clause)
        # Suporte para filtros hierárquicos (documento primeiro, depois chunks)
        document_level_filter = query_filters_from_builder.get("document_level_entities", [])
        chunk_level_entities = entity_ids
        
        entity_filter = None
        if enable_entity_filter:
            # Se há filtro de documento, primeiro filtrar documentos
            if document_level_filter:
                try:
                    from verba_extensions.utils.document_entity_filter import get_documents_by_entity
                    
                    # Normalizar nome da collection
                    normalized = weaviate_manager._normalize_embedder_name(embedder)
                    collection_name = weaviate_manager.embedding_table.get(embedder, f"VERBA_Embedding_{normalized}")
                    
                    # Obter documentos que contêm entidade do nível documento
                    doc_uuids_filtered = []
                    for doc_entity_id in document_level_filter:
                        doc_uuids = await get_documents_by_entity(
                            client,
                            collection_name,
                            doc_entity_id
                        )
                        doc_uuids_filtered.extend(doc_uuids)
                    
                    # Remover duplicatas
                    doc_uuids_filtered = list(set(doc_uuids_filtered))
                    
                    if doc_uuids_filtered:
                        # Combinar filtro de documento com filtro de chunk
                        # Restringir busca aos documentos filtrados
                        if document_uuids:
                            # Intersecção: documentos filtrados E documentos especificados pelo usuário
                            document_uuids = list(set(document_uuids) & set(doc_uuids_filtered))
                        else:
                            # Usar apenas documentos filtrados
                            document_uuids = doc_uuids_filtered
                        
                        msg.good(f"  Filtro hierárquico: {len(document_uuids)} documentos com entidade(s) {document_level_filter}")
                    else:
                        msg.warn(f"  Nenhum documento encontrado com entidade(s) {document_level_filter}")
                        # Retornar vazio se não há documentos
                        return []
                        
                except ImportError:
                    msg.warn("  document_entity_filter não disponível, usando filtro de chunk apenas")
                except Exception as e:
                    msg.warn(f"  Erro ao aplicar filtro hierárquico: {str(e)}")
            
            # Filtro de chunk (entidades no nível do chunk)
            if chunk_level_entities:
                # Usar propriedade sugerida pelo builder se disponível
                # Padrão: section_entity_ids para evitar contaminação entre entidades
                # (ex: documento fala de 10 empresas, busca por empresa 2 não deve pegar empresa 8)
                entity_property = query_filters_from_builder.get("entity_property", "section_entity_ids")
                entity_filter = Filter.by_property(entity_property).contains_any(chunk_level_entities)
                msg.good(f"  Aplicando filtro de chunk: {entity_property} = {chunk_level_entities}")
        
        # 2.1. FILTRO DE IDIOMA (Bilingual Filter)
        enable_lang_filter = config.get("Enable Language Filter", {}).value if isinstance(config.get("Enable Language Filter"), InputConfig) else True
        lang_filter = None
        
        # Se QueryBuilder forneceu language, usar ele
        builder_language = query_filters_from_builder.get("language")
        
        if enable_lang_filter:
            if builder_language:
                # Usar language do builder
                try:
                    from verba_extensions.plugins.bilingual_filter import BilingualFilterPlugin
                    bilingual_plugin = BilingualFilterPlugin()
                    lang_filter = bilingual_plugin.build_language_filter(builder_language)
                    if lang_filter:
                        msg.good(f"  Query builder: filtro de idioma aplicado: {builder_language}")
                except Exception as e:
                    msg.warn(f"  Erro ao aplicar filtro de idioma do builder: {str(e)}")
            else:
                # Fallback para detecção automática
                try:
                    from verba_extensions.plugins.bilingual_filter import BilingualFilterPlugin
                    bilingual_plugin = BilingualFilterPlugin()
                    lang_filter = bilingual_plugin.get_language_filter_for_query(query)
                    if lang_filter:
                        msg.good(f"  Aplicando filtro de idioma: {bilingual_plugin.detect_query_language(query)}")
                except Exception as e:
                    msg.warn(f"  Erro ao aplicar filtro de idioma (não crítico): {str(e)}")
        
        # 2.2. FILTRO TEMPORAL (Temporal Filter)
        temporal_filter = None
        # Se QueryBuilder forneceu date_range, usar ele
        builder_date_range = query_filters_from_builder.get("date_range")
        
        if enable_temporal_filter:
            if builder_date_range:
                # Usar date_range do builder
                try:
                    from verba_extensions.plugins.temporal_filter import TemporalFilterPlugin
                    temporal_plugin = TemporalFilterPlugin()
                    start_date = builder_date_range.get("start")
                    end_date = builder_date_range.get("end")
                    temporal_filter = temporal_plugin.build_temporal_filter(
                        start_date=start_date,
                        end_date=end_date,
                        date_field=date_field_name
                    )
                    if temporal_filter:
                        msg.good(f"  Query builder: filtro temporal aplicado: {start_date} até {end_date}")
                except Exception as e:
                    msg.warn(f"  Erro ao aplicar filtro temporal do builder: {str(e)}")
            else:
                # Fallback para detecção automática
                try:
                    from verba_extensions.plugins.temporal_filter import TemporalFilterPlugin
                    temporal_plugin = TemporalFilterPlugin()
                    temporal_filter = temporal_plugin.get_temporal_filter_for_query(query, date_field=date_field_name)
                    if temporal_filter:
                        date_range = temporal_plugin.extract_date_range(query)
                        if date_range:
                            start_date, end_date = date_range
                            msg.good(f"  Aplicando filtro temporal: {start_date} até {end_date}")
                except Exception as e:
                    msg.warn(f"  Erro ao aplicar filtro temporal (não crítico): {str(e)}")
        
        # 2.3. FILTRO POR FREQUÊNCIA (se habilitado)
        frequency_filter = None
        filter_by_frequency = query_filters_from_builder.get("filter_by_frequency", False)
        min_frequency = query_filters_from_builder.get("min_frequency", 0)
        dominant_only = query_filters_from_builder.get("dominant_only", False)
        frequency_comparison = query_filters_from_builder.get("frequency_comparison")
        
        if filter_by_frequency and (min_frequency > 0 or dominant_only or frequency_comparison):
            try:
                from verba_extensions.utils.entity_frequency import (
                    get_entity_hierarchy,
                    get_dominant_entity,
                    get_entity_ratio
                )
                
                # Se há document_uuids filtrados, usar eles. Senão, buscar todos documentos do resultado
                # Por enquanto, aplicamos filtro de frequência após buscar chunks (pós-processamento)
                # Isso porque precisamos calcular frequência por documento primeiro
                msg.info(f"  Filtro por frequência ativado: min_frequency={min_frequency}, dominant_only={dominant_only}")
                # Nota: Filtro de frequência será aplicado após buscar chunks (pós-processamento)
                # pois requer cálculo de frequência por documento
            except ImportError:
                msg.warn("  entity_frequency não disponível, ignorando filtro de frequência")
        
        # Combinar filtros (entity + language + temporal)
        # IMPORTANTE: Quando não há entidades, filtros podem estar restringindo demais os resultados
        # Estratégia: aplicar filtros apenas quando há entidades OU quando são realmente necessários
        combined_filter = None
        filters_list = []
        
        # REGRA PRINCIPAL: Se não há entidades, não aplicar filtros restritivos
        # (exceto temporal, que não é restritivo demais)
        has_entities = bool(entity_ids)
        
        # Aplicar filtro de entidade apenas se houver entidades detectadas
        if entity_filter and has_entities:
            filters_list.append(entity_filter)
            msg.info(f"  ✅ Filtro de entidade aplicado: {entity_ids}")
        elif entity_filter and not has_entities:
            msg.info(f"  ⚠️ Filtro de entidade ignorado (sem entidades detectadas)")
        
        # Filtro de idioma: aplicar APENAS quando há entidades
        # Quando NÃO há entidades, o filtro de idioma pode estar restringindo demais os resultados
        if lang_filter:
            if has_entities:
                # Quando há entidades, filtro de idioma ajuda a evitar contaminação
                filters_list.append(lang_filter)
                msg.info(f"  ✅ Filtro de idioma aplicado (com entidades)")
            else:
                # Quando não há entidades, filtro de idioma pode estar restringindo demais
                # Ignorar para permitir busca mais ampla
                msg.info(f"  ⚠️ Filtro de idioma ignorado (sem entidades, pode restringir demais)")
        
        # Filtro temporal: aplicar sempre que disponível (não restritivo demais)
        if temporal_filter:
            filters_list.append(temporal_filter)
            msg.info(f"  ✅ Filtro temporal aplicado")
        
        if len(filters_list) == 1:
            combined_filter = filters_list[0]
        elif len(filters_list) > 1:
            combined_filter = Filter.all_of(filters_list)
        
        # Atualizar debug info sobre filtros
        if combined_filter:
            filter_types = []
            if entity_filter and has_entities:
                filter_types.append("entidade")
            if lang_filter and has_entities:  # Só conta se foi aplicado
                filter_types.append("idioma")
            if temporal_filter:
                filter_types.append("temporal")
            
            if filter_types:
                debug_info["filters_applied"] = {
                    "type": "combined" if len(filter_types) > 1 else filter_types[0],
                    "description": f"Filtros aplicados: {', '.join(filter_types)}"
                }
            else:
                debug_info["filters_applied"] = {
                    "type": "temporal_only",
                    "description": "Apenas filtro temporal"
                }
        else:
            debug_info["filters_applied"] = {
                "type": "none",
                "description": "Sem filtros aplicados (sem entidades detectadas)"
            }
        
        # 3. DETERMINA QUERY PARA BUSCA SEMÂNTICA
        # Prioridade: rewritten_query > semantic_terms > query original
        if enable_query_rewriting:
            search_query = rewritten_query
            msg.info(f"  Query semântica (rewritten): '{search_query}'")
        elif enable_semantic and semantic_terms:
            # Se tem conceitos semânticos, usa-os para melhorar a busca
            search_query = " ".join(semantic_terms)
            msg.info(f"  Query semântica: '{search_query}'")
        else:
            search_query = query  # Padrão: query completa
        
        # Atualizar debug info com query final usada
        if not debug_info["rewritten_query"]:
            debug_info["rewritten_query"] = search_query
        debug_info["search_mode"] = search_mode
        
        # 4. BUSCA HÍBRIDA COM FILTRO (O MAGIC AQUI!)
        if search_mode == "Hybrid Search":
            try:
                if combined_filter:
                    # FILTRA por entidade + idioma, DEPOIS faz busca semântica
                    msg.info(f"  Executando: Hybrid search com filtros combinados")
                    # debug_info já foi atualizado acima
                    
                    chunks = await weaviate_manager.hybrid_chunks_with_filter(
                        client=client,
                        embedder=embedder,
                        query=search_query,        # ← Query semântica ou completa
                        vector=vector,              # ← Vetor da query
                        limit_mode=limit_mode,
                        limit=limit,
                        labels=labels,
                        document_uuids=document_uuids,
                        filters=combined_filter,   # ← FILTRA por entidade + idioma PRIMEIRO
                        alpha=rewritten_alpha,     # ← Alpha ajustado pelo query rewriting
                    )
                elif entity_filter and enable_entity_filter:
                    # FILTRA apenas por entidade
                    msg.info(f"  Executando: Hybrid search com entity filter")
                    # debug_info já foi atualizado acima
                    
                    chunks = await weaviate_manager.hybrid_chunks_with_filter(
                        client=client,
                        embedder=embedder,
                        query=search_query,
                        vector=vector,
                        limit_mode=limit_mode,
                        limit=limit,
                        labels=labels,
                        document_uuids=document_uuids,
                        filters=entity_filter,
                        alpha=rewritten_alpha,     # ← Alpha ajustado pelo query rewriting
                    )
                else:
                    # Sem filtros: busca normal
                    msg.info(f"  Executando: Hybrid search sem filtros")
                    # debug_info já foi atualizado acima
                    
                    chunks = await weaviate_manager.hybrid_chunks(
                        client=client,
                        embedder=embedder,
                        query=search_query,
                        vector=vector,
                        limit_mode=limit_mode,
                        limit=limit,
                        labels=labels,
                        document_uuids=document_uuids,
                        alpha=rewritten_alpha,  # ← Alpha também aplicado quando não há filtros
                    )
            except Exception as e:
                msg.fail(f"Erro na busca híbrida: {str(e)}")
                # Fallback
                chunks = []
        
        if len(chunks) == 0:
            msg.warn("Nenhum chunk encontrado")
            return ([], "We couldn't find any chunks to the query")
        
        msg.good(f"Encontrados {len(chunks)} chunks")
        
        # 4.5. FILTRO POR FREQUÊNCIA (pós-processamento após buscar chunks)
        if filter_by_frequency and (min_frequency > 0 or dominant_only or frequency_comparison):
            try:
                from verba_extensions.utils.entity_frequency import (
                    get_entity_hierarchy,
                    get_dominant_entity,
                    get_entity_ratio
                )
                
                # Normalizar nome da collection
                normalized = weaviate_manager._normalize_embedder_name(embedder)
                collection_name = weaviate_manager.embedding_table.get(embedder, f"VERBA_Embedding_{normalized}")
                
                # Agrupar chunks por doc_uuid
                chunks_by_doc = {}
                for chunk in chunks:
                    doc_uuid = str(chunk.properties.get("doc_uuid", ""))
                    if doc_uuid:
                        if doc_uuid not in chunks_by_doc:
                            chunks_by_doc[doc_uuid] = []
                        chunks_by_doc[doc_uuid].append(chunk)
                
                # Filtrar documentos baseado em frequência
                filtered_chunks = []
                filtered_docs = 0
                
                for doc_uuid, doc_chunks in chunks_by_doc.items():
                    should_include = True
                    
                    # Verificar frequência mínima
                    if min_frequency > 0 and chunk_level_entities:
                        from verba_extensions.utils.entity_frequency import get_entity_frequency_in_document
                        freq = await get_entity_frequency_in_document(
                            client, collection_name, doc_uuid
                        )
                        # Verificar se alguma entidade do filtro tem frequência suficiente
                        has_min_freq = any(
                            freq.get(eid, 0) >= min_frequency
                            for eid in chunk_level_entities
                        )
                        if not has_min_freq:
                            should_include = False
                            continue
                    
                    # Verificar entidade dominante
                    if dominant_only and chunk_level_entities:
                        dominant_entity, _, _ = await get_dominant_entity(
                            client, collection_name, doc_uuid
                        )
                        # Verificar se alguma entidade do filtro é dominante
                        if dominant_entity not in chunk_level_entities:
                            should_include = False
                            continue
                    
                    # Verificar comparação de frequência
                    if frequency_comparison:
                        entity_1 = frequency_comparison.get("entity_1")
                        entity_2 = frequency_comparison.get("entity_2")
                        min_ratio = frequency_comparison.get("min_ratio", 1.0)
                        
                        if entity_1 and entity_2:
                            ratio, _ = await get_entity_ratio(
                                client, collection_name, doc_uuid,
                                entity_1, entity_2
                            )
                            if ratio < min_ratio:
                                should_include = False
                                continue
                    
                    if should_include:
                        filtered_chunks.extend(doc_chunks)
                        filtered_docs += 1
                
                if filtered_chunks:
                    chunks = filtered_chunks
                    msg.good(f"  Filtro de frequência: {len(filtered_chunks)} chunks de {filtered_docs} documentos")
                else:
                    msg.warn(f"  Filtro de frequência: nenhum documento passou nos critérios")
                    return ([], "Nenhum documento atende aos critérios de frequência de entidade")
                    
            except ImportError:
                msg.warn("  entity_frequency não disponível, ignorando filtro de frequência")
            except Exception as e:
                msg.warn(f"  Erro ao aplicar filtro de frequência: {str(e)}")
                # Continua com chunks originais
        
        # 5. PROCESSA CHUNKS (aplicar window)
        chunks, message = await self._process_chunks(
            client, chunks, weaviate_manager, embedder, config
        )
        
        # 6. ✨ RERANKING (se disponível)
        try:
            from verba_extensions.plugins.plugin_manager import get_plugin_manager
            plugin_manager = get_plugin_manager()
            
            # Procura plugin Reranker
            reranker = None
            for plugin in plugin_manager.plugins:
                if plugin.name == "Reranker":
                    reranker = plugin
                    break
            
            if reranker:
                # Converte chunks Weaviate para Chunk objects para reranking
                chunk_objects = []
                for chunk in chunks:
                    if hasattr(chunk, "properties"):
                        chunk_obj = Chunk(
                            content=chunk.properties.get("content", ""),
                            chunk_id=str(chunk.uuid),
                            content_without_overlap=chunk.properties.get("content_without_overlap", "")
                        )
                        # Atribui metadata após criação (meta não é parâmetro do construtor)
                        import json
                        meta_str = chunk.properties.get("meta", "{}")
                        try:
                            chunk_obj.meta = json.loads(meta_str) if isinstance(meta_str, str) else (meta_str or {})
                        except:
                            chunk_obj.meta = {}
                        # Copia outros campos relevantes
                        chunk_obj.uuid = chunk.uuid
                        chunk_obj.doc_uuid = chunk.properties.get("doc_uuid")
                        chunk_obj.chunk_lang = chunk.properties.get("chunk_lang")
                        chunk_obj.chunk_date = chunk.properties.get("chunk_date")
                        chunk_obj.title = chunk.properties.get("title", "")
                        chunk_objects.append(chunk_obj)
                
                if chunk_objects:
                    # Rerank usando top_k baseado no limit original
                    reranked_objects = await reranker.process_chunks(
                        chunk_objects,
                        query=query,
                        config={"top_k": limit}
                    )
                    
                    # Reconstrói chunks Weaviate a partir dos rerankeados
                    reranked_uuids = {chunk.chunk_id for chunk in reranked_objects}
                    chunks = [c for c in chunks if str(c.uuid) in reranked_uuids]
                    
                    # Reordena conforme reranking
                    uuid_to_chunk = {str(c.uuid): c for c in chunks}
                    chunks = [uuid_to_chunk.get(chunk.chunk_id) for chunk in reranked_objects if chunk.chunk_id in uuid_to_chunk]
                    
                    msg.good(f"Reranked {len(chunks)} chunks usando {reranker.name}")
        except Exception as e:
            msg.warn(f"Reranking falhou (não crítico): {str(e)}")
            # Continua sem reranking
        
        # 7. CONVERTE CHUNKS PARA FORMATO ESPERADO (dicionários serializáveis)
        # Similar ao WindowRetriever, precisa converter objetos Weaviate para dicionários
        documents = []
        doc_map = {}
        
        for chunk in chunks:
            if not hasattr(chunk, "properties"):
                continue
                
            chunk_props = chunk.properties
            doc_uuid = str(chunk_props.get("doc_uuid", ""))
            
            if not doc_uuid:
                continue
            
            # Buscar documento se ainda não foi buscado
            if doc_uuid not in doc_map:
                try:
                    document = await weaviate_manager.get_document(client, doc_uuid)
                    if document is None:
                        continue
                    doc_map[doc_uuid] = {
                        "title": document.get("title", ""),
                        "chunks": [],
                        "score": 0,
                        "metadata": document.get("metadata", {}),
                    }
                except Exception as e:
                    msg.warn(f"Erro ao buscar documento {doc_uuid}: {str(e)}")
                    continue
            
            # Adicionar chunk ao documento
            chunk_score = chunk.metadata.score if hasattr(chunk, "metadata") and hasattr(chunk.metadata, "score") else 0
            
            # Converter chunk_id para int (pode vir como float ou string do Weaviate)
            chunk_id_raw = chunk_props.get("chunk_id", 0)
            try:
                # Tenta converter para int
                if isinstance(chunk_id_raw, (int, float)):
                    chunk_id = int(chunk_id_raw)
                elif isinstance(chunk_id_raw, str):
                    # Se for string, tenta converter
                    if chunk_id_raw.strip() == "":
                        chunk_id = 0
                    else:
                        chunk_id = int(float(chunk_id_raw))
                else:
                    chunk_id = 0
            except (ValueError, TypeError):
                chunk_id = 0
            
            doc_map[doc_uuid]["chunks"].append({
                "uuid": str(chunk.uuid),
                "score": chunk_score,
                "chunk_id": chunk_id,  # Agora garantidamente int
                "content": chunk_props.get("content", ""),
            })
            doc_map[doc_uuid]["score"] += chunk_score
        
        # Converter doc_map para lista de documentos e gerar contexto
        documents = []
        context_documents = []
        
        for doc_uuid, doc_data in doc_map.items():
            # Documento com chunks mínimos (sem content nos chunks)
            _chunks = [
                {
                    "uuid": chunk["uuid"],
                    "score": chunk["score"],
                    "chunk_id": chunk["chunk_id"],
                    "embedder": embedder,
                }
                for chunk in doc_data["chunks"]
            ]
            
            # Documento com content para contexto
            context_chunks = [
                {
                    "uuid": chunk["uuid"],
                    "score": chunk["score"],
                    "content": chunk["content"],
                    "chunk_id": chunk["chunk_id"],
                    "embedder": embedder,
                }
                for chunk in doc_data["chunks"]
            ]
            
            # Ordenar por chunk_id
            _chunks_sorted = sorted(_chunks, key=lambda x: x["chunk_id"])
            context_chunks_sorted = sorted(context_chunks, key=lambda x: x["chunk_id"])
            
            documents.append({
                "title": doc_data["title"],
                "chunks": _chunks_sorted,
                "score": doc_data["score"],
                "metadata": doc_data["metadata"],
                "uuid": doc_uuid,
            })
            
            context_documents.append({
                "title": doc_data["title"],
                "chunks": context_chunks_sorted,
                "score": doc_data["score"],
                "uuid": doc_uuid,
                "metadata": doc_data["metadata"],
            })
        
        # Ordenar por score
        sorted_context_documents = sorted(
            context_documents, key=lambda x: x["score"], reverse=True
        )
        sorted_documents = sorted(documents, key=lambda x: x["score"], reverse=True)
        
        # Gerar contexto combinado
        context = self.combine_context(sorted_context_documents)
        
        # Adicionar informações de debug ao contexto (formato JSON no final)
        debug_summary = f"\n\n[DEBUG INFO]\n"
        debug_summary += f"Query original: {debug_info['original_query']}\n"
        debug_summary += f"Query reescrita: {debug_info['rewritten_query']}\n"
        if debug_info['query_builder_used']:
            debug_summary += f"Query Builder usado: Sim\n"
        if debug_info['query_rewriter_used']:
            debug_summary += f"Query Rewriter usado: Sim\n"
        if debug_info['entities_detected']:
            debug_summary += f"Entidades detectadas: {', '.join(debug_info['entities_detected'])}\n"
        if debug_info['semantic_terms']:
            debug_summary += f"Termos semânticos: {', '.join(debug_info['semantic_terms'])}\n"
        if debug_info['filters_applied']:
            debug_summary += f"Filtros aplicados: {debug_info['filters_applied'].get('description', 'N/A')}\n"
        debug_summary += f"Alpha usado: {debug_info['alpha_used']}\n"
        debug_summary += f"Modo de busca: {debug_info['search_mode']}\n"
        if debug_info.get('explanation'):
            debug_summary += f"Explicação: {debug_info['explanation']}\n"
        
        # Retornar com informações de debug como terceiro elemento (para API)
        # Mas também incluir no contexto para compatibilidade
        context_with_debug = context + debug_summary
        
        return (sorted_documents, context_with_debug, debug_info)
    
    async def _process_chunks(self, client, chunks, weaviate_manager, embedder, config):
        """Processa chunks aplicando window technique"""
        
        chunk_window = int(config.get("Chunk Window", {}).value if hasattr(config.get("Chunk Window"), 'value') else config.get("Chunk Window", 1))
        
        if chunk_window > 0 and chunks:
            # Agrupa chunks adjacentes com window
            windowed_chunks = []
            for i, chunk in enumerate(chunks):
                context_chunks = chunks[max(0, i - chunk_window):min(len(chunks), i + chunk_window + 1)]
                # Acessa content do Weaviate object corretamente
                combined_content = " ".join([
                    c.properties["content"] if hasattr(c, "properties") else c.get("content", "")
                    for c in context_chunks
                ])
                # Atualiza o content do chunk atual
                if hasattr(chunk, "properties"):
                    chunk.properties["content"] = combined_content
                else:
                    chunk["content"] = combined_content
                windowed_chunks.append(chunk)
            chunks = windowed_chunks
        
        return (chunks, "Chunks retrieved with entity-aware filtering")
    
    def combine_context(self, documents: list[dict]) -> str:
        """Combina contexto dos documentos"""
        from goldenverba.components.retriever.WindowRetriever import WindowRetriever
        window_retriever = WindowRetriever()
        return window_retriever.combine_context(documents)


def register():
    """
    Registra este plugin no sistema de extensões
    """
    return {
        'name': 'entity_aware_retriever',
        'version': '1.0.0',
        'description': 'Entity-aware retriever with anti-contamination filtering',
        'retrievers': [EntityAwareRetriever()],
        'compatible_verba_version': '>=2.1.0',
    }

