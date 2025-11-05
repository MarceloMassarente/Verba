# 🔍 EntityAware Retriever: Tipos de Queries Suportadas

## ✅ **O Que Funciona (Hoje)**

### **1. Entidades Nomeadas Simples**

```
Query: "Apple"
↓
spaCy detecta: "Apple" (ORG)
↓
Gazetteer mapeia: Apple → entity_id "Q123"
↓
Resultado: ✅ Chunks APENAS sobre Apple
```

### **2. Múltiplas Entidades**

```
Query: "apple e microsoft"
↓
spaCy detecta: ["Apple" (ORG), "Microsoft" (ORG)]
↓
Entity filter: contains_any(["Q123", "Q456"])  ← OR logic
↓
Resultado: ✅ Chunks sobre (Apple OU Microsoft)
```

### **3. Nomes de Pessoas**

```
Query: "inovações de Steve Jobs"
↓
spaCy detecta: ["Steve Jobs" (PERSON)]
↓
Gazetteer mapeia: Steve Jobs → entity_id "Q789"
↓
Resultado: ✅ Chunks sobre Steve Jobs
```

### **4. Localizações**

```
Query: "empresas em São Paulo"
↓
spaCy detecta: ["São Paulo" (GPE)]
↓
Resultado: ✅ Chunks sobre São Paulo
```

---

## ❌ **O Que NÃO Funciona (Limitações Atuais)**

### **1. Palavras-Chave Genéricas**

```
Query: "inovação"
↓
spaCy detecta: NADA (não é entidade nomeada)
↓
Entity filter: ❌ NÃO APLICA
↓
Resultado: ⚠️ Busca normal (sem filtro entity-aware)
```

### **2. Conceitos Compostos**

```
Query: "apple e inovação"
↓
spaCy detecta: ["Apple" (ORG)]  ← "inovação" ignorada!
↓
Entity filter: contains_any(["Q123"])  ← Só Apple
↓
Resultado: ⚠️ Filtra por Apple, MAS ignora "inovação"
        Você quer: chunks sobre (Apple E inovação)
        Recebe: chunks sobre Apple (com qualquer contexto)
```

### **3. Perguntas Complexas com Lógica**

```
Query: "qual é a diferença de inovação entre Apple e Microsoft?"
↓
spaCy detecta: ["Apple" (ORG), "Microsoft" (ORG)]
↓
Entity filter: contains_any(["Q123", "Q456"])  ← Apple OU Microsoft
↓
Resultado: ⚠️ Filtra por (Apple OU Microsoft), mas não captura:
           - Relacionamento entre empresas
           - Comparação
           - Diferenças
```

---

## 📊 **Tabela de Compatibilidade**

| Query | Tipo | Funciona? | Comportamento |
|-------|------|-----------|---------------|
| `"apple"` | Entidade única | ✅ SIM | Filtra por Apple |
| `"apple e microsoft"` | Múltiplas entidades | ✅ SIM | Filtra por (Apple OU Microsoft) |
| `"Steve Jobs"` | Pessoa | ✅ SIM | Filtra por Steve Jobs |
| `"apple e inovação"` | Entidade + conceito | ⚠️ PARCIAL | Filtra Apple, ignora "inovação" |
| `"inovação"` | Conceito puro | ❌ NÃO | Sem filtro entity-aware |
| `"empresas de tecnologia"` | Descrição genérica | ❌ NÃO | Sem filtro entity-aware |
| `"apple vs microsoft"` | Comparação | ⚠️ PARCIAL | Filtra (Apple OU Microsoft), sem contexto de "vs" |

---

## 🎯 **Solução Recomendada**

### **Para Queries Complexas (Conceitos + Entidades)**

Use a **busca vetorial padrão** em vez do EntityAware:

1. **Chat Settings** → **Retriever** → **Window** (em vez de EntityAware)
2. Query: `"apple e inovação"`
3. O sistema faz:
   - Busca vetorial por relevância (não filtrada por entidade)
   - Retorna chunks mais relevantes para "apple" AND "inovação"
   - ✅ Funciona bem para conceitos + contexto

### **Para Queries Puras de Entidades**

Use **EntityAware Retriever**:

1. **Chat Settings** → **Retriever** → **EntityAware**
2. Query: `"apple"` ou `"apple e microsoft"`
3. O sistema faz:
   - Extrai entidades com spaCy + Gazetteer
   - Aplica filtro WHERE no Weaviate (mais rápido!)
   - ✅ Evita contaminação entre empresas

---

## 🚀 **Como Melhorar (Roadmap)**

### **Opção 1: Suporte a Palavras-Chave**

```python
# Adicionar keywords ao gazetteer
gazetteer.json:
{
  "inovacao_topic": {
    "entity_id": "TOPIC_INOVACAO",
    "aliases": ["inovação", "inovações", "innovation"]
  }
}

# Query: "apple e inovação"
# Resultado: Filtra por (Apple AND inovação_topic)
```

### **Opção 2: Hybrid Filtering**

```python
# Combina entity filter + keyword search
entity_filter = Filter.by_property("entities").contains_any(["Q123"])
keyword_filter = Filter.by_property("keywords").contains_any(["inovacao"])

# Aplica: entity_filter AND keyword_filter
final_filter = entity_filter & keyword_filter
```

### **Opção 3: Query Rewriting**

```python
# Expande query antes de processar
"apple e inovação"
  ↓
"apple AND (inovação OR innovation OR innovative)"
  ↓
Filtra por entidades + keywords
```

---

## 📝 **Resumo: Use EntityAware Quando**

✅ Quer **evitar contaminação** entre empresas/pessoas  
✅ Query tem **entidades nomeadas claras** (Apple, Microsoft, etc)  
✅ Quer **busca rápida** (filtro WHERE em vez de vector)  
✅ Tem **gazetteer bem alimentado**  

❌ Quer buscar por **conceitos abstratos** (inovação, tendências)  
❌ Query é **muito complexa** (múltiplas condições lógicas)  
❌ Precisa de **relacionamentos** entre entidades  
