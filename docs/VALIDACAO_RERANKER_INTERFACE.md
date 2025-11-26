# Validação: Opções de Reranker Expostas na Interface

## 1. Configurações do Backend (RerankerPlugin)

### Configurações Principais (Sempre Disponíveis)
- ✅ `Reranker Provider` (dropdown)
- ✅ `Reranker Mode` (dropdown: Cascade, Parallel, Hybrid)
- ✅ `Top K` (number)
- ✅ `Enable Metadata Reranker` (bool)
- ✅ `Enable Haystack Reranker` (bool)
- ✅ `Enable Cohere Reranker` (bool)
- ✅ `Enable Jina Reranker` (bool)
- ✅ `Enable VoyageAI Reranker` (bool)
- ✅ `Enable ContextualAI Reranker` (bool)

### Configurações Condicionais (Baseadas em Disponibilidade)
- ⚠️ `Haystack Model` (dropdown) - apenas se Haystack disponível
- ⚠️ `Cohere Model` (dropdown) - apenas se Cohere disponível
- ⚠️ `Cohere API Key` (password) - apenas se Cohere disponível E sem env var
- ⚠️ `Jina API Key` (password) - apenas se Jina disponível E sem env var
- ⚠️ `VoyageAI API Key` (password) - apenas se VoyageAI disponível E sem env var
- ⚠️ `ContextualAI Model` (dropdown) - apenas se ContextualAI disponível
- ⚠️ `ContextualAI Instruction` (text) - apenas se ContextualAI disponível
- ⚠️ `ContextualAI API Key` (password) - apenas se ContextualAI disponível E sem env var

### Configurações Adicionais (Presets)
- ✅ `Reranker Preset` (dropdown) - em EntityAwareRetriever.config

---

## 2. Configurações Expostas no Frontend

### Bloco "Reranker" em RetrieverConfigBlocks.tsx

#### ✅ PRESENTE (Todas as opções listadas):
```tsx
configs: [
  "Reranker Provider",         ✅ principal
  "Reranker Mode",             ✅ principal
  "Enable Metadata Reranker",  ✅ principal
  "Enable Haystack Reranker",  ✅ principal
  "Enable Cohere Reranker",    ✅ principal
  "Enable Jina Reranker",      ✅ principal
  "Enable VoyageAI Reranker",  ✅ principal
  "Enable ContextualAI Reranker", ✅ principal
  "Haystack Model",            ✅ condicional
  "Cohere Model",              ✅ condicional
  "ContextualAI Model",        ✅ condicional
  "ContextualAI Instruction",  ✅ condicional
]
```

#### ❌ FALTAM (Não estão no array `configs`):
- `Top K` - **CRÍTICO**: Deve estar para que o usuário controle número de chunks retornados
- `Cohere API Key` - **Importante**: Quando Cohere disponível sem env var
- `Jina API Key` - **Importante**: Quando Jina disponível sem env var
- `VoyageAI API Key` - **Importante**: Quando VoyageAI disponível sem env var
- `ContextualAI API Key` - **Importante**: Quando ContextualAI disponível sem env var

---

## 3. Mecanismo de Atualização de Configurações

### Fluxo Atual (Funcionando ✅):

```
Usuario muda config no frontend
    ↓
RetrieverConfigBlocks.tsx: renderConfigField()
    ↓
updateConfig("Retriever", configKey, newValue)
    ↓
ChatConfig.tsx: updateConfig()
    ↓
setRAGConfig() - atualiza estado local
    ↓
RAGConfig.Retriever.components[selected].config[configKey].value = newValue
    ↓
Estado mantido em memória
```

### Salvamento de Config (Funciona quando "Save Config" clicado):

```
Usuario clica "Save Config"
    ↓
ChatInterface.tsx: onSaveConfig()
    ↓
updateRAGConfig(RAGConfig, credentials)
    ↓
API: POST /api/set_rag_config
    ↓
Backend salva em Weaviate
```

---

## 4. Validação de Registro de Configurações

### ✅ VALIDADO:
1. **Valores são atualizados em tempo real** - `updateConfig` modifica o estado local imediatamente
2. **Valores persistem durante a sessão** - Mantidos no estado `RAGConfig`
3. **Valores são enviados para o backend** - Via `updateRAGConfig()` quando "Save Config" clicado
4. **Configurações são renderizadas** - `renderConfigField()` renderiza corretamente inputs/selects/checkboxes

### ⚠️ POSSÍVEIS PROBLEMAS:
1. **Configurações condicionais podem não aparecer** - Se a disponibilidade da API não for detectada corretamente
2. **API Keys não são salvas se com env var** - Campos não aparecem se API key está em variável de ambiente (esperado, por segurança)
3. **Validações de dependências faltam** - Ex: Reranker Mode "Parallel" requer múltiplos rerankers habilitados

---

## 5. Checklist de Correções Necessárias

### CRÍTICO:
- [ ] **Adicionar "Top K" ao array `configs`** no bloco "Reranker"
  - Localização: `frontend/app/components/Chat/RetrieverConfigBlocks.tsx:86-99`
  - Ação: Adicionar `"Top K"` à lista

### Importante:
- [ ] **Adicionar campos de API Key condicionais**
  - `"Cohere API Key"`
  - `"Jina API Key"`
  - `"VoyageAI API Key"`
  - `"ContextualAI API Key"`
  - **Problema**: Estes campos são criados condicionalmente no backend, mas o frontend lista estaticamente
  - **Solução**: Filtrar campos vazios ou não renderizar campos não presentes no config

### Melhorias:
- [ ] **Validação de dependências** - Avisar se Reranker Mode requer múltiplos providers
- [ ] **Indicadores de disponibilidade** - Mostrar quais providers estão disponíveis/não disponíveis
- [ ] **Agrupamento por provider** - Organizar opções por provider (Metadata, Haystack, etc)

---

## 6. Resumo do Mecanismo de Salvamento

### Persistência:
1. **Em Memória**: ✅ Funcionando
2. **Backend Storage**: ✅ Funcionando (quando Save Config clicado)
3. **Entre Sessões**: ✅ Funcionando (salvo no Weaviate)

### Validações:
1. **No Cliente**: ⚠️ Parcialmente (valida Two-Phase/Aggregation, não valida Reranker)
2. **No Backend**: ✅ Deve validar em `process_chunks()` do EntityAwareRetriever

### Fluxo de Query:
```
1. Usuario muda config → estado atualizado
2. Usuario clica "Save Config" → backend atualizado
3. Usuario faz query → EntityAwareRetriever lê config
4. Config é aplicado em process_chunks()
```

---

## 7. Teste Recomendado

Para validar tudo funciona:

1. **Navegue para Settings → Config → Retriever → EntityAware**
2. **Abra o bloco "Reranker"**
3. **Mude "Reranker Mode" para "Parallel"**
4. **Ative múltiplos providers** (ex: Haystack + Cohere)
5. **Clique "Save Config"** (parte superior)
6. **Recarregue a página** (F5)
7. **Verifique se config foi preservada**
8. **Faça uma query** e monitore logs para ver se config é aplicada

---

## Conclusão

✅ **Mecanismo de salvamento funciona**
⚠️ **Faltam alguns campos na interface (Top K, API Keys)**
✅ **Valores são registrados e persistidos corretamente**
⚠️ **Validações de dependências precisam melhorar**

