# 🔧 Patch: Método `connect_to_custom()` Completo

## 📍 Localização

**Arquivo**: `goldenverba/components/managers.py`
**Classe**: `WeaviateManager`
**Método**: `async def connect_to_custom(self, host, w_key, port)`
**Linhas**: ~230-450 (aproximado, varia por versão)

---

## 🎯 Mudanças Principais

Este método foi **completamente reescrito** para:

1. ✅ Detectar Railway domains automaticamente
2. ✅ Mapear portas corretamente (8080 interno vs 443 externo)
3. ✅ Suportar Weaviate API v3 via adapter
4. ✅ Fallback automático v4 → v3
5. ✅ Tratamento correto de HTTPS/HTTP

---

## 📝 Método Completo

⚠️ **IMPORTANTE**: Este é o método COMPLETO. Ao atualizar Verba, você precisa:

1. **Encontrar o método `connect_to_custom()` na nova versão**
2. **Substituir pelo nosso código completo abaixo**
3. **OU fazer merge manual se Verba adicionou melhorias**

```python
async def connect_to_custom(self, host, w_key, port):
    msg.info(f"Connecting to Weaviate Custom")

    if host is None or host == "":
        raise Exception("No Host URL provided")

    from urllib.parse import urlparse
    is_full_url = "://" in host
    
    if is_full_url:
        parsed_host = urlparse(host)
        actual_host = parsed_host.hostname or parsed_host.netloc.split(':')[0]
        scheme = parsed_host.scheme or "http"
        url_port = parsed_host.port
        
        if url_port:
            port_int = url_port
        elif port:
            port_int = int(port)
        elif scheme == "https":
            port_int = 443
        else:
            port_int = 8080
            
        if scheme == "https" or port_int == 443:
            url = f"https://{actual_host}"
            if port_int != 443:
                url = f"{url}:{port_int}"
            use_https = True
        else:
            url = f"http://{actual_host}"
            if port_int != 80:
                url = f"{url}:{port_int}"
            use_https = False
    else:
        actual_host = host
        port_int = int(port) if port else 8080
        
        if actual_host.startswith("http://"):
            actual_host = actual_host.replace("http://", "")
            use_https = False
            if not port:
                port_int = 80 if port_int == 8080 else port_int
        elif actual_host.startswith("https://"):
            actual_host = actual_host.replace("https://", "")
            use_https = True
            if not port or port_int == 8080:
                port_int = 443
        else:
            if port_int == 443:
                use_https = True
            elif port_int == 80:
                use_https = False
            elif ".railway.internal" in actual_host.lower():
                use_https = False
                if port_int == 443 or not port_int:
                    port_int = 8080
                msg.info("Rede interna Railway detectada - usando HTTP porta 8080")
            elif ".railway.app" in actual_host.lower() and port_int == 8080:
                use_https = True
                port_int = 443
                msg.info("Railway porta 8080 detectado - usando HTTPS porta 443 (porta 8080 é interna)")
            elif ".railway.app" in actual_host.lower():
                use_https = True
                if port_int != 443:
                    port_int = 443
            else:
                use_https = False
        
        if 'url' not in locals():
            if use_https:
                url = f"https://{actual_host}" if port_int == 443 else f"https://{actual_host}:{port_int}"
            else:
                url = f"http://{actual_host}" if port_int == 80 else f"http://{actual_host}:{port_int}"

    msg.info(f"URL Weaviate: {url} (port: {port_int}, HTTPS: {use_https})")
    
    if use_https:
        msg.info("Usando conexao HTTPS externa")
        try:
            if w_key is None or w_key == "":
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
                    
                    try:
                        from verba_extensions.compatibility.weaviate_v3_adapter import WeaviateV3HTTPAdapter
                        adapter = WeaviateV3HTTPAdapter(url, None)
                        if await adapter.is_ready():
                            msg.good("Conexao HTTPS estabelecida via adapter v3")
                            return adapter
                    except ImportError:
                        msg.warn("Adapter v3 nao disponivel - usando metodo alternativo")
                    except Exception as e_adapter:
                        msg.warn(f"Adapter v3 falhou: {str(e_adapter)[:100]}")
                    
                    raise e_local
            else:
                client = weaviate.use_async_with_local(
                    host=actual_host,
                    port=port_int,
                    skip_init_checks=True,
                    auth_credentials=AuthApiKey(w_key),
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=60, query=300, insert=300)
                    ),
                )
                await client.connect()
                if await client.is_ready():
                    msg.good("Conexao HTTPS com auth estabelecida")
                    return client
                await client.close()
                raise Exception("Cliente conectado mas nao esta pronto")
        except Exception as e:
            error_str = str(e).lower()
            msg.warn(f"Tentativa HTTPS falhou: {str(e)[:150]}")
            
            if any(x in error_str for x in ['api', 'version', 'schema', '400', 'meta endpoint']):
                try:
                    from verba_extensions.compatibility.weaviate_v3_adapter import WeaviateV3HTTPAdapter
                    msg.info("Tentando adapter v3 HTTP como fallback...")
                    adapter = WeaviateV3HTTPAdapter(url, w_key if w_key else None)
                    if await adapter.is_ready():
                        msg.good("Conexao estabelecida via adapter v3 HTTP")
                        return adapter
                except ImportError:
                    pass
                except Exception as e_adapter:
                    msg.warn(f"Adapter v3 falhou: {str(e_adapter)[:100]}")
            
            raise
    else:
        try:
            if w_key is None or w_key == "":
                return weaviate.use_async_with_local(
                    host=actual_host,
                    port=port_int,
                    skip_init_checks=True,
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=60, query=300, insert=300)
                    ),
                )
            else:
                return weaviate.use_async_with_local(
                    host=actual_host,
                    port=port_int,
                    skip_init_checks=True,
                    auth_credentials=AuthApiKey(w_key),
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=60, query=300, insert=300)
                    ),
                )
        except Exception as e:
            error_str = str(e).lower()
            
            if any(x in error_str for x in ['api', 'version', 'schema', 'client', 'attribute', 'connection']):
                msg.warn(f"Conexao v4 falhou (possivel incompatibilidade): {str(e)}")
                msg.info("Tentando conexao via API REST direta para v3...")
                
                try:
                    from verba_extensions.compatibility.weaviate_v3_adapter import WeaviateV3HTTPAdapter
                    adapter = WeaviateV3HTTPAdapter(url, w_key if w_key else None)
                    
                    if await adapter.is_ready():
                        msg.good("Conexao v3 estabelecida via API REST direta")
                        return adapter
                    else:
                        raise Exception("Weaviate v3 nao esta pronto")
                except Exception as e2:
                    msg.fail(f"Tentativa v3 tambem falhou: {str(e2)}")
                    raise e
            else:
                raise
```

---

## 🔍 Como Aplicar em Update

1. **Localizar método na nova versão**:
   ```bash
   grep -n "async def connect_to_custom" goldenverba/components/managers.py
   ```

2. **Verificar se Verba mudou o método**:
   ```bash
   diff goldenverba_backup/components/managers.py goldenverba/components/managers.py | grep -A 50 "connect_to_custom"
   ```

3. **Se método não mudou**: Substituir completamente

4. **Se método mudou**: Fazer merge manual, mantendo:
   - Nossa lógica de Railway
   - Nossa lógica de v3 adapter
   - Melhorias do Verba (se houver)

---

## ⚠️ Imports Necessários

Certifique-se de que estes imports existem no início do arquivo:

```python
from weaviate.classes.init import AdditionalConfig, Timeout
from weaviate.auth import AuthApiKey
```

E que `verba_extensions.compatibility.weaviate_v3_adapter` está disponível.

---

**Método completo documentado para replicação em updates!** 🔧

