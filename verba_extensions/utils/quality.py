"""
Utilitários para cálculo de quality score de chunks.

Calcula score de qualidade de chunks para filtrar conteúdo de baixa qualidade
automaticamente. Adaptado do RAG2 para Verba.

Features:
- Score de 0.0 a 1.0
- Type-aware (diferentes thresholds por tipo)
- Proteção de summaries (nunca descartados)
- Detecção de login walls e placeholders

Uso:
    from verba_extensions.utils.quality import compute_quality_score
    
    # Calcular score
    score, reason = compute_quality_score(
        text=chunk.text,
        parent_type=chunk.meta.get("parent_type"),
        is_summary=chunk.meta.get("is_summary", False)
    )
    
    # Filtrar chunks de baixa qualidade
    if score < 0.3:  # Threshold configurável
        # Opcional: registrar na telemetria
        from verba_extensions.utils.telemetry import get_telemetry
        get_telemetry().record_chunk_filtered_by_quality(
            parent_type=chunk.meta.get("parent_type", "unknown"),
            score=score,
            reason=reason
        )
        continue  # Pula chunk

Fatores considerados:
- Comprimento do texto (200-3000 chars ideal)
- Densidade alfanumérica (>= 0.55 ideal)
- Detecção de login walls
- Detecção de placeholders
- Type-aware boost (experiências curtas são aceitas)

Benefícios:
- Filtragem automática de conteúdo de baixa qualidade
- Melhor qualidade de resultados de busca
- Redução de ruído nos resultados

Documentação completa: verba_extensions/utils/README.md
"""
import math
import re
from typing import Optional


def is_login_wall(text: str) -> bool:
    """
    Verifica se texto contém indicadores de login wall.
    
    Args:
        text: Texto a verificar
    
    Returns:
        True se parece ser login wall
    """
    t = (text or "").lower()
    patterns = [
        "sign in to",
        "entrar no",
        "log in to view",
        "login required",
        "conteúdo indisponível",
    ]
    return any(p in t for p in patterns)


def compute_quality_score(text: str, parent_type: Optional[str] = None, is_summary: bool = False) -> tuple[float, str]:
    """
    Calcula quality score com awareness de tipo e proveniência.
    
    Args:
        text: Texto a avaliar
        parent_type: Tipo do conteúdo (e.g., "experience", "section", "chunk")
        is_summary: Se True, é um resumo (nunca descartado)
    
    Returns:
        (score, reason_code) onde reason_code explica o cálculo
    
    Notas:
    - Summaries nunca são descartados (score mínimo 0.75)
    - Type-aware scoring evita penalizar conteúdos curtos incorretamente
    """
    if not text:
        return 0.0, "EMPTY_TEXT"
    
    t = re.sub(r"\s+", " ", text).strip()
    if not t:
        return 0.0, "EMPTY_AFTER_TRIM"
    
    # Summaries são preservados
    if is_summary:
        return 0.75, "SUMMARY_PROTECTED"

    length = len(t)
    alpha = sum(ch.isalnum() for ch in t)
    density = alpha / max(1, length)

    score = 0.0
    reason_parts = []
    
    # Comprimento adequado
    if 200 <= length <= 3000:
        score += 0.4
        reason_parts.append("LEN_OK")
    elif 80 <= length < 200:
        score += 0.2
        reason_parts.append("LEN_SHORT")
    else:
        reason_parts.append("LEN_V_SHORT")
    
    # Densidade
    if density >= 0.55:
        score += 0.3
        reason_parts.append("DENSITY_HIGH")
    elif density >= 0.4:
        score += 0.15
        reason_parts.append("DENSITY_MED")
    else:
        reason_parts.append("DENSITY_LOW")
    
    # Penalizações
    if is_login_wall(t):
        score -= 0.6
        reason_parts.append("LOGIN_WALL")
    
    if re.search(r"\b(lorem ipsum|click here|placeholder)\b", t, re.IGNORECASE):
        score -= 0.2
        reason_parts.append("PLACEHOLDER")
    
    # Type-aware boost
    if parent_type == "experience" and 20 <= length <= 100:
        # Boost para summaries de experiência (Position | Company | Location)
        score += 0.15
        reason_parts.append("EXP_SUMMARY_BOOST")
    
    score = max(0.0, min(1.0, score))
    reason_code = ":".join(reason_parts) if reason_parts else "BASE"
    
    return score, reason_code

