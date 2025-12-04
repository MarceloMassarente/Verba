from goldenverba.server.types import FileConfig
from goldenverba.components.chunk import Chunk
from spacy.tokens import Doc
from spacy.language import Language
import spacy
import json
import re

from langdetect import detect


# Padrões que NÃO devem ser quebrados em sentenças
# Números com ponto (1., 2., 3., etc.) - comum em listas
_BULLET_PATTERN = re.compile(r'^\s*\d+\.\s*$')
# Abreviações comuns que terminam com ponto
_ABBREVIATIONS = {
    'dr', 'sr', 'sra', 'mr', 'mrs', 'ms', 'prof', 'eng', 'arq',
    'fig', 'tab', 'cap', 'vol', 'pag', 'pg', 'sec', 'art',
    'ex', 'etc', 'vs', 'ie', 'eg', 'cf', 'ibid', 'op', 'cit',
    'inc', 'ltd', 'co', 'corp', 'llc', 'sa', 'ltda',
    'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
    'no', 'nos', 'ref', 'tel', 'fax', 'email', 'www', 'http', 'https',
    'min', 'max', 'avg', 'aprox', 'approx', 'est', 'ca',
}


@Language.component("smart_sentencizer")
def smart_sentencizer(doc):
    """
    Sentenciador inteligente que evita quebras falsas em:
    - Números com ponto (bullets: 1., 2., 3.)
    - Abreviações comuns (Dr., Fig., etc.)
    - Linhas muito curtas (< 10 chars)
    
    Usa quebras de linha dupla como forte indicador de nova sentença.
    """
    if len(doc) == 0:
        return doc
    
    # Primeira passada: marca todas as sentenças normalmente
    for token in doc:
        token.is_sent_start = False
    doc[0].is_sent_start = True
    
    for i, token in enumerate(doc[:-1]):
        next_token = doc[i + 1]
        
        # Se o token atual termina com pontuação de fim de sentença
        if token.text in '.!?':
            # Verifica se é uma quebra válida
            is_valid_break = True
            
            # 1. Não quebrar após números com ponto (bullets)
            if token.text == '.' and i > 0:
                prev_token = doc[i - 1]
                # Se o token anterior é um número, provavelmente é bullet
                if prev_token.text.isdigit() or prev_token.like_num:
                    is_valid_break = False
            
            # 2. Não quebrar após abreviações conhecidas
            if token.text == '.' and i > 0:
                prev_token = doc[i - 1]
                if prev_token.text.lower().rstrip('.') in _ABBREVIATIONS:
                    is_valid_break = False
            
            # 3. Não quebrar se o próximo token é minúsculo (continuação)
            if next_token.text and next_token.text[0].islower():
                is_valid_break = False
            
            if is_valid_break:
                next_token.is_sent_start = True
        
        # 4. Quebra de linha dupla é forte indicador de nova sentença
        elif '\n\n' in token.text or token.text == '\n\n':
            next_token.is_sent_start = True
        
        # 5. Linha que termina com dois pontos geralmente precede uma lista
        elif token.text == ':' and next_token.text.strip().startswith('\n'):
            next_token.is_sent_start = True
    
    return doc


def load_nlp_for_language(language: str):
    """
    Load SpaCy models based on language with smart sentencizer.
    
    O smart_sentencizer evita fragmentação excessiva em:
    - Bullets numerados (1., 2., 3.)
    - Abreviações (Dr., Fig., Sr.)
    - Linhas curtas
    """
    if language == "en":
        nlp = spacy.blank("en")
    elif language == "zh":
        nlp = spacy.blank("zh")
    elif language == "zh-hant":
        nlp = spacy.blank("zh-hant")
    elif language == "fr":
        nlp = spacy.blank("fr")
    elif language == "de":
        nlp = spacy.blank("de")
    elif language == "nl":
        nlp = spacy.blank("nl")
    elif language == "pt":
        nlp = spacy.blank("pt")
    else:
        nlp = spacy.blank("en")

    # Usa sentenciador inteligente ao invés do básico
    nlp.add_pipe("smart_sentencizer")

    return nlp


def detect_language(text: str) -> str:
    """Automatically detect language"""
    try:
        detected_lang = detect(text)
        if detected_lang == "zh-cn":
            return "zh"
        elif detected_lang == "zh-tw" or detected_lang == "zh-hk":
            return "zh-hant"
        return detected_lang
    except:
        return "unknown"


class Document:
    def __init__(
        self,
        title: str = "",
        content: str = "",
        extension: str = "",
        fileSize: int = 0,
        labels: list[str] = [],
        source: str = "",
        meta: dict = {},
        metadata: str = "",
    ):
        self.title = title
        self.content = content
        self.extension = extension
        self.fileSize = fileSize
        self.labels = labels
        self.source = source
        self.meta = meta
        self.metadata = metadata
        self.chunks: list[Chunk] = []

        MAX_BATCH_SIZE = 500000

        if len(content) > MAX_BATCH_SIZE:
            # Process content in batches
            docs = []
            detected_language = detect_language(content[0:MAX_BATCH_SIZE])
            nlp = load_nlp_for_language(detected_language)

            for i in range(0, len(content), MAX_BATCH_SIZE):
                docs.append(nlp(content[i : i + MAX_BATCH_SIZE]))

            # Merged all processed docs
            doc = Doc.from_docs(docs)
        else:
            # Process smaller content, directly based on language
            detected_language = detect_language(content)
            nlp = load_nlp_for_language(detected_language)
            doc = nlp(content)

        self.spacy_doc = doc

    @staticmethod
    def to_json(document) -> dict:
        """Convert the Document object to a JSON dict."""
        # Limpa meta para garantir que é JSON-serializável
        # Remove objetos complexos que possam não ser JSON-serializáveis
        cleaned_meta = {}
        if hasattr(document, 'meta') and document.meta:
            for key, value in document.meta.items():
                # Pula chaves que começam com _ (temporárias/internas)
                if key.startswith('_'):
                    continue
                
                # Tenta serializar o valor - se falhar, pula
                try:
                    json.dumps(value)
                    cleaned_meta[key] = value
                except (TypeError, ValueError):
                    # Se não é JSON-serializável, converte para string
                    try:
                        cleaned_meta[key] = str(value)
                    except Exception:
                        # Se ainda não conseguir, pula
                        pass
        
        doc_dict = {
            "title": document.title,
            "content": document.content,
            "extension": document.extension,
            "fileSize": document.fileSize,
            "labels": document.labels,
            "source": document.source,
            "meta": json.dumps(cleaned_meta),
            "metadata": document.metadata,
        }
        return doc_dict

    @staticmethod
    def from_json(doc_dict: dict, nlp):
        """Convert a JSON string to a Document object."""

        if (
            "title" in doc_dict
            and "content" in doc_dict
            and "extension" in doc_dict
            and "fileSize" in doc_dict
            and "labels" in doc_dict
            and "source" in doc_dict
            and "meta" in doc_dict
            and "metadata" in doc_dict
        ):
            document = Document(
                title=doc_dict.get("title", ""),
                content=doc_dict.get("content", ""),
                extension=doc_dict.get("extension", ""),
                fileSize=doc_dict.get("fileSize", 0),
                labels=doc_dict.get("labels", []),
                source=doc_dict.get("source", ""),
                meta=doc_dict.get("meta", {}),
                metadata=doc_dict.get("metadata", ""),
            )
            return document
        else:
            return None


def create_document(content: str, fileConfig: FileConfig) -> Document:
    """Create a Document object from the file content."""
    return Document(
        title=fileConfig.filename,
        content=content,
        extension=fileConfig.extension,
        labels=fileConfig.labels,
        source=fileConfig.source,
        fileSize=fileConfig.file_size,
        metadata=fileConfig.metadata,
        meta={},
    )
