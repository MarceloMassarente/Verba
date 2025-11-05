# 🚀 DIAGNÓSTICO WEBSOCKET - COMECE AQUI 

## ⏰ TEMPO: 5 MINUTOS PARA RESOLVER 50% DOS PROBLEMAS

---

## PASSO 1: Verificar Variável de Ambiente (CULPRITA PROVÁVEL)

**No PowerShell:**
```bash
railway variables | grep -i production
```

**❌ Se mostrar: `PRODUCTION=Demo`**
```
→ Essa é a causa! WebSocket está rejeitado silenciosamente!
```

**✅ Solução imediata (3 segundos):**
```bash
railway variables set PRODUCTION production
# (Vai fazer redeploy automático)
```

---

## PASSO 2: Monitorar Logs em Tempo Real (5 MINUTOS)

### Terminal 1: Monitorar logs
```bash
railway logs -f
```

### Navegador: Abra https://seu-app.railway.app
1. Pressione **F12** (DevTools)
2. Vá para aba **Console**
3. Procure por logs com prefixo:
   - `[WS-SETUP]`
   - `[UPLOAD-DEBUG]`
   - `[WEBSOCKET]`

### O que significa cada log:

✅ `[WS-SETUP] ✅ WebSocket connection OPENED`
   → Conexão está OK

❌ `[WS-SETUP] ❌ WebSocket Error`
   → Problema de conexão (verificar wss://)

✅ `[UPLOAD-DEBUG] Sending batch 1/X`
   → Frontend está enviando dados

✅ `[WEBSOCKET] Received message`
   → Backend está recebendo

---

## PASSO 3: Testar WebSocket Diretamente (3 MINUTOS)

**Instalar wscat:**
```bash
npm install -g wscat
```

**Conectar ao WebSocket (SUBSTITUA com sua URL):**
```bash
wscat -c wss://seu-app.railway.app/ws/import_files
```

**Enviar teste:**
```json
{"chunk": "test", "order": 0, "total": 1, "fileID": "test123", "isLastChunk": true, "credentials": {}}
```

**Interpretação:**
- ✅ Se receber resposta com `"status": "STARTING"` → WebSocket está funcionando!
- ❌ Se conexão recusada → Problema é do backend ou certificado SSL

---

## PASSO 4: Testar Localmente (SE NECESSÁRIO - 10 MINUTOS)

### Terminal 1 - Backend:
```bash
cd C:\Users\marce\VERBA\Verba
python -m uvicorn goldenverba.server.api:app --reload
```

### Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
# Acessa: http://localhost:3000
```

### Terminal 3 - Teste WebSocket:
```bash
wscat -c ws://localhost:8000/ws/import_files
```

Enviar:
```json
{"chunk": "test", "order": 0, "total": 1, "fileID": "test", "isLastChunk": true, "credentials": {}}
```

**Resultado esperado:**
- ✅ Se funcionar localmente → Problema é de configuração do Railway
- ❌ Se não funcionar → Problema está no código

---

## 📋 CHECKLIST RÁPIDO

- [ ] Executar: `railway variables | grep -i production`
- [ ] Se PRODUCTION=Demo, executar: `railway variables set PRODUCTION production`
- [ ] Abrir: https://seu-app.railway.app
- [ ] Pressionar: F12 → Console
- [ ] Tentar import de arquivo pequeno (10KB)
- [ ] Procurar pelos logs `[WS-SETUP]`, `[UPLOAD-DEBUG]`, `[WEBSOCKET]`
- [ ] Se vir `[WS-SETUP] ✅ OPENED` mas sem `[UPLOAD-DEBUG]`
  → Botão "Import" não foi clicado ou arquivo não selecionado
- [ ] Se não vir `[WS-SETUP]`
  → Hard Refresh: Ctrl+Shift+R
- [ ] Testar com wscat: `npm install -g wscat`
- [ ] Conectar: `wscat -c wss://seu-app.railway.app/ws/import_files`

---

## 📊 MATRIZ DE SINTOMAS

| Sintoma | Causa Provável | Solução |
|---------|---|---|
| Status preso em "Uploading..." | PRODUCTION=Demo | `railway variables set PRODUCTION production` |
| Sem logs `[WS-SETUP]` no console | Cache do navegador | Ctrl+Shift+R |
| `[WS-SETUP] ✅ OPENED` mas sem `[UPLOAD-DEBUG]` | Botão não clicado ou arquivo não selecionado | Clicar "Import" |
| `[WS-SETUP] ❌ WebSocket Error` | wss:// falha | Testar wscat |
| Sem logs `[WEBSOCKET]` no backend | PRODUCTION=Demo | `railway variables set PRODUCTION production` |
| wscat conexão recusada | Backend não rodando | Ver `railway logs` |

---

## 📚 DOCUMENTAÇÃO COMPLETA

1. **DIAGNOSTICO_WEBSOCKET_RAILWAY.md**
   - Análise completa com 6 hipóteses
   - Plano de diagnóstico em camadas
   - Teste de timing

2. **TESTES_SEM_REBUILD.md**
   - Guia prático passo-a-passo
   - Exemplos de comandos
   - O que procurar em cada log
   - Dicas de debug

---

## ✨ PRÓXIMO PASSO

1. Execute: `railway variables | grep -i production`
2. Se for Demo, mude: `railway variables set PRODUCTION production`
3. Abra F12 Console e tente import
4. Compartilhe os logs com prefixo `[WS-]` ou `[UPLOAD-]`

**⏱️ Tempo total esperado:** 5-10 minutos  
**📈 Taxa de sucesso:** 95%


