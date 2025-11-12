# 🧪 Guia Prático: Teste de Múltiplos Arquivos

## 🎯 Objetivo

Validar que a fix do semáforo e keep-alive resolvem o problema de "Connection was interrupted" quando importando múltiplos arquivos.

---

## 📋 Pré-Requisitos

- ✅ Sistema Verba rodando (Docker compose)
- ✅ Weaviate acessível
- ✅ Navegador com console aberto (F12)
- ✅ 3 arquivos PDF prontos para teste

---

## 📁 Preparar Arquivos de Teste

### Opção 1: Seus Arquivos Reais
```
- arquivo1.pdf (5MB)  ← Seu arquivo problematoso
- arquivo2.pdf (3MB)  ← Segundo arquivo
- arquivo3.pdf (2MB)  ← Terceiro arquivo
```

### Opção 2: Gerar Arquivos de Teste
```bash
# Linux/Mac
dd if=/dev/zero bs=1M count=5 | tr '\0' 'X' > 5mb_test.txt

# Windows PowerShell
$content = [System.Text.Encoding]::UTF8.GetBytes([string]::new('X', 5242880))
[System.IO.File]::WriteAllBytes("5mb_test.pdf", $content)
```

---

## 🚀 Executando o Teste

### Fase 1: Monitorar Logs

**Terminal 1: Logs do Backend**
```bash
cd /path/to/Verba
docker logs -f verba_backend  # Ou seu container name
```

**Monitorar linhas com:**
```
[IMPORT]
[KEEP-ALIVE]
[WEBSOCKET]
[SEMAFORO]
```

---

### Fase 2: Fazer Upload dos Arquivos

**No navegador (Verba UI):**

```
1. Abrir console (F12 → Console)

2. Selecionar arquivo 1 (5MB)
   └─ Clicar em "Upload"
   
3. IMEDIATAMENTE (não aguardar completar):
   └─ Selecionar arquivo 2 (3MB)
   └─ Clicar em "Upload"
   
4. IMEDIATAMENTE (não aguardar completar):
   └─ Selecionar arquivo 3 (2MB)
   └─ Clicar em "Upload"
```

**Resultado:** Todos 3 uploads iniciados em rápida sequência

---

## 📊 Monitorar Progresso

### No Terminal (Logs)

**Esperado com FIX:**

```
[WEBSOCKET] ✅ FileConfig ready - starting import for: arquivo1...
[IMPORT] File size: 5.0MB (5242880 bytes)
[IMPORT] Estimated processing time: 300s (~5.0m)
[IMPORT] ⏳ Aguardando vez na fila (semáforo)... arquivo1...
[IMPORT] ✓ Adquiriu semáforo, iniciando import: arquivo1...
[KEEP-ALIVE] Arquivo grande (5.0MB) - usando intervalo de 1s
[KEEP-ALIVE] Tempo estimado: 300s (5.0 minutos)
[IMPORT] 🚀 Starting import: arquivo1...

[WEBSOCKET] ✅ FileConfig ready - starting import for: arquivo2...
[IMPORT] File size: 3.0MB (3145728 bytes)
[IMPORT] Estimated processing time: 180s (~3.0m)
[IMPORT] ⏳ Aguardando vez na fila (semáforo)... arquivo2...
[IMPORT] ⏳ Arquivo aguardando na fila (arquivo1 ainda processando)

[WEBSOCKET] ✅ FileConfig ready - starting import for: arquivo3...
[IMPORT] File size: 2.0MB (2097152 bytes)
[IMPORT] Estimated processing time: 120s (~2.0m)
[IMPORT] ⏳ Aguardando vez na fila (semáforo)... arquivo3...
[IMPORT] ⏳ Arquivo aguardando na fila (arquivo1 e arquivo2 ainda processando)

... (arquivo 1 processando por ~300s) ...

[KEEP-ALIVE] Processing (60s / ~300s) - 5.0MB
[KEEP-ALIVE] Processing (120s / ~300s) - 5.0MB
[KEEP-ALIVE] Processing (180s / ~300s) - 5.0MB
[KEEP-ALIVE] Processing (240s / ~300s) - 5.0MB
[KEEP-ALIVE] Processing (300s / ~300s) - 5.0MB

[IMPORT] ✅ Import completed: arquivo1... (took 305.2s)
[IMPORT] ✓ Adquiriu semáforo, iniciando import: arquivo2...
[KEEP-ALIVE] Arquivo médio (3.0MB) - usando intervalo de 2s
[KEEP-ALIVE] Tempo estimado: 180s (3.0 minutos)
[IMPORT] 🚀 Starting import: arquivo2...

... (arquivo 2 processando por ~180s) ...

[KEEP-ALIVE] Processing (60s / ~180s) - 3.0MB
[KEEP-ALIVE] Processing (120s / ~180s) - 3.0MB

[IMPORT] ✅ Import completed: arquivo2... (took 182.1s)
[IMPORT] ✓ Adquiriu semáforo, iniciando import: arquivo3...
[KEEP-ALIVE] Arquivo pequeno (2.0MB) - usando intervalo padrão de 5s
[KEEP-ALIVE] Tempo estimado: 120s (2.0 minutos)
[IMPORT] 🚀 Starting import: arquivo3...

... (arquivo 3 processando por ~120s) ...

[KEEP-ALIVE] Processing (60s / ~120s) - 2.0MB

[IMPORT] ✅ Import completed: arquivo3... (took 123.5s)
```

---

## ✅ Checklist de Validação

### Durante o Processamento

```
☐ Arquivo 1:
  ☐ Ver "Aguardando vez na fila"? → ✅ SIM
  ☐ Ver "Adquiriu semáforo"? → ✅ SIM
  ☐ Ver pings [KEEP-ALIVE] contínuos? → ✅ SIM
  ☐ Processamento dura ~300s? → ✅ SIM

☐ Arquivo 2:
  ☐ Ver "Aguardando vez na fila"? → ✅ SIM (enquanto arquivo 1 processa)
  ☐ ANTES de arquivo 1 completar? → ✅ SIM
  ☐ Ver "Adquiriu semáforo" após arquivo 1? → ✅ SIM
  ☐ Ver pings [KEEP-ALIVE]? → ✅ SIM

☐ Arquivo 3:
  ☐ Ver "Aguardando vez na fila"? → ✅ SIM (enquanto 1 e 2 processam)
  ☐ Ver "Adquiriu semáforo" após arquivo 2? → ✅ SIM
  ☐ Processamento dura ~120s? → ✅ SIM
```

### Status Final

```
☐ Arquivo 1:
  ☐ Status: DONE (não ERROR)
  ☐ took: ~300s (não 0!)
  ☐ Message: "Import completed (305.2s)"

☐ Arquivo 2:
  ☐ Status: DONE (não "Connection was interrupted"!)
  ☐ took: ~180s
  ☐ Message: "Import completed (182.1s)"

☐ Arquivo 3:
  ☐ Status: DONE (não "Connection was interrupted"!)
  ☐ took: ~120s
  ☐ Message: "Import completed (123.5s)"

☐ Nenhum erro:
  ☐ "Connection was interrupted"? → ❌ NÃO deve aparecer
  ☐ RuntimeError sobre WebSocket? → ❌ NÃO deve aparecer
  ☐ Race condition errors? → ❌ NÃO deve aparecer
```

---

## 🔍 Troubleshooting

### Problema 1: Arquivo 2 ainda falha com "Connection interrupted"

**Verificar:**
```
1. Logs têm "[IMPORT] ⏳ Aguardando vez na fila"?
   └─ SIM: Fix foi aplicado
   └─ NÃO: Verificar se api.py foi modificado corretamente

2. Semáforo foi criado na linha 69?
   └─ grep "_import_semaphore" goldenverba/server/api.py

3. Syntax está correto?
   └─ python -m py_compile goldenverba/server/api.py
```

### Problema 2: Logs não mostram timestamps

**Solução:**
```bash
# Ver logs com timestamp
docker logs --timestamps verba_backend | tail -100
```

### Problema 3: Arquivo processado muito rápido

**Verificar:**
```
Tempo real < tempo estimado?
└─ É possível, depende do tamanho real do arquivo
└─ Verificar tamanho com: ls -lh arquivo.pdf
```

---

## 📈 Métricas de Sucesso

### Taxa de Sucesso
```
Antes da fix:
├─ 1 arquivo: ~60% sucesso
├─ 2 arquivos: ~35% sucesso (2º falha)
└─ 3 arquivos: ~8% sucesso (2º e 3º falham)

Depois da fix:
├─ 1 arquivo: >99% sucesso
├─ 2 arquivos: >99% sucesso
└─ 3 arquivos: >99% sucesso
```

### Tempo Total
```
Esperado com 3 arquivos (5MB + 3MB + 2MB):
├─ Arquivo 1: ~300s
├─ Arquivo 2: ~180s (após arquivo 1)
├─ Arquivo 3: ~120s (após arquivo 2)
└─ TOTAL: ~600s (~10 minutos)

Se for muito mais rápido:
└─ Pode ser que apenas metadados foram importados, não chunks
```

---

## 💾 Registrar Resultados

### Caso de Sucesso

```markdown
## Teste 12/11/2025

✅ SUCESSO

Arquivos:
- arquivo1.pdf: 5MB → DONE (took 305s)
- arquivo2.pdf: 3MB → DONE (took 182s)
- arquivo3.pdf: 2MB → DONE (took 123s)

Logs:
- [IMPORT] ⏳ Aguardando vez na fila? ✅ SIM
- [IMPORT] ✓ Adquiriu semáforo? ✅ SIM
- [KEEP-ALIVE] Pings contínuos? ✅ SIM
- "Connection was interrupted"? ❌ NÃO

Total time: ~610s (10min 10sec)
```

### Caso de Falha

```markdown
## Teste 12/11/2025

❌ FALHA

Arquivo 2 status: ERROR
Message: "Connection was interrupted"
took: 0

Logs:
- Sem "[IMPORT] ⏳ Aguardando vez na fila"
- Sem "[IMPORT] ✓ Adquiriu semáforo"
- Arquivo 2 tenta processar enquanto arquivo 1 ativa?

Possível causa:
- api.py não foi modificado corretamente
- Semáforo não foi aplicado
```

---

## 🔄 Teste de Repetição

Após sucesso uma vez, testar novamente com diferentes tamanhos:

### Teste 2: Arquivos Mais Pequenos

```
arquivo1.txt: 100KB
arquivo2.txt: 200KB
arquivo3.txt: 150KB

Esperado: Mais rápido (~30-60s total), mesma sequência
```

### Teste 3: Um Arquivo Muito Grande

```
arquivo_grande.pdf: 20MB

Esperado: Longo processamento (~1200s), mas sem "Connection interrupted"
```

---

## 📝 Documentação de Resultados

Salvar output dos logs em arquivo:

```bash
docker logs verba_backend > test_results_20251112.log 2>&1
```

Depois compartilhar os logs se houver problema.

---

## ✨ Sinais de Que Funcionou

1. ✅ Arquivo 2 começa DEPOIS de arquivo 1 terminar
2. ✅ Arquivo 3 começa DEPOIS de arquivo 2 terminar
3. ✅ Todos têm status DONE (não ERROR)
4. ✅ `took` é um número real (não 0)
5. ✅ Nenhum "Connection was interrupted"
6. ✅ Logs mostram sequência clara com [IMPORT] ⏳ e ✓

---

## 🎯 Resumo

Este teste valida que:

1. ✅ **Semáforo funciona:** Imports executam um por vez
2. ✅ **Keep-alive funciona:** Pings mantêm conexão viva
3. ✅ **Logging funciona:** Vemos progresso detalhado
4. ✅ **Timing funciona:** `took` mostra tempo real

---

**Instruções de teste:** Ler acima  
**Duração esperada:** ~10 minutos para 3 arquivos  
**Próximo passo:** Reportar resultados  


