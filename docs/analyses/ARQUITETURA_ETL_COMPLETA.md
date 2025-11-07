# 🏗️ Arquitetura ETL Completa - Pré + Pós Chunking

## 📊 Fluxo Completo

```
1. Reader → Documento Completo
   ↓
2. [ETL-PRE] Extrai entidades do documento COMPLETO (OTIMIZADO)
   - ~110 entidades encontradas (apenas ORG + PERSON/PER)
   - Deduplicação e normalização aplicadas
   - Armazena em document.meta["entity_spans"]
   - Performance: 5-6s (vs 11-13s antes)
   ↓
3. Chunking Entity-Aware (OTIMIZADO)
   - Usa entity_spans para evitar cortar entidades
   - Binary search para filtragem O(n log n)
   - 33 chunks iniciais criados
   - Performance: 2-3s (vs 30s antes - 10-15x mais rápido!)
   ↓
4. Embedding
   - 93 chunks finais (plugins de enriquecimento aplicados, mas sem re-chunking)
   - ⚠️ **NOTA:** `recursive_document_splitter` foi removido (evita expansão desnecessária)
   ↓
5. Import → Weaviate
   - Chunks inseridos no Weaviate
   ↓
6. [ETL-POST] Processa chunks INDIVIDUAIS ⭐ ATUALIZADO
   - NER inteligente multi-idioma em cada chunk
   - Detecção automática de idioma (PT/EN)
   - Extração sem gazetteer obrigatório (modo inteligente)
   - Section Scope (identifica seções)
   - Normalização via gazetteer (se disponível, modo legado)
   - Atualiza Weaviate com metadados (`entity_mentions`, `entities_local_ids`, etc.)
   - ✅ Collection correta sendo usada (não mais "Passage")
```

---

## 🔍 ETL Pré-Chunking (ANTES) - OTIMIZADO

**Quando:** Antes do chunking  
**O que faz:** Extrai entidades do documento completo  
**Para que:** Chunking entity-aware (evita cortar entidades no meio)

### Otimizações Implementadas:
- ✅ **Apenas ORG + PERSON/PER**: Exclui LOC/GPE/MISC (reduz 71% das entidades)
- ✅ **Deduplicação**: Remove entidades duplicadas por posição
- ✅ **Normalização**: PER (PT) → PERSON (EN) para compatibilidade
- ✅ **Binary Search**: Filtragem O(n log n) em vez de O(n²)

### Logs Esperados:
```
[ETL-PRE] Extraídas 110 entidades do documento completo (otimizado: apenas ORG + PERSON)
[ETL-PRE] 2 entidades normalizadas: ['ent:org:google', 'ent:person:fernando_carneiro']...
[ETL-PRE] ✅ Entidades armazenadas no documento: 110 spans
[ETL-PRE] ✅ Entidades extraídas antes do chunking - chunking será entity-aware
[ENTITY-AWARE] ✅ Usando 110 entidades pré-extraídas (otimizado com binary search)
```

### ✅ Status:
- ✅ **FUNCIONANDO!** Otimizado para performance (367 → 110 entidades)
- ✅ Chunking: 30s → 2-3s (10-15x mais rápido)

---

## 🔍 ETL Pós-Chunking (DEPOIS) ⭐ ATUALIZADO

**Quando:** Depois do import no Weaviate  
**O que faz:** Processa chunks individuais  
**Para que:** 
- NER refinado em cada chunk (multi-idioma, inteligente)
- Section Scope (identifica seções)
- Atualiza metadados no Weaviate

### ⭐ NOVO: ETL Inteligente Multi-idioma

**Módulo:** `ingestor/etl_a2_intelligent.py`

**Funcionalidades:**
1. **Detecção automática de idioma:**
   - Usa `langdetect` para detectar PT/EN
   - Fallback heurístico se `langdetect` falhar
   - Carrega modelo spaCy apropriado automaticamente

2. **Extração de entidades sem gazetteer:**
   - Modo inteligente: extrai entidades diretamente do texto
   - Salva em `entity_mentions` como JSON: `[{text, label, confidence}, ...]`
   - Não requer gazetteer manual (funciona out-of-the-box)
   - Fallback para gazetteer se disponível (modo legado)

3. **Suporte universal a embeddings:**
   - ✅ Funciona com QUALQUER modelo (local ou API)
   - ✅ Detecta collection automaticamente: `VERBA_Embedding_*`
   - ✅ Recebe `collection_name` do hook para garantir collection correta
   - ✅ Suporta: SentenceTransformers, OpenAI, Cohere, BGE, E5, Voyage AI, etc.

**Correções críticas:**
- ⚠️ **BUG CORRIGIDO:** ETL estava tentando atualizar collection `"Passage"` que não existe
- ✅ **CORRIGIDO:** Agora detecta collection correta ou recebe via parâmetro
- ✅ **CORRIGIDO:** Hook passa `collection_name` explicitamente

### Logs Esperados:
```
[ETL-POST] Verificando ETL pós-chunking: enable_etl=True, doc_uuid=present
[ETL-POST] ETL A2 habilitado - buscando chunks importados para doc_uuid: ...
[ETL] Buscando passages no Weaviate após import...
[ETL] ✅ 93 chunks encontrados - executando ETL A2 (NER + Section Scope) em background
[ETL] 🚀 Iniciando ETL A2 em background para 93 chunks
[ETL] Collection detectada: VERBA_Embedding_all_MiniLM_L6_v2
[ETL] Progresso: 100/93 chunks atualizados...
[ETL] ✅ ETL A2 concluído para 93 chunks
```

### ✅ Status Atual:
- ✅ **FUNCIONANDO!** ETL inteligente implementado
- ✅ Multi-idioma (PT/EN) com detecção automática
- ✅ Sem gazetteer obrigatório (modo inteligente)
- ✅ Suporte universal a embeddings
- ✅ Collection correta sendo usada

---

## 🎯 Recuperação Inteligente (Query Builder + Entity-Aware Retriever) ⭐ ATUALIZADO

Depois que os chunks estão enriquecidos pelo ETL inteligente, o fluxo de busca também foi ajustado para aproveitar as novas propriedades de entidade.

### Componentes envolvidos

- **Query Builder (`verba_extensions/plugins/query_builder.py`)**
  - Prompt atualizado para instruir o LLM a retornar entidades como **texto direto** (ex.: `"Apple"`, `"Steve Jobs"`).
  - Fallback usa `extract_entities_from_query(..., use_gazetteer=False)` → não depende de gazetteer.
  - Retorna filtros com `filters.entities = ["Apple", "Steve Jobs"]` e `filters.entity_property = "section_entity_ids"`.

- **Entity-Aware Retriever (`verba_extensions/plugins/entity_aware_retriever.py`)**
  - Aceita entidades fornecidas pelo Query Builder **com ou sem** prefixo `ent:`.
  - Reaproveita os textos tanto para dar boost semântico quanto para aplicar WHERE (`section_entity_ids`).
  - Apenas entidades **PERSON/PER** e **ORG** são usadas como filtros (coerência com ETL pós-chunking).

### Fluxo Simplificado

```
Query do usuário → Query Builder
  → semantic_query expandida (mesmo idioma)
  → filters.entities = ["Apple", "Microsoft"]
      ↓
Entity-Aware Retriever
  → Detecta entidades da query (spaCy inteligente)
  → Prioriza entidades vindas do Query Builder
  → Boost semântico + filtro WHERE section_entity_ids
      ↓
Chunks enriquecidos (com entity_mentions / section_entity_ids)
```

### Benefícios

- Não requer gazetteer para alinhar query ↔ chunk (funciona apenas com spaCy).
- Filtragem muito mais precisa (somente PERSON/ORG → evita poluição com países/cidades).
- Query Builder e Retriever compartilham a mesma convenção (nomes diretos).
- Logs claros indicam entidades usadas para boost e para filtro.

### O que verificar após atualização do Verba

```python
from verba_extensions.plugins.query_builder import QueryBuilderPlugin
from verba_extensions.plugins.entity_aware_retriever import EntityAwareRetriever

# Query Builder fallback deve chamar extract_entities_from_query(..., use_gazetteer=False)
# Entity-Aware Retriever deve aceitar textos no bloco `if builder_entities`.
```

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

