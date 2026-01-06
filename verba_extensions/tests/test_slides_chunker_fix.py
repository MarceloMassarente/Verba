
import pytest
from goldenverba.components.document import Document
from verba_extensions.plugins.slides_semantica_visual_chunker import SlidesSemanticaVisualChunker

class MockConfig:
    def get(self, key, default=None):
        return {"value": True}

@pytest.mark.asyncio
async def test_extract_slide_content_v019_format():
    """
    Testa se o chunker consegue extrair slides no formato V019 gerado pelo Reader.
    Formato problemático: "# Slide X - Titulo\nConteudo" (sem linha vazia entre titulo e conteudo as vezes, ou regex falhando no $)
    """
    chunker = SlidesSemanticaVisualChunker()
    chunker.config = MockConfig()
    
    # Simula output do UnifiedConsultingIngestor
    # Note: O Reader gera "# Slide 1 - Titulo\n\nConteudo..."
    markdown_content = """# Slide 1 - Apresentação institucional

São Paulo, agosto de 2024
Introdução à Mirow & Co.

**Posição:** opening

---

# Slide 2 - Quem somos

Somos uma consultoria estratégica.

**Frameworks Deste Slide:** SWOT
**Stakeholders Deste Slide:** Apple, Google

---
"""
    
    document = Document(
        title="Test PPTX",
        content=markdown_content,
        extension="pptx",
        fileSize=1024,
        source="test.pptx",
        meta={
            "slides_metadata": [
                {"slide_number": 1, "slide_title": "Apresentação institucional"},
                {"slide_number": 2, "slide_title": "Quem somos"}
            ]
        }
    )
    
    # Tenta extrair slide 1
    content1 = chunker._extract_slide_content(markdown_content, 1, "Apresentação institucional")
    print(f"DEBUG: Content 1 extracted: '{content1}'")
    
    # A falha atual retorna string vazia
    assert content1.strip() != "", "Falha: Conteúdo do slide 1 não foi extraído (regex falhou)"
    assert "Introdução à Mirow" in content1
    
    # Tenta extrair slide 2
    content2 = chunker._extract_slide_content(markdown_content, 2, "Quem somos")
    print(f"DEBUG: Content 2 extracted: '{content2}'")
    
    assert content2.strip() != "", "Falha: Conteúdo do slide 2 não foi extraído"
    assert "Somos uma consultoria" in content2

@pytest.mark.asyncio
async def test_chunk_slides_aware_flow():
    """Testa o fluxo completo de chunking com o documento mockado"""
    chunker = SlidesSemanticaVisualChunker()
    chunker.config = MockConfig()
    
    markdown_content = """# Slide 1 - Intro

Texto do slide 1. Este texto precisa ser longo o suficiente para não ser considerado um chunk pequeno e ser mesclado com o anterior. Então vamos adicionar mais palavras aqui para garantir que tenha mais de 100 caracteres.

---

# Slide 2 - Contexto

Texto do slide 2. Tambem precisa ser longo. O chunker tem uma logica de merge que junta chunks com menos de 100 chars. Isso e otimo na pratica mas atrapalha o teste se usarmos textos curtos demais. Agora deve funcionar.
"""
    
    document = Document(
        title="Full Flow Test",
        content=markdown_content,
        extension="pptx",
        fileSize=100,
        source="flow.pptx",
        meta={
            "slides_metadata": [
                {"slide_number": 1, "slide_title": "Intro"},
                {"slide_number": 2, "slide_title": "Contexto"}
            ]
        }
    )

    # Executa chunking
    # Mocking msg to avoid spam output if needed, but wasabi is usually fine
    chunked_doc = chunker._chunk_slides_aware(document)
    
    # Verifica se gerou chunks
    print(f"DEBUG: Total chunks generated: {len(chunked_doc.chunks)}")
    
    # Deve ter pelo menos 2 chunks de slides (mais possivelmente 1 summary)
    assert len(chunked_doc.chunks) >= 2, f"Esperado >= 2 chunks, recebeu {len(chunked_doc.chunks)}"
    
    # Verifica conteúdo
    chunk_contents = [c.content for c in chunked_doc.chunks]
    assert any("Texto do slide 1" in c for c in chunk_contents)
    assert any("Texto do slide 2" in c for c in chunk_contents)
