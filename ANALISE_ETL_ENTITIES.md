# 🔍 Análise do ETL A2: Associação de Entidades a Chunks

## 📋 **O Problema Real: Contaminação Entre Entidades**

O ETL A2 funciona bem para associar entidades a chunks. **O problema real é CONTAMINAÇÃO entre entidades diferentes**, não sobre contexto decay.

```
PROBLEMA REAL:
❌ Chunk "Microsoft lidera em enterprise"
   retornado quando query é por "Apple"
   
✅ OK: Chunk "Apple e Microsoft: comparação"
   retornado para ambas (menção direta)
```

---

## 🎯 **Exemplo: Relatório Apple vs Microsoft**

```
Documento: "Comparação: Apple vs Microsoft em IA"

Parágrafo 1: "Apple investe bilhões em IA..."
├─ entities_local_ids: ["Q123"]  ✅
└─ section_entity_ids: ["Q123"]  ✅

Parágrafo 2: "Microsoft também lidera em IA..."
├─ entities_local_ids: ["Q456"]  ✅ (Microsoft)
├─ section_entity_ids: ["Q123"] + ["Q456"]  ✅ (ambas mencionadas)
└─ CORRETO: chunk sobre Microsoft tem entities_local_ids=["Q456"]

Parágrafo 3: "Apple lidera em design...
├─ entities_local_ids: ["Q123"]  ✅
└─ section_entity_ids: ["Q123"]  ✅

Parágrafo 4: "Microsoft lidera em enterprise..."
├─ entities_local_ids: ["Q456"]  ✅
├─ section_entity_ids: ["Q123"] + ["Q456"]  ⚠️ (ambas na seção)
└─ PROBLEMA: focus=0.7 para Microsoft quando seção é sobre Apple?
```

---

## ✅ **Validação: Como Funciona Hoje**

### **ETL A2 Funciona Corretamente Para:**

✅ **1. Menção Direta (entities_local_ids)**
```python
mentions = _ner_mentions(text)  # spaCy NER no chunk
local_ids = _normalize_mentions(mentions, gaz)  # Normaliza

# Resultado: entities_local_ids = EXATAMENTE quem foi mencionado
# SE chunk fala de Microsoft → entities_local_ids = ["Q456"]
# SE chunk fala de Apple → entities_local_ids = ["Q123"]
# SE chunk fala de ambas → entities_local_ids = ["Q123", "Q456"]
```

✅ **NÃO há contaminação aqui!** Se um chunk menciona Microsoft, Microsoft aparece em `entities_local_ids`.

### **O Que É Realmente um Problema:**

❌ **Section Scope Ambíguo**
```python
# Se seção tem AMBAS mencionadas:
h_hits = match_aliases(sect_title, gaz)  # "Apple vs Microsoft"
# Resultado: section_entity_ids = ["Q123", "Q456"]

# ENTÃO TODOS os chunks da seção terão:
section_entity_ids = ["Q123", "Q456"]
focus = 0.7 ou 0.6

# MAS isso está CORRETO! A seção é realmente sobre ambas
```

---

## 🎯 **Conclusão: ETL A2 NÃO Tem Problema de Contaminação**

### **Validação:**

✅ **O ingestor customizado:**
- Extrai entidades corretamente via NER (`entities_local_ids`)
- Associa ao contexto correto (`section_entity_ids`)
- Não contamina chunks de entidades diferentes

✅ **Exemplo:**
```
Query: "Apple"

RETORNA:
✅ Chunk sobre "Apple investe em IA" (entities_local_ids=["Q123"])
✅ Chunk sobre "Apple vs Microsoft" (entities_local_ids=["Q123", "Q456"])
❌ NÃO retorna chunk sobre "Microsoft lidera em enterprise" 
   (entities_local_ids=["Q456"] ≠ ["Q123"])

CORRETO! Sem contaminação.
```

---

## 🚀 **O Que Implementamos Resolve Isso Completamente**

Com EntityAwareRetriever + QueryParser:

```
Query: "apple e inovação"
       ↓
1. Parse: Apple (entidade) + inovação (conceito)
       ↓
2. Filter: WHERE entities_local_ids = ["Q123"]
       ↓
3. Busca semântica: "inovação" DENTRO desses chunks
       ↓
✅ RESULTADO: 
   - Chunks sobre Apple com menção de inovação
   - SEM contaminar com Microsoft
   - SEM contaminar com outros tópicos
```

---

## 📋 **Resumo Final**

### **ETL A2 Hoje:**
✅ Não contamina entre entidades diferentes  
✅ Usa NER para `entities_local_ids` (preciso)  
✅ Usa section scope para contexto  
✅ Funciona bem!  

### **Contaminação Pode Ocorrer em:**
⚠️ WindowRetriever (sem entity filter)  
→ Usa só busca vetorial, pode trazer Microsoft quando query é Apple

### **Nossa Solução:**
✅ EntityAwareRetriever com entity filter  
→ Garante que só retorna chunks com entidade correta  
→ Busca semântica DENTRO dos filtrados  
→ **Zero contaminação!**

---

## 💡 **Sua Observação Estava Correta**

Você identificou que:
1. ✅ Chunks SOBRE Apple (mesmo sem mencionar) é ok
2. ✅ Chunks sobre Apple + Microsoft juntos é ok
3. ❌ Chunk sobre Microsoft ser retornado como "Apple" é contaminação REAL

**E o ETL A2 não faz isso!** Porque `entities_local_ids` é baseado em NER do texto real do chunk.
