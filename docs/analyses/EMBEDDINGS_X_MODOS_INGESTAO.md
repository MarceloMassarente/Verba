# Embeddings x Modos de Ingestão: Análise Cruzada

**Data:** Janeiro 2025  
**Versão:** 1.0  
**Status:** Análise Técnica Consolidada

---

## 📋 SUMÁRIO EXECUTIVO

Este documento cruza as **recomendações de embeddings do Guia Comparativo PT-BR** com os **modos de ingestão do Verba** (Universal e Semântica Visual), identificando as melhores combinações de modelo + modo para cada caso de uso.

### **Principais Descobertas:**

1. **Universal Mode**: Melhor com **Voyage 3.5** ou **BGE-M3** (versatilidade)
2. **Semântica Visual Mode**: Requer **BGE-M3** + **ColQwen2** (híbrido visual+text)
3. **Gap crítico**: Semântica Visual não tem visual embeddings implementado
4. **Oportunidade**: Universal pode se beneficiar de Serafim para docs curtos

---

## 1. MODOS DE INGESTÃO NO VERBA

### 1.1 Modo Universal (Universal A2 Reader)

**Características:**
- ✅ Aceita **qualquer formato** (PDF, DOCX, PPTX, TXT, JSON, CSV, etc.)
- ✅ Aplica **ETL A2 automaticamente** (NER + Section Scope)
- ✅ Integração **Tika** para melhor extração
- ✅ **SpaCy** para extração de entidades
- ✅ Processa **arquivos + URLs + JSON**

**Fluxo:**
```
Arquivo → Universal A2 Reader → Texto + Metadados → Chunking → Embedding → Weaviate
```

**Quando usar:**
- Documentos genéricos (PDFs, DOCX, etc.)
- Quando precisa de ETL automático
- Múltiplos formatos misturados
- URLs web

**Limitações:**
- Não otimizado para slides com gráficos/tabelas visuais
- Não captura layout visual (apenas texto)

---

### 1.2 Modo Semântica Visual (SlidesSemanticaVisualReader + Chunker)

**Características:**
- ✅ Recebe **arquivo .md pré-processado** por Visual API externa
- ✅ **Análise visual já foi feita** pela Visual API (não precisa de ColQwen2!)
- ✅ Extrai **metadata rico** do markdown estruturado (frameworks, stakeholders, visual semantics)
- ✅ Respeita **boundaries de slides** (não quebra meio de slide)
- ✅ Preserva **metadata estruturado V019** em cada chunk
- ✅ Cria **chunk de síntese global** no início
- ✅ **Entity guard-rails** (não corta entidades no meio)
- ✅ Suporta **multi-vector search** por slide, framework, stakeholder

**Formato de Entrada (.md pré-processado):**
```markdown
# Slide 1 - Título do Slide

**Frameworks:** BCG Matrix, Porter Five Forces
**Stakeholders:** Apple Inc., Microsoft Corp.
**Qualidade da Ponte:** 0.85
**Posição:** opening
**Tipo de Slide:** diagnostic
**Arquétipo Visual:** comparison_matrix
**Pattern Genetics:** market_analysis, competitive_positioning
**Reusability Score:** 0.92

Conteúdo do slide aqui...
```

**Fluxo Completo:**
```
PPTX/PDF → Visual API Externa → .md estruturado → SlidesSemanticaVisualReader → 
Extrai metadata → SlidesSemanticaVisualChunker → Chunks por Slide + Metadata → 
Embedding → Weaviate
```

**Quando usar:**
- Apresentações de consultoria (McKinsey, BCG, Bain) **já processadas pela Visual API**
- Slides com análise visual pré-existente
- Quando precisa de pattern genetics e metadata rico
- Documentos com estrutura V019

**Limitações:**
- Requer **pré-processamento pela Visual API** (não faz análise visual internamente)
- Não funciona com documentos genéricos (fallback para SentenceChunker)
- Depende do formato .md estruturado correto

---

## 2. CRUZAMENTO: EMBEDDINGS x MODOS DE INGESTÃO

### 2.1 Modo Universal + Embeddings

#### **Cenário 1: RAG Geral PT-BR**

**Recomendação do Guia:** Voyage 3.5

**Combinação:**
```
Universal A2 Reader + Voyage 3.5 Embedder
```

**Por quê:**
- ✅ Universal aceita qualquer formato (PDF, DOCX, etc.)
- ✅ Voyage 3.5: melhor custo-benefício ($0.06/1M tokens)
- ✅ Performance 85-90% em RAG geral
- ✅ 32k context window (docs longos)

**Performance esperada:**
- Precision@10: **85-90%**
- Recall@100: **90-95%**
- Custo: **$50-100/mês** (volume típico)

**Alternativa (budget zero):**
```
Universal A2 Reader + BGE-M3 (local)
```
- Performance: 75-80%
- Custo: $0 (self-hosted)

---

#### **Cenário 2: Jurídico BR**

**Recomendação do Guia:** Voyage Multilingual-2

**Combinação:**
```
Universal A2 Reader + Voyage Multilingual-2 Embedder
```

**Por quê:**
- ✅ Universal processa PDFs longos (contratos, processos)
- ✅ Voyage Multilingual-2: 32k context (contratos completos)
- ✅ Hard negatives training (diferencia cláusulas similares)
- ✅ ETL A2 extrai entidades jurídicas (pessoas, organizações)

**Performance esperada:**
- Busca jurisprudencial: **80%**
- Identificação cláusulas: **85%**
- Cross-references: **75%**

**Limitação:**
- Sem fine-tuning legal BR: gaps de 15-20% persistem

---

#### **Cenário 3: Financeiro PT-BR**

**Recomendação do Guia:** BGE-M3

**Combinação:**
```
Universal A2 Reader + BGE-M3 Embedder
```

**Por quê:**
- ✅ Universal processa DREs, balanços (PDF, Excel)
- ✅ BGE-M3: 8k context (DREs completos)
- ✅ Hybrid sparse (captura termos técnicos: CSLL, IRPJ)
- ✅ Zero custo (self-hosted)

**Performance esperada:**
- Busca por empresa/setor: **75%**
- Extração métricas: **65%**
- Comparação demonstrativos: **60%**

**Limitação:**
- Performance 65-70% (sem fine-tuning financeiro PT-BR)
- Tabelas complexas desafiadoras

**Técnicas compensatórias necessárias:**
- Table serialization inteligente
- Glossário financeiro BR (metadata injection)
- Multi-step retrieval

---

#### **Cenário 4: Docs Curtos (<512 tokens)**

**Recomendação do Guia:** Serafim-900M

**Combinação:**
```
Universal A2 Reader + Serafim-900M Embedder
```

**Por quê:**
- ✅ Universal processa qualquer formato
- ✅ Serafim-900M: SOTA português (0.854 MRR@10)
- ✅ Zero custo, LGPD-compliant
- ⚠️ Limitação: 512 tokens (adequado para chunks curtos)

**Performance esperada:**
- Precision@10: **80-85%** (melhor que BGE-M3 para docs curtos)
- Recall@100: **87%**

**Quando usar:**
- FAQs, manuais técnicos
- Documentos com chunks pequenos
- Prioridade absoluta performance PT-BR

---

### 2.2 Modo Semântica Visual + Embeddings

#### **Cenário 1: Consultoria PPTX (Ideal)**

**Recomendação do Guia:** BGE-M3 (visual já processado pela Visual API)

**Combinação Atual:**
```
Visual API Externa → .md estruturado → SlidesSemanticaVisualReader → 
SlidesSemanticaVisualChunker + BGE-M3 Embedder
```

**O que funciona:**
- ✅ **Visual API externa** já fez análise visual (não precisa ColQwen2!)
- ✅ SlidesSemanticaVisualReader extrai metadata rico do .md
- ✅ SlidesSemanticaVisualChunker preserva metadata (frameworks, stakeholders)
- ✅ BGE-M3: 8k context (apresentações completas)
- ✅ Hybrid sparse (captura frameworks: BCG, Porter)
- ✅ Multi-vector search por slide/framework

**O que falta:**
- ⚠️ **BGE-M3 sparse não usado** (perdendo 10-15% performance)
- ⚠️ Metadata rico não injetado no embedding (apenas armazenado)

**Performance atual:**
- Extração frameworks: **70%** (via metadata, não embedding)
- Quantificação: **75%**
- Pattern genetics: **60%** (limitado sem fine-tuning)

**Performance esperada (com BGE-M3 hybrid):**
- Extração frameworks: **75%** (+5% com sparse)
- Quantificação: **80%** (+5%)
- Pattern genetics: **65%** (+5% com sparse)

---

#### **Cenário 2: Slides com Gráficos/Tabelas**

**Recomendação do Guia:** BGE-M3 (visual já processado pela Visual API)

**Combinação Atual:**
```
Visual API Externa → .md com análise visual → SlidesSemanticaVisualReader → 
SlidesSemanticaVisualChunker + BGE-M3 Embedder
```

**Arquitetura atual:**
```python
# Fluxo real:
# 1. Visual API externa processa PPTX/PDF
#    - Analisa gráficos, tabelas, layout
#    - Extrai metadata visual (visual_archetype, semantic_bridge_quality)
#    - Gera .md estruturado com metadata rico

# 2. SlidesSemanticaVisualReader recebe .md
#    - Extrai metadata do markdown (frameworks, stakeholders, visual_archetype)
#    - Cria slides_metadata estruturado

# 3. SlidesSemanticaVisualChunker cria chunks
#    - Preserva metadata em cada chunk
#    - Respeita boundaries de slides

# 4. BGE-M3 embeda texto + metadata
#    - Texto do slide
#    - Metadata rico (frameworks, stakeholders) pode ser injetado no texto
```

**O que funciona:**
- ✅ Visual API externa já fez análise visual (não precisa ColQwen2!)
- ✅ Metadata visual extraído e armazenado
- ✅ BGE-M3 embeda texto com contexto rico

**O que falta:**
- ⚠️ **Metadata não injetado no embedding** (apenas armazenado como propriedade)
- ⚠️ **BGE-M3 sparse não usado** (perdendo 10-15%)

**Melhoria possível:**
- Injetar metadata no texto antes de embedar:
  ```python
  enriched_text = f"""
  Frameworks: {', '.join(frameworks)}
  Stakeholders: {', '.join(stakeholders)}
  Visual Archetype: {visual_archetype}
  
  {slide_content}
  """
  ```

---

#### **Cenário 3: Slides Texto-Only (Sem Gráficos)**

**Recomendação do Guia:** BGE-M3

**Combinação:**
```
SlidesSemanticaVisualChunker + BGE-M3 Embedder
```

**Por quê:**
- ✅ SlidesSemanticaVisual preserva estrutura de slides
- ✅ BGE-M3: 8k context (apresentações completas)
- ✅ Hybrid sparse (captura frameworks, termos técnicos)
- ✅ Metadata rico permite multi-vector search

**Performance esperada:**
- Busca por framework: **80%**
- Síntese cross-deck: **65%**
- Pattern genetics: **60%** (limitado sem visual)

**Adequado quando:**
- Slides são principalmente texto
- Gráficos são simples ou descritos em texto
- Prioridade é estrutura e frameworks

---

## 3. MATRIZ DE DECISÃO: MODO x EMBEDDING

| Caso de Uso | Modo de Ingestão | Embedding Recomendado | Performance | Status |
|-------------|------------------|---------------------|-------------|--------|
| **RAG Geral PT-BR** | Universal | Voyage 3.5 | 85-90% | ⚠️ Voyage 3.5 faltando |
| **RAG Geral PT-BR (docs curtos)** | Universal | Serafim-900M | 80-85% | ⚠️ Serafim faltando |
| **Jurídico BR** | Universal | Voyage Multilingual-2 | 75-80% | ✅ Disponível |
| **Financeiro PT-BR** | Universal | BGE-M3 | 65-70% | ✅ Disponível |
| **Consultoria PPTX (texto)** | Semântica Visual | BGE-M3 | 70-75% | ✅ Disponível |
| **Consultoria PPTX (visual)** | Semântica Visual | BGE-M3 + ColQwen2 | 75-80% | ❌ ColQwen2 faltando |
| **RH Code-Switching** | Universal | Voyage Multi-2 + MiniLM | 82-85% | ⚠️ Two-stage faltando |

---

## 4. GAPS IDENTIFICADOS POR MODO

### 4.1 Modo Universal

**Gaps:**
1. ❌ Voyage 3.5 não disponível (crítico)
2. ❌ Serafim models não disponíveis (importante)
3. ⚠️ Default não otimizado PT-BR (all-MiniLM-L6-v2)

**Impacto:**
- Perdendo melhor custo-benefício (Voyage 3.5)
- Perdendo SOTA português (Serafim)
- Performance subótima para usuários BR

**Ações:**
- Adicionar Voyage 3.5 ao VoyageAIEmbedder
- Adicionar Serafim ao SentenceTransformersEmbedder
- Mudar default para BGE-M3

---

### 4.2 Modo Semântica Visual

**Gaps:**
1. ⚠️ **BGE-M3 sparse não usado** (perdendo 10-15%)
2. ⚠️ **Metadata rico não injetado no embedding** (apenas armazenado)
3. ⚠️ **Visual API externa não integrada** (processo manual)

**Impacto:**
- Perdendo 10-15% performance (sparse embeddings não usados)
- Metadata rico não aproveitado no embedding (apenas filtros)
- Processo de ingestão não automatizado (requer Visual API externa)

**Ações:**
- Implementar BGE-M3 hybrid retrieval (sparse) - **prioridade alta**
- Injetar metadata no texto antes de embedar - **prioridade média**
- Documentar integração com Visual API - **prioridade baixa**

---

## 5. RECOMENDAÇÕES POR COMBINAÇÃO

### 5.1 Universal + Voyage 3.5 (Ideal para RAG Geral)

**Stack:**
```
Reader: Universal A2
Chunker: Entity-Semantic (ou Recursive)
Embedder: Voyage 3.5
Retriever: EntityAwareRetriever (ou WindowRetriever)
```

**Performance:**
- Precision@10: **85-90%**
- Recall@100: **90-95%**
- Custo: **$50-100/mês**

**Status:** ⚠️ Voyage 3.5 precisa ser adicionado

---

### 5.2 Universal + BGE-M3 (Budget Zero)

**Stack:**
```
Reader: Universal A2
Chunker: Entity-Semantic
Embedder: BGE-M3 (local)
Retriever: EntityAwareRetriever
```

**Performance:**
- Precision@10: **75-80%**
- Recall@100: **88%**
- Custo: **$0** (self-hosted)

**Status:** ✅ Disponível (mas default não é BGE-M3)

---

### 5.3 Semântica Visual + BGE-M3 (Consultoria Texto)

**Stack:**
```
Reader: Universal A2 (ou Docling)
Chunker: Slides Semântica Visual
Embedder: BGE-M3
Retriever: EntityAwareRetriever (com multi-vector)
```

**Performance:**
- Extração frameworks: **70%**
- Pattern genetics: **60%**
- Síntese cross-deck: **65%**

**Status:** ✅ Disponível (mas sem visual embeddings)

---

### 5.4 Semântica Visual + BGE-M3 (Consultoria Visual - Ideal)

**Stack:**
```
Visual API Externa → .md estruturado → Slides Semântica Visual Reader → 
Chunker: Slides Semântica Visual → Embedder: BGE-M3 (hybrid) → 
Retriever: EntityAwareRetriever (multi-vector)
```

**Performance:**
- Extração frameworks: **75%** (via metadata + sparse)
- Pattern genetics: **65%** (limitado sem fine-tuning)
- Síntese cross-deck: **70%**

**Status:** ✅ Disponível (mas BGE-M3 sparse não usado)

---

## 6. PLANO DE AÇÃO CONSOLIDADO

### 6.1 Fase 1: Melhorias Modo Universal (1 semana)

**Prioridade:** 🔴 ALTA

1. **Adicionar Voyage 3.5**
   - Arquivo: `goldenverba/components/embedding/VoyageAIEmbedder.py`
   - Impacto: +20-25% performance, -50% custo
   - Esforço: 🟢 BAIXO

2. **Adicionar Serafim models**
   - Arquivo: `goldenverba/components/embedding/SentenceTransformersEmbedder.py`
   - Impacto: SOTA português para docs curtos
   - Esforço: 🟢 BAIXO

3. **Mudar default para BGE-M3**
   - Arquivo: `goldenverba/components/embedding/SentenceTransformersEmbedder.py`
   - Impacto: +10-15% performance default
   - Esforço: 🟢 BAIXO

---

### 6.2 Fase 2: Melhorias Modo Semântica Visual (1-2 semanas)

**Prioridade:** 🟡 MÉDIA

1. **Implementar BGE-M3 Hybrid Retrieval**
   - Arquivos: `SentenceTransformersEmbedder.py`, `WeaviateManager`
   - Impacto: +10-15% performance (sparse embeddings)
   - Esforço: 🟡 MÉDIO
   - **Nota:** Visual API externa já fez análise visual, não precisa ColQwen2!

2. **Injetar Metadata no Embedding**
   - Arquivo: `SlidesSemanticaVisualChunker.py`
   - Impacto: +5-10% (metadata rico no embedding)
   - Esforço: 🟢 BAIXO
   - **Ação:** Adicionar frameworks/stakeholders ao texto antes de embedar

3. **Documentar Integração Visual API**
   - Arquivo: `docs/guides/INTEGRACAO_VISUAL_API.md` (NOVO)
   - Impacto: Facilita uso do modo Semântica Visual
   - Esforço: 🟢 BAIXO

---

## 7. IMPACTO ESPERADO POR MODO

### 7.1 Modo Universal

**Antes:**
- Default: all-MiniLM-L6-v2 → 60-65% PT-BR
- Voyage disponível mas não otimizado

**Depois (Fase 1):**
- Default: BGE-M3 → 70-75% PT-BR (+10-15%)
- Voyage 3.5 disponível → 85-90% RAG geral (+20-25%)
- Serafim disponível → 80-85% docs curtos (+15-20%)

**Economia:**
- Voyage 3.5: -50% custo ($0.06 vs $0.12)

---

### 7.2 Modo Semântica Visual

**Antes:**
- BGE-M3 apenas dense → 70-75% consultoria
- Metadata rico não injetado → perdendo contexto

**Depois (Fase 2):**
- BGE-M3 hybrid (dense+sparse) → 75-80% (+5-10%)
- Metadata injetado no embedding → +5-10% adicional
- Total: 80-85% consultoria (+10-15%)

**Melhoria:**
- Pattern genetics: 60% → 65% (+5% com sparse)
- Extração frameworks: 70% → 75% (+5% com sparse + metadata)
- **Nota:** Visual API externa já processa gráficos, não precisa ColQwen2!

---

## 8. CONCLUSÃO

### 8.1 Resumo de Combinações Ideais

| Modo | Embedding | Caso de Uso | Performance | Status |
|------|-----------|-------------|-------------|--------|
| **Universal** | Voyage 3.5 | RAG Geral PT-BR | 85-90% | ⚠️ Faltando |
| **Universal** | BGE-M3 | Financeiro PT-BR | 65-70% | ✅ Disponível |
| **Universal** | Serafim-900M | Docs Curtos PT-BR | 80-85% | ⚠️ Faltando |
| **Semântica Visual** | BGE-M3 | Consultoria PPTX (texto) | 70-75% | ✅ Disponível |
| **Semântica Visual** | BGE-M3 (hybrid) | Consultoria PPTX (visual) | 75-80% | ⚠️ Sparse faltando |

---

### 8.2 Próximos Passos

**Imediato (1 semana):**
1. Adicionar Voyage 3.5 (crítico para Universal)
2. Adicionar Serafim (importante para Universal)
3. Mudar default BGE-M3 (melhoria imediata)

**Curto prazo (1 mês):**
4. BGE-M3 Hybrid Retrieval (melhora Semântica Visual)
5. Documentar combinações ideais

**Médio prazo (2-3 meses):**
6. Documentar integração Visual API (facilita uso)
7. Otimizar injeção de metadata no embedding

---

**Documento criado em:** Janeiro 2025  
**Última atualização:** Janeiro 2025  
**Baseado em:** Guia Comparativo Embeddings PT-BR + Análise Modos de Ingestão Verba

