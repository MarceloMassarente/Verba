"""
Atualiza schema do Verba para adicionar campos de ETL
Adiciona propriedades necessárias para ETL funcionar completamente
"""

import os
from typing import Optional, Dict, Any
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
        Property(
            name="entity_mentions",
            data_type=DataType.TEXT,
            description="JSON array de entidades detectadas (modo inteligente): [{text, label, confidence}] - opcional",
        ),
        Property(
            name="section_first_para",
            data_type=DataType.TEXT,
            description="Primeiro parágrafo da seção (contexto para Section Scope) - opcional",
        ),
        Property(
            name="parent_entities",
            data_type=DataType.TEXT_ARRAY,
            description="Entity IDs do documento pai (herança para Section Scope) - opcional",
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


def get_framework_properties():
    """
    Retorna lista de propriedades de framework para adicionar a collections
    
    NOTA: Essas propriedades são OPCIONAIS - chunks normais podem deixá-las vazias.
    Schema framework-aware serve para AMBOS os casos (chunks normais e framework-aware).
    
    Returns:
        Lista de Property objects do Weaviate
    """
    from weaviate.classes.config import Property, DataType
    
    return [
        Property(
            name="frameworks",
            data_type=DataType.TEXT_ARRAY,
            description="Frameworks detectados (SWOT, Porter, BCG, etc.)",
            index_filterable=True
        ),
        Property(
            name="companies",
            data_type=DataType.TEXT_ARRAY,
            description="Empresas mencionadas no chunk",
            index_filterable=True
        ),
        Property(
            name="sectors",
            data_type=DataType.TEXT_ARRAY,
            description="Setores/indústrias mencionados",
            index_filterable=True
        ),
        Property(
            name="framework_confidence",
            data_type=DataType.NUMBER,
            description="Confiança na detecção de frameworks (0.0-1.0)"
        ),
    ]


def get_named_vector_text_properties():
    """
    Retorna propriedades de texto que alimentam named vectors.
    
    Essas propriedades contêm texto especializado extraído do chunk:
    - concept_text: Conceitos abstratos (frameworks, estratégias, metodologias)
    - sector_text: Setores/indústrias (varejo, bancos, tecnologia)
    - company_text: Empresas específicas (Apple, Microsoft, etc.)
    
    NOTA: Essas propriedades são OPCIONAIS - apenas necessárias se named vectors estiverem habilitados.
    
    Returns:
        Lista de Property objects do Weaviate
    """
    from weaviate.classes.config import Property, DataType
    
    return [
        Property(
            name="concept_text",
            data_type=DataType.TEXT,
            description="Texto focado em conceitos abstratos (frameworks, estratégias, metodologias) - usado para concept_vec",
            tokenization="word"  # Word tokenization para busca textual
        ),
        Property(
            name="sector_text",
            data_type=DataType.TEXT,
            description="Texto focado em setores/indústrias - usado para sector_vec",
            tokenization="word"  # Word tokenization para busca textual
        ),
        Property(
            name="company_text",
            data_type=DataType.TEXT,
            description="Texto focado em empresas específicas - usado para company_vec",
            tokenization="word"  # Word tokenization para busca textual
        ),
    ]


def get_all_embedding_properties(include_named_vectors: bool = False):
    """
    Retorna TODAS as propriedades para collections de embedding.
    
    Schema completo serve para AMBOS:
    - Chunks normais: deixam propriedades ETL/framework vazias
    - Chunks ETL-aware: preenchem propriedades ETL
    - Chunks framework-aware: preenchem propriedades de framework
    - Chunks com named vectors: preenchem concept_text, sector_text, company_text
    
    Args:
        include_named_vectors: Se True, inclui propriedades de texto para named vectors
    
    Returns:
        Lista completa de Property objects
    """
    properties = (
        get_verba_standard_properties() + 
        get_etl_properties() + 
        get_framework_properties()
    )
    
    if include_named_vectors:
        properties = properties + get_named_vector_text_properties()
    
    return properties


def get_vector_config(
    enable_named_vectors: bool = False,
    estimated_count: int = 0,
    use_pq: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Retorna vectorConfig para collections com named vectors.
    
    Args:
        enable_named_vectors: Se True, retorna vectorConfig com named vectors
        estimated_count: Número estimado de objetos (para PQ)
        use_pq: Se True, ativa PQ automaticamente se count >= threshold
    
    Returns:
        Dict com vectorConfig ou None se desabilitado
    """
    if not enable_named_vectors:
        return None
    
    try:
        from verba_extensions.integration.vector_config_builder import build_named_vectors_config
        return build_named_vectors_config(
            enable_named_vectors=True,
            estimated_count=estimated_count,
            use_pq=use_pq
        )
    except ImportError:
        # Se vector_config_builder não estiver disponível, retorna None
        return None


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
            
            # Collections que NUNCA precisam de schema ETL-aware (apenas configurações)
            config_only_collections = ["VERBA_CONFIGURATION", "VERBA_SUGGESTIONS"]
            
            # Collections que devem ter schema ETL-aware (documentos podem ter metadados ETL)
            etl_collections = ["VERBA_DOCUMENTS"]  # Documentos podem ter metadados ETL agregados
            
            # Se collection já existe, verifica se tem propriedades de ETL
            if await client.collections.exists(collection_name):
                # Para collections de configuração, não verifica schema ETL (não precisam)
                if collection_name in config_only_collections:
                    # Usa método original sem verificar ETL
                    return await original_verify(self, client, collection_name)
                
                # Para collections que devem ter ETL (embedding ou documentos), verifica
                should_have_etl = ("VERBA_Embedding" in collection_name) or (collection_name in etl_collections)
                
                if should_have_etl:
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
                else:
                    # Collection que não precisa de ETL - usa método original
                    return await original_verify(self, client, collection_name)
            
            # Se collection não existe e deve ter ETL, cria com schema ETL-aware
            should_create_with_etl = ("VERBA_Embedding" in collection_name) or (collection_name in etl_collections)
            
            if should_create_with_etl:
                try:
                    # Verifica se named vectors estão habilitados (via env var ou padrão False)
                    enable_named_vectors = os.getenv("ENABLE_NAMED_VECTORS", "false").lower() == "true"
                    
                    # Obtém todas as propriedades (padrão Verba + ETL + opcionalmente named vectors)
                    all_properties = get_all_embedding_properties(include_named_vectors=enable_named_vectors)
                    
                    # Obtém vectorConfig se named vectors estiverem habilitados
                    vector_config = None
                    if enable_named_vectors:
                        # Estima count baseado em collection existente ou usa 0
                        estimated_count = 0
                        try:
                            # Tenta obter count de collection similar se existir
                            all_collections = await client.collections.list_all()
                            for coll_name in all_collections:
                                if "VERBA_Embedding" in coll_name:
                                    coll = client.collections.get(coll_name)
                                    count = await coll.length()
                                    estimated_count = max(estimated_count, count)
                                    break
                        except:
                            pass  # Se falhar, usa 0
                        
                        vector_config = get_vector_config(
                            enable_named_vectors=True,
                            estimated_count=estimated_count,
                            use_pq=True
                        )
                    
                    msg.info(f"🔧 Criando collection {collection_name} com schema ETL-aware...")
                    msg.info(f"   📋 Total de propriedades: {len(all_properties)}")
                    if enable_named_vectors:
                        msg.info(f"   🎯 Named vectors habilitados: concept_vec, sector_vec, company_vec")
                    msg.info(f"   📝 Schema serve para chunks normais E ETL-aware (propriedades ETL são opcionais)")
                    
                    # Cria collection com todas as propriedades e opcionalmente vectorConfig
                    # NOTA: Não especificamos vectorizer - Verba não usa vectorizer do Weaviate
                    # (gera embeddings localmente e insere os vetores - modo BYOV)
                    
                    if vector_config:
                        # Para named vectors, precisamos usar create_from_dict (API mais flexível)
                        # Constrói schema completo como dict
                        from weaviate.classes.config import Configure
                        
                        schema_dict = {
                            "class": collection_name,
                            "description": f"Collection com named vectors: concept_vec, sector_vec, company_vec",
                            "vectorConfig": vector_config,
                            "properties": [
                                {
                                    "name": prop.name,
                                    "dataType": [prop.data_type.value] if hasattr(prop.data_type, 'value') else [str(prop.data_type)],
                                    "description": prop.description or "",
                                    "tokenization": prop.tokenization.value if hasattr(prop.tokenization, 'value') else str(prop.tokenization) if hasattr(prop, 'tokenization') and prop.tokenization else None,
                                    "indexFilterable": prop.index_filterable if hasattr(prop, 'index_filterable') else False,
                                    "indexSearchable": prop.index_searchable if hasattr(prop, 'index_searchable') else False,
                                }
                                for prop in all_properties
                                if prop.tokenization is not None  # Remove None tokenization
                            ]
                        }
                        
                        # Remove None values do schema
                        schema_dict["properties"] = [
                            {k: v for k, v in prop.items() if v is not None}
                            for prop in schema_dict["properties"]
                        ]
                        
                        try:
                            # Usa create_from_dict para named vectors
                            collection = await client.collections.create_from_dict(schema_dict)
                            msg.info(f"   ✅ Collection criada usando create_from_dict (named vectors)")
                        except Exception as dict_error:
                            msg.warn(f"   ⚠️  Erro ao criar com create_from_dict: {str(dict_error)}")
                            msg.warn(f"   💡 Tentando criar sem named vectors como fallback...")
                            # Fallback: cria sem named vectors
                            collection = await client.collections.create(
                                name=collection_name,
                                properties=all_properties,
                            )
                    else:
                        # Sem named vectors - usa API normal
                        collection = await client.collections.create(
                            name=collection_name,
                            properties=all_properties,
                        )
                    
                    if collection:
                        msg.good(f"✅ Collection {collection_name} criada com schema ETL-aware!")
                        if enable_named_vectors:
                            msg.good(f"   🎯 Named vectors habilitados!")
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
            
            # Para collections que não precisam de ETL (configurações), usa método original
            # Essas collections não precisam de schema ETL-aware
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

