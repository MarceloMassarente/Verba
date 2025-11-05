#!/usr/bin/env python3
"""
Script de Verificação de Patches
Verifica se patches foram aplicados corretamente no código
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Cores para output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

# Definição de patches para verificar
PATCHES_TO_VERIFY = {
    "api_startup": {
        "file": "goldenverba/server/api.py",
        "markers": [
            "verba_extensions.startup",
            "initialize_extensions",
            "Extensoes carregadas"
        ],
        "description": "Carregamento de extensões no startup"
    },
    "api_cors": {
        "file": "goldenverba/server/api.py",
        "markers": [
            ".railway.app",
            "ALLOWED_ORIGINS",
            "normalize_url"
        ],
        "description": "CORS middleware para Railway"
    },
    "managers_sentence_transformers": {
        "file": "goldenverba/components/managers.py",
        "markers": [
            "SentenceTransformersEmbedder",
            "from goldenverba.components.embedding.SentenceTransformersEmbedder"
        ],
        "description": "SentenceTransformersEmbedder"
    },
    "managers_connect_to_cluster": {
        "file": "goldenverba/components/managers.py",
        "markers": [
            "WEAVIATE_HTTP_HOST",
            "WEAVIATE_GRPC_HOST",
            "PaaS configuration"
        ],
        "description": "connect_to_cluster() - Priorização PaaS"
    },
    "managers_connect_to_custom": {
        "file": "goldenverba/components/managers.py",
        "markers": [
            ".railway.app",
            "connect_to_custom",
            "http_secure=True",
            "grpc_host"
        ],
        "description": "connect_to_custom() - Railway/v3/v4"
    },
    "openai_generator_get_models": {
        "file": "goldenverba/components/generation/OpenAIGenerator.py",
        "markers": [
            "get_models",
            "gpt-",
            "o1-"
        ],
        "description": "OpenAIGenerator.get_models() - Filtro melhorado"
    },
    "anthropic_generator_get_models": {
        "file": "goldenverba/components/generation/AnthropicGenerator.py",
        "markers": [
            "get_models",
            "claude-",
            "anthropic"
        ],
        "description": "AnthropicGenerator.get_models() - Método adicionado"
    }
}

def verify_patch(patch_name: str, patch_config: Dict) -> Tuple[bool, List[str]]:
    """Verifica se um patch foi aplicado"""
    file_path = Path(patch_config["file"])
    issues = []
    
    if not file_path.exists():
        return False, [f"Arquivo não encontrado: {file_path}"]
    
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Verifica cada marcador
        missing_markers = []
        for marker in patch_config["markers"]:
            if marker not in content:
                missing_markers.append(marker)
        
        if missing_markers:
            issues.append(f"Marcadores faltando: {', '.join(missing_markers)}")
            return False, issues
        else:
            return True, []
    
    except Exception as e:
        return False, [f"Erro ao ler arquivo: {str(e)}"]

def get_verba_version() -> str:
    """Obtém a versão do Verba instalado"""
    try:
        import setup
        if hasattr(setup, 'version'):
            return setup.version
        import goldenverba
        if hasattr(goldenverba, '__version__'):
            return goldenverba.__version__
        return "unknown"
    except:
        return "unknown"

def main():
    parser = argparse.ArgumentParser(
        description='Verifica se patches foram aplicados corretamente',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--version',
        type=str,
        help='Versão do Verba (ex: 2.1.3). Se não especificado, detecta automaticamente.'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Verifica todos os patches'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Gera relatório detalhado'
    )
    parser.add_argument(
        '--patch',
        type=str,
        help='Verifica apenas um patch específico'
    )
    
    args = parser.parse_args()
    
    print_info("🔍 Verificador de Patches para Verba")
    print_info("=" * 50)
    
    # Verifica se está no diretório correto
    if not Path("goldenverba").exists():
        print_error("Diretório goldenverba não encontrado!")
        print_error("Execute este script na raiz do projeto Verba")
        sys.exit(1)
    
    # Detecta versão
    version = args.version or get_verba_version()
    print_info(f"Versão do Verba: {version}")
    
    # Filtra patches a verificar
    patches_to_check = {}
    if args.patch:
        if args.patch in PATCHES_TO_VERIFY:
            patches_to_check = {args.patch: PATCHES_TO_VERIFY[args.patch]}
        else:
            print_error(f"Patch não encontrado: {args.patch}")
            print_info(f"Patches disponíveis: {', '.join(PATCHES_TO_VERIFY.keys())}")
            sys.exit(1)
    else:
        patches_to_check = PATCHES_TO_VERIFY
    
    print_info(f"\nVerificando {len(patches_to_check)} patches...")
    print_info("-" * 50)
    
    results = {}
    total_ok = 0
    total_failed = 0
    
    for patch_name, patch_config in patches_to_check.items():
        print_info(f"\n{patch_name}:")
        print_info(f"   {patch_config['description']}")
        print_info(f"   Arquivo: {patch_config['file']}")
        
        is_ok, issues = verify_patch(patch_name, patch_config)
        results[patch_name] = {
            'ok': is_ok,
            'issues': issues,
            'config': patch_config
        }
        
        if is_ok:
            print_success(f"   ✅ Patch aplicado corretamente")
            total_ok += 1
        else:
            print_error(f"   ❌ Patch NÃO aplicado ou incompleto")
            for issue in issues:
                print_error(f"      - {issue}")
            total_failed += 1
    
    # Relatório final
    print_info("\n" + "=" * 50)
    print_info("Resumo:")
    print_success(f"Patches OK: {total_ok}")
    if total_failed > 0:
        print_error(f"Patches com problemas: {total_failed}")
    
    # Relatório detalhado
    if args.report:
        print_info("\n" + "=" * 50)
        print_info("Relatório Detalhado:")
        
        for patch_name, result in results.items():
            print_info(f"\n{patch_name}:")
            print_info(f"   Status: {'✅ OK' if result['ok'] else '❌ FALHOU'}")
            print_info(f"   Arquivo: {result['config']['file']}")
            print_info(f"   Descrição: {result['config']['description']}")
            if result['issues']:
                print_info(f"   Problemas:")
                for issue in result['issues']:
                    print_error(f"      - {issue}")
            print_info(f"   Marcadores esperados:")
            for marker in result['config']['markers']:
                print_info(f"      - {marker}")
    
    # Sugestões
    if total_failed > 0:
        print_info("\n" + "=" * 50)
        print_info("💡 Próximos Passos:")
        print_warning("1. Veja: patches/{}/README.md para aplicar patches faltantes".format(version))
        print_warning("2. Veja: GUIA_APLICAR_PATCHES_UPDATE.md para guia completo")
        print_warning("3. Execute: python scripts/apply_patches.py para patches automáticos")
    
    # Exit code
    if total_failed > 0:
        sys.exit(1)
    else:
        print_success("\n✅ Todos os patches verificados estão aplicados corretamente!")
        sys.exit(0)

if __name__ == "__main__":
    main()

