# Explicação Detalhada: Funcionalidades Avançadas de Recuperação

## 📋 Índice

1. [Two-Phase Search](#two-phase-search)
2. [Query Expansion](#query-expansion)
3. [Alpha Optimizer (Dynamic Alpha)](#alpha-optimizer-dynamic-alpha)
4. [Multi-Vector Search](#multi-vector-search)
5. [Relative Score Fusion](#relative-score-fusion)
6. [BM25 Boosting (query_properties)](#bm25-boosting-query_properties)
7. [Named Vectors](#named-vectors)

---

## 🔄 Two-Phase Search

### O que é?

Modo de busca em duas fases otimizado para documentos de consultoria:
- **Fase 1**: Filtra por entidades (cria subespaço relevante)
- **Fase 2**: Busca multi-vector dentro do subespaço filtrado

### Como Funciona?

#### Fase 1: Filtro por Entidades (Subespaço)

1. **Detecção de Entidades**:
   - Usa `QueryExpanderPlugin.expand_query_for_entities()` para gerar variações focadas em entidades
   - Extrai `entity_ids` (formato `ent:*`) e `entity_texts` (nomes de entidades)
   - Detecta frameworks, empresas e setores mencionados na query

2. **Construção do Filtro**:
   ```python
   # Filtro por entity_ids (formato ent:*)
   phase1_entity_filter = Filter.by_property("section_entity_ids").contains_any(entity_ids)
   
   # OU filtro por entity_texts (modo inteligente)
   phase1_entity_filter = Filter.by_property("entities_local_ids").contains_any(entity_texts)
   ```

3. **Busca Híbrida na Fase 1**:
   - Executa `weaviate_manager.hybrid_chunks_with_filter()` com:
     - `alpha=0.4` (mais BM25, foco em entidades)
     - Filtro de entidades aplicado
     - `limit=limit * 3` (busca mais chunks para ter subespaço maior)
   - **Objetivo**: Identificar chunks que mencionam as entidades (não precisa ser muito relevante, apenas filtrar)

4. **Extração de UUIDs**:
   - Extrai UUIDs dos chunks encontrados na Fase 1
   - Esses UUIDs definem o **subespaço** para a Fase 2

#### Fase 2: Multi-Vector Search dentro do Subespaço

1. **Query Expansion (Temas)**:
   - Usa `QueryExpanderPlugin.expand_query_for_themes()` para gerar variações focadas em conceitos/temas
   - Gera 3-5 variações que exploram sinônimos e conceitos relacionados

2. **Geração de Embedding**:
   - Usa `EmbeddingManager.vectorize_query()` para gerar embedding da query expandida
   - Embedding é usado para busca vetorial em múltiplos named vectors

3. **Construção do Filtro da Fase 2**:
   ```python
   # Filtro combina: subespaço (UUIDs da Fase 1) + outros filtros
   phase2_filter = Filter.all_of([
       Filter.by_property("uuid").contains_any(phase1_uuids),  # Subespaço
       temporal_filter,  # Filtro temporal (se houver)
       framework_filter   # Filtro de frameworks (se houver)
   ])
   ```

4. **Multi-Vector Search**:
   - Executa `MultiVectorSearcher.search_multi_vector()` com:
     - `vectors=["concept_vec", "sector_vec", "company_vec"]` (ou subconjunto)
     - `fusion_type="RELATIVE_SCORE"` (ou "RRF" como fallback)
     - `query_properties=["content", "title^2"]` (BM25 boosting)
     - `alpha=rewritten_alpha` (alpha otimizado pelo AlphaOptimizer)
     - Filtro do subespaço aplicado

5. **Retorno**:
   - Retorna chunks ordenados por relevância dentro do subespaço filtrado

### Quando é Ativado?

- **Modo "auto"** (padrão): Ativa automaticamente se detectar entidades na query
- **Modo "enabled"**: Sempre ativo
- **Modo "disabled"**: Nunca ativo

### Plugins e Recursos Acionados

- ✅ **QueryExpanderPlugin** (Fase 1 e Fase 2)
- ✅ **MultiVectorSearcher** (Fase 2)
- ✅ **AlphaOptimizerPlugin** (alpha otimizado)
- ✅ **Relative Score Fusion** (se habilitado)
- ✅ **BM25 Boosting** (query_properties)

### Named Vectors Usados

- **Fase 1**: Não usa named vectors (busca híbrida normal)
- **Fase 2**: Usa **todos os named vectors disponíveis**:
  - `concept_vec`: Conceitos abstratos, frameworks, estratégias
  - `sector_vec`: Setores/indústrias
  - `company_vec`: Empresas específicas

---

## 🔍 Query Expansion

### O que é?

Gera múltiplas variações de uma query usando LLM para melhorar Recall.

### Como Funciona?

#### Dois Modos de Expansão

1. **`expand_query_for_entities()`**:
   - Foco: Extrair entidades nomeadas (empresas, pessoas, organizações)
   - Gera 3-5 variações que exploram sinônimos e formas alternativas de mencionar entidades
   - **Usado em**: Fase 1 do Two-Phase Search, detecção inicial de entidades

2. **`expand_query_for_themes()`**:
   - Foco: Conceitos, temas, frameworks, metodologias
   - Gera 3-5 variações que exploram conceitos relacionados e sinônimos
   - **Usado em**: Fase 2 do Two-Phase Search, busca normal, multi-vector search

#### Fluxo de Execução

1. **Cache Check**:
   - Verifica cache usando chave `entities:{query}` ou `themes:{query}`
   - TTL padrão: 3600 segundos (1 hora)

2. **Geração com LLM**:
   - Usa `GeneratorManager` para obter generator (OpenAI, Ollama, etc.)
   - Envia prompt para LLM com instruções específicas
   - LLM retorna lista de variações

3. **Parse e Validação**:
   - Parseia resposta do LLM (extrai JSON ou lista)
   - Filtra variações muito curtas (<5 caracteres)
   - Limita a 5 variações
   - Sempre inclui query original como primeira variação

4. **Cache**:
   - Armazena no cache com timestamp
   - Reutiliza em próximas queries similares

### Quando é Ativado?

- Configuração: `Enable Query Expansion` (padrão: `True`)
- **Sempre ativo** quando habilitado, em:
  - Two-Phase Search (Fase 1 e Fase 2)
  - Busca normal (antes de hybrid_chunks)
  - Multi-vector search (antes de gerar embedding)

### Plugins e Recursos Acionados

- ✅ **QueryExpanderPlugin** (próprio plugin)
- ✅ **GeneratorManager** (para acessar LLM)
- ✅ **Cache em memória** (TTL configurável)

### Named Vectors Usados

- **Não usa named vectors diretamente**
- **Indiretamente**: Melhora a qualidade das queries que são usadas para buscar em named vectors

---

## ⚖️ Alpha Optimizer (Dynamic Alpha)

### O que é?

Calcula automaticamente o valor ótimo de `alpha` para busca híbrida baseado no tipo de query.

### Como Funciona?

#### Detecção do Tipo de Query

1. **Query "entity-rich"** (alpha baixo, foco BM25):
   - Indicadores:
     - Presença de entidades detectadas
     - Palavras capitalizadas (nomes próprios)
     - Padrões regex de nomes próprios
     - Termos específicos: "capacidade", "capacity", "revenue", "market share"
     - Query curta (≤5 palavras)
   - **Alpha calculado**: `0.3` (mais BM25, menos vetor)

2. **Query "exploratory"** (alpha alto, foco vetor):
   - Indicadores:
     - Palavras exploratórias: "como", "o que", "quais", "oportunidades", "tendências"
     - Query longa (>8 palavras)
     - Contém "?" (pergunta)
     - Termos exploratórios: "melhor", "recomendação", "análise", "visão"
   - **Alpha calculado**: `0.7` (mais vetor, menos BM25)

#### Ajustes Adicionais

1. **Baseado em Intent**:
   - `intent="comparison"`: Reduz alpha em 0.1 (mais BM25)
   - `intent="description"`: Aumenta alpha em 0.1 (mais vetor)

2. **Baseado em Comprimento**:
   - Query muito curta (≤3 palavras): Reduz alpha em 0.1
   - Query muito longa (>15 palavras): Aumenta alpha em 0.1

3. **Limites**:
   - Alpha final sempre entre `0.0` e `1.0`

### Quando é Ativado?

- Configuração: `Enable Dynamic Alpha` (padrão: `True`)
- **Sempre ativo** quando habilitado, em:
  - Two-Phase Search (Fase 2)
  - Busca normal (antes de hybrid_chunks)
  - Multi-vector search

### Plugins e Recursos Acionados

- ✅ **AlphaOptimizerPlugin** (próprio plugin)
- ✅ **Regex patterns** (para detectar nomes próprios)
- ✅ **Análise de entidades** (da detecção de entidades)

### Named Vectors Usados

- **Não usa named vectors diretamente**
- **Indiretamente**: Otimiza o alpha usado nas buscas em named vectors

---

## 🎯 Multi-Vector Search

### O que é?

Busca paralela em múltiplos named vectors especializados com combinação inteligente de resultados.

### Como Funciona?

#### Named Vectors Disponíveis

1. **`concept_vec`**:
   - **Foco**: Conceitos abstratos, frameworks, estratégias, metodologias
   - **Texto fonte**: `concept_text` (frameworks + termos semânticos + texto base)
   - **Quando usar**: Queries sobre conceitos, frameworks, estratégias

2. **`sector_vec`**:
   - **Foco**: Setores/indústrias (varejo, bancos, tecnologia)
   - **Texto fonte**: `sector_text` (setores + texto base)
   - **Quando usar**: Queries sobre setores, indústrias, domínios

3. **`company_vec`**:
   - **Foco**: Empresas específicas (Apple, Microsoft, etc.)
   - **Texto fonte**: `company_text` (empresas + texto base)
   - **Quando usar**: Queries sobre empresas específicas

#### Fluxo de Execução

1. **Seleção de Vetores**:
   - Detecta frameworks, empresas e setores na query
   - Seleciona vetores relevantes:
     ```python
     if detected_frameworks:
         vectors_to_search.append("concept_vec")
     if detected_sectors:
         vectors_to_search.append("sector_vec")
     if detected_companies:
         vectors_to_search.append("company_vec")
     ```
   - **Mínimo**: 2 vetores (caso contrário, usa busca simples)

2. **Busca Paralela**:
   - Executa `_search_single_vector()` para cada vetor em paralelo (usando `asyncio.gather()`)
   - Cada busca retorna até `limit` resultados

3. **Busca Individual por Vetor**:
   - **Vector Search** (se `alpha > 0`):
     - `collection.query.near_vector()` com `target_vector=vector_name`
     - Busca até `limit * alpha * 1.5` resultados
   - **BM25 Search** (se `alpha < 1.0`):
     - `collection.query.bm25()` com `query_properties` (se especificado)
     - Busca até `limit * (1 - alpha) * 1.5` resultados
   - **Combinação**: Prioriza vector, depois BM25, remove duplicatas

4. **Fusão de Resultados**:
   - **Modo "RELATIVE_SCORE"** (preferido):
     - Usa `collection.query.hybrid()` com `fusion_type=HybridFusion.RELATIVE_SCORE`
     - Preserva magnitude da similaridade (não apenas rank)
     - Usa `TargetVectors.manual_weights()` para pesar vetores
   - **Modo "RRF"** (fallback):
     - Combina manualmente usando RRF (Reciprocal Rank Fusion)
     - Score RRF = `sum(weight / (k + rank))` para cada vetor
     - `k=60` (parâmetro RRF padrão)

5. **Deduplicação**:
   - Remove duplicatas baseado em UUID
   - Mantém apenas o resultado com maior score

6. **Retorno**:
   - Retorna top `limit` resultados ordenados por score combinado

### Quando é Ativado?

- Configuração: `Enable Multi-Vector Search` (padrão: `False`)
- **Ativo quando**:
  - Habilitado na configuração
  - Named vectors estão disponíveis na collection
  - Pelo menos 2 vetores são selecionados

### Plugins e Recursos Acionados

- ✅ **MultiVectorSearcher** (próprio plugin)
- ✅ **Relative Score Fusion** (se habilitado)
- ✅ **BM25 Boosting** (query_properties)
- ✅ **Alpha Optimizer** (alpha otimizado)
- ✅ **Query Expansion** (antes de gerar embedding)

### Named Vectors Usados

- **Todos os vetores selecionados** (mínimo 2):
  - `concept_vec`: Se frameworks detectados
  - `sector_vec`: Se setores detectados
  - `company_vec`: Se empresas detectadas

---

## 🔗 Relative Score Fusion

### O que é?

Algoritmo de fusão nativo do Weaviate que normaliza scores de diferentes branches (vetorial e BM25) para uma escala comum antes de combinar, preservando a magnitude da similaridade.

### Como Funciona?

#### Diferença entre RRF e Relative Score Fusion

1. **RRF (Reciprocal Rank Fusion)**:
   - Baseado apenas em **rank** (posição do resultado)
   - Ignora magnitude da similaridade
   - Score = `sum(1 / (k + rank))`
   - **Problema**: Resultado com score 0.99 e rank 1 tem mesmo peso que resultado com score 0.5 e rank 1

2. **Relative Score Fusion**:
   - Normaliza scores de diferentes branches para escala comum
   - Preserva magnitude da similaridade
   - Combina scores normalizados com pesos
   - **Vantagem**: Resultado com score 0.99 tem mais peso que resultado com score 0.5

#### Implementação

1. **Em Hybrid Search**:
   ```python
   collection.query.hybrid(
       query=query,
       vector=vector,
       alpha=alpha,
       fusion_type=HybridFusion.RELATIVE_SCORE,  # ⚡
       query_properties=query_properties
   )
   ```

2. **Em Multi-Vector Search**:
   ```python
   collection.query.hybrid(
       query=query,
       vector=HybridVector.near_vector(vector={vector_name: query_vector}),
       target_vector=TargetVectors.manual_weights(weights={...}),
       alpha=alpha,
       fusion_type=HybridFusion.RELATIVE_SCORE,  # ⚡
       query_properties=query_properties
   )
   ```

3. **Fallback**:
   - Se `RELATIVE_SCORE` não disponível (Weaviate antigo), usa RRF manual

### Quando é Ativado?

- Configuração: `Enable Relative Score Fusion` (padrão: `True`)
- **Ativo quando**:
  - Habilitado na configuração
  - Weaviate suporta `HybridFusion.RELATIVE_SCORE` (v4+)
  - Usado em todas as buscas híbridas (normal e multi-vector)

### Plugins e Recursos Acionados

- ✅ **Weaviate v4+** (suporte nativo)
- ✅ **HybridFusion.RELATIVE_SCORE** (enum do Weaviate)
- ✅ **Fallback para RRF** (se não disponível)

### Named Vectors Usados

- **Usado em todos os named vectors** quando aplicado em multi-vector search
- **Não usa named vectors diretamente**, mas melhora a fusão de resultados de múltiplos vetores

---

## 📊 BM25 Boosting (query_properties)

### O que é?

Permite dar pesos diferentes a diferentes propriedades na busca BM25, priorizando propriedades mais relevantes (ex: título tem mais peso que conteúdo).

### Como Funciona?

#### Sintaxe

```python
query_properties = ["content", "title^2"]  # title tem peso 2x maior que content
```

- `"content"`: Peso padrão (1.0)
- `"title^2"`: Peso 2x maior que padrão
- `"title^3"`: Peso 3x maior que padrão

#### Propriedades Otimizadas

1. **`content`**:
   - Propriedade principal do chunk
   - `index_searchable=True`, `tokenization=Tokenization.WORD`
   - Peso padrão: 1.0

2. **`title`**:
   - Título do documento
   - `index_searchable=True`, `tokenization=Tokenization.WORD`
   - **Peso boost**: 2.0 (configurado como `"title^2"`)

3. **Propriedades Especializadas** (para named vectors):
   - `concept_text`: `index_searchable=True`, `tokenization=Tokenization.WORD`
   - `sector_text`: `index_searchable=True`, `tokenization=Tokenization.WORD`
   - `company_text`: `index_searchable=True`, `tokenization=Tokenization.WORD`

#### Implementação

```python
collection.query.hybrid(
    query=query,
    vector=vector,
    alpha=alpha,
    query_properties=["content", "title^2"]  # ⚡ BM25 boosting
)
```

### Quando é Ativado?

- **Sempre ativo** em todas as buscas híbridas
- Configuração padrão: `["content", "title^2"]`
- Pode ser customizado por busca

### Plugins e Recursos Acionados

- ✅ **Weaviate v4+** (suporte a `query_properties`)
- ✅ **Schema otimizado** (`index_searchable=True`, `tokenization=WORD`)
- ✅ **BM25 engine** (do Weaviate)

### Named Vectors Usados

- **Não usa named vectors diretamente**
- **Indiretamente**: Melhora a qualidade da busca BM25 que é combinada com busca vetorial em named vectors

---

## 🎨 Named Vectors

### O que são?

Múltiplos vetores especializados em uma única collection, cada um focado em um aspecto diferente do conteúdo.

### Como Funcionam?

#### Estrutura

Cada named vector tem:
- **Nome**: `concept_vec`, `sector_vec`, `company_vec`
- **Índice HNSW próprio**: Cada vetor tem seu próprio índice de busca
- **Texto fonte**: Propriedade especializada que alimenta o embedding
- **Configuração**: HNSW com quantização PQ (se collection grande)

#### Named Vectors Disponíveis

1. **`concept_vec`**:
   - **Texto fonte**: `concept_text`
   - **Conteúdo**: Frameworks detectados + termos semânticos + texto base
   - **Uso**: Queries sobre conceitos, frameworks, estratégias
   - **Exemplo**: "SWOT analysis", "Porter's Five Forces", "inovação estratégica"

2. **`sector_vec`**:
   - **Texto fonte**: `sector_text`
   - **Conteúdo**: Setores detectados + texto base
   - **Uso**: Queries sobre setores, indústrias, domínios
   - **Exemplo**: "varejo", "bancos", "tecnologia", "saúde"

3. **`company_vec`**:
   - **Texto fonte**: `company_text`
   - **Conteúdo**: Empresas detectadas + texto base
   - **Uso**: Queries sobre empresas específicas
   - **Exemplo**: "Apple", "Microsoft", "Amazon"

#### Criação e População

1. **Durante Chunking**:
   - `VectorExtractor` extrai textos especializados:
     - `concept_text`: frameworks + termos semânticos + texto base
     - `sector_text`: setores + texto base
     - `company_text`: empresas + texto base

2. **Durante Import**:
   - Embeddings são gerados para cada texto especializado
   - Cada embedding é armazenado no named vector correspondente:
     - `concept_text` → `concept_vec`
     - `sector_text` → `sector_vec`
     - `company_text` → `company_vec`

3. **Schema**:
   - Collection criada com `vectorConfig` contendo os 3 named vectors
   - Cada vetor tem configuração HNSW independente

#### Busca em Named Vectors

1. **Busca Individual**:
   ```python
   collection.query.near_vector(
       vector=query_vector,
       target_vector="concept_vec"  # ⚡ Especifica qual named vector
   )
   ```

2. **Busca Multi-Vector**:
   ```python
   collection.query.hybrid(
       query=query,
       vector=HybridVector.near_vector(vector={vector_name: query_vector}),
       target_vector=TargetVectors.manual_weights(weights={
           "concept_vec": 0.6,
           "sector_vec": 0.4
       })  # ⚡ Múltiplos named vectors com pesos
   )
   ```

### Quando são Usados?

- **⚠️ IMPORTANTE: Named vectors NÃO são habilitados por padrão**
- **Habilitado via**:
  1. **Configuração do VerbaManager** (Settings → Advanced → Enable Named Vectors) - **RECOMENDADO**
  2. **Variável de ambiente** `ENABLE_NAMED_VECTORS=true` (fallback/compatibilidade)
- **Ativo quando**:
  - Named vectors estão habilitados (configuração ou variável de ambiente)
  - Collection foi criada com `vectorConfig` (requer recriação de collections existentes)
  - Multi-vector search está habilitado no retriever
  - Pelo menos 2 vetores são selecionados baseado na query
- **Padrão**: `False` (desabilitado) - precisa habilitar explicitamente

### Plugins e Recursos Acionados

- ✅ **VectorExtractor** (extração de textos especializados)
- ✅ **Schema Updater** (criação de `vectorConfig`)
- ✅ **MultiVectorSearcher** (busca em múltiplos vetores)
- ✅ **Relative Score Fusion** (fusão de resultados)
- ✅ **Query Expansion** (melhora queries para named vectors)

### Named Vectors Usados

- **Todos os 3 vetores** (quando aplicável):
  - `concept_vec`: Sempre que frameworks são detectados
  - `sector_vec`: Sempre que setores são detectados
  - `company_vec`: Sempre que empresas são detectadas

---

## 🔄 Fluxo Completo: Exemplo de Query

### Query: "Apple e inovação tecnológica"

#### 1. Detecção Inicial
- **Entidades detectadas**: `["Apple"]`
- **Frameworks detectados**: `[]`
- **Setores detectados**: `[]`
- **Empresas detectadas**: `["Apple"]`
- **Tipo de query**: `"entity-rich"` (Alpha Optimizer)

#### 2. Two-Phase Search (Modo "auto" → ativado)

**Fase 1: Filtro por Entidades**
- Query Expansion (entidades): `["Apple", "Apple Inc.", "empresa Apple"]`
- Filtro: `Filter.by_property("entities_local_ids").contains_any(["Apple"])`
- Busca híbrida: `alpha=0.4` (mais BM25)
- Resultado: 50 chunks no subespaço

**Fase 2: Multi-Vector Search**
- Query Expansion (temas): `["inovação tecnológica", "novas tecnologias", "estratégias inovadoras"]`
- Alpha otimizado: `alpha=0.3` (entity-rich → mais BM25)
- Named vectors selecionados: `["company_vec"]` (apenas 1 → não usa multi-vector)
- Fallback: Busca híbrida normal com filtro do subespaço
- Resultado: 10 chunks relevantes sobre Apple e inovação

#### 3. Se Multi-Vector Estivesse Habilitado

**Fase 2: Multi-Vector Search**
- Named vectors selecionados: `["concept_vec", "company_vec"]`
- Query: `"inovação tecnológica"` (primeira variação expandida)
- Fusion: `RELATIVE_SCORE`
- BM25 boosting: `["content", "title^2"]`
- Alpha: `0.3` (entity-rich)
- Resultado: 10 chunks combinados de `concept_vec` e `company_vec`

---

## 📊 Resumo: Plugins e Recursos por Funcionalidade

| Funcionalidade | Plugins | Recursos Weaviate | Named Vectors |
|---------------|---------|-------------------|---------------|
| **Two-Phase Search** | QueryExpander, MultiVectorSearcher, AlphaOptimizer | Hybrid Search, Filters, Relative Score Fusion | concept_vec, sector_vec, company_vec (Fase 2) |
| **Query Expansion** | QueryExpander, GeneratorManager | - | - (indireto) |
| **Alpha Optimizer** | AlphaOptimizer | - | - (indireto) |
| **Multi-Vector Search** | MultiVectorSearcher, QueryExpander, AlphaOptimizer | Named Vectors, Hybrid Search, Relative Score Fusion | concept_vec, sector_vec, company_vec |
| **Relative Score Fusion** | - | HybridFusion.RELATIVE_SCORE | - (melhora fusão) |
| **BM25 Boosting** | - | query_properties | - (melhora BM25) |
| **Named Vectors** | VectorExtractor, Schema Updater | vectorConfig, HNSW, PQ | concept_vec, sector_vec, company_vec |

---

## 🎯 Quando Cada Named Vector é Usado?

### `concept_vec`
- ✅ Frameworks detectados na query
- ✅ Queries sobre conceitos abstratos
- ✅ Queries sobre estratégias, metodologias
- ❌ Queries apenas sobre empresas específicas (sem frameworks)

### `sector_vec`
- ✅ Setores detectados na query
- ✅ Queries sobre indústrias, domínios
- ❌ Queries apenas sobre empresas específicas (sem setores)

### `company_vec`
- ✅ Empresas detectadas na query
- ✅ Queries sobre organizações específicas
- ❌ Queries apenas sobre conceitos (sem empresas)

### Combinações Comuns

- **`concept_vec + company_vec`**: "Apple e inovação" (empresa + conceito)
- **`sector_vec + concept_vec`**: "varejo e estratégia" (setor + conceito)
- **`company_vec + sector_vec`**: "Apple no setor de tecnologia" (empresa + setor)
- **Todos os 3**: "Apple, varejo e estratégia de inovação" (empresa + setor + conceito)

---

## 🔧 Configurações Recomendadas

### Para Documentos de Consultoria

```python
{
    "Two-Phase Search Mode": "auto",  # Ativa automaticamente quando detecta entidades
    "Enable Query Expansion": True,    # Melhora Recall
    "Enable Relative Score Fusion": True,  # Melhor fusão que RRF
    "Enable Dynamic Alpha": True,     # Otimiza alpha automaticamente
    "Enable Multi-Vector Search": True,  # Usa named vectors
    "Alpha": "0.5",  # Base (será otimizado pelo Dynamic Alpha)
}
```

### Para Queries Exploratórias

```python
{
    "Two-Phase Search Mode": "disabled",  # Não precisa filtrar por entidades
    "Enable Query Expansion": True,       # Ajuda a explorar conceitos
    "Enable Multi-Vector Search": True,   # Busca em múltiplos aspectos
    "Alpha": "0.7",  # Mais vetor, menos BM25
}
```

### Para Queries Específicas (Entity-Rich)

```python
{
    "Two-Phase Search Mode": "enabled",  # Sempre filtra por entidades
    "Enable Query Expansion": True,      # Ajuda a encontrar variações de nomes
    "Enable Dynamic Alpha": True,         # Reduz alpha automaticamente
    "Alpha": "0.3",  # Mais BM25, menos vetor
}
```

---

## 🔧 Como Habilitar Named Vectors?

### ⚠️ IMPORTANTE: Named Vectors NÃO são habilitados por padrão

Por padrão, o sistema usa apenas **um vetor único** (vetor padrão do Weaviate). Para usar named vectors (`concept_vec`, `sector_vec`, `company_vec`), você precisa habilitá-los explicitamente.

### Opção 1: Via Configuração do VerbaManager (RECOMENDADO)

1. Acesse **Settings → Advanced** na interface do Verba
2. Ative **"Enable Named Vectors"**
3. Salve a configuração
4. **⚠️ IMPORTANTE**: Collections existentes precisam ser recriadas para usar named vectors

### Opção 2: Via Variável de Ambiente (Fallback/Compatibilidade)

```bash
# .env ou variáveis de ambiente
ENABLE_NAMED_VECTORS=true
```

**Nota**: Requer reiniciar a aplicação para aplicar.

### Verificação

Após habilitar, você pode verificar se named vectors estão ativos:

1. **Durante criação de collection**: Logs mostram:
   ```
   🎯 Named vectors habilitados: concept_vec, sector_vec, company_vec
   ```

2. **Verificar schema**: Collection deve ter `vectorConfig` com os 3 named vectors

3. **Durante import**: Logs mostram extração de textos especializados:
   ```
   [Named-Vectors] Extraindo textos especializados...
   ```

### ⚠️ Requisitos e Limitações

1. **Recriação de Collections**: Collections existentes precisam ser deletadas e recriadas
2. **Memória**: Aumenta uso de memória (~3x) - cada named vector tem seu próprio índice HNSW
3. **Processamento**: Requer geração de 3 embeddings por chunk (um para cada named vector)
4. **Weaviate v4+**: Requer Weaviate v4 ou superior (suporte a named vectors)

### Quando Habilitar?

**Recomendado habilitar se**:
- ✅ Você tem documentos de consultoria com frameworks, empresas e setores
- ✅ Você quer usar Multi-Vector Search
- ✅ Você tem memória suficiente (~3x mais)
- ✅ Você está disposto a recriar collections existentes

**Não recomendado se**:
- ❌ Collections já existem e não podem ser recriadas
- ❌ Memória limitada
- ❌ Documentos simples sem necessidade de busca especializada

---

## 🔄 Query Rewriter vs Query Builder

### ⚠️ IMPORTANTE: Ambos Usam LLM, Mas de Formas Diferentes

**Ambos usam LLM**, mas são versões diferentes:

1. **QueryRewriter** (antigo, simples):
   - ✅ Usa LLM para expansão semântica genérica
   - ❌ **NÃO conhece o schema** do Weaviate
   - ❌ **NÃO é um agente** - apenas reescreve queries
   - ❌ Retorna `filters: {}` (sempre vazio)

2. **QueryBuilder** (novo, avançado):
   - ✅ Usa LLM **com conhecimento do schema**
   - ✅ **Conhece o schema** - obtém dinamicamente do Weaviate
   - ✅ **Pode aplicar filtros** - gera filtros baseados em schema
   - ✅ **Mais inteligente** - entende estrutura dos dados

**Por que existem 2?**
- QueryRewriter foi criado primeiro (baseado em RAG2)
- QueryBuilder é uma melhoria que conhece schema
- Ambos são mantidos por compatibilidade (QueryBuilder tenta primeiro, QueryRewriter como fallback)

**Para mais detalhes**, veja:
- [`QUERY_REWRITER_VS_QUERY_BUILDER.md`](./QUERY_REWRITER_VS_QUERY_BUILDER.md) - Comparação técnica
- [`POR_QUE_DOIS_QUERY_REWRITERS.md`](./POR_QUE_DOIS_QUERY_REWRITERS.md) - Por que existem 2

---

## 📝 Notas Finais

1. **Named Vectors são OPCIONAIS e DESABILITADOS por padrão**: Sistema funciona sem eles, mas com melhor qualidade quando habilitados
2. **Two-Phase Search é ESPECÍFICO para consultoria**: Otimizado para queries com entidades + temas
3. **Query Expansion melhora Recall**: Gera variações que capturam sinônimos e formas alternativas
4. **Dynamic Alpha otimiza automaticamente**: Não precisa ajustar manualmente para cada tipo de query
5. **Relative Score Fusion é melhor que RRF**: Preserva magnitude da similaridade, não apenas rank
6. **BM25 Boosting prioriza títulos**: Títulos são mais relevantes que conteúdo geral
7. **Query Rewriter NÃO conhece schema**: É uma ferramenta simples de expansão semântica, não um agente

