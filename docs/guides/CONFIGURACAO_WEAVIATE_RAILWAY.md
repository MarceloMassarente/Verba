# 🔧 Configuração do Weaviate no Railway

## 📋 Informações do Seu Weaviate

Baseado nas configurações do Railway:

### URL Pública (Externa)
```
https://weaviate-production-0d0e.up.railway.app
```
- **Porta**: 8080
- **Uso**: Para acesso de fora do Railway ou de outros projetos
- **Acesso**: HTTP público

### URL Privada (Interna)
```
weaviate.railway.internal
```
- **Uso**: Para comunicação dentro da rede Railway
- **Vantagem**: Mais rápido, sem passar pela internet pública
- **Requisito**: Verba e Weaviate precisam estar na mesma rede Railway

---

## ✅ Como Configurar no Verba

### Opção 1: Usar URL Pública (Recomendado para projetos separados)

**No Railway → Verba → Variables:**

```bash
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app
WEAVIATE_API_KEY_VERBA=
DEFAULT_DEPLOYMENT=Custom
```

**Na UI do Verba (tela de login):**
- Deployment: **Custom**
- Host: `weaviate-production-0d0e.up.railway.app`
- Port: `8080` (não 443, pois Railway usa porta 8080 internamente)
- API Key: (vazio)

**⚠️ IMPORTANTE**: Para URL pública, use porta **8080**, não 443!

---

### Opção 2: Usar URL Privada (Se no mesmo projeto)

Se Verba e Weaviate estão no **mesmo projeto Railway**:

```bash
WEAVIATE_URL_VERBA=http://weaviate.railway.internal:8080
WEAVIATE_API_KEY_VERBA=
DEFAULT_DEPLOYMENT=Custom
```

**Na UI:**
- Deployment: **Custom**
- Host: `weaviate.railway.internal`
- Port: `8080`
- API Key: (vazio)

**Vantagens:**
- ✅ Mais rápido (comunicação interna)
- ✅ Mais seguro (não passa pela internet pública)
- ✅ Não consome quota de rede externa

---

## 🔍 Verificação

### Teste URL Pública:
```bash
curl https://weaviate-production-0d0e.up.railway.app/v1/.well-known/ready
```

**Deve retornar**: Status 200 (sem conteúdo, mas OK)

### Teste URL Privada (se no mesmo projeto):
```bash
# Dentro do container do Verba
curl http://weaviate.railway.internal:8080/v1/.well-known/ready
```

---

## ⚠️ Problema Comum: Porta Errada

Se usar URL pública com porta 443:
- ❌ `https://weaviate-production-0d0e.up.railway.app:443`
- ❌ Não funciona! Railway expõe na porta 8080

**Correto:**
- ✅ `https://weaviate-production-0d0e.up.railway.app` (sem porta = porta padrão HTTP)
- ✅ `http://weaviate-production-0d0e.up.railway.app:8080` (explícito)

---

## 📝 Configuração Recomendada (Atual)

Como seu Verba está em **outro projeto**, use:

**Railway → Verba → Variables:**
```bash
# URL PÚBLICA (sem /v1 no final)
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app

# API Key (vazio se não tiver)
WEAVIATE_API_KEY_VERBA=

# Deployment
DEFAULT_DEPLOYMENT=Custom

# CORS (para evitar 403)
ALLOWED_ORIGINS=https://verba-production-c347.up.railway.app
```

**Na UI do Verba:**
- Deployment: **Custom**
- Host: `weaviate-production-0d0e.up.railway.app`
- Port: `8080` ← **IMPORTANTE: Use 8080, não 443!**
- API Key: (vazio)

---

## 🎯 Resumo

| Item | Valor |
|------|-------|
| **URL Pública** | `https://weaviate-production-0d0e.up.railway.app` |
| **URL Privada** | `weaviate.railway.internal` |
| **Porta** | 8080 |
| **API Key** | Não requerida (deixe vazio) |
| **Deployment** | Custom |

**Use URL pública se projetos estão separados (seu caso atual).**

