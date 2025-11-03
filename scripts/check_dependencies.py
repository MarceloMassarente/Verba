"""
Script para verificar e corrigir dependências do sistema
"""

import sys
import subprocess
from wasabi import msg

def check_and_fix_dependencies():
    """Verifica e instala dependências corretas"""
    msg.info("Verificando dependencias do sistema Verba Extensions...")
    
    issues = []
    fixes = []
    
    # Verifica weaviate-client
    try:
        import weaviate
        version = getattr(weaviate, '__version__', 'unknown')
        
        try:
            from weaviate.client import WeaviateAsyncClient
            from weaviate.classes.query import Filter
            msg.good(f"OK: weaviate-client {version} (v4 compativel)")
        except ImportError:
            issues.append(f"weaviate-client {version} nao e v4 - precisa atualizar")
            fixes.append("pip install --upgrade weaviate-client==4.9.6")
            msg.warn(f"AVISO: weaviate-client {version} nao e v4")
    except ImportError:
        issues.append("weaviate-client nao instalado")
        fixes.append("pip install weaviate-client==4.9.6")
        msg.fail("weaviate-client nao instalado")
    
    # Verifica outras dependências
    required_packages = {
        'httpx': 'httpx',
        'trafilatura': 'trafilatura',
        'spacy': 'spacy',
        'nltk': 'nltk',
    }
    
    for module, package in required_packages.items():
        try:
            __import__(module)
            msg.good(f"OK: {package} instalado")
        except ImportError:
            issues.append(f"{package} nao instalado")
            fixes.append(f"pip install {package}")
            msg.warn(f"AVISO: {package} nao instalado")
    
    # Resumo
    msg.info("")
    if issues:
        msg.warn(f"Encontrados {len(issues)} problemas:")
        for issue in issues:
            msg.warn(f"  - {issue}")
        
        msg.info("")
        msg.info("Para corrigir, execute:")
        for fix in fixes:
            msg.info(f"  {fix}")
        
        return False
    else:
        msg.good("Todas as dependencias estao corretas!")
        return True

if __name__ == "__main__":
    success = check_and_fix_dependencies()
    sys.exit(0 if success else 1)

