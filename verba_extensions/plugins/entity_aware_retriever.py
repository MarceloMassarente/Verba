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
            description="Limit value or sensitivity (for initial search)",
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
        self.config["Reranker Top K"] = InputConfig(
            type="number",
            value=5,
            description="Number of top chunks to return after reranking (default: 5, use 0 to return all)",
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
        # Ler reranker_top_k da configuração
        reranker_top_k_config = config.get("Reranker Top K", {})
        if reranker_top_k_config and hasattr(reranker_top_k_config, 'value'):
            reranker_top_k = int(reranker_top_k_config.value)
        else:
            reranker_top_k = 5  # Default
        
        # Verificar se não está confundindo com Limit/Sensitivity
        if reranker_top_k == limit and limit != 5:
            msg.warn(f"  ⚠️ ATENÇÃO: reranker_top_k={reranker_top_k} é igual a limit={limit}! Isso pode indicar que 'Reranker Top K' não está na configuração e está usando limit por engano.")
            # Se for igual ao limit e limit não for o default, usar 5 como fallback seguro
            if limit < 5:
                msg.warn(f"  ⚠️ Usando reranker_top_k=5 como fallback seguro (limit={limit} é muito baixo para reranker)")
                reranker_top_k = 5
        
        msg.good(f"  ⚙️ CONFIG RETRIEVER: limit={limit} (busca inicial), reranker_top_k={reranker_top_k} (pós-rerank)")
        if reranker_top_k == 2:
            msg.warn(f"  ⚠️ ATENÇÃO: reranker_top_k={reranker_top_k} está limitando demais! Considere aumentar para 5-10 na interface.")
        elif reranker_top_k < 5:
            msg.warn(f"  ⚠️ reranker_top_k={reranker_top_k} pode ser muito baixo. Recomendado: 5-10")
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
        
        # DIAGNÓSTICO: Verificar se spaCy e Gazetteer estão disponíveis
        try:
            from verba_extensions.plugins.entity_aware_query_orchestrator import get_nlp, load_gazetteer, detect_query_language
            query_language = detect_query_language(query)
            msg.info(f"  🌐 DIAGNÓSTICO: Idioma da query detectado: {query_language.upper()}")
            
            # Tentar carregar modelo para o idioma detectado
            nlp_model = get_nlp(language=query_language)
            gaz = load_gazetteer()
            
            if not nlp_model:
                msg.warn(f"  ⚠️ DIAGNÓSTICO: spaCy não está disponível para {query_language.upper()} - entidades NÃO serão detectadas")
                if query_language == "pt":
                    msg.warn(f"  💡 Instale: python -m spacy download pt_core_news_sm")
                elif query_language == "en":
                    msg.warn(f"  💡 Instale: python -m spacy download en_core_web_sm")
                else:
                    msg.warn(f"  💡 Instale modelo spaCy apropriado para {query_language}")
            else:
                model_name = nlp_model.meta.get('name', 'unknown')
                msg.info(f"  ✅ DIAGNÓSTICO: spaCy está disponível (modelo: {model_name}, idioma: {query_language.upper()})")
            
            if not gaz:
                msg.warn(f"  ⚠️ DIAGNÓSTICO: Gazetteer vazio ou não encontrado - entidades NÃO serão mapeadas")
                msg.warn(f"  💡 Verifique se existe: verba_extensions/resources/gazetteer.json")
            else:
                gaz_size = len(gaz)
                msg.info(f"  ✅ DIAGNÓSTICO: Gazetteer carregado com {gaz_size} entidades")
                # Mostrar algumas entidades como exemplo
                if gaz_size > 0:
                    sample_entities = list(gaz.items())[:3]
                    sample_text = ", ".join([f"{eid} ({len(aliases)} aliases)" for eid, aliases in sample_entities])
                    msg.info(f"  ℹ️ Exemplos: {sample_text}")
        except Exception as e:
            msg.warn(f"  ⚠️ Erro ao verificar diagnóstico de entidades: {str(e)}")
        
        parse_query_text = rewritten_query if enable_query_rewriting or rewritten_query != query else query
        parsed = parse_query(parse_query_text)
        parsed_entity_ids = [e["entity_id"] for e in parsed["entities"] if e["entity_id"]]
        semantic_terms = parsed["semantic_concepts"]
        
        # Combinar entidades do builder e do parser (priorizar builder)
        entity_ids = builder_entities if builder_entities else parsed_entity_ids
        
        msg.info(f"  🔍 Entidades detectadas: {entity_ids} (builder: {builder_entities}, parser: {parsed_entity_ids})")
        msg.info(f"  🔍 Conceitos semânticos: {semantic_terms}")
        
        # DIAGNÓSTICO: Se não encontrou entidades, mostrar por quê
        if not entity_ids:
            msg.warn(f"  ⚠️ DIAGNÓSTICO: Nenhuma entidade detectada na query: '{query}'")
            if parsed.get("entities"):
                entities_without_id = [e["text"] for e in parsed["entities"] if not e.get("entity_id")]
                if entities_without_id:
                    msg.warn(f"  💡 Menções detectadas pelo spaCy mas SEM entity_id no gazetteer: {entities_without_id}")
                    msg.warn(f"  💡 Adicione essas entidades ao gazetteer.json para habilitar filtros")
            else:
                msg.warn(f"  💡 Nenhuma menção detectada pelo spaCy (ORG, PERSON, GPE, LOC)")
                msg.warn(f"  💡 Verifique se a query contém nomes próprios (empresas, pessoas, lugares)")
        
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
                    # IMPORTANTE: O reranker tem sua própria configuração de top_k
                    # O `limit` é usado apenas para a busca inicial (Autocut/Fixed)
                    # O `Reranker Top K` controla quantos chunks passam pelo reranking
                    num_chunks = len(chunk_objects)
                    
                    # Se reranker_top_k = 0, rerankear todos os chunks recuperados
                    # Caso contrário, usar o valor configurado (mas não mais que os chunks disponíveis)
                    if reranker_top_k == 0:
                        top_k_for_rerank = num_chunks  # Rerankear todos
                    else:
                        top_k_for_rerank = min(reranker_top_k, num_chunks)  # Usar config ou todos, o que for menor
                    
                    msg.good(f"  🔄 RERANKER INPUT: {num_chunks} chunks recuperados, top_k={top_k_for_rerank} (limit={limit} busca inicial, reranker_top_k={reranker_top_k})")
                    msg.info(f"  Reranker config: top_k={top_k_for_rerank}, query='{query[:50]}...'")
                    
                    reranked_objects = await reranker.process_chunks(
                        chunk_objects,
                        query=query,
                        config={"top_k": top_k_for_rerank}
                    )
                    
                    msg.info(f"  Reranker retornou {len(reranked_objects)} chunks (esperado: {top_k_for_rerank})")
                    if len(reranked_objects) < top_k_for_rerank:
                        msg.warn(f"  ⚠️ Reranker retornou menos chunks ({len(reranked_objects)}) do que esperado ({top_k_for_rerank})")
                    if len(reranked_objects) > 0:
                        msg.info(f"  Primeiro chunk rerankado: chunk_id={reranked_objects[0].chunk_id}, content_preview='{reranked_objects[0].content[:50]}...'")
                    
                    # Reconstrói chunks Weaviate a partir dos rerankeados
                    # IMPORTANTE: chunk.chunk_id é str(chunk.uuid) do objeto Weaviate original
                    reranked_uuids = {str(chunk.chunk_id) for chunk in reranked_objects}
                    chunks_filtered = [c for c in chunks if str(c.uuid) in reranked_uuids]
                    
                    msg.info(f"  Chunks filtrados: {len(chunks_filtered)} de {len(chunks)} originais")
                    
                    # Reordena conforme reranking
                    uuid_to_chunk = {str(c.uuid): c for c in chunks_filtered}
                    chunks_ordered = []
                    for reranked_chunk in reranked_objects:
                        chunk_uuid = str(reranked_chunk.chunk_id)
                        if chunk_uuid in uuid_to_chunk:
                            chunks_ordered.append(uuid_to_chunk[chunk_uuid])
                        else:
                            msg.warn(f"  ⚠️ Chunk {chunk_uuid} do reranker não encontrado nos chunks originais")
                    
                    chunks = chunks_ordered
                    
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
        
        # Obter chunk_window da config para passar ao filtro de qualidade
        chunk_window_config = config.get("Chunk Window", {})
        chunk_window = int(chunk_window_config.value) if hasattr(chunk_window_config, 'value') else 0
        
        # Gerar contexto combinado (isso filtra chunks de baixa qualidade)
        context, filtered_context_documents = self.combine_context(sorted_context_documents, chunk_window=chunk_window)
        
        # IMPORTANTE: Atualizar documents para refletir chunks filtrados
        # Isso garante que o frontend mostre os mesmos chunks que foram enviados ao LLM
        # Criar um mapeamento dos chunks filtrados por documento
        filtered_documents_map = {doc["uuid"]: doc for doc in filtered_context_documents}
        
        # Atualizar sorted_documents para refletir apenas chunks filtrados
        updated_documents = []
        total_chunks_before = 0
        total_chunks_after = 0
        for doc in sorted_documents:
            doc_uuid = doc["uuid"]
            if doc_uuid in filtered_documents_map:
                filtered_doc = filtered_documents_map[doc_uuid]
                # Criar lista de chunks atualizada (sem content, apenas metadados)
                filtered_chunks_metadata = [
                    {
                        "uuid": chunk["uuid"],
                        "score": chunk["score"],
                        "chunk_id": chunk["chunk_id"],
                        "embedder": embedder,
                    }
                    for chunk in filtered_doc["chunks"]
                ]
                total_chunks_before += len(doc["chunks"])
                total_chunks_after += len(filtered_chunks_metadata)
                
                updated_doc = doc.copy()
                updated_doc["chunks"] = filtered_chunks_metadata
                updated_documents.append(updated_doc)
            else:
                # Documento foi completamente filtrado (todos os chunks eram de baixa qualidade)
                total_chunks_before += len(doc["chunks"])
                # Não adicionar ao updated_documents
        
        # Adicionar informação sobre filtragem ao debug_info
        chunks_filtered = total_chunks_before - total_chunks_after
        if chunks_filtered > 0:
            debug_info["chunks_filtered"] = {
                "total_before": total_chunks_before,
                "total_after": total_chunks_after,
                "filtered_count": chunks_filtered,
                "message": f"{chunks_filtered} chunks filtrados por baixa qualidade"
            }
            msg.warn(f"  ⚠️ {chunks_filtered}/{total_chunks_before} chunks filtrados - frontend atualizado para mostrar apenas chunks válidos")
        
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
        if debug_info.get('chunks_filtered'):
            debug_summary += f"Chunks filtrados: {debug_info['chunks_filtered']['message']}\n"
        if debug_info.get('explanation'):
            debug_summary += f"Explicação: {debug_info['explanation']}\n"
        
        # Retornar com informações de debug como terceiro elemento (para API)
        # Mas também incluir no contexto para compatibilidade
        context_with_debug = context + debug_summary
        
        # Retornar documents atualizados (com chunks filtrados)
        return (updated_documents, context_with_debug, debug_info)
    
    async def _process_chunks(self, client, chunks, weaviate_manager, embedder, config):
        """Processa chunks aplicando window technique"""
        
        chunk_window_config = config.get("Chunk Window", {})
        if hasattr(chunk_window_config, 'value'):
            chunk_window = int(chunk_window_config.value)
        else:
            chunk_window = 1  # Default
        
        msg.info(f"  📦 Chunk Window: {chunk_window} (vai combinar chunks adjacentes)")
        
        if chunk_window > 0 and chunks:
            # Agrupa chunks adjacentes com window, evitando repetição excessiva
            windowed_chunks = []
            for i, chunk in enumerate(chunks):
                context_chunks = chunks[max(0, i - chunk_window):min(len(chunks), i + chunk_window + 1)]
                
                # Coletar conteúdos únicos (evitar duplicação exata)
                contents = []
                seen_contents = set()
                for c in context_chunks:
                    content = c.properties["content"] if hasattr(c, "properties") else c.get("content", "")
                    content_normalized = content.strip().lower()
                    # Evitar adicionar conteúdo exatamente igual
                    if content_normalized and content_normalized not in seen_contents:
                        contents.append(content)
                        seen_contents.add(content_normalized)
                
                # Combinar com separador adequado
                combined_content = " ".join(contents)
                
                # Se o conteúdo combinado for muito repetitivo, usar apenas o chunk central
                # (evitar criar repetição massiva)
                if len(contents) > 1:
                    # Verificar se há repetição excessiva na combinação
                    words = combined_content.split()
                    if len(words) > 10:
                        # Contar repetições de sequências curtas
                        seq_counts = {}
                        for seq_len in [3, 4]:
                            if len(words) >= seq_len * 2:
                                for j in range(len(words) - seq_len + 1):
                                    seq = " ".join(words[j:j+seq_len])
                                    seq_counts[seq] = seq_counts.get(seq, 0) + 1
                        
                        max_repetition = max(seq_counts.values()) if seq_counts else 0
                        # Se há muita repetição (mais de 5x), usar apenas o chunk central
                        if max_repetition > 5:
                            msg.warn(f"  ⚠️ Chunk Window: repetição detectada ({max_repetition}x) ao combinar chunks, usando apenas chunk central")
                            central_content = context_chunks[len(context_chunks)//2]
                            combined_content = central_content.properties["content"] if hasattr(central_content, "properties") else central_content.get("content", "")
                
                # Atualiza o content do chunk atual
                if hasattr(chunk, "properties"):
                    chunk.properties["content"] = combined_content
                else:
                    chunk["content"] = combined_content
                windowed_chunks.append(chunk)
            chunks = windowed_chunks
        
        return (chunks, "Chunks retrieved with entity-aware filtering")
    
    def _is_chunk_quality_good(self, chunk_content: str, chunk_window: int = 0) -> bool:
        """Valida qualidade do chunk antes de incluir no contexto
        
        Detecta:
        - Chunks repetitivos (mesmo texto repetido múltiplas vezes)
        - Chunks fragmentados (começam/fim no meio de palavras)
        - Chunks muito curtos ou vazios
        
        NÃO filtra:
        - Tabelas/gráficos (muitos números, poucas palavras)
        - Chunks com dados estruturados legítimos
        - Chunks combinados via Chunk Window (espera-se alguma repetição)
        - Repetições de cabeçalhos/rodapés de documento (normal em PDFs)
        
        Args:
            chunk_content: Conteúdo do chunk a validar
            chunk_window: Tamanho do chunk window usado (0 = não usado)
        """
        if not chunk_content or len(chunk_content.strip()) < 10:
            return False
        
        content = chunk_content.strip()
        words = content.split()
        if len(words) < 3:
            return False
        
        # Detectar e remover cabeçalhos/rodapés comuns de documentos PDF
        # Cabeçalhos/rodapés geralmente aparecem no início ou fim e são repetidos em múltiplos chunks
        # Exemplo: "Documento de discussão São Paulo, 17 de setembro de 2025 1 AGENDA Sobre a..."
        import re
        
        # Padrões comuns de cabeçalhos/rodapés
        lines = content.split('\n')
        
        # Verificar primeiras 2-3 linhas (possível cabeçalho)
        header_lines = [line.strip() for line in lines[:3] if line.strip()]
        # Verificar últimas 2-3 linhas (possível rodapé)
        footer_lines = [line.strip() for line in lines[-3:] if line.strip()]
        
        # Padrões de palavras-chave de cabeçalhos/rodapés
        header_footer_keywords = ['documento', 'discussão', 'agenda', 'página', 'data', 'setembro', 
                                  'outubro', 'novembro', 'dezembro', 'janeiro', 'fevereiro', 'março', 
                                  'abril', 'maio', 'junho', 'julho', 'agosto']
        
        potential_headers_footers = []
        
        # 1. Verificar linhas individuais (cabeçalhos simples)
        for line in header_lines + footer_lines:
            if len(line) < 150 and any(keyword in line.lower() for keyword in header_footer_keywords):
                potential_headers_footers.append(line)
        
        # 2. Detectar padrão específico: "Documento de discussão [Local] [Data] [Número] AGENDA [Tópicos]"
        # Padrão flexível que captura o cabeçalho completo
        header_pattern = r'Documento de discussão[^.]*?\d+\s+de\s+\w+\s+de\s+\d+[^.]*?AGENDA[^.]*?(?:Modelo|Abordagem|Sobre|Sobre a|da|de|na|em)'
        content_start = content[:250]  # Primeiros 250 caracteres (onde cabeçalho geralmente está)
        header_match = re.search(header_pattern, content_start, re.IGNORECASE)
        if header_match:
            header_text = header_match.group(0).strip()
            if header_text not in potential_headers_footers:
                potential_headers_footers.append(header_text)
        
        # 3. Detectar sequências repetitivas no início que parecem cabeçalhos
        # Se os primeiros 80-150 caracteres aparecem múltiplas vezes, provavelmente é cabeçalho
        for check_len in [80, 120, 150]:
            first_chars = content[:check_len].strip()
            if len(first_chars) < 40:  # Muito curto, pular
                continue
            # Contar quantas vezes aparece (case-insensitive)
            occurrences = len(re.findall(re.escape(first_chars), content, re.IGNORECASE))
            # Se aparece 2+ vezes e contém palavras-chave de cabeçalho, é provável cabeçalho
            if occurrences >= 2 and any(keyword in first_chars.lower() for keyword in header_footer_keywords):
                if first_chars not in potential_headers_footers:
                    potential_headers_footers.append(first_chars)
                break  # Encontrou um, não precisa verificar outros tamanhos
        
        # Remover cabeçalhos/rodapés do conteúdo para verificação de repetição
        content_for_repetition_check = content
        if potential_headers_footers:
            # Remover ocorrências de cabeçalhos/rodapés (podem aparecer múltiplas vezes)
            for header_footer in potential_headers_footers:
                # Remover todas as ocorrências (case-insensitive parcial)
                # Usar regex para remover variações
                escaped = re.escape(header_footer)
                # Permitir pequenas variações (espaços extras, etc.)
                pattern = escaped.replace(r'\ ', r'\s+')
                content_for_repetition_check = re.sub(pattern, ' ', content_for_repetition_check, flags=re.IGNORECASE)
            
            # Limpar espaços múltiplos
            content_for_repetition_check = re.sub(r'\s+', ' ', content_for_repetition_check).strip()
            msg.info(f"  ℹ️ Cabeçalhos/rodapés detectados e ignorados: {len(potential_headers_footers)} padrões")
        
        # Se após remover cabeçalhos/rodapés o conteúdo ficou muito pequeno, usar conteúdo original
        if len(content_for_repetition_check.split()) < 5:
            content_for_repetition_check = content
        
        # Verificar se é uma tabela/gráfico (muitos números, poucas palavras)
        # Chunks de tabelas/gráficos são legítimos mesmo que tenham padrões repetitivos
        numbers = re.findall(r'\d+', content)
        number_ratio = len(numbers) / len(words) if words else 0
        
        # Se mais de 30% do conteúdo são números, provavelmente é tabela/gráfico
        # Aceitar esses chunks mesmo com repetição
        is_likely_table_or_chart = number_ratio > 0.3
        
        if is_likely_table_or_chart:
            # Para tabelas/gráficos, ser mais permissivo com repetição
            # Apenas filtrar se for claramente um erro (sequência muito curta repetida muitas vezes)
            if len(words) > 20:  # Tabelas grandes são OK
                return True
        
        # Ajustar threshold baseado no chunk window
        # Quando chunks são combinados (chunk_window > 0), espera-se mais repetição
        # porque chunks adjacentes podem ter conteúdo similar
        base_threshold_short = 5  # Sequências curtas (3 palavras): aceita até 5 repetições
        base_threshold_medium = 4  # Sequências médias (4 palavras): aceita até 4 repetições
        base_threshold_long = 3   # Sequências longas (5 palavras): aceita até 3 repetições
        
        # Aumentar threshold se chunk window está ativo (chunks combinados)
        if chunk_window > 0:
            # Chunks combinados podem ter mais repetição natural
            window_multiplier = 1.5 + (chunk_window * 0.3)  # Ex: window=3 → multiplier=2.4
            base_threshold_short = int(base_threshold_short * window_multiplier)
            base_threshold_medium = int(base_threshold_medium * window_multiplier)
            base_threshold_long = int(base_threshold_long * window_multiplier)
        
        # Ajustar ainda mais para tabelas/gráficos
        if is_likely_table_or_chart:
            base_threshold_short = max(base_threshold_short, 8)
            base_threshold_medium = max(base_threshold_medium, 6)
            base_threshold_long = max(base_threshold_long, 5)
        
        # Usar conteúdo sem cabeçalhos/rodapés para verificação de repetição
        words_for_repetition = content_for_repetition_check.split()
        
        # Detectar repetição excessiva: verifica sequências de diferentes tamanhos
        # Verificar se há padrões repetitivos (mesma sequência de palavras repetida)
        # Exemplo: "mização da revisão tarifária" repetido múltiplas vezes
        # Verifica sequências de 3, 4 e 5 palavras para capturar diferentes padrões
        max_repetition = 0
        max_repetition_seq_length = 0
        
        for seq_length in [3, 4, 5]:
            if len(words_for_repetition) < seq_length:
                continue
            word_sequences = {}
            for i in range(len(words_for_repetition) - seq_length + 1):
                seq = " ".join(words_for_repetition[i:i+seq_length])
                word_sequences[seq] = word_sequences.get(seq, 0) + 1
            
            current_max = max(word_sequences.values()) if word_sequences else 0
            if current_max > max_repetition:
                max_repetition = current_max
                max_repetition_seq_length = seq_length
        
        # Aplicar threshold apropriado baseado no tamanho da sequência repetida
        if max_repetition_seq_length == 3:
            threshold = base_threshold_short
        elif max_repetition_seq_length == 4:
            threshold = base_threshold_medium
        elif max_repetition_seq_length == 5:
            threshold = base_threshold_long
        else:
            threshold = base_threshold_medium  # Default
        
        # Filtrar apenas se repetição for claramente excessiva
        # E também verificar se a repetição representa uma fração significativa do chunk
        # Usar words_for_repetition (sem cabeçalhos/rodapés) para cálculo de fração
        if max_repetition > threshold:
            # Calcular fração do chunk ocupada pela sequência repetida (usando conteúdo sem cabeçalhos/rodapés)
            repeated_fraction = (max_repetition * max_repetition_seq_length) / len(words_for_repetition) if len(words_for_repetition) > 0 else 0
            
            # Filtrar apenas se repetição é alta E ocupa mais de 40% do chunk (sem cabeçalhos/rodapés)
            # (permite repetição moderada em chunks longos)
            if repeated_fraction > 0.4:
                msg.warn(f"  ⚠️ Chunk filtrado: conteúdo repetitivo detectado (sequência de {max_repetition_seq_length} palavras repetida {max_repetition} vezes, {int(repeated_fraction * 100)}% do conteúdo útil, threshold={threshold})")
                return False
            else:
                # Repetição alta mas não ocupa tanto espaço - provavelmente OK
                msg.info(f"  ℹ️ Repetição moderada detectada ({max_repetition}x), mas apenas {int(repeated_fraction * 100)}% do conteúdo útil - mantendo")
                return True
        
        # Verificação adicional: detectar repetição de frases completas (não apenas sequências curtas)
        # Útil para casos como "mização da revisão tarifária" ou frases completas repetidas
        # Para tabelas/gráficos, verificar apenas frases longas (não números)
        min_phrase_length = 6 if is_likely_table_or_chart else 4
        max_phrase_length = 15  # Frases muito longas podem ser parágrafos completos
        
        # Ajustar thresholds de repetição de frases baseado no chunk window
        # Quando chunks são combinados, frases podem se repetir mais naturalmente
        phrase_repetition_multiplier = 1.0
        if chunk_window > 0:
            phrase_repetition_multiplier = 1.5 + (chunk_window * 0.2)  # Ex: window=3 → multiplier=2.1
        
        if len(words_for_repetition) > 10:
            # Verificar sequências de diferentes tamanhos (4-15 palavras)
            # Usar words_for_repetition para ignorar repetições de cabeçalhos/rodapés
            for seq_length in range(min_phrase_length, min(max_phrase_length + 1, len(words_for_repetition) // 2 + 1)):
                if len(words_for_repetition) < seq_length * 2:  # Precisa ter pelo menos 2 repetições
                    continue
                
                phrase_counts = {}
                for i in range(len(words_for_repetition) - seq_length + 1):
                    phrase = " ".join(words_for_repetition[i:i+seq_length])
                    # Para tabelas/gráficos, ignorar sequências que são principalmente números
                    if is_likely_table_or_chart:
                        # Se a frase tem mais de 50% números, provavelmente é parte de uma tabela legítima
                        phrase_numbers = len(re.findall(r'\d+', phrase))
                        if phrase_numbers / seq_length > 0.5:
                            continue
                    
                    phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
                
                if phrase_counts:
                    most_common_phrase = max(phrase_counts.items(), key=lambda x: x[1])
                    phrase_text, phrase_count = most_common_phrase
                    
                    # Para frases longas (8+ palavras), ser mais permissivo
                    # Para frases médias (4-7 palavras), ser mais restritivo
                    if seq_length >= 8:
                        # Frases longas: filtrar apenas se aparecer muitas vezes E representar >30% do chunk
                        threshold_ratio = 0.3
                        min_repetitions = int(2 * phrase_repetition_multiplier)
                    else:
                        # Frases médias: filtrar se aparecer muitas vezes E representar >40% do chunk
                        threshold_ratio = 0.4
                        min_repetitions = int(2 * phrase_repetition_multiplier)
                    
                    # Aumentar threshold_ratio quando chunk window está ativo (mais tolerante)
                    if chunk_window > 0:
                        threshold_ratio = threshold_ratio * (1.0 + chunk_window * 0.1)  # Ex: window=3 → +30%
                    
                    # Usar words_for_repetition para calcular fração (ignora cabeçalhos/rodapés)
                    if phrase_count >= min_repetitions and (phrase_count * seq_length) / len(words_for_repetition) > threshold_ratio:
                        msg.warn(f"  ⚠️ Chunk filtrado: frase repetitiva detectada ('{phrase_text[:60]}...' aparece {phrase_count} vezes, {int((phrase_count * seq_length) / len(words_for_repetition) * 100)}% do conteúdo útil, {seq_length} palavras, min_repetitions={min_repetitions}, threshold_ratio={threshold_ratio:.2f})")
                        return False
        
        # Detectar fragmentação: chunk começa ou termina no meio de palavra
        # (palavras muito curtas no início/fim podem indicar fragmentação)
        if len(words) > 0:
            first_word = words[0]
            last_word = words[-1]
            # Palavras muito curtas no início/fim podem ser fragmentos
            if len(first_word) < 3 and len(words) > 1:
                msg.warn(f"  ⚠️ Chunk filtrado: possível fragmentação detectada (começa com palavra muito curta: '{first_word}')")
                return False
        
        return True
    
    def combine_context(self, documents: list[dict], chunk_window: int = 0) -> tuple[str, list[dict]]:
        """Combina contexto dos documentos, filtrando chunks de baixa qualidade
        
        Args:
            documents: Lista de documentos com chunks
            chunk_window: Tamanho do chunk window usado (para ajustar thresholds de qualidade)
        
        Returns:
            tuple: (context_string, filtered_documents)
        """
        from goldenverba.components.retriever.WindowRetriever import WindowRetriever
        
        # Filtrar chunks de baixa qualidade antes de combinar
        filtered_documents = []
        total_chunks = 0
        filtered_chunks = 0
        
        for document in documents:
            filtered_chunks_list = []
            for chunk in document["chunks"]:
                total_chunks += 1
                chunk_content = chunk.get("content", "")
                if self._is_chunk_quality_good(chunk_content, chunk_window=chunk_window):
                    filtered_chunks_list.append(chunk)
                else:
                    filtered_chunks += 1
            
            # Só adicionar documento se tiver pelo menos um chunk válido
            if filtered_chunks_list:
                filtered_document = document.copy()
                filtered_document["chunks"] = filtered_chunks_list
                filtered_documents.append(filtered_document)
        
        # FALLBACK: Se todos os chunks foram filtrados, usar os chunks originais (mesmo com repetição)
        # Isso evita retornar contexto vazio quando o filtro é muito restritivo
        if len(filtered_documents) == 0 and len(documents) > 0:
            msg.warn(f"  ⚠️ ATENÇÃO: Todos os {total_chunks} chunks foram filtrados!")
            msg.warn(f"  ⚠️ Usando fallback: mantendo todos os chunks originais (mesmo com possível repetição)")
            
            # Usar documentos originais como fallback
            filtered_documents = documents
            filtered_chunks = 0  # Resetar contador para não confundir
        
        if filtered_chunks > 0:
            msg.warn(f"  ⚠️ {filtered_chunks}/{total_chunks} chunks filtrados por baixa qualidade")
        
        # Usar método do WindowRetriever para combinar contexto
        window_retriever = WindowRetriever()
        context = window_retriever.combine_context(filtered_documents)
        
        return (context, filtered_documents)


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

