#!/usr/bin/env python3
"""
Script para converter PDFs para formato JSON do A2 Results Ingestor
Pode processar:
- PDF único (um artigo)
- PDF com múltiplos artigos (separação automática)
"""

import sys
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

try:
    from pypdf import PdfReader
except ImportError:
    print("❌ pypdf não instalado. Execute: pip install pypdf")
    sys.exit(1)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrai todo o texto de um PDF"""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text.strip():
                    text_parts.append(text)
            return "\n\n".join(text_parts)
    except Exception as e:
        print(f"❌ Erro ao ler PDF: {str(e)}")
        return ""


def detect_articles(text: str) -> List[Dict[str, str]]:
    """
    Detecta múltiplos artigos no texto baseado em padrões comuns:
    - Títulos em maiúsculas
    - Linhas vazias duplas/triplas
    - Padrões de data
    """
    articles = []
    
    # Divide por múltiplas quebras de linha (2+ linhas vazias)
    sections = [s.strip() for s in text.split("\n\n\n") if s.strip()]
    
    if len(sections) <= 1:
        # Provavelmente um único artigo
        return [{"title": "", "content": text}]
    
    # Tenta detectar títulos (linhas curtas, possivelmente em maiúsculas)
    for i, section in enumerate(sections):
        lines = section.split("\n")
        title = ""
        content_start = 0
        
        # Procura por título (primeira linha curta, possivelmente título)
        if len(lines) > 0:
            first_line = lines[0].strip()
            # Se primeira linha é curta (<100 chars) e não termina com ponto, pode ser título
            if len(first_line) < 100 and not first_line.endswith('.'):
                title = first_line
                content_start = 1
        
        # Conteúdo é o resto
        content = "\n".join(lines[content_start:]).strip()
        
        if content:
            articles.append({
                "title": title or f"Artigo {i+1}",
                "content": content
            })
    
    return articles


def create_a2_json(
    articles: List[Dict[str, str]],
    pdf_filename: str,
    base_url: str = "doc://"
) -> Dict[str, Any]:
    """
    Cria JSON no formato esperado pelo A2 Results Ingestor
    """
    results = []
    
    for i, article in enumerate(articles):
        url = f"{base_url}{pdf_filename}#article{i+1}"
        if len(articles) == 1:
            url = f"{base_url}{pdf_filename}"
        
        result = {
            "url": url,
            "title": article.get("title", f"Artigo {i+1}"),
            "content": article.get("content", ""),
            "published_at": datetime.now().strftime("%Y-%m-%d"),  # Data atual como padrão
            "metadata": {
                "language": "pt",  # Ajuste se necessário
                "source": pdf_filename,
                "article_index": i + 1
            }
        }
        results.append(result)
    
    return {"results": results}


def main():
    """Função principal"""
    if len(sys.argv) < 2:
        print("📄 Conversor PDF → JSON A2")
        print("=" * 50)
        print("Uso: python pdf_to_a2_json.py <caminho_do_pdf> [opções]")
        print("\nOpções:")
        print("  --output <arquivo.json>   Especifica arquivo de saída")
        print("  --split                   Força separação em múltiplos artigos")
        print("  --no-split                Trata como um único artigo")
        print("\nExemplo:")
        print("  python pdf_to_a2_json.py artigo.pdf")
        print("  python pdf_to_a2_json.py revista.pdf --split --output revista.json")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not os.path.exists(pdf_path):
        print(f"❌ Arquivo não encontrado: {pdf_path}")
        sys.exit(1)
    
    # Opções
    output_path = None
    force_split = False
    no_split = False
    
    for i, arg in enumerate(sys.argv[2:], start=2):
        if arg == "--output" and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
        elif arg == "--split":
            force_split = True
        elif arg == "--no-split":
            no_split = True
    
    print(f"📄 Processando: {pdf_path}")
    
    # Extrai texto
    text = extract_text_from_pdf(pdf_path)
    if not text:
        print("❌ Não foi possível extrair texto do PDF")
        sys.exit(1)
    
    print(f"✅ Texto extraído: {len(text)} caracteres")
    
    # Detecta artigos
    if no_split:
        articles = [{"title": Path(pdf_path).stem, "content": text}]
        print("📝 Tratando como um único artigo")
    elif force_split or len(text.split("\n\n\n")) > 2:
        articles = detect_articles(text)
        print(f"📚 Detectados {len(articles)} artigos")
    else:
        articles = [{"title": Path(pdf_path).stem, "content": text}]
        print("📝 Tratando como um único artigo (use --split para forçar separação)")
    
    # Cria JSON
    pdf_filename = os.path.basename(pdf_path)
    json_data = create_a2_json(articles, pdf_filename)
    
    # Salva arquivo
    if output_path:
        output_file = output_path
    else:
        output_file = Path(pdf_path).stem + "_a2.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ JSON salvo em: {output_file}")
    print(f"📊 {len(json_data['results'])} artigo(s) processado(s)")
    print("\n💡 Próximo passo:")
    print(f"   1. Abra Verba → Import Data")
    print(f"   2. Escolha 'A2 Results Ingestor'")
    print(f"   3. Faça upload de: {output_file}")
    print(f"   4. Ative 'Enable ETL'")


if __name__ == "__main__":
    main()

