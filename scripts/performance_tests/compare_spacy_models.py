#!/usr/bin/env python3
"""
Compara modelos spaCy PT vs EN para identificar diferenças
"""

import spacy
from pypdf import PdfReader
from collections import Counter

pdf_path = "docs/assets/Estudo Mercado Headhunting Brasil.pdf"

# Carrega PDF
reader = PdfReader(pdf_path)
text = '\n'.join([p.extract_text() for p in reader.pages[:5]])  # Primeiras 5 páginas
print(f"Text length: {len(text):,} chars\n")

# Testa ambos modelos
models = {}
try:
    models['PT'] = spacy.load('pt_core_news_sm')
    print("✅ Modelo PT carregado: pt_core_news_sm")
except Exception as e:
    print(f"❌ Erro ao carregar PT: {e}")
    models['PT'] = None

try:
    models['EN'] = spacy.load('en_core_web_sm')
    print("✅ Modelo EN carregado: en_core_web_sm")
except Exception as e:
    print(f"❌ Erro ao carregar EN: {e}")
    models['EN'] = None

print("\n" + "="*80)
print("COMPARAÇÃO DE ENTIDADES")
print("="*80)

results = {}

for model_name, nlp in models.items():
    if nlp is None:
        continue
    
    print(f"\n{model_name} Model:")
    print("-" * 80)
    
    doc = nlp(text)
    entities = list(doc.ents)
    
    # Conta por label
    labels = Counter(e.label_ for e in entities)
    
    print(f"Total entities: {len(entities)}")
    print(f"Unique labels: {len(labels)}")
    print("\nLabels found:")
    for label, count in sorted(labels.items(), key=lambda x: -x[1]):
        pct = 100 * count / len(entities)
        print(f"  {label:15} {count:4} ({pct:5.1f}%)")
    
    # Mostra exemplos de cada label
    print("\nExamples by label:")
    for label in sorted(labels.keys()):
        examples = [e.text for e in entities if e.label_ == label][:5]
        print(f"  {label:15} {', '.join(examples)}")
    
    results[model_name] = {
        'labels': labels,
        'entities': entities,
        'total': len(entities)
    }

# Compara diferenças
if 'PT' in results and 'EN' in results:
    print("\n" + "="*80)
    print("ANÁLISE DE DIFERENÇAS")
    print("="*80)
    
    pt_labels = set(results['PT']['labels'].keys())
    en_labels = set(results['EN']['labels'].keys())
    
    print(f"\nLabels only in PT: {pt_labels - en_labels}")
    print(f"Labels only in EN: {en_labels - pt_labels}")
    print(f"Common labels: {pt_labels & en_labels}")
    
    # Mapeamento conhecido
    print("\n" + "="*80)
    print("MAPEAMENTO DE LABELS PT -> EN")
    print("="*80)
    
    label_mapping = {
        'PER': 'PERSON',      # Pessoa
        'ORG': 'ORG',         # Organização (mesmo)
        'LOC': 'LOC',         # Localização (mesmo)
        'MISC': 'MISC',       # Miscelânea (mesmo)
        'GPE': 'GPE',         # Geopolitical Entity (mesmo)
    }
    
    print("\nMapping conhecido:")
    for pt_label, en_label in sorted(label_mapping.items()):
        pt_count = results['PT']['labels'].get(pt_label, 0)
        en_count = results['EN']['labels'].get(en_label, 0)
        match = "✓" if pt_label == en_label or (pt_label in results['PT']['labels'] and en_label in results['EN']['labels']) else "✗"
        print(f"  {match} {pt_label:10} -> {en_label:10} (PT: {pt_count:4}, EN: {en_count:4})")
    
    # Labels únicos de cada modelo
    print("\nLabels únicos do PT:")
    for label in sorted(pt_labels - en_labels):
        count = results['PT']['labels'][label]
        examples = [e.text for e in results['PT']['entities'] if e.label_ == label][:3]
        print(f"  {label:15} {count:4} (ex: {', '.join(examples)})")
    
    print("\nLabels únicos do EN:")
    for label in sorted(en_labels - pt_labels):
        count = results['EN']['labels'][label]
        examples = [e.text for e in results['EN']['entities'] if e.label_ == label][:3]
        print(f"  {label:15} {count:4} (ex: {', '.join(examples)})")

# Testa performance
print("\n" + "="*80)
print("PERFORMANCE")
print("="*80)

import time

for model_name, nlp in models.items():
    if nlp is None:
        continue
    
    start = time.perf_counter()
    doc = nlp(text)
    elapsed = time.perf_counter() - start
    
    print(f"{model_name:10} {elapsed:6.3f}s ({len(doc.ents)} entities)")

# Recomendações
print("\n" + "="*80)
print("RECOMENDAÇÕES PARA O CÓDIGO")
print("="*80)

if 'PT' in results:
    pt_labels = set(results['PT']['labels'].keys())
    
    print("\n1. Labels para aceitar:")
    print("   - ORG (organizações)")
    print("   - PER (pessoas) - equivalente a PERSON em EN")
    
    if 'MISC' in pt_labels:
        print("   - MISC (miscelânea) - pode ser útil?")
    
    print("\n2. Labels para considerar:")
    if 'LOC' in pt_labels:
        print("   - LOC (localizações) - removido para performance, mas pode ser útil")
    if 'GPE' in pt_labels:
        print("   - GPE (entidades geopolíticas) - removido para performance")
    
    print("\n3. Código atual:")
    print("   ✅ Aceita: ORG, PERSON, PER")
    print("   ❌ Remove: LOC, GPE")
    print("   💡 Sugestão: Criar função normalize_label() que mapeia PER->PERSON")

