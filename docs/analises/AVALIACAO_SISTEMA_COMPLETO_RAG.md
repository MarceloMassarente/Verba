# Avaliação Completa do Sistema RAG Verba

**Data:** Dezembro 2025  
**Escopo:** Schema, Ingestão, Retrieval, Reranking, Geração

---

## 1. SCHEMA (Weaviate)

### 1.1 Estrutura Atual

O schema é definido em `verba_extensions/integration/schema_updater.py` e inclui:

#### Propriedades Padrão Verba
| Propriedade | Tipo | Indexação | Uso |
|-------------|------|-----------|-----|
| `content` | TEXT | `index_searchable=True`, `tokenization=WORD` | BM25 híbrido |
| `title` | TEXT | `index_searchable=True`, `tokenization=WORD` | Boost de título |
| `doc_uuid` | UUID | `index_filterable=True` | Hierarchical filtering |
| `labels` | TEXT_ARRAY | `index_filterable=True` | Document filtering |
| `chunk_lang` | TEXT | `index_filterable=True` | Bilingual filtering |
| `chunk_date` | TEXT | `index_filterable=True` | Temporal filtering |
| `chunk_id` | NUMBER | - | Identificação |
| `pca` | NUMBER_ARRAY | - | Visualização 3D |

#### Propriedades ETL
| Propriedade | Tipo | Indexação | Uso |
|-------------|------|-----------|-----|
| `entities_local_ids` | TEXT_ARRAY | `index_filterable=True` | Entity filtering |
| `primary_entity_id` | TEXT | `index_filterable=True` | Entity filtering |
| `entity_mentions` | TEXT | - | JSON de entidades |
| `section_title` | TEXT | - | Contexto de seção |
| `section_entity_ids` | TEXT_ARRAY | - | Entidades da seção |

#### Propriedades V019 (Slides)
| Propriedade | Tipo | Indexação | Uso |
|-------------|------|-----------|-----|
| `slide_position` | TEXT | `index_filterable=True` | Posição narrativa |
| `slide_type` | TEXT | `index_filterable=True` | Tipo de slide |
| `pattern_genetics` | TEXT_ARRAY | `index_filterable=True` | Patterns reusáveis |
| `visual_archetype` | TEXT | `index_filterable=True` | Arquétipo visual |

#### Propriedades Named Vectors
| Propriedade | Tipo | Uso |
|-------------|------|-----|
| `concept_text` | TEXT | Vetor de conceitos |
| `sector_text` | TEXT | Vetor de setores |
| `company_text` | TEXT | Vetor de empresas |

### 1.2 Avaliação do Schema

#### ✅ Pontos Positivos

1. **Indexação Otimizada**
   - `index_filterable=True` em campos de filtro frequente
   - `index_searchable=True` com `tokenization=WORD` para BM25
   - Suporta busca híbrida eficiente

2. **Flexibilidade**
   - Propriedades ETL são opcionais (chunks normais funcionam)
   - Named vectors são opcionais
   - Schema serve para múltiplos casos de uso

3. **Compatibilidade**
   - Backward compatible com Verba padrão
   - Suporta Weaviate v4

#### ⚠️ Pontos de Atenção

1. **`chunk_date` como TEXT**
   - Deveria ser `DATE` para comparações temporais nativas
   - Atualmente requer parsing no filtro
   - **Recomendação:** Migrar para `DataType.DATE` em versão futura

2. **`meta` como TEXT serializado**
   - JSON serializado não é indexável
   - **Recomendação:** Extrair campos críticos para propriedades dedicadas

3. **Named Vectors**
   - Requer 4x mais armazenamento (4 vetores por chunk)
   - **Recomendação:** Usar apenas quando necessário

### 1.3 Compatibilidade com Melhores Práticas

| Prática | Status | Notas |
|---------|--------|-------|
| Indexação seletiva | ✅ | Apenas campos filtrados têm `index_filterable` |
| Tokenização adequada | ✅ | `WORD` para BM25 |
| Tipos de dados corretos | ⚠️ | `chunk_date` deveria ser DATE |
| Schema evolutivo | ✅ | Propriedades opcionais |

---

## 2. INGESTÃO (Entity-Semantic Chunking)

### 2.1 Pipeline Atual

```
Documento
    │
    ▼
[Reader] → Extrai conteúdo (PDF, DOCX, etc.)
    │
    ▼
[ETL Pré-Chunking] → Extrai entidades do documento completo
    │
    ▼
[EntitySemanticChunker] → Chunking com:
    │   - Section scope (evita contaminação)
    │   - Entity guardrails (não corta entidades)
    │   - Semantic breakpoints (similaridade)
    │
    ▼
[ETL Pós-Chunking] → Enriquece chunks com metadados
    │
    ▼
[Embedder] → Gera vetores
    │
    ▼
[Weaviate] → Armazena
```

### 2.2 EntitySemanticChunker

**Arquivo:** `verba_extensions/plugins/entity_semantic_chunker.py`

#### Funcionalidades

1. **Section Scope**
   - Detecta limites de seção
   - Evita misturar conteúdo de seções diferentes
   - Preserva contexto narrativo

2. **Entity Guardrails**
   - Usa `entity_spans` do ETL pré-chunking
   - Não corta entidades no meio
   - Ajusta boundaries automaticamente

3. **Semantic Breakpoints**
   - Usa similaridade de cosseno entre sentenças
   - Configurable via `Breakpoint Percentile Threshold`
   - Fallback para tamanho máximo se bibliotecas não disponíveis

#### Configurações

| Config | Default | Descrição |
|--------|---------|-----------|
| `Breakpoint Percentile Threshold` | 80 | Percentil para split semântico |
| `Max Sentences Per Chunk` | 20 | Máximo de sentenças |
| `Overlap` | 0 | Overlap entre chunks |

### 2.3 Avaliação da Ingestão

#### ✅ Pontos Positivos

1. **Entity-Aware**
   - ETL pré-chunking extrai entidades antes de chunkar
   - Guardrails evitam cortar entidades
   - Entidades são preservadas intactas

2. **Section-Aware**
   - Respeita limites de seção
   - Evita contaminação entre assuntos
   - Melhor para documentos estruturados

3. **Semantic Breakpoints**
   - Quebras baseadas em similaridade
   - Chunks mais coerentes semanticamente
   - Melhor que chunking por tamanho fixo

#### ⚠️ Pontos de Atenção

1. **Dependências Opcionais**
   - numpy/sklearn são opcionais
   - Fallback é chunking por tamanho (menos eficaz)
   - **Recomendação:** Garantir numpy/sklearn em produção

2. **Performance**
   - Cálculo de similaridade pode ser lento para documentos grandes
   - **Recomendação:** Batch processing para documentos >100 páginas

### 2.4 Compatibilidade com Melhores Práticas

| Prática | Status | Notas |
|---------|--------|-------|
| Chunking semântico | ✅ | Breakpoints por similaridade |
| Entity preservation | ✅ | Guardrails de entidades |
| Section awareness | ✅ | Respeita limites de seção |
| Overlap configurável | ✅ | Disponível mas default 0 |
| Metadata enrichment | ✅ | ETL pós-chunking |

---

## 3. RETRIEVAL (Entity-Aware Retriever)

### 3.1 Pipeline Atual

```
Query
    │
    ▼
[Query Processing]
    ├─ AdaptiveEntropyAnalyzer → Decide força do rewrite
    ├─ QueryRewriterPlugin → Reescrita semântica
    ├─ QueryBuilderPlugin → Query estruturada
    ├─ BilingualFilter → Filtro por idioma
    └─ TemporalFilter → Filtro por data
    │
    ▼
[IntelligentCache.get()] → Verifica cache por similaridade
    │
    ▼ (se cache miss)
[EntityAwareRetriever]
    ├─ Extrai entidades da query
    ├─ Aplica WHERE filter (entidades)
    ├─ Hybrid search (BM25 + Vector)
    └─ Retorna chunks filtrados
    │
    ▼
[Reranking]
    ├─ DynamicReranker → Enriquece scores
    └─ RerankerPlugin → Reranking semântico
    │
    ▼
[IntelligentCache.set()] → Armazena no cache
```

### 3.2 EntityAwareRetriever

**Arquivo:** `verba_extensions/plugins/entity_aware_retriever.py`

#### Funcionalidades

1. **Entity Filtering**
   - Extrai entidades da query (spaCy + Gazetteer)
   - Aplica WHERE filter no Weaviate
   - Evita contaminação entre entidades

2. **Hybrid Search**
   - BM25 (keyword) + Vector (semântico)
   - Alpha configurável (0.0=keyword, 1.0=vector)
   - Default: 0.6 (60% vector, 40% keyword)

3. **Query Processing**
   - QueryRewriter para expansão semântica
   - QueryBuilder para queries estruturadas
   - Filtros bilíngues e temporais

4. **RAG 2.0 Features**
   - IntelligentCache (similaridade)
   - DynamicReranker (multi-dimensional)

### 3.3 Avaliação do Retrieval

#### ✅ Pontos Positivos

1. **Entity-First Approach**
   - Filtra por entidade ANTES de buscar semanticamente
   - Evita "contaminação" (chunks de outras entidades)
   - Muito mais preciso para queries com entidades

2. **Hybrid Search**
   - Combina BM25 e vector search
   - Melhor recall que apenas vector
   - Melhor precision que apenas BM25

3. **Query Processing Pipeline**
   - Rewriting adaptativo (economiza LLM)
   - Filtros múltiplos (idioma, data, entidades)
   - Cache inteligente (reduz latência)

4. **Configurabilidade**
   - 20+ configurações disponíveis
   - Feature flags para cada componente
   - Presets para casos comuns

#### ⚠️ Pontos de Atenção

1. **Complexidade**
   - Muitas configurações podem confundir usuários
   - **Recomendação:** Documentar presets recomendados

2. **Dependência de ETL**
   - Entity filtering só funciona se ETL foi aplicado
   - Chunks sem `entities_local_ids` não são filtrados
   - **Recomendação:** Fallback gracioso se ETL não disponível

3. **Performance**
   - Query processing pode adicionar 100-500ms
   - **Recomendação:** Cache agressivo para queries frequentes

### 3.4 Compatibilidade com Melhores Práticas

| Prática | Status | Notas |
|---------|--------|-------|
| Hybrid search | ✅ | BM25 + Vector |
| Query expansion | ✅ | QueryRewriter + QueryBuilder |
| Entity filtering | ✅ | WHERE filter antes de vector search |
| Caching | ✅ | IntelligentCache com similaridade |
| Adaptive processing | ✅ | Entropia decide força do rewrite |

---

## 4. RERANKING

### 4.1 Pipeline Atual

```
Chunks Recuperados
    │
    ▼
[DynamicReranker] (RAG 2.0)
    ├─ Score de similaridade (original)
    ├─ Score de recência
    ├─ Score de entidades
    └─ Score combinado
    │
    ▼
[RerankerPlugin]
    ├─ MetadataReranker (local)
    ├─ HaystackReranker (local)
    ├─ CohereReranker (API)
    ├─ JinaReranker (API)
    ├─ VoyageAIReranker (API)
    └─ ContextualAIReranker (API)
```

### 4.2 DynamicReranker vs RerankerPlugin

| Aspecto | DynamicReranker | RerankerPlugin |
|---------|-----------------|----------------|
| **Foco** | Multi-dimensional (metadados) | Semântico (query-documento) |
| **Custo** | Zero (local) | Pode ter custo de API |
| **Dimensões** | Similarity + Recency + Entities | Similaridade semântica |
| **Posição** | ANTES do RerankerPlugin | DEPOIS do DynamicReranker |
| **Propósito** | Enriquecer scores | Refinar ordenação |

### 4.3 Avaliação do Reranking

#### ✅ Pontos Positivos

1. **Multi-Provider**
   - 6 providers diferentes
   - Fallback automático
   - Modos: Cascade, Parallel, Hybrid

2. **Multi-Dimensional**
   - DynamicReranker adiciona recência e entidades
   - Não apenas similaridade semântica
   - Configurável via pesos

3. **Presets**
   - `production`: Balanceado
   - `max_quality`: Múltiplos rerankers
   - `local_only`: Sem APIs

#### ⚠️ Pontos de Atenção

1. **Latência**
   - Cada reranker adiciona latência
   - API rerankers: 200-500ms cada
   - **Recomendação:** Usar cache para queries frequentes

2. **Custo**
   - APIs de reranking têm custo
   - **Recomendação:** Usar local_only para desenvolvimento

### 4.4 Compatibilidade com Melhores Práticas

| Prática | Status | Notas |
|---------|--------|-------|
| Cross-encoder reranking | ✅ | Haystack, Cohere, etc. |
| Multi-stage reranking | ✅ | DynamicReranker → RerankerPlugin |
| Fallback gracioso | ✅ | MetadataReranker sempre disponível |
| Configurabilidade | ✅ | Presets e configurações granulares |

---

## 5. GERAÇÃO

### 5.1 Pipeline Atual

```
Contexto + Query
    │
    ▼
[Generator]
    ├─ OpenAI
    ├─ Anthropic
    ├─ Groq
    ├─ Ollama
    └─ etc.
    │
    ▼ (se Iterative Search habilitado)
[IterativeSearchPlugin]
    ├─ Detecta [SEARCH: query]
    ├─ Faz busca adicional
    └─ Injeta contexto
    │
    ▼
Resposta
```

### 5.2 Avaliação da Geração

#### ✅ Pontos Positivos

1. **Multi-Provider**
   - Suporta múltiplos LLMs
   - Configuração via UI
   - Fallback disponível

2. **Iterative Search (RAG 2.0)**
   - Busca durante geração
   - Simula RAG 2.0 dinâmico
   - Configurável

#### ⚠️ Pontos de Atenção

1. **Iterative Search**
   - Requer modelo que gere tokens [SEARCH:]
   - Adiciona latência significativa
   - **Recomendação:** Usar apenas quando necessário

---

## 6. COMPATIBILIDADE GERAL

### 6.1 Matriz de Compatibilidade

| Componente A | Componente B | Compatível | Notas |
|--------------|--------------|------------|-------|
| Schema ETL | EntitySemanticChunker | ✅ | Chunker preenche propriedades ETL |
| Schema ETL | EntityAwareRetriever | ✅ | Retriever usa `entities_local_ids` |
| EntitySemanticChunker | RerankerPlugin | ✅ | Metadata do chunk usado no reranking |
| QueryRewriterPlugin | IntelligentCache | ✅ | Query reescrita é cacheada |
| DynamicReranker | RerankerPlugin | ✅ | Trabalham em sequência |
| IntelligentCache | EntityAwareRetriever | ✅ | Cache antes e depois do retrieve |
| AdaptiveEntropyAnalyzer | QueryRewriterPlugin | ✅ | Entropia decide modo de rewrite |

### 6.2 Fluxo de Dados Completo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INGESTÃO                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Documento → Reader → ETL-Pré → EntitySemanticChunker → ETL-Pós → Weaviate   │
│                                                                              │
│ Schema: content, entities_local_ids, section_title, chunk_lang, chunk_date  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ (dados armazenados)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RETRIEVAL                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ Query                                                                        │
│   │                                                                          │
│   ├─► AdaptiveEntropyAnalyzer (decide rewrite)                              │
│   │                                                                          │
│   ├─► QueryRewriter/QueryBuilder (processa query)                           │
│   │                                                                          │
│   ├─► IntelligentCache.get() [RAG 2.0]                                      │
│   │   └─► Se HIT: retorna resposta cacheada                                 │
│   │                                                                          │
│   ├─► EntityAwareRetriever                                                   │
│   │   ├─► Extrai entidades da query                                         │
│   │   ├─► WHERE filter: entities_local_ids CONTAINS entity_id               │
│   │   ├─► Hybrid search: BM25(content) + Vector(embedding)                  │
│   │   └─► Retorna chunks filtrados                                          │
│   │                                                                          │
│   ├─► DynamicReranker [RAG 2.0]                                             │
│   │   └─► Score = similarity + recency + entity_frequency                   │
│   │                                                                          │
│   ├─► RerankerPlugin                                                         │
│   │   └─► Cross-encoder reranking (Cohere, Jina, etc.)                      │
│   │                                                                          │
│   └─► IntelligentCache.set() [RAG 2.0]                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ (chunks rerankeados)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GERAÇÃO                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ Contexto + Query → Generator → [IterativeSearch] → Resposta                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. RECOMENDAÇÕES

### 7.1 Melhorias de Curto Prazo

1. **Schema**
   - [ ] Migrar `chunk_date` de TEXT para DATE
   - [ ] Documentar propriedades obrigatórias vs opcionais

2. **Ingestão**
   - [ ] Garantir numpy/sklearn em produção
   - [ ] Adicionar métricas de qualidade de chunking

3. **Retrieval**
   - [ ] Documentar presets recomendados
   - [ ] Adicionar fallback se ETL não disponível

4. **Reranking**
   - [ ] Benchmark de latência por provider
   - [ ] Documentar trade-offs de cada preset

### 7.2 Melhorias de Médio Prazo

1. **Schema**
   - [ ] Adicionar propriedades para citation tracking
   - [ ] Suporte a multi-tenancy

2. **Retrieval**
   - [ ] Implementar query decomposition
   - [ ] Adicionar suporte a filtros compostos

3. **Reranking**
   - [ ] Implementar learned reranking (fine-tuned)
   - [ ] Adicionar A/B testing de rerankers

### 7.3 Melhorias de Longo Prazo

1. **RAG 2.0 Completo**
   - [ ] End-to-end training (retriever + generator)
   - [ ] Latent query rewriting (não textual)
   - [ ] Iterative search durante geração (completo)

---

## 8. CONCLUSÃO

### 8.1 Pontuação Geral

| Componente | Pontuação | Justificativa |
|------------|-----------|---------------|
| Schema | 8/10 | Bem estruturado, `chunk_date` poderia ser DATE |
| Ingestão | 9/10 | Entity-semantic chunking é state-of-the-art |
| Retrieval | 9/10 | Hybrid + entity filtering + cache |
| Reranking | 9/10 | Multi-provider + multi-dimensional |
| Geração | 7/10 | Iterative search é experimental |
| **GERAL** | **8.4/10** | Sistema robusto e bem integrado |

### 8.2 Veredicto

O sistema está **bem integrado** e segue **melhores práticas** de RAG:

✅ **Entity-aware** em toda a pipeline (ingestão → retrieval → reranking)  
✅ **Hybrid search** com BM25 + Vector  
✅ **Multi-stage reranking** com fallbacks  
✅ **Caching inteligente** por similaridade  
✅ **Configurabilidade** granular com presets  
✅ **Backward compatible** com Verba padrão  

O sistema implementa muitos conceitos do **RAG 2.0** (adaptive rewriting, multi-dimensional reranking, iterative search) de forma prática e sem necessidade de training end-to-end.

