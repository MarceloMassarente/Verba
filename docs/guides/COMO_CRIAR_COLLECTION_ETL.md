# 🔧 Como Criar Collection do Zero com ETL

## 📋 Resumo

Este guia mostra como criar uma collection do Weaviate do zero com todas as propriedades de ETL, limpar dados antigos se necessário, e testar o processo completo.

## ⚠️ Limitação do Weaviate v4

**Importante:** Weaviate v4 **não permite adicionar propriedades depois** que a collection foi criada. Portanto, é necessário criar a collection com todas as propriedades desde o início.

## 🚀 Processo Completo

### 1. Limpar Collections Antigas (Opcional)

Se você quer começar do zero:

```python
import weaviate

client = weaviate.connect_to_custom(...)

# Deleta collection antiga
if await client.collections.exists("VERBA_Embedding_all_MiniLM_L6_v2"):
    client.collections.delete("VERBA_Embedding_all_MiniLM_L6_v2")
```

### 2. Criar Collection com Propriedades de ETL

```python
from weaviate.classes.config import Configure, Property, DataType
from verba_extensions.integration.schema_updater import get_etl_properties

# Propriedades padrão do Verba
verba_properties = [
    Property(name="chunk_id", data_type=DataType.NUMBER),
    Property(name="end_i", data_type=DataType.NUMBER),
    Property(name="chunk_date", data_type=DataType.TEXT),
    Property(name="meta", data_type=DataType.TEXT),
    Property(name="content", data_type=DataType.TEXT),
    Property(name="uuid", data_type=DataType.TEXT),
    Property(name="doc_uuid", data_type=DataType.UUID),
    Property(name="content_without_overlap", data_type=DataType.TEXT),
    Property(name="pca", data_type=DataType.NUMBER_ARRAY),
    Property(name="labels", data_type=DataType.TEXT_ARRAY),
    Property(name="title", data_type=DataType.TEXT),
    Property(name="start_i", data_type=DataType.NUMBER),
    Property(name="chunk_lang", data_type=DataType.TEXT),
]

# Propriedades de ETL
etl_properties = get_etl_properties()

# Todas as propriedades
all_properties = verba_properties + etl_properties

# Cria collection
collection = client.collections.create(
    name="VERBA_Embedding_all_MiniLM_L6_v2",
    vectorizer_config=Configure.Vectorizer.sentence_transformers(
        model="all-MiniLM-L6-v2",
        vectorize_collection_name=False
    ),
    properties=all_properties,
)
```

### 3. Propriedades de ETL Adicionadas

As seguintes propriedades serão adicionadas:

```python
# ETL pré-chunking
entities_local_ids: TEXT_ARRAY  # Entity IDs encontradas no chunk

# ETL pós-chunking
section_title: TEXT  # Título da seção
section_entity_ids: TEXT_ARRAY  # Entity IDs da seção
section_scope_confidence: NUMBER  # Confiança (0.0-1.0)
primary_entity_id: TEXT  # Entity ID primária
entity_focus_score: NUMBER  # Score de foco (0.0-1.0)
etl_version: TEXT  # Versão do ETL
```

### 4. Importar Documentos

Após criar a collection, importe documentos normalmente usando o Verba. O ETL será executado automaticamente e preencherá as propriedades de ETL.

### 5. Verificar Resultados

```python
from weaviate.classes.query import Filter

# Busca chunks com ETL
chunks = collection.query.fetch_objects(
    filters=Filter.by_property("doc_uuid").equal(doc_uuid),
    limit=10
)

# Verifica se têm metadados de ETL
for chunk in chunks.objects:
    props = chunk.properties
    if props.get("entities_local_ids"):
        print(f"Chunk {props['chunk_id']} tem {len(props['entities_local_ids'])} entity IDs")
```

### 6. Testar Queries por Entidades

```python
# Query por entity_id
results = collection.query.fetch_objects(
    filters=Filter.by_property("entities_local_ids").contains_any(["Q312"]),
    limit=5
)

print(f"Encontrados {len(results.objects)} chunks com entity_id Q312")
```

## 📝 Script Completo

Veja `scripts/create_collection_etl_from_scratch.py` para um exemplo completo que:
- Conecta ao Weaviate
- Limpa collections antigas
- Cria collection com propriedades de ETL
- Importa PDF
- Executa ETL
- Verifica resultados
- Testa queries

## 🔍 Troubleshooting

### Erro: "Collection already exists"
- Delete a collection antiga primeiro
- Ou use um nome diferente

### Erro: "Property already exists"
- Isso não deve acontecer se você criar a collection do zero
- Verifique se a collection foi realmente deletada

### ETL não preenche metadados
- Verifique se `enable_etl=True` no documento
- Verifique logs do ETL
- Confirme que o hook está sendo executado

## ✅ Checklist

- [ ] Collection criada com propriedades de ETL
- [ ] Documentos importados com `enable_etl=True`
- [ ] ETL pré-chunking executado (visto nos logs)
- [ ] ETL pós-chunking executado (visto nos logs)
- [ ] Chunks têm `entities_local_ids` preenchidos
- [ ] Queries por entidades funcionam

## 📚 Referências

- `verba_extensions/integration/schema_updater.py` - Funções para gerenciar schema
- `scripts/create_collection_etl_from_scratch.py` - Script completo de exemplo
- `COMO_ADICIONAR_CAMPOS_ETL_SCHEMA.md` - Guia de migração


