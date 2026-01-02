"""
Central configuration value access utilities for Verba.

Provides safe access to config values that work with both:
- Pydantic InputConfig objects (config[key].value)
- Dictionary configs from external APIs (config[key]["value"])

Usage:
    from goldenverba.components.config_utils import get_config_value
    
    model = get_config_value(config, "Model", default="gpt-4")
"""

from typing import Any, Dict, Optional


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safely get a config value supporting both InputConfig and dict types.
    
    Args:
        config: Configuration dictionary (may contain InputConfig or dict values)
        key: Key to access
        default: Default value if key not found or value is None
        
    Returns:
        The config value, or default if not found
    """
    if key not in config:
        return default
    
    item = config[key]
    
    if item is None:
        return default
    
    # InputConfig object with .value attribute
    if hasattr(item, 'value'):
        return item.value if item.value is not None else default
    
    # Dictionary with 'value' key
    if isinstance(item, dict):
        return item.get('value', default)
    
    # Plain value
    return item


def get_config_values(config: Dict[str, Any], key: str, default: list = None) -> list:
    """
    Safely get a config values list (for multi-select fields).
    
    Args:
        config: Configuration dictionary
        key: Key to access
        default: Default list if key not found
        
    Returns:
        List of values
    """
    if default is None:
        default = []
    
    if key not in config:
        return default
    
    item = config[key]
    
    if item is None:
        return default
    
    # InputConfig object with .values attribute
    if hasattr(item, 'values'):
        return item.values if item.values is not None else default
    
    # Dictionary with 'values' key
    if isinstance(item, dict):
        return item.get('values', default)
    
    # Already a list
    if isinstance(item, list):
        return item
    
    return default


def set_config_value(config: Dict[str, Any], key: str, value: Any) -> None:
    """
    Safely set a config value supporting both InputConfig and dict types.
    
    Args:
        config: Configuration dictionary
        key: Key to set
        value: Value to set
    """
    if key not in config:
        config[key] = {"value": value}
        return
    
    item = config[key]
    
    # InputConfig object
    if hasattr(item, 'value'):
        item.value = value
    # Dictionary
    elif isinstance(item, dict):
        item['value'] = value
    else:
        config[key] = {"value": value}
