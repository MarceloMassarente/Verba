# 🔍 Embedder: Import vs Query - Preciso Usar o Mesmo?

## ✅ **Resposta Direta**

**SIM, você precisa usar o mesmo embedder na query que foi usado no import!**

Cada embedder tem sua própria collection no Weaviate, e os chunks são armazenados na collection do embedder usado no import.

---

## 🔍 **Como Funciona**

### **1. Importação: Chunks são Armazenados na Collection do Embedder**

Quando você importa um documento:

```python
# goldenverba/components/managers.py (linha 731-735)

embedder = "SentenceTransformers"  # ou outro
collection_name = "VERBA_Embedding_SentenceTransformers"

# Chunks são inseridos nesta collection
embedder_collection = client.collections.get(collection_name)
```

**Cada embedder tem sua própria collection:**
- `SentenceTransformers` → `VERBA_Embedding_SentenceTransformers`
- `Ollama` → `VERBA_Embedding_Ollama`
- `OpenAI` → `VERBA_Embedding_OpenAI`
- etc.

### **2. Query: Busca na Collection do Embedder Selecionado**

Quando você faz uma query no chat:

```python
# goldenverba/verba_manager.py (linha 848-863)

async def retrieve_chunks(self, client, query: str, rag_config: dict, ...):
    # Pega embedder do RAG config (o que você selecionou no chat)
    embedder = rag_config["Embedder"].selected
    
    # Vectoriza a query com esse embedder
    vector = await self.embedder_manager.vectorize_query(embedder, query, rag_config)
    
    # Busca na collection desse embedder
    documents, context = await self.retriever_manager.retrieve(
        client,
        retriever,
        query,
        vector,
        rag_config,
        self.weaviate_manager,
        ...
    )
```

**A query busca na collection do embedder selecionado no chat.**

---

## ⚠️ **Problema: Embedder Diferente**

### **Cenário 1: Import com SentenceTransformers, Query com Ollama**

```
IMPORT:
  - Embedder: SentenceTransformers
  - Collection: VERBA_Embedding_SentenceTransformers
  - Chunks inseridos: ✅ 100 chunks

QUERY:
  - Embedder selecionado: Ollama
  - Collection buscada: VERBA_Embedding_Ollama
  - Resultado: ❌ 0 chunks (collection vazia!)
```

### **Cenário 2: Import com SentenceTransformers, Query com SentenceTransformers**

```
IMPORT:
  - Embedder: SentenceTransformers
  - Collection: VERBA_Embedding_SentenceTransformers
  - Chunks inseridos: ✅ 100 chunks

QUERY:
  - Embedder selecionado: SentenceTransformers
  - Collection buscada: VERBA_Embedding_SentenceTransformers
  - Resultado: ✅ 100 chunks encontrados!
```

---

## 🎯 **Solução: Usar o Mesmo Embedder**

### **Opção 1: Sempre Usar o Mesmo Embedder (Recomendado)**

1. **Import:** Use `SentenceTransformers` (ou outro)
2. **Query:** Use o mesmo `SentenceTransformers`

**Vantagens:**
- ✅ Simples e direto
- ✅ Garante que encontra todos os chunks
- ✅ Vetores são compatíveis (mesmo modelo)

### **Opção 2: Importar com Múltiplos Embedders**

Se você quiser flexibilidade:

1. **Import o mesmo documento com diferentes embedders:**
   - Import com `SentenceTransformers` → chunks em `VERBA_Embedding_SentenceTransformers`
   - Import com `Ollama` → chunks em `VERBA_Embedding_Ollama`
   - Import com `OpenAI` → chunks em `VERBA_Embedding_OpenAI`

2. **Query com qualquer embedder:**
   - Query com `SentenceTransformers` → encontra chunks do primeiro import
   - Query com `Ollama` → encontra chunks do segundo import
   - Query com `OpenAI` → encontra chunks do terceiro import

**Desvantagens:**
- ❌ Consome mais espaço (mesmos chunks duplicados)
- ❌ Mais tempo de importação
- ❌ Não é necessário na maioria dos casos

---

## 📊 **Como Verificar Qual Embedder Foi Usado**

### **1. Na UI do Verba:**

- **Settings** → **Embedder** → mostra qual está selecionado
- **Documents** → ver detalhes do documento (pode mostrar embedder usado)

### **2. No Weaviate:**

- Lista collections: `VERBA_Embedding_*`
- Collection com chunks = embedder usado no import

### **3. Nos Logs:**

```
[EMBEDDER] Starting vectorization: embedder=SentenceTransformers
[EMBEDDER] Generated 70 embeddings for document 1
```

---

## 🔧 **Como Trocar Embedder (se necessário)**

Se você importou com um embedder mas quer usar outro:

### **Opção A: Re-importar com Novo Embedder**

1. Delete o documento antigo
2. Import novamente com o novo embedder
3. Chunks serão salvos na collection do novo embedder

### **Opção B: Importar com Múltiplos Embedders**

1. Mantenha o documento original
2. Import novamente com o novo embedder (mesmo documento)
3. Agora você tem chunks em ambas as collections

---

## 📋 **Resumo**

| Situação | Resultado |
|----------|-----------|
| **Import com Embedder A** → **Query com Embedder A** | ✅ Funciona perfeitamente |
| **Import com Embedder A** → **Query com Embedder B** | ❌ Não encontra chunks (collection diferente) |
| **Import com Embedder A + B** → **Query com Embedder A ou B** | ✅ Funciona (mas chunks duplicados) |

---

## ✅ **Recomendação**

**Use sempre o mesmo embedder para import e query!**

- ✅ Simples
- ✅ Eficiente
- ✅ Garante compatibilidade
- ✅ Não duplica dados

**Exceção:** Se você tem razões específicas para usar diferentes embedders (ex: comparar qualidade de busca), importe o mesmo documento com múltiplos embedders.

---

## 💡 **Por Que Isso Acontece?**

Cada embedder gera vetores com características diferentes:
- **Dimensões diferentes:** `all-MiniLM-L6-v2` = 384d, `OpenAI text-embedding-ada-002` = 1536d
- **Espaços vetoriais diferentes:** modelos diferentes mapeiam palavras para vetores diferentes
- **Collections separadas:** Weaviate precisa de collections separadas para vetores de dimensões diferentes

**Não é possível fazer busca semântica entre vetores de embedders diferentes!**

