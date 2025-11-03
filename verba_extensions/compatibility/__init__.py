"""
Compatibility layer para Weaviate v3/v4
"""

from .weaviate_imports import Filter, WEAVIATE_V4, WEAVIATE_V3
from .weaviate_version_detector import detect_weaviate_version
from .weaviate_v3_adapter import WeaviateV3HTTPAdapter

__all__ = [
    "Filter",
    "WEAVIATE_V4",
    "WEAVIATE_V3",
    "detect_weaviate_version",
    "WeaviateV3HTTPAdapter",
]

