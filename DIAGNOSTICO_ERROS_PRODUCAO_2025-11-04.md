# 🔴 Diagnóstico de Erros em Produção - 2025-11-04

**Data:** 2025-11-04  
**Versão:** Verba Customizado v2.1.3+  
**Ambiente:** Railway + Weaviate  
**Status:** 3 problemas críticos identificados

---

## 📋 Resumo Executivo

Foram identificados **3 erros críticos** que estão impedindo o import de documentos:

| # | Problema | Severidade | Status | Solução |
|---|----------|-----------|--------|---------|
| 1 | Plugin Reranker sem `process_chunk/process_batch` | 🔴 CRÍTICA | ✅ FIXADO | Adicionar métodos necessários |
| 2 | WebSocket: "Cannot call send once close message sent" | 🔴 CRÍTICA | ⚠️ PARCIAL | Capturar exception e tratar antes de enviar |
| 3 | Collection `VERBA_Embedding_all-MiniLM-L6-v2` não existe | 🟠 IMPORTANTE | ⚠️ INVESTIGAR | Verificar inicialização da coleção |

---

## 🔍 Problema #1: Plugin Reranker sem Métodos Necessários

### ❌ Sintoma
```
Plugin Reranker has no process_chunk or process_batch method
```

### 🎯 Root Cause
O `RerankerPlugin` em `verba_extensions/plugins/reranker.py` implementa `process_chunks()` mas o `PluginManager` procura por `process_chunk()` ou `process_batch()`.

### 📊 Análise do Código

**Arquivo:** `verba_extensions/plugins/plugin_manager.py` (linha 104-121)
```python
for plugin in self.plugins:
    try:
        if hasattr(plugin, "process_batch"):
            # Processa em batch se disponível
            processed_chunks = await plugin.process_batch(
                processed_chunks,
                config=config
            )
        elif hasattr(plugin, "process_chunk"):
            # Processa individualmente se batch não disponível
            processed = []
            for chunk in processed_chunks:
                processed_chunk = await plugin.process_chunk(
                    chunk,
                    config=config
                )
                processed.append(processed_chunk)
            processed_chunks = processed
        else:
            logger.warning(f"Plugin {plugin.name} has no process_chunk or process_batch method")
```

O plugin **RerankerPlugin** não possui estes métodos.

### ✅ Solução Aplicada

Adicionei os métodos `process_chunk()` e `process_batch()` ao `RerankerPlugin`:

```python
async def process_chunk(self, chunk, config=None):
    """Processa um único chunk - para reranking, apenas retorna o chunk"""
    return chunk

async def process_batch(self, chunks, config=None):
    """Processa múltiplos chunks em batch com reranking"""
    query = ""
    if config and isinstance(config, dict):
        query = config.get("query", "")
    
    if not query:
        return chunks  # Sem query, não faz reranking
    
    return await self.process_chunks(chunks, query, config)
```

### 📌 Observações
- Reranking é uma operação em batch (requer comparação entre múltiplos chunks)
- `process_chunk()` apenas retorna o chunk sem modificação
- `process_batch()` chama `process_chunks()` que é a lógica real de reranking
- Agora o plugin é totalmente compatível com o sistema de plugins

---

## 🔍 Problema #2: WebSocket Connection Closed Before Response

### ❌ Sintoma (Logs)
```
2025-11-04T11:31:26.781399292Z [inf]  [38;5;3m⚠ WebSocket connection closed by client.[0m

2025-11-04T11:31:26.781399292Z [inf]  failed: Cannot call "send" once a close message has been sent. | 0[0m

2025-11-04T11:31:26.781405887Z [inf]  [38;5;1m✘ Import WebSocket Error: Cannot call "send" once a close message has been sent.[0m

2025-11-04T11:31:26.781412486Z [inf]  ✘ No documents imported 0 of 1 succesful tasks
```

### 🎯 Root Cause

O arquivo foi **completamente processado e pronto para enviar status** quando o **cliente fechou a conexão WebSocket**, e depois o servidor tentou enviar a resposta.

**Timeline:**
1. ✅ Documento carregado: 1.35s
2. ✅ Chunking: 54.33s
3. ✅ Embeddings: 93.17s
4. ✅ Vetorização completada
5. ❌ **Cliente fecha conexão** (`WebSocketDisconnect`)
6. ❌ **Servidor tenta enviar resultado** → "Cannot call send once close message has been sent"

### 📊 Análise do Código

**Arquivo:** `goldenverba/server/api.py` (linha 318-360)
```python
@app.websocket("/ws/import_files")
async def websocket_import_files(websocket: WebSocket):

    await websocket.accept()
    logger = LoggerManager(websocket)
    batcher = BatchManager()

    while True:
        try:
            data = await websocket.receive_text()
            batch_data = DataBatchPayload.model_validate_json(data)
            fileConfig = batcher.add_batch(batch_data)
            if fileConfig is not None:
                # ... import process ...
                await asyncio.create_task(
                    manager.import_document(client, fileConfig, logger)
                )
                # Aqui pode ocorrer WebSocketDisconnect
```

**Arquivo:** `goldenverba/server/helpers.py` (linha 16-28)
```python
async def send_report(
    self, file_Id: str, status: FileStatus, message: str, took: float
):
    msg.info(f"{status} | {file_Id} | {message} | {took}")
    if self.socket is not None:
        payload: StatusReport = {
            "fileID": file_Id,
            "status": status,
            "message": message,
            "took": took,
        }
        # ❌ Tenta enviar mesmo se socket foi fechado
        await self.socket.send_json(payload)
```

### ✅ Soluções Recomendadas

#### **Solução 1: Capturar exception em send_report** (Recomendado - Mínima)
```python
async def send_report(self, file_Id: str, status: FileStatus, message: str, took: float):
    msg.info(f"{status} | {file_Id} | {message} | {took}")
    if self.socket is not None:
        try:
            payload: StatusReport = {
                "fileID": file_Id,
                "status": status,
                "message": message,
                "took": took,
            }
            await self.socket.send_json(payload)
        except RuntimeError as e:
            # Socket foi fechado pelo cliente - log apenas
            if "close message has been sent" in str(e):
                msg.info(f"Socket already closed, skipping report: {message}")
            else:
                raise
        except Exception as e:
            msg.warn(f"Failed to send report: {str(e)}")
```

#### **Solução 2: Verificar estado da conexão antes de enviar** (Mais Robusta)
```python
async def send_report(self, file_Id: str, status: FileStatus, message: str, took: float):
    msg.info(f"{status} | {file_Id} | {message} | {took}")
    if self.socket is not None and self.socket.application_state == WebSocketState.CONNECTED:
        try:
            payload: StatusReport = {
                "fileID": file_Id,
                "status": status,
                "message": message,
                "took": took,
            }
            await self.socket.send_json(payload)
        except Exception as e:
            msg.warn(f"Failed to send report: {str(e)}")
```

#### **Solução 3: Timeout para client inativo** (Preventiva)
```python
@app.websocket("/ws/import_files")
async def websocket_import_files(websocket: WebSocket):
    await websocket.accept()
    logger = LoggerManager(websocket)
    batcher = BatchManager()
    
    # Timeout: 5 minutos de inatividade
    max_timeout = 300

    while True:
        try:
            data = await asyncio.wait_for(
                websocket.receive_text(), 
                timeout=max_timeout
            )
            # ... rest of the logic ...
        except asyncio.TimeoutError:
            msg.warn("WebSocket timeout - client inactive for 5 minutes")
            await websocket.close(code=1000, reason="Client timeout")
            break
        except WebSocketDisconnect:
            msg.warn("WebSocket disconnected by client")
            break
```

### 📌 Por Que Está Acontecendo?

1. **Processamento Longo:** Arquivo leva ~150 segundos para processar
2. **Client Timeout:** Cliente (navegador/frontend) espera timeout padrão (~30s) e fecha conexão
3. **Servidor Continua:** Servidor não sabe que cliente desconectou e continua processando
4. **Erro ao Enviar:** Quando tenta enviar resultado, socket já foi fechado

### 🔧 Implementação Recomendada

```python
# Em goldenverba/server/helpers.py

class LoggerManager:
    def __init__(self, socket: WebSocket = None):
        self.socket = socket

    async def send_report(
        self, file_Id: str, status: FileStatus, message: str, took: float
    ):
        msg.info(f"{status} | {file_Id} | {message} | {took}")
        if self.socket is not None:
            try:
                payload: StatusReport = {
                    "fileID": file_Id,
                    "status": status,
                    "message": message,
                    "took": took,
                }
                # Tenta enviar, mas captura se socket foi fechado
                await self.socket.send_json(payload)
            except RuntimeError as e:
                # WebSocket foi fechado - é normal em imports longos
                if "close message" in str(e):
                    msg.info(f"Client disconnected before receiving: {message}")
                else:
                    raise
            except Exception as e:
                # Outros erros - log apenas
                msg.warn(f"Failed to send status to client: {str(e)}")
```

---

## 🔍 Problema #3: Collection VERBA_Embedding_all-MiniLM-L6-v2 Não Existe

### ❌ Sintoma (Logs)
```
[38;5;3m⚠ Collection VERBA_Embedding_all-MiniLM-L6-v2 does not exist, returning 0[0m
```

### 🎯 Root Cause

A coleção de embeddings **não está sendo criada automaticamente** no Weaviate.

Padrão esperado: `VERBA_Embedding_<embedder_name>`  
Exemplo: `VERBA_Embedding_all-MiniLM-L6-v2` (SentenceTransformers)

### 📊 Análise do Código

**Arquivo:** `goldenverba/components/managers.py` (linha 654-665)
```python
async def verify_embedding_collections(
    self, client: WeaviateAsyncClient, environment_variables, libraries
):
    for embedder in embedders:
        if embedder.check_available(environment_variables, libraries):
            if "Model" in embedder.config:
                for _embedder in embedder.config["Model"].values:
                    normalized = self._normalize_embedder_name(_embedder)
                    self.embedding_table[_embedder] = "VERBA_Embedding_" + normalized
                    await self.verify_collection(
                        client, self.embedding_table[_embedder]
                    )
```

**Processo de Normalização:** (linha 602-636)
```python
def _normalize_embedder_name(self, embedder: str) -> str:
    # Remove hífens, pontos, etc.
    # all-MiniLM-L6-v2 → all_MiniLM_L6_v2
```

### ✅ Investigação Necessária

**1. Quando é chamado `verify_embedding_collections`?**

Procurar por chamadas no código:
```bash
grep -r "verify_embedding_collections" goldenverba/
```

Deve ser chamado durante:
- Inicialização do VerbaManager
- Conexão com Weaviate
- Setup de RAG config

**2. Verificar se SentenceTransformersEmbedder está disponível:**

```python
# O embedder está na lista?
# goldenverba/components/managers.py (linha 103-111)
embedders = [
    OllamaEmbedder(),
    SentenceTransformersEmbedder(),  # ✅ Está aqui
    WeaviateEmbedder(),
    # ...
]
```

**3. O modelo `all-MiniLM-L6-v2` está configurado?**

```python
# SentenceTransformersEmbedder deveria ter este modelo
# Arquivo: goldenverba/components/embedding/SentenceTransformersEmbedder.py
```

### 🔧 Verificação e Solução

#### **Step 1: Verificar o SentenceTransformersEmbedder**
```bash
grep -A 20 "class SentenceTransformersEmbedder" goldenverba/components/embedding/SentenceTransformersEmbedder.py
```

#### **Step 2: Garantir que coleções são criadas no connect**
```python
# Em VerbaManager ou WeaviateManager
async def on_connect(self):
    # ... after connecting to Weaviate ...
    await self.weaviate_manager.verify_embedding_collections(
        client,
        os.environ,
        sys.modules
    )
```

#### **Step 3: Adicionar log de debug**
```python
async def verify_embedding_collection(self, client: WeaviateAsyncClient, embedder):
    if embedder not in self.embedding_table:
        normalized = self._normalize_embedder_name(embedder)
        collection_name = "VERBA_Embedding_" + normalized
        msg.info(f"Verifying collection: {collection_name}")
        self.embedding_table[embedder] = collection_name
        result = await self.verify_collection(client, collection_name)
        msg.info(f"Collection {collection_name} verified: {result}")
        return result
    else:
        return True
```

---

## 🛠️ Plano de Ação

### Imediato (Hoje)

1. ✅ **[FIXADO] Plugin Reranker**
   - Adicionar `process_chunk()` e `process_batch()` métodos
   - Arquivo: `verba_extensions/plugins/reranker.py`
   - Status: ✅ COMPLETO

2. ⚠️ **[INVESTIGAR] WebSocket Error**
   - Capturar `RuntimeError` em `send_report()`
   - Arquivo: `goldenverba/server/helpers.py`
   - Status: PENDENTE IMPLEMENTAÇÃO

3. 🔍 **[INVESTIGAR] Collection não existe**
   - Verificar quando `verify_embedding_collections()` é chamado
   - Adicionar logs de debug
   - Status: PENDENTE INVESTIGAÇÃO

### Curto Prazo (Esta Semana)

- [ ] Implementar captura de exception no WebSocket
- [ ] Adicionar timeout para clients inativos
- [ ] Adicionar mais logs de debug no verify_collection
- [ ] Testar com documento grande (>50MB)

### Médio Prazo

- [ ] Implementar health check do WebSocket
- [ ] Adicionar fila de processamento com persistência
- [ ] Separar processamento pesado em worker assíncrono

---

## 📊 Impacto dos Erros

| Erro | Impacto | Usuário vê |
|------|--------|-----------|
| #1 (Reranker) | Chunks não são rerankeados | Query retorna resultados em ordem errada |
| #2 (WebSocket) | Import falha silenciosamente | "Import falhou" mas sem detalhes |
| #3 (Collection) | Embed não é armazenado | Query retorna 0 resultados |

---

## 🔗 Arquivos Relacionados

- `goldenverba/server/api.py` - WebSocket endpoints
- `goldenverba/server/helpers.py` - LoggerManager
- `goldenverba/components/managers.py` - WeaviateManager, collection management
- `verba_extensions/plugins/reranker.py` - RerankerPlugin (FIXADO)
- `verba_extensions/plugins/plugin_manager.py` - Plugin loading

---

**Última atualização:** 2025-11-04  
**Próxima ação:** Implementar solução para WebSocket error
