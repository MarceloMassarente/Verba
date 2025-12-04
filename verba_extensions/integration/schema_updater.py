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
    from weaviate.classes.config import Property, DataType, Tokenization
    
    return [
        Property(name="chunk_id", data_type=DataType.NUMBER, description="ID único do chunk"),
        Property(name="end_i", data_type=DataType.NUMBER, description="Índice final no documento"),
        Property(
            name="chunk_date", 
            data_type=DataType.DATE, 
            description="Data do chunk (ISO format: YYYY-MM-DD ou RFC3339)",
            index_filterable=True,  # ⚡ Otimização: usado em temporal filtering
            index_range_filterable=True  # ⚡ Otimização: permite range queries (>=, <=, between)
        ),
        Property(name="meta", data_type=DataType.TEXT, description="Metadados serializados em JSON"),
        Property(
            name="content", 
            data_type=DataType.TEXT, 
            description="Conteúdo do chunk",
            index_searchable=True,  # ⚡ Otimização BM25: crítico para busca híbrida
            tokenization=Tokenization.WORD  # ⚡ Otimização BM25: word tokenization para matching de termos
        ),
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
        Property(
            name="title", 
            data_type=DataType.TEXT, 
            description="Título do documento",
            index_searchable=True,  # ⚡ Otimização BM25: permite boost de título (title^2)
            tokenization=Tokenization.WORD  # ⚡ Otimização BM25: word tokenization
        ),
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
            name="persons",
            data_type=DataType.TEXT_ARRAY,
            description="Pessoas mencionadas (executivos, consultores, autores) - limitado a 10 por chunk",
            index_filterable=True
        ),
        Property(
            name="conceitos_negocio",
            data_type=DataType.TEXT_ARRAY,
            description="Conceitos de negócio detectados (vantagem competitiva, proposta de valor, etc.)",
            index_filterable=True
        ),
        Property(
            name="metricas_mencionadas",
            data_type=DataType.TEXT_ARRAY,
            description="Métricas e KPIs mencionados no chunk",
            index_filterable=True
        ),
        Property(
            name="tipo_conteudo",
            data_type=DataType.TEXT,
            description="Tipo de conteúdo: analise, recomendacao, acao, contexto",
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


def get_v019_properties():
    """
    Retorna lista de propriedades específicas do sistema V019 para adicionar a collections.
    
    Propriedades específicas para documentos V019 (slides de consultoria):
    - semantic_bridge_quality: Qualidade da ponte semântica (0.0-1.0)
    - slide_position: Posição no deck (opening, diagnostic, analysis, etc.)
    - slide_type: Tipo do slide (complex, simple, metadata)
    - pattern_genetics: Componentes atômicos identificados (pattern DNA)
    - reusability_score: Score de reusabilidade (0-100)
    - visual_archetype: Arquétipo visual (pyramid, matrix, flow, etc.)
    
    NOTA: Essas propriedades são OPCIONAIS - chunks normais podem deixá-las vazias.
    Schema V019-aware serve para AMBOS os casos (chunks normais e V019-aware).
    
    Returns:
        Lista de Property objects do Weaviate
    """
    from weaviate.classes.config import Property, DataType
    
    return [
        Property(
            name="semantic_bridge_quality",
            data_type=DataType.NUMBER,
            description="Qualidade da ponte semântica (0.0-1.0) - opcional",
        ),
        Property(
            name="slide_position",
            data_type=DataType.TEXT,
            description="Posição no deck (opening, diagnostic, analysis, etc.) - opcional",
            index_filterable=True  # ⚡ Otimização: usado em filtering por posição narrativa
        ),
        Property(
            name="slide_type",
            data_type=DataType.TEXT,
            description="Tipo do slide (complex, simple, metadata) - opcional",
            index_filterable=True  # ⚡ Otimização: usado em filtering por tipo de slide
        ),
        Property(
            name="pattern_genetics",
            data_type=DataType.TEXT_ARRAY,
            description="Componentes atômicos identificados (pattern DNA) - opcional",
            index_filterable=True  # ⚡ Otimização: usado em filtering por pattern reusável
        ),
        Property(
            name="reusability_score",
            data_type=DataType.NUMBER,
            description="Score de reusabilidade (0-100) - opcional",
        ),
        Property(
            name="visual_archetype",
            data_type=DataType.TEXT,
            description="Arquétipo visual (pyramid, matrix, flow, etc.) - opcional",
            index_filterable=True  # ⚡ Otimização: usado em filtering por arquétipo visual
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
    from weaviate.classes.config import Property, DataType, Tokenization
    
    return [
        Property(
            name="concept_text",
            data_type=DataType.TEXT,
            description="Texto focado em conceitos abstratos (frameworks, estratégias, metodologias) - usado para concept_vec",
            index_searchable=True,  # ⚡ Otimização BM25: permite BM25 em propriedades especializadas
            tokenization=Tokenization.WORD  # Word tokenization para busca textual
        ),
        Property(
            name="sector_text",
            data_type=DataType.TEXT,
            description="Texto focado em setores/indústrias - usado para sector_vec",
            index_searchable=True,  # ⚡ Otimização BM25: permite BM25 em propriedades especializadas
            tokenization=Tokenization.WORD  # Word tokenization para busca textual
        ),
        Property(
            name="company_text",
            data_type=DataType.TEXT,
            description="Texto focado em empresas específicas - usado para company_vec",
            index_searchable=True,  # ⚡ Otimização BM25: permite BM25 em propriedades especializadas
            tokenization=Tokenization.WORD  # Word tokenization para busca textual
        ),
    ]


def get_all_embedding_properties(include_named_vectors: bool = True):
    """
    Retorna TODAS as propriedades para collections de embedding.
    
    Schema completo serve para AMBOS:
    - Chunks normais: deixam propriedades ETL/framework/V019 vazias
    - Chunks ETL-aware: preenchem propriedades ETL
    - Chunks framework-aware: preenchem propriedades de framework
    - Chunks V019-aware: preenchem propriedades V019 (semantic bridge, slide position, etc.)
    - Chunks com named vectors: preenchem concept_text, sector_text, company_text
    
    Args:
        include_named_vectors: Se True, inclui propriedades de texto para named vectors
    
    Returns:
        Lista completa de Property objects
    """
    properties = (
        get_verba_standard_properties() + 
        get_etl_properties() + 
        get_framework_properties() +
        get_v019_properties()  # Adiciona propriedades V019
    )
    
    if include_named_vectors:
        properties = properties + get_named_vector_text_properties()
    
    return properties


def get_vector_config(
    enable_named_vectors: bool = True,
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
                    # Verifica se named vectors estão habilitados
                    # 1. Tenta pegar da configuração do Verba salva no Weaviate
                    enable_named_vectors = True  # Padrão: habilitado
                    try:
                        from goldenverba.verba_manager import VerbaManager
                        vm = VerbaManager()
                        # Tenta obter configuração salva
                        try:
                            config = await vm.weaviate_manager.get_config(
                                client, vm.rag_config_uuid
                            )
                            if config and "Advanced" in config and "Enable Named Vectors" in config["Advanced"]:
                                enable_named_vectors = config["Advanced"]["Enable Named Vectors"].get("value", True)
                                msg.info(f"📋 Named vectors lido da configuração: {enable_named_vectors}")
                        except:
                            # Se não conseguir ler, usa padrão do create_config
                            default_config = vm.create_config()
                            if "Advanced" in default_config and "Enable Named Vectors" in default_config["Advanced"]:
                                enable_named_vectors = default_config["Advanced"]["Enable Named Vectors"]["value"]
                                msg.info(f"📋 Named vectors lido do padrão: {enable_named_vectors}")
                    except Exception as e:
                        msg.debug(f"[Schema-Updater] Erro ao ler config do VerbaManager: {str(e)}")
                    
                    # 2. Fallback para variável de ambiente (compatibilidade)
                    # Se variável de ambiente estiver definida, usa ela (permite desabilitar via env)
                    env_value = os.getenv("ENABLE_NAMED_VECTORS")
                    if env_value is not None:
                        enable_named_vectors = env_value.lower() == "true"
                        if enable_named_vectors:
                            msg.info(f"📋 Named vectors lido de variável de ambiente: ENABLE_NAMED_VECTORS=true")
                        else:
                            msg.info(f"📋 Named vectors desabilitado via variável de ambiente: ENABLE_NAMED_VECTORS=false")
                    
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
                        
                        # Converte Property objects para dict format
                        properties_dict = []
                        for prop in all_properties:
                            # Verifica se Property é válido
                            if prop is None:
                                msg.warn(f"   ⚠️  Property é None - pulando")
                                continue
                            
                            # Verifica se Property tem data_type antes de acessar
                            if not hasattr(prop, 'data_type'):
                                prop_name = getattr(prop, 'name', 'unknown')
                                msg.warn(f"   ⚠️  Property {prop_name} não tem atributo 'data_type' - pulando")
                                msg.debug(f"   🔍 Tipo do objeto: {type(prop)}")
                                msg.debug(f"   🔍 Atributos disponíveis: {dir(prop)}")
                                continue
                            
                            # Verifica se nome e data_type são válidos
                            if not hasattr(prop, 'name') or not prop.name:
                                msg.warn(f"   ⚠️  Property não tem atributo 'name' - pulando")
                                continue
                            
                            if not prop.data_type:
                                msg.warn(f"   ⚠️  Property {getattr(prop, 'name', 'unknown')} tem data_type None - pulando")
                                continue
                            
                            # Converte dataType para formato esperado pelo Weaviate
                            # Weaviate espera uma lista com o nome do tipo (ex: ["text"], ["number"], ["uuid"])
                            try:
                                if hasattr(prop.data_type, 'value'):
                                    # DataType enum tem atributo 'value' (ex: "text", "number", "uuid")
                                    data_type_value = prop.data_type.value
                                elif hasattr(prop.data_type, 'name'):
                                    # Se for um enum, pega o nome e converte para lowercase
                                    data_type_value = prop.data_type.name.lower()
                                    # Mapeia nomes de enum para valores esperados pelo Weaviate
                                    type_mapping = {
                                        "number": "number",
                                        "text": "text",
                                        "uuid": "uuid",
                                        "date": "date",
                                        "number_array": "number[]",
                                        "text_array": "text[]",
                                    }
                                    data_type_value = type_mapping.get(data_type_value, data_type_value)
                                else:
                                    # Fallback: converte para string e remove prefixos comuns
                                    data_type_str = str(prop.data_type).lower()
                                    # Remove prefixos como "DataType." se existirem
                                    if "." in data_type_str:
                                        data_type_value = data_type_str.split(".")[-1]
                                    else:
                                        data_type_value = data_type_str
                            except Exception as e:
                                # Se falhar, usa string direta como último recurso
                                msg.warn(f"   ⚠️  Erro ao converter dataType para {getattr(prop, 'name', 'unknown')}: {str(e)}")
                                try:
                                    data_type_value = str(prop.data_type).lower().replace("datatype.", "")
                                except:
                                    # Se ainda falhar, usa fallback genérico
                                    msg.warn(f"   ⚠️  Não foi possível determinar dataType para {getattr(prop, 'name', 'unknown')} - usando 'text' como fallback")
                                    data_type_value = "text"
                            
                            prop_dict = {
                                "name": prop.name,
                                "dataType": [data_type_value],
                            }
                            
                            # Adiciona description se existir
                            if hasattr(prop, 'description') and prop.description:
                                prop_dict["description"] = prop.description
                            
                            # Adiciona tokenization apenas se existir (propriedades TEXT podem ter)
                            if hasattr(prop, 'tokenization') and prop.tokenization is not None:
                                if hasattr(prop.tokenization, 'value'):
                                    prop_dict["tokenization"] = prop.tokenization.value
                                else:
                                    prop_dict["tokenization"] = str(prop.tokenization)
                            
                            # Adiciona indexFilterable se True
                            if hasattr(prop, 'index_filterable') and prop.index_filterable:
                                prop_dict["indexFilterable"] = True
                            
                            # Adiciona indexSearchable se True
                            if hasattr(prop, 'index_searchable') and prop.index_searchable:
                                prop_dict["indexSearchable"] = True
                            
                            properties_dict.append(prop_dict)
                        
                        schema_dict = {
                            "class": collection_name,
                            "description": f"Collection com named vectors: concept_vec, sector_vec, company_vec",
                            "vectorConfig": vector_config,
                            "properties": properties_dict
                        }
                        
                        try:
                            # Usa create_from_dict para named vectors
                            collection = await client.collections.create_from_dict(schema_dict)
                            msg.info(f"   ✅ Collection criada usando create_from_dict (named vectors)")
                        except Exception as dict_error:
                            msg.warn(f"   ⚠️  Erro ao criar com create_from_dict: {str(dict_error)}")
                            msg.warn(f"   📋 Total de propriedades no schema: {len(properties_dict)}")
                            msg.warn(f"   💡 Tentando criar sem named vectors como fallback...")
                            import traceback
                            msg.debug(f"   🔍 Traceback completo:\n{traceback.format_exc()}")
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

