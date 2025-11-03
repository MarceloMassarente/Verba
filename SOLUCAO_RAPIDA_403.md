# ⚡ Solução Rápida: Erro 403 ao Conectar Weaviate

## 🔴 Problema Identificado

- **Erro**: `POST /api/connect HTTP/1.1" 403 Forbidden`
- **URL na interface**: `https://weaviate-production-Od0e.up.railway.app/v1`
- **Deployment**: "Weaviate"

---

## ✅ Solução Imediata

### Problema 1: URL com `/v1` no final

**❌ Errado:**
```
https://weaviate-production-Od0e.up.railway.app/v1
```

**✅ Correto:**
```
https://weaviate-production-Od0e.up.railway.app
```

### Problema 2: Deployment Type

Para Railway, use **"Custom"**, não "Weaviate".

---

## 🔧 Passo a Passo

### No Railway - Variáveis de Ambiente:

1. Railway → Verba → Settings → Variables
2. Edite ou adicione:

```bash
WEAVIATE_URL_VERBA=https://weaviate-production-Od0e.up.railway.app
```

**IMPORTANTE**: 
- ❌ SEM `/v1` no final
- ✅ Apenas o domínio

3. Configure também:

```bash
WEAVIATE_API_KEY_VERBA=
DEFAULT_DEPLOYMENT=Custom
```

4. Salve (Railway faz redeploy automático)

### No Verba UI - Tela de Login:

1. Acesse a tela de login do Verba
2. Selecione **"Custom"** (não "Weaviate")
3. Preencha:
   - **Host**: `weaviate-production-Od0e.up.railway.app`
   - **Port**: `443`
   - **API Key**: (deixe vazio)
4. Clique em Conectar

---

## 🔍 Verificação

Após configurar, nos logs do Railway você deve ver:

```
INFO: Connecting to Weaviate Custom
INFO: Connecting to Weaviate at https://weaviate-production-Od0e.up.railway.app
INFO: Succesfully Connected to Weaviate
```

**Se aparecer erro**, copie a mensagem completa dos logs.

---

## 📋 Checklist Rápido

- [ ] URL não tem `/v1` no final
- [ ] Deployment type = "Custom" (não "Weaviate")
- [ ] Port = 443 (para HTTPS)
- [ ] API Key = vazio (ou sua key se tiver)
- [ ] Weaviate está acessível (teste: `curl https://weaviate-production-Od0e.up.railway.app/v1/.well-known/ready`)

---

## 🚨 Se ainda não funcionar

### Teste direto o Weaviate:

```bash
# Teste se está acessível
curl https://weaviate-production-Od0e.up.railway.app/v1/.well-known/ready

# Se retornar 200, está OK
# Se retornar 401, precisa de API key
# Se retornar erro, verifique URL
```

### Veja logs detalhados:

Railway → Verba → Deploy Logs

Procure por:
- `ERROR:`
- `Couldn't connect`
- `403`
- `Forbidden`

---

## 💡 Dica

O erro 403 geralmente é:
1. **URL malformada** (com `/v1`) ← Mais comum
2. **Deployment type errado** ("Weaviate" ao invés de "Custom")
3. **Falta API key** quando requerida

**Solução mais comum**: Use deployment "Custom" com URL sem `/v1`!

