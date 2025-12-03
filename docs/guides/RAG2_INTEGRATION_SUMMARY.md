# RAG 2.0 Integration Summary

## Visão Geral do Sistema

O Verba implementa uma arquitetura RAG avançada com múltiplos plugins que trabalham em conjunto:

```
Query → [Query Processing] → [Retrieval] → [Reranking] → [Generation] → Response
```

## Plugins por Fase

### 1. Query Processing (Antes da Busca)

| Plugin | Arquivo | Propósito | Status |
|--------|---------|-----------|--------|
| **AdaptiveEntropyAnalyzer** | `adaptive_entropy.py` | Analisa entropia para decidir força do rewrite | ✅ Existente |
| **QueryRewriterPlugin** | `query_rewriter.py` | Reescrita semântica via LLM | ✅ Existente + Melhorado |
| **QueryBuilderPlugin** | `query_builder.py` | Construção de queries com schema awareness | ✅ Existente |
| **QueryExpanderPlugin** | `query_expander.py` | Expansão para múltiplas variações | ✅ Existente |
| **BilingualFilterPlugin** | `bilingual_filter.py` | Filtro por idioma | ✅ Existente |
| **TemporalFilterPlugin** | `temporal_filter.py` | Filtro por data | ✅ Existente |

### 2. Retrieval (Busca)

| Plugin | Arquivo | Propósito | Status |
|--------|---------|-----------|--------|
| **EntityAwareRetriever** | `entity_aware_retriever.py` | Retriever principal com filtros | ✅ Existente |
| **IntelligentCache** | `intelligent_cache.py` | Cache por similaridade semântica | ✅ **NOVO RAG 2.0** |
| **MultiVectorSearcher** | `multi_vector_searcher.py` | Busca em múltiplos vetores | ✅ Existente |

### 3. Reranking (Pós-Busca)

| Plugin | Arquivo | Propósito | Status |
|--------|---------|-----------|--------|
| **DynamicReranker** | `dynamic_reranker.py` | Enriquecimento de scores (recency, entities) | ✅ **NOVO RAG 2.0** |
| **RerankerPlugin** | `reranker.py` | Reranking semântico multi-provider | ✅ Existente |

### 4. Generation (Resposta)

| Plugin | Arquivo | Propósito | Status |
|--------|---------|-----------|--------|
| **IterativeSearch** | `iterative_search.py` | Busca iterativa durante geração | ✅ **NOVO RAG 2.0** |

---

## Fluxo Detalhado com RAG 2.0

```
┌─────────────────────────────────────────────────────────────────────┐
│                        QUERY PROCESSING                              │
├─────────────────────────────────────────────────────────────────────┤
│ 1. AdaptiveEntropyAnalyzer                                           │
│    └─ Calcula entropia → decide modo de rewrite                     │
│                                                                      │
│ 2. QueryRewriterPlugin (se entropy > threshold)                      │
│    └─ Reescrita leve/moderada/forte baseada em entropia             │
│                                                                      │
│ 3. BilingualFilter + TemporalFilter                                  │
│    └─ Detecta idioma e range de datas                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         RETRIEVAL                                    │
├─────────────────────────────────────────────────────────────────────┤
│ 4. IntelligentCache.get() [RAG 2.0]                                  │
│    └─ Verifica cache por similaridade (threshold 0.85)              │
│    └─ Se HIT → retorna resposta cacheada (skip busca)               │
│                                                                      │
│ 5. EntityAwareRetriever.retrieve()                                   │
│    └─ Busca híbrida (keyword + semantic)                            │
│    └─ Aplica filtros (entidades, idioma, data)                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         RERANKING                                    │
├─────────────────────────────────────────────────────────────────────┤
│ 6. DynamicReranker [RAG 2.0]                                         │
│    └─ Enriquece scores com recency + entity frequency               │
│    └─ NÃO substitui RerankerPlugin, apenas adiciona dimensões      │
│                                                                      │
│ 7. RerankerPlugin (se habilitado)                                    │
│    └─ Reranking semântico via Cohere/Jina/ContextualAI              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         POST-RETRIEVAL                               │
├─────────────────────────────────────────────────────────────────────┤
│ 8. IntelligentCache.set() [RAG 2.0]                                  │
│    └─ Armazena resposta com TTL adaptativo por tipo de documento    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Feature Flags RAG 2.0

### EntityAwareRetriever (Retrieval)

| Flag | Default | Descrição |
|------|---------|-----------|
| `Enable Intelligent Cache` | `false` | Ativa cache por similaridade |
| `Cache Similarity Threshold` | `0.85` | Threshold para cache hit |
| `Enable Dynamic Reranking` | `false` | Ativa enriquecimento de scores |
| `Reranking Recency Weight` | `0.15` | Peso da recência no score |
| `Reranking Entity Weight` | `0.15` | Peso das entidades no score |

### Generator (Generation)

| Flag | Default | Descrição |
|------|---------|-----------|
| `Enable Iterative Search` | `false` | Ativa busca iterativa durante geração |
| `Max Iterative Searches` | `3` | Máximo de buscas por geração |

---

## Compatibilidade

### ✅ Backward Compatible

- Todas as features novas são **desabilitadas por padrão**
- Sistema funciona exatamente como antes se flags não forem ativados
- Plugins novos são opcionais e não afetam código existente

### ✅ Integração com Plugins Existentes

- **DynamicReranker + RerankerPlugin**: Trabalham em sequência
  - DynamicReranker enriquece scores (local, zero custo)
  - RerankerPlugin refina semanticamente (pode ter custo de API)
  
- **IntelligentCache + QueryRewriterPlugin**: Complementares
  - Cache reutiliza respostas de queries similares
  - QueryRewriter melhora a query antes de cachear

- **AdaptiveEntropyAnalyzer**: Compartilhado
  - Usado por QueryRewriterPlugin
  - Pode ser usado por QueryBuilderPlugin

---

## Benefícios RAG 2.0

### 1. Redução de Latência
- **IntelligentCache**: Evita buscas repetidas para queries similares
- **Adaptive Rewriting**: Evita chamadas LLM desnecessárias

### 2. Melhoria de Relevância
- **DynamicReranker**: Prioriza chunks recentes e ricos em entidades
- **Multi-dimensional scoring**: Combina similaridade + recência + entidades

### 3. Redução de Custos
- **Cache**: Reutiliza respostas (menos chamadas LLM)
- **Adaptive**: Skip de rewrite quando query já é específica

### 4. Flexibilidade
- **Feature flags**: Ativa/desativa cada feature independentemente
- **Pesos configuráveis**: Ajusta importância de cada dimensão

---

## Status de Implementação

### ✅ Completo

1. **Intelligent Cache** (`intelligent_cache.py`)
   - Cache por similaridade semântica
   - TTL adaptativo por tipo de documento
   - Integrado no EntityAwareRetriever

2. **Dynamic Reranker** (`dynamic_reranker.py`)
   - Enriquecimento de scores multi-dimensional
   - Recency + Entity Frequency
   - Integrado no EntityAwareRetriever

3. **Iterative Search** (`iterative_search.py`)
   - Detecta tokens `[SEARCH: query]` durante geração
   - Integrado no VerbaManager (`generate_stream_answer_iterative`)
   - Configuração via Generator config (`Enable Iterative Search`)

4. **Adaptive Query Rewriting** (já existia, melhorado)
   - Usa `AdaptiveEntropyAnalyzer` compartilhado
   - Skip/light/moderate/strong baseado em entropia

### ⏳ Pendente

1. **Testes de Integração**
   - Testar com todas as flags desabilitadas
   - Testar com cada flag individualmente
   - Testar combinações de flags

---

## Arquivos Modificados/Criados

### Novos (RAG 2.0)
- `verba_extensions/plugins/intelligent_cache.py` ✅
- `verba_extensions/plugins/dynamic_reranker.py` ✅
- `verba_extensions/plugins/iterative_search.py` ✅

### Modificados
- `verba_extensions/plugins/entity_aware_retriever.py` ✅
  - Adicionadas configurações RAG 2.0
  - Integração com IntelligentCache e DynamicReranker

- `goldenverba/verba_manager.py` ✅
  - Adicionado método `generate_stream_answer_iterative()`
  - Suporte a busca iterativa durante geração

- `goldenverba/components/interfaces.py` ✅
  - Adicionadas configs `Enable Iterative Search` e `Max Iterative Searches` na classe Generator

- `goldenverba/server/api.py` ✅
  - WebSocket `/ws/generate_stream` verifica flag de iterative search

### Existentes (não modificados)
- `verba_extensions/plugins/adaptive_entropy.py` ✅ (já existia)
- `verba_extensions/plugins/query_rewriter.py` ✅ (já tinha adaptive mode)
- `verba_extensions/plugins/reranker.py` ✅ (continua funcionando)

