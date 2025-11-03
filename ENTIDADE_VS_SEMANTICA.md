# 🧠 Entidade vs Semântica: A Diferença Fundamental

## 📚 **Conceitos**

### **ENTIDADE (Named Entity Recognition)**
- **Definição**: Coisa/pessoa/local com identidade ÚNICA e FIXA
- **Quem decide**: Modelo de NER (spaCy) + gazetteer manual
- **Exemplos**:
  - ✅ "Apple" → ORG (organização)
  - ✅ "Steve Jobs" → PERSON (pessoa)
  - ✅ "São Paulo" → GPE (local)
  - ❌ "inovação" → NADA (conceito, não entidade)

### **SEMÂNTICA (Semantic/Vector Search)**
- **Definição**: Significado e contexto das palavras
- **Quem decide**: Embedding model (BERT, GPT, etc)
- **Exemplos**:
  - ✅ "inovação" → próximo de ["novo", "criativo", "tecnologia"]
  - ✅ "visão" → próximo de ["futuro", "objetivo", "direção"]
  - ✅ "disruptivo" → próximo de ["inovação", "mudança", "perturbador"]

---

## 🔍 **Comparação Lado a Lado**

| Aspecto | Entidade | Semântica |
|---------|----------|-----------|
| **O quê captura** | Identidades fixas | Significado/contexto |
| **Tecnologia** | spaCy NER + Gazetteer | Embedding model |
| **Velocidade** | ⚡ Rápida (WHERE filter) | 🐢 Mais lenta (similarity) |
| **Precisão** | 📍 Alta (regras) | 📊 Moderada (probabilística) |
| **Recall** | 📦 Baixo (só nomes conhecidos) | 🎯 Alto (captura conceitos) |
| **Query: "apple"** | ✅ Encontra | ✅ Encontra |
| **Query: "inovação"** | ❌ Ignora | ✅ Encontra |
| **Query: "apple e inovação"** | ⚠️ Só filtra Apple | ✅ Encontra ambos |

---

## 🎬 **Fluxo Visual: Query "apple e inovação"**

### **Cenário 1: Só Entidade (EntityAware - HOJE)**

```
┌─────────────────────────────────────┐
│ Query: "apple e inovação"           │
└────────────┬────────────────────────┘
             │
             ↓
┌─────────────────────────────────────┐
│ spaCy NER extrai:                   │
│ - "Apple" → ORG ✅                  │
│ - "inovação" → ??? ❌               │
└────────────┬────────────────────────┘
             │
             ↓
┌─────────────────────────────────────┐
│ Gazetteer mapeia:                   │
│ - Apple → entity_id "Q123" ✅       │
│ - inovação → NOT FOUND ❌           │
└────────────┬────────────────────────┘
             │
             ↓
┌─────────────────────────────────────┐
│ Weaviate WHERE filter:              │
│ WHERE entities_local_ids = ["Q123"] │
└────────────┬────────────────────────┘
             │
             ↓
┌─────────────────────────────────────┐
│ ⚠️ RESULTADO: Chunks sobre Apple    │
│    MAS: Pode estar em qualquer      │
│    contexto (não necessariamente    │
│    relacionado a "inovação")        │
└─────────────────────────────────────┘
```

### **Cenário 2: Só Semântica (Window Retriever - Padrão)**

```
┌─────────────────────────────────────┐
│ Query: "apple e inovação"           │
└────────────┬────────────────────────┘
             │
             ↓
┌─────────────────────────────────────┐
│ Embedding Model (ex: BERT):         │
│ Converte em vetor 768-dim:          │
│ [0.234, 0.891, 0.123, ...]         │
└────────────┬────────────────────────┘
             │
             ↓
┌─────────────────────────────────────┐
│ Busca Vetorial (Weaviate):          │
│ Calcula similaridade cos(q, chunk)  │
│ com TODOS os chunks                 │
└────────────┬────────────────────────┘
             │
             ↓
┌─────────────────────────────────────┐
│ ✅ RESULTADO: Chunks relevantes     │
│    MAS: Pode vir de Microsoft tb    │
│    (contaminação entre empresas)    │
│    porque trata "apple" como palavra│
│    semântica, não entidade única    │
└─────────────────────────────────────┘
```

### **Cenário 3: HÍBRIDO (IDEAL - O que Falta)**

```
┌─────────────────────────────────────┐
│ Query: "apple e inovação"           │
└────────────┬────────────────────────┘
             │
    ┌────────┴─────────┐
    ↓                  ↓
┌──────────────┐  ┌──────────────────┐
│ Entidade:    │  │ Semântica:       │
│ "Apple"      │  │ "apple + inov." │
│ → Q123       │  │ → [0.234, ...]  │
└──────┬───────┘  └────────┬─────────┘
       │                   │
       ↓                   ↓
┌─────────────────────────────────────┐
│ Weaviate:                           │
│ 1. WHERE entities = "Q123" ✅       │
│ 2. Vector search ✅                 │
│ 3. RERANK by relevance ✅           │
└────────────┬────────────────────────┘
             │
             ↓
┌─────────────────────────────────────┐
│ ✅ RESULTADO: Chunks sobre Apple    │
│    ✅ QUE MENCIONAM inovação        │
│    ✅ SEM contaminação              │
│    ✅ ALTA relevância               │
└─────────────────────────────────────┘
```

---

## 🧩 **Por Que Hoje Não Funciona Assim?**

### **Problema 1: spaCy Não Reconhece Conceitos**

```python
nlp = spacy.load("pt_core_news_sm")
doc = nlp("apple e inovação")

for ent in doc.ents:
    print(f"{ent.text} → {ent.label_}")

# OUTPUT:
# Apple → ORG  ✅
# (nada para "inovação") ❌
```

**Por quê?** spaCy é treinado apenas em entidades nomeadas (ORG, PERSON, etc). Conceitos abstratos não são entidades!

### **Problema 2: Gazetteer Só Tem Nomes**

```json
{
  "Q123": {
    "name": "Apple Inc.",
    "aliases": ["Apple", "Apple Inc.", "AAPL"]
  },
  // Não tem "inovação"!
  // Conceitos abstratos não são mapeados
}
```

### **Problema 3: EntityAware Ignora Semântica**

```python
# entity_aware_retriever.py
entity_filter = Filter.by_property("entities").contains_any(["Q123"])
# Filtra APENAS por entidade
# Completamente IGNORA o embedding/semântica de "inovação"
```

---

## ✅ **Solução: Arquitetura Híbrida**

### **Como Seria**

```python
# Pseudocódigo do que DEVERIA existir

async def retrieve(self, query, config, ...):
    # 1. Extrai entidades
    entities = extract_entities(query)  # ["Q123"]
    
    # 2. Cria embedding da query COMPLETA
    query_vector = embedding_model.encode(query)
    
    # 3. Busca com AMBOS os filtros
    chunks = await weaviate_manager.hybrid_search(
        vector=query_vector,
        entity_filter=Filter("entities").contains_any(entities),
        alpha=0.6  # Balance entre keyword e vector
    )
    
    # 4. Rerank por relevância
    chunks = self.rerank_by_relevance(chunks, query)
    
    return chunks
```

### **Vantagens**

✅ **Precisão**: Filtra por entidade (evita contaminação)  
✅ **Recall**: Busca semântica (captura conceitos)  
✅ **Velocidade**: WHERE clause reduce dataset antes de vector search  
✅ **Flexibilidade**: "apple", "inovação" ou "apple e inovação"  

---

## 📊 **Matriz de Compatibilidade: Cenários Reais**

| Query | Entidade | Semântica | Híbrido |
|-------|----------|-----------|---------|
| `"apple"` | ✅ Ótimo | ✅ Bom | ✅ Ótimo |
| `"inovação"` | ❌ Falha | ✅ Bom | ✅ Bom |
| `"apple e inovação"` | ⚠️ Incompleto | ✅ Bom | ✅✅ Excelente |
| `"qual é a estratégia de inovação da Apple?"` | ⚠️ Incompleto | ✅ Bom | ✅✅ Excelente |
| `"apple vs microsoft"` | ⚠️ Parcial | ✅ Bom | ✅✅ Excelente |
| `"empresas de tecnologia em São Paulo"` | ⚠️ Parcial | ✅ Bom | ✅✅ Excelente |

---

## 🚀 **Próximos Passos**

### **Curto Prazo (Rápido)**
- [ ] Adicionar suporte a keywords no gazetteer
- [ ] Combinar entity + semantic scores

### **Médio Prazo**
- [ ] Implementar Hybrid Retriever
- [ ] Treinar modelo de reranking

### **Longo Prazo**
- [ ] Graph embeddings (relacionamentos entre entidades)
- [ ] Ontologias (taxonomias de conceitos)
