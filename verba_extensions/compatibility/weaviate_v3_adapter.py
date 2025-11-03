"""
Adapter para compatibilidade com Weaviate API v3
Permite usar Verba com Weaviate v3 mesmo que o cliente seja v4
"""

import os
from typing import Optional
from wasabi import msg

def detect_weaviate_version(url: str) -> str:
    """
    Detecta versão do Weaviate via API
    Retorna 'v3' ou 'v4'
    """
    try:
        import httpx
        import asyncio
        
        async def check():
            async with httpx.AsyncClient(timeout=5.0) as client:
                # API v3 tem /v1/meta, API v4 também mas estrutura pode diferir
                r = await client.get(f"{url}/v1/meta")
                if r.status_code == 200:
                    data = r.json()
                    # API v3 geralmente retorna estrutura mais simples
                    # API v4 retorna modules e mais detalhes
                    if 'modules' in data and isinstance(data['modules'], dict):
                        return 'v4'  # Provável v4
                    else:
                        return 'v3'  # Provável v3
                return 'unknown'
        
        return asyncio.run(check())
    except:
        return 'unknown'


def get_v3_client(url: str, api_key: Optional[str] = None, port: int = 443):
    """
    Cria cliente Weaviate v3 usando weaviate-client<4.0.0
    Fallback para usar API REST direta se necessário
    """
    try:
        # Tenta importar weaviate v3 (se instalado)
        try:
            # weaviate-client v3 usa Client diretamente
            import weaviate3 as weaviate
            
            if api_key:
                return weaviate.Client(
                    url=url,
                    auth_client_secret=weaviate.AuthApiKey(api_key=api_key)
                )
            else:
                return weaviate.Client(url=url)
                
        except ImportError:
            # Se não tem v3 instalado, usa httpx direto como fallback
            msg.warn("weaviate-client v3 não encontrado, usando HTTP direto")
            return None
            
    except Exception as e:
        msg.warn(f"Erro ao criar cliente v3: {str(e)}")
        return None


def create_compatible_client(url: str, api_key: Optional[str] = None, port: int = 443):
    """
    Cria cliente compatível detectando versão automaticamente
    """
    version = detect_weaviate_version(url)
    
    if version == 'v3':
        msg.info("Detectado Weaviate API v3 - usando adapter")
        # Para v3, precisamos usar weaviate-client v3 ou API REST direta
        # Por enquanto, retorna None para usar API REST direta
        return None, 'v3'
    else:
        # Usa cliente v4 normal
        return None, 'v4'


class WeaviateV3HTTPAdapter:
    """
    Adapter HTTP direto para Weaviate API v3
    Usa httpx para fazer chamadas diretas à API REST
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def is_ready(self) -> bool:
        """Verifica se Weaviate está pronto"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{self.base_url}/v1/.well-known/ready",
                    headers=self.headers,
                    timeout=5.0
                )
                return r.status_code == 200
        except:
            return False
    
    async def schema_get(self):
        """Obtém schema"""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/v1/schema",
                headers=self.headers,
                timeout=10.0
            )
            if r.status_code == 200:
                return r.json()
            return None
    
    async def objects_create(self, class_name: str, properties: dict, vector: Optional[list] = None):
        """Cria objeto"""
        import httpx
        payload = {"class": class_name, "properties": properties}
        if vector:
            payload["vector"] = vector
        
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base_url}/v1/objects",
                json=payload,
                headers=self.headers,
                timeout=30.0
            )
            if r.status_code == 200:
                return r.json()
            raise Exception(f"Erro ao criar objeto: {r.status_code} - {r.text}")
    
    async def query_get(self, class_name: str, query_params: dict):
        """Query GraphQL v3"""
        import httpx
        # API v3 usa GraphQL
        query = self._build_graphql_query(class_name, query_params)
        
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base_url}/v1/graphql",
                json={"query": query},
                headers=self.headers,
                timeout=30.0
            )
            if r.status_code == 200:
                return r.json()
            raise Exception(f"Erro na query: {r.status_code} - {r.text}")
    
    def _build_graphql_query(self, class_name: str, params: dict) -> str:
        """Constrói query GraphQL para v3"""
        # Implementação básica - pode ser expandida
        limit = params.get('limit', 10)
        where = params.get('where', '')
        
        query = f"""
        {{
            Get {{
                {class_name}(limit: {limit}) {{
                    _additional {{
                        id
                    }}
                }}
            }}
        }}
        """
        return query

