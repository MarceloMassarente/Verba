# 🔧 Solução: Erro 403 por Validação de Origin

## 🔴 Problema Identificado

O erro `403 Forbidden` em `/api/connect` e `/api/get_meta` está sendo causado por um **middleware de validação de Origin** no código do Verba.

O código verifica o header `Origin` e bloqueia requisições que não vêm de:
- `http://localhost:*`
- Mesmo domínio do servidor

---

## ✅ Solução 1: Ajustar Variáveis de Ambiente (Recomendado)

O middleware pode estar sendo muito restritivo no Railway. Configure:

```bash
# No Railway → Verba → Variables
ALLOWED_ORIGINS=*
# OU
ALLOWED_ORIGINS=https://verba-production-c347.up.railway.app
```

---

## ✅ Solução 2: Verificar URL do Weaviate

O problema pode ser a URL com `/v1` no final:

**No Railway Variables:**
```bash
# ❌ ERRADO
WEAVIATE_URL_VERBA=https://weaviate-production-Od0e.up.railway.app/v1

# ✅ CORRETO
WEAVIATE_URL_VERBA=https://weaviate-production-Od0e.up.railway.app
```

**E use Deployment "Custom":**
```bash
DEFAULT_DEPLOYMENT=Custom
```

---

## ✅ Solução 3: Modificar Código (Se necessário)

Se as soluções acima não funcionarem, pode ser necessário ajustar o middleware de CORS.

O código está em `goldenverba/server/api.py` linhas ~70-110.

**Para Railway**, o middleware pode precisar permitir:
- O domínio do próprio Railway
- Requisições do frontend

---

## 🔍 Diagnóstico

### Passo 1: Verifique os Headers

Nos logs HTTP do Railway, veja os detalhes da requisição 403:
- `request_origin`: Qual origin está sendo enviado?
- `expected_origin`: Qual origin o servidor espera?

### Passo 2: Teste Direto

Tente acessar diretamente:
```bash
curl -X POST https://verba-production-c347.up.railway.app/api/connect \
  -H "Origin: https://verba-production-c347.up.railway.app" \
  -H "Content-Type: application/json" \
  -d '{"credentials": {...}}'
```

---

## 📋 Checklist

- [ ] URL do Weaviate SEM `/v1` no final
- [ ] Deployment type = "Custom"
- [ ] Variáveis de ambiente configuradas no Railway
- [ ] Verificar headers Origin nas requisições
- [ ] Logs mostram qual origin está sendo bloqueado

---

## 🚨 Solução Temporária (Se urgente)

Se precisar de uma solução rápida, pode modificar temporariamente o middleware em `api.py`:

```python
# Linha ~95, mude de:
if request.url.path.startswith("/api/"):
    return JSONResponse(status_code=403, ...)

# Para:
if request.url.path.startswith("/api/") and request.url.path != "/api/health":
    # Apenas para rotas específicas, não todas
    if origin and origin not in allowed_origins:
        return JSONResponse(status_code=403, ...)
```

**Mas isso é temporário!** A solução correta é configurar as variáveis.

---

## 💡 Dica

O erro 403 está vindo **antes** da tentativa de conexão com Weaviate. Isso significa que o Verba nem chega a tentar conectar - está bloqueado pelo middleware.

**Solução mais provável**: Configure `ALLOWED_ORIGINS` ou ajuste o middleware para Railway.

