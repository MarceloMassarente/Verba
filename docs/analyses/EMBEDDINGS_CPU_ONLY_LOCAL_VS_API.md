# Embeddings Sem GPU: Local vs API - Análise Comparativa

**Data:** Janeiro 2025  
**Versão:** 1.0  
**Status:** Análise Técnica

---

## 📋 SUMÁRIO EXECUTIVO

Este documento compara **modelos de embedding sem GPU**, analisando **opções locais (CPU-only)** vs **APIs**, considerando performance, custo, latência e facilidade de uso.

### **Principais Descobertas:**

1. **CPU-only local**: Performance 60-75%, latência 200-500ms, **zero custo**
2. **APIs**: Performance 75-90%, latência 100-200ms, **$50-300/mês**
3. **Melhor CPU-only local**: **BGE-M3** (70-75% performance, 8k context)
4. **Melhor API custo-benefício**: **Voyage 3.5** (85-90% performance, $0.06/1M tokens)
5. **Break-even**: ~2-5M páginas/mês (dependendo do modelo)

---

## 1. MODELOS LOCAIS (CPU-ONLY)

### 1.1 BGE-M3 (BAAI/bge-m3)

**Especificações:**
- **Parâmetros:** 568M
- **Context:** 8,192 tokens
- **Dimensões:** 1024
- **VRAM necessária:** 0 (CPU-only funciona)
- **Tamanho modelo:** 1.2GB (FP16), 2.3GB (FP32)

**Performance CPU-only:**
- **Latência:** ~200-500ms por query (batch 1)
- **Throughput:** ~10-20 docs/sec (CPU)
- **Performance PT-BR:** 70-75% (estimado)
- **Hybrid retrieval:** ✅ Suporta (dense + sparse)

**Requisitos:**
- CPU: 4+ cores recomendado
- RAM: 4-8GB (modelo + batch)
- Storage: 2-3GB

**Vantagens:**
- ✅ Zero custo API
- ✅ 8k context (docs longos)
- ✅ Hybrid retrieval nativo
- ✅ LGPD-compliant (100% local)
- ✅ Controle total pipeline

**Desvantagens:**
- ⚠️ Latência alta (200-500ms)
- ⚠️ Throughput limitado (10-20 docs/sec)
- ⚠️ Performance 10-15% inferior a APIs

**Quando usar:**
- Budget zero
- Dados sensíveis (LGPD crítico)
- Volume <2M páginas/mês
- Latência <500ms aceitável

---

### 1.2 Serafim-900M (PORTULAN)

**Especificações:**
- **Parâmetros:** 900M
- **Context:** 512 tokens (limitação crítica)
- **Dimensões:** 1024
- **VRAM necessária:** 0 (CPU-only funciona)
- **Tamanho modelo:** 1.8GB (FP16)

**Performance CPU-only:**
- **Latência:** ~200-300ms por query
- **Throughput:** ~15-25 docs/sec (CPU)
- **Performance PT-BR:** 80-85% (SOTA português validado)
- **Hybrid retrieval:** ❌ Não suporta (só dense)

**Requisitos:**
- CPU: 4+ cores recomendado
- RAM: 6-10GB (modelo + batch)
- Storage: 2GB

**Vantagens:**
- ✅ **SOTA português** (0.854 MRR@10)
- ✅ Zero custo API
- ✅ LGPD-compliant (100% local)
- ✅ Performance melhor que BGE-M3 para PT-BR

**Desvantagens:**
- ❌ **512 tokens context** (fatal para docs longos)
- ⚠️ Latência alta (200-300ms)
- ⚠️ Throughput limitado (15-25 docs/sec)
- ❌ Não suporta sparse embeddings

**Quando usar:**
- Docs curtos (<512 tokens/chunk)
- Prioridade absoluta performance PT-BR
- Budget zero
- Latência <300ms aceitável

**Quando NÃO usar:**
- Documentos longos (jurídico, financeiro, consultoria)
- Necessita context window >512 tokens

---

### 1.3 all-MiniLM-L6-v2 (Default Atual)

**Especificações:**
- **Parâmetros:** 22.7M (muito leve)
- **Context:** 256 tokens (muito limitado)
- **Dimensões:** 384
- **VRAM necessária:** 0 (CPU-only funciona)
- **Tamanho modelo:** 90MB

**Performance CPU-only:**
- **Latência:** ~20-50ms por query (muito rápido!)
- **Throughput:** ~50-100 docs/sec (CPU)
- **Performance PT-BR:** 60-65% (baixo)
- **Hybrid retrieval:** ❌ Não suporta

**Requisitos:**
- CPU: 2+ cores suficiente
- RAM: 1-2GB (muito leve)
- Storage: 100MB

**Vantagens:**
- ✅ Extremamente rápido (20-50ms)
- ✅ Muito leve (90MB)
- ✅ Zero custo
- ✅ Baixo uso de recursos

**Desvantagens:**
- ❌ **256 tokens context** (muito limitado)
- ❌ Performance baixa (60-65% PT-BR)
- ❌ Não otimizado PT-BR

**Quando usar:**
- Prototipagem rápida
- Latência crítica (<50ms)
- Recursos muito limitados
- Performance não crítica

**Quando NÃO usar:**
- Produção séria
- Documentos longos
- Performance importante

---

### 1.4 paraphrase-MiniLM-L6-v2

**Especificações:**
- **Parâmetros:** 22.7M
- **Context:** 128 tokens (crítico)
- **Dimensões:** 384
- **VRAM necessária:** 0
- **Tamanho modelo:** 90MB

**Performance CPU-only:**
- **Latência:** ~15-30ms por query (ultra-rápido!)
- **Throughput:** ~60-120 docs/sec (CPU)
- **Performance PT-BR:** 70-75% (melhor que all-MiniLM)
- **Hybrid retrieval:** ❌ Não suporta

**Requisitos:**
- CPU: 2+ cores suficiente
- RAM: 1-2GB
- Storage: 100MB

**Vantagens:**
- ✅ Ultra-rápido (15-30ms)
- ✅ Muito leve (90MB)
- ✅ Performance melhor que all-MiniLM
- ✅ Zero custo

**Desvantagens:**
- ❌ **128 tokens context** (inútil para docs reais)
- ❌ Performance 20-30% inferior modelos principais

**Quando usar:**
- **Two-stage retrieval** (stage 1 fast)
- Autocompletar skills (UI interativa)
- Triagem inicial ultra-rápida
- Prototipagem

**Quando NÃO usar:**
- Qualquer aplicação séria de produção
- Documentos longos

---

## 2. MODELOS API (SEM GPU NECESSÁRIA)

### 2.1 Voyage 3.5

**Especificações:**
- **Preço:** $0.06/1M tokens
- **Context:** 32,000 tokens
- **Dimensões:** 1024
- **Latência:** ~100-150ms (API)
- **Performance PT-BR:** 85-90% (estimado)

**Vantagens:**
- ✅ Melhor custo-benefício ($0.06 vs $0.12 voyage-2)
- ✅ Performance 85-90% (melhor que local)
- ✅ 32k context (docs muito longos)
- ✅ Zero setup (API)
- ✅ Matryoshka (reduz storage 50-75%)
- ✅ Latência baixa (100-150ms)

**Desvantagens:**
- ❌ Custo variável ($0.06/1M tokens)
- ❌ Vendor lock-in
- ❌ Dados na cloud (LGPD concern)
- ❌ Dependência de internet

**Custo estimado:**
- 1M páginas/mês (2k tokens/página): **$120/mês**
- 5M páginas/mês: **$600/mês**
- 10M páginas/mês: **$1,200/mês**

**Quando usar:**
- Volume <5M páginas/mês
- Performance >80% necessária
- Budget $100-500/mês OK
- Setup rápido prioritário

---

### 2.2 Voyage 3.5 Lite

**Especificações:**
- **Preço:** $0.02/1M tokens (3x mais barato!)
- **Context:** 32,000 tokens
- **Dimensões:** 1024
- **Latência:** ~100-150ms (API)
- **Performance PT-BR:** 80-85% (estimado, 5% inferior 3.5)

**Vantagens:**
- ✅ **Muito barato** ($0.02/1M tokens)
- ✅ Performance 80-85% (ainda melhor que local)
- ✅ 32k context
- ✅ Latência baixa

**Desvantagens:**
- ⚠️ Performance 5% inferior a 3.5
- ❌ Custo variável
- ❌ Vendor lock-in

**Custo estimado:**
- 1M páginas/mês: **$40/mês**
- 5M páginas/mês: **$200/mês**
- 10M páginas/mês: **$400/mês**

**Quando usar:**
- Alto volume (>5M páginas/mês)
- Budget limitado
- Performance 80%+ suficiente

---

### 2.3 OpenAI text-embedding-3-small

**Especificações:**
- **Preço:** $0.02/1M tokens
- **Context:** 8,000 tokens
- **Dimensões:** 1536
- **Latência:** ~150-200ms (API)
- **Performance PT-BR:** 75-80% (estimado)

**Vantagens:**
- ✅ Barato ($0.02/1M tokens)
- ✅ Performance 75-80%
- ✅ 8k context
- ✅ API estabelecida

**Desvantagens:**
- ⚠️ Performance inferior Voyage 3.5
- ⚠️ Context menor (8k vs 32k)
- ❌ Custo variável

**Custo estimado:**
- 1M páginas/mês: **$40/mês**
- 5M páginas/mês: **$200/mês**

**Quando usar:**
- Fallback se Voyage indisponível
- Integração existente OpenAI
- Budget muito limitado

---

### 2.4 Voyage Multilingual-2

**Especificações:**
- **Preço:** $0.12/1M tokens
- **Context:** 32,000 tokens
- **Dimensões:** 1024
- **Latência:** ~100-150ms (API)
- **Performance PT-BR:** 75-80% (jurídico), 80-85% (code-switching)

**Vantagens:**
- ✅ Melhor code-switching PT+EN
- ✅ 32k context
- ✅ Performance 80-85% code-switching

**Desvantagens:**
- ❌ Mais caro ($0.12 vs $0.06)
- ❌ Performance similar 3.5 em geral

**Custo estimado:**
- 1M páginas/mês: **$240/mês**
- 5M páginas/mês: **$1,200/mês**

**Quando usar:**
- Code-switching crítico (RH)
- Cross-lingual retrieval
- Budget permite

---

## 3. COMPARAÇÃO: LOCAL (CPU) vs API

### 3.1 Performance

| Modelo | Performance PT-BR | Latência | Throughput |
|--------|------------------|----------|-------------|
| **BGE-M3 (CPU)** | 70-75% | 200-500ms | 10-20 docs/sec |
| **Serafim-900M (CPU)** | 80-85% | 200-300ms | 15-25 docs/sec |
| **all-MiniLM-L6-v2 (CPU)** | 60-65% | 20-50ms | 50-100 docs/sec |
| **Voyage 3.5 (API)** | 85-90% | 100-150ms | Ilimitado |
| **Voyage 3.5 Lite (API)** | 80-85% | 100-150ms | Ilimitado |
| **OpenAI small (API)** | 75-80% | 150-200ms | Ilimitado |

**Vencedor Performance:** Voyage 3.5 (API) - 85-90%  
**Vencedor Local:** Serafim-900M - 80-85% (mas limitado 512 tokens)

---

### 3.2 Custo

| Modelo | Custo Fixo | Custo Marginal | Total 1M pgs/mês |
|--------|-----------|----------------|------------------|
| **BGE-M3 (CPU)** | $0 | $0 | **$0** |
| **Serafim-900M (CPU)** | $0 | $0 | **$0** |
| **all-MiniLM-L6-v2 (CPU)** | $0 | $0 | **$0** |
| **Voyage 3.5 (API)** | $0 | $0.06/1M tokens | **$120/mês** |
| **Voyage 3.5 Lite (API)** | $0 | $0.02/1M tokens | **$40/mês** |
| **OpenAI small (API)** | $0 | $0.02/1M tokens | **$40/mês** |

**Vencedor Custo:** Local (zero custo)  
**Vencedor API:** Voyage 3.5 Lite ou OpenAI small ($40/mês)

---

### 3.3 Latência

| Modelo | Latência p50 | Latência p95 | Uso |
|--------|-------------|--------------|-----|
| **BGE-M3 (CPU)** | 200-300ms | 400-500ms | Produção OK |
| **Serafim-900M (CPU)** | 200-250ms | 300-400ms | Produção OK |
| **all-MiniLM-L6-v2 (CPU)** | 20-30ms | 40-50ms | UI interativa |
| **Voyage 3.5 (API)** | 100-120ms | 150-200ms | Produção ideal |
| **Voyage 3.5 Lite (API)** | 100-120ms | 150-200ms | Produção ideal |
| **OpenAI small (API)** | 150-180ms | 200-250ms | Produção OK |

**Vencedor Latência:** all-MiniLM-L6-v2 (20-30ms) - mas performance baixa  
**Vencedor Balanceado:** Voyage 3.5 (100-150ms) - API rápida + boa performance

---

### 3.4 Facilidade de Uso

| Modelo | Setup | Manutenção | Escalabilidade |
|--------|-------|------------|----------------|
| **BGE-M3 (CPU)** | 🟡 MÉDIO | 🟡 MÉDIO | 🟡 Limitada (CPU) |
| **Serafim-900M (CPU)** | 🟡 MÉDIO | 🟡 MÉDIO | 🟡 Limitada (CPU) |
| **all-MiniLM-L6-v2 (CPU)** | 🟢 FÁCIL | 🟢 FÁCIL | 🟡 Limitada (CPU) |
| **Voyage 3.5 (API)** | 🟢 FÁCIL | 🟢 FÁCIL | 🟢 Ilimitada |
| **Voyage 3.5 Lite (API)** | 🟢 FÁCIL | 🟢 FÁCIL | 🟢 Ilimitada |
| **OpenAI small (API)** | 🟢 FÁCIL | 🟢 FÁCIL | 🟢 Ilimitada |

**Vencedor Facilidade:** APIs (zero setup, zero manutenção)

---

## 4. BREAK-EVEN ANALYSIS

### 4.1 BGE-M3 (CPU) vs Voyage 3.5 (API)

**Premissas:**
- BGE-M3: $0 custo, 200-500ms latência, 70-75% performance
- Voyage 3.5: $0.06/1M tokens, 100-150ms latência, 85-90% performance
- Documento médio: 2k tokens (5 páginas)

**Break-even:**
```
Custo Voyage = $0.06/1M tokens
Volume break-even = Infinito (local é sempre mais barato em custo direto)

MAS: Considerando custo de oportunidade (performance):
- Performance gap: 15-20%
- Se performance <70% inaceitável → API vale a pena
- Se performance 70%+ aceitável → Local OK
```

**Recomendação:**
- Volume <2M páginas/mês + Performance 70%+ OK → **BGE-M3 local**
- Volume >2M páginas/mês OU Performance >80% necessária → **Voyage 3.5 API**

---

### 4.2 Serafim-900M (CPU) vs Voyage 3.5 Lite (API)

**Premissas:**
- Serafim: $0 custo, 200-300ms latência, 80-85% performance, **512 tokens limit**
- Voyage 3.5 Lite: $0.02/1M tokens, 100-150ms latência, 80-85% performance, **32k tokens**

**Break-even:**
```
Custo Voyage Lite = $0.02/1M tokens = $40/mês (1M páginas)

Se docs curtos (<512 tokens):
- Serafim: Performance 80-85%, $0
- Voyage Lite: Performance 80-85%, $40/mês
- → Serafim vence (mesma performance, zero custo)

Se docs longos (>512 tokens):
- Serafim: Não funciona (limite 512 tokens)
- Voyage Lite: Performance 80-85%, $40/mês
- → Voyage Lite vence (única opção)
```

**Recomendação:**
- Docs curtos (<512 tokens) → **Serafim local**
- Docs longos (>512 tokens) → **Voyage 3.5 Lite API**

---

## 5. RECOMENDAÇÕES POR CASO DE USO (SEM GPU)

### 5.1 RAG Geral PT-BR

**Opção 1: Local (Budget Zero)**
```
BGE-M3 (CPU)
- Performance: 70-75%
- Custo: $0
- Latência: 200-500ms
- Context: 8k tokens
```

**Opção 2: API (Melhor Performance)**
```
Voyage 3.5
- Performance: 85-90%
- Custo: $120/mês (1M páginas)
- Latência: 100-150ms
- Context: 32k tokens
```

**Recomendação:**
- Budget zero → **BGE-M3 local**
- Budget $100-200/mês → **Voyage 3.5 API**

---

### 5.2 Jurídico BR

**Opção 1: Local**
```
BGE-M3 (CPU)
- Performance: 70-75%
- Custo: $0
- Context: 8k tokens (razoável para chunks)
```

**Opção 2: API**
```
Voyage Multilingual-2
- Performance: 75-80%
- Custo: $240/mês (1M páginas)
- Context: 32k tokens (contratos completos)
```

**Recomendação:**
- Budget zero → **BGE-M3 local**
- Budget $200-300/mês → **Voyage Multilingual-2 API**

---

### 5.3 Consultoria PPTX (Semântica Visual)

**Opção 1: Local**
```
BGE-M3 (CPU)
- Performance: 70-75%
- Custo: $0
- Context: 8k tokens (apresentações completas)
- Metadata rico preservado
```

**Opção 2: API**
```
Voyage 3.5
- Performance: 85-90%
- Custo: $120/mês (1M páginas)
- Context: 32k tokens
```

**Recomendação:**
- Budget zero → **BGE-M3 local** (já funciona bem com metadata)
- Budget $100-200/mês → **Voyage 3.5 API**

---

### 5.4 Financeiro PT-BR

**Opção 1: Local**
```
BGE-M3 (CPU)
- Performance: 65-70%
- Custo: $0
- Context: 8k tokens (DREs completos)
- Hybrid sparse (captura termos técnicos)
```

**Opção 2: API**
```
Voyage 3.5
- Performance: 70-75%
- Custo: $120/mês (1M páginas)
```

**Recomendação:**
- Budget zero → **BGE-M3 local** (única opção decente)
- Budget $100-200/mês → **Voyage 3.5 API** (melhoria marginal)

---

### 5.5 Docs Curtos (<512 tokens)

**Opção 1: Local (Ideal)**
```
Serafim-900M (CPU)
- Performance: 80-85% (SOTA português!)
- Custo: $0
- Latência: 200-300ms
- Context: 512 tokens (perfeito para docs curtos)
```

**Opção 2: API**
```
Voyage 3.5 Lite
- Performance: 80-85%
- Custo: $40/mês (1M páginas)
- Context: 32k tokens (overkill)
```

**Recomendação:**
- **Serafim-900M local** (mesma performance, zero custo)

---

## 6. MATRIZ DE DECISÃO RÁPIDA

### 6.1 Escolha Local vs API

```
[ ] Budget zero? → Local (BGE-M3 ou Serafim)
[ ] Budget $50-300/mês OK? → API (Voyage 3.5)

[ ] Performance >80% necessária? → API (Voyage 3.5)
[ ] Performance 70-80% aceitável? → Local (BGE-M3)

[ ] Docs curtos (<512 tokens)? → Serafim local (SOTA PT)
[ ] Docs longos (>512 tokens)? → BGE-M3 local ou Voyage API

[ ] Latência <100ms crítica? → API (Voyage 3.5)
[ ] Latência <500ms aceitável? → Local (BGE-M3)

[ ] Volume >5M páginas/mês? → API (escala melhor)
[ ] Volume <2M páginas/mês? → Local (custo zero)

[ ] LGPD crítico (dados não podem sair)? → Local
[ ] Dados podem ir cloud? → API (mais fácil)
```

---

## 7. RECOMENDAÇÕES FINAIS

### 7.1 Melhor Opção Local (CPU-only)

**Para maioria dos casos:**
```
BGE-M3 (CPU)
- Performance: 70-75%
- Custo: $0
- Context: 8k tokens
- Hybrid retrieval: ✅
```

**Para docs curtos:**
```
Serafim-900M (CPU)
- Performance: 80-85% (SOTA PT)
- Custo: $0
- Context: 512 tokens
```

---

### 7.2 Melhor Opção API (Sem GPU)

**Para maioria dos casos:**
```
Voyage 3.5
- Performance: 85-90%
- Custo: $120/mês (1M páginas)
- Context: 32k tokens
- Melhor custo-benefício
```

**Para alto volume:**
```
Voyage 3.5 Lite
- Performance: 80-85%
- Custo: $40/mês (1M páginas)
- Context: 32k tokens
- 3x mais barato que 3.5
```

---

### 7.3 Quando Usar Cada Um

| Situação | Recomendação | Justificativa |
|----------|-------------|---------------|
| **Budget zero** | BGE-M3 local | Zero custo, performance 70-75% |
| **Docs curtos** | Serafim local | SOTA PT, zero custo |
| **Performance >80%** | Voyage 3.5 API | Melhor performance disponível |
| **Alto volume** | Voyage 3.5 Lite API | Barato, escala ilimitada |
| **LGPD crítico** | BGE-M3 local | 100% local, zero cloud |
| **Setup rápido** | Voyage 3.5 API | Zero setup, funciona imediatamente |
| **Latência crítica** | Voyage 3.5 API | 100-150ms vs 200-500ms local |

---

## 8. CONCLUSÃO

### 8.1 Resumo Executivo

**Sem GPU, as melhores opções são:**

1. **Local (CPU-only):**
   - **BGE-M3**: Melhor versatilidade (70-75%, 8k context)
   - **Serafim-900M**: Melhor PT-BR docs curtos (80-85%, 512 tokens)

2. **API:**
   - **Voyage 3.5**: Melhor custo-benefício geral (85-90%, $0.06/1M)
   - **Voyage 3.5 Lite**: Melhor para alto volume (80-85%, $0.02/1M)

### 8.2 Recomendação Final

**Para começar (sem GPU):**
```
1. Teste BGE-M3 local (zero custo, performance 70-75%)
2. Se performance insuficiente → migre para Voyage 3.5 API
3. Se docs curtos → use Serafim-900M local
```

**Break-even típico:**
- Volume <2M páginas/mês → **Local** (custo zero)
- Volume >5M páginas/mês → **API** (escala melhor)
- Performance >80% necessária → **API** (Voyage 3.5)

---

**Documento criado em:** Janeiro 2025  
**Última atualização:** Janeiro 2025  
**Baseado em:** Guia Comparativo Embeddings PT-BR + Análise CPU-only


