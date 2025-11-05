# 🔧 Guia: Configuração do Weaviate no Docker

## 📋 Como Funciona

### ✅ Weaviate Automático (Padrão)

Por padrão, o `docker-compose.yml` **já inclui o Weaviate** automaticamente:

```yaml
services:
  verba:
    # ...
    depends_on:
      weaviate:  # Weaviate roda junto
  
  weaviate:  # ← Serviço Weaviate incluído
    image: semitechnologies/weaviate:1.25.10
    # ...
```

**Você não precisa fazer nada!** O Weaviate sobe automaticamente junto com o Verba.

---

## 🔄 Usar Weaviate Externo

Se você já tem um Weaviate rodando (Railway, Cloud, outro servidor), siga estes passos:

### Opção 1: Ajustar docker-compose.yml (Recomendado)

**1. Comente o serviço weaviate:**

```yaml
services:
  verba:
    # ... configurações ...
    # Remove ou comenta esta linha:
    # depends_on:
    #   weaviate:
    #     condition: service_healthy

  # Comente todo o serviço weaviate:
  # weaviate:
  #   image: semitechnologies/weaviate:1.25.10
  #   # ... resto da config ...
```

**2. Configure variáveis de ambiente:**

Crie/edite arquivo `.env` na raiz:

```bash
# Para Weaviate Railway (sem API key)
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app
WEAVIATE_API_KEY_VERBA=

# Para Weaviate Cloud (com API key)
# WEAVIATE_URL_VERBA=https://cluster.weaviate.cloud
# WEAVIATE_API_KEY_VERBA=sua-api-key-aqui

# Para Weaviate em outro servidor
# WEAVIATE_URL_VERBA=http://outro-servidor:8080
# WEAVIATE_API_KEY_VERBA=
```

**3. Reinicie:**

```bash
docker-compose down
docker-compose up -d
```

---

### Opção 2: Usar Variáveis de Ambiente Direto

Sem editar `docker-compose.yml`, você pode sobrescrever via `.env`:

```bash
# .env
WEAVIATE_URL_VERBA=https://seu-weaviate.externo.com
WEAVIATE_API_KEY_VERBA=sua-key
```

E o `docker-compose.yml` já está configurado para usar essas variáveis!

---

## 🎯 Exemplos Práticos

### Exemplo 1: Weaviate Railway (sem API key)

**Arquivo `.env`:**
```bash
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app
WEAVIATE_API_KEY_VERBA=
```

**docker-compose.yml:** Comente apenas `depends_on: weaviate`

```yaml
services:
  verba:
    environment:
      - WEAVIATE_URL_VERBA=${WEAVIATE_URL_VERBA}
      - WEAVIATE_API_KEY_VERBA=${WEAVIATE_API_KEY_VERBA}
    # depends_on:  # Comentado
    #   weaviate:
```

---

### Exemplo 2: Weaviate Cloud (com API key)

**Arquivo `.env`:**
```bash
WEAVIATE_URL_VERBA=https://o3r2eli2twaoxcx50nrv3q.c0.us-west3.gcp.weaviate.cloud
WEAVIATE_API_KEY_VERBA=WR-wxyz123...
```

**docker-compose.yml:** Mesma configuração do exemplo 1

---

### Exemplo 3: Weaviate em Outro Container Docker

Se você tem Weaviate rodando em outro `docker-compose`:

**docker-compose.yml do Verba:**
```yaml
services:
  verba:
    environment:
      - WEAVIATE_URL_VERBA=http://weaviate-outro:8080
    networks:
      - verba-net
      - outro-net  # Rede onde está o outro Weaviate

networks:
  outro-net:
    external: true  # Usa rede externa
```

---

## 📝 Arquivo docker-compose.yml Completo para Externo

Aqui está um exemplo completo do `docker-compose.yml` configurado para usar Weaviate externo:

```yaml
---

services:
  verba:
    build:
      context: ./
      dockerfile: Dockerfile
    ports:
      - 8000:8000
    environment:
      # Configuração do Weaviate externo
      - WEAVIATE_URL_VERBA=${WEAVIATE_URL_VERBA:-http://weaviate:8080}
      - WEAVIATE_API_KEY_VERBA=${WEAVIATE_API_KEY_VERBA:-}
      
      # Outras configurações
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ENABLE_EXTENSIONS=true
      - ENABLE_ETL_A2=${ENABLE_ETL_A2:-true}
      
    volumes:
      - ./data:/data/
    
    # SEM depends_on - usando Weaviate externo
    # depends_on:
    #   weaviate:
    
    healthcheck:
      test: wget --no-verbose --tries=3 --spider http://localhost:8000 || exit 1
      interval: 5s
      timeout: 10s
      retries: 5
      start_period: 10s
    networks:
      - verba-net
    restart: unless-stopped

  # Serviço Weaviate COMENTADO - usando externo
  # weaviate:
  #   image: semitechnologies/weaviate:1.25.10
  #   # ...

networks:
  verba-net:
    external: false

volumes:
  # Sem volume do Weaviate se usar externo
```

---

## ✅ Verificação

### Testar Conexão com Weaviate Externo

```bash
# Dentro do container
docker-compose exec verba python test_cloud_simple.py

# Ou testar diretamente
docker-compose exec verba wget -O- ${WEAVIATE_URL_VERBA}/v1/.well-known/ready
```

### Verificar Variáveis de Ambiente

```bash
docker-compose exec verba env | grep WEAVIATE
```

---

## 🔄 Resumo Rápido

| Situação | Ação |
|----------|------|
| **Quer Weaviate local** | ✅ Não faça nada - já está configurado |
| **Quer Weaviate externo** | 1. Comente `depends_on: weaviate`<br>2. Configure `.env` com URL<br>3. Comente serviço `weaviate:` |
| **Quer trocar depois** | Edite `.env` e reinicie: `docker-compose down && docker-compose up -d` |

---

## 🚀 Quick Commands

```bash
# Usar Weaviate local (padrão)
docker-compose up -d

# Usar Weaviate externo (edite .env primeiro)
docker-compose down
# Edite .env
docker-compose up -d

# Verificar qual Weaviate está sendo usado
docker-compose exec verba env | grep WEAVIATE_URL
```

---

**Pronto!** Agora você sabe como configurar o Weaviate no Docker. 🎉

