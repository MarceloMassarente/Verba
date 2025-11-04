"""
Testes unitários para TemporalFilterPlugin
"""

import unittest
from verba_extensions.plugins.temporal_filter import TemporalFilterPlugin


class TestTemporalFilterPlugin(unittest.TestCase):
    
    def setUp(self):
        self.plugin = TemporalFilterPlugin()
    
    def test_extract_single_year(self):
        """Testa extração de ano único"""
        query = "inovação em 2024"
        date_range = self.plugin.extract_date_range(query)
        self.assertIsNotNone(date_range)
        start_date, end_date = date_range
        self.assertEqual(start_date, "2024-01-01")
        self.assertEqual(end_date, "2024-12-31")
    
    def test_extract_year_range(self):
        """Testa extração de range de anos"""
        query = "inovação entre 2023 e 2024"
        date_range = self.plugin.extract_date_range(query)
        self.assertIsNotNone(date_range)
        start_date, end_date = date_range
        self.assertEqual(start_date, "2023-01-01")
        self.assertEqual(end_date, "2024-12-31")
    
    def test_extract_since_year_pt(self):
        """Testa extração de 'desde' em português"""
        query = "inovação desde 2024"
        date_range = self.plugin.extract_date_range(query)
        self.assertIsNotNone(date_range)
        start_date, end_date = date_range
        self.assertEqual(start_date, "2024-01-01")
        self.assertIsNone(end_date)
    
    def test_extract_until_year_pt(self):
        """Testa extração de 'até' em português"""
        query = "inovação até 2024"
        date_range = self.plugin.extract_date_range(query)
        self.assertIsNotNone(date_range)
        start_date, end_date = date_range
        self.assertIsNone(start_date)
        self.assertEqual(end_date, "2024-12-31")
    
    def test_extract_from_year_en(self):
        """Testa extração de 'from' em inglês"""
        query = "innovation from 2024"
        date_range = self.plugin.extract_date_range(query)
        self.assertIsNotNone(date_range)
        start_date, end_date = date_range
        self.assertEqual(start_date, "2024-01-01")
        self.assertIsNone(end_date)
    
    def test_extract_until_year_en(self):
        """Testa extração de 'until' em inglês"""
        query = "innovation until 2024"
        date_range = self.plugin.extract_date_range(query)
        self.assertIsNotNone(date_range)
        start_date, end_date = date_range
        self.assertIsNone(start_date)
        self.assertEqual(end_date, "2024-12-31")
    
    def test_extract_no_dates(self):
        """Testa query sem datas"""
        query = "inovação da Apple"
        date_range = self.plugin.extract_date_range(query)
        self.assertIsNone(date_range)
    
    def test_build_temporal_filter_start_only(self):
        """Testa construção de filtro apenas com start_date"""
        filter_obj = self.plugin.build_temporal_filter("2024-01-01", None)
        self.assertIsNotNone(filter_obj)
    
    def test_build_temporal_filter_end_only(self):
        """Testa construção de filtro apenas com end_date"""
        filter_obj = self.plugin.build_temporal_filter(None, "2024-12-31")
        self.assertIsNotNone(filter_obj)
    
    def test_build_temporal_filter_range(self):
        """Testa construção de filtro com range"""
        filter_obj = self.plugin.build_temporal_filter("2024-01-01", "2024-12-31")
        self.assertIsNotNone(filter_obj)
    
    def test_build_temporal_filter_none(self):
        """Testa construção de filtro sem datas"""
        filter_obj = self.plugin.build_temporal_filter(None, None)
        self.assertIsNone(filter_obj)
    
    def test_get_temporal_filter_for_query(self):
        """Testa método de conveniência"""
        query = "inovação em 2024"
        filter_obj = self.plugin.get_temporal_filter_for_query(query)
        self.assertIsNotNone(filter_obj)
    
    def test_get_temporal_filter_for_query_no_dates(self):
        """Testa método de conveniência sem datas"""
        query = "inovação da Apple"
        filter_obj = self.plugin.get_temporal_filter_for_query(query)
        self.assertIsNone(filter_obj)
    
    def test_custom_date_field(self):
        """Testa filtro com campo de data customizado"""
        filter_obj = self.plugin.build_temporal_filter(
            "2024-01-01", "2024-12-31", date_field="published_at"
        )
        self.assertIsNotNone(filter_obj)


if __name__ == "__main__":
    unittest.main()

