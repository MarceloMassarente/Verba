#!/usr/bin/env python3
"""
Script para aplicar patches do Verba após update
Lê LOG_COMPLETO_MUDANCAS.md e aplica mudanças automaticamente
"""

import os
import sys
import shutil
from pathlib import Path
from typing import List, Dict
import re

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

# Patches definidos
PATCHES = {
    "api_startup": {
        "file": "goldenverba/server/api.py",
        "after": "load_dotenv()",
        "insert": '''# Carrega extensões ANTES de criar managers
# Isso garante que plugins apareçam na lista de componentes
try:
    import verba_extensions.startup
    from verba_extensions.startup import initialize_extensions
    plugin_manager, version_checker = initialize_extensions()
    if plugin_manager:
        msg.good(f"Extensoes carregadas: {len(plugin_manager.list_plugins())} plugins")
except ImportError:
    msg.info("Extensoes nao disponiveis (continuando sem extensoes)")
except Exception as e:
    msg.warn(f"Erro ao carregar extensoes: {str(e)} (continuando sem extensoes)")
''',
        "description": "Carregamento de extensões no startup"
    },
    "managers_sentence_transformers": {
        "file": "goldenverba/components/managers.py",
        "find": "from goldenverba.components.embedding.OpenAIEmbedder import OpenAIEmbedder",
        "after_find": True,
        "insert": "from goldenverba.components.embedding.SentenceTransformersEmbedder import (\n    SentenceTransformersEmbedder,\n)",
        "description": "Import SentenceTransformersEmbedder"
    },
    "managers_embedders_list": {
        "file": "goldenverba/components/managers.py",
        "find": "embedders = [\n        OllamaEmbedder(),",
        "insert_after": True,
        "insert": "        SentenceTransformersEmbedder(),",
        "description": "Adicionar SentenceTransformersEmbedder na lista"
    }
}

def apply_patch(file_path: Path, patch_config: Dict) -> bool:
    """Aplica um patch em um arquivo"""
    if not file_path.exists():
        print_error(f"Arquivo não encontrado: {file_path}")
        return False
    
    content = file_path.read_text(encoding='utf-8')
    original_content = content
    
    try:
        if "after" in patch_config:
            # Inserir após linha específica
            after_line = patch_config["after"]
            if after_line in content:
                # Verificar se já foi aplicado
                if patch_config["insert"].strip() in content:
                    print_warning(f"Patch já aplicado: {patch_config['description']}")
                    return True
                
                content = content.replace(
                    after_line,
                    after_line + "\n" + patch_config["insert"]
                )
                print_success(f"Patch aplicado: {patch_config['description']}")
            else:
                print_error(f"Linha não encontrada: {after_line[:50]}...")
                return False
        
        elif "find" in patch_config:
            # Encontrar e inserir próximo
            find_line = patch_config["find"]
            if find_line in content:
                # Verificar se já foi aplicado
                if patch_config.get("insert") and patch_config["insert"].strip() in content:
                    print_warning(f"Patch já aplicado: {patch_config['description']}")
                    return True
                
                if patch_config.get("after_find"):
                    # Inserir após a linha encontrada
                    content = content.replace(
                        find_line,
                        find_line + "\n" + patch_config["insert"]
                    )
                else:
                    # Substituir linha encontrada
                    content = content.replace(
                        find_line,
                        patch_config["insert"]
                    )
                print_success(f"Patch aplicado: {patch_config['description']}")
            else:
                print_error(f"Padrão não encontrado: {find_line[:50]}...")
                return False
        
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True
        else:
            print_warning(f"Nenhuma mudança necessária: {patch_config['description']}")
            return True
    
    except Exception as e:
        print_error(f"Erro ao aplicar patch: {str(e)}")
        return False

def main():
    """Função principal"""
    print_info("🔄 Aplicador de Patches para Verba")
    print_info("=" * 50)
    
    # Verifica se está no diretório correto
    if not Path("goldenverba").exists():
        print_error("Diretório goldenverba não encontrado!")
        print_error("Execute este script na raiz do projeto Verba")
        sys.exit(1)
    
    # Verifica se há backup
    backup_exists = Path("goldenverba_backup").exists()
    if not backup_exists:
        print_warning("Backup não encontrado. Recomendado fazer backup antes!")
        response = input("Continuar mesmo assim? (s/n): ")
        if response.lower() != 's':
            print_info("Operação cancelada")
            sys.exit(0)
    
    print_info("\nAplicando patches...")
    print_info("-" * 50)
    
    applied = 0
    failed = 0
    
    for patch_name, patch_config in PATCHES.items():
        file_path = Path(patch_config["file"])
        print_info(f"\nProcessando: {patch_name}")
        
        if apply_patch(file_path, patch_config):
            applied += 1
        else:
            failed += 1
    
    print_info("\n" + "=" * 50)
    print_info("Resumo:")
    print_success(f"Patches aplicados: {applied}")
    if failed > 0:
        print_error(f"Patches falharam: {failed}")
    
    print_info("\n⚠️  IMPORTANTE:")
    print_warning("1. Método connect_to_custom() precisa ser aplicado MANUALMENTE")
    print_warning("2. Ver PATCH_CONNECT_TO_CUSTOM.md para detalhes")
    print_warning("3. Teste o sistema após aplicar patches!")
    
    if failed == 0:
        print_success("\n✅ Todos os patches automáticos foram aplicados!")
    else:
        print_error("\n❌ Alguns patches falharam. Revise manualmente.")

if __name__ == "__main__":
    main()

