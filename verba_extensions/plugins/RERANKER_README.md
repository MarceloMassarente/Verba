# Plugin de Reranker Multi-Provider

Plugin de reranking avançado para o Verba com suporte a múltiplos providers e combinação de estratégias.

## Visão Geral

O plugin de reranker melhora a relevância dos resultados de busca aplicando técnicas de reranking após a recuperação inicial. Suporta múltiplos providers (Metadata, Haystack, Cohere, Jina, VoyageAI) e permite combinar estratégias em diferentes modos.

## Providers Disponíveis

### 1. Metadata Reranker (Sempre Disponível)

Reranking baseado em metadata enriquecido e keywords. Não requer dependências externas.

**Características:**
- Usa metadata enriquecido (empresas, tópicos, keywords)
- Matching de keywords
- Score baseado em tamanho do chunk (prefere chunks médios)

**Quando usar:**
- Quando você precisa de reranking rápido sem dependências
- Quando metadata enriquecido está disponível
- Como base para combinação com outros providers

### 2. Haystack Reranker (Local)

Reranking usando CrossEncoderRanker do Haystack. Requer `haystack-ai` instalado.

**Instalação:**
```bash
pip install haystack-ai
```

**Modelos disponíveis:**
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (padrão, mais rápido)
- `cross-encoder/ms-marco-MiniLM-L-12-v2` (mais preciso, mais lento)
- `cross-encoder/ms-marco-electra-base` (mais preciso, mais lento)

**Quando usar:**
- Quando você precisa de reranking preciso sem custos de API
- Quando você tem GPU disponível (opcional, funciona em CPU)
- Para combinar com outros providers em modo Hybrid

### 3. Cohere Reranker (API)

Reranking usando Cohere Rerank API. Requer `COHERE_API_KEY` configurada.

**Configuração:**
```bash
export COHERE_API_KEY="sua-chave-aqui"
```

Ou configure via interface do Verba.

**Modelos disponíveis:**
- `rerank-english-v3.0` (inglês)
- `rerank-multilingual-v3.0` (multilíngue)

**Quando usar:**
- Quando você precisa de reranking de alta qualidade
- Para queries multilíngues
- Quando você tem orçamento para APIs

**Limitações:**
- Até 100 documentos por request
- Requer conexão com internet
- Custo por request

### 4. Jina Reranker (API)

Reranking usando Jina Rerank API. Requer `JINA_API_KEY` configurada.

**Configuração:**
```bash
export JINA_API_KEY="sua-chave-aqui"
```

**Quando usar:**
- Quando você precisa de reranking rápido via API
- Para queries multilíngues

### 5. VoyageAI Reranker (API)

Reranking usando VoyageAI Rerank API. Requer `VOYAGE_API_KEY` configurada.

**Configuração:**
```bash
export VOYAGE_API_KEY="sua-chave-aqui"
```

**Quando usar:**
- Quando você precisa de reranking de alta qualidade
- Para queries multilíngues

## Modos de Combinação

### Cascade (Sequencial)

Aplica rerankers sequencialmente, refinando resultados a cada etapa.

**Fluxo:**
1. Metadata Reranker (se habilitado)
2. Haystack Reranker (se habilitado)
3. Cohere Reranker (se habilitado)
4. Jina Reranker (se habilitado)
5. VoyageAI Reranker (se habilitado)

**Quando usar:**
- Quando você quer refinar resultados progressivamente
- Quando você tem múltiplos providers disponíveis
- Para máxima precisão (mais lento)

**Exemplo:**
```
Metadata → Haystack → Cohere
```

### Parallel (Paralelo)

Aplica múltiplos rerankers em paralelo e combina scores usando RRF (Reciprocal Rank Fusion).

**Fluxo:**
1. Executa todos os rerankers habilitados simultaneamente
2. Combina scores usando RRF
3. Retorna top_k chunks ordenados por score combinado

**Quando usar:**
- Quando você quer aproveitar múltiplos providers simultaneamente
- Para melhorar robustez (um provider pode compensar falhas de outro)
- Quando você tem recursos suficientes para executar em paralelo

**Exemplo:**
```
Metadata + Haystack + Cohere (todos em paralelo) → RRF → Top K
```

### Hybrid (Híbrido)

Combina cascade e parallel: aplica alguns rerankers em paralelo, depois outros em cascade.

**Fluxo:**
1. Fase 1: Metadata + Haystack em paralelo (se ambos habilitados)
2. Fase 2: APIs (Cohere, Jina, VoyageAI) em cascade

**Quando usar:**
- Quando você quer combinar velocidade (paralelo) com precisão (cascade)
- Para otimizar custos de API (aplica APIs apenas nos melhores resultados)
- Para melhor balance entre performance e qualidade

**Exemplo:**
```
(Metadata + Haystack em paralelo) → Cohere → Top K
```

## Configuração

### Via Interface do Verba

1. Acesse as configurações do Retriever
2. Configure as opções do Reranker:
   - **Reranker Provider**: Selecione o provider ou "Combined"
   - **Enable Metadata Reranker**: Ativar/desativar metadata reranker
   - **Enable Haystack Reranker**: Ativar/desativar Haystack (requer haystack-ai)
   - **Enable Cohere Reranker**: Ativar/desativar Cohere (requer COHERE_API_KEY)
   - **Enable Jina Reranker**: Ativar/desativar Jina (requer JINA_API_KEY)
   - **Enable VoyageAI Reranker**: Ativar/desativar VoyageAI (requer VOYAGE_API_KEY)
   - **Reranker Mode**: Cascade, Parallel ou Hybrid
   - **Top K**: Número de chunks a retornar após reranking

### Via Variáveis de Ambiente

```bash
# Cohere
export COHERE_API_KEY="sua-chave"
export COHERE_BASE_URL="https://api.cohere.com/v1"  # Opcional

# Jina
export JINA_API_KEY="sua-chave"
export JINA_BASE_URL="https://api.jina.ai/v1"  # Opcional

# VoyageAI
export VOYAGE_API_KEY="sua-chave"
export VOYAGE_BASE_URL="https://api.voyageai.com/v1"  # Opcional
```

## Exemplos de Uso

### Exemplo 1: Metadata Only (Padrão)

```python
# Configuração mínima - usa apenas metadata
config = {
    "Reranker Provider": "Metadata Only",
    "Top K": 5
}
```

### Exemplo 2: Haystack Local

```python
# Requer haystack-ai instalado
config = {
    "Reranker Provider": "Haystack",
    "Haystack Model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "Top K": 5
}
```

### Exemplo 3: Cohere API

```python
# Requer COHERE_API_KEY configurada
config = {
    "Reranker Provider": "Cohere",
    "Cohere Model": "rerank-english-v3.0",
    "Top K": 5
}
```

### Exemplo 4: Combinação Hybrid

```python
# Combina metadata + haystack em paralelo, depois Cohere
config = {
    "Reranker Provider": "Combined",
    "Enable Metadata Reranker": True,
    "Enable Haystack Reranker": True,
    "Enable Cohere Reranker": True,
    "Reranker Mode": "Hybrid",
    "Top K": 5
}
```

## Performance

### Latência Estimada

| Provider | Latência (100 chunks) | Requisitos |
|----------|----------------------|------------|
| Metadata | ~10ms | CPU apenas |
| Haystack | ~500ms (CPU) / ~50ms (GPU) | CPU/GPU, haystack-ai |
| Cohere | ~200-500ms | Internet, API key |
| Jina | ~200-500ms | Internet, API key |
| VoyageAI | ~200-500ms | Internet, API key |

### Custo Estimado (APIs)

- **Cohere**: ~$0.001 por 1000 documentos rerankeados
- **Jina**: Verificar preços atuais
- **VoyageAI**: Verificar preços atuais

## Troubleshooting

### Haystack não está disponível

**Problema:** "Haystack não disponível (haystack-ai não instalado)"

**Solução:**
```bash
pip install haystack-ai
```

### API Key não configurada

**Problema:** "Cohere API key não configurada"

**Solução:**
1. Configure a variável de ambiente: `export COHERE_API_KEY="sua-chave"`
2. Ou configure via interface do Verba

### Reranker retorna menos chunks que esperado

**Problema:** Reranker retorna menos chunks que o `top_k` configurado

**Possíveis causas:**
- Menos chunks disponíveis que `top_k`
- Erro em um provider (fallback para menos chunks)
- Filtros muito restritivos

**Solução:**
- Verifique logs para erros
- Aumente `top_k` se necessário
- Verifique se há chunks suficientes antes do reranking

### Performance lenta

**Problema:** Reranking está muito lento

**Soluções:**
- Use Metadata Only para máxima velocidade
- Reduza `top_k` se possível
- Use Haystack em GPU se disponível
- Considere usar apenas um provider ao invés de Combined

## Compatibilidade

- **Backward Compatible**: O reranker atual (Metadata Only) continua funcionando
- **API Compatible**: `process_chunks()`, `process_batch()` mantêm mesma assinatura
- **Config Compatible**: Configurações antigas continuam funcionando

## Integração

O reranker é automaticamente integrado com o `EntityAwareRetriever`. Não é necessário fazer mudanças no código para usar o reranker - apenas configure as opções na interface do Verba.

## Referências

- [Haystack Documentation](https://docs.haystack.deepset.ai/)
- [Cohere Rerank API](https://docs.cohere.com/docs/reranking)
- [Jina Rerank API](https://jina.ai/reranker/)
- [VoyageAI Documentation](https://www.voyageai.com/docs)

