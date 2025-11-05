# ⚠️ O Problema Real: Queries em Linguagem Natural vs Entity Extraction

## 🎯 **Seu Exemplo é PERFEITO**

```
Query: "descreva o que se fala sobre a Apple e Inovação"
```

### **O Que Acontece HOJE:**

```
Input: "descreva o que se fala sobre a Apple e Inovação"

spaCy NER extrai:
├─ "Apple" → ORG ✅
└─ "Inovação" → ??? (não é entidade)

extract_entities_from_query():
├─ Procura "Apple" no gazetteer → entity_id="Q123" ✅
├─ Procura "Inovação" no gazetteer → NÃO ENCONTRA ❌
└─ Resultado: ["Q123"]

EntityAwareRetriever com entity_ids=["Q123"]:
├─ WHERE entities = "Q123" ✅
└─ Ignora COMPLETAMENTE o resto da query! ❌

Weaviate busca:
├─ BM25: "descreva o que se fala sobre a Apple e Inovação"
├─ Vector: [vetor da query completa]
└─ Combina resultados

PROBLEMA: 
❌ Perguntas/verbos IGNORADOS ("descreva", "o que se fala")
❌ Estrutura da pergunta IGNORADA
❌ Intento da query PERDIDO
```

---

## 🔍 **Análise Detalhada**

### **POS Tagging da Query:**

```python
import spacy

nlp = spacy.load("pt_core_news_sm")
doc = nlp("descreva o que se fala sobre a Apple e Inovação")

for token in doc:
    print(f"{token.text:15} | POS: {token.pos_:6} | ENT: {token.ent_type_}")

# OUTPUT:
# descreva        | POS: VERB   | ENT: 
# o               | POS: DET    | ENT:
# que             | POS: PRON   | ENT:
# se              | POS: PRON   | ENT:
# fala            | POS: VERB   | ENT:
# sobre           | POS: ADP    | ENT:
# a               | POS: DET    | ENT:
# Apple           | POS: PROPN  | ENT: ORG  ✅
# e               | POS: CCONJ  | ENT:
# Inovação        | POS: NOUN   | ENT:      (não é entidade nomeada!)
```

---

## 📊 **O Problema em 3 Camadas**

### **Camada 1: Estrutura Linguística**

```
Query Simples:        "Apple e inovação"
                      └─ Nome próprio + nome comum
                      └─ Estrutura clara

Query Natural:        "descreva o que se fala sobre a Apple e Inovação"
                      ├─ Verbo: "descreva"
                      ├─ Estrutura interrogativa: "o que se fala"
                      ├─ Preposição: "sobre"
                      ├─ Entidade: "Apple"
                      └─ Conceito: "Inovação"
```

**Problema:** spaCy + Gazetteer só vê "Apple", ignora toda a estrutura!

---

### **Camada 2: Intenção vs Dado**

```
Query: "descreva o que se fala sobre a Apple e Inovação"
       
DECOMPOSIÇÃO:
├─ INTENÇÃO/TAREFA: "descreva" + "o que se fala"
│                   └─ Pede para o LLM DESCREVER/RESUMIR
│
├─ ESCOPO: "sobre a Apple"
│          └─ Contexto: entidade Apple
│
└─ TÓPICO: "e Inovação"
           └─ Tema: inovação

HOJE:
Entity extraction: ["Apple"] → Filtra por Apple ✅
Semântica: IGNORADA! ❌
Intenção: PERDIDA! ❌
```

---

### **Camada 3: Diferença entre Busca e Pergunta**

```
BUSCA (Search Query):
  "Apple inovação"
  └─ Usuário quer: encontrar algo sobre esses tópicos
  └─ Solução: Entity filter + Vector search

PERGUNTA (Natural Language):
  "descreva o que se fala sobre a Apple e Inovação"
  ├─ Usuário quer: uma RESPOSTA elaborada
  ├─ Pede: resumo ("descreva")
  ├─ Contexto: Apple + Inovação
  └─ Solução: Precisa ENTENDER a intenção!
```

---

## 🚨 **Por Que Isso é um Problema**

### **Exemplo Real:**

```
Query: "descreva o que se fala sobre a Apple e Inovação"

HOJE (com EntityAwareRetriever):

1. Extract entities: ["Apple"]

2. WHERE filter: entities = "Apple"
   Retorna chunks sobre Apple (qualquer contexto)
   
   Exemplos de chunks retornados:
   ✅ "Apple investe em inovação de IA"
   ✅ "A estratégia de inovação da Apple foca em..."
   ✅ "Steve Jobs revolucionou com inovação"
   ❌ "A Apple não inova em relação a outras empresas"  ← RUIM!
   ❌ "Produtos da Apple competem com Microsoft"        ← FORA DO ESCOPO!

3. LLM recebe esses chunks + query
   Tenta gerar resposta sobre "Apple e Inovação"
   Mas chunks podem estar desalinhados

RESULTADO: Resposta ruim porque chunks não são específicos sobre "inovação"
```

---

## ✅ **A Solução Real**

### **Não é APENAS Parser de Entidades**

O problema é que você precisa de:

```
Query: "descreva o que se fala sobre a Apple e Inovação"

1. ✅ ENTIDADE EXTRACTION
   └─ Encontra: Apple

2. ✅ SEMANTIC EXTRACTION (Query Parser novo!)
   ├─ Encontra: Inovação
   ├─ Classifica: NOUN (conceito semântico)
   └─ Intent: DESCRIPTION ("descreva")

3. ✅ INTENT CLASSIFICATION
   ├─ Tipo: QUESTION/DESCRIPTION
   ├─ Ação pedida: "descreva" → pede resumo
   └─ Escopo: "sobre" → contexto específico

4. ✅ QUERY REWRITING (OPCIONAL - LLM)
   Input:  "descreva o que se fala sobre a Apple e Inovação"
   Output: "inovação da Apple" (mais específico)
   
5. ✅ HYBRID RETRIEVAL
   ├─ Entity filter: WHERE entities = "Apple"
   ├─ Semantic search: "inovação"
   ├─ Intent-aware: Prioriza chunks descritivos
   └─ Resultado: Chunks sobre Apple + inovação + informativos
```

---

## 🧠 **Comparação: Sem vs Com Solução Completa**

### **SEM Query Parser (HOJE)**

```
"descreva o que se fala sobre a Apple e Inovação"
        ↓
    Entity: ["Apple"]
    ❌ Ignora: "descreva", "Inovação", estrutura
        ↓
    Weaviate: BM25 + Vector (query completa)
    ❌ Chunks podem não ser sobre inovação
        ↓
    LLM: "Aqui está o que encontrei sobre Apple..."
    ❌ Pode não focar em inovação
```

### **COM Query Parser + Intent Classification**

```
"descreva o que se fala sobre a Apple e Inovação"
        ↓
    Parser:
    ├─ Entity: "Apple"
    ├─ Semantic: "Inovação"
    ├─ Intent: "DESCRIPTION"
    └─ Scope: "sobre"
        ↓
    EntityAwareRetriever:
    ├─ WHERE: entities = "Apple"
    ├─ Vector: "inovação"
    ├─ Rerank: por relevância descritiva
    └─ Resultado: chunks sobre Apple que falam de inovação
        ↓
    LLM: "Apple é conhecida pela inovação em..."
    ✅ Resposta alinhada com intenção do usuário
```

---

## 🎯 **Solução: 3 Estratégias**

### **Estratégia 1: Query Cleaning (Simples)**

```python
def clean_query_for_entity_search(query: str) -> str:
    """Remove palavras funcionais, mantém entidades e conceitos"""
    
    nlp = spacy.load("pt_core_news_sm")
    doc = nlp(query)
    
    # Mantém: PROPN, NOUN, ADJ, VERB (principais)
    # Remove: DET, ADP, CCONJ (palavras de função)
    
    important_tokens = [
        token.text for token in doc
        if token.pos_ in ["PROPN", "NOUN", "ADJ", "VERB"]
    ]
    
    return " ".join(important_tokens)

# Teste
query = "descreva o que se fala sobre a Apple e Inovação"
cleaned = clean_query_for_entity_search(query)
# Resultado: "descreva fala Apple Inovação"
# Muito melhor para entity extraction!
```

**Vantagem:** Simples, rápido  
**Desvantagem:** Perde contexto ("descreva" virou genérico)

---

### **Estratégia 2: Intent-Aware Query Rewriting (Médio)**

```python
def rewrite_query_for_search(query: str) -> str:
    """Reescreve query mantendo entidades mas simplificando"""
    
    nlp = spacy.load("pt_core_news_sm")
    doc = nlp(query)
    
    # Identifica estrutura
    entities = [ent.text for ent in doc.ents]
    concepts = [token.text for token in doc 
                if token.pos_ in ["NOUN", "ADJ"] 
                and token.ent_type_ == ""]
    
    # Reescreve
    if entities and concepts:
        return f"{' '.join(entities)} {' '.join(concepts)}"
    elif entities:
        return " ".join(entities)
    else:
        return query

# Teste
query = "descreva o que se fala sobre a Apple e Inovação"
rewritten = rewrite_query_for_search(query)
# Resultado: "Apple Inovação"
# Perfeito para EntityAwareRetriever!
```

**Vantagem:** Simples, mantém entidades e conceitos  
**Desvantagem:** Perde intenção ("descreva")

---

### **Estratégia 3: LLM Query Rewriting (Avançado)**

```python
async def rewrite_with_llm(query: str, llm_client) -> str:
    """Usa LLM para reescrever query mantendo intenção"""
    
    prompt = f"""
    Reescreva esta query de forma mais concisa para busca:
    Original: "{query}"
    
    Mantenha:
    - Entidades (nomes próprios)
    - Conceitos (tópicos principais)
    - Intenção (se relevante)
    
    Remove:
    - Artigos, preposições desnecessárias
    - Estrutura gramatical
    
    Resultado:
    """
    
    response = await llm_client.generate(prompt)
    return response.strip()

# Teste
query = "descreva o que se fala sobre a Apple e Inovação"
rewritten = await rewrite_with_llm(query, client)
# Resultado possível: "inovação da Apple" ou "estratégia de inovação Apple"
# Muito bom para EntityAwareRetriever + LLM!
```

**Vantagem:** Mantém contexto e intenção  
**Desvantagem:** Mais lento, custa tokens

---

## 🚀 **O Que Implementar Primeiro**

### **Curto Prazo (Rápido):**

```python
# No EntityAwareRetriever.retrieve():

# 1. Limpa query com Query Parser
parsed = parse_query(query)

# 2. Se tem conceitos semânticos, adiciona à busca
if parsed["semantic_concepts"]:
    search_query = " ".join(parsed["semantic_concepts"])
else:
    search_query = query

# 3. Busca com ambos (entidade + semântica)
chunks = await weaviate_manager.hybrid_search(
    vector=embedding_model.encode(search_query),
    entity_filter=Filter("entities").contains_any(parsed["entity_ids"]),
    alpha=0.6
)
```

### **Médio Prazo:**

```python
# Query Cleaning adiciona ao workflow
cleaned_query = clean_query_for_entity_search(query)

# Usa cleaned_query para entity extraction
entity_ids = extract_entities_from_query(cleaned_query)

# Usa query original para vector search
vector = embedding_model.encode(query)
```

### **Longo Prazo:**

```python
# Query Rewriting com LLM (antes de retrieval)
rewritten = await llm_client.rewrite_query(query)

# Usa rewritten para retrieval
# Usa original para geração
```

---

## 💡 **Sua Observação Identificou um Padrão Real**

Quando o usuário escreve em **linguagem natural com verbos**:

```
❌ "descreva o que se fala sobre..."
❌ "qual é a relação entre..."
❌ "como a Apple inova em..."
❌ "compare Apple e Microsoft"
```

O sistema **NÃO consegue extrair entidades e conceitos corretamente** porque:

1. **Ruído linguístico**: Verbos, artigos, preposições atrapalham
2. **Perda de intenção**: "descreva" é importante para LLM
3. **Estrutura complexa**: Não é apenas "entidade + conceito"
4. **Ambiguidade**: "sobre" muda o contexto

**Solução necessária**: Query Cleaning + Intent Preservation
