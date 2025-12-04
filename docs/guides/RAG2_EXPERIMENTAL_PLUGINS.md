# Plugins Experimentais RAG 2.0

Este documento descreve plugins experimentais baseados em conceitos do RAG 2.0 que ainda estão em fase de desenvolvimento e teste.

## Status: Experimental

Estes plugins são **experimentais** e podem:
- Ter APIs instáveis
- Requerer configuração especial
- Não estar totalmente integrados no fluxo principal
- Ter bugs conhecidos ou limitações

**Use com cautela em produção.**

---

## Plugins Experimentais

### 1. Intelligent Cache (`intelligent_cache.py`)

**Status:** Experimental

**Descrição:**
Cache inteligente que reutiliza respostas de queries similares (não apenas idênticas). Usa busca por similaridade semântica para encontrar respostas de cache mesmo quando a query não é exatamente igual.

**Características:**
- Busca por similaridade semântica (não apenas match exato)
- TTL adaptativo por tipo de documento
- Estatísticas de uso
- Limpeza automática de entradas expiradas

**Uso:**
```python
from verba_extensions.plugins.intelligent_cache import IntelligentCache

cache = IntelligentCache(
    similarity_threshold=0.85,
    max_entries=1000
)
```

**Limitações:**
- Requer função de embedding para calcular similaridade
- Pode consumir memória significativa com muitas entradas
- Não está integrado automaticamente no fluxo de queries

---

### 2. Iterative Search (`iterative_search.py`)

**Status:** Experimental

**Descrição:**
Implementa busca iterativa durante a geração de resposta, simulando o comportamento do RAG 2.0 onde o modelo pode pausar a geração para buscar mais informações quando necessário.

**Conceito RAG 2.0:**
- Modelo gera texto normalmente
- Quando detecta necessidade de mais informação, emite token especial `[SEARCH: query]`
- Sistema pausa, faz nova busca, injeta contexto adicional
- Modelo continua gerando com contexto enriquecido

**Características:**
- Monitora tokens gerados em tempo real
- Detecta padrão `[SEARCH: query]` no texto
- Faz busca adicional via retriever
- Injeta novo contexto no prompt

**Limitações:**
- Requer suporte do modelo para gerar tokens `[SEARCH:]`
- Adiciona latência (cada busca = ~500ms-2s)
- Máximo de iterações configurável para evitar loops
- Não está integrado automaticamente no fluxo de geração

**Uso:**
```python
from verba_extensions.plugins.iterative_search import IterativeSearchPlugin

plugin = IterativeSearchPlugin(config=IterativeSearchConfig(
    enabled=True,
    max_iterations=3
))
```

---

### 3. Multi-Vector Searcher (`multi_vector_searcher.py`)

**Status:** Experimental

**Descrição:**
Busca inteligente em múltiplos named vectors com combinação RRF (Reciprocal Rank Fusion). Permite buscar em vetores especializados (concept_vec, sector_vec, company_vec) em paralelo e combinar resultados.

**Características:**
- Busca paralela em 2-3 vetores especializados
- Combinação com RRF (Reciprocal Rank Fusion)
- Deduplicação automática
- Reranking opcional

**Limitações:**
- Requer named vectors configurados no Weaviate
- Modo BYOV (Bring Your Own Vector) - query_vector deve ser pré-calculado
- Não está integrado automaticamente no EntityAwareRetriever

**Uso:**
```python
from verba_extensions.plugins.multi_vector_searcher import MultiVectorSearcher

searcher = MultiVectorSearcher()
results = await searcher.search_multi_vector(
    client=weaviate_client,
    collection_name="Document",
    query="inovação",
    query_vector=embedding_vector,
    vectors=["concept_vec", "sector_vec"],
    limit=50
)
```

---

## Integração Futura

Estes plugins podem ser integrados no fluxo principal no futuro:

1. **Intelligent Cache:** Integrar no QueryRewriter ou QueryBuilder para cache automático
2. **Iterative Search:** Integrar no Generator para busca iterativa durante geração
3. **Multi-Vector Searcher:** Integrar no EntityAwareRetriever como estratégia alternativa

---

## Contribuindo

Se você quiser ajudar a integrar ou melhorar estes plugins experimentais:

1. Teste em ambiente de desenvolvimento
2. Documente bugs e limitações encontradas
3. Proponha melhorias via issues ou PRs
4. Considere integrar no fluxo principal se estiver estável

---

## Referências

- [RAG 2.0 Paper](https://arxiv.org/abs/2405.21040)
- [Reciprocal Rank Fusion](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)

