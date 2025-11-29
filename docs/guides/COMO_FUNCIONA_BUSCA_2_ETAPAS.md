# Como Funciona a Busca em 2 Etapas (Two-Phase Search)

## 📋 Visão Geral

A **busca em 2 etapas** (Two-Phase Search) é um modo de busca otimizado para documentos de consultoria que combina:
- **Fase 1**: Filtro por entidades (busca **léxica/híbrida** com mais BM25)
- **Fase 2**: Busca semântica dentro do subespaço filtrado (busca **semântica/híbrida** com multi-vector)
- **Rerank**: Reordenação final dos resultados (após as 2 fases)

---

## 🔄 Fluxo Completo: Fase 1 → Fase 2 → Rerank

```
QUERY DO USUÁRIO
       ↓
┌─────────────────────────────────────────┐
│  FASE 1: FILTRO POR ENTIDADES           │
│  (Busca Léxica/Híbrida)                 │
└─────────────────────────────────────────┘
       ↓
  Subespaço (UUIDs)
       ↓
┌─────────────────────────────────────────┐
│  FASE 2: BUSCA SEMÂNTICA                │
│  (Busca Semântica/Híbrida + Multi-Vector)│
└─────────────────────────────────────────┘
       ↓
  Chunks Retornados
       ↓
┌─────────────────────────────────────────┐
│  RERANK: REORDENAÇÃO FINAL              │
│  (Cross-encoder, Metadata, etc.)        │
└─────────────────────────────────────────┘
       ↓
  RESULTADOS FINAIS
```

---

## 🔍 FASE 1: Filtro por Entidades (Subespaço)

### O que busca?
**Busca chunks que mencionam as entidades detectadas na query** (Apple, Microsoft, frameworks, setores, etc.)

### Que tipo de busca usa?
**Busca Híbrida com mais BM25 (léxica)** - `alpha=0.4`

**Por quê mais BM25?**
- BM25 (léxica) é melhor para encontrar **nomes exatos** de entidades
- Não precisa ser muito relevante semanticamente, apenas identificar chunks com a entidade
- O objetivo é criar um **subespaço** (lista de UUIDs), não retornar os melhores resultados

### Parâmetros da Fase 1:

```python
# Busca híbrida com:
- alpha = 0.4  # 40% semântico, 60% BM25 (léxica) → MAIS BM25
- limit = limit * 3  # Busca 3x mais chunks (ex: se limit=5, busca 15)
- Filtro: section_entity_ids ou entities_local_ids contém entidades
- Query: Query original (ou expandida para entidades)
```

### Exemplo:
```
Query: "estratégia de inovação da Apple"

Fase 1:
- Detecta entidade: "Apple"
- Filtro: section_entity_ids CONTAINS "Apple"
- Busca híbrida: alpha=0.4 (mais BM25)
- Resultado: 30 chunks que mencionam "Apple"
- Extrai UUIDs desses 30 chunks → Subespaço
```

### Características:
- ✅ **Léxica (BM25) predominante**: Encontra nomes exatos
- ✅ **Ampla**: Busca 3x mais chunks para ter subespaço maior
- ✅ **Foco em entidades**: Não precisa ser semanticamente relevante
- ✅ **Cria subespaço**: Lista de UUIDs para Fase 2 filtrar

---

## 🎯 FASE 2: Busca Semântica dentro do Subespaço

### O que busca?
**Busca chunks semanticamente relevantes dentro do subespaço criado na Fase 1**

### Que tipo de busca usa?
**Busca Híbrida Semântica + Multi-Vector Search** - `alpha` otimizado (geralmente 0.5-0.7)

**Por quê mais semântica?**
- Agora que já temos chunks com a entidade, precisamos encontrar os **mais relevantes semanticamente**
- Busca por conceitos, temas, sinônimos (não apenas palavras exatas)
- Pode usar **multi-vector search** (concept_vec, sector_vec, company_vec)

### Parâmetros da Fase 2:

```python
# Busca híbrida semântica com:
- alpha = rewritten_alpha  # Otimizado (geralmente 0.5-0.7) → MAIS SEMÂNTICO
- limit = limit  # Busca quantidade normal (ex: 5-10 chunks)
- Filtro: uuid IN (UUIDs da Fase 1) + outros filtros
- Query: Query expandida para temas/conceitos
- Multi-Vector: Se habilitado, busca em concept_vec, sector_vec, company_vec
```

### Exemplo:
```
Query: "estratégia de inovação da Apple"

Fase 2:
- Query expandida: ["estratégia de inovação", "inovação estratégica", "estratégias inovadoras"]
- Filtro: uuid IN [UUIDs dos 30 chunks da Fase 1]
- Busca híbrida: alpha=0.6 (mais semântico)
- Multi-Vector: concept_vec (frameworks/estratégias) + company_vec (Apple)
- Resultado: 5 chunks mais relevantes sobre "estratégia de inovação da Apple"
```

### Características:
- ✅ **Semântica predominante**: Encontra conceitos, sinônimos, temas
- ✅ **Focada**: Busca quantidade normal (não ampla como Fase 1)
- ✅ **Dentro do subespaço**: Apenas chunks que têm a entidade
- ✅ **Multi-vector**: Pode buscar em múltiplos vetores especializados
- ✅ **Query expansion**: Gera variações focadas em temas/conceitos

---

## 🔄 RERANK: Reordenação Final

### Quando acontece?
**Depois das 2 fases** - Rerankea os chunks retornados pela Fase 2

### O que faz?
**Reordena os chunks por relevância** usando modelos mais sofisticados que a busca inicial

### Tipos de Rerankers disponíveis:

1. **Metadata Reranker** (sempre disponível):
   - Metadata matching (40%)
   - Keyword matching (30%)
   - Content length (10%)

2. **Cross-Encoder Rerankers** (opcionais):
   - **Haystack CrossEncoderRanker** (local)
   - **Cohere Rerank API** (multilíngue)
   - **Jina Rerank API** (rápido)
   - **VoyageAI Rerank API** (alta qualidade)
   - **Contextual AI Rerank API** (com instruções customizadas)

### Parâmetros do Rerank:

```python
# Rerank recebe:
- Chunks: Resultados da Fase 2
- Query: Query original do usuário
- Top K: Quantidade final (Reranker Top K configurado, ex: 5)
```

### Exemplo:
```
Fase 2 retornou: 10 chunks sobre "estratégia de inovação da Apple"

Rerank:
- Processa todos os 10 chunks
- Usa Cross-Encoder para calcular relevância precisa
- Reordena por score
- Retorna top 5 (Reranker Top K = 5)
```

### Características:
- ✅ **Após as 2 fases**: Recebe resultados já filtrados e buscados
- ✅ **Cross-encoder**: Modelo mais preciso que busca inicial
- ✅ **Reordena**: Pode mudar a ordem dos chunks
- ✅ **Limita quantidade**: Retorna apenas top K configurado

---

## 📊 Comparação: Fase 1 vs Fase 2

| Aspecto | **FASE 1** | **FASE 2** |
|---------|-----------|-----------|
| **Objetivo** | Criar subespaço (filtrar por entidades) | Buscar chunks relevantes no subespaço |
| **Tipo de busca** | **Léxica/Híbrida** (mais BM25) | **Semântica/Híbrida** (mais vetor) |
| **Alpha** | `0.4` (40% semântico, 60% BM25) | `0.5-0.7` (50-70% semântico) |
| **Limit** | `limit * 3` (amplo, ex: 15 chunks) | `limit` (focado, ex: 5 chunks) |
| **Filtro** | Por entidades (`section_entity_ids`) | Por UUIDs do subespaço + outros |
| **Query** | Query original/expandida para entidades | Query expandida para temas |
| **Multi-Vector** | ❌ Não usa | ✅ Pode usar (concept_vec, etc.) |
| **Named Vectors** | ❌ Não usa | ✅ Usa (se habilitado) |
| **Resultado** | Lista de UUIDs (subespaço) | Chunks relevantes ordenados |

---

## 🔄 Onde Entra o Rerank?

### Fluxo Completo com Rerank:

```
1. QUERY DO USUÁRIO
   ↓
2. FASE 1: Filtro por Entidades
   - Busca léxica/híbrida (alpha=0.4, mais BM25)
   - Retorna: 30 chunks (subespaço)
   ↓
3. FASE 2: Busca Semântica
   - Busca semântica/híbrida (alpha=0.6, mais vetor)
   - Filtra pelo subespaço da Fase 1
   - Retorna: 10 chunks relevantes
   ↓
4. RERANK: Reordenação Final
   - Recebe os 10 chunks da Fase 2
   - Usa Cross-Encoder para reordenar
   - Retorna: Top 5 chunks (Reranker Top K = 5)
   ↓
5. RESULTADOS FINAIS
   - 5 chunks mais relevantes e bem ordenados
```

### Observações Importantes:

1. **Rerank acontece DEPOIS das 2 fases**
   - Não participa da Fase 1 nem da Fase 2
   - Recebe os resultados finais da Fase 2

2. **Rerank é opcional**
   - Se não houver reranker configurado, retorna resultados da Fase 2
   - Se falhar, continua sem reranking (não crítico)

3. **Rerank pode reduzir quantidade**
   - Se Fase 2 retornou 10 chunks e Reranker Top K = 5
   - Retorna apenas os 5 melhores após reranking

---

## 💡 Resumo Executivo

### FASE 1: Filtro por Entidades
- **Busca:** Léxica/Híbrida (mais BM25, `alpha=0.4`)
- **Objetivo:** Encontrar chunks que mencionam entidades
- **Ampla:** Busca 3x mais chunks para criar subespaço
- **Resultado:** Lista de UUIDs (subespaço)

### FASE 2: Busca Semântica
- **Busca:** Semântica/Híbrida (mais vetor, `alpha=0.5-0.7`)
- **Objetivo:** Encontrar chunks relevantes dentro do subespaço
- **Focada:** Busca quantidade normal
- **Resultado:** Chunks relevantes ordenados

### RERANK: Reordenação Final
- **Quando:** Depois das 2 fases
- **Como:** Cross-encoder ou metadata reranker
- **Objetivo:** Reordenar por relevância precisa
- **Resultado:** Top K chunks finais

---

## 📝 Exemplo Prático Completo

### Query: "estratégia de inovação da Apple"

#### FASE 1: Filtro por Entidades
```
1. Detecta entidade: "Apple"
2. Query: "estratégia de inovação da Apple" (ou expandida para entidades)
3. Busca híbrida:
   - alpha = 0.4 (60% BM25, 40% semântico)
   - limit = 15 chunks (5 * 3)
   - Filtro: section_entity_ids CONTAINS "Apple"
4. Retorna: 30 chunks que mencionam "Apple"
5. Extrai UUIDs → Subespaço = [uuid1, uuid2, ..., uuid30]
```

#### FASE 2: Busca Semântica
```
1. Query expandida: ["estratégia de inovação", "inovação estratégica", ...]
2. Embedding gerado da query expandida
3. Busca híbrida semântica:
   - alpha = 0.6 (60% semântico, 40% BM25)
   - limit = 5 chunks
   - Filtro: uuid IN [uuid1, uuid2, ..., uuid30]
   - Multi-Vector: concept_vec + company_vec
4. Retorna: 5 chunks sobre "estratégia de inovação da Apple"
```

#### RERANK: Reordenação Final
```
1. Recebe: 5 chunks da Fase 2
2. Query: "estratégia de inovação da Apple" (original)
3. Cross-Encoder calcula relevância precisa de cada chunk
4. Reordena por score
5. Retorna: 5 chunks (mesmos chunks, melhor ordenados)
```

---

## ⚙️ Configurações Recomendadas

### Para Documentos de Consultoria:
```json
{
  "Two-Phase Search Mode": "auto",
  "Enable Multi-Vector Search": true,
  "Enable Relative Score Fusion": true,
  "Enable Query Expansion": true,
  "Enable Dynamic Alpha": true,
  "Reranker Top K": 5
}
```

### Quando usar cada modo:

**Use Two-Phase Search se:**
- ✅ Documentos de consultoria
- ✅ Queries com entidades + conceitos
- ✅ Precisa de alta precisão

**Use busca normal se:**
- ✅ Queries simples
- ✅ Sem entidades específicas
- ✅ Precisa de velocidade

---

## 📚 Referências

- [`EXPLICACAO_DETALHADA_FUNCIONALIDADES.md`](./EXPLICACAO_DETALHADA_FUNCIONALIDADES.md) - Detalhes técnicos
- [`MODOS_DE_BUSCA_COMPLETO.md`](./MODOS_DE_BUSCA_COMPLETO.md) - Comparação de modos
- [`TOP_K_PRE_POS_RERANK.md`](./TOP_K_PRE_POS_RERANK.md) - Sobre Limit vs Reranker Top K

---

## 🎯 Boost de Proximidade (Document-Level Only)

### Problema Resolvido

**Cenário:** 
- Chunk 1 menciona "Apple" (entidade)
- Chunk 2 fala sobre "governança" (assunto pesquisado), mas não menciona "Apple" diretamente

**Problema sem Boost de Proximidade:**
- Fase 1 inclui o documento (porque tem Apple no chunk 1)
- Fase 2 busca semanticamente por "governança" nos chunks do documento
- Chunk 2 pode não ter alta relevância semântica isolada
- Resultado: Chunk 2 pode não ser encontrado ou ter baixa prioridade

### Como Funciona o Boost de Proximidade

**Apenas no modo Document-Level:**

1. **Fase 1**: Além de identificar documentos, também identifica os **chunks específicos** que mencionam a entidade
   - Extrai `(doc_uuid, chunk_id)` de cada chunk com entidade
   - Exemplo: Documento A, chunk_id=0 menciona "Apple"

2. **Fase 2**: Após busca semântica, aplica **boost de proximidade**:
   - Chunks que estão **adjacentes** (±2 posições) aos chunks com entidades recebem boost
   - Score combinado: 70% relevância semântica + 30% boost de proximidade
   - Chunks próximos são priorizados mesmo com relevância semântica menor

### Exemplo Prático

```
Documento: "Análise Apple 2024"
├─ Chunk 0: "Apple foi fundada em 1976..." [menciona Apple]
├─ Chunk 1: "A governança corporativa da empresa..." [fala sobre governança]
├─ Chunk 2: "Os produtos principais incluem..." 
└─ Chunk 3: "A estratégia de inovação..." [fala sobre inovação]

Query: "governança na Apple"
```

**Sem Boost de Proximidade:**
- Fase 1: Documento incluído (tem Apple no chunk 0)
- Fase 2: Busca por "governança"
  - Chunk 1 pode não ter alta relevância semântica isolada
  - Pode ser ignorado ou ter baixa prioridade

**Com Boost de Proximidade:**
- Fase 1: Documento incluído + identifica chunk 0 (menciona Apple)
- Fase 2: Busca por "governança"
  - Chunk 1 está a ±1 posição do chunk 0 → **BOOST ALTO** (0.8)
  - Score combinado: relevância semântica × 0.7 + 0.8 × 0.3
  - **Chunk 1 é priorizado** mesmo com relevância semântica menor

### Parâmetros do Boost

- **Proximity Window**: ±2 posições (configurável)
- **Boost por Distância**:
  - Distância 0 (mesmo chunk): boost 1.0
  - Distância 1 (adjacente): boost 0.7
  - Distância 2: boost 0.4
  - >2: sem boost

- **Score Final**: 70% relevância semântica + 30% boost de proximidade

### Quando é Aplicado

✅ **Modo Document-Level**: Sempre ativo automaticamente  
❌ **Modo Chunk-Level**: Não aplicado (já filtra por chunks específicos)

---

---

## 🎯 Boost de Proximidade (Document-Level Only)

### Problema Resolvido

**Cenário:** 
- Chunk 1 menciona "Apple" (entidade)
- Chunk 2 fala sobre "governança" (assunto pesquisado), mas não menciona "Apple" diretamente

**Problema sem Boost de Proximidade:**
- Fase 1 inclui o documento (porque tem Apple no chunk 1)
- Fase 2 busca semanticamente por "governança" nos chunks do documento
- Chunk 2 pode não ter alta relevância semântica isolada
- Resultado: Chunk 2 pode não ser encontrado ou ter baixa prioridade

### Como Funciona o Boost de Proximidade

**Apenas no modo Document-Level:**

1. **Fase 1**: Além de identificar documentos, também identifica os **chunks específicos** que mencionam a entidade
   - Extrai `(doc_uuid, chunk_id)` de cada chunk com entidade
   - Exemplo: Documento A, chunk_id=0 menciona "Apple"

2. **Fase 2**: Após busca semântica, aplica **boost de proximidade**:
   - Chunks que estão **adjacentes** (±2 posições) aos chunks com entidades recebem boost
   - Score combinado: 70% relevância semântica + 30% boost de proximidade
   - Chunks próximos são priorizados mesmo com relevância semântica menor

### Exemplo Prático

```
Documento: "Análise Apple 2024"
├─ Chunk 0: "Apple foi fundada em 1976..." [menciona Apple]
├─ Chunk 1: "A governança corporativa da empresa..." [fala sobre governança]
├─ Chunk 2: "Os produtos principais incluem..." 
└─ Chunk 3: "A estratégia de inovação..." [fala sobre inovação]

Query: "governança na Apple"
```

**Sem Boost de Proximidade:**
- Fase 1: Documento incluído (tem Apple no chunk 0)
- Fase 2: Busca por "governança"
  - Chunk 1 pode não ter alta relevância semântica isolada
  - Pode ser ignorado ou ter baixa prioridade

**Com Boost de Proximidade:**
- Fase 1: Documento incluído + identifica chunk 0 (menciona Apple)
- Fase 2: Busca por "governança"
  - Chunk 1 está a ±1 posição do chunk 0 → **BOOST ALTO** (0.7)
  - Score combinado: relevância semântica × 0.7 + 0.7 × 0.3
  - **Chunk 1 é priorizado** mesmo com relevância semântica menor

### Parâmetros do Boost

- **Proximity Window**: ±2 posições (configurável internamente)
- **Boost por Distância**:
  - Distância 0 (mesmo chunk): boost 1.0
  - Distância 1 (adjacente): boost 0.7
  - Distância 2: boost 0.4
  - >2: sem boost

- **Score Final**: 70% relevância semântica + 30% boost de proximidade

### Quando é Aplicado

✅ **Modo Document-Level**: Sempre ativo automaticamente  
❌ **Modo Chunk-Level**: Não aplicado (já filtra por chunks específicos)

---

**Última atualização**: Janeiro 2025  
**Status**: Documentação de busca em 2 etapas  
**Compatibilidade**: Verba 2.1.x + EntityAwareRetriever

