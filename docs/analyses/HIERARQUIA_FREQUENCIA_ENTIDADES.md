# 📊 Hierarquia de Frequência de Entidades

## ❓ Pergunta

**Existe alguma hierarquia de presença de entidades? Tipo quantas vezes Apple vs Microsoft é citada?**

## ✅ Resposta

**Sim!** Agora existe suporte para calcular frequência e hierarquia de entidades.

---

## 🔧 O Que Foi Criado

### **1. Helper: `entity_frequency.py`**

Funções para calcular frequência de entidades:

#### **`get_entity_frequency_in_document()`**
```python
# Conta quantas vezes cada entidade aparece em um documento
freq = await get_entity_frequency_in_document(
    client,
    "VERBA_Embedding_all_MiniLM_L6_v2",
    "doc-123"
)

# Retorna: {"Q312": 15, "Q2283": 8, "Q95": 3}
# Significa: Apple aparece 15x, Microsoft 8x, Google 3x
```

#### **`get_entity_hierarchy()`**
```python
# Retorna hierarquia ordenada por frequência
hierarchy = await get_entity_hierarchy(
    client,
    "VERBA_Embedding_all_MiniLM_L6_v2",
    "doc-123"
)

# Retorna: [
#   ("Q312", 15, 0.58),  # Apple: 15 menções, 58% do total
#   ("Q2283", 8, 0.31),  # Microsoft: 8 menções, 31% do total
#   ("Q95", 3, 0.12)     # Google: 3 menções, 12% do total
# ]
```

#### **`get_dominant_entity()`**
```python
# Retorna entidade mais frequente
dominant = await get_dominant_entity(
    client,
    "VERBA_Embedding_all_MiniLM_L6_v2",
    "doc-123"
)

# Retorna: ("Q312", 15, 0.58)  # Apple é dominante
```

#### **`get_entity_ratio()`**
```python
# Compara duas entidades
ratio, freqs = await get_entity_ratio(
    client,
    "VERBA_Embedding_all_MiniLM_L6_v2",
    "doc-123",
    "Q312",  # Apple
    "Q2283"  # Microsoft
)

# Retorna: (1.875, {"Q312": 15, "Q2283": 8})
# Significa: Apple aparece 1.875x mais que Microsoft
```

---

## 📊 Como Funciona

### **1. Contagem de Frequência**

```python
# Para cada chunk do documento:
for chunk in chunks:
    # Conta entities_local_ids (peso 1.0)
    for entity_id in chunk.entities_local_ids:
        counter[entity_id] += 1.0
    
    # Conta section_entity_ids (peso 0.5 - menos específico)
    for entity_id in chunk.section_entity_ids:
        counter[entity_id] += 0.5
```

### **2. Ordenação por Frequência**

```python
# Ordena por frequência (decrescente)
hierarchy = sorted(
    entities.items(),
    key=lambda x: x[1],
    reverse=True
)

# Calcula porcentagens
total = sum(count for _, count in hierarchy)
for entity_id, count in hierarchy:
    percentage = count / total
```

---

## 🎯 Casos de Uso

### **1. Filtrar por Entidade Dominante**

```python
# Buscar documentos onde Apple é dominante
hierarchy = await get_entity_hierarchy(client, collection_name, doc_uuid)
if hierarchy[0][0] == "Q312":  # Apple é primeira
    # Apple é dominante neste documento
    pass
```

### **2. Comparar Entidades**

```python
# Verificar se Apple aparece mais que Microsoft
ratio, freqs = await get_entity_ratio(
    client, collection_name, doc_uuid,
    "Q312", "Q2283"
)

if ratio > 1.0:
    print(f"Apple aparece {ratio:.2f}x mais que Microsoft")
elif ratio < 1.0:
    print(f"Microsoft aparece {1/ratio:.2f}x mais que Apple")
else:
    print("Ambas aparecem igualmente")
```

### **3. Filtrar por Frequência Mínima**

```python
# Apenas entidades que aparecem pelo menos 5 vezes
hierarchy = await get_entity_hierarchy(
    client, collection_name, doc_uuid,
    min_frequency=5
)
```

---

## 📋 Exemplo Completo

### **Documento:**
```
Chunk 1: entities_local_ids = ["Q312"] (Apple)
Chunk 2: entities_local_ids = ["Q312", "Q2283"] (Apple + Microsoft)
Chunk 3: entities_local_ids = ["Q2283"] (Microsoft)
Chunk 4: entities_local_ids = ["Q312"] (Apple)
Chunk 5: entities_local_ids = ["Q95"] (Google)
```

### **Frequência:**
```python
freq = await get_entity_frequency_in_document(...)

# Resultado:
{
    "Q312": 3.0,   # Apple: 3 chunks
    "Q2283": 2.0,  # Microsoft: 2 chunks
    "Q95": 1.0     # Google: 1 chunk
}
```

### **Hierarquia:**
```python
hierarchy = await get_entity_hierarchy(...)

# Resultado:
[
    ("Q312", 3.0, 0.50),  # Apple: 50% do total
    ("Q2283", 2.0, 0.33), # Microsoft: 33% do total
    ("Q95", 1.0, 0.17)     # Google: 17% do total
]
```

### **Entidade Dominante:**
```python
dominant = await get_dominant_entity(...)

# Resultado:
("Q312", 3.0, 0.50)  # Apple é dominante
```

---

## 🔄 Integração com QueryBuilder

O QueryBuilder pode ser estendido para usar frequência:

```json
{
    "filters": {
        "entities": ["Q312"],
        "min_frequency": 5,  // Apenas se aparecer 5+ vezes
        "dominant_only": true  // Apenas se for entidade dominante
    }
}
```

---

## ✅ Resumo

1. **Frequência de Entidades:**
   - ✅ Contagem por documento
   - ✅ Contagem por chunks
   - ✅ Pesos diferentes (local_ids: 1.0, section_ids: 0.5)

2. **Hierarquia:**
   - ✅ Ordenação por frequência
   - ✅ Porcentagens do total
   - ✅ Filtro por frequência mínima

3. **Comparação:**
   - ✅ Razão entre duas entidades
   - ✅ Entidade dominante

4. **Uso:**
   - ✅ Filtrar por entidade dominante
   - ✅ Comparar Apple vs Microsoft
   - ✅ Identificar documentos focados em uma entidade

---

**Última atualização:** 2025-01-XX  
**Versão:** 1.0

