"""
Reader Universal A2 - Verdadeiramente Universal
Aceita ARQUIVOS e URLs, aplica ETL automaticamente em qualquer conteúdo

FONTES SUPORTADAS:
- Arquivos: PDF, DOCX, TXT, JSON, CSV, Excel, HTML, Markdown
- URLs: Qualquer página web (extração via Trafilatura)
- JSON Results: Formato {"results": [...]} para pipelines externas

INTEGRAÇÃO TIKA: Usa Tika quando disponível para melhor extração e metadados
INTEGRAÇÃO DOCLING: Usa Docling quando disponível para parsing estruturado com mapeamento por página
"""

import os
import requests
import re
import base64
import json
import hashlib
from typing import List, Optional, Dict, Any
from html import unescape
from urllib.parse import urlparse
from goldenverba.components.document import Document
from goldenverba.components.interfaces import Reader
from goldenverba.server.types import FileConfig
from goldenverba.components.types import InputConfig
from wasabi import msg

# Web scraping
try:
    import httpx
    import trafilatura
    WEBSCRAPING_AVAILABLE = True
except ImportError:
    WEBSCRAPING_AVAILABLE = False
    msg.warn("⚠️ Web scraping não disponível. Instale: pip install httpx trafilatura")


def _url_host(url: str) -> str:
    """Extrai hostname de uma URL"""
    try:
        return urlparse(url).netloc.lower()
    except:
        return ""


async def _fetch_url_to_text(url: str) -> tuple:
    """Baixa URL e extrai texto usando Trafilatura"""
    meta = {"title": "", "language": "und", "published_at": ""}
    
    if not WEBSCRAPING_AVAILABLE:
        return f"Erro: httpx/trafilatura não instalados", meta
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            r = await client.get(url, headers={"User-Agent": "Verba-Universal/1.0"})
            html = r.text
        
        # Extrai título
        title_match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        if title_match:
            meta["title"] = re.sub(r"\s+", " ", title_match.group(1)).strip()
        
        # Extrai texto limpo com Trafilatura
        text = trafilatura.extract(html, include_comments=False, favor_recall=True) or ""
        
        # Detecta idioma
        lang_match = re.search(r'lang=["\']([a-zA-Z-]+)["\']', html)
        if lang_match:
            meta["language"] = lang_match.group(1).lower()
        
        return text, meta
    except Exception as e:
        return f"Erro ao buscar {url}: {str(e)}", meta


class UniversalA2Reader(Reader):
    """
    Reader Verdadeiramente Universal com ETL A2 automático
    
    Suporta:
    - Arquivos: PDF, DOCX, TXT, JSON, CSV, Excel, HTML, Markdown
    - URLs: Páginas web (via Trafilatura)
    - JSON Results: Formato {"results": [...]} de pipelines externas
    
    Prioridade de extração:
    1. Docling (parsing estruturado) - se configurado
    2. Tika (multi-formato) - se disponível
    3. BasicReader (fallback padrão)
    4. Trafilatura (para URLs web)
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Universal A2 (Arquivos + URLs)"
        self.type = "BOTH"  # Aceita FILE e URL
        # Aceita todos os formatos
        self.extension = [
            ".txt", ".md", ".csv", ".json", ".pdf", 
            ".docx", ".pptx", ".ppt",  # Added PPTX/PPT support
            ".xlsx", ".xls", ".html", ".htm"
        ]
        self.description = (
            "Reader verdadeiramente universal: processa ARQUIVOS (PDF, DOCX, etc.) e URLs (páginas web). "
            "Aplica ETL A2 automaticamente (NER + Section Scope). "
            "Usa Docling/Tika quando disponível para melhor extração."
        )
        
        # === Configurações Gerais ===
        self.config["Enable ETL"] = InputConfig(
            type="bool",
            value=True,
            description="Aplicar ETL A2 automaticamente (NER + Section Scope)",
            values=[],
        )
        self.config["Language Hint"] = InputConfig(
            type="text",
            value="pt",
            description="Idioma padrão para NER (pt, en, etc.)",
            values=[],
        )
        
        # === Configurações para URLs ===
        self.config["URLs"] = InputConfig(
            type="multi",
            value="",
            description="Lista de URLs para ingerir (uma por linha). Deixe vazio se usar upload de arquivo.",
            values=[],
        )
        
        # === Configurações para Tika ===
        self.config["Use Tika When Available"] = InputConfig(
            type="bool",
            value=True,
            description="Usar Tika quando disponível para melhor extração e metadados (PPTX, formatos complexos, etc.)",
            values=[],
        )
        
        # === Configurações para Docling ===
        self.config["Use Docling When Available"] = InputConfig(
            type="bool",
            value=False,
            description="Usar Docling quando disponível para parsing estruturado com mapeamento por página (requer DOCLING_API_URL)",
            values=[],
        )
        
        self.config["Docling API URL"] = InputConfig(
            type="text",
            value=os.getenv("DOCLING_API_URL", ""),
            description="URL da API Docling (ex: https://api.docling.ai/v1) ou configure DOCLING_API_URL env var",
            values=[],
        )
        
        self.config["Docling API Key"] = InputConfig(
            type="password",
            value=os.getenv("DOCLING_API_KEY", ""),
            description="API Key do Docling (ou configure DOCLING_API_KEY env var)",
            values=[],
        )
        
        self._tika_available = None
        self._tika_server = None
        self._docling_available = None
        self._docling_api_url = None
    
    def _check_tika_available(self) -> bool:
        """Verifica se Tika está disponível"""
        if self._tika_available is not None:
            return self._tika_available
        
        try:
            tika_server = os.getenv("TIKA_SERVER_URL", "http://localhost:9998")
            self._tika_server = tika_server
            response = requests.get(f"{tika_server}/tika", timeout=5)
            self._tika_available = response.status_code in [200, 405]
            return self._tika_available
        except:
            self._tika_available = False
            return False
    
    def _should_use_tika(self, extension: str, use_tika: bool) -> bool:
        """Determina se deve usar Tika para este formato"""
        if not use_tika or not self._check_tika_available():
            return False
        
        # Formatos que se beneficiam muito do Tika
        tika_beneficial = ['.pptx', '.ppt', '.doc', '.rtf', '.odt', '.ods', '.odp', '.epub']
        if extension.lower() in tika_beneficial:
            return True
        
        # Para outros formatos, Tika pode ser útil se disponível (mas não obrigatório)
        # O fallback automático do BasicReader já cuida disso
        return False
    
    async def _extract_with_tika(self, content: bytes, extract_metadata: bool = True):
        """Extrai texto e metadados usando Tika (runs in executor to avoid blocking)"""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._extract_with_tika_sync, content, extract_metadata)

    def _extract_with_tika_sync(self, content: bytes, extract_metadata: bool = True):
        """Implementação síncrona da extração com Tika"""
        try:
            tika_server = self._tika_server or os.getenv("TIKA_SERVER_URL", "http://localhost:9998")
            
            # Extrai texto
            text_url = f"{tika_server}/tika"
            text_response = requests.put(
                text_url,
                data=content,
                headers={'Content-Type': 'application/octet-stream'},
                timeout=120
            )
            
            if text_response.status_code != 200:
                return None, None
            
            text_raw = text_response.text
            
            # Se vem em HTML, extrai texto real
            if text_raw.startswith('<?xml') or text_raw.startswith('<html'):
                text = re.sub(r'<[^>]+>', ' ', text_raw)
                text = unescape(text)
                text = ' '.join(text.split())
            else:
                text = text_raw
            
            # Extrai metadados
            metadata = {}
            if extract_metadata:
                meta_url = f"{tika_server}/meta"
                meta_response = requests.put(
                    meta_url,
                    data=content,
                    headers={'Content-Type': 'application/octet-stream'},
                    timeout=120
                )
                
                if meta_response.status_code == 200:
                    try:
                        metadata = meta_response.json()
                    except:
                        # Parseia formato CSV ou HTML
                        metadata_text = meta_response.text
                        if metadata_text:
                            lines = metadata_text.strip().split('\n')
                            for line in lines:
                                if ',' in line:
                                    parts = line.split(',', 1)
                                    if len(parts) == 2:
                                        key = parts[0].strip()
                                        value = parts[1].strip()
                                        if key and value:
                                            metadata[key] = value
                            
                            if not metadata and '<meta' in metadata_text:
                                meta_tags = re.findall(
                                    r'<meta\s+name=["\']([^"\']+)["\']\s+content=["\']([^"\']+)["\']', 
                                    metadata_text
                                )
                                for key, value in meta_tags:
                                    metadata[key] = value
            
            return text, metadata
            
        except Exception as e:
            msg.warn(f"[UNIVERSAL-READER] Erro ao usar Tika: {str(e)}")
            return None, None
    
    def _check_docling_available(self, api_url: str, api_key: str) -> bool:
        """Verifica se Docling está disponível"""
        if not api_url or not api_key:
            return False
        
        if self._docling_available is not None:
            return self._docling_available
        
        try:
            # Verifica se API está acessível (endpoint de health ou similar)
            # Por enquanto, apenas valida que URL e key estão configurados
            self._docling_available = bool(api_url and api_key)
            return self._docling_available
        except:
            self._docling_available = False
            return False
    
    def _should_use_docling(self, extension: str, use_docling: bool, api_url: str, api_key: str) -> bool:
        """Determina se deve usar Docling para este formato"""
        if not use_docling or not self._check_docling_available(api_url, api_key):
            return False
        
        # Formatos que se beneficiam muito do Docling (parsing estruturado)
        docling_beneficial = ['.pdf', '.pptx', '.ppt', '.docx', '.doc']
        if extension.lower() in docling_beneficial:
            return True
        
        return False
    
    async def _extract_with_docling(self, content: bytes, api_url: str, api_key: str):
        """
        Extrai conteúdo usando Docling API seguindo práticas recomendadas.
        Retorna (md_content, json_content, metadata) ou (None, None, None) em caso de erro.
        """
        import asyncio
        import aiohttp
        import base64
        import json
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._extract_with_docling_sync, content, api_url, api_key)
    
    def _extract_with_docling_sync(self, content: bytes, api_url: str, api_key: str):
        """Implementação síncrona da extração com Docling"""
        import requests
        import json
        import base64
        
        try:
            # Endpoint da API Docling
            # NOTA: Endpoint pode variar conforme versão da API Docling
            # Ajustar conforme documentação oficial se necessário
            parse_url = f"{api_url.rstrip('/')}/parse" if api_url else None
            if not parse_url:
                return None, None, None
            
            headers = {
                "Authorization": f"Bearer {api_key}",
            }
            
            # Prepara FormData com arquivo
            files = {
                "document": ("document", content, "application/octet-stream")
            }
            
            # Payload seguindo práticas recomendadas
            # Para multipart form-data, arrays podem precisar ser enviados como JSON string
            # ou como campos repetidos - ajustar conforme documentação da API Docling
            data = {
                "target_type": "inbody",
                "to_formats": json.dumps(["md", "json"]),  # JSON string para multipart
                "do_ocr": "true",
                "do_table_structure": "true",
                "table_mode": "accurate",
                "include_images": "false"
            }
            
            # NOTA: Se a API Docling aceita array direto, pode tentar:
            # data["to_formats"] = ["md", "json"]  # Array direto
            # Mas requests pode não serializar corretamente em multipart
            
            msg.info(f"[UNIVERSAL-READER] Chamando Docling API: {parse_url}")
            response = requests.post(parse_url, headers=headers, files=files, data=data, timeout=300)
            
            if response.status_code != 200:
                msg.warn(f"[UNIVERSAL-READER] Docling API retornou status {response.status_code}")
                return None, None, None
            
            result = response.json()
            
            # Extrai md_content e json_content
            document = result.get("document", {})
            md_content = document.get("md_content", "")
            json_content = document.get("json_content", {})
            
            if not md_content:
                msg.warn("[UNIVERSAL-READER] Docling não retornou md_content")
                return None, None, None
            
            # Prepara metadados
            metadata = {
                "source_api": "docling",
                "json_content": json_content,  # Preserva estrutura completa
            }
            
            # Extrai informações de páginas se disponível
            if json_content and isinstance(json_content, dict):
                pages = json_content.get("pages", {})
                texts = json_content.get("texts", [])
                groups = json_content.get("groups", [])
                tables = json_content.get("tables", [])
                
                metadata["docling_pages_count"] = len(pages)
                metadata["docling_texts_count"] = len(texts)
                metadata["docling_groups_count"] = len(groups)
                metadata["docling_tables_count"] = len(tables)
            
            msg.info(f"[UNIVERSAL-READER] Docling extraiu: {len(md_content)} caracteres (md), JSON com {len(json_content) if json_content else 0} chaves")
            
            return md_content, json_content, metadata
            
        except Exception as e:
            msg.warn(f"[UNIVERSAL-READER] Erro ao usar Docling: {str(e)}")
            import traceback
            msg.debug(f"Traceback Docling: {traceback.format_exc()}")
            return None, None, None
    
    def _map_content_by_page(self, json_content: dict, md_content: str) -> dict:
        """
        Mapeia conteúdo por página usando texts[].prov[].page_no.
        Retorna dict com {page_no: content_string}
        """
        if not json_content or not isinstance(json_content, dict):
            return {}
        
        texts = json_content.get("texts", [])
        pages = json_content.get("pages", {})
        
        if not texts:
            return {}
        
        # Agrupa textos por página
        texts_by_page = {}
        for text_item in texts:
            if not isinstance(text_item, dict):
                continue
            
            prov = text_item.get("prov", [])
            if not prov or not isinstance(prov, list):
                continue
            
            # Pega primeiro prov (pode ter múltiplos para o mesmo texto)
            first_prov = prov[0] if prov else {}
            if not isinstance(first_prov, dict):
                continue
            
            page_no = first_prov.get("page_no")
            if page_no is None:
                continue
            
            text_content = text_item.get("text") or text_item.get("orig", "")
            if not text_content:
                continue
            
            if page_no not in texts_by_page:
                texts_by_page[page_no] = []
            
            texts_by_page[page_no].append(text_content)
        
        # Cria conteúdo por página
        pages_content = {}
        for page_no in sorted(texts_by_page.keys()):
            page_texts = texts_by_page[page_no]
            pages_content[page_no] = "\n\n".join(page_texts)
        
        return pages_content
    
    # ════════════════════════════════════════════════════════════════════════════════
    # MÉTODOS PARA PROCESSAMENTO DE URLs (Web Scraping)
    # ════════════════════════════════════════════════════════════════════════════════
    
    async def _load_from_urls(self, urls_str: str, enable_etl: bool, language_hint: str) -> List[Document]:
        """
        Processa lista de URLs e retorna Documents.
        Usa Trafilatura para extração de texto limpo de páginas web.
        """
        if not WEBSCRAPING_AVAILABLE:
            msg.fail("[UNIVERSAL-READER] httpx/trafilatura não instalados. Instale: pip install httpx trafilatura")
            return []
        
        urls = [u.strip() for u in urls_str.split("\n") if u.strip() and u.strip().startswith(("http://", "https://"))]
        
        if not urls:
            msg.warn("[UNIVERSAL-READER] Nenhuma URL válida encontrada")
            return []
        
        msg.info(f"[UNIVERSAL-READER] Processando {len(urls)} URL(s)...")
        documents = []
        
        for url in urls:
            try:
                text, meta = await _fetch_url_to_text(url)
                
                if not text or text.startswith("Erro"):
                    msg.warn(f"[UNIVERSAL-READER] Falha ao extrair conteúdo de: {url}")
                    continue
                
                # Cria Document
                doc = Document(
                    title=meta.get("title") or url,
                    content=text,
                    source=url,
                    meta={
                        "url": url,
                        "title": meta.get("title", ""),
                        "language": meta.get("language") or language_hint,
                        "source_domain": _url_host(url),
                        "source_type": "url",
                        "enable_etl": enable_etl,
                    }
                )
                
                documents.append(doc)
                msg.good(f"[UNIVERSAL-READER] URL carregada: {url} ({len(text)} chars)")
                
            except Exception as e:
                msg.fail(f"[UNIVERSAL-READER] Erro ao processar URL {url}: {str(e)}")
                continue
        
        msg.good(f"[UNIVERSAL-READER] {len(documents)} documento(s) carregado(s) de URLs")
        return documents
    
    async def _try_load_json_results(self, fileConfig: FileConfig, enable_etl: bool, language_hint: str) -> Optional[List[Document]]:
        """
        Tenta carregar JSON no formato de Results (pipeline externa).
        Formato esperado: {"results": [{"url": "...", "content": "...", "title": "...", "metadata": {...}}]}
        
        Returns:
            Lista de Documents se for formato de results, None se não for.
        """
        try:
            # Decodifica conteúdo
            if isinstance(fileConfig.content, str):
                try:
                    content_str = base64.b64decode(fileConfig.content).decode('utf-8')
                except:
                    content_str = fileConfig.content
            elif isinstance(fileConfig.content, bytes):
                content_str = fileConfig.content.decode('utf-8')
            else:
                return None
            
            data = json.loads(content_str)
            
            # Verifica se é formato de results
            if not isinstance(data, dict) or "results" not in data:
                return None  # Não é formato de results, processa como JSON normal
            
            results = data.get("results", [])
            if not isinstance(results, list) or len(results) == 0:
                return None
            
            msg.info(f"[UNIVERSAL-READER] Detectado JSON de Results ({len(results)} itens)")
            documents = []
            
            for item in results:
                try:
                    url = item.get("url", "")
                    content = item.get("content", "").strip()
                    title = item.get("title", "")
                    meta_dict = item.get("metadata", {})
                    
                    if not content:
                        content = f"(Conteúdo vazio) URL: {url}"
                    
                    doc = Document(
                        title=title or url or f"Result {len(documents) + 1}",
                        content=content,
                        source=url,
                        meta={
                            "url": url,
                            "title": title,
                            "language": meta_dict.get("language", language_hint),
                            "source_domain": _url_host(url) if url else "",
                            "source_type": "json_results",
                            "published_at": item.get("published_at", ""),
                            "enable_etl": enable_etl,
                        }
                    )
                    
                    documents.append(doc)
                    msg.good(f"[UNIVERSAL-READER] Result carregado: {title or url}")
                    
                except Exception as e:
                    msg.warn(f"[UNIVERSAL-READER] Erro ao processar result: {str(e)}")
                    continue
            
            msg.good(f"[UNIVERSAL-READER] {len(documents)} documento(s) carregado(s) de JSON Results")
            return documents
            
        except json.JSONDecodeError:
            return None  # Não é JSON válido, processa como arquivo normal
        except Exception as e:
            msg.debug(f"[UNIVERSAL-READER] Erro ao tentar parsear como JSON Results: {str(e)}")
            return None
    
    # ════════════════════════════════════════════════════════════════════════════════
    # MÉTODO PRINCIPAL DE CARREGAMENTO
    # ════════════════════════════════════════════════════════════════════════════════
    
    async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
        """
        Carrega conteúdo de ARQUIVOS ou URLs e aplica ETL automaticamente.
        
        Prioridade:
        1. Se URLs configuradas → processa URLs via Trafilatura
        2. Se JSON de results → processa como pipeline externa
        3. Se arquivo → Docling > Tika > BasicReader
        """
        # Extrai valores do config de forma robusta
        def get_config_value(config_key: str, default_value):
            """Extrai valor do config de forma segura"""
            config_item = config.get(config_key, {})
            if isinstance(config_item, dict):
                return config_item.get("value", default_value)
            elif hasattr(config_item, 'value'):
                return config_item.value
            else:
                return default_value
        
        enable_etl = get_config_value("Enable ETL", True)
        language_hint = get_config_value("Language Hint", "pt")
        use_tika = get_config_value("Use Tika When Available", True)
        use_docling = get_config_value("Use Docling When Available", False)
        
        # Obtém configurações Docling
        docling_api_url = get_config_value("Docling API URL", os.getenv("DOCLING_API_URL", ""))
        docling_api_key = get_config_value("Docling API Key", os.getenv("DOCLING_API_KEY", ""))
        
        # ══════════════════════════════════════════════════════════════════════
        # MODO 1: Processa URLs (se configuradas)
        # ══════════════════════════════════════════════════════════════════════
        urls_str = get_config_value("URLs", "")
        if urls_str and urls_str.strip():
            return await self._load_from_urls(urls_str, enable_etl, language_hint)
        
        # ══════════════════════════════════════════════════════════════════════
        # MODO 2: Processa JSON de Results (formato pipeline externa)
        # ══════════════════════════════════════════════════════════════════════
        # Normaliza extensão para sempre ter ponto no início
        raw_ext = fileConfig.extension.lower() if fileConfig.extension else ""
        extension = f".{raw_ext}" if raw_ext and not raw_ext.startswith(".") else raw_ext
        
        if extension == ".json":
            json_docs = await self._try_load_json_results(fileConfig, enable_etl, language_hint)
            if json_docs:
                return json_docs
            # Se não era formato de results, continua para processamento normal
        
        # ══════════════════════════════════════════════════════════════════════
        # MODO 3: Processa Arquivo (Docling > Tika > BasicReader)
        # ══════════════════════════════════════════════════════════════════════
        
        # Prioridade: Docling > Tika > BasicReader
        # Docling primeiro (parsing estruturado mais poderoso)
        if use_docling and self._should_use_docling(extension, use_docling, docling_api_url, docling_api_key):
            try:
                msg.info(f"[UNIVERSAL-READER] Usando Docling para '{fileConfig.filename}' (formato: {extension})")
                
                # Decodifica conteúdo (fileConfig.content geralmente vem como base64 string)
                try:
                    if isinstance(fileConfig.content, str):
                        decoded_bytes = base64.b64decode(fileConfig.content)
                    elif isinstance(fileConfig.content, bytes):
                        decoded_bytes = fileConfig.content
                    else:
                        decoded_bytes = base64.b64decode(str(fileConfig.content))
                except Exception as e:
                    msg.warn(f"[UNIVERSAL-READER] Erro ao decodificar conteúdo: {str(e)}")
                    decoded_bytes = None
                
                if not decoded_bytes:
                    msg.warn("[UNIVERSAL-READER] Não foi possível decodificar conteúdo do arquivo, pulando Docling")
                else:
                    # Extrai com Docling
                    md_content, json_content, metadata = await self._extract_with_docling(
                        decoded_bytes, docling_api_url, docling_api_key
                    )
                    
                    if md_content:
                        # Cria documento
                        from goldenverba.components.document import create_document
                        document = create_document(md_content, fileConfig)
                        
                        # Adiciona metadados
                        if document.meta is None:
                            document.meta = {}
                        
                        # Adiciona metadados do Docling
                        if metadata:
                            document.meta.update(metadata)
                            if json_content:
                                # Mapeia conteúdo por página para uso futuro
                                pages_content = self._map_content_by_page(json_content, md_content)
                                if pages_content:
                                    document.meta["docling_pages_content"] = pages_content
                                    document.meta["docling_pages_mapped"] = len(pages_content)
                            msg.info(f"[UNIVERSAL-READER] Metadados Docling extraídos: {len(metadata)} campos")
                        
                        # Configura ETL
                        document.meta["enable_etl"] = enable_etl
                        document.meta["language"] = document.meta.get("language", language_hint)
                        
                        msg.good(f"[UNIVERSAL-READER] Documento extraído via Docling: {len(md_content)} caracteres (md)")
                        return [document]
                    else:
                        msg.warn(f"[UNIVERSAL-READER] Docling não extraiu conteúdo, tentando Tika/BasicReader...")
                
            except Exception as e:
                msg.warn(f"[UNIVERSAL-READER] Erro ao usar Docling, tentando Tika/BasicReader: {str(e)}")
        
        # Formatos que se beneficiam muito do Tika (aviso especial se não disponível)
        tika_beneficial_formats = ['.pptx', '.ppt', '.doc', '.rtf', '.odt', '.ods', '.odp', '.epub']
        ext_lower = extension.lower() if extension else ""
        
        # Avisa se Tika seria útil mas não está disponível
        if ext_lower in tika_beneficial_formats and not self._check_tika_available():
            msg.warn(f"[UNIVERSAL-READER] Tika não disponível para {ext_lower}. Usando BasicReader (requer python-pptx/python-docx instalados).")
        
        # Tenta usar Tika se Docling não foi usado e está configurado
        if use_tika and self._should_use_tika(extension, use_tika):
            try:
                msg.info(f"[UNIVERSAL-READER] Usando Tika para '{fileConfig.filename}' (formato: {extension})")
                
                # Decodifica conteúdo (fileConfig.content geralmente vem como base64 string)
                try:
                    if isinstance(fileConfig.content, str):
                        decoded_bytes = base64.b64decode(fileConfig.content)
                    elif isinstance(fileConfig.content, bytes):
                        decoded_bytes = fileConfig.content
                    else:
                        decoded_bytes = base64.b64decode(str(fileConfig.content))
                except Exception as decode_err:
                    msg.warn(f"[UNIVERSAL-READER] Erro ao decodificar conteúdo para Tika: {str(decode_err)}")
                    decoded_bytes = None
                
                if not decoded_bytes:
                    msg.warn(f"[UNIVERSAL-READER] Não foi possível decodificar conteúdo para Tika, tentando BasicReader...")
                    raise ValueError("Conteúdo não pode ser decodificado")
                
                # Extrai com Tika (agora async/thread-safe)
                text, metadata = await self._extract_with_tika(decoded_bytes, extract_metadata=True)
                
                if text:
                    # Cria documento
                    from goldenverba.components.document import create_document
                    document = create_document(text, fileConfig)
                    
                    # Adiciona metadados
                    if document.meta is None:
                        document.meta = {}
                    
                    # Adiciona metadados do Tika
                    if metadata:
                        important_keys = ['title', 'author', 'creator', 'producer', 'subject', 'keywords', 'created', 'modified']
                        for key in important_keys:
                            for meta_key in [key, f'dc:{key}', f'pdf:docinfo:{key}', f'xmp:{key}']:
                                if meta_key in metadata and metadata[meta_key]:
                                    document.meta[f'tika_{key}'] = metadata[meta_key]
                                    break
                        document.meta['tika_metadata'] = metadata
                        msg.info(f"[UNIVERSAL-READER] Metadados extraídos: {len(metadata)} campos")
                    
                    # Configura ETL
                    document.meta["enable_etl"] = enable_etl
                    document.meta["language"] = document.meta.get("language", language_hint)
                    
                    msg.good(f"[UNIVERSAL-READER] Documento extraído via Tika: {len(text)} caracteres")
                    return [document]
                else:
                    msg.warn(f"[UNIVERSAL-READER] Tika não extraiu texto, tentando BasicReader...")
            except Exception as e:
                msg.warn(f"[UNIVERSAL-READER] Erro ao usar Tika, tentando BasicReader: {str(e)}")
        
        # Fallback para BasicReader (que também usa Tika como fallback se necessário)
        try:
            from goldenverba.components.reader.BasicReader import BasicReader
            default_reader = BasicReader()
        except ImportError as e:
            msg.fail(f"Default Reader não disponível: {str(e)}")
            raise ImportError(f"Failed to import BasicReader: {str(e)}")
        
        # Carrega usando Default Reader (suporta PDF, DOCX, TXT, etc.)
        # O patch Tika fallback garante que formatos não suportados usem Tika automaticamente
        try:
            msg.info(f"[UNIVERSAL-READER] Carregando '{fileConfig.filename}' com BasicReader...")
            documents = await default_reader.load(config, fileConfig)
            
            if not documents:
                msg.warn(f"[UNIVERSAL-READER] Nenhum documento foi carregado de {fileConfig.filename}")
                return []
            
            # Garante que todos os documentos tenham enable_etl=True
            for doc in documents:
                if not hasattr(doc, 'meta') or doc.meta is None:
                    doc.meta = {}
                
                # Marca para ETL
                doc.meta["enable_etl"] = enable_etl
                doc.meta["language"] = doc.meta.get("language", language_hint)
                
                msg.info(f"[UNIVERSAL-READER] Documento '{doc.title}' preparado - enable_etl={enable_etl}, language={language_hint}")
            
            msg.good(f"[UNIVERSAL-READER] {len(documents)} documento(s) carregado(s) com ETL habilitado")
            return documents
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            
            # Mensagem específica para formatos que precisam de Tika ou bibliotecas específicas
            ext_lower = extension.lower() if extension else ""
            if ext_lower in ['.pptx', '.ppt']:
                tika_available = self._check_tika_available()
                if not tika_available:
                    msg.fail(f"[UNIVERSAL-READER] PPTX requer 'python-pptx' ou servidor Tika!")
                    msg.fail(f"[UNIVERSAL-READER] Soluções: 1) pip install python-pptx OU 2) Configurar TIKA_SERVER_URL")
                    raise ImportError(
                        f"Falha ao processar '{fileConfig.filename}': "
                        f"PPTX requer 'python-pptx' instalado ou servidor Tika configurado (TIKA_SERVER_URL). "
                        f"Erro original: {str(e)}"
                    )
            
            msg.fail(f"[UNIVERSAL-READER] Erro ao carregar arquivo '{fileConfig.filename}': {str(e)}")
            msg.fail(f"Traceback completo:\n{error_trace}")
            raise


def register():
    """
    Registra plugin Universal A2 Reader
    
    Substitui:
    - a2_reader.py (A2URLReader, A2ResultsReader) - funcionalidades integradas
    - tika_reader.py - funcionalidade integrada como opção
    """
    return {
        'name': 'universal_a2_reader',
        'version': '2.0.0',
        'description': 'Reader Verdadeiramente Universal: Arquivos (PDF, DOCX, etc.) + URLs (web scraping) + JSON Results. ETL A2 automático.',
        'readers': [UniversalA2Reader()],
        'compatible_verba_version': '>=2.1.0',
    }

