# Atualização: Presets de Busca e Correções UI (2025-12-31)

**Data:** 2025-12-31  
**Versão:** 2.2  
**Status:** ✅ Implementado

---

## Resumo das Mudanças

### 1. Correção: Aplicar Preset Não Causa Mais "Restart"

**Problema:**
- Ao aplicar um preset de busca, a página fazia `window.location.reload()`, causando uma experiência ruim (parecia que o Verba reiniciava)

**Solução:**
- Implementado prop drilling de `refreshRAGConfig` através da hierarquia de componentes:
  - `ChatInterface.tsx` → `ChatConfig.tsx` → `ComponentView.tsx` → `RetrieverConfigBlocks.tsx`
- `handlePresetChange` agora chama `refreshRAGConfig()` para atualizar o estado sem recarregar a página
- Fallback para `window.location.reload()` se `refreshRAGConfig` não estiver disponível

**Arquivos Modificados:**
- `frontend/app/components/Chat/ChatInterface.tsx` - Passa `refreshRAGConfig` para `ChatConfig`
- `frontend/app/components/Chat/ChatConfig.tsx` - Aceita e passa `refreshRAGConfig` para `ComponentView`
- `frontend/app/components/Ingestion/ComponentView.tsx` - Aceita e passa `refreshRAGConfig` para `RetrieverConfigBlocks`
- `frontend/app/components/Chat/RetrieverConfigBlocks.tsx` - Usa `refreshRAGConfig` em vez de `window.location.reload()`

---

### 2. Presets de Busca Disponíveis

O sistema agora expõe 7 presets otimizados:

| Preset | Display Name | Provider | Latência | Qualidade | Requisitos |
|--------|--------------|----------|----------|-----------|------------|
| `consulting_frameworks` | 📊 Consultoria & Frameworks | Combined | ~800ms | Muito Alta | Nenhum (interno) |
| `company_research` | 🏢 Pesquisa de Empresas | (per config) | ~600ms | Alta | Nenhum |
| `sector_analysis` | 📈 Análise Setorial | (per config) | ~900ms | Muito Alta | Nenhum |
| `speed` | ⚡ Velocidade | Metadata Only | ~150ms | Moderada | Nenhum |
| `max_quality` | 🎯 Qualidade Máxima | Combined | ~1.5s | Muito Alta | haystack-ai, CONTEXTUAL_API_KEY |
| `balanced` | ⚖️ Balanceado | ContextualAI | ~500ms | Alta | CONTEXTUAL_API_KEY |
| `offline` | 🔌 Offline | Combined | ~500ms | Alta | haystack-ai |

**Localização:** `verba_extensions/plugins/reranker.py` - classe `RerankerPresets`

---

### 3. Arquitetura dos Presets

Cada preset define configurações para:

1. **Arquitetura de Busca:**
   - `Two-Phase Search Mode` - auto/enabled/disabled
   - `Enable Multi-Vector Search` - True/False
   - `Enable Aggregation` - True/False

2. **Parâmetros de Busca:**
   - `Alpha` - peso semântico vs keyword (0.0-1.0)
   - `Limit/Sensitivity` - sensibilidade da busca
   - `Reranker Top K` - número de chunks no reranking

3. **Otimizações:**
   - `Enable Query Expansion` - expande query
   - `Enable Dynamic Alpha` - ajusta alpha dinamicamente
   - `Enable Intelligent Cache` - cache de embeddings
   - `Chunk Window` - contexto de chunks adjacentes

4. **Reranking:**
   - `Reranker Provider` - Metadata Only, Haystack, Cohere, ContextualAI, Combined
   - `Reranker Mode` - Cascade, Parallel, Hybrid
   - `Enable Metadata Reranker` - sempre disponível

---

### 4. Fluxo de Aplicação de Preset

```
Frontend                          Backend
   │                                 │
   │  1. Usuário seleciona preset   │
   │  2. Clica "Aplicar"            │
   │                                 │
   ├─────────────────────────────────>
   │  POST /api/apply_reranker_preset
   │  { preset_name, query, credentials }
   │                                 │
   │                                 │  3. Carrega RAG config
   │                                 │  4. Obtém plugin Reranker
   │                                 │  5. **AUTO-SWITCH**: Muda retriever para Entity-Aware
   │                                 │  6. Aplica preset.config ao plugin
   │                                 │  7. Atualiza Entity-Aware retriever
   │                                 │  8. Salva config no Weaviate
   │                                 │
   <─────────────────────────────────┤
   │  { status: 200, preset_applied, config }
   │                                 │
   │  8. refreshRAGConfig()         │
   │     (atualiza UI sem reload)   │
   │                                 │
```

---

### 5. Problema Conhecido: Display Names

**Status:** ⚠️ Pendente

A UI mostra nomes gerados (ex: "Consulting Frameworks") em vez dos nomes bonitos com emojis definidos no preset (ex: "📊 Consultoria & Frameworks").

**Causa:**
`RerankerPlugin.get_presets_metadata()` gera o `display_name` em vez de usar o definido no preset:
```python
"display_name": preset_name.replace("_", " ").title(),  # BUG
```

**Correção Sugerida:**
```python
"display_name": preset_config.get("display_name", preset_name.replace("_", " ").title()),
```

---

## Referências

- **Commit:** be1894f - "fix: improve preset apply UX - use refreshRAGConfig instead of reload"
- **Arquivos de Presets:** `verba_extensions/plugins/reranker.py`
- **Componente Frontend:** `frontend/app/components/Chat/RetrieverConfigBlocks.tsx`
- **Endpoint Backend:** `POST /api/apply_reranker_preset`

---

## Próximos Passos

- [ ] Corrigir bug do `display_name` nos presets
- [ ] Mostrar presets apenas para Entity-Aware retriever (ou validar compatibilidade)
- [ ] Adicionar feedback visual quando preset é aplicado (toast/notification)
- [ ] Permitir criar presets customizados pelo usuário
