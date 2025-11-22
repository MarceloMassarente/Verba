# Guia de Análise de Logs - Importação Sequencial

## ✅ O que verificar nos logs para confirmar que a correção funcionou:

### 1. **Semáforo Funcionando (Serialização)**
Procure por estas mensagens que indicam que os arquivos estão sendo processados sequencialmente:

```
[IMPORT] ⏳ Aguardando vez na fila (semáforo)... arquivo1.pdf...
[IMPORT] ✓ Adquiriu semáforo, iniciando import: arquivo1.pdf...
[IMPORT] 🚀 Starting import: arquivo1.pdf...
[IMPORT] ✅ Import completed: arquivo1.pdf... (took 120.5s)
```

**Para múltiplos arquivos, você deve ver:**
- Arquivo 1: Aguarda → Adquire → Processa → Completa
- Arquivo 2: Aguarda (enquanto arquivo 1 processa) → Adquire → Processa → Completa
- Arquivo 3: Aguarda (enquanto arquivo 2 processa) → Adquire → Processa → Completa

**❌ PROBLEMA se você ver:**
- Múltiplos arquivos "Adquiriu semáforo" ao mesmo tempo
- Arquivos processando simultaneamente sem esperar

### 2. **Keep-Alive Adaptativo**
Verifique se o intervalo de keep-alive está sendo ajustado baseado no tamanho do arquivo:

```
[IMPORT] File size: 1.8MB (1887436 bytes)
[IMPORT] Estimated processing time: 108s (~1.8m)
[KEEP-ALIVE] Arquivo médio (1.8MB) - usando intervalo de 2s
[KEEP-ALIVE] Tempo estimado: 108s (1.8 minutos)
```

**Categorias esperadas:**
- **> 5MB**: intervalo de 1s
- **> 1MB**: intervalo de 2s
- **≤ 1MB**: intervalo de 5s

### 3. **Timing Correto (took)**
Verifique se o valor `took` está sendo reportado corretamente (não sempre 0):

```
[IMPORT] ✅ Import completed: arquivo.pdf... (took 120.5s)
DONE | fileID123 | Import completed (120.5s) | 120.5
```

**❌ PROBLEMA se você ver:**
- `took: 0` em todos os imports completos
- `took` não corresponde ao tempo real de processamento

### 4. **Sem Erros de "Connection was interrupted"**
Não deve haver erros de conexão durante o processamento:

**✅ BOM:**
```
[WEBSOCKET] Client disconnected (normal during long imports)
[WEBSOCKET] Client disconnected before receiving report: Import completed
```

**❌ PROBLEMA:**
```
Connection was interrupted
WebSocket connection lost unexpectedly
```

### 5. **Processamento Sequencial Completo**
Para 3 arquivos, você deve ver um padrão claro:

```
# Arquivo 1
[IMPORT] ⏳ Aguardando vez na fila... arquivo1.pdf...
[IMPORT] ✓ Adquiriu semáforo, iniciando import: arquivo1.pdf...
[IMPORT] 🚀 Starting import: arquivo1.pdf...
... (processamento) ...
[IMPORT] ✅ Import completed: arquivo1.pdf... (took 120.5s)

# Arquivo 2 (só começa DEPOIS do arquivo 1 terminar)
[IMPORT] ⏳ Aguardando vez na fila... arquivo2.pdf...
[IMPORT] ✓ Adquiriu semáforo, iniciando import: arquivo2.pdf...
[IMPORT] 🚀 Starting import: arquivo2.pdf...
... (processamento) ...
[IMPORT] ✅ Import completed: arquivo2.pdf... (took 95.3s)

# Arquivo 3 (só começa DEPOIS do arquivo 2 terminar)
[IMPORT] ⏳ Aguardando vez na fila... arquivo3.pdf...
[IMPORT] ✓ Adquiriu semáforo, iniciando import: arquivo3.pdf...
[IMPORT] 🚀 Starting import: arquivo3.pdf...
... (processamento) ...
[IMPORT] ✅ Import completed: arquivo3.pdf... (took 78.2s)
```

## 📊 Resumo do que foi implementado:

1. **Semáforo (`_import_semaphore`)**: Garante que apenas 1 arquivo seja processado por vez
2. **Keep-alive adaptativo**: Intervalo baseado no tamanho do arquivo (1s/2s/5s)
3. **Timing preciso**: Usa `time.time()` para calcular `took` real
4. **Logging detalhado**: Mensagens claras para debug e monitoramento

## 🔍 Como compartilhar os logs:

Cole aqui os logs que contêm as mensagens `[IMPORT]`, `[KEEP-ALIVE]`, e `[WEBSOCKET]` para análise.

