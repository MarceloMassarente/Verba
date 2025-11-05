# 🔍 Validação: ETL Pré-Chunking e Pós-Chunking

## 📋 Resumo Executivo

**Data:** 2025-01-XX  
**Documento testado:** `Dossiê_ Flow Executive Finders.pdf`  
**Resultado:** ❌ **ETL NÃO ESTÁ SALVANDO METADADOS NOS CHUNKS**

---

## ✅ O que foi validado

### 1. ETL Pré-Chunking
- ✅ **Código implementado:** `verba_extensions/integration/chunking_hook.py`
- ✅ **Integração:** `goldenverba/verba_manager.py` chama `apply_etl_pre_chunking()` antes do chunking
- ❌ **Metadados salvos:** **NÃO ENCONTRADOS** nos chunks

### 2. ETL Pós-Chunking
- ✅ **Código implementado:** `verba_extensions/integration/import_hook.py`
- ✅ **Hook aplicado:** Monkey patch em `WeaviateManager.import_document()`
- ❌ **Metadados salvos:** **NÃO ENCONTRADOS** nos chunks

### 3. Schema do Weaviate
- ✅ **Collection:** `VERBA_Embedding_all_MiniLM_L6_v2`
- ❌ **Campos de ETL:** **NÃO EXISTEM** no schema
- ✅ **Campos disponíveis:** `chunk_id`, `content`, `meta`, `doc_uuid`, `title`, etc.

---

## 🔍 Análise Detalhada

### 1. ETL Pré-Chunking

**O que deveria acontecer:**
1. `apply_etl_pre_chunking()` extrai entidades do documento completo
2. Armazena `entity_spans` em `document.meta["entity_spans"]`
3. Chunker usa `entity_spans` para evitar cortar entidades
4. Metadados são preservados nos chunks

**O que está acontecendo:**
- ✅ ETL pré-chunking é executado (visto nos logs)
- ✅ `entity_spans` são armazenados em `document.meta`
- ❌ **Metadados NÃO são salvos nos chunks no Weaviate**

**Evidência:**
```python
# Script de validação encontrou:
- Total de chunks: 20
- Chunks com entities_local_ids: 0
- Chunks com entity_spans: 0
- Chunks com section_title: 0
```

### 2. ETL Pós-Chunking

**O que deveria acontecer:**
1. `patched_import_document()` busca `passage_uuids` após import
2. Chama `run_etl_on_passages()` para processar chunks
3. Atualiza chunks com `entities_local_ids`, `section_title`, etc.

**O que está acontecendo:**
- ✅ Hook está sendo executado (visto nos logs)
- ✅ `passage_uuids` são encontrados
- ❌ **Atualização de chunks FALHA** porque campos não existem no schema

**Problema identificado:**
```python
# verba_extensions/plugins/a2_etl_hook.py linha 190
props = {
    "entities_local_ids": local_ids,  # ❌ Campo não existe no schema
    "section_entity_ids": sect_ids,   # ❌ Campo não existe no schema
    "section_title": "...",            # ❌ Campo não existe no schema
    ...
}

# Tenta atualizar, mas falha silenciosamente
coll.data.update(uuid=uid, properties=props)  # ❌ Erro não reportado
```

### 3. Schema do Weaviate

**Campos disponíveis na collection `VERBA_Embedding_all_MiniLM_L6_v2`:**
- ✅ `chunk_id` (number)
- ✅ `content` (text)
- ✅ `meta` (text) - **Pode conter JSON!**
- ✅ `doc_uuid` (uuid)
- ✅ `title` (text)
- ❌ `entities_local_ids` - **NÃO EXISTE**
- ❌ `section_title` - **NÃO EXISTE**
- ❌ `section_entity_ids` - **NÃO EXISTE**

**Solução possível:**
O campo `meta` existe e pode conter JSON. Os metadados de ETL **podem ser salvos em `meta`** como JSON string.

---

## 🐛 Problemas Identificados

### Problema 1: Campos de ETL não existem no schema
**Severidade:** 🔴 **CRÍTICO**

O ETL tenta atualizar campos que não existem no schema do Verba:
- `entities_local_ids`
- `section_title`
- `section_entity_ids`
- `primary_entity_id`
- `entity_focus_score`

**Impacto:**
- ETL executa, mas falha silenciosamente ao atualizar chunks
- Metadados nunca chegam ao Weaviate
- Queries por entidades não funcionam

### Problema 2: ETL pré-chunking não persiste metadados
**Severidade:** 🟡 **MÉDIO**

`entity_spans` são armazenados em `document.meta`, mas não são transferidos para os chunks quando são salvos no Weaviate.

**Impacto:**
- Chunking entity-aware funciona (usando `entity_spans` em memória)
- Mas metadados não ficam disponíveis para queries posteriores

### Problema 3: Erros não são reportados
**Severidade:** 🟡 **MÉDIO**

O ETL falha silenciosamente quando tenta atualizar campos inexistentes.

**Impacto:**
- Difícil diagnosticar problemas
- Logs não mostram erros de atualização

---

## ✅ Soluções Propostas

### Solução 1: Salvar metadados em `meta` (JSON)

**Abordagem:**
Salvar metadados de ETL no campo `meta` como JSON string.

**Vantagens:**
- ✅ Não requer mudança no schema
- ✅ Funciona com schema atual do Verba
- ✅ Metadados ficam disponíveis para queries

**Implementação:**
```python
# Em a2_etl_hook.py
import json

# Atualiza meta com metadados de ETL
current_meta = obj.properties.get("meta", "{}")
try:
    meta_dict = json.loads(current_meta) if current_meta else {}
except:
    meta_dict = {}

meta_dict.update({
    "entities_local_ids": local_ids,
    "section_entity_ids": sect_ids,
    "section_title": sect_title,
    "etl_version": "entity_scope_v1"
})

props = {
    "meta": json.dumps(meta_dict, ensure_ascii=False)
}
coll.data.update(uuid=uid, properties=props)
```

### Solução 2: Adicionar campos ao schema (Recomendado a longo prazo)

**Abordagem:**
Adicionar campos de ETL ao schema do Verba via migration.

**Vantagens:**
- ✅ Queries mais eficientes (campos indexados)
- ✅ Estrutura mais clara
- ✅ Melhor performance

**Desvantagens:**
- ❌ Requer mudança no schema
- ❌ Pode quebrar compatibilidade com versões antigas

### Solução 3: Transferir metadados do chunking para Weaviate

**Abordagem:**
Modificar `WeaviateManager.import_document()` para transferir `chunk.meta` para `meta` no Weaviate.

**Implementação:**
```python
# Em managers.py, ao salvar chunk
chunk_props = {
    "content": chunk.content,
    "meta": json.dumps(chunk.meta) if chunk.meta else "{}",
    ...
}
```

---

## 📊 Estatísticas de Validação

### Chunks Analisados
- **Total:** 20 chunks
- **Com meta:** 20 chunks (100%)
- **Com metadados de ETL:** 0 chunks (0%)

### Metadados Esperados
- `entities_local_ids`: ❌ 0 chunks
- `section_title`: ❌ 0 chunks
- `entity_spans`: ❌ 0 chunks

---

## 🎯 Próximos Passos

1. **Implementar Solução 1** (salvar em `meta` como JSON)
   - Modificar `a2_etl_hook.py` para salvar em `meta`
   - Testar salvamento de metadados
   - Validar queries por entidades

2. **Verificar logs do ETL**
   - Confirmar se ETL está sendo executado
   - Verificar se há erros silenciosos
   - Adicionar logs mais detalhados

3. **Testar queries por entidades**
   - Após implementar Solução 1, testar queries por `entities_local_ids`
   - Verificar se busca por entidades funciona

4. **Documentar solução**
   - Atualizar documentação de ETL
   - Criar guia de troubleshooting

---

## 📝 Conclusão

**Status atual:** ❌ **ETL NÃO ESTÁ FUNCIONANDO COMPLETAMENTE**

- ✅ ETL pré-chunking executa e melhora chunking (entity-aware)
- ✅ ETL pós-chunking executa e processa chunks
- ❌ **Metadados não são salvos no Weaviate** (campos não existem no schema)
- ❌ **Queries por entidades não funcionam** (sem metadados)

**Ação recomendada:** Implementar Solução 1 (salvar metadados em `meta` como JSON) para ter funcionalidade imediata, e considerar Solução 2 (adicionar campos ao schema) para longo prazo.


