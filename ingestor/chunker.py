"""Chunker - divisão de texto em passages"""

import re
import nltk

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

from nltk.tokenize import sent_tokenize

# Regex para headers Markdown
HDR = re.compile(r"(^|\n)(#{1,6}\s.+?$)|(^\n?[A-ZÁÉÍÓÚÂÊÔÃÕÇ].{0,80}\n[-=]{3,}$)", re.M)

def split_into_passages(text: str, max_chars: int = 900, overlap: int = 120):
    """
    Divide texto em passages com detecção de seções
    
    Retorna: [(section_title, first_para, chunk_text), ...]
    """
    if not text:
        return []
    
    out = []
    
    # Divide por seções (headers Markdown ou underline)
    sections = _find_sections(text)
    
    if not sections:
        sections = [("", "", text)]
    
    for section_title, section_first_para, block in sections:
        if not block.strip():
            continue
            
        sents = sent_tokenize(block)
        if not sents:
            out.append((section_title, "", block.strip()))
            continue
        
        # Primeiro parágrafo para section_first_para
        first_para = sents[0] if sents else ""
        
        # Chunking por sentenças com overlap
        joined = []
        buf = ""
        
        for s in sents:
            if len(buf) + len(s) + 1 <= max_chars:
                buf = (buf + " " + s).strip()
            else:
                if buf:
                    joined.append(buf)
                # Overlap: mantém últimas N chars
                tail = buf[-overlap:] if overlap < len(buf) else buf
                buf = (tail + " " + s).strip()
        
        if buf:
            joined.append(buf)
        
        # Cria passages
        for chunk in joined:
            out.append((section_title, first_para, chunk))
    
    return out

def _find_sections(text: str):
    """Encontra seções no texto baseado em headers"""
    sections = []
    last = 0
    
    for m in HDR.finditer(text):
        start = m.start()
        if start > last:
            sections.append(("", "", text[last:start]))
        last = start
    
    if last < len(text):
        sections.append(("", "", text[last:]))
    
    return sections

