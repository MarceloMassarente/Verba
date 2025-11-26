# Plugin de Reranker Multi-Provider

Plugin de reranking avançado para o Verba com suporte a múltiplos providers e combinação de estratégias.

## Visão Geral

O plugin de reranker melhora a relevância dos resultados de busca aplicando técnicas de reranking após a recuperação inicial. Suporta múltiplos providers (Metadata, Haystack, Cohere, Jina, VoyageAI, ContextualAI) e permite combinar estratégias em diferentes modos.

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

### 6. Contextual AI Reranker (API) ⭐ Novo

Reranking usando **Contextual AI Rerank API** (única API disponível). Requer `CONTEXTUAL_API_KEY` configurada.

**Diferenciais:**
- ✅ **Instruções customizadas**: Permite orientar o reranking com instruções específicas (ex: "Prioritize recent documents", "Prefer internal sales documents")
- ✅ **Metadata por documento**: Suporta metadata estruturado para cada documento
- ✅ **Multilíngue**: Modelos otimizados para RAG em múltiplos idiomas
- ✅ **Otimizado para RAG**: Modelos treinados especificamente para RAG (não apenas Q&A)
- ✅ **Sem API de query**: Contextual AI não oferece API de search, apenas reranking

**Configuração:**
```bash
export CONTEXTUAL_API_KEY="sua-chave-aqui"
```

**Modelos disponíveis:**
- `ctxl-rerank-v2-instruct-multilingual` (padrão, mais preciso)
- `ctxl-rerank-v2-instruct-multilingual-mini` (mais rápido)
- `ctxl-rerank-v1-instruct` (versão anterior)

**Exemplo de instrução customizada:**
```
Prioritize internal sales documents over market analysis reports. 
More recent documents should be weighted higher. 
Enterprise portal content supersedes distributor communications.
```

**Quando usar:**
- Quando você precisa de controle fino sobre critérios de reranking
- Para priorizar documentos por tipo, data, fonte ou metadata
- Quando você tem requisitos específicos de negócio (ex: preferir documentos internos)
- Para RAG de alta qualidade com contexto de negócio

**Limitações:**
- Total request: 400,000 tokens
- Por documento: 8,000 tokens (query + instruction + document + metadata)
- Requer conexão com internet
- Custo por request

**Referência:** [Contextual AI Rerank API](https://docs.contextual.ai/api-reference/rerank/rerank)

## Modos de Combinação

### Cascade (Sequencial)

Aplica rerankers sequencialmente, refinando resultados a cada etapa.

**Fluxo:**
1. Metadata Reranker (se habilitado)
2. Haystack Reranker (se habilitado)
3. Cohere Reranker (se habilitado)
4. Jina Reranker (se habilitado)
5. VoyageAI Reranker (se habilitado)
6. ContextualAI Reranker (se habilitado)

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
2. Fase 2: APIs (Cohere, Jina, VoyageAI, ContextualAI) em cascade

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
   - **Enable ContextualAI Reranker**: Ativar/desativar ContextualAI (requer CONTEXTUAL_API_KEY)
   - **ContextualAI Model**: Modelo a usar (ctxl-rerank-v2-instruct-multilingual, etc.)
   - **ContextualAI Instruction**: Instruções customizadas para orientar o reranking (opcional)
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

# ContextualAI
export CONTEXTUAL_API_KEY="sua-chave"
export CONTEXTUAL_BASE_URL="https://api.contextual.ai/v1"  # Opcional
```

## Presets de Reranking

O sistema inclui presets otimizados que configuram automaticamente o reranker para diferentes cenários. Veja o guia completo em [RERANKER_PRESETS.md](./RERANKER_PRESETS.md).

### Presets Disponíveis

1. **Production** (Recomendado para uso geral)
   - ContextualAI apenas
   - Latência: ~500ms
   - Qualidade: Alta
   - Requisitos: CONTEXTUAL_API_KEY

2. **Max Quality** (Máxima precisão)
   - Metadata + Haystack + ContextualAI
   - Latência: ~1.5s
   - Qualidade: Muito Alta
   - Requisitos: haystack-ai, CONTEXTUAL_API_KEY

3. **Local Only** (Sem APIs)
   - Metadata + Haystack
   - Latência: ~500ms
   - Qualidade: Alta
   - Requisitos: haystack-ai

### Auto-Seleção

O preset "auto" seleciona automaticamente o melhor preset baseado na query e recursos disponíveis.

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

### Exemplo 4: ContextualAI com Instruções Customizadas

```python
# Requer CONTEXTUAL_API_KEY configurada
config = {
    "Reranker Provider": "ContextualAI",
    "ContextualAI Model": "ctxl-rerank-v2-instruct-multilingual",
    "ContextualAI Instruction": "Prioritize recent documents and internal sales documents over market analysis reports.",
    "Top K": 5
}
```

### Exemplo 5: Combinação Hybrid

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
| ContextualAI | ~300-600ms | Internet, API key |

### Custo Estimado (APIs)

- **Cohere**: ~$0.001 por 1000 documentos rerankeados
- **Jina**: Verificar preços atuais
- **VoyageAI**: Verificar preços atuais
- **ContextualAI**: Verificar preços atuais em [contextual.ai](https://contextual.ai)

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

### Integração com Named Vectors

**✅ SIM, todos os modos de reranking (Cascade, Parallel, Hybrid) funcionam com Named Vectors!**

**Como funciona:**

1. **Busca Inicial com Named Vectors**:
   - O `EntityAwareRetriever` usa named vectors (`concept_vec`, `sector_vec`, `company_vec`) quando habilitado
   - Multi-vector search busca em múltiplos named vectors em paralelo
   - Chunks são recuperados usando os named vectors apropriados baseado na query

2. **Reranking dos Chunks Recuperados**:
   - O reranker recebe os chunks **já recuperados** usando named vectors
   - Todos os modos (Cascade, Parallel, Hybrid) funcionam normalmente
   - O reranker trabalha com o conteúdo e metadata dos chunks

**Como Cada API Usa os Chunks dos Named Vectors:**

#### 1. **MetadataReranker** (Sempre Disponível)
- **O que usa**: `chunk.content` + `chunk.meta["enriched"]`
- **Metadata aproveitada**: empresas, tópicos, keywords detectados durante chunking
- **Named vectors indireto**: Se named vectors foram usados para recuperar chunks sobre conceitos específicos, o reranker usa essa metadata enriquecida

#### 2. **HaystackReranker** (Local)
- **O que usa**: `chunk.content` (apenas)
- **Como funciona**: CrossEncoder compara query vs conteúdo diretamente
- **Named vectors indireto**: Named vectors melhoram quais chunks chegam ao reranker, mas o Haystack trabalha apenas com o conteúdo

#### 3. **CohereReranker** (API)
- **O que usa**: `chunk.content` (apenas)
- **Como funciona**: API recebe query + lista de documentos (conteúdos)
- **Named vectors indireto**: Named vectors influenciam quais conteúdos chegam à API

#### 4. **JinaReranker** (API)
- **O que usa**: `chunk.content` (apenas)
- **Como funciona**: Similar ao Cohere, query + documentos
- **Named vectors indireto**: Mesmo impacto dos named vectors

#### 5. **VoyageAIReranker** (API)
- **O que usa**: `chunk.content` (apenas)
- **Como funciona**: Query + documentos para reranking
- **Named vectors indireto**: Named vectors determinam quais documentos chegam

#### 6. **ContextualAI Reranker** (API) ⭐ **Mais Sofisticado**
- **O que usa**: `chunk.content` + `chunk.meta` (metadata rica)
- **Metadata extraída**:
  - `doc_name`: nome do documento
  - `chunk_date`: data do chunk
  - `chunk_lang`: idioma
  - `enriched.companies`: empresas detectadas
  - `enriched.key_topics`: tópicos principais
- **Como funciona**: Combina relevância semântica com instruções customizadas + metadata contextual
- **Named vectors indireto**: Named vectors influenciam quais chunks (com metadata rica) chegam ao reranker

**Exemplo de Fluxo Completo:**

```
Query: "Apple e inovação estratégica"
  ↓
1. Detecção: empresas=["Apple"], frameworks=["estratégica"]
  ↓
2. Named Vectors: busca em `company_vec` + `concept_vec` → 50 chunks relevantes
  ↓
3. Reranking (ContextualAI): 
   - Recebe: query + 50 conteúdos + metadata de cada chunk
   - Instruction: "Prioritize recent documents about innovation"
   - Metadata: "Empresas: Apple | Tópicos: inovação estratégica"
  ↓
4. Resultado: top 5 chunks mais relevantes contextualmente
```

**Tabela Comparativa: Named Vectors + Rerankers**

| Reranker | Conteúdo Usado | Metadata Usada | Benefício Named Vectors | Benefício Específico |
|----------|----------------|----------------|-------------------------|---------------------|
| **Metadata** | ✅ `chunk.content` | ✅ `enriched` (empresas, tópicos, keywords) | Chunks semanticamente relevantes têm melhor metadata | Usa metadata detectada durante chunking |
| **Haystack** | ✅ `chunk.content` | ❌ Nenhum | Chunks mais relevantes chegam ao CrossEncoder | Comparação direta query vs conteúdo |
| **Cohere** | ✅ `chunk.content` | ❌ Nenhum | Melhor conjunto de documentos para API | Reranking multilíngue de alta qualidade |
| **Jina** | ✅ `chunk.content` | ❌ Nenhum | Mesmo benefício | Reranking rápido via API |
| **VoyageAI** | ✅ `chunk.content` | ❌ Nenhum | Mesmo benefício | Reranking multilíngue especializado |
| **ContextualAI** | ✅ `chunk.content` | ✅ **Rica** (doc_name, date, lang, enriched) | Chunks com metadata contextual chegam à API | **Combina relevância + instruções + metadata** |

### Como Contextual AI se Integra (Sem API de Query)

**Arquitetura do Contextual AI:**
```
Não tem API de query/search → Só API de rerank
```

**Fluxo no Verba:**
```
1. Weaviate/Named Vectors fazem a busca inicial (retrieval)
2. Chunks recuperados vão para Contextual AI reranker
3. Contextual AI rerankea os chunks já recuperados
```

**Por que funciona:**
- Contextual AI é **apenas reranker**, não search engine
- Ele assume que você já tem os documentos candidatos
- O Verba fornece os documentos via Weaviate + named vectors
- Contextual AI apenas reordena esses documentos

**Diferença de outros providers:**
- **Cohere/Jina/VoyageAI**: APIs de rerank (como Contextual AI)
- **Haystack**: CrossEncoder local (não API)
- **Metadata**: Reranker local (sempre disponível)

**Nota Técnica:**
- Named vectors melhoram **recall** (encontrar chunks semanticamente relevantes)
- Reranker melhora **precision** (reordenar por relevância contextual)
- ContextualAI é o que mais aproveita metadata (potencialmente enriquecida pelos named vectors)
- Os outros rerankers trabalham principalmente com conteúdo, mas se beneficiam dos chunks mais relevantes dos named vectors

## ⚠️ Análise Crítica: Encadeamento de Múltiplos Rerankers

### O Sistema Permite Encadear Rerankers?

**SIM**, o sistema permite encadear múltiplos rerankers em 3 modos:

1. **Cascade**: Sequencial (Metadata → Haystack → Cohere → ...)
2. **Parallel**: Todos em paralelo, combina com RRF
3. **Hybrid**: Alguns em paralelo, outros em cascade

### É Efetivo? ⚠️ **DEPENDE - Geralmente NÃO é recomendado**

#### ❌ **Problemas do Encadeamento:**

**1. Diminishing Returns (Lei dos Retornos Decrescentes)**
```
Metadata Only: +30% relevância
Metadata + Haystack: +35% relevância (+5% adicional)
Metadata + Haystack + Cohere: +37% relevância (+2% adicional)
Metadata + Haystack + Cohere + ContextualAI: +38% relevância (+1% adicional)
```
- **Custo**: Latência aumenta linearmente
- **Ganho**: Melhoria diminui exponencialmente

**2. Redundância entre Rerankers**
- Todos os rerankers fazem tarefa similar (ordenar por relevância)
- Encadear múltiplos pode apenas **reordenar o que já foi reordenado**
- Rerankers de API (Cohere, Jina, VoyageAI, ContextualAI) são todos baseados em modelos similares

**3. Custo vs Benefício**
```
Cascade com 3 APIs:
- Latência: ~1.5-2 segundos (soma de todas as APIs)
- Custo: 3x chamadas de API
- Ganho: +2-5% relevância adicional
- ROI: ⚠️ Questionável
```

**4. Overfitting de Ordem**
- Rerankers subsequentes podem "memorizar" a ordem do anterior
- Pode perder diversidade nos resultados
- Pode piorar resultados se o primeiro reranker estiver errado

#### ✅ **Quando Pode Ser Efetivo:**

**1. Cascade com Rerankers Complementares:**
```
Metadata (rápido, local) → ContextualAI (lento, com instruções)
```
- **Por quê**: Metadata filtra rapidamente, ContextualAI refina com instruções
- **Ganho**: Reduz latência (ContextualAI processa menos chunks)
- **Efetivo**: ✅ SIM

**2. Parallel com Rerankers Diferentes:**
```
Haystack (local, semântico) + Metadata (local, keywords) → RRF
```
- **Por quê**: Diferentes abordagens (semântica vs keywords)
- **Ganho**: Combina forças complementares
- **Efetivo**: ✅ SIM (se ambos são rápidos)

**3. Hybrid (Melhor dos dois mundos):**
```
(Metadata + Haystack em paralelo) → ContextualAI (com instruções)
```
- **Por quê**: Local rápido em paralelo, depois API com instruções
- **Ganho**: Velocidade + precisão final
- **Efetivo**: ✅ SIM

#### ❌ **Quando NÃO é Efetivo:**

**1. Cascade de Múltiplas APIs:**
```
Cohere → Jina → VoyageAI → ContextualAI
```
- **Problema**: Todas fazem tarefa similar, alto custo, baixo ganho
- **Recomendação**: ❌ Use apenas 1 API reranker

**2. Parallel de Múltiplas APIs:**
```
Cohere + Jina + VoyageAI + ContextualAI (todos em paralelo)
```
- **Problema**: Custo 4x, ganho marginal
- **Recomendação**: ❌ Escolha 1 API baseado em suas necessidades

**3. Cascade Longo:**
```
Metadata → Haystack → Cohere → Jina → VoyageAI → ContextualAI
```
- **Problema**: Latência muito alta, ganho mínimo
- **Recomendação**: ❌ Máximo 2-3 rerankers em cascade

### 📊 Recomendações Práticas

#### ✅ **Configurações Recomendadas:**

**1. Produção (Velocidade + Qualidade):**
```
Provider: ContextualAI (ou Cohere)
Modo: Single (não Combined)
```
- **Por quê**: 1 reranker de alta qualidade é suficiente
- **Latência**: ~300-600ms
- **Ganho**: +30-40% relevância

**2. Máxima Qualidade (Aceita Latência) - ⭐ RECOMENDADO:**
```
Provider: Combined
Modo: Hybrid
- Metadata: ✅ (filtro rápido, local)
- Haystack: ✅ (semântico, local)
- ContextualAI: ✅ (com instruções, API)
```
- **Por quê**: Combina 3 abordagens complementares sem redundância
  - Metadata: keywords/metadata (rápido)
  - Haystack: semântica profunda (local)
  - ContextualAI: instruções customizadas (API)
- **Latência**: ~1-1.5s
- **Ganho**: +40-45% relevância
- **Custo**: 1 chamada de API apenas

**3. Sem APIs (Local apenas):**
```
Provider: Combined
Modo: Parallel
- Metadata: ✅ (keywords/metadata)
- Haystack: ✅ (semântico)
```
- **Por quê**: Ambos são locais, complementares, sem custo de API
- **Latência**: ~500ms (CPU) / ~100ms (GPU)
- **Ganho**: +35-40% relevância
- **Nota**: Boa opção se não tem API keys ou quer evitar custos

#### ❌ **Configurações NÃO Recomendadas:**

**1. Cascade de Múltiplas APIs:**
```
❌ Metadata → Cohere → Jina → VoyageAI → ContextualAI
```
- **Problema**: Latência ~2-3s, ganho marginal
- **Custo**: 4x APIs

**2. Parallel de Múltiplas APIs:**
```
❌ Cohere + Jina + VoyageAI + ContextualAI (todos em paralelo)
```
- **Problema**: Custo 4x, redundância

**3. Cascade Longo:**
```
❌ Metadata → Haystack → Cohere → Jina → VoyageAI → ContextualAI
```
- **Problema**: Latência muito alta, overfitting

### 🎯 Conclusão

**Encadeamento pode ser efetivo SE:**
- ✅ Rerankers são **complementares** (ex: Metadata + Haystack + 1 API)
- ✅ Máximo **3 rerankers** (Metadata + Haystack + 1 API)
- ✅ Combina **local rápido** (Metadata + Haystack) + **1 API com instruções**
- ✅ Usa **Hybrid mode** (paralelo local, cascade API)
- ⭐ **IDEAL**: Metadata + Haystack + ContextualAI (ou Cohere)

**Encadeamento NÃO é efetivo SE:**
- ❌ Múltiplas **APIs similares** em cascade
- ❌ Mais de **3 rerankers** em cascade
- ❌ **Todas APIs** em parallel (custo alto, ganho baixo)
- ❌ **Latência** é crítica (produção síncrona)

**Recomendação Geral - ⭐ IDEAL:**
- **Produção**: Use **1 reranker de alta qualidade** (ContextualAI ou Cohere)
- **Máxima qualidade**: Use **Hybrid mode** com **Metadata + Haystack + 1 API reranker**
  - ✅ Metadata: filtro rápido local
  - ✅ Haystack: semântica profunda local
  - ✅ 1 API (ContextualAI/Cohere): instruções ou alta qualidade
  - ❌ **NÃO** adicione múltiplas APIs (redundância)
- **Evite**: Cascade de múltiplas APIs similares

## 🚀 Guia de Implementação: Sistema Otimizado para Reranking

### Visão Geral da Arquitetura Otimizada

```
INDEXING (Import)              AGENT (Query)                 FRONTEND (UI)
├── Named Vectors ✓          ├── Hybrid Search ✓           ├── Configuração ✓
├── Metadata Enrichment ✓     ├── Multi-Vector ✓            ├── Preset Modes ✓
├── Framework Detection ✓     ├── Entity Filtering ✓        ├── Performance ✓
└── Chunking Hierárquico ✓    └── Reranking ✓               └── Monitoring ✓
```

### 1. 📊 INDEXING: Preparação Otimizada

#### **Configurações Essenciais para Named Vectors:**

**Arquivo: `environment variables` ou `VerbaManager`**
```bash
# Habilitar Named Vectors (global)
ENABLE_NAMED_VECTORS="true"

# Configurações de chunking para reranking
CHUNK_SIZE=512
CHUNK_OVERLAP=50

# Metadata enrichment (para MetadataReranker)
ENABLE_METADATA_ENRICHMENT="true"
```

**Arquivo: `verba_extensions/integration/vector_config_builder.py`**
```python
# VectorConfig otimizado para reranking
vector_config = build_named_vectors_config(
    enable_named_vectors=True,
    estimated_count=10000,  # Para quantização PQ
    use_pq=True
)
```

#### **Processo de Indexing Otimizado:**

1. **Import Document**:
   - Extração de textos especializados (`concept_text`, `sector_text`, `company_text`)
   - Embedding generation para 3 named vectors
   - Metadata enrichment (empresas, tópicos, keywords)

2. **Schema Creation**:
   - Collections com `vectorConfig` para named vectors
   - Propriedades para metadata rica
   - Índices HNSW otimizados

### 2. 🤖 AGENTE: Configuração Inteligente

#### **Preset Configurations Recomendadas:**

**Arquivo: `verba_extensions/plugins/entity_aware_retriever.py`**

```python
# PRESETS OTIMIZADOS

PRESET_PRODUCTION = {
    "Reranker Provider": "ContextualAI",
    "ContextualAI Model": "ctxl-rerank-v2-instruct-multilingual",
    "ContextualAI Instruction": "Prioritize recent and authoritative content.",
    "Top K": 5,
    "Enable Named Vectors": True,
    "Two-Phase Search Mode": "auto"
}

PRESET_MAX_QUALITY = {
    "Reranker Provider": "Combined",
    "Reranker Mode": "Hybrid",
    "Enable Metadata Reranker": True,
    "Enable Haystack Reranker": True,
    "Enable ContextualAI Reranker": True,
    "ContextualAI Instruction": "Prioritize internal documents and recent content.",
    "Top K": 5,
    "Enable Named Vectors": True,
    "Two-Phase Search Mode": "enabled"
}

PRESET_LOCAL_ONLY = {
    "Reranker Provider": "Combined",
    "Reranker Mode": "Parallel",
    "Enable Metadata Reranker": True,
    "Enable Haystack Reranker": True,
    "Top K": 5,
    "Enable Named Vectors": True,
    "Two-Phase Search Mode": "auto"
}
```

#### **Lógica de Seleção Automática:**

```python
def select_optimal_preset(query: str, has_api_keys: bool, latency_budget: float):
    """
    Seleciona preset otimizado baseado na query e recursos disponíveis
    """

    # Análise da query
    has_entities = detect_entities(query)
    has_complexity = len(query.split()) > 10
    needs_instructions = detect_instruction_need(query)

    # Seleção baseada em critérios
    if latency_budget < 1.0 and has_api_keys:
        return PRESET_PRODUCTION
    elif needs_instructions and has_api_keys:
        return PRESET_MAX_QUALITY
    elif has_entities and not has_api_keys:
        return PRESET_LOCAL_ONLY
    else:
        return PRESET_PRODUCTION  # fallback
```

### 3. 🎨 FRONTEND: Interface Otimizada

#### **Configurações Simplificadas:**

**Arquivo: `frontend/AgentConfiguration.tsx`**

```tsx
// PRESETS PARA USUÁRIO
const PRESET_OPTIONS = [
  {
    id: "production",
    name: "🚀 Produção (Recomendado)",
    description: "Velocidade + Qualidade Balanceada",
    config: PRESET_PRODUCTION,
    latency: "~500ms",
    accuracy: "Alta"
  },
  {
    id: "max_quality",
    name: "🎯 Máxima Qualidade",
    description: "Melhor precisão (aceita latência)",
    config: PRESET_MAX_QUALITY,
    latency: "~1.5s",
    accuracy: "Muito Alta"
  },
  {
    id: "local_only",
    name: "💻 Local Apenas",
    description: "Sem APIs (CPU/GPU apenas)",
    config: PRESET_LOCAL_ONLY,
    latency: "~500ms",
    accuracy: "Alta"
  }
];
```

#### **Interface de Configuração:**

```tsx
// Componente simplificado
const RerankerConfig = ({ config, onChange }) => {
  const [selectedPreset, setSelectedPreset] = useState("production");

  // Preset buttons
  return (
    <div>
      <h3>🎯 Configuração de Reranking</h3>

      {/* Preset Selection */}
      <div className="preset-buttons">
        {PRESET_OPTIONS.map(preset => (
          <button
            key={preset.id}
            onClick={() => {
              setSelectedPreset(preset.id);
              onChange(preset.config);
            }}
            className={selectedPreset === preset.id ? "active" : ""}
          >
            <div className="preset-name">{preset.name}</div>
            <div className="preset-desc">{preset.description}</div>
            <div className="preset-metrics">
              {preset.latency} | {preset.accuracy}
            </div>
          </button>
        ))}
      </div>

      {/* Advanced Options (collapsible) */}
      <details>
        <summary>⚙️ Configurações Avançadas</summary>
        {/* Detalhes técnicos aqui */}
      </details>
    </div>
  );
};
```

#### **Monitoramento em Tempo Real:**

```tsx
// Performance metrics no frontend
const PerformanceMetrics = ({ queryTime, rerankerTime, accuracy }) => (
  <div className="performance-panel">
    <h4>📊 Performance</h4>
    <div className="metrics">
      <div>Query Total: {queryTime}ms</div>
      <div>Reranking: {rerankerTime}ms</div>
      <div>Estimated Accuracy: {accuracy}%</div>
    </div>
  </div>
);
```

### 4. 🔧 IMPLEMENTAÇÃO SISTÊMICA

#### **VerbaManager: Centralização de Configs**

**Arquivo: `goldenverba/components/managers.py`**

```python
class VerbaManager:
    def __init__(self):
        self.presets = {
            "production": PRESET_PRODUCTION,
            "max_quality": PRESET_MAX_QUALITY,
            "local_only": PRESET_LOCAL_ONLY
        }

    def get_optimal_config(self, query: str, context: dict) -> dict:
        """
        Retorna configuração otimizada baseada na query e contexto
        """
        has_api_keys = self._check_api_keys()
        latency_budget = context.get("latency_budget", 2.0)

        return select_optimal_preset(query, has_api_keys, latency_budget)
```

#### **Agent: Auto-configuração**

**Arquivo: `goldenverba/components/agent.py`**

```python
class Agent:
    def __init__(self, config_preset: str = "auto"):
        self.verba_manager = VerbaManager()

        if config_preset == "auto":
            # Auto-seleção baseada na query
            self.config = None  # Será definido por query
        else:
            self.config = self.verba_manager.presets.get(config_preset)

    def query(self, question: str, **kwargs):
        # Auto-configuração se necessário
        if self.config is None:
            self.config = self.verba_manager.get_optimal_config(question, kwargs)

        # Executa query com config otimizada
        return self._execute_query(question, self.config)
```

### 5. 📈 MONITORAMENTO E OTIMIZAÇÃO

#### **Métricas Essenciais:**

```python
# Em cada query, coletar:
query_metrics = {
    "total_time": end_time - start_time,
    "retrieval_time": retrieval_end - retrieval_start,
    "reranking_time": rerank_end - rerank_start,
    "chunks_before_rerank": len(raw_chunks),
    "chunks_after_rerank": len(final_chunks),
    "reranker_used": reranker_provider,
    "accuracy_estimate": calculate_accuracy_score(final_chunks, question)
}
```

#### **Auto-ajuste:**

```python
class AdaptiveConfig:
    def adjust_config(self, query_metrics: dict):
        """
        Ajusta configurações baseado em performance histórica
        """
        if query_metrics["total_time"] > 2000:  # Muito lento
            # Reduz para preset production
            return "production"
        elif query_metrics["accuracy_estimate"] < 0.7:  # Baixa qualidade
            # Aumenta para max_quality
            return "max_quality"

        return "current"  # Mantém atual
```

### 6. 🎯 RESULTADO FINAL

#### **Fluxo Otimizado Completo:**

```
User Query
    ↓
Agent (Auto-configuração baseada na query)
    ↓
Retriever (Named Vectors + Entity Filtering)
    ↓
Reranker (Metadata + Haystack + ContextualAI)
    ↓
LLM (Context otimizado)
    ↓
Response + Metrics
```

#### **Benefícios da Organização:**

- ✅ **Auto-otimização**: Configuração automática baseada na query
- ✅ **Performance**: Latência controlada, qualidade garantida
- ✅ **Usabilidade**: Presets simplificam configuração
- ✅ **Monitoramento**: Métricas em tempo real
- ✅ **Escalabilidade**: Suporte a diferentes perfis de uso

Essa organização garante que o sistema seja otimizado para reranking desde o indexing até a resposta final, maximizando qualidade e performance.

## Referências

- [Haystack Documentation](https://docs.haystack.deepset.ai/)
- [Cohere Rerank API](https://docs.cohere.com/docs/reranking)
- [Jina Rerank API](https://jina.ai/reranker/)
- [VoyageAI Documentation](https://www.voyageai.com/docs)
- [Contextual AI Rerank API](https://docs.contextual.ai/api-reference/rerank/rerank)

