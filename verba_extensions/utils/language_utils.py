"""
Módulo Utilitário Comum para Detecção de Idioma e NLP
Consolida código duplicado de múltiplos plugins

Este módulo fornece:
- Detecção de idioma de queries
- Carregamento lazy de modelos spaCy com cache global
- Stopwords PT/EN para análise de texto
"""

import os
from typing import Optional, Set, Any
from wasabi import msg

# ============================================================================
# STOPWORDS
# ============================================================================

STOPWORDS_PT: Set[str] = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos",
    "em", "na", "no", "nas", "nos", "por", "para", "com", "sem", "sob", "sobre",
    "e", "ou", "que", "qual", "quais", "como", "quando", "onde", "quem", "porque",
    "é", "são", "está", "estão", "foi", "foram", "ser", "ter", "haver",
    "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas",
    "aquele", "aquela", "aqueles", "aquelas", "isso", "isto", "aquilo",
    "meu", "minha", "seu", "sua", "nosso", "nossa", "dele", "dela",
    "me", "te", "se", "nos", "vos", "lhe", "lhes"
}

STOPWORDS_EN: Set[str] = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "from", "by",
    "about", "as", "is", "are", "was", "were", "been", "be", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "this", "that", "these", "those", "it", "its", "they", "them", "their",
    "what", "which", "who", "whom", "where", "when", "why", "how",
    "and", "or", "but", "if", "then", "else", "so", "because",
    "i", "you", "he", "she", "we", "my", "your", "his", "her", "our"
}

# ============================================================================
# CACHE DE MODELOS NLP
# ============================================================================

_nlp_models: dict = {}  # Cache global de modelos spaCy por idioma


# ============================================================================
# FUNÇÕES PÚBLICAS
# ============================================================================

def detect_query_language(query: str) -> str:
    """
    Detecta idioma da query (pt, en, etc.).
    
    Usa langdetect se disponível, senão usa heurística simples baseada em palavras comuns.
    
    Args:
        query: Query do usuário
        
    Returns:
        Código do idioma ("pt", "en", etc.) - default "pt" se não detectar
    """
    if not query or not query.strip():
        return "pt"  # Default
    
    try:
        from langdetect import detect
        lang = detect(query)
        # Normalizar códigos de idioma
        if lang in ["pt", "pt-BR", "pt-PT"]:
            return "pt"
        elif lang in ["en", "en-US", "en-GB"]:
            return "en"
        return lang
    except ImportError:
        # langdetect não disponível, usar heurística
        pass
    except Exception:
        # Erro na detecção, usar heurística
        pass
    
    # Fallback: heurística simples
    query_lower = query.lower()
    pt_words = ["de", "da", "do", "em", "para", "com", "que", "não", "é", "são"]
    en_words = ["the", "of", "to", "in", "for", "with", "that", "not", "is", "are"]
    pt_count = sum(1 for word in pt_words if word in query_lower)
    en_count = sum(1 for word in en_words if word in query_lower)
    
    if pt_count > en_count:
        return "pt"
    elif en_count > pt_count:
        return "en"
    
    return "pt"  # Default para português


def get_nlp(language: Optional[str] = None) -> Optional[Any]:
    """
    Lazy load spaCy com suporte multi-idioma e cache global.
    
    Args:
        language: Código do idioma ("pt", "en"). Se None, usa default da env var SPACY_MODEL
        
    Returns:
        Modelo spaCy apropriado ou None se não disponível
    """
    global _nlp_models
    
    # Se language não fornecido, tentar usar default da env var
    if language is None:
        model_name = os.getenv("SPACY_MODEL", "pt_core_news_sm")
        # Inferir idioma do nome do modelo
        if "pt_core" in model_name or "pt" in model_name:
            language = "pt"
        elif "en_core" in model_name or "en" in model_name:
            language = "en"
        else:
            language = "pt"  # Default
    
    # Retornar modelo já carregado
    if language in _nlp_models:
        return _nlp_models[language]
    
    # Mapear idioma para modelo spaCy
    model_map = {
        "pt": "pt_core_news_sm",
        "en": "en_core_web_sm",
    }
    
    model_name = model_map.get(language, "pt_core_news_sm")
    
    try:
        import spacy
        nlp = spacy.load(model_name)
        _nlp_models[language] = nlp
        return nlp
    except OSError:
        msg.warn(f"spaCy model '{model_name}' not found for language '{language}', NLP parsing disabled")
        # Tentar fallback para português se não for pt
        if language != "pt" and "pt" in model_map:
            try:
                fallback_model = model_map["pt"]
                nlp = spacy.load(fallback_model)
                _nlp_models["pt"] = nlp
                return nlp
            except:
                pass
        return None
    except Exception as e:
        msg.warn(f"Error loading spaCy: {str(e)}")
        return None


def get_stopwords(language: str = "pt") -> Set[str]:
    """
    Retorna conjunto de stopwords para o idioma especificado.
    
    Args:
        language: Código do idioma ("pt", "en")
        
    Returns:
        Conjunto de stopwords
    """
    if language == "en":
        return STOPWORDS_EN
    elif language == "pt":
        return STOPWORDS_PT
    else:
        # Default para português
        return STOPWORDS_PT


def get_all_stopwords() -> Set[str]:
    """
    Retorna conjunto combinado de stopwords PT e EN.
    
    Returns:
        Conjunto de todas as stopwords
    """
    return STOPWORDS_PT | STOPWORDS_EN

