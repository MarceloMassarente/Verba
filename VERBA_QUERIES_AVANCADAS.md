# 🔍 Verba: Chat vs Queries Avançadas

## ❓ Resposta Rápida

**Não, o Verba NÃO só funciona via chat!** Ele tem várias formas de consulta:

1. ✅ **Chat** (interface conversacional)
2. ✅ **Busca de Documentos** (filtros, paginação)
3. ✅ **API REST** (queries programáticas)
4. ⚠️ **Queries Avançadas** (limitado - podemos expandir!)

---

## 🎯 O Que Já Existe

### **1. Chat (Interface Conversacional)**

**Como usar:**
- Abra o Verba → **Chat**
- Digite sua pergunta
- Recebe resposta gerada com contexto dos documentos

**Limitações:**
- ❌ Não permite filtros complexos diretamente
- ❌ Não permite where clauses customizados
- ❌ Não permite busca por entidades específicas (sem EntityAware)

---

### **2. Busca de Documentos (Documents Section)**

**Como usar:**
- Abra o Verba → **Documents**
- Use a busca para encontrar documentos
- Filtre por **Labels** (tags)

**O que permite:**
- ✅ Busca textual (BM25) por título/conteúdo
- ✅ Filtro por labels (tags)
- ✅ Paginação
- ✅ Ordenação

**Limitações:**
- ❌ Apenas busca em metadados de documentos (não em chunks)
- ❌ Não permite busca por entidades
- ❌ Não permite where clauses complexos

---

### **3. API REST**

#### **Endpoint: `/api/query`**
```python
POST /api/query
{
  "query": "inovação da Apple",
  "RAG": {...},  # Config do retriever
  "labels": [...],  # Filtro por labels
  "documentFilter": [...]  # Filtro por documentos específicos
}
```

**Permite:**
- ✅ Queries com retriever configurável
- ✅ Filtros por labels e documentos
- ✅ Com EntityAware Retriever: busca por entidades

#### **Endpoint: `/api/get_all_documents`**
```python
POST /api/get_all_documents
{
  "query": "inovação",  # Busca textual
  "labels": [...],  # Filtro por labels
  "page": 1,
  "pageSize": 20
}
```

**Permite:**
- ✅ Busca textual em documentos
- ✅ Filtro por labels
- ✅ Paginação

---

## 🚀 O Que Podemos Adicionar

### **Queries Avançadas com Where Clauses**

Podemos criar um endpoint para queries avançadas:

```python
POST /api/advanced_query
{
  "query": "inovação tecnológica",
  "where": {
    "property": "entities_local_ids",
    "operator": "ContainsAny",
    "value": ["Q312", "Q95"]  # Apple ou Google
  },
  "filters": [
    {
      "property": "section_entity_ids",
      "operator": "ContainsAny",
      "value": ["Q312"]
    },
    {
      "property": "section_scope_confidence",
      "operator": "GreaterOrEqual",
      "value": 0.7
    }
  ],
  "limit": 10,
  "embedder": "SentenceTransformers"
}
```

---

## 💡 Como Usar Queries Avançadas Atualmente

### **Opção 1: Via EntityAware Retriever (Recomendado)**

**No Chat:**
1. Escolha **EntityAware** como retriever nas Settings
2. Faça query mencionando entidade: "inovação da Apple"
3. O retriever aplica filtro automaticamente:
   ```python
   where: entities_local_ids contains "Q312"
   ```

**Via API:**
```python
import requests

response = requests.post("https://verba.up.railway.app/api/query", json={
    "query": "inovação da Apple",
    "RAG": {
        "Retriever": {
            "selected": "EntityAware",
            "components": {
                "EntityAware": {
                    "config": {
                        "Enable Entity Filter": {"value": True}
                    }
                }
            }
        },
        ...
    },
    "credentials": {...}
})
```

---

### **Opção 2: Filtros por Documentos/Labels**

**No Chat:**
- Use a interface de filtros (se disponível) para selecionar documentos específicos
- Isso já funciona via `documentFilter` na API

**Via API:**
```python
response = requests.post("https://verba.up.railway.app/api/query", json={
    "query": "inovação",
    "labels": ["tech", "startups"],  # Filtro por labels
    "documentFilter": [
        {"uuid": "doc-123"},  # Filtro por documentos específicos
        {"uuid": "doc-456"}
    ],
    "RAG": {...},
    "credentials": {...}
})
```

---

### **Opção 3: Busca Direta no Weaviate (Avançado)**

Se você tem acesso direto ao Weaviate:

```python
import weaviate

client = weaviate.connect_to_custom(
    http_host="weaviate.up.railway.app",
    http_port=8080,
    ...
)

# Query direta com where clause
results = client.collections.get("VERBA_Embedding_SentenceTransformers").query.bm25(
    query="inovação",
    limit=10,
    filters=Filter.by_property("entities_local_ids").contains_any(["Q312"])
)
```

---

## 🛠️ Implementação: Endpoint de Queries Avançadas

Podemos criar um novo endpoint que permite where clauses customizados:

```python
@app.post("/api/advanced_query")
async def advanced_query(payload: AdvancedQueryPayload):
    """
    Permite queries avançadas com where clauses customizados
    """
    # Constrói filtros customizados
    filters = build_where_clauses(payload.where_clauses)
    
    # Busca com filtros
    chunks = await weaviate_manager.query_chunks(
        client,
        query=payload.query,
        embedder=payload.embedder,
        filters=filters,
        limit=payload.limit
    )
    
    return {"chunks": chunks, "count": len(chunks)}
```

**Payload:**
```python
class AdvancedQueryPayload(BaseModel):
    query: str
    embedder: str
    where_clauses: List[WhereClause]  # Filtros customizados
    limit: int = 10
    credentials: Credentials

class WhereClause(BaseModel):
    property: str  # "entities_local_ids", "section_entity_ids", etc.
    operator: str  # "ContainsAny", "Equal", "GreaterOrEqual", etc.
    value: Any  # ["Q312"], 0.7, etc.
```

---

## 📊 Comparação: Chat vs Queries Avançadas

| Feature | Chat | Documents Search | API `/api/query` | API Avançada (proposta) |
|---------|------|------------------|-----------------|------------------------|
| **Busca Textual** | ✅ | ✅ | ✅ | ✅ |
| **Filtro por Labels** | ⚠️ | ✅ | ✅ | ✅ |
| **Filtro por Documentos** | ⚠️ | ❌ | ✅ | ✅ |
| **Where Clauses** | ❌ | ❌ | ⚠️ (via retriever) | ✅ |
| **Busca por Entidades** | ⚠️ (EntityAware) | ❌ | ⚠️ (EntityAware) | ✅ |
| **Filtros Complexos** | ❌ | ❌ | ❌ | ✅ |
| **Interface Visual** | ✅ | ✅ | ❌ | ❌ |

---

## 🎯 Recomendação de Uso

### **Para Usuários Finais:**
- Use **Chat** para perguntas simples
- Use **Documents** para buscar/filtrar documentos
- Use **EntityAware Retriever** no chat para busca por entidades

### **Para Desenvolvedores/APIs:**
- Use **`/api/query`** com EntityAware Retriever
- Use **`/api/get_all_documents`** para busca de documentos
- Para queries muito específicas: acesse Weaviate diretamente (ou crie endpoint customizado)

---

## 🚀 Próximos Passos

Quer que eu implemente:

1. **Endpoint `/api/advanced_query`** com where clauses customizados?
2. **Interface visual** para construir queries avançadas?
3. **Builder de filtros** na UI (similar ao EntityAware, mas mais flexível)?

**Posso criar qualquer um desses!** Qual você prefere? 🛠️

