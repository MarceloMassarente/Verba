"""
Apply RerankerPresets to an in-memory RAG config dict (EntityAware retriever).
Shared by agent search and optional callers.
"""
from __future__ import annotations

from typing import Any, Optional

from wasabi import msg


def apply_reranker_preset_to_rag(
    rag_config: dict[str, Any], preset: Optional[str]
) -> Optional[str]:
    """
    Mutates rag_config in place. Returns the preset name if applied, else None.
    """
    if not preset or not str(preset).strip():
        return None
    name = str(preset).strip()
    try:
        from verba_extensions.plugins.reranker import RerankerPresets

        presets = RerankerPresets.get_all_presets()
        preset_config = presets.get(name)
        if not preset_config:
            preset_config = presets.get(name.replace("-", "_").lower())
        if not preset_config:
            msg.warn(
                f"Preset '{name}' not found. Available: {list(presets.keys())}"
            )
            return None
        if "Retriever" not in rag_config:
            msg.warn("Retriever not in RAG config, preset ignored")
            return None
        retriever = rag_config.get("Retriever")
        if not retriever:
            return None
        components = retriever.get("components", {}) if isinstance(retriever, dict) else {}
        entity_aware_key = None
        if "EntityAware" in components:
            entity_aware_key = "EntityAware"
        elif "Entity-Aware" in components:
            entity_aware_key = "Entity-Aware"
        if not entity_aware_key:
            msg.warn("EntityAware not in RAG config, preset ignored")
            return None
        if isinstance(retriever, dict):
            retriever["selected"] = entity_aware_key
        entity_aware = components[entity_aware_key]
        ea_config = (
            entity_aware.get("config", {})
            if isinstance(entity_aware, dict)
            else getattr(entity_aware, "config", {}) or {}
        )
        if not ea_config:
            return None
        skip = {
            "name",
            "display_name",
            "description",
            "latency_estimate",
            "quality_estimate",
            "requirements",
        }
        for key, value in preset_config.items():
            if key in skip:
                continue
            if key not in ea_config:
                continue
            item = ea_config[key]
            if hasattr(item, "value"):
                item.value = value
            elif isinstance(item, dict) and "value" in item:
                item["value"] = value
            else:
                ea_config[key] = value
        msg.good(f"Preset '{name}' applied to EntityAware")
        return name
    except Exception as e:
        msg.warn(f"Failed to apply preset '{name}': {e}")
        return None
