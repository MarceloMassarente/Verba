"""Utilidades do ingestor"""

import hashlib
from urllib.parse import urlparse

def sha1(s: str) -> str:
    """Gera hash SHA1 de uma string"""
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()

def url_host(u: str) -> str:
    """Extrai hostname de uma URL"""
    try:
        return urlparse(u).netloc.lower()
    except:
        return ""

