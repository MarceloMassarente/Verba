# Modos de Busca - Guia Completo

## 📋 Resumo Executivo

O **EntityAwareRetriever** suporta **3 modos principais de busca**, que são **mutuamente exclusivos**:

1. **Modo Padrão** (Entity Filter + Semantic Search)
2. **Modo Dois-Fases** (Two-Phase Search)
3. **Modo Análise** (Aggregation)

Além disso, há **otimizações opcionais** que podem ser combinadas com qualquer modo.

---

## 🎯 Modos de Busca Principais

### 1. Modo Padrão (Entity Filter + Semantic Search)

**Status:** Ativo quando nenhum outro modo está ativo  
**Quando usar:** Busca geral com filtros de entidades

**Características:**
- ✅ Usa Entity Filter para pré-filtrar por entidades
- ✅ Aplica busca semântica dentro dos resultados filtrados
- ✅ Mais rápido que Two-Phase Search
- ✅ Ideal para queries simples com entidades conhecidas

**Configuração:**
```json
{
  "Two-Phase Search Mode": "disabled",
  "Enable Aggregation": false,
  "Enable Entity Filter": true,
  "Enable Semantic Search": true
}
```

**Fluxo:**
```
Query → Extrai Entidades → Filtro WHERE → Busca Semântica → Resultados
```

---

### 2. Modo Dois-Fases (Two-Phase Search)

**Status:** Ativo quando `Two-Phase Search Mode` ≠ "disabled"  
**Quando usar:** Documentos de consultoria, queries complexas, melhor precisão

**Características:**
- ✅ Fase 1: Filtra por entidades (cria subespaço)
- ✅ Fase 2: Multi-vector search dentro do subespaço
- ✅ Melhor precisão para queries complexas
- ✅ Suporta Multi-Vector Search (named vectors)
- ⚠️ Desabilita Entity Filter automaticamente (redundante)

**Configuração:**
```json
{
  "Two-Phase Search Mode": "auto",  // ou "enabled"
  "Enable Multi-Vector Search": true,  // opcional, mas recomendado
  "Enable Relative Score Fusion": true  // recomendado
}
```

**Opções de Two-Phase Search Mode:**
- **`"auto"`** (padrão): Ativa automaticamente se detectar entidades na query
- **`"enabled"`**: Sempre ativo, independente de entidades
- **`"disabled"`**: Nunca ativo (usa Modo Padrão)

**Fluxo:**
```
Query → Fase 1: Filtro Entidades → Subespaço → Fase 2: Multi-Vector Search → Resultados
```

**Otimizações Recomendadas:**
- ✅ Enable Multi-Vector Search (se named vectors habilitados)
- ✅ Enable Relative Score Fusion
- ✅ Enable Query Expansion
- ✅ Enable Dynamic Alpha

---

### 3. Modo Análise (Aggregation)

**Status:** Ativo quando `Enable Aggregation` = true  
**Quando usar:** Análises estatísticas, contagens, agrupamentos

**Características:**
- ✅ Retorna análises ao invés de chunks
- ✅ Suporta GROUP BY, COUNT, SUM, etc.
- ⚠️ Desabilita todos os outros modos automaticamente
- ⚠️ Não retorna chunks para RAG

**Configuração:**
```json
{
  "Enable Aggregation": true
}
```

**Fluxo:**
```
Query → Agregação → Análise Estatística → Resultados (não chunks)
```

**⚠️ IMPORTANTE:**
- Modo Agregação é **alternativo** - não retorna chunks
- Todos os outros modos são desabilitados automaticamente
- Use apenas para análises, não para RAG

---

## 🔧 Otimizações Opcionais

Estas otimizações podem ser combinadas com qualquer modo principal:

### Query Expansion
- **Flag:** `Enable Query Expansion`
- **O que faz:** Gera 3-5 variações da query para melhorar recall
- **Quando usar:** Queries complexas, melhor cobertura
- **Risco:** Baixo (apenas melhora recall)

### Dynamic Alpha
- **Flag:** `Enable Dynamic Alpha`
- **O que faz:** Ajusta automaticamente o alpha baseado no tipo de query
- **Quando usar:** Queries variadas (entity-rich vs exploratory)
- **Risco:** Baixo (sobrescreve alpha manual)

### Multi-Vector Search
- **Flag:** `Enable Multi-Vector Search`
- **O que faz:** Busca em múltiplos named vectors (concept_vec, sector_vec, company_vec)
- **Quando usar:** Com Two-Phase Search, documentos de consultoria
- **Requisito:** ⚠️ **Enable Named Vectors** habilitado globalmente
- **Risco:** Médio (requer recriação de collections)

### Relative Score Fusion
- **Flag:** `Enable Relative Score Fusion`
- **O que faz:** Combina resultados de múltiplos vetores preservando magnitude
- **Quando usar:** Com Multi-Vector Search
- **Risco:** Baixo (melhor que RRF padrão)

### Query Rewriting
- **Flag:** `Enable Query Rewriting`
- **O que faz:** LLM reescreve query (fallback se QueryBuilder falhar)
- **Quando usar:** Queries complexas, melhor compreensão
- **Risco:** Médio (custo de LLM, cache recomendado)

---

## 📊 Matriz de Compatibilidade

| Modo Principal | Entity Filter | Two-Phase | Multi-Vector | Aggregation |
|----------------|---------------|-----------|--------------|-------------|
| **Modo Padrão** | ✅ Sim | ❌ Não | ⚠️ Opcional* | ❌ Não |
| **Two-Phase** | ❌ Não** | ✅ Sim | ✅ Recomendado | ❌ Não |
| **Aggregation** | ❌ Não** | ❌ Não** | ❌ Não** | ✅ Sim |

\* Multi-Vector pode ser usado no Modo Padrão, mas não é recomendado (Two-Phase é melhor)  
\*\* Desabilitado automaticamente

---

## 🎨 Como Deve Aparecer na Interface

### Bloco 1: Busca Fundamental (sempre visível)
```
┌─────────────────────────────────────────┐
│ Busca Fundamental                        │
│ Configurações básicas de busca          │
├─────────────────────────────────────────┤
│ Search Mode: [Hybrid Search ▼]          │
│ Limit Mode: [Autocut ▼]                 │
│ Limit/Sensitivity: [1]                  │
│ Alpha: [0.6]                            │
│ Reranker Top K: [5]                     │
└─────────────────────────────────────────┘
```

### Bloco 2: Filtros (independentes)
```
┌─────────────────────────────────────────┐
│ Filtros                                 │
│ Filtros independentes que podem ser     │
│ combinados                              │
├─────────────────────────────────────────┤
│ ☑ Enable Entity Filter                 │
│   Entity Filter Mode: [adaptive ▼]     │
│   💡 Desabilite 'Two-Phase Search Mode' │
│      no bloco 'Modo de Busca' para     │
│      ativar                             │
│                                         │
│ ☑ Enable Semantic Search               │
│ ☑ Enable Language Filter                │
│ ☑ Enable Temporal Filter                │
│   Date Field Name: [chunk_date]        │
│ ☑ Enable Framework Filter              │
└─────────────────────────────────────────┘
```

### Bloco 3: Modo de Busca (escolher UM)
```
┌─────────────────────────────────────────┐
│ Modo de Busca                           │
│ Escolha o modo de busca                │
│ (mutuamente exclusivos)                 │
├─────────────────────────────────────────┤
│                                         │
│ ⚫ Modo Padrão                          │
│   (Entity Filter + Semantic)            │
│   └─ Ativo quando:                       │
│      • Two-Phase = "disabled"            │
│      • Aggregation = false              │
│                                         │
│ ⚫ Modo Dois-Fases                      │
│   Two-Phase Search Mode: [auto ▼]       │
│   • auto: Ativa se detectar entidades   │
│   • enabled: Sempre ativo                │
│   • disabled: Nunca ativo               │
│                                         │
│   ☑ Enable Multi-Vector Search          │
│     ⚠️ Requer: Enable Named Vectors     │
│        (Settings → Advanced)             │
│                                         │
│   ☑ Enable Relative Score Fusion         │
│                                         │
│   ⚠️ Entity Filter será desabilitado    │
│      automaticamente (redundante)       │
│                                         │
│ ⚫ Modo Análise                          │
│   ☑ Enable Aggregation                  │
│                                         │
│   ⚠️ Todos os outros modos serão         │
│      desabilitados automaticamente      │
│                                         │
└─────────────────────────────────────────┘
```

### Bloco 4: Otimizações (opcional)
```
┌─────────────────────────────────────────┐
│ Otimizações                             │
│ Melhorias opcionais de performance e    │
│ qualidade                               │
├─────────────────────────────────────────┤
│ ☑ Enable Query Expansion                │
│ ☑ Enable Dynamic Alpha                   │
│   ⚠️ Se ativado, Alpha acima é apenas   │
│      base (será ajustado automaticamente)│
│                                         │
│ ☐ Enable Query Rewriting                │
│   Query Rewriter Cache TTL: [3600]      │
│                                         │
│ ☑ Enable Relative Score Fusion           │
│                                         │
│ Chunk Window: [1]                       │
└─────────────────────────────────────────┘
```

---

## 🔄 Lógica de Ativação Automática

### Modo Padrão
- **Ativo quando:**
  - `Two-Phase Search Mode` = "disabled" **E**
  - `Enable Aggregation` = false

### Modo Dois-Fases
- **Ativo quando:**
  - `Two-Phase Search Mode` = "auto" **E** entidades detectadas **OU**
  - `Two-Phase Search Mode` = "enabled"
- **Desabilita automaticamente:**
  - `Enable Entity Filter` (redundante)

### Modo Análise
- **Ativo quando:**
  - `Enable Aggregation` = true
- **Desabilita automaticamente:**
  - `Enable Entity Filter`
  - `Two-Phase Search Mode` → "disabled"
  - `Enable Multi-Vector Search`

---

## 💡 Recomendações por Caso de Uso

### Caso 1: Busca Geral Simples
```
✅ Modo Padrão
✅ Enable Entity Filter
✅ Enable Semantic Search
✅ Enable Query Expansion
```

### Caso 2: Documentos de Consultoria
```
✅ Modo Dois-Fases (Two-Phase = "auto")
✅ Enable Multi-Vector Search
✅ Enable Relative Score Fusion
✅ Enable Query Expansion
✅ Enable Dynamic Alpha
```

### Caso 3: Análises Estatísticas
```
✅ Modo Análise (Enable Aggregation)
⚠️ Não retorna chunks para RAG
```

### Caso 4: Máxima Precisão
```
✅ Modo Dois-Fases (Two-Phase = "enabled")
✅ Enable Multi-Vector Search
✅ Enable Relative Score Fusion
✅ Enable Query Expansion
✅ Enable Dynamic Alpha
✅ Enable Query Rewriting (fallback)
```

---

## ⚠️ Avisos Importantes

1. **Named Vectors:** Multi-Vector Search requer `Enable Named Vectors` habilitado globalmente (Settings → Advanced)

2. **Recriação de Collections:** Se habilitar Named Vectors, collections existentes precisam ser recriadas

3. **Modo Agregação:** Não retorna chunks - use apenas para análises

4. **Two-Phase vs Entity Filter:** São mutuamente exclusivos - Two-Phase já faz filtro de entidades

5. **Dynamic Alpha:** Se ativado, o Alpha manual é apenas base - será ajustado automaticamente

---

## 📚 Referências

- [Configuração Hierárquica](./CONFIGURACAO_HIERARQUICA.md)
- [Explicação Detalhada de Funcionalidades](./EXPLICACAO_DETALHADA_FUNCIONALIDADES.md)
- [Reorganização Hierárquica de Flags](./REORGANIZACAO_HIERARQUICA_FLAGS.md)

