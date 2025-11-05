# ✅ Configuração Final - Railway

## 🔧 Configuração Correta do Weaviate

### No Railway → Verba → Settings → Variables

Configure estas variáveis:

```bash
# Weaviate - URL PÚBLICA (SEM /v1 no final)
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app

# Weaviate - Porta (8080, não 443!)
WEAVIATE_PORT=8080

# Weaviate - API Key (vazio se não tiver)
WEAVIATE_API_KEY_VERBA=

# Deployment Type
DEFAULT_DEPLOYMENT=Custom

# CORS (para evitar erro 403)
ALLOWED_ORIGINS=https://verba-production-c347.up.railway.app

# Extensões
ENABLE_EXTENSIONS=true
ENABLE_ETL_A2=true

# Tika (opcional mas recomendado para PPTX, DOC, RTF, etc.)
TIKA_SERVER_URL=http://192.168.1.197:9998
```

---

## 📋 Na UI do Verba

Quando acessar a tela de login:

1. **Deployment**: Selecione **"Custom"** (não "Weaviate")
2. **Host**: `weaviate-production-0d0e.up.railway.app`
3. **Port**: `8080` ← **IMPORTANTE: 8080, não 443!**
4. **API Key**: (deixe vazio)

---

## ⚠️ Erros Comuns

### ❌ Erro 1: URL com `/v1`
```
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app/v1
```
**✅ Correto**: Remova `/v1` do final

### ❌ Erro 2: Porta 443
```
Port: 443
```
**✅ Correto**: Use porta `8080` (Railway expõe Weaviate na 8080)

### ❌ Erro 3: Deployment "Weaviate"
```
Deployment: Weaviate
```
**✅ Correto**: Use **"Custom"** para Railway

### ❌ Erro 4: Erro 403
**✅ Solução**: Configure `ALLOWED_ORIGINS` (já corrigido no código)

---

## 🔍 Verificação

Após configurar, nos logs do Railway você deve ver:

```
INFO: Connecting to Weaviate Custom
INFO: Connecting to Weaviate at https://weaviate-production-0d0e.up.railway.app
INFO: Succesfully Connected to Weaviate
```

**Se aparecer erro**, veja a mensagem completa nos logs.

---

## 📊 Resumo das URLs

| Tipo | URL | Quando Usar |
|------|-----|-------------|
| **Pública** | `https://weaviate-production-0d0e.up.railway.app` | Projetos separados (seu caso) |
| **Privada** | `http://weaviate.railway.internal:8080` | Mesmo projeto Railway |

**Você está usando**: URL Pública ✅

---

## ✅ Checklist Final

- [ ] URL sem `/v1` no final
- [ ] Porta 8080 (não 443)
- [ ] Deployment = "Custom"
- [ ] API Key vazia (ou sua key)
- [ ] `ALLOWED_ORIGINS` configurado
- [ ] Código corrigido commitado

**Pronto para conectar!** 🚀

