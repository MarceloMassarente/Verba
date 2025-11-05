#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para encontrar o padrão exato de repetição que aparece no Verba
Busca especificamente por "posicionamento da Flow neste 1234562.21"
"""

import sys
import io
from pathlib import Path

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from pypdf import PdfReader
except ImportError:
    print("❌ pypdf não instalado")
    sys.exit(1)

# Procura o arquivo na pasta atual
pdf_file = None
for pdf in Path('.').glob('*.pdf'):
    if 'Flow Executive Finders' in pdf.name:
        pdf_file = pdf
        break

if not pdf_file:
    print("❌ Arquivo PDF não encontrado")
    sys.exit(1)

print(f"📄 Analisando: {pdf_file}\n")

reader = PdfReader(pdf_file)
all_text = "\n\n".join(page.extract_text() for page in reader.pages)
lines = all_text.split('\n')

# Procura o padrão específico mencionado pelo usuário
print("🔍 Buscando padrão 'posicionamento da Flow neste 1234562.21':\n")
print("=" * 80)

# Busca linhas contendo "posicionamento" e "Flow"
pattern_lines = []
for i, line in enumerate(lines):
    line_stripped = line.strip()
    if 'posicionamento' in line_stripped.lower() and 'flow' in line_stripped.lower():
        pattern_lines.append((i+1, line_stripped))

if pattern_lines:
    print(f"✅ Encontradas {len(pattern_lines)} linhas com 'posicionamento' e 'Flow':\n")
    for line_num, line in pattern_lines[:10]:
        print(f"Linha {line_num}: {line[:100]}")
else:
    print("⚠️  Nenhuma linha encontrada com 'posicionamento' e 'Flow' juntos")
    print("\n🔍 Buscando apenas 'posicionamento':\n")
    pos_lines = [(i+1, l.strip()) for i, l in enumerate(lines) if 'posicionamento' in l.strip().lower()]
    for line_num, line in pos_lines[:10]:
        print(f"Linha {line_num}: {line[:100]}")

# Procura padrão de repetição progressiva
print("\n" + "=" * 80)
print("🔍 Buscando padrão de repetição progressiva:\n")

# Busca sequências de linhas que começam com variações do mesmo texto
for i in range(len(lines) - 5):
    window = [l.strip() for l in lines[i:i+10] if l.strip()]
    
    # Verifica se há padrão de corte progressivo
    if len(window) >= 3:
        # Procura por "posicionamento" ou "Flow" neste bloco
        has_pos = any('posicionamento' in l.lower() or 'flow' in l.lower() for l in window)
        
        if has_pos:
            # Verifica se há linhas progressivamente cortadas
            for j in range(len(window) - 1):
                curr = window[j]
                next_l = window[j + 1]
                
                # Padrão: linha atual contém a próxima ou vice-versa
                if len(curr) > 10 and len(next_l) > 10:
                    if (next_l in curr and curr.startswith(next_l)) or \
                       (curr in next_l and next_l.startswith(curr)):
                        # Verifica se é o padrão específico
                        if 'posicionamento' in curr.lower() or 'posicionamento' in next_l.lower():
                            print(f"⚠️  PADRÃO ENCONTRADO nas linhas {i+j+1}-{i+j+2}:")
                            print(f"   '{curr[:70]}'")
                            print(f"   '{next_l[:70]}'")
                            print()

print("=" * 80)
print("📊 Resumo:\n")

# Conta duplicatas
unique_lines = set()
duplicates = []
for i, line in enumerate(lines):
    line_stripped = line.strip()
    if line_stripped:
        if line_stripped in unique_lines:
            duplicates.append((i+1, line_stripped[:60]))
        unique_lines.add(line_stripped)

print(f"Total de linhas: {len(lines)}")
print(f"Linhas únicas: {len(unique_lines)}")
print(f"Duplicatas: {len(duplicates)} ({len(duplicates)/len(lines)*100:.1f}%)")

if duplicates:
    print(f"\nPrimeiras 10 duplicatas:")
    for line_num, text in duplicates[:10]:
        print(f"  Linha {line_num}: {text}...")


