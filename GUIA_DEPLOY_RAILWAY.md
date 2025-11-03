# 🚀 Guia: Deploy Correto no Railway

## ⚠️ Problema Atual

Os logs mostram que o código antigo ainda está rodando:
- `Railway porta 8080 detectado - tentando HTTP primeiro` ❌
- Deveria mostrar: `Railway porta 8080 detectado - usando HTTPS porta 443` ✅

## ✅ Solução

### 1. Verificar se código foi deployado

No Railway:
- Verba → Deploy Logs
- Verifique o commit hash (deve ser `7352494` ou mais recente)
- Verifique se build completou sem erros

### 2. Forçar redeploy

Se necessário:
```bash
# No Railway UI:
# Verba → Settings → Deploy
# Clique em "Redeploy"
```

### 3. Verificar variáveis de ambiente

No Railway → Verba → Variables:
- Não precisa de variáveis especiais
- `WEAVIATE_URL_VERBA` pode estar vazio
- `WEAVIATE_API_KEY_VERBA` pode estar vazio

### 4. Configuração na UI do Verba

Após redeploy, use:
- **Host**: `weaviate-production-0d0e.up.railway.app`
- **Port**: `8080` (código converte automaticamente para HTTPS 443)
- **API Key**: (deixe vazio)

OU:

- **Host**: `weaviate-production-0d0e.up.railway.app`  
- **Port**: `443`
- **API Key**: (deixe vazio)

## 🔍 O que esperar nos logs após correção

```
ℹ Connecting to Weaviate Custom
ℹ Railway porta 8080 detectado - usando HTTPS porta 443 (porta 8080 é interna)
ℹ URL Weaviate: https://weaviate-production-0d0e.up.railway.app (port: 443, HTTPS: True)
ℹ Usando conexao HTTPS externa
✅ Conexao HTTPS estabelecida via use_async_with_local
```

**NÃO** deve aparecer:
- ❌ "tentando HTTP primeiro"
- ❌ "URL Weaviate: http://..."

