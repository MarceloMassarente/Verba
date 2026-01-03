
import pytest
from unittest.mock import Mock, AsyncMock, patch
from verba_extensions.plugins.entity_aware_retriever import EntityAwareRetriever
from goldenverba.components.chunk import Chunk

class MockWeaviateObject:
    def __init__(self, uuid, content, score=None, doc_uuid="doc1", chunk_id=0):
        self.uuid = uuid
        self.properties = {
            "content": content,
            "doc_uuid": doc_uuid,
            "chunk_id": chunk_id,
            "meta": '{"source": "test"}'
        }
        self.metadata = Mock()
        self.metadata.score = score

@pytest.mark.asyncio
async def test_cascade_empty_recall():
    """Verifica se o modo cascade lida bem com 0 resultados na fase 1"""
    retriever = EntityAwareRetriever()
    
    # Lista vazia de chunks
    result = await retriever._execute_cascade_search([], "query", {})
    
    assert result == []

@pytest.mark.asyncio
async def test_cascade_reranker_limit_exceeded():
    """Verifica comportamento se Top K > Chunks disponíveis"""
    retriever = EntityAwareRetriever()
    
    chunks = [MockWeaviateObject("u1", "c1", chunk_id=1)]
    config = {"Reranker Top K": {"value": 10}} # Quero 10, mas só tem 1
    
    with patch("verba_extensions.plugins.reranker.RerankerPlugin") as MockReranker:
        mock_reranker = MockReranker.return_value
        # Reranker retorna apenas o que recebeu (1 chunk)
        c1 = Chunk(content="c1", chunk_id=1)
        mock_reranker.rerank = AsyncMock(return_value=[c1])
        
        result = await retriever._execute_cascade_search(chunks, "q", config)
        
        assert len(result) == 1
        assert result[0].uuid == "u1"

@pytest.mark.asyncio
async def test_cascade_reranker_failure_fallback():
    """Verifica se o sistema falha graciosamente (mantém chunks originais) se o reranker der erro"""
    retriever = EntityAwareRetriever()
    
    chunks = [MockWeaviateObject("u1", "c1", score=0.9)]
    
    with patch("verba_extensions.plugins.reranker.RerankerPlugin") as MockReranker:
        mock_reranker = MockReranker.return_value
        # Simula erro crítico no Reranker (ex: timeout ou API key inválida)
        mock_reranker.rerank = AsyncMock(side_effect=Exception("Reranker down"))
        
        # O método _execute_cascade_search tem um try/except interno que loga e retorna os chunks originais?
        # Vamos verificar o código. Atualmente ele levanta exceção se o rerank falhar?
        # Olhando o código anterior: "except Exception as e: msg.warn... return chunks"
        
        result = await retriever._execute_cascade_search(chunks, "q", {})
        
        # Deve retornar os chunks originais (fallback)
        assert len(result) == 1
        assert result[0].uuid == "u1"
        assert result[0].metadata.score == 0.9

@pytest.mark.asyncio
async def test_cascade_malformed_metadata_conversion():
    """Verifica se a conversão lida com metadata corrompido"""
    retriever = EntityAwareRetriever()
    
    bad_chunk = MockWeaviateObject("u1", "c1")
    bad_chunk.properties["meta"] = "not a json" # Metadata inválido
    
    with patch("verba_extensions.plugins.reranker.RerankerPlugin") as MockReranker:
        mock_reranker = MockReranker.return_value
        c1 = Chunk(content="c1", chunk_id=1)
        # O reranker costuma limpar ou ignorar meta ruim
        mock_reranker.rerank = AsyncMock(return_value=[c1])
        
        # Não deve explodir no json.loads
        result = await retriever._execute_cascade_search([bad_chunk], "q", {})
        
        assert len(result) == 1
        assert result[0].uuid == "u1"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
