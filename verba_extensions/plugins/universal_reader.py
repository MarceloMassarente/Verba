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
        enable_etl = config.get("Enable ETL", {}).value if hasattr(config.get("Enable ETL", {}), 'value') else True
        language_hint = config.get("Language Hint", {}).value if hasattr(config.get("Language Hint", {}), 'value') else "pt"
        
        # Importa Default Reader dinamicamente
        try:
            from goldenverba.components.reader.BasicReader import BasicReader
            default_reader = BasicReader()
        except ImportError:
            msg.fail("Default Reader não disponível")
            return []
        
        # Carrega usando Default Reader (suporta PDF, DOCX, TXT, etc.)
        try:
            documents = await default_reader.load(config, fileConfig)
            
            # Garante que todos os documentos tenham enable_etl=True
            for doc in documents:
                if not hasattr(doc, 'meta') or doc.meta is None:
                    doc.meta = {}
                
                # Marca para ETL
                doc.meta["enable_etl"] = enable_etl
                doc.meta["language"] = doc.meta.get("language", language_hint)
                
                msg.info(f"Documento '{doc.title}' preparado para ETL A2")
            
            msg.good(f"{len(documents)} documento(s) carregado(s) com ETL habilitado")
            return documents
            
        except Exception as e:
            msg.fail(f"Erro ao carregar arquivo: {str(e)}")
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

