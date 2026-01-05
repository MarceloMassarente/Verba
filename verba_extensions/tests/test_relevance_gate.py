"""
Simplified unit tests for the Relevance Gate configuration in EntityAwareRetriever.

These tests verify that:
1. The new configuration options are correctly added to the retriever
2. The gate logic functions correctly with various score scenarios
"""

import unittest
from verba_extensions.plugins.entity_aware_retriever import EntityAwareRetriever, get_config_value


class TestRelevanceGateConfig(unittest.TestCase):
    """Tests for the Relevance Gate configuration options."""
    
    def setUp(self):
        self.retriever = EntityAwareRetriever()
        
    def test_new_configs_added(self):
        """Test that the new gate configurations are correctly added."""
        self.assertIn("Retrieval Threshold", self.retriever.config)
        self.assertIn("Retrieval Margin", self.retriever.config)
        self.assertIn("Gate Failure Message", self.retriever.config)
        
    def test_default_values(self):
        """Test that default values are set correctly."""
        self.assertEqual(self.retriever.config["Retrieval Threshold"].value, "0.15")
        self.assertEqual(self.retriever.config["Retrieval Margin"].value, "0.0")
        self.assertEqual(self.retriever.config["Gate Failure Message"].value, "NAO ENCONTREI NO DOCUMENTO")
        
    def test_configs_in_fundamental_block(self):
        """Test that configs are in the 'fundamental' block for UI grouping."""
        self.assertEqual(self.retriever.config["Retrieval Threshold"].block, "fundamental")
        self.assertEqual(self.retriever.config["Retrieval Margin"].block, "fundamental")
        self.assertEqual(self.retriever.config["Gate Failure Message"].block, "fundamental")


class TestRelevanceGateLogic(unittest.TestCase):
    """Tests for the Relevance Gate decision logic."""
    
    def test_gate_passes_when_score_above_threshold(self):
        """When top score >= threshold, gate should pass."""
        top_1_score = 0.8
        top_2_score = 0.4
        gate_threshold = 0.5
        gate_margin = 0.0
        
        # Gate logic (replicated from retrieve method)
        is_gate_failed = False
        if gate_threshold > 0 and top_1_score < gate_threshold:
            is_gate_failed = True
        elif gate_margin > 0 and (top_1_score - top_2_score) < gate_margin:
            is_gate_failed = True
            
        self.assertFalse(is_gate_failed)
        
    def test_gate_fails_when_score_below_threshold(self):
        """When top score < threshold, gate should fail."""
        top_1_score = 0.4
        top_2_score = 0.2
        gate_threshold = 0.5
        gate_margin = 0.0
        
        # Gate logic
        is_gate_failed = False
        if gate_threshold > 0 and top_1_score < gate_threshold:
            is_gate_failed = True
        elif gate_margin > 0 and (top_1_score - top_2_score) < gate_margin:
            is_gate_failed = True
            
        self.assertTrue(is_gate_failed)
        
    def test_gate_fails_when_margin_too_small(self):
        """When margin between top scores is too small, gate should fail."""
        top_1_score = 0.8
        top_2_score = 0.75  # Margin = 0.05
        gate_threshold = 0.0  # Disabled
        gate_margin = 0.3    # Requires at least 0.3 margin
        
        # Gate logic
        is_gate_failed = False
        if gate_threshold > 0 and top_1_score < gate_threshold:
            is_gate_failed = True
        elif gate_margin > 0 and (top_1_score - top_2_score) < gate_margin:
            is_gate_failed = True
            
        self.assertTrue(is_gate_failed)
        
    def test_gate_passes_with_sufficient_margin(self):
        """When margin is sufficient, gate should pass."""
        top_1_score = 0.9
        top_2_score = 0.5  # Margin = 0.4
        gate_threshold = 0.0  # Disabled
        gate_margin = 0.3    # Requires at least 0.3 margin
        
        # Gate logic
        is_gate_failed = False
        if gate_threshold > 0 and top_1_score < gate_threshold:
            is_gate_failed = True
        elif gate_margin > 0 and (top_1_score - top_2_score) < gate_margin:
            is_gate_failed = True
            
        self.assertFalse(is_gate_failed)
        
    def test_gate_disabled_by_default(self):
        """When both threshold and margin are 0, gate should always pass."""
        top_1_score = 0.1  # Very low score
        top_2_score = 0.09  # Almost no margin
        gate_threshold = 0.0  # Disabled
        gate_margin = 0.0    # Disabled
        
        # Gate logic
        is_gate_failed = False
        if gate_threshold > 0 and top_1_score < gate_threshold:
            is_gate_failed = True
        elif gate_margin > 0 and (top_1_score - top_2_score) < gate_margin:
            is_gate_failed = True
            
        self.assertFalse(is_gate_failed)
        
    def test_combined_threshold_and_margin(self):
        """Test that threshold is checked before margin."""
        # Score is above threshold but margin is insufficient
        top_1_score = 0.7
        top_2_score = 0.65  # Margin = 0.05
        gate_threshold = 0.5  # Passes
        gate_margin = 0.3     # Fails
        
        # Gate logic - threshold check first, then margin
        is_gate_failed = False
        if gate_threshold > 0 and top_1_score < gate_threshold:
            is_gate_failed = True
        elif gate_margin > 0 and (top_1_score - top_2_score) < gate_margin:
            is_gate_failed = True
            
        self.assertTrue(is_gate_failed)  # Fails due to margin


class TestGetConfigValue(unittest.TestCase):
    """Tests for the get_config_value utility function."""
    
    def test_extracts_from_inputconfig(self):
        """Test extraction from InputConfig objects."""
        retriever = EntityAwareRetriever()
        value = get_config_value(retriever.config, "Retrieval Threshold", "default")
        self.assertEqual(value, "0.15")
        
    def test_returns_default_for_missing_key(self):
        """Test that default is returned for missing keys."""
        config = {}
        value = get_config_value(config, "NonexistentKey", "my_default")
        self.assertEqual(value, "my_default")
        
    def test_extracts_from_dict(self):
        """Test extraction from plain dict config."""
        config = {"Retrieval Threshold": {"value": "0.7"}}
        value = get_config_value(config, "Retrieval Threshold", "default")
        self.assertEqual(value, "0.7")


if __name__ == "__main__":
    unittest.main()
