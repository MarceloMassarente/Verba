#!/usr/bin/env python3
"""Verifica se há PERSONs no PDF"""
import spacy
from pypdf import PdfReader
from collections import Counter

pdf_path = "docs/assets/Estudo Mercado Headhunting Brasil.pdf"

print("Loading PDF and extracting entities...")
reader = PdfReader(pdf_path)
text = '\n'.join([p.extract_text() for p in reader.pages[:10]])  # Primeiras 10 páginas

print(f"Text length: {len(text):,} chars")

try:
    nlp = spacy.load('pt_core_news_sm')
except:
    nlp = spacy.load('en_core_web_sm')

doc = nlp(text)

# Todas as entidades
all_ents = list(doc.ents)
labels = Counter(e.label_ for e in all_ents)

print(f"\nTotal entities: {len(all_ents)}")
print("Breakdown by label:")
for label, count in sorted(labels.items()):
    print(f"  {label}: {count}")

# PERSONs específicas
persons = [e.text for e in all_ents if e.label_ == 'PERSON']
print(f"\nPERSON entities found: {len(persons)}")
if persons:
    print("Sample PERSONs:")
    for p in persons[:20]:
        print(f"  - {p}")
else:
    print("(No PERSON entities detected in this document)")

# ORGs
orgs = [e.text for e in all_ents if e.label_ == 'ORG']
print(f"\nORG entities found: {len(orgs)}")
if orgs:
    print("Sample ORGs:")
    for o in orgs[:10]:
        print(f"  - {o}")

