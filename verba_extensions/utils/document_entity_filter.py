"""
Helper: Filtro de Documentos por Entidade
Obtém lista de documentos que contêm uma entidade específica

Usado para filtros hierárquicos:
1. Nível 1: Filtrar documentos que contêm entidade X
2. Nível 2: Filtrar chunks dentro desses documentos que contêm entidade Y
"""

from typing import List, Optional
from wasabi import msg


async def get_documents_by_entity(
    client,
    collection_name: str,
    entity_id: str,
    limit: int = 1000
) -> List[str]:
    """
    Retorna lista de doc_uuid de documentos que contêm a entidade especificada.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection de embedding (ex: "VERBA_Embedding_all_MiniLM_L6_v2")
        entity_id: Entity ID (ex: "Q312" para Apple)
        limit: Número máximo de chunks a buscar (default: 1000)
        
    Returns:
        Lista de doc_uuid únicos (sem duplicatas)
        
    Exemplo:
        doc_uuids = await get_documents_by_entity(
            client,
            "VERBA_Embedding_all_MiniLM_L6_v2",
            "Q312"  # Apple
        )
        # Retorna: ["doc-1", "doc-2", "doc-3"] (documentos que têm chunks com Apple)
    """
    try:
        from verba_extensions.compatibility.weaviate_imports import Filter
        
        collection = client.collections.get(collection_name)
        
        # Buscar chunks com a entidade
        # Verifica tanto entities_local_ids quanto section_entity_ids
        entity_filter_local = Filter.by_property("entities_local_ids").contains_any([entity_id])
        entity_filter_section = Filter.by_property("section_entity_ids").contains_any([entity_id])
        
        # Combinar: chunks que têm entidade em entities_local_ids OU section_entity_ids
        combined_entity_filter = Filter.any_of([entity_filter_local, entity_filter_section])
        
        results = await collection.query.fetch_objects(
            filters=combined_entity_filter,
            limit=limit,
            return_properties=["doc_uuid"]
        )
        
        # Extrair doc_uuid únicos
        doc_uuids = []
        seen = set()
        for obj in results.objects:
            doc_uuid = str(obj.properties.get("doc_uuid", ""))
            if doc_uuid and doc_uuid not in seen:
                doc_uuids.append(doc_uuid)
                seen.add(doc_uuid)
        
        msg.info(f"  Documentos encontrados com entidade {entity_id}: {len(doc_uuids)}")
        return doc_uuids
        
    except Exception as e:
        msg.warn(f"  Erro ao buscar documentos por entidade: {str(e)}")
        return []


async def get_documents_by_multiple_entities(
    client,
    collection_name: str,
    entity_ids: List[str],
    require_all: bool = False,
    limit: int = 1000
) -> List[str]:
    """
    Retorna lista de doc_uuid de documentos que contêm as entidades especificadas.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection de embedding
        entity_ids: Lista de Entity IDs (ex: ["Q312", "Q2283"])
        require_all: Se True, documento deve conter TODAS as entidades. Se False, qualquer uma (default: False)
        limit: Número máximo de chunks a buscar (default: 1000)
        
    Returns:
        Lista de doc_uuid únicos
        
    Exemplo:
        # Documentos que contêm Apple OU Microsoft
        doc_uuids = await get_documents_by_multiple_entities(
            client,
            "VERBA_Embedding_all_MiniLM_L6_v2",
            ["Q312", "Q2283"],  # Apple ou Microsoft
            require_all=False
        )
        
        # Documentos que contêm Apple E Microsoft
        doc_uuids = await get_documents_by_multiple_entities(
            client,
            "VERBA_Embedding_all_MiniLM_L6_v2",
            ["Q312", "Q2283"],  # Apple e Microsoft
            require_all=True
        )
    """
    try:
        from verba_extensions.compatibility.weaviate_imports import Filter
        
        if not entity_ids:
            return []
        
        collection = client.collections.get(collection_name)
        
        # Criar filtros para cada entidade
        entity_filters = []
        for entity_id in entity_ids:
            entity_filter_local = Filter.by_property("entities_local_ids").contains_any([entity_id])
            entity_filter_section = Filter.by_property("section_entity_ids").contains_any([entity_id])
            combined = Filter.any_of([entity_filter_local, entity_filter_section])
            entity_filters.append(combined)
        
        # Combinar filtros
        if require_all:
            # Documento deve conter TODAS as entidades
            combined_filter = Filter.all_of(entity_filters)
        else:
            # Documento pode conter QUALQUER entidade
            combined_filter = Filter.any_of(entity_filters)
        
        results = await collection.query.fetch_objects(
            filters=combined_filter,
            limit=limit,
            return_properties=["doc_uuid"]
        )
        
        # Extrair doc_uuid únicos
        doc_uuids = []
        seen = set()
        for obj in results.objects:
            doc_uuid = str(obj.properties.get("doc_uuid", ""))
            if doc_uuid and doc_uuid not in seen:
                doc_uuids.append(doc_uuid)
                seen.add(doc_uuid)
        
        msg.info(f"  Documentos encontrados com entidades {entity_ids}: {len(doc_uuids)}")
        return doc_uuids
        
    except Exception as e:
        msg.warn(f"  Erro ao buscar documentos por múltiplas entidades: {str(e)}")
        return []

