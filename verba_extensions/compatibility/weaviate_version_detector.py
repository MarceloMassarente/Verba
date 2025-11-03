"""
Detector de versão Weaviate e adapter compatível
"""

import httpx
import asyncio
from typing import Optional, Union

class WeaviateVersionDetector:
    """Detecta versão do Weaviate e cria cliente compatível"""
    
    @staticmethod
    async def detect(url: str) -> str:
        """
        Detecta versão do Weaviate
        Retorna: 'v3', 'v4', ou 'unknown'
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Tenta endpoint que funciona em ambas versões
                r = await client.get(f"{url.rstrip('/')}/v1/meta")
                
                if r.status_code == 200:
                    data = r.json()
                    
                    # Verifica versão pelo formato da resposta
                    # v4 geralmente tem estrutura mais complexa em modules
                    # v3 pode ter modules mas estrutura diferente
                    
                    if 'version' in data:
                        version_str = str(data['version'])
                        if version_str.startswith('1.'):
                            # Weaviate 1.x = API v1 (GraphQL v3)
                            # Verifica se tem estrutura v4
                            if 'modules' in data and isinstance(data['modules'], dict):
                                # Conta quantos módulos (v4 tem mais)
                                if len(data.get('modules', {})) > 5:
                                    return 'v4'
                                # v3 pode ter modules mas estrutura diferente
                                return 'v3'
                            return 'v3'
                    
                    # Fallback: se tem modules detalhado, provavelmente v4
                    if 'modules' in data:
                        modules = data['modules']
                        if isinstance(modules, dict):
                            # v4 tem modules como dict com documentação
                            # v3 pode ter como lista simples ou estrutura diferente
                            if any('documentationHref' in str(m) for m in modules.values()):
                                return 'v4'
                            return 'v3'
                    
                    # Default: assume v3 se não conseguir detectar
                    return 'v3'
                    
        except Exception as e:
            print(f"Erro ao detectar versão: {str(e)}")
            return 'unknown'
    
    @staticmethod
    async def create_compatible_connection(
        url: str,
        api_key: Optional[str] = None,
        port: Optional[int] = None
    ):
        """
        Cria conexão compatível detectando versão automaticamente
        
        Para v3: Usa API REST direta (httpx)
        Para v4: Usa weaviate-client v4
        """
        version = await WeaviateVersionDetector.detect(url)
        
        if version == 'v3':
            print(f"Detectado Weaviate API v3 - usando API REST direta")
            from verba_extensions.compatibility.weaviate_v3_adapter import WeaviateV3HTTPAdapter
            return WeaviateV3HTTPAdapter(url, api_key)
        elif version == 'v4':
            print(f"Detectado Weaviate API v4 - usando weaviate-client v4")
            # Usa cliente v4 normal (já implementado)
            import weaviate
            from weaviate.classes.init import AdditionalConfig, Timeout
            from weaviate.auth import AuthApiKey
            
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname
            
            if port is None:
                port = parsed.port or (443 if parsed.scheme == 'https' else 8080)
            
            if api_key:
                return weaviate.use_async_with_local(
                    host=host,
                    port=port,
                    skip_init_checks=True,
                    auth_credentials=AuthApiKey(api_key),
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=60, query=300, insert=300)
                    )
                )
            else:
                return weaviate.use_async_with_local(
                    host=host,
                    port=port,
                    skip_init_checks=True,
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=60, query=300, insert=300)
                    )
                )
        else:
            raise Exception(f"Versão Weaviate desconhecida: {version}")

