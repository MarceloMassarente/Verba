# Presets Recomendados para Verba RAG

Este guia apresenta configurações otimizadas para diferentes casos de uso.

---

## 1. Presets de Retriever (EntityAwareRetriever)

### 1.1 Preset: Produção Balanceada

**Caso de uso:** Ambiente de produção com boa qualidade e latência aceitável.

```yaml
# Busca Fundamental
Search Mode: Hybrid Search
Alpha: 0.6  # 60% vector, 40% keyword
Limit Mode: Autocut
Limit/Sensitivity: 1
Reranker Top K: 5

# Filtros
Enable Entity Filter: true
Entity Filter Mode: adaptive
Enable Temporal Filter: true

# Query Processing
Enable Query Rewriting: true
Enable Query Builder: true

# RAG 2.0 (Opcionais)
Enable Intelligent Cache: true
Cache Similarity Threshold: 0.85
Enable Dynamic Reranking: false  # Desabilitado para menor latência
```

**Benefícios:**
- ✅ Boa qualidade de resultados
- ✅ Cache reduz latência em queries repetidas
- ✅ Entity filtering evita contaminação
- ✅ Latência média: 500-1000ms

---

### 1.2 Preset: Máxima Qualidade

**Caso de uso:** Quando precisão é mais importante que latência.

```yaml
# Busca Fundamental
Search Mode: Hybrid Search
Alpha: 0.5  # Balanceado
Limit Mode: Autocut
Limit/Sensitivity: 2  # Mais sensível
Reranker Top K: 10  # Mais chunks para reranking

# Filtros
Enable Entity Filter: true
Entity Filter Mode: strict
Enable Temporal Filter: true

# Query Processing
Enable Query Rewriting: true
Enable Query Builder: true

# RAG 2.0
Enable Intelligent Cache: true
Cache Similarity Threshold: 0.90  # Threshold mais alto
Enable Dynamic Reranking: true
Reranking Recency Weight: 0.15
Reranking Entity Weight: 0.15
```

**Benefícios:**
- ✅ Máxima precisão
- ✅ Multi-dimensional reranking
- ⚠️ Latência maior: 1000-2000ms

---

### 1.3 Preset: Baixa Latência

**Caso de uso:** Quando velocidade é crítica (chatbots, real-time).

```yaml
# Busca Fundamental
Search Mode: Hybrid Search
Alpha: 0.7  # Mais vector (mais rápido)
Limit Mode: Fixed
Limit/Sensitivity: 3  # Menos resultados
Reranker Top K: 3

# Filtros
Enable Entity Filter: false  # Desabilitado para velocidade
Enable Temporal Filter: false

# Query Processing
Enable Query Rewriting: false  # Desabilitado
Enable Query Builder: false

# RAG 2.0
Enable Intelligent Cache: true  # Cache é essencial
Cache Similarity Threshold: 0.80  # Threshold mais baixo = mais hits
Enable Dynamic Reranking: false
```

**Benefícios:**
- ✅ Latência mínima: 200-500ms
- ✅ Cache agressivo
- ⚠️ Menor precisão

---

### 1.4 Preset: Documentos Técnicos

**Caso de uso:** Busca em documentação técnica, manuais, whitepapers.

```yaml
# Busca Fundamental
Search Mode: Hybrid Search
Alpha: 0.4  # Mais keyword (termos técnicos)
Limit Mode: Autocut
Limit/Sensitivity: 1
Reranker Top K: 7

# Filtros
Enable Entity Filter: true
Entity Filter Mode: adaptive
Enable Temporal Filter: false  # Docs técnicos não mudam muito

# Query Processing
Enable Query Rewriting: true
Enable Query Builder: true

# RAG 2.0
Enable Intelligent Cache: true
Cache Similarity Threshold: 0.85
Enable Dynamic Reranking: true
Reranking Recency Weight: 0.05  # Recência menos importante
Reranking Entity Weight: 0.25  # Entidades mais importantes
```

**Benefícios:**
- ✅ Bom para termos técnicos específicos
- ✅ Prioriza chunks com mais entidades técnicas
- ✅ Cache longo (docs não mudam)

---

### 1.5 Preset: Notícias e Conteúdo Temporal

**Caso de uso:** Busca em notícias, relatórios, conteúdo datado.

```yaml
# Busca Fundamental
Search Mode: Hybrid Search
Alpha: 0.6
Limit Mode: Autocut
Limit/Sensitivity: 1
Reranker Top K: 5

# Filtros
Enable Entity Filter: true
Entity Filter Mode: adaptive
Enable Temporal Filter: true
Date Field Name: chunk_date

# Query Processing
Enable Query Rewriting: true
Enable Query Builder: true

# RAG 2.0
Enable Intelligent Cache: true
Cache Similarity Threshold: 0.85
Enable Dynamic Reranking: true
Reranking Recency Weight: 0.30  # Recência muito importante
Reranking Entity Weight: 0.10
```

**Benefícios:**
- ✅ Prioriza conteúdo recente
- ✅ Filtro temporal funciona bem
- ⚠️ Cache TTL deve ser curto para notícias

---

## 2. Presets de Reranking (RerankerPlugin)

### 2.1 Preset: production

**Descrição:** ContextualAI apenas (rápido e eficiente)

```yaml
Reranker Provider: ContextualAI
ContextualAI Model: ctxl-rerank-v2-instruct-multilingual
Top K: 5
```

**Requisitos:** `CONTEXTUAL_API_KEY`  
**Latência:** ~500ms  
**Qualidade:** Alta

---

### 2.2 Preset: max_quality

**Descrição:** Metadata + Haystack + ContextualAI (melhor precisão)

```yaml
Reranker Provider: Combined
Reranker Mode: Hybrid
Enable Metadata Reranker: true
Enable Haystack Reranker: true
Enable ContextualAI Reranker: true
Top K: 5
```

**Requisitos:** `haystack-ai`, `CONTEXTUAL_API_KEY`  
**Latência:** ~1.5s  
**Qualidade:** Muito Alta

---

### 2.3 Preset: local_only

**Descrição:** Metadata + Haystack (sem APIs, local apenas)

```yaml
Reranker Provider: Combined
Reranker Mode: Parallel
Enable Metadata Reranker: true
Enable Haystack Reranker: true
Top K: 5
```

**Requisitos:** `haystack-ai`  
**Latência:** ~500ms  
**Qualidade:** Alta

---

## 3. Presets de Generator

### 3.1 Preset: Padrão

```yaml
Enable Iterative Search: false
Max Iterative Searches: 3
```

### 3.2 Preset: RAG 2.0 Experimental

```yaml
Enable Iterative Search: true
Max Iterative Searches: 3
```

**Nota:** Requer modelo que gere tokens `[SEARCH: query]`.

---

## 4. Combinações Recomendadas

### 4.1 Setup Completo de Produção

```
Retriever: Produção Balanceada
Reranker: production
Generator: Padrão
```

**Latência total:** 1-2s  
**Qualidade:** Alta  
**Custo:** Médio (APIs de reranking)

---

### 4.2 Setup Local (Sem APIs)

```
Retriever: Baixa Latência
Reranker: local_only
Generator: Padrão
```

**Latência total:** 500ms-1s  
**Qualidade:** Boa  
**Custo:** Zero (local apenas)

---

### 4.3 Setup Máxima Qualidade

```
Retriever: Máxima Qualidade
Reranker: max_quality
Generator: Padrão
```

**Latência total:** 2-4s  
**Qualidade:** Máxima  
**Custo:** Alto (múltiplas APIs)

---

## 5. Tabela de Decisão Rápida

| Prioridade | Retriever | Reranker | Cache | Latência |
|------------|-----------|----------|-------|----------|
| Velocidade | Baixa Latência | local_only | Agressivo | <500ms |
| Balanceado | Produção Balanceada | production | Normal | 1-2s |
| Qualidade | Máxima Qualidade | max_quality | Normal | 2-4s |
| Técnico | Documentos Técnicos | production | Longo | 1-2s |
| Temporal | Notícias | production | Curto | 1-2s |

---

## 6. Como Aplicar Presets

### Via UI (Recomendado)

1. Acesse **Settings** no Verba
2. Navegue até **Retriever Settings**
3. Ajuste cada configuração conforme o preset desejado
4. Clique em **Save**

### Via Código

```python
# Exemplo: Aplicar preset de produção
retriever_config = {
    "Search Mode": {"value": "Hybrid Search"},
    "Alpha": {"value": "0.6"},
    "Enable Entity Filter": {"value": True},
    "Enable Intelligent Cache": {"value": True},
    # ... outras configurações
}
```

---

## 7. Monitoramento de Performance

### Métricas a Observar

| Métrica | Bom | Atenção | Crítico |
|---------|-----|---------|---------|
| Latência p50 | <1s | 1-2s | >2s |
| Latência p95 | <2s | 2-4s | >4s |
| Cache Hit Rate | >30% | 10-30% | <10% |
| Reranking Time | <500ms | 500ms-1s | >1s |

### Logs Importantes

```bash
# Verificar cache hits
grep "Intelligent Cache HIT" logs/verba.log

# Verificar fallbacks
grep "Fallback" logs/verba.log

# Verificar latência
grep "took=" logs/verba.log
```

---

## 8. Troubleshooting

### Cache Hit Rate Baixo

1. Reduzir `Cache Similarity Threshold` (ex: 0.80)
2. Verificar se queries são muito variadas
3. Aumentar TTL do cache

### Latência Alta

1. Desabilitar `Enable Query Rewriting`
2. Reduzir `Reranker Top K`
3. Usar preset `Baixa Latência`

### Resultados Irrelevantes

1. Habilitar `Enable Entity Filter`
2. Aumentar `Reranker Top K`
3. Usar preset `Máxima Qualidade`

### Entity Filter Não Funciona

1. Verificar se chunks têm `entities_local_ids`
2. Verificar se ETL pré-chunking foi executado
3. Verificar logs: "Schema não tem propriedades ETL"

