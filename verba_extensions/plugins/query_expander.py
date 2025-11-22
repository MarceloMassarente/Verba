"""
Query Expander Plugin
Gera múltiplas variações de queries para melhorar Recall em busca multi-vector

Suporta expansão para:
- Fase 1: Entidades (foco em extrair entidades nomeadas)
- Fase 2: Temas (foco em conceitos, setores, frameworks)
"""

import time
from typing import List, Dict, Any, Optional
from wasabi import msg


class QueryExpanderPlugin:
    """
    Plugin para expansão de queries usando LLM.
    
    Gera 3-5 variações da query original para aumentar Recall em busca multi-vector.
    """
    
    def __init__(self, cache_ttl_seconds: int = 3600):
        """
        Inicializa Query Expander.
        
        Args:
            cache_ttl_seconds: TTL do cache em segundos (padrão: 1 hora)
        """
        self.cache_ttl = cache_ttl_seconds
        self.cache: Dict[str, tuple] = {}  # {query: (variations, timestamp)}
        self._generator = None
    
    def _get_generator(self):
        """Lazy load do generator para LLM"""
        if self._generator is None:
            try:
                from goldenverba.components.managers import GeneratorManager
                generator_manager = GeneratorManager()
                # Tenta pegar primeiro generator disponível (geralmente OpenAI ou Ollama)
                if generator_manager.generators:
                    self._generator = list(generator_manager.generators.values())[0]
            except Exception as e:
                msg.debug(f"QueryExpander: Generator não disponível: {str(e)}")
        return self._generator
    
    async def expand_query_for_entities(
        self, 
        query: str,
        use_cache: bool = True
    ) -> List[str]:
        """
        Expande query focando em extrair entidades nomeadas.
        
        Gera variações que ajudam a identificar entidades (empresas, pessoas, organizações).
        
        Args:
            query: Query original
            use_cache: Se deve usar cache (default: True)
        
        Returns:
            Lista de variações da query (incluindo a original)
        """
        if not query or not query.strip():
            return [query]
        
        # Verificar cache
        if use_cache:
            cache_key = f"entities:{query.lower().strip()}"
            if cache_key in self.cache:
                variations, timestamp = self.cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    msg.debug(f"QueryExpander: Cache hit para entidades")
                    return variations
        
        # Tentar usar LLM para expansão
        generator = self._get_generator()
        if generator:
            try:
                prompt = f"""Gere 3-5 variações da seguinte query focando em identificar entidades nomeadas (empresas, pessoas, organizações, lugares).

Query original: "{query}"

Variações devem:
- Manter o foco em entidades específicas
- Usar sinônimos e formas alternativas de mencionar as mesmas entidades
- Ser concisas (1-2 frases cada)

Retorne apenas as variações, uma por linha, sem numeração ou marcadores:
"""
                response = await generator.generate([{"role": "user", "content": prompt}])
                
                if response and hasattr(response, 'content'):
                    variations_text = response.content
                elif isinstance(response, str):
                    variations_text = response
                else:
                    variations_text = ""
                
                # Parse variações
                variations = [q.strip() for q in variations_text.split('\n') if q.strip()]
                variations = [q for q in variations if len(q) > 5]  # Filtrar muito curtas
                
                # Limitar a 5 variações
                variations = variations[:5]
                
                # Sempre incluir query original
                if query not in variations:
                    variations.insert(0, query)
                else:
                    # Mover original para primeiro lugar
                    variations.remove(query)
                    variations.insert(0, query)
                
                # Cache
                if use_cache:
                    cache_key = f"entities:{query.lower().strip()}"
                    self.cache[cache_key] = (variations, time.time())
                
                msg.info(f"QueryExpander: Geradas {len(variations)} variações para entidades")
                return variations
                
            except Exception as e:
                msg.warn(f"QueryExpander: Erro ao expandir query com LLM: {str(e)}")
        
        # Fallback: retorna apenas query original
        return [query]
    
    async def expand_query_for_themes(
        self,
        query: str,
        use_cache: bool = True
    ) -> List[str]:
        """
        Expande query focando em temas, conceitos e frameworks.
        
        Gera variações que ajudam a identificar conceitos abstratos, setores, metodologias.
        
        Args:
            query: Query original
            use_cache: Se deve usar cache (default: True)
        
        Returns:
            Lista de variações da query (incluindo a original)
        """
        if not query or not query.strip():
            return [query]
        
        # Verificar cache
        if use_cache:
            cache_key = f"themes:{query.lower().strip()}"
            if cache_key in self.cache:
                variations, timestamp = self.cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    msg.debug(f"QueryExpander: Cache hit para temas")
                    return variations
        
        # Tentar usar LLM para expansão
        generator = self._get_generator()
        if generator:
            try:
                prompt = f"""Gere 3-5 variações da seguinte query focando em temas, conceitos, frameworks e metodologias.

Query original: "{query}"

Variações devem:
- Explorar conceitos relacionados e sinônimos
- Incluir termos técnicos e jargão do domínio
- Ser concisas (1-2 frases cada)
- Manter o contexto semântico

Retorne apenas as variações, uma por linha, sem numeração ou marcadores:
"""
                response = await generator.generate([{"role": "user", "content": prompt}])
                
                if response and hasattr(response, 'content'):
                    variations_text = response.content
                elif isinstance(response, str):
                    variations_text = response
                else:
                    variations_text = ""
                
                # Parse variações
                variations = [q.strip() for q in variations_text.split('\n') if q.strip()]
                variations = [q for q in variations if len(q) > 5]  # Filtrar muito curtas
                
                # Limitar a 5 variações
                variations = variations[:5]
                
                # Sempre incluir query original
                if query not in variations:
                    variations.insert(0, query)
                else:
                    # Mover original para primeiro lugar
                    variations.remove(query)
                    variations.insert(0, query)
                
                # Cache
                if use_cache:
                    cache_key = f"themes:{query.lower().strip()}"
                    self.cache[cache_key] = (variations, time.time())
                
                msg.info(f"QueryExpander: Geradas {len(variations)} variações para temas")
                return variations
                
            except Exception as e:
                msg.warn(f"QueryExpander: Erro ao expandir query com LLM: {str(e)}")
        
        # Fallback: retorna apenas query original
        return [query]
    
    async def expand_query_multi(
        self,
        query: str,
        phase: str = "entities",
        use_cache: bool = True
    ) -> List[str]:
        """
        Expande query para múltiplas variações baseado na fase.
        
        Args:
            query: Query original
            phase: "entities" ou "themes"
            use_cache: Se deve usar cache
        
        Returns:
            Lista de variações da query
        """
        if phase == "entities":
            return await self.expand_query_for_entities(query, use_cache)
        elif phase == "themes":
            return await self.expand_query_for_themes(query, use_cache)
        else:
            # Fallback: retorna apenas query original
            return [query]

