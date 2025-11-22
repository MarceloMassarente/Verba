# Dockerfile.weaviate - Guia de Uso no Railway

## 📋 Visão Geral

O `Dockerfile.weaviate` é um Dockerfile otimizado para executar Weaviate 1.34.0 em modo BYOV (Bring Your Own Vectors) no Railway, especificamente configurado para o Verba RAG System.

---

## 🎯 Características Principais

### BYOV Mode (Bring Your Own Vectors)
- ✅ **Sem módulos externos**: Verba fornece seus próprios vetores
- ✅ **BM25 nativo**: Usa BM25 nativo do Weaviate (não precisa de módulos)
- ✅ **Performance otimizada**: Configurações ajustadas para produção

### Configurações Otimizadas
- ✅ **Cache de vetores**: 70% da RAM disponível
- ✅ **Indexação paralela**: Usa todos os CPUs disponíveis
- ✅ **Compressão GZIP**: Reduz tráfego de rede
- ✅ **gRPC habilitado**: Porta 50051 para melhor performance

---

## 🚀 Como Usar no Railway

### Opção 1: Usar Dockerfile.weaviate do Repositório

1. **No Railway, configure o serviço Weaviate:**
   - Source: Este repositório
   - Dockerfile Path: `Dockerfile.weaviate`
   - Build Command: (deixe vazio, Railway detecta automaticamente)

2. **Variáveis de Ambiente (opcionais):**
   ```bash
   # Já configuradas no Dockerfile, mas podem ser sobrescritas:
   AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true
   PERSISTENCE_DATA_PATH=/var/lib/weaviate
   QUERY_DEFAULTS_LIMIT=25
   LOG_LEVEL=info
   ```

3. **Portas:**
   - **8080**: HTTP/REST API (público)
   - **50051**: gRPC API (público ou rede privada)

4. **Volumes:**
   - Railway cria volume automaticamente em `/var/lib/weaviate`

---

### Opção 2: Usar Rede Privada Railway

Para melhor performance e segurança, use rede privada Railway:

1. **Configure variáveis de ambiente no Verba:**
   ```bash
   # Conexão HTTP (REST)
   WEAVIATE_HTTP_HOST=weaviate.railway.internal
   WEAVIATE_HTTP_PORT=8080
   WEAVIATE_HTTP_SECURE=False
   
   # Conexão gRPC (Alta Performance)
   WEAVIATE_GRPC_HOST=weaviate.railway.internal
   WEAVIATE_GRPC_PORT=50051
   WEAVIATE_GRPC_SECURE=False
   ```

2. **No Railway:**
   - Configure rede privada entre serviços Verba e Weaviate
   - Use `.railway.internal` para comunicação interna

---

## 📊 Comparação com docker-compose.yml

### docker-compose.yml (Desenvolvimento Local)
```yaml
weaviate:
  image: semitechnologies/weaviate:1.34.0
  environment:
    ENABLE_MODULES: 'e'  # Módulo específico
    AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
    PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
```

### Dockerfile.weaviate (Produção Railway)
```dockerfile
ENV ENABLE_MODULES=""  # BYOV - sem módulos
ENV AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED="true"
ENV PERSISTENCE_DATA_PATH="/var/lib/weaviate"
```

**Diferenças:**
- ✅ **BYOV Mode**: Sem módulos externos (mais leve)
- ✅ **Otimizações**: Cache, compressão, timeouts
- ✅ **gRPC**: Habilitado explicitamente
- ✅ **Healthcheck**: Otimizado para Railway

---

## ⚙️ Configurações Detalhadas

### Performance
```dockerfile
ENV VECTOR_CACHE_MAINTENANCE_IN_MEMORY_PERCENTAGE="70"
ENV INDEXING_GO_MAX_PROCS="0"
ENV GZIP_ENABLED="true"
ENV GZIP_MIN_LENGTH="1024"
```

### Timeouts
```dockerfile
ENV REQUEST_TIMEOUT="60s"
ENV REQUEST_IDLE_TIMEOUT="60s"
```

### Logging
```dockerfile
ENV LOG_LEVEL="info"
ENV LOG_FORMAT="text"
```

---

## 🔍 Healthcheck

O healthcheck verifica se o Weaviate está pronto:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/v1/.well-known/ready || exit 1
```

**Railway usa este healthcheck para:**
- ✅ Detectar quando o serviço está pronto
- ✅ Reiniciar automaticamente se falhar
- ✅ Balanceamento de carga (se multi-instance)

---

## 🔐 Segurança

### Acesso Anônimo (Desenvolvimento)
```dockerfile
ENV AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED="true"
```

### Acesso com API Key (Produção)
Para produção, configure autenticação:

1. **No Railway, adicione variável de ambiente:**
   ```bash
   AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=false
   AUTHENTICATION_APIKEY_ENABLED=true
   AUTHENTICATION_APIKEY_ALLOWED_KEYS=your-api-key-here
   ```

2. **No Verba, configure:**
   ```bash
   WEAVIATE_API_KEY_VERBA=your-api-key-here
   ```

---

## 📈 Monitoramento

### Logs no Railway
```bash
# Ver logs do Weaviate
railway logs --service weaviate

# Filtrar por nível
railway logs --service weaviate | grep "ERROR"
```

### Métricas
- **Memória**: Verifique uso de cache (`VECTOR_CACHE_MAINTENANCE_IN_MEMORY_PERCENTAGE`)
- **CPU**: Verifique indexação paralela (`INDEXING_GO_MAX_PROCS`)
- **Rede**: Verifique compressão GZIP (`GZIP_ENABLED`)

---

## 🐛 Troubleshooting

### Problema: Weaviate não inicia
**Solução:**
- Verifique logs: `railway logs --service weaviate`
- Verifique se porta 8080 está disponível
- Verifique permissões do volume `/var/lib/weaviate`

### Problema: Conexão gRPC falha
**Solução:**
- Verifique se porta 50051 está exposta
- Use rede privada Railway (`.railway.internal`)
- Verifique variáveis `WEAVIATE_GRPC_HOST` e `WEAVIATE_GRPC_PORT`

### Problema: Performance lenta
**Solução:**
- Aumente `VECTOR_CACHE_MAINTENANCE_IN_MEMORY_PERCENTAGE` (se tiver RAM)
- Verifique se gRPC está sendo usado (mais rápido que HTTP)
- Verifique compressão GZIP (`GZIP_ENABLED=true`)

---

## 📚 Referências

- [Weaviate Documentation](https://weaviate.io/developers/weaviate)
- [Weaviate Docker Hub](https://hub.docker.com/r/semitechnologies/weaviate)
- [Railway Documentation](https://docs.railway.app/)
- [Verba Weaviate Integration](./REFATORACAO_WEAVIATE_V4.md)

---

**Última atualização:** Novembro 2025

