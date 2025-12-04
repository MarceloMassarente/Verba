"""
EXPERIMENTAL - RAG 2.0 Enhancement: Iterative Search During Generation

⚠️ STATUS: Este plugin é EXPERIMENTAL e não está totalmente integrado no fluxo principal.
Use com cautela em produção. Veja docs/guides/RAG2_EXPERIMENTAL_PLUGINS.md para mais detalhes.

Este plugin implementa busca iterativa durante a geração de resposta,
simulando o comportamento do RAG 2.0 onde o modelo pode pausar a geração
para buscar mais informações quando necessário.

Conceito RAG 2.0:
- Modelo gera texto normalmente
- Quando detecta necessidade de mais informação, emite token especial [SEARCH: query]
- Sistema pausa, faz nova busca, injeta contexto adicional
- Modelo continua gerando com contexto enriquecido

Implementação:
- Monitora tokens gerados em tempo real
- Detecta padrão [SEARCH: query] no texto
- Extrai query de busca
- Faz busca adicional via retriever
- Injeta novo contexto no prompt
- Continua geração

Limitações:
- Requer suporte do modelo para gerar tokens [SEARCH:]
- Adiciona latência (cada busca = ~500ms-2s)
- Máximo de iterações configurável para evitar loops
"""

import re
import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator, Tuple
from dataclasses import dataclass, field
from wasabi import msg


@dataclass
class SearchRequest:
    """Representa uma requisição de busca extraída do texto."""
    query: str
    position: int  # Posição no texto onde foi encontrada
    original_match: str  # Match original (ex: "[SEARCH: query]")


@dataclass
class IterativeSearchConfig:
    """Configuração para busca iterativa."""
    enabled: bool = False
    max_iterations: int = 3
    search_token_pattern: str = r'\[SEARCH:\s*([^\]]+)\]'
    min_chars_before_search: int = 50  # Mínimo de chars antes de permitir busca
    inject_separator: str = "\n\n[Additional Context from Search]\n"
    timeout_per_search: float = 5.0  # Timeout em segundos


class IterativeSearchPlugin:
    """
    Plugin para busca iterativa durante geração.
    
    Monitora o texto sendo gerado e detecta tokens especiais que
    indicam necessidade de busca adicional.
    """
    
    def __init__(self, config: Optional[IterativeSearchConfig] = None):
        """
        Inicializa o plugin.
        
        Args:
            config: Configuração do plugin
        """
        self.config = config or IterativeSearchConfig()
        self._search_pattern = re.compile(self.config.search_token_pattern)
        
        # Estatísticas
        self._stats = {
            "total_generations": 0,
            "generations_with_search": 0,
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "timeouts": 0
        }
    
    def detect_search_token(self, text: str) -> Optional[SearchRequest]:
        """
        Detecta token de busca no texto.
        
        Args:
            text: Texto gerado até o momento
            
        Returns:
            SearchRequest se encontrado, None caso contrário
        """
        if not text or len(text) < self.config.min_chars_before_search:
            return None
        
        match = self._search_pattern.search(text)
        if match:
            return SearchRequest(
                query=match.group(1).strip(),
                position=match.start(),
                original_match=match.group(0)
            )
        
        return None
    
    def extract_all_search_tokens(self, text: str) -> List[SearchRequest]:
        """
        Extrai todos os tokens de busca do texto.
        
        Args:
            text: Texto completo
            
        Returns:
            Lista de SearchRequest
        """
        requests = []
        for match in self._search_pattern.finditer(text):
            requests.append(SearchRequest(
                query=match.group(1).strip(),
                position=match.start(),
                original_match=match.group(0)
            ))
        return requests
    
    def remove_search_tokens(self, text: str) -> str:
        """
        Remove tokens de busca do texto final.
        
        Args:
            text: Texto com tokens
            
        Returns:
            Texto limpo
        """
        return self._search_pattern.sub('', text)
    
    def should_continue_search(self, iteration: int) -> bool:
        """
        Verifica se deve continuar buscando.
        
        Args:
            iteration: Número da iteração atual
            
        Returns:
            True se deve continuar, False caso contrário
        """
        return iteration < self.config.max_iterations
    
    async def process_stream_with_search(
        self,
        generator_stream: AsyncGenerator[Dict[str, Any], None],
        search_func: callable,
        context_builder_func: callable
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Processa stream de geração com busca iterativa.
        
        Este é o método principal que:
        1. Monitora tokens sendo gerados
        2. Detecta [SEARCH: query]
        3. Pausa, faz busca, injeta contexto
        4. Continua geração
        
        Args:
            generator_stream: Stream do generator original
            search_func: Função async para buscar (query -> chunks)
            context_builder_func: Função para construir contexto (chunks -> str)
            
        Yields:
            Dict com tokens gerados (mesmo formato do generator original)
        """
        if not self.config.enabled:
            # Se desabilitado, apenas repassa o stream
            async for result in generator_stream:
                yield result
            return
        
        self._stats["total_generations"] += 1
        
        accumulated_text = ""
        iteration = 0
        searches_done = []
        
        async for result in generator_stream:
            token = result.get("message", "")
            accumulated_text += token
            
            # Verificar se há token de busca
            search_request = self.detect_search_token(accumulated_text)
            
            if search_request and self.should_continue_search(iteration):
                iteration += 1
                self._stats["total_searches"] += 1
                
                msg.info(f"  🔍 Iterative Search #{iteration}: '{search_request.query}'")
                
                try:
                    # Fazer busca
                    search_task = asyncio.create_task(
                        search_func(search_request.query)
                    )
                    chunks = await asyncio.wait_for(
                        search_task,
                        timeout=self.config.timeout_per_search
                    )
                    
                    if chunks:
                        # Construir contexto adicional
                        additional_context = context_builder_func(chunks)
                        
                        # Remover o token de busca do texto acumulado
                        accumulated_text = accumulated_text.replace(
                            search_request.original_match,
                            ""
                        )
                        
                        # Injetar contexto (será usado na próxima iteração)
                        searches_done.append({
                            "query": search_request.query,
                            "chunks_found": len(chunks),
                            "context_length": len(additional_context)
                        })
                        
                        self._stats["successful_searches"] += 1
                        msg.info(f"  ✅ Search #{iteration}: {len(chunks)} chunks encontrados")
                        
                        # Emitir token indicando contexto adicional
                        yield {
                            "message": f"\n\n[Contexto adicional encontrado para: {search_request.query}]\n",
                            "finish_reason": None,
                            "iterative_search": True
                        }
                    else:
                        self._stats["failed_searches"] += 1
                        msg.warn(f"  ⚠️ Search #{iteration}: nenhum chunk encontrado")
                        
                except asyncio.TimeoutError:
                    self._stats["timeouts"] += 1
                    msg.warn(f"  ⏱️ Search #{iteration}: timeout")
                except Exception as e:
                    self._stats["failed_searches"] += 1
                    msg.warn(f"  ❌ Search #{iteration}: erro - {str(e)[:50]}")
            
            # Sempre emitir o token original
            yield result
        
        # Registrar estatísticas
        if searches_done:
            self._stats["generations_with_search"] += 1
            msg.info(f"  📊 Iterative Search: {len(searches_done)} buscas realizadas")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do plugin."""
        return self._stats.copy()
    
    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            "total_generations": 0,
            "generations_with_search": 0,
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "timeouts": 0
        }


# Prompt template para instruir o modelo a usar [SEARCH:]
ITERATIVE_SEARCH_SYSTEM_PROMPT = """
You have the ability to search for additional information during your response.
When you need more specific information that is not in the provided context, 
you can use the special token [SEARCH: your query here] to trigger a search.

Example:
"Based on the context, Apple's revenue in 2023 was strong. [SEARCH: Apple revenue 2024] 
However, I need to verify the 2024 figures..."

Rules:
1. Only use [SEARCH:] when the context is insufficient
2. Keep search queries concise and specific
3. Maximum 3 searches per response
4. Continue your response after the search token
"""


def create_iterative_search_plugin(
    enabled: bool = False,
    max_iterations: int = 3
) -> IterativeSearchPlugin:
    """
    Factory para criar plugin configurado.
    
    Args:
        enabled: Se o plugin está habilitado
        max_iterations: Máximo de buscas por geração
        
    Returns:
        IterativeSearchPlugin configurado
    """
    config = IterativeSearchConfig(
        enabled=enabled,
        max_iterations=max_iterations
    )
    return IterativeSearchPlugin(config)


# Singleton global
_global_plugin: Optional[IterativeSearchPlugin] = None


def get_iterative_search_plugin() -> IterativeSearchPlugin:
    """Retorna instância singleton do plugin."""
    global _global_plugin
    if _global_plugin is None:
        _global_plugin = IterativeSearchPlugin()
    return _global_plugin


def enable_iterative_search(max_iterations: int = 3):
    """Habilita busca iterativa globalmente."""
    plugin = get_iterative_search_plugin()
    plugin.config.enabled = True
    plugin.config.max_iterations = max_iterations
    msg.info(f"  Iterative Search habilitado (max={max_iterations})")


def disable_iterative_search():
    """Desabilita busca iterativa globalmente."""
    plugin = get_iterative_search_plugin()
    plugin.config.enabled = False
    msg.info("  Iterative Search desabilitado")



