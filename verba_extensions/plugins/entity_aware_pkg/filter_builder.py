
from typing import Optional, Dict, Any, List, Tuple
from wasabi import msg
from goldenverba.components.chunk import Chunk
from verba_extensions.compatibility.weaviate_imports import Filter, WEAVIATE_V4
import json
import re

def get_config_value(config, key, default=None):
    if key not in config: return default
    item = config[key]
    if item is None: return default
    if hasattr(item, 'value'): return item.value if item.value is not None else default
    if isinstance(item, dict): return item.get('value', default)
    return item


def _calculate_framework_boost(
    self,
    result: Dict[str, Any],
    query_frameworks: List[str]
) -> float:
    """
    Calcula boost baseado em match de frameworks.
    
    Args:
        result: Resultado do Weaviate
        query_frameworks: Frameworks detectados na query
    
    Returns:
        Boost score (0.0-1.0)
    """
    if not query_frameworks:
        return 0.0
    
    result_frameworks = result.get("frameworks", [])
    if not result_frameworks:
        return 0.0
    
    # Conta quantos frameworks da query estão no resultado
    matches = len(set(query_frameworks) & set(result_frameworks))
    if matches == 0:
        return 0.0
    
    # Boost proporcional ao número de matches
    return min(matches / len(query_frameworks), 1.0)


def _calculate_concept_boost(
    self,
    result: Dict[str, Any],
    query_concepts: List[str]
) -> float:
    """
    Calcula boost baseado em match de conceitos de negócio.
    
    Args:
        result: Resultado do Weaviate
        query_concepts: Conceitos detectados na query
    
    Returns:
        Boost score (0.0-1.0)
    """
    if not query_concepts:
        return 0.0
    
    result_concepts = result.get("conceitos_negocio", [])
    if not result_concepts:
        return 0.0
    
    # Match parcial (conceitos podem ter variações)
    matches = 0
    for qc in query_concepts:
        qc_lower = qc.lower()
        for rc in result_concepts:
            if qc_lower in rc.lower() or rc.lower() in qc_lower:
                matches += 1
                break
    
    if matches == 0:
        return 0.0
    
    return min(matches / len(query_concepts), 1.0)


def _calculate_company_boost(
    self,
    result: Dict[str, Any],
    query_companies: List[str]
) -> float:
    """
    Calcula boost baseado em match de empresas.
    
    Args:
        result: Resultado do Weaviate
        query_companies: Empresas detectadas na query
    
    Returns:
        Boost score (0.0-1.0)
    """
    if not query_companies:
        return 0.0
    
    result_companies = result.get("companies", [])
    if not result_companies:
        return 0.0
    
    # Match exato ou parcial
    matches = 0
    for qc in query_companies:
        qc_lower = qc.lower()
        for rc in result_companies:
            if qc_lower == rc.lower() or qc_lower in rc.lower() or rc.lower() in qc_lower:
                matches += 1
                break
    
    if matches == 0:
        return 0.0
    
    return min(matches / len(query_companies), 1.0)


def _calculate_content_type_boost(
    self,
    result: Dict[str, Any],
    query_content_type: Optional[str]
) -> float:
    """
    Calcula boost baseado em match de tipo de conteúdo.
    
    Args:
        result: Resultado do Weaviate
        query_content_type: Tipo de conteúdo da query (se detectado)
    
    Returns:
        Boost score (0.0-1.0)
    """
    if not query_content_type:
        return 0.0
    
    result_content_type = result.get("tipo_conteudo", "contexto")
    if not result_content_type:
        return 0.0
    
    # Match exato
    if query_content_type.lower() == result_content_type.lower():
        return 1.0
    
    return 0.0

