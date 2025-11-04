"""
Testes unitários para BilingualFilterPlugin
"""

import unittest
from verba_extensions.plugins.bilingual_filter import BilingualFilterPlugin


class TestBilingualFilterPlugin(unittest.TestCase):
    
    def setUp(self):
        self.plugin = BilingualFilterPlugin()
    
    def test_detect_portuguese(self):
        """Testa detecção de português"""
        query = "inovação da Apple"
        lang = self.plugin.detect_query_language(query)
        self.assertEqual(lang, "pt")
    
    def test_detect_english(self):
        """Testa detecção de inglês"""
        query = "innovation from Apple"
        lang = self.plugin.detect_query_language(query)
        self.assertEqual(lang, "en")
    
    def test_detect_neutral(self):
        """Testa query neutra que não detecta idioma"""
        query = "Apple innovation"
        lang = self.plugin.detect_query_language(query)
        # Pode retornar None ou um dos idiomas
        self.assertIn(lang, ["pt", "en", None])
    
    def test_build_language_filter_pt(self):
        """Testa construção de filtro para português"""
        filter_obj = self.plugin.build_language_filter("pt")
        self.assertIsNotNone(filter_obj)
    
    def test_build_language_filter_en(self):
        """Testa construção de filtro para inglês"""
        filter_obj = self.plugin.build_language_filter("en")
        self.assertIsNotNone(filter_obj)
    
    def test_build_language_filter_invalid(self):
        """Testa construção de filtro com idioma inválido"""
        filter_obj = self.plugin.build_language_filter("invalid")
        self.assertIsNone(filter_obj)
    
    def test_get_language_filter_for_query_pt(self):
        """Testa método de conveniência com query em português"""
        query = "inovação da empresa"
        filter_obj = self.plugin.get_language_filter_for_query(query)
        self.assertIsNotNone(filter_obj)
    
    def test_get_language_filter_for_query_en(self):
        """Testa método de conveniência com query em inglês"""
        query = "innovation from company"
        filter_obj = self.plugin.get_language_filter_for_query(query)
        self.assertIsNotNone(filter_obj)
    
    def test_empty_query(self):
        """Testa query vazia"""
        lang = self.plugin.detect_query_language("")
        self.assertIsNone(lang)
        
        filter_obj = self.plugin.get_language_filter_for_query("")
        self.assertIsNone(filter_obj)


if __name__ == "__main__":
    unittest.main()

