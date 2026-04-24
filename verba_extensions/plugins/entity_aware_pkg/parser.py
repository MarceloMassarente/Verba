
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


def _detect_entity_focus_in_query(self, query: str, entities: List[str]) -> bool:
    """
    Detecta se a query tem foco explícito em entidades (para modo hybrid)
    
    Padrões que indicam foco em entidade:
    - "sobre [entidade]"
    - "da [entidade]"
    - "[entidade] fez/tem/é"
    - "comparar [entidade] com"
    - apenas a entidade sem contexto
    
    Returns:
        True se query tem foco explícito em entidade
        False se query é exploratória/conceitual
    """
    if not entities:
        return False
    
    query_lower = query.lower()
    
    # Padrões de foco explícito em entidade
    explicit_patterns = [
        r'\b(sobre|da|do|de)\s+{entity}',  # "sobre Apple"
        r'\b{entity}\s+(fez|tem|é|foi|tinha|apresentou)',  # "Apple fez"
        r'\b(comparar|compare|diferença|vs|versus)\s+{entity}',  # "comparar Apple"
        r'\b{entity}\s+e\s+{entity}',  # "Apple e Microsoft"
        r'^{entity}',  # Query começa com entidade
        r'{entity}$',  # Query termina com entidade
    ]
    
    import re
    for entity in entities:
        entity_escaped = re.escape(entity.lower())
        for pattern in explicit_patterns:
            pattern_filled = pattern.replace('{entity}', entity_escaped)
            if re.search(pattern_filled, query_lower, re.IGNORECASE):
                return True
    
    # Se query é curta (<5 palavras) e contém entidade, assume foco
    words = query_lower.split()
    if len(words) <= 5:
        for entity in entities:
            if entity.lower() in query_lower:
                return True
    
    return False


def _detect_aggregation_query(self, query: str) -> bool:
    """
    Detecta se a query é uma query de agregação/analytics.
    
    Padrões que indicam agregação:
    - "quantos documentos"
    - "count"
    - "agrupar por"
    - "group by"
    - "quantidade de"
    
    Args:
        query: Query do usuário
    
    Returns:
        True se é query de agregação
    """
    query_lower = query.lower()
    
    aggregation_keywords = [
        "quantos",
        "quantas",
        "count",
        "agrupar",
        "group by",
        "quantidade",
        "total de",
        "número de",
        "estatísticas",
        "analytics",
        "agregação"
    ]
    
    return any(keyword in query_lower for keyword in aggregation_keywords)


def _detect_document_listing_query(self, query: str) -> bool:
    """
    Detecta queries que pedem listagem de documentos.
    
    Padrões que indicam listagem:
    - "quais documentos"
    - "liste documentos"
    - "documentos que têm"
    - "quais ... têm ... framework"
    - "documentos com ... framework"
    
    Args:
        query: Query do usuário
    
    Returns:
        True se é query de listagem de documentos
    """
    import re
    query_lower = query.lower()
    patterns = [
        r"quais documentos",
        r"liste documentos", 
        r"documentos que",
        r"quais .* têm .* framework",
        r"documentos com .* framework",
        r"documentos.*framework",
        r"lista.*documentos.*framework"
    ]
    return any(re.search(pattern, query_lower) for pattern in patterns)


def _extract_group_by_from_query(self, query: str) -> Optional[List[str]]:
    """
    Extrai propriedades para group_by da query.
    
    Args:
        query: Query do usuário
    
    Returns:
        Lista de propriedades para agrupar ou None
    """
    query_lower = query.lower()
    
    # Mapear termos da query para propriedades Weaviate
    property_mapping = {
        "framework": "frameworks",
        "empresa": "companies",
        "setor": "sectors",
        "company": "companies",
        "sector": "sectors",
        "data": "chunk_date",
        "date": "chunk_date",
        "idioma": "chunk_lang",
        "language": "chunk_lang"
    }
    
    group_by = []
    for term, property_name in property_mapping.items():
        if term in query_lower:
            group_by.append(property_name)
    
    # Se é query de listagem de documentos, adicionar doc_uuid
    if self._detect_document_listing_query(query):
        if "doc_uuid" not in group_by:
            group_by.append("doc_uuid")
    
    return group_by if group_by else None

