"""
Reranker Plugin for Verba - Multi-Provider Support

Reranking inteligente de chunks usando múltiplos providers:
- Metadata-based (sempre disponível)
- Haystack CrossEncoderRanker (local)
- Cohere Rerank API
- Jina Rerank API
- VoyageAI Rerank API
- Contextual AI Rerank API (com instruções customizadas)

Suporta combinação de múltiplas estratégias (Cascade, Parallel, Hybrid).
"""

import logging
import asyncio
import os
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod
from goldenverba.components.chunk import Chunk
from goldenverba.components.types import InputConfig
from goldenverba.components.util import get_environment, get_token

logger = logging.getLogger(__name__)


# ============================================================================
# BASE CLASSES
# ============================================================================

class BaseReranker(ABC):
    """Classe base abstrata para todos os rerankers."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.available = False
    
    @abstractmethod
    async def rerank(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int
    ) -> List[Chunk]:
        """
        Reranks chunks baseado em query.
        
        Args:
            chunks: Lista de chunks a rerankear
            query: Query do usuário
            top_k: Número de chunks a retornar
        
        Returns:
            Chunks rerankeados (ordenados por relevância)
        """
        pass
    
    def _normalize_score(self, score: float) -> float:
        """Normaliza score para 0.0 a 1.0."""
        return max(0.0, min(1.0, score))
    
    def _chunk_to_dict(self, chunk: Chunk) -> Dict[str, Any]:
        """Converte Chunk para dict para facilitar manipulação."""
        return {
            "chunk": chunk,
            "content": chunk.content,
            "score": 0.0,
            "original_index": None
        }


# ============================================================================
# METADATA RERANKER (sempre disponível)
# ============================================================================

class MetadataReranker(BaseReranker):
    """Reranker baseado em metadata enriquecido e keywords."""
    
    def __init__(self):
        super().__init__("Metadata", "Reranking baseado em metadata e keywords")
        self.available = True
    
    async def rerank(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int
    ) -> List[Chunk]:
        """Reranks chunks usando metadata e keywords."""
        if not chunks or not query:
            return chunks[:top_k]
        
        # Calcula scores para cada chunk
        scored_chunks = []
        for chunk in chunks:
            score = self._calculate_score(chunk, query)
            scored_chunks.append((score, chunk))
        
        # Ordena por score (maior primeiro)
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Retorna top_k chunks
        return [chunk for _, chunk in scored_chunks[:top_k]]
    
    def _calculate_score(self, chunk: Chunk, query: str) -> float:
        """Calcula score combinado de metadata, keywords e length."""
        scores = []
        
        # 1. Metadata-based scoring (40% weight)
        metadata_score = self._score_by_metadata(chunk, query)
        scores.append(metadata_score * 0.4)
        
        # 2. Keyword matching (30% weight)
        keyword_score = self._score_by_keywords(chunk.content, query)
        scores.append(keyword_score * 0.3)
        
        # 3. Content length score (10% weight)
        length_score = self._score_by_length(len(chunk.content))
        scores.append(length_score * 0.1)
        
        # Média ponderada
        return sum(scores) if scores else 0.5
    
    def _score_by_metadata(self, chunk: Chunk, query: str) -> float:
        """Calcula score baseado em metadata enriquecido e propriedades V019."""
        query_lower = query.lower()
        score = 0.0
        has_metadata = False
        
        # 1. Metadata enriquecido tradicional (enriched)
        if chunk.meta and "enriched" in chunk.meta:
            has_metadata = True
            enriched = chunk.meta.get("enriched", {})
            
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
            score += confidence * 0.2  # Reduzido de 0.3 para dar espaço para V019
        
        # 2. Propriedades V019 (se disponíveis)
        # Verifica tanto em chunk.meta (se foram copiadas) quanto diretamente
        v019_score = 0.0
        v019_weight = 0.3  # Peso para propriedades V019
        
        # Extrai propriedades V019 do chunk.meta (se disponível)
        slide_position = None
        slide_type = None
        pattern_genetics = []
        reusability_score = None
        visual_archetype = None
        semantic_bridge_quality = None
        
        if chunk.meta:
            slide_position = chunk.meta.get("slide_position")
            slide_type = chunk.meta.get("slide_type")
            pattern_genetics = chunk.meta.get("pattern_genetics", [])
            reusability_score = chunk.meta.get("reusability_score")
            visual_archetype = chunk.meta.get("visual_archetype")
            semantic_bridge_quality = chunk.meta.get("semantic_bridge_quality")
        
        # Se não encontrou em chunk.meta, tenta extrair de slides_metadata
        if not any([slide_position, slide_type, pattern_genetics, reusability_score, visual_archetype, semantic_bridge_quality]):
            if chunk.meta and "slides_metadata" in chunk.meta:
                slides_metadata = chunk.meta.get("slides_metadata", [])
                if slides_metadata and len(slides_metadata) > 0:
                    first_slide = slides_metadata[0]
                    slide_position = first_slide.get("slide_position")
                    slide_type = first_slide.get("slide_type")
                    pattern_genetics = first_slide.get("pattern_genetics", [])
                    reusability_score = first_slide.get("reusability_score")
                    visual_archetype = first_slide.get("visual_archetype")
                    semantic_bridge_quality = first_slide.get("semantic_bridge_quality")
        
        # Score V019 baseado em matches com a query
        if slide_position:
            # Match com posições do deck
            position_keywords = ["opening", "diagnostic", "analysis", "closing", "abertura", "diagnóstico", "análise", "conclusão"]
            if any(kw in query_lower and slide_position.lower() == kw for kw in position_keywords):
                v019_score += 0.2
                has_metadata = True
        
        if slide_type:
            # Match com tipos de slide
            type_keywords = ["complex", "simple", "metadata", "complexo", "simples"]
            if any(kw in query_lower and slide_type.lower() == kw for kw in type_keywords):
                v019_score += 0.15
                has_metadata = True
        
        if pattern_genetics:
            # Match com pattern genetics
            for pattern in pattern_genetics:
                if isinstance(pattern, str) and pattern.lower() in query_lower:
                    v019_score += 0.2
                    has_metadata = True
                    break
        
        if visual_archetype:
            # Match com arquétipos visuais
            archetype_keywords = ["pyramid", "matrix", "flow", "pirâmide", "matriz", "fluxo"]
            if any(kw in query_lower and visual_archetype.lower() == kw for kw in archetype_keywords):
                v019_score += 0.15
                has_metadata = True
        
        # Boost por qualidade semântica (se alta qualidade)
        if semantic_bridge_quality is not None and semantic_bridge_quality > 0.8:
            v019_score += 0.1
            has_metadata = True
        
        # Boost por alta reusabilidade (se relevante para a query)
        if reusability_score is not None and reusability_score > 80:
            # Se query menciona "reusável", "reutilizável", "template", etc.
            reusability_keywords = ["reus", "reutiliz", "template", "pattern", "padrão"]
            if any(kw in query_lower for kw in reusability_keywords):
                v019_score += 0.15
                has_metadata = True
        
        # Adiciona score V019 ao score total
        score += v019_score * v019_weight
        
        # Se não encontrou nenhum metadata, retorna score neutro
        if not has_metadata:
            return 0.5
        
        return self._normalize_score(score)
    
    def _score_by_keywords(self, content: str, query: str) -> float:
        """Calcula score baseado em matching de keywords."""
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
        """Calcula score baseado no tamanho do chunk (prefere médios)."""
        ideal_min = 500
        ideal_max = 1500
        
        if ideal_min <= length <= ideal_max:
            return 1.0
        elif length < ideal_min:
            return length / ideal_min * 0.5
        else:
            if length > ideal_max * 2:
                return 0.3
            return 1.0 - ((length - ideal_max) / ideal_max) * 0.5


# ============================================================================
# HAYSTACK RERANKER
# ============================================================================

class HaystackReranker(BaseReranker):
    """Reranker usando Haystack CrossEncoderRanker."""
    
    def __init__(self, model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        super().__init__("Haystack", "Reranking usando Haystack CrossEncoderRanker")
        self.model = model
        self.ranker = None
        self._initialize()
    
    def _initialize(self):
        """Inicializa o Haystack reranker se disponível."""
        try:
            from haystack.components.rankers import CrossEncoderRanker
            from haystack.dataclasses import Document
            
            self.ranker = CrossEncoderRanker(model=self.model)
            self.available = True
            logger.info(f"HaystackReranker inicializado com modelo: {self.model}")
        except ImportError:
            logger.debug("Haystack não disponível (haystack-ai não instalado)")
            self.available = False
        except Exception as e:
            logger.warning(f"Erro ao inicializar HaystackReranker: {e}")
            self.available = False
    
    async def rerank(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int
    ) -> List[Chunk]:
        """Reranks chunks usando Haystack CrossEncoderRanker."""
        if not self.available or not chunks or not query:
            return chunks[:top_k]
        
        try:
            from haystack.dataclasses import Document
            
            # Converte chunks para formato Haystack
            haystack_docs = []
            for chunk in chunks:
                doc = Document(
                    content=chunk.content,
                    meta={
                        "chunk_id": chunk.chunk_id,
                        "doc_uuid": chunk.doc_uuid,
                        "uuid": chunk.uuid,
                    }
                )
                haystack_docs.append(doc)
            
            # Reranking com Haystack
            result = self.ranker.run(query=query, documents=haystack_docs, top_k=top_k)
            reranked_docs = result.get("documents", [])
            
            # Converte de volta para Chunk objects
            chunk_map = {chunk.uuid or id(chunk): chunk for chunk in chunks}
            reranked_chunks = []
            
            for doc in reranked_docs:
                chunk_uuid = doc.meta.get("uuid")
                if chunk_uuid and chunk_uuid in chunk_map:
                    reranked_chunks.append(chunk_map[chunk_uuid])
                else:
                    # Fallback: busca por conteúdo
                    for chunk in chunks:
                        if chunk.content == doc.content:
                            reranked_chunks.append(chunk)
                            break
            
            logger.info(f"HaystackReranker rerankou {len(reranked_chunks)} chunks")
            return reranked_chunks[:top_k]
            
        except Exception as e:
            logger.error(f"Erro ao rerankear com Haystack: {e}")
            return chunks[:top_k]


# ============================================================================
# COHERE RERANKER
# ============================================================================

class CohereReranker(BaseReranker):
    """Reranker usando Cohere Rerank API."""
    
    def __init__(self):
        super().__init__("Cohere", "Reranking usando Cohere Rerank API")
        self.url = os.getenv("COHERE_BASE_URL", "https://api.cohere.com/v1")
        self.api_key = get_token("COHERE_API_KEY", None)
        self.available = self.api_key is not None
        self.default_model = "rerank-english-v3.0"
    
    async def rerank(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> List[Chunk]:
        """Reranks chunks usando Cohere Rerank API."""
        if not chunks or not query:
            return chunks[:top_k]
        
        model = model or self.default_model
        # Prioriza API key do parâmetro, depois do config, depois da env var
        api_key = api_key or self.api_key
        base_url = base_url or self.url
        
        if not api_key:
            logger.warning("Cohere API key não configurada")
            return chunks[:top_k]
        
        try:
            import aiohttp
            import json
            from verba_extensions.utils.retry import retry_with_backoff
            
            # Cohere aceita até 100 documentos por request
            batch_size = 100
            all_results = []
            
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]
                
                # Prepara dados para API
                texts = [chunk.content for chunk in batch_chunks]
                
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    }
                    
                    data = {
                        "model": model,
                        "query": query,
                        "documents": texts,
                        "top_n": min(top_k, len(batch_chunks)),
                    }
                    
                    # Função interna para fazer requisição com retry
                    async def make_request():
                        async with session.post(
                            f"{base_url}/rerank",
                            headers=headers,
                            json=data
                        ) as response:
                            response.raise_for_status()
                            return await response.json()
                    
                    # Executa com retry
                    result = await retry_with_backoff(
                        make_request,
                        max_retries=3,
                        base_delay=1.0,
                        retryable_status_codes=[429, 500, 502, 503, 504],
                        operation_name=f"Cohere Rerank API (batch {i//batch_size + 1})"
                    )
                    
                    # Cohere retorna resultados com índices e scores
                    reranked_indices = result.get("results", [])
                    
                    # Ordena por score (maior primeiro)
                    reranked_indices.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
                    
                    # Mapeia de volta para chunks
                    for item in reranked_indices[:top_k]:
                        index = item.get("index", 0)
                        if 0 <= index < len(batch_chunks):
                            all_results.append((item.get("relevance_score", 0), batch_chunks[index]))
            
            # Ordena todos os resultados e retorna top_k
            all_results.sort(key=lambda x: x[0], reverse=True)
            reranked_chunks = [chunk for _, chunk in all_results[:top_k]]
            
            logger.info(f"CohereReranker rerankou {len(reranked_chunks)} chunks")
            return reranked_chunks
            
        except Exception as e:
            logger.error(f"Erro ao rerankear com Cohere: {e}")
            return chunks[:top_k]


# ============================================================================
# JINA RERANKER
# ============================================================================

class JinaReranker(BaseReranker):
    """Reranker usando Jina Rerank API."""
    
    def __init__(self):
        super().__init__("Jina", "Reranking usando Jina Rerank API")
        self.url = os.getenv("JINA_BASE_URL", "https://api.jina.ai/v1")
        self.api_key = get_token("JINA_API_KEY", None)
        self.available = self.api_key is not None
    
    async def rerank(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> List[Chunk]:
        """Reranks chunks usando Jina Rerank API."""
        if not chunks or not query:
            return chunks[:top_k]
        
        # Prioriza API key do parâmetro, depois do config, depois da env var
        api_key = api_key or self.api_key
        base_url = base_url or self.url
        
        if not api_key:
            logger.warning("Jina API key não configurada")
            return chunks[:top_k]
        
        try:
            import aiohttp
            import json
            
            # Prepara dados para API
            texts = [chunk.content for chunk in chunks]
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
                
                data = {
                    "query": query,
                    "documents": texts,
                    "top_n": top_k,
                }
                
                # Função interna para fazer requisição com retry
                async def make_request():
                    async with session.post(
                        f"{base_url}/rerank",
                        headers=headers,
                        json=data
                    ) as response:
                        response.raise_for_status()
                        return await response.json()
                
                # Executa com retry
                from verba_extensions.utils.retry import retry_with_backoff
                result = await retry_with_backoff(
                    make_request,
                    max_retries=3,
                    base_delay=1.0,
                    retryable_status_codes=[429, 500, 502, 503, 504],
                    operation_name="Jina Rerank API"
                )
                
                # Jina retorna resultados com índices e scores
                reranked_results = result.get("results", [])
                
                # Ordena por score (maior primeiro)
                reranked_results.sort(key=lambda x: x.get("score", 0), reverse=True)
                
                # Mapeia de volta para chunks
                reranked_chunks = []
                for item in reranked_results[:top_k]:
                    index = item.get("index", 0)
                    if 0 <= index < len(chunks):
                        reranked_chunks.append(chunks[index])
                    
                    logger.info(f"JinaReranker rerankou {len(reranked_chunks)} chunks")
                    return reranked_chunks
                    
        except Exception as e:
            logger.error(f"Erro ao rerankear com Jina: {e}")
            return chunks[:top_k]


# ============================================================================
# VOYAGEAI RERANKER
# ============================================================================

class VoyageAIReranker(BaseReranker):
    """Reranker usando VoyageAI Rerank API."""
    
    def __init__(self):
        super().__init__("VoyageAI", "Reranking usando VoyageAI Rerank API")
        self.url = os.getenv("VOYAGE_BASE_URL", "https://api.voyageai.com/v1")
        self.api_key = get_token("VOYAGE_API_KEY", None)
        self.available = self.api_key is not None
    
    async def rerank(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> List[Chunk]:
        """Reranks chunks usando VoyageAI Rerank API."""
        if not chunks or not query:
            return chunks[:top_k]
        
        # Prioriza API key do parâmetro, depois do config, depois da env var
        api_key = api_key or self.api_key
        base_url = base_url or self.url
        
        if not api_key:
            logger.warning("VoyageAI API key não configurada")
            return chunks[:top_k]
        
        try:
            import aiohttp
            import json
            from verba_extensions.utils.retry import retry_with_backoff
            
            # Prepara dados para API
            texts = [chunk.content for chunk in chunks]
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
                
                data = {
                    "query": query,
                    "documents": texts,
                    "top_n": top_k,
                }
                
                # Função interna para fazer requisição com retry
                async def make_request():
                    async with session.post(
                        f"{base_url}/rerank",
                        headers=headers,
                        json=data
                    ) as response:
                        response.raise_for_status()
                        return await response.json()
                
                # Executa com retry
                result = await retry_with_backoff(
                    make_request,
                    max_retries=3,
                    base_delay=1.0,
                    retryable_status_codes=[429, 500, 502, 503, 504],
                    operation_name="VoyageAI Rerank API"
                )
                
                # VoyageAI retorna resultados com índices e scores
                reranked_results = result.get("results", [])
                
                # Ordena por score (maior primeiro)
                reranked_results.sort(key=lambda x: x.get("score", 0), reverse=True)
                
                # Mapeia de volta para chunks
                reranked_chunks = []
                for item in reranked_results[:top_k]:
                    index = item.get("index", 0)
                    if 0 <= index < len(chunks):
                        reranked_chunks.append(chunks[index])
                
                logger.info(f"VoyageAIReranker rerankou {len(reranked_chunks)} chunks")
                return reranked_chunks
                    
        except Exception as e:
            logger.error(f"Erro ao rerankear com VoyageAI: {e}")
            return chunks[:top_k]


# ============================================================================
# CONTEXTUAL AI RERANKER
# ============================================================================

class ContextualAIReranker(BaseReranker):
    """
    Reranker usando Contextual AI Rerank API.
    
    Diferenciais:
    - Suporta instruções customizadas (instruction) para orientar o reranking
    - Suporta metadata por documento
    - Modelos multilíngues otimizados para RAG
    - Combina relevância da query com instruções customizadas
    """
    
    def __init__(self):
        super().__init__("ContextualAI", "Reranking usando Contextual AI Rerank API com instruções customizadas")
        self.url = os.getenv("CONTEXTUAL_BASE_URL", "https://api.contextual.ai/v1")
        self.api_key = get_token("CONTEXTUAL_API_KEY", None)
        self.available = self.api_key is not None
        self.default_model = "ctxl-rerank-v2-instruct-multilingual"
    
    async def rerank(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int,
        model: Optional[str] = None,
        instruction: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> List[Chunk]:
        """
        Reranks chunks usando Contextual AI Rerank API.
        
        Args:
            chunks: Lista de chunks a rerankear
            query: Query do usuário
            top_k: Número de chunks a retornar
            model: Modelo a usar (opcional)
            instruction: Instruções customizadas para orientar o reranking (opcional)
            api_key: API key (opcional, usa do config/env se não fornecido)
            base_url: Base URL (opcional, usa do config/env se não fornecido)
        
        Returns:
            Chunks rerankeados (ordenados por relevância)
        """
        if not chunks or not query:
            return chunks[:top_k]
        
        model = model or self.default_model
        # Prioriza API key do parâmetro, depois do config, depois da env var
        api_key = api_key or self.api_key
        base_url = base_url or self.url
        
        if not api_key:
            logger.warning("Contextual AI API key não configurada")
            return chunks[:top_k]
        
        try:
            import aiohttp
            import json
            
            # Prepara dados para API
            documents = [chunk.content for chunk in chunks]
            
            # Prepara metadata (se disponível nos chunks)
            metadata_list = []
            for chunk in chunks:
                # Extrai metadata relevante do chunk
                chunk_metadata = ""
                if chunk.meta:
                    # Pode incluir informações como tipo de documento, data, etc.
                    meta_parts = []
                    if "doc_name" in chunk.meta:
                        meta_parts.append(f"Documento: {chunk.meta['doc_name']}")
                    if "chunk_date" in chunk.meta:
                        meta_parts.append(f"Data: {chunk.meta['chunk_date']}")
                    if "chunk_lang" in chunk.meta:
                        meta_parts.append(f"Idioma: {chunk.meta['chunk_lang']}")
                    if "enriched" in chunk.meta:
                        enriched = chunk.meta["enriched"]
                        if "companies" in enriched:
                            meta_parts.append(f"Empresas: {', '.join(enriched['companies'][:3])}")
                        if "key_topics" in enriched:
                            meta_parts.append(f"Tópicos: {', '.join(enriched['key_topics'][:3])}")
                    
                    # Propriedades V019 (se disponíveis)
                    v019_parts = []
                    if "slide_position" in chunk.meta:
                        v019_parts.append(f"Posição: {chunk.meta['slide_position']}")
                    if "slide_type" in chunk.meta:
                        v019_parts.append(f"Tipo: {chunk.meta['slide_type']}")
                    if "visual_archetype" in chunk.meta:
                        v019_parts.append(f"Arquétipo: {chunk.meta['visual_archetype']}")
                    if "pattern_genetics" in chunk.meta:
                        patterns = chunk.meta["pattern_genetics"]
                        if isinstance(patterns, list) and patterns:
                            v019_parts.append(f"Patterns: {', '.join(patterns[:2])}")
                    if "reusability_score" in chunk.meta and chunk.meta["reusability_score"]:
                        v019_parts.append(f"Reusabilidade: {chunk.meta['reusability_score']}%")
                    if "semantic_bridge_quality" in chunk.meta and chunk.meta["semantic_bridge_quality"]:
                        quality = chunk.meta["semantic_bridge_quality"]
                        if quality > 0.8:
                            v019_parts.append(f"Qualidade Alta")
                    
                    # Se não encontrou diretamente, tenta extrair de slides_metadata
                    if not v019_parts and "slides_metadata" in chunk.meta:
                        slides_metadata = chunk.meta.get("slides_metadata", [])
                        if slides_metadata and len(slides_metadata) > 0:
                            first_slide = slides_metadata[0]
                            if first_slide.get("slide_position"):
                                v019_parts.append(f"Posição: {first_slide['slide_position']}")
                            if first_slide.get("slide_type"):
                                v019_parts.append(f"Tipo: {first_slide['slide_type']}")
                            if first_slide.get("visual_archetype"):
                                v019_parts.append(f"Arquétipo: {first_slide['visual_archetype']}")
                    
                    if v019_parts:
                        meta_parts.append(f"V019: {', '.join(v019_parts)}")
                    
                    chunk_metadata = " | ".join(meta_parts) if meta_parts else ""
                
                metadata_list.append(chunk_metadata)
            
            # Contextual AI aceita até 400k tokens total, 8k tokens por documento
            # Para segurança, vamos processar em batches menores se necessário
            batch_size = 50  # Processa 50 chunks por vez para evitar exceder limites
            all_results = []
            
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]
                batch_documents = documents[i:i + batch_size]
                batch_metadata = metadata_list[i:i + batch_size]
                
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    }
                    
                    # Monta payload da API
                    data = {
                        "query": query,
                        "documents": batch_documents,
                        "model": model,
                        "top_n": min(top_k, len(batch_chunks)),
                    }
                    
                    # Adiciona instruction se fornecida
                    if instruction:
                        data["instruction"] = instruction
                    
                    # Adiciona metadata se disponível
                    if any(batch_metadata):  # Só adiciona se houver pelo menos um metadata não vazio
                        data["metadata"] = batch_metadata
                    
                    # Função interna para fazer requisição com retry
                    async def make_request():
                        async with session.post(
                            f"{base_url}/rerank",
                            headers=headers,
                            json=data
                        ) as response:
                            response.raise_for_status()
                            return await response.json()
                    
                    # Executa com retry
                    from verba_extensions.utils.retry import retry_with_backoff
                    result = await retry_with_backoff(
                        make_request,
                        max_retries=3,
                        base_delay=1.0,
                        retryable_status_codes=[429, 500, 502, 503, 504],
                        operation_name=f"ContextualAI Rerank API (batch {i//batch_size + 1})"
                    )
                    
                    # Contextual AI retorna resultados com índices e relevance_score
                    reranked_results = result.get("results", [])
                    
                    # Ordena por score (maior primeiro)
                    reranked_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
                    
                    # Mapeia de volta para chunks
                    for item in reranked_results:
                        index = item.get("index", 0)
                        # Ajusta índice para o batch atual
                        original_index = i + index
                        if 0 <= original_index < len(chunks):
                            score = item.get("relevance_score", 0)
                            all_results.append((score, chunks[original_index]))
            
            # Ordena todos os resultados e retorna top_k
            all_results.sort(key=lambda x: x[0], reverse=True)
            reranked_chunks = [chunk for _, chunk in all_results[:top_k]]
            
            logger.info(f"ContextualAIReranker rerankou {len(reranked_chunks)} chunks (model: {model})")
            return reranked_chunks
            
        except aiohttp.ClientError as e:
            logger.error(f"Erro de conexão ao rerankear com Contextual AI: {e}")
            return chunks[:top_k]
        except Exception as e:
            logger.error(f"Erro ao rerankear com Contextual AI: {e}")
            return chunks[:top_k]


# ============================================================================
# RERANKER PRESETS
# ============================================================================

class RerankerPresets:
    """Presets otimizados para reranking."""
    
    # Preset: Balanced (antigo Production)
    BALANCED = {
        "name": "balanced",
        "display_name": "⚖️ Balanceado",
        "description": "ContextualAI apenas (rápido e eficiente)",
        "Reranker Provider": "ContextualAI",
        "ContextualAI Model": "ctxl-rerank-v2-instruct-multilingual",
        "ContextualAI Instruction": "Prioritize recent and authoritative content.",
        "Top K": 5,
        "latency_estimate": "~500ms",
        "quality_estimate": "Alta",
        "requirements": ["CONTEXTUAL_API_KEY"]
    }
    
    # Preset 2: Máxima Qualidade (Metadata + Haystack + ContextualAI)
    MAX_QUALITY = {
        "name": "max_quality",
        "display_name": "🎯 Qualidade Máxima",
        "description": "Metadata + Haystack + ContextualAI (melhor precisão)",
        "Reranker Provider": "Combined",
        "Reranker Mode": "Hybrid",
        "Enable Metadata Reranker": True,
        "Enable Haystack Reranker": True,
        "Enable ContextualAI Reranker": True,
        "ContextualAI Model": "ctxl-rerank-v2-instruct-multilingual",
        "ContextualAI Instruction": "Prioritize internal documents and recent content.",
        "Top K": 5,
        "latency_estimate": "~1.5s",
        "quality_estimate": "Muito Alta",
        "requirements": ["haystack-ai", "CONTEXTUAL_API_KEY"]
    }
    
    # Preset: Offline (Sem APIs)
    OFFLINE = {
        "name": "offline",
        "display_name": "🔌 Offline",
        "description": "Metadata + Haystack (sem APIs, local apenas)",
        "Reranker Provider": "Combined",
        "Reranker Mode": "Parallel",
        "Enable Metadata Reranker": True,
        "Enable Haystack Reranker": True,
        "Top K": 5,
        "latency_estimate": "~500ms",
        "quality_estimate": "Alta",
        "requirements": ["haystack-ai"]
    }

    # ============================================================================
    # NEW PRESETS - CONSULTING OPTIMIZED
    # ============================================================================

    # Preset: Consulting Frameworks (DEFAULT)
    CONSULTING_FRAMEWORKS = {
        "name": "consulting_frameworks",
        "display_name": "📊 Consultoria & Frameworks",
        "description": "Otimizado para buscar frameworks (SWOT, Porter, BCG) e metodologias em documentos de consultoria",
        
        # Arquitetura
        "Two-Phase Search Mode": "auto",
        "Two-Phase Search Filter Level": "document",  # Contexto completo, evita fragmentação
        "Enable Multi-Vector Search": True,
        
        # Busca
        "Alpha": 0.6,
        "Limit/Sensitivity": 2,
        "Reranker Top K": 7,
        
        # Otimizações
        "Enable Query Expansion": True,
        "Enable Dynamic Alpha": True,
        "Enable Relative Score Fusion": True,
        "Enable Intelligent Cache": True,
        "Enable Dynamic Reranking": True,
        "Chunk Window": 2,
        
        # Filtros
        "Enable Framework Filter": True,
        "Enable Language Filter": True,
        "Enable Semantic Search": True,
        "Enable Temporal Filter": False,  # Frameworks são atemporais
        
        # Reranker
        "Reranker Provider": "Combined",
        "Reranker Mode": "Cascade",
        "Enable Metadata Reranker": True,
        
        "latency_estimate": "~800ms",
        "quality_estimate": "Muito Alta",
    }

    # Preset: Company Research
    COMPANY_RESEARCH = {
        "name": "company_research",
        "display_name": "🏢 Pesquisa de Empresas",
        "description": "Otimizado para buscar informações sobre empresas específicas. Prioriza segmentação por documento.",
        
        # Arquitetura - Foco em entidades
        "Two-Phase Search Mode": "enabled",  # Sempre Two-Phase para isolar documentos
        "Two-Phase Search Filter Level": "document", # CRÍTICO: Evita contaminação entre empresas
        "Enable Multi-Vector Search": True,
        
        # Busca
        "Alpha": 0.4,  # Mais keyword para nomes
        "Limit/Sensitivity": 3,
        "Reranker Top K": 5,
        
        # Otimizações
        "Enable Query Expansion": False,
        "Enable Dynamic Alpha": False,
        "Enable Relative Score Fusion": True,
        "Enable Intelligent Cache": True,
        "Enable Dynamic Reranking": True,
        "Reranking Entity Weight": 0.3, # Prioriza entidades
        "Chunk Window": 1,
        
        # Filtros
        "Enable Entity Filter": False,
        "Entity Filter Mode": "strict",  # Quando reabilitado pelo usuário
        "Enable Framework Filter": True,
        "Enable Semantic Search": True,
        "Enable Temporal Filter": False,  # Foco em entidades, não tempo
        
        "latency_estimate": "~600ms",
        "quality_estimate": "Alta",
    }

    # Preset: Sector Analysis
    SECTOR_ANALYSIS = {
        "name": "sector_analysis",
        "display_name": "📈 Análise Setorial",
        "description": "Busca tendências e análises de setores (Agro, Tech, etc). Prioriza recência.",
        
        # Arquitetura
        "Two-Phase Search Mode": "auto",
        "Two-Phase Search Filter Level": "chunk",
        "Enable Multi-Vector Search": True,
        
        # Busca
        "Alpha": 0.7,
        "Limit/Sensitivity": 2,
        "Reranker Top K": 10,
        
        # Otimizações
        "Enable Query Expansion": True,
        "Enable Dynamic Alpha": True,
        "Enable Relative Score Fusion": True,
        "Enable Intelligent Cache": True,
        "Enable Dynamic Reranking": True,
        "Reranking Recency Weight": 0.25,
        "Chunk Window": 2,
        
        # Filtros
        "Enable Semantic Search": True,
        "Enable Temporal Filter": True,  # CRÍTICO: Prioriza documentos recentes
        "Enable Language Filter": True,
        
        "latency_estimate": "~900ms",
        "quality_estimate": "Muito Alta",
    }

    # Preset: Speed Mode
    SPEED_MODE = {
        "name": "speed",
        "display_name": "⚡ Velocidade",
        "description": "Prioriza velocidade. Ideal para demos.",
        
        # Arquitetura
        "Two-Phase Search Mode": "disabled",
        "Enable Multi-Vector Search": False,
        "Enable Aggregation": False,
        
        # Busca
        "Alpha": 0.5,
        "Limit/Sensitivity": 1,
        "Reranker Top K": 3,
        
        # Otimizações
        "Enable Query Expansion": False,
        "Enable Dynamic Alpha": False,
        "Enable Relative Score Fusion": False,
        "Enable Intelligent Cache": True,
        "Enable Dynamic Reranking": False,
        "Chunk Window": 0,
        "Reranker Provider": "Metadata Only",
        
        "latency_estimate": "~150ms",
        "quality_estimate": "Moderada",
    }
    
    @classmethod
    def get_preset(cls, preset_name: str) -> Optional[Dict[str, Any]]:
        """Retorna preset por nome."""
        return cls.get_all_presets().get(preset_name.lower())
    
    @classmethod
    def get_all_presets(cls) -> Dict[str, Dict[str, Any]]:
        """Retorna todos os presets."""
        return {
            "consulting_frameworks": cls.CONSULTING_FRAMEWORKS,
            "company_research": cls.COMPANY_RESEARCH,
            "sector_analysis": cls.SECTOR_ANALYSIS,
            "speed": cls.SPEED_MODE,
            "max_quality": cls.MAX_QUALITY,
            "balanced": cls.BALANCED,
            "offline": cls.OFFLINE,
            "cascade": cls.CASCADE,
            "cascade_premium": cls.CASCADE_PREMIUM
        }
    
    # Preset: Cascade (Fast Recall + MiniLM)
    CASCADE = {
        "name": "cascade",
        "display_name": "🌊 Cascade (Fast)",
        "description": "Recuperação rápida (MiniLM) com reranking local leve. Ótimo custo-benefício.",
        
        # Arquitetura
        "Two-Phase Search Mode": "auto",
        "Two-Phase Search Filter Level": "document",
        "Enable Multi-Vector Search": True,
        
        # Busca
        "Alpha": 0.5,
        "Limit/Sensitivity": 2,
        "Reranker Top K": 5,
        
        # Otimizações
        "Enable Query Expansion": True,
        "Enable Dynamic Alpha": True,
        "Chunk Window": 1,
        
        # Reranker
        "Reranker Provider": "Haystack",
        "Haystack Model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "Reranker Mode": "Cascade",
        
        "latency_estimate": "~400ms",
        "quality_estimate": "Alta",
        "requirements": ["haystack-ai"]
    }

    # Preset: Cascade Premium (Voyage Reranker)
    CASCADE_PREMIUM = {
        "name": "cascade_premium",
        "display_name": "💎 Cascade Premium",
        "description": "Recuperação profunda + Voyage AI Reranker. Máxima precisão para consultoria.",
        
        # Arquitetura
        "Two-Phase Search Mode": "auto",
        "Two-Phase Search Filter Level": "document",
        "Enable Multi-Vector Search": True,
        
        # Busca
        "Alpha": 0.6,
        "Limit/Sensitivity": 3,
        "Reranker Top K": 10,
        
        # Otimizações
        "Enable Query Expansion": True,
        "Enable Dynamic Alpha": True,
        "Enable Relative Score Fusion": True,
        "Chunk Window": 2,
        
        # Reranker Frameworks
        "Reranker Provider": "VoyageAI", 
        "Enable VoyageAI Reranker": True,
        "Reranker Mode": "Cascade",
        "Reranker Top K": 10,
        
        "latency_estimate": "~1.2s",
        "quality_estimate": "Estado da Arte",
        "requirements": ["VOYAGE_API_KEY"]
    }
    
    @classmethod
    def check_preset_availability(cls, preset_name: str, reranker_plugin: 'RerankerPlugin') -> Dict[str, Any]:
        """
        Verifica disponibilidade de um preset baseado nos recursos disponíveis.
        
        Returns:
            Dict com 'available' (bool), 'missing_requirements' (list), 'preset' (dict)
        """
        preset = cls.get_preset(preset_name)
        if not preset:
            return {
                "available": False,
                "missing_requirements": [],
                "preset": None,
                "reason": f"Preset '{preset_name}' não encontrado"
            }
        
        missing = []
        requirements = preset.get("requirements", [])
        
        for req in requirements:
            if req == "haystack-ai":
                if not reranker_plugin.haystack_reranker.available:
                    missing.append("haystack-ai não instalado")
            elif req == "CONTEXTUAL_API_KEY":
                if not reranker_plugin.contextualai_reranker.available:
                    missing.append("CONTEXTUAL_API_KEY não configurada")
            elif req == "COHERE_API_KEY":
                if not reranker_plugin.cohere_reranker.available:
                    missing.append("COHERE_API_KEY não configurada")
            elif req == "JINA_API_KEY":
                if not reranker_plugin.jina_reranker.available:
                    missing.append("JINA_API_KEY não configurada")
            elif req == "VOYAGE_API_KEY":
                if not reranker_plugin.voyageai_reranker.available:
                    missing.append("VOYAGE_API_KEY não configurada")
        
        return {
            "available": len(missing) == 0,
            "missing_requirements": missing,
            "preset": preset,
            "reason": None if len(missing) == 0 else f"Faltam: {', '.join(missing)}"
        }


# ============================================================================
# MAIN RERANKER PLUGIN (ORCHESTRATOR)
# ============================================================================

class RerankerPlugin:
    """
    Plugin para reranking de chunks usando múltiplos providers.
    
    Suporta:
    - Metadata-based (sempre disponível)
    - Haystack CrossEncoderRanker
    - Cohere Rerank API
    - Jina Rerank API
    - VoyageAI Rerank API
    - Contextual AI Rerank API (com instruções customizadas)
    
    Modos de combinação:
    - Cascade: Aplica rerankers sequencialmente
    - Parallel: Aplica múltiplos rerankers e combina scores
    - Hybrid: Combina cascade e parallel
    """
    
    def __init__(self):
        self.name = "Reranker"
        self.description = "Reranking inteligente de chunks para melhor relevância"
        self.installed = True
        self.last_metrics = None  # Armazena métricas da última execução
        
        # Inicializa providers
        self.metadata_reranker = MetadataReranker()
        self.haystack_reranker = HaystackReranker()
        self.cohere_reranker = CohereReranker()
        self.jina_reranker = JinaReranker()
        self.voyageai_reranker = VoyageAIReranker()
        self.contextualai_reranker = ContextualAIReranker()
        
        # Configuração padrão
        self.default_top_k = 5
        
        # Configuração via InputConfig
        self.config = self._build_config()
    
    def _build_config(self) -> Dict[str, InputConfig]:
        """Constrói configuração do plugin."""
        # Sempre mostra todos os providers no dropdown (mesmo sem API key)
        # Isso permite que o usuário configure API keys e endpoints via UI
        all_providers = ["Metadata Only", "Haystack", "Cohere", "Jina", "VoyageAI", "ContextualAI"]
        
        # Detecta providers disponíveis (com API key configurada)
        available_providers = ["Metadata Only"]
        if self.haystack_reranker.available:
            available_providers.append("Haystack")
        if self.cohere_reranker.available:
            available_providers.append("Cohere")
        if self.jina_reranker.available:
            available_providers.append("Jina")
        if self.voyageai_reranker.available:
            available_providers.append("VoyageAI")
        if self.contextualai_reranker.available:
            available_providers.append("ContextualAI")
        
        # Se múltiplos providers disponíveis, adiciona "Combined"
        if len(available_providers) > 2:
            all_providers.append("Combined")
        
        config = {
            "Reranker Provider": InputConfig(
                type="dropdown",
                value=all_providers[0],
                description="Selecione o provider de reranking",
                values=all_providers,
            ),
            "Enable Metadata Reranker": InputConfig(
                type="bool",
                value=True,
                description="Usar reranking baseado em metadata (sempre disponível)",
                values=[],
            ),
            "Enable Haystack Reranker": InputConfig(
                type="bool",
                value=self.haystack_reranker.available,
                description="Usar Haystack CrossEncoderRanker (requer haystack-ai instalado)",
                values=[],
                warning="Haystack não está instalado" if not self.haystack_reranker.available else None,
            ),
            "Enable Cohere Reranker": InputConfig(
                type="bool",
                value=self.cohere_reranker.available,
                description="Usar Cohere Rerank API (requer COHERE_API_KEY)",
                values=[],
                warning="COHERE_API_KEY não configurada" if not self.cohere_reranker.available else None,
            ),
            "Enable Jina Reranker": InputConfig(
                type="bool",
                value=self.jina_reranker.available,
                description="Usar Jina Rerank API (requer JINA_API_KEY)",
                values=[],
                warning="JINA_API_KEY não configurada" if not self.jina_reranker.available else None,
            ),
            "Enable VoyageAI Reranker": InputConfig(
                type="bool",
                value=self.voyageai_reranker.available,
                description="Usar VoyageAI Rerank API (requer VOYAGE_API_KEY)",
                values=[],
                warning="VOYAGE_API_KEY não configurada" if not self.voyageai_reranker.available else None,
            ),
            "Enable ContextualAI Reranker": InputConfig(
                type="bool",
                value=self.contextualai_reranker.available,
                description="Usar Contextual AI Rerank API com instruções customizadas (requer CONTEXTUAL_API_KEY)",
                values=[],
                warning="CONTEXTUAL_API_KEY não configurada" if not self.contextualai_reranker.available else None,
            ),
            "Reranker Mode": InputConfig(
                type="dropdown",
                value="Cascade",
                description="Modo de combinação de rerankers",
                values=["Cascade", "Parallel", "Hybrid"],
            ),
            "Top K": InputConfig(
                type="number",
                value=self.default_top_k,
                description="Número de chunks a retornar após reranking",
                values=[],
            ),
        }
        
        # Adiciona configurações específicas de providers
        # Sempre mostra campos de configuração, mesmo se provider não está disponível
        # Isso permite que o usuário configure via UI
        
        # Haystack Model (sempre disponível se haystack-ai instalado)
        config["Haystack Model"] = InputConfig(
            type="dropdown",
            value="cross-encoder/ms-marco-MiniLM-L-6-v2",
            description="Modelo Haystack CrossEncoderRanker",
            values=[
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                "cross-encoder/ms-marco-MiniLM-L-12-v2",
                "cross-encoder/ms-marco-electra-base",
            ],
        )
        
        # Cohere configurações
        config["Cohere Model"] = InputConfig(
            type="dropdown",
            value="rerank-english-v3.0",
            description="Modelo Cohere Rerank",
            values=[
                "rerank-english-v3.0",
                "rerank-multilingual-v3.0",
            ],
        )
        config["Cohere API Key"] = InputConfig(
            type="password",
            value=get_token("COHERE_API_KEY", "") or "",
            description="Cohere API Key (ou configure COHERE_API_KEY env var)",
            values=[],
        )
        config["Cohere Base URL"] = InputConfig(
            type="text",
            value=os.getenv("COHERE_BASE_URL", "https://api.cohere.com/v1"),
            description="Cohere API Base URL (padrão: https://api.cohere.com/v1)",
            values=[],
        )
        
        # Jina configurações
        config["Jina API Key"] = InputConfig(
            type="password",
            value=get_token("JINA_API_KEY", "") or "",
            description="Jina API Key (ou configure JINA_API_KEY env var)",
            values=[],
        )
        config["Jina Base URL"] = InputConfig(
            type="text",
            value=os.getenv("JINA_BASE_URL", "https://api.jina.ai/v1"),
            description="Jina API Base URL (padrão: https://api.jina.ai/v1)",
            values=[],
        )
        
        # VoyageAI configurações
        config["VoyageAI API Key"] = InputConfig(
            type="password",
            value=get_token("VOYAGE_API_KEY", "") or "",
            description="VoyageAI API Key (ou configure VOYAGE_API_KEY env var)",
            values=[],
        )
        config["VoyageAI Base URL"] = InputConfig(
            type="text",
            value=os.getenv("VOYAGE_BASE_URL", "https://api.voyageai.com/v1"),
            description="VoyageAI API Base URL (padrão: https://api.voyageai.com/v1)",
            values=[],
        )
        
        # ContextualAI configurações
        config["ContextualAI Model"] = InputConfig(
            type="dropdown",
            value="ctxl-rerank-v2-instruct-multilingual",
            description="Modelo Contextual AI Rerank",
            values=[
                "ctxl-rerank-v2-instruct-multilingual",
                "ctxl-rerank-v2-instruct-multilingual-mini",
                "ctxl-rerank-v1-instruct",
            ],
        )
        config["ContextualAI Instruction"] = InputConfig(
            type="text",
            value="",
            description="Instruções customizadas para orientar o reranking (opcional). Ex: 'Prioritize recent documents and internal sales documents over market analysis.'",
            values=[],
        )
        config["ContextualAI API Key"] = InputConfig(
            type="password",
            value=get_token("CONTEXTUAL_API_KEY", "") or "",
            description="Contextual AI API Key (ou configure CONTEXTUAL_API_KEY env var)",
            values=[],
        )
        config["ContextualAI Base URL"] = InputConfig(
            type="text",
            value=os.getenv("CONTEXTUAL_BASE_URL", "https://api.contextual.ai/v1"),
            description="Contextual AI API Base URL (padrão: https://api.contextual.ai/v1)",
            values=[],
        )
        
        return config
    
    async def process_chunk(self, chunk, config=None):
        """Processa um único chunk (compatibilidade com plugin system)."""
        return chunk
    
    async def process_batch(self, chunks, config=None):
        """Processa múltiplos chunks em batch (reranking)."""
        query = ""
        if config and isinstance(config, dict):
            query = config.get("query", "")
        
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
        Reranks chunks baseado em query e configuração.
        
        Args:
            chunks: Lista de chunks a rerankear
            query: Query do usuário
            config: Configuração opcional (pode incluir configurações do plugin ou RAG config)
        
        Returns:
            Chunks rerankeados (ordenados por relevância)
        """
        import time
        start_time = time.time()
        num_chunks_before = len(chunks)
        
        if not chunks:
            return chunks
        
        config = config or {}
        
        # Tenta buscar configurações do RAG config se disponível
        reranker_config = self._get_reranker_config_from_rag(config)
        
        # Extrai configurações (prioriza RAG config, depois config direto, depois defaults)
        provider = self._get_config_value(reranker_config, "Reranker Provider", 
                                         self._get_config_value(config, "Reranker Provider", "Metadata Only"))
        use_metadata = self._get_config_value(reranker_config, "Enable Metadata Reranker",
                                            self._get_config_value(config, "Enable Metadata Reranker", True))
        use_haystack = self._get_config_value(reranker_config, "Enable Haystack Reranker",
                                             self._get_config_value(config, "Enable Haystack Reranker", False))
        use_cohere = self._get_config_value(reranker_config, "Enable Cohere Reranker",
                                          self._get_config_value(config, "Enable Cohere Reranker", False))
        use_jina = self._get_config_value(reranker_config, "Enable Jina Reranker",
                                         self._get_config_value(config, "Enable Jina Reranker", False))
        use_voyageai = self._get_config_value(reranker_config, "Enable VoyageAI Reranker",
                                            self._get_config_value(config, "Enable VoyageAI Reranker", False))
        use_contextualai = self._get_config_value(reranker_config, "Enable ContextualAI Reranker",
                                                 self._get_config_value(config, "Enable ContextualAI Reranker", False))
        mode = self._get_config_value(reranker_config, "Reranker Mode",
                                    self._get_config_value(config, "Reranker Mode", "Cascade"))
        top_k = self._get_config_value(config, "top_k", 
                                     self._get_config_value(reranker_config, "Top K",
                                                           self._get_config_value(config, "Top K", self.default_top_k)))
        
        # Merge configs para passar para métodos internos
        merged_config = {**config, **reranker_config}
        
        # Se provider específico selecionado, usa apenas ele
        if provider == "Metadata Only":
            result = await self.metadata_reranker.rerank(chunks, query, top_k)
        elif provider == "Haystack" and self.haystack_reranker.available:
            result = await self.haystack_reranker.rerank(chunks, query, top_k)
        elif provider == "Cohere":
            cohere_model = self._get_config_value(merged_config, "Cohere Model", "rerank-english-v3.0")
            cohere_api_key = self._get_config_value(merged_config, "Cohere API Key", None)
            cohere_base_url = self._get_config_value(merged_config, "Cohere Base URL", None)
            # Tenta usar API key do config, se não disponível usa a do reranker (env var)
            if cohere_api_key or self.cohere_reranker.available:
                result = await self.cohere_reranker.rerank(
                    chunks, query, top_k, cohere_model, 
                    api_key=cohere_api_key, base_url=cohere_base_url
                )
            else:
                logger.warning("Cohere API key não configurada, usando Metadata Only")
                result = await self.metadata_reranker.rerank(chunks, query, top_k)
        elif provider == "Jina":
            jina_api_key = self._get_config_value(merged_config, "Jina API Key", None)
            jina_base_url = self._get_config_value(merged_config, "Jina Base URL", None)
            # Tenta usar API key do config, se não disponível usa a do reranker (env var)
            if jina_api_key or self.jina_reranker.available:
                result = await self.jina_reranker.rerank(
                    chunks, query, top_k,
                    api_key=jina_api_key, base_url=jina_base_url
                )
            else:
                logger.warning("Jina API key não configurada, usando Metadata Only")
                result = await self.metadata_reranker.rerank(chunks, query, top_k)
        elif provider == "VoyageAI":
            voyageai_api_key = self._get_config_value(merged_config, "VoyageAI API Key", None)
            voyageai_base_url = self._get_config_value(merged_config, "VoyageAI Base URL", None)
            # Tenta usar API key do config, se não disponível usa a do reranker (env var)
            if voyageai_api_key or self.voyageai_reranker.available:
                result = await self.voyageai_reranker.rerank(
                    chunks, query, top_k,
                    api_key=voyageai_api_key, base_url=voyageai_base_url
                )
            else:
                logger.warning("VoyageAI API key não configurada, usando Metadata Only")
                result = await self.metadata_reranker.rerank(chunks, query, top_k)
        elif provider == "ContextualAI":
            contextualai_model = self._get_config_value(merged_config, "ContextualAI Model", "ctxl-rerank-v2-instruct-multilingual")
            contextualai_instruction = self._get_config_value(merged_config, "ContextualAI Instruction", None)
            contextualai_api_key = self._get_config_value(merged_config, "ContextualAI API Key", None)
            contextualai_base_url = self._get_config_value(merged_config, "ContextualAI Base URL", None)
            # Tenta usar API key do config, se não disponível usa a do reranker (env var)
            if contextualai_api_key or self.contextualai_reranker.available:
                result = await self.contextualai_reranker.rerank(
                    chunks, query, top_k, contextualai_model, contextualai_instruction,
                    api_key=contextualai_api_key, base_url=contextualai_base_url
                )
            else:
                logger.warning("ContextualAI API key não configurada, usando Metadata Only")
                result = await self.metadata_reranker.rerank(chunks, query, top_k)
        elif provider == "Combined":
            # Modo combinado: usa configurações individuais
            result = await self._rerank_combined(
                chunks, query, top_k, mode,
                use_metadata, use_haystack, use_cohere, use_jina, use_voyageai, use_contextualai, merged_config
            )
        else:
            # Fallback: metadata only
            logger.warning(f"Provider '{provider}' não disponível, usando Metadata Only")
            result = await self.metadata_reranker.rerank(chunks, query, top_k)
        
        # Tracking de métricas
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        num_chunks_after = len(result)
        
        # Armazena métricas no objeto para acesso posterior
        self.last_metrics = {
            "provider": provider,
            "latency_ms": latency_ms,
            "chunks_before": num_chunks_before,
            "chunks_after": num_chunks_after,
            "query": query[:50] if query else "",  # Primeiros 50 chars para log
        }
        
        logger.debug(f"Reranking: {provider} | {num_chunks_before}→{num_chunks_after} chunks | {latency_ms:.2f}ms")
        
        return result
    
    def _get_reranker_config_from_rag(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai configurações do reranker do RAG config se disponível."""
        reranker_config = {}
        
        # Tenta buscar do RAG config (estrutura: rag_config["Retriever"].components["Entity-Aware"].config)
        if "rag_config" in config:
            rag_config = config["rag_config"]
            try:
                if "Retriever" in rag_config:
                    retriever_config = rag_config["Retriever"]
                    if hasattr(retriever_config, "components"):
                        # Verifica se há componente Entity-Aware
                        entity_aware = retriever_config.components.get("Entity-Aware")
                        if entity_aware and hasattr(entity_aware, "config"):
                            # Busca configurações do reranker no config do retriever
                            retriever_plugin_config = entity_aware.config
                            # O reranker pode estar em um plugin separado ou no próprio retriever
                            # Por enquanto, assumimos que está no retriever config
                            for key in ["Reranker Provider", "Enable Metadata Reranker", 
                                       "Enable Haystack Reranker", "Enable Cohere Reranker",
                                       "Enable Jina Reranker", "Enable VoyageAI Reranker",
                                       "Enable ContextualAI Reranker", "Reranker Mode", "Top K", 
                                       "Haystack Model", "Cohere Model", "ContextualAI Model", 
                                       "ContextualAI Instruction"]:
                                if key in retriever_plugin_config:
                                    reranker_config[key] = retriever_plugin_config[key]
            except Exception as e:
                logger.debug(f"Erro ao extrair config do RAG: {e}")
        
        # Se não encontrou no RAG config, tenta usar configurações padrão do plugin
        if not reranker_config:
            # Usa configurações padrão do próprio plugin
            for key, input_config in self.config.items():
                if key.startswith("Reranker") or key.startswith("Enable") or key in ["Top K", "Haystack Model", "Cohere Model"]:
                    reranker_config[key] = input_config
        
        return reranker_config
    
    async def _rerank_combined(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int,
        mode: str,
        use_metadata: bool,
        use_haystack: bool,
        use_cohere: bool,
        use_jina: bool,
        use_voyageai: bool,
        use_contextualai: bool,
        config: Dict[str, Any]
    ) -> List[Chunk]:
        """Combina múltiplos rerankers baseado no modo."""
        if mode == "Cascade":
            return await self._rerank_cascade(
                chunks, query, top_k,
                use_metadata, use_haystack, use_cohere, use_jina, use_voyageai, use_contextualai, config
            )
        elif mode == "Parallel":
            return await self._rerank_parallel(
                chunks, query, top_k,
                use_metadata, use_haystack, use_cohere, use_jina, use_voyageai, use_contextualai, config
            )
        elif mode == "Hybrid":
            return await self._rerank_hybrid(
                chunks, query, top_k,
                use_metadata, use_haystack, use_cohere, use_jina, use_voyageai, use_contextualai, config
            )
        else:
            # Fallback: cascade
            return await self._rerank_cascade(
                chunks, query, top_k,
                use_metadata, use_haystack, use_cohere, use_jina, use_voyageai, use_contextualai, config
            )
    
    async def _rerank_cascade(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int,
        use_metadata: bool,
        use_haystack: bool,
        use_cohere: bool,
        use_jina: bool,
        use_voyageai: bool,
        use_contextualai: bool,
        config: Dict[str, Any]
    ) -> List[Chunk]:
        """Aplica rerankers sequencialmente (cascade)."""
        current_chunks = chunks
        
        # 1. Metadata reranker (sempre primeiro se habilitado)
        if use_metadata:
            current_chunks = await self.metadata_reranker.rerank(
                current_chunks, query, min(top_k * 2, len(current_chunks))
            )
        
        # 2. Haystack (se habilitado)
        if use_haystack and self.haystack_reranker.available:
            current_chunks = await self.haystack_reranker.rerank(
                current_chunks, query, min(top_k * 1.5, len(current_chunks))
            )
        
        # 3. Cohere (se habilitado)
        if use_cohere:
            cohere_model = self._get_config_value(config, "Cohere Model", "rerank-english-v3.0")
            cohere_api_key = self._get_config_value(config, "Cohere API Key", None)
            cohere_base_url = self._get_config_value(config, "Cohere Base URL", None)
            if cohere_api_key or self.cohere_reranker.available:
                current_chunks = await self.cohere_reranker.rerank(
                    current_chunks, query, top_k, cohere_model,
                    api_key=cohere_api_key, base_url=cohere_base_url
                )
        
        # 4. Jina (se habilitado)
        if use_jina:
            jina_api_key = self._get_config_value(config, "Jina API Key", None)
            jina_base_url = self._get_config_value(config, "Jina Base URL", None)
            if jina_api_key or self.jina_reranker.available:
                current_chunks = await self.jina_reranker.rerank(
                    current_chunks, query, top_k,
                    api_key=jina_api_key, base_url=jina_base_url
                )
        
        # 5. VoyageAI (se habilitado)
        if use_voyageai:
            voyageai_api_key = self._get_config_value(config, "VoyageAI API Key", None)
            voyageai_base_url = self._get_config_value(config, "VoyageAI Base URL", None)
            if voyageai_api_key or self.voyageai_reranker.available:
                current_chunks = await self.voyageai_reranker.rerank(
                    current_chunks, query, top_k,
                    api_key=voyageai_api_key, base_url=voyageai_base_url
                )
        
        # 6. ContextualAI (se habilitado)
        if use_contextualai:
            contextualai_model = self._get_config_value(config, "ContextualAI Model", "ctxl-rerank-v2-instruct-multilingual")
            contextualai_instruction = self._get_config_value(config, "ContextualAI Instruction", None)
            contextualai_api_key = self._get_config_value(config, "ContextualAI API Key", None)
            contextualai_base_url = self._get_config_value(config, "ContextualAI Base URL", None)
            if contextualai_api_key or self.contextualai_reranker.available:
                current_chunks = await self.contextualai_reranker.rerank(
                    current_chunks, query, top_k, contextualai_model, contextualai_instruction,
                    api_key=contextualai_api_key, base_url=contextualai_base_url
                )
        
        return current_chunks[:top_k]
    
    async def _rerank_parallel(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int,
        use_metadata: bool,
        use_haystack: bool,
        use_cohere: bool,
        use_jina: bool,
        use_voyageai: bool,
        use_contextualai: bool,
        config: Dict[str, Any]
    ) -> List[Chunk]:
        """Aplica múltiplos rerankers em paralelo e combina scores usando RRF."""
        tasks = []
        reranker_names = []
        
        # Prepara tasks para cada reranker habilitado
        if use_metadata:
            tasks.append(self.metadata_reranker.rerank(chunks, query, len(chunks)))
            reranker_names.append("metadata")
        
        if use_haystack and self.haystack_reranker.available:
            tasks.append(self.haystack_reranker.rerank(chunks, query, len(chunks)))
            reranker_names.append("haystack")
        
        if use_cohere:
            cohere_model = self._get_config_value(config, "Cohere Model", "rerank-english-v3.0")
            cohere_api_key = self._get_config_value(config, "Cohere API Key", None)
            cohere_base_url = self._get_config_value(config, "Cohere Base URL", None)
            if cohere_api_key or self.cohere_reranker.available:
                tasks.append(self.cohere_reranker.rerank(
                    chunks, query, len(chunks), cohere_model,
                    api_key=cohere_api_key, base_url=cohere_base_url
                ))
                reranker_names.append("cohere")
        
        if use_jina:
            jina_api_key = self._get_config_value(config, "Jina API Key", None)
            jina_base_url = self._get_config_value(config, "Jina Base URL", None)
            if jina_api_key or self.jina_reranker.available:
                tasks.append(self.jina_reranker.rerank(
                    chunks, query, len(chunks),
                    api_key=jina_api_key, base_url=jina_base_url
                ))
                reranker_names.append("jina")
        
        if use_voyageai:
            voyageai_api_key = self._get_config_value(config, "VoyageAI API Key", None)
            voyageai_base_url = self._get_config_value(config, "VoyageAI Base URL", None)
            if voyageai_api_key or self.voyageai_reranker.available:
                tasks.append(self.voyageai_reranker.rerank(
                    chunks, query, len(chunks),
                    api_key=voyageai_api_key, base_url=voyageai_base_url
                ))
                reranker_names.append("voyageai")
        
        if use_contextualai:
            contextualai_model = self._get_config_value(config, "ContextualAI Model", "ctxl-rerank-v2-instruct-multilingual")
            contextualai_instruction = self._get_config_value(config, "ContextualAI Instruction", None)
            contextualai_api_key = self._get_config_value(config, "ContextualAI API Key", None)
            contextualai_base_url = self._get_config_value(config, "ContextualAI Base URL", None)
            if contextualai_api_key or self.contextualai_reranker.available:
                tasks.append(self.contextualai_reranker.rerank(
                    chunks, query, len(chunks), contextualai_model, contextualai_instruction,
                    api_key=contextualai_api_key, base_url=contextualai_base_url
                ))
                reranker_names.append("contextualai")
        
        if not tasks:
            # Nenhum reranker habilitado, retorna original
            return chunks[:top_k]
        
        # Executa todos os rerankers em paralelo
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combina resultados usando RRF (Reciprocal Rank Fusion)
        chunk_scores = {}
        for reranker_name, result in zip(reranker_names, results):
            if isinstance(result, Exception):
                logger.warning(f"Reranker {reranker_name} falhou: {result}")
                continue
            
            # Calcula RRF score para cada chunk
            for rank, chunk in enumerate(result):
                chunk_id = chunk.uuid or id(chunk)
                if chunk_id not in chunk_scores:
                    chunk_scores[chunk_id] = {"chunk": chunk, "score": 0.0}
                
                # RRF: score = 1 / (k + rank)
                # k = 60 (valor padrão usado em RRF)
                k = 60
                rrf_score = 1.0 / (k + rank + 1)
                chunk_scores[chunk_id]["score"] += rrf_score
        
        # Ordena por score combinado
        scored_chunks = sorted(
            chunk_scores.values(),
            key=lambda x: x["score"],
            reverse=True
        )
        
        reranked_chunks = [item["chunk"] for item in scored_chunks[:top_k]]
        logger.info(f"Parallel reranking combinou {len(reranker_names)} rerankers")
        return reranked_chunks
    
    async def _rerank_hybrid(
        self,
        chunks: List[Chunk],
        query: str,
        top_k: int,
        use_metadata: bool,
        use_haystack: bool,
        use_cohere: bool,
        use_jina: bool,
        use_voyageai: bool,
        use_contextualai: bool,
        config: Dict[str, Any]
    ) -> List[Chunk]:
        """Combina cascade e parallel (metadata + haystack em parallel, depois API em cascade)."""
        # Fase 1: Metadata + Haystack em parallel (se ambos habilitados)
        if use_metadata and use_haystack and self.haystack_reranker.available:
            tasks = [
                self.metadata_reranker.rerank(chunks, query, len(chunks)),
                self.haystack_reranker.rerank(chunks, query, len(chunks))
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combina usando RRF
            chunk_scores = {}
            for result in results:
                if isinstance(result, Exception):
                    continue
                for rank, chunk in enumerate(result):
                    chunk_id = chunk.uuid or id(chunk)
                    if chunk_id not in chunk_scores:
                        chunk_scores[chunk_id] = {"chunk": chunk, "score": 0.0}
                    k = 60
                    rrf_score = 1.0 / (k + rank + 1)
                    chunk_scores[chunk_id]["score"] += rrf_score
            
            # Ordena e pega top chunks
            scored_chunks = sorted(
                chunk_scores.values(),
                key=lambda x: x["score"],
                reverse=True
            )
            current_chunks = [item["chunk"] for item in scored_chunks[:min(top_k * 2, len(chunks))]]
        elif use_metadata:
            current_chunks = await self.metadata_reranker.rerank(
                chunks, query, min(top_k * 2, len(chunks))
            )
        elif use_haystack and self.haystack_reranker.available:
            current_chunks = await self.haystack_reranker.rerank(
                chunks, query, min(top_k * 2, len(chunks))
            )
        else:
            current_chunks = chunks
        
        # Fase 2: APIs em cascade (se habilitadas)
        if use_cohere:
            cohere_model = self._get_config_value(config, "Cohere Model", "rerank-english-v3.0")
            cohere_api_key = self._get_config_value(config, "Cohere API Key", None)
            cohere_base_url = self._get_config_value(config, "Cohere Base URL", None)
            if cohere_api_key or self.cohere_reranker.available:
                current_chunks = await self.cohere_reranker.rerank(
                    current_chunks, query, top_k, cohere_model,
                    api_key=cohere_api_key, base_url=cohere_base_url
                )
        
        if use_jina:
            jina_api_key = self._get_config_value(config, "Jina API Key", None)
            jina_base_url = self._get_config_value(config, "Jina Base URL", None)
            if jina_api_key or self.jina_reranker.available:
                current_chunks = await self.jina_reranker.rerank(
                    current_chunks, query, top_k,
                    api_key=jina_api_key, base_url=jina_base_url
                )
        
        if use_voyageai:
            voyageai_api_key = self._get_config_value(config, "VoyageAI API Key", None)
            voyageai_base_url = self._get_config_value(config, "VoyageAI Base URL", None)
            if voyageai_api_key or self.voyageai_reranker.available:
                current_chunks = await self.voyageai_reranker.rerank(
                    current_chunks, query, top_k,
                    api_key=voyageai_api_key, base_url=voyageai_base_url
                )
        
        if use_contextualai:
            contextualai_model = self._get_config_value(config, "ContextualAI Model", "ctxl-rerank-v2-instruct-multilingual")
            contextualai_instruction = self._get_config_value(config, "ContextualAI Instruction", None)
            contextualai_api_key = self._get_config_value(config, "ContextualAI API Key", None)
            contextualai_base_url = self._get_config_value(config, "ContextualAI Base URL", None)
            if contextualai_api_key or self.contextualai_reranker.available:
                current_chunks = await self.contextualai_reranker.rerank(
                    current_chunks, query, top_k, contextualai_model, contextualai_instruction,
                    api_key=contextualai_api_key, base_url=contextualai_base_url
                )
        
        return current_chunks[:top_k]
    
    def _get_config_value(self, config: Dict[str, Any], key: str, default: Any) -> Any:
        """Extrai valor de configuração, suportando InputConfig ou valor direto."""
        if key not in config:
            return default
        
        value = config[key]
        
        # Se é InputConfig, extrai .value
        if hasattr(value, 'value'):
            return value.value
        
        # Se é dict com 'value', extrai
        if isinstance(value, dict) and 'value' in value:
            return value['value']
        
        # Caso contrário, retorna direto
        return value
    
    def get_config(self) -> Dict[str, Any]:
        """Retorna configuração do plugin."""
        return {
            "name": self.name,
            "description": self.description,
            "default_top_k": self.default_top_k,
            "available_providers": {
                "metadata": self.metadata_reranker.available,
                "haystack": self.haystack_reranker.available,
                "cohere": self.cohere_reranker.available,
                "jina": self.jina_reranker.available,
                "voyageai": self.voyageai_reranker.available,
                "contextualai": self.contextualai_reranker.available,
            }
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
    
    def select_optimal_preset(
        self,
        query: str,
        has_api_keys: bool = None,
        latency_budget: float = 2.0
    ) -> str:
        """
        Seleciona preset otimizado baseado na query e recursos disponíveis.
        
        Args:
            query: Query do usuário
            has_api_keys: Se há API keys disponíveis (None = auto-detect)
            latency_budget: Orçamento de latência em segundos
        
        Returns:
            Nome do preset recomendado: "production", "max_quality", ou "local_only"
        """
        # Auto-detect API keys se não fornecido
        if has_api_keys is None:
            has_api_keys = (
                self.contextualai_reranker.available or
                self.cohere_reranker.available or
                self.jina_reranker.available or
                self.voyageai_reranker.available
            )
        
        # Análise básica da query
        query_lower = query.lower()
        query_words = len(query.split())
        has_entities = any(keyword in query_lower for keyword in ["apple", "microsoft", "empresa", "company"])
        needs_instructions = any(keyword in query_lower for keyword in ["recente", "recent", "interno", "internal", "prioritize"])
        is_complex = query_words > 10
        
        # Lógica de seleção
        if latency_budget < 1.0 and has_api_keys:
            # Latência crítica: usar produção (1 API apenas)
            return "production"
        elif needs_instructions and has_api_keys and self.haystack_reranker.available:
            # Precisa instruções + tem recursos: usar max_quality
            return "max_quality"
        elif has_entities and not has_api_keys and self.haystack_reranker.available:
            # Sem APIs mas tem Haystack: usar local_only
            return "local_only"
        elif has_api_keys:
            # Tem APIs: usar produção (balanceado)
            return "production"
        elif self.haystack_reranker.available:
            # Apenas Haystack: usar local_only
            return "local_only"
        else:
            # Fallback: produção (sempre disponível via Metadata)
            return "production"
    
    def apply_preset(self, preset_name: str) -> Dict[str, Any]:
        """
        Aplica configurações de preset ao config do plugin.
        
        Args:
            preset_name: Nome do preset ("production", "max_quality", "local_only", ou "auto")
        
        Returns:
            Dict com configuração aplicada
        """
        # Se "auto", seleciona preset otimizado
        if preset_name == "auto":
            preset_name = self.select_optimal_preset("")
        
        # Se "custom", não aplica nada (mantém config atual)
        if preset_name == "custom":
            return {key: getattr(value, 'value', value) if hasattr(value, 'value') else value 
                   for key, value in self.config.items()}
        
        # Obtém preset
        preset = RerankerPresets.get_preset(preset_name)
        if not preset:
            logger.warning(f"Preset '{preset_name}' não encontrado, usando config atual")
            return {key: getattr(value, 'value', value) if hasattr(value, 'value') else value 
                   for key, value in self.config.items()}
        
        # Verifica disponibilidade
        availability = RerankerPresets.check_preset_availability(preset_name, self)
        if not availability["available"]:
            logger.warning(f"Preset '{preset_name}' não disponível: {availability['reason']}")
            # Tenta fallback para balanced
            if preset_name != "balanced":
                return self.apply_preset("balanced")
        
        # Aplica configurações do preset ao self.config
        applied_config = {}
        for key, value in preset.items():
            # Ignora metadados do preset
            if key in ["latency_estimate", "quality_estimate", "description", "requirements"]:
                continue
            
            # Atualiza config se a chave existir
            if key in self.config:
                if isinstance(self.config[key], InputConfig):
                    self.config[key].value = value
                else:
                    self.config[key] = value
                applied_config[key] = value
        
        logger.info(f"Preset '{preset_name}' aplicado com sucesso")
        return applied_config
    
    def get_presets_metadata(self) -> List[Dict[str, Any]]:
        """
        Retorna metadados de todos os presets com disponibilidade.
        
        Returns:
            Lista de dicts com informações de cada preset
        """
        presets = RerankerPresets.get_all_presets()
        metadata = []
        
        for preset_name, preset_config in presets.items():
            availability = RerankerPresets.check_preset_availability(preset_name, self)
            metadata.append({
                "name": preset_name,
                "display_name": preset_name.replace("_", " ").title(),
                "description": preset_config.get("description", ""),
                "latency_estimate": preset_config.get("latency_estimate", "N/A"),
                "quality_estimate": preset_config.get("quality_estimate", "N/A"),
                "available": availability["available"],
                "missing_requirements": availability["missing_requirements"],
                "config": preset_config
            })
        
        return metadata


def create_reranker() -> RerankerPlugin:
    """Factory para criar instância do plugin."""
    return RerankerPlugin()
