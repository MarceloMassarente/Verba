# Top K Pré-Rerank vs Pós-Rerank - Guia de Configuração

## 📊 Visão Geral

O sistema de retrieval do Verba funciona em duas etapas principais:

1. **Busca Inicial (Pré-Rerank)**: Recupera chunks do Weaviate baseado na query
2. **Reranking (Pós-Rerank)**: Reordena e filtra os chunks recuperados por relevância

Cada etapa tem seu próprio "top k" configurável.

---

## 🔍 Top K Pré-Rerank (Busca Inicial)

### Configurações na Interface:

#### **Limit Mode** (Dropdown)
- **Valores**: `Autocut` ou `Fixed`
- **Padrão**: `Autocut`
- **Função**: Define como o limite de chunks será aplicado na busca inicial

#### **Limit/Sensitivity** (Número)
- **Valores**: Qualquer número inteiro (ex: 1, 5, 10)
- **Padrão**: `1`
- **Função**: Controla quantos chunks são recuperados do Weaviate

### Como Funciona:

#### **Modo Autocut** (Recomendado)
```
Limit Mode = "Autocut"
Limit/Sensitivity = 1
```

- O Weaviate decide automaticamente quantos chunks recuperar
- O valor de `Limit/Sensitivity` (ex: 1) é usado como **sensibilidade**:
  - Valores menores (1-2): Mais restritivo, recupera menos chunks
  - Valores maiores (3-5): Menos restritivo, recupera mais chunks
- **Resultado típico**: 3-10 chunks recuperados (depende da relevância)

**Exemplo**:
- `Limit/Sensitivity = 1` → Pode recuperar 5-8 chunks (depende da qualidade dos matches)
- `Limit/Sensitivity = 3` → Pode recuperar 10-15 chunks (mais permissivo)

#### **Modo Fixed**
```
Limit Mode = "Fixed"
Limit/Sensitivity = 5
```

- Recupera exatamente o número especificado em `Limit/Sensitivity`
- **Resultado**: Exatamente 5 chunks (ou menos se não houver chunks suficientes)

**Exemplo**:
- `Limit/Sensitivity = 5` → Sempre recupera exatamente 5 chunks
- `Limit/Sensitivity = 10` → Sempre recupera exatamente 10 chunks

### Resumo Top K Pré-Rerank:

| Limit Mode | Limit/Sensitivity | Chunks Recuperados (Top K Pré-Rerank) |
|------------|-------------------|----------------------------------------|
| Autocut    | 1                 | ~5-8 chunks (automático)               |
| Autocut    | 3                 | ~10-15 chunks (automático)             |
| Fixed      | 5                 | Exatamente 5 chunks                    |
| Fixed      | 10                | Exatamente 10 chunks                   |

---

## 🎯 Top K Pós-Rerank (Após Reranking)

### Configuração na Interface:

#### **Reranker Top K** (Número) - **NOVO!**
- **Valores**: Qualquer número inteiro (ex: 0, 5, 10)
- **Padrão**: `5`
- **Função**: Controla quantos chunks passam pelo reranking e são retornados

### Como Funciona:

#### **Valor > 0** (Filtragem)
```
Reranker Top K = 5
```

- Rerankea todos os chunks recuperados (pré-rerank)
- Retorna apenas os **top 5** mais relevantes após reranking
- **Resultado**: Máximo de 5 chunks (ou menos se houver menos chunks recuperados)

**Exemplo**:
- 10 chunks recuperados (pré-rerank) → Rerankea todos → Retorna top 5
- 3 chunks recuperados (pré-rerank) → Rerankea todos → Retorna todos os 3

#### **Valor = 0** (Sem Filtragem)
```
Reranker Top K = 0
```

- Rerankea todos os chunks recuperados (pré-rerank)
- Retorna **todos** os chunks rerankeados (apenas reordenados)
- **Resultado**: Todos os chunks recuperados, mas em ordem de relevância melhorada

**Exemplo**:
- 10 chunks recuperados (pré-rerank) → Rerankea todos → Retorna todos os 10 (reordenados)

### Resumo Top K Pós-Rerank:

| Reranker Top K | Chunks Recuperados | Chunks Retornados (Top K Pós-Rerank) |
|----------------|-------------------|--------------------------------------|
| 0              | 10                | 10 chunks (todos, reordenados)       |
| 5              | 10                | 5 chunks (top 5)                     |
| 5              | 3                 | 3 chunks (todos, pois há menos)     |
| 10             | 15                | 10 chunks (top 10)                   |

---

## 🔄 Fluxo Completo: Exemplo Prático

### Cenário 1: Configuração Conservadora
```
Limit Mode: Autocut
Limit/Sensitivity: 1
Reranker Top K: 5
```

**Fluxo**:
1. **Busca Inicial**: Weaviate recupera ~5-8 chunks (Autocut com sensibilidade 1)
2. **Reranking**: Rerankea todos os ~5-8 chunks recuperados
3. **Resultado Final**: Retorna top 5 chunks mais relevantes

**Total**: ~5 chunks finais

---

### Cenário 2: Configuração Permissiva
```
Limit Mode: Fixed
Limit/Sensitivity: 10
Reranker Top K: 0
```

**Fluxo**:
1. **Busca Inicial**: Weaviate recupera exatamente 10 chunks (Fixed)
2. **Reranking**: Rerankea todos os 10 chunks
3. **Resultado Final**: Retorna todos os 10 chunks (reordenados por relevância)

**Total**: 10 chunks finais

---

### Cenário 3: Configuração Balanceada
```
Limit Mode: Autocut
Limit/Sensitivity: 2
Reranker Top K: 5
```

**Fluxo**:
1. **Busca Inicial**: Weaviate recupera ~7-12 chunks (Autocut com sensibilidade 2)
2. **Reranking**: Rerankea todos os ~7-12 chunks recuperados
3. **Resultado Final**: Retorna top 5 chunks mais relevantes

**Total**: 5 chunks finais

---

## 📋 Tabela de Referência Rápida

| Configuração | Controla | Quando Usar |
|--------------|---------|-------------|
| **Limit Mode** | Como aplicar limite na busca | Autocut: quando quer flexibilidade<br>Fixed: quando quer número exato |
| **Limit/Sensitivity** | Quantos chunks recuperar (pré-rerank) | Valores baixos (1-2): queries específicas<br>Valores altos (5+): queries amplas |
| **Reranker Top K** | Quantos chunks retornar (pós-rerank) | 0: quer todos os chunks rerankeados<br>5-10: quer apenas os mais relevantes |

---

## ⚠️ Pontos Importantes

### 1. **Limit/Sensitivity ≠ Reranker Top K**
- **Limit/Sensitivity**: Controla busca inicial (pré-rerank)
- **Reranker Top K**: Controla resultado final (pós-rerank)
- São **independentes** e servem propósitos diferentes

### 2. **Reranker Top K não pode ser maior que chunks recuperados**
- Se recuperar 5 chunks (pré-rerank) e `Reranker Top K = 10`
- Resultado: 5 chunks (não pode retornar mais do que foi recuperado)

### 3. **Reranker sempre rerankea todos os chunks recuperados**
- Mesmo que `Reranker Top K = 5`, o reranker processa todos os chunks
- Apenas retorna os top 5 após reranking

### 4. **Modo Autocut é mais inteligente**
- Adapta-se automaticamente à qualidade dos resultados
- Pode recuperar mais chunks se a relevância for alta
- Recomendado para a maioria dos casos

---

## 🎯 Recomendações

### Para Queries Específicas (ex: "Nine Dragons capacity")
```
Limit Mode: Autocut
Limit/Sensitivity: 1
Reranker Top K: 5
```
- Recupera poucos chunks altamente relevantes
- Rerankea e retorna top 5

### Para Queries Amplas (ex: "oportunidades de revisão tarifária")
```
Limit Mode: Autocut
Limit/Sensitivity: 2-3
Reranker Top K: 5-10
```
- Recupera mais chunks para ter contexto amplo
- Rerankea e retorna top 5-10 mais relevantes

### Para Máximo Contexto
```
Limit Mode: Fixed
Limit/Sensitivity: 10
Reranker Top K: 0
```
- Recupera exatamente 10 chunks
- Rerankea todos e retorna todos (reordenados)

---

## 📝 Notas Técnicas

- **Top K Pré-Rerank**: Implementado em `weaviate_manager.hybrid_chunks()` ou `hybrid_chunks_with_filter()`
- **Top K Pós-Rerank**: Implementado em `reranker.process_chunks()` com `config={"top_k": ...}`
- O reranker suporta múltiplos providers e estratégias:
  - **Metadata Reranker** (sempre disponível): Metadata matching (40%), Keyword matching (30%), Content length (10%)
  - **Haystack Reranker** (opcional): CrossEncoderRanker local usando modelos pré-treinados
  - **Cohere Reranker** (opcional): API de reranking multilíngue de alta qualidade
  - **Jina Reranker** (opcional): API de reranking rápida
  - **VoyageAI Reranker** (opcional): API de reranking de alta qualidade
  - **Modos de combinação**: Cascade (sequencial), Parallel (paralelo com RRF), Hybrid (híbrido)
  
Para mais detalhes, consulte: `verba_extensions/plugins/RERANKER_README.md`

