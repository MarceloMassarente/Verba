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
    },
    "verba_manager_etl_pre_chunking": {
        "file": "goldenverba/verba_manager.py",
        "find": "# Check if ETL is enabled BEFORE chunking",
        "after_find": True,
        "insert": '''            # FASE 1: ETL Pré-Chunking (extrai entidades do documento completo)
            # ⚠️ PATCH: Integração de ETL pré-chunking via hook
            # Documentado em: verba_extensions/patches/README_PATCHES.md
            # Ao atualizar Verba, verificar se este patch ainda funciona
            if enable_etl:
                try:
                    from verba_extensions.integration.chunking_hook import apply_etl_pre_chunking
                    document = apply_etl_pre_chunking(document, enable_etl=True)
                    msg.info(f"[ETL-PRE] ✅ Entidades extraídas antes do chunking - chunking será entity-aware")
                except ImportError:
                    msg.warn(f"[ETL-PRE] Hook de ETL pré-chunking não disponível (continuando sem)")
                except Exception as e:
                    msg.warn(f"[ETL-PRE] Erro no ETL pré-chunking (não crítico, continuando): {str(e)}")
            ''',
        "description": "ETL Pré-Chunking Hook - extrai entidades antes do chunking para entity-aware chunking"
    },
    "api_pydantic_dict_fix": {
        "file": "goldenverba/server/api.py",
        "find": "rag_config = payload.RAG.dict()",
        "insert": """        # PATCH: Fix Pydantic/dict incompatibility for payload.RAG
        # Ensures compatibility with both dict (runtime) and Pydantic models (validation)
        if isinstance(payload.RAG, dict):
            rag_config = payload.RAG
        elif hasattr(payload.RAG, 'model_dump'):
            rag_config = payload.RAG.model_dump()
        else:
            rag_config = payload.RAG.dict()""",
        "description": "Fix AttributeError: 'dict' object has no attribute 'dict' in /api/query"
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

def get_verba_version() -> str:
    """Obtém a versão do Verba instalado"""
    try:
        import setup
        if hasattr(setup, 'version'):
            return setup.version
        # Tenta pegar do goldenverba
        import goldenverba
        if hasattr(goldenverba, '__version__'):
            return goldenverba.__version__
        return "unknown"
    except:
        return "unknown"

def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Aplica patches automáticos no Verba',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts/apply_patches.py --version 2.1.3
  python scripts/apply_patches.py --dry-run
  python scripts/apply_patches.py --auto
        """
    )
    parser.add_argument(
        '--version',
        type=str,
        help='Versão do Verba (ex: 2.1.3). Se não especificado, detecta automaticamente.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Modo simulação - não aplica patches, apenas mostra o que seria feito'
    )
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Aplica patches automaticamente sem pedir confirmação'
    )
    
    args = parser.parse_args()
    
    print_info("🔄 Aplicador de Patches para Verba")
    print_info("=" * 50)
    
    # Verifica se está no diretório correto
    if not Path("goldenverba").exists():
        print_error("Diretório goldenverba não encontrado!")
        print_error("Execute este script na raiz do projeto Verba")
        sys.exit(1)
    
    # Detecta versão
    version = args.version or get_verba_version()
    if version == "unknown":
        print_warning("Não foi possível detectar versão do Verba")
        version = input("Digite a versão do Verba (ex: 2.1.3): ").strip()
        if not version:
            print_error("Versão é obrigatória")
            sys.exit(1)
    
    print_info(f"Versão do Verba: {version}")
    
    # Verifica se há patches para esta versão
    patches_dir = Path(f"patches/{version}")
    if patches_dir.exists():
        print_info(f"📁 Patches encontrados em: patches/{version}/")
        print_info(f"   Para detalhes, veja: patches/{version}/README.md")
    else:
        print_warning(f"⚠️  Diretório de patches não encontrado: patches/{version}/")
        print_warning("   Usando patches padrão (pode não estar atualizado para esta versão)")
    
    # Verifica se há backup
    if not args.auto and not args.dry_run:
        backup_exists = Path("goldenverba_backup").exists()
        if not backup_exists:
            print_warning("Backup não encontrado. Recomendado fazer backup antes!")
            response = input("Continuar mesmo assim? (s/n): ")
            if response.lower() != 's':
                print_info("Operação cancelada")
                sys.exit(0)
    
    if args.dry_run:
        print_info("\n🔍 Modo DRY-RUN - Nenhuma mudança será aplicada")
        print_info("-" * 50)
    
    print_info("\nAplicando patches...")
    print_info("-" * 50)
    
    applied = 0
    failed = 0
    skipped = 0
    
    for patch_name, patch_config in PATCHES.items():
        file_path = Path(patch_config["file"])
        print_info(f"\nProcessando: {patch_name}")
        print_info(f"   Arquivo: {patch_config['file']}")
        print_info(f"   Descrição: {patch_config['description']}")
        
        if args.dry_run:
            # Apenas verifica se patch já está aplicado
            content = file_path.read_text(encoding='utf-8')
            if patch_config["insert"].strip() in content:
                print_warning(f"   ⚠️  Patch já aplicado (seria pulado)")
                skipped += 1
            else:
                print_success(f"   ✅ Patch seria aplicado")
                applied += 1
        else:
            if apply_patch(file_path, patch_config):
                applied += 1
            else:
                failed += 1
    
    print_info("\n" + "=" * 50)
    print_info("Resumo:")
    if args.dry_run:
        print_success(f"Patches que seriam aplicados: {applied}")
        print_warning(f"Patches já aplicados: {skipped}")
    else:
        print_success(f"Patches aplicados: {applied}")
        if failed > 0:
            print_error(f"Patches falharam: {failed}")
    
    print_info("\n⚠️  IMPORTANTE:")
    print_warning("1. Patches complexos precisam ser aplicados MANUALMENTE:")
    print_warning("   - connect_to_custom() (managers.py)")
    print_warning("   - connect_to_cluster() (managers.py)")
    print_warning("   - CORS middleware (api.py)")
    print_warning("   - get_models() (OpenAIGenerator.py, AnthropicGenerator.py)")
    print_warning("2. Veja: patches/{}/README.md para detalhes".format(version))
    print_warning("3. Veja: GUIA_APLICAR_PATCHES_UPDATE.md para guia completo")
    print_warning("4. TESTE o sistema após aplicar patches!")
    
    if args.dry_run:
        print_info("\n💡 Execute sem --dry-run para aplicar os patches")
    elif failed == 0 and applied > 0:
        print_success("\n✅ Todos os patches automáticos foram aplicados!")
    elif failed == 0 and applied == 0:
        print_warning("\n⚠️  Todos os patches já estavam aplicados")
    else:
        print_error("\n❌ Alguns patches falharam. Revise manualmente.")

if __name__ == "__main__":
    main()

