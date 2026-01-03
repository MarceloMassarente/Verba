
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch
from verba_extensions.embedders.hybrid_embedder import HybridConsultingEmbedder, MAX_VOYAGE_TOKENS
from goldenverba.components.chunk import Chunk
from goldenverba.components.document import Document

class MockEmbedResult:
    def __init__(self, count, dims=1024):
        self.embeddings = [[0.1] * dims for _ in range(count)]

@pytest.fixture
def embedder():
    with patch("sentence_transformers.SentenceTransformer"), \
         patch("voyageai.Client"):
        emb = HybridConsultingEmbedder()
        emb.voyage_client = MagicMock()
        emb.minilm = MagicMock()
        # Mock minilm.encode behavior
        emb.minilm.encode.return_value = Mock() 
        return emb

@pytest.mark.asyncio
async def test_adaptive_context_levels(embedder):
    """Verifica se o nível de contexto muda conforme o tamanho do chunk"""
    
    doc = Document(text="Full Doc", title="Consulting Strategy 2026", uuid="doc1")
    global_context = {
        "title": "Consulting Strategy 2026",
        "frameworks": ["MECE", "Porter"],
        "companies": ["Apple", "Google"],
        "sectors": ["Tech"]
    }
    
    # 1. SMALL CHUNK (< 20k tokens)
    # 1k tokens ≈ 4000 chars
    small_chunk = Chunk(content="Small content" * 100) # ~1300 chars
    small_chunk.meta = {"frameworks": [], "companies": [], "sectors": []}
    
    text_small = embedder._build_default_text(global_context, small_chunk)
    assert "Frameworks: MECE" in text_small
    assert "Companies" not in text_small # Code uses "Empresas" in PT
    assert "Empresas: Apple" in text_small
    
    # 2. MEDIUM CHUNK (> 20k tokens)
    # 21k tokens ≈ 84,000 chars
    medium_content = "Word " * 17000 # ~85,000 chars
    medium_chunk = Chunk(content=medium_content)
    medium_chunk.meta = {"frameworks": ["F1"], "companies": ["C1"]}
    
    text_medium = embedder._build_default_text(global_context, medium_chunk)
    assert "Frameworks: F1" in text_medium
    assert "Porter" not in text_medium # Reduced context should only contain chunk-specific entities
    assert "Consulting Strategy 2026" in text_medium
    
    # 3. LARGE CHUNK (> 25k tokens)
    # 26k tokens ≈ 104,000 chars
    large_content = "BigWord " * 22000 # ~176,000 chars
    large_chunk = Chunk(content=large_content)
    
    text_large = embedder._build_default_text(global_context, large_chunk)
    assert "Documento: Consulting Strategy 2026" in text_large
    assert "Frameworks" not in text_large # Minimal context
    assert "Empresas" not in text_large

@pytest.mark.asyncio
async def test_truncation_logic(embedder):
    """Verifica se chunks gigantes são truncados antes do envio para API"""
    
    # 35k tokens ≈ 140,000 chars
    huge_content = "START " + ("A" * 150000) + " END"
    embedder.voyage_client.embed.return_value = MockEmbedResult(1)
    
    await embedder.vectorize({}, [huge_content])
    
    # Verifica o que foi enviado para a API
    sent_text = embedder.voyage_client.embed.call_args[1]['texts'][0]
    assert "START" in sent_text
    assert "END" in sent_text
    assert "[... CONTEÚDO TRUNCADO ...]" in sent_text
    assert len(sent_text) <= (MAX_VOYAGE_TOKENS * 4) + 100 

@pytest.mark.asyncio
async def test_multi_vector_dimensions(embedder):
    """Verifica se cada named vector tem a dimensão correta"""
    
    chunk = Chunk(content="Test content")
    chunk.doc_uuid = "doc1"
    chunk.meta = {}
    doc = Document(text="Test", title="Test Doc", uuid="doc1")
    
    # Mock behavior for local/voyage
    embedder.voyage_client.embed.return_value = MockEmbedResult(1, 1024)
    # Mock minilm.encode to return 384d list
    embedder.minilm.encode.return_value = [[0.1] * 384]
    
    results = await embedder.vectorize_with_named_vectors([chunk], [doc])
    
    assert len(results["default"][0]) == 1024
    assert len(results["concept_vec"][0]) == 384
    assert len(results["company_vec"][0]) == 384
    assert len(results["sector_vec"][0]) == 384

@pytest.mark.asyncio
async def test_voyage_batching(embedder):
    """Verifica se o processamento por batch (128) funciona"""
    
    many_texts = ["test"] * 150 # > 128
    embedder.voyage_client.embed.side_effect = [
        MockEmbedResult(128),
        MockEmbedResult(22)
    ]
    
    results = await embedder._embed_voyage_batch(many_texts)
    
    assert len(results) == 150
    assert embedder.voyage_client.embed.call_count == 2

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
