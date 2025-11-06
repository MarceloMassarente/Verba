"""
Plugin: Query Builder (Inteligente)
Constrói queries complexas conhecendo o schema do Weaviate

DIFERENÇA do QueryRewriter:
- QueryRewriter: Expansão semântica genérica (não conhece schema)
- QueryBuilder: Constrói query estruturada conhecendo schema, entidades, filtros

Features:
- Obtém schema do Weaviate dinamicamente
- Usa LLM para entender prompt do usuário
- Gera query estruturada com filtros, entidades, etc.
- Valida query com usuário antes de executar
"""

import json
import time
from typing import Dict, Any, Optional, List
from wasabi import msg


class QueryBuilderPlugin:
    """
    Plugin que constrói queries complexas conhecendo o schema do Weaviate.
    
    Diferente do QueryRewriter que só faz expansão semântica, este:
    - Conhece o schema do Weaviate (propriedades disponíveis)
    - Entende entidades e como usar filtros
    - Gera queries estruturadas com filtros complexos
    - Valida com o usuário antes de executar
    """
    
    def __init__(self, cache_ttl_seconds: int = 3600):
        """
        Inicializa QueryBuilderPlugin.
        
        Args:
            cache_ttl_seconds: TTL do cache em segundos (default: 1 hora)
        """
        self.cache: Dict[str, tuple[Dict[str, Any], float]] = {}
        self.cache_ttl = cache_ttl_seconds
        self._generator = None
        self._schema_cache: Optional[Dict[str, Any]] = None
        self._schema_cache_time: float = 0
        self._schema_cache_ttl = 300  # 5 minutos
    
    def _get_generator(self):
        """Lazy load do generator (Anthropic)"""
        if self._generator is None:
            try:
                from goldenverba.components.generation.AnthrophicGenerator import AnthropicGenerator
                self._generator = AnthropicGenerator()
            except Exception as e:
                msg.warn(f"AnthropicGenerator não disponível: {e}")
                return None
        return self._generator
    
    async def get_schema_info(self, client, collection_name: str) -> Dict[str, Any]:
        """
        Obtém informações do schema do Weaviate para uma collection.
        
        Args:
            client: Cliente Weaviate
            collection_name: Nome da collection (ex: "VERBA_Embedding_all_MiniLM_L6_v2")
            
        Returns:
            Dict com informações do schema:
            {
                "properties": [
                    {"name": "content", "type": "text", "description": "..."},
                    {"name": "entities_local_ids", "type": "text[]", "description": "..."},
                    ...
                ],
                "etl_aware": True/False,
                "available_filters": ["entities_local_ids", "section_title", "chunk_lang", ...]
            }
        """
        try:
            # Verificar cache
            current_time = time.time()
            if (self._schema_cache and 
                current_time - self._schema_cache_time < self._schema_cache_ttl and
                self._schema_cache.get("collection_name") == collection_name):
                return self._schema_cache
            
            # Obter schema do Weaviate
            collection = client.collections.get(collection_name)
            # Verificar se config.get() é await ou não
            try:
                config = collection.config.get()
                # Se não é await, já retorna o config
                if hasattr(config, '__await__'):
                    config = await config
            except TypeError:
                # Se deu erro, tentar como coroutine
                config = await collection.config.get()
            
            # Extrair propriedades
            properties = []
            etl_properties = [
                "entities_local_ids", "section_title", "section_entity_ids",
                "section_scope_confidence", "primary_entity_id", "entity_focus_score",
                "etl_version"
            ]
            
            has_etl = False
            for prop in config.properties:
                prop_info = {
                    "name": prop.name,
                    "type": str(prop.data_type),
                    "description": getattr(prop, 'description', '')
                }
                properties.append(prop_info)
                
                if prop.name in etl_properties:
                    has_etl = True
            
            schema_info = {
                "collection_name": collection_name,
                "properties": properties,
                "etl_aware": has_etl,
                "available_filters": [p["name"] for p in properties if p["name"] not in ["content", "uuid", "doc_uuid"]],
                "timestamp": current_time
            }
            
            # Cache
            self._schema_cache = schema_info
            self._schema_cache_time = current_time
            
            return schema_info
            
        except Exception as e:
            msg.warn(f"Erro ao obter schema: {str(e)}")
            # Retornar schema padrão conhecido
            return self._get_default_schema()
    
    def _get_default_schema(self) -> Dict[str, Any]:
        """Retorna schema padrão conhecido se não conseguir obter do Weaviate"""
        return {
            "collection_name": "unknown",
            "properties": [
                {"name": "content", "type": "text", "description": "Conteúdo do chunk"},
                {"name": "entities_local_ids", "type": "text[]", "description": "Entity IDs no chunk"},
                {"name": "section_title", "type": "text", "description": "Título da seção"},
                {"name": "section_entity_ids", "type": "text[]", "description": "Entity IDs da seção"},
                {"name": "chunk_lang", "type": "text", "description": "Idioma do chunk (pt/en)"},
                {"name": "chunk_date", "type": "text", "description": "Data do chunk"},
                {"name": "labels", "type": "text[]", "description": "Labels do chunk"},
            ],
            "etl_aware": True,
            "available_filters": ["entities_local_ids", "section_title", "section_entity_ids", "chunk_lang", "chunk_date", "labels"],
            "timestamp": time.time()
        }
    
    async def build_query(
        self,
        user_query: str,
        client,
        collection_name: str,
        use_cache: bool = True,
        validate: bool = False,
        auto_detect_aggregation: bool = True
    ) -> Dict[str, Any]:
        """
        Constrói query complexa conhecendo o schema.
        
        Args:
            user_query: Query do usuário (ex: "mostre inovação da Apple em 2024")
            client: Cliente Weaviate
            collection_name: Nome da collection
            use_cache: Se deve usar cache
            validate: Se deve retornar query para validação (não executar ainda)
            auto_detect_aggregation: Se deve detectar automaticamente queries de agregação
            
        Returns:
            Dict com query estruturada:
            {
                "semantic_query": "query expandida",
                "keyword_query": "query para BM25",
                "intent": "search|comparison|description|aggregation",
                "filters": {...},
                "alpha": 0.6,
                "explanation": "Explicação da query gerada",
                "requires_validation": True/False,
                "is_aggregation": True/False,  # NOVO: indica se é agregação
                "aggregation_info": {...}  # NOVO: info de agregação se aplicável
            }
        """
        if not user_query or not user_query.strip():
            return self._fallback_response(user_query)
        
        # NOVO: Detectar se precisa de agregação
        if auto_detect_aggregation and self._needs_aggregation(user_query):
            msg.info(f"  Query builder: detectou necessidade de agregação")
            try:
                # Tentar construir query de agregação
                aggregation_info = await self._build_aggregation_from_query(
                    user_query, client, collection_name
                )
                if aggregation_info and "error" not in aggregation_info:
                    return {
                        "semantic_query": user_query,
                        "keyword_query": user_query,
                        "intent": "aggregation",
                        "filters": {},
                        "alpha": 0.6,
                        "explanation": f"Query de agregação detectada: {aggregation_info.get('aggregation_type', 'unknown')}",
                        "requires_validation": validate,
                        "is_aggregation": True,
                        "aggregation_info": aggregation_info
                    }
            except Exception as e:
                msg.warn(f"  Query builder: erro ao construir agregação ({str(e)}), continuando com query normal")
        
        # Verificar cache
        if use_cache:
            cache_key = f"{user_query.lower().strip()}|{collection_name}"
            if cache_key in self.cache:
                cached_strategy, timestamp = self.cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    msg.info(f"  Query builder: cache hit")
                    return cached_strategy
        
        # Obter schema
        schema_info = await self.get_schema_info(client, collection_name)
        
        # Chamar LLM para construir query
        try:
            generator = self._get_generator()
            if generator is None:
                msg.warn("  Query builder: generator não disponível, usando fallback")
                return self._fallback_response(user_query)
            
            strategy = await self._call_llm_with_schema(generator, user_query, schema_info, validate)
            
            # Validar resposta
            if not self._validate_strategy(strategy):
                msg.warn("  Query builder: resposta inválida do LLM, usando fallback")
                return self._fallback_response(user_query)
            
            # Validar se query foi expandida (não deve ser idêntica à original)
            semantic_query = strategy.get("semantic_query", user_query)
            if semantic_query == user_query:
                msg.warn(f"  ⚠️ Query builder: LLM retornou query idêntica - pode não ter expandido corretamente")
                msg.warn(f"  Considerando usar fallback ou verificar prompt do LLM")
            
            # Adicionar flag de agregação
            strategy["is_aggregation"] = False
            strategy["aggregation_info"] = None
            
            # Cache
            if use_cache:
                cache_key = f"{user_query.lower().strip()}|{collection_name}"
                self.cache[cache_key] = (strategy, time.time())
            
            msg.good(f"  Query builder: query estruturada gerada")
            if semantic_query != user_query:
                msg.info(f"  Query expandida: '{user_query[:50]}...' → '{semantic_query[:100]}...'")
            return strategy
            
        except Exception as e:
            msg.warn(f"  Query builder: erro ({str(e)}), usando fallback")
            return self._fallback_response(user_query)
    
    async def _call_llm_with_schema(
        self,
        generator,
        user_query: str,
        schema_info: Dict[str, Any],
        validate: bool
    ) -> Dict[str, Any]:
        """Chama LLM para construir query conhecendo o schema"""
        
        properties_str = "\n".join([
            f"  - {p['name']} ({p['type']}): {p.get('description', '')}"
            for p in schema_info["properties"]
        ])
        
        available_filters = ", ".join(schema_info["available_filters"])
        
        prompt = f"""Você é um assistente especializado em construir queries complexas para busca vetorial no Weaviate.

SCHEMA DA COLLECTION ({schema_info['collection_name']}):
Propriedades disponíveis:
{properties_str}

Filtros disponíveis: {available_filters}
ETL-aware: {schema_info['etl_aware']}

QUERY DO USUÁRIO: "{user_query}"

Sua tarefa:
1. Analisar a query do usuário e entender o que ele quer
2. Extrair entidades mencionadas (ex: "Apple", "Microsoft", "2024")
3. Identificar filtros necessários (entidades, datas, idioma, etc.)
4. **EXPANDIR a query semântica** com sinônimos, termos relacionados e conceitos semânticos
5. Gerar query keyword otimizada para BM25 (termos-chave importantes)
6. Determinar intenção (search, comparison, description)
7. Sugerir alpha para hybrid search

REGRA CRÍTICA - EXPANSÃO SEMÂNTICA:
- A query semântica DEVE ser EXPANDIDA, não apenas repetir a query original
- Adicione sinônimos, termos relacionados, conceitos semânticos
- Exemplo: "oportunidades de ganho" → "oportunidades de ganho retorno lucro benefício maximização valor receita"
- Exemplo: "revisão tarifária" → "revisão tarifária tarifa distribuidora energia elétrica ANEEL receita requerida"
- Exemplo: "fatores de sucesso" → "fatores de sucesso elementos críticos componentes essenciais requisitos fundamentais"
- NUNCA retorne a query original sem expansão

IMPORTANTE:
- Use propriedades do schema para filtros (entities_local_ids, section_entity_ids, chunk_lang, chunk_date, etc.)
- Se mencionar empresa/pessoa, use filtro de entidade (entities_local_ids ou section_entity_ids)
- Se mencionar data/ano, use filtro temporal (chunk_date)
- Se mencionar idioma, use filtro de idioma (chunk_lang)
- **SEMPRE expanda a query semântica** - adicione termos relacionados, sinônimos, conceitos
- Gere query keyword otimizada para BM25 (termos-chave principais)

FILTROS HIERÁRQUICOS (se necessário):
- Se query menciona "documentos que falam sobre X, depois chunks sobre Y":
  - document_level_entities: ["Q312"]  // Filtrar documentos com Apple
  - entities: ["Q2283"]  // Filtrar chunks com Microsoft dentro desses documentos

FILTROS POR FREQUÊNCIA (se necessário):
- Se query menciona "entidade dominante", "mais frequente", "principal":
  - filter_by_frequency: true
  - min_frequency: 5  // Frequência mínima (opcional)
  - dominant_only: true  // Apenas entidade dominante (opcional)
- Se query menciona "mais que X", "aparece mais que Y":
  - frequency_comparison: {{"entity_1": "Q312", "entity_2": "Q2283", "min_ratio": 1.5}}

Retorne JSON válido:
{{
    "semantic_query": "query expandida para busca semântica",
    "keyword_query": "query otimizada para BM25",
    "intent": "search|comparison|description",
    "filters": {{
        "entities": ["Q312", "Q2283"],  // Entity IDs extraídos (se mencionados)
        "entity_property": "section_entity_ids",  // Propriedade a usar: "section_entity_ids" (contexto de seção, evita contaminação) ou "entities_local_ids" (apenas menções explícitas no chunk)
        "document_level_entities": [],  // Entidades para filtrar documentos primeiro (ex: ["Q312"] para Apple)
        "filter_by_frequency": false,  // Se deve filtrar por frequência de entidade
        "min_frequency": 0,  // Frequência mínima requerida (0 = qualquer)
        "dominant_only": false,  // Apenas se entidade for dominante no documento
        "frequency_comparison": null,  // Comparação de frequência: {{"entity_1": "Q312", "entity_2": "Q2283", "min_ratio": 1.5}}
        "date_range": {{"start": "2024-01-01", "end": "2024-12-31"}},  // Se mencionar data
        "language": "pt",  // Se detectar idioma
        "labels": [],  // Labels específicos (se mencionados)
        "section_title": ""  // Se mencionar seção específica
    }},
    "alpha": 0.6,  // Balance keyword/vector (0.0-1.0)
    "explanation": "Explicação da query: filtros aplicados, entidades detectadas, etc.",
    "requires_validation": {str(validate).lower()}  // Se precisa validar com usuário
}}

Retorne apenas JSON válido, sem markdown, sem explicações fora do JSON:
"""
        
        try:
            import asyncio
            
            generator_config = generator.config if hasattr(generator, "config") else {}
            
            response_text = ""
            async for chunk in generator.generate_stream(
                generator_config,
                prompt,
                "",
                [],
            ):
                if isinstance(chunk, dict) and "message" in chunk:
                    response_text += chunk["message"]
            
            # Parse JSON
            if response_text:
                response_text = response_text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                strategy = json.loads(response_text)
            else:
                raise ValueError("Empty response from LLM")
            
            return strategy
            
        except json.JSONDecodeError as e:
            msg.warn(f"Erro ao decodificar JSON do LLM: {e}")
            msg.warn(f"Resposta recebida: {response_text[:500]}")
            raise
        except Exception as e:
            msg.warn(f"Erro ao chamar LLM: {e}")
            raise
    
    def _validate_strategy(self, strategy: Dict[str, Any]) -> bool:
        """Valida estrutura da estratégia retornada pelo LLM"""
        required_fields = ["semantic_query", "keyword_query", "intent", "filters", "alpha", "explanation"]
        
        if not isinstance(strategy, dict):
            return False
        
        for field in required_fields:
            if field not in strategy:
                return False
        
        # Validar tipos
        if not isinstance(strategy["semantic_query"], str):
            return False
        if not isinstance(strategy["keyword_query"], str):
            return False
        if strategy["intent"] not in ["comparison", "description", "search"]:
            return False
        if not isinstance(strategy["filters"], dict):
            return False
        if not isinstance(strategy["alpha"], (int, float)) or not (0.0 <= strategy["alpha"] <= 1.0):
            return False
        
        return True
    
    def _fallback_response(self, query: str) -> Dict[str, Any]:
        """Resposta de fallback se LLM falhar"""
        msg.warn(f"  Query builder: usando fallback (LLM não disponível ou erro)")
        return {
            "semantic_query": query,  # Fallback não expande - apenas retorna original
            "keyword_query": query,
            "intent": "search",
            "filters": {
                "entities": [],
                "entity_property": "section_entity_ids",  # Padrão: usa contexto de seção para evitar contaminação
                "document_level_entities": [],  # Entidades para filtrar documentos primeiro
                "filter_by_frequency": False,  # Filtrar por frequência
                "min_frequency": 0,  # Frequência mínima
                "dominant_only": False,  # Apenas entidade dominante
                "frequency_comparison": None,  # Comparação de frequência
                "date_range": None,
                "language": None,
                "labels": [],
                "section_title": ""
            },
            "alpha": 0.6,
            "explanation": "Query simples (fallback - LLM não disponível)",
            "requires_validation": False
        }
    
    def clear_cache(self):
        """Limpa cache"""
        self.cache.clear()
        self._schema_cache = None
        msg.info("Cache de query builder limpo")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache"""
        current_time = time.time()
        valid_entries = sum(
            1 for _, (_, timestamp) in self.cache.items()
            if current_time - timestamp < self.cache_ttl
        )
        
        return {
            "total_entries": len(self.cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self.cache) - valid_entries,
            "cache_ttl_seconds": self.cache_ttl,
            "schema_cached": self._schema_cache is not None
        }
    
    async def build_aggregation_query(
        self,
        aggregation_type: str,
        client,
        collection_name: str,
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Constrói query de agregação usando GraphQL Builder.
        
        Args:
            aggregation_type: Tipo de agregação ("entity_stats", "document_stats", "custom")
            client: Cliente Weaviate
            collection_name: Nome da collection
            filters: Filtros opcionais
            group_by: Campos para agrupar
            **kwargs: Parâmetros adicionais
            
        Returns:
            Dict com query GraphQL e método para executar
            
        Exemplo:
            query_info = await builder.build_aggregation_query(
                aggregation_type="entity_stats",
                client=client,
                collection_name="VERBA_Embedding_all_MiniLM_L6_v2",
                filters={"entities_local_ids": ["Q312"]}
            )
            
            # Executar query
            results = await query_info["execute"]()
            stats = query_info["parse"](results)
        """
        try:
            from verba_extensions.utils.graphql_builder import GraphQLBuilder
            graphql_builder = GraphQLBuilder()
        except ImportError:
            msg.warn("GraphQLBuilder não disponível, usando fallback")
            return {
                "error": "GraphQLBuilder não disponível",
                "query": None,
                "execute": None,
                "parse": None
            }
        
        # Construir query baseada no tipo
        if aggregation_type == "entity_stats":
            query = graphql_builder.build_entity_aggregation(
                collection_name=collection_name,
                filters=filters,
                group_by=group_by,
                top_occurrences_limit=kwargs.get("top_occurrences_limit", 10)
            )
        elif aggregation_type == "document_stats":
            query = graphql_builder.build_document_stats_query(
                collection_name=collection_name,
                filters=filters
            )
        elif aggregation_type == "multi_collection":
            queries = kwargs.get("queries", [])
            if not queries:
                return {"error": "queries é obrigatório para multi_collection"}
            query = graphql_builder.build_multi_collection_query(queries)
        elif aggregation_type == "complex_filter":
            filter_logic = kwargs.get("filter_logic")
            if not filter_logic:
                return {"error": "filter_logic é obrigatório para complex_filter"}
            query = graphql_builder.build_complex_filter_query(
                collection_name=collection_name,
                filter_logic=filter_logic,
                limit=kwargs.get("limit", 50),
                fields=kwargs.get("fields")
            )
        else:
            return {"error": f"Tipo de agregação desconhecido: {aggregation_type}"}
        
        # Retornar query e métodos para executar e parsear
        return {
            "query": query,
            "aggregation_type": aggregation_type,
            "execute": lambda: graphql_builder.execute(client, query),
            "parse": lambda results: graphql_builder.parse_aggregation_results(results)
        }
    
    def _needs_aggregation(self, user_query: str) -> bool:
        """
        Detecta se a query do usuário precisa de agregação.
        
        Args:
            user_query: Query do usuário
            
        Returns:
            True se precisa de agregação
        """
        # Palavras-chave que indicam necessidade de agregação
        aggregation_keywords = [
            "quantos", "quantas", "contar", "contagem",
            "estatísticas", "estatistica", "stats",
            "distribuição", "distribuicao",
            "agrupar", "agrupado", "por documento", "por entidade",
            "top", "mais frequente", "mais citado",
            "quantidade", "número de", "numero de",
            "how many", "count", "statistics", "stats",
            "distribution", "group by", "aggregate"
        ]
        
        query_lower = user_query.lower()
        return any(keyword in query_lower for keyword in aggregation_keywords)
    
    async def _build_aggregation_from_query(
        self,
        user_query: str,
        client,
        collection_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Tenta construir query de agregação a partir da query do usuário.
        
        Args:
            user_query: Query do usuário
            client: Cliente Weaviate
            collection_name: Nome da collection
            
        Returns:
            Dict com informações de agregação ou None se não conseguir determinar
        """
        try:
            query_lower = user_query.lower()
            
            # Detectar tipo de agregação
            aggregation_type = "entity_stats"  # Default
            
            # Detectar se é estatísticas por documento
            if any(word in query_lower for word in ["por documento", "por doc", "documentos", "docs"]):
                aggregation_type = "document_stats"
            
            # Extrair filtros básicos (se houver)
            filters = None
            group_by = None
            
            # Tentar extrair entidades mencionadas (se houver)
            # Isso pode ser melhorado com NER/LLM no futuro
            if any(word in query_lower for word in ["apple", "microsoft", "google", "meta"]):
                # Por enquanto, não tentamos extrair entity IDs automaticamente
                # Seria necessário NER + Gazetteer
                pass
            
            # Detectar groupBy
            if "agrupar" in query_lower or "group by" in query_lower:
                if "por documento" in query_lower or "por doc" in query_lower:
                    group_by = ["doc_uuid"]
                elif "por entidade" in query_lower:
                    group_by = ["entities_local_ids"]
                elif "por data" in query_lower or "por date" in query_lower:
                    group_by = ["chunk_date"]
            
            # Construir query de agregação
            query_info = await self.build_aggregation_query(
                aggregation_type=aggregation_type,
                client=client,
                collection_name=collection_name,
                filters=filters,
                group_by=group_by
            )
            
            if "error" in query_info:
                return None
            
            return query_info
            
        except Exception as e:
            msg.warn(f"Erro ao construir agregação: {str(e)}")
            return None

