# 🐳 Instalação no Docker - Guia Rápido

## ⚡ Quick Start

### 1. Instale Docker (se ainda não tem)

**Windows:**
- Baixe: https://www.docker.com/products/docker-desktop/
- Instale e reinicie

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**Mac:**
- Baixe Docker Desktop para Mac
- Ou: `brew install --cask docker`

### 2. Clone e Configure

```bash
git clone https://github.com/MarceloMassarente/Verba.git
cd Verba

# Copie arquivo de exemplo (opcional)
cp .env.example .env

# Edite .env com suas chaves de API (opcional)
```

### 3. Inicie

```bash
# Build e inicia
docker-compose up -d

# Ver logs
docker-compose logs -f verba
```

### 4. Acesse

Abra: http://localhost:8000

---

## 📝 Configuração Básica

### Usar Weaviate Local (Padrão)

Já configurado no `docker-compose.yml`. Não precisa fazer nada!

### Usar Weaviate Externo (Railway/Cloud)

Edite `.env`:

```bash
WEAVIATE_URL_VERBA=https://seu-weaviate.up.railway.app
WEAVIATE_API_KEY_VERBA=  # Deixe vazio se não tiver
```

E comente o serviço `weaviate` no `docker-compose.yml`:

```yaml
services:
  # weaviate:  # Comentado - usando externo
  #   ...
```

---

## 🔧 Comandos Úteis

```bash
# Iniciar
docker-compose up -d

# Parar
docker-compose stop

# Parar e remover
docker-compose down

# Ver logs
docker-compose logs -f verba

# Rebuild após mudanças
docker-compose build --no-cache
docker-compose up -d

# Acessar shell do container
docker-compose exec verba bash

# Testar sistema
docker-compose exec verba python test_sistema_completo.py
```

---

## 🛠️ Desenvolvimento

Para desenvolvimento com hot-reload:

```bash
# Use docker-compose.dev.yml
docker-compose -f docker-compose.dev.yml up

# Código em verba_extensions/ será montado como volume
# Mudanças refletem imediatamente (após reload do Python)
```

---

## ✅ Verificação

Após iniciar, verifique:

```bash
# Container está rodando?
docker-compose ps

# Verba responde?
curl http://localhost:8000

# Weaviate responde?
curl http://localhost:8080/v1/.well-known/ready

# Testar extensões
docker-compose exec verba python test_sistema_completo.py
```

---

## 🐛 Problemas Comuns

### Porta 8000 já em uso

```bash
# Mude a porta no docker-compose.yml
ports:
  - 8081:8000  # Usa 8081 no host
```

### Container não inicia

```bash
# Ver logs detalhados
docker-compose logs verba

# Verifique variáveis de ambiente
docker-compose exec verba env | grep WEAVIATE
```

### Extensões não carregam

```bash
# Verifique se arquivos estão no container
docker-compose exec verba ls -la /Verba/verba_extensions

# Teste import
docker-compose exec verba python -c "import verba_extensions"
```

---

## 📦 O que está incluído

- ✅ Verba completo
- ✅ Extensões (EntityAware, A2Readers, ETL)
- ✅ Suporte Weaviate v3/v4
- ✅ Dependências instaladas (httpx, trafilatura, etc)
- ✅ Weaviate incluído (ou use externo)

---

## 🚀 Pronto!

Sistema rodando em: **http://localhost:8000**

Para mais detalhes, veja: `GUIA_DOCKER.md`

