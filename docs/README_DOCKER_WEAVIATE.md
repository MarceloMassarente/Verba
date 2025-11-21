# 🐳 Weaviate no Docker - Resumo Rápido

## ✅ Sim, Weaviate é instalado automaticamente!

Por padrão, quando você roda:
```bash
docker-compose up -d
```

O Weaviate **sobe automaticamente** junto com o Verba. Não precisa fazer nada!

---

## 🔄 Como usar Weaviate externo

### Método 1: Ajustar docker-compose.yml (Simples)

**1. Edite `docker-compose.yml` e comente:**

```yaml
services:
  verba:
    # ... outras configs ...
    # COMENTE estas linhas:
    # depends_on:
    #   weaviate:
    #     condition: service_healthy

  # COMENTE todo o serviço weaviate:
  # weaviate:
  #   image: semitechnologies/weaviate:1.34.0
  #   # ... resto ...
```

**2. Crie/edite `.env`:**

```bash
# Para Railway (sem API key)
WEAVIATE_URL_VERBA=https://weaviate-production.up.railway.app
WEAVIATE_API_KEY_VERBA=

# Para Weaviate Cloud (com API key)
# WEAVIATE_URL_VERBA=https://cluster.weaviate.cloud
# WEAVIATE_API_KEY_VERBA=sua-api-key
```

**3. Reinicie:**

```bash
docker-compose down
docker-compose up -d
```

---

### Método 2: Usar arquivo separado

```bash
# Use o arquivo já pronto
cp docker-compose.externo.yml docker-compose.yml

# Configure .env
echo "WEAVIATE_URL_VERBA=https://seu-weaviate.com" >> .env

# Inicie
docker-compose up -d
```

---

## 📋 Resumo Visual

```
docker-compose up -d
    ↓
┌─────────────────┐
│  Verba (8000)   │
│                 │
│  ┌───────────┐  │
│  │ Weaviate  │  │ ← Instalado automaticamente
│  │  (8080)   │  │
│  └───────────┘  │
└─────────────────┘
```

**Para usar externo:**
- Comente serviço `weaviate:` no docker-compose.yml
- Configure `WEAVIATE_URL_VERBA` no .env
- Reinicie

---

## ✅ Teste Rápido

```bash
# Verificar qual Weaviate está sendo usado
docker-compose exec verba env | grep WEAVIATE_URL

# Testar conexão
docker-compose exec verba python test_cloud_simple.py
```

---

**Pronto!** Para mais detalhes, veja `GUIA_WEAVIATE_DOCKER.md`

