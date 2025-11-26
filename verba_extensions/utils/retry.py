"""
Utility genérica de retry com exponential backoff para APIs externas.

Fornece decorator e função helper para retry automático em chamadas de API
com tratamento de rate limits, timeouts e erros temporários.
"""

import asyncio
import random
from typing import Callable, List, Optional, TypeVar, Any, Dict
from functools import wraps
import aiohttp
import httpx
from wasabi import msg

T = TypeVar('T')


# Status codes que devem ser retryados
DEFAULT_RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]

# Exceções que devem ser retryadas
RETRYABLE_EXCEPTIONS = (
    asyncio.TimeoutError,
    aiohttp.ClientTimeout,
    aiohttp.ClientConnectionError,
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
)


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    retryable_status_codes: Optional[List[int]] = None,
    retryable_exceptions: Optional[tuple] = None,
    operation_name: str = "API call",
    *args,
    **kwargs
) -> Any:
    """
    Executa função async com retry e exponential backoff.
    
    Args:
        func: Função async a ser executada
        max_retries: Número máximo de tentativas (default: 3)
        base_delay: Delay base em segundos (default: 1.0)
        max_delay: Delay máximo em segundos (default: 60.0)
        jitter: Se True, adiciona jitter aleatório ao delay (default: True)
        retryable_status_codes: Lista de status codes HTTP que devem ser retryados
        retryable_exceptions: Tupla de exceções que devem ser retryadas
        operation_name: Nome da operação para logging (default: "API call")
        *args, **kwargs: Argumentos para a função
    
    Returns:
        Resultado da função
    
    Raises:
        Exception: Se todas as tentativas falharem
    """
    if retryable_status_codes is None:
        retryable_status_codes = DEFAULT_RETRYABLE_STATUS_CODES
    
    if retryable_exceptions is None:
        retryable_exceptions = RETRYABLE_EXCEPTIONS
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Executa função
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Sucesso - retorna resultado
            if attempt > 0:
                msg.good(f"[RETRY] {operation_name} bem-sucedida apos {attempt + 1} tentativa(s)")
            return result
            
        except Exception as e:
            last_error = e
            
            # Verifica se é exceção retryável
            is_retryable = False
            status_code = None
            
            # Verifica exceções retryáveis
            if isinstance(e, retryable_exceptions):
                is_retryable = True
            # Verifica ClientResponseError (aiohttp)
            elif isinstance(e, aiohttp.ClientResponseError):
                status_code = e.status
                is_retryable = status_code in retryable_status_codes
            # Verifica HTTPStatusError (httpx)
            elif isinstance(e, httpx.HTTPStatusError):
                status_code = e.response.status_code
                is_retryable = status_code in retryable_status_codes
            # Verifica HTTPError genérico
            elif hasattr(e, 'status') or hasattr(e, 'status_code'):
                status_code = getattr(e, 'status', None) or getattr(e, 'status_code', None)
                if status_code:
                    is_retryable = status_code in retryable_status_codes
            
            # Se não é retryável ou é última tentativa, levanta exceção
            if not is_retryable or attempt == max_retries - 1:
                if not is_retryable:
                    msg.fail(f"[RETRY] {operation_name} falhou com erro nao-retryavel: {type(e).__name__}: {str(e)}")
                else:
                    msg.fail(f"[RETRY] {operation_name} falhou apos {max_retries} tentativas: {type(e).__name__}: {str(e)}")
                raise
            
            # Calcula delay com exponential backoff
            delay = min(base_delay * (2 ** attempt), max_delay)
            
            # Adiciona jitter se habilitado
            if jitter:
                jitter_amount = random.uniform(0, delay * 0.1)  # 10% jitter
                delay += jitter_amount
            
            # Log da tentativa
            error_msg = f"{type(e).__name__}"
            if status_code:
                error_msg += f" (HTTP {status_code})"
            else:
                error_msg += f": {str(e)[:100]}"
            
            msg.warn(
                f"[RETRY] {operation_name} falhou (tentativa {attempt + 1}/{max_retries}): {error_msg}. "
                f"Tentando novamente em {delay:.2f}s..."
            )
            
            # Aguarda antes de retry
            await asyncio.sleep(delay)
    
    # Se chegou aqui, todas as tentativas falharam
    raise Exception(f"{operation_name} falhou após {max_retries} tentativas: {str(last_error)}")


def retry_api_call(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    retryable_status_codes: Optional[List[int]] = None,
    retryable_exceptions: Optional[tuple] = None,
    operation_name: Optional[str] = None,
):
    """
    Decorator para aplicar retry com exponential backoff em funções async.
    
    Args:
        max_retries: Número máximo de tentativas (default: 3)
        base_delay: Delay base em segundos (default: 1.0)
        max_delay: Delay máximo em segundos (default: 60.0)
        jitter: Se True, adiciona jitter aleatório ao delay (default: True)
        retryable_status_codes: Lista de status codes HTTP que devem ser retryados
        retryable_exceptions: Tupla de exceções que devem ser retryadas
        operation_name: Nome da operação para logging (usa nome da função se None)
    
    Exemplo:
        @retry_api_call(max_retries=3, base_delay=2.0, operation_name="Cohere API")
        async def call_cohere_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__name__}()"
            return await retry_with_backoff(
                func,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                jitter=jitter,
                retryable_status_codes=retryable_status_codes,
                retryable_exceptions=retryable_exceptions,
                operation_name=op_name,
                *args,
                **kwargs
            )
        return wrapper
    return decorator


async def retry_http_request(
    session: Any,
    method: str,
    url: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    retryable_status_codes: Optional[List[int]] = None,
    operation_name: Optional[str] = None,
    **request_kwargs
) -> Any:
    """
    Helper para fazer requisição HTTP com retry automático.
    
    Funciona com aiohttp.ClientSession e httpx.AsyncClient.
    
    Args:
        session: aiohttp.ClientSession ou httpx.AsyncClient
        method: Método HTTP ('GET', 'POST', etc.)
        url: URL da requisição
        max_retries: Número máximo de tentativas (default: 3)
        base_delay: Delay base em segundos (default: 1.0)
        max_delay: Delay máximo em segundos (default: 60.0)
        jitter: Se True, adiciona jitter aleatório ao delay (default: True)
        retryable_status_codes: Lista de status codes HTTP que devem ser retryados
        operation_name: Nome da operação para logging
        **request_kwargs: Argumentos adicionais para a requisição (headers, json, data, etc.)
    
    Returns:
        Response object (aiohttp.ClientResponse ou httpx.Response)
    
    Exemplo:
        async with aiohttp.ClientSession() as session:
            response = await retry_http_request(
                session, 'POST', 'https://api.example.com/endpoint',
                json={'data': 'value'},
                max_retries=3,
                base_delay=2.0,
                operation_name="Example API"
            )
    """
    if retryable_status_codes is None:
        retryable_status_codes = DEFAULT_RETRYABLE_STATUS_CODES
    
    op_name = operation_name or f"{method} {url}"
    
    async def make_request():
        # Detecta tipo de session
        if isinstance(session, aiohttp.ClientSession):
            async with session.request(method, url, **request_kwargs) as response:
                response.raise_for_status()
                return response
        elif isinstance(session, httpx.AsyncClient):
            response = await session.request(method, url, **request_kwargs)
            response.raise_for_status()
            return response
        else:
            raise ValueError(f"Tipo de session não suportado: {type(session)}")
    
    return await retry_with_backoff(
        make_request,
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        jitter=jitter,
        retryable_status_codes=retryable_status_codes,
        operation_name=op_name
    )

