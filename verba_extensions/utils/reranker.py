
import os
from typing import List, Dict, Any, Optional
from wasabi import msg
import asyncio

# Tenta importar voyageai, mas falha graciosamente se não estiver instalado
try:
    import voyageai
    VOYAGE_AVAILABLE = True
except ImportError:
    VOYAGE_AVAILABLE = False
    msg.warn("[Cascade-Reranker] voyageai not installed. Reranking will be disabled.")

class CascadeReranker:
    """
    Cascade Reranker Utility.
    
    Responsável pela segunda etapa do Cascade Retrieval:
    1. Recebe lista de chunks candidatos (Top-K ~50-100)
    2. Usa modelo de reranking (Voyage Reranker) para reordenar
    3. Retorna Top-N (ex: 5-10) mais relevantes
    
    Model: voyage-rerank-2
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("VOYAGE_API_KEY")
        self.client = None
        
        if self.api_key and VOYAGE_AVAILABLE:
            try:
                self.client = voyageai.Client(api_key=self.api_key)
                msg.info("[Cascade-Reranker] Voyage Client initialized.")
            except Exception as e:
                msg.warn(f"[Cascade-Reranker] Failed to initialize Voyage Client: {e}")
        else:
             if not self.api_key:
                  msg.warn("[Cascade-Reranker] No API Key provided.")
    
    async def rerank(
        self,
        query: str,
        chunks: List[Any], # Weaviate Objects or Dicts
        top_k: int = 5,
        model: str = "rerank-2"
    ) -> List[Any]:
        """
        Rerank a list of chunks based on the query using Voyage Reranker.
        
        Args:
            query: The search query
            chunks: List of documents/chunks to rerank
            top_k: Number of results to return
            model: Voyage model name
            
        Returns:
            Reordered list of chunks with updated scores
        """
        if not self.client or not chunks:
            msg.info("[Cascade-Reranker] Reranker inactive or empty chunks. Returning original order.")
            return chunks[:top_k]

        try:
            # Extract texts specific to each chunk for reranking
            documents = []
            for chunk in chunks:
                # Handle both Weaviate Objects and Dicts
                content = getattr(chunk, 'properties', {}).get('content') or \
                          getattr(chunk, 'properties', {}).get('text') or \
                          chunk.get('content') or chunk.get('text') or ""
                documents.append(content)
            
            if not documents:
                return chunks[:top_k]

            # Call Voyage Rerank API (Sync call wrapped in thread for async if needed, 
            # but Voyage client might be sync. Let's assume sync for now and just run it.)
            # For high concurrency, might want to run in executor.
            
            # Voyage rerank returns a RerankingObject
            reranking_result = self.client.rerank(
                query=query,
                documents=documents,
                model=model,
                top_k=top_k
            )
            
            # Map results back to chunks
            reranked_chunks = []
            for result in reranking_result.results:
                original_index = result.index
                chunk = chunks[original_index]
                
                # Update score if possible (Optional, for debugging)
                # Weaviate objects might be read-only or rigid. 
                # Ideally we return a wrapper or just the chunk.
                # Let's attach score to metadata if possible or just return ordered list.
                
                reranked_chunks.append(chunk)
                
            msg.good(f"[Cascade-Reranker] Reranked {len(chunks)} -> {len(reranked_chunks)} results.")
            return reranked_chunks

        except Exception as e:
            msg.fail(f"[Cascade-Reranker] Reranking failed: {e}")
            import traceback
            msg.debug(traceback.format_exc())
            return chunks[:top_k] # Fallback to original order
