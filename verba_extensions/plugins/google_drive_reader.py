"""
Google Drive Reader - Importa arquivos do Google Drive com ETL A2 automático

Este plugin permite importar arquivos diretamente do Google Drive para o Verba,
com suporte completo ao ETL A2 avançado (NER + Section Scope).

AUTENTICAÇÃO:
- Suporta Service Account (recomendado para servidores)
- Suporta OAuth 2.0 (para acesso a contas pessoais)
- Configuração via variáveis de ambiente

ETL INTEGRADO:
- Aplica ETL A2 automaticamente em todos os arquivos importados
- Extração de entidades (NER) e Section Scope por chunk
- Compatível com o sistema ETL avançado existente
"""

import os
import base64
import json
from typing import List, Optional, Dict, Any
from pathlib import Path

from goldenverba.components.document import Document
from goldenverba.components.interfaces import Reader
from goldenverba.server.types import FileConfig
from goldenverba.components.types import InputConfig
from goldenverba.components.reader.BasicReader import BasicReader
from wasabi import msg

# Google Drive API
try:
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    import io
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    msg.warn("⚠️ Google Drive API não disponível. Instale: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")


class GoogleDriveReader(Reader):
    """
    Reader para importar arquivos do Google Drive com ETL A2 automático
    
    Funcionalidades:
    - Lista arquivos de pastas/compartilhamentos do Google Drive
    - Baixa arquivos automaticamente
    - Aplica ETL A2 em todos os documentos importados
    - Suporta múltiplos formatos (PDF, DOCX, TXT, etc.)
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Google Drive (ETL A2)"
        self.type = "URL"  # Tipo URL para aparecer na interface de URLs
        self.requires_env = ["GOOGLE_DRIVE_CREDENTIALS"]  # Service Account JSON ou OAuth
        self.requires_library = ["google-api-python-client", "google-auth-httplib2", "google-auth-oauthlib"]
        self.description = "Importa arquivos do Google Drive com ETL A2 automático (NER + Section Scope). Suporta Service Account e OAuth 2.0."
        
        self.config = {
            "Folder ID": InputConfig(
                type="text",
                value="",
                description="ID da pasta do Google Drive (ou 'root' para raiz, ou URL compartilhada)",
                values=[],
            ),
            "File IDs": InputConfig(
                type="multi",
                value="",
                description="IDs específicos de arquivos (opcional, separados por vírgula ou um por linha)",
                values=[],
            ),
            "Recursive": InputConfig(
                type="bool",
                value=True,
                description="Importar arquivos de subpastas recursivamente",
                values=[],
            ),
            "File Types": InputConfig(
                type="multi",
                value="pdf,docx,txt,md",
                description="Tipos de arquivo para importar (extensões separadas por vírgula)",
                values=[],
            ),
            "Enable ETL": InputConfig(
                type="bool",
                value=True,
                description="Aplicar ETL A2 automaticamente (NER + Section Scope)",
                values=[],
            ),
            "Language Hint": InputConfig(
                type="text",
                value="pt",
                description="Idioma padrão para NER (pt, en, etc.)",
                values=[],
            ),
        }
        
        self._service = None
        self._credentials = None
    
    def _get_credentials(self) -> Optional[Any]:
        """Obtém credenciais do Google Drive (Service Account ou OAuth)"""
        if self._credentials:
            return self._credentials
        
        credentials_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
        if not credentials_path:
            msg.warn("⚠️ GOOGLE_DRIVE_CREDENTIALS não configurado")
            return None
        
        try:
            # Tenta como Service Account primeiro
            if os.path.exists(credentials_path):
                with open(credentials_path, 'r') as f:
                    creds_data = json.load(f)
                
                # Verifica se é Service Account
                if 'type' in creds_data and creds_data['type'] == 'service_account':
                    self._credentials = service_account.Credentials.from_service_account_file(
                        credentials_path,
                        scopes=['https://www.googleapis.com/auth/drive.readonly']
                    )
                    msg.info("✅ Autenticado via Service Account")
                    return self._credentials
                # Se não, tenta como OAuth credentials
                else:
                    self._credentials = Credentials.from_authorized_user_file(
                        credentials_path,
                        scopes=['https://www.googleapis.com/auth/drive.readonly']
                    )
                    msg.info("✅ Autenticado via OAuth 2.0")
                    return self._credentials
            else:
                # Tenta parsear como JSON string direto
                try:
                    creds_data = json.loads(credentials_path)
                    if 'type' in creds_data and creds_data['type'] == 'service_account':
                        self._credentials = service_account.Credentials.from_service_account_info(
                            creds_data,
                            scopes=['https://www.googleapis.com/auth/drive.readonly']
                        )
                        msg.info("✅ Autenticado via Service Account (JSON string)")
                        return self._credentials
                except json.JSONDecodeError:
                    pass
                
                msg.warn(f"⚠️ Arquivo de credenciais não encontrado: {credentials_path}")
                return None
        except Exception as e:
            msg.warn(f"⚠️ Erro ao carregar credenciais: {str(e)}")
            return None
    
    def _get_service(self):
        """Obtém serviço do Google Drive API"""
        if self._service:
            return self._service
        
        creds = self._get_credentials()
        if not creds:
            return None
        
        try:
            self._service = build('drive', 'v3', credentials=creds)
            return self._service
        except Exception as e:
            msg.warn(f"⚠️ Erro ao criar serviço do Google Drive: {str(e)}")
            return None
    
    def _extract_folder_id_from_url(self, url_or_id: str) -> str:
        """Extrai folder ID de URL do Google Drive ou retorna o ID direto"""
        if not url_or_id:
            return "root"
        
        # Se já é um ID (sem caracteres especiais de URL)
        if '/' not in url_or_id and len(url_or_id) > 20:
            return url_or_id
        
        # Tenta extrair de diferentes formatos de URL
        import re
        patterns = [
            r'/folders/([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)',
            r'/([a-zA-Z0-9_-]{25,})',  # IDs do Google Drive têm pelo menos 25 caracteres
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        
        # Se não encontrou, assume que é o ID direto
        return url_or_id if url_or_id else "root"
    
    def _list_files_in_folder(self, folder_id: str, recursive: bool = True, file_types: List[str] = None) -> List[Dict]:
        """Lista arquivos em uma pasta do Google Drive"""
        service = self._get_service()
        if not service:
            return []
        
        if file_types is None:
            file_types = ['pdf', 'docx', 'txt', 'md', 'doc', 'xlsx', 'pptx']
        
        # Mapeia extensões para MIME types do Google Drive
        mime_type_map = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'doc': 'application/msword',
            'txt': 'text/plain',
            'md': 'text/markdown',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'xls': 'application/vnd.ms-excel',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'ppt': 'application/vnd.ms-powerpoint',
        }
        
        mime_types = [mime_type_map.get(ft.lower(), f'application/{ft}') for ft in file_types]
        
        all_files = []
        page_token = None
        
        try:
            while True:
                # Busca arquivos na pasta
                query = f"'{folder_id}' in parents and trashed=false"
                if mime_types:
                    mime_query = " or ".join([f"mimeType='{mt}'" for mt in mime_types])
                    query += f" and ({mime_query})"
                
                results = service.files().list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
                    pageToken=page_token
                ).execute()
                
                files = results.get('files', [])
                all_files.extend(files)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            # Se recursivo, busca subpastas DEPOIS de listar todos os arquivos da pasta atual
            if recursive:
                folders = service.files().list(
                    q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="files(id, name)"
                ).execute().get('files', [])
                
                for folder in folders:
                    msg.info(f"📁 Buscando em subpasta: {folder.get('name', folder['id'])}")
                    sub_files = self._list_files_in_folder(folder['id'], recursive=True, file_types=file_types)
                    all_files.extend(sub_files)
            
            msg.info(f"✅ Encontrados {len(all_files)} arquivo(s) no Google Drive")
            return all_files
            
        except HttpError as e:
            msg.warn(f"⚠️ Erro ao listar arquivos: {str(e)}")
            return []
    
    def _download_file(self, file_id: str, file_name: str) -> Optional[bytes]:
        """Baixa um arquivo do Google Drive"""
        service = self._get_service()
        if not service:
            return None
        
        try:
            # Para Google Docs/Sheets/Slides, exporta como formato específico
            file_info = service.files().get(fileId=file_id, fields='mimeType, name').execute()
            mime_type = file_info.get('mimeType', '')
            
            # Google Docs/Sheets/Slides precisam ser exportados
            export_mime_map = {
                'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            }
            
            if mime_type in export_mime_map:
                # Exporta Google Doc como DOCX
                request = service.files().export_media(fileId=file_id, mimeType=export_mime_map[mime_type])
            else:
                # Baixa arquivo normal
                request = service.files().get_media(fileId=file_id)
            
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_content.seek(0)
            return file_content.read()
            
        except HttpError as e:
            msg.warn(f"⚠️ Erro ao baixar arquivo {file_name} (ID: {file_id}): {str(e)}")
            return None
    
    async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
        """
        Carrega arquivos do Google Drive e cria documentos Verba com ETL habilitado
        """
        if not GOOGLE_DRIVE_AVAILABLE:
            raise ImportError("Google Drive API não disponível. Instale: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        
        # Obtém configurações
        folder_id_or_url = config.get("Folder ID", {}).value if hasattr(config.get("Folder ID", {}), 'value') else ""
        file_ids_str = config.get("File IDs", {}).values if hasattr(config.get("File IDs", {}), 'values') else []
        recursive = config.get("Recursive", {}).value if hasattr(config.get("Recursive", {}), 'value') else True
        file_types_str = config.get("File Types", {}).value if hasattr(config.get("File Types", {}), 'value') else "pdf,docx,txt,md"
        enable_etl = config.get("Enable ETL", {}).value if hasattr(config.get("Enable ETL", {}), 'value') else True
        language_hint = config.get("Language Hint", {}).value if hasattr(config.get("Language Hint", {}), 'value') else "pt"
        
        # Parse file types
        file_types = [ft.strip().lstrip('.') for ft in file_types_str.split(',') if ft.strip()]
        
        # Parse file IDs
        file_ids_list = []
        if file_ids_str:
            for fid in file_ids_str:
                # Pode ser separado por vírgula ou um por linha
                for item in fid.replace('\n', ',').split(','):
                    item = item.strip()
                    if item:
                        file_ids_list.append(item)
        
        documents = []
        basic_reader = BasicReader()
        
        # Se tem file IDs específicos, baixa apenas esses
        if file_ids_list:
            msg.info(f"📥 Baixando {len(file_ids_list)} arquivo(s) específico(s) do Google Drive...")
            service = self._get_service()
            if not service:
                raise Exception("Não foi possível autenticar com Google Drive")
            
            for file_id in file_ids_list:
                try:
                    file_info = service.files().get(fileId=file_id, fields='id, name, mimeType').execute()
                    file_name = file_info.get('name', f'file_{file_id}')
                    
                    msg.info(f"📥 Baixando: {file_name}")
                    file_content = self._download_file(file_id, file_name)
                    
                    if file_content:
                        # Determina extensão do arquivo
                        extension = file_name.split('.')[-1].lower() if '.' in file_name else 'txt'
                        
                        # Cria FileConfig para o arquivo baixado
                        base64_content = base64.b64encode(file_content).decode('utf-8')
                        new_file_config = FileConfig(
                            fileID=f"{fileConfig.fileID}_{file_id}",
                            filename=file_name,
                            isURL=False,
                            overwrite=fileConfig.overwrite,
                            extension=extension,
                            source=f"gdrive://{file_id}",
                            content=base64_content,
                            labels=fileConfig.labels,
                            rag_config=fileConfig.rag_config,
                            file_size=len(file_content),
                            status=fileConfig.status,
                            status_report=fileConfig.status_report,
                            metadata=json.dumps({
                                "source": "google_drive",
                                "file_id": file_id,
                                "language_hint": language_hint
                            }),
                        )
                        
                        # Carrega documento usando BasicReader
                        doc_list = await basic_reader.load(self.config, new_file_config)
                        
                        # Habilita ETL em todos os documentos
                        for doc in doc_list:
                            if not hasattr(doc, 'meta'):
                                doc.meta = {}
                            doc.meta["enable_etl"] = enable_etl
                            doc.meta["language_hint"] = language_hint
                            doc.meta["source"] = "google_drive"
                            doc.meta["gdrive_file_id"] = file_id
                            documents.append(doc)
                            msg.info(f"✅ Arquivo '{file_name}' carregado - ETL={'habilitado' if enable_etl else 'desabilitado'}")
                
                except Exception as e:
                    msg.warn(f"⚠️ Erro ao processar arquivo {file_id}: {str(e)}")
                    continue
        
        # Se tem folder ID, lista e baixa arquivos da pasta
        elif folder_id_or_url:
            folder_id = self._extract_folder_id_from_url(folder_id_or_url)
            msg.info(f"📁 Listando arquivos da pasta: {folder_id}")
            
            files = self._list_files_in_folder(folder_id, recursive=recursive, file_types=file_types)
            
            if not files:
                msg.warn("⚠️ Nenhum arquivo encontrado na pasta")
                return documents
            
            msg.info(f"📥 Baixando {len(files)} arquivo(s) do Google Drive...")
            
            for file_info in files:
                file_id = file_info['id']
                file_name = file_info['name']
                
                try:
                    msg.info(f"📥 Baixando: {file_name}")
                    file_content = self._download_file(file_id, file_name)
                    
                    if file_content:
                        # Determina extensão
                        extension = file_name.split('.')[-1].lower() if '.' in file_name else 'txt'
                        
                        # Cria FileConfig
                        base64_content = base64.b64encode(file_content).decode('utf-8')
                        new_file_config = FileConfig(
                            fileID=f"{fileConfig.fileID}_{file_id}",
                            filename=file_name,
                            isURL=False,
                            overwrite=fileConfig.overwrite,
                            extension=extension,
                            source=f"gdrive://{file_id}",
                            content=base64_content,
                            labels=fileConfig.labels,
                            rag_config=fileConfig.rag_config,
                            file_size=len(file_content),
                            status=fileConfig.status,
                            status_report=fileConfig.status_report,
                            metadata=json.dumps({
                                "source": "google_drive",
                                "file_id": file_id,
                                "language_hint": language_hint
                            }),
                        )
                        
                        # Carrega documento
                        doc_list = await basic_reader.load(self.config, new_file_config)
                        
                        # Habilita ETL
                        for doc in doc_list:
                            if not hasattr(doc, 'meta'):
                                doc.meta = {}
                            doc.meta["enable_etl"] = enable_etl
                            doc.meta["language_hint"] = language_hint
                            doc.meta["source"] = "google_drive"
                            doc.meta["gdrive_file_id"] = file_id
                            documents.append(doc)
                            msg.info(f"✅ Arquivo '{file_name}' carregado - ETL={'habilitado' if enable_etl else 'desabilitado'}")
                
                except Exception as e:
                    msg.warn(f"⚠️ Erro ao processar arquivo {file_name}: {str(e)}")
                    continue
        else:
            msg.warn("⚠️ Nenhum Folder ID ou File ID especificado")
            return documents
        
        msg.good(f"✅ {len(documents)} documento(s) carregado(s) do Google Drive com ETL A2 {'habilitado' if enable_etl else 'desabilitado'}")
        return documents


def register():
    """
    Registra o plugin Google Drive Reader
    Patchable - não modifica código core do Verba
    """
    return {
        'name': 'google_drive_reader',
        'description': 'Reader para importar arquivos do Google Drive com ETL A2 automático',
        'readers': [GoogleDriveReader()],
    }

