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

# Importar detecção de idioma
try:
    from goldenverba.components.document import detect_language
except ImportError:
    # Fallback se não disponível
    try:
        from langdetect import detect as detect_language
    except ImportError:
        def detect_language(text: str) -> str:
            """Fallback simples de detecção de idioma"""
            # Detecção básica por palavras comuns
            text_lower = text.lower()
            if any(word in text_lower for word in ['the', 'is', 'are', 'which', 'what', 'where', 'when', 'how']):
                return 'en'
            elif any(word in text_lower for word in ['o', 'a', 'os', 'as', 'que', 'qual', 'onde', 'quando', 'como']):
                return 'pt'
            return 'unknown'


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
    
    def _get_generator(self, preferred_generator_name: Optional[str] = None):
        """
        Lazy load do generator com fallback inteligente.
        
        Tenta usar o mesmo tipo de generator que está configurado no chat.
        Ordem de tentativa:
        1. Generator preferido (se especificado)
        2. OpenAI (mais comum)
        3. Anthropic
        4. Outros generators disponíveis
        """
        if self._generator is None:
            # Lista de generators para tentar (em ordem de preferência)
            generators_to_try = []
            
            if preferred_generator_name:
                generators_to_try.append(preferred_generator_name)
            
            # Adicionar generators comuns em ordem de preferência
            generators_to_try.extend([
                "OpenAI",      # Mais comum
                "Anthropic",   # Segundo mais comum
                "Groq",        # Alternativa rápida
                "Cohere",      # Outra alternativa
            ])
            
            # Tentar criar cada generator até conseguir
            for gen_name in generators_to_try:
                try:
                    if gen_name == "OpenAI":
                        from goldenverba.components.generation.OpenAIGenerator import OpenAIGenerator
                        self._generator = OpenAIGenerator()
                        msg.info(f"  Query builder: usando generator padrão '{gen_name}'")
                        return self._generator
                    elif gen_name == "Anthropic":
                        from goldenverba.components.generation.AnthrophicGenerator import AnthropicGenerator
                        self._generator = AnthropicGenerator()
                        msg.info(f"  Query builder: usando generator padrão '{gen_name}'")
                        return self._generator
                    elif gen_name == "Groq":
                        from goldenverba.components.generation.GroqGenerator import GroqGenerator
                        self._generator = GroqGenerator()
                        msg.info(f"  Query builder: usando generator padrão '{gen_name}'")
                        return self._generator
                    elif gen_name == "Cohere":
                        from goldenverba.components.generation.CohereGenerator import CohereGenerator
                        self._generator = CohereGenerator()
                        msg.info(f"  Query builder: usando generator padrão '{gen_name}'")
                        return self._generator
                except Exception as e:
                    msg.warn(f"  Query builder: não foi possível criar generator '{gen_name}': {e}")
                    continue
            
            # Se nenhum funcionou, tentar via GeneratorManager
            try:
                from goldenverba.components.managers import GeneratorManager
                generator_manager = GeneratorManager()
                
                # Tentar usar o primeiro generator disponível
                if generator_manager.generators:
                    first_gen_name = list(generator_manager.generators.keys())[0]
                    self._generator = generator_manager.generators[first_gen_name]
                    msg.info(f"  Query builder: usando primeiro generator disponível '{first_gen_name}'")
                    return self._generator
            except Exception as e:
                msg.warn(f"  Query builder: erro ao obter generator via GeneratorManager: {e}")
            
            msg.warn("  Query builder: nenhum generator disponível para fallback")
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
    
    async def get_dominant_language(
        self,
        client,
        collection_name: str,
        labels: Optional[List[str]] = None,
        document_uuids: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Obtém o idioma dominante dos documentos filtrados na collection.
        
        IMPORTANTE: Calcula apenas dos documentos que serão buscados (filtrados por labels/document_uuids).
        Isso permite que diferentes coleções de documentos tenham idiomas dominantes diferentes.
        
        Args:
            client: Cliente Weaviate
            collection_name: Nome da collection
            labels: Lista de labels para filtrar documentos (opcional)
            document_uuids: Lista de UUIDs de documentos para filtrar (opcional)
            
        Returns:
            Código do idioma dominante (ex: "en", "pt") ou None se não conseguir detectar
        """
        try:
            collection = client.collections.get(collection_name)
            
            # Verificar se chunk_lang existe no schema
            try:
                config = collection.config.get()
                if hasattr(config, '__await__'):
                    config = await config
            except TypeError:
                config = await collection.config.get()
            
            has_chunk_lang = any(prop.name == "chunk_lang" for prop in config.properties)
            
            if not has_chunk_lang:
                msg.info(f"  Query builder: collection '{collection_name}' não tem propriedade 'chunk_lang', não é possível detectar idioma dominante")
                return None
            
            # Construir filtros para agregação (apenas documentos que serão buscados)
            from weaviate.classes.query import Filter
            from weaviate.classes.aggregate import GroupByAggregate
            
            filters = []
            
            # Filtro por labels (se fornecido e não vazio)
            if labels and isinstance(labels, list) and len(labels) > 0:
                # Verificar se a collection tem propriedade "labels"
                has_labels = any(prop.name == "labels" for prop in config.properties)
                if has_labels:
                    filters.append(Filter.by_property("labels").contains_any(labels))
            
            # Filtro por document_uuids (se fornecido e não vazio)
            if document_uuids and isinstance(document_uuids, list) and len(document_uuids) > 0:
                # Verificar se a collection tem propriedade "doc_uuid"
                has_doc_uuid = any(prop.name == "doc_uuid" for prop in config.properties)
                if has_doc_uuid:
                    filters.append(Filter.by_property("doc_uuid").contains_any(document_uuids))
            
            # Combinar filtros
            combined_filter = None
            if len(filters) == 1:
                combined_filter = filters[0]
            elif len(filters) > 1:
                # AND entre filtros (documento deve ter label E estar na lista de UUIDs)
                combined_filter = filters[0]
                for f in filters[1:]:
                    combined_filter = combined_filter & f
            
            try:
                # Fazer agregação com filtros (se houver)
                if combined_filter:
                    result = await collection.aggregate.over_all(
                        filters=combined_filter,
                        group_by=GroupByAggregate(prop="chunk_lang"),
                        total_count=True
                    )
                    filter_info = []
                    if labels:
                        filter_info.append(f"labels={labels}")
                    if document_uuids:
                        filter_info.append(f"docs={len(document_uuids)}")
                    msg.info(f"  Query builder: calculando idioma dominante com filtros: {', '.join(filter_info)}")
                else:
                    msg.info(f"  Query builder: calculando idioma dominante de toda a collection '{collection_name}' (sem filtros)")
                    result = await collection.aggregate.over_all(
                        group_by=GroupByAggregate(prop="chunk_lang"),
                        total_count=True
                    )
                
                if not result.groups:
                    msg.info(f"  Query builder: agregação não retornou grupos (collection pode estar vazia ou chunk_lang não tem valores)")
                    return None
                
                # Log detalhado dos grupos encontrados
                msg.info(f"  Query builder: grupos de idioma encontrados: {[(g.grouped_by.value if hasattr(g.grouped_by, 'value') else 'unknown', g.total_count) for g in result.groups]}")
                
                # Encontrar o grupo com maior total_count
                dominant_group = max(result.groups, key=lambda g: g.total_count)
                dominant_lang = dominant_group.grouped_by.value if hasattr(dominant_group.grouped_by, 'value') else None
                
                if dominant_lang:
                    filter_desc = ""
                    if labels or document_uuids:
                        parts = []
                        if labels:
                            parts.append(f"labels: {labels}")
                        if document_uuids:
                            parts.append(f"{len(document_uuids)} docs")
                        filter_desc = f" (filtrado: {', '.join(parts)})"
                    msg.info(f"  Query builder: idioma dominante dos documentos{filter_desc}: {dominant_lang}")
                    return dominant_lang
                    
            except Exception as e:
                msg.info(f"  Query builder: erro ao obter idioma dominante: {str(e)}")
                return None
                
        except Exception as e:
            msg.info(f"  Query builder: erro ao verificar idioma dominante: {str(e)}")
            return None
        
        return None
    
    async def _detect_language_from_quick_search(
        self,
        client,
        collection_name: str,
        query: str,
        limit: int = 10
    ) -> Optional[str]:
        """
        Tenta detectar o idioma dominante fazendo uma busca rápida inicial.
        Útil quando a agregação não funciona ou quando não há filtros.
        
        Args:
            client: Cliente Weaviate
            collection_name: Nome da collection
            query: Query do usuário
            limit: Número de chunks para analisar (padrão: 10)
            
        Returns:
            Código do idioma dominante (ex: "en", "pt") ou None se não conseguir detectar
        """
        try:
            collection = client.collections.get(collection_name)
            
            # Verificar se chunk_lang existe no schema
            try:
                config = collection.config.get()
                if hasattr(config, '__await__'):
                    config = await config
            except TypeError:
                config = await collection.config.get()
            
            has_chunk_lang = any(prop.name == "chunk_lang" for prop in config.properties)
            if not has_chunk_lang:
                return None
            
            # Fazer busca híbrida rápida (BM25 + Vector se disponível)
            # Usar apenas BM25 para ser mais rápido e não depender de embedder
            from weaviate.classes.query import MetadataQuery, QueryReturn
            
            try:
                # Busca híbrida simples (BM25 com alpha=0.0 = apenas keyword)
                # Isso não requer vetor, então é mais rápido
                results = await collection.query.hybrid(
                    query=query,
                    alpha=0.0,  # Apenas BM25 (keyword search)
                    limit=limit,
                    return_metadata=MetadataQuery(score=True),
                    return_properties=["chunk_lang"]
                )
                
                if not results.objects:
                    return None
                
                # Contar idiomas dos chunks encontrados
                lang_counts = {}
                for obj in results.objects:
                    chunk_lang = obj.properties.get("chunk_lang")
                    if chunk_lang:
                        lang_counts[chunk_lang] = lang_counts.get(chunk_lang, 0) + 1
                
                if not lang_counts:
                    return None
                
                # Retornar idioma mais frequente
                dominant_lang = max(lang_counts.items(), key=lambda x: x[1])[0]
                msg.info(f"  Query builder: busca rápida encontrou {len(results.objects)} chunks, idiomas: {lang_counts}, dominante: {dominant_lang}")
                return dominant_lang
                
            except Exception as e:
                msg.info(f"  Query builder: erro na busca rápida: {str(e)}")
                return None
                
        except Exception as e:
            msg.info(f"  Query builder: erro ao fazer busca rápida para detectar idioma: {str(e)}")
            return None
    
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
        auto_detect_aggregation: bool = True,
        rag_config: Optional[Dict[str, Any]] = None,
        labels: Optional[List[str]] = None,
        document_uuids: Optional[List[str]] = None
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
        
        # SIMPLIFICADO: Usar sempre o idioma da query, não tentar detectar idioma dominante
        # Motivos:
        # 1. Com muitos documentos, busca rápida pode pegar chunks irrelevantes
        # 2. Agregação pode falhar ou retornar idioma não representativo
        # 3. É mais simples e confiável usar o idioma que o usuário está usando
        # 4. O LLM pode expandir a query adequadamente no idioma da query
        dominant_language = None  # Não usar detecção de idioma dominante
        
        # Chamar LLM para construir query
        try:
            # Obter generator configurado do RAG config (mesmo do chat) ou usar fallback
            generator = None
            generator_config = None
            preferred_generator_name = None  # Para usar no fallback se necessário
            
            if rag_config and "Generator" in rag_config:
                try:
                    from goldenverba.components.managers import GeneratorManager
                    generator_manager = GeneratorManager()
                    
                    generator_name = rag_config["Generator"].selected
                    preferred_generator_name = generator_name  # Guardar para fallback
                    generator_config = rag_config["Generator"].components[generator_name].config
                    
                    if generator_name in generator_manager.generators:
                        generator = generator_manager.generators[generator_name]
                        msg.info(f"  Query builder: usando generator configurado '{generator_name}' do RAG config")
                    else:
                        msg.warn(f"  Query builder: generator '{generator_name}' não encontrado no GeneratorManager, tentando criar novo")
                        # Tentar criar diretamente se não estiver no manager
                        try:
                            if generator_name == "OpenAI":
                                from goldenverba.components.generation.OpenAIGenerator import OpenAIGenerator
                                generator = OpenAIGenerator()
                            elif generator_name == "Anthropic":
                                from goldenverba.components.generation.AnthrophicGenerator import AnthropicGenerator
                                generator = AnthropicGenerator()
                            elif generator_name == "Groq":
                                from goldenverba.components.generation.GroqGenerator import GroqGenerator
                                generator = GroqGenerator()
                            elif generator_name == "Cohere":
                                from goldenverba.components.generation.CohereGenerator import CohereGenerator
                                generator = CohereGenerator()
                            else:
                                msg.warn(f"  Query builder: tipo de generator '{generator_name}' não suportado para criação direta")
                            
                            # Aplicar configuração do rag_config ao generator criado
                            if generator and generator_config:
                                try:
                                    # Atualizar config do generator com as configurações do rag_config
                                    for key, value in generator_config.items():
                                        if key in generator.config:
                                            if hasattr(generator.config[key], 'value'):
                                                generator.config[key].value = value.get('value', generator.config[key].value)
                                    msg.info(f"  Query builder: configuração do RAG config aplicada ao generator '{generator_name}'")
                                except Exception as e:
                                    msg.warn(f"  Query builder: erro ao aplicar configuração ao generator: {str(e)}")
                        except Exception as e:
                            msg.warn(f"  Query builder: erro ao criar generator '{generator_name}': {str(e)}")
                except Exception as e:
                    msg.warn(f"  Query builder: erro ao obter generator do RAG config: {str(e)}, tentando fallback")
            
            # Fallback: criar generator padrão se não conseguiu do RAG config
            # IMPORTANTE: Tenta usar o mesmo tipo de generator que está configurado no chat
            if generator is None:
                generator = self._get_generator(preferred_generator_name=preferred_generator_name)
                if generator is None:
                    msg.warn("  Query builder: generator não disponível, usando fallback (query não será expandida)")
                    return self._fallback_response(user_query)
                else:
                    if preferred_generator_name:
                        msg.info(f"  Query builder: usando generator padrão '{preferred_generator_name}' (RAG config não disponível, mas tentando mesmo tipo)")
                    else:
                        msg.info("  Query builder: usando generator padrão (RAG config não disponível)")
            
            strategy = await self._call_llm_with_schema(
                generator, user_query, schema_info, validate, generator_config, dominant_language
            )
            
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
        validate: bool,
        generator_config: Optional[Dict[str, Any]] = None,
        dominant_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Chama LLM para construir query conhecendo o schema"""
        
        # Detectar idioma da query
        query_language = detect_language(user_query)
        if query_language == "unknown":
            query_language = "en"  # Default para inglês se não detectar
        msg.info(f"  Query builder: idioma da query: {query_language.upper()}")
        
        # SIMPLIFICADO: Usar sempre o idioma da query para expansão
        # Não tentar detectar idioma dominante (pode ser problemático com muitos documentos)
        
        properties_str = "\n".join([
            f"  - {p['name']} ({p['type']}): {p.get('description', '')}"
            for p in schema_info["properties"]
        ])
        
        available_filters = ", ".join(schema_info["available_filters"])
        
        # Instrução sobre idioma baseada apenas no idioma da query
        language_instruction = ""
        if query_language == "en":
            language_instruction = """
REGRA CRÍTICA - IDIOMA:
- A query do usuário está em INGLÊS
- Você DEVE manter TODOS os termos expandidos em INGLÊS
- NÃO traduza para português ou qualquer outro idioma
- Exemplo: "which companies" → "companies corporations firms businesses organizations" (todos em inglês)
- Exemplo: "adding capacity" → "adding capacity expanding production increasing output building new facilities" (todos em inglês)
"""
        elif query_language == "pt":
            language_instruction = """
REGRA CRÍTICA - IDIOMA:
- A query do usuário está em PORTUGUÊS
- Você DEVE manter TODOS os termos expandidos em PORTUGUÊS
- NÃO traduza para inglês ou qualquer outro idioma
- Exemplo: "oportunidades de ganho" → "oportunidades de ganho retorno lucro benefício maximização valor receita" (todos em português)
"""
        else:
            language_instruction = f"""
REGRA CRÍTICA - IDIOMA:
- A query do usuário está em {query_language.upper()}
- Você DEVE manter TODOS os termos expandidos no MESMO IDIOMA ({query_language})
- NÃO traduza para outro idioma
- Mantenha a consistência linguística em toda a expansão
"""
        
        prompt = f"""Você é um assistente especializado em construir queries complexas para busca vetorial no Weaviate.

SCHEMA DA COLLECTION ({schema_info['collection_name']}):
Propriedades disponíveis:
{properties_str}

Filtros disponíveis: {available_filters}
ETL-aware: {schema_info['etl_aware']}

QUERY DO USUÁRIO: "{user_query}"
IDIOMA DA QUERY: {query_language.upper()}

{language_instruction}

Sua tarefa:
1. Analisar a query do usuário e entender o que ele quer
2. Extrair entidades mencionadas (ex: "Apple", "Microsoft", "2024")
3. Identificar filtros necessários (entidades, datas, idioma, etc.)
4. **EXPANDIR a query semântica** com sinônimos, termos relacionados e conceitos semânticos **NO MESMO IDIOMA DA QUERY ORIGINAL**
5. Gerar query keyword otimizada para BM25 (termos-chave importantes) **NO MESMO IDIOMA**
6. Determinar intenção (search, comparison, description)
7. Sugerir alpha para hybrid search

REGRA CRÍTICA - EXPANSÃO SEMÂNTICA:
- A query semântica DEVE ser EXPANDIDA, não apenas repetir a query original
- Adicione sinônimos, termos relacionados, conceitos semânticos **NO MESMO IDIOMA DA QUERY ORIGINAL**
- Exemplo (português): "oportunidades de ganho" → "oportunidades de ganho retorno lucro benefício maximização valor receita"
- Exemplo (português): "revisão tarifária" → "revisão tarifária tarifa distribuidora energia elétrica ANEEL receita requerida"
- Exemplo (inglês): "which companies" → "which companies corporations firms businesses organizations enterprises"
- Exemplo (inglês): "adding capacity" → "adding capacity expanding production increasing output building new facilities"
- NUNCA retorne a query original sem expansão
- NUNCA traduza a query para outro idioma

IMPORTANTE:
- Use propriedades do schema para filtros (entities_local_ids, section_entity_ids, chunk_lang, chunk_date, etc.)
- Se mencionar empresa/pessoa, use filtro de entidade (entities_local_ids ou section_entity_ids)
  - NOVO: Use NOMES DIRETOS das entidades (ex: ["Apple", "Microsoft"]) em vez de IDs
  - O sistema detecta automaticamente PERSON e ORG usando NER inteligente
  - Exemplo: "sobre Apple" → entities: ["Apple"]
  - Exemplo: "Steve Jobs e Microsoft" → entities: ["Steve Jobs", "Microsoft"]
- Se mencionar data/ano, use filtro temporal (chunk_date)
- Se mencionar idioma, use filtro de idioma (chunk_lang)
- **SEMPRE expanda a query semântica** - adicione termos relacionados, sinônimos, conceitos
- Gere query keyword otimizada para BM25 (termos-chave principais)

FILTROS HIERÁRQUICOS (se necessário):
- Se query menciona "documentos que falam sobre X, depois chunks sobre Y":
  - document_level_entities: ["Apple"]  // Filtrar documentos que mencionam Apple
  - entities: ["Microsoft"]  // Depois filtrar chunks sobre Microsoft dentro desses documentos

FILTROS POR FREQUÊNCIA (se necessário):
- Se query menciona "entidade dominante", "mais frequente", "principal":
  - filter_by_frequency: true
  - min_frequency: 5  // Frequência mínima (opcional)
  - dominant_only: true  // Apenas entidade dominante (opcional)
- Se query menciona "mais que X", "aparece mais que Y":
  - frequency_comparison: {{"entity_1": "Apple", "entity_2": "Microsoft", "min_ratio": 1.5}}

Retorne JSON válido (SEM COMENTÁRIOS, SEM //, SEM /* */):
{{
    "semantic_query": "query expandida para busca semântica",
    "keyword_query": "query otimizada para BM25",
    "intent": "search|comparison|description",
    "filters": {{
        "entities": ["Apple", "Microsoft"],
        "entity_property": "section_entity_ids",
        "document_level_entities": [],
        "filter_by_frequency": false,
        "min_frequency": 0,
        "dominant_only": false,
        "frequency_comparison": null,
        "date_range": {{"start": "2024-01-01", "end": "2024-12-31"}},
        "language": "pt",
        "labels": [],
        "section_title": ""
    }},
    "alpha": 0.6,
    "explanation": "Explicação da query: filtros aplicados, entidades detectadas, etc.",
    "requires_validation": {str(validate).lower()}
}}

IMPORTANTE: Retorne APENAS JSON válido, sem comentários (// ou /* */), sem markdown, sem explicações fora do JSON.
"""
        
        try:
            import asyncio
            
            # Usar generator_config passado (do RAG config) ou fallback para generator.config
            if generator_config is None:
                generator_config = generator.config if hasattr(generator, "config") else {}
            
            # Log do modelo usado
            model_name = "unknown"
            if isinstance(generator_config, dict) and "Model" in generator_config:
                model_config = generator_config["Model"]
                if isinstance(model_config, dict):
                    model_name = model_config.get("value", "unknown")
                elif hasattr(model_config, "value"):
                    model_name = model_config.value
            msg.info(f"  Query builder: usando config do generator (modelo: {model_name})")
            
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
                # Remover markdown code blocks
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                # Remover comentários de linha (//) e de bloco (/* */) do JSON
                import re
                # Remove comentários de linha (// ...)
                response_text = re.sub(r'//.*?$', '', response_text, flags=re.MULTILINE)
                # Remove comentários de bloco (/* ... */)
                response_text = re.sub(r'/\*.*?\*/', '', response_text, flags=re.DOTALL)
                
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
        """Resposta de fallback se LLM falhar - ainda tenta extrair entidades"""
        msg.warn(f"  Query builder: usando fallback (LLM não disponível ou erro)")
        
        # Tentar extrair entidades mesmo no fallback usando spaCy (modo inteligente)
        entity_ids = []
        try:
            from verba_extensions.plugins.entity_aware_query_orchestrator import extract_entities_from_query
            # MODO INTELIGENTE: detecta PERSON/ORG sem precisar de gazetteer
            entity_ids = extract_entities_from_query(query, use_gazetteer=False)
            if entity_ids:
                msg.info(f"  Query builder (fallback): entidades detectadas (modo inteligente): {entity_ids}")
        except Exception as e:
            msg.info(f"  Query builder (fallback): erro ao extrair entidades: {str(e)}")
        
        return {
            "semantic_query": query,  # Fallback não expande - apenas retorna original
            "keyword_query": query,
            "intent": "search",
            "filters": {
                "entities": entity_ids,  # Entidades extraídas via spaCy + Gazetteer
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
            "explanation": f"Query simples (fallback - LLM não disponível)" + (f", entidades detectadas: {len(entity_ids)}" if entity_ids else ""),
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

