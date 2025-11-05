# 🏗️ Hierarquia de Entidades e Filtros em Dois Níveis

## 📊 Estrutura Atual

### **Hierarquia:**
```
VERBA_DOCUMENTS (Documento)
  └── VERBA_Embedding_* (Chunks)
      ├── Chunk 1: entities_local_ids = ["Q312"] (Apple)
      ├── Chunk 2: entities_local_ids = ["Q312", "Q2283"] (Apple + Microsoft)
      ├── Chunk 3: entities_local_ids = ["Q2283"] (Microsoft)
      └── Chunk 4: entities_local_ids = ["Q95"] (Google)
```

### **Problema Atual:**
- ❌ `VERBA_DOCUMENTS` **não armazena entidades** (apenas metadados básicos)
- ✅ Chunks têm `entities_local_ids` e `section_entity_ids`
- ❌ Não há forma direta de filtrar "documentos que contêm Apple"

---

## ✅ Solução: Filtros em Dois Níveis

### **Estratégia:**

1. **Nível 1: Filtrar Documentos**
   - Buscar todos os `doc_uuid` que têm chunks com entidade desejada (ex: Apple)
   - Usar filtro: `entities_local_ids contains "Q312"` na collection de chunks
   - Extrair `doc_uuid` únicos

2. **Nível 2: Filtrar Chunks**
   - Dentro dos documentos filtrados, buscar chunks com outra entidade (ex: Microsoft)
   - Usar filtro: `doc_uuid in [lista_de_doc_uuids] AND entities_local_ids contains "Q2283"`

---

## 🔧 Implementação

### **1. Função Helper: Obter Documentos por Entidade**

```python
async def get_documents_by_entity(
    client,
    collection_name: str,
    entity_id: str,
    embedder: str
) -> List[str]:
    """
    Retorna lista de doc_uuid de documentos que contêm a entidade especificada.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection de embedding
        entity_id: Entity ID (ex: "Q312" para Apple)
        embedder: Nome do embedder
        
    Returns:
        Lista de doc_uuid únicos
    """
    from verba_extensions.compatibility.weaviate_imports import Filter
    
    collection = client.collections.get(collection_name)
    
    # Buscar chunks com a entidade
    results = await collection.query.fetch_objects(
        filters=Filter.by_property("entities_local_ids").contains_any([entity_id]),
        limit=1000,  # Ajustar conforme necessário
        return_properties=["doc_uuid"]
    )
    
    # Extrair doc_uuid únicos
    doc_uuids = list(set(str(obj.properties["doc_uuid"]) for obj in results.objects))
    
    return doc_uuids
```

### **2. Filtro em Dois Níveis no EntityAwareRetriever**

```python
# Nível 1: Filtrar documentos por entidade primária
if document_level_entity_filter:
    primary_doc_uuids = await get_documents_by_entity(
        client, collection_name, primary_entity_id, embedder
    )
    
    # Nível 2: Filtrar chunks dentro desses documentos
    if primary_doc_uuids:
        # Combinar filtro de documento com filtro de chunk
        chunk_entity_filter = Filter.by_property("entities_local_ids").contains_any([secondary_entity_id])
        doc_filter = Filter.by_property("doc_uuid").contains_any(primary_doc_uuids)
        
        combined_filter = Filter.all_of([chunk_entity_filter, doc_filter])
    else:
        # Nenhum documento encontrado
        return []
else:
    # Filtro normal (apenas chunks)
    combined_filter = Filter.by_property("entities_local_ids").contains_any([entity_id])
```

---

## 📋 Exemplo de Uso

### **Cenário:**
Documento fala sobre Apple, Microsoft e Meta. Queremos:
1. Garantir que o documento fala sobre Apple
2. Depois buscar chunks que falam sobre Microsoft

### **Query:**
```python
# 1. Obter documentos que contêm Apple
doc_uuids_with_apple = await get_documents_by_entity(
    client,
    "VERBA_Embedding_all_MiniLM_L6_v2",
    "Q312",  # Apple
    "all-MiniLM-L6-v2"
)

# 2. Buscar chunks dentro desses documentos que falam sobre Microsoft
from verba_extensions.compatibility.weaviate_imports import Filter

collection = client.collections.get("VERBA_Embedding_all_MiniLM_L6_v2")

# Filtro combinado
chunk_filter = Filter.by_property("entities_local_ids").contains_any(["Q2283"])  # Microsoft
doc_filter = Filter.by_property("doc_uuid").contains_any(doc_uuids_with_apple)

combined_filter = Filter.all_of([chunk_filter, doc_filter])

# Buscar chunks
results = await collection.query.fetch_objects(
    filters=combined_filter,
    limit=10,
    return_properties=["content", "doc_uuid", "entities_local_ids"]
)
```

---

## 🎯 Extensão do QueryBuilder

O `QueryBuilder` pode ser estendido para suportar filtros hierárquicos:

```json
{
    "semantic_query": "...",
    "filters": {
        "document_level": {
            "entities": ["Q312"],  // Filtrar documentos com Apple
            "operation": "must_contain"  // Documento deve conter
        },
        "chunk_level": {
            "entities": ["Q2283"],  // Filtrar chunks com Microsoft
            "operation": "must_contain"
        }
    },
    "explanation": "Busca documentos que falam sobre Apple, depois chunks sobre Microsoft"
}
```

---

## ✅ Benefícios

1. **Hierarquia Clara:**
   - Documento → Chunks
   - Filtros em dois níveis

2. **Precisão:**
   - Garante que documento menciona entidade principal
   - Depois filtra chunks específicos

3. **Flexibilidade:**
   - Pode combinar múltiplas entidades
   - Pode usar diferentes operações (must_contain, must_not_contain, etc.)

---

## 🚀 Próximos Passos

1. **Adicionar campo `entities_all_ids` ao VERBA_DOCUMENTS** (opcional)
   - Consolidar todas as entidades do documento
   - Facilitar filtro direto em documentos

2. **Implementar função helper** `get_documents_by_entity`

3. **Estender QueryBuilder** para suportar filtros hierárquicos

4. **Adicionar configuração no EntityAwareRetriever** para filtros em dois níveis

---

**Última atualização:** 2025-01-XX  
**Versão:** 1.0

