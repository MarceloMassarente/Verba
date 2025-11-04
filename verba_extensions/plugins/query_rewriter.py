"""
Plugin: Query Rewriter
Reescreve queries usando LLM para melhorar busca semântica

Baseado em RAG2: agent/query_understander.py
"""

import json
import time
from typing import Dict, Any, Optional
from wasabi import msg


class QueryRewriterPlugin:
    """
    Plugin que reescreve queries usando LLM para melhorar busca.
    
    Features:
    - Expansão de sinônimos e conceitos relacionados
    - Separação entre query semântica e keyword query
    - Detecção de intenção (comparison, description, search)
    - Sugestão de alpha para hybrid search
    - Cache LRU para queries similares
    """
    
    def __init__(self, cache_ttl_seconds: int = 3600):
        """
        Inicializa QueryRewriterPlugin.
        
        Args:
            cache_ttl_seconds: TTL do cache em segundos (default: 1 hora)
        """
        self.cache: Dict[str, tuple[Dict[str, Any], float]] = {}
        self.cache_ttl = cache_ttl_seconds
        self._generator = None
    
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
    
    async def rewrite_query(
        self,
        original_query: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Reescreve query usando LLM.
        
        Args:
            original_query: Query original do usuário
            use_cache: Se deve usar cache (default: True)
            
        Returns:
            Dict com:
            {
                "semantic_query": "query expandida para busca semântica",
                "keyword_query": "query para BM25",
                "intent": "comparison|description|search",
                "filters": {},
                "alpha": 0.6
            }
        """
        if not original_query or not original_query.strip():
            return self._fallback_response(original_query)
        
        # Verificar cache
        if use_cache:
            cache_key = original_query.lower().strip()
            if cache_key in self.cache:
                cached_strategy, timestamp = self.cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    msg.info(f"  Query rewriting: cache hit")
                    return cached_strategy
        
        # Chamar LLM
        try:
            generator = self._get_generator()
            if generator is None:
                msg.warn("  Query rewriting: generator não disponível, usando fallback")
                return self._fallback_response(original_query)
            
            strategy = await self._call_llm(generator, original_query)
            
            # Validar resposta
            if not self._validate_strategy(strategy):
                msg.warn("  Query rewriting: resposta inválida do LLM, usando fallback")
                return self._fallback_response(original_query)
            
            # Cache
            if use_cache:
                cache_key = original_query.lower().strip()
                self.cache[cache_key] = (strategy, time.time())
            
            msg.good(f"  Query rewriting: query otimizada")
            return strategy
            
        except Exception as e:
            msg.warn(f"  Query rewriting: erro ({str(e)}), usando fallback")
            return self._fallback_response(original_query)
    
    async def _call_llm(self, generator, query: str) -> Dict[str, Any]:
        """Chama LLM para reescrever query (async)"""
        prompt = f"""Analise a query do usuário e retorne JSON com:
1. semantic_query: Query reescrita para busca semântica (expandir sinônimos, conceitos relacionados, contexto)
2. keyword_query: Query otimizada para busca BM25 (manter termos-chave importantes, remover stopwords irrelevantes)
3. intent: "comparison" (comparação), "description" (descrição), "search" (busca simples)
4. filters: Objeto vazio {{}} (pode ser usado para filtros futuros)
5. alpha: Balance entre keyword (0.0) e vector (1.0) - sugerir entre 0.4-0.7

Query original: "{query}"

Retorne apenas JSON válido, sem markdown, sem explicações:
{{
    "semantic_query": "...",
    "keyword_query": "...",
    "intent": "...",
    "filters": {{}},
    "alpha": 0.6
}}
"""
        
        try:
            # AnthropicGenerator.generate é async e retorna generator
            # Precisamos coletar a resposta completa
            import asyncio
            
            # Criar mensagem para o generator
            messages = [{"role": "user", "content": prompt}]
            
            # Config básico
            generator_config = generator.config if hasattr(generator, "config") else {}
            
            # Chamar generate_stream (async generator)
            # Assinatura: generate_stream(config, query, context, conversation=[])
            response_text = ""
            async for chunk in generator.generate_stream(
                generator_config,
                prompt,
                "",  # context vazio para query rewriting
                [],  # conversation vazia
            ):
                if isinstance(chunk, dict) and "message" in chunk:
                    response_text += chunk["message"]
            
            # Parse JSON
            if response_text:
                # Remove markdown code blocks se houver
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
            raise
        except Exception as e:
            msg.warn(f"Erro ao chamar LLM: {e}")
            raise
    
    def _validate_strategy(self, strategy: Dict[str, Any]) -> bool:
        """Valida estrutura da estratégia retornada pelo LLM"""
        required_fields = ["semantic_query", "keyword_query", "intent", "alpha"]
        
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
        if not isinstance(strategy["alpha"], (int, float)) or not (0.0 <= strategy["alpha"] <= 1.0):
            return False
        
        return True
    
    def _fallback_response(self, query: str) -> Dict[str, Any]:
        """Resposta de fallback se LLM falhar"""
        return {
            "semantic_query": query,
            "keyword_query": query,
            "intent": "search",
            "filters": {},
            "alpha": 0.6
        }
    
    def clear_cache(self):
        """Limpa cache"""
        self.cache.clear()
        msg.info("Cache de query rewriting limpo")
    
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
            "cache_ttl_seconds": self.cache_ttl
        }

