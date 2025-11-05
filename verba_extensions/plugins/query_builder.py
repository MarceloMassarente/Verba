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
        validate: bool = False
    ) -> Dict[str, Any]:
        """
        Constrói query complexa conhecendo o schema.
        
        Args:
            user_query: Query do usuário (ex: "mostre inovação da Apple em 2024")
            client: Cliente Weaviate
            collection_name: Nome da collection
            use_cache: Se deve usar cache
            validate: Se deve retornar query para validação (não executar ainda)
            
        Returns:
            Dict com query estruturada:
            {
                "semantic_query": "query expandida",
                "keyword_query": "query para BM25",
                "intent": "search|comparison|description",
                "filters": {
                    "entities": ["Q312"],  # Entity IDs extraídos
                    "entity_property": "entities_local_ids",  # Propriedade a usar
                    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                    "language": "pt",
                    "labels": [],
                    "section_title": ""
                },
                "alpha": 0.6,
                "explanation": "Explicação da query gerada",
                "requires_validation": True/False
            }
        """
        if not user_query or not user_query.strip():
            return self._fallback_response(user_query)
        
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
            
            # Cache
            if use_cache:
                cache_key = f"{user_query.lower().strip()}|{collection_name}"
                self.cache[cache_key] = (strategy, time.time())
            
            msg.good(f"  Query builder: query estruturada gerada")
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
4. Gerar query semântica expandida
5. Gerar query keyword otimizada
6. Determinar intenção (search, comparison, description)
7. Sugerir alpha para hybrid search

IMPORTANTE:
- Use propriedades do schema para filtros (entities_local_ids, section_entity_ids, chunk_lang, chunk_date, etc.)
- Se mencionar empresa/pessoa, use filtro de entidade (entities_local_ids ou section_entity_ids)
- Se mencionar data/ano, use filtro temporal (chunk_date)
- Se mencionar idioma, use filtro de idioma (chunk_lang)
- Gere query semântica expandida com sinônimos e conceitos relacionados
- Gere query keyword otimizada para BM25

Retorne JSON válido:
{{
    "semantic_query": "query expandida para busca semântica",
    "keyword_query": "query otimizada para BM25",
    "intent": "search|comparison|description",
    "filters": {{
        "entities": ["Q312", "Q2283"],  // Entity IDs extraídos (se mencionados)
        "entity_property": "entities_local_ids",  // Propriedade a usar (entities_local_ids ou section_entity_ids)
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
        return {
            "semantic_query": query,
            "keyword_query": query,
            "intent": "search",
            "filters": {
                "entities": [],
                "entity_property": "entities_local_ids",
                "date_range": None,
                "language": None,
                "labels": [],
                "section_title": ""
            },
            "alpha": 0.6,
            "explanation": "Query simples (fallback)",
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

