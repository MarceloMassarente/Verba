"""
Script para executar todos os testes do Verba
"""
import sys
import os

# Adicionar raiz do projeto ao path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import subprocess
from wasabi import msg

def run_test(test_file):
    """Executa um teste e retorna True se passou"""
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def main():
    msg.info("=" * 60)
    msg.info("EXECUTANDO TODOS OS TESTES DO VERBA")
    msg.info("=" * 60)
    
    tests = [
        ("Testes de Acesso Weaviate", "test_weaviate_access.py"),
        ("Testes Named Vectors v4", "test_named_vectors_v4_simple.py"),
    ]
    
    results = []
    
    for test_name, test_file in tests:
        msg.info(f"\n[{test_name}]")
        msg.info(f"  Arquivo: {test_file}")
        
        passed, stdout, stderr = run_test(test_file)
        
        if passed:
            msg.good(f"  [OK] {test_name} passou")
            results.append((test_name, True))
        else:
            msg.fail(f"  [FAIL] {test_name} falhou")
            if stderr:
                msg.warn(f"  Erro: {stderr[:200]}")
            results.append((test_name, False))
    
    # Resumo
    msg.info("\n" + "=" * 60)
    msg.info("RESUMO DOS TESTES")
    msg.info("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "[OK]" if passed else "[FAIL]"
        msg.info(f"{status} {test_name}")
    
    msg.info(f"\nTotal: {passed_count}/{total_count} testes passaram")
    
    if passed_count == total_count:
        msg.good("\n[OK] TODOS OS TESTES PASSARAM!")
        return 0
    else:
        msg.warn(f"\n[WARN] {total_count - passed_count} teste(s) falharam")
        return 1

if __name__ == "__main__":
    exit(main())

