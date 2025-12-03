"""
RAG 2.0 Enhancement: Intelligent Cache with Similarity Search

Este plugin implementa cache inteligente que:
1. Reutiliza respostas de queries SIMILARES (não apenas idênticas)
2. Usa TTL adaptativo baseado no tipo de documento
3. Economiza chamadas ao LLM e melhora latência

Exemplo:
- Query 1: "O que é inovação da Apple?"
- Query 2: "Qual é a inovação da Apple?"  
- Similaridade: 0.92 → Cache hit! Reutiliza resposta da Query 1
"""

import time
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from wasabi import msg


@dataclass
class CacheEntry:
    """Entrada do cache com metadados."""
    query: str
    query_embedding: Optional[List[float]]
    response: Dict[str, Any]
    doc_type: str
    created_at: float
    ttl_seconds: float
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Verifica se entrada expirou."""
        return time.time() > (self.created_at + self.ttl_seconds)
    
    def touch(self):
        """Incrementa contador de hits."""
        self.hit_count += 1


class IntelligentCache:
    """
    Cache inteligente com busca por similaridade.
    
    Features:
    - Busca por similaridade semântica (não apenas match exato)
    - TTL adaptativo por tipo de documento
    - Estatísticas de uso
    - Limpeza automática de entradas expiradas
    """
    
    # TTL padrão por tipo de documento (em segundos)
    DEFAULT_TTL_MAP = {
        "whitepaper": 30 * 24 * 3600,  # 30 dias
        "report": 14 * 24 * 3600,       # 14 dias
        "article": 7 * 24 * 3600,       # 7 dias
        "news": 1 * 24 * 3600,          # 1 dia
        "general": 7 * 24 * 3600,       # 7 dias (default)
    }
    
    def __init__(
        self,
        similarity_threshold: float = 0.85,
        max_entries: int = 1000,
        ttl_map: Optional[Dict[str, int]] = None,
        embedder_func: Optional[callable] = None
    ):
        """
        Inicializa cache inteligente.
        
        Args:
            similarity_threshold: Threshold de similaridade para cache hit (0-1)
            max_entries: Número máximo de entradas no cache
            ttl_map: Mapa de TTL por tipo de documento
            embedder_func: Função para gerar embeddings (async)
        """
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.ttl_map = ttl_map or self.DEFAULT_TTL_MAP.copy()
        self.embedder_func = embedder_func
        
        # Cache storage
        self._cache: Dict[str, CacheEntry] = {}
        
        # Estatísticas
        self._stats = {
            "hits": 0,
            "misses": 0,
            "similarity_hits": 0,
            "exact_hits": 0,
            "evictions": 0
        }
    
    def _compute_hash(self, query: str) -> str:
        """Computa hash da query para lookup rápido."""
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcula similaridade cosseno entre dois vetores."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _get_ttl(self, doc_type: str) -> float:
        """Retorna TTL para o tipo de documento."""
        return self.ttl_map.get(doc_type, self.ttl_map.get("general", 7 * 24 * 3600))
    
    def _cleanup_expired(self):
        """Remove entradas expiradas."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._cache[key]
            self._stats["evictions"] += 1
        
        if expired_keys:
            msg.info(f"  Cache: removidas {len(expired_keys)} entradas expiradas")
    
    def _evict_if_needed(self):
        """Evicta entradas se cache estiver cheio (LRU-like)."""
        if len(self._cache) >= self.max_entries:
            # Ordenar por hit_count (menos usado primeiro) e created_at (mais antigo primeiro)
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: (x[1].hit_count, -x[1].created_at)
            )
            
            # Remover 10% das entradas menos usadas
            to_remove = max(1, len(self._cache) // 10)
            for key, _ in sorted_entries[:to_remove]:
                del self._cache[key]
                self._stats["evictions"] += 1
    
    async def get(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Busca no cache por query exata ou similar.
        
        Args:
            query: Query do usuário
            query_embedding: Embedding da query (opcional, para busca por similaridade)
            
        Returns:
            Tuple[Optional[Dict], Dict]: (cached_response ou None, debug_info)
        """
        # Limpar expirados periodicamente
        if len(self._cache) > 0 and len(self._cache) % 100 == 0:
            self._cleanup_expired()
        
        debug_info = {
            "cache_size": len(self._cache),
            "query_hash": self._compute_hash(query),
            "hit_type": None,
            "similarity": None
        }
        
        # 1. Tentar match exato primeiro (mais rápido)
        query_hash = self._compute_hash(query)
        if query_hash in self._cache:
            entry = self._cache[query_hash]
            if not entry.is_expired():
                entry.touch()
                self._stats["hits"] += 1
                self._stats["exact_hits"] += 1
                debug_info["hit_type"] = "exact"
                msg.info(f"  Cache: HIT exato (hits={entry.hit_count})")
                return entry.response, debug_info
        
        # 2. Buscar por similaridade se temos embedding
        if query_embedding and len(self._cache) > 0:
            best_match = None
            best_similarity = 0.0
            
            for key, entry in self._cache.items():
                if entry.is_expired():
                    continue
                if entry.query_embedding is None:
                    continue
                
                similarity = self._cosine_similarity(query_embedding, entry.query_embedding)
                
                if similarity > best_similarity and similarity >= self.similarity_threshold:
                    best_similarity = similarity
                    best_match = entry
            
            if best_match:
                best_match.touch()
                self._stats["hits"] += 1
                self._stats["similarity_hits"] += 1
                debug_info["hit_type"] = "similarity"
                debug_info["similarity"] = round(best_similarity, 3)
                msg.info(f"  Cache: HIT por similaridade ({best_similarity:.3f})")
                return best_match.response, debug_info
        
        # Cache miss
        self._stats["misses"] += 1
        debug_info["hit_type"] = "miss"
        return None, debug_info
    
    async def set(
        self,
        query: str,
        response: Dict[str, Any],
        doc_type: str = "general",
        query_embedding: Optional[List[float]] = None
    ):
        """
        Armazena resposta no cache.
        
        Args:
            query: Query original
            response: Resposta a ser cacheada
            doc_type: Tipo de documento (para TTL)
            query_embedding: Embedding da query (para busca por similaridade)
        """
        # Evictar se necessário
        self._evict_if_needed()
        
        query_hash = self._compute_hash(query)
        ttl = self._get_ttl(doc_type)
        
        entry = CacheEntry(
            query=query,
            query_embedding=query_embedding,
            response=response,
            doc_type=doc_type,
            created_at=time.time(),
            ttl_seconds=ttl
        )
        
        self._cache[query_hash] = entry
        msg.info(f"  Cache: SET (type={doc_type}, ttl={ttl/3600:.1f}h)")
    
    def invalidate(self, query: str):
        """Invalida entrada específica do cache."""
        query_hash = self._compute_hash(query)
        if query_hash in self._cache:
            del self._cache[query_hash]
            msg.info(f"  Cache: invalidada entrada")
    
    def clear(self):
        """Limpa todo o cache."""
        count = len(self._cache)
        self._cache.clear()
        msg.info(f"  Cache: limpo ({count} entradas removidas)")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            "total_entries": len(self._cache),
            "max_entries": self.max_entries,
            "total_requests": total_requests,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "exact_hits": self._stats["exact_hits"],
            "similarity_hits": self._stats["similarity_hits"],
            "evictions": self._stats["evictions"],
            "hit_rate": round(hit_rate, 3),
            "similarity_threshold": self.similarity_threshold
        }


# Singleton global
_global_cache: Optional[IntelligentCache] = None


def get_cache(
    similarity_threshold: float = 0.85,
    max_entries: int = 1000
) -> IntelligentCache:
    """
    Retorna instância singleton do cache.
    
    Args:
        similarity_threshold: Threshold de similaridade
        max_entries: Máximo de entradas
        
    Returns:
        IntelligentCache: Instância do cache
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = IntelligentCache(
            similarity_threshold=similarity_threshold,
            max_entries=max_entries
        )
    return _global_cache


def reset_cache():
    """Reseta o cache global."""
    global _global_cache
    if _global_cache:
        _global_cache.clear()
    _global_cache = None



