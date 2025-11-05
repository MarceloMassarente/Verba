# 🔍 Como o Verba Detecta e Usa Schema com Propriedades de ETL

## 📋 Resumo

O Verba **não cria automaticamente** collections com propriedades de ETL. O schema precisa ser criado **antes** de importar documentos. Este documento explica como funciona e como garantir que o schema ETL seja usado.

## 🔄 Fluxo Atual

### 1. Inicialização (startup.py)

Quando o Verba inicia, o `verba_extensions/startup.py` aplica patches:

```python
# Aplica patch de schema ETL
from verba_extensions.integration.schema_updater import patch_weaviate_manager_verify_collection
patch_weaviate_manager_verify_collection()
```

### 2. Patch de Verificação (schema_updater.py)

O `patch_weaviate_manager_verify_collection()` faz:

```python
async def patched_verify_collection(self, client, collection_name: str):
    # Se collection já existe, verifica se tem propriedades de ETL
    if await client.collections.exists(collection_name):
        has_etl = await check_collection_has_etl_properties(client, collection_name)
        if has_etl:
            msg.info(f"ℹ️  Collection {collection_name} já tem propriedades de ETL")
            return True
        else:
            msg.warn(f"⚠️  Collection {collection_name} existe mas não tem propriedades de ETL")
            # ⚠️ PROBLEMA: Weaviate v4 não permite adicionar propriedades depois
            return True  # Ainda retorna True para não quebrar
    
    # Se collection não existe...
    if "VERBA_Embedding" in collection_name:
        msg.warn(f"⚠️  Collection {collection_name} será criada SEM propriedades de ETL")
        # ⚠️ PROBLEMA: Não cria com propriedades de ETL automaticamente
```

**⚠️ Problema:** O patch **apenas verifica** mas **não cria** collections com propriedades de ETL.

## 🎯 Como Funciona o Chunking ETL-Aware

### 1. ETL Pré-Chunking (chunking_hook.py)

O hook `apply_etl_pre_chunking()` é chamado **antes** do chunking:

```python
# verba_extensions/integration/chunking_hook.py
def apply_etl_pre_chunking(document: Document, enable_etl: bool = True):
    # Extrai entidades do documento completo
    entity_spans = extract_entities(document.content)
    # Armazena em document.meta
    document.meta["entity_spans"] = entity_spans
    document.meta["entity_ids"] = normalized_ids
    return document
```

**Isso funciona INDEPENDENTE do schema** - apenas armazena em `document.meta`.

### 2. Section-Aware Chunker

O `SectionAwareChunker` usa as entidades pré-extraídas:

```python
# verba_extensions/plugins/section_aware_chunker.py
async def chunk(self, config, documents, embedder, embedder_config):
    # Lê entity_spans do document.meta
    entity_spans = document.meta.get("entity_spans", [])
    # Usa para evitar cortar entidades
    # ...
```

**Isso também funciona INDEPENDENTE do schema** - apenas usa `document.meta`.

### 3. ETL Pós-Chunking (import_hook.py)

O hook `patched_import_document()` executa ETL pós-chunking:

```python
# verba_extensions/integration/import_hook.py
async def patched_import_document(self, client, document, embedder):
    # Após import, busca passage_uuids
    # Executa ETL A2
    result = await run_etl_on_passages(client, passage_uuids)
    # Tenta salvar em propriedades de ETL
    # ⚠️ MAS se schema não tem propriedades, salva em 'meta' JSON
```

**AQUI está o problema:** Se o schema não tem propriedades de ETL, os metadados são salvos em `meta` (JSON string) ao invés de propriedades separadas.

## ⚠️ Limitação do Weaviate v4

**Weaviate v4 NÃO permite adicionar propriedades depois que a collection foi criada.**

Portanto:
- ✅ Se collection **já existe** sem propriedades ETL → **Não pode adicionar**
- ✅ Se collection **não existe** → **Pode criar com propriedades ETL**

## ✅ Solução: Criar Collection com ETL ANTES

### Opção 1: Criar Manualmente (Recomendado)

Execute o script ANTES de usar o Verba:

```bash
python scripts/create_collection_etl_from_scratch.py
```

Ou use o script simplificado:

```python
# scripts/create_collection_with_etl.py
from verba_extensions.integration.schema_updater import get_etl_properties
from weaviate.classes.config import Property, DataType

# Propriedades padrão do Verba
verba_properties = [
    Property(name="chunk_id", data_type=DataType.NUMBER),
    Property(name="content", data_type=DataType.TEXT),
    # ... outras propriedades padrão
]

# Propriedades de ETL
etl_properties = get_etl_properties()

# Cria collection com todas as propriedades
collection = client.collections.create(
    name="VERBA_Embedding_all_MiniLM_L6_v2",
    properties=verba_properties + etl_properties,
)
```

### Opção 2: Modificar Patch para Criar Automaticamente

Podemos modificar `patch_weaviate_manager_verify_collection()` para criar collections com ETL automaticamente:

```python
async def patched_verify_collection(self, client, collection_name: str):
    # Se collection não existe e é de embedding
    if "VERBA_Embedding" in collection_name and not await client.collections.exists(collection_name):
        # Cria com propriedades de ETL
        etl_properties = get_etl_properties()
        # Propriedades padrão do Verba
        verba_properties = get_verba_properties()
        # Cria collection
        collection = client.collections.create(
            name=collection_name,
            properties=verba_properties + etl_properties,
        )
        return True
```

**⚠️ Problema:** Precisamos saber as propriedades padrão do Verba e o vectorizer config.

### Opção 3: Usar Script de Migração

Para collections existentes:

```bash
python scripts/migrate_collection_with_etl.py
```

Isso cria uma nova collection com ETL e copia os dados.

## 🚀 Como Garantir no Railway

### Método 1: Script de Setup (Recomendado)

Crie um script que roda no startup do Railway:

```python
# scripts/railway_setup.py
async def setup_weaviate_schema():
    """Cria collections com ETL se não existirem"""
    client = await get_weaviate_client()
    
    # Lista de collections esperadas
    collections = [
        "VERBA_Embedding_all_MiniLM_L6_v2",
        "VERBA_Embedding_all_MiniLM_L12_v2",
        # ... outras
    ]
    
    for coll_name in collections:
        if not client.collections.exists(coll_name):
            # Cria com propriedades de ETL
            create_collection_with_etl(client, coll_name)
```

Execute no Dockerfile ou startup script:

```dockerfile
# Dockerfile
RUN python scripts/railway_setup.py
```

### Método 2: Verificação na UI

O Verba verifica automaticamente se a collection tem propriedades de ETL:

```python
# Em algum lugar do código (precisa adicionar)
has_etl = await check_collection_has_etl_properties(client, collection_name)
if not has_etl:
    msg.warn("Collection não tem propriedades de ETL - ETL não funcionará completamente")
```

### Método 3: Criar na Primeira Importação

Modificar o patch para criar collection com ETL na primeira vez:

```python
async def patched_verify_collection(self, client, collection_name: str):
    if not await client.collections.exists(collection_name):
        if "VERBA_Embedding" in collection_name:
            # Cria com ETL na primeira vez
            return await create_with_etl(client, collection_name)
    return await original_verify(self, client, collection_name)
```

## 📊 Verificação

### Como Verificar se Schema tem ETL

```python
from verba_extensions.integration.schema_updater import check_collection_has_etl_properties

has_etl = await check_collection_has_etl_properties(client, "VERBA_Embedding_all_MiniLM_L6_v2")
if has_etl:
    print("✅ Collection tem propriedades de ETL")
else:
    print("❌ Collection NÃO tem propriedades de ETL")
```

### Propriedades de ETL Esperadas

```python
etl_properties = [
    "entities_local_ids",      # TEXT_ARRAY
    "section_title",           # TEXT
    "section_entity_ids",      # TEXT_ARRAY
    "section_scope_confidence", # NUMBER
    "primary_entity_id",       # TEXT
    "entity_focus_score",      # NUMBER
    "etl_version",             # TEXT
]
```

## 🎯 Resumo

1. **Chunking ETL-aware funciona SEM schema ETL** - usa `document.meta`
2. **ETL pós-chunking precisa de schema ETL** - para salvar em propriedades separadas
3. **Schema ETL deve ser criado ANTES** - Weaviate v4 não permite adicionar depois
4. **Patch atual apenas VERIFICA** - não cria automaticamente
5. **Solução:** Criar collection com ETL manualmente ou via script de setup

## ✅ Checklist para Railway

- [ ] Collection criada com propriedades de ETL
- [ ] Patch de schema aplicado (via startup.py)
- [ ] Hook de chunking aplicado (via startup.py)
- [ ] Hook de import aplicado (via startup.py)
- [ ] ETL pré-chunking funcionando (armazena em document.meta)
- [ ] ETL pós-chunking funcionando (salva em propriedades ETL)

## 🔧 Próximos Passos

1. **Modificar patch** para criar collections com ETL automaticamente
2. **Ou criar script de setup** que roda no Railway
3. **Ou documentar** que usuário deve criar collection manualmente antes

