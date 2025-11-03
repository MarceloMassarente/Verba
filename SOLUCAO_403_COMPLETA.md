# ✅ Solução Completa: Erro 403 Forbidden

## 🔴 Causa do Problema

O erro `403 Forbidden` em `/api/connect` está sendo causado por um **middleware de segurança** no Verba que valida o header `Origin`.

O middleware bloqueia requisições que não vêm do mesmo domínio, o que causa problemas no Railway onde o frontend e backend podem ter origins ligeiramente diferentes.

---

## ✅ Solução Aplicada

Corrigi o código em `goldenverba/server/api.py` para:

1. **Aceitar variável `ALLOWED_ORIGINS`** do ambiente
2. **Permitir automaticamente domínios `.railway.app`**
3. **Manter compatibilidade** com localhost e desenvolvimento

---

## 🔧 Como Resolver Agora

### Opção 1: Configurar Variável (Mais Seguro)

No Railway → Verba → Settings → Variables, adicione:

```bash
ALLOWED_ORIGINS=https://verba-production-c347.up.railway.app
```

**OU** para permitir todos (menos seguro, mas funciona):

```bash
ALLOWED_ORIGINS=*
```

### Opção 2: Usar o Código Corrigido

O código agora **já permite automaticamente** domínios Railway. Mas você precisa:

1. **Fazer commit e push** do código corrigido
2. **Railway vai fazer redeploy** automaticamente

---

## 📋 Configuração Completa no Railway

Configure estas variáveis:

```bash
# Weaviate (SEM /v1 no final!)
WEAVIATE_URL_VERBA=https://weaviate-production-Od0e.up.railway.app
WEAVIATE_API_KEY_VERBA=

# CORS/Origin (para evitar 403)
ALLOWED_ORIGINS=https://verba-production-c347.up.railway.app
# OU simplesmente:
# ALLOWED_ORIGINS=*

# Deployment
DEFAULT_DEPLOYMENT=Custom

# Extensões
ENABLE_EXTENSIONS=true
ENABLE_ETL_A2=true
```

---

## ✅ Checklist

- [x] Código corrigido para aceitar Railway domains
- [ ] Configure `ALLOWED_ORIGINS` no Railway
- [ ] URL Weaviate SEM `/v1`
- [ ] Deployment = "Custom"
- [ ] Commit e push do código corrigido

---

## 🚀 Próximos Passos

1. **Commit o código corrigido:**
   ```bash
   git add goldenverba/server/api.py
   git commit -m "fix: Allow Railway origins in CORS middleware"
   git push
   ```

2. **Configure variáveis no Railway** (veja acima)

3. **Aguarde redeploy** (automático após push)

4. **Teste novamente** a conexão

---

**O código agora permite automaticamente domínios Railway, mas configure `ALLOWED_ORIGINS` para garantir!**

