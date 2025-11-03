"""
Teste EXATO usando configurações do Railway
Domain: weaviate-production-0d0e.up.railway.app
Port: 8080 (HTTP)
"""

import asyncio
from wasabi import msg

# Configurações exatas do Railway
HOST = "weaviate-production-0d0e.up.railway.app"
PORT = "8080"
API_KEY = ""  # Sem API key conforme configuração

async def test_exact_railway_settings():
    """Testa conexão usando EXATAMENTE as configurações do Railway"""
    msg.info("=" * 60)
    msg.info("TESTE: Configuracoes Exatas Railway")
    msg.info("=" * 60)
    msg.info(f"Host: {HOST}")
    msg.info(f"Port: {PORT}")
    msg.info(f"API Key: {'(vazio)' if not API_KEY else '(fornecida)'}")
    msg.info("")
    
    try:
        # Simula EXATAMENTE o que connect_to_custom faz
        from urllib.parse import urlparse
        import weaviate
        from weaviate.classes.init import AdditionalConfig, Timeout
        
        actual_host = HOST
        port_int = int(PORT)
        
        # Detecta Railway porta 8080
        is_railway_8080 = ".railway.app" in actual_host.lower() and port_int == 8080
        
        if is_railway_8080:
            use_https = False
            url = f"http://{actual_host}:{port_int}"
            msg.info("Railway porta 8080 detectado - tentando HTTP primeiro")
        else:
            use_https = False
            url = f"http://{actual_host}:{port_int}"
        
        msg.info(f"URL Weaviate: {url} (port: {port_int}, HTTPS: {use_https})")
        msg.info("")
        
        # Tenta conexão HTTP (como o código faz)
        msg.info("Tentando conexao HTTP via use_async_with_local...")
        try:
            if not API_KEY:
                client = weaviate.use_async_with_local(
                    host=actual_host,
                    port=port_int,
                    skip_init_checks=True,
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=60, query=300, insert=300)
                    ),
                )
            else:
                from weaviate.auth import AuthApiKey
                client = weaviate.use_async_with_local(
                    host=actual_host,
                    port=port_int,
                    skip_init_checks=True,
                    auth_credentials=AuthApiKey(API_KEY),
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=60, query=300, insert=300)
                    ),
                )
            
            msg.info("Cliente criado, tentando conectar...")
            await client.connect()
            
            if await client.is_ready():
                msg.good("OK: Conexao HTTP estabelecida!")
                
                # Testa listar coleções
                try:
                    collections = await client.collections.list_all()
                    msg.good(f"OK: {len(collections)} colecoes encontradas")
                    for col in collections[:5]:
                        msg.info(f"  - {col}")
                except Exception as e:
                    msg.warn(f"Aviso ao listar colecoes: {str(e)[:200]}")
                
                await client.close()
                return True
            else:
                msg.fail("Cliente conectado mas nao esta pronto")
                await client.close()
                return False
                
        except Exception as e:
            error_str = str(e)
            msg.fail(f"Erro na conexao HTTP: {str(e)}")
            msg.info("")
            
            # Se falhar, tenta HTTPS como fallback (como o código faz)
            if is_railway_8080:
                msg.info("Tentando HTTPS como fallback para Railway porta 8080...")
                try:
                    https_url = f"https://{actual_host}"
                    from verba_extensions.compatibility.weaviate_v3_adapter import WeaviateV3HTTPAdapter
                    adapter = WeaviateV3HTTPAdapter(https_url, API_KEY if API_KEY else None)
                    
                    if await adapter.is_ready():
                        msg.good("OK: Conexao HTTPS estabelecida como fallback!")
                        
                        # Testa listar classes (v3 API)
                        try:
                            classes = await adapter.get_schema()
                            msg.good(f"OK: {len(classes.get('classes', []))} classes encontradas")
                        except:
                            pass
                        
                        return True
                    else:
                        msg.fail("Adapter HTTP nao esta pronto")
                        return False
                except Exception as e_https:
                    msg.fail(f"Tentativa HTTPS fallback falhou: {str(e_https)[:200]}")
            
            # Tenta adapter v3 como último recurso
            msg.info("Tentando adapter v3 HTTP direto...")
            try:
                from verba_extensions.compatibility.weaviate_v3_adapter import WeaviateV3HTTPAdapter
                adapter = WeaviateV3HTTPAdapter(url, API_KEY if API_KEY else None)
                
                if await adapter.is_ready():
                    msg.good("OK: Conexao via adapter v3 estabelecida!")
                    return True
                else:
                    msg.fail("Adapter v3 nao esta pronto")
                    return False
            except Exception as e2:
                msg.fail(f"Tentativa adapter v3 falhou: {str(e2)[:200]}")
            
            return False
            
    except ImportError as e:
        msg.fail(f"Biblioteca nao disponivel: {str(e)}")
        return False
    except Exception as e:
        msg.fail(f"Erro geral: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_direct_http():
    """Teste direto via HTTP usando httpx"""
    msg.info("")
    msg.info("=" * 60)
    msg.info("TESTE: HTTP/HTTPS Direto (httpx)")
    msg.info("=" * 60)
    
    try:
        import httpx
        
        # Tenta HTTPS primeiro (Railway geralmente expõe via HTTPS)
        urls_to_try = [
            f"https://{HOST}",  # HTTPS sem porta (padrão Railway)
            f"https://{HOST}:443",  # HTTPS porta 443
            f"http://{HOST}:{PORT}",  # HTTP porta 8080 (como configurado)
            f"http://{HOST}",  # HTTP sem porta
        ]
        
        for url in urls_to_try:
            msg.info(f"\nTestando: {url}")
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    # Testa /ready
                    msg.info("Testando /v1/.well-known/ready...")
                    r1 = await client.get(f"{url}/v1/.well-known/ready", timeout=10.0)
                    msg.info(f"Status: {r1.status_code}")
                    
                    if r1.status_code == 200:
                        msg.good(f"OK: Weaviate acessivel em {url}!")
                        
                        # Testa /meta
                        msg.info("\nTestando /v1/meta...")
                        r2 = await client.get(f"{url}/v1/meta", timeout=10.0)
                        if r2.status_code == 200:
                            data = r2.json()
                            msg.good(f"OK: Version {data.get('version', 'N/A')}")
                        
                        # Testa /schema
                        msg.info("\nTestando /v1/schema...")
                        r3 = await client.get(f"{url}/v1/schema", timeout=10.0)
                        if r3.status_code == 200:
                            schema = r3.json()
                            classes = schema.get('classes', [])
                            msg.good(f"OK: {len(classes)} classes encontradas")
                        
                        msg.info(f"\nURL FUNCIONAL: {url}")
                        return url  # Retorna URL que funcionou
                    else:
                        msg.warn(f"Status {r1.status_code}")
            except httpx.ConnectTimeout:
                msg.warn(f"Timeout ao conectar em {url}")
                continue
            except httpx.ConnectError as e:
                msg.warn(f"Erro de conexao: {str(e)[:100]}")
                continue
            except Exception as e:
                msg.warn(f"Erro: {str(e)[:100]}")
                continue
        
        msg.fail("Nenhuma URL funcionou")
        return None
                
    except Exception as e:
        msg.fail(f"Erro geral: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    except Exception as e:
        msg.fail(f"Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    msg.info("")
    msg.info("=" * 60)
    msg.info("TESTE COM CONFIGURACOES EXATAS DO RAILWAY")
    msg.info("=" * 60)
    msg.info("")
    msg.info("Configuracoes:")
    msg.info(f"  Host: {HOST}")
    msg.info(f"  Port: {PORT}")
    msg.info(f"  API Key: {'(vazio)' if not API_KEY else '(fornecida)'}")
    msg.info("")
    
    result1 = asyncio.run(test_direct_http())
    
    # Se encontrou URL funcional, testa com essa URL
    if result1:
        msg.info(f"\nURL que funciona: {result1}")
        msg.info("Testando metodo Verba com URL funcional...")
        
        # Extrai informações da URL
        from urllib.parse import urlparse
        parsed = urlparse(result1)
        test_host = parsed.hostname
        test_port = str(parsed.port) if parsed.port else ("443" if parsed.scheme == "https" else "80")
        
        msg.info(f"Host: {test_host}, Port: {test_port}, Scheme: {parsed.scheme}")
    
    result2 = asyncio.run(test_exact_railway_settings())
    
    msg.info("")
    msg.info("=" * 60)
    msg.info("RESUMO")
    msg.info("=" * 60)
    if result1:
        msg.good(f"HTTP/HTTPS Direto: OK - URL funcional: {result1}")
    else:
        msg.fail("HTTP/HTTPS Direto: FALHOU - Nenhuma URL funcionou")
    
    msg.info(f"Verba connect_to_custom: {'OK' if result2 else 'FALHOU (biblioteca nao disponivel localmente)'}")
    msg.info("")
    
    if result1:
        msg.good("URL ACESSIVEL ENCONTRADA!")
        msg.info(f"")
        msg.info("CONFIGURACAO PARA VERBA:")
        msg.info(f"  Host: {test_host}")
        msg.info(f"  Port: {test_port}")
        msg.info(f"  URL completa: {result1}")
        msg.info("")
        msg.info("Esta e a configuracao que deve funcionar no Verba!")
    else:
        msg.fail("Nenhuma URL funcionou.")
        msg.info("Verifique se Weaviate esta acessivel publicamente.")

