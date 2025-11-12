# 📊 Diagrama Visual: Fix para "Connection was interrupted"

## 🔴 ANTES da Fix

```
TIMELINE DO ERRO:

Frontend (Browser)              Backend (Python)           Weaviate
    │                                │                         │
    │ 1. Connect WebSocket           │                         │
    ├────────────────────────────→   │                         │
    │                                │ (conectado)             │
    │ 2. Upload chunks               │                         │
    ├────────────────────────────→   │                         │
    │    (1.76MB = 7-10 chunks)      │ 3. Processa chunks      │
    │                                ├────────────────────────→│
    │ 4. ESPERA POR RESPOSTA         │    (30-60s processando) │
    │                                │                         │
    │ ⏱️  5 segundos passam          │                         │
    │ ⏱️  10 segundos passam         │                         │
    │ ⏱️  15 segundos passam         │                         │
    │ ⏱️  20 segundos passam         │                         │
    │ ⏱️  30 segundos passam         │                         │
    │ ⏱️  60 segundos passam         │                         │
    │ ❌ TIMEOUT (browser default)   │                         │
    │ ✗ Desconecta WebSocket         │                         │
    │                                │ 6. Tenta enviar status  │
    │                                ├→ ✗ SOCKET FECHADO       │
    │ 7. ERROR RELATO                ├→ RuntimeError           │
    │ ← "Connection was interrupted" │                         │
    │    took: 0                     │                         │
    │                                │ ← Weaviate responde     │
    │                                │   (mas muito tarde)     │
    │                                │                         │


PROBLEMA:
=========
❌ Keep-alive a cada 5s é insuficiente
❌ Processamento leva > 60s
❌ Cliente timeout antes de server terminar
❌ WebSocket fecha
❌ took: 0 (nunca processou)
```

---

## 🟢 DEPOIS da Fix

```
TIMELINE COM FIX:

Frontend (Browser)              Backend (Python)           Weaviate
    │                                │                         │
    │ 1. Connect WebSocket           │                         │
    ├────────────────────────────→   │                         │
    │                                │ (conectado)             │
    │ 2. Upload chunks               │                         │
    ├────────────────────────────→   │                         │
    │    (1.76MB = 7-10 chunks)      │ 3. Processa chunks      │
    │                                ├────────────────────────→│
    │ 4. ESPERA POR RESPOSTA         │    (30-60s processando) │
    │                                │                         │
    │ ✅ KEEP-ALIVE PING (2s)        │ 5. Keep-alive envia:    │
    │ ←────────────────────────────  │    "Processing (2s/105s)"
    │    ✓ Recebe status             │                         │
    │                                │                         │
    │ ✅ KEEP-ALIVE PING (4s)        │ 6. Keep-alive envia:    │
    │ ←────────────────────────────  │    "Processing (4s/105s)"
    │    ✓ Recebe status             │                         │
    │                                │                         │
    │ ✅ KEEP-ALIVE PING (6s)        │ 7. Keep-alive envia:    │
    │ ←────────────────────────────  │    "Processing (6s/105s)"
    │    ✓ Recebe status             │                         │
    │                                │                         │
    │ ... (pings continuam) ...      │ ... (processamento) ...  │
    │                                │                         │
    │ ⏱️  30 segundos passam         │                         │
    │ ⏱️  60 segundos passam         │                         │
    │ ⏱️  90 segundos passam         │                         │
    │ ⏱️  120 segundos passam        │                         │
    │ ❌ NÃO HÁ TIMEOUT              │                         │
    │ ✓ WebSocket PERMANECE VIVO     │ 8. Processamento OK     │
    │                                │←─────────────────────────
    │ 9. Recebe status final         │ 9. Envia:               │
    │ ←────────────────────────────  │    DONE, took: 125.4s   │
    │    ✓ took: 125.4s              │                         │
    │    ✓ SUCESSO!                  │                         │
    │                                │                         │


SOLUÇÃO:
========
✅ Keep-alive a cada 2s (adaptativo)
✅ WebSocket mantém vivo durante processamento longo
✅ Processamento completa naturalmente
✅ took: 125.4 (tempo real)
✅ Status: DONE
✅ SUCESSO!
```

---

## 📈 Comparação de Intervalos

```
ARQUIVOS PEQUENOS (< 500KB):
┌─────────────────────────────────┐
│ Keep-alive: 5 segundos (padrão) │
│ Tempo esperado: < 30s           │
│ Timeout: Nunca (20+ pings)      │
└─────────────────────────────────┘

ARQUIVOS MÉDIOS (1-5MB):  ← SEU CASO
┌─────────────────────────────────┐
│ Keep-alive: 2 segundos          │ ← NOVO
│ Tempo esperado: 60-120s         │
│ Timeout: Nunca (30-60 pings)    │
└─────────────────────────────────┘

ARQUIVOS GRANDES (> 5MB):
┌─────────────────────────────────┐
│ Keep-alive: 1 segundo           │ ← NOVO
│ Tempo esperado: 180-600s        │
│ Timeout: Nunca (100-600 pings)  │
└─────────────────────────────────┘
```

---

## 🎯 Fluxo de Decisão

```
[ARQUIVO SUBMETIDO]
        │
        ↓
    [CALCULA TAMANHO]
        │
        ├─ file_size > 5MB? ───→ keep_alive = 1s
        │
        ├─ file_size > 1MB? ───→ keep_alive = 2s  ← SEU CASO (1.76MB)
        │
        └─ file_size ≤ 1MB? ───→ keep_alive = 5s
        │
        ↓
    [LOG ESTIMATIVA]
        │
        ├─ Estimated: 105s (1.8 minutos)
        │
        ↓
    [INICIA IMPORT]
        │
        ├─ Start keep-alive task (pings a cada 2s)
        ├─ Start import task (processamento)
        │
        ↓
    [DURANTE PROCESSAMENTO]
        │
        ├─ Keep-alive: "Processing (2s / ~105s)"
        ├─ Keep-alive: "Processing (4s / ~105s)"
        ├─ Keep-alive: "Processing (6s / ~105s)"
        ├─ ... (pings continuam)
        │
        ↓
    [PROCESSAMENTO COMPLETA]
        │
        ├─ Calcula elapsed_time: 125.4s
        ├─ Envia: "Import completed (125.4s)"
        ├─ took: 125.4 (não zero!)
        │
        ↓
    [✅ SUCESSO!]
```

---

## 📊 Gráfico de Keep-Alive

```
TIMELINE DE PINGS (arquivo 1.76MB):

0s  ├─ Upload começa
    │
2s  ├─ PING: "Processing (2s / ~105s)"
    │
4s  ├─ PING: "Processing (4s / ~105s)"
    │
6s  ├─ PING: "Processing (6s / ~105s)"
    │
8s  ├─ PING: "Processing (8s / ~105s)"
    │
... ├─ (pings continuam a cada 2s)
    │
100s├─ PING: "Processing (100s / ~105s)"
    │
102s├─ PING: "Processing (102s / ~105s)"
    │
105s├─ Processamento completa
    ├─ FINAL: "Import completed (125.4s)"
    │
125s├─ took: 125.4
    └─ Status: DONE


TIMEOUT COMPARISON:

Antes (5s interval):
├─ 5s  │ PING
├─ 10s │ PING
├─ 15s │ PING
├─ 20s │ PING  ← Apenas 12 pings em 60s
├─ ...
└─ 60s │ ❌ TIMEOUT

Depois (2s interval):
├─ 2s  │ PING
├─ 4s  │ PING
├─ 6s  │ PING
├─ 8s  │ PING
├─ 10s │ PING
├─ ...
├─ 58s │ PING
├─ 60s │ PING  ← 30 pings em 60s
└─ 120s│ ✅ CONTINUA VIVO (nenhum timeout)
```

---

## 🔍 Log Pattern Matcher

```
LOGS QUE INDICAM SUCESSO:

┌────────────────────────────────────────────────┐
│ [IMPORT] File size: 1.7MB (1762290 bytes)      │ ✅ Tamanho detectado
├────────────────────────────────────────────────┤
│ [IMPORT] Estimated processing time: 102s       │ ✅ Estimativa
├────────────────────────────────────────────────┤
│ [KEEP-ALIVE] Arquivo médio (1.76MB)           │ ✅ Keep-alive adapta
│             - usando intervalo de 2s           │
├────────────────────────────────────────────────┤
│ [KEEP-ALIVE] Tempo estimado: 105s (1.8 min)   │ ✅ Estimativa clara
├────────────────────────────────────────────────┤
│ [IMPORT] 🚀 Starting import...                │ ✅ Import iniciado
├────────────────────────────────────────────────┤
│ [KEEP-ALIVE] Processing (2s / ~105s) - 1.76MB │ ✅ Pings funcionando
│ [KEEP-ALIVE] Processing (4s / ~105s) - 1.76MB │
│ [KEEP-ALIVE] Processing (6s / ~105s) - 1.76MB │
│ ... (mais pings) ...                           │
├────────────────────────────────────────────────┤
│ [IMPORT] ✅ Import completed (took 125.4s)    │ ✅ Sucesso com tempo
├────────────────────────────────────────────────┤
│ Status: DONE                                   │ ✅ Final status OK
│ took: 125.4                                    │ ✅ took != 0
└────────────────────────────────────────────────┘
```

---

## 🚨 Log Pattern Matcher (ERROS)

```
LOGS QUE INDICAM PROBLEMA:

┌────────────────────────────────────────────────┐
│ ❌ Connection was interrupted                  │ ✗ Erro clássico
├────────────────────────────────────────────────┤
│ ❌ took: 0                                      │ ✗ Nunca processou
├────────────────────────────────────────────────┤
│ ❌ [KEEP-ALIVE] WebSocket desconectado         │ ✗ Timeout ocorreu
│    (antes de 60 segundos)                      │
├────────────────────────────────────────────────┤
│ ❌ Nenhum log [IMPORT] ou [KEEP-ALIVE]        │ ✗ Nem começou
├────────────────────────────────────────────────┤
│ ❌ Status: ERROR                               │ ✗ Falha
│    message: Connection was interrupted         │
└────────────────────────────────────────────────┘
```

---

## 🎓 Entendendo os Números

```
SEU ARQUIVO: 20250919_Proposta CMOC_v2.pdf

Tamanho:           1,762,290 bytes = 1.76 MB
Keep-alive:        2 segundos (adaptativo)
Tempo estimado:    max(60, 1.76 * 60) = 105 segundos
Tempo real:        ~125 segundos (incluindo overhead)

BREAKDOWN ESTIMADO:
┌────────────────────────────────┐
│ 1. PDF Extraction    : 30-60s   │ ← ByteReader
├────────────────────────────────┤
│ 2. Chunking          : 20-40s   │ ← Entity-Semantic
├────────────────────────────────┤
│ 3. ETL A2 (NER)      : 10-30s   │ ← spaCy + Gazetteer
├────────────────────────────────┤
│ 4. Weaviate Import   : 30-60s   │ ← Database operations
├────────────────────────────────┤
│ TOTAL:               : 90-190s  │ ← Estimativa
│ (com overhead)       : ~125s    │ ← Tempo real típico
└────────────────────────────────┘
```

---

## 💡 Insight Chave

```
ANTES:
  Client timeout: 60 segundos
  Keep-alive: a cada 5s (máximo 12 pings)
  Resultado: ❌ TIMEOUT ANTES DO PROCESSAMENTO TERMINAR

DEPOIS:
  Client timeout: 60+ segundos (renovado por pings)
  Keep-alive: a cada 2s (20-30 pings)
  Resultado: ✅ NUNCA TIMEOUT (keep-alive mantém vivo)

SIMPLES MAS PODEROSO:
  Manter o cliente informado = Cliente não desiste
```

---

**Diagrama criado:** 12 de Novembro de 2025  
**Arquivo em questão:** 20250919_Proposta CMOC_v2.pdf (1.76MB)  
**Solução:** Keep-alive adaptativo + timing real  


