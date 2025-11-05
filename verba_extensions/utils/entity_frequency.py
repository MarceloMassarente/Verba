"""
Helper: Contagem de Frequência de Entidades
Calcula quantas vezes cada entidade aparece em documentos/chunks

Usado para:
- Identificar entidade dominante em um documento
- Criar hierarquia de entidades por frequência
- Filtrar por entidade mais/menos frequente
"""

from typing import Dict, List, Tuple
from collections import Counter
from wasabi import msg


async def get_entity_frequency_in_document(
    client,
    collection_name: str,
    doc_uuid: str
) -> Dict[str, int]:
    """
    Retorna frequência de cada entidade em um documento específico.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection de embedding
        doc_uuid: UUID do documento
        
    Returns:
        Dict {entity_id: count} ordenado por frequência (decrescente)
        
    Exemplo:
        freq = await get_entity_frequency_in_document(
            client,
            "VERBA_Embedding_all_MiniLM_L6_v2",
            "doc-123"
        )
        # Retorna: {"Q312": 15, "Q2283": 8, "Q95": 3}
        # Significa: Apple aparece 15x, Microsoft 8x, Google 3x
    """
    try:
        from verba_extensions.compatibility.weaviate_imports import Filter
        
        collection = client.collections.get(collection_name)
        
        # Buscar todos os chunks do documento
        results = await collection.query.fetch_objects(
            filters=Filter.by_property("doc_uuid").equal(doc_uuid),
            limit=1000,  # Ajustar conforme necessário
            return_properties=["entities_local_ids", "section_entity_ids"]
        )
        
        # Contar frequência de entidades
        entity_counter = Counter()
        
        for obj in results.objects:
            props = obj.properties
            
            # Contar entities_local_ids
            local_ids = props.get("entities_local_ids", [])
            if local_ids:
                entity_counter.update(local_ids)
            
            # Contar section_entity_ids (peso menor)
            section_ids = props.get("section_entity_ids", [])
            if section_ids:
                # Seção conta menos (0.5x) pois é menos específica
                entity_counter.update({eid: 0.5 for eid in section_ids})
        
        # Converter para dict ordenado por frequência
        freq_dict = dict(entity_counter.most_common())
        
        msg.info(f"  Frequência de entidades no documento {doc_uuid[:20]}...: {len(freq_dict)} entidades")
        return freq_dict
        
    except Exception as e:
        msg.warn(f"  Erro ao calcular frequência de entidades: {str(e)}")
        return {}


async def get_entity_frequency_in_chunks(
    client,
    collection_name: str,
    chunk_uuids: List[str]
) -> Dict[str, int]:
    """
    Retorna frequência de cada entidade em uma lista de chunks.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection de embedding
        chunk_uuids: Lista de UUIDs dos chunks
        
    Returns:
        Dict {entity_id: count} ordenado por frequência (decrescente)
    """
    try:
        from verba_extensions.compatibility.weaviate_imports import Filter
        
        collection = client.collections.get(collection_name)
        
        # Buscar chunks
        results = await collection.query.fetch_objects(
            filters=Filter.by_property("uuid").contains_any(chunk_uuids),
            limit=len(chunk_uuids),
            return_properties=["entities_local_ids", "section_entity_ids"]
        )
        
        # Contar frequência
        entity_counter = Counter()
        
        for obj in results.objects:
            props = obj.properties
            
            local_ids = props.get("entities_local_ids", [])
            if local_ids:
                entity_counter.update(local_ids)
            
            section_ids = props.get("section_entity_ids", [])
            if section_ids:
                entity_counter.update({eid: 0.5 for eid in section_ids})
        
        return dict(entity_counter.most_common())
        
    except Exception as e:
        msg.warn(f"  Erro ao calcular frequência em chunks: {str(e)}")
        return {}


async def get_entity_hierarchy(
    client,
    collection_name: str,
    doc_uuid: str,
    min_frequency: int = 1
) -> List[Tuple[str, int, float]]:
    """
    Retorna hierarquia de entidades por frequência em um documento.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection de embedding
        doc_uuid: UUID do documento
        min_frequency: Frequência mínima para incluir (default: 1)
        
    Returns:
        Lista de tuplas (entity_id, count, percentage) ordenada por frequência
        - entity_id: ID da entidade
        - count: Número de menções
        - percentage: Porcentagem do total (0.0-1.0)
        
    Exemplo:
        hierarchy = await get_entity_hierarchy(
            client,
            "VERBA_Embedding_all_MiniLM_L6_v2",
            "doc-123"
        )
        # Retorna: [
        #   ("Q312", 15, 0.58),  # Apple: 15 menções, 58% do total
        #   ("Q2283", 8, 0.31),  # Microsoft: 8 menções, 31% do total
        #   ("Q95", 3, 0.12)     # Google: 3 menções, 12% do total
        # ]
    """
    freq = await get_entity_frequency_in_document(client, collection_name, doc_uuid)
    
    if not freq:
        return []
    
    # Filtrar por frequência mínima
    filtered = {eid: count for eid, count in freq.items() if count >= min_frequency}
    
    if not filtered:
        return []
    
    # Calcular total
    total = sum(filtered.values())
    
    # Calcular porcentagens e ordenar
    hierarchy = [
        (eid, count, count / total)
        for eid, count in sorted(filtered.items(), key=lambda x: x[1], reverse=True)
    ]
    
    return hierarchy


async def get_dominant_entity(
    client,
    collection_name: str,
    doc_uuid: str
) -> Tuple[str, int, float]:
    """
    Retorna a entidade dominante (mais frequente) em um documento.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection de embedding
        doc_uuid: UUID do documento
        
    Returns:
        Tupla (entity_id, count, percentage) ou (None, 0, 0.0) se não houver
        
    Exemplo:
        dominant = await get_dominant_entity(
            client,
            "VERBA_Embedding_all_MiniLM_L6_v2",
            "doc-123"
        )
        # Retorna: ("Q312", 15, 0.58)  # Apple é dominante
    """
    hierarchy = await get_entity_hierarchy(client, collection_name, doc_uuid)
    
    if hierarchy:
        return hierarchy[0]  # Primeira (mais frequente)
    
    return (None, 0, 0.0)


async def get_entity_ratio(
    client,
    collection_name: str,
    doc_uuid: str,
    entity_id_1: str,
    entity_id_2: str
) -> Tuple[float, Dict[str, int]]:
    """
    Calcula razão entre duas entidades em um documento.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection de embedding
        doc_uuid: UUID do documento
        entity_id_1: Primeira entidade
        entity_id_2: Segunda entidade
        
    Returns:
        Tupla (ratio, frequencies)
        - ratio: Razão entity_id_1 / entity_id_2 (infinito se entity_id_2 = 0)
        - frequencies: Dict com frequências de ambas
        
    Exemplo:
        ratio, freqs = await get_entity_ratio(
            client,
            "VERBA_Embedding_all_MiniLM_L6_v2",
            "doc-123",
            "Q312",  # Apple
            "Q2283"  # Microsoft
        )
        # Retorna: (1.875, {"Q312": 15, "Q2283": 8})
        # Significa: Apple aparece 1.875x mais que Microsoft
    """
    freq = await get_entity_frequency_in_document(client, collection_name, doc_uuid)
    
    count_1 = freq.get(entity_id_1, 0)
    count_2 = freq.get(entity_id_2, 0)
    
    if count_2 == 0:
        ratio = float('inf') if count_1 > 0 else 0.0
    else:
        ratio = count_1 / count_2
    
    return (ratio, {entity_id_1: count_1, entity_id_2: count_2})

