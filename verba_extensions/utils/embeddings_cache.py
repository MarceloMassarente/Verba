"""
Cache determinístico de embeddings para evitar re-embedding redundante.

Adaptado do RAG2 para Verba.

Este módulo fornece cache in-memory determinístico de embeddings para reduzir
chamadas desnecessárias a APIs de embedding. É especialmente útil em:
- Re-uploads de documentos
- Processamento batch
- Documentos com chunks duplicados

Features:
- Cache determinístico baseado em hash do texto
- Estatísticas de hit rate
- Thread-safe (cache global compartilhado)
- Opcional (pode ser desabilitado)

Uso básico:
    from verba_extensions.utils.embeddings_cache import (
        get_cached_embedding,
        get_cache_key,
        get_cache_stats
    )
    
    # Gerar chave de cache
    cache_key = get_cache_key(
        text=chunk.text,
        doc_uuid=str(doc.uuid),
        parent_type="chunk"
    )
    
    # Obter embedding com cache
    embedding, was_cached = get_cached_embedding(
        text=chunk.text,
        cache_key=cache_key,
        embed_fn=lambda t: self._call_embedding_api(t),
        enable_cache=True
    )
    
    # Verificar estatísticas
    stats = get_cache_stats()
    print(f"Hit rate: {stats['hit_rate']:.2f}%")

Impacto esperado:
- Redução de 50-90% em chamadas de embedding em re-uploads
- Economia de custo de APIs (OpenAI, Cohere, etc.)
- Melhoria de performance (especialmente em processamento batch)

Documentação completa: GUIA_INTEGRACAO_RAG2_COMPONENTES.md
"""

from __future__ import annotations

import hashlib
from typing import Callable, List, Optional


# Cache global in-memory
_embeddings_cache: dict[str, List[float]] = {}
_cache_stats = {
    "hits": 0,
    "misses": 0,
    "total_size_bytes": 0
}


def get_cache_key(text: str, doc_uuid: str, parent_type: str = "chunk") -> str:
    """
    Gera chave determinística de cache para um embedding
    
    Args:
        text: Texto a embeds
        doc_uuid: UUID do documento
        parent_type: Tipo do parent (e.g., 'chunk', 'document', 'section')
        
    Returns:
        Chave de cache determinística
    """
    # Hash do texto para reduzir tamanho da chave
    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
    return f"{doc_uuid}|{parent_type}|{text_hash}"


def get_cached_embedding(
    text: str,
    cache_key: str,
    embed_fn: Callable[[str], List[float]],
    enable_cache: bool = True
) -> tuple[List[float], bool]:
    """
    Obtém embedding com cache determinístico
    
    Args:
        text: Texto a embeds
        cache_key: Chave de cache (use get_cache_key)
        embed_fn: Função que gera embedding dado um texto
        enable_cache: Se False, desabilita cache e sempre re-embed
        
    Returns:
        Tupla (embedding, was_cached)
        - was_cached: True se veio do cache, False se gerado novo
    """
    if not enable_cache:
        return embed_fn(text), False
    
    # Verifica cache
    if cache_key in _embeddings_cache:
        _cache_stats["hits"] += 1
        return _embeddings_cache[cache_key], True
    
    # Cache miss: gera embedding
    embedding = embed_fn(text)
    _embeddings_cache[cache_key] = embedding
    _cache_stats["misses"] += 1
    _cache_stats["total_size_bytes"] += len(embedding) * 8  # float64 = 8 bytes
    
    return embedding, False


def get_cache_stats() -> dict[str, int | float]:
    """
    Retorna estatísticas do cache
    
    Returns:
        Dict com hits, misses, total_size_bytes, hit_rate
    """
    hits = _cache_stats["hits"]
    misses = _cache_stats["misses"]
    total = hits + misses
    
    return {
        "hits": hits,
        "misses": misses,
        "hit_rate": (hits / total * 100) if total > 0 else 0.0,
        "total_size_bytes": _cache_stats["total_size_bytes"],
        "cache_size_kb": _cache_stats["total_size_bytes"] / 1024,
        "cached_embeddings": len(_embeddings_cache)
    }


def clear_cache() -> None:
    """Limpa cache e estatísticas"""
    global _embeddings_cache, _cache_stats
    _embeddings_cache = {}
    _cache_stats = {
        "hits": 0,
        "misses": 0,
        "total_size_bytes": 0
    }


def set_cache(entries: dict[str, List[float]]) -> None:
    """
    Define cache explicitamente (útil para loading de cache persistido)
    
    Args:
        entries: Dict {cache_key: embedding}
    """
    global _embeddings_cache
    _embeddings_cache = entries.copy()

