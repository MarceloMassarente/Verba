#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para comparar diferentes bibliotecas de extração de PDF
Identifica qual biblioteca produz melhor resultado para PDFs multi-coluna
"""

import sys
import os
import io

# Configura encoding para Windows
if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def find_pdf_file(search_path: str):
    """Encontra arquivo PDF no caminho especificado"""
    # Tenta o caminho direto
    if os.path.exists(search_path):
        return search_path
    
    # Tenta encontrar no diretório
    dir_path = os.path.dirname(search_path)
    if os.path.exists(dir_path):
        files = os.listdir(dir_path)
        # Procura qualquer PDF que comece com "Dossi" ou "Flow"
        matching = [f for f in files if f.endswith('.pdf') and ('Dossi' in f or 'Flow' in f)]
        if matching:
            return os.path.join(dir_path, matching[0])
    
    return None

def test_pypdf(pdf_bytes: bytes):
    """Testa extração com pypdf"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        
        # Método 1: Padrão
        text_standard = "\n\n".join(page.extract_text() for page in reader.pages)
        
        # Método 2: Tentar com diferentes parâmetros
        text_alt = []
        for page in reader.pages:
            try:
                # Tenta diferentes métodos se disponíveis
                text = page.extract_text()
                text_alt.append(text)
            except:
                pass
        
        return {
            'name': 'pypdf',
            'standard': text_standard,
            'lines': len(text_standard.split('\n')),
            'chars': len(text_standard),
            'available': True
        }
    except ImportError:
        return {'name': 'pypdf', 'available': False, 'error': 'Não instalado'}
    except Exception as e:
        return {'name': 'pypdf', 'available': True, 'error': str(e)}

def test_pdfplumber(pdf_bytes: bytes):
    """Testa extração com pdfplumber"""
    try:
        import pdfplumber
        
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            # Método 1: Padrão
            text_standard = "\n\n".join(page.extract_text() for page in pdf.pages)
            
            # Método 2: Com layout
            text_layout = "\n\n".join(
                page.extract_text(layout=True) for page in pdf.pages
            )
            
            return {
                'name': 'pdfplumber',
                'standard': text_standard,
                'layout': text_layout,
                'lines_standard': len(text_standard.split('\n')),
                'lines_layout': len(text_layout.split('\n')),
                'chars_standard': len(text_standard),
                'chars_layout': len(text_layout),
                'available': True
            }
    except ImportError:
        return {'name': 'pdfplumber', 'available': False, 'error': 'Não instalado (pip install pdfplumber)'}
    except Exception as e:
        return {'name': 'pdfplumber', 'available': True, 'error': str(e)}

def test_pymupdf(pdf_bytes: bytes):
    """Testa extração com PyMuPDF (fitz)"""
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Método 1: Padrão
        text_standard = "\n\n".join(page.get_text("text") for page in doc)
        
        # Método 2: Com sort (ordena por posição)
        text_sorted = "\n\n".join(page.get_text("text", sort=True) for page in doc)
        
        # Método 3: Blocks (preserva layout)
        text_blocks = []
        for page in doc:
            blocks = page.get_text("blocks", sort=True)
            page_text = "\n".join([block[4] for block in blocks])
            text_blocks.append(page_text)
        text_blocks = "\n\n".join(text_blocks)
        
        doc.close()
        
        return {
            'name': 'PyMuPDF (fitz)',
            'standard': text_standard,
            'sorted': text_sorted,
            'blocks': text_blocks,
            'lines_standard': len(text_standard.split('\n')),
            'lines_sorted': len(text_sorted.split('\n')),
            'lines_blocks': len(text_blocks.split('\n')),
            'chars_standard': len(text_standard),
            'chars_sorted': len(text_sorted),
            'chars_blocks': len(text_blocks),
            'available': True
        }
    except ImportError:
        return {'name': 'PyMuPDF (fitz)', 'available': False, 'error': 'Não instalado (pip install pymupdf)'}
    except Exception as e:
        return {'name': 'PyMuPDF (fitz)', 'available': True, 'error': str(e)}

def test_pypdf2(pdf_bytes: bytes):
    """Testa extração com PyPDF2 (versão antiga)"""
    try:
        import PyPDF2
        
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text = "\n\n".join(page.extract_text() for page in reader.pages)
        
        return {
            'name': 'PyPDF2',
            'standard': text,
            'lines': len(text.split('\n')),
            'chars': len(text),
            'available': True
        }
    except ImportError:
        return {'name': 'PyPDF2', 'available': False, 'error': 'Não instalado'}
    except Exception as e:
        return {'name': 'PyPDF2', 'available': True, 'error': str(e)}

def analyze_fragmentation(text: str, name: str):
    """Analisa fragmentação e repetição no texto"""
    lines = text.split('\n')
    unique_lines = set()
    duplicates = []
    fragments = []
    
    prev_line = None
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if line_stripped and len(line_stripped) > 5:
            # Verifica duplicatas
            if line_stripped in unique_lines:
                if len(duplicates) < 10:
                    duplicates.append((i+1, line_stripped[:60]))
            unique_lines.add(line_stripped)
            
            # Verifica fragmentos (linha atual é parte da anterior ou vice-versa)
            if prev_line and len(prev_line) > 10 and len(line_stripped) > 10:
                if line_stripped in prev_line or prev_line in line_stripped:
                    if len(fragments) < 10:
                        fragments.append((i+1, prev_line[:50], line_stripped[:50]))
            
            prev_line = line_stripped
    
    return {
        'total_lines': len(lines),
        'unique_lines': len(unique_lines),
        'duplicates': len(lines) - len(unique_lines),
        'duplication_rate': ((len(lines) - len(unique_lines)) / len(lines) * 100) if lines else 0,
        'duplicate_examples': duplicates[:5],
        'fragment_examples': fragments[:5]
    }

def compare_readers(pdf_path: str):
    """Compara diferentes bibliotecas de extração de PDF"""
    pdf_file = find_pdf_file(pdf_path)
    if not pdf_file:
        print(f"❌ Arquivo PDF não encontrado: {pdf_path}")
        print("💡 Verifique o caminho ou coloque o arquivo na raiz do projeto")
        return
    
    print(f"📄 Arquivo: {pdf_file}\n")
    print("=" * 80)
    
    # Lê o PDF em bytes
    with open(pdf_file, 'rb') as f:
        pdf_bytes = f.read()
    
    print(f"📊 Tamanho do arquivo: {len(pdf_bytes):,} bytes\n")
    
    # Testa cada biblioteca
    readers = [
        test_pypdf,
        test_pdfplumber,
        test_pymupdf,
        test_pypdf2
    ]
    
    results = []
    for reader_func in readers:
        print(f"🔍 Testando {reader_func.__name__}...")
        try:
            result = reader_func(pdf_bytes)
            results.append(result)
            if result.get('available'):
                print(f"   ✅ Disponível")
            else:
                print(f"   ❌ {result.get('error', 'Indisponível')}")
        except Exception as e:
            print(f"   ❌ Erro: {str(e)}")
            results.append({'name': reader_func.__name__, 'error': str(e)})
    
    print("\n" + "=" * 80)
    print("📊 RESULTADOS COMPARATIVOS")
    print("=" * 80 + "\n")
    
    # Analisa cada resultado
    for result in results:
        if not result.get('available') or 'error' in result:
            print(f"❌ {result['name']}: {result.get('error', 'Indisponível')}\n")
            continue
        
        print(f"📚 {result['name']}")
        print("-" * 80)
        
        # Mostra estatísticas básicas
        if 'standard' in result:
            analysis = analyze_fragmentation(result['standard'], result['name'])
            print(f"   Método Padrão:")
            print(f"   - Linhas: {analysis['total_lines']}")
            print(f"   - Linhas únicas: {analysis['unique_lines']}")
            print(f"   - Duplicatas: {analysis['duplicates']} ({analysis['duplication_rate']:.1f}%)")
            
            if analysis['duplicate_examples']:
                print(f"   - Exemplos de duplicatas:")
                for line_num, text in analysis['duplicate_examples'][:3]:
                    print(f"     Linha {line_num}: {text}...")
            
            if analysis['fragment_examples']:
                print(f"   - Exemplos de fragmentação:")
                for line_num, prev, curr in analysis['fragment_examples'][:3]:
                    print(f"     Linha {line_num}: '{prev}' → '{curr}'")
            
            # Mostra amostra do texto
            lines = result['standard'].split('\n')
            print(f"\n   📋 Amostra (primeiras 5 linhas não vazias):")
            count = 0
            for line in lines:
                if line.strip() and count < 5:
                    print(f"      {count+1}: {line[:70]}")
                    count += 1
        
        # Se tem múltiplos métodos, compara
        if 'layout' in result or 'sorted' in result or 'blocks' in result:
            print(f"\n   Métodos Alternativos:")
            if 'layout' in result:
                analysis_layout = analyze_fragmentation(result['layout'], result['name'] + ' (layout)')
                print(f"   - Layout Mode: {analysis_layout['total_lines']} linhas, "
                      f"{analysis_layout['duplication_rate']:.1f}% duplicação")
            
            if 'sorted' in result:
                analysis_sorted = analyze_fragmentation(result['sorted'], result['name'] + ' (sorted)')
                print(f"   - Sort Mode: {analysis_sorted['total_lines']} linhas, "
                      f"{analysis_sorted['duplication_rate']:.1f}% duplicação")
            
            if 'blocks' in result:
                analysis_blocks = analyze_fragmentation(result['blocks'], result['name'] + ' (blocks)')
                print(f"   - Blocks Mode: {analysis_blocks['total_lines']} linhas, "
                      f"{analysis_blocks['duplication_rate']:.1f}% duplicação")
        
        print()
    
    # Recomendação
    print("=" * 80)
    print("💡 RECOMENDAÇÃO")
    print("=" * 80 + "\n")
    
    available_readers = [r for r in results if r.get('available') and 'error' not in r]
    if not available_readers:
        print("❌ Nenhuma biblioteca disponível para teste")
        print("💡 Instale pelo menos uma: pip install pdfplumber ou pip install pymupdf")
        return
    
    # Encontra o melhor (menor taxa de duplicação)
    best = None
    best_rate = 100
    
    for reader in available_readers:
        if 'standard' in reader:
            analysis = analyze_fragmentation(reader['standard'], reader['name'])
            if analysis['duplication_rate'] < best_rate:
                best_rate = analysis['duplication_rate']
                best = reader['name']
        
        # Verifica métodos alternativos
        for method in ['layout', 'sorted', 'blocks']:
            if method in reader:
                analysis = analyze_fragmentation(reader[method], reader['name'])
                if analysis['duplication_rate'] < best_rate:
                    best_rate = analysis['duplication_rate']
                    best = f"{reader['name']} ({method})"
    
    if best:
        print(f"✅ Melhor resultado: {best} ({best_rate:.1f}% duplicação)")
        print(f"\n💡 Recomendação:")
        if 'pdfplumber' in best.lower():
            print("   - Use pdfplumber com layout=True para melhor preservação de colunas")
        elif 'pymupdf' in best.lower() or 'fitz' in best.lower():
            print("   - Use PyMuPDF (fitz) com sort=True para melhor ordenação espacial")
        else:
            print("   - O método atual pode ser melhorado com as técnicas de limpeza implementadas")
    else:
        print("⚠️  Não foi possível determinar o melhor método")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python compare_pdf_readers.py <caminho_do_pdf>")
        print("\nExemplo:")
        print('  python compare_pdf_readers.py "C:\\Users\\marce\\Documentos\\arquivo.pdf"')
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    compare_readers(pdf_path)


