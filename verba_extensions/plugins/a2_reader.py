"""
Reader Plugin A2 - Ingestão direta de URLs e Results
Integrado na UI original do Verba
"""

import os
import json
import hashlib
from typing import List
import httpx
import trafilatura
import re
from urllib.parse import urlparse

from goldenverba.components.document import Document
from goldenverba.components.interfaces import Reader
from goldenverba.server.types import FileConfig
from goldenverba.components.types import InputConfig
from wasabi import msg

def sha1(s: str) -> str:
    """Hash SHA1"""
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()

def url_host(u: str) -> str:
    """Extrai hostname"""
    try:
        return urlparse(u).netloc.lower()
    except:
        return ""

async def fetch_url_to_text(url: str):
    """Baixa URL e extrai texto"""
    meta = {"title": "", "language": "und", "published_at": ""}
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            r = await client.get(url, headers={"User-Agent": "Verba-A2/1.0"})
            html = r.text
        
        title_match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        if title_match:
            meta["title"] = re.sub(r"\s+", " ", title_match.group(1)).strip()
        
        text = trafilatura.extract(html, include_comments=False, favor_recall=True) or ""
        
        lang_match = re.search(r'lang=["\']([a-zA-Z-]+)["\']', html)
        if lang_match:
            meta["language"] = lang_match.group(1).lower()
        
        return text, meta
    except Exception as e:
        return f"Erro ao buscar {url}: {str(e)}", meta


class A2URLReader(Reader):
    """
    Reader para ingestão de URLs diretamente
    Aparece na UI do Verba como opção de Reader
    """
    
    def __init__(self):
        super().__init__()
        self.name = "A2 URL Ingestor"
        self.type = "URL"
        self.description = "Ingere URLs diretamente (com ETL opcional pós-chunking)"
        
        self.config["URLs"] = InputConfig(
            type="multi",
            value="",
            description="Lista de URLs para ingerir (uma por linha)",
            values=[],
        )
        self.config["Language Hint"] = InputConfig(
            type="text",
            value="pt",
            description="Idioma padrão (pt, en, etc.)",
            values=[],
        )
        self.config["Enable ETL"] = InputConfig(
            type="bool",
            value=True,
            description="Executar ETL A2 após chunking (NER + Section Scope)",
            values=[],
        )
    
    async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
        """Carrega URLs e retorna Documents"""
        urls_str = config.get("URLs", {}).value if hasattr(config.get("URLs", {}), 'value') else ""
        urls = [u.strip() for u in urls_str.split("\n") if u.strip()]
        language_hint = config.get("Language Hint", {}).value if hasattr(config.get("Language Hint", {}), 'value') else "pt"
        enable_etl = config.get("Enable ETL", {}).value if hasattr(config.get("Enable ETL", {}), 'value') else True
        
        documents = []
        
        for url in urls:
            try:
                text, meta = await fetch_url_to_text(url)
                if not text:
                    text = f"(Stub) conteúdo não extraído; URL: {url}"
                
                # Cria Document no formato Verba
                doc = Document(
                    title=meta.get("title") or url,
                    content=text,
                    source=url,
                    meta={
                        "url": url,
                        "title": meta.get("title", ""),
                        "language": meta.get("language") or language_hint,
                        "source_domain": url_host(url),
                        "enable_etl": enable_etl,  # Flag para hook posterior
                    }
                )
                
                documents.append(doc)
                msg.good(f"URL carregada: {url}")
                
            except Exception as e:
                msg.fail(f"Erro ao carregar URL {url}: {str(e)}")
                continue
        
        return documents


class A2ResultsReader(Reader):
    """
    Reader para ingestão de results (conteúdo já extraído)
    Aceita JSON com array de results
    """
    
    def __init__(self):
        super().__init__()
        self.name = "A2 Results Ingestor"
        self.type = "FILE"
        self.extension = [".json"]
        self.description = "Ingere results JSON (content já extraído)"
        
        self.config["Results JSON"] = InputConfig(
            type="textarea",
            value='{"results": [{"url": "...", "content": "...", "title": "...", "metadata": {...}}]}',
            description="JSON com array de results",
            values=[],
        )
        self.config["Enable ETL"] = InputConfig(
            type="bool",
            value=True,
            description="Executar ETL A2 após chunking",
            values=[],
        )
    
    async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
        """Carrega results JSON e retorna Documents"""
        json_str = config.get("Results JSON", {}).value if hasattr(config.get("Results JSON", {}), 'value') else "{}"
        enable_etl = config.get("Enable ETL", {}).value if hasattr(config.get("Enable ETL", {}), 'value') else True
        
        try:
            data = json.loads(json_str)
            results = data.get("results", [])
        except Exception as e:
            msg.fail(f"Erro ao parsear JSON: {str(e)}")
            return []
        
        documents = []
        
        for item in results:
            try:
                url = item.get("url", "")
                content = item.get("content", "").strip()
                title = item.get("title", "")
                meta_dict = item.get("metadata", {})
                
                if not content:
                    content = f"(Stub) sem conteúdo; URL: {url}"
                
                doc = Document(
                    title=title or url,
                    content=content,
                    source=url,
                    meta={
                        "url": url,
                        "title": title,
                        "language": meta_dict.get("language", "pt"),
                        "source_domain": url_host(url),
                        "published_at": item.get("published_at", ""),
                        "enable_etl": enable_etl,
                    }
                )
                
                documents.append(doc)
                msg.good(f"Result carregado: {title or url}")
                
            except Exception as e:
                msg.fail(f"Erro ao processar result: {str(e)}")
                continue
        
        return documents


def register():
    """
    Registra plugins no sistema
    """
    return {
        'name': 'a2_readers',
        'version': '1.0.0',
        'description': 'Readers A2 para ingestão de URLs e Results',
        'readers': [A2URLReader(), A2ResultsReader()],
        'compatible_verba_version': '>=2.1.0',
    }

