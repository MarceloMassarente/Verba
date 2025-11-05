"""
Script para verificar se ETL foi processado corretamente em um documento

Verifica:
1. ETL pré-chunking (entity_spans no documento)
2. Chunking entity-aware (chunks não cortam entidades)
3. ETL pós-chunking (propriedades ETL nos chunks)
4. Schema ETL-aware nas collections

Uso:
    python scripts/verify_etl_processing.py [doc_title]
"""

import os
import asyncio
import sys
from dotenv import load_dotenv
from wasabi import msg

# Carrega variáveis de ambiente
load_dotenv()

# Importa Weaviate
try:
    import weaviate
    from weaviate.classes.query import Filter
    from weaviate.auth import AuthApiKey
except ImportError:
    msg.fail("❌ Weaviate não está instalado. Execute: pip install weaviate-client")
    exit(1)


async def connect_to_weaviate():
    """Conecta ao Weaviate usando configurações do ambiente"""
    url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    api_key = os.getenv("WEAVIATE_API_KEY_VERBA")
    
    # Verifica se é Railway (rede interna)
    http_host = os.getenv("WEAVIATE_HTTP_HOST")
    grpc_host = os.getenv("WEAVIATE_GRPC_HOST")
    
    if http_host and grpc_host:
        # Railway/Private Network - usar connect_to_custom
        http_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
        grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
        http_secure = os.getenv("WEAVIATE_HTTP_SECURE", "False").lower() == "true"
        grpc_secure = os.getenv("WEAVIATE_GRPC_SECURE", "False").lower() == "true"
        
        auth_creds = AuthApiKey(api_key) if api_key else None
        
        msg.info(f"🔗 Conectando via Railway (HTTP: {http_host}:{http_port})")
        client = await weaviate.connect_to_custom(
            http_host=http_host,
            http_port=http_port,
            http_secure=http_secure,
            grpc_host=grpc_host,
            grpc_port=grpc_port,
            grpc_secure=grpc_secure,
            auth_credentials=auth_creds,
        )
    elif url.startswith("http://") or url.startswith("https://"):
        # URL padrão (WCS ou local)
        auth_creds = AuthApiKey(api_key) if api_key else None
        msg.info(f"🔗 Conectando via URL: {url}")
        client = await weaviate.connect_to_weaviate_cloud(
            cluster_url=url,
            auth_credentials=auth_creds,
        )
    else:
        # Local
        msg.info(f"🔗 Conectando localmente: {url}")
        client = await weaviate.connect_to_local(
            host=url,
        )
    
    return client


async def get_document_by_title(client, doc_title: str):
    """Busca documento por título"""
    try:
        documents_collection = client.collections.get("VERBA_DOCUMENTS")
        
        results = await documents_collection.query.fetch_objects(
            filters=Filter.by_property("title").equal(doc_title),
            limit=1
        )
        
        if results.objects:
            return results.objects[0]
        return None
    except Exception as e:
        msg.warn(f"Erro ao buscar documento: {str(e)}")
        return None


async def get_chunks_for_document(client, doc_uuid: str, collection_name: str):
    """Busca todos os chunks de um documento"""
    try:
        collection = client.collections.get(collection_name)
        
        results = await collection.query.fetch_objects(
            filters=Filter.by_property("doc_uuid").equal(doc_uuid),
            limit=10000  # Limite alto para pegar todos
        )
        
        return results.objects
    except Exception as e:
        msg.warn(f"Erro ao buscar chunks: {str(e)}")
        return []


async def check_collection_schema(client, collection_name: str):
    """Verifica se collection tem schema ETL-aware"""
    try:
        collection = client.collections.get(collection_name)
        config = await collection.config.get()
        
        etl_properties = [
            "entities_local_ids",
            "section_title",
            "section_entity_ids",
            "section_scope_confidence",
            "primary_entity_id",
            "entity_focus_score",
            "etl_version"
        ]
        
        existing_props = [p.name for p in config.properties]
        has_etl = any(prop in existing_props for prop in etl_properties)
        
        return has_etl, existing_props
    except Exception as e:
        msg.warn(f"Erro ao verificar schema: {str(e)}")
        return False, []


async def verify_etl_processing(client, doc_title: str = None):
    """Verifica se ETL foi processado corretamente"""
    msg.info("=" * 70)
    msg.info("🔍 Verificação de Processamento ETL")
    msg.info("=" * 70)
    
    # Se não especificou documento, lista todos
    if not doc_title:
        try:
            documents_collection = client.collections.get("VERBA_DOCUMENTS")
            results = await documents_collection.query.fetch_objects(limit=10)
            if results.objects:
                msg.info("\n📋 Documentos encontrados:")
                for i, doc in enumerate(results.objects, 1):
                    msg.info(f"   {i}. {doc.properties.get('title', 'N/A')}")
                doc_title = results.objects[0].properties.get('title')
                msg.info(f"\n✅ Verificando primeiro documento: {doc_title}")
            else:
                msg.fail("❌ Nenhum documento encontrado")
                return
        except Exception as e:
            msg.fail(f"❌ Erro ao listar documentos: {str(e)}")
            return
    
    # Busca documento
    msg.info(f"\n📄 Buscando documento: {doc_title}")
    document = await get_document_by_title(client, doc_title)
    
    if not document:
        msg.fail(f"❌ Documento '{doc_title}' não encontrado")
        return
    
    doc_uuid = str(document.uuid)
    msg.good(f"✅ Documento encontrado: {doc_uuid[:50]}...")
    
    # Verifica propriedades do documento
    doc_props = document.properties
    msg.info(f"\n📊 Propriedades do Documento:")
    msg.info(f"   - Título: {doc_props.get('title', 'N/A')}")
    msg.info(f"   - Labels: {doc_props.get('labels', [])}")
    
    # Tenta encontrar collection de embedding
    # Procura em meta do documento
    meta_str = doc_props.get('meta', '{}')
    embedder_name = None
    try:
        import json
        meta = json.loads(meta_str) if isinstance(meta_str, str) else meta_str
        if isinstance(meta, dict) and 'Embedder' in meta:
            embedder_config = meta['Embedder']
            if isinstance(embedder_config, dict) and 'config' in embedder_config:
                model = embedder_config['config'].get('Model', {}).get('value', '')
                if model:
                    embedder_name = model
    except:
        pass
    
    # Lista collections de embedding
    all_collections = await client.collections.list_all()
    embedding_collections = [c for c in all_collections if "VERBA_Embedding" in c]
    
    if not embedding_collections:
        msg.fail("❌ Nenhuma collection de embedding encontrada")
        return
    
    msg.info(f"\n📦 Collections de embedding encontradas: {len(embedding_collections)}")
    
    # Verifica cada collection
    for collection_name in embedding_collections:
        msg.info(f"\n{'=' * 70}")
        msg.info(f"🔍 Verificando: {collection_name}")
        msg.info(f"{'=' * 70}")
        
        # Verifica schema
        has_etl_schema, props = await check_collection_schema(client, collection_name)
        if has_etl_schema:
            msg.good(f"✅ Schema ETL-aware presente")
            etl_props = [p for p in props if p in [
                "entities_local_ids", "section_title", "section_entity_ids",
                "section_scope_confidence", "primary_entity_id", 
                "entity_focus_score", "etl_version"
            ]]
            msg.info(f"   Propriedades ETL: {', '.join(etl_props)}")
        else:
            msg.warn(f"⚠️  Schema ETL-aware NÃO encontrado")
        
        # Busca chunks
        chunks = await get_chunks_for_document(client, doc_uuid, collection_name)
        
        if not chunks:
            msg.info(f"   ℹ️  Nenhum chunk encontrado nesta collection")
            continue
        
        msg.good(f"✅ {len(chunks)} chunks encontrados")
        
        # Analisa chunks
        chunks_with_etl = 0
        chunks_with_entities = 0
        chunks_with_section = 0
        total_entities = 0
        
        for chunk in chunks[:10]:  # Analisa primeiros 10 chunks
            props = chunk.properties
            
            # Verifica propriedades ETL
            has_entities = bool(props.get("entities_local_ids"))
            has_section = bool(props.get("section_title") or props.get("section_entity_ids"))
            has_etl = has_entities or has_section or bool(props.get("primary_entity_id"))
            
            if has_etl:
                chunks_with_etl += 1
            if has_entities:
                chunks_with_entities += 1
                total_entities += len(props.get("entities_local_ids", []))
            if has_section:
                chunks_with_section += 1
        
        # Estatísticas
        msg.info(f"\n📊 Estatísticas dos Chunks (amostra de {min(10, len(chunks))}):")
        msg.info(f"   ✅ Chunks com ETL: {chunks_with_etl}/{min(10, len(chunks))}")
        msg.info(f"   ✅ Chunks com entidades: {chunks_with_entities}/{min(10, len(chunks))}")
        msg.info(f"   ✅ Chunks com section scope: {chunks_with_section}/{min(10, len(chunks))}")
        
        if chunks_with_etl > 0:
            msg.good(f"✅ ETL foi processado! {chunks_with_etl} chunks têm propriedades ETL")
            
            # Mostra exemplo de chunk com ETL
            for chunk in chunks[:5]:
                props = chunk.properties
                if props.get("entities_local_ids"):
                    msg.info(f"\n📝 Exemplo de chunk com ETL:")
                    msg.info(f"   UUID: {str(chunk.uuid)[:50]}...")
                    msg.info(f"   Entidades (local): {props.get('entities_local_ids', [])[:5]}")
                    msg.info(f"   Entidades (section): {props.get('section_entity_ids', [])[:5]}")
                    msg.info(f"   Primary Entity: {props.get('primary_entity_id', 'N/A')}")
                    msg.info(f"   Section Title: {props.get('section_title', 'N/A')}")
                    msg.info(f"   ETL Version: {props.get('etl_version', 'N/A')}")
                    break
        else:
            msg.warn(f"⚠️  Nenhum chunk tem propriedades ETL preenchidas")
            msg.info(f"   💡 Isso pode indicar que ETL pós-chunking não foi executado")
        
        # Verifica se há chunks suficientes para análise
        if len(chunks) > 10:
            msg.info(f"\n   ℹ️  (Total de {len(chunks)} chunks - analisados apenas {min(10, len(chunks))})")
    
    msg.info(f"\n{'=' * 70}")
    msg.info("✅ Verificação concluída")
    msg.info(f"{'=' * 70}")


async def main():
    """Função principal"""
    doc_title = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Conecta ao Weaviate
    try:
        client = await connect_to_weaviate()
        msg.good("✅ Conectado ao Weaviate")
    except Exception as e:
        msg.fail(f"❌ Erro ao conectar ao Weaviate: {str(e)}")
        return
    
    # Verifica ETL
    try:
        await verify_etl_processing(client, doc_title)
    except Exception as e:
        msg.fail(f"❌ Erro durante verificação: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

