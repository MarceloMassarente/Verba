"""
Utilitários para pré-processamento consistente de texto para embedding.

Garante que o texto embeddado é idêntico ao texto armazenado, evitando
problemas de inconsistência que podem afetar a qualidade dos embeddings.
Adaptado do RAG2 para Verba.

Features:
- Remove unicode invisível (zero-width spaces, etc.)
- Normaliza whitespace
- Truncamento semântico (preserva boundaries naturais)
- Validação de consistência

Uso básico:
    from verba_extensions.utils.preprocess import (
        prepare_for_embedding,
        validate_text_for_embedding,
        truncate_semantic
    )
    
    # Normalizar texto antes de embedding
    text_for_embedding = prepare_for_embedding(chunk.text)
    
    # Garantir consistência
    is_valid, error = validate_text_for_embedding(
        text_stored=chunk.text,
        text_embedded=text_for_embedding
    )
    
    if not is_valid:
        print(f"Erro: {error}")
    
    # Truncar semanticamente (preserva sentenças)
    truncated = truncate_semantic(
        text="Texto muito longo...",
        max_chars=200,
        ellipsis="…"
    )

Benefícios:
- Consistência entre texto armazenado e embeddado
- Melhor qualidade de embeddings (texto normalizado)
- Evita problemas de encoding

Documentação completa: verba_extensions/utils/README.md
"""
import re
from typing import Optional


def prepare_for_embedding(s: Optional[str]) -> str:
    """
    Pré-processa texto de forma consistente antes de embedding.
    
    Garante que o texto embeddado é idêntico ao texto armazenado.
    Remove apenas whitespace/unicode invisível, mantém semântica.
    
    Args:
        s: Texto a ser pré-processado
    
    Returns:
        Texto normalizado (ou string vazia se None/empty)
    """
    if not s:
        return ""
    
    # Remove non-breaking spaces e outros whitespace unicode
    s = s.replace("\u00A0", " ")  # non-breaking space
    s = s.replace("\u200B", "")   # zero-width space
    s = s.replace("\u200C", "")   # zero-width non-joiner
    s = s.replace("\u200D", "")   # zero-width joiner
    s = s.replace("\uFEFF", "")   # zero-width no-break space
    
    # Trim
    s = s.strip()
    
    # Normaliza espaços múltiplos em um único espaço
    s = " ".join(s.split())
    
    return s


def validate_text_for_embedding(text_stored: str, text_embedded: str) -> tuple[bool, Optional[str]]:
    """
    Valida que texto armazenado é idêntico ao texto embeddado.
    
    Args:
        text_stored: Texto que foi armazenado
        text_embedded: Texto que foi embeddado
    
    Returns:
        Tupla (is_valid, error_message)
    """
    if text_stored != text_embedded:
        return False, f"Mismatch: stored={text_stored[:50]!r} != embedded={text_embedded[:50]!r}"
    
    return True, None


def truncate_with_ellipsis(text: str, max_chars: int, ellipsis: str = "...") -> str:
    """
    Trunca texto respeitando limite de caracteres, adicionando ellipsis se necessário.
    
    Args:
        text: Texto a truncar
        max_chars: Limite de caracteres
        ellipsis: String de ellipsis (padrão: "...")
    
    Returns:
        Texto truncado (com ellipsis se foi truncado)
    """
    if len(text) <= max_chars:
        return text
    
    if max_chars < len(ellipsis):
        return text[:max_chars]
    
    return text[:max_chars - len(ellipsis)] + ellipsis


def truncate_semantic(text: str, max_chars: int, ellipsis: str = "…") -> str:
    """
    Trunca texto em delimitadores naturais para preservar semântica.
    
    Prioridade de delimitadores:
    1. Ponto final (.)
    2. Pipe (|) - comum em summaries
    3. Vírgula (,)
    4. Fallback: corte bruto
    
    Args:
        text: Texto a truncar
        max_chars: Limite de caracteres
        ellipsis: String de ellipsis (padrão: "…")
    
    Returns:
        Texto truncado semanticamente
    """
    if len(text) <= max_chars:
        return text
    
    if max_chars < len(ellipsis):
        return text[:max_chars]
    
    # Tenta encontrar delimitador natural antes do limite
    target_len = max_chars - len(ellipsis)
    
    # Prioridade: ponto final
    cut = text.rfind(".", 0, target_len)
    if cut >= target_len * 0.6:
        return text[:cut].rstrip() + ellipsis
    
    # Fallback: pipe
    cut = text.rfind(" | ", 0, target_len)
    if cut >= target_len * 0.6:
        return text[:cut].rstrip() + ellipsis
    
    # Fallback: vírgula
    cut = text.rfind(",", 0, target_len)
    if cut >= target_len * 0.7:
        return text[:cut].rstrip() + ellipsis
    
    # Último recurso: corte bruto
    return text[:target_len].rstrip() + ellipsis

