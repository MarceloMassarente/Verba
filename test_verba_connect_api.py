"""
Teste direto da API /api/connect do Verba
Simula o que o frontend faz
"""

import asyncio
import httpx
import json

VERBA_URL = "https://verba-production-c347.up.railway.app"
WEAVIATE_URL = "https://weaviate-production-0d0e.up.railway.app"

async def test_connect_api():
    """Testa endpoint /api/connect diretamente"""
    print("=" * 60)
    print("TESTE: API /api/connect do Verba")
    print("=" * 60)
    print(f"Verba URL: {VERBA_URL}")
    print(f"Weaviate URL: {WEAVIATE_URL}")
    print()
    
    # Payload como o frontend enviaria
    payload = {
        "credentials": {
            "deployment": "Custom",
            "url": WEAVIATE_URL,
            "key": ""
        },
        "port": "8080"
    }
    
    print("Payload:")
    print(json.dumps(payload, indent=2))
    print()
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # Testa /api/health primeiro
            print("Testando /api/health...")
            r_health = await client.get(f"{VERBA_URL}/api/health")
            print(f"Status: {r_health.status_code}")
            
            if r_health.status_code != 200:
                print(f"ERRO: Verba nao esta respondendo corretamente")
                return False
            
            print("OK: /api/health funciona")
            print()
            
            # Tenta /api/connect
            print("Testando /api/connect...")
            print(f"Headers: Origin={VERBA_URL}")
            
            r_connect = await client.post(
                f"{VERBA_URL}/api/connect",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Origin": VERBA_URL,
                    "Referer": f"{VERBA_URL}/"
                }
            )
            
            print(f"Status: {r_connect.status_code}")
            print(f"Response: {r_connect.text[:500]}")
            print()
            
            if r_connect.status_code == 200:
                print("OK: Conexao bem-sucedida!")
                data = r_connect.json()
                print(f"Connected: {data.get('connected', False)}")
                return True
            elif r_connect.status_code == 403:
                print("ERRO 403: Middleware CORS bloqueou")
                print()
                print("Detalhes da resposta:")
                try:
                    error_data = r_connect.json()
                    print(json.dumps(error_data, indent=2))
                    print()
                    print("Solucao:")
                    print("1. Verifique se codigo corrigido foi deployado")
                    print("2. Configure ALLOWED_ORIGINS no Railway")
                    print("3. Aguarde redeploy completo")
                except:
                    print(r_connect.text)
                return False
            else:
                print(f"ERRO: Status {r_connect.status_code}")
                print(f"Response: {r_connect.text[:500]}")
                return False
                
    except Exception as e:
        print(f"\nERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_without_origin():
    """Testa sem header Origin (para ver se middleware bloqueia)"""
    print("\n" + "=" * 60)
    print("TESTE: Sem header Origin")
    print("=" * 60)
    
    payload = {
        "credentials": {
            "deployment": "Custom",
            "url": WEAVIATE_URL,
            "key": ""
        },
        "port": "8080"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{VERBA_URL}/api/connect",
                json=payload,
                headers={"Content-Type": "application/json"}
                # SEM Origin header
            )
            
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text[:500]}")
            
            return r.status_code != 403
            
    except Exception as e:
        print(f"ERRO: {str(e)}")
        return False

if __name__ == "__main__":
    print()
    
    result1 = asyncio.run(test_connect_api())
    result2 = asyncio.run(test_without_origin())
    
    print()
    print("=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Teste com Origin: {'OK' if result1 else 'FALHOU'}")
    print(f"Teste sem Origin: {'OK' if result2 else 'FALHOU'}")
    print()
    
    if not result1:
        print("PROBLEMA: Middleware CORS ainda esta bloqueando")
        print()
        print("Verifique:")
        print("1. Codigo corrigido foi commitado e pushado?")
        print("2. Railway fez redeploy com novo codigo?")
        print("3. ALLOWED_ORIGINS esta configurado?")
        print("4. Aguarde alguns minutos apos push para redeploy completo")

