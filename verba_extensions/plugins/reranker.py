"""
Reranker Plugin for Verba

Reranking inteligente de chunks usando cross-encoders ou LLM scoring.
Melhora relevância dos resultados finais antes de enviar para LLM.
"""

import logging
from typing import List, Dict, Any, Optional
from goldenverba.components.chunk import Chunk

logger = logging.getLogger(__name__)


class RerankerPlugin:
    """
    Plugin para reranking de chunks usando múltiplas estratégias.
    
    Estratégias disponíveis:
    1. Metadata-based scoring (usa enriched metadata)
    2. Cross-encoder scoring (requer modelo)
    3. LLM-based scoring (requer API)
    """
    
    def __init__(self):
        self.name = "Reranker"
        self.description = "Reranking inteligente de chunks para melhor relevância"
        self.installed = True
        
        # Configuração padrão
        self.default_top_k = 5
        self.use_metadata = True
        self.use_cross_encoder = False  # Requer modelo instalado
        self.use_llm_scoring = False  # Requer API key
        
    async def process_chunk(
        self,
        chunk,
        config = None
    ):
        """
        Processa um único chunk (compatibilidade com plugin system).
        Como reranking requer contexto de múltiplos chunks, apenas retorna o chunk.
        
        Args:
            chunk: Chunk a processar
            config: Configuração opcional
        
        Returns:
            Chunk processado (sem alteração para chunk individual)
        """
        # Reranking é melhor feito em batch, então apenas retorna o chunk
        return chunk
    
    async def process_batch(
        self,
        chunks,
        config = None
    ):
        """
        Processa múltiplos chunks em batch (reranking).
        
        Args:
            chunks: Lista de chunks a rerankear
            config: Configuração opcional (pode incluir 'query')
        
        Returns:
            Chunks rerankeados (ordenados por relevância)
        """
        # Extrai query da configuração se disponível
        query = ""
        if config and isinstance(config, dict):
            query = config.get("query", "")
        
        # Se não houver query, apenas retorna chunks na ordem original
        if not query:
            logger.debug("No query provided for reranking, returning chunks unchanged")
            return chunks
        
        return await self.process_chunks(chunks, query, config)
    
    async def process_chunks(
        self,
        chunks: List[Chunk],
        query: str,
        config: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Reranks chunks baseado em query e metadata.
        
        Args:
            chunks: Lista de chunks a rerankear
            query: Query do usuário
            config: Configuração opcional
        
        Returns:
            Chunks rerankeados (ordenados por relevância)
        """
        if not chunks:
            return chunks
        
        config = config or {}
        top_k = config.get("top_k", self.default_top_k)
        
        # Log para debug
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"RERANKER: Recebeu {len(chunks)} chunks, top_k={top_k} (default={self.default_top_k})")
        
        # Calcula scores para cada chunk
        scored_chunks = []
        for chunk in chunks:
            score = await self._calculate_relevance_score(chunk, query, config)
            scored_chunks.append((score, chunk))
        
        # Ordena por score (maior primeiro)
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Retorna top_k chunks
        reranked = [chunk for _, chunk in scored_chunks[:top_k]]
        
        logger.info(f"RERANKER: Retornando {len(reranked)} chunks de {len(chunks)} (top_k={top_k})")
        if len(reranked) < top_k and len(chunks) >= top_k:
            logger.warning(f"RERANKER: ATENÇÃO - Retornou apenas {len(reranked)} chunks quando deveria retornar {top_k}!")
        
        return reranked
    
    async def _calculate_relevance_score(
        self,
        chunk: Chunk,
        query: str,
        config: Dict[str, Any]
    ) -> float:
        """
        Calcula score de relevância para um chunk.
        
        Args:
            chunk: Chunk a scorear
            query: Query do usuário
            config: Configuração
        
        Returns:
            Score de relevância (0.0 a 1.0)
        """
        scores = []
        
        # 1. Metadata-based scoring
        if self.use_metadata and chunk.meta:
            metadata_score = self._score_by_metadata(chunk, query)
            scores.append(metadata_score * 0.4)  # 40% weight
        
        # 2. Keyword matching
        keyword_score = self._score_by_keywords(chunk.content, query)
        scores.append(keyword_score * 0.3)  # 30% weight
        
        # 3. Content length score (prefer chunks médios)
        length_score = self._score_by_length(len(chunk.content))
        scores.append(length_score * 0.1)  # 10% weight
        
        # 4. Cross-encoder scoring (se disponível)
        if self.use_cross_encoder:
            try:
                cross_score = await self._score_cross_encoder(chunk.content, query)
                scores.append(cross_score * 0.2)  # 20% weight
            except Exception as e:
                logger.debug(f"Cross-encoder scoring failed: {e}")
        
        # 5. LLM scoring (se disponível)
        if self.use_llm_scoring:
            try:
                llm_score = await self._score_llm(chunk, query)
                scores.append(llm_score * 0.3)  # 30% weight
            except Exception as e:
                logger.debug(f"LLM scoring failed: {e}")
        
        # Média ponderada dos scores
        if scores:
            return sum(scores) / len(scores)
        return 0.5  # Score neutro
    
    def _score_by_metadata(
        self,
        chunk: Chunk,
        query: str
    ) -> float:
        """
        Calcula score baseado em metadata enriquecido.
        
        Args:
            chunk: Chunk com metadata
            query: Query do usuário
        
        Returns:
            Score baseado em metadata (0.0 a 1.0)
        """
        if not chunk.meta or "enriched" not in chunk.meta:
            return 0.5  # Score neutro
        
        enriched = chunk.meta.get("enriched", {})
        query_lower = query.lower()
        score = 0.0
        
        # Match com empresas mencionadas
        companies = enriched.get("companies", [])
        for company in companies:
            if company.lower() in query_lower:
                score += 0.3
        
        # Match com tópicos
        topics = enriched.get("key_topics", [])
        for topic in topics:
            if topic.lower() in query_lower:
                score += 0.2
        
        # Match com keywords
        keywords = enriched.get("keywords", [])
        matched_keywords = sum(1 for kw in keywords if kw.lower() in query_lower)
        if keywords:
            score += (matched_keywords / len(keywords)) * 0.2
        
        # Confidence score do enriched metadata
        confidence = enriched.get("confidence_score", 0.8)
        score += confidence * 0.3
        
        return min(score, 1.0)  # Cap em 1.0
    
    def _score_by_keywords(
        self,
        content: str,
        query: str
    ) -> float:
        """
        Calcula score baseado em matching de keywords.
        
        Args:
            content: Conteúdo do chunk
            query: Query do usuário
        
        Returns:
            Score de keyword matching (0.0 a 1.0)
        """
        if not content or not query:
            return 0.0
        
        content_lower = content.lower()
        query_words = query.lower().split()
        
        # Remove stopwords simples
        stopwords = {'a', 'o', 'e', 'de', 'da', 'do', 'em', 'para', 'com', 'que', 'é', 'um', 'uma'}
        query_words = [w for w in query_words if w not in stopwords]
        
        if not query_words:
            return 0.5
        
        # Conta matches
        matches = sum(1 for word in query_words if word in content_lower)
        
        # Score proporcional ao número de matches
        return min(matches / len(query_words), 1.0)
    
    def _score_by_length(self, length: int) -> float:
        """
        Calcula score baseado no tamanho do chunk.
        
        Prefere chunks médios (não muito pequenos, não muito grandes).
        
        Args:
            length: Tamanho do chunk em caracteres
        
        Returns:
            Score de tamanho (0.0 a 1.0)
        """
        # Ideal: 500-1500 caracteres
        ideal_min = 500
        ideal_max = 1500
        
        if ideal_min <= length <= ideal_max:
            return 1.0
        elif length < ideal_min:
            # Penaliza chunks muito pequenos
            return length / ideal_min * 0.5
        else:
            # Penaliza chunks muito grandes
            if length > ideal_max * 2:
                return 0.3
            return 1.0 - ((length - ideal_max) / ideal_max) * 0.5
    
    async def _score_cross_encoder(
        self,
        content: str,
        query: str
    ) -> float:
        """
        Calcula score usando cross-encoder (requer modelo).
        
        Args:
            content: Conteúdo do chunk
            query: Query do usuário
        
        Returns:
            Score do cross-encoder (0.0 a 1.0)
        """
        # TODO: Implementar com sentence-transformers cross-encoder
        # Por enquanto retorna score neutro
        return 0.5
    
    async def _score_llm(
        self,
        chunk: Chunk,
        query: str
    ) -> float:
        """
        Calcula score usando LLM (requer API).
        
        Args:
            chunk: Chunk a scorear
            query: Query do usuário
        
        Returns:
            Score do LLM (0.0 a 1.0)
        """
        # TODO: Implementar com AnthropicGenerator
        # Por enquanto retorna score neutro
        return 0.5
    
    def get_config(self) -> Dict[str, Any]:
        """Retorna configuração do plugin."""
        return {
            "name": self.name,
            "description": self.description,
            "default_top_k": self.default_top_k,
            "use_metadata": self.use_metadata,
            "use_cross_encoder": self.use_cross_encoder,
            "use_llm_scoring": self.use_llm_scoring
        }
    
    def install(self) -> bool:
        """Instala o plugin."""
        self.installed = True
        logger.info("Reranker instalado")
        return True
    
    def uninstall(self) -> bool:
        """Desinstala o plugin."""
        self.installed = False
        logger.info("Reranker desinstalado")
        return True


def create_reranker() -> RerankerPlugin:
    """Factory para criar instância do plugin."""
    return RerankerPlugin()

