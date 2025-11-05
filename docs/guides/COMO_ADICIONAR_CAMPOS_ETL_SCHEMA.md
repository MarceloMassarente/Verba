# 🔧 Como Adicionar Campos de ETL ao Schema do Verba

## 📋 Situação Atual

**Problema:** Os campos de ETL (`entities_local_ids`, `section_title`, etc.) não existem no schema do Verba, então o ETL não consegue salvar metadados nos chunks.

**Causa:** O Verba cria collections sem essas propriedades.

**Limitação:** Weaviate v4 **não permite adicionar propriedades depois** que a collection foi criada.

---

## ✅ Soluções Disponíveis

### Solução 1: Migração de Collection (Recomendado)

**Para collections existentes:**

1. **Execute o script de migração:**
   ```bash
   python scripts/migrate_collection_with_etl.py VERBA_Embedding_all_MiniLM_L6_v2
   ```

2. **O script irá:**
   - Criar nova collection com propriedades de ETL
   - Copiar todos os dados da collection antiga
   - Manter configuração de vectorizer
   - Adicionar propriedades de ETL vazias (serão preenchidas pelo ETL)

3. **Atualize código:**
   - Use o nome da nova collection no código
   - Ou atualize `embedding_table` no WeaviateManager

4. **Execute ETL:**
   - Reimporte documentos ou execute ETL nos objetos existentes

**Vantagens:**
- ✅ Não perde dados
- ✅ Mantém configuração original
- ✅ Permite testar antes de deletar collection antiga

**Desvantagens:**
- ⚠️  Requer espaço adicional temporário (duas collections)
- ⚠️  Pode levar tempo para grandes volumes

---

### Solução 2: Deletar e Recriar Collection

**Para collections novas ou quando migração não é viável:**

1. **Backup dos dados (se necessário):**
   ```bash
   # Exporte dados antes de deletar
   python scripts/export_collection.py VERBA_Embedding_all_MiniLM_L6_v2
   ```

2. **Delete collection:**
   ```python
   # Via código ou API
   client.collections.delete("VERBA_Embedding_all_MiniLM_L6_v2")
   ```

3. **Crie collection com propriedades de ETL:**
   ```python
   from verba_extensions.integration.schema_updater import get_etl_properties
   from weaviate.classes.config import Configure
   
   properties = [
       # Propriedades padrão do Verba
       Property(name="chunk_id", data_type=DataType.NUMBER),
       Property(name="content", data_type=DataType.TEXT),
       Property(name="doc_uuid", data_type=DataType.UUID),
       Property(name="title", data_type=DataType.TEXT),
       # ... outras propriedades padrão
       
       # Propriedades de ETL
       *get_etl_properties()
   ]
   
   client.collections.create(
       name="VERBA_Embedding_all_MiniLM_L6_v2",
       vectorizer_config=Configure.Vectorizer.sentence_transformers(...),
       properties=properties
   )
   ```

4. **Reimporte documentos:**
   - Os documentos serão importados com schema correto
   - ETL poderá salvar metadados

**Vantagens:**
- ✅ Schema limpo desde o início
- ✅ Sem duplicação de dados

**Desvantagens:**
- ⚠️  Perde dados existentes (se não fizer backup)
- ⚠️  Requer reimportação completa

---

### Solução 3: Usar Campo `meta` (JSON) - Alternativa Temporária

**Se não puder alterar schema:**

Use o campo `meta` existente para salvar metadados de ETL como JSON:

```python
import json

# Ao salvar chunk
meta_dict = {
    "entities_local_ids": ["Q312", "Q2283"],
    "section_title": "Introdução",
    "section_entity_ids": ["Q312"],
    # ... outros metadados
}

chunk_properties = {
    "content": chunk.content,
    "meta": json.dumps(meta_dict),  # Salva como JSON string
    # ... outras propriedades
}
```

**Vantagens:**
- ✅ Funciona sem alterar schema
- ✅ Metadados disponíveis para queries (via parsing JSON)

**Desvantagens:**
- ⚠️  Queries menos eficientes (precisa parsear JSON)
- ⚠️  Não pode usar filtros diretos (ex: `Filter.by_property("entities_local_ids")`)

---

## 🔧 Propriedades de ETL

As seguintes propriedades são adicionadas:

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

---

## 📝 Scripts Disponíveis

### 1. `scripts/update_verba_schema_etl.py`
Atualiza schema de todas as collections de embedding (verifica se propriedades existem).

**Nota:** Weaviate v4 não permite adicionar propriedades depois, então este script apenas verifica.

### 2. `scripts/migrate_collection_with_etl.py`
Migra collection existente para nova com propriedades de ETL.

**Uso:**
```bash
python scripts/migrate_collection_with_etl.py <collection_name> [new_collection_name]
```

### 3. `verba_extensions/integration/schema_updater.py`
Módulo com funções para gerenciar schema de ETL.

---

## 🎯 Recomendação Final

**Para produção:**
1. Use **Solução 1 (Migração)** para collections existentes
2. Para novas collections, modifique `verify_collection` para criar com propriedades de ETL desde o início

**Para desenvolvimento:**
1. Use **Solução 3 (meta JSON)** temporariamente
2. Migre para schema completo quando possível

---

## ⚠️  Limitações do Weaviate v4

- ❌ **Não permite adicionar propriedades** depois que collection existe
- ✅ **Permite criar collection** com todas as propriedades desde o início
- ✅ **Permite deletar e recriar** collection

**Consequência:** Se collection já existe, precisa migrar ou recriar.

---

## 📚 Referências

- [Weaviate v4 Schema Documentation](https://weaviate.io/developers/weaviate/manage-data/collections)
- `verba_extensions/integration/schema_updater.py` - Módulo de atualização de schema
- `scripts/migrate_collection_with_etl.py` - Script de migração


