"""
Reader Universal A2 - Aplica ETL automaticamente em qualquer conteúdo
Usa qualquer formato (PDF, DOCX, TXT, etc.) e garante ETL por chunk
"""

from typing import List
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
        self.description = "Processa qualquer arquivo e aplica ETL A2 automaticamente (NER + Section Scope por chunk)"
        
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
    
    async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
        """
        Carrega arquivo usando Default Reader e garante ETL
        """
        # Extrai valores do config de forma robusta
        # O config pode vir como InputConfig (backend) ou dict simples (frontend)
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
        
        # Importa Default Reader dinamicamente
        try:
            from goldenverba.components.reader.BasicReader import BasicReader
            default_reader = BasicReader()
        except ImportError as e:
            msg.fail(f"Default Reader não disponível: {str(e)}")
            raise ImportError(f"Failed to import BasicReader: {str(e)}")
        
        # Carrega usando Default Reader (suporta PDF, DOCX, TXT, etc.)
        try:
            msg.info(f"Iniciando carregamento do arquivo: {fileConfig.filename}")
            documents = await default_reader.load(config, fileConfig)
            
            if not documents:
                msg.warn(f"Nenhum documento foi carregado de {fileConfig.filename}")
                return []
            
            # Garante que todos os documentos tenham enable_etl=True
            for doc in documents:
                if not hasattr(doc, 'meta') or doc.meta is None:
                    doc.meta = {}
                
                # Marca para ETL
                doc.meta["enable_etl"] = enable_etl
                doc.meta["language"] = doc.meta.get("language", language_hint)
                
                msg.info(f"[UNIVERSAL-READER] Documento '{doc.title}' preparado - enable_etl={enable_etl}, language={language_hint}")
                msg.info(f"[UNIVERSAL-READER] Meta configurada: {doc.meta}")
            
            msg.good(f"{len(documents)} documento(s) carregado(s) com ETL habilitado")
            return documents
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            msg.fail(f"Erro ao carregar arquivo '{fileConfig.filename}': {str(e)}")
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

