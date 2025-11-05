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

### **FASE 2: Chunking** ⏱️ ~1-3s

```
Documento Completo → Chunker → Múltiplos Chunks
```

**O que acontece:**
1. Verba aplica o **chunker** escolhido (ex: SentenceChunker)
2. Divide o texto em chunks de ~200-500 palavras cada

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

### **FASE 3: Embedding (Vectorização)** ⏱️ ~5-15s

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

### **FASE 4: Import no Weaviate** ⏱️ ~2-5s

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

### **FASE 5: Hook Detecta Import** ⏱️ ~0.1s

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

### **FASE 6: ETL Executa por Chunk** ⏱️ ~10-30s (background)

```
Cada Chunk → ETL A2 → Entidades + Seções → Atualiza Weaviate
```

**O que acontece para CADA chunk:**

#### **6.1. Extração de Entidades via SpaCy**

Para o **Chunk 1**: `"Apple lança novo iPhone. A empresa americana anunciou..."`

```python
nlp = spacy.load("pt_core_news_sm")
doc = nlp("Apple lança novo iPhone. A empresa americana anunciou...")

# Entidades encontradas:
entidades_encontradas = [
    {"text": "Apple", "label": "ORG"},      # Organização
    {"text": "iPhone", "label": "MISC"},    # Produto
    {"text": "americana", "label": "GPE"}   # Localização
]
```

**Resultado:**
- ✅ Lista de entidades por chunk (texto + label)

---

#### **6.2. Normalização via Gazetteer**

Para o **Chunk 1** com entidade `"Apple"`:

```python
# Gazetteer mapeia aliases para entity_ids
gazetteer = {
    "Q312": ["Apple", "Apple Inc", "Apple Computer"],
    "Q2283": ["Microsoft", "MSFT", "Microsoft Corporation"],
    "Q95": ["Google", "Google LLC", "Alphabet"]
}

# Busca "Apple" no gazetteer
entity_ids = ["Q312"]  # Apple Inc
```

**Resultado:**
- ✅ Entidades normalizadas para `entity_ids` canônicos
- ✅ Aliases mapeados corretamente

---

#### **6.3. Detecção de Seções**

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

#### **6.4. Atualização no Weaviate**

Para **cada chunk**, atualiza metadados:

```python
# Chunk 1
passage_collection.data.update(
    uuid="chunk-1",
    properties={
        "entities_local_ids": ["Q312"],           # Entidades neste chunk
        "section_title": "Artigo 1: Apple...",
        "section_first_para": "A empresa...",
        "section_entity_ids": ["Q312"],          # Entidades da seção
        "section_scope_confidence": 0.85
    }
)

# Chunk 3 (sobre Microsoft)
passage_collection.data.update(
    uuid="chunk-3",
    properties={
        "entities_local_ids": ["Q2283"],          # Microsoft
        "section_title": "Artigo 2: Microsoft...",
        "section_first_para": "Microsoft anuncia...",
        "section_entity_ids": ["Q2283", "Q199300"]  # Microsoft + OpenAI
    }
)
```

**Resultado:**
- ✅ Cada chunk tem metadados de entidades
- ✅ Metadados de seção preenchidos

---

### **FASE 7: Consolidação no Article** ⏱️ ~1-2s

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

### **Chunks (Passages) com ETL:**
```
Chunk 1 (Apple):
  - text: "Apple lança novo iPhone..."
  - entities_local_ids: ["Q312"]              ← Apple Inc
  - section_title: "Artigo 1: Apple..."
  - section_entity_ids: ["Q312"]

Chunk 3 (Microsoft):
  - text: "Microsoft anuncia parceria..."
  - entities_local_ids: ["Q2283"]            ← Microsoft
  - section_entity_ids: ["Q2283", "Q199300"]  ← Microsoft + OpenAI

Chunk 5 (Google):
  - text: "Google desenvolve IA..."
  - entities_local_ids: ["Q95"]              ← Google
  - section_entity_ids: ["Q95"]
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

## ⏱️ Tempo Total Estimado

- **Upload + Leitura**: 2-5s
- **Chunking**: 1-3s
- **Embedding**: 5-15s
- **Import Weaviate**: 2-5s
- **ETL (background)**: 10-30s
- **Total**: **20-58 segundos**

**Importante**: ETL executa em background, então você pode continuar usando o Verba enquanto processa!

---

## 💡 Pontos Importantes

### ✅ **Vantagens:**
1. **Automático**: Você só faz upload e importa
2. **Por Chunk**: Entidades extraídas contextualmente
3. **Normalizado**: Aliases mapeados para IDs canônicos
4. **Seções**: Detecção automática de estrutura
5. **Background**: Não bloqueia interface

### ⚠️ **Limitações:**
1. **SpaCy**: Requer modelo instalado (`pt_core_news_sm`)
2. **Gazetteer**: Entidades precisam estar no arquivo JSON
3. **Performance**: ETL adiciona 10-30s por documento
4. **PDF Complexo**: Pode não separar artigos automaticamente (se forem contínuos)

---

## 🔧 Ajustes Possíveis

### **Se PDF tem múltiplos artigos bem separados:**

O Verba pode criar múltiplos documentos se houver quebras claras. Mas se tudo vem como um único documento:

**Opção 1**: Use o script `pdf_to_a2_json.py` para separar manualmente
**Opção 2**: Importe como está - ETL processa todos os chunks mesmo assim

### **Se alguma empresa não é detectada:**

Adicione ao `gazetteer.json`:
```json
{
  "entity_id": "Q999",
  "aliases": ["Nome da Empresa", "Nome Alternativo", "Sigla"]
}
```

---

**Agora você entende exatamente o que acontece quando faz upload de um PDF com artigos sobre empresas!** 🎉

