# 🔍 Como Verificar ETL no Railway

## Opção 1: Executar Script Localmente (Conecta ao Railway)

### **Passo 1: Configure Variáveis de Ambiente**

No seu `.env` ou terminal, configure:

```bash
# Railway Internal Network
export WEAVIATE_HTTP_HOST=weaviate.railway.internal
export WEAVIATE_HTTP_PORT=8080
export WEAVIATE_GRPC_HOST=weaviate.railway.internal  
export WEAVIATE_GRPC_PORT=50051

# OU se você tem acesso externo
export WEAVIATE_URL=https://seu-weaviate.railway.app
export WEAVIATE_API_KEY_VERBA=sua_api_key
```

### **Passo 2: Execute o Script**

```bash
python scripts/verify_etl_processing.py "Estudo Mercado Headhunting Brasil.pdf"
```

---

## Opção 2: Verificar via Railway Logs

### **Verificar Logs de Importação**

Procure nos logs do Railway por:

1. **ETL Pré-Chunking:**
   ```
   ✔ [ETL-PRE] ✅ Entidades extraídas antes do chunking - chunking será entity-aware
   ℹ [ETL-PRE] Extraídas 370 entidades do documento completo
   ```

2. **Chunking Entity-Aware:**
   ```
   ℹ [ENTITY-AWARE] Usando 370 entidades pré-extraídas para chunking entity-aware
   ```

3. **ETL Pós-Chunking:**
   ```
   ℹ [ETL] ✅ 2921 chunks encontrados - executando ETL A2 (NER + Section Scope) em background
   ✔ [ETL] ✅ ETL A2 concluído para 2921 chunks
   ```

---

## Opção 3: Verificar via API Weaviate (Diretamente)

### **Usar GraphQL ou Python**

```python
import weaviate
from weaviate.classes.query import Filter

# Conecta
client = await weaviate.connect_to_custom(...)

# Busca documento
doc_collection = client.collections.get("VERBA_DOCUMENTS")
docs = await doc_collection.query.fetch_objects(
    filters=Filter.by_property("title").equal("Estudo Mercado Headhunting Brasil.pdf"),
    limit=1
)

if docs.objects:
    doc_uuid = str(docs.objects[0].uuid)
    
    # Busca chunks
    embed_collection = client.collections.get("VERBA_Embedding_SentenceTransformers")  # ou outra
    chunks = await embed_collection.query.fetch_objects(
        filters=Filter.by_property("doc_uuid").equal(doc_uuid),
        limit=10
    )
    
    # Verifica propriedades ETL
    for chunk in chunks.objects:
        props = chunk.properties
        print(f"Chunk UUID: {chunk.uuid}")
        print(f"  entities_local_ids: {props.get('entities_local_ids', [])}")
        print(f"  primary_entity_id: {props.get('primary_entity_id', 'N/A')}")
        print(f"  section_title: {props.get('section_title', 'N/A')}")
        print(f"  etl_version: {props.get('etl_version', 'N/A')}")
```

---

## Opção 4: Verificar via Weaviate UI (Se disponível)

1. Acesse Weaviate UI (se configurado)
2. Navegue até a collection `VERBA_Embedding_SentenceTransformers` (ou a que você usou)
3. Busque chunks por `doc_uuid`
4. Verifique se chunks têm propriedades:
   - `entities_local_ids`
   - `section_entity_ids`
   - `primary_entity_id`
   - `section_title`
   - `etl_version`

---

## ✅ Checklist de Verificação

### **ETL Pré-Chunking**
- [ ] Logs mostram: `[ETL-PRE] ✅ Entidades extraídas antes do chunking`
- [ ] Logs mostram número de entidades extraídas (ex: "370 entidades")

### **Chunking Entity-Aware**
- [ ] Logs mostram: `[ENTITY-AWARE] Usando X entidades pré-extraídas`
- [ ] Chunks não cortam entidades no meio (verificar manualmente)

### **ETL Pós-Chunking**
- [ ] Logs mostram: `[ETL] ✅ ETL A2 concluído para X chunks`
- [ ] Chunks têm propriedades ETL preenchidas:
  - [ ] `entities_local_ids` não está vazio
  - [ ] `primary_entity_id` está preenchido
  - [ ] `section_title` ou `section_entity_ids` presentes
  - [ ] `etl_version` está presente

### **Schema ETL-aware**
- [ ] Collection tem propriedades ETL no schema
- [ ] Logs mostram: `✅ Collection X criada com schema ETL-aware`

---

## 🚨 Problemas Comuns

### **"could not find class Passage in schema"**
- ✅ **CORRIGIDO** - Agora usa collection de embedding correta
- Se ainda aparecer, verifique se o código foi atualizado

### **"Nenhum chunk tem propriedades ETL"**
- Verifique se `enable_etl=1` no documento
- Verifique logs: `[ETL] ✅ ETL A2 concluído`
- Verifique se collection tem schema ETL-aware

### **"Collection não tem schema ETL-aware"**
- Delete e recrie a collection
- Verifique se patch foi aplicado: `✅ Patch de schema ETL-aware aplicado`

---

**Script disponível**: `scripts/verify_etl_processing.py`

