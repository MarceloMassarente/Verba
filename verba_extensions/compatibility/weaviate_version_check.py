"""
Verifica e fornece informações sobre versão do weaviate-client
"""

import sys
from typing import Optional, Tuple

def check_weaviate_version() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verifica se weaviate-client está instalado e qual versão
    
    Returns:
        (is_compatible, version, error_message)
    """
    try:
        import weaviate
        
        # Tenta importar classes v4
        try:
            from weaviate.client import WeaviateAsyncClient
            from weaviate.classes.query import Filter
            return (True, getattr(weaviate, '__version__', 'unknown'), None)
        except ImportError:
            # Versão antiga ou incompatível
            version = getattr(weaviate, '__version__', 'unknown')
            return (False, version, "weaviate.classes or WeaviateAsyncClient not available")
            
    except ImportError:
        return (False, None, "weaviate-client not installed")

def get_weaviate_import_error() -> Optional[str]:
    """Retorna mensagem de erro se houver problema com imports"""
    try:
        from weaviate.client import WeaviateAsyncClient
        from weaviate.classes.query import Filter
        return None
    except ImportError as e:
        return str(e)

def is_weaviate_v4_compatible() -> bool:
    """Verifica rapidamente se é compatível com v4"""
    compatible, _, _ = check_weaviate_version()
    return compatible

