# Changelog: Dockerfile.weaviate para Railway

**Data:** Novembro 2025  
**Status:** ✅ Implementado

---

## 📋 Resumo

Criação do `Dockerfile.weaviate` otimizado para deploy no Railway, permitindo que o Weaviate seja construído a partir do próprio repositório Verba ao invés de usar um Dockerfile de outro repositório.

---

## 🎯 Objetivo

Centralizar a configuração do Weaviate no repositório Verba, facilitando:
- ✅ Manutenção e versionamento
- ✅ Deploy no Railway
- ✅ Configurações otimizadas para Verba
- ✅ Documentação integrada

---

## ✨ Melhorias Implementadas

### 1. Versão Alinhada
- ✅ **Weaviate 1.34.0** (mesma versão do `docker-compose.yml`)
- ✅ Compatível com weaviate-client v4 usado pelo Verba

### 2. BYOV Mode Otimizado
- ✅ **ENABLE_MODULES=""**: Sem módulos externos (BYOV puro)
- ✅ **DEFAULT_VECTORIZER_MODULE="none"**: Verba fornece seus próprios vetores
- ✅ **BM25 nativo**: Usa BM25 nativo do Weaviate (não precisa de módulos)

### 3. Performance
- ✅ **Cache de vetores**: 70% da RAM (`VECTOR_CACHE_MAINTENANCE_IN_MEMORY_PERCENTAGE="70"`)
- ✅ **Indexação paralela**: Todos os CPUs (`INDEXING_GO_MAX_PROCS="0"`)
- ✅ **Compressão GZIP**: Reduz tráfego de rede
- ✅ **Timeouts otimizados**: 60s para requests

### 4. gRPC Habilitado
- ✅ **Porta 50051**: gRPC para melhor performance
- ✅ **Suporte Railway**: Configurado para rede privada Railway
- ✅ **Comando explícito**: `--grpc-port 50051` no CMD

### 5. Healthcheck Otimizado
- ✅ **Interval**: 30s (Railway-friendly)
- ✅ **Start period**: 40s (tempo para inicialização)
- ✅ **Retries**: 3 (balance entre detecção e estabilidade)

### 6. Configurações de Produção
- ✅ **Logging**: INFO level, formato text
- ✅ **Query limits**: 25 padrão, 10000 máximo
- ✅ **Cluster**: Single node (Railway)
- ✅ **Persistência**: Volume em `/var/lib/weaviate`

---

## 📊 Comparação: Original vs. Otimizado

### Original (Fornecido pelo Usuário)
```dockerfile
FROM cr.weaviate.io/semitechnologies/weaviate:1.34.0
ENV ENABLE_MODULES=""
ENV DEFAULT_VECTORIZER_MODULE="none"
ENV AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED="true"
ENV PERSISTENCE_DATA_PATH="/var/lib/weaviate"
ENV QUERY_DEFAULTS_LIMIT="25"
ENV CLUSTER_HOSTNAME="weaviate-node"
ENV LOG_LEVEL="info"
ENV VECTOR_CACHE_MAINTENANCE_IN_MEMORY_PERCENTAGE="70"
ENV INDEXING_GO_MAX_PROCS="0"
ENV GZIP_ENABLED="true"
ENV GZIP_MIN_LENGTH="1024"
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/v1/.well-known/ready || exit 1
EXPOSE 8080
EXPOSE 50051
CMD ["/bin/weaviate", "--host", "0.0.0.0", "--port", "8080", "--scheme", "http"]
```

### Otimizado (Implementado)
```dockerfile
# Adicionado:
- Labels (maintainer, description, version)
- Timeouts (REQUEST_TIMEOUT, REQUEST_IDLE_TIMEOUT)
- Logging format (LOG_FORMAT="text")
- Query maximum results (QUERY_MAXIMUM_RESULTS="10000")
- Cluster ports (7100, 7101) para multi-node futuro
- Volume declaration
- gRPC port explícito no CMD
- Start period aumentado para 40s (Railway)
- Setup de diretórios (/var/log/weaviate)
```

---

## 🔧 Configurações Adicionais

### Timeouts
```dockerfile
ENV REQUEST_TIMEOUT="60s"
ENV REQUEST_IDLE_TIMEOUT="60s"
```

### Query Limits
```dockerfile
ENV QUERY_DEFAULTS_LIMIT="25"
ENV QUERY_MAXIMUM_RESULTS="10000"
```

### Cluster (Single Node)
```dockerfile
ENV CLUSTER_HOSTNAME="weaviate-node"
ENV CLUSTER_GOSSIP_BIND_PORT="7100"
ENV CLUSTER_DATA_BIND_PORT="7101"
```

### Logging
```dockerfile
ENV LOG_LEVEL="info"
ENV LOG_FORMAT="text"
```

---

## 📁 Arquivos Criados

1. **Dockerfile.weaviate**
   - Dockerfile principal otimizado
   - Localização: Raiz do projeto

2. **docs/guides/DOCKERFILE_WEAVIATE_RAILWAY.md**
   - Guia completo de uso
   - Instruções para Railway
   - Troubleshooting
   - Comparação com docker-compose.yml

---

## 🚀 Como Usar

### No Railway

1. **Configure o serviço Weaviate:**
   - Source: Este repositório
   - Dockerfile Path: `Dockerfile.weaviate`
   - Build Command: (vazio, Railway detecta automaticamente)

2. **Variáveis de Ambiente (opcionais):**
   - Já configuradas no Dockerfile
   - Podem ser sobrescritas no Railway se necessário

3. **Portas:**
   - 8080: HTTP/REST API
   - 50051: gRPC API

4. **Volumes:**
   - Railway cria automaticamente em `/var/lib/weaviate`

---

## ✅ Validação

### Testes Recomendados

1. **Build local:**
   ```bash
   docker build -f Dockerfile.weaviate -t weaviate-verba:test .
   ```

2. **Run local:**
   ```bash
   docker run -p 8080:8080 -p 50051:50051 weaviate-verba:test
   ```

3. **Healthcheck:**
   ```bash
   curl http://localhost:8080/v1/.well-known/ready
   ```

4. **Conexão Verba:**
   - Configure Verba para conectar ao Weaviate
   - Teste import e busca

---

## 📚 Documentação

- ✅ `Dockerfile.weaviate` - Dockerfile principal
- ✅ `docs/guides/DOCKERFILE_WEAVIATE_RAILWAY.md` - Guia completo
- ✅ Comentários inline no Dockerfile

---

## 🎯 Benefícios

### Para Desenvolvedores
- ✅ **Centralizado**: Tudo no mesmo repositório
- ✅ **Versionado**: Git controla mudanças
- ✅ **Documentado**: Guia completo incluído

### Para Deploy
- ✅ **Railway-ready**: Otimizado para Railway
- ✅ **Performance**: Configurações otimizadas
- ✅ **Monitoramento**: Healthcheck e logging

### Para Manutenção
- ✅ **Alinhado**: Mesma versão do docker-compose.yml
- ✅ **Consistente**: Configurações padronizadas
- ✅ **Flexível**: Variáveis podem ser sobrescritas

---

## 🔄 Próximos Passos (Opcional)

1. **Testar no Railway**: Deploy e validação
2. **Monitorar performance**: Ajustar cache se necessário
3. **Adicionar autenticação**: Para produção
4. **Multi-node**: Se necessário escalar

---

**Commit:** `9a95d51` - Adicionar Dockerfile.weaviate otimizado para Railway  
**Status:** ✅ Pronto para uso

