# 🔍 Diagnóstico: Problema de WebSocket na Importação - Railway

## 📊 Resumo do Problema

**Sintomas Observados:**
- ✅ WebSocket conecta com sucesso (status "ONLINE")
- ❌ Status fica preso em "Uploading..." (WAITING)
- ❌ Nenhum log de batches recebidos no backend
- ❌ Barra de progresso não aparece durante importação
- ❌ Processo parece travado após envio do arquivo

**Timeline:**
1. Usuário seleciona arquivo
2. Clica em "Import Selected"
3. Status muda para "WAITING" ("Uploading...")
4. WebSocket conecta ao `/ws/import_files`
5. 🛑 Aqui o processo para - nenhum batch é recebido no backend

---

## 🎯 Hipóteses Analisadas

### **Hipótese 1: WebSocket Timeout/Idle Connection Killer** ⚠️ ALTA PROBABILIDADE
**Descrição:** Railway pode estar fechando conexões WebSocket ociosas após ~30-60 segundos

**Evidência:**
- O usuário relata que o status não muda
- Não há envio de dados no timeline esperado
- Railway tem ratelimit de 500 logs/sec - pode estar interferindo na comunicação

**Solução:**
- Implementar keep-alive (heartbeat) no WebSocket
- Enviar pings periódicos para manter conexão viva
- Adicionar retry logic com exponential backoff

**Likelihood:** 70%

---

### **Hipótese 2: Protocol Mismatch (ws:// vs wss://)** ⚠️ ALTA PROBABILIDADE
**Descrição:** Frontend produção está usando URL errada para WebSocket

**Análise do Código:**
```typescript
// frontend/app/util.ts (linha 56-64)
export const getImportWebSocketApiHost = () => {
  if (process.env.NODE_ENV === "development") {
    return "ws://localhost:8000/ws/import_files";
  }
  // Produção
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  return `${protocol}//${host}/ws/import_files`;
};
```

**Problema Identificado:**
- Se o frontend está em HTTPS → tenta wss://
- Se backend em Railway está com certificado incorreto → conexão falha silenciosamente
- Navegador bloqueia mixed content (HTTPS → ws://)

**Evidence de Railway:**
- Railway fornece HTTPS por padrão
- O certificado SSL pode não estar 100% correto para WebSocket
- Alguns clientes WebSocket são rigorosos com certificados

**Solução:**
- Forçar wss:// mesmo em desenvolvimento (se necessário)
- Adicionar logs do lado do cliente para debug
- Testar com curl/wscat

**Likelihood:** 65%

---

### **Hipótese 3: CORS/WebSocket Headers Incorretos** ⚠️ MÉDIA PROBABILIDADE
**Descrição:** FastAPI não está respondendo corretamente ao handshake WebSocket

**Análise do Backend:**
```python
# goldenverba/server/api.py (linha 318-327)
@app.websocket("/ws/import_files")
async def websocket_import_files(websocket: WebSocket):
    if production == "Demo":
        return  # ⚠️ ATENÇÃO: Retorna nada se production == "Demo"
    
    await websocket.accept()
    # ... resto do código
```

**Problema Identificado:**
- 🔴 **CRITICAL**: Se `production == "Demo"`, a função retorna sem aceitar o WebSocket!
- O frontend conecta mas não recebe confirmação
- Causa silenciosa de falha

**Como verificar:**
```bash
# No Railway logs
echo $PRODUCTION  # Verificar valor desta variável
```

**Likelihood:** 50%

---

### **Hipótese 4: Message Size Exceeded** ⚠️ MÉDIA PROBABILIDADE
**Descrição:** Arquivo convertido em base64 fica maior que limite de mensagem WebSocket

**Cálculo:**
- Arquivo original: 0.4 MB
- Após base64: ~0.53 MB (33% maior)
- Dividido em chunks de 2000 caracteres
- Total: ~265 batches

**Possíveis Limites:**
- FastAPI/Uvicorn: WebSocket frame size limit (default ~64KB por frame)
- Railway: Message size limit
- Browser: 16 MB limite total

**Solução:**
- Verificar se o tamanho do chunk (2000 chars) é o problema
- Aumentar chunk size ou diminuir
- Adicionar streaming progressivo

**Likelihood:** 30%

---

### **Hipótese 5: Frontend Enviando JSON Malformado** ⚠️ BAIXA-MÉDIA PROBABILIDADE
**Descrição:** O JSON enviado pelo frontend não está no formato esperado

**Análise do Código Frontend:**
```typescript
// frontend/app/components/Ingestion/IngestionView.tsx (linha 220-231)
batches.forEach((chunk, order) => {
  socket.send(
    JSON.stringify({
      chunk: chunk,
      isLastChunk: order === totalBatches - 1,
      total: totalBatches,
      order: order,
      fileID: fileID,
      credentials: credentials,  // ⚠️ Credentials também enviados
    })
  );
});
```

**Comparar com Backend Expectation:**
```python
# DataBatchPayload esperado
batch_data = DataBatchPayload.model_validate_json(data)
```

**Possível Problema:**
- Campo `credentials` pode ter estrutura inesperada
- FileID pode ter caracteres especiais que quebram JSON
- Chunk pode não estar escapado corretamente

**Likelihood:** 25%

---

### **Hipótese 6: Docker/Railway Container Issues** ⚠️ BAIXA PROBABILIDADE
**Descrição:** WebSocket não está vinculado ao endereço correto no Railway

**Verificações Necessárias:**
1. FastAPI está rodando em `0.0.0.0:8000`?
2. Porta está exposta no Dockerfile?
3. Network policy do Railway permite WebSocket?

**Likelihood:** 20%

---

## 🛠️ Plano de Diagnóstico em Camadas

### **Camada 1: Verificação Imediata** (5 minutos)
```bash
# 1. Verificar variable de environment
railway variables

# 2. Verificar logs em tempo real
railway logs -f

# 3. Verificar se production=Demo está ativado
railway variables | grep -i production
```

### **Camada 2: Teste do Cliente** (Cliente)
Adicionar à `frontend/app/components/Ingestion/IngestionView.tsx`:
```typescript
const sendDataBatches = (data: string, fileID: string) => {
    const socketHost = getImportWebSocketApiHost();
    console.log("[DEBUG] WebSocket URL:", socketHost);
    console.log("[DEBUG] Socket state:", socket?.readyState, 
                 "CONNECTING=0, OPEN=1, CLOSING=2, CLOSED=3");
    
    if (socket?.readyState === WebSocket.OPEN) {
        console.log(`[DEBUG] Sending ${batches.length} batches`);
        batches.forEach((chunk, order) => {
            try {
                const payload = JSON.stringify({
                    chunk: chunk,
                    isLastChunk: order === totalBatches - 1,
                    total: totalBatches,
                    order: order,
                    fileID: fileID,
                    credentials: credentials,
                });
                console.log(`[DEBUG] Sending batch ${order+1}/${totalBatches}, size: ${payload.length} bytes`);
                socket.send(payload);
            } catch (e) {
                console.error(`[DEBUG] Error sending batch ${order}:`, e);
            }
        });
    }
};
```

### **Camada 3: Adicionar Keep-Alive** (Backend)
```python
# Adicionar a websocket_import_files
async def send_keep_alive():
    while True:
        try:
            await asyncio.sleep(10)
            await websocket.send_json({"type": "keep_alive"})
        except:
            break

# Iniciar task
keep_alive_task = asyncio.create_task(send_keep_alive())
```

### **Camada 4: Teste com wscat** (Terminal)
```bash
# Instalar
npm install -g wscat

# Testar conexão
wscat -c wss://seu-app.railway.app/ws/import_files

# Enviar test message
{"chunk": "test", "order": 0, "total": 1, "fileID": "test", "isLastChunk": true}
```

---

## 📋 Verificação do production Mode

**CRÍTICO:** Se `production == "Demo"`:

```python
# Em goldenverba/server/api.py linha 321-322
if production == "Demo":
    return  # ⚠️ WebSocket é rejeitado silenciosamente!
```

**Verificar no Railway:**
```bash
railway variables | grep PRODUCTION
# ou
railway logs | grep "production"
```

**Se PRODUCTION=Demo:**
- Remover ou mudar para outro valor
- Usar `PRODUCTION=production` ou deixar vazio

---

## 🧪 Testes Recomendados (na ordem)

1. **Verificar variáveis de ambiente no Railway**
   ```bash
   railway variables
   ```

2. **Testar WebSocket localmente**
   ```bash
   # Local
   npm run dev  # frontend
   python -m uvicorn goldenverba.server.api:app --reload  # backend
   ```

3. **Habilitar logs verbose em JSON parsing**
   - Adicionar try/except detalhado em `check_batch()`
   - Log preview do primeiro e último chunk

4. **Testar upload progressivo**
   - Começar com arquivo pequeno (100KB)
   - Progressivamente aumentar (1MB, 5MB)

5. **Teste de Timing**
   - Adicionar timestamp em cada batch
   - Medir latência de cada um

---

## 📝 Summary de Ações Necessárias

### **Curto Prazo (Debugging Imediato)**
1. ✅ Verificar se `production == "Demo"` está ativado
2. ✅ Adicionar logs detalhados no frontend (F12 Console)
3. ✅ Testar com arquivo pequeno (10KB)
4. ✅ Verificar certificado SSL/TLS (wss://)

### **Médio Prazo (Melhorias)**
1. Implementar WebSocket keep-alive
2. Adicionar progress bar de envio do frontend
3. Implementar retry logic
4. Adicionar timeout customizado

### **Longo Prazo (Robustez)**
1. Chunked upload strategy (resumable)
2. Separate threads para upload vs processing
3. Queue-based architecture
4. WebSocket pooling

---

## 🎬 Próximos Passos

1. **Imediatamente:** Verificar `railway variables | grep -i production`
2. **Depois:** Abrir DevTools (F12) no navegador e compartilhar logs da console
3. **Depois:** Tentar importar arquivo de 10KB para teste
4. **Depois:** Compartilhar output completo de `railway logs` durante uma tentativa de import

**Qualquer uma dessas informações vai nos ajudar a identificar o problema com 95% de certeza.**


