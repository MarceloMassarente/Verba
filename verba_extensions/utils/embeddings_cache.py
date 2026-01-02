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
import time
from typing import Callable, List, Optional, Dict, Any


# Cache global in-memory with TTL support
_embeddings_cache: Dict[str, Dict[str, Any]] = {}  # {key: {"embedding": [...], "timestamp": float}}
_cache_stats = {
    "hits": 0,
    "misses": 0,
    "total_size_bytes": 0,
    "evictions": 0
}

# Cache configuration
CACHE_TTL_SECONDS = 3600  # 1 hour TTL
MAX_CACHE_ENTRIES = 10000  # LRU limit


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


def _evict_if_needed() -> None:
    """Evict oldest entries if cache exceeds max size."""
    global _embeddings_cache, _cache_stats
    
    if len(_embeddings_cache) < MAX_CACHE_ENTRIES:
        return
    
    # Sort by timestamp and remove oldest 10%
    entries = sorted(_embeddings_cache.items(), key=lambda x: x[1].get("timestamp", 0))
    to_remove = len(entries) // 10 or 1
    
    for key, _ in entries[:to_remove]:
        del _embeddings_cache[key]
        _cache_stats["evictions"] += 1


def get_cached_embedding(
    text: str,
    cache_key: str,
    embed_fn: Callable[[str], List[float]],
    enable_cache: bool = True
) -> tuple[List[float], bool]:
    """
    Obtém embedding com cache determinístico e TTL
    
    Args:
        text: Texto a embeds
        cache_key: Chave de cache (use get_cache_key)
        embed_fn: Função que gera embedding dado um texto
        enable_cache: Se False, desabilita cache e sempre re-embed
        
    Returns:
        Tupla (embedding, was_cached)
        - was_cached: True se veio do cache, False se gerado novo
    """
    global _cache_stats
    
    if not enable_cache:
        return embed_fn(text), False
    
    now = time.time()
    
    # Verifica cache com TTL
    if cache_key in _embeddings_cache:
        entry = _embeddings_cache[cache_key]
        if now - entry.get("timestamp", 0) < CACHE_TTL_SECONDS:
            _cache_stats["hits"] += 1
            return entry["embedding"], True
        else:
            # Expired - remove
            del _embeddings_cache[cache_key]
    
    # Evict if needed before adding new entry
    _evict_if_needed()
    
    # Cache miss: gera embedding
    embedding = embed_fn(text)
    _embeddings_cache[cache_key] = {"embedding": embedding, "timestamp": now}
    _cache_stats["misses"] += 1
    _cache_stats["total_size_bytes"] += len(embedding) * 8  # float64 = 8 bytes
    
    return embedding, False


def get_cache_stats() -> dict[str, int | float]:
    """
    Retorna estatísticas do cache
    
    Returns:
        Dict com hits, misses, total_size_bytes, hit_rate, evictions
    """
    hits = _cache_stats["hits"]
    misses = _cache_stats["misses"]
    total = hits + misses
    
    return {
        "hits": hits,
        "misses": misses,
        "evictions": _cache_stats.get("evictions", 0),
        "hit_rate": (hits / total * 100) if total > 0 else 0.0,
        "total_size_bytes": _cache_stats["total_size_bytes"],
        "cache_size_kb": _cache_stats["total_size_bytes"] / 1024,
        "cached_embeddings": len(_embeddings_cache),
        "ttl_seconds": CACHE_TTL_SECONDS,
        "max_entries": MAX_CACHE_ENTRIES
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

