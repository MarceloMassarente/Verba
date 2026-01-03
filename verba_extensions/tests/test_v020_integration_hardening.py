
import pytest
import json
from verba_extensions.readers.unified_consulting_ingestor import UnifiedConsultingIngestor
from verba_extensions.plugins.unified_chunker_plugin import UnifiedSemanticChunker
from goldenverba.server.types import FileConfig

@pytest.mark.asyncio
async def test_ingestor_chunker_integration():
    """
    Verifica se o Chunker consome corretamente o que o Ingestor produz (V019).
    """
    ingestor = UnifiedConsultingIngestor()
    chunker = UnifiedSemanticChunker()
    
    # 1. Ingestão (Mock Markdown)
    markdown = """# Slide 1 - Strategic Analysis
Analysis content for BCG Matrix.
**Frameworks Deste Slide:** BCG Matrix, SWOT
**Stakeholders Deste Slide:** Microsoft
**Qualidade da Ponte:** 0.90
**Posição:** analysis
**Arquétipo Visual:** matrix
---
# Slide 2 - Implementation
Next steps.
**Frameworks Deste Slide:** 7S
**Stakeholders Deste Slide:** McKinsey
---"""
    
    file_config = FileConfig(
        filename="strategy.md",
        content=markdown,
        extension="md"
    )
    
    documents = await ingestor.load({}, file_config)
    assert len(documents) == 1
    doc = documents[0]
    
    # 2. Chunking
    # O chunker extrai metadata do meta do documento (JSON string) e do texto.
    chunks = await chunker.chunk([doc])
    
    assert len(chunks) >= 2
    
    # 3. Verificação do Primeiro Chunk
    chunk1 = chunks[0]
    assert "BCG Matrix" in chunk1.meta.get("frameworks", [])
    assert "SWOT" in chunk1.meta.get("frameworks", [])
    assert "Microsoft" in chunk1.meta.get("companies", [])
    assert chunk1.meta.get("visual_archetype") == "matrix"
    assert chunk1.meta.get("slide_title") == "Strategic Analysis"
    
    # 4. Verificação do Segundo Chunk
    chunk2 = chunks[-1] # Pega o ultimo slide
    assert "7S" in chunk2.meta.get("frameworks", [])
    assert "McKinsey" in chunk2.meta.get("companies", [])
    assert "Implementation" in chunk2.meta.get("slide_title")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
