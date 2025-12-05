"""
Teste de Integração: Named Vectors Pipeline

Valida que o fluxo completo funciona:
1. EntitySemanticChunker extrai companies para chunk.meta
2. VectorExtractor usa chunk.meta.companies para company_text
3. EntityAwareRetriever pode usar named vectors

Este teste NÃO requer conexão com Weaviate - testa apenas a lógica Python.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

# ============================================================================
# TESTE 1: EntitySemanticChunker extrai companies
# ============================================================================

def test_extract_companies_from_entity_spans():
    """Verifica que _extract_companies_from_spans extrai ORGs corretamente."""
    from verba_extensions.plugins.entity_semantic_chunker import _extract_companies_from_spans
    
    spans = [
        {"text": "Apple", "label": "ORG", "start": 0, "end": 5},
        {"text": "Microsoft", "label": "ORG", "start": 10, "end": 19},
        {"text": "Steve Jobs", "label": "PERSON", "start": 25, "end": 35},
        {"text": "Google", "label": "ORG", "start": 40, "end": 46},
    ]
    
    companies = _extract_companies_from_spans(spans)
    
    # Deve extrair apenas ORGs e normalizar para lowercase
    assert "apple" in companies
    assert "microsoft" in companies
    assert "google" in companies
    # PERSON não deve estar incluído
    assert "steve jobs" not in companies
    assert "Steve Jobs" not in companies


def test_extract_companies_handles_empty():
    """Verifica que _extract_companies_from_spans lida com lista vazia."""
    from verba_extensions.plugins.entity_semantic_chunker import _extract_companies_from_spans
    
    companies = _extract_companies_from_spans([])
    assert companies == []
    
    companies = _extract_companies_from_spans(None)
    assert companies == []


# ============================================================================
# TESTE 2: VectorExtractor usa chunk.meta.companies
# ============================================================================

def test_vector_extractor_uses_companies_meta():
    """Verifica que VectorExtractor extrai company_text do meta."""
    from verba_extensions.utils.vector_extractor import VectorExtractor
    
    extractor = VectorExtractor()
    
    # Simular chunk com meta.companies
    chunk = MagicMock()
    chunk.content = "This document discusses innovation strategies."
    chunk.meta = {
        "companies": ["apple", "microsoft"],
        "sectors": ["technology"],
        "frameworks": ["SWOT"]
    }
    
    # Extrair textos
    texts = extractor.extract_all_texts(chunk)
    
    # company_text deve conter as empresas + conteúdo base
    assert "apple" in texts["company_text"]
    assert "microsoft" in texts["company_text"]
    assert "innovation strategies" in texts["company_text"]
    
    # sector_text deve conter setores
    assert "technology" in texts["sector_text"]
    
    # concept_text deve conter frameworks
    assert "SWOT" in texts["concept_text"]


def test_vector_extractor_handles_missing_meta():
    """Verifica que VectorExtractor lida com chunk sem meta."""
    from verba_extensions.utils.vector_extractor import VectorExtractor
    
    extractor = VectorExtractor()
    
    # Chunk sem meta
    chunk = MagicMock()
    chunk.content = "Some content without metadata."
    chunk.meta = None
    
    texts = extractor.extract_all_texts(chunk)
    
    # Deve retornar apenas o conteúdo base
    assert texts["company_text"] == "Some content without metadata."
    assert texts["sector_text"] == "Some content without metadata."
    assert texts["concept_text"] == "Some content without metadata."


def test_vector_extractor_singleton():
    """Verifica que get_vector_extractor retorna singleton."""
    from verba_extensions.utils.vector_extractor import get_vector_extractor
    
    extractor1 = get_vector_extractor()
    extractor2 = get_vector_extractor()
    
    assert extractor1 is extractor2


# ============================================================================
# TESTE 3: EntityAwareRetriever config validation
# ============================================================================

def test_entity_aware_retriever_has_multi_vector_config():
    """Verifica que EntityAwareRetriever tem config de multi-vector."""
    from verba_extensions.plugins.entity_aware_retriever import EntityAwareRetriever
    
    retriever = EntityAwareRetriever()
    
    # Deve ter config de multi-vector
    assert "Enable Multi-Vector Search" in retriever.config
    
    # Descrição deve mencionar named vectors
    config = retriever.config["Enable Multi-Vector Search"]
    assert "concept_vec" in config.description or "named vector" in config.description.lower()


def test_entity_aware_retriever_has_entity_filter():
    """Verifica que EntityAwareRetriever tem config de entity filter."""
    from verba_extensions.plugins.entity_aware_retriever import EntityAwareRetriever
    
    retriever = EntityAwareRetriever()
    
    # Deve ter configs de entity filtering
    assert "Enable Entity Filter" in retriever.config
    assert "Entity Filter Mode" in retriever.config


# ============================================================================
# TESTE 4: Merge de chunks pequenos
# ============================================================================

def test_merge_small_chunks():
    """Verifica que _merge_small_chunks funciona corretamente."""
    from verba_extensions.plugins.entity_semantic_chunker import _merge_small_chunks
    from goldenverba.components.chunk import Chunk
    
    # Criar chunks de teste
    chunks = [
        Chunk(content="First chunk with enough content to not be merged.", chunk_id=0, start_i=0, end_i=50),
        Chunk(content="Tiny.", chunk_id=1, start_i=51, end_i=56),  # Muito pequeno
        Chunk(content="Another small chunk that should be merged.", chunk_id=2, start_i=57, end_i=100),
    ]
    
    # Mínimo de 100 chars
    merged = _merge_small_chunks(chunks, min_chars=100)
    
    # O chunk "Tiny." deve ter sido mesclado com o anterior
    assert len(merged) < len(chunks)


def test_merge_small_chunks_preserves_companies():
    """Verifica que _merge_small_chunks preserva metadata de companies."""
    from verba_extensions.plugins.entity_semantic_chunker import _merge_small_chunks
    from goldenverba.components.chunk import Chunk
    
    # Criar chunks com metadata
    chunk1 = Chunk(content="First chunk about Apple innovations.", chunk_id=0, start_i=0, end_i=40)
    chunk1.meta = {"companies": ["apple"]}
    
    chunk2 = Chunk(content="Short.", chunk_id=1, start_i=41, end_i=47)
    chunk2.meta = {"companies": ["microsoft"]}
    
    merged = _merge_small_chunks([chunk1, chunk2], min_chars=50)
    
    # Se mesclados, deve preservar ambas as empresas
    if len(merged) == 1:
        assert "apple" in merged[0].meta.get("companies", [])
        assert "microsoft" in merged[0].meta.get("companies", [])


# ============================================================================
# TESTE 5: Frequent entities detection
# ============================================================================

def test_get_frequent_entities():
    """Verifica que _get_frequent_entities identifica entidades repetidas."""
    from verba_extensions.plugins.entity_semantic_chunker import _get_frequent_entities
    
    spans = [
        {"text": "Apple", "label": "ORG"},
        {"text": "apple", "label": "ORG"},  # Mesmo que Apple (lowercase)
        {"text": "Microsoft", "label": "ORG"},  # Apenas 1x
        {"text": "Google", "label": "ORG"},
        {"text": "google", "label": "ORG"},  # Mesmo que Google
        {"text": "Steve Jobs", "label": "PERSON"},
    ]
    
    # Com min_frequency=2, deve retornar apple e google
    frequent = _get_frequent_entities(spans, min_frequency=2)
    
    assert "apple" in frequent
    assert "google" in frequent
    assert "microsoft" not in frequent  # Apenas 1x


# ============================================================================
# TESTE 6: System prompt atualizado
# ============================================================================

def test_generator_system_prompt_mentions_named_vectors():
    """Verifica que o system prompt menciona capacidades de named vectors."""
    from goldenverba.components.interfaces import Generator
    
    # Criar instância mock para acessar config
    class TestGenerator(Generator):
        async def generate_stream(self, queries, context, conversation=None):
            pass
        def prepare_messages(self, queries, context, conversation):
            pass
    
    generator = TestGenerator()
    
    system_message = generator.config["System Message"].value
    
    # Deve mencionar named vectors e capacidades
    assert "concept_vec" in system_message or "company_vec" in system_message or "named vector" in system_message.lower()
    assert "company" in system_message.lower() or "empresa" in system_message.lower()
    assert "semantic" in system_message.lower() or "semântic" in system_message.lower()


# ============================================================================
# TESTE 7: Normalize company function
# ============================================================================

def test_normalize_company():
    """Verifica que _normalize_company normaliza nomes."""
    from verba_extensions.plugins.entity_semantic_chunker import _normalize_company
    
    # Deve retornar pelo menos o nome normalizado (lowercase)
    variants = _normalize_company("Apple Inc.")
    assert any("apple" in v for v in variants)
    
    # Deve lidar com string vazia
    variants = _normalize_company("")
    assert variants == [] or variants == [""]
    
    # Deve lidar com espaços
    variants = _normalize_company("  Microsoft  ")
    assert any("microsoft" in v for v in variants)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

