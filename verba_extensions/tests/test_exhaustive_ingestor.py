
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from verba_extensions.readers.unified_consulting_ingestor import UnifiedConsultingIngestor
from goldenverba.server.types import FileConfig

@pytest.fixture
def ingestor():
    return UnifiedConsultingIngestor()

@pytest.mark.asyncio
async def test_ingestor_routing_markdown(ingestor):
    """Verifica se arquivos .md são roteados para o caminho direto"""
    file_config = FileConfig(
        filename="test.md",
        content="# Slide 1 - Title\nContent\n**Frameworks Deste Slide:** SWOT\n---",
        extension="md"
    )
    
    # Processa
    results = await ingestor.load({}, file_config)
    
    assert len(results) == 1
    doc = results[0]
    assert doc.reader == "Unified Consulting Ingestor"
    assert "SWOT" in doc.meta # meta is json string
    meta = json.loads(doc.meta)
    assert meta["slide_count"] == 1
    assert "SWOT" in meta["all_frameworks"]

@pytest.mark.asyncio
async def test_ingestor_routing_pptx_visual_off(ingestor):
    """Verifica se .pptx usa Docling quando Visual Analysis está OFF"""
    file_config = FileConfig(
        filename="test.pptx",
        content=b"fake binary",
        extension="pptx"
    )
    config = {"Enable Visual Analysis": {"value": False}}
    
    with patch.object(ingestor, "_extract_text_with_docling", new_callable=AsyncMock) as mock_docling:
        mock_docling.return_value = {
            "slides": [{"number": 1, "title": "Docling Slide", "content": "Text"}]
        }
        
        results = await ingestor.load(config, file_config)
        
        assert len(results) == 1
        assert "Docling Slide" in results[0].text
        mock_docling.assert_called_once()

@pytest.mark.asyncio
async def test_ingestor_routing_pdf_visual_on(ingestor):
    """Verifica se .pdf usa Visual API quando habilitado"""
    file_config = FileConfig(
        filename="test.pdf",
        content=b"fake binary",
        extension="pdf"
    )
    config = {
        "Enable Visual Analysis": {"value": True},
        "Visual API Provider": {"value": "Contextual.AI"}
    }
    
    # Vamos mockar o _call_visual_api diretamente
    with patch.object(ingestor, "_call_visual_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = {
            "slides": [{"number": 1, "title": "Visual Slide", "content": "Analysis"}]
        }
        
        results = await ingestor.load(config, file_config)
        
        assert len(results) == 1
        assert "Visual Slide" in results[0].text
        mock_api.assert_called_once()

@pytest.mark.asyncio
async def test_ingestor_framework_detection_regex(ingestor):
    """Verifica detecção de frameworks via regex (fallback do Docling)"""
    docling_raw = {
        "slides": [
            {"number": 1, "title": "Market", "content": "Using BCG matrix for analysis"}
        ]
    }
    
    result = ingestor._detect_frameworks_regex(docling_raw)
    assert "BCG Matrix" in result["slides"][0]["frameworks"]

@pytest.mark.asyncio
async def test_ingestor_metadata_v019_parsing(ingestor):
    """Verifica se o parser de markdown extrai corretamente os campos V019"""
    markdown = """# Slide 1 - Strategy
Content here
**Frameworks Deste Slide:** MECE, Porter
**Stakeholders Deste Slide:** Apple, Google
**Qualidade da Ponte:** 0.85
**Posição:** analysis
**Arquétipo Visual:** pyramid
---"""
    
    metadata = ingestor._extract_slides_metadata_v019(markdown)
    assert len(metadata) == 1
    slide = metadata[0]
    assert slide["slide_title"] == "Strategy"
    assert "MECE" in slide["frameworks"]
    assert "Apple" in slide["companies"]
    assert slide["semantic_bridge_quality"] == 0.85
    assert slide["position"] == "analysis"
    assert slide["visual_archetype"] == "pyramid"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
