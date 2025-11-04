# Patches para Weaviate v4 - Documentação para Updates

Este documento descreve todas as mudanças feitas no código do Verba para suportar Weaviate v4, especialmente para deployments em Railway (PaaS). Use este documento para aplicar patches após atualizações do Verba padrão.

## Arquivos Modificados

### 1. `goldenverba/components/managers.py`

Este é o arquivo principal que precisa de patches. Contém as mudanças na lógica de conexão Weaviate.

---

## MUDANÇA 1: Priorização de Configuração PaaS Explícita

**Localização:** `async def connect_to_cluster(self, w_url, w_key)`

**Contexto:** Para deployments em Railway (e outros PaaS), precisamos de portas HTTP e gRPC separadas. O código padrão do Verba não suporta isso adequadamente.

**Código Original (assumido):**
```python
async def connect_to_cluster(self, w_url, w_key):
    if w_url is None or w_url == "":
        raise Exception("No URL provided")
    
    # Conecta diretamente via URL
    return weaviate.use_async_with_weaviate_cloud(...)
    # ou
    return weaviate.use_async_with_local(...)
```

**Código Modificado (adicionar no início da função, antes de qualquer outra lógica):**
```python
async def connect_to_cluster(self, w_url, w_key):
    if w_url is None or w_url == "":
        raise Exception("No URL provided")
    
    # ===== PATCH 1: PRIORIDADE 1 - Configuração PaaS Explícita =====
    # Verificar se há configuração PaaS explícita (Railway, etc.)
    # Isso permite usar rede privada e portas HTTP/gRPC separadas
    http_host = os.getenv("WEAVIATE_HTTP_HOST")
    grpc_host = os.getenv("WEAVIATE_GRPC_HOST")
    
    if http_host and grpc_host:
        # Configuração PaaS explícita - usar connect_to_custom com portas separadas
        msg.info(f"Connecting to Weaviate via PaaS configuration (Railway/Private Network)")
        msg.info(f"  HTTP Host: {http_host}")
        msg.info(f"  gRPC Host: {grpc_host}")
        
        http_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
        grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
        
        http_secure = os.getenv("WEAVIATE_HTTP_SECURE", "False").lower() == "true"
        grpc_secure = os.getenv("WEAVIATE_GRPC_SECURE", "False").lower() == "true"
        
        # Usar API key se disponível
        api_key = w_key or os.getenv("WEAVIATE_API_KEY_VERBA")
        auth_creds = AuthApiKey(api_key) if api_key else None
        
        try:
            # Usar connect_to_custom para PaaS (permite portas HTTP e gRPC separadas)
            client = weaviate.connect_to_custom(
                http_host=http_host,
                http_port=http_port,
                http_secure=http_secure,
                grpc_host=grpc_host,
                grpc_port=grpc_port,
                grpc_secure=grpc_secure,
                auth_credentials=auth_creds,
                skip_init_checks=False,
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=60, query=300, insert=300)
                )
            )
            return client
        except Exception as e:
            msg.warn(f"PaaS connection failed: {str(e)[:200]}")
            msg.info("Falling back to URL-based connection...")
            # Continua para tentar método baseado em URL
    # ===== FIM PATCH 1 =====
    
    # Resto do código original...
```

**Imports necessários (adicionar no topo do arquivo se não existirem):**
```python
from weaviate.auth import AuthApiKey
from weaviate.classes.init import AdditionalConfig, Timeout
```

---

## MUDANÇA 2: Suporte a HTTPS com connect_to_custom

**Localização:** Dentro de `async def connect_to_custom(self, host, w_key, port)`

**Contexto:** Para conexões HTTPS externas (Railway), `connect_to_custom` é mais confiável que `use_async_with_local`.

**Buscar no código:**
```python
if w_key is None or w_key == "":
    # Tenta conexão via URL completa sem auth
    # Para Railway, use_async_with_local pode funcionar...
    client = weaviate.use_async_with_local(...)
```

**Substituir por:**
```python
if w_key is None or w_key == "":
    # Tenta conexão via URL completa sem auth
    # Para Railway HTTPS, tenta connect_to_custom primeiro (mais confiável)
    try:
        client = weaviate.connect_to_custom(
            http_host=actual_host,
            http_port=port_int,
            http_secure=True,
            grpc_host=actual_host,
            grpc_port=50051,
            grpc_secure=True,
            skip_init_checks=False,
            additional_config=AdditionalConfig(
                timeout=Timeout(init=60, query=300, insert=300)
            ),
        )
        await client.connect()
        if await client.is_ready():
            msg.good("Conexao HTTPS estabelecida via connect_to_custom")
            return client
        await client.close()
    except Exception as e_custom:
        msg.warn(f"connect_to_custom falhou: {str(e_custom)[:100]}")
        
        # Fallback: use_async_with_local
        try:
            client = weaviate.use_async_with_local(
                host=actual_host,
                port=port_int,
                skip_init_checks=True,
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=60, query=300, insert=300)
                ),
            )
            await client.connect()
            if await client.is_ready():
                msg.good("Conexao HTTPS estabelecida via use_async_with_local")
                return client
            await client.close()
        except Exception as e_local:
            msg.warn(f"use_async_with_local falhou: {str(e_local)[:100]}")
            raise e_custom  # Re-raise erro do connect_to_custom
```

---

## MUDANÇA 3: Remoção de WeaviateV3HTTPAdapter

**Localização:** Remover todas as referências a `WeaviateV3HTTPAdapter`

**Contexto:** O adapter v3 não é compatível com a interface do cliente v4 e causa erros (`'WeaviateV3HTTPAdapter' object has no attribute 'connect'`).

**Buscar e remover:**
```python
from verba_extensions.compatibility.weaviate_v3_adapter import WeaviateV3HTTPAdapter
adapter = WeaviateV3HTTPAdapter(url, None)
if await adapter.is_ready():
    return adapter
```

**Substituir por:** Nada (remover completamente essas tentativas de fallback)

**Nota:** Se o código original tiver tentativas de usar o adapter v3, substitua por tentativas de `connect_to_custom` ou `use_async_with_local`.

---

## MUDANÇA 4: Verificação de connect() antes de chamar

**Localização:** `async def connect(self, deployment, weaviateURL, weaviateAPIKey, port)`

**Contexto:** Clientes v4 podem não ter `connect()` explícito ou já estar conectados.

**Buscar:**
```python
if client is not None:
    await client.connect()
    if await client.is_ready():
        msg.good("Succesfully Connected to Weaviate")
        return client
```

**Substituir por:**
```python
if client is not None:
    # Clientes v4 já estão conectados após connect_to_*, mas verificamos ready
    # Se cliente não tem connect(), já está conectado (comportamento v4)
    try:
        if hasattr(client, 'connect'):
            await client.connect()
    except AttributeError:
        # Cliente já está conectado (comportamento padrão v4)
        pass
    
    if await client.is_ready():
        msg.good("Succesfully Connected to Weaviate")
        return client
```

---

## MUDANÇA 5: Fallback HTTPS para Railway porta 8080

**Localização:** Dentro de `async def connect_to_custom(self, host, w_key, port)`, seção de erro HTTP

**Buscar:**
```python
# Para Railway porta 8080, se HTTP falhou, tenta HTTPS como fallback
if is_railway_8080 and not use_https:
    # ... código usando WeaviateV3HTTPAdapter
```

**Substituir por:**
```python
# Para Railway porta 8080, se HTTP falhou, tenta HTTPS como fallback
if is_railway_8080 and not use_https:
    msg.warn(f"Conexao HTTP falhou: {str(e)[:100]}")
    msg.info("Tentando HTTPS como fallback para Railway porta 8080...")
    try:
        # Tenta connect_to_custom com HTTPS
        client = weaviate.connect_to_custom(
            http_host=actual_host,
            http_port=443,
            http_secure=True,
            grpc_host=actual_host,
            grpc_port=50051,
            grpc_secure=True,
            skip_init_checks=False,
            additional_config=AdditionalConfig(
                timeout=Timeout(init=60, query=300, insert=300)
            ),
        )
        await client.connect()
        if await client.is_ready():
            msg.good("Conexao HTTPS estabelecida como fallback")
            return client
        await client.close()
    except Exception as e_https:
        msg.warn(f"Tentativa HTTPS fallback falhou: {str(e_https)[:100]}")
```

---

## Checklist para Aplicar Patches Após Update

1. **Verificar versão do weaviate-client:**
   ```bash
   pip show weaviate-client
   ```
   Deve ser `>=4.0.0`

2. **Backup do arquivo original:**
   ```bash
   cp goldenverba/components/managers.py goldenverba/components/managers.py.backup
   ```

3. **Aplicar patches na ordem:**
   - [ ] PATCH 1: Priorização de configuração PaaS
   - [ ] PATCH 2: Suporte HTTPS com connect_to_custom
   - [ ] PATCH 3: Remover WeaviateV3HTTPAdapter
   - [ ] PATCH 4: Verificação de connect()
   - [ ] PATCH 5: Fallback HTTPS para Railway

4. **Verificar imports:**
   ```python
   from weaviate.auth import AuthApiKey
   from weaviate.classes.init import AdditionalConfig, Timeout
   ```

5. **Testar conexão:**
   - Testar com variáveis de ambiente PaaS
   - Testar com URL direta
   - Verificar logs para erros

---

## Variáveis de Ambiente Necessárias (PaaS)

Para usar a configuração PaaS explícita, configure:

```bash
WEAVIATE_HTTP_HOST=weaviate-production-0d0e.up.railway.app
WEAVIATE_GRPC_HOST=weaviate-production-0d0e.up.railway.app
WEAVIATE_HTTP_PORT=8080
WEAVIATE_GRPC_PORT=50051
WEAVIATE_HTTP_SECURE=False  # Para rede privada
WEAVIATE_GRPC_SECURE=False  # Para rede privada
WEAVIATE_API_KEY_VERBA=your_api_key  # Opcional
```

**Nota:** Para Railway com rede privada (`.railway.internal`), use HTTP na porta 8080. Para acesso externo, use HTTPS na porta 443.

---

## Diferenças Principais vs Verba Padrão

1. **Suporte a PaaS explícito:** Verba padrão não prioriza configuração PaaS com portas separadas
2. **Priorização de connect_to_custom:** Usa método mais confiável para HTTPS
3. **Remoção de adapter v3:** Não tenta usar adapter incompatível
4. **Verificação de connect():** Trata clientes v4 que podem já estar conectados

---

## Troubleshooting

### Erro: `'WeaviateV3HTTPAdapter' object has no attribute 'connect'`
**Solução:** Remover todas as referências a `WeaviateV3HTTPAdapter` (PATCH 3)

### Erro: `Meta endpoint! Unexpected status code: 400`
**Solução:** Verificar se está usando `connect_to_custom` com parâmetros corretos (PATCH 2)

### Erro: `gRPC health check could not be completed`
**Solução:** Verificar variáveis de ambiente `WEAVIATE_GRPC_HOST` e `WEAVIATE_GRPC_PORT` (PATCH 1)

### Conexão funciona mas é lenta
**Solução:** Usar configuração PaaS explícita com gRPC habilitado (PATCH 1)

---

## Referências

- [Weaviate Python Client v4 Docs](https://weaviate.io/developers/weaviate/client-libraries/python)
- [Weaviate v4 Migration Guide](https://weaviate.io/developers/weaviate/client-libraries/python#migrating-from-v3-to-v4)
- [Railway Private Networking](https://docs.railway.app/guides/private-networking)

---

**Última atualização:** 2025-11-04
**Verba Base Version:** (verificar após cada update)
**weaviate-client Version:** 4.17.0

