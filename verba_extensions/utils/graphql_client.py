"""
GraphQL Client
Executa queries GraphQL via HTTP REST com fallback

Aprende do RAG2: HTTP fallback quando SDK Python não suporta features avançadas
"""

import os
from typing import Dict, Any, Optional, List
import httpx
from wasabi import msg


class GraphQLClient:
    """
    Cliente GraphQL para Weaviate com HTTP fallback.
    
    Usa HTTP REST API quando:
    - SDK Python não suporta features avançadas
    - gRPC está desabilitado
    - Named vectors requerem queries GraphQL diretas
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Inicializa cliente GraphQL.
        
        Args:
            base_url: URL base do Weaviate (ex: "http://localhost:8080")
            api_key: API key do Weaviate (opcional)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def execute_query(
        self,
        query: str,
        timeout: float = 30.0,
        retries: int = 3
    ) -> Dict[str, Any]:
        """
        Executa query GraphQL via HTTP REST.
        
        Args:
            query: Query GraphQL como string
            timeout: Timeout em segundos
            retries: Número de tentativas em caso de falha
        
        Returns:
            Dict com resposta do Weaviate
        
        Raises:
            Exception: Se query falhar após todas as tentativas
        """
        url = f"{self.base_url}/v1/graphql"
        
        payload = {
            "query": query
        }
        
        last_error = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=self.headers
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # Verificar erros GraphQL
                        if "errors" in result:
                            errors = result["errors"]
                            error_msg = "; ".join([e.get("message", str(e)) for e in errors])
                            raise Exception(f"GraphQL errors: {error_msg}")
                        
                        return result
                    else:
                        raise Exception(f"HTTP {response.status_code}: {response.text}")
                        
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < retries - 1:
                    msg.warn(f"Timeout na query GraphQL (tentativa {attempt + 1}/{retries}), tentando novamente...")
                    await asyncio.sleep(1.0 * (attempt + 1))  # Backoff exponencial
                else:
                    raise Exception(f"Timeout após {retries} tentativas: {str(e)}")
            
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    msg.warn(f"Erro na query GraphQL (tentativa {attempt + 1}/{retries}): {str(e)}, tentando novamente...")
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    raise Exception(f"Falha após {retries} tentativas: {str(e)}")
        
        # Se chegou aqui, todas as tentativas falharam
        raise Exception(f"Falha ao executar query GraphQL após {retries} tentativas: {str(last_error)}")
    
    async def execute_with_fallback(
        self,
        query: str,
        sdk_method: Optional[callable] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Executa query com fallback: tenta SDK primeiro, depois HTTP.
        
        Args:
            query: Query GraphQL como string
            sdk_method: Método do SDK para tentar primeiro (opcional)
            timeout: Timeout em segundos
        
        Returns:
            Dict com resposta do Weaviate
        """
        # Tentar SDK primeiro se disponível
        if sdk_method:
            try:
                return await sdk_method()
            except Exception as sdk_error:
                error_str = str(sdk_error).lower()
                # Se erro é de gRPC ou feature não suportada, usar HTTP fallback
                if "grpc" in error_str or "not supported" in error_str or "targetvector" in error_str:
                    msg.info(f"SDK falhou ({str(sdk_error)[:100]}), usando HTTP fallback")
                else:
                    # Re-raise se erro não é relacionado a gRPC/features
                    raise
        
        # Fallback: usar HTTP
        return await self.execute_query(query, timeout=timeout)


def get_graphql_client(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> GraphQLClient:
    """
    Factory function para obter instância do GraphQLClient.
    
    Args:
        base_url: URL base do Weaviate (se None, tenta obter de env vars)
        api_key: API key do Weaviate (se None, tenta obter de env vars)
    
    Returns:
        Instância de GraphQLClient
    """
    if not base_url:
        base_url = os.getenv("WEAVIATE_URL_VERBA") or os.getenv("WEAVIATE_URL") or "http://localhost:8080"
    
    if not api_key:
        api_key = os.getenv("WEAVIATE_API_KEY_VERBA") or os.getenv("WEAVIATE_API_KEY")
    
    return GraphQLClient(base_url, api_key)


# Import asyncio para sleep
import asyncio

