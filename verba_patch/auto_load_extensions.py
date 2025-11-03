"""
Patch para carregar extensões automaticamente no Verba
Este arquivo deve ser importado ANTES de goldenverba.server.api
"""

import os
import sys

def patch_verba_imports():
    """
    Patch no sistema de imports do Verba para carregar extensões automaticamente
    """
    # Adiciona extensões ao path se necessário
    extensions_path = os.path.join(os.path.dirname(__file__), "..", "verba_extensions")
    if extensions_path not in sys.path:
        sys.path.insert(0, extensions_path)
    
    # Importa e inicializa extensões
    try:
        # Importa startup que auto-inicializa
        import verba_extensions.startup
        from verba_extensions.startup import initialize_extensions
        
        # Inicializa se ainda não foi
        if not hasattr(sys.modules.get('verba_extensions'), '_plugin_manager'):
            initialize_extensions()
        
        return True
    except ImportError as e:
        # Extensões não disponíveis, continua sem elas
        print(f"⚠️ Extensões não disponíveis: {str(e)}")
        return False

# Auto-executa o patch quando importado
if __name__ != "__main__":
    patch_verba_imports()

