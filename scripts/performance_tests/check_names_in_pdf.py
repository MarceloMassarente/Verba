#!/usr/bin/env python3
"""Verifica como nomes próprios estão sendo classificados"""
import spacy
from pypdf import PdfReader
import re

pdf_path = "docs/assets/Estudo Mercado Headhunting Brasil.pdf"

print("Loading PDF...")
reader = PdfReader(pdf_path)
text = '\n'.join([p.extract_text() for p in reader.pages])

print(f"Text length: {len(text):,} chars")

# Procura por nomes comuns
common_names = ["Fernando", "João", "Maria", "Carlos", "Ana", "Paulo", "Roberto", "Marcelo"]
found_names = {}

for name in common_names:
    # Busca case-insensitive
    pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
    matches = pattern.findall(text)
    if matches:
        found_names[name] = len(matches)
        print(f"\nFound '{name}': {len(matches)} times")
        # Mostra contexto
        for match in re.finditer(pattern, text):
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].replace('\n', ' ')
            print(f"  Context: ...{context}...")
            if len(found_names) >= 3:  # Limita para não poluir
                break

# Agora testa com spaCy
try:
    nlp = spacy.load('pt_core_news_sm')
except:
    nlp = spacy.load('en_core_web_sm')

print("\n" + "="*70)
print("Testing with spaCy...")
print("="*70)

# Testa um trecho que contém "Fernando"
if "Fernando" in text or "fernando" in text:
    # Pega um trecho de 500 chars ao redor de "Fernando"
    idx = text.lower().find("fernando")
    if idx > 0:
        sample = text[max(0, idx-250):min(len(text), idx+250)]
        doc = nlp(sample)
        
        print(f"\nSample text (500 chars around 'Fernando'):")
        print("-" * 70)
        print(sample[:500])
        print("-" * 70)
        
        print("\nEntities detected:")
        for ent in doc.ents:
            print(f"  {ent.text:30} -> {ent.label_}")
        
        # Verifica especificamente "Fernando"
        fernando_ents = [e for e in doc.ents if "fernando" in e.text.lower()]
        print(f"\nEntities containing 'Fernando': {len(fernando_ents)}")
        for e in fernando_ents:
            print(f"  '{e.text}' -> {e.label_}")

