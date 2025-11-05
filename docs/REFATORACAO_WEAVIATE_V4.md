# Refatoração Weaviate v4 - Implementação Concluída

## Resumo

Refatoração do Verba seguindo o **Manual Definitivo de Refatoração do Verba: Migrando para o Cliente Weaviate v4 com Foco em Desempenho e Implantação**.

## Mudanças Implementadas

### 1. Conexão Weaviate - Suporte a PaaS (Railway)

**Prioridade de Conexão Implementada:**

1. **PRIORIDADE 1: Configuração PaaS Explícita**
   - Detecta variáveis de ambiente: `WEAVIATE_HTTP_HOST`, `WEAVIATE_GRPC_HOST`
   - Usa `connect_to_custom` com portas HTTP e gRPC separadas
   - Permite usar rede privada Railway (`.railway.internal`)
   - Suporta gRPC para melhor performance

2. **PRIORIDADE 2: Weaviate Cloud (WCS)**
   - Mantém suporte para `use_async_with_weaviate_cloud`
   - Usa API key para autenticação

3. **PRIORIDADE 3: Fallback URL-based**
   - Mantém compatibilidade com URL única
   - Usa `use_async_with_local` como fallback

### 2. Variáveis de Ambiente Suportadas

**Para Deploy Railway (Rede Privada):**

```bash
# Conexão HTTP (REST)
WEAVIATE_HTTP_HOST="weaviate.railway.internal"
WEAVIATE_HTTP_PORT="8080"
WEAVIATE_HTTP_SECURE="False"

# Conexão gRPC (Alta Performance)
WEAVIATE_GRPC_HOST="weaviate.railway.internal"
WEAVIATE_GRPC_PORT="50051"
WEAVIATE_GRPC_SECURE="False"

# Autenticação (opcional)
WEAVIATE_API_KEY_VERBA="sua-chave-api"
```

**Para Weaviate Cloud (WCS):**

```bash
WEAVIATE_URL_VERBA="my-cluster.weaviate.network"
WEAVIATE_API_KEY_VERBA="sua-chave-api"
```

**Para Deploy Custom (URL-based):**

```bash
WEAVIATE_URL_VERBA="https://weaviate.example.com"
WEAVIATE_API_KEY_VERBA="sua-chave-api"  # Opcional
```

### 3. Mudanças na API

**Antes (v3-style fallback):**
```python
client = weaviate.use_async_with_local(
    host=host,
    port=port,
    skip_init_checks=True
)
```

**Depois (v4 com PaaS):**
```python
# Prioriza configuração PaaS explícita
if WEAVIATE_HTTP_HOST and WEAVIATE_GRPC_HOST:
    client = weaviate.connect_to_custom(
        http_host=http_host,
        http_port=8080,
        http_secure=False,
        grpc_host=grpc_host,
        grpc_port=50051,
        grpc_secure=False,
        auth_credentials=Auth.api_key(api_key) if api_key else None
    )
```

### 4. Benefícios da Refatoração

✅ **Suporte a gRPC**: Conexão gRPC permite 40-80% de melhoria em performance

✅ **Rede Privada Railway**: Usa `.railway.internal` para acessar ambas as portas (8080 e 50051)

✅ **Configuração Explícita**: Variáveis de ambiente claras para PaaS

✅ **Backward Compatible**: Mantém compatibilidade com configurações antigas (URL-based)

✅ **Autenticação Moderna**: Usa `Auth.api_key()` conforme manual v4

## Como Usar

### Deploy Railway (Recomendado)

1. **Configure o serviço Weaviate:**
   - Certifique-se de que está escutando em `[::]:8080` (HTTP) e `[::]:50051` (gRPC)
   - Verifique logs: `"grpc server listening at [::]:50051"`

2. **Configure o serviço Verba:**
   - Adicione as variáveis de ambiente PaaS (veja acima)
   - Use `.railway.internal` para rede privada

3. **Teste a conexão:**
   ```python
   # O código detectará automaticamente a configuração PaaS
   # e usará connect_to_custom com portas separadas
   ```

### Deploy Weaviate Cloud

1. Configure:
   ```bash
   WEAVIATE_URL_VERBA="my-cluster.weaviate.network"
   WEAVIATE_API_KEY_VERBA="sua-chave"
   ```

2. O código usará `use_async_with_weaviate_cloud` automaticamente

### Deploy Custom (URL-based)

1. Configure:
   ```bash
   WEAVIATE_URL_VERBA="https://weaviate.example.com"
   ```

2. O código usará `use_async_with_local` como fallback

## Arquivos Modificados

- `goldenverba/components/managers.py`:
  - `connect_to_cluster()`: Prioriza configuração PaaS explícita
  - Usa `connect_to_custom` para PaaS
  - Usa `Auth.api_key()` conforme manual v4

## Próximos Passos

1. ✅ Conexão refatorada - **CONCLUÍDO**
2. ⏳ Testar conexão Railway com rede privada
3. ⏳ Verificar performance com gRPC
4. ⏳ Documentar configuração Railway no README

## Referências

- Manual: "O Manual Definitivo de Refatoração do Verba: Migrando para o Cliente Weaviate v4"
- Weaviate v4 Docs: https://weaviate.io/developers/weaviate/client-libraries/python
- Railway Docs: https://docs.railway.app

