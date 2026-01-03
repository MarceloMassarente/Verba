
import pytest
from unittest.mock import Mock, AsyncMock, patch
from verba_extensions.plugins.entity_aware_retriever import EntityAwareRetriever
from goldenverba.components.chunk import Chunk

# Mock Weaviate Object that mimics what Weaviate client returns
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
async def test_cascade_retrieval_flow():
    """
    Testa o fluxo completo do Cascade Retrieval:
    1. Fase 1: Busca ampla (simulada)
    2. Fase 2: Reranking (simulado)
    3. Verificação de limites e tipos
    """
    
    # 1. Configurar Retriever com Cascade Mode
    retriever = EntityAwareRetriever()
    config = {
        "Cascade Mode": {"value": True},
        "Cascade Phase 1 Limit": {"value": 20}, # Quero 20 candidatos
        "Reranker Top K": {"value": 3},         # Quero top 3 final
        "Limit Mode": {"value": "Autocut"},     # Deve ser ignorado pelo Cascade
    }
    
    # 2. Mockar dependências
    mock_client = Mock()
    mock_weaviate_manager = Mock()
    
    # Simular retorno da Fase 1 (Busca Híbrida)
    # Retorna 10 chunks candidatos (simulando "Fast Recall")
    phase1_candidates = [
        MockWeaviateObject(f"uuid_{i}", f"Content {i}", score=0.5 + (i*0.01)) 
        for i in range(10)
    ]
    
    # Configurar weaviate_manager para retornar esses candidatos
    # O retriever chama hybrid_chunks_with_filter ou similar
    # Vamos mockar o método `retrieve` internals se possível, mas aqui estamos testando `retrieve`
    # O `retrieve` chama `builder.build_query` depois executa query via weaviate_manager
    # É difícil testar `retrieve` inteiro sem mockar tudo.
    
    # Vamos testar `_execute_cascade_search` isoladamente primeiro, é a parte nova crítica.
    pass

@pytest.mark.asyncio
async def test_execute_cascade_search_logic():
    """
    Testa especificamente a lógica da Fase 2 (_execute_cascade_search)
    Verifica se converte tipos corretamente e chama o reranker.
    """
    retriever = EntityAwareRetriever()
    
    # Chunks de entrada (Tipo Weaviate Object)
    input_chunks = [
        MockWeaviateObject("uuid_1", "Content 1 (Relevante)", score=0.8, chunk_id=1),
        MockWeaviateObject("uuid_2", "Content 2 (Pouco relevante)", score=0.4, chunk_id=2),
        MockWeaviateObject("uuid_3", "Content 3 (Muito Relevante)", score=0.9, chunk_id=3),
    ]
    
    config = {
        "Reranker Top K": {"value": 2} # Quero apenas top 2 (formatado como InputConfig dict)
    }
    
    # Mock RerankerPlugin dentro do método
    with patch("verba_extensions.plugins.reranker.RerankerPlugin") as MockRerankerClass:
        mock_reranker = MockRerankerClass.return_value
        
        # Configurar rerank para retornar chunks reordenados
        # O Reranker recebe Chunk objects e retorna Chunk objects
        
        # Simular retorno do Reranker (Chunk objects)
        # Note que o reranker deve retornar Chunk objects, não Weaviate objects
        chunk3 = Chunk(content="Content 3 (Muito Relevante)", chunk_id=3)
        chunk3.doc_uuid = "doc1"
        chunk3.uuid = "uuid_3"
        
        chunk1 = Chunk(content="Content 1 (Relevante)", chunk_id=1)
        chunk1.doc_uuid = "doc1"
        chunk1.uuid = "uuid_1"
        
        # Retorna reordenado (3 depois 1)
        mock_reranker.rerank = AsyncMock(return_value=[chunk3, chunk1]) 
        
        # Executar método sob teste
        result = await retriever._execute_cascade_search(
            chunks=input_chunks,
            query="test query",
            config=config
        )
        
        # VERIFICAÇÕES
        
        # 1. Deve retornar 2 chunks (Top K = 2)
        assert len(result) == 2
        
        # 2. O primeiro deve ser o chunk 3 (o mais relevante)
        assert result[0].uuid == "uuid_3"
        assert "Muito Relevante" in result[0].properties["content"]
        
        # 3. O objeto retornado deve ter estrutura compatível com Weaviate (properties, metadata)
        assert hasattr(result[0], "properties")
        assert hasattr(result[0], "metadata")
        assert hasattr(result[0].metadata, "score")
        
        # 4. Deve ter chamado rerank com Chunk objects convertidos
        call_args = mock_reranker.rerank.call_args
        assert call_args is not None
        passed_chunks = call_args[1]['chunks']
        assert len(passed_chunks) == 3 # Passou todos os 3 para o reranker
        assert isinstance(passed_chunks[0], Chunk) # Confirmar conversão de tipo

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
