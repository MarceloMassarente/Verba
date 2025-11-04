"""
Testes para LLMMetadataExtractor Plugin
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pydantic import ValidationError

from goldenverba.components.types import Chunk
from verba_extensions.plugins.llm_metadata_extractor import (
    LLMMetadataExtractorPlugin,
    EnrichedMetadata,
    EntityRelationship,
    create_llm_metadata_extractor
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_chunk():
    """Cria um chunk de amostra para testes."""
    return Chunk(
        uuid="test-chunk-1",
        content="Apple investe bilhões em inteligência artificial. Microsoft também lidera neste setor.",
        meta={"source": "test"}
    )


@pytest.fixture
def plugin():
    """Cria instância do plugin para testes."""
    return LLMMetadataExtractorPlugin()


# ============================================================================
# TESTES DO SCHEMA PYDANTIC
# ============================================================================

class TestEnrichedMetadataSchema:
    """Testes do schema EnrichedMetadata."""
    
    def test_valid_metadata(self):
        """Testa criação de metadata válido."""
        metadata = EnrichedMetadata(
            companies=["Apple", "Microsoft"],
            key_topics=["AI", "Innovation"],
            sentiment="positive",
            summary="Test summary",
            confidence_score=0.95,
            keywords=["apple", "ai"]
        )
        
        assert metadata.companies == ["Apple", "Microsoft"]
        assert metadata.sentiment == "positive"
        assert metadata.confidence_score == 0.95
    
    def test_default_values(self):
        """Testa valores padrão do schema."""
        metadata = EnrichedMetadata()
        
        assert metadata.companies == []
        assert metadata.key_topics == []
        assert metadata.sentiment == "neutral"
        assert metadata.confidence_score == 0.8
    
    def test_entity_relationship(self):
        """Testa schema de relação entre entidades."""
        rel = EntityRelationship(
            entity="Microsoft",
            relationship_type="competitor"
        )
        
        assert rel.entity == "Microsoft"
        assert rel.relationship_type == "competitor"
        assert rel.confidence == 0.8
    
    def test_confidence_validation(self):
        """Testa validação de confidence score."""
        # Deve aceitar valores 0-1
        metadata = EnrichedMetadata(confidence_score=0.5)
        assert metadata.confidence_score == 0.5
        
        # Deve rejeitar valores fora do range
        with pytest.raises(ValidationError):
            EnrichedMetadata(confidence_score=1.5)


# ============================================================================
# TESTES DO PLUGIN
# ============================================================================

class TestLLMMetadataExtractorPlugin:
    """Testes da classe principal do plugin."""
    
    def test_plugin_init(self):
        """Testa inicialização do plugin."""
        plugin = LLMMetadataExtractorPlugin()
        
        assert plugin.name == "LLMMetadataExtractor"
        assert plugin.installed == True
        assert isinstance(plugin.extraction_cache, dict)
        assert plugin.batch_size == 5
    
    def test_plugin_config(self, plugin):
        """Testa obtenção de configuração."""
        config = plugin.get_config()
        
        assert config["name"] == "LLMMetadataExtractor"
        assert "cache_size" in config
        assert "has_llm" in config
    
    def test_plugin_install(self, plugin):
        """Testa instalação do plugin."""
        plugin.installed = False
        result = plugin.install()
        
        assert result == True
        assert plugin.installed == True
    
    def test_plugin_uninstall(self, plugin):
        """Testa desinstalação do plugin."""
        plugin.extraction_cache["test"] = {"data": "value"}
        result = plugin.uninstall()
        
        assert result == True
        assert plugin.installed == False
        assert len(plugin.extraction_cache) == 0


# ============================================================================
# TESTES DE PROCESSAMENTO
# ============================================================================

class TestChunkProcessing:
    """Testes de processamento de chunks."""
    
    @pytest.mark.asyncio
    async def test_process_chunk_without_llm(self, plugin, sample_chunk):
        """Testa processamento sem LLM disponível."""
        plugin.has_llm = False
        
        result = await plugin.process_chunk(sample_chunk)
        
        assert result.uuid == sample_chunk.uuid
        # Sem LLM, não deve ter enriquecimento
        assert "enriched" not in result.meta or result.meta.get("enriched") is None
    
    @pytest.mark.asyncio
    async def test_process_chunk_with_cache_hit(self, plugin, sample_chunk):
        """Testa cache hit no processamento."""
        plugin.has_llm = True
        cache_key = plugin._get_cache_key(sample_chunk.content)
        cached_metadata = {"companies": ["Cached"]}
        plugin.extraction_cache[cache_key] = cached_metadata
        
        result = await plugin.process_chunk(sample_chunk)
        
        assert result.meta["enriched"] == cached_metadata
    
    @pytest.mark.asyncio
    async def test_process_batch(self, plugin):
        """Testa processamento em lote."""
        plugin.has_llm = False  # Simula sem LLM para não fazer chamadas reais
        
        chunks = [
            Chunk(uuid=f"chunk-{i}", content=f"Content {i}", meta={})
            for i in range(3)
        ]
        
        results = await plugin.process_batch(chunks)
        
        assert len(results) == 3
        assert all(isinstance(r, Chunk) for r in results)


# ============================================================================
# TESTES DE PROMPT E PARSING
# ============================================================================

class TestPromptBuilding:
    """Testes de construção de prompts."""
    
    def test_build_extraction_prompt(self, plugin):
        """Testa construção do prompt de extração."""
        text = "Apple investe em AI"
        prompt = plugin._build_extraction_prompt(text)
        
        assert "Apple investe em AI" in prompt
        assert "JSON" in prompt
        assert "companies" in prompt
        assert "key_topics" in prompt
    
    def test_build_extraction_prompt_handles_special_chars(self, plugin):
        """Testa prompt com caracteres especiais."""
        text = 'Text with "quotes" and \\escapes'
        prompt = plugin._build_extraction_prompt(text)
        
        # Deve não falhar e incluir o texto
        assert len(prompt) > 0


# ============================================================================
# TESTES DE PARSING DE RESPONSE
# ============================================================================

class TestResponseParsing:
    """Testes de parsing de respostas do LLM."""
    
    def test_parse_valid_json(self, plugin):
        """Testa parsing de JSON válido."""
        response = """{
            "companies": ["Apple", "Microsoft"],
            "key_topics": ["AI"],
            "sentiment": "positive",
            "summary": "Test",
            "confidence_score": 0.9,
            "keywords": ["ai"]
        }"""
        
        result = plugin._parse_extraction_response(response)
        
        assert result["companies"] == ["Apple", "Microsoft"]
        assert result["sentiment"] == "positive"
    
    def test_parse_json_with_extra_text(self, plugin):
        """Testa parsing com texto extra ao redor do JSON."""
        response = """Some explanation text
        {
            "companies": ["Apple"],
            "key_topics": [],
            "sentiment": "neutral",
            "summary": "",
            "confidence_score": 0.8,
            "keywords": []
        }
        More text after"""
        
        result = plugin._parse_extraction_response(response)
        
        assert result["companies"] == ["Apple"]
    
    def test_parse_invalid_json(self, plugin):
        """Testa parsing com JSON inválido."""
        response = "This is not JSON at all"
        
        with pytest.raises(Exception):
            plugin._parse_extraction_response(response)


# ============================================================================
# TESTES DE CACHE
# ============================================================================

class TestCaching:
    """Testes do sistema de cache."""
    
    def test_get_cache_key(self, plugin):
        """Testa geração de chave de cache."""
        text = "Test content"
        key1 = plugin._get_cache_key(text)
        key2 = plugin._get_cache_key(text)
        
        # Mesmo texto deve gerar mesma chave
        assert key1 == key2
        
        # Textos diferentes devem gerar chaves diferentes
        key3 = plugin._get_cache_key("Different content")
        assert key1 != key3
    
    def test_cache_hit_multiple_calls(self, plugin):
        """Testa que o cache funciona em múltiplas chamadas."""
        text = "Test content"
        key = plugin._get_cache_key(text)
        
        # Adiciona ao cache
        plugin.extraction_cache[key] = {"companies": ["Test"]}
        
        # Deve encontrar no cache
        assert key in plugin.extraction_cache
        assert plugin.extraction_cache[key]["companies"] == ["Test"]


# ============================================================================
# TESTES DE FACTORY
# ============================================================================

class TestFactory:
    """Testes da função factory."""
    
    def test_create_plugin(self):
        """Testa criação de plugin via factory."""
        plugin = create_llm_metadata_extractor()
        
        assert isinstance(plugin, LLMMetadataExtractorPlugin)
        assert plugin.name == "LLMMetadataExtractor"


# ============================================================================
# TESTES DE INTEGRAÇÃO
# ============================================================================

class TestIntegration:
    """Testes de integração."""
    
    @pytest.mark.asyncio
    async def test_full_processing_flow_no_llm(self, plugin, sample_chunk):
        """Testa fluxo completo sem LLM."""
        plugin.has_llm = False
        
        result = await plugin.process_chunk(sample_chunk)
        
        assert result.uuid == sample_chunk.uuid
        assert result.content == sample_chunk.content
    
    def test_plugin_lifecycle(self):
        """Testa ciclo completo do plugin."""
        plugin = LLMMetadataExtractorPlugin()
        
        # Initial state
        assert plugin.installed == True
        
        # Uninstall
        assert plugin.uninstall() == True
        assert plugin.installed == False
        
        # Reinstall
        assert plugin.install() == True
        assert plugin.installed == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
