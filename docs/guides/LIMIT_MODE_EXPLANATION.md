# Limit Mode e Limit/Sensitivity - Como Afetam o Entity-Aware Retriever

## Visão Geral

O Entity-Aware Retriever usa dois parâmetros principais para controlar quantos chunks são recuperados:

1. **Limit Mode** (Autocut / Fixed) - Controla COMO a busca inicial limita os resultados
2. **Limit/Sensitivity** - Valor numérico que funciona diferente dependendo do modo
3. **Reranker Top K** - Controla quantos chunks são retornados APÓS o reranking (não aparece na interface atualmente)

## Como Funciona

### 1. Busca Inicial no Weaviate

A busca inicial no Weaviate é controlada por `Limit Mode` e `Limit/Sensitivity`:

#### **Autocut Mode** (Recomendado)
- Usa `auto_limit` no Weaviate
- O Weaviate decide automaticamente quantos chunks retornar baseado na relevância
- `Limit/Sensitivity` funciona como **sensibilidade**:
  - Valor **baixo (1-2)**: Mais restritivo, retorna apenas chunks muito relevantes
  - Valor **alto (5-10)**: Menos restritivo, retorna mais chunks mesmo com relevância menor
- **Exemplo**: Com `Limit/Sensitivity=1` e `Autocut`, o Weaviate pode retornar 1-5 chunks dependendo da relevância

#### **Fixed Mode**
- Usa `limit` fixo no Weaviate
- Retorna exatamente o número especificado em `Limit/Sensitivity`
- **Exemplo**: Com `Limit/Sensitivity=5` e `Fixed`, sempre retorna exatamente 5 chunks

### 2. Reranking

Após a busca inicial, os chunks são rerankeados:

- O reranker recebe **todos os chunks** recuperados na busca inicial
- O reranker reordena os chunks por relevância
- `Reranker Top K` controla quantos chunks são retornados **após** o reranking
- **IMPORTANTE**: O reranker só pode retornar chunks que foram recuperados na busca inicial

### 3. Fluxo Completo

```
Query do Usuário
    ↓
Busca Inicial (Weaviate)
    ├─ Limit Mode: Autocut/Fixed
    ├─ Limit/Sensitivity: 1-10
    └─ Retorna: N chunks (ex: 5 chunks)
    ↓
Reranking
    ├─ Recebe: N chunks da busca inicial
    ├─ Reordena por relevância
    ├─ Reranker Top K: 5 (padrão)
    └─ Retorna: min(N, Reranker Top K) chunks (ex: 5 chunks)
    ↓
Contexto para LLM
```

## Problema Atual

### Por que apenas 1 chunk está sendo retornado?

Com a configuração atual:
- `Limit Mode`: Autocut
- `Limit/Sensitivity`: 1
- `Reranker Top K`: 5 (padrão, mas não visível na interface)

**O que acontece:**
1. Busca inicial com `Autocut` e `Limit/Sensitivity=1` pode retornar poucos chunks (1-3)
2. Reranker recebe esses poucos chunks
3. Reranker retorna `min(chunks_recuperados, Reranker Top K)`
4. Se apenas 1 chunk foi recuperado, o reranker só pode retornar 1 chunk

### Solução

Para obter mais chunks:

1. **Aumentar `Limit/Sensitivity`**:
   - Com `Autocut`: Aumentar para 3-5 para buscar mais chunks
   - Com `Fixed`: Aumentar para 5-10 para garantir mais chunks

2. **Verificar `Reranker Top K`**:
   - Atualmente não aparece na interface
   - Valor padrão é 5
   - Pode ser ajustado no código (linha 84-89 de `entity_aware_retriever.py`)

## Recomendações

### Para Queries Gerais (sem entidades)
- `Limit Mode`: Autocut
- `Limit/Sensitivity`: 3-5
- `Reranker Top K`: 5 (padrão)

### Para Queries com Entidades (filtros aplicados)
- `Limit Mode`: Fixed
- `Limit/Sensitivity`: 5-10
- `Reranker Top K`: 5-10

### Para Queries Muito Específicas
- `Limit Mode`: Autocut
- `Limit/Sensitivity`: 1-2
- `Reranker Top K`: 3-5

## Próximos Passos

1. **Adicionar `Reranker Top K` à interface** para permitir configuração explícita
2. **Melhorar descrição** de `Limit/Sensitivity` para explicar diferença entre Autocut e Fixed
3. **Adicionar tooltips** explicando cada parâmetro

