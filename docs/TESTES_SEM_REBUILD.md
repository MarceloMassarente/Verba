# 🚀 Testes Rápidos - SEM Rebuild da Imagem

## ✅ Teste 1: Verificar Variáveis de Ambiente (1 minuto)

```bash
# Terminal
cd C:\Users\marce\VERBA\Verba

# Conectar ao Railway CLI
railway variables

# Procurar por estas variáveis CRÍTICAS:
# PRODUCTION = Demo?  (THIS IS THE LIKELY CULPRIT!)
# WEAVIATE_URL
# PORT
```

**Se `PRODUCTION=Demo`:**
```bash
# Remover ou mudar
railway variables unset PRODUCTION
# ou
railway variables set PRODUCTION production

# Isso vai fazer redeploy automaticamente
```

---

## ✅ Teste 2: Monitorar Logs em Tempo Real (5 minutos)

```bash
# Terminal 1: Monitorar logs
railway logs -f

# Em outro terminal/abra do navegador:
# 1. Abra https://seu-app.railway.app
# 2. Abra DevTools (F12)
# 3. Vá para aba "Console"
# 4. Selecione um arquivo e clique "Import Selected"
# 5. Compartilhe TUDO que aparecer com prefixo:
#    - [WS-SETUP]
#    - [WS-MESSAGE]
#    - [UPLOAD-DEBUG]
#    - [WEBSOCKET] (backend)
```

**O que procurar nos logs:**
- ✅ `[WS-SETUP] ✅ WebSocket connection OPENED` = Conexão OK
- ❌ `[WS-SETUP] ❌ WebSocket Error` = Problema de conexão
- ✅ `[UPLOAD-DEBUG] Sending batch 1/X` = Frontend enviando
- ✅ `[WEBSOCKET] Received message` = Backend recebendo

---

## ✅ Teste 3: Testar WebSocket Diretamente (3 minutos)

### Opção A: Usando wscat (Recomendado)

```bash
# 1. Instalar wscat (se não tiver)
npm install -g wscat

# 2. Conectar ao WebSocket (SUBSTITUA COM SUA URL)
wscat -c wss://seu-app.railway.app/ws/import_files

# 3. Enviar teste simples
{"chunk": "test", "order": 0, "total": 1, "fileID": "test123", "isLastChunk": true, "credentials": {}}

# 4. Verificar resposta
# Deve receber algo como:
# {"fileID": "test123", "status": "STARTING", "message": "...", "took": 0}
```

### Opção B: Usando curl (se wscat não funcionar)

```bash
# Instalar websocat (alternativa cross-platform)
# No PowerShell:
scoop install websocat

# Ou via cargo (Rust):
cargo install websocat

# Conectar:
websocat wss://seu-app.railway.app/ws/import_files

# Enviar JSON
{"chunk": "test", "order": 0, "total": 1, "fileID": "test123", "isLastChunk": true, "credentials": {}}
```

---

## ✅ Teste 4: Testar Localmente (10 minutos)

Se quiser testar **localmente** sem rebuild:

```bash
# Terminal 1: Backend
cd C:\Users\marce\VERBA\Verba
python -m uvicorn goldenverba.server.api:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd C:\Users\marce\VERBA\Verba\frontend
npm run dev
# Vai rodar em http://localhost:3000

# Terminal 3: Monitorar logs
cd C:\Users\marce\VERBA\Verba
# (já está rodando no Terminal 1)

# Terminal 4: Teste WebSocket local
wscat -c ws://localhost:8000/ws/import_files
# Enviar: {"chunk": "test", "order": 0, "total": 1, "fileID": "test123", "isLastChunk": true, "credentials": {}}
```

**Resultado esperado:**
- ✅ Se funcionar localmente → Problema é de configuração do Railway
- ❌ Se não funcionar localmente → Problema está no código

---

## ✅ Teste 5: Verificar Production Mode (1 minuto)

```bash
# Na aplicação rodando localmente ou em Railway
# Abra DevTools Console

# Digitar:
console.log(window.location.protocol)
// Deve mostrar: https: (produção) ou http: (local)

console.log(window.location.host)
// Deve mostrar: seu-app.railway.app ou localhost:3000
```

**Se tiver mismatch (HTTPS com ws://):**
```typescript
// Isso causaria erro - verificar em frontend/app/util.ts
const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
```

---

## 🎯 Teste Sequencial Recomendado (Comece Aqui!)

### Passo 1: Diagnóstico Rápido (5 minutos)
```bash
# 1. Verificar PRODUCTION
railway variables | grep -i production

# 2. Se PRODUCTION=Demo, MUDE:
railway variables set PRODUCTION production

# 3. Monitore logs enquanto muda:
railway logs -f
```

### Passo 2: Se ainda não funcionar (10 minutos)
```bash
# 1. Abra a app em produção
# 2. F12 → Console
# 3. Procure por estes logs IMPORTANTES:
#    [WS-SETUP] Creating WebSocket connection to: wss://...
#    [UPLOAD-DEBUG] Sending batch 1/...

# Se VER: [WS-SETUP] ✅ WebSocket connection OPENED
#   → Problema está DEPOIS (no envio dos batches)
# Se NÃO VER: [WS-SETUP] 
#   → Problema está NA CONEXÃO

# Compartilhe EXATAMENTE o que vê
```

### Passo 3: Se conexão está OK (outro 10 minutos)
```bash
# Teste local:
python -m uvicorn goldenverba.server.api:app --reload
# Em outro terminal:
wscat -c ws://localhost:8000/ws/import_files
{"chunk": "test", "order": 0, "total": 1, "fileID": "test", "isLastChunk": true, "credentials": {}}

# Deve receber resposta
```

---

## 📊 Matriz de Diagnóstico Rápido

| Sintoma | Causa Provável | Teste |
|---------|---|---|
| DevTools não mostra `[WS-SETUP]` | Frontend não carregou novos logs | Fazer hard refresh (Ctrl+Shift+R) |
| `[WS-SETUP] ✅ OPENED` mas sem `[UPLOAD-DEBUG]` | Botão "Import" não foi clicado ou arquivo não está selecionado | Verificar se arquivo está selecionado (azul na lista) |
| `[WS-SETUP] ❌ WebSocket Error` | Conexão bloqueada ou wss:// falha | Testar com wscat, verificar certificado |
| `[WEBSOCKET]` não aparece nos logs | Variável PRODUCTION=Demo está ativada | `railway variables \| grep -i production` |
| wscat conexão recusada | WebSocket não está rodando/escutando | Verificar se backend está rodando |
| Arquivo selecionado mas botão desativado | Arquivo não passou na validação | Verificar console para erros de validação |

---

## 🔍 O que Procurar em Cada Log

### Console do Navegador (F12)

```
✅ BOM:
[WS-SETUP] Creating WebSocket connection to: wss://app.railway.app/ws/import_files
[WS-SETUP] ✅ WebSocket connection OPENED to wss://app.railway.app/ws/import_files
[WS-SETUP] ReadyState: 1 (1=OPEN)
[UPLOAD-DEBUG] Starting upload
[UPLOAD-DEBUG] Socket is OPEN, proceeding with send
[UPLOAD-DEBUG] Total data length: 53000 chars
[UPLOAD-DEBUG] Total batches to send: 27
[UPLOAD-DEBUG] Sending batch 1/27, payload size: 2500 bytes
[UPLOAD-DEBUG] All 27 batches sent to WebSocket
[WS-MESSAGE] Received message, length: 85
[WS-MESSAGE] Parsed data type: StatusReport
[WS-MESSAGE] Data: {fileID: "...", status: "STARTING", ...}

❌ RUIM:
[WS-SETUP] Creating WebSocket connection to: ws://app.railway.app/ws/import_files
// (não recebe WS-SETUP OPENED)
[WS-SETUP] ❌ WebSocket Error: [object Event]
// (não aparece UPLOAD-DEBUG)
```

### Logs do Railway (railway logs -f)

```
✅ BOM:
[WEBSOCKET] Import WebSocket connection accepted
[WEBSOCKET] Received message (length: 2500 chars)
[BATCH] Progress: 1/27 chunks received (3.7%)
[BATCH] Progress: 25/27 chunks received (92.6%)
[BATCH] Completed collection for Mercado de...
[IMPORT] Starting import for file: arquivo.pdf

❌ RUIM:
// (não há logs de WEBSOCKET recebendo)
// (não há logs de BATCH)
// (apenas logs de health check)
```

---

## 💡 Dicas Práticas

### Debug no Console
```javascript
// Copie e cole no Console do DevTools (F12) durante o teste:

// Ver se socket existe
window.socket

// Ver estado do socket (0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED)
window.socket?.readyState

// Enviar teste manual
window.socket?.send(JSON.stringify({
  chunk: "test",
  order: 0,
  total: 1,
  fileID: "teste123",
  isLastChunk: true,
  credentials: {}
}))
```

### Limpar Cache
```bash
# Se logs antigos aparecerem, limpar cache do navegador:
# Chrome/Edge: Ctrl+Shift+Delete
# Firefox: Ctrl+Shift+Delete
# Depois: Hard Refresh (Ctrl+Shift+R)
```

---

## 🆘 Se Tudo Falhar - Informações para Coletar

Quando compartilhar para debug, coleta:

```
1. Output completo de:
   railway variables

2. Screenshot/log completo do:
   railway logs -f
   (durante tentativa de import)

3. Console do navegador (F12):
   Todos os logs com prefixo [WS-] e [UPLOAD-]

4. Tamanho do arquivo:
   (no Windows) dir "Estudo Mercado Headhunting Brasil.pdf"

5. Se testar com wscat:
   wscat -c wss://seu-app.railway.app/ws/import_files
   (output completo)

6. Se testar localmente:
   python -m uvicorn goldenverba.server.api:app --reload
   (output durante teste)
```

---

## ⏱️ Estimativa de Tempo

| Teste | Tempo | Insight |
|-------|-------|---------|
| Teste 1 (Vars env) | 1 min | Vai resolver 50% dos problemas |
| Teste 2 (Logs) | 5 min | Vai apontar exatamente onde está falhando |
| Teste 3 (wscat) | 3 min | Confirma se WebSocket está funcional |
| Teste 4 (Local) | 10 min | Identifica se é problema de código ou deploy |
| **Total** | **19 min** | **95% de chance de resolver** |

---

## ✨ Comece Aqui Agora

```bash
# Terminal
railway variables | grep -i production
# Copie a resposta aqui

# Se for Demo, execute:
railway variables set PRODUCTION production

# Depois verifique:
railway logs -f

# E compartilhe screenshot/texto dos logs
```
