# Dynamic Reranker vs Reranker Plugin

## Resumo

O Verba tem **dois sistemas de reranking** que se complementam:

| Sistema | Propósito | Custo | Latência |
|---------|-----------|-------|----------|
| **RerankerPlugin** | Reranking semântico via APIs | Pode ter custo | Depende de API |
| **DynamicReranker** | Enriquecimento de scores com metadados | Zero custo | Muito rápido |

## RerankerPlugin (Existente)

**Localização:** `verba_extensions/plugins/reranker.py`

**O que faz:**
- Reranking semântico usando modelos de cross-encoder
- Suporta múltiplos providers: Metadata, Haystack, Cohere, Jina, VoyageAI, ContextualAI
- Modos de combinação: Cascade, Parallel, Hybrid

**Quando usar:**
- Quando precisar de alta qualidade de reranking
- Quando tiver API keys disponíveis
- Para queries complexas que precisam de compreensão semântica profunda

## DynamicReranker (RAG 2.0 Enhancement)

**Localização:** `verba_extensions/plugins/dynamic_reranker.py`

**O que faz:**
- Enriquece scores de chunks com dimensões adicionais:
  - Similaridade (score original)
  - Recência (chunks mais recentes)
  - Frequência de entidades (chunks com mais entidades)
  - Autoridade do documento (opcional)

**Quando usar:**
- Como pré-processador antes do RerankerPlugin
- Quando não tiver APIs disponíveis (alternativa leve)
- Para priorizar documentos recentes ou com mais entidades

## Pipeline Recomendado

```
Query → Retrieve → DynamicReranker (enriquece) → RerankerPlugin (refina) → Resposta
```

1. **Retrieve**: Busca chunks no Weaviate
2. **DynamicReranker**: Adiciona scores de recência/entidades (opcional, zero custo)
3. **RerankerPlugin**: Reranking semântico final (opcional, pode ter custo)

## Configuração

### Ativar DynamicReranker

Na interface do Verba (Retriever Settings):

```
Enable Dynamic Reranking: true
Reranking Recency Weight: 0.15
Reranking Entity Weight: 0.15
```

Isso significa:
- 70% do score vem da similaridade original
- 15% vem da recência
- 15% vem da frequência de entidades

### Ativar RerankerPlugin

Na interface do Verba (Retriever Settings > Reranker):

```
Reranker Provider: ContextualAI (ou outro)
Enable Metadata Reranker: true
Enable Haystack Reranker: true (se disponível)
```

## Exemplo de Fluxo

```
Query: "Quais foram as inovações da Apple em 2024?"

1. Retrieve retorna 20 chunks
   - Chunk A: score=0.85, date=2024-01, entities=["Apple", "iPhone"]
   - Chunk B: score=0.82, date=2023-06, entities=["Apple"]
   - Chunk C: score=0.80, date=2024-03, entities=["Apple", "Vision Pro", "AI"]

2. DynamicReranker enriquece scores:
   - Chunk A: combined_score=0.78 (recente, 2 entidades)
   - Chunk B: combined_score=0.65 (antigo, 1 entidade)
   - Chunk C: combined_score=0.82 (recente, 3 entidades) ← sobe!

3. RerankerPlugin refina semanticamente:
   - Chunk C: final_score=0.91 (mais relevante para "inovações 2024")
   - Chunk A: final_score=0.85
   - Chunk B: final_score=0.72

4. Resultado: [Chunk C, Chunk A, Chunk B]
```

## Benefícios da Combinação

1. **Melhor recall**: DynamicReranker prioriza chunks recentes/ricos
2. **Melhor precision**: RerankerPlugin refina semanticamente
3. **Flexibilidade**: Pode usar um ou ambos
4. **Custo otimizado**: DynamicReranker é gratuito



