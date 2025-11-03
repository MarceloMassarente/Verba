# 🔗 Guia: Acesso Interno Railway (Mesmo Projeto)

## ✅ Se Verba e Weaviate estão no MESMO projeto Railway

Você pode usar acesso interno via rede Railway, que é:
- **Mais rápido** (comunicação interna)
- **Mais simples** (HTTP direto, sem HTTPS)
- **Mais seguro** (não passa pela internet pública)

---

## 🔧 Configuração

### Opção 1: Via Variável de Ambiente (Recomendado)

No Railway → **Verba** → Settings → Variables:

```bash
WEAVIATE_URL_VERBA=http://weaviate.railway.internal:8080
WEAVIATE_API_KEY_VERBA=
DEFAULT_DEPLOYMENT=Custom
```

### Opção 2: Via UI do Verba

Na tela de login do Verba:
- **Deployment**: `Custom`
- **Host**: `weaviate.railway.internal`
- **Port**: `8080`
- **API Key**: (deixe vazio)

---

## 🎯 Como Funciona

Railway cria uma rede interna privada onde serviços no mesmo projeto podem se comunicar:

```
┌─────────────────────────────────┐
│  Projeto Railway (mesmo)        │
│                                  │
│  ┌──────────┐    ┌──────────┐   │
│  │  Verba   │───▶│ Weaviate │   │
│  │          │HTTP │          │   │
│  │ :8000    │:8080│ :8080    │   │
│  └──────────┘    └──────────┘   │
│                                  │
│  Rede Interna Railway            │
│  (weaviate.railway.internal)     │
└─────────────────────────────────┘
```

**Vantagens:**
- ✅ HTTP direto (não precisa HTTPS)
- ✅ Porta 8080 funciona normalmente
- ✅ Sem problemas de CORS
- ✅ Mais rápido (rede interna)

---

## 🔍 Verificação

Nos logs do Verba, você deve ver:

```
ℹ Connecting to Weaviate Custom
ℹ Rede interna Railway detectada - usando HTTP porta 8080
ℹ URL Weaviate: http://weaviate.railway.internal:8080 (port: 8080, HTTPS: False)
✅ Conexao HTTP estabelecida
```

---

## ⚠️ Se Não Funcionar

Se o acesso interno não funcionar:

1. **Verifique se estão no mesmo projeto**:
   - Railway → Verifique se ambos serviços aparecem juntos

2. **Verifique o nome do serviço**:
   - O nome deve ser exatamente `weaviate` (nome do serviço no Railway)
   - Pode variar: `weaviate.railway.internal` ou apenas `weaviate`

3. **Use acesso público como fallback**:
   - Host: `weaviate-production-0d0e.up.railway.app`
   - Port: `443` (HTTPS)

---

## 📋 Comparação

| Método | Host | Port | Protocolo | Velocidade |
|--------|------|------|-----------|------------|
| **Interno** | `weaviate.railway.internal` | `8080` | HTTP | ⚡ Mais rápido |
| **Público** | `weaviate-production-0d0e.up.railway.app` | `443` | HTTPS | 🐌 Mais lento |

**Use interno se possível!** 🚀

