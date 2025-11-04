"""
Testes de integração para features do RAG2
Valida EntityAwareRetriever com todas as features integradas
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
from verba_extensions.plugins.entity_aware_retriever import EntityAwareRetriever
from verba_extensions.plugins.bilingual_filter import BilingualFilterPlugin
from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin
from verba_extensions.plugins.temporal_filter import TemporalFilterPlugin


class TestRAG2FeaturesIntegration(unittest.TestCase):
    
    def setUp(self):
        self.retriever = EntityAwareRetriever()
        self.bilingual_plugin = BilingualFilterPlugin()
        self.temporal_plugin = TemporalFilterPlugin()
    
    def test_config_exists(self):
        """Testa se todas as configs foram adicionadas"""
        self.assertIn("Enable Language Filter", self.retriever.config)
        self.assertIn("Enable Query Rewriting", self.retriever.config)
        self.assertIn("Enable Temporal Filter", self.retriever.config)
        self.assertIn("Date Field Name", self.retriever.config)
    
    def test_bilingual_filter_integration(self):
        """Testa integração do bilingual filter"""
        query_pt = "inovação da Apple"
        query_en = "innovation from Apple"
        
        lang_pt = self.bilingual_plugin.detect_query_language(query_pt)
        lang_en = self.bilingual_plugin.detect_query_language(query_en)
        
        self.assertEqual(lang_pt, "pt")
        self.assertEqual(lang_en, "en")
        
        filter_pt = self.bilingual_plugin.get_language_filter_for_query(query_pt)
        filter_en = self.bilingual_plugin.get_language_filter_for_query(query_en)
        
        self.assertIsNotNone(filter_pt)
        self.assertIsNotNone(filter_en)
    
    def test_temporal_filter_integration(self):
        """Testa integração do temporal filter"""
        query_with_date = "inovação em 2024"
        query_no_date = "inovação da Apple"
        
        date_range = self.temporal_plugin.extract_date_range(query_with_date)
        self.assertIsNotNone(date_range)
        
        date_range_none = self.temporal_plugin.extract_date_range(query_no_date)
        self.assertIsNone(date_range_none)
        
        filter_obj = self.temporal_plugin.get_temporal_filter_for_query(query_with_date)
        self.assertIsNotNone(filter_obj)
    
    def test_query_rewriter_fallback(self):
        """Testa query rewriter com fallback"""
        import asyncio
        rewriter = QueryRewriterPlugin()
        query = "test query"
        
        # Sem generator, deve retornar fallback (async)
        response = asyncio.run(rewriter.rewrite_query(query, use_cache=False))
        
        self.assertIn("semantic_query", response)
        self.assertIn("keyword_query", response)
        self.assertIn("intent", response)
        self.assertIn("alpha", response)
        self.assertEqual(response["semantic_query"], query)
    
    def test_combined_filters(self):
        """Testa combinação de filtros"""
        # Query com entidade + idioma + data
        query = "inovação da Apple em 2024"
        
        # Bilingual filter
        lang_filter = self.bilingual_plugin.get_language_filter_for_query(query)
        self.assertIsNotNone(lang_filter)
        
        # Temporal filter
        temporal_filter = self.temporal_plugin.get_temporal_filter_for_query(query)
        self.assertIsNotNone(temporal_filter)
        
        # Ambos devem estar presentes
        self.assertIsNotNone(lang_filter)
        self.assertIsNotNone(temporal_filter)
    
    def test_config_defaults(self):
        """Testa valores padrão das configs"""
        lang_filter_config = self.retriever.config["Enable Language Filter"]
        self.assertTrue(lang_filter_config.value)
        
        query_rewriting_config = self.retriever.config["Enable Query Rewriting"]
        self.assertFalse(query_rewriting_config.value)  # Default: False
        
        temporal_filter_config = self.retriever.config["Enable Temporal Filter"]
        self.assertTrue(temporal_filter_config.value)
        
        date_field_config = self.retriever.config["Date Field Name"]
        self.assertEqual(date_field_config.value, "chunk_date")
    
    def test_empty_query_handling(self):
        """Testa tratamento de queries vazias"""
        import asyncio
        empty_query = ""
        
        lang = self.bilingual_plugin.detect_query_language(empty_query)
        # Para queries vazias, pode retornar "unknown" ou None
        self.assertIn(lang, ["unknown", None, ""])
        
        date_range = self.temporal_plugin.extract_date_range(empty_query)
        self.assertIsNone(date_range)
        
        rewriter = QueryRewriterPlugin()
        response = asyncio.run(rewriter.rewrite_query(empty_query, use_cache=False))
        # Deve retornar fallback válido mesmo com query vazia
        self.assertIn("semantic_query", response)


if __name__ == "__main__":
    unittest.main()

