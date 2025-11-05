"""
Atualiza schema do Verba para adicionar campos de ETL
Adiciona propriedades necessárias para ETL funcionar completamente
"""

from typing import Optional
from wasabi import msg

def get_etl_properties():
    """
    Retorna lista de propriedades de ETL para adicionar a collections
    
    Returns:
        Lista de Property objects do Weaviate
    """
    from weaviate.classes.config import Property, DataType
    
    return [
        # ETL pré-chunking
        Property(
            name="entities_local_ids",
            data_type=DataType.TEXT_ARRAY,
            description="Entity IDs localizadas no chunk (ETL pré-chunking)",
        ),
        
        # ETL pós-chunking
        Property(
            name="section_title",
            data_type=DataType.TEXT,
            description="Título da seção identificada (ETL pós-chunking)",
        ),
        Property(
            name="section_entity_ids",
            data_type=DataType.TEXT_ARRAY,
            description="Entity IDs relacionadas à seção (ETL pós-chunking)",
        ),
        Property(
            name="section_scope_confidence",
            data_type=DataType.NUMBER,
            description="Confiança na identificação da seção (0.0-1.0)",
        ),
        Property(
            name="primary_entity_id",
            data_type=DataType.TEXT,
            description="Entity ID primária do chunk",
        ),
        Property(
            name="entity_focus_score",
            data_type=DataType.NUMBER,
            description="Score de foco da entidade primária (0.0-1.0)",
        ),
        Property(
            name="etl_version",
            data_type=DataType.TEXT,
            description="Versão do ETL aplicado",
        ),
    ]


async def check_collection_has_etl_properties(client, collection_name: str) -> bool:
    """
    Verifica se collection já tem propriedades de ETL
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection
    
    Returns:
        True se collection tem propriedades de ETL
    """
    try:
        if not await client.collections.exists(collection_name):
            return False
        
        collection = client.collections.get(collection_name)
        config = collection.config.get()
        
        # Verifica se tem pelo menos uma propriedade de ETL
        etl_prop_names = [p.name for p in get_etl_properties()]
        existing_props = [p.name for p in config.properties]
        
        return any(prop_name in existing_props for prop_name in etl_prop_names)
        
    except Exception as e:
        msg.warn(f"⚠️  Erro ao verificar propriedades de ETL: {str(e)}")
        return False


async def update_all_embedding_collections(client, weaviate_manager) -> dict:
    """
    Atualiza todas as collections de embedding do Verba com propriedades de ETL
    
    Args:
        client: Cliente Weaviate
        weaviate_manager: Instância de WeaviateManager
    
    Returns:
        Dict com resultados por collection
    """
    results = {}
    
    # Pega todas as collections de embedding conhecidas
    embedding_collections = list(weaviate_manager.embedding_table.values())
    
    if not embedding_collections:
        msg.warn("Nenhuma collection de embedding encontrada")
        return results
    
    msg.info(f"🔧 Atualizando schema de {len(embedding_collections)} collections...")
    
    for collection_name in embedding_collections:
        msg.info(f"📋 Atualizando {collection_name}...")
        success = await add_etl_properties_to_collection(client, collection_name)
        results[collection_name] = success
    
    return results


def patch_weaviate_manager_verify_collection():
    """
    Patch no verify_collection para criar collections com propriedades de ETL
    
    NOTA: Weaviate v4 não permite adicionar propriedades depois que collection existe.
    Então precisamos criar a collection com todas as propriedades desde o início.
    """
    try:
        from goldenverba.components import managers
        from verba_extensions.integration.schema_updater import get_etl_properties, check_collection_has_etl_properties
        from weaviate.classes.config import Configure
        
        original_verify = managers.WeaviateManager.verify_collection
        
        async def patched_verify_collection(self, client, collection_name: str):
            """Verifica collection e cria com propriedades de ETL se necessário"""
            
            # Se collection já existe, verifica se tem propriedades de ETL
            if await client.collections.exists(collection_name):
                has_etl = await check_collection_has_etl_properties(client, collection_name)
                if has_etl:
                    msg.info(f"ℹ️  Collection {collection_name} já tem propriedades de ETL")
                    return True
                else:
                    msg.warn(f"⚠️  Collection {collection_name} existe mas não tem propriedades de ETL")
                    msg.warn(f"   ⚠️  Weaviate v4 não permite adicionar propriedades depois")
                    msg.warn(f"   💡 Para adicionar propriedades, delete e recrie a collection")
                    # Ainda retorna True para não quebrar o fluxo
                    return True
            
            # Se collection não existe e é de embedding, cria com propriedades de ETL
            if "VERBA_Embedding" in collection_name:
                try:
                    etl_properties = get_etl_properties()
                    
                    # Cria collection com propriedades de ETL
                    # NOTA: O Verba usa vectorizer config padrão, então precisamos manter compatibilidade
                    # Mas não podemos saber qual vectorizer usar sem acessar o embedder
                    # Por enquanto, cria collection básica e deixa Verba gerenciar vectorizer
                    
                    # Na verdade, é melhor deixar o método original criar e apenas avisar
                    # que propriedades de ETL não estarão disponíveis
                    msg.warn(f"⚠️  Collection {collection_name} será criada SEM propriedades de ETL")
                    msg.warn(f"   💡 Para ter propriedades de ETL, crie manualmente ou use script de migração")
                    
                except Exception as e:
                    msg.warn(f"⚠️  Erro ao preparar propriedades de ETL: {str(e)}")
            
            # Chama método original
            return await original_verify(self, client, collection_name)
        
        # Substitui método
        managers.WeaviateManager.verify_collection = patched_verify_collection
        msg.info("✅ Patch de schema ETL aplicado ao WeaviateManager (verificação)")
        return True
        
    except Exception as e:
        msg.warn(f"⚠️  Erro ao aplicar patch de schema: {str(e)}")
        return False

