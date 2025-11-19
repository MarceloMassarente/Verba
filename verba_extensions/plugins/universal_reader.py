"""
Reader Universal A2 - Aplica ETL automaticamente em qualquer conteúdo
Usa qualquer formato (PDF, DOCX, TXT, etc.) e garante ETL por chunk

INTEGRAÇÃO TIKA: Usa Tika quando disponível para melhor extração e metadados
"""

import os
import requests
import re
from typing import List, Optional
from html import unescape
from goldenverba.components.document import Document
from goldenverba.components.interfaces import Reader
from goldenverba.server.types import FileConfig
from goldenverba.components.types import InputConfig
from wasabi import msg


class UniversalA2Reader(Reader):
    """
    Reader Universal que aplica ETL A2 automaticamente
    
    Funciona como wrapper do Default Reader, mas:
    - Aceita qualquer formato (PDF, DOCX, TXT, JSON, CSV, Excel)
    - Garante que enable_etl=True em todos os documentos
    - ETL executa automaticamente após chunking (via hook)
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Universal A2 (ETL Automático)"
        self.type = "FILE"
        # Aceita todos os formatos do Default Reader
        self.extension = [
            ".txt", ".md", ".csv", ".json", ".pdf", 
            ".docx", ".xlsx", ".xls", ".html", ".htm"
        ]
        self.description = "Processa qualquer arquivo e aplica ETL A2 automaticamente (NER + Section Scope por chunk). Usa Tika quando disponível para melhor extração e metadados."
        
        self.config["Enable ETL"] = InputConfig(
            type="bool",
            value=True,  # Sempre True por padrão
            description="Aplicar ETL A2 automaticamente (NER + Section Scope)",
            values=[],
        )
        self.config["Language Hint"] = InputConfig(
            type="text",
            value="pt",
            description="Idioma padrão para NER (pt, en, etc.)",
            values=[],
        )
        
        self.config["Use Tika When Available"] = InputConfig(
            type="bool",
            value=True,
            description="Usar Tika quando disponível para melhor extração e metadados (PPTX, formatos complexos, etc.)",
            values=[],
        )
        
        self._tika_available = None
        self._tika_server = None
    
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
    
    async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
        """
        Carrega arquivo usando Default Reader ou Tika (quando disponível e benéfico)
        e garante ETL
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
        
        extension = fileConfig.extension.lower() if fileConfig.extension else ""
        
        # Tenta usar Tika primeiro se configurado e benéfico
        if use_tika and self._should_use_tika(extension, use_tika):
            try:
                msg.info(f"[UNIVERSAL-READER] Usando Tika para '{fileConfig.filename}' (formato: {extension})")
                
                # Decodifica conteúdo
                decoded_bytes = fileConfig.content if isinstance(fileConfig.content, bytes) else fileConfig.content.encode() if isinstance(fileConfig.content, str) else None
                if not decoded_bytes:
                    decoded_bytes = fileConfig.content.encode('utf-8') if hasattr(fileConfig, 'content') else b''
                
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
            msg.fail(f"[UNIVERSAL-READER] Erro ao carregar arquivo '{fileConfig.filename}': {str(e)}")
            msg.fail(f"Traceback completo:\n{error_trace}")
            raise


def register():
    """
    Registra plugin
    """
    return {
        'name': 'universal_a2_reader',
        'version': '1.0.0',
        'description': 'Reader Universal com ETL A2 automático para qualquer formato',
        'readers': [UniversalA2Reader()],
        'compatible_verba_version': '>=2.1.0',
    }

