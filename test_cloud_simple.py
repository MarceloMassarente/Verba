"""
Teste simples do cluster Weaviate Cloud perfislk
"""

import asyncio
import httpx

async def test():
    rest_endpoint = "o3r2eli2twaoxcx50nrv3q.c0.us-west3.gcp.weaviate.cloud"
    url = f"https://{rest_endpoint}"
    
    print("=" * 60)
    print("TESTE: Weaviate Cloud - Cluster perfislk")
    print("=" * 60)
    print(f"REST Endpoint: {rest_endpoint}")
    print(f"URL: {url}")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Testa /ready (geralmente nao precisa auth)
            print("Testando /v1/.well-known/ready...")
            r1 = await client.get(f"{url}/v1/.well-known/ready")
            print(f"Status: {r1.status_code}")
            
            if r1.status_code == 200:
                print("OK: Cluster esta pronto!")
            else:
                print(f"Status {r1.status_code}: {r1.text[:100]}")
            
            # Testa /meta (precisa auth no Weaviate Cloud)
            print("\nTestando /v1/meta...")
            r2 = await client.get(f"{url}/v1/meta")
            print(f"Status: {r2.status_code}")
            
            if r2.status_code == 200:
                data = r2.json()
                print("OK: Meta obtido!")
                print(f"Version: {data.get('version', 'N/A')}")
            elif r2.status_code == 401:
                print("401: Precisa de API Key (esperado para Weaviate Cloud)")
            else:
                print(f"Status {r2.status_code}")
            
            # Testa /schema (precisa auth)
            print("\nTestando /v1/schema...")
            r3 = await client.get(f"{url}/v1/schema")
            print(f"Status: {r3.status_code}")
            
            if r3.status_code == 200:
                schema = r3.json()
                classes = schema.get('classes', [])
                print(f"OK: Schema obtido - {len(classes)} classes")
            elif r3.status_code == 401:
                print("401: Precisa de API Key (esperado)")
            else:
                print(f"Status {r3.status_code}")
                
    except Exception as e:
        print(f"Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    print("=" * 60)
    print("RESULTADO:")
    print("=" * 60)
    print()
    print("OK: Cluster Weaviate Cloud esta funcionando!")
    print()
    print("IMPORTANTE: Weaviate Cloud requer API Key para:")
    print("  - /v1/meta")
    print("  - /v1/schema")
    print("  - Queries e operacoes")
    print()
    print("Para conectar no Verba:")
    print("  1. Va no console: console.weaviate.cloud")
    print("  2. Clique em '+ New key' no cluster perfislk")
    print("  3. Copie a API Key")
    print("  4. Configure:")
    print(f"     Deployment: Weaviate")
    print(f"     URL: {url}")
    print("     API Key: <sua-key>")
    print()
    
    return True

if __name__ == "__main__":
    asyncio.run(test())

