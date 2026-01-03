# Resumo: Embeddings Sem GPU - Local vs API

## 🎯 Resposta Rápida

### **Melhor Local (CPU-only):**
- **BGE-M3**: 70-75% performance, $0, 8k context, 200-500ms
- **Serafim-900M**: 80-85% performance, $0, 512 tokens, 200-300ms

### **Melhor API:**
- **Voyage 3.5**: 85-90% performance, $120/mês (1M páginas), 32k context, 100-150ms
- **Voyage 3.5 Lite**: 80-85% performance, $40/mês (1M páginas), 32k context, 100-150ms

---

## 📊 Comparação Rápida

| Modelo | Tipo | Performance | Custo | Latência | Context |
|--------|------|------------|-------|----------|---------|
| **BGE-M3** | Local CPU | 70-75% | $0 | 200-500ms | 8k |
| **Serafim-900M** | Local CPU | 80-85% | $0 | 200-300ms | 512 |
| **Voyage 3.5** | API | 85-90% | $120/mês | 100-150ms | 32k |
| **Voyage 3.5 Lite** | API | 80-85% | $40/mês | 100-150ms | 32k |
| **OpenAI small** | API | 75-80% | $40/mês | 150-200ms | 8k |

---

## 🚀 Recomendações por Situação

### **Budget Zero**
```
BGE-M3 (local)
- Performance: 70-75%
- Custo: $0
- Context: 8k tokens
```

### **Docs Curtos (<512 tokens)**
```
Serafim-900M (local)
- Performance: 80-85% (SOTA PT!)
- Custo: $0
- Context: 512 tokens
```

### **Melhor Performance**
```
Voyage 3.5 (API)
- Performance: 85-90%
- Custo: $120/mês (1M páginas)
- Context: 32k tokens
```

### **Alto Volume**
```
Voyage 3.5 Lite (API)
- Performance: 80-85%
- Custo: $40/mês (1M páginas)
- Context: 32k tokens
```

---

## 💰 Break-Even

**Local vs API:**
- Volume <2M páginas/mês → **Local** (custo zero)
- Volume >5M páginas/mês → **API** (escala melhor)
- Performance >80% necessária → **API** (Voyage 3.5)

**Custo típico:**
- 1M páginas/mês: Local $0 vs API $40-120/mês
- 5M páginas/mês: Local $0 vs API $200-600/mês

---

## ⚡ Latência

| Modelo | Latência | Uso |
|--------|----------|-----|
| **BGE-M3 (CPU)** | 200-500ms | Produção OK |
| **Serafim-900M (CPU)** | 200-300ms | Produção OK |
| **Voyage 3.5 (API)** | 100-150ms | Produção ideal |
| **all-MiniLM-L6-v2 (CPU)** | 20-50ms | UI interativa (mas performance baixa) |

---

## ✅ Checklist de Decisão

```
[ ] Budget zero? → BGE-M3 local
[ ] Docs curtos (<512 tokens)? → Serafim-900M local
[ ] Performance >80% necessária? → Voyage 3.5 API
[ ] Alto volume (>5M páginas/mês)? → Voyage 3.5 Lite API
[ ] Latência <100ms crítica? → Voyage 3.5 API
[ ] LGPD crítico (dados não podem sair)? → BGE-M3 local
[ ] Setup rápido prioritário? → Voyage 3.5 API
```

---

## 🎯 Recomendação Final

**Para começar (sem GPU):**
1. Teste **BGE-M3 local** (zero custo, 70-75%)
2. Se performance insuficiente → **Voyage 3.5 API** (85-90%)
3. Se docs curtos → **Serafim-900M local** (80-85%, SOTA PT)

**Break-even típico:**
- Volume <2M páginas/mês → **Local** (custo zero)
- Volume >5M páginas/mês → **API** (escala melhor)
- Performance >80% necessária → **API** (Voyage 3.5)

---

**Documento completo:** `docs/analyses/EMBEDDINGS_CPU_ONLY_LOCAL_VS_API.md`


