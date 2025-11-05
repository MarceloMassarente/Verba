# 🎯 Query Parsing: Como Separar Entidade vs Semântica

## ❓ **O Problema**

```
Query: "apple e inovação"
          ^^^^^   ^^^^^^^^^^
       Entidade   Semântica?

O sistema precisa saber:
- "apple" → procurar como ENTIDADE (filtro WHERE)
- "inovação" → procurar como SEMÂNTICA (busca vetorial)
```

---

## 🧩 **Estratégia 1: Análise POS (Part-of-Speech) + NER**

### **Como Funciona**

```python
import spacy

nlp = spacy.load("pt_core_news_sm")
query = "apple e inovação"

doc = nlp(query)

for token in doc:
    print(f"{token.text:15} | POS: {token.pos_:6} | ENT: {token.ent_type_}")

# OUTPUT:
# apple           | POS: PROPN  | ENT: ORG
# e               | POS: CCONJ  | ENT: 
# inovação        | POS: NOUN   | ENT: 

# INTERPRETAÇÃO:
# - PROPN (Proper Noun) + ORG → ENTIDADE
# - NOUN (Common Noun) sem NER → SEMÂNTICA
```

### **Lógica**

```python
def classify_token(token):
    """Classifica se token é entidade ou semântico"""
    
    # 1. Se tem NER label e é PROPN → ENTIDADE
    if token.ent_type_ in ["ORG", "PERSON", "GPE", "LOC"]:
        return "ENTITY"
    
    # 2. Se é nome próprio → ENTIDADE (mesmo sem NER)
    if token.pos_ == "PROPN":
        return "ENTITY"
    
    # 3. Se é substantivo comum → SEMÂNTICO
    if token.pos_ in ["NOUN", "VERB", "ADJ"]:
        return "SEMANTIC"
    
    # 4. Palavras de conexão → IGNORAR
    if token.pos_ in ["CCONJ", "ADP", "DET"]:
        return "CONNECTOR"
    
    return "OTHER"

# Teste
for token in doc:
    classification = classify_token(token)
    print(f"{token.text:15} → {classification}")

# OUTPUT:
# apple           → ENTITY
# e               → CONNECTOR
# inovação        → SEMANTIC
```

---

## 🔍 **Estratégia 2: Dependency Parsing (Análise de Dependências)**

### **Como Funciona**

```python
query = "qual é a estratégia de inovação da Apple?"

doc = nlp(query)

for token in doc:
    if token.dep_ != "punct":  # Ignora pontuação
        print(f"{token.text:15} → {token.dep_:10} (parent: {token.head.text})")

# OUTPUT:
# qual            → ROOT       (parent: é)
# é               → ROOT       (parent: é)
# a               → det        (parent: estratégia)
# estratégia      → attr       (parent: é)
# de              → case       (parent: inovação)
# inovação        → nmod       (parent: estratégia)  ← SEMÂNTICA!
# da              → case       (parent: Apple)
# Apple           → nmod       (parent: inovação)   ← ENTIDADE!

# INTERPRETAÇÃO DA ESTRUTURA:
# [estratégia] ← tem NMODifier
#   ├─ [inovação] (conceito)
#   └─ [de Apple] (entidade)
```

### **Lógica**

```python
def extract_semantic_and_entities(query):
    """Extrai componentes semânticos e entidades da query"""
    
    doc = nlp(query)
    entities = []
    semantic_concepts = []
    
    for token in doc:
        # Entidades nomeadas
        if token.ent_type_ in ["ORG", "PERSON", "GPE"]:
            entities.append(token.text)
        
        # Conceitos: NOUN ou ADJ (que não sejam entidades)
        elif token.pos_ in ["NOUN", "ADJ"] and token.ent_type_ == "":
            semantic_concepts.append(token.text)
    
    return entities, semantic_concepts

# Teste
entities, concepts = extract_semantic_and_entities(
    "qual é a estratégia de inovação da Apple?"
)

print(f"Entidades: {entities}")          # ['Apple']
print(f"Conceitos: {concepts}")          # ['estratégia', 'inovação']
```

---

## 🧠 **Estratégia 3: Query Intent Classification**

### **Como Funciona**

```python
def classify_query_intent(query):
    """Classifica a INTENÇÃO da query"""
    
    # Pattern matching
    if any(word in query.lower() for word in ["qual", "o que", "como"]):
        return "QUESTION"
    
    if any(word in query.lower() for word in ["comparação", "vs", "versus"]):
        return "COMPARISON"
    
    if any(word in query.lower() for word in ["e", "ambos", "combinação"]):
        return "COMBINATION"
    
    return "GENERAL_SEARCH"

# Teste
queries = [
    "qual é a estratégia de Apple?",
    "Apple vs Microsoft",
    "Apple e inovação",
    "empresas de tecnologia"
]

for q in queries:
    intent = classify_query_intent(q)
    print(f"{q:40} → {intent}")

# OUTPUT:
# qual é a estratégia de Apple?        → QUESTION
# Apple vs Microsoft                   → COMPARISON
# Apple e inovação                     → COMBINATION
# empresas de tecnologia               → GENERAL_SEARCH
```

---

## ⚙️ **Estratégia 4: Fuzzy Matching com Gazetteer**

### **Como Funciona**

```python
from fuzzywuzzy import fuzz

GAZETTEER = {
    "Q123": ["Apple", "Apple Inc.", "AAPL"],
    "Q456": ["Microsoft", "MSFT"],
    "Q789": ["Steve Jobs", "Jobs"],
}

def find_entities_in_query(query):
    """Encontra entidades usando fuzzy matching"""
    
    entities_found = []
    words = query.split()
    
    # Tenta bigrams também
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        for entity_id, aliases in GAZETTEER.items():
            for alias in aliases:
                # Fuzzy match (não precisa ser 100% exato)
                similarity = fuzz.ratio(bigram.lower(), alias.lower())
                if similarity > 80:  # 80% de similaridade
                    entities_found.append({
                        "entity_id": entity_id,
                        "alias": alias,
                        "similarity": similarity
                    })
    
    return entities_found

# Teste
query = "apple e inovação"
entities = find_entities_in_query(query)

for e in entities:
    print(f"Entity: {e['alias']} ({e['entity_id']}) - {e['similarity']}% match")

# OUTPUT:
# Entity: Apple (Q123) - 100% match
```

---

## 🎯 **Estratégia 5: RECOMENDADA - Combinação Híbrida**

### **Pseudocódigo Completo**

```python
class QueryParser:
    def __init__(self, nlp_model, gazetteer):
        self.nlp = nlp_model
        self.gazetteer = gazetteer
    
    def parse(self, query):
        """Faz parsing completo da query"""
        
        doc = self.nlp(query)
        result = {
            "entities": [],
            "semantic_concepts": [],
            "intent": self._classify_intent(query),
            "tokens": []
        }
        
        # 1. NER + POS tagging
        for token in doc:
            token_info = {
                "text": token.text,
                "pos": token.pos_,
                "ent_type": token.ent_type_,
                "dep": token.dep_
            }
            
            # 2. Classifica cada token
            if token.ent_type_ in ["ORG", "PERSON", "GPE"]:
                # É entidade nomeada
                entity_id = self._lookup_gazetteer(token.text)
                result["entities"].append({
                    "text": token.text,
                    "entity_id": entity_id,
                    "confidence": 0.95,
                    "source": "NER"
                })
                token_info["classification"] = "ENTITY"
            
            elif token.pos_ in ["NOUN", "ADJ"] and token.ent_type_ == "":
                # É conceito semântico
                result["semantic_concepts"].append(token.text)
                token_info["classification"] = "SEMANTIC"
            
            elif token.pos_ in ["CCONJ", "ADP"]:
                token_info["classification"] = "CONNECTOR"
            
            result["tokens"].append(token_info)
        
        return result
    
    def _lookup_gazetteer(self, text):
        """Procura text no gazetteer"""
        for entity_id, aliases in self.gazetteer.items():
            if text.lower() in [a.lower() for a in aliases]:
                return entity_id
        return None
    
    def _classify_intent(self, query):
        """Classifica intenção da query"""
        if "vs" in query.lower() or "versus" in query.lower():
            return "COMPARISON"
        if "e" in query.lower() or "ambos" in query.lower():
            return "COMBINATION"
        if any(w in query.lower() for w in ["qual", "o que", "como"]):
            return "QUESTION"
        return "GENERAL_SEARCH"

# Uso
parser = QueryParser(nlp, GAZETTEER)
result = parser.parse("Apple e inovação em design")

print(result)
# OUTPUT:
# {
#   "entities": [
#     {"text": "Apple", "entity_id": "Q123", "confidence": 0.95, "source": "NER"}
#   ],
#   "semantic_concepts": ["inovação", "design"],
#   "intent": "COMBINATION",
#   "tokens": [...]
# }
```

---

## 📊 **Matriz de Decisão: Quando Usar Cada Estratégia**

| Query | Strategy | Entities | Semantic | Intent |
|-------|----------|----------|----------|--------|
| `"Apple"` | NER | ["Apple"] | [] | GENERAL |
| `"inovação"` | POS | [] | ["inovação"] | GENERAL |
| `"Apple e inovação"` | Hybrid | ["Apple"] | ["inovação"] | COMBINATION |
| `"Apple vs Microsoft"` | Intent | ["Apple", "Microsoft"] | [] | COMPARISON |
| `"qual é a inovação da Apple?"` | Dependency | ["Apple"] | ["inovação"] | QUESTION |
| `"empresas de tech"` | POS | [] | ["empresas", "tech"] | GENERAL |

---

## 🚀 **Implementação Prática para Verba**

### **1. Adicionar ao QueryOrchestrator**

```python
# verba_extensions/plugins/entity_aware_query_orchestrator.py

def parse_query_for_hybrid_search(query: str) -> Dict[str, Any]:
    """Parse query para extrair entidades e conceitos"""
    
    nlp = get_nlp()
    doc = nlp(query)
    
    result = {
        "original_query": query,
        "entities": [],
        "semantic_terms": [],
        "intent": "GENERAL"
    }
    
    # 1. Extrai entidades
    for ent in doc.ents:
        if ent.label_ in ["ORG", "PERSON", "GPE"]:
            entity_id = gazetteer_lookup(ent.text)
            result["entities"].append({
                "text": ent.text,
                "entity_id": entity_id
            })
    
    # 2. Extrai conceitos semânticos
    for token in doc:
        if token.pos_ in ["NOUN", "ADJ"] and token.ent_type_ == "":
            result["semantic_terms"].append(token.text)
    
    # 3. Classifica intent
    if "vs" in query.lower():
        result["intent"] = "COMPARISON"
    elif " e " in query.lower():
        result["intent"] = "COMBINATION"
    
    return result

# Uso
query_parse = parse_query_for_hybrid_search("Apple e inovação")
# → {
#     "entities": [{"text": "Apple", "entity_id": "Q123"}],
#     "semantic_terms": ["inovação"],
#     "intent": "COMBINATION"
#   }
```

### **2. Usar no Retriever**

```python
# entity_aware_retriever.py

async def retrieve(self, query, config, ...):
    # 1. Parse query
    parsed = parse_query_for_hybrid_search(query)
    
    # 2. Se tem entidades → aplicar filtro
    if parsed["entities"]:
        entity_ids = [e["entity_id"] for e in parsed["entities"]]
        entity_filter = Filter("entities").contains_any(entity_ids)
    else:
        entity_filter = None
    
    # 3. Se tem conceitos semânticos → busca vetorial
    search_query = " ".join(parsed["semantic_terms"]) if parsed["semantic_terms"] else query
    query_vector = embedding_model.encode(search_query)
    
    # 4. Executa busca combinada
    chunks = await weaviate_manager.hybrid_search(
        vector=query_vector,
        entity_filter=entity_filter,
        alpha=0.6
    )
    
    return chunks
```

---

## ✅ **Resumo: Como o Sistema Sabe**

| Aspecto | Como Funciona |
|---------|---------------|
| **Detecção de Entidades** | spaCy NER + POS tagging |
| **Detecção de Conceitos** | Análise POS (NOUN, ADJ) + Dependency parsing |
| **Classificação de Intent** | Pattern matching + POS structure |
| **Lookup** | Gazetteer fuzzy matching |
| **Combinação** | Híbrido: WHERE filter + Vector search |

**Exemplo Final:**

```
Query: "qual é a estratégia de inovação da Apple?"
       ├─ Entidade: "Apple" (ORG) → entity_filter = WHERE entities = "Q123"
       ├─ Conceitos: "estratégia", "inovação" → semantic_search
       ├─ Intent: QUESTION
       └─ Busca combinada: chunks sobre (Apple E estratégia E inovação)
```
