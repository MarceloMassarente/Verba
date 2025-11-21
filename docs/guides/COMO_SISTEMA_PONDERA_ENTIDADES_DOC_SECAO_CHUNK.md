# Como o Sistema Pondera Entidades: Documento vs Seção vs Chunk

## Hierarquia de Níveis

O sistema armazena e pondera entidades em **3 níveis hierárquicos**:

```
DOCUMENTO (nível mais alto)
  └─ SEÇÃO (nível intermediário)
      └─ CHUNK (nível mais baixo)
```

## Campos Armazenados em Cada Chunk

### 1. Entidades Locais (Chunk Level)
- **Campo**: `entities_local_ids`
- **Origem**: Extraídas diretamente do **texto do chunk** via spaCy NER
- **Peso na frequência**: **1.0** (peso completo)
- **Confiança**: **100%** (menção explícita no chunk)

### 2. Entidades da Seção (Section Level)
- **Campo**: `section_entity_ids`
- **Origem**: Extraídas do contexto da seção (título, primeiro parágrafo, ou parent)
- **Peso na frequência**: **0.5** (peso reduzido)
- **Confiança**: **0.6 - 0.9** (depende da origem)

### 3. Confiança do SectionScope
- **Campo**: `section_scope_confidence`
- **Valores**:
  - `0.9`: Entidade encontrada no `section_title` (mais confiável)
  - `0.7`: Entidade encontrada no `section_first_para`
  - `0.6`: Entidade herdada de `parent_entities`
  - `0.0`: Nenhuma entidade encontrada

### 4. Entidade Primária
- **Campo**: `primary_entity_id`
- **Lógica**: Primeira entidade de `entities_local_ids`, ou primeira de `section_entity_ids`
- **Prioridade**: `local_ids[0]` > `sect_ids[0]`

### 5. Entity Focus Score
- **Campo**: `entity_focus_score`
- **Valores**:
  - `1.0`: Entidade primária está em `entities_local_ids` (mencionada explicitamente)
  - `0.7`: Entidade primária está apenas em `section_entity_ids` (contexto)
  - `0.0`: Nenhuma entidade primária

## Cálculo de Frequência

### Como Funciona

**Arquivo**: `verba_extensions/utils/entity_frequency.py` (linhas 16-78)

```python
async def get_entity_frequency_in_document(...):
    entity_counter = Counter()
    
    for chunk in chunks_do_documento:
        # Peso 1.0 para entities_local_ids
        local_ids = chunk.properties.get("entities_local_ids", [])
        if local_ids:
            entity_counter.update(local_ids)  # +1.0 por chunk
        
        # Peso 0.5 para section_entity_ids
        section_ids = chunk.properties.get("section_entity_ids", [])
        if section_ids:
            entity_counter.update({eid: 0.5 for eid in section_ids})  # +0.5 por chunk
    
    # Retorna: {"Q312": 15.5, "Q2283": 8.0}
    return dict(entity_counter.most_common())
```

### Exemplo Prático

**Documento**: "Análise de Mercado Tech 2024"

```
Chunk 1:
  entities_local_ids: ["Q312"]        # Apple mencionada explicitamente
  section_entity_ids: ["Q312"]        # Seção também sobre Apple
  → Contagem: Q312 = 1.0 + 0.5 = 1.5

Chunk 2:
  entities_local_ids: []              # Não menciona Apple
  section_entity_ids: ["Q312"]        # Mas seção é sobre Apple
  → Contagem: Q312 = 0.0 + 0.5 = 0.5

Chunk 3:
  entities_local_ids: ["Q312", "Q2283"]  # Apple e Microsoft
  section_entity_ids: ["Q312"]           # Seção sobre Apple
  → Contagem: Q312 = 1.0 + 0.5 = 1.5
    Q2283 = 1.0 + 0.0 = 1.0

Total no documento:
  Q312 (Apple): 1.5 + 0.5 + 1.5 = 3.5
  Q2283 (Microsoft): 1.0
```

## Hierarquia de Confiança

### 1. SectionScope (Ordem de Prioridade)

**Arquivo**: `verba_extensions/etl/etl_a2.py` (linhas 112-124)

```python
# Ordem de verificação:
if h_hits:  # section_title menciona entidade
    sect_ids, scope_conf = h_hits, 0.9  # ← MAIS CONFIANÇA
elif fp_hits:  # section_first_para menciona
    sect_ids, scope_conf = fp_hits, 0.7
elif parent_ents:  # parent_entities (herdado)
    sect_ids, scope_conf = parent_ents, 0.6  # ← MENOS CONFIANÇA
```

**Exemplo**:
```
Section Title: "Apple e Inovação"
  → section_entity_ids: ["Q312"]
  → section_scope_confidence: 0.9  ✅

Section Title: "" (vazio)
Section First Para: "Apple foi fundada..."
  → section_entity_ids: ["Q312"]
  → section_scope_confidence: 0.7  ✅

Ambos vazios, mas parent_entities: ["Q312"]
  → section_entity_ids: ["Q312"]
  → section_scope_confidence: 0.6  ✅
```

### 2. Entity Focus Score

**Arquivo**: `verba_extensions/etl/etl_a2.py` (linha 128)

```python
# Primary entity escolhida
primary = local_ids[0] if local_ids else (sect_ids[0] if sect_ids else None)

# Focus score baseado em onde está a primary
focus = 1.0 if primary and primary in local_ids else (0.7 if primary else 0.0)
```

**Lógica**:
- **focus = 1.0**: Entidade primária mencionada explicitamente no chunk
- **focus = 0.7**: Entidade primária apenas no contexto da seção
- **focus = 0.0**: Sem entidade primária

## Filtros por Frequência

### 1. Frequência Mínima

**Arquivo**: `verba_extensions/plugins/entity_aware_retriever.py` (linhas 570-582)

```python
# Filtrar documentos onde entidade aparece pelo menos N vezes
if min_frequency > 0:
    freq = await get_entity_frequency_in_document(client, collection_name, doc_uuid)
    
    # Verificar se entidade tem frequência suficiente
    has_min_freq = any(
        freq.get(eid, 0) >= min_frequency
        for eid in chunk_level_entities
    )
    
    if not has_min_freq:
        exclude_document  # ❌ Exclui documento inteiro
```

**Exemplo**:
```python
# Query: "Apple" com min_frequency=5
# Documento 1: Apple aparece 8 vezes → ✅ INCLUÍDO
# Documento 2: Apple aparece 2 vezes → ❌ EXCLUÍDO
```

### 2. Entidade Dominante

**Arquivo**: `verba_extensions/plugins/entity_aware_retriever.py` (linhas 585-592)

```python
# Filtrar apenas documentos onde entidade é dominante
if dominant_only:
    dominant_entity, _, _ = await get_dominant_entity(
        client, collection_name, doc_uuid
    )
    
    # Verificar se entidade do filtro é dominante
    if dominant_entity not in chunk_level_entities:
        exclude_document  # ❌ Exclui documento
```

**Exemplo**:
```python
# Query: "Apple" com dominant_only=True
# Documento 1: Apple (15x), Microsoft (3x) → ✅ Apple é dominante
# Documento 2: Microsoft (20x), Apple (5x) → ❌ Microsoft é dominante
```

### 3. Comparação de Frequência

**Arquivo**: `verba_extensions/plugins/entity_aware_retriever.py` (linhas 595-607)

```python
# Filtrar documentos onde entity_1 aparece N vezes mais que entity_2
if frequency_comparison:
    ratio = freq_1 / freq_2
    
    if ratio < min_ratio:
        exclude_document  # ❌ Exclui documento
```

**Exemplo**:
```python
# Query: "Apple" vs "Microsoft" com min_ratio=2.0
# Documento 1: Apple (20x), Microsoft (5x) → ratio=4.0 → ✅ INCLUÍDO
# Documento 2: Apple (10x), Microsoft (8x) → ratio=1.25 → ❌ EXCLUÍDO
```

## Filtros Hierárquicos

### Document Level vs Chunk Level

**Arquivo**: `verba_extensions/plugins/entity_aware_retriever.py` (linhas 306-352)

```python
# 1. PRIMEIRO: Filtrar documentos (nível documento)
document_level_filter = query_filters_from_builder.get("document_level_entities", [])

if document_level_filter:
    # Busca documentos que contêm entidade
    doc_uuids = await get_documents_by_entity(
        client, collection_name, entity_id
    )
    
    # Restringe busca a esses documentos
    document_uuids = doc_uuids

# 2. DEPOIS: Filtrar chunks dentro dos documentos (nível chunk)
chunk_level_entities = entity_ids

if chunk_level_entities:
    # Filtra chunks dentro dos documentos já filtrados
    entity_filter = Filter.by_property("section_entity_ids").contains_any(
        chunk_level_entities
    )
```

**Exemplo**:
```python
# Query: "documentos sobre Apple, depois chunks sobre inovação"

# Passo 1: Filtrar documentos
document_level_entities: ["Q312"]  # Apple
→ Encontra: Doc1, Doc2, Doc3 (todos falam de Apple)

# Passo 2: Filtrar chunks dentro desses documentos
chunk_level_entities: []  # Não há, mas busca semântica por "inovação"
→ Dentro de Doc1, Doc2, Doc3, busca chunks sobre "inovação"
```

## Resumo da Ponderação

### Peso na Frequência

| Nível | Campo | Peso | Exemplo |
|-------|-------|------|---------|
| **Chunk** | `entities_local_ids` | **1.0** | Apple mencionada no texto do chunk |
| **Seção** | `section_entity_ids` | **0.5** | Apple no título da seção |

### Confiança do SectionScope

| Origem | Confidence | Significado |
|--------|-----------|-------------|
| `section_title` | **0.9** | Título da seção menciona entidade |
| `section_first_para` | **0.7** | Primeiro parágrafo menciona |
| `parent_entities` | **0.6** | Herdado do documento/seção pai |

### Entity Focus Score

| Score | Condição | Significado |
|-------|----------|-------------|
| **1.0** | `primary_entity_id` em `entities_local_ids` | Entidade mencionada explicitamente |
| **0.7** | `primary_entity_id` apenas em `section_entity_ids` | Entidade apenas no contexto |
| **0.0** | Sem `primary_entity_id` | Nenhuma entidade identificada |

## Exemplo Completo

### Documento: "Análise de Mercado Tech 2024"

**Estrutura**:
```
Documento
├─ [Seção: "Apple - Inovação"]
│  ├─ Chunk 1: "Apple foi fundada em 1976..."
│  │   entities_local_ids: ["Q312"]
│  │   section_entity_ids: ["Q312"]
│  │   section_scope_confidence: 0.9
│  │   primary_entity_id: "Q312"
│  │   entity_focus_score: 1.0
│  │   → Frequência: Q312 = 1.0 + 0.5 = 1.5
│  │
│  ├─ Chunk 2: "O iPhone revolucionou..."
│  │   entities_local_ids: []
│  │   section_entity_ids: ["Q312"]
│  │   section_scope_confidence: 0.9
│  │   primary_entity_id: "Q312"
│  │   entity_focus_score: 0.7
│  │   → Frequência: Q312 = 0.0 + 0.5 = 0.5
│  │
│  └─ Chunk 3: "Em Cupertino, a empresa..."
│      entities_local_ids: []
│      section_entity_ids: ["Q312"]
│      section_scope_confidence: 0.9
│      primary_entity_id: "Q312"
│      entity_focus_score: 0.7
│      → Frequência: Q312 = 0.0 + 0.5 = 0.5
│
└─ [Seção: "Microsoft - Competição"]
   ├─ Chunk 4: "Microsoft lançou o Windows..."
   │   entities_local_ids: ["Q2283"]
   │   section_entity_ids: ["Q2283"]
   │   section_scope_confidence: 0.9
   │   primary_entity_id: "Q2283"
   │   entity_focus_score: 1.0
   │   → Frequência: Q2283 = 1.0 + 0.5 = 1.5
   │
   └─ Chunk 5: "A empresa de Redmond..."
      entities_local_ids: []
      section_entity_ids: ["Q2283"]
      section_scope_confidence: 0.9
      primary_entity_id: "Q2283"
      entity_focus_score: 0.7
      → Frequência: Q2283 = 0.0 + 0.5 = 0.5
```

**Frequência Total no Documento**:
```
Q312 (Apple): 1.5 + 0.5 + 0.5 = 2.5
Q2283 (Microsoft): 1.5 + 0.5 = 2.0

Entidade Dominante: Q312 (Apple) com 2.5 menções
```

## Como Usar na Busca

### 1. Filtro Simples (Chunk Level)

```python
# Busca chunks com Apple em section_entity_ids
Filter.by_property("section_entity_ids").contains_any(["Q312"])
```

**Resultado**: Todos chunks que têm Apple no contexto (seção ou chunk)

### 2. Filtro com Frequência Mínima

```python
# Busca documentos onde Apple aparece pelo menos 5 vezes
filter_by_frequency: True
min_frequency: 5
```

**Resultado**: Apenas documentos onde Apple tem frequência >= 5

### 3. Filtro por Entidade Dominante

```python
# Busca documentos onde Apple é entidade dominante
filter_by_frequency: True
dominant_only: True
```

**Resultado**: Apenas documentos onde Apple é a mais frequente

### 4. Filtro Hierárquico

```python
# Primeiro: documentos sobre Apple
# Depois: chunks sobre inovação dentro desses documentos
document_level_entities: ["Q312"]
entities: []  # Sem filtro de chunk, busca semântica por "inovação"
```

**Resultado**: Chunks sobre inovação dentro de documentos sobre Apple

## Conclusão

O sistema pondera entidades usando:

1. **Peso na Frequência**:
   - Chunk level (`entities_local_ids`): **1.0**
   - Section level (`section_entity_ids`): **0.5**

2. **Confiança do Contexto**:
   - Section title: **0.9**
   - Section first para: **0.7**
   - Parent entities: **0.6**

3. **Entity Focus**:
   - Mencionada explicitamente: **1.0**
   - Apenas contexto: **0.7**

4. **Filtros Disponíveis**:
   - Frequência mínima
   - Entidade dominante
   - Comparação de frequência
   - Filtro hierárquico (documento → chunk)

Essa hierarquia permite:
- ✅ Filtrar documentos por entidade dominante
- ✅ Filtrar chunks por contexto de seção
- ✅ Priorizar chunks com menções explícitas
- ✅ Considerar frequência relativa entre documentos




