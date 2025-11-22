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
        self.config["Entity Filter Mode"] = InputConfig(
            type="dropdown",
            value="adaptive",
            description="Entity filter strategy: strict (hard filter), boost (soft boost), adaptive (fallback), hybrid (syntax-based)",
            values=["strict", "boost", "adaptive", "hybrid"],
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
        self.config["Enable Framework Filter"] = InputConfig(
            type="bool",
            value=True,
            description="Enable framework/company/sector filtering in search",
            values=[],
        )
        self.config["Enable Multi-Vector Search"] = InputConfig(
            type="bool",
            value=False,
            description="Enable multi-vector search using named vectors (concept_vec, sector_vec, company_vec)",
            values=[],
        )
        self.config["Enable Aggregation"] = InputConfig(
            type="bool",
            value=False,
            description="Enable aggregation queries for analytics (count, group by, etc.)",
            values=[],
        )
        self.config["Two-Phase Search Mode"] = InputConfig(
            type="dropdown",
            value="auto",
            description="Two-phase search: first filter by entities, then multi-vector search within subspace",
            values=["auto", "enabled", "disabled"],
        )
        self.config["Enable Query Expansion"] = InputConfig(
            type="bool",
            value=True,
            description="Enable query expansion (generates 3-5 variations to improve Recall)",
            values=[],
        )
        self.config["Enable Relative Score Fusion"] = InputConfig(
            type="bool",
            value=True,
            description="Enable Relative Score Fusion (preserves magnitude, better than RRF)",
            values=[],
        )
        self.config["Enable Dynamic Alpha"] = InputConfig(
            type="bool",
            value=True,
            description="Enable dynamic alpha optimization based on query type",
            values=[],
        )
    
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
                msg.warn(f"    Fase 1: Nenhum chunk encontrado com entidades")
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
            
            # Multi-Vector Search na Fase 2
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
                    
                    # Configurar fusion type
                    enable_relative_score = self.config.get("Enable Relative Score Fusion", {}).get("value", True)
                    fusion_type = "RELATIVE_SCORE" if enable_relative_score else "RRF"
                    
                    # Configurar query_properties para BM25 boosting
                    query_properties = ["content", "title^2"]  # Boost de título
                    
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
            )
            
            if phase2_chunks:
                msg.good(f"    Fase 2: {len(phase2_chunks)} chunks retornados (fallback)")
                debug_info["two_phase_search"]["phase2_results"] = len(phase2_chunks)
                return phase2_chunks
            else:
                msg.warn(f"    Fase 2: Nenhum chunk retornado")
                return []
                
        except Exception as e:
            msg.warn(f"  Erro em Two-Phase Search: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _detect_entity_focus_in_query(self, query: str, entities: List[str]) -> bool:
        """
        Detecta se a query tem foco explícito em entidades (para modo hybrid)
        
        Padrões que indicam foco em entidade:
        - "sobre [entidade]"
        - "da [entidade]"
        - "[entidade] fez/tem/é"
        - "comparar [entidade] com"
        - apenas a entidade sem contexto
        
        Returns:
            True se query tem foco explícito em entidade
            False se query é exploratória/conceitual
        """
        if not entities:
            return False
        
        query_lower = query.lower()
        
        # Padrões de foco explícito em entidade
        explicit_patterns = [
            r'\b(sobre|da|do|de)\s+{entity}',  # "sobre Apple"
            r'\b{entity}\s+(fez|tem|é|foi|tinha|apresentou)',  # "Apple fez"
            r'\b(comparar|compare|diferença|vs|versus)\s+{entity}',  # "comparar Apple"
            r'\b{entity}\s+e\s+{entity}',  # "Apple e Microsoft"
            r'^{entity}',  # Query começa com entidade
            r'{entity}$',  # Query termina com entidade
        ]
        
        import re
        for entity in entities:
            entity_escaped = re.escape(entity.lower())
            for pattern in explicit_patterns:
                pattern_filled = pattern.replace('{entity}', entity_escaped)
                if re.search(pattern_filled, query_lower, re.IGNORECASE):
                    return True
        
        # Se query é curta (<5 palavras) e contém entidade, assume foco
        words = query_lower.split()
        if len(words) <= 5:
            for entity in entities:
                if entity.lower() in query_lower:
                    return True
        
        return False
    
    def _detect_aggregation_query(self, query: str) -> bool:
        """
        Detecta se a query é uma query de agregação/analytics.
        
        Padrões que indicam agregação:
        - "quantos documentos"
        - "count"
        - "agrupar por"
        - "group by"
        - "quantidade de"
        
        Args:
            query: Query do usuário
        
        Returns:
            True se é query de agregação
        """
        query_lower = query.lower()
        
        aggregation_keywords = [
            "quantos",
            "quantas",
            "count",
            "agrupar",
            "group by",
            "quantidade",
            "total de",
            "número de",
            "estatísticas",
            "analytics",
            "agregação"
        ]
        
        return any(keyword in query_lower for keyword in aggregation_keywords)
    
    def _extract_group_by_from_query(self, query: str) -> Optional[List[str]]:
        """
        Extrai propriedades para group_by da query.
        
        Args:
            query: Query do usuário
        
        Returns:
            Lista de propriedades para agrupar ou None
        """
        query_lower = query.lower()
        
        # Mapear termos da query para propriedades Weaviate
        property_mapping = {
            "framework": "frameworks",
            "empresa": "companies",
            "setor": "sectors",
            "company": "companies",
            "sector": "sectors",
            "data": "chunk_date",
            "date": "chunk_date",
            "idioma": "chunk_lang",
            "language": "chunk_lang"
        }
        
        group_by = []
        for term, property_name in property_mapping.items():
            if term in query_lower:
                group_by.append(property_name)
        
        return group_by if group_by else None
    
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
        entity_filter_mode = config.get("Entity Filter Mode", {}).value if isinstance(config.get("Entity Filter Mode"), InputConfig) else "adaptive"
        enable_semantic = config.get("Enable Semantic Search", {}).value if isinstance(config.get("Enable Semantic Search"), InputConfig) else True
        enable_query_rewriting = config.get("Enable Query Rewriting", {}).value if isinstance(config.get("Enable Query Rewriting"), InputConfig) else False
        cache_ttl = int(config.get("Query Rewriter Cache TTL", {}).value) if isinstance(config.get("Query Rewriter Cache TTL"), InputConfig) else 3600
        enable_temporal_filter = config.get("Enable Temporal Filter", {}).value if isinstance(config.get("Enable Temporal Filter"), InputConfig) else True
        date_field_name = config.get("Date Field Name", {}).value if isinstance(config.get("Date Field Name"), InputConfig) else "chunk_date"
        enable_aggregation = config.get("Enable Aggregation", {}).value if isinstance(config.get("Enable Aggregation"), InputConfig) else False
        
        msg.info(f"🎯 Entity Filter Mode: {entity_filter_mode}")
        
        # 0.5. VERIFICAR SE É QUERY DE AGREGAÇÃO
        is_aggregation_query = False
        if enable_aggregation:
            is_aggregation_query = self._detect_aggregation_query(query)
            if is_aggregation_query:
                try:
                    # Normalizar nome da collection
                    normalized = weaviate_manager._normalize_embedder_name(embedder)
                    collection_name = weaviate_manager.embedding_table.get(embedder, f"VERBA_Embedding_{normalized}")
                    
                    # Executar aggregation
                    from verba_extensions.utils.aggregation_wrapper import get_aggregation_wrapper
                    aggregation_wrapper = get_aggregation_wrapper()
                    
                    # Detectar propriedades para group_by
                    group_by = self._extract_group_by_from_query(query)
                    
                    # Executar aggregation
                    result = await aggregation_wrapper.aggregate_over_all(
                        client=client,
                        collection_name=collection_name,
                        group_by=group_by,
                        total_count=True,
                        use_http_fallback=True
                    )
                    
                    # Converter resultado para formato de chunks (para compatibilidade)
                    # Retornar resultado formatado
                    msg.good(f"  ✅ Aggregation executada: {result}")
                    
                    # Por enquanto, retornar lista vazia (aggregation retorna dados analíticos, não chunks)
                    # Em uma implementação futura, poderia retornar um formato especial
                    return []
                    
                except Exception as e:
                    msg.warn(f"  ⚠️ Erro ao executar aggregation: {str(e)}, usando busca normal")
                    is_aggregation_query = False
        
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
            
            # Alpha Dinâmico (sobrescreve se habilitado)
            enable_dynamic_alpha = self.config.get("Enable Dynamic Alpha", {}).get("value", True)
            if enable_dynamic_alpha:
                try:
                    from verba_extensions.plugins.alpha_optimizer import AlphaOptimizerPlugin
                    alpha_optimizer = AlphaOptimizerPlugin()
                    
                    # Detectar entidades para cálculo de alpha
                    detected_entities = builder_entities if builder_entities else []
                    intent = strategy.get("intent", "search")
                    
                    optimal_alpha = await alpha_optimizer.calculate_optimal_alpha(
                        query=query,
                        entities=detected_entities,
                        intent=intent
                    )
                    
                    rewritten_alpha = optimal_alpha
                    debug_info["alpha_optimized"] = optimal_alpha
                    debug_info["alpha_optimizer_used"] = True
                    msg.info(f"  Alpha Dinâmico: ajustado para {optimal_alpha}")
                except Exception as e:
                    msg.debug(f"  Alpha Dinâmico não disponível: {str(e)}")
            
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
                    
                    # Alpha Dinâmico (sobrescreve se habilitado)
                    enable_dynamic_alpha = self.config.get("Enable Dynamic Alpha", {}).get("value", True)
                    if enable_dynamic_alpha:
                        try:
                            from verba_extensions.plugins.alpha_optimizer import AlphaOptimizerPlugin
                            alpha_optimizer = AlphaOptimizerPlugin()
                            
                            # Detectar entidades para cálculo de alpha (vazio por enquanto, será preenchido depois)
                            optimal_alpha = await alpha_optimizer.calculate_optimal_alpha(
                                query=query,
                                entities=[],
                                intent=intent
                            )
                            
                            rewritten_alpha = optimal_alpha
                            debug_info["alpha_optimized"] = optimal_alpha
                            debug_info["alpha_optimizer_used"] = True
                            msg.info(f"  Alpha Dinâmico: ajustado para {optimal_alpha}")
                        except Exception as e:
                            msg.debug(f"  Alpha Dinâmico não disponível: {str(e)}")
                    
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
        
        # NOVO: Modo inteligente - detectar entidades automaticamente (sem gazetteer obrigatório)
        entity_texts = []  # Menções de texto detectadas (modo inteligente)
        entity_ids = []    # Entity IDs (modo gazetteer, opcional)
        
        # Tentar extrair entidades usando modo inteligente (sem gazetteer)
        try:
            from verba_extensions.plugins.entity_aware_query_orchestrator import extract_entities_from_query
            # Modo inteligente: retorna menções de texto diretamente
            entity_texts = extract_entities_from_query(query, use_gazetteer=False)
            
            # Se há gazetteer, tentar também mapear para entity_ids (opcional)
            try:
                entity_ids_from_gazetteer = extract_entities_from_query(query, use_gazetteer=True)
                if entity_ids_from_gazetteer and all(not eid.startswith("ent:") for eid in entity_ids_from_gazetteer):
                    # Se retornou textos (não entity_ids), usar como fallback
                    entity_texts = entity_ids_from_gazetteer
                else:
                    # Se retornou entity_ids, usar eles
                    entity_ids = entity_ids_from_gazetteer
            except:
                pass
        except Exception as e:
            msg.warn(f"  ⚠️ Erro ao extrair entidades (modo inteligente): {str(e)}")
        
        # Fallback: usar query_parser se modo inteligente não funcionou
        if not entity_texts and not entity_ids:
            parse_query_text = rewritten_query if enable_query_rewriting or rewritten_query != query else query
            parsed = parse_query(parse_query_text)
            parsed_entity_texts = [e["text"] for e in parsed["entities"] if e.get("text")]
            parsed_entity_ids = [e["entity_id"] for e in parsed["entities"] if e.get("entity_id")]
            
            # Usar textos se não houver entity_ids
            if parsed_entity_texts:
                entity_texts = parsed_entity_texts
            if parsed_entity_ids:
                entity_ids = parsed_entity_ids
        
        # Combinar entidades do builder (se houver)
        if builder_entities:
            # Query Builder é mais inteligente (conhece schema) - SEMPRE priorizar suas entidades
            # Pode retornar entity_ids formatados (ent:*) ou textos de entidades (PERSON/ORG)
            if all(isinstance(eid, str) and eid.startswith("ent:") for eid in builder_entities):
                # Entity IDs formatados do gazetteer
                entity_ids = builder_entities
                msg.info(f"  ✅ Query Builder forneceu entity_ids validados: {entity_ids}")
            elif all(isinstance(e, str) for e in builder_entities):
                # Textos de entidades (modo inteligente) - ACEITAR como entity_texts
                # Query Builder é confiável pois analisa schema e contexto
                entity_texts = builder_entities
                msg.info(f"  ✅ Query Builder forneceu textos de entidades: {entity_texts}")
            else:
                # Formato misto ou inválido
                msg.warn(f"  ⚠️ Query Builder retornou formato inválido: {builder_entities}")
        
        # Log final
        if entity_texts:
            msg.info(f"  🔍 Entidades detectadas (modo inteligente): {entity_texts}")
        if entity_ids:
            msg.info(f"  🔍 Entity IDs detectados (via gazetteer): {entity_ids}")
        
        # Usar entity_texts para boostar busca (adicionar à query de keyword search)
        # Isso faz chunks que contenham essas entidades terem score maior
        if entity_texts:
            # Adicionar entidades à query de busca para boostar chunks que as contenham
            entity_boost = " ".join(entity_texts)
            msg.info(f"  ✅ Usando entidades para boostar busca: {entity_boost}")
        
        # NOVA ESTRATÉGIA: Aplicar filtro de entidade APENAS quando:
        # 1. Há entity_ids validados (formato ent:*) do gazetteer, OU
        # 2. Há entity_texts E a query usa sintaxe explícita ("sobre X", "de X", "da X", etc.)
        
        # Detectar se query usa sintaxe explícita de entidade
        # Padrões: "sobre [entidade]", "da [entidade]", "de [entidade]", "na [entidade]", etc.
        # MELHORADO: Inclui artigos opcionais ("sobre a X", "sobre o X")
        # NOVO: Expandido para incluir "menções à", "menções de", "fala sobre", etc.
        explicit_entity_patterns = [
            r'\bsobre\s+(?:a|o|as|os|a\s+)?([A-Z][a-zA-Z\s]+)',  # "sobre Apple", "sobre a Egon Zehnder"
            r'\bda\s+(?:a|o|as|os|a\s+)?([A-Z][a-zA-Z\s]+)',      # "da Microsoft", "da empresa X"
            r'\bde\s+(?:a|o|as|os|a\s+)?([A-Z][a-zA-Z\s]+)',      # "de Google", "de uma empresa"
            r'\bna\s+(?:a|o|as|os|a\s+)?([A-Z][a-zA-Z\s]+)',      # "na China", "na empresa X"
            r'\bmenções?\s+(?:à|a|de|do|da|das|dos)\s+([A-Z][a-zA-Z\s]+)',  # "menções à China", "menção de Apple"
            r'\bmenciona\s+(?:a|o|as|os|a\s+)?([A-Z][a-zA-Z\s]+)',  # "menciona China"
            r'\bfala\s+(?:sobre|de|da|do)\s+(?:a|o|as|os|a\s+)?([A-Z][a-zA-Z\s]+)',  # "fala sobre Apple", "fala da China"
            r'\bfalam\s+(?:sobre|de|da|do)\s+(?:a|o|as|os|a\s+)?([A-Z][a-zA-Z\s]+)',  # "falam sobre Apple"
            r'\babout\s+(?:the\s+)?([A-Z][a-zA-Z\s]+)',         # "about Apple", "about the company"
            r'\bfrom\s+(?:the\s+)?([A-Z][a-zA-Z\s]+)',           # "from Microsoft", "from the company"
            r'\bat\s+(?:the\s+)?([A-Z][a-zA-Z\s]+)',             # "at Google", "at the company"
            r'\bcompara\s+(?:a|o|as|os|a\s+)?([A-Z][a-zA-Z\s]+)', # "compara Egon Zehnder"
            r'\bcompare\s+(?:the\s+)?([A-Z][a-zA-Z\s]+)',        # "compare Apple"
        ]
        
        import re
        has_explicit_entity = False
        if entity_texts:
            for pattern in explicit_entity_patterns:
                matches = re.findall(pattern, query)
                if matches:
                    # Verificar se alguma menção detectada está nos matches
                    for match in matches:
                        if any(entity.lower() in match.lower() or match.lower() in entity.lower() 
                               for entity in entity_texts):
                            has_explicit_entity = True
                            break
                if has_explicit_entity:
                    break
        
        # DECISÃO: Usar entity_texts como filtro APENAS se sintaxe explícita
        final_entity_ids = entity_ids  # entity_ids do gazetteer (formato ent:*)
        if not entity_ids and entity_texts and has_explicit_entity:
            # Usuário mencionou explicitamente entidade ("sobre Apple", "da Microsoft")
            # Seguro usar entity_texts como filtro
            final_entity_ids = entity_texts
            msg.info(f"  ✅ Query com entidade explícita detectada, usando como filtro: {entity_texts}")
        elif entity_texts and not has_explicit_entity:
            # spaCy detectou entidade mas sintaxe não é explícita
            # Usar apenas para boost semântico, NÃO para filtro
            msg.info(f"  ℹ️ Entidades detectadas mas sem sintaxe explícita, usando apenas para boost: {entity_texts}")
        
        # Query Expansion (Fase 1: Entidades) - antes de detectar entidades
        enable_query_expansion = self.config.get("Enable Query Expansion", {}).get("value", True)
        expanded_queries_phase1 = [query]  # Fallback: usar query original
        
        if enable_query_expansion:
            try:
                from verba_extensions.plugins.query_expander import QueryExpanderPlugin
                query_expander = QueryExpanderPlugin(cache_ttl_seconds=cache_ttl)
                expanded_queries_phase1 = await query_expander.expand_query_for_entities(query, use_cache=True)
                msg.info(f"  Query Expansion (Fase 1): {len(expanded_queries_phase1)} variações geradas")
                debug_info["query_expansion_phase1"] = expanded_queries_phase1
            except Exception as e:
                msg.debug(f"  Query Expansion não disponível: {str(e)}")
        
        # Detectar entidades de TODAS as variações expandidas
        # Usar a primeira variação expandida para parsing (ou query original se não expandiu)
        parse_query_text = expanded_queries_phase1[0] if expanded_queries_phase1 else query
        
        # Obter termos semânticos
        parsed = parse_query(parse_query_text)
        semantic_terms = parsed["semantic_concepts"]
        
        msg.info(f"  🔍 Conceitos semânticos: {semantic_terms}")
        
        # Detectar frameworks mencionados na query
        detected_frameworks = []
        detected_companies = []
        detected_sectors = []
        
        try:
            from verba_extensions.utils.framework_detector import get_framework_detector
            framework_detector = get_framework_detector()
            framework_data = await framework_detector.detect_frameworks(query)
            detected_frameworks = framework_data.get("frameworks", [])
            detected_companies = framework_data.get("companies", [])
            detected_sectors = framework_data.get("sectors", [])
            
            if detected_frameworks:
                msg.info(f"  🔍 Frameworks detectados na query: {detected_frameworks}")
            if detected_companies:
                msg.info(f"  🔍 Empresas detectadas na query: {detected_companies}")
            if detected_sectors:
                msg.info(f"  🔍 Setores detectados na query: {detected_sectors}")
        except Exception as e:
            msg.debug(f"  Erro ao detectar frameworks na query (não crítico): {str(e)}")
        
        # Para compatibilidade: entity_ids usado para filtro
        entity_ids = final_entity_ids
        
        # Se não há entity_ids, não aplicar filtro de entidade
        if not entity_ids:
            msg.info(f"  ℹ️ Nenhum filtro de entidade será aplicado (busca semântica ampla)")
        
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
                # CORREÇÃO: Se entity_property vier vazio, usar fallback
                if not entity_property or entity_property.strip() == "":
                    entity_property = "section_entity_ids"
                    msg.warn(f"  entity_property vazio, usando fallback: {entity_property}")
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
        
        # 2.4. FILTRO DE FRAMEWORK (se habilitado e collection suporta)
        framework_filter = None
        enable_framework_filter = config.get("Enable Framework Filter", {}).value if isinstance(config.get("Enable Framework Filter"), InputConfig) else True
        
        if enable_framework_filter and (detected_frameworks or detected_companies or detected_sectors):
            try:
                from verba_extensions.integration.schema_validator import collection_has_framework_properties
                
                # Normalizar nome da collection
                normalized = weaviate_manager._normalize_embedder_name(embedder)
                collection_name = weaviate_manager.embedding_table.get(embedder, f"VERBA_Embedding_{normalized}")
                
                # Verifica se collection tem propriedades de framework
                has_framework_props = await collection_has_framework_properties(client, collection_name)
                
                if has_framework_props:
                    framework_filters = []
                    
                    # Filtro por frameworks
                    if detected_frameworks:
                        framework_filters.append(
                            Filter.by_property("frameworks").contains_any(detected_frameworks)
                        )
                    
                    # Filtro por empresas
                    if detected_companies:
                        framework_filters.append(
                            Filter.by_property("companies").contains_any(detected_companies)
                        )
                    
                    # Filtro por setores
                    if detected_sectors:
                        framework_filters.append(
                            Filter.by_property("sectors").contains_any(detected_sectors)
                        )
                    
                    # Combina filtros de framework (AND - todos devem estar presentes)
                    if len(framework_filters) == 1:
                        framework_filter = framework_filters[0]
                    elif len(framework_filters) > 1:
                        framework_filter = Filter.all_of(framework_filters)
                    
                    if framework_filter:
                        msg.good(f"  ✅ Filtro de framework aplicado: frameworks={detected_frameworks}, companies={detected_companies}, sectors={detected_sectors}")
                else:
                    msg.info(f"  ℹ️ Collection não tem propriedades de framework - filtro não será aplicado")
            except Exception as e:
                msg.debug(f"  Erro ao aplicar filtro de framework (não crítico): {str(e)}")
        
        # Combinar filtros (entity + language + temporal + framework)
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
        
        # Filtro de framework: aplicar se disponível e collection suporta
        if framework_filter:
            filters_list.append(framework_filter)
            # Log já foi feito acima
        
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
        # NOVO: Adicionar entidades detectadas à query para boostar chunks que as contenham
        # Prioridade: rewritten_query > semantic_terms + entity_texts > query original
        
        # Preparar query com boost de entidades
        base_query = query
        if enable_query_rewriting:
            base_query = rewritten_query
        elif enable_semantic and semantic_terms:
            base_query = " ".join(semantic_terms)
        
        # Adicionar entidades detectadas para boostar busca (modo inteligente)
        if entity_texts:
            # Combinar query base com entidades para melhorar relevância
            entity_boost = " ".join(entity_texts)
            search_query = f"{base_query} {entity_boost}".strip()
            msg.info(f"  Query semântica (com boost de entidades): '{base_query}' + '{entity_boost}'")
        else:
            search_query = base_query
            if enable_query_rewriting:
                msg.info(f"  Query semântica (rewritten): '{search_query}'")
            elif enable_semantic and semantic_terms:
                msg.info(f"  Query semântica: '{search_query}'")
            else:
                msg.info(f"  Query semântica: '{search_query}'")
        
        # Atualizar debug info com query final usada
        if not debug_info["rewritten_query"]:
            debug_info["rewritten_query"] = search_query
        debug_info["search_mode"] = search_mode
        
        # 3.4. QUERY EXPANSION PARA BUSCA NORMAL (será aplicada depois se Two-Phase Search não estiver ativo)
        # Preparar variável para armazenar query expandida (será usada nas buscas normais)
        expanded_query_normal = search_query
        
        # 3.5. VERIFICAR SE DEVE USAR MULTI-VECTOR SEARCH
        enable_multi_vector = config.get("Enable Multi-Vector Search", {}).value if isinstance(config.get("Enable Multi-Vector Search"), InputConfig) else False
        use_multi_vector = False
        vectors_to_search = []
        
        if enable_multi_vector:
            try:
                # Normalizar nome da collection
                normalized = weaviate_manager._normalize_embedder_name(embedder)
                collection_name = weaviate_manager.embedding_table.get(embedder, f"VERBA_Embedding_{normalized}")
                
                # Verificar se collection tem named vectors
                collection = client.collections.get(collection_name)
                config_obj = await collection.config.get()
                has_named_vectors = hasattr(config_obj, 'vector_config') and config_obj.vector_config is not None
                
                if has_named_vectors:
                    # Decidir quais vetores usar baseado na query
                    has_concept = bool(semantic_terms) or bool(detected_frameworks)
                    has_sector = bool(detected_sectors)
                    has_company = bool(detected_companies)
                    
                    # Se tem 2+ aspectos, usar multi-vector
                    if has_concept:
                        vectors_to_search.append("concept_vec")
                    if has_sector:
                        vectors_to_search.append("sector_vec")
                    if has_company:
                        vectors_to_search.append("company_vec")
                    
                    if len(vectors_to_search) >= 2:
                        use_multi_vector = True
                        msg.good(f"  🎯 Multi-vector search habilitado: {vectors_to_search}")
                    else:
                        msg.info(f"  ℹ️ Multi-vector não aplicável (apenas {len(vectors_to_search)} vetor(es) relevante(s))")
            except Exception as e:
                msg.debug(f"  Erro ao verificar named vectors (não crítico): {str(e)}")
                use_multi_vector = False
        
        # 3.6. VERIFICAR TWO-PHASE SEARCH MODE
        two_phase_mode = self.config.get("Two-Phase Search Mode", {}).get("value", "auto")
        should_use_two_phase = False
        
        if two_phase_mode == "enabled":
            should_use_two_phase = True
            msg.info(f"  Two-Phase Search: ENABLED (sempre ativo)")
        elif two_phase_mode == "auto":
            # Auto: ativa se detectar entidades na query
            should_use_two_phase = bool(entity_ids or entity_texts)
            if should_use_two_phase:
                msg.info(f"  Two-Phase Search: AUTO → ENABLED (entidades detectadas)")
            else:
                msg.info(f"  Two-Phase Search: AUTO → DISABLED (sem entidades)")
        else:  # disabled
            should_use_two_phase = False
            msg.info(f"  Two-Phase Search: DISABLED")
        
        debug_info["two_phase_search"] = {
            "mode": two_phase_mode,
            "enabled": should_use_two_phase
        }
        
        # 4. BUSCA HÍBRIDA COM FILTRO (O MAGIC AQUI!) - SUPORTE MULTI-MODO E TWO-PHASE
        if search_mode == "Hybrid Search":
            try:
                # Se Two-Phase Search está ativo, executar Fase 1 primeiro
                if should_use_two_phase:
                    chunks = await self._execute_two_phase_search(
                        client=client,
                        weaviate_manager=weaviate_manager,
                        embedder=embedder,
                        query=query,
                        search_query=search_query,
                        vector=vector,
                        entity_ids=entity_ids,
                        entity_texts=entity_texts,
                        semantic_terms=semantic_terms,
                        detected_frameworks=detected_frameworks,
                        detected_companies=detected_companies,
                        detected_sectors=detected_sectors,
                        combined_filter=combined_filter,
                        lang_filter=lang_filter,
                        temporal_filter=temporal_filter,
                        framework_filter=framework_filter,
                        limit_mode=limit_mode,
                        limit=limit,
                        labels=labels,
                        document_uuids=document_uuids,
                        rewritten_alpha=rewritten_alpha,
                        enable_query_expansion=enable_query_expansion,
                        enable_multi_vector=enable_multi_vector,
                        vectors_to_search=vectors_to_search,
                        cache_ttl=cache_ttl,
                        debug_info=debug_info,
                        rag_config=rag_config
                    )
                    
                    if chunks:
                        msg.good(f"  ✅ Two-Phase Search retornou {len(chunks)} chunks")
                        # Pular busca híbrida normal, já temos resultados
                        # Continuar para reranking e retorno
                    else:
                        msg.warn(f"  ⚠️ Two-Phase Search não retornou resultados, usando busca normal")
                        # Continuar com busca híbrida normal como fallback
                        should_use_two_phase = False
                
                if not should_use_two_phase:
                    # Busca híbrida normal (comportamento atual)
                    # Aplicar Query Expansion para busca normal (se habilitado)
                    if enable_query_expansion:
                        try:
                            from verba_extensions.plugins.query_expander import QueryExpanderPlugin
                            query_expander = QueryExpanderPlugin(cache_ttl_seconds=cache_ttl)
                            expanded_queries_normal = await query_expander.expand_query_for_themes(search_query, use_cache=True)
                            if expanded_queries_normal and len(expanded_queries_normal) > 0:
                                # Usar primeira variação expandida
                                expanded_query_normal = expanded_queries_normal[0]
                                msg.info(f"  Query Expansion (normal): usando variação expandida")
                                debug_info["query_expansion_normal"] = expanded_queries_normal
                                # Atualizar search_query para usar variação expandida
                                search_query = expanded_query_normal
                        except Exception as e:
                            msg.debug(f"  Query Expansion não disponível: {str(e)}")
                    
                    # Decidir estratégia baseado no modo
                    use_strict_filter = False
                    use_boost_only = False
                
                if not enable_entity_filter or not entity_filter:
                    # Filtro desabilitado ou sem entidades - busca normal
                    msg.info(f"  Modo: busca sem filtro (filtro desabilitado ou sem entidades)")
                    use_strict_filter = False
                    use_boost_only = False
                
                elif entity_filter_mode == "strict":
                    # STRICT: Sempre filtro duro
                    msg.info(f"  Modo STRICT: filtro duro (apenas chunks com entidade)")
                    use_strict_filter = True
                    use_boost_only = False
                
                elif entity_filter_mode == "boost":
                    # BOOST: Nunca filtro, apenas boost
                    msg.info(f"  Modo BOOST: soft filter (boost de score, sem exclusão)")
                    use_strict_filter = False
                    use_boost_only = True
                
                elif entity_filter_mode == "hybrid":
                    # HYBRID: Detecta sintaxe da query para decidir
                    has_entity_focus = self._detect_entity_focus_in_query(query, entity_texts)
                    if has_entity_focus:
                        msg.info(f"  Modo HYBRID: query com foco em entidade → filtro STRICT")
                        use_strict_filter = True
                        use_boost_only = False
                    else:
                        msg.info(f"  Modo HYBRID: query exploratória → modo BOOST")
                        use_strict_filter = False
                        use_boost_only = True
                
                elif entity_filter_mode == "adaptive":
                    # ADAPTIVE: Começa strict, faz fallback para boost se poucos resultados
                    msg.info(f"  Modo ADAPTIVE: tentará filtro STRICT com fallback para BOOST")
                    use_strict_filter = True
                    use_boost_only = False
                
                # Executar busca baseado na estratégia escolhida
                chunks = []
                
                # Se multi-vector está habilitado e aplicável, usar ele
                if use_multi_vector and vectors_to_search:
                    try:
                        from verba_extensions.plugins.multi_vector_searcher import MultiVectorSearcher
                        from goldenverba.components.managers import EmbeddingManager
                        
                        # Query Expansion para multi-vector search (se habilitado)
                        search_query_mv = search_query
                        if enable_query_expansion:
                            try:
                                from verba_extensions.plugins.query_expander import QueryExpanderPlugin
                                query_expander = QueryExpanderPlugin(cache_ttl_seconds=cache_ttl)
                                expanded_queries_mv = await query_expander.expand_query_for_themes(search_query, use_cache=True)
                                if expanded_queries_mv:
                                    search_query_mv = expanded_queries_mv[0]  # Usar primeira variação
                                    msg.info(f"  Query Expansion (multi-vector): usando variação expandida")
                            except Exception as e:
                                msg.debug(f"  Query Expansion não disponível: {str(e)}")
                        
                        # Obter embedder para gerar query_vector
                        embedding_manager = EmbeddingManager()
                        query_vector = None
                        
                        if rag_config:
                            # Usar vectorize_query que já lida com config corretamente
                            query_vector = await embedding_manager.vectorize_query(
                                embedder=embedder,
                                content=search_query_mv,
                                rag_config=rag_config
                            )
                        else:
                            # Fallback: usar método direto (pode não ter config correto)
                            if embedder not in embedding_manager.embedders:
                                raise Exception(f"Embedder {embedder} não encontrado")
                            
                            embedder_obj = embedding_manager.embedders[embedder]
                            embedder_config = {}
                            
                            # Gerar embedding da query expandida
                            query_embeddings = await embedder_obj.vectorize(embedder_config, [search_query_mv])
                            if query_embeddings and len(query_embeddings) > 0:
                                query_vector = query_embeddings[0]
                        
                        if query_vector:
                            
                            # Obter configuração de Relative Score Fusion
                            enable_relative_score = self.config.get("Enable Relative Score Fusion", {}).get("value", True)
                            fusion_type = "RELATIVE_SCORE" if enable_relative_score else "RRF"
                            
                            # Configurar query_properties para BM25 boosting
                            query_properties = ["content", "title^2"]  # Boost de título
                            
                            # Criar searcher e executar busca multi-vector
                            searcher = MultiVectorSearcher()
                            multi_vector_result = await searcher.search_multi_vector(
                                client=client,
                                collection_name=collection_name,
                                query=search_query_mv,  # Usar query expandida
                                query_vector=query_vector,
                                vectors=vectors_to_search,
                                filters=combined_filter if combined_filter else None,
                                limit=limit * 2,  # Buscar mais para ter opções
                                alpha=rewritten_alpha,
                                fusion_type=fusion_type,  # Relative Score Fusion
                                query_properties=query_properties  # BM25 boosting
                            )
                            
                            # Converter resultados para formato de chunks
                            from goldenverba.components.chunk import Chunk
                            chunks = []
                            for result in multi_vector_result.get("results", [])[:limit]:
                                try:
                                    chunk = Chunk(
                                        text=result.get("text", ""),
                                        doc_uuid=result.get("doc_uuid", ""),
                                        chunk_id=result.get("chunk_id", 0)
                                    )
                                    # Adicionar metadados se disponíveis
                                    if "frameworks" in result:
                                        chunk.meta = chunk.meta or {}
                                        chunk.meta["frameworks"] = result["frameworks"]
                                    if "companies" in result:
                                        chunk.meta = chunk.meta or {}
                                        chunk.meta["companies"] = result["companies"]
                                    if "sectors" in result:
                                        chunk.meta = chunk.meta or {}
                                        chunk.meta["sectors"] = result["sectors"]
                                    chunks.append(chunk)
                                except Exception as e:
                                    msg.debug(f"  Erro ao converter resultado multi-vector: {str(e)}")
                            
                            msg.good(f"  ✅ Multi-vector search: {len(chunks)} chunks encontrados")
                        else:
                            msg.warn(f"  ⚠️ Não foi possível gerar embedding para multi-vector, usando busca normal")
                            use_multi_vector = False
                    except Exception as e:
                        msg.warn(f"  ⚠️ Erro ao executar multi-vector search: {str(e)}, usando busca normal")
                        use_multi_vector = False
                
                # Se multi-vector não foi usado, usar busca normal
                if not use_multi_vector:
                    # Obter configuração de Relative Score Fusion
                    enable_relative_score = self.config.get("Enable Relative Score Fusion", {}).get("value", True)
                    fusion_type = "RELATIVE_SCORE" if enable_relative_score else None
                    
                    # Configurar query_properties para BM25 boosting
                    query_properties = ["content", "title^2"]  # Boost de título
                    
                    if use_boost_only:
                        # MODO BOOST: Busca SEM filtro + boost na query
                        # Entidades já foram adicionadas à search_query (linha 758)
                        msg.info(f"  Executando: Hybrid search com BOOST (sem filtro)")
                    chunks = await weaviate_manager.hybrid_chunks(
                        client=client,
                        embedder=embedder,
                        query=search_query,  # Já inclui entity_boost
                        vector=vector,
                        limit_mode=limit_mode,
                        limit=limit,
                        labels=labels,
                        document_uuids=document_uuids,
                        alpha=rewritten_alpha,
                        fusion_type=fusion_type,  # Relative Score Fusion
                        query_properties=query_properties,  # BM25 boosting
                    )
                
                elif use_strict_filter:
                    # MODO STRICT (ou ADAPTIVE tentativa 1): Busca COM filtro
                    # Obter entity_property antes de usar no fallback
                    entity_property = query_filters_from_builder.get("entity_property", "section_entity_ids")
                    if not entity_property or entity_property.strip() == "":
                        entity_property = "section_entity_ids"
                    
                    # Obter configuração de Relative Score Fusion
                    enable_relative_score = self.config.get("Enable Relative Score Fusion", {}).get("value", True)
                    fusion_type = "RELATIVE_SCORE" if enable_relative_score else None
                    
                    # Configurar query_properties para BM25 boosting
                    query_properties = ["content", "title^2"]  # Boost de título
                    
                    if combined_filter:
                        msg.info(f"  Executando: Hybrid search com filtros combinados")
                        chunks = await weaviate_manager.hybrid_chunks_with_filter(
                            client=client,
                            embedder=embedder,
                            query=search_query,
                            vector=vector,
                            limit_mode=limit_mode,
                            limit=limit,
                            labels=labels,
                            document_uuids=document_uuids,
                            filters=combined_filter,
                            alpha=rewritten_alpha,
                            fusion_type=fusion_type,  # Relative Score Fusion
                            query_properties=query_properties,  # BM25 boosting
                        )
                    elif entity_filter:
                        msg.info(f"  Executando: Hybrid search com entity filter")
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
                            alpha=rewritten_alpha,
                            fusion_type=fusion_type,  # Relative Score Fusion
                            query_properties=query_properties,  # BM25 boosting
                        )
                    else:
                        # Sem filtros disponíveis
                        msg.info(f"  Executando: Hybrid search sem filtros")
                        chunks = await weaviate_manager.hybrid_chunks(
                            client=client,
                            embedder=embedder,
                            query=search_query,
                            vector=vector,
                            limit_mode=limit_mode,
                            limit=limit,
                            labels=labels,
                            document_uuids=document_uuids,
                            alpha=rewritten_alpha,
                            fusion_type=fusion_type,  # Relative Score Fusion
                            query_properties=query_properties,  # BM25 boosting
                        )
                    
                    # ADAPTIVE FALLBACK: Se poucos resultados (<3), tentar modo BOOST
                    # NOVO: Também tentar entities_local_ids se section_entity_ids não encontrou resultados
                    if entity_filter_mode == "adaptive" and len(chunks) < 3:
                        msg.warn(f"  ⚠️ ADAPTIVE FALLBACK: apenas {len(chunks)} chunks com filtro strict, tentando alternativas...")
                        
                        # Tentativa 1: Tentar entities_local_ids se estava usando section_entity_ids
                        if entity_property == "section_entity_ids" and chunk_level_entities:
                            try:
                                msg.info(f"  💡 Tentando filtro alternativo: entities_local_ids (em vez de section_entity_ids)")
                                fallback_filter = Filter.by_property("entities_local_ids").contains_any(chunk_level_entities)
                                # Combinar com outros filtros se houver
                                fallback_filters_list = [fallback_filter]
                                if lang_filter and has_entities:
                                    fallback_filters_list.append(lang_filter)
                                if temporal_filter:
                                    fallback_filters_list.append(temporal_filter)
                                
                                if len(fallback_filters_list) == 1:
                                    combined_fallback_filter = fallback_filter
                                else:
                                    combined_fallback_filter = Filter.all_of(fallback_filters_list)
                                
                                # Obter configuração de Relative Score Fusion para fallback
                                enable_relative_score = self.config.get("Enable Relative Score Fusion", {}).get("value", True)
                                fusion_type = "RELATIVE_SCORE" if enable_relative_score else None
                                query_properties = ["content", "title^2"]
                                
                                chunks_fallback = await weaviate_manager.hybrid_chunks_with_filter(
                                    client=client,
                                    embedder=embedder,
                                    query=search_query,
                                    vector=vector,
                                    limit_mode=limit_mode,
                                    limit=limit,
                                    labels=labels,
                                    document_uuids=document_uuids,
                                    filters=combined_fallback_filter,
                                    alpha=rewritten_alpha,
                                    fusion_type=fusion_type,  # Relative Score Fusion
                                    query_properties=query_properties,  # BM25 boosting
                                )
                                
                                if len(chunks_fallback) > len(chunks):
                                    msg.good(f"  ✅ ADAPTIVE FALLBACK: encontrados {len(chunks_fallback)} chunks com entities_local_ids (vs {len(chunks)} com section_entity_ids)")
                                    chunks = chunks_fallback
                                else:
                                    msg.info(f"  ADAPTIVE FALLBACK: entities_local_ids também não encontrou mais resultados ({len(chunks_fallback)} chunks)")
                            except Exception as e:
                                msg.warn(f"  ⚠️ Erro ao tentar fallback entities_local_ids: {str(e)}")
                        
                        # Tentativa 2: Se ainda não encontrou, tentar modo BOOST (sem filtro)
                        if len(chunks) < 3:
                            msg.info(f"  💡 Tentando modo BOOST (sem filtro, apenas boost semântico)")
                            
                            # Obter configuração de Relative Score Fusion para fallback
                            enable_relative_score = self.config.get("Enable Relative Score Fusion", {}).get("value", True)
                            fusion_type = "RELATIVE_SCORE" if enable_relative_score else None
                            query_properties = ["content", "title^2"]
                            
                            chunks_boost = await weaviate_manager.hybrid_chunks(
                                client=client,
                                embedder=embedder,
                                query=search_query,  # Já inclui entity_boost
                                vector=vector,
                                limit_mode=limit_mode,
                                limit=limit,
                                labels=labels,
                                document_uuids=document_uuids,
                                alpha=rewritten_alpha,
                                fusion_type=fusion_type,  # Relative Score Fusion
                                query_properties=query_properties,  # BM25 boosting
                            )
                            if len(chunks_boost) > len(chunks):
                                msg.good(f"  ✅ ADAPTIVE FALLBACK: encontrados {len(chunks_boost)} chunks com BOOST (vs {len(chunks)} com filtro)")
                                chunks = chunks_boost
                            else:
                                msg.info(f"  ADAPTIVE FALLBACK: mantendo {len(chunks)} chunks originais")
                
                else:
                    # Sem filtros: busca normal
                    msg.info(f"  Executando: Hybrid search sem filtros")
                    
                    # Obter configuração de Relative Score Fusion
                    enable_relative_score = self.config.get("Enable Relative Score Fusion", {}).get("value", True)
                    fusion_type = "RELATIVE_SCORE" if enable_relative_score else None
                    
                    # Configurar query_properties para BM25 boosting
                    query_properties = ["content", "title^2"]  # Boost de título
                    
                    chunks = await weaviate_manager.hybrid_chunks(
                        client=client,
                        embedder=embedder,
                        query=search_query,
                        vector=vector,
                        limit_mode=limit_mode,
                        limit=limit,
                        labels=labels,
                        document_uuids=document_uuids,
                        alpha=rewritten_alpha,
                        fusion_type=fusion_type,  # Relative Score Fusion
                        query_properties=query_properties,  # BM25 boosting
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
                    
                    # Log reduzido - apenas mostrar resumo (removido para reduzir verbosidade)
                    
                    reranked_objects = await reranker.process_chunks(
                        chunk_objects,
                        query=query,
                        config={"top_k": top_k_for_rerank}
                    )
                    
                    # Logs reduzidos - apenas mostrar se houver problema
                    if len(reranked_objects) < top_k_for_rerank:
                        msg.warn(f"  ⚠️ Reranker retornou menos chunks ({len(reranked_objects)}) do que esperado ({top_k_for_rerank})")
                    # Removidos logs verbosos de cada chunk rerankado
                    
                    # Reconstrói chunks Weaviate a partir dos rerankeados
                    # IMPORTANTE: chunk.chunk_id é str(chunk.uuid) do objeto Weaviate original
                    reranked_uuids = {str(chunk.chunk_id) for chunk in reranked_objects}
                    chunks_filtered = [c for c in chunks if str(c.uuid) in reranked_uuids]
                    
                    # Log removido para reduzir verbosidade
                    
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
        context, filtered_context_documents, filter_info = self.combine_context(sorted_context_documents, chunk_window=chunk_window)
        
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
        
        # Adicionar informação sobre filtragem ao debug_info (usar filter_info se disponível)
        if filter_info and not filter_info.get('fallback_used', False):
            # Apenas mostrar se não foi usado fallback (evitar logs redundantes)
            chunks_filtered = filter_info.get('filtered_count', total_chunks_before - total_chunks_after)
            if chunks_filtered > 0 and chunks_filtered < total_chunks_before * 0.5:
                # Apenas logar se menos de 50% foram filtrados (casos normais)
                debug_info["chunks_filtered"] = {
                    "total_before": filter_info.get('total_count', total_chunks_before),
                    "total_after": filter_info.get('final_count', total_chunks_after),
                    "filtered_count": chunks_filtered,
                    "message": f"{chunks_filtered} chunks filtrados por baixa qualidade"
                }
                # Log removido para reduzir verbosidade
        
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
        
        # Log removido para reduzir verbosidade (chunk window é aplicado silenciosamente)
        
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
                            # Log removido para reduzir verbosidade (chunk window aplicado silenciosamente)
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
            # Log removido para reduzir verbosidade (cabeçalhos detectados silenciosamente)
        
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
                # Log removido para reduzir verbosidade (filtros são contabilizados ao final)
                return False
            else:
                # Repetição alta mas não ocupa tanto espaço - provavelmente OK
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
                        # Log removido para reduzir verbosidade (filtros são contabilizados ao final)
                        return False
        
        # Detectar fragmentação: chunk começa ou termina no meio de palavra
        # (palavras muito curtas no início/fim podem indicar fragmentação)
        if len(words) > 0:
            first_word = words[0]
            last_word = words[-1]
            # Palavras muito curtas no início/fim podem ser fragmentos
            if len(first_word) < 3 and len(words) > 1:
                # Log removido para reduzir verbosidade (filtros são contabilizados ao final)
                return False
        
        return True
    
    def combine_context(self, documents: list[dict], chunk_window: int = 0) -> tuple[str, list[dict], dict]:
        """Combina contexto dos documentos, filtrando chunks de baixa qualidade
        
        Args:
            documents: Lista de documentos com chunks
            chunk_window: Tamanho do chunk window usado (para ajustar thresholds de qualidade)
        
        Returns:
            tuple: (context_string, filtered_documents, filter_info)
                filter_info: dict com informações sobre filtragem {'fallback_used': bool, 'filtered_count': int, 'total_count': int}
        """
        from goldenverba.components.retriever.WindowRetriever import WindowRetriever
        
        # Filtrar chunks de baixa qualidade antes de combinar
        filtered_documents = []
        total_chunks = 0
        filtered_chunks = 0
        fallback_used = False
        
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
        
        # FALLBACK 1: Se mais de 80% dos chunks foram filtrados, tentar novamente com thresholds mais relaxados
        if total_chunks > 0 and filtered_chunks / total_chunks > 0.8:
            # Log consolidado - apenas uma mensagem ao invés de múltiplas
            msg.warn(f"  ⚠️ {filtered_chunks}/{total_chunks} chunks filtrados - ativando modo emergência")
            
            # Segunda passada com modo emergência (thresholds mais relaxados)
            filtered_documents_emergency = []
            filtered_chunks_emergency = 0
            
            for document in documents:
                filtered_chunks_list = []
                for chunk in document["chunks"]:
                    chunk_content = chunk.get("content", "")
                    # Modo emergência: apenas filtrar chunks completamente vazios ou muito fragmentados
                    if chunk_content and len(chunk_content.strip()) >= 10:
                        # Apenas verificar fragmentação extrema (palavras muito curtas no início/fim)
                        words = chunk_content.strip().split()
                        if len(words) >= 3:
                            first_word = words[0] if words else ""
                            # Apenas filtrar se começar com fragmento muito óbvio (1-2 caracteres)
                            if len(first_word) >= 2:
                                filtered_chunks_list.append(chunk)
                            else:
                                filtered_chunks_emergency += 1
                        else:
                            filtered_chunks_emergency += 1
                    else:
                        filtered_chunks_emergency += 1
                
                if filtered_chunks_list:
                    filtered_document = document.copy()
                    filtered_document["chunks"] = filtered_chunks_list
                    filtered_documents_emergency.append(filtered_document)
            
            # Se modo emergência conseguiu salvar alguns chunks, usar eles
            if len(filtered_documents_emergency) > 0:
                # Log reduzido
                msg.info(f"  ✅ Modo emergência: {total_chunks - filtered_chunks_emergency}/{total_chunks} chunks mantidos")
                filtered_documents = filtered_documents_emergency
                filtered_chunks = filtered_chunks_emergency
                fallback_used = True
            else:
                # Modo emergência também falhou, usar todos os chunks originais
                msg.warn(f"  ⚠️ Modo emergência falhou - usando todos os chunks originais")
                filtered_documents = documents
                filtered_chunks = 0
                fallback_used = True
        
        # FALLBACK 2: Se ainda não há documentos, usar todos os chunks originais
        if len(filtered_documents) == 0 and len(documents) > 0:
            # Log consolidado
            msg.warn(f"  ⚠️ Todos os {total_chunks} chunks filtrados - usando fallback final")
            filtered_documents = documents
            filtered_chunks = 0
            fallback_used = True
        
        # Mostrar mensagem de filtragem apenas se não foi usado fallback (log reduzido)
        if filtered_chunks > 0 and not fallback_used and filtered_chunks < total_chunks * 0.5:
            # Apenas logar se menos de 50% foram filtrados (casos normais)
            pass  # Log removido para reduzir verbosidade
        elif fallback_used:
            # Log já foi feito acima, não repetir
            pass
        
        # Usar método do WindowRetriever para combinar contexto
        window_retriever = WindowRetriever()
        context = window_retriever.combine_context(filtered_documents)
        
        # Informações sobre filtragem
        filter_info = {
            'fallback_used': fallback_used,
            'filtered_count': filtered_chunks,
            'total_count': total_chunks,
            'final_count': sum(len(doc['chunks']) for doc in filtered_documents)
        }
        
        return (context, filtered_documents, filter_info)


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

