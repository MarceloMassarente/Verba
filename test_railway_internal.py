"""
Testa acesso interno Railway entre serviços no mesmo projeto
"""

import asyncio
from wasabi import msg
import os

# Nomes possíveis do serviço Weaviate no Railway
WEAVIATE_INTERNAL_NAMES = [
    "weaviate.railway.internal",  # Formato Railway padrão
    "weaviate",  # Nome curto (pode funcionar em alguns casos)
]

WEAVIATE_PUBLIC_URL = "https://weaviate-production-0d0e.up.railway.app"
WEAVIATE_PORT = 8080  # Porta interna

async def test_internal_access():
    """Testa acesso via rede interna Railway"""
    msg.info("=" * 60)
    msg.info("TESTE: Acesso Interno Railway")
    msg.info("=" * 60)
    msg.info("")
    msg.info("Verificando variaveis de ambiente Railway...")
    
    # Railway injeta variáveis de ambiente com informações dos serviços
    railway_env = {}
    for key, value in os.environ.items():
        if "RAILWAY" in key or "SERVICE" in key:
            railway_env[key] = value
            msg.info(f"  {key}: {value}")
    
    msg.info("")
    msg.info("Tentando acesso interno...")
    
    for internal_name in WEAVIATE_INTERNAL_NAMES:
        msg.info(f"\nTestando: {internal_name}:{WEAVIATE_PORT}")
        try:
            import httpx
            
            url = f"http://{internal_name}:{WEAVIATE_PORT}"
            msg.info(f"URL interna: {url}")
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{url}/v1/.well-known/ready")
                if r.status_code == 200:
                    msg.good(f"OK: Acesso interno funciona via {internal_name}!")
                    return url
                else:
                    msg.warn(f"Status {r.status_code} para {internal_name}")
        except Exception as e:
            msg.warn(f"Falhou {internal_name}: {str(e)[:100]}")
    
    return None

async def test_public_vs_internal():
    """Compara acesso público vs interno"""
    msg.info("\n" + "=" * 60)
    msg.info("COMPARACAO: Publico vs Interno")
    msg.info("=" * 60)
    
    # Testa público
    msg.info("\n1. Acesso Publico (HTTPS):")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{WEAVIATE_PUBLIC_URL}/v1/.well-known/ready")
            if r.status_code == 200:
                msg.good(f"   OK: {WEAVIATE_PUBLIC_URL}")
                public_ok = True
            else:
                msg.warn(f"   Status {r.status_code}")
                public_ok = False
    except Exception as e:
        msg.warn(f"   Erro: {str(e)[:100]}")
        public_ok = False
    
    # Testa interno
    msg.info("\n2. Acesso Interno (HTTP porta 8080):")
    internal_url = await test_internal_access()
    internal_ok = internal_url is not None
    
    msg.info("")
    msg.info("=" * 60)
    msg.info("RESUMO")
    msg.info("=" * 60)
    msg.info(f"Acesso Publico: {'OK' if public_ok else 'FALHOU'}")
    msg.info(f"Acesso Interno: {'OK' if internal_ok else 'FALHOU'}")
    msg.info("")
    
    if internal_ok:
        msg.good("RECOMENDACAO: Use acesso interno!")
        msg.info(f"")
        msg.info("Configuracao para Verba:")
        msg.info(f"  Host: {internal_url.replace('http://', '').split(':')[0]}")
        msg.info(f"  Port: {WEAVIATE_PORT}")
        msg.info(f"  URL: {internal_url}")
        msg.info("")
        msg.info("Vantagens:")
        msg.info("  - Mais rapido (rede interna)")
        msg.info("  - Nao precisa HTTPS")
        msg.info("  - Porta 8080 funciona diretamente")
        msg.info("  - Sem problemas de CORS/autenticacao")
    elif public_ok:
        msg.warn("Acesso interno nao disponivel - use acesso publico")
    else:
        msg.fail("Nenhum acesso funcionou")

if __name__ == "__main__":
    asyncio.run(test_public_vs_internal())

