"""
Vector Config Builder
Constrói vectorConfig para named vectors no modo BYOV (Bring Your Own Vector)

Aprende do RAG2: named vectors especializados com quantização PQ automática
"""

from typing import Dict, Any, Optional
from wasabi import msg


def get_pq_config(
    estimated_count: int,
    threshold: int = 50000
) -> Dict[str, Any]:
    """
    Retorna configuração de Product Quantization (PQ) baseada no count estimado.
    
    PQ reduz uso de RAM ~4x mas só é benéfico para collections grandes.
    Ativa automaticamente apenas quando estimated_count >= threshold.
    
    Args:
        estimated_count: Número estimado de objetos na collection
        threshold: Limite para ativar PQ (padrão: 50k)
    
    Returns:
        Configuração de PQ para vectorIndexConfig
    """
    if estimated_count >= threshold:
        return {
            "pq": {
                "enabled": True,
                "segments": 0  # Auto - Weaviate decide número de segmentos
            }
        }
    else:
        return {
            "pq": {
                "enabled": False
            }
        }


def build_named_vectors_config(
    enable_named_vectors: bool = True,
    estimated_count: int = 0,
    use_pq: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Constrói vectorConfig com named vectors especializados.
    
    Named vectors:
    - concept_vec: Conceitos abstratos (frameworks, estratégias, metodologias)
    - sector_vec: Setores/indústrias (varejo, bancos, tecnologia, etc.)
    - company_vec: Empresas específicas (Apple, Microsoft, etc.)
    
    Modo BYOV (Bring Your Own Vector):
    - Não usa vectorizer do Weaviate
    - Embeddings são calculados manualmente e inseridos
    - Permite usar qualquer modelo de embedding
    
    Args:
        enable_named_vectors: Se True, retorna vectorConfig com named vectors
        estimated_count: Número estimado de objetos (para PQ)
        use_pq: Se True, ativa PQ automaticamente se count >= threshold
    
    Returns:
        Dict com vectorConfig ou None se desabilitado
    """
    if not enable_named_vectors:
        return None  # Usa vetor padrão do Weaviate
    
    # Quantização PQ se collection grande
    pq_config = get_pq_config(estimated_count, threshold=50000) if use_pq else {}
    
    # Configuração HNSW otimizada
    base_vector_config = {
        "vectorIndexType": "hnsw",
        "vectorIndexConfig": {
            "distance": "cosine",
            **pq_config
        }
    }
    
    # Named vectors especializados
    vector_config = {
        "concept_vec": {
            **base_vector_config,
            # concept_vec: para conceitos abstratos, frameworks, estratégias
        },
        "sector_vec": {
            **base_vector_config,
            # sector_vec: para setores, indústrias, domínios
        },
        "company_vec": {
            **base_vector_config,
            # company_vec: para empresas, organizações, entidades
        }
    }
    
    return vector_config


def should_enable_named_vectors(
    collection_size: int = 0,
    min_size_threshold: int = 1000
) -> bool:
    """
    Decide se named vectors devem ser habilitados baseado no tamanho da collection.
    
    Named vectors têm overhead de memória e processamento.
    Para collections pequenas, pode não valer a pena.
    
    Args:
        collection_size: Tamanho atual da collection
        min_size_threshold: Tamanho mínimo para habilitar (padrão: 1000)
    
    Returns:
        True se named vectors devem ser habilitados
    """
    return collection_size >= min_size_threshold


def get_vector_index_config(
    estimated_count: int = 0,
    distance: str = "cosine",
    use_pq: bool = True
) -> Dict[str, Any]:
    """
    Retorna configuração de índice vetorial otimizada.
    
    Args:
        estimated_count: Número estimado de objetos
        distance: Métrica de distância (cosine, dot, l2-squared)
        use_pq: Se True, ativa PQ se count >= threshold
    
    Returns:
        Configuração de vectorIndexConfig
    """
    pq_config = get_pq_config(estimated_count) if use_pq else {}
    
    return {
        "distance": distance,
        **pq_config
    }


def validate_vector_config(vector_config: Optional[Dict[str, Any]]) -> bool:
    """
    Valida se vectorConfig está bem formado.
    
    Args:
        vector_config: VectorConfig a validar
    
    Returns:
        True se válido
    """
    if vector_config is None:
        return True  # None é válido (usa vetor padrão)
    
    if not isinstance(vector_config, dict):
        return False
    
    # Verificar que cada named vector tem estrutura correta
    required_keys = ["vectorIndexType", "vectorIndexConfig"]
    
    for vector_name, vector_config_data in vector_config.items():
        if not isinstance(vector_config_data, dict):
            return False
        
        for key in required_keys:
            if key not in vector_config_data:
                return False
        
        # Validar vectorIndexConfig
        index_config = vector_config_data.get("vectorIndexConfig", {})
        if not isinstance(index_config, dict):
            return False
        
        if "distance" not in index_config:
            return False
    
    return True

