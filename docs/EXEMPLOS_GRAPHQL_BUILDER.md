# 📚 Exemplos: GraphQL Builder

**Data**: Janeiro 2025  
**Objetivo**: Exemplos práticos de como usar o GraphQL Builder

---

## 🎯 Casos de Uso

### **1. Estatísticas de Entidades**

**Query**: "Quantos chunks têm Apple vs Microsoft?"

```python
from verba_extensions.utils.graphql_builder import GraphQLBuilder

builder = GraphQLBuilder()

# Construir query
query = builder.build_entity_aggregation(
    collection_name="VERBA_Embedding_all_MiniLM_L6_v2",
    filters={"entities_local_ids": ["Q312", "Q2283"]}  # Apple, Microsoft
)

# Executar
results = await builder.execute(client, query)

# Parsear resultados
stats = builder.parse_aggregation_results(results)

# Resultado:
# {
#   "type": "simple",
#   "data": {
#     "entities_local_ids": {
#       "count": 150,
#       "topOccurrences": [
#         {"occurs": 85, "value": "Q312"},  # Apple
#         {"occurs": 65, "value": "Q2283"}  # Microsoft
#       ]
#     }
#   }
# }
```

**Via API**:
```python
POST /api/query/aggregate
{
  "query": "quantos chunks têm Apple vs Microsoft",
  "RAG": {
    "Embedder": {"selected": "SentenceTransformers"},
    "Aggregation": {
      "type": "entity_stats",
      "filters": {"entities_local_ids": ["Q312", "Q2283"]}
    }
  },
  "credentials": {...}
}
```

---

### **2. Estatísticas por Documento**

**Query**: "Quais documentos têm mais menções de entidades?"

```python
# Construir query
query = builder.build_document_stats_query(
    collection_name="VERBA_Embedding_all_MiniLM_L6_v2"
)

# Executar
results = await builder.execute(client, query)

# Parsear resultados
stats = builder.parse_aggregation_results(results)

# Resultado:
# {
#   "type": "grouped",
#   "groups": [
#     {
#       "count": 45,
#       "entities_local_ids": {
#         "count": 120,
#         "topOccurrences": [
#           {"occurs": 60, "value": "Q312"},  # Apple
#           {"occurs": 40, "value": "Q2283"}  # Microsoft
#         ]
#       },
#       "chunk_date": {
#         "date": {"minimum": "2024-01-01", "maximum": "2024-12-31"}
#       }
#     },
#     ...
#   ],
#   "total_groups": 10
# }
```

**Via API**:
```python
POST /api/query/aggregate
{
  "query": "quais documentos têm mais menções de entidades",
  "RAG": {
    "Embedder": {"selected": "SentenceTransformers"},
    "Aggregation": {
      "type": "document_stats"
    }
  },
  "credentials": {...}
}
```

---

### **3. Agregação com GroupBy**

**Query**: "Agrupar entidades por documento"

```python
# Construir query com groupBy
query = builder.build_entity_aggregation(
    collection_name="VERBA_Embedding_all_MiniLM_L6_v2",
    group_by=["doc_uuid"]
)

# Executar
results = await builder.execute(client, query)

# Parsear resultados
stats = builder.parse_aggregation_results(results)

# Resultado:
# {
#   "type": "grouped",
#   "groups": [
#     {
#       "count": 20,
#       "entities_local_ids": {
#         "count": 35,
#         "topOccurrences": [
#           {"occurs": 20, "value": "Q312"},  # Apple
#           {"occurs": 15, "value": "Q2283"}  # Microsoft
#         ]
#       }
#     },
#     ...
#   ]
# }
```

**Via API**:
```python
POST /api/query/aggregate
{
  "query": "agrupar entidades por documento",
  "RAG": {
    "Embedder": {"selected": "SentenceTransformers"},
    "Aggregation": {
      "type": "entity_stats",
      "group_by": ["doc_uuid"]
    }
  },
  "credentials": {...}
}
```

---

### **4. Query Multi-Collection**

**Query**: "Buscar documentos e seus chunks relacionados"

```python
# Construir query multi-collection
query = builder.build_multi_collection_query([
    {
        "alias": "documents",
        "collection": "VERBA_DOCUMENTS",
        "limit": 10,
        "fields": ["title", "uuid"]
    },
    {
        "alias": "chunks",
        "collection": "VERBA_Embedding_all_MiniLM_L6_v2",
        "limit": 50,
        "filters": {"doc_uuid": ["doc-1", "doc-2"]},
        "fields": ["content", "entities_local_ids"]
    }
])

# Executar
results = await builder.execute(client, query)

# Resultado:
# {
#   "data": {
#     "documents": {
#       "Get": {
#         "VERBA_DOCUMENTS": [
#           {"title": "Documento 1", "uuid": "doc-1"},
#           ...
#         ]
#       }
#     },
#     "chunks": {
#       "Get": {
#         "VERBA_Embedding_all_MiniLM_L6_v2": [
#           {"content": "...", "entities_local_ids": ["Q312"]},
#           ...
#         ]
#       }
#     }
#   }
# }
```

---

### **5. Filtros Complexos**

**Query**: "Chunks que têm (Apple OU Microsoft) E são de 2024 E NÃO têm Google"

```python
# Construir query com filtros complexos
filter_logic = {
    "operator": "And",
    "operands": [
        {
            "operator": "Or",
            "operands": [
                {"path": ["entities_local_ids"], "operator": "ContainsAny", "valueText": ["Q312"]},
                {"path": ["entities_local_ids"], "operator": "ContainsAny", "valueText": ["Q2283"]}
            ]
        },
        {"path": ["chunk_date"], "operator": "GreaterThanEqual", "valueDate": "2024-01-01T00:00:00Z"},
        {"path": ["chunk_date"], "operator": "LessThanEqual", "valueDate": "2024-12-31T23:59:59Z"},
        {
            "operator": "Not",
            "operands": [
                {"path": ["entities_local_ids"], "operator": "ContainsAny", "valueText": ["Q95"]}
            ]
        }
    ]
}

query = builder.build_complex_filter_query(
    collection_name="VERBA_Embedding_all_MiniLM_L6_v2",
    filter_logic=filter_logic,
    limit=50,
    fields=["content", "entities_local_ids", "chunk_date"]
)

# Executar
results = await builder.execute(client, query)
```

---

## 🔧 Integração com QueryBuilderPlugin

O `QueryBuilderPlugin` agora detecta automaticamente se a query precisa de agregação:

```python
from verba_extensions.plugins.query_builder import QueryBuilderPlugin

builder = QueryBuilderPlugin()

# Query normal (usa API Python)
query_plan = await builder.build_query(
    user_query="inovação da Apple",
    client=client,
    collection_name="VERBA_Embedding_all_MiniLM_L6_v2"
)
# Retorna: query plan normal (sem agregação)

# Query com agregação (usa GraphQL)
query_info = await builder.build_aggregation_query(
    aggregation_type="entity_stats",
    client=client,
    collection_name="VERBA_Embedding_all_MiniLM_L6_v2",
    filters={"entities_local_ids": ["Q312"]}
)
# Retorna: query GraphQL + métodos para executar e parsear
```

---

## 📊 Dashboard de Estatísticas (Exemplo Completo)

```python
from verba_extensions.utils.graphql_builder import GraphQLBuilder

async def get_dashboard_stats(client, collection_name: str):
    """Retorna estatísticas completas para dashboard"""
    builder = GraphQLBuilder()
    
    # 1. Estatísticas de entidades
    entity_query = builder.build_entity_aggregation(
        collection_name=collection_name,
        top_occurrences_limit=20
    )
    entity_results = await builder.execute(client, entity_query)
    entity_stats = builder.parse_aggregation_results(entity_results)
    
    # 2. Estatísticas por documento
    doc_query = builder.build_document_stats_query(
        collection_name=collection_name
    )
    doc_results = await builder.execute(client, doc_query)
    doc_stats = builder.parse_aggregation_results(doc_results)
    
    return {
        "entity_stats": entity_stats,
        "document_stats": doc_stats,
        "timestamp": time.time()
    }
```

---

## ⚠️ Limitações

1. **GraphQL Builder é para agregações complexas**
   - Para queries normais de busca, use API Python (type-safe)

2. **Validação de schema**
   - GraphQL não valida schema em tempo de desenvolvimento
   - Erros só aparecem em runtime

3. **Manutenibilidade**
   - Queries GraphQL são strings (difícil de manter)
   - Prefira API Python quando possível

---

## ✅ Recomendação de Uso

**Use GraphQL Builder para:**
- ✅ Agregações complexas (estatísticas, contagens)
- ✅ Queries multi-collection
- ✅ Filtros extremamente complexos

**Use API Python para:**
- ✅ Queries normais de busca
- ✅ Hybrid search
- ✅ Filtros básicos/médios

---

**Última atualização**: Janeiro 2025  
**Versão**: 1.0

