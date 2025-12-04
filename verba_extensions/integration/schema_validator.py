"""
Schema Validator para Verba
Valida propriedades de collections do Weaviate sem modificar schema

Funcionalidades:
- Validar se collection tem todas as propriedades necessárias antes de usar
- Detectar incompatibilidades de schema
- Gerar relatório de validação
"""

from typing import List, Dict, Optional, Set
from wasabi import msg


async def validate_collection_schema(
    client, 
    collection_name: str, 
    required_props: List[str]
) -> Dict:
    """
    Valida schema sem modificar collection.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection a validar
        required_props: Lista de nomes de propriedades obrigatórias
    
    Returns:
        Dict com:
        - valid: bool - Se schema é válido
        - missing: List[str] - Propriedades faltando
        - warnings: List[str] - Avisos sobre schema
        - existing: List[str] - Propriedades existentes
    """
    result = {
        "valid": False,
        "missing": [],
        "warnings": [],
        "existing": [],
        "collection_exists": False
    }
    
    try:
        # Verifica se collection existe
        if not await client.collections.exists(collection_name):
            result["warnings"].append(f"Collection '{collection_name}' não existe")
            return result
        
        result["collection_exists"] = True
        
        # Obtém configuração da collection
        collection = client.collections.get(collection_name)
        config = await collection.config.get()
        
        # Lista propriedades existentes
        existing_props = [prop.name for prop in config.properties]
        result["existing"] = existing_props
        
        # Verifica propriedades obrigatórias
        missing_props = [prop for prop in required_props if prop not in existing_props]
        result["missing"] = missing_props
        
        # Schema é válido se não faltam propriedades obrigatórias
        result["valid"] = len(missing_props) == 0
        
        # Gera avisos se necessário
        if missing_props:
            result["warnings"].append(
                f"Collection '{collection_name}' está faltando {len(missing_props)} propriedade(s): {', '.join(missing_props)}"
            )
        
        return result
        
    except Exception as e:
        result["warnings"].append(f"Erro ao validar schema: {str(e)}")
        return result


async def collection_has_properties(
    client,
    collection_name: str,
    property_names: List[str]
) -> bool:
    """
    Verifica se collection tem todas as propriedades especificadas.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection
        property_names: Lista de nomes de propriedades a verificar
    
    Returns:
        True se collection tem todas as propriedades
    """
    try:
        if not await client.collections.exists(collection_name):
            return False
        
        collection = client.collections.get(collection_name)
        config = await collection.config.get()
        existing_props = {prop.name for prop in config.properties}
        
        return all(prop_name in existing_props for prop_name in property_names)
        
    except Exception as e:
        msg.warn(f"Erro ao verificar propriedades: {str(e)}")
        return False


async def collection_has_framework_properties(client, collection_name: str) -> bool:
    """
    Verifica se collection tem propriedades de framework.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection
    
    Returns:
        True se collection tem propriedades de framework (básicas ou expandidas)
    """
    # Propriedades básicas (obrigatórias para considerar que tem framework properties)
    framework_props_basic = ["frameworks", "companies", "sectors", "framework_confidence"]
    
    # Propriedades expandidas (opcionais, mas indicam schema completo)
    framework_props_expanded = [
        "persons", "conceitos_negocio", "metricas_mencionadas", "tipo_conteudo"
    ]
    
    # Verifica se tem pelo menos as propriedades básicas
    has_basic = await collection_has_properties(client, collection_name, framework_props_basic)
    
    # Se tem básicas, verifica se também tem expandidas (para relatórios)
    if has_basic:
        has_expanded = await collection_has_properties(client, collection_name, framework_props_expanded)
        if has_expanded:
            msg.debug(f"Collection {collection_name} tem schema de framework completo (básico + expandido)")
    
    return has_basic


async def collection_has_v019_properties(client, collection_name: str) -> bool:
    """
    Verifica se collection tem propriedades V019.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection
    
    Returns:
        True se collection tem propriedades V019
    """
    v019_props = [
        "semantic_bridge_quality",
        "slide_position",
        "slide_type",
        "pattern_genetics",
        "reusability_score",
        "visual_archetype"
    ]
    return await collection_has_properties(client, collection_name, v019_props)


async def get_collection_properties(client, collection_name: str) -> List[str]:
    """
    Obtém lista de propriedades de uma collection.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection
    
    Returns:
        Lista de nomes de propriedades
    """
    try:
        if not await client.collections.exists(collection_name):
            return []
        
        collection = client.collections.get(collection_name)
        config = await collection.config.get()
        return [prop.name for prop in config.properties]
        
    except Exception as e:
        msg.warn(f"Erro ao obter propriedades: {str(e)}")
        return []


async def validate_collection_for_framework_features(
    client,
    collection_name: str
) -> Dict:
    """
    Valida se collection está pronta para usar features de framework.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection
    
    Returns:
        Dict com resultado da validação
    """
    # Propriedades básicas (obrigatórias)
    framework_props_basic = ["frameworks", "companies", "sectors", "framework_confidence"]
    
    # Propriedades expandidas (opcionais, mas recomendadas)
    framework_props_expanded = [
        "persons", "conceitos_negocio", "metricas_mencionadas", "tipo_conteudo"
    ]
    
    # Valida propriedades básicas
    result_basic = await validate_collection_schema(client, collection_name, framework_props_basic)
    
    # Verifica propriedades expandidas (não obrigatórias)
    result_expanded = await validate_collection_schema(client, collection_name, framework_props_expanded)
    
    # Combina resultados
    result = {
        "valid": result_basic["valid"],
        "missing_basic": result_basic["missing"],
        "missing_expanded": result_expanded["missing"],
        "warnings": result_basic["warnings"] + result_expanded["warnings"],
        "existing": result_basic["existing"],
        "has_expanded_features": len(result_expanded["missing"]) == 0
    }
    
    return result


async def get_schema_compatibility_report(
    client,
    collection_name: str
) -> Dict:
    """
    Gera relatório de compatibilidade de schema.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection
    
    Returns:
        Dict com relatório detalhado
    """
    report = {
        "collection_name": collection_name,
        "exists": False,
        "has_standard_props": False,
        "has_etl_props": False,
        "has_framework_props": False,
        "properties": [],
        "missing_standard": [],
        "missing_etl": [],
        "missing_framework": [],
        "recommendations": []
    }
    
    try:
        if not await client.collections.exists(collection_name):
            report["recommendations"].append("Collection não existe - será criada com schema completo na próxima ingestão")
            return report
        
        report["exists"] = True
        
        # Obtém propriedades existentes
        existing_props = await get_collection_properties(client, collection_name)
        report["properties"] = existing_props
        
        # Verifica propriedades padrão
        from verba_extensions.integration.schema_updater import get_verba_standard_properties
        standard_props = [p.name for p in get_verba_standard_properties()]
        report["has_standard_props"] = all(prop in existing_props for prop in standard_props)
        report["missing_standard"] = [p for p in standard_props if p not in existing_props]
        
        # Verifica propriedades ETL
        from verba_extensions.integration.schema_updater import get_etl_properties
        etl_props = [p.name for p in get_etl_properties()]
        report["has_etl_props"] = any(prop in existing_props for prop in etl_props)
        report["missing_etl"] = [p for p in etl_props if p not in existing_props]
        
        # Verifica propriedades de framework
        framework_props_basic = ["frameworks", "companies", "sectors", "framework_confidence"]
        framework_props_expanded = ["persons", "conceitos_negocio", "metricas_mencionadas", "tipo_conteudo"]
        
        report["has_framework_props"] = all(prop in existing_props for prop in framework_props_basic)
        report["has_framework_expanded"] = all(prop in existing_props for prop in framework_props_expanded)
        
        missing_framework_basic = [prop for prop in framework_props_basic if prop not in existing_props]
        missing_framework_expanded = [prop for prop in framework_props_expanded if prop not in existing_props]
        
        report["missing_framework"] = missing_framework_basic + missing_framework_expanded
        report["missing_framework"] = [p for p in framework_props if p not in existing_props]
        
        # Gera recomendações
        if not report["has_framework_props"]:
            report["recommendations"].append(
                "Collection não tem propriedades de framework. "
                "Para usar detecção de frameworks, migre a collection usando o script de migração."
            )
        elif not report.get("has_framework_expanded", False):
            report["recommendations"].append(
                "Collection tem propriedades básicas de framework, mas não tem propriedades expandidas "
                "(persons, conceitos_negocio, metricas_mencionadas, tipo_conteudo). "
                "Para usar todas as funcionalidades de enriquecimento, recrie a collection com schema completo."
            )
        
        if not report["has_etl_props"]:
            report["recommendations"].append(
                "Collection não tem propriedades de ETL. "
                "Algumas funcionalidades avançadas podem não estar disponíveis."
            )
        
        return report
        
    except Exception as e:
        report["recommendations"].append(f"Erro ao gerar relatório: {str(e)}")
        return report

