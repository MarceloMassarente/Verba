# 🔧 Troubleshooting: Erro 403 Forbidden ao Conectar Weaviate

## ❌ Erro Identificado

Nos logs aparece:
```
POST /api/connect HTTP/1.1" 403 Forbidden
POST /api/get_meta HTTP/1.1" 403 Forbidden
```

E na interface mostra:
- **Connected to:** `https://weaviate-production-Od0e.up.railway.app/v1`
- **Deployment:** "Weaviate"

---

## 🔍 Possíveis Causas

### 1. URL com `/v1` no Final

O Verba pode estar adicionando `/v1` automaticamente. Verifique:

**❌ Errado:**
```
WEAVIATE_URL_VERBA=https://weaviate-production-Od0e.up.railway.app/v1
```

**✅ Correto:**
```
WEAVIATE_URL_VERBA=https://weaviate-production-Od0e.up.railway.app
```

### 2. Deployment Type Incorreto

Para Weaviate Railway (sem API key), deve ser **"Custom"**, não "Weaviate":

**No Railway Variables:**
```
WEAVIATE_URL_VERBA=https://weaviate-production-Od0e.up.railway.app
WEAVIATE_API_KEY_VERBA=
DEFAULT_DEPLOYMENT=Custom
```

**OU configure na UI do Verba:**
- Deployment: **Custom** (não "Weaviate")
- URL: `weaviate-production-Od0e.up.railway.app`
- Port: `443` (para HTTPS)
- API Key: (vazio)

### 3. Problema de Autenticação

Se seu Weaviate requer API key mas não foi fornecida, retorna 403.

**Solução:**
1. Verifique se seu Weaviate precisa de API key
2. Se sim, configure `WEAVIATE_API_KEY_VERBA`
3. Se não, deixe vazio mas use deployment "Custom"

### 4. Versão Weaviate Incompatível

Se for Weaviate v3 e o Verba espera v4, pode dar 403.

**Solução:** Use deployment "Custom" que tem fallback v3.

---

## ✅ Solução Passo a Passo

### Passo 1: Verifique a URL

No Railway → Verba → Variables, verifique:

```bash
# REMOVA /v1 do final se estiver
WEAVIATE_URL_VERBA=https://weaviate-production-Od0e.up.railway.app

# NÃO assim:
# WEAVIATE_URL_VERBA=https://weaviate-production-Od0e.up.railway.app/v1
```

### Passo 2: Configure Deployment Type

Adicione/edite:

```bash
DEFAULT_DEPLOYMENT=Custom
```

**OU** remova `DEFAULT_DEPLOYMENT` e configure na UI do Verba.

### Passo 3: Limpe Cache e Reconecte

1. No Verba UI → Settings → Admin
2. Clique em "Clear Config"
3. Tente conectar novamente na tela de login

### Passo 4: Verifique Logs Detalhados

No Railway → Verba → Deploy Logs, procure por:

```
INFO: Connecting to Weaviate Custom
INFO: Connecting to Weaviate at https://...
ERROR: ...
```

Isso mostrará o erro exato.

---

## 🔧 Configuração Recomendada (Railway)

### Variáveis de Ambiente no Railway:

```bash
# URL SEM /v1
WEAVIATE_URL_VERBA=https://weaviate-production-Od0e.up.railway.app

# API Key (vazio se não tiver)
WEAVIATE_API_KEY_VERBA=

# Deployment type
DEFAULT_DEPLOYMENT=Custom

# Outras (opcionais)
ENABLE_EXTENSIONS=true
ENABLE_ETL_A2=true
```

---

## 🧪 Teste de Conexão

Após configurar, teste via Railway logs:

1. Railway → Verba → Deploy Logs
2. Procure por mensagens de conexão
3. Se aparecer erro, copie a mensagem completa

---

## 📝 Checklist

- [ ] URL não tem `/v1` no final
- [ ] Deployment type é "Custom" (não "Weaviate")
- [ ] API Key configurada corretamente (ou vazia)
- [ ] Weaviate está acessível (teste: `curl https://weaviate-production-Od0e.up.railway.app/v1/.well-known/ready`)
- [ ] Variáveis foram salvas no Railway
- [ ] Container foi redeployado após mudanças

---

## 🚨 Se ainda não funcionar

1. **Teste direto o Weaviate:**
   ```bash
   curl https://weaviate-production-Od0e.up.railway.app/v1/.well-known/ready
   ```

2. **Verifique se precisa de API key:**
   ```bash
   curl https://weaviate-production-Od0e.up.railway.app/v1/meta
   # Se retornar 401, precisa de API key
   ```

3. **Veja logs detalhados** do Verba no Railway

4. **Tente deployment "Custom"** com host/port separados:
   - Host: `weaviate-production-Od0e.up.railway.app`
   - Port: `443`
   - API Key: (vazio)

---

**O erro 403 geralmente é:**
- URL malformada (com `/v1`)
- Deployment type errado ("Weaviate" ao invés de "Custom")
- Falta de API key quando requerida

