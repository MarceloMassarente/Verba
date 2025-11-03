"""Fetcher de URLs - extração de conteúdo"""

import httpx
import trafilatura
import re
from typing import Tuple, Dict

async def fetch_url_to_text(url: str) -> Tuple[str, Dict]:
    """Baixa URL e extrai texto usando Trafilatura"""
    meta = {"title": "", "language": "und", "published_at": ""}
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            r = await client.get(url, headers={"User-Agent": "Verba-A2-Ingestor/1.0"})
            html = r.text
        
        # Extrai título
        title_match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        if title_match:
            meta["title"] = re.sub(r"\s+", " ", title_match.group(1)).strip()
        
        # Extrai texto com Trafilatura
        text = trafilatura.extract(html, include_comments=False, favor_recall=True) or ""
        
        # Detecta idioma
        lang_match = re.search(r'lang=["\']([a-zA-Z-]+)["\']', html)
        if lang_match:
            meta["language"] = lang_match.group(1).lower()
        
        return text, meta
    except Exception as e:
        return f"Erro ao buscar {url}: {str(e)}", meta

