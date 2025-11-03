"""
Compatibility layer para Weaviate v3/v4
"""

# Imports opcionais para evitar erros se módulos não estiverem disponíveis
try:
    from .weaviate_imports import Filter, WEAVIATE_V4
    # WEAVIATE_V3 é o inverso de WEAVIATE_V4
    WEAVIATE_V3 = not WEAVIATE_V4 if WEAVIATE_V4 is not None else True
except ImportError:
    Filter = None
    WEAVIATE_V4 = None
    WEAVIATE_V3 = True  # Default para v3 se não conseguir importar

try:
    from .weaviate_version_detector import detect_weaviate_version
except ImportError:
    detect_weaviate_version = None

try:
    from .weaviate_v3_adapter import WeaviateV3HTTPAdapter
except ImportError:
    WeaviateV3HTTPAdapter = None

__all__ = [
    "Filter",
    "WEAVIATE_V4",
    "WEAVIATE_V3",
    "detect_weaviate_version",
    "WeaviateV3HTTPAdapter",
]

