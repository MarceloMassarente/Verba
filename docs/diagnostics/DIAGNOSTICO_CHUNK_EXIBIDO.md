# 🔍 Diagnóstico: Chunk Exibido na UI

## 📋 Chunk Mostrado

**Chunk 2.028** do documento:
"Executive Search Technology Solutions_Market Landscape 2023-2025.pdf"

**Conteúdo:**
```
bforce +2 Draup Alpha Apex Group Talentis Global talentis Loxo +2 Jake Jor govan TrustRadius Loxo Loxo Loxo Loxo RecruiterFlow Jake Jor govan RecruiterFlow Executivesearch
```

---

## ❓ Problemas Identificados

### 1. **Chunk Fragmentado**
- Parece ser uma **lista de nomes de empresas/ferramentas**
- Conteúdo está muito fragmentado e sem contexto
- Não há frases completas ou contexto semântico

### 2. **Possíveis Causas**

#### A. **Chunking por Sentenças em Lista**
- Se o documento tem listas sem pontuação completa
- O chunker pode estar dividindo por `.` ou `\n`
- Mas listas não têm estrutura clara de sentenças

#### B. **ETL Pré-Chunking Não Conseguiu Evitar**
- `entity_spans` pode não estar detectando essas entidades corretamente
- Listas podem não ter estrutura clara para detectar entidades
- spaCy pode não reconhecer todos os nomes como entidades

#### C. **Chunking por Seções Falhou**
- Se não detectou seções claras, usa chunking por sentenças
- Mas listas não têm sentenças completas

---

## ✅ Verificações Necessárias

### 1. **ETL Pré-Chunking Funcionou?**
Procure nos logs:
```
[ETL-PRE] Extraídas 472 entidades do documento completo
[ETL-PRE] ✅ Entidades armazenadas no documento: 472 spans
[ENTITY-AWARE] Usando 472 entidades pré-extraídas para chunking entity-aware
```

**Se apareceu:** ✅ ETL pré funcionou  
**Se não apareceu:** ❌ ETL pré não funcionou

### 2. **Chunker Usou Entity-Aware?**
Procure nos logs:
```
[ENTITY-AWARE] Usando X entidades pré-extraídas para chunking entity-aware
[ENTITY-AWARE] Evitando cortar entidade no meio - incluindo parágrafo completo
```

**Se apareceu:** ✅ Chunker está tentando ser entity-aware  
**Se não apareceu:** ❌ Chunker não está usando entity_spans

### 3. **ETL Pós-Chunking Adicionou Metadados?**
Verifique no Weaviate se o chunk tem:
- `entities_local_ids`: Lista de entity_ids detectados no chunk
- `section_title`: Título da seção
- `section_first_para`: Primeiro parágrafo da seção

---

## 🎯 O Que Deveria Acontecer

### **Cenário Ideal:**
1. **ETL Pré:** Extrai entidades do documento completo
   - Detecta: "Draup", "Alpha Apex Group", "Loxo", "RecruiterFlow", etc.
   - Armazena posições em `entity_spans`

2. **Chunking Entity-Aware:**
   - Detecta que há entidades nesta lista
   - Tenta manter a lista completa em um chunk
   - Evita cortar no meio de "Alpha Apex Group" ou "Jake Jorgovan"

3. **ETL Pós:**
   - Processa chunk individual
   - Adiciona metadados: `entities_local_ids = ["ent:org:draup", "ent:org:loxo", ...]`
   - Identifica seção: "Market Landscape - Tools"

### **Resultado Esperado:**
- ✅ Chunk completo com lista inteira
- ✅ Metadados de entidades no Weaviate
- ✅ Chunk pode ser filtrado por entidade (ex: "Loxo")

---

## 🔧 Possíveis Problemas

### **Problema 1: Listas Não São Detectadas como Entidades**
**Causa:** spaCy pode não reconhecer todos os nomes como ORG  
**Solução:** Melhorar gazetteer ou adicionar regras customizadas

### **Problema 2: Chunker Não Está Usando Entity-Spans**
**Causa:** `entity_spans` pode não estar chegando no chunker  
**Solução:** Verificar se `document.meta["entity_spans"]` está presente

### **Problema 3: Chunking por Sentenças Não Funciona para Listas**
**Causa:** Listas não têm estrutura de sentenças  
**Solução:** Melhorar detecção de listas no chunker

---

## 📊 Checklist de Diagnóstico

Execute esta verificação:

### **1. Verificar Logs de ETL Pré:**
```bash
# Procure nos logs:
[ETL-PRE] Extraídas X entidades
[ETL-PRE] ✅ Entidades armazenadas
```

### **2. Verificar Logs de Chunking:**
```bash
# Procure nos logs:
[ENTITY-AWARE] Usando X entidades
[ENTITY-AWARE] Evitando cortar entidade
```

### **3. Verificar Metadados no Weaviate:**
```python
# No Weaviate, verifique um chunk:
chunk = client.collections.get("Passage").query.fetch_objects(
    filters=Filter.by_property("chunk_id").equal("2.028"),
    limit=1
)

# Verifique se tem:
chunk.properties.get("entities_local_ids")  # Deveria ter lista
chunk.properties.get("section_title")      # Deveria ter título
```

### **4. Verificar Conteúdo Original:**
```python
# No Weaviate, veja o texto completo do chunk:
chunk.properties.get("text")  # Deveria ter mais contexto
```

---

## 💡 Conclusão

**Chunk Mostrado:** ❌ **NÃO parece ideal**
- Fragmentado demais
- Sem contexto semântico claro
- Parece ser uma lista cortada

**Possíveis Causas:**
1. Listas não são detectadas como entidades pelo spaCy
2. Chunker não está evitando cortes em listas
3. Chunking por sentenças não funciona bem para listas

**Próximos Passos:**
1. Verificar logs para confirmar se ETL pré funcionou
2. Verificar se chunker está usando entity_spans
3. Verificar se ETL pós adicionou metadados
4. Melhorar chunker para lidar melhor com listas

