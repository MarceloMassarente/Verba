"""
Apply preset and AdvancedSearchOptions to an in-memory RAG config (EntityAware only).

All Weaviate access remains inside the Verba backend; this only mutates the RAG dict.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from wasabi import msg

from verba_extensions.tools.rag_preset import apply_reranker_preset_to_rag

VERBA_API_SEARCH_RAG_KEY = "verba_api_search"

_VALID_TARGET = frozenset(
    {"default", "concept_vec", "company_vec", "sector_vec"}
)
_ENTITY_MODES = frozenset({"strict", "boost", "adaptive", "hybrid"})
_TWO_PHASE = frozenset({"auto", "enabled", "disabled"})
_FILTER_LEVEL = frozenset({"chunk", "document"})


def _set_ea_config_value(
    ea_config: dict[str, Any], key: str, value: Any
) -> bool:
    if key not in ea_config:
        return False
    item = ea_config[key]
    if hasattr(item, "value"):
        item.value = value
    elif isinstance(item, dict) and "value" in item:
        item["value"] = value
    else:
        ea_config[key] = value
    return True


def apply_preset_and_advanced_search_to_rag(
    rag_config: dict[str, Any],
    preset: Optional[str],
    advanced: Any,
) -> dict[str, Any]:
    """
    Mutates rag_config in place. Applies preset first, then advanced options.

    Returns metadata for API responses: preset_applied, advanced_applied, advanced_ignored, warnings.
    """
    meta: dict[str, Any] = {
        "preset_applied": None,
        "advanced_applied": {},
        "advanced_ignored": [],
        "warnings": [],
    }
    rag_config.pop(VERBA_API_SEARCH_RAG_KEY, None)

    if preset:
        meta["preset_applied"] = apply_reranker_preset_to_rag(rag_config, preset)

    if not advanced:
        return meta

    if hasattr(advanced, "model_dump"):
        data = advanced.model_dump(exclude_none=True)
    elif isinstance(advanced, dict):
        data = {k: v for k, v in advanced.items() if v is not None}
    else:
        meta["warnings"].append("advanced_search: invalid type, ignored")
        return meta

    if not data:
        return meta

    if "Retriever" not in rag_config or not isinstance(
        rag_config["Retriever"], dict
    ):
        meta["warnings"].append("Retriever missing; advanced_search ignored")
        return meta

    retriever = rag_config["Retriever"]
    components = retriever.get("components", {})
    entity_aware_key = None
    if "EntityAware" in components:
        entity_aware_key = "EntityAware"
    elif "Entity-Aware" in components:
        entity_aware_key = "Entity-Aware"
    if not entity_aware_key:
        meta["warnings"].append("EntityAware not in RAG; advanced_search ignored")
        return meta

    retriever["selected"] = entity_aware_key
    entity_aware = components[entity_aware_key]
    ea_config = (
        entity_aware.get("config", {})
        if isinstance(entity_aware, dict)
        else {}
    )

    applied: dict[str, Any] = {}
    ignored: list[str] = []

    tv = data.get("target_vectors")
    if tv is not None:
        if not isinstance(tv, list):
            ignored.append("target_vectors")
        else:
            cleaned = [v for v in tv if v in _VALID_TARGET]
            if not cleaned and tv:
                ignored.append("target_vectors (no valid values)")
            elif cleaned:
                applied["target_vectors"] = cleaned
                if len(cleaned) < len(tv):
                    meta["warnings"].append("target_vectors: dropped invalid names")
            else:
                ignored.append("target_vectors")

    tpm = data.get("two_phase_mode")
    if tpm is not None:
        if tpm in _TWO_PHASE:
            applied["two_phase_mode"] = tpm
        else:
            ignored.append("two_phase_mode")

    tfl = data.get("two_phase_filter_level")
    if tfl is not None:
        if tfl in _FILTER_LEVEL:
            applied["two_phase_filter_level"] = tfl
        else:
            ignored.append("two_phase_filter_level")

    em = data.get("entity_filter_mode")
    if em is not None:
        if em in _ENTITY_MODES and _set_ea_config_value(
            ea_config, "Entity Filter Mode", em
        ):
            applied["entity_filter_mode"] = em
        else:
            ignored.append("entity_filter_mode")

    if "enable_multi_vector" in data:
        v = data["enable_multi_vector"]
        if isinstance(v, bool) and _set_ea_config_value(
            ea_config, "Enable Multi-Vector Search", v
        ):
            applied["enable_multi_vector"] = v
        else:
            ignored.append("enable_multi_vector")

    al = data.get("alpha")
    if al is not None:
        try:
            a = float(al)
            if 0.0 <= a <= 1.0 and _set_ea_config_value(
                ea_config, "Alpha", str(a)
            ):
                applied["alpha"] = a
            else:
                ignored.append("alpha")
        except (TypeError, ValueError):
            ignored.append("alpha")

    for key, cfg_name in (
        ("enable_query_expansion", "Enable Query Expansion"),
        ("enable_dynamic_alpha", "Enable Dynamic Alpha"),
        ("enable_relative_score_fusion", "Enable Relative Score Fusion"),
    ):
        if key in data:
            v = data[key]
            if isinstance(v, bool) and _set_ea_config_value(
                ea_config, cfg_name, v
            ):
                applied[key] = v
            else:
                ignored.append(key)

    rk = data.get("reranker_top_k")
    if rk is not None:
        try:
            k = int(rk)
            if k >= 0 and _set_ea_config_value(
                ea_config, "Reranker Top K", k
            ):
                applied["reranker_top_k"] = k
            else:
                ignored.append("reranker_top_k")
        except (TypeError, ValueError):
            ignored.append("reranker_top_k")

    api_debug = data.get("debug")
    if api_debug is not None:
        if isinstance(api_debug, bool):
            applied["debug"] = api_debug
        else:
            ignored.append("debug")

    meta["advanced_ignored"] = ignored
    meta["advanced_applied"] = applied

    verba_block: dict[str, Any] = {
        "overrides": {
            "target_vectors": applied.get("target_vectors"),
            "two_phase_mode": applied.get("two_phase_mode"),
            "two_phase_filter_level": applied.get("two_phase_filter_level"),
        },
    }
    if isinstance(api_debug, bool):
        verba_block["api_debug"] = api_debug
    if any(
        v is not None
        for v in verba_block["overrides"].values()
    ) or "api_debug" in verba_block:
        rag_config[VERBA_API_SEARCH_RAG_KEY] = deepcopy(verba_block)
    if ignored and not applied:
        msg.info(f"verba advanced_search: all keys ignored: {ignored}")

    return meta
