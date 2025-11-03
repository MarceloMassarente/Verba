"""
Patch para adicionar suporte a Weaviate API v3
Modifica WeaviateManager para detectar e usar v3 quando necessário
"""

from wasabi import msg
import os

def patch_weaviate_manager_for_v3():
    """
    Adiciona suporte a Weaviate API v3 ao WeaviateManager
    Detecta automaticamente a versão e usa método apropriado
    """
    try:
        from goldenverba.components import managers
        
        # Guarda método original
        original_connect_custom = managers.WeaviateManager.connect_to_custom
        original_connect_cluster = managers.WeaviateManager.connect_to_cluster
        
        async def patched_connect_to_custom(self, host, w_key, port):
            """
            Connect to custom com suporte a v3
            Tenta v4 primeiro, se falhar por incompatibilidade, tenta v3
            """
            # Tenta conexão v4 normal primeiro
            try:
                return await original_connect_custom(self, host, w_key, port)
            except Exception as e:
                error_str = str(e).lower()
                # Se erro sugere incompatibilidade de API, tenta v3
                if any(x in error_str for x in ['api', 'version', 'schema', 'v3', 'v4']):
                    msg.warn(f"Possivel incompatibilidade de API, tentando conexao v3: {str(e)}")
                    return await self._connect_to_custom_v3(host, w_key, port)
                raise
        
        async def _connect_to_custom_v3(self, host, w_key, port):
            """
            Conexão usando API REST direta para v3
            Retorna um objeto compatível que funciona com o resto do código
            """
            from urllib.parse import urlparse
            
            # Constrói URL completa
            if port == "443" or port == 443:
                url = f"https://{host}"
            elif port == "80" or port == 80:
                url = f"http://{host}"
            else:
                url = f"http://{host}:{port}"
            
            msg.info(f"Conectando via API REST direta (v3): {url}")
            
            # Cria adapter HTTP v3
            from verba_extensions.compatibility.weaviate_v3_adapter import WeaviateV3HTTPAdapter
            adapter = WeaviateV3HTTPAdapter(url, w_key if w_key else None)
            
            # Verifica se está pronto
            if await adapter.is_ready():
                msg.good("Conexao v3 estabelecida via API REST")
                # Retorna adapter wrapped em objeto compatível
                return adapter
            else:
                raise Exception("Weaviate v3 nao esta pronto")
        
        async def patched_connect_to_cluster(self, w_url, w_key):
            """
            Connect to cluster com suporte a v3
            """
            # Para cluster, geralmente é v4, mas pode tentar v3 se falhar
            try:
                return await original_connect_cluster(self, w_url, w_key)
            except Exception as e:
                error_str = str(e).lower()
                if any(x in error_str for x in ['api', 'version', 'schema']):
                    msg.warn("Possivel Weaviate v3 em cluster, usando API REST direta")
                    # Extrai host da URL
                    from urllib.parse import urlparse
                    parsed = urlparse(w_url)
                    host = parsed.hostname
                    port = parsed.port or (443 if parsed.scheme == 'https' else 8080)
                    return await self._connect_to_custom_v3(host, w_key or "", str(port))
                raise
        
        # Aplica patches
        managers.WeaviateManager.connect_to_custom = patched_connect_to_custom
        managers.WeaviateManager.connect_to_cluster = patched_connect_to_cluster
        managers.WeaviateManager._connect_to_custom_v3 = _connect_to_custom_v3
        
        msg.info("Patch de compatibilidade v3 aplicado ao WeaviateManager")
        return True
        
    except Exception as e:
        msg.warn(f"Erro ao aplicar patch v3: {str(e)}")
        return False

