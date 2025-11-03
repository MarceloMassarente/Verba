"""
Teste simples de conexao Weaviate Railway
"""

import asyncio
import httpx

WEAVIATE_URL = "https://weaviate-production-0d0e.up.railway.app"

async def test():
    print("=" * 60)
    print("TESTE: Weaviate Railway")
    print("=" * 60)
    print(f"URL: {WEAVIATE_URL}")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Testa /ready
            print("Testando /v1/.well-known/ready...")
            r1 = await client.get(f"{WEAVIATE_URL}/v1/.well-known/ready")
            print(f"Status: {r1.status_code}")
            
            if r1.status_code == 200:
                print("OK: Weaviate esta pronto!")
            else:
                print(f"FALHOU: Status {r1.status_code}")
                return False
            
            # Testa /meta
            print("\nTestando /v1/meta...")
            r2 = await client.get(f"{WEAVIATE_URL}/v1/meta")
            print(f"Status: {r2.status_code}")
            
            if r2.status_code == 200:
                data = r2.json()
                print("OK: Meta obtido!")
                print(f"Version: {data.get('version', 'N/A')}")
            else:
                print(f"Status {r2.status_code}")
            
            # Testa /schema
            print("\nTestando /v1/schema...")
            r3 = await client.get(f"{WEAVIATE_URL}/v1/schema")
            print(f"Status: {r3.status_code}")
            
            if r3.status_code == 200:
                schema = r3.json()
                classes = schema.get('classes', [])
                print(f"OK: Schema obtido - {len(classes)} classes")
                for cls in classes[:5]:
                    print(f"  - {cls.get('class', 'N/A')}")
            
            print()
            print("=" * 60)
            print("RESULTADO: CONEXAO OK!")
            print("=" * 60)
            print()
            print("Configuracao para Railway:")
            print(f"  WEAVIATE_URL_VERBA={WEAVIATE_URL}")
            print("  WEAVIATE_API_KEY_VERBA=")
            print("  DEFAULT_DEPLOYMENT=Custom")
            print()
            print("Na UI do Verba:")
            print("  Deployment: Custom")
            print(f"  Host: weaviate-production-0d0e.up.railway.app")
            print("  Port: 8080")
            print("  API Key: (vazio)")
            
            return True
            
    except Exception as e:
        print(f"\nERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test())

