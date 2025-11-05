"""
Atualiza schema do Verba para adicionar campos de ETL
Adiciona propriedades necessárias para ETL funcionar completamente
"""

from typing import Optional
from wasabi import msg

def get_verba_standard_properties():
    """
    Retorna lista de propriedades padrão do Verba (baseadas em chunk.to_json())
    
    OTIMIZAÇÃO FASE 1: Adicionados indexFilterable aos fields críticos para performance
    - doc_uuid: usado em hierarchical filtering
    - labels: usado em document filtering
    - chunk_lang: usado em bilingual filtering
    - chunk_date: usado em temporal filtering
    
    Returns:
        Lista de Property objects do Weaviate
    """
    from weaviate.classes.config import Property, DataType
    
    return [
        Property(name="chunk_id", data_type=DataType.NUMBER, description="ID único do chunk"),
        Property(name="end_i", data_type=DataType.NUMBER, description="Índice final no documento"),
        Property(
            name="chunk_date", 
            data_type=DataType.TEXT, 
            description="Data do chunk (ISO format)",
            index_filterable=True  # ⚡ Otimização: usado em temporal filtering
        ),
        Property(name="meta", data_type=DataType.TEXT, description="Metadados serializados em JSON"),
        Property(name="content", data_type=DataType.TEXT, description="Conteúdo do chunk"),
        Property(name="uuid", data_type=DataType.TEXT, description="UUID do chunk"),
        Property(
            name="doc_uuid", 
            data_type=DataType.UUID, 
            description="UUID do documento pai",
            index_filterable=True  # ⚡ Otimização: crítico para hierarchical filtering
        ),
        Property(name="content_without_overlap", data_type=DataType.TEXT, description="Conteúdo sem overlap"),
        Property(name="pca", data_type=DataType.NUMBER_ARRAY, description="Coordenadas PCA para visualização 3D"),
        Property(
            name="labels", 
            data_type=DataType.TEXT_ARRAY, 
            description="Labels do chunk",
            index_filterable=True  # ⚡ Otimização: usado em document filtering
        ),
        Property(name="title", data_type=DataType.TEXT, description="Título do documento"),
        Property(name="start_i", data_type=DataType.NUMBER, description="Índice inicial no documento"),
        Property(
            name="chunk_lang", 
            data_type=DataType.TEXT, 
            description="Código de idioma (pt, en, etc.)",
            index_filterable=True  # ⚡ Otimização: usado em bilingual filtering
        ),
    ]


def get_etl_properties():
    """
    Retorna lista de propriedades de ETL para adicionar a collections
    
    NOTA: Essas propriedades são OPCIONAIS - chunks normais podem deixá-las vazias.
    Schema ETL-aware serve para AMBOS os casos (chunks normais e ETL-aware).
    
    OTIMIZAÇÃO FASE 1: Adicionados indexFilterable aos fields críticos
    - entities_local_ids: usado em entity filtering e agregações
    - primary_entity_id: usado em entity filtering
    
    Returns:
        Lista de Property objects do Weaviate
    """
    from weaviate.classes.config import Property, DataType
    
    return [
        # ETL pré-chunking
        Property(
            name="entities_local_ids",
            data_type=DataType.TEXT_ARRAY,
            description="Entity IDs localizadas no chunk (ETL pré-chunking) - opcional",
            index_filterable=True  # ⚡ Otimização: crítico para entity filtering e agregações
        ),
        
        # ETL pós-chunking
        Property(
            name="section_title",
            data_type=DataType.TEXT,
            description="Título da seção identificada (ETL pós-chunking) - opcional",
        ),
        Property(
            name="section_entity_ids",
            data_type=DataType.TEXT_ARRAY,
            description="Entity IDs relacionadas à seção (ETL pós-chunking) - opcional",
        ),
        Property(
            name="section_scope_confidence",
            data_type=DataType.NUMBER,
            description="Confiança na identificação da seção (0.0-1.0) - opcional",
        ),
        Property(
            name="primary_entity_id",
            data_type=DataType.TEXT,
            description="Entity ID primária do chunk - opcional",
            index_filterable=True  # ⚡ Otimização: usado em entity filtering
        ),
        Property(
            name="entity_focus_score",
            data_type=DataType.NUMBER,
            description="Score de foco da entidade primária (0.0-1.0) - opcional",
        ),
        Property(
            name="etl_version",
            data_type=DataType.TEXT,
            description="Versão do ETL aplicado - opcional",
        ),
    ]


def get_all_embedding_properties():
    """
    Retorna TODAS as propriedades para collections de embedding (padrão + ETL)
    
    Schema ETL-aware serve para AMBOS:
    - Chunks normais: deixam propriedades ETL vazias
    - Chunks ETL-aware: preenchem propriedades ETL
    
    Returns:
        Lista completa de Property objects
    """
    return get_verba_standard_properties() + get_etl_properties()


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
        config = await collection.config.get()
        
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
        msg.info(f"📋 Verificando {collection_name}...")
        has_etl = await check_collection_has_etl_properties(client, collection_name)
        results[collection_name] = has_etl
        if has_etl:
            msg.info(f"   ✅ {collection_name} já tem schema ETL-aware")
        else:
            msg.warn(f"   ⚠️  {collection_name} não tem schema ETL-aware (deletar e recriar para adicionar)")
    
    return results


def patch_weaviate_manager_verify_collection():
    """
    Patch no verify_collection para criar collections com propriedades ETL-aware desde o início
    
    IMPORTANTE: Schema ETL-aware serve para AMBOS os casos:
    - Chunks normais: propriedades ETL ficam vazias (None/[]/0.0/"")
    - Chunks ETL-aware: propriedades ETL são preenchidas
    
    Comportamento:
    1. Se collection existe → verifica se tem propriedades ETL
    2. Se collection não existe e é VERBA_Embedding → cria com TODAS as propriedades (padrão + ETL)
    3. Se collection não existe e não é embedding → cria normalmente (sem ETL)
    
    NOTA: Weaviate v4 não permite adicionar propriedades depois que collection existe.
    Por isso criamos com todas as propriedades desde o início.
    """
    try:
        from goldenverba.components import managers
        from verba_extensions.integration.schema_updater import (
            get_all_embedding_properties,
            check_collection_has_etl_properties
        )
        
        original_verify = managers.WeaviateManager.verify_collection
        
        async def patched_verify_collection(self, client, collection_name: str):
            """Verifica collection e cria com propriedades ETL-aware se necessário"""
            
            # Se collection já existe, verifica se tem propriedades de ETL
            if await client.collections.exists(collection_name):
                has_etl = await check_collection_has_etl_properties(client, collection_name)
                if has_etl:
                    msg.info(f"✅ Collection {collection_name} já tem schema ETL-aware")
                    return True
                else:
                    msg.warn(f"⚠️  Collection {collection_name} existe mas NÃO tem schema ETL-aware")
                    msg.warn(f"   ⚠️  Weaviate v4 não permite adicionar propriedades depois")
                    msg.warn(f"   💡 Delete e recrie a collection para ter schema ETL-aware")
                    msg.warn(f"   📝 Chunks normais funcionarão, mas ETL pós-chunking não salvará metadados")
                    # Ainda retorna True para não quebrar o fluxo
                    return True
            
            # Se collection não existe e é de embedding, cria com schema ETL-aware
            if "VERBA_Embedding" in collection_name:
                try:
                    # Obtém todas as propriedades (padrão Verba + ETL)
                    all_properties = get_all_embedding_properties()
                    
                    msg.info(f"🔧 Criando collection {collection_name} com schema ETL-aware...")
                    msg.info(f"   📋 Total de propriedades: {len(all_properties)}")
                    msg.info(f"   📝 Schema serve para chunks normais E ETL-aware (propriedades ETL são opcionais)")
                    
                    # Cria collection com todas as propriedades
                    # NOTA: Não especificamos vectorizer - Verba não usa vectorizer do Weaviate
                    # (gera embeddings localmente e insere os vetores)
                    collection = await client.collections.create(
                        name=collection_name,
                        properties=all_properties,
                    )
                    
                    if collection:
                        msg.good(f"✅ Collection {collection_name} criada com schema ETL-aware!")
                        msg.info(f"   ✅ Chunks normais podem usar (propriedades ETL opcionais)")
                        msg.info(f"   ✅ Chunks ETL-aware podem usar (propriedades ETL preenchidas)")
                        return True
                    else:
                        msg.warn(f"⚠️  Falha ao criar collection {collection_name}")
                        # Fallback para método original
                        return await original_verify(self, client, collection_name)
                    
                except Exception as e:
                    msg.warn(f"⚠️  Erro ao criar collection com schema ETL-aware: {str(e)}")
                    msg.warn(f"   💡 Tentando criar collection padrão como fallback...")
                    import traceback
                    traceback.print_exc()
                    # Fallback para método original
                    return await original_verify(self, client, collection_name)
            
            # Para collections não-embedding, usa método original
            return await original_verify(self, client, collection_name)
        
        # Substitui método
        managers.WeaviateManager.verify_collection = patched_verify_collection
        msg.good("✅ Patch de schema ETL-aware aplicado - collections serão criadas com ETL desde o início")
        return True
        
    except Exception as e:
        msg.warn(f"⚠️  Erro ao aplicar patch de schema: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

