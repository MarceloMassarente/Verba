# Resumo Executivo: Embeddings x Modos de Ingestão

## 🎯 Principais Descobertas

### **Modo Universal**
- ✅ Melhor com **Voyage 3.5** (RAG geral) ou **BGE-M3** (budget zero)
- ⚠️ **Voyage 3.5 faltando** (crítico)
- ⚠️ **Serafim faltando** (docs curtos)
- ⚠️ Default não otimizado PT-BR

### **Modo Semântica Visual**
- ✅ Funciona com **BGE-M3** (recebe .md pré-processado pela Visual API)
- ✅ **Visual API externa** já faz análise visual (não precisa ColQwen2!)
- ⚠️ **BGE-M3 sparse não usado** (perdendo 10-15%)
- ⚠️ **Metadata rico não injetado no embedding** (apenas armazenado)

---

## 📊 Matriz de Decisão Rápida

| Caso de Uso | Modo | Embedding | Performance | Status |
|-------------|------|-----------|-------------|--------|
| **RAG Geral PT-BR** | Universal | Voyage 3.5 | 85-90% | ⚠️ Faltando |
| **RAG Geral (docs curtos)** | Universal | Serafim-900M | 80-85% | ⚠️ Faltando |
| **Jurídico BR** | Universal | Voyage Multi-2 | 75-80% | ✅ OK |
| **Financeiro PT-BR** | Universal | BGE-M3 | 65-70% | ✅ OK |
| **Consultoria PPTX (texto)** | Semântica Visual | BGE-M3 | 70-75% | ✅ OK |
| **Consultoria PPTX (visual)** | Semântica Visual | BGE-M3 (hybrid) | 75-80% | ⚠️ Sparse faltando |

---

## 🚀 Ações Prioritárias

### **Fase 1: Universal (1 semana)** 🔴 ALTA

1. **Adicionar Voyage 3.5**
   - Impacto: +20-25% performance, -50% custo
   - Esforço: 🟢 BAIXO

2. **Adicionar Serafim models**
   - Impacto: SOTA português docs curtos
   - Esforço: 🟢 BAIXO

3. **Mudar default para BGE-M3**
   - Impacto: +10-15% performance default
   - Esforço: 🟢 BAIXO

### **Fase 2: Semântica Visual (1-2 semanas)** 🟡 MÉDIA

4. **BGE-M3 Hybrid Retrieval**
   - Impacto: +10-15% (sparse embeddings)
   - Esforço: 🟡 MÉDIO
   - **Nota:** Visual API externa já faz análise visual!

5. **Injetar Metadata no Embedding**
   - Impacto: +5-10% (metadata rico no embedding)
   - Esforço: 🟢 BAIXO

---

## 💰 Impacto Financeiro

**Modo Universal:**
- Voyage 3.5: **-$300/mês** (1M páginas)
- Performance: **+20-25%**

**Modo Semântica Visual:**
- ColQwen2: **+$400/mês** (GPU)
- Performance: **+15-20%** (slides visual)

---

## ⚠️ Gaps Críticos

| Modo | Gap | Impacto | Prioridade |
|------|-----|---------|------------|
| **Universal** | Voyage 3.5 faltando | -20-25% performance | 🔴 ALTA |
| **Universal** | Serafim faltando | -15-20% docs curtos | 🟡 MÉDIA |
| **Semântica Visual** | ColQwen2 faltando | -10-15% slides visual | 🟡 MÉDIA |
| **Semântica Visual** | BGE-M3 sparse não usado | -10-15% geral | 🟡 MÉDIA |

---

**Documento completo:** `docs/analyses/EMBEDDINGS_X_MODOS_INGESTAO.md`

