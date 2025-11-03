"""
Teste de conexao com Weaviate Cloud cluster perfislk
"""

import asyncio
import httpx
from wasabi import msg

async def test_cloud_cluster():
    """Testa conexao com cluster Weaviate Cloud"""
    
    # Informacoes do cluster da imagem
    rest_endpoint = "o3r2eli2twaoxcx50nrv3q.c0.us-west3.gcp.weaviate.cloud"
    grpc_endpoint = "grpc-o3r2eli2twaoxcx50nrv3q.c0.us-west3.gcp.weaviate.cloud"
    
    # URL completa (geralmente HTTPS)
    url = f"https://{rest_endpoint}"
    
    msg.info("=" * 60)
    msg.info("TESTE: Weaviate Cloud - Cluster perfislk")
    msg.info("=" * 60)
    msg.info(f"REST Endpoint: {rest_endpoint}")
    msg.info(f"gRPC Endpoint: {grpc_endpoint}")
    msg.info("")
    
    # Testa endpoints basicos
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Testa /ready
            msg.info("Testando /v1/.well-known/ready...")
            r1 = await client.get(f"{url}/v1/.well-known/ready")
            msg.info(f"Status: {r1.status_code}")
            
            if r1.status_code == 200:
                msg.good("OK: Cluster esta pronto!")
            elif r1.status_code == 401:
                msg.warn("401: Requer autenticacao (API Key)")
            else:
                msg.warn(f"Status {r1.status_code}: {r1.text[:200]}")
            
            # Testa /meta (pode precisar auth)
            msg.info("\nTestando /v1/meta...")
            try:
                r2 = await client.get(f"{url}/v1/meta")
                msg.info(f"Status: {r2.status_code}")
                
                if r2.status_code == 200:
                    data = r2.json()
                    msg.good("OK: Meta obtido com sucesso!")
                    msg.info(f"Version: {data.get('version', 'N/A')}")
                    msg.info(f"Hostname: {data.get('hostname', 'N/A')}")
                elif r2.status_code == 401:
                    msg.warn("401: Requer API Key para /meta")
                else:
                    msg.warn(f"Status {r2.status_code}")
            except Exception as e:
                msg.warn(f"Erro ao obter meta: {str(e)}")
            
            # Testa /schema
            msg.info("\nTestando /v1/schema...")
            try:
                r3 = await client.get(f"{url}/v1/schema")
                msg.info(f"Status: {r3.status_code}")
                
                if r3.status_code == 200:
                    schema = r3.json()
                    classes = schema.get('classes', [])
                    msg.good(f"OK: Schema obtido - {len(classes)} classes encontradas")
                    for cls in classes[:5]:
                        msg.info(f"  - {cls.get('class', 'N/A')}")
                elif r3.status_code == 401:
                    msg.warn("401: Requer API Key para /schema")
                else:
                    msg.warn(f"Status {r3.status_code}")
            except Exception as e:
                msg.warn(f"Erro ao obter schema: {str(e)}")
                
    except httpx.ConnectError as e:
        msg.fail(f"Erro de conexao: {str(e)}")
        return False
    except Exception as e:
        msg.fail(f"Erro geral: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def test_with_verba_manager():
    """Testa usando o WeaviateManager do Verba"""
    rest_endpoint = "o3r2eli2twaoxcx50nrv3q.c0.us-west3.gcp.weaviate.cloud"
    url = f"https://{rest_endpoint}"
    
    msg.info("\n" + "=" * 60)
    msg.info("TESTE: VerbaManager com Weaviate Cloud")
    msg.info("=" * 60)
    
    # Pula teste se versao incompativel
    try:
        from goldenverba.components.managers import WeaviateManager
    except ImportError as e:
        msg.warn(f"Versao weaviate-client incompativel: {str(e)}")
        msg.info("Pulando teste VerbaManager - use teste HTTP acima")
        return False
    
    try:
        manager = WeaviateManager()
        
        # Weaviate Cloud geralmente precisa de API Key
        api_key = os.getenv("WEAVIATE_API_KEY", "")
        
        msg.info(f"Testando conexao 'Weaviate Cloud'...")
        msg.info(f"URL: {url}")
        msg.info(f"API Key: {'Fornecida' if api_key else 'Nao fornecida'}")
        
        # Tenta como "Weaviate" deployment (Cloud)
        try:
            client = await manager.connect(
                deployment="Weaviate",
                weaviateURL=url,
                weaviateAPIKey=api_key,
                port="443"
            )
            
            if client:
                msg.good("OK: Conexao estabelecida!")
                if await client.is_ready():
                    msg.good("OK: Cluster esta pronto!")
                    
                    collections = await client.collections.list_all()
                    msg.good(f"OK: {len(collections)} colecoes encontradas")
                    
                    await manager.disconnect(client)
                    return True
            else:
                msg.warn("Client nao foi criado")
                return False
                
        except Exception as e:
            error_str = str(e).lower()
            if '401' in str(e) or 'unauthorized' in error_str or 'auth' in error_str:
                msg.warn("Erro de autenticacao: Precisa de API Key")
                msg.info("")
                msg.info("Para usar este cluster:")
                msg.info("  1. Crie uma API Key no Weaviate Cloud console")
                msg.info("  2. Configure: WEAVIATE_API_KEY=<sua-key>")
                msg.info("  3. Deployment: 'Weaviate' (Cloud)")
                msg.info(f"  4. URL: {url}")
            else:
                msg.fail(f"Erro na conexao: {str(e)}")
            return False
            
    except Exception as e:
        msg.fail(f"Erro geral: {str(e)}")
        return False

import os

if __name__ == "__main__":
    msg.info("")
    
    # Teste HTTP basico
    result1 = asyncio.run(test_cloud_cluster())
    
    # Teste com VerbaManager
    result2 = asyncio.run(test_with_verba_manager())
    
    msg.info("")
    msg.info("=" * 60)
    msg.info("RESUMO:")
    msg.info(f"HTTP Test: {'OK' if result1 else 'Falhou'}")
    msg.info(f"VerbaManager Test: {'OK' if result2 else 'Falhou (pode precisar API Key)'}")
    msg.info("")
    
    if not result2:
        msg.info("INSTRUCOES:")
        msg.info("")
        msg.info("1. Vá no Weaviate Cloud Console")
        msg.info("2. Clique em '+ New key' no cluster perfislk")
        msg.info("3. Copie a API Key gerada")
        msg.info("4. Configure no .env:")
        msg.info("   WEAVIATE_API_KEY=<sua-key>")
        msg.info("   WEAVIATE_URL_VERBA=https://o3r2eli2twaoxcx50nrv3q.c0.us-west3.gcp.weaviate.cloud")
        msg.info("")
        msg.info("5. No Verba UI:")
        msg.info("   Deployment: 'Weaviate'")
        msg.info("   URL: (pega do .env ou digita)")
        msg.info("   API Key: (pega do .env ou digita)")

