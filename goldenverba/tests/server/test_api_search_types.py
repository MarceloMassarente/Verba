"""Contract tests for AdvancedSearchOptions (Pydantic)."""

import pytest
from pydantic import ValidationError

from goldenverba.server.types import AdvancedSearchOptions


def test_advanced_search_minimal_omitted():
    m = AdvancedSearchOptions()
    assert m.model_dump(exclude_none=True) == {}


def test_advanced_search_full_valid():
    m = AdvancedSearchOptions(
        target_vectors=["default", "company_vec"],
        enable_multi_vector=True,
        two_phase_mode="auto",
        two_phase_filter_level="document",
        entity_filter_mode="adaptive",
        alpha=0.35,
        enable_query_expansion=False,
        enable_dynamic_alpha=True,
        enable_relative_score_fusion=True,
        reranker_top_k=12,
        debug=True,
    )
    d = m.model_dump(exclude_none=True)
    assert d["target_vectors"] == ["default", "company_vec"]
    assert d["alpha"] == 0.35


def test_target_vectors_deduped():
    m = AdvancedSearchOptions(
        target_vectors=["default", "default", "sector_vec", "default"]
    )
    assert m.target_vectors == ["default", "sector_vec"]


def test_alpha_out_of_range_fails():
    with pytest.raises(ValidationError):
        AdvancedSearchOptions(alpha=1.5)
    with pytest.raises(ValidationError):
        AdvancedSearchOptions(alpha=-0.01)


def test_reranker_top_k_negative_fails():
    with pytest.raises(ValidationError):
        AdvancedSearchOptions(reranker_top_k=-1)


def test_target_vector_invalid_literal_fails():
    with pytest.raises(ValidationError):
        AdvancedSearchOptions(target_vectors=["not_a_vector"])  # type: ignore[list-item]
