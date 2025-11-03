"""
Compatibilidade de imports do Weaviate
Gerencia imports v3 vs v4 automaticamente
"""

import sys
from typing import Optional, Any

WEAVIATE_V4 = False
Filter = None
WeaviateAsyncClient = None

try:
    # Tenta importar classes v4
    from weaviate.client import WeaviateAsyncClient
    from weaviate.classes.query import Filter
    WEAVIATE_V4 = True
except ImportError:
    # Versão incompatível ou v3 - cria objetos dummy
    WEAVIATE_V4 = False
    
    # Cria classe Filter dummy para v3
    class FilterDummy:
        """Filter dummy para v3"""
        @staticmethod
        def by_property(prop: str):
            class PropertyFilter:
                def contains_any(self, values):
                    return {'path': [prop], 'operator': 'ContainsAny', 'valueString': values}
                def contains_all(self, values):
                    return {'path': [prop], 'operator': 'ContainsAll', 'valueString': values}
                def equal(self, value):
                    return {'path': [prop], 'operator': 'Equal', 'valueString': str(value)}
                def greater_or_equal(self, value):
                    return {'path': [prop], 'operator': 'GreaterOrEqual', 'valueNumber': float(value)}
            return PropertyFilter()
    
    Filter = FilterDummy()
    WeaviateAsyncClient = None

# Exporta informações de compatibilidade
__all__ = ['Filter', 'WEAVIATE_V4', 'WeaviateAsyncClient']
