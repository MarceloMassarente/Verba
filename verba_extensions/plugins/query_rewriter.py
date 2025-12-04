"""
Plugin: Query Rewriter
Reescreve queries usando LLM para melhorar busca semântica

Baseado em RAG2: agent/query_understander.py

=== RAG 2.0 Enhancement: Adaptive Query Rewriting ===
- Calcula entropia da query para decidir força do rewrite
- Queries genéricas (alta entropia) → rewrite forte
- Queries específicas (baixa entropia) → rewrite leve ou skip
- Economiza chamadas ao LLM quando não necessário
"""

import json
import time
import math
import re
from typing import Dict, Any, Optional, Tuple
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
    
    def __init__(self, cache_ttl_seconds: int = 3600, adaptive_mode: bool = True):
        """
        Inicializa QueryRewriterPlugin.
        
        Args:
            cache_ttl_seconds: TTL do cache em segundos (default: 1 hora)
            adaptive_mode: Se True, usa entropia para decidir força do rewrite (default: True)
        """
        self.cache: Dict[str, tuple[Dict[str, Any], float]] = {}
        self.cache_ttl = cache_ttl_seconds
        self._generator = None
        self.adaptive_mode = adaptive_mode
        
        # Thresholds para decisão adaptativa
        self.entropy_threshold_skip = 0.3  # Muito específico, não reescrever
        self.entropy_threshold_light = 0.5  # Moderado, rewrite leve
        self.entropy_threshold_strong = 0.7  # Genérico, rewrite forte
        
        # Stopwords para cálculo de entropia - importadas do módulo utilitário comum
        from verba_extensions.utils.language_utils import STOPWORDS_PT, STOPWORDS_EN
        self._stopwords_pt = STOPWORDS_PT
        self._stopwords_en = STOPWORDS_EN
    
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
    
    # =========================================================================
    # RAG 2.0 Enhancement: Adaptive Query Rewriting
    # =========================================================================
    
    def _calculate_entropy(self, query: str) -> Tuple[float, Dict[str, Any]]:
        """
        Calcula entropia léxica da query.
        
        Entropia alta = query genérica (ex: "o que é isso?")
        Entropia baixa = query específica (ex: "Steve Jobs cofundador Apple 2007")
        
        Args:
            query: Query do usuário
            
        Returns:
            Tuple[float, Dict]: (entropy_score 0-1, debug_info)
        """
        if not query or not query.strip():
            return 0.5, {"error": "empty query"}
        
        # Tokenizar (simples, sem dependências)
        words = re.findall(r'\b\w+\b', query.lower())
        
        if len(words) == 0:
            return 0.5, {"error": "no words"}
        
        # Remover stopwords
        stopwords = self._stopwords_pt | self._stopwords_en
        content_words = [w for w in words if w not in stopwords and len(w) > 1]
        
        if len(content_words) == 0:
            # Query é só stopwords = muito genérica
            return 1.0, {"reason": "only_stopwords", "words": words}
        
        # Calcular métricas
        total_words = len(words)
        unique_words = len(set(words))
        content_word_count = len(content_words)
        unique_content_words = len(set(content_words))
        
        # Detectar entidades (palavras com maiúscula ou números)
        entities = [w for w in query.split() if w[0].isupper() or any(c.isdigit() for c in w)]
        entity_count = len(entities)
        
        # Calcular entropia combinada
        # 1. Ratio de palavras únicas (0-1, maior = mais diverso)
        uniqueness_ratio = unique_words / total_words if total_words > 0 else 0
        
        # 2. Ratio de stopwords (0-1, maior = mais genérico)
        stopword_ratio = (total_words - content_word_count) / total_words if total_words > 0 else 0
        
        # 3. Presença de entidades (0-1, maior = mais específico)
        entity_ratio = min(entity_count / max(total_words, 1), 1.0)
        
        # 4. Comprimento da query (queries muito curtas tendem a ser genéricas)
        length_factor = min(total_words / 10, 1.0)  # Normaliza até 10 palavras
        
        # Combinar fatores
        # Alta entropia = genérico = precisa rewrite forte
        # Baixa entropia = específico = não precisa rewrite
        entropy = (
            0.3 * uniqueness_ratio +      # Diversidade léxica
            0.4 * stopword_ratio +         # Proporção de stopwords
            0.2 * (1 - entity_ratio) +     # Ausência de entidades
            0.1 * (1 - length_factor)      # Queries curtas
        )
        
        debug_info = {
            "total_words": total_words,
            "unique_words": unique_words,
            "content_words": content_word_count,
            "entities_detected": entities,
            "uniqueness_ratio": round(uniqueness_ratio, 3),
            "stopword_ratio": round(stopword_ratio, 3),
            "entity_ratio": round(entity_ratio, 3),
            "length_factor": round(length_factor, 3),
            "entropy": round(entropy, 3)
        }
        
        return entropy, debug_info
    
    def should_rewrite(self, query: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Decide se deve reescrever a query e com qual intensidade.
        
        Args:
            query: Query do usuário
            
        Returns:
            Tuple[bool, str, Dict]: (should_rewrite, rewrite_mode, debug_info)
            - rewrite_mode: "skip" | "light" | "moderate" | "strong"
        """
        entropy, debug_info = self._calculate_entropy(query)
        
        if entropy < self.entropy_threshold_skip:
            # Query muito específica - não reescrever
            mode = "skip"
            should = False
            msg.info(f"  Adaptive rewrite: SKIP (entropy={entropy:.3f}, query específica)")
        elif entropy < self.entropy_threshold_light:
            # Query moderadamente específica - rewrite leve
            mode = "light"
            should = True
            msg.info(f"  Adaptive rewrite: LIGHT (entropy={entropy:.3f})")
        elif entropy < self.entropy_threshold_strong:
            # Query moderada - rewrite moderado
            mode = "moderate"
            should = True
            msg.info(f"  Adaptive rewrite: MODERATE (entropy={entropy:.3f})")
        else:
            # Query genérica - rewrite forte
            mode = "strong"
            should = True
            msg.info(f"  Adaptive rewrite: STRONG (entropy={entropy:.3f}, query genérica)")
        
        debug_info["rewrite_mode"] = mode
        debug_info["should_rewrite"] = should
        
        return should, mode, debug_info
    
    def _get_prompt_for_mode(self, query: str, mode: str) -> str:
        """
        Retorna prompt apropriado para o modo de rewrite.
        
        Args:
            query: Query original
            mode: "light" | "moderate" | "strong"
            
        Returns:
            str: Prompt para o LLM
        """
        if mode == "light":
            return f"""Faça uma expansão LEVE da query do usuário. Adicione apenas 2-3 sinônimos diretos.
NÃO mude o significado. NÃO adicione conceitos novos.

Query original: "{query}"

Retorne apenas JSON válido, sem markdown:
{{
    "semantic_query": "query com 2-3 sinônimos diretos adicionados",
    "keyword_query": "{query}",
    "intent": "search",
    "filters": {{}},
    "alpha": 0.6
}}"""
        
        elif mode == "moderate":
            return f"""Expanda a query do usuário de forma MODERADA.
Adicione sinônimos e alguns conceitos relacionados.

Query original: "{query}"

Retorne apenas JSON válido, sem markdown:
{{
    "semantic_query": "query expandida com sinônimos e conceitos relacionados",
    "keyword_query": "termos-chave principais",
    "intent": "comparison|description|search",
    "filters": {{}},
    "alpha": 0.5-0.7
}}"""
        
        else:  # strong
            return f"""Analise a query do usuário e retorne JSON com:
1. semantic_query: Query FORTEMENTE reescrita para busca semântica (expandir sinônimos, conceitos relacionados, contexto, termos técnicos)
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
}}"""
    
    async def rewrite_query(
        self,
        original_query: str,
        use_cache: bool = True,
        force_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reescreve query usando LLM com modo adaptativo.
        
        Args:
            original_query: Query original do usuário
            use_cache: Se deve usar cache (default: True)
            force_mode: Força um modo específico ("skip", "light", "moderate", "strong")
                        Se None, usa modo adaptativo baseado em entropia
            
        Returns:
            Dict com:
            {
                "semantic_query": "query expandida para busca semântica",
                "keyword_query": "query para BM25",
                "intent": "comparison|description|search",
                "filters": {},
                "alpha": 0.6,
                "adaptive_info": {...}  # Info sobre decisão adaptativa
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
        
        # RAG 2.0: Decisão adaptativa baseada em entropia
        if self.adaptive_mode and force_mode is None:
            should_rewrite, rewrite_mode, adaptive_info = self.should_rewrite(original_query)
            
            if not should_rewrite:
                # Query muito específica, não precisa reescrever
                response = self._fallback_response(original_query)
                response["adaptive_info"] = adaptive_info
                response["adaptive_info"]["skipped"] = True
                msg.info(f"  Query rewriting: SKIPPED (query específica, entropy={adaptive_info.get('entropy', 0):.3f})")
                return response
        else:
            # Modo forçado ou não-adaptativo
            rewrite_mode = force_mode if force_mode else "strong"
            adaptive_info = {"mode": rewrite_mode, "forced": True}
        
        # Chamar LLM com o modo apropriado
        try:
            generator = self._get_generator()
            if generator is None:
                msg.warn("  Query rewriting: generator não disponível, usando fallback")
                return self._fallback_response(original_query)
            
            strategy = await self._call_llm(generator, original_query, rewrite_mode)
            
            # Validar resposta
            if not self._validate_strategy(strategy):
                msg.warn("  Query rewriting: resposta inválida do LLM, usando fallback")
                return self._fallback_response(original_query)
            
            # Adicionar info adaptativa
            strategy["adaptive_info"] = adaptive_info
            
            # Cache
            if use_cache:
                cache_key = original_query.lower().strip()
                self.cache[cache_key] = (strategy, time.time())
            
            msg.good(f"  Query rewriting: query otimizada (mode={rewrite_mode})")
            return strategy
            
        except Exception as e:
            msg.warn(f"  Query rewriting: erro ({str(e)}), usando fallback")
            return self._fallback_response(original_query)
    
    async def _call_llm(self, generator, query: str, mode: str = "strong") -> Dict[str, Any]:
        """
        Chama LLM para reescrever query (async).
        
        Args:
            generator: Generator LLM
            query: Query original
            mode: Modo de rewrite ("light", "moderate", "strong")
        """
        # Usar prompt apropriado para o modo
        prompt = self._get_prompt_for_mode(query, mode)
        
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

