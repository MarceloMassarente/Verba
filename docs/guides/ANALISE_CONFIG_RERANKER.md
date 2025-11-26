# Análise: Por que Reranker retorna apenas 2 chunks?

## Problema Observado
```
✔ Encontrados 10 chunks
✔ Reranked 2 chunks usando Reranker
```

Esperado: 5 chunks (ou mais)
Observado: 2 chunks

## Fluxo de Configuração (como funciona)

### 1. Definição de `InputConfig` (Pydantic model)
```python
# goldenverba/components/types.py
class InputConfig(BaseModel):
    type: Literal["number", "text", "dropdown", "password", "bool", "multi", "textarea"]
    value: Union[int, str, bool]
    description: str
    values: list[str]
```

### 2. Declaração no `EntityAwareRetriever.__init__()`
```python
self.config["Reranker Top K"] = InputConfig(
    type="number",
    value=5,  # <--- Valor padrão
    description="Number of top chunks to return after reranking (default: 5, use 0 to return all)",
    values=[],
)
```

### 3. Carregamento da Configuração (`verba_manager.py`)

```python
async def load_rag_config(self, client):
    loaded_config = await self.weaviate_manager.get_config(client, self.rag_config_uuid)
    new_config = self.create_config()
    
    if loaded_config is not None:
        if self.verify_config(loaded_config, new_config):
            # ⚠️ USA CONFIGURAÇÃO SALVA (pode ter valores antigos)
            return loaded_config
        else:
            # Configuração incompatível, usa nova
            await self.set_rag_config(client, new_config)
            return new_config
    else:
        return new_config
```

### 4. `verify_config()` - Validação de compatibilidade

```python
def verify_config(self, a: dict, b: dict) -> bool:
    # Compara chaves (config keys)
    if set(a_config.keys()) != set(b_config.keys()):
        msg.warn("Config keys mismatch, will use new configuration")
        return False  # <--- Força uso de configuração NOVA
    
    # Se todas as chaves coincidem, retorna True
    return True
```

**IMPORTANTE**: Se a configuração salva tem as mesmas chaves que a configuração atual, o sistema usa a **configuração salva** (que pode ter valores diferentes do default).

## Cenários

### Cenário 1: Configuração Salva NÃO tem "Reranker Top K"
- `verify_config()` retorna `False` (chave faltando)
- Sistema usa **configuração NOVA** (com `value=5`)
- ✅ Funciona corretamente

### Cenário 2: Configuração Salva TEM "Reranker Top K" = 2
- Usuário configurou antes como 2
- `verify_config()` retorna `True` (mesmas chaves)
- Sistema usa **configuração SALVA** (com `value=2`)
- ❌ Limita demais (apenas 2 chunks)

### Cenário 3: Campo "Reranker Top K" não aparece na interface
- Frontend não renderiza o campo (problema de UI)
- Usuário não consegue alterar o valor
- Config permanece com valor antigo
- ❌ Sem controle do usuário

## Hipóteses sobre o Problema

### Hipótese 1: `Limit/Sensitivity` sendo confundido com `Reranker Top K`
**INCORRETA**: O código lê explicitamente `config.get("Reranker Top K", {})`, não há confusão.

### Hipótese 2: Configuração salva tem `Reranker Top K = 2`
**PROVÁVEL**: 
- Configuração foi salva anteriormente com `Reranker Top K = 2`
- `verify_config()` aprova (mesmas chaves)
- Sistema usa configuração salva com `value=2`

### Hipótese 3: Campo não aparece na interface
**PROVÁVEL**:
- Campo "Reranker Top K" NÃO aparece na interface (screenshot mostra apenas Limit/Sensitivity)
- Usuário não consegue alterar o valor
- Valor permanece como 2 (configuração antiga)

## Diferença: Entity-Aware vs Advanced (Nativo)

### Advanced (WindowRetriever)
```python
# NÃO tem "Reranker Top K"
self.config["Limit/Sensitivity"] = InputConfig(
    type="number",
    value=1,  # Usado APENAS para busca inicial (Autocut/Fixed)
    ...
)
```

- `Limit/Sensitivity=2` com `Autocut` → busca inicial recupera ~10 chunks
- Sem reranker → retorna todos os 10 chunks
- ✅ Funciona como esperado

### EntityAware
```python
# TEM "Reranker Top K" adicional
self.config["Limit/Sensitivity"] = InputConfig(value=1, ...)  # Busca inicial
self.config["Reranker Top K"] = InputConfig(value=5, ...)      # Pós-rerank
```

- `Limit/Sensitivity=2` com `Autocut` → busca inicial recupera 10 chunks
- `Reranker Top K=2` → **reranker retorna apenas 2 chunks** (mesmo tendo 10 disponíveis)
- ❌ Limita demais os resultados

## Chunk Window

### Código (entity_aware_retriever.py linha 1041+)
```python
async def _process_chunks(self, client, chunks, weaviate_manager, embedder, config):
    chunk_window_config = config.get("Chunk Window", {})
    if hasattr(chunk_window_config, 'value'):
        chunk_window = int(chunk_window_config.value)
    else:
        chunk_window = 1  # Default
    
    msg.info(f"  📦 Chunk Window: {chunk_window} (vai combinar chunks adjacentes)")
    
    if chunk_window > 0 and chunks:
        # Combina chunk_window chunks adjacentes
        windowed_chunks = []
        for i, chunk in enumerate(chunks):
            context_chunks = chunks[max(0, i - chunk_window):min(len(chunks), i + chunk_window + 1)]
            combined_content = " ".join([...])
            chunk.properties["content"] = combined_content
            windowed_chunks.append(chunk)
        chunks = windowed_chunks
```

**Chunk Window é aplicado**: 
- ANTES do reranking (linha 748: `_process_chunks`)
- Combina chunks adjacentes para contexto maior
- `Chunk Window=3` → cada chunk inclui conteúdo de 3 chunks vizinhos (anterior + atual + próximo)

## Solução Aplicada

### 1. Fallback seguro
```python
# Verificar se não está confundindo com Limit/Sensitivity
if reranker_top_k == limit and limit != 5:
    msg.warn(f"  ⚠️ ATENÇÃO: reranker_top_k={reranker_top_k} é igual a limit={limit}!")
    if limit < 5:
        msg.warn(f"  ⚠️ Usando reranker_top_k=5 como fallback seguro")
        reranker_top_k = 5
```

### 2. Logs de debug
```python
msg.info(f"  DEBUG: reranker_top_k_config type={type(reranker_top_k_config)}")
msg.info(f"  DEBUG: reranker_top_k lido da config: {reranker_top_k}")
msg.good(f"  ⚙️ CONFIG RETRIEVER: limit={limit} (busca inicial), reranker_top_k={reranker_top_k} (pós-rerank)")
```

### 3. Log do Chunk Window
```python
msg.info(f"  📦 Chunk Window: {chunk_window} (vai combinar chunks adjacentes)")
```

## Atualização: Reranker Multi-Provider (2025-01-XX)

O reranker foi refatorado para suportar múltiplos providers:

- **Metadata Reranker**: Sempre disponível, baseado em metadata e keywords
- **Haystack Reranker**: Local, usando CrossEncoderRanker (requer `haystack-ai`)
- **Cohere Reranker**: API, usando Cohere Rerank API (requer `COHERE_API_KEY`)
- **Jina Reranker**: API, usando Jina Rerank API (requer `JINA_API_KEY`)
- **VoyageAI Reranker**: API, usando VoyageAI Rerank API (requer `VOYAGE_API_KEY`)

**Modos de combinação:**
- **Cascade**: Aplica rerankers sequencialmente
- **Parallel**: Aplica múltiplos rerankers em paralelo e combina com RRF
- **Hybrid**: Combina paralelo e cascade

**Configuração:**
- `Reranker Provider`: Seleciona provider ou "Combined" para usar múltiplos
- `Reranker Mode`: Cascade, Parallel ou Hybrid (quando usando "Combined")
- `Top K`: Número de chunks a retornar após reranking (substitui "Reranker Top K" em alguns contextos)

Para mais detalhes, consulte: `verba_extensions/plugins/RERANKER_README.md`

## Recomendações

1. **Resetar configuração do Retriever** (botão "Reset" na interface)
   - Isso força uso da configuração padrão (`Reranker Top K = 5`)

2. **Adicionar campo "Reranker Top K" à interface**
   - Permitir configuração explícita pelo usuário
   - Evitar confusão com `Limit/Sensitivity`

3. **Separar conceitos claramente**:
   - `Limit/Sensitivity` (Autocut/Fixed): busca inicial no Weaviate
   - `Reranker Top K`: quantos chunks retornar APÓS reranking

4. **Documentar diferença entre retrievers**:
   - Advanced: sem reranker
   - EntityAware: com reranker (precisa de `Reranker Top K` configurado corretamente)

