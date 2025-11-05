# 🔄 Como Recriar Collections sem API Key

## ✅ **Solução Simples: Redeploy do Weaviate**

Você não precisa de API key! Basta fazer redeploy do Weaviate e o Verba criará tudo automaticamente com schema ETL-aware.

---

## 🎯 **Opção 1: Redeploy do Weaviate (Recomendado)**

### No Railway:

1. **Vá para o serviço Weaviate no Railway**
2. **Deletar o serviço** (ou fazer redeploy)
3. **Recriar o serviço** (ou aguardar redeploy automático)

### Quando o Verba iniciar:

✅ O patch de schema será aplicado automaticamente (via `startup.py`)  
✅ Quando você importar um documento, o Verba vai:
   - Chamar `verify_embedding_collection()`
   - Que chama `verify_collection()` (que está patched)
   - Que detecta que collection não existe
   - **Cria collection com schema ETL-aware completo (20 propriedades)**

---

## 🎯 **Opção 2: Deletar Collections Manualmente (via UI Weaviate)**

Se você tem acesso à UI do Weaviate (sem API key):

1. **Acesse a UI do Weaviate** (geralmente em `http://seu-weaviate:8080` ou URL do Railway)
2. **Vá em "Schema"**
3. **Delete as collections de embedding:**
   - `VERBA_Embedding_all_MiniLM_L6_v2`
   - `VERBA_Embedding_text_embedding_ada_002`
   - Qualquer outra collection `VERBA_Embedding_*`
4. **Mantenha:** `VERBA_DOCUMENTS`, `VERBA_CONFIGURATION`, etc.

### Quando o Verba iniciar:

✅ Mesmo comportamento - collections serão criadas com schema ETL-aware automaticamente

---

## 🎯 **Opção 3: Deletar via Script (se conseguir conectar)**

Se conseguir configurar acesso (mesmo sem API key):

```bash
# No Railway (via terminal)
railway run python scripts/recreate_collections_etl_aware.py --force
```

---

## ✅ **Como Confirmar que Funcionou**

### 1. **Verificar Logs na Inicialização:**

Quando o Verba iniciar, você deve ver:

```
🔧 Criando collection VERBA_Embedding_... com schema ETL-aware...
   📋 Total de propriedades: 20
✅ Collection criada com schema ETL-aware!
```

### 2. **Verificar após Importar Documento:**

Após importar um documento, os logs devem mostrar:

```
✅ Collection VERBA_Embedding_... já tem schema ETL-aware
[ETL-POST] ✅ ETL executado
```

### 3. **Verificar Schema (se tiver acesso ao Weaviate):**

Na UI do Weaviate, em "Schema" → Coleção de embedding:
- Deve ter **20 propriedades** (13 padrão + 7 ETL)
- Propriedades ETL devem aparecer:
  - `entities_local_ids`
  - `section_title`
  - `section_entity_ids`
  - `section_scope_confidence`
  - `primary_entity_id`
  - `entity_focus_score`
  - `etl_version`

---

## 🔍 **Como o Patch Funciona**

### Arquivo: `verba_extensions/startup.py` (linha 57-60)

```python
# Aplica patch de schema ETL (adiciona propriedades automaticamente)
from verba_extensions.integration.schema_updater import patch_weaviate_manager_verify_collection
patch_weaviate_manager_verify_collection()
```

### Arquivo: `verba_extensions/integration/schema_updater.py` (linha 191-225)

```python
async def patched_verify_collection(self, client, collection_name: str):
    # Se collection não existe e é de embedding, cria com schema ETL-aware
    if "VERBA_Embedding" in collection_name:
        all_properties = get_all_embedding_properties()  # 20 propriedades
        collection = await client.collections.create(
            name=collection_name,
            properties=all_properties,  # Schema ETL-aware completo
        )
```

### Quando é Chamado:

1. **Na inicialização do Verba:**
   - Quando `WeaviateManager` é criado
   - Verifica collections existentes

2. **Ao importar documento:**
   - `verify_embedding_collection()` é chamado
   - Que chama `verify_collection()` (patched)
   - Se collection não existe → cria com schema ETL-aware

---

## 📋 **Checklist Pós-Redeploy**

Após fazer redeploy do Weaviate:

- [ ] Verificar logs do Verba: "Patch de schema ETL-aware aplicado"
- [ ] Importar um documento de teste
- [ ] Verificar logs: "Criando collection ... com schema ETL-aware"
- [ ] Verificar logs: "Collection criada com schema ETL-aware!"
- [ ] Verificar se ETL pós-chunking executou (logs: "[ETL-POST] ✅")
- [ ] Verificar se chunks têm metadados ETL (se tiver acesso ao Weaviate)

---

## ✅ **Resumo**

**SIM, fazer redeploy do Weaviate resolve!**

Quando o Verba iniciar:
1. ✅ Patch de schema será aplicado automaticamente
2. ✅ Collections serão criadas com schema ETL-aware quando necessário
3. ✅ ETL pós-chunking salvará metadados corretamente

**Não precisa de API key!** O patch funciona automaticamente. 🎉

