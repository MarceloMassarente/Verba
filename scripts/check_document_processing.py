#!/usr/bin/env python3
"""
Script para verificar se documento foi processado corretamente no Weaviate
Verifica: documento, chunks, propriedades ETL, schema
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# Adiciona diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configura encoding UTF-8 para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import weaviate
    from weaviate.classes.init import AdditionalConfig, Timeout
    from weaviate.auth import AuthApiKey
    from wasabi import msg
except ImportError as e:
    print(f"Erro ao importar dependências: {e}")
    print("Execute: pip install weaviate-client wasabi")
    sys.exit(1)


async def get_weaviate_client():
    """Conecta ao Weaviate via HTTP (sem gRPC)"""
    try:
        url = os.getenv("WEAVIATE_URL", "https://weaviate-production-0d0e.up.railway.app")
        api_key = os.getenv("WEAVIATE_API_KEY")
        
        msg.info(f"Conectando ao Weaviate: {url}")
        
        # Se tem API key, sempre usa connect_to_weaviate_cloud
        if api_key:
            msg.info(f"Connecting to Weaviate Cloud at {url} with Auth (HTTP only)")
            client = weaviate.connect_to_weaviate_cloud(
                cluster_url=url,
                auth_credentials=AuthApiKey(api_key),
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=60, query=300, insert=300)
                )
            )
        else:
            # Sem API key - tenta via URL (pode falhar se precisar de auth)
            msg.warn("⚠️  Nenhuma API key encontrada - tentando conexão sem auth")
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname or parsed.netloc.split(':')[0] if parsed.netloc else "localhost"
            
            # Default ports based on scheme
            if parsed.port:
                port = parsed.port
            elif parsed.scheme == 'https':
                port = 443
            elif parsed.scheme == 'http':
                port = 80
            else:
                port = 8080
            
            msg.info(f"Connecting to Weaviate at {url} without Auth (host={host}, port={port})")
            client = weaviate.connect_to_local(
                host=host,
                port=port,
                skip_init_checks=True,
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=60, query=300, insert=300)
                )
            )
        
        return client
    except Exception as e:
        msg.fail(f"Erro ao conectar: {str(e)}")
        msg.warn("💡 Dica: Verifique se WEAVIATE_API_KEY está configurada se o Weaviate requer autenticação")
        import traceback
        traceback.print_exc()
        return None


async def check_document(client, doc_title: str = None):
    """Verifica se documento existe e seus detalhes"""
    try:
        doc_collection = client.collections.get("VERBA_DOCUMENTS")
        
        # Busca documentos
        if doc_title:
            results = await doc_collection.query.fetch_objects(
                filters=doc_collection.query.Filter.by_property("title").equal(doc_title),
                limit=10
            )
        else:
            results = await doc_collection.query.fetch_objects(limit=10)
        
        if not results.objects:
            msg.warn("Nenhum documento encontrado")
            return None
        
        msg.good(f"✅ Encontrados {len(results.objects)} documento(s)")
        
        for obj in results.objects:
            doc_uuid = str(obj.uuid)
            title = obj.properties.get("title", "N/A")
            source = obj.properties.get("source", "N/A")
            
            msg.info(f"\n📄 Documento: {title}")
            msg.info(f"   UUID: {doc_uuid}")
            msg.info(f"   Source: {source}")
            
            # Verifica chunks relacionados
            await check_chunks_for_document(client, doc_uuid, title)
        
        return results.objects[0] if results.objects else None
        
    except Exception as e:
        msg.fail(f"Erro ao verificar documento: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def check_chunks_for_document(client, doc_uuid: str, doc_title: str):
    """Verifica chunks relacionados ao documento"""
    try:
        # Tenta encontrar collection de embedding
        # Pode ser várias dependendo do embedder usado
        possible_collections = [
            "VERBA_Embedding_all_MiniLM_L6_v2",
            "VERBA_Embedding_text_embedding_ada_002",
            "VERBA_Embedding_SentenceTransformers",
        ]
        
        collection_found = None
        for coll_name in possible_collections:
            if client.collections.exists(coll_name):
                collection_found = coll_name
                break
        
        if not collection_found:
            # Lista todas as collections
            all_collections = client.collections.list_all()
            embedding_collections = [c for c in all_collections if "VERBA_Embedding" in c]
            
            if embedding_collections:
                collection_found = embedding_collections[0]
                msg.info(f"   Usando collection: {collection_found}")
            else:
                msg.warn("   ⚠️  Nenhuma collection de embedding encontrada")
                return
        
        embed_collection = client.collections.get(collection_found)
        
        # Busca chunks do documento
        results = await embed_collection.query.fetch_objects(
            filters=embed_collection.query.Filter.by_property("doc_uuid").equal(doc_uuid),
            limit=100,
            return_metadata=["count"]
        )
        
        if not results.objects:
            msg.warn(f"   ⚠️  Nenhum chunk encontrado para documento {doc_uuid}")
            return
        
        msg.good(f"   ✅ Encontrados {len(results.objects)} chunks")
        
        # Verifica propriedades ETL
        etl_props = [
            "entities_local_ids",
            "section_title",
            "section_entity_ids",
            "section_scope_confidence",
            "primary_entity_id",
            "entity_focus_score",
            "etl_version",
        ]
        
        # Verifica schema da collection
        config = await embed_collection.config.get()
        schema_props = [p.name for p in config.properties]
        
        has_etl_schema = any(prop in schema_props for prop in etl_props)
        
        if has_etl_schema:
            msg.good(f"   ✅ Collection tem schema ETL-aware")
            
            # Verifica chunks com dados ETL
            chunks_with_etl = 0
            for chunk in results.objects[:10]:  # Verifica primeiros 10
                chunk_props = chunk.properties
                has_etl_data = any(
                    chunk_props.get(prop) and chunk_props.get(prop) != [] and chunk_props.get(prop) != ""
                    for prop in etl_props
                )
                if has_etl_data:
                    chunks_with_etl += 1
                    
                    # Mostra exemplo de chunk com ETL
                    if chunks_with_etl == 1:
                        msg.info(f"\n   📋 Exemplo de chunk com ETL (chunk_id={chunk_props.get('chunk_id', 'N/A')}):")
                        for prop in etl_props:
                            value = chunk_props.get(prop)
                            if value and value != [] and value != "":
                                msg.info(f"      - {prop}: {value}")
            
            msg.info(f"   📊 Chunks com dados ETL: {chunks_with_etl}/{min(10, len(results.objects))} (amostra)")
        else:
            msg.warn(f"   ⚠️  Collection NÃO tem schema ETL-aware")
            msg.warn(f"      Propriedades no schema: {', '.join(schema_props[:10])}...")
        
        # Mostra exemplo de chunk
        if results.objects:
            first_chunk = results.objects[0]
            chunk_props = first_chunk.properties
            msg.info(f"\n   📋 Exemplo de chunk (chunk_id={chunk_props.get('chunk_id', 'N/A')}):")
            msg.info(f"      - Content (primeiros 100 chars): {str(chunk_props.get('content', ''))[:100]}...")
            msg.info(f"      - Title: {chunk_props.get('title', 'N/A')}")
            msg.info(f"      - Start_i: {chunk_props.get('start_i', 'N/A')}")
            msg.info(f"      - End_i: {chunk_props.get('end_i', 'N/A')}")
        
    except Exception as e:
        msg.fail(f"   Erro ao verificar chunks: {str(e)}")
        import traceback
        traceback.print_exc()


async def check_collection_schema(client, collection_name: str):
    """Verifica schema de uma collection"""
    try:
        if not client.collections.exists(collection_name):
            msg.warn(f"Collection {collection_name} não existe")
            return
        
        collection = client.collections.get(collection_name)
        config = await collection.config.get()
        
        msg.info(f"\n📋 Schema da collection {collection_name}:")
        msg.info(f"   Total de propriedades: {len(config.properties)}")
        
        for prop in config.properties:
            msg.info(f"   - {prop.name}: {prop.data_type}")
        
        # Verifica propriedades ETL
        etl_props = [
            "entities_local_ids",
            "section_title",
            "section_entity_ids",
            "section_scope_confidence",
            "primary_entity_id",
            "entity_focus_score",
            "etl_version",
        ]
        
        has_etl = any(prop.name in etl_props for prop in config.properties)
        
        if has_etl:
            msg.good(f"   ✅ Collection tem propriedades ETL")
        else:
            msg.warn(f"   ⚠️  Collection NÃO tem propriedades ETL")
        
    except Exception as e:
        msg.fail(f"Erro ao verificar schema: {str(e)}")
        import traceback
        traceback.print_exc()


async def main():
    """Função principal"""
    msg.info("🔍 Verificando processamento de documento no Weaviate\n")
    
    # Conecta ao Weaviate
    client = await get_weaviate_client()
    if not client:
        msg.fail("Não foi possível conectar ao Weaviate")
        return
    
    try:
        # Verifica documento mais recente ou específico
        doc_title = os.getenv("DOC_TITLE", "VNP — Inteligência de Mercado (IM) — 2025 - Formulários Google.pdf")
        
        msg.info(f"Buscando documento: {doc_title}\n")
        
        # Verifica documento
        doc = await check_document(client, doc_title)
        
        if doc:
            # Verifica schema da collection de embedding
            msg.info("\n" + "="*60)
            await check_collection_schema(client, "VERBA_Embedding_all_MiniLM_L6_v2")
        
        # Lista todas as collections
        msg.info("\n" + "="*60)
        msg.info("📚 Todas as collections:")
        all_collections = client.collections.list_all()
        for coll_name in all_collections:
            coll = client.collections.get(coll_name)
            count = await coll.aggregate.over_all(total_count=True)
            msg.info(f"   - {coll_name}: {count.total_count if hasattr(count, 'total_count') else 'N/A'} objetos")
        
    except Exception as e:
        msg.fail(f"Erro: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())

