"""
Testes unitários para QueryRewriterPlugin
"""

import unittest
from unittest.mock import Mock, patch
from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin


class TestQueryRewriterPlugin(unittest.TestCase):
    
    def setUp(self):
        self.plugin = QueryRewriterPlugin(cache_ttl_seconds=3600)
    
    def test_fallback_response(self):
        """Testa resposta de fallback"""
        query = "test query"
        response = self.plugin._fallback_response(query)
        
        self.assertIn("semantic_query", response)
        self.assertIn("keyword_query", response)
        self.assertIn("intent", response)
        self.assertIn("alpha", response)
        self.assertEqual(response["semantic_query"], query)
        self.assertEqual(response["keyword_query"], query)
        self.assertEqual(response["intent"], "search")
        self.assertEqual(response["alpha"], 0.6)
    
    def test_validate_strategy_valid(self):
        """Testa validação de estratégia válida"""
        strategy = {
            "semantic_query": "expanded query",
            "keyword_query": "keywords",
            "intent": "search",
            "filters": {},
            "alpha": 0.6
        }
        self.assertTrue(self.plugin._validate_strategy(strategy))
    
    def test_validate_strategy_invalid_missing_field(self):
        """Testa validação de estratégia com campo faltando"""
        strategy = {
            "semantic_query": "expanded query",
            # Missing keyword_query
            "intent": "search",
            "alpha": 0.6
        }
        self.assertFalse(self.plugin._validate_strategy(strategy))
    
    def test_validate_strategy_invalid_intent(self):
        """Testa validação de estratégia com intent inválido"""
        strategy = {
            "semantic_query": "expanded query",
            "keyword_query": "keywords",
            "intent": "invalid_intent",
            "filters": {},
            "alpha": 0.6
        }
        self.assertFalse(self.plugin._validate_strategy(strategy))
    
    def test_validate_strategy_invalid_alpha(self):
        """Testa validação de estratégia com alpha inválido"""
        strategy = {
            "semantic_query": "expanded query",
            "keyword_query": "keywords",
            "intent": "search",
            "filters": {},
            "alpha": 1.5  # Invalid: > 1.0
        }
        self.assertFalse(self.plugin._validate_strategy(strategy))
    
    def test_cache_stats(self):
        """Testa estatísticas do cache"""
        stats = self.plugin.get_cache_stats()
        self.assertIn("total_entries", stats)
        self.assertIn("valid_entries", stats)
        self.assertIn("expired_entries", stats)
        self.assertIn("cache_ttl_seconds", stats)
    
    def test_clear_cache(self):
        """Testa limpeza do cache"""
        # Adiciona algo ao cache
        self.plugin.cache["test"] = ({"semantic_query": "test"}, 1000)
        self.assertEqual(len(self.plugin.cache), 1)
        
        # Limpa cache
        self.plugin.clear_cache()
        self.assertEqual(len(self.plugin.cache), 0)
    
    @patch('verba_extensions.plugins.query_rewriter.QueryRewriterPlugin._get_generator')
    def test_rewrite_query_without_generator(self, mock_get_generator):
        """Testa reescrita sem generator disponível"""
        mock_get_generator.return_value = None
        
        query = "test query"
        response = self.plugin.rewrite_query(query, use_cache=False)
        
        # Deve retornar fallback
        self.assertEqual(response["semantic_query"], query)
        self.assertEqual(response["intent"], "search")


if __name__ == "__main__":
    unittest.main()

