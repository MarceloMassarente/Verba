"""
Aggregation Wrapper
Wrapper para aggregation do Weaviate com HTTP fallback

Aprende do RAG2: HTTP fallback quando gRPC falha para aggregation
"""

import os
from typing import Dict, Any, Optional, List
import httpx
from wasabi import msg


class AggregationWrapper:
    """
    Wrapper para aggregation com HTTP fallback.
    
    Usa HTTP REST API quando:
    - gRPC falha
    - SDK Python não suporta features avançadas
    - Aggregation requer queries complexas
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Inicializa AggregationWrapper.
        
        Args:
            base_url: URL base do Weaviate (se None, tenta obter de env vars)
            api_key: API key do Weaviate (se None, tenta obter de env vars)
        """
        if not base_url:
            base_url = os.getenv("WEAVIATE_URL_VERBA") or os.getenv("WEAVIATE_URL") or "http://localhost:8080"
        
        if not api_key:
            api_key = os.getenv("WEAVIATE_API_KEY_VERBA") or os.getenv("WEAVIATE_API_KEY")
        
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def aggregate_over_all(
        self,
        client,
        collection_name: str,
        group_by: Optional[List[str]] = None,
        total_count: bool = False,
        use_http_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Executa aggregation com fallback HTTP.
        
        Args:
            client: Cliente Weaviate (para tentar SDK primeiro)
            collection_name: Nome da collection
            group_by: Lista de propriedades para agrupar
            total_count: Se True, retorna total_count
            use_http_fallback: Se True, usa HTTP se SDK falhar
        
        Returns:
            Dict com resultados da aggregation
        """
        # Tentar via SDK primeiro
        if client and use_http_fallback:
            try:
                collection = client.collections.get(collection_name)
                result = await collection.aggregate.over_all(
                    group_by=group_by,
                    total_count=total_count
                )
                return result
            except Exception as e:
                error_str = str(e).lower()
                if use_http_fallback and ("grpc" in error_str or "not supported" in error_str):
                    msg.info(f"SDK falhou ({str(e)[:100]}), usando HTTP fallback para aggregation")
                    return await self._aggregate_via_http(
                        collection_name, group_by, total_count
                    )
                else:
                    # Re-raise se erro não é relacionado a gRPC/features
                    raise
        
        # Se não há cliente ou fallback desabilitado, usar HTTP diretamente
        return await self._aggregate_via_http(
            collection_name, group_by, total_count
        )
    
    async def _aggregate_via_http(
        self,
        collection_name: str,
        group_by: Optional[List[str]],
        total_count: bool
    ) -> Dict[str, Any]:
        """
        Executa aggregation via HTTP REST API.
        
        Args:
            collection_name: Nome da collection
            group_by: Lista de propriedades para agrupar
            total_count: Se True, retorna total_count
        
        Returns:
            Dict com resultados da aggregation
        """
        url = f"{self.base_url}/v1/objects/aggregate"
        
        # Construir payload
        payload = {
            "class": collection_name
        }
        
        if group_by:
            payload["groupBy"] = group_by
        
        if total_count:
            payload["fields"] = ["meta { count }"]
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
        except Exception as e:
            msg.warn(f"Erro ao executar aggregation via HTTP: {str(e)}")
            raise
    
    async def aggregate_with_filters(
        self,
        client,
        collection_name: str,
        filters: Optional[Any] = None,  # Weaviate Filter object
        group_by: Optional[List[str]] = None,
        total_count: bool = False,
        use_http_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Executa aggregation com filtros.
        
        Args:
            client: Cliente Weaviate
            collection_name: Nome da collection
            filters: Filtros Weaviate (Filter object)
            group_by: Lista de propriedades para agrupar
            total_count: Se True, retorna total_count
            use_http_fallback: Se True, usa HTTP se SDK falhar
        
        Returns:
            Dict com resultados da aggregation
        """
        # Tentar via SDK primeiro
        if client and use_http_fallback:
            try:
                collection = client.collections.get(collection_name)
                result = await collection.aggregate.over_all(
                    filters=filters,
                    group_by=group_by,
                    total_count=total_count
                )
                return result
            except Exception as e:
                error_str = str(e).lower()
                if use_http_fallback and ("grpc" in error_str or "not supported" in error_str):
                    msg.info(f"SDK falhou ({str(e)[:100]}), usando HTTP fallback para aggregation com filtros")
                    return await self._aggregate_via_http_with_filters(
                        collection_name, filters, group_by, total_count
                    )
                else:
                    raise
        
        # Fallback HTTP
        return await self._aggregate_via_http_with_filters(
            collection_name, filters, group_by, total_count
        )
    
    async def _aggregate_via_http_with_filters(
        self,
        collection_name: str,
        filters: Optional[Any],
        group_by: Optional[List[str]],
        total_count: bool
    ) -> Dict[str, Any]:
        """
        Executa aggregation com filtros via HTTP REST API.
        
        Args:
            collection_name: Nome da collection
            filters: Filtros Weaviate (Filter object)
            group_by: Lista de propriedades para agrupar
            total_count: Se True, retorna total_count
        
        Returns:
            Dict com resultados da aggregation
        """
        url = f"{self.base_url}/v1/objects/aggregate"
        
        # Construir payload
        payload = {
            "class": collection_name
        }
        
        # Converter filtros para formato HTTP
        if filters:
            try:
                if hasattr(filters, 'to_dict'):
                    filter_dict = filters.to_dict()
                elif hasattr(filters, '__dict__'):
                    filter_dict = filters.__dict__
                else:
                    filter_dict = filters
                
                payload["where"] = filter_dict
            except Exception as e:
                msg.warn(f"Erro ao converter filtros para HTTP: {str(e)}")
                # Continuar sem filtros
        
        if group_by:
            payload["groupBy"] = group_by
        
        if total_count:
            payload["fields"] = ["meta { count }"]
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
        except Exception as e:
            msg.warn(f"Erro ao executar aggregation com filtros via HTTP: {str(e)}")
            raise


def get_aggregation_wrapper(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> AggregationWrapper:
    """
    Factory function para obter instância do AggregationWrapper.
    
    Args:
        base_url: URL base do Weaviate (se None, tenta obter de env vars)
        api_key: API key do Weaviate (se None, tenta obter de env vars)
    
    Returns:
        Instância de AggregationWrapper
    """
    return AggregationWrapper(base_url, api_key)

