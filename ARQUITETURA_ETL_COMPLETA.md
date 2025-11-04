# 🏗️ Arquitetura ETL Completa - Pré + Pós Chunking

## 📊 Fluxo Completo

```
1. Reader → Documento Completo
   ↓
2. [ETL-PRE] Extrai entidades do documento COMPLETO
   - 472 entidades encontradas
   - Armazena em document.meta["entity_spans"]
   ↓
3. Chunking Entity-Aware
   - Usa entity_spans para evitar cortar entidades
   - 33 chunks iniciais criados
   ↓
4. Embedding
   - 2226 chunks finais (expandidos por plugins)
   ↓
5. Import → Weaviate
   - Chunks inseridos no Weaviate
   ↓
6. [ETL-POST] Processa chunks INDIVIDUAIS
   - NER em cada chunk (pode encontrar mais entidades)
   - Section Scope (identifica seções)
   - Normalização via gazetteer
   - Atualiza Weaviate com metadados
```

---

## 🔍 ETL Pré-Chunking (ANTES)

**Quando:** Antes do chunking  
**O que faz:** Extrai entidades do documento completo  
**Para que:** Chunking entity-aware (evita cortar entidades no meio)

### Logs Esperados:
```
[ETL-PRE] Extraídas 472 entidades do documento completo
[ETL-PRE] 2 entidades normalizadas: ['ent:loc:usa', 'ent:org:google']...
[ETL-PRE] ✅ Entidades armazenadas no documento: 472 spans
[ETL-PRE] ✅ Entidades extraídas antes do chunking - chunking será entity-aware
```

### ✅ Status nos Seus Logs:
- ✅ **FUNCIONOU!** Vi todos esses logs

---

## 🔍 ETL Pós-Chunking (DEPOIS)

**Quando:** Depois do import no Weaviate  
**O que faz:** Processa chunks individuais  
**Para que:** 
- NER refinado em cada chunk
- Section Scope (identifica seções)
- Atualiza metadados no Weaviate

### Logs Esperados:
```
[ETL-POST] Verificando ETL pós-chunking: enable_etl=True, doc_uuid=present
[ETL-POST] ETL A2 habilitado - buscando chunks importados para doc_uuid: ...
[ETL] Buscando passages no Weaviate após import...
[ETL] ✅ 2226 chunks encontrados - executando ETL A2 (NER + Section Scope) em background
[ETL] 🚀 Iniciando ETL A2 em background para 2226 chunks
[ETL] ✅ ETL A2 concluído para 2226 chunks
```

### ❌ Status nos Seus Logs:
- ❌ **NÃO APARECEU!** Nenhum desses logs foi visto

---

## 🤔 Por Que ETL Pós Não Apareceu?

### Possíveis Causas:

1. **Hook não está sendo executado**
   - Monkey patch não foi aplicado
   - Verificar: `[ETL-POST] Verificando ETL pós-chunking` deveria aparecer

2. **enable_etl não está chegando no hook**
   - Pode estar sendo perdido no caminho
   - Verificar logs: `[ETL-POST] ETL pós-chunking não habilitado (enable_etl=False)`

3. **doc_uuid não está sendo retornado**
   - Import pode não estar retornando doc_uuid
   - Verificar logs: `[ETL-POST] ETL pós-chunking não executado (doc_uuid não disponível)`

4. **Executando em background silenciosamente**
   - ETL pós pode estar rodando mas logs não aparecem
   - Verificar se chunks têm metadados de entidades no Weaviate

---

## 📋 Checklist de Verificação

### ETL Pré-Chunking:
- [x] ✅ Extraiu entidades do documento completo (472 entidades)
- [x] ✅ Armazenou entity_spans no documento
- [x] ✅ Chunking entity-aware usou as entidades

### ETL Pós-Chunking:
- [ ] ❓ Hook está sendo executado?
- [ ] ❓ enable_etl está chegando no hook?
- [ ] ❓ doc_uuid está sendo retornado?
- [ ] ❓ Chunks têm metadados de entidades no Weaviate?

---

## 🔧 Próximos Passos para Diagnosticar ETL Pós

1. **Verificar se hook está aplicado:**
   - Procurar log: `✅ Hook ETL A2 integrado no WeaviateManager` (deveria aparecer no startup)

2. **Verificar se enable_etl está presente:**
   - Logs adicionados mostram: `[ETL-POST] Verificando ETL pós-chunking: enable_etl=...`

3. **Verificar se doc_uuid está sendo retornado:**
   - Logs adicionados mostram: `[ETL-POST] ... doc_uuid=...`

4. **Verificar se chunks têm metadados:**
   - Checar no Weaviate se chunks têm `entities_local_ids` ou `section_title`

---

## 💡 Resumo

**ETL Pré:** ✅ **FUNCIONANDO** - Extrai entidades antes do chunking  
**ETL Pós:** ❌ **NÃO VISÍVEL** - Precisa diagnosticar por que não apareceu nos logs

**Arquitetura Correta:**
- ✅ Pré: Para chunking entity-aware
- ✅ Pós: Para NER refinado + Section Scope + Atualizar Weaviate

**Ambos são necessários!**

