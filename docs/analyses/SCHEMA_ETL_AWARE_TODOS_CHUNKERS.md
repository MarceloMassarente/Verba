# 📋 Schema ETL-Aware: Todos os Chunkers Usam o Mesmo Schema

## ✅ **Resposta Direta**

**SIM, TODOS os chunkers usam o mesmo schema ETL-aware!**

O schema não depende do chunker, mas sim da **collection de embedding** (baseada no embedder).

---

## 🔍 **Como Funciona**

### **1. Schema é Criado por Collection (não por Chunker)**

```python
# verba_extensions/integration/schema_updater.py (linha 209)

if "VERBA_Embedding" in collection_name:
    # Cria collection com schema ETL-aware
    # Isso acontece para QUALQUER embedder
```

**Collection é criada baseada no embedder:**
- `VERBA_Embedding_all_MiniLM_L6_v2`
- `VERBA_Embedding_text_embedding_ada_002`
- `VERBA_Embedding_SentenceTransformers`
- etc.

**NÃO baseada no chunker:**
- TokenChunker
- SentenceChunker
- RecursiveChunker
- **SectionAwareChunker** (nosso)
- SemanticChunker
- etc.

### **2. Todos os Chunkers Usam a Mesma Collection**

Quando você importa um documento:
1. Escolhe um **Reader** (ex: Universal A2)
2. Escolhe um **Chunker** (ex: Section-Aware, Token, Sentence, etc.)
3. Escolhe um **Embedder** (ex: SentenceTransformers)
4. Chunks são inseridos na collection `VERBA_Embedding_SentenceTransformers`

**Todos os chunkers** vão inserir chunks na **mesma collection** do embedder escolhido.

### **3. Schema ETL-Aware é Universal**

O schema tem **20 propriedades**:
- **13 padrão Verba:** `content`, `chunk_id`, `doc_uuid`, `title`, etc.
- **7 ETL opcionais:** `entities_local_ids`, `section_title`, etc.

**Propriedades ETL são opcionais:**
- ✅ Chunks normais (Token, Sentence, etc.): deixam propriedades ETL vazias
- ✅ Chunks ETL-aware (Section-Aware com ETL): preenchem propriedades ETL

---

## 📊 **Exemplos Práticos**

### **Exemplo 1: TokenChunker sem ETL**

```python
# Chunker: TokenChunker
# ETL: desabilitado
# Embedder: SentenceTransformers

# Collection: VERBA_Embedding_SentenceTransformers
# Schema: ETL-aware (20 propriedades)
# Chunk inserido:
{
    "content": "Texto do chunk...",
    "chunk_id": 0,
    "doc_uuid": "...",
    # Propriedades ETL ficam vazias:
    "entities_local_ids": [],
    "section_title": "",
    "section_entity_ids": [],
    "section_scope_confidence": 0.0,
    "primary_entity_id": "",
    "entity_focus_score": 0.0,
    "etl_version": "",
}
```

### **Exemplo 2: SectionAwareChunker com ETL**

```python
# Chunker: SectionAwareChunker
# ETL: habilitado
# Embedder: SentenceTransformers

# Collection: VERBA_Embedding_SentenceTransformers (MESMA!)
# Schema: ETL-aware (20 propriedades) (MESMO!)
# Chunk inserido:
{
    "content": "Texto do chunk...",
    "chunk_id": 0,
    "doc_uuid": "...",
    # Propriedades ETL preenchidas:
    "entities_local_ids": ["ent:org:google", "ent:person:john"],
    "section_title": "Introdução",
    "section_entity_ids": ["ent:org:google"],
    "section_scope_confidence": 0.85,
    "primary_entity_id": "ent:org:google",
    "entity_focus_score": 0.92,
    "etl_version": "1.0",
}
```

### **Exemplo 3: RecursiveChunker sem ETL**

```python
# Chunker: RecursiveChunker
# ETL: desabilitado
# Embedder: SentenceTransformers

# Collection: VERBA_Embedding_SentenceTransformers (MESMA!)
# Schema: ETL-aware (20 propriedades) (MESMO!)
# Chunk inserido: (igual ao Exemplo 1 - propriedades ETL vazias)
```

---

## 🎯 **Por Que Isso Funciona**

### **1. Schema Universal (One Schema for All)**

O schema ETL-aware foi projetado para ser **universal**:
- ✅ Serve para chunks normais (propriedades ETL vazias)
- ✅ Serve para chunks ETL-aware (propriedades ETL preenchidas)

### **2. Propriedades ETL São Opcionais**

```python
# verba_extensions/integration/schema_updater.py

# Propriedades ETL são opcionais
Property(
    name="entities_local_ids",
    data_type=DataType.TEXT_ARRAY,
    description="Entity IDs localizadas no chunk (ETL pré-chunking) - opcional",
),
```

Chunks podem deixar essas propriedades vazias sem problemas.

### **3. Collection é Criada Uma Vez**

```python
# goldenverba/components/managers.py (linha 647-651)

async def verify_embedding_collection(self, client, embedder):
    if embedder not in self.embedding_table:
        normalized = self._normalize_embedder_name(embedder)
        self.embedding_table[embedder] = "VERBA_Embedding_" + normalized
        return await self.verify_collection(client, self.embedding_table[embedder])
```

**Collection é criada baseada no embedder**, não no chunker.

**Todos os chunkers** que usam o mesmo embedder vão usar a **mesma collection** com o **mesmo schema**.

---

## 📋 **Resumo**

| Aspecto | Detalhes |
|---------|----------|
| **Schema** | ETL-aware (20 propriedades) |
| **Aplicado a** | Todas as collections `VERBA_Embedding_*` |
| **Depende de** | Embedder escolhido (não chunker) |
| **Chunkers que usam** | TODOS (Token, Sentence, Recursive, Section-Aware, etc.) |
| **Propriedades ETL** | Opcionais (vazias para chunks normais, preenchidas para ETL-aware) |

---

## ✅ **Conclusão**

**SIM, todos os chunkers usam o mesmo schema ETL-aware!**

- ✅ TokenChunker → usa schema ETL-aware (propriedades ETL vazias)
- ✅ SentenceChunker → usa schema ETL-aware (propriedades ETL vazias)
- ✅ RecursiveChunker → usa schema ETL-aware (propriedades ETL vazias)
- ✅ **SectionAwareChunker** → usa schema ETL-aware (propriedades ETL preenchidas)

**O schema é universal e serve para ambos os casos!** 🎉

