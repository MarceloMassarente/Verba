"""
Teste especifico para Weaviate API v3 no Railway
"""

import asyncio
import httpx
from wasabi import msg

async def test_v3_connection():
    """Testa conexao especificamente para API v3"""
    url = "https://weaviate-production-0d0e.up.railway.app"
    
    msg.info(f"Testando conexao v3 com: {url}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Testa endpoints v3
            endpoints = [
                "/v1/.well-known/ready",
                "/v1/.well-known/live",
                "/v1/meta",
                "/v1/schema"
            ]
            
            results = {}
            
            for endpoint in endpoints:
                try:
                    r = await client.get(f"{url}{endpoint}")
                    results[endpoint] = {
                        "status": r.status_code,
                        "success": r.status_code == 200
                    }
                    
                    if r.status_code == 200:
                        msg.good(f"OK: {endpoint} - Status {r.status_code}")
                    else:
                        msg.warn(f"Status {r.status_code}: {endpoint}")
                        
                except Exception as e:
                    results[endpoint] = {"error": str(e)}
                    msg.warn(f"Erro em {endpoint}: {str(e)}")
            
            # Tenta detectar versão pela resposta do /v1/meta
            try:
                r = await client.get(f"{url}/v1/meta")
                if r.status_code == 200:
                    data = r.json()
                    msg.info(f"Meta response keys: {list(data.keys())[:5]}")
                    
                    # API v3 geralmente tem estrutura mais simples
                    # API v4 tem 'modules' como dict detalhado
                    if 'modules' in data:
                        if isinstance(data['modules'], dict) and len(data['modules']) > 0:
                            msg.info("Detectado: Provavel API v4 (modules detalhado)")
                            return "v4", results
                        else:
                            msg.info("Detectado: Provavel API v3 (modules simples ou ausente)")
                            return "v3", results
                    else:
                        msg.info("Detectado: Provavel API v3 (sem modules)")
                        return "v3", results
            except:
                pass
            
            # Se todos endpoints funcionaram, assume v3
            if all(r.get("success", False) for r in results.values() if isinstance(r, dict)):
                msg.good("TODOS ENDPOINTS FUNCIONARAM!")
                msg.info("Recomendacao: Usar API REST direta ou weaviate-client v3")
                return "v3", results
            else:
                msg.warn("Alguns endpoints falharam")
                return "unknown", results
                
    except Exception as e:
        msg.fail(f"Erro geral: {str(e)}")
        import traceback
        traceback.print_exc()
        return "error", {}

async def test_graphql_v3():
    """Testa query GraphQL (API v3)"""
    url = "https://weaviate-production-0d0e.up.railway.app"
    
    msg.info("\nTestando GraphQL (API v3)...")
    
    query = """
    {
        Meta {
            __name
        }
    }
    """
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{url}/v1/graphql",
                json={"query": query},
                timeout=10.0
            )
            
            if r.status_code == 200:
                msg.good(f"OK: GraphQL funcionou - Status {r.status_code}")
                msg.info(f"Response: {r.text[:200]}")
                return True
            else:
                msg.warn(f"GraphQL retornou: {r.status_code}")
                msg.info(f"Response: {r.text[:200]}")
                return False
                
    except Exception as e:
        msg.warn(f"GraphQL nao funcionou: {str(e)}")
        return False

if __name__ == "__main__":
    msg.info("=" * 60)
    msg.info("TESTE ESPECIFICO WEAVIATE API V3")
    msg.info("=" * 60)
    msg.info("")
    
    version, results = asyncio.run(test_v3_connection())
    graphql_works = asyncio.run(test_graphql_v3())
    
    msg.info("")
    msg.info("=" * 60)
    msg.info("RESULTADO:")
    msg.info(f"Versao detectada: {version}")
    msg.info(f"GraphQL funciona: {'Sim' if graphql_works else 'Nao'}")
    msg.info("")
    
    if version == "v3":
        msg.good("CONFIRMADO: Weaviate API v3")
        msg.info("")
        msg.info("Solucao:")
        msg.info("  1. Instale weaviate-client v3: pip install 'weaviate-client<4.0.0'")
        msg.info("  2. OU use o adapter v3 criado em verba_extensions/compatibility/")
        msg.info("  3. OU use API REST direta (httpx)")
    elif version == "v4":
        msg.info("Detectado API v4 - codigo atual deve funcionar")
    else:
        msg.warn("Versao nao detectada claramente")
        msg.info("Tente usar deployment 'Custom' no Verba")

