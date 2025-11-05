"""
Patch: Integra Tika como fallback no BasicReader
Permite usar Tika quando métodos nativos falham ou para formatos não suportados

⚠️ PATCH/MONKEY PATCH - Documentado em verba_extensions/patches/README_PATCHES.md

Este patch modifica BasicReader para usar Tika como fallback quando:
1. Método nativo falha (ex: PDF complexo)
2. Formato não é suportado (ex: PPTX)
3. Usuário quer extrair metadados

Aplicado via: verba_extensions/startup.py (durante inicialização)
"""

import os
from typing import Optional
from wasabi import msg


def patch_basic_reader_with_tika_fallback():
    """
    Aplica patch no BasicReader para usar Tika como fallback
    """
    try:
        from goldenverba.components.reader.BasicReader import BasicReader
        
        # Guarda métodos originais
        original_load_pdf = BasicReader.load_pdf_file
        original_load_docx = BasicReader.load_docx_file
        original_load = BasicReader.load
        
        def _extract_with_tika(content: bytes, tika_server: str, extract_metadata: bool = False):
            """Helper para extrair com Tika"""
            try:
                import requests
                import re
                from html import unescape
                
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
                
                # Extrai metadados se solicitado
                metadata = None
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
                                metadata = {}
                                lines = metadata_text.strip().split('\n')
                                for line in lines:
                                    if ',' in line:
                                        parts = line.split(',', 1)
                                        if len(parts) == 2:
                                            key = parts[0].strip()
                                            value = parts[1].strip()
                                            if key and value:
                                                metadata[key] = value
                
                return text, metadata
                
            except Exception as e:
                msg.warn(f"[TIKA-FALLBACK] Erro ao usar Tika: {str(e)}")
                return None, None
        
        async def patched_load_pdf_file(self, decoded_bytes: bytes) -> str:
            """Tenta método nativo primeiro, depois Tika como fallback"""
            try:
                # Tenta método original
                return await original_load_pdf(self, decoded_bytes)
            except Exception as e:
                msg.warn(f"[TIKA-FALLBACK] PDF nativo falhou, tentando Tika: {str(e)}")
                
                # Fallback para Tika
                tika_server = os.getenv("TIKA_SERVER_URL", "http://localhost:9998")
                text, metadata = _extract_with_tika(decoded_bytes, tika_server)
                
                if text:
                    msg.good("[TIKA-FALLBACK] PDF extraído com sucesso via Tika")
                    return text
                else:
                    # Re-raise erro original se Tika também falhar
                    raise e
        
        async def patched_load_docx_file(self, decoded_bytes: bytes) -> str:
            """Tenta método nativo primeiro, depois Tika como fallback"""
            try:
                # Tenta método original
                return await original_load_docx(self, decoded_bytes)
            except Exception as e:
                msg.warn(f"[TIKA-FALLBACK] DOCX nativo falhou, tentando Tika: {str(e)}")
                
                # Fallback para Tika
                tika_server = os.getenv("TIKA_SERVER_URL", "http://localhost:9998")
                text, metadata = _extract_with_tika(decoded_bytes, tika_server)
                
                if text:
                    msg.good("[TIKA-FALLBACK] DOCX extraído com sucesso via Tika")
                    return text
                else:
                    # Re-raise erro original se Tika também falhar
                    raise e
        
        async def patched_load(self, config: dict, fileConfig) -> list:
            """Tenta método nativo primeiro, depois Tika para formatos não suportados"""
            try:
                # Tenta método original
                return await original_load(self, config, fileConfig)
            except (ValueError, ImportError) as e:
                # Se erro é "Unsupported file extension" ou falta de biblioteca
                if "Unsupported" in str(e) or "not installed" in str(e) or "not available" in str(e):
                    msg.info(f"[TIKA-FALLBACK] Formato não suportado nativamente, tentando Tika: {fileConfig.extension}")
                    
                    # Fallback para Tika
                    tika_server = os.getenv("TIKA_SERVER_URL", "http://localhost:9998")
                    
                    # Verifica se Tika está disponível
                    try:
                        import requests
                        response = requests.get(f"{tika_server}/tika", timeout=5)
                        if response.status_code not in [200, 405]:
                            raise Exception("Tika não disponível")
                    except:
                        msg.warn(f"[TIKA-FALLBACK] Tika não disponível em {tika_server}")
                        raise e
                    
                    # Decodifica conteúdo
                    decoded_bytes = fileConfig.content if isinstance(fileConfig.content, bytes) else fileConfig.content.encode()
                    
                    # Extrai com Tika
                    text, metadata = _extract_with_tika(decoded_bytes, tika_server, extract_metadata=True)
                    
                    if text:
                        msg.good(f"[TIKA-FALLBACK] Arquivo '{fileConfig.filename}' extraído com sucesso via Tika")
                        from goldenverba.components.document import create_document
                        return [create_document(text, fileConfig)]
                    else:
                        raise e
                else:
                    # Re-raise erro original se não for formato não suportado
                    raise e
        
        # Aplica patches
        BasicReader.load_pdf_file = patched_load_pdf_file
        BasicReader.load_docx_file = patched_load_docx_file
        BasicReader.load = patched_load
        
        msg.good("Patch Tika fallback aplicado ao BasicReader")
        return True
        
    except Exception as e:
        msg.warn(f"Patch Tika fallback não aplicado: {str(e)}")
        return False


def patch_verba_manager():
    """Aplica patch adicional se necessário"""
    # Placeholder para futuras extensões
    pass

