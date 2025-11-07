# 📖 Explicação Completa: O Que Acontece com um PDF de Artigos sobre Empresas?

## 🎯 Cenário

Você faz upload de um PDF chamado `artigos_empresas.pdf` que contém:
- **Artigo 1**: "Apple lança novo iPhone"
- **Artigo 2**: "Microsoft anuncia parceria com OpenAI"
- **Artigo 3**: "Google desenvolve IA avançada"

Você escolhe: **"Universal A2 (ETL Automático)"**

---

## 🔄 Fluxo Passo a Passo

### **FASE 1: Upload e Leitura** ⏱️ ~2-5s

```
PDF → Universal A2 Reader → Default Reader → Extração de Texto
```

**O que acontece:**
1. Você faz upload do `artigos_empresas.pdf`
2. `UniversalA2Reader` delega para `BasicReader` (Default)
3. `BasicReader` usa `pypdf` para extrair texto de todas as páginas
4. Texto extraído: `"[Artigo 1 completo]...\n\n[Artigo 2 completo]...\n\n[Artigo 3 completo]..."`

**Resultado:**
- ✅ Um **Document** criado com:
  - `title`: "artigos_empresas.pdf"
  - `content`: Todo o texto extraído (3 artigos juntos)
  - `meta.enable_etl = True` ← Marca para ETL posterior

---

### **FASE 2: ETL Pré-Chunking** ⏱️ ~5-6s (OTIMIZADO)

```
Documento Completo → Extração de Entidades → Entity-Spans
```

**O que acontece:**
1. **Extração de Entidades** via spaCy NER:
   - Extrai apenas **ORG** (organizações) e **PERSON/PER** (pessoas)
   - Exclui LOC/GPE/MISC para performance (reduz 367 → ~110 entidades)
   - **Deduplica** entidades duplicadas por posição
   - **Normaliza** PER (PT) → PERSON (EN) para compatibilidade
   
2. **Armazenamento** em `document.meta["entity_spans"]`:
   ```python
   entity_spans = [
       {"text": "Apple", "start": 0, "end": 5, "label": "ORG"},
       {"text": "Fernando Carneiro", "start": 150, "end": 167, "label": "PERSON"},
       ...
   ]
   ```

**Otimizações:**
- ✅ **Binary search** para filtragem O(n log n) em vez de O(n²)
- ✅ **Deduplicação** evita processar entidades repetidas
- ✅ **Filtro de tipos** reduz volume em 71%

**Resultado:**
- ✅ ~110 entidades extraídas (ORG + PERSON apenas)
- ✅ Armazenadas em `document.meta["entity_spans"]`
- ✅ Prontas para uso no chunking entity-aware

---

### **FASE 3: Chunking Entity-Aware** ⏱️ ~2-3s (OTIMIZADO)

```
Documento + Entity-Spans → Section-Aware Chunker → Múltiplos Chunks
```

**O que acontece:**
1. **Section-Aware Chunker** usa `entity_spans` para:
   - **Evitar cortar entidades** no meio dos chunks
   - **Respeitar seções** do documento
   - **Binary search** para filtrar entidades por seção (O(log n))

2. Divide o texto em chunks respeitando:
   - Limites de seções
   - Posições das entidades (não corta no meio)

**Exemplo de chunks criados:**
```
Chunk 1: "Apple lança novo iPhone. A empresa americana anunciou..."
Chunk 2: "...características técnicas incluem processador A17..."
Chunk 3: "Microsoft anuncia parceria estratégica com OpenAI..."
Chunk 4: "...visa acelerar desenvolvimento de IA generativa..."
Chunk 5: "Google desenvolve novo modelo de IA avançada..."
Chunk 6: "...chamado Gemini Pro, supera ChatGPT em vários benchmarks..."
```

**Resultado:**
- ✅ **6-10 chunks** criados (dependendo do tamanho do PDF)
- Cada chunk tem:
  - `text`: Texto do chunk
  - `doc_uuid`: ID do documento pai (será atribuído depois)

---

### **FASE 4: Embedding (Vectorização)** ⏱️ ~5-15s

```
Chunks → Embedder → Vetores (384/768/1536 dimensões)
```

**O que acontece:**
1. Verba usa o **embedder** escolhido (ex: SentenceTransformers)
2. Cada chunk é convertido em um vetor numérico

**Exemplo:**
```
Chunk 1 → [0.123, -0.456, 0.789, ..., 0.234] (384 números)
Chunk 2 → [0.234, -0.567, 0.890, ..., 0.345]
...
```

**Resultado:**
- ✅ Cada chunk tem um **vetor de embedding**
- Vetores serão usados para busca semântica depois

---

### **FASE 5: Import no Weaviate** ⏱️ ~2-5s

```
Chunks + Vetores → Weaviate → Armazenamento
```

**O que acontece:**
1. `WeaviateManager.import_document()` é chamado
2. Documento é inserido na collection `VERBA_Document`
3. Cada chunk é inserido na collection do embedder (ex: `VERBA_Embedding_SentenceTransformers`)

**Estrutura no Weaviate:**
```
VERBA_Document:
  - uuid: "abc-123-def"
  - properties:
    - title: "artigos_empresas.pdf"
    - content: "[texto completo]"
    - source: "artigos_empresas.pdf"

VERBA_Embedding_SentenceTransformers:
  - uuid: "chunk-1"
  - properties:
    - text: "Apple lança novo iPhone..."
    - doc_uuid: "abc-123-def"
    - chunk_index: 0
  - vector: [0.123, -0.456, ...]
  
  - uuid: "chunk-2"
  - properties:
    - text: "...características técnicas..."
    - doc_uuid: "abc-123-def"
    - chunk_index: 1
  - vector: [0.234, -0.567, ...]
  
  ... (mais chunks)
```

**Resultado:**
- ✅ Documento e chunks armazenados no Weaviate
- ✅ Chunks têm `doc_uuid` vinculado ao documento

---

### **FASE 6: Hook Detecta Import** ⏱️ ~0.1s

```
import_document completo → Hook detecta → Prepara para ETL
```

**O que acontece:**
1. `patched_import_document()` verifica `document.meta.enable_etl`
2. Como está `True`, busca todos os `passage_uuids` do documento:
   ```python
   passages = await embedder_collection.query.fetch_objects(
       filters=Filter.by_property("doc_uuid").equal("abc-123-def"),
       limit=10000
   )
   passage_uuids = ["chunk-1", "chunk-2", "chunk-3", ...]
   ```
3. Dispara hook `'import.after'` em background (não bloqueia)

**Resultado:**
- ✅ Hook registrado para executar ETL
- ✅ Lista de `passage_uuids` preparada

---

### **FASE 7: ETL Pós-Chunking Executa por Chunk** ⏱️ ~10-30s (background) ⭐ ATUALIZADO

```
Cada Chunk → ETL A2 Inteligente → Entidades + Seções → Atualiza Weaviate
```

**⭐ NOVO: ETL Inteligente Multi-idioma**

**O que acontece para CADA chunk:**

#### **7.1. Detecção de Idioma e Extração de Entidades** ⭐ NOVO

Para o **Chunk 1**: `"Apple lança novo iPhone. A empresa americana anunciou..."`

**⭐ NOVO: Detecção Automática de Idioma**

```python
# 1. Detecta idioma automaticamente
from langdetect import detect
language = detect("Apple lança novo iPhone...")  # Retorna "pt"

# 2. Carrega modelo spaCy apropriado
if language == "pt":
    nlp = spacy.load("pt_core_news_sm")
elif language == "en":
    nlp = spacy.load("en_core_web_sm")
else:
    nlp = spacy.load("pt_core_news_sm")  # Fallback

# 3. Extrai entidades (modo inteligente - sem gazetteer obrigatório)
doc = nlp("Apple lança novo iPhone. A empresa americana anunciou...")

# Entidades encontradas (todas as labels):
entity_mentions = [
    {"text": "Apple", "label": "ORG", "confidence": 0.95},
    {"text": "iPhone", "label": "MISC", "confidence": 0.80},
    # Modo inteligente extrai TODAS as entidades, não apenas ORG+PERSON
]
```

**⭐ NOVO: Modo Inteligente vs Modo Gazetteer**

**Modo Inteligente (padrão):**
- ✅ Extrai entidades diretamente do texto
- ✅ Não requer gazetteer manual
- ✅ Funciona out-of-the-box
- ✅ Salva em `entity_mentions` como JSON

**Modo Gazetteer (opcional):**
- Usa gazetteer se disponível para normalização
- Mapeia aliases para `entity_ids` canônicos
- Salva em `entities_local_ids`

**Resultado:**
- ✅ Lista de entidades por chunk (`entity_mentions`)
- ✅ Entidades normalizadas se gazetteer disponível (`entities_local_ids`)

---

#### **7.2. Normalização via Gazetteer (Opcional)**

Para o **Chunk 1** com entidade `"Apple"`:

```python
# Gazetteer mapeia aliases para entity_ids (se disponível)
gazetteer = {
    "Q312": ["Apple", "Apple Inc", "Apple Computer"],
    "Q2283": ["Microsoft", "MSFT", "Microsoft Corporation"],
    "Q95": ["Google", "Google LLC", "Alphabet"]
}

# Busca "Apple" no gazetteer (se disponível)
if gazetteer:
    entity_ids = ["Q312"]  # Apple Inc (normalizado)
else:
    entity_ids = []  # Modo inteligente não requer normalização
```

**Resultado:**
- ✅ Entidades normalizadas para `entity_ids` canônicos (se gazetteer disponível)
- ✅ Modo inteligente funciona mesmo sem gazetteer

---

#### **7.3. Detecção de Seções**

Para o **Chunk 1** no contexto do documento completo:

```python
# Detecta se está em uma seção específica
# Procura por padrões: "## Título", "Introdução", etc.

section_title = "Artigo 1: Apple lança novo iPhone"
section_first_para = "A empresa americana anunciou..."
section_entity_ids = ["Q312"]  # Entidades mencionadas nesta seção
```

**Resultado:**
- ✅ Título de seção identificado
- ✅ Primeiro parágrafo da seção
- ✅ Entidades da seção

---

#### **7.4. Atualização no Weaviate** ⭐ ATUALIZADO

Para **cada chunk**, atualiza metadados na **collection correta**:

```python
# ⭐ NOVO: Collection correta (não mais "Passage")
collection_name = "VERBA_Embedding_all_MiniLM_L6_v2"  # Ou qualquer outro embedder
coll = client.collections.get(collection_name)

# Chunk 1
await coll.data.update(
    uuid="chunk-1",
    properties={
        # ⭐ NOVO: entity_mentions (modo inteligente)
        "entity_mentions": json.dumps([
            {"text": "Apple", "label": "ORG", "confidence": 0.95}
        ]),
        # Modo legado (se gazetteer disponível):
        "entities_local_ids": ["Q312"],           # Entidades normalizadas
        "section_title": "Artigo 1: Apple...",
        "section_first_para": "A empresa...",
        "section_entity_ids": ["Q312"],          # Entidades da seção
        "section_scope_confidence": 0.85,
        "etl_version": "entity_scope_intelligent_v2"  # ⭐ NOVO
    }
)

# Chunk 3 (sobre Microsoft)
await coll.data.update(
    uuid="chunk-3",
    properties={
        # ⭐ NOVO: entity_mentions (modo inteligente)
        "entity_mentions": json.dumps([
            {"text": "Microsoft", "label": "ORG", "confidence": 0.95},
            {"text": "OpenAI", "label": "ORG", "confidence": 0.90}
        ]),
        # Modo legado (se gazetteer disponível):
        "entities_local_ids": ["Q2283"],          # Microsoft
        "section_title": "Artigo 2: Microsoft...",
        "section_first_para": "Microsoft anuncia...",
        "section_entity_ids": ["Q2283", "Q199300"],  # Microsoft + OpenAI
        "etl_version": "entity_scope_intelligent_v2"  # ⭐ NOVO
    }
)
```

**Resultado:**
- ✅ Cada chunk tem metadados de entidades
- ✅ Metadados de seção preenchidos

---

### **FASE 8: Consolidação no Article** ⏱️ ~1-2s

```
Passages atualizados → Consolida entidades → Atualiza Article
```

**O que acontece:**
1. ETL coleta todas as `entities_local_ids` de todos os chunks
2. Cria/atualiza collection `Article` (se usar schema A2)
3. Atualiza `entities_all_ids` com todas as entidades únicas

```python
# Article consolidado
article_collection.data.insert(
    properties={
        "article_id": "abc-123-def",
        "url_final": "doc://artigos_empresas.pdf",
        "title": "artigos_empresas.pdf",
        "entities_all_ids": ["Q312", "Q2283", "Q199300", "Q95"],  # Todas as empresas
        "source_domain": "local",
        "published_at": "2025-01-15"
    }
)
```

**Resultado:**
- ✅ `Article` criado com todas as entidades consolidadas
- ✅ Relacionamento Article ↔ Passages estabelecido

---

## 📊 Resultado Final no Weaviate

### **Documento Original:**
```
VERBA_Document:
  - title: "artigos_empresas.pdf"
  - content: "[texto completo dos 3 artigos]"
```

### **Chunks (Passages) com ETL:** ⭐ ATUALIZADO
```
Chunk 1 (Apple):
  - text: "Apple lança novo iPhone..."
  - entity_mentions: [{"text": "Apple", "label": "ORG", "confidence": 0.95}]  ⭐ NOVO
  - entities_local_ids: ["Q312"]              ← Apple Inc (se gazetteer disponível)
  - section_title: "Artigo 1: Apple..."
  - section_entity_ids: ["Q312"]
  - etl_version: "entity_scope_intelligent_v2"  ⭐ NOVO

Chunk 3 (Microsoft):
  - text: "Microsoft anuncia parceria..."
  - entity_mentions: [{"text": "Microsoft", "label": "ORG", "confidence": 0.95}, {"text": "OpenAI", "label": "ORG", "confidence": 0.90}]  ⭐ NOVO
  - entities_local_ids: ["Q2283"]            ← Microsoft (se gazetteer disponível)
  - section_entity_ids: ["Q2283", "Q199300"]  ← Microsoft + OpenAI
  - etl_version: "entity_scope_intelligent_v2"  ⭐ NOVO

Chunk 5 (Google):
  - text: "Google desenvolve IA..."
  - entity_mentions: [{"text": "Google", "label": "ORG", "confidence": 0.95}]  ⭐ NOVO
  - entities_local_ids: ["Q95"]              ← Google (se gazetteer disponível)
  - section_entity_ids: ["Q95"]
  - etl_version: "entity_scope_intelligent_v2"  ⭐ NOVO
```

### **Article (se usar schema A2):**
```
Article:
  - article_id: "abc-123-def"
  - title: "artigos_empresas.pdf"
  - entities_all_ids: ["Q312", "Q2283", "Q199300", "Q95"]  ← Todas as empresas
```

---

## 🎯 Como Usar Depois

### **Busca por Entidade Específica:**

Use **Entity-Aware Retriever**:
```
Query: "inovação tecnológica"
+ Filter: entities_local_ids contains "Q312" (Apple)

Resultado:
- Retorna apenas chunks que mencionam Apple
- Evita contaminação com Microsoft/Google
```

### **Busca por Seção:**

```
Query: "parcerias"
+ Filter: section_entity_ids contains "Q2283" (Microsoft)

Resultado:
- Retorna apenas seção sobre Microsoft
```

### **Busca Híbrida:**

```
Query: "inteligência artificial"
+ Filter: entities_all_ids contains any of ["Q95", "Q2283"] (Google ou Microsoft)

Resultado:
- Chunks sobre Google ou Microsoft relacionados a IA
- Exclui Apple automaticamente
```

---

## ⏱️ Tempo Total Estimado (OTIMIZADO)

- **Upload + Leitura**: 2-5s
- **ETL Pré-Chunking**: 5-6s (otimizado: 71% menos entidades)
- **Chunking Entity-Aware**: 2-3s (otimizado: binary search, 10-15x mais rápido)
- **Embedding**: 5-15s
  - ⚠️ **NOTA:** `recursive_document_splitter` foi removido (evita expansão 93 → 2379 chunks)
- **Import Weaviate**: 2-5s
- **ETL Pós-Chunking (background)**: 10-30s
  - ⭐ **NOVO:** ETL inteligente multi-idioma (detecção automática PT/EN)
  - ⭐ **NOVO:** Collection correta sendo usada (não mais "Passage")
- **Total**: **26-64 segundos**

**Antes das otimizações**: 30s+ apenas no chunking  
**Depois das otimizações**: 2-3s no chunking  
**Ganho total**: **10-15x mais rápido** no chunking!

**Importante**: ETL pós-chunking executa em background, então você pode continuar usando o Verba enquanto processa!

---

## 💡 Pontos Importantes

### ✅ **Vantagens:**
1. **Automático**: Você só faz upload e importa
2. **Por Chunk**: Entidades extraídas contextualmente
3. **Normalizado**: Aliases mapeados para IDs canônicos
4. **Seções**: Detecção automática de estrutura
5. **Background**: Não bloqueia interface

### ⚠️ **Limitações:**
1. **SpaCy**: Requer modelo instalado (`pt_core_news_sm` ou `en_core_web_sm`)
   - ⭐ **NOVO:** Modelo é carregado automaticamente baseado no idioma detectado
2. **Gazetteer**: ⭐ **OPCIONAL** - ETL inteligente funciona sem gazetteer
   - Modo inteligente: extrai entidades diretamente (não requer gazetteer)
   - Modo legado: usa gazetteer se disponível para normalização
3. **Performance**: ETL adiciona 10-30s por documento (pós-chunking, em background)
4. **PDF Complexo**: Pode não separar artigos automaticamente (se forem contínuos)
5. **Tipos de Entidades**: ⭐ **ATUALIZADO** - Modo inteligente extrai TODAS as labels
   - Modo pré-chunking: apenas ORG + PERSON (otimização)
   - Modo pós-chunking: todas as labels (ORG, PERSON, LOC, GPE, MISC, etc.)

### 🚀 **Otimizações Implementadas:**
1. **Binary Search**: Filtragem O(n²) → O(n log n) (6.7x mais rápido)
2. **Deduplicação**: Remove entidades duplicadas por posição
3. **Filtro de Tipos**: Apenas ORG + PERSON (reduz 71% das entidades)
4. **Normalização**: PER (PT) → PERSON (EN) para compatibilidade
5. **Entity-Aware**: Chunking não corta entidades no meio (qualidade mantida)

---

## 🔧 Ajustes Possíveis

### **Se PDF tem múltiplos artigos bem separados:**

O Verba pode criar múltiplos documentos se houver quebras claras. Mas se tudo vem como um único documento:

**Opção 1**: Use o script `pdf_to_a2_json.py` para separar manualmente
**Opção 2**: Importe como está - ETL processa todos os chunks mesmo assim

### **Se alguma empresa não é detectada:**

**⭐ NOVO: Modo Inteligente (sem gazetteer):**
- ETL detecta entidades automaticamente via spaCy
- Não requer gazetteer manual
- Funciona out-of-the-box

**Modo Legado (com gazetteer):**
- Adicione ao `gazetteer.json` para normalização:
```json
{
  "entity_id": "Q999",
  "aliases": ["Nome da Empresa", "Nome Alternativo", "Sigla"]
}
```
- Gazetteer é opcional - ETL funciona sem ele

---

**Agora você entende exatamente o que acontece quando faz upload de um PDF com artigos sobre empresas!** 🎉

