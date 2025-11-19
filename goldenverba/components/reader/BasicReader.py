import base64
import json
import io
import csv

from wasabi import msg

from goldenverba.components.document import Document, create_document
from goldenverba.components.interfaces import Reader
from goldenverba.server.types import FileConfig

# Optional imports with error handling
try:
    from pypdf import PdfReader
except ImportError:
    msg.warn("pypdf not installed, PDF functionality will be limited.")
    PdfReader = None

try:
    import spacy
except ImportError:
    msg.warn("spacy not installed, NLP functionality will be limited.")
    spacy = None

try:
    import docx
except ImportError:
    msg.warn("python-docx not installed, DOCX functionality will be limited.")
    docx = None

try:
    import pandas as pd
except ImportError:
    msg.warn("pandas not installed, Excel functionality will be limited.")
    pd = None

try:
    import openpyxl
except ImportError:
    msg.warn("openpyxl not installed, Excel functionality will be limited.")
    openpyxl = None

try:
    import xlrd
except ImportError:
    msg.warn("xlrd not installed, .xls file functionality will be limited.")
    xlrd = None


class BasicReader(Reader):
    """
    The BasicReader reads text, code, PDF, DOCX, CSV, and Excel files.
    """

    def __init__(self):
        super().__init__()
        self.name = "Default"
        self.description = "Ingests text, code, PDF, DOCX, CSV, and Excel files"
        self.requires_library = ["pypdf", "docx", "spacy", "pandas", "openpyxl"]
        self.extension = [
            ".txt",
            ".py",
            ".js",
            ".html",
            ".css",
            ".md",
            ".mdx",
            ".json",
            ".pdf",
            ".docx",
            ".pptx",
            ".xlsx",
            ".xls",
            ".csv",
            ".ts",
            ".tsx",
            ".vue",
            ".svelte",
            ".astro",
            ".php",
            ".rb",
            ".go",
            ".rs",
            ".swift",
            ".kt",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
        ]  # Add supported text extensions

        # Initialize spaCy model if available
        self.nlp = spacy.blank("en") if spacy else None
        if self.nlp:
            self.nlp.add_pipe("sentencizer", config={"punct_chars": None})

    async def load(self, config: dict, fileConfig: FileConfig) -> list[Document]:
        """
        Load and process a file based on its extension.
        """
        msg.info(f"Loading {fileConfig.filename} ({fileConfig.extension.lower()})")

        if fileConfig.extension != "":
            decoded_bytes = base64.b64decode(fileConfig.content)

        try:
            if fileConfig.extension == "":
                file_content = fileConfig.content
            elif fileConfig.extension.lower() == "json":
                return await self.load_json_file(decoded_bytes, fileConfig)
            elif fileConfig.extension.lower() == "pdf":
                file_content = await self.load_pdf_file(decoded_bytes)
            elif fileConfig.extension.lower() == "docx":
                file_content = await self.load_docx_file(decoded_bytes)
            elif fileConfig.extension.lower() == "csv":
                file_content = await self.load_csv_file(decoded_bytes)
            elif fileConfig.extension.lower() in ["xlsx", "xls"]:
                file_content = await self.load_excel_file(
                    decoded_bytes, fileConfig.extension.lower()
                )
            elif fileConfig.extension.lower() in [
                ext.lstrip(".") for ext in self.extension
            ]:
                file_content = await self.load_text_file(decoded_bytes)
            else:
                try:
                    file_content = await self.load_text_file(decoded_bytes)
                except Exception as e:
                    raise ValueError(
                        f"Unsupported file extension: {fileConfig.extension}"
                    )

            return [create_document(file_content, fileConfig)]
        except Exception as e:
            msg.fail(f"Failed to load {fileConfig.filename}: {str(e)}")
            raise

    async def load_text_file(self, decoded_bytes: bytes) -> str:
        """Load and decode a text file."""
        try:
            return decoded_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Fallback to latin-1 if UTF-8 fails
            return decoded_bytes.decode("latin-1")

    async def load_json_file(
        self, decoded_bytes: bytes, fileConfig: FileConfig
    ) -> list[Document]:
        """Load and parse a JSON file."""
        try:
            json_obj = json.loads(decoded_bytes.decode("utf-8"))
            document = Document.from_json(json_obj, self.nlp)
            return (
                [document]
                if document
                else [create_document(json.dumps(json_obj, indent=2), fileConfig)]
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {fileConfig.filename}: {str(e)}")

    async def load_pdf_file(self, decoded_bytes: bytes) -> str:
        """Load and extract text from a PDF file (runs in executor to avoid blocking)."""
        if not PdfReader:
            raise ImportError("pypdf is not installed. Cannot process PDF files.")
        
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._load_pdf_file_sync, decoded_bytes)

    def _load_pdf_file_sync(self, decoded_bytes: bytes) -> str:
        """Synchronous implementation of PDF loading."""
        pdf_bytes = io.BytesIO(decoded_bytes)
        reader = PdfReader(pdf_bytes)
        
        # Tenta extrair com layout preservation primeiro (melhor para multi-coluna)
        text_parts = []
        for page in reader.pages:
            try:
                # Tenta extrair com layout_strip (preserva ordem espacial)
                text = page.extract_text(layout_mode=True)
                if not text or len(text.strip()) == 0:
                    # Fallback para método padrão
                    text = page.extract_text()
                
                # Remove linhas duplicadas consecutivas (causa comum de fragmentação)
                lines = text.split('\n')
                cleaned_lines = []
                prev_line = None
                for line in lines:
                    line_stripped = line.strip()
                    # Ignora linhas vazias ou muito curtas que são fragmentos
                    if line_stripped and len(line_stripped) > 3:
                        # Não adiciona se for fragmento da linha anterior
                        if prev_line and line_stripped in prev_line:
                            continue
                        # Não adiciona se linha anterior for fragmento desta
                        if prev_line and prev_line in line_stripped:
                            cleaned_lines.pop() if cleaned_lines else None
                        cleaned_lines.append(line)
                        prev_line = line_stripped
                    elif line_stripped:  # Linhas não vazias mas curtas
                        cleaned_lines.append(line)
                
                cleaned_text = '\n'.join(cleaned_lines)
                if cleaned_text.strip():
                    text_parts.append(cleaned_text)
            except Exception as e:
                # Fallback para método padrão se layout_mode falhar
                try:
                    text = page.extract_text()
                    if text.strip():
                        text_parts.append(text)
                except Exception:
                    msg.warn(f"Failed to extract text from page: {str(e)}")
                    continue
        
        return "\n\n".join(text_parts)

    async def load_docx_file(self, decoded_bytes: bytes) -> str:
        """Load and extract text from a DOCX file (runs in executor)."""
        if not docx:
            raise ImportError(
                "python-docx is not installed. Cannot process DOCX files."
            )
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._load_docx_file_sync, decoded_bytes)

    def _load_docx_file_sync(self, decoded_bytes: bytes) -> str:
        """Synchronous implementation of DOCX loading."""
        docx_bytes = io.BytesIO(decoded_bytes)
        reader = docx.Document(docx_bytes)
        return "\n".join(paragraph.text for paragraph in reader.paragraphs)

    async def load_csv_file(self, decoded_bytes: bytes) -> str:
        """Load and convert CSV file to readable text format (runs in executor)."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._load_csv_file_sync, decoded_bytes)

    def _load_csv_file_sync(self, decoded_bytes: bytes) -> str:
        """Synchronous implementation of CSV loading."""
        try:
            # Try UTF-8 first, fallback to latin-1
            try:
                text_content = decoded_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text_content = decoded_bytes.decode("latin-1")

            csv_reader = csv.reader(io.StringIO(text_content))
            rows = list(csv_reader)

            if not rows:
                return "Empty CSV file"

            # Format as a readable table
            result = []
            headers = rows[0] if rows else []

            # Add headers
            if headers:
                result.append("Headers: " + " | ".join(headers))
                result.append(" \n\n")

            # Add data rows
            for i, row in enumerate(rows[1:], 1):
                if len(row) == len(headers):
                    row_data = []
                    for header, value in zip(headers, row):
                        row_data.append(f"{header}: {value}")
                    result.append(f"Row {i}: {' | '.join(row_data)}")
                else:
                    # Handle rows with different column counts
                    result.append(f"Row {i}: {' | '.join(row)}")
                result.append(" \n\n")
            return "\n".join(result)

        except Exception as e:
            raise ValueError(f"Error reading CSV file: {str(e)}")

    async def load_excel_file(self, decoded_bytes: bytes, extension: str) -> str:
        """Load and convert Excel file to readable text format (runs in executor)."""
        if not pd and not openpyxl:
            raise ImportError("pandas or openpyxl is required to process Excel files.")
        
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._load_excel_file_sync, decoded_bytes, extension)

    def _load_excel_file_sync(self, decoded_bytes: bytes, extension: str) -> str:
        """Synchronous implementation of Excel loading."""
