# 🔧 Como o ETL Funciona Baseado no Chunker Escolhido

## 📊 Resumo Executivo

**ETL Pré-Chunking:** Executado **ANTES** do chunking, **independente** do chunker escolhido  
**ETL Pós-Chunking:** Executado **DEPOIS** do embedding, **independente** do chunker escolhido  
**Aproveitamento de Entity-Spans:** Apenas o **Section-Aware Chunker** usa `entity_spans` para chunking entity-aware

---

## 🔄 Fluxo Completo Independente do Chunker

```
1. Reader → Documento Completo
   ↓
2. [ETL-PRE] Extrai entidades do documento COMPLETO
   - Executado SEMPRE que enable_etl=True
   - Armazena entity_spans em document.meta
   ↓
3. Chunking (qualquer chunker)
   - Section-Aware: USA entity_spans (entity-aware)
   - Outros: IGNORAM entity_spans (mas ETL pré ainda foi executado)
   ↓
4. Embedding
   ↓
5. Import → Weaviate
   ↓
6. [ETL-POST] Processa chunks INDIVIDUAIS
   - Executado SEMPRE que enable_etl=True
   - Independente do chunker usado
```

---

## 📋 Chunkers Disponíveis no Verba

### Chunkers Padrão (do Verba Core):
1. **TokenChunker** - Divisão por tokens
2. **SentenceChunker** - Divisão por sentenças
3. **RecursiveChunker** - Divisão recursiva baseada em separadores
4. **SemanticChunker** - Agrupamento por similaridade semântica
5. **HTMLChunker** - Específico para HTML
6. **MarkdownChunker** - Específico para Markdown
7. **CodeChunker** - Específico para código
8. **JSONChunker** - Específico para JSON

### Chunkers Customizados:
9. **Section-Aware Chunker** - Respeita seções e entidades (usa `entity_spans`)

---

## 🎯 Como Cada Chunker Interage com ETL

### ✅ Section-Aware Chunker (RECOMENDADO para ETL)

**ETL Pré-Chunking:**
- ✅ **Usa** `entity_spans` para evitar cortar entidades no meio
- ✅ Chunking **entity-aware**: Tenta manter entidades completas no mesmo chunk
- ✅ **Binary search** para filtragem O(n log n) (6.7x mais rápido)
- ✅ **Apenas ORG + PERSON/PER** (exclui LOC/GPE para performance)
- ✅ Logs: `[ENTITY-AWARE] ✅ Usando X entidades pré-extraídas (otimizado com binary search)`

**ETL Pós-Chunking:**
- ✅ Executado normalmente (independente do chunker)

**Resultado:**
- ✅ Melhor qualidade de chunks (entidades não cortadas)
- ✅ Melhor aproveitamento do ETL pré-chunking
- ✅ Performance: 2-3s (vs 30s antes - 10-15x mais rápido!)
- ✅ ~110 entidades processadas (vs 367 antes - 71% redução)

---

### 📦 Outros Chunkers (Token, Sentence, Recursive, etc.)

**ETL Pré-Chunking:**
- ✅ **Executado normalmente** (entidades são extraídas)
- ❌ **Não usa** `entity_spans` (chunkers não foram modificados)
- ⚠️ Entidades podem ser cortadas no meio dos chunks

**ETL Pós-Chunking:**
- ✅ Executado normalmente (independente do chunker)

**Resultado:**
- ✅ ETL pré e pós funcionam normalmente
- ⚠️ Chunking pode cortar entidades no meio (menos ideal)
- ⚠️ `entity_spans` são extraídos mas não aproveitados no chunking

---

## 📍 Onde Cada Parte Acontece

### ETL Pré-Chunking
**Localização:** `goldenverba/verba_manager.py` (linha ~243-256)  
**Execução:** ANTES do chunking, para TODOS os chunkers  
**Condição:** `enable_etl=True` no `document.meta`

```python
# Em verba_manager.py
if enable_etl:
    document = apply_etl_pre_chunking(document, enable_etl=True)
    # Armazena entity_spans em document.meta["entity_spans"]

# Depois, chunking é executado (qualquer chunker)
chunked_documents = await self.chunker_manager.chunk(...)
```

### Section-Aware Chunker (Entity-Aware)
**Localização:** `verba_extensions/plugins/section_aware_chunker.py`  
**Execução:** Durante o chunking  
**Condição:** Chunker escolhido = "Section-Aware"

```python
# Em section_aware_chunker.py
entity_spans = document.meta.get("entity_spans", [])
if entity_spans:
    # Usa entity_spans para evitar cortar entidades
    # ...
```

### ETL Pós-Chunking
**Localização:** `verba_extensions/integration/import_hook.py` (monkey patch)  
**Execução:** DEPOIS do import no Weaviate  
**Condição:** `enable_etl=True` e `doc_uuid` disponível

```python
# Em import_hook.py (monkey patch de WeaviateManager.import_document)
if enable_etl and doc_uuid:
    # Busca chunks e executa ETL em background
    await run_etl_on_passages(client, passage_uuids, tenant=self.tenant)
```

---

## 🔍 Logs para Identificar o Comportamento

### ETL Pré-Chunking (Todos os Chunkers) - OTIMIZADO
```
[ETL-PRE-CHECK] Verificando ETL para documento '...': enable_etl=True
[ETL-PRE] ETL habilitado detectado - iniciando extração de entidades pré-chunking
[ETL-PRE] Extraídas 110 entidades do documento completo (otimizado: apenas ORG + PERSON)
[ETL-PRE] ✅ Entidades armazenadas no documento: 110 spans
[ETL-PRE] ✅ Entidades extraídas antes do chunking - chunking será entity-aware
```

### Section-Aware Chunker (Entity-Aware) - OTIMIZADO
```
[ENTITY-AWARE] ✅ Usando 110 entidades pré-extraídas (otimizado com binary search)
[ENTITY-AWARE] Evitando cortar entidade no meio - incluindo parágrafo completo
[CHUNKING] Chunking concluído: 20 chunks criados (ETL será executado após import)
```

### Outros Chunkers (Não Usam Entity-Spans)
```
[CHUNKING] Iniciando chunking para '...' (ETL=enabled)
# Não há logs de [ENTITY-AWARE] porque chunker não usa entity_spans
```

### ETL Pós-Chunking (Todos os Chunkers)
```
[ETL-POST] Verificando ETL pós-chunking: enable_etl=True, doc_uuid=present
[ETL-POST] ETL A2 habilitado - buscando chunks importados...
[ETL] ✅ 2226 chunks encontrados - executando ETL A2 (NER + Section Scope) em background
[ETL] ✅ ETL A2 concluído para 2226 chunks
```

---

## 💡 Recomendações

### Para Melhor Aproveitamento do ETL:

1. **Use Section-Aware Chunker:**
   - ✅ Aproveita `entity_spans` do ETL pré-chunking
   - ✅ Evita cortar entidades no meio
   - ✅ Melhor qualidade de chunks

2. **Outros Chunkers:**
   - ✅ ETL pré e pós funcionam normalmente
   - ⚠️ Entidades podem ser cortadas no meio dos chunks
   - 💡 Se precisar de melhor qualidade, modifique o chunker para usar `entity_spans`

---

## 🔧 Como Adicionar Suporte a Entity-Spans em Outros Chunkers

Se quiser que outro chunker também use `entity_spans`:

```python
# No método chunk() do chunker
entity_spans = []
if hasattr(document, 'meta') and document.meta:
    entity_spans = document.meta.get("entity_spans", [])

if entity_spans:
    # Usar entity_spans para evitar cortar entidades
    # Ver exemplo em section_aware_chunker.py
```

---

## 📊 Resumo por Chunker

| Chunker | ETL Pré Executado? | Usa Entity-Spans? | ETL Pós Executado? | Qualidade |
|---------|-------------------|-------------------|-------------------|-----------|
| **Section-Aware** | ✅ Sim | ✅ Sim | ✅ Sim | ⭐⭐⭐⭐⭐ |
| Token | ✅ Sim | ❌ Não | ✅ Sim | ⭐⭐⭐ |
| Sentence | ✅ Sim | ❌ Não | ✅ Sim | ⭐⭐⭐ |
| Recursive | ✅ Sim | ❌ Não | ✅ Sim | ⭐⭐⭐ |
| Semantic | ✅ Sim | ❌ Não | ✅ Sim | ⭐⭐⭐ |
| HTML | ✅ Sim | ❌ Não | ✅ Sim | ⭐⭐⭐ |
| Markdown | ✅ Sim | ❌ Não | ✅ Sim | ⭐⭐⭐ |
| Code | ✅ Sim | ❌ Não | ✅ Sim | ⭐⭐⭐ |
| JSON | ✅ Sim | ❌ Não | ✅ Sim | ⭐⭐⭐ |

---

## ✅ Conclusão

**ETL Pré-Chunking:**
- ✅ Executado para **TODOS** os chunkers quando `enable_etl=True`
- ✅ Extrai entidades do documento completo
- ✅ Apenas **Section-Aware Chunker** usa essas entidades no chunking

**ETL Pós-Chunking:**
- ✅ Executado para **TODOS** os chunkers quando `enable_etl=True`
- ✅ Processa chunks individuais após import
- ✅ Independente do chunker escolhido

**Recomendação:**
- 🎯 Use **Section-Aware Chunker** para melhor aproveitamento do ETL pré-chunking
- 🎯 Outros chunkers funcionam, mas não aproveitam `entity_spans` no chunking

---

## 🚀 Otimizações Implementadas (2025-11-05)

### Performance
- **Chunking**: 30s → 2-3s (**10-15x mais rápido**)
- **Extração**: 11.24s → 5.30s (**2.1x mais rápido**)
- **Filtragem**: 0.212ms → 0.013ms (**16x mais rápido**)

### Otimizações Técnicas
1. **Binary Search**: O(n²) → O(n log n) na filtragem de entidades
2. **Deduplicação**: Remove entidades duplicadas por posição
3. **Filtro de Tipos**: Apenas ORG + PERSON/PER (exclui LOC/GPE/MISC)
4. **Normalização**: PER (PT) → PERSON (EN) para compatibilidade entre modelos

### Resultados
- **Entidades**: 367 → 110 (71% redução)
- **Qualidade**: Entity-aware chunking mantido (não corta entidades)
- **Compatibilidade**: Funciona com modelos PT e EN do spaCy

**Ver documentação completa**: `docs/guides/CONFIGURACAO_ETL_FINAL.md`

