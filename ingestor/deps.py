"""Dependências do ingestor - conexão Weaviate"""

import os
import weaviate
from weaviate.classes.init import AdditionalConfig, Timeout

def get_weaviate():
    """Retorna cliente Weaviate configurado"""
    url = os.getenv("WEAVIATE_URL", "http://weaviate:8080")
    api_key = os.getenv("WEAVIATE_API_KEY")
    
    # Parse URL
    if url.startswith("http://"):
        host = url.replace("http://", "").split(":")[0]
        port = int(url.split(":")[-1]) if ":" in url else 8080
        secure = False
    elif url.startswith("https://"):
        host = url.replace("https://", "").split(":")[0]
        port = int(url.split(":")[-1]) if ":" in url else 443
        secure = True
    else:
        host = url.split(":")[0]
        port = int(url.split(":")[-1]) if ":" in url else 8080
        secure = False
    
    if api_key:
        return weaviate.connect_to_custom(
            http_host=host,
            http_port=port,
            http_secure=secure,
            auth_credentials=weaviate.auth.AuthApiKey(api_key),
            additional_config=AdditionalConfig(
                timeout=Timeout(init=60, query=30, insert=30)
            )
        )
    else:
        return weaviate.connect_to_local(
            host=host,
            port=port,
            skip_init_checks=True,
            additional_config=AdditionalConfig(
                timeout=Timeout(init=60, query=30, insert=30)
            )
        )

