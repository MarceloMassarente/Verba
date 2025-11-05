"""
Reader Tika - Usa Apache Tika para extração de documentos
Funciona como fallback para formatos não suportados ou melhor extração

⚠️ PATCH/MONKEY PATCH - Documentado em verba_extensions/patches/README_PATCHES.md

Este plugin:
1. Adiciona um Reader que usa Tika para todos os formatos
2. Pode ser usado como alternativa ao BasicReader
3. Permite extrair metadados dos documentos
"""

import os
import requests
import re
from typing import List, Optional
from html import unescape
from goldenverba.components.document import Document, create_document
from goldenverba.components.interfaces import Reader
from goldenverba.server.types import FileConfig
from goldenverba.components.types import InputConfig
from wasabi import msg


class TikaReader(Reader):
    """
    Reader que usa Apache Tika para extração de documentos
    Suporta 1000+ formatos e extrai metadados
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Tika Reader (Multi-Formato)"
        self.type = "FILE"
        self.description = "Usa Apache Tika para extrair texto e metadados de 1000+ formatos (PDF, DOCX, PPTX, ODT, RTF, etc.)"
        
        # Tika suporta muitos formatos
        self.extension = [
            ".pdf", ".docx", ".doc", ".pptx", ".ppt", 
            ".odt", ".ods", ".odp", ".rtf", ".txt",
            ".xlsx", ".xls", ".csv", ".html", ".htm",
            ".xml", ".json", ".md", ".epub", ".pages"
        ]
        
        # Configuração do servidor Tika
        self.config["Tika Server URL"] = InputConfig(
            type="text",
            value=os.getenv("TIKA_SERVER_URL", "http://localhost:9998"),
            description="URL do servidor Apache Tika",
            values=[],
        )
        
        self.config["Extract Metadata"] = InputConfig(
            type="bool",
            value=True,
            description="Extrair metadados dos documentos (autor, título, data, etc.)",
            values=[],
        )
        
        self._tika_server = None
        self._tika_available = None
    
    def _get_tika_server(self, config: dict) -> Optional[str]:
        """Obtém URL do servidor Tika do config"""
        def get_config_value(key: str, default):
            config_item = config.get(key, {})
            if isinstance(config_item, dict):
                return config_item.get("value", default)
            elif hasattr(config_item, 'value'):
                return config_item.value
            return default
        
        return get_config_value("Tika Server URL", os.getenv("TIKA_SERVER_URL", "http://localhost:9998"))
    
    def _check_tika_available(self, tika_server: str) -> bool:
        """Verifica se servidor Tika está disponível"""
        if self._tika_available is not None:
            return self._tika_available
        
        try:
            response = requests.get(f"{tika_server}/tika", timeout=5)
            self._tika_available = response.status_code in [200, 405]  # 405 = método não permitido mas servidor ativo
            return self._tika_available
        except:
            self._tika_available = False
            return False
    
    def _extract_with_tika(self, content: bytes, tika_server: str, extract_metadata: bool = True):
        """Extrai texto e metadados usando Tika"""
        try:
            # Extrai texto
            text_url = f"{tika_server}/tika"
            text_response = requests.put(
                text_url,
                data=content,
                headers={'Content-Type': 'application/octet-stream'},
                timeout=120
            )
            
            if text_response.status_code != 200:
                raise Exception(f"Erro ao extrair texto: HTTP {text_response.status_code}")
            
            text_raw = text_response.text
            
            # Se vem em HTML, extrai texto real
            if text_raw.startswith('<?xml') or text_raw.startswith('<html'):
                text = re.sub(r'<[^>]+>', ' ', text_raw)
                text = unescape(text)
                text = ' '.join(text.split())
            else:
                text = text_raw
            
            # Extrai metadados se solicitado
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
                            # Parseia CSV
                            lines = metadata_text.strip().split('\n')
                            for line in lines:
                                if ',' in line:
                                    parts = line.split(',', 1)
                                    if len(parts) == 2:
                                        key = parts[0].strip()
                                        value = parts[1].strip()
                                        if key and value:
                                            metadata[key] = value
                            
                            # Se não encontrou, tenta HTML
                            if not metadata and '<meta' in metadata_text:
                                meta_tags = re.findall(
                                    r'<meta\s+name=["\']([^"\']+)["\']\s+content=["\']([^"\']+)["\']', 
                                    metadata_text
                                )
                                for key, value in meta_tags:
                                    metadata[key] = value
            
            return text, metadata
            
        except Exception as e:
            raise Exception(f"Erro ao extrair com Tika: {str(e)}")
    
    async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
        """Carrega arquivo usando Tika"""
        try:
            # Obtém configuração
            tika_server = self._get_tika_server(config)
            extract_metadata = config.get("Extract Metadata", {}).get("value", True) if isinstance(config.get("Extract Metadata"), dict) else True
            
            # Verifica se Tika está disponível
            if not self._check_tika_available(tika_server):
                raise Exception(f"Servidor Tika não está disponível em {tika_server}")
            
            # Decodifica conteúdo
            decoded_bytes = fileConfig.content if isinstance(fileConfig.content, bytes) else fileConfig.content.encode() if isinstance(fileConfig.content, str) else None
            
            if not decoded_bytes:
                decoded_bytes = fileConfig.content.encode('utf-8') if hasattr(fileConfig, 'content') else b''
            
            # Extrai com Tika
            msg.info(f"[TIKA] Extraindo '{fileConfig.filename}' com Tika...")
            text, metadata = self._extract_with_tika(decoded_bytes, tika_server, extract_metadata)
            
            if not text:
                msg.warn(f"[TIKA] Nenhum texto extraído de '{fileConfig.filename}'")
                return []
            
            # Cria documento
            document = create_document(text, fileConfig)
            
            # Adiciona metadados ao documento se disponíveis
            if metadata and hasattr(document, 'meta'):
                if document.meta is None:
                    document.meta = {}
                
                # Adiciona metadados importantes ao meta do documento
                important_keys = ['title', 'author', 'creator', 'producer', 'subject', 'keywords', 'created', 'modified']
                for key in important_keys:
                    # Tenta diferentes variações do nome
                    for meta_key in [key, f'dc:{key}', f'pdf:docinfo:{key}', f'xmp:{key}']:
                        if meta_key in metadata and metadata[meta_key]:
                            document.meta[f'tika_{key}'] = metadata[meta_key]
                            break
                
                # Adiciona todos os metadados em um campo separado
                document.meta['tika_metadata'] = metadata
                
                msg.info(f"[TIKA] Metadados extraídos: {len(metadata)} campos")
            
            msg.good(f"[TIKA] Documento '{fileConfig.filename}' extraído: {len(text)} caracteres")
            return [document]
            
        except Exception as e:
            msg.fail(f"[TIKA] Erro ao processar '{fileConfig.filename}': {str(e)}")
            import traceback
            msg.warn(f"Traceback: {traceback.format_exc()}")
            raise


def register():
    """Registra plugin"""
    return {
        'name': 'tika_reader',
        'version': '1.0.0',
        'description': 'Reader usando Apache Tika para suporte a 1000+ formatos e extração de metadados',
        'readers': [TikaReader()],
        'compatible_verba_version': '>=2.1.0',
    }

