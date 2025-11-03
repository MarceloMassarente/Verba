# 🐳 Guia: Instalação e Uso no Docker

## 📋 Pré-requisitos

- Docker instalado
- Docker Compose instalado (ou Docker com compose plugin)
- Pelo menos 2GB de RAM livre
- Pelo menos 5GB de espaço em disco

---

## 🚀 Instalação Rápida

### Opção 1: Usando Docker Compose (Recomendado)

```bash
# Clone o repositório (se ainda não fez)
git clone https://github.com/MarceloMassarente/Verba.git
cd Verba

# Crie arquivo .env (opcional)
cp .env.example .env

# Inicie os serviços
docker-compose up -d

# Ver logs
docker-compose logs -f verba
```

**Acesse**: http://localhost:8000

---

### Opção 2: Build Manual

```bash
# Build da imagem
docker build -t verba-extensions .

# Execute o container
docker run -d \
  -p 8000:8000 \
  -e WEAVIATE_URL_VERBA=http://weaviate-host:8080 \
  -e OPENAI_API_KEY=your-key \
  --name verba \
  verba-extensions
```

---

## ⚙️ Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```bash
# Weaviate
WEAVIATE_URL_VERBA=http://weaviate:8080
WEAVIATE_API_KEY_VERBA=

# Para usar Weaviate externo (Railway, Cloud, etc)
# WEAVIATE_URL_VERBA=https://seu-weaviate.up.railway.app
# WEAVIATE_API_KEY_VERBA=sua-api-key

# OpenAI (opcional)
OPENAI_API_KEY=sk-...

# Cohere (opcional)
COHERE_API_KEY=...

# Extensões
ENABLE_EXTENSIONS=true
ENABLE_ETL_A2=true
```

### Usando Weaviate Externo

Se você já tem um Weaviate rodando (Railway, Cloud, etc):

```yaml
# Em docker-compose.yml, comente o serviço weaviate
# E ajuste WEAVIATE_URL_VERBA no .env

services:
  verba:
    # ...
    environment:
      - WEAVIATE_URL_VERBA=https://seu-weaviate.up.railway.app
      - WEAVIATE_API_KEY_VERBA=sua-api-key
    # Remova depends_on: weaviate
```

---

## 🔧 Comandos Úteis

### Gerenciamento Básico

```bash
# Iniciar serviços
docker-compose up -d

# Parar serviços
docker-compose stop

# Parar e remover containers
docker-compose down

# Ver logs
docker-compose logs -f verba

# Rebuild após mudanças
docker-compose build --no-cache verba
docker-compose up -d
```

### Acesso ao Container

```bash
# Shell interativo
docker-compose exec verba bash

# Executar comandos
docker-compose exec verba python -m verba_extensions.startup
docker-compose exec verba python test_sistema_completo.py
```

### Limpar Dados

```bash
# Remove containers e volumes
docker-compose down -v

# Remove apenas volumes do Weaviate
docker volume rm verba_weaviate_data
```

---

## 📦 O que está incluído na imagem Docker

### Extensões Instaladas:
- ✅ Sistema de plugins (`verba_extensions/`)
- ✅ EntityAwareRetriever
- ✅ A2URLReader e A2ResultsReader
- ✅ A2ETLHook
- ✅ Adapters v3/v4 para Weaviate
- ✅ Sistema de hooks

### Dependências Instaladas:
- httpx (URL fetching)
- trafilatura (extração de texto)
- spacy (NER - opcional)
- nltk (chunking)

---

## 🎯 Usando com Weaviate Externo

### Weaviate Railway

```yaml
# docker-compose.yml
services:
  verba:
    environment:
      - WEAVIATE_URL_VERBA=https://weaviate-production.up.railway.app
      - WEAVIATE_API_KEY_VERBA=  # Deixe vazio se não tiver
```

### Weaviate Cloud

```yaml
services:
  verba:
    environment:
      - WEAVIATE_URL_VERBA=https://cluster.weaviate.cloud
      - WEAVIATE_API_KEY_VERBA=sua-api-key
```

---

## 🧪 Testando no Docker

### Teste de Sistema

```bash
# Dentro do container
docker-compose exec verba python test_sistema_completo.py

# Ou build local
docker-compose exec verba python scripts/check_dependencies.py
```

### Teste de Conexão

```bash
# Teste conexão Weaviate
docker-compose exec verba python test_cloud_simple.py
```

---

## 🐛 Troubleshooting

### Container não inicia

```bash
# Ver logs
docker-compose logs verba

# Verificar saúde
docker-compose ps
```

### Erro de conexão Weaviate

1. Verifique se Weaviate está acessível:
   ```bash
   docker-compose exec verba wget http://weaviate:8080/v1/.well-known/ready
   ```

2. Verifique variáveis de ambiente:
   ```bash
   docker-compose exec verba env | grep WEAVIATE
   ```

### Extensões não carregam

1. Verifique se arquivos estão copiados:
   ```bash
   docker-compose exec verba ls -la /Verba/verba_extensions
   ```

2. Verifique inicialização:
   ```bash
   docker-compose exec verba python -c "import verba_extensions.startup; print('OK')"
   ```

### Rebuild necessário após mudanças

```bash
# Rebuild completo
docker-compose build --no-cache verba
docker-compose up -d verba
```

---

## 📊 Produção

### Otimizações para Produção

1. **Use variáveis de ambiente seguras**:
   ```bash
   # Use docker secrets ou variáveis do host
   export WEAVIATE_API_KEY=$(cat /path/to/secret)
   docker-compose up -d
   ```

2. **Limite recursos**:
   ```yaml
   services:
     verba:
       deploy:
         resources:
           limits:
             memory: 2G
             cpus: '1.0'
   ```

3. **Use volumes named** (já configurado):
   - `weaviate_data` persiste dados do Weaviate

---

## 🚀 Quick Start Completo

```bash
# 1. Clone
git clone https://github.com/MarceloMassarente/Verba.git
cd Verba

# 2. Configure (opcional)
echo "OPENAI_API_KEY=sk-..." > .env

# 3. Inicie
docker-compose up -d

# 4. Aguarde inicialização
docker-compose logs -f verba

# 5. Acesse
open http://localhost:8000
```

---

## 📝 Notas Importantes

1. **Modelos spaCy**: Por padrão não são baixados. Descomente no Dockerfile se precisar:
   ```dockerfile
   RUN python -m spacy download pt_core_news_sm en_core_web_sm || true
   ```

2. **Desenvolvimento**: Para desenvolver com volumes mount:
   ```yaml
   volumes:
     - ./verba_extensions:/Verba/verba_extensions
   ```

3. **Portas**: 
   - Verba: 8000
   - Weaviate: 8080

---

**Pronto para usar!** 🎉

