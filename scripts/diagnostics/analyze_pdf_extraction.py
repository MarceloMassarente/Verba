#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para analisar extração de PDF e identificar problemas de fragmentação
"""

import sys
import os
from pathlib import Path

# Configura encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from pypdf import PdfReader
except ImportError:
    print("❌ pypdf não instalado. Execute: pip install pypdf")
    sys.exit(1)

def analyze_pdf_extraction(pdf_path: str):
    """Analisa a extração de texto do PDF"""
    # Tenta normalizar o caminho para lidar com encoding
    try:
        # Tenta abrir o arquivo diretamente para verificar se existe
        with open(pdf_path, 'rb') as test_file:
            pass
    except FileNotFoundError:
        # Tenta encontrar o arquivo com encoding alternativo
        try:
            # Lista arquivos no diretório para encontrar o correto
            dir_path = os.path.dirname(pdf_path)
            filename = os.path.basename(pdf_path)
            if os.path.exists(dir_path):
                files = os.listdir(dir_path)
                # Procura arquivo que começa com "Dossi"
                matching = [f for f in files if f.startswith('Dossi') and f.endswith('.pdf')]
                if matching:
                    pdf_path = os.path.join(dir_path, matching[0])
                    print(f"📁 Arquivo encontrado com nome alternativo: {matching[0]}")
                else:
                    print(f"❌ Arquivo não encontrado: {pdf_path}")
                    print(f"📁 Arquivos PDF no diretório: {[f for f in files if f.endswith('.pdf')]}")
                    return
            else:
                print(f"❌ Diretório não encontrado: {dir_path}")
                return
        except Exception as e:
            print(f"❌ Erro ao buscar arquivo: {str(e)}")
            return
    
    print(f"📄 Analisando: {pdf_path}\n")
    print("=" * 80)
    
    try:
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            total_pages = len(reader.pages)
            print(f"📊 Total de páginas: {total_pages}\n")
            
            # Analisa primeiras páginas em detalhes
            pages_to_analyze = min(3, total_pages)
            
            for page_num in range(pages_to_analyze):
                page = reader.pages[page_num]
                print(f"\n{'='*80}")
                print(f"📄 PÁGINA {page_num + 1}/{total_pages}")
                print(f"{'='*80}\n")
                
                # Extração padrão
                text_standard = page.extract_text()
                lines_standard = text_standard.split('\n')
                
                print(f"📝 Extração padrão:")
                print(f"   - Total de linhas: {len(lines_standard)}")
                print(f"   - Total de caracteres: {len(text_standard)}")
                
                # Verifica linhas repetidas
                unique_lines = set()
                duplicate_count = 0
                fragment_lines = []
                
                for i, line in enumerate(lines_standard):
                    line_stripped = line.strip()
                    if line_stripped:
                        # Verifica se é duplicata
                        if line_stripped in unique_lines:
                            duplicate_count += 1
                            if len(fragment_lines) < 10:  # Mostra primeiras 10
                                fragment_lines.append((i+1, line_stripped[:80]))
                        unique_lines.add(line_stripped)
                
                print(f"   - Linhas únicas: {len(unique_lines)}")
                print(f"   - Linhas duplicadas: {duplicate_count}")
                
                if fragment_lines:
                    print(f"\n   ⚠️  Primeiras linhas duplicadas/fragmentadas encontradas:")
                    for line_num, line_text in fragment_lines[:5]:
                        print(f"      Linha {line_num}: {line_text}...")
                
                # Tenta extração com layout (se disponível)
                try:
                    text_layout = page.extract_text(layout_mode=True)
                    if text_layout != text_standard:
                        lines_layout = text_layout.split('\n')
                        print(f"\n📝 Extração com layout_mode=True:")
                        print(f"   - Total de linhas: {len(lines_layout)}")
                        print(f"   - Total de caracteres: {len(text_layout)}")
                        print(f"   ✅ Layout mode produziu resultado diferente!")
                except Exception as e:
                    print(f"\n📝 Layout mode não disponível ou erro: {str(e)}")
                
                # Mostra amostra do texto extraído
                print(f"\n📋 Amostra do texto extraído (primeiras 10 linhas):")
                print("-" * 80)
                for i, line in enumerate(lines_standard[:10]):
                    if line.strip():
                        print(f"{i+1:3d}: {line[:70]}")
                print("-" * 80)
                
                # Detecta padrões de fragmentação
                print(f"\n🔍 Análise de fragmentação:")
                fragment_patterns = []
                for i in range(len(lines_standard) - 1):
                    curr = lines_standard[i].strip()
                    next_line = lines_standard[i + 1].strip()
                    
                    # Verifica se próxima linha é fragmento da anterior
                    if curr and next_line and len(next_line) > 5:
                        if next_line in curr or curr in next_line:
                            if len(fragment_patterns) < 5:
                                fragment_patterns.append((i+1, curr[:50], next_line[:50]))
                
                if fragment_patterns:
                    print(f"   ⚠️  Encontrados {len(fragment_patterns)} padrões de fragmentação:")
                    for line_num, curr, next_l in fragment_patterns:
                        print(f"      Linha {line_num}: '{curr}' → '{next_l}'")
                else:
                    print(f"   ✅ Nenhum padrão óbvio de fragmentação detectado")
            
            # Resumo geral
            print(f"\n{'='*80}")
            print(f"📊 RESUMO GERAL")
            print(f"{'='*80}\n")
            
            all_text = "\n\n".join(page.extract_text() for page in reader.pages)
            all_lines = all_text.split('\n')
            unique_all = set(line.strip() for line in all_lines if line.strip())
            
            print(f"Total de linhas extraídas: {len(all_lines)}")
            print(f"Linhas únicas: {len(unique_all)}")
            print(f"Duplicação: {len(all_lines) - len(unique_all)} linhas")
            print(f"Taxa de duplicação: {((len(all_lines) - len(unique_all)) / len(all_lines) * 100):.1f}%")
            
    except Exception as e:
        print(f"❌ Erro ao analisar PDF: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analyze_pdf_extraction.py <caminho_do_pdf>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    analyze_pdf_extraction(pdf_path)

