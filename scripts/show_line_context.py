#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
from pypdf import PdfReader

pdf_file = None
for pdf in Path('.').glob('*.pdf'):
    if 'Flow Executive Finders' in pdf.name:
        pdf_file = pdf
        break

if pdf_file:
    reader = PdfReader(pdf_file)
    text = '\n'.join([page.extract_text() for page in reader.pages])
    lines = text.split('\n')
    
    print("Contexto da linha 25 (posicionamento):\n")
    for i in range(20, min(35, len(lines))):
        marker = " >>>" if i == 24 else ""
        print(f'{i+1:3d}: {lines[i][:80]}{marker}')
    
    print("\n\nProcurando padrão de repetição progressiva:\n")
    # Procura sequências de linhas que começam com texto similar
    for i in range(len(lines) - 5):
        window = [l.strip() for l in lines[i:i+10] if l.strip() and len(l.strip()) > 10]
        if len(window) >= 3:
            # Verifica se há padrão de corte progressivo
            for j in range(len(window) - 1):
                curr = window[j]
                next_l = window[j + 1]
                if 'posicionamento' in curr.lower() or 'posicionamento' in next_l.lower():
                    # Verifica se é corte progressivo
                    if (next_l in curr and curr.startswith(next_l)) or \
                       (curr in next_l and next_l.startswith(curr)):
                        print(f"⚠️  Padrão encontrado nas linhas {i+j+1}-{i+j+2}:")
                        print(f"   '{curr[:70]}'")
                        print(f"   '{next_l[:70]}'")
                        print()


