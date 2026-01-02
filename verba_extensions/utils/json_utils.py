"""
Safe JSON parsing utilities for Verba.

Provides defensive JSON parsing that handles common LLM output issues:
- Trailing commas
- Comments (// and /* */)
- Unescaped quotes
- Partial JSON extraction
- Special characters (currency symbols, etc.)
"""

import json
import re
from typing import Any, Dict, Optional, Union


def sanitize_json_string(json_str: str) -> str:
    """
    Sanitize a JSON string by removing common formatting issues.
    
    Args:
        json_str: Raw JSON string (potentially malformed)
    
    Returns:
        Sanitized JSON string ready for parsing
    """
    if not json_str:
        return "{}"
    
    # Remove markdown code blocks if present
    json_str = json_str.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    elif json_str.startswith("```"):
        json_str = json_str[3:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
    
    # Remove line comments (// ...)
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    
    # Remove block comments (/* ... */)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    
    # Remove trailing commas before } or ]
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    
    # Fix common currency/special character issues
    json_str = json_str.replace('R$', 'R ')
    
    return json_str.strip()


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract JSON object or array from text that may contain other content.
    
    Args:
        text: Text that may contain JSON
    
    Returns:
        Extracted JSON string or None
    """
    # Try to find JSON object
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        return match.group()
    
    # Try to find JSON array
    match = re.search(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', text, re.DOTALL)
    if match:
        return match.group()
    
    return None


def safe_json_parse(
    json_str: str,
    default: Optional[Union[Dict, list]] = None,
    raise_on_error: bool = False
) -> Union[Dict[str, Any], list, None]:
    """
    Safely parse JSON with multiple fallback strategies.
    
    Args:
        json_str: Raw JSON string to parse
        default: Default value if parsing fails (default: empty dict)
        raise_on_error: If True, raise exception on parse failure
    
    Returns:
        Parsed JSON object, or default if parsing fails
    
    Raises:
        json.JSONDecodeError: If raise_on_error=True and parsing fails
    """
    if default is None:
        default = {}
    
    if not json_str or not isinstance(json_str, str):
        return default
    
    # Strategy 1: Direct parse (optimistic)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Sanitize and retry
    try:
        sanitized = sanitize_json_string(json_str)
        return json.loads(sanitized)
    except json.JSONDecodeError:
        pass
    
    # Strategy 3: Extract JSON from text and retry
    try:
        extracted = extract_json_from_text(json_str)
        if extracted:
            sanitized = sanitize_json_string(extracted)
            return json.loads(sanitized)
    except json.JSONDecodeError:
        pass
    
    # All strategies failed
    if raise_on_error:
        raise json.JSONDecodeError(
            f"Failed to parse JSON after all strategies",
            json_str,
            0
        )
    
    return default


def safe_json_parse_with_info(
    json_str: str,
    default: Optional[Union[Dict, list]] = None
) -> tuple:
    """
    Parse JSON and return info about the parsing process.
    
    Args:
        json_str: Raw JSON string to parse
        default: Default value if parsing fails
    
    Returns:
        Tuple of (parsed_result, success, strategy_used)
        - parsed_result: The parsed JSON or default
        - success: True if parsing succeeded
        - strategy_used: Which strategy succeeded (1, 2, 3 or 0 for failure)
    """
    if default is None:
        default = {}
    
    if not json_str or not isinstance(json_str, str):
        return default, False, 0
    
    # Strategy 1
    try:
        return json.loads(json_str), True, 1
    except json.JSONDecodeError:
        pass
    
    # Strategy 2
    try:
        sanitized = sanitize_json_string(json_str)
        return json.loads(sanitized), True, 2
    except json.JSONDecodeError:
        pass
    
    # Strategy 3
    try:
        extracted = extract_json_from_text(json_str)
        if extracted:
            sanitized = sanitize_json_string(extracted)
            return json.loads(sanitized), True, 3
    except json.JSONDecodeError:
        pass
    
    return default, False, 0
