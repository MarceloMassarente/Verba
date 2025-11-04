#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para análise de erros de indentação e problemas estruturais no código Python
"""

import os
import re
import ast
import sys
from pathlib import Path

def check_file_indentation(file_path):
    """Verifica problemas de indentação em um arquivo Python"""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return [f"Erro ao ler arquivo: {e}"]
    
    # Verifica mistura de tabs e espaços
    has_tabs = False
    has_spaces = False
    for i, line in enumerate(lines, 1):
        if line.startswith('\t'):
            has_tabs = True
        if line.startswith(' ') and not line.strip().startswith('#'):
            has_spaces = True
    
    if has_tabs and has_spaces:
        issues.append(f"Linha 1: Arquivo mistura tabs e espaços")
    
    # Verifica indentação inconsistente
    indentation_levels = {}
    for i, line in enumerate(lines, 1):
        if not line.strip() or line.strip().startswith('#'):
            continue
        
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        
        # Verifica se há espaços extras antes de comandos importantes
        if indent > 0:
            # Verifica padrões suspeitos de indentação excessiva
            match = re.match(r'^(\s+)(for|if|try|except|async def|def |class |while|with|return|await|break|continue|raise)', stripped)
            if match:
                indent_str = match.group(1)
                # Se já havia indentação antes, pode ser erro
                if indent > 12 and indent % 4 != 0:
                    issues.append(f"Linha {i}: Indentação suspeita ({indent} espaços) antes de '{stripped[:30]}'")
    
    # Verifica estrutura sintática com AST
    try:
        ast.parse(''.join(lines))
    except SyntaxError as e:
        issues.append(f"Erro de sintaxe: Linha {e.lineno}: {e.msg}")
        if e.text:
            issues.append(f"  Texto: {e.text.strip()}")
    
    # Verifica blocos try/except mal formatados
    in_try = False
    try_indent = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('try:'):
            in_try = True
            try_indent = len(line) - len(line.lstrip())
        elif stripped.startswith('except'):
            if not in_try:
                issues.append(f"Linha {i}: 'except' sem 'try' correspondente")
            else:
                current_indent = len(line) - len(line.lstrip())
                if current_indent != try_indent:
                    issues.append(f"Linha {i}: 'except' com indentação diferente do 'try' (try: {try_indent}, except: {current_indent})")
                in_try = False
                try_indent = 0
    
    # Verifica linhas com múltiplos espaços consecutivos no início (suspeito)
    for i, line in enumerate(lines, 1):
        if line.strip() and not line.strip().startswith('#'):
            # Conta espaços consecutivos no início
            leading_spaces = len(line) - len(line.lstrip())
            if leading_spaces > 0:
                # Verifica se há espaços extras suspeitos
                if leading_spaces > 20:  # Mais de 20 espaços é suspeito
                    issues.append(f"Linha {i}: Indentação muito profunda ({leading_spaces} espaços)")
    
    return issues

def analyze_codebase():
    """Analisa todos os arquivos Python no código"""
    base_path = Path('goldenverba')
    
    if not base_path.exists():
        print("Diretório goldenverba não encontrado")
        return
    
    all_issues = {}
    python_files = list(base_path.rglob('*.py'))
    
    print(f"Analisando {len(python_files)} arquivos Python...\n")
    
    for py_file in python_files:
        issues = check_file_indentation(py_file)
        if issues:
            all_issues[str(py_file)] = issues
    
    # Também verifica arquivos principais na raiz
    root_files = ['goldenverba/verba_manager.py', 'goldenverba/server/api.py']
    for root_file in root_files:
        if Path(root_file).exists():
            issues = check_file_indentation(root_file)
            if issues:
                all_issues[root_file] = issues
    
    # Relatório
    if all_issues:
        print("=" * 80)
        print("PROBLEMAS ENCONTRADOS:")
        print("=" * 80)
        for file_path, issues in all_issues.items():
            print(f"\n[FILE] {file_path}:")
            for issue in issues:
                print(f"  [WARN] {issue}")
        print(f"\n{'=' * 80}")
        print(f"Total de arquivos com problemas: {len(all_issues)}")
    else:
        print("[OK] Nenhum problema de indentacao encontrado!")
    
    return all_issues

if __name__ == "__main__":
    analyze_codebase()

