"""Tests for verba_extensions.tools.api_search_rag (preset + advanced overrides)."""

import copy
from typing import Any

import pytest

from verba_extensions.tools.api_search_rag import (
    VERBA_API_SEARCH_RAG_KEY,
    apply_preset_and_advanced_search_to_rag,
)
from goldenverba.server.types import AdvancedSearchOptions


def _setting(value: Any) -> dict[str, Any]:
    return {
        "type": "str",
        "value": value,
        "description": "t",
        "values": [],
    }


def _bool_setting(value: bool) -> dict[str, Any]:
    return {
        "type": "bool",
        "value": value,
        "description": "t",
        "values": [],
    }


def _int_setting(value: int) -> dict[str, Any]:
    return {
        "type": "int",
        "value": value,
        "description": "t",
        "values": [],
    }


def _minimal_rag_with_entity_aware() -> dict[str, Any]:
    return {
        "Reader": {"selected": "x", "components": {}},
        "Chunker": {"selected": "x", "components": {}},
        "Embedder": {"selected": "x", "components": {}},
        "Generator": {"selected": "x", "components": {}},
        "Retriever": {
            "selected": "EntityAware",
            "components": {
                "EntityAware": {
                    "name": "EntityAware",
                    "config": {
                        "Entity Filter Mode": _setting("adaptive"),
                        "Enable Multi-Vector Search": _bool_setting(False),
                        "Alpha": _setting("0.6"),
                        "Enable Query Expansion": _bool_setting(True),
                        "Enable Dynamic Alpha": _bool_setting(False),
                        "Enable Relative Score Fusion": _bool_setting(True),
                        "Reranker Top K": _int_setting(5),
                    },
                }
            },
        },
    }


def test_advanced_applies_to_entity_aware_config():
    rag = _minimal_rag_with_entity_aware()
    adv = AdvancedSearchOptions(
        entity_filter_mode="strict",
        alpha=0.25,
        enable_multi_vector=True,
        reranker_top_k=8,
        two_phase_mode="disabled",
    )
    meta = apply_preset_and_advanced_search_to_rag(
        rag, None, adv
    )
    assert meta["advanced_applied"]["entity_filter_mode"] == "strict"
    assert meta["advanced_applied"]["alpha"] == 0.25
    assert meta["advanced_applied"]["enable_multi_vector"] is True
    assert meta["advanced_applied"]["reranker_top_k"] == 8
    assert meta["advanced_applied"]["two_phase_mode"] == "disabled"
    assert meta["advanced_ignored"] == []
    ec = (
        rag["Retriever"]["components"]["EntityAware"]["config"][
            "Entity Filter Mode"
        ]["value"]
    )
    assert ec == "strict"
    assert (
        rag["Retriever"]["components"]["EntityAware"]["config"]["Alpha"][
            "value"
        ]
        == "0.25"
    )
    assert VERBA_API_SEARCH_RAG_KEY in rag
    assert rag[VERBA_API_SEARCH_RAG_KEY]["overrides"]["two_phase_mode"] == (
        "disabled"
    )


def test_invalid_target_vector_names_ignored_in_helper_dict_path():
    rag = _minimal_rag_with_entity_aware()
    data = {
        "target_vectors": ["company_vec", "nope", "bad"],
    }
    meta = apply_preset_and_advanced_search_to_rag(
        rag, None, data
    )
    assert "warnings" in meta
    assert meta["advanced_applied"]["target_vectors"] == ["company_vec"]


def test_no_retriever_warns():
    rag: dict[str, Any] = {"Reader": {}}
    meta = apply_preset_and_advanced_search_to_rag(
        rag, None, {"alpha": 0.5}
    )
    assert any("Retriever missing" in w for w in meta["warnings"])


def test_advanced_explicit_overrides_after_preset():
    """
    If preset and advanced both set alpha, the helper applies preset first
    then advanced: advanced must win.
    """
    from verba_extensions.plugins.reranker import RerankerPresets

    presets = RerankerPresets.get_all_presets()
    if "speed" not in presets:
        pytest.skip("reranker preset 'speed' not in environment")

    rag = _minimal_rag_with_entity_aware()
    base = copy.deepcopy(rag)
    only_preset = copy.deepcopy(rag)
    apply_preset_and_advanced_search_to_rag(only_preset, "speed", None)
    after_preset = (
        only_preset["Retriever"]["components"]["EntityAware"][
            "config"
        ]["Alpha"]["value"]
    )
    assert after_preset is not None

    meta = apply_preset_and_advanced_search_to_rag(
        base,
        "speed",
        AdvancedSearchOptions(alpha=0.9),
    )
    assert meta["advanced_applied"]["alpha"] == 0.9
    final_alpha = base["Retriever"]["components"]["EntityAware"][
        "config"
    ]["Alpha"]["value"]
    assert final_alpha == "0.9"
