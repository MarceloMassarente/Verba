#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script completo: Limpa tudo, cria collection do zero com ETL, importa PDF e testa
"""

import sys
import os
import asyncio
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from wasabi import msg
from verba_extensions.integration.schema_updater import get_etl_properties
from weaviate.classes.config import Configure, Property, DataType

async def get_weaviate_client():
    """Conecta ao Weaviate via HTTP (sem gRPC) - mesma lógica do Verba"""
    try:
        import weaviate
        from weaviate.classes.init import AdditionalConfig, Timeout
        from weaviate.auth import AuthApiKey
        
        url = os.getenv("WEAVIATE_URL", "https://weaviate-production-0d0e.up.railway.app")
        api_key = os.getenv("WEAVIATE_API_KEY")
        
        # Detecta configuração PaaS (Railway)
        http_host = os.getenv("WEAVIATE_HTTP_HOST")
        grpc_host = os.getenv("WEAVIATE_GRPC_HOST")
        
        if http_host and grpc_host:
            # PaaS (Railway) - usar portas separadas
            http_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
            grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
            http_secure = os.getenv("WEAVIATE_HTTP_SECURE", "False").lower() == "true"
            grpc_secure = os.getenv("WEAVIATE_GRPC_SECURE", "False").lower() == "true"
            
            auth_creds = AuthApiKey(api_key) if api_key else None
            
            client = weaviate.connect_to_custom(
                http_host=http_host,
                http_port=http_port,
                http_secure=http_secure,
                grpc_host=grpc_host,
                grpc_port=grpc_port,
                grpc_secure=grpc_secure,
                auth_credentials=auth_creds,
                skip_init_checks=True,
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=60, query=300, insert=300)
                )
            )
        else:
            # Conexão via URL - mesma lógica do WeaviateManager
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname or parsed.netloc.split(':')[0] if parsed.netloc else "localhost"
            
            # Default ports based on scheme (como no managers.py)
            if parsed.port:
                port = parsed.port
            elif parsed.scheme == 'https':
                port = 443
            elif parsed.scheme == 'http':
                port = 80
            else:
                port = 8080
            
            msg.info(f"Conectando ao Weaviate: {url} (host={host}, port={port}) - HTTP apenas")
            
            if api_key:
                # PRIORIDADE: Weaviate Cloud (WCS) com API key - usa HTTP apenas
                msg.info(f"Connecting to Weaviate Cloud at {url} with Auth (HTTP only)")
                client = weaviate.connect_to_weaviate_cloud(
                    cluster_url=url,
                    auth_credentials=AuthApiKey(api_key),
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=60, query=300, insert=300)
                    )
                )
            else:
                # Sem auth - usar use_async_with_local (HTTP apenas, sem gRPC)
                # NOTA: use_async_with_local não suporta gRPC adequadamente para PaaS
                msg.info(f"Connecting to Weaviate at {url} without Auth (HTTP only)")
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
        msg.warn(f"Erro ao conectar: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """Cria collection do zero, importa PDF e testa ETL"""
    
    print("=" * 80)
    print("🚀 CRIAR COLLECTION DO ZERO COM ETL - LIMPAR E RECRIAR")
    print("=" * 80 + "\n")
    
    # 1. Conecta ao Weaviate
    msg.info("📡 Conectando ao Weaviate...")
    client = await get_weaviate_client()
    
    if not client:
        msg.warn("❌ Não foi possível conectar ao Weaviate")
        msg.info("💡 Verifique variáveis de ambiente: WEAVIATE_URL, WEAVIATE_API_KEY")
        return
    
    msg.good("✅ Conectado ao Weaviate\n")
    
    # 2. Define collection name
    collection_name = "VERBA_Embedding_all_MiniLM_L6_v2_ETL"
    embedder_name = "all-MiniLM-L6-v2"
    
    # 3. Limpa collections antigas
    msg.info("🧹 Limpando collections antigas...")
    
    collections_to_check = [
        collection_name,
        "VERBA_Embedding_all_MiniLM_L6_v2",
        "VERBA_Embedding_all_MiniLM_L6_v2_ETL_TEST"
    ]
    
    for coll_name in collections_to_check:
        if client.collections.exists(coll_name):
            try:
                client.collections.delete(coll_name)
                msg.info(f"   🗑️  Deletada: {coll_name}")
            except Exception as e:
                msg.warn(f"   ⚠️  Erro ao deletar {coll_name}: {str(e)}")
    
    msg.good("✅ Limpeza concluída\n")
    
    # 4. Cria collection com propriedades de ETL
    msg.info(f"🔧 Criando collection {collection_name} com propriedades de ETL...")
    
    try:
        # Propriedades padrão do Verba (baseado no schema atual)
        verba_properties = [
            Property(name="chunk_id", data_type=DataType.NUMBER),
            Property(name="end_i", data_type=DataType.NUMBER),
            Property(name="chunk_date", data_type=DataType.TEXT),
            Property(name="meta", data_type=DataType.TEXT),
            Property(name="content", data_type=DataType.TEXT),
            Property(name="uuid", data_type=DataType.TEXT),
            Property(name="doc_uuid", data_type=DataType.UUID),
            Property(name="content_without_overlap", data_type=DataType.TEXT),
            Property(name="pca", data_type=DataType.NUMBER_ARRAY),
            Property(name="labels", data_type=DataType.TEXT_ARRAY),
            Property(name="title", data_type=DataType.TEXT),
            Property(name="start_i", data_type=DataType.NUMBER),
            Property(name="chunk_lang", data_type=DataType.TEXT),
        ]
        
        # Propriedades de ETL
        etl_properties = get_etl_properties()
        
        # Todas as propriedades
        all_properties = verba_properties + etl_properties
        
        # Cria collection sem vectorizer (Verba gera embeddings localmente)
        collection = client.collections.create(
            name=collection_name,
            properties=all_properties,
        )
        
        msg.good(f"✅ Collection {collection_name} criada")
        msg.info(f"   - Total de propriedades: {len(all_properties)}")
        msg.info(f"   - Propriedades padrão: {len(verba_properties)}")
        msg.info(f"   - Propriedades de ETL: {len(etl_properties)}")
        msg.info(f"   - Vectorizer: None (Verba gera embeddings localmente com {embedder_name})\n")
        
    except Exception as e:
        msg.warn(f"❌ Erro ao criar collection: {str(e)}")
        import traceback
        traceback.print_exc()
        client.close()
        return
    
    # 5. Encontra PDF
    msg.info("📄 Procurando PDF...")
    pdf_path = None
    possible_paths = [
        "Dossiê_ Flow Executive Finders.pdf",
        "./Dossiê_ Flow Executive Finders.pdf",
        os.path.join(os.getcwd(), "Dossiê_ Flow Executive Finders.pdf")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            pdf_path = path
            break
    
    if not pdf_path:
        msg.warn("❌ PDF não encontrado")
        msg.info("💡 Coloque o PDF na pasta do projeto")
        client.close()
        return
    
    msg.good(f"✅ PDF encontrado: {pdf_path}\n")
    
    # 6. Importa PDF usando Verba
    msg.info("📥 Importando PDF usando Verba...")
    
    try:
        from goldenverba.components.document import Document
        from goldenverba.components.reader.BasicReader import BasicReader
        from verba_extensions.plugins.section_aware_chunker import SectionAwareChunker
        from goldenverba.components.embedding.SentenceTransformersEmbedder import SentenceTransformersEmbedder
        from verba_extensions.integration.chunking_hook import apply_etl_pre_chunking
        
        # Lê PDF
        reader = BasicReader()
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
        
        content = await reader.load_pdf_file(pdf_bytes)
        msg.good(f"✅ PDF lido: {len(content)} caracteres")
        
        # Cria documento
        doc_title = os.path.basename(pdf_path)
        document = Document(
            content=content,
            title=doc_title
        )
        document.meta = {"enable_etl": True}
        
        # Aplica ETL pré-chunking
        msg.info("🔍 Aplicando ETL pré-chunking...")
        document = apply_etl_pre_chunking(document, enable_etl=True)
        
        entity_spans = document.meta.get("entity_spans", []) if document.meta else []
        entity_ids = document.meta.get("entity_ids", []) if document.meta else []
        
        msg.good(f"✅ ETL pré-chunking concluído")
        msg.info(f"   - Entity spans: {len(entity_spans)}")
        msg.info(f"   - Entity IDs: {len(entity_ids)}")
        if entity_spans:
            msg.info(f"   - Exemplo: {entity_spans[0].get('text', 'N/A')}")
        
        # Chunking
        msg.info("✂️  Fazendo chunking (entity-aware)...")
        chunker = SectionAwareChunker()
        chunker_config = {
            "Chunk Size": 1000,
            "Chunk Overlap": 200,
        }
        
        chunks = await chunker.chunk(
            config=chunker_config,
            documents=[document],
            embedder=None,
            embedder_config=None
        )
        
        msg.good(f"✅ Chunking concluído: {len(chunks)} chunks criados")
        
        # Embedding
        msg.info("🔢 Gerando embeddings...")
        embedder = SentenceTransformersEmbedder()
        embedder_model = embedder.config["Model"].value
        
        # Gera embeddings para cada chunk
        for i, chunk in enumerate(chunks):
            chunk.vector = (await embedder.vectorize(embedder.config, [chunk.content]))[0]
            if (i + 1) % 10 == 0:
                msg.info(f"   {i + 1}/{len(chunks)} embeddings gerados...")
        
        msg.good(f"✅ Embeddings gerados: {len(chunks)} vetores\n")
        
        # 7. Salva no Weaviate
        msg.info("💾 Salvando no Weaviate...")
        
        # Cria documento no Weaviate
        doc_collection = client.collections.get("VERBA_DOCUMENTS")
        
        # Deleta documento antigo se existir
        from weaviate.classes.query import Filter
        existing_docs = doc_collection.query.fetch_objects(
            filters=Filter.by_property("title").equal(doc_title),
            limit=1
        )
        
        if existing_docs.objects:
            doc_uuid = str(existing_docs.objects[0].uuid)
            msg.info(f"ℹ️  Documento já existe, deletando...")
            doc_collection.data.delete_by_uuid(doc_uuid)
        
        # Cria novo documento
        doc_obj = doc_collection.data.insert(
            properties={
                "title": doc_title,
                "content": content,
                "source": doc_title,
                "labels": []
            }
        )
        doc_uuid = str(doc_obj)
        msg.good(f"✅ Documento criado: {doc_uuid}")
        
        # Insere chunks
        collection_obj = client.collections.get(collection_name)
        
        inserted_count = 0
        for i, chunk in enumerate(chunks):
            chunk_props = chunk.to_json()
            chunk_props["doc_uuid"] = doc_uuid
            chunk_props["title"] = doc_title
            
            # Inicializa propriedades de ETL (serão preenchidas pelo ETL pós-chunking)
            chunk_props["entities_local_ids"] = []
            chunk_props["section_title"] = ""
            chunk_props["section_entity_ids"] = []
            chunk_props["section_scope_confidence"] = 0.0
            chunk_props["primary_entity_id"] = ""
            chunk_props["entity_focus_score"] = 0.0
            chunk_props["etl_version"] = ""
            
            collection_obj.data.insert(
                properties=chunk_props,
                vector=chunk.vector
            )
            inserted_count += 1
            
            if (i + 1) % 10 == 0:
                msg.info(f"   {i + 1}/{len(chunks)} chunks inseridos...")
        
        msg.good(f"✅ {inserted_count} chunks inseridos no Weaviate\n")
        
        # 8. Executa ETL pós-chunking
        msg.info("🔍 Executando ETL pós-chunking...")
        
        # Busca chunks do documento
        chunk_objects = collection_obj.query.fetch_objects(
            filters=Filter.by_property("doc_uuid").equal(doc_uuid),
            limit=10000
        )
        
        passage_uuids = [str(c.uuid) for c in chunk_objects.objects]
        msg.info(f"   📊 {len(passage_uuids)} chunks encontrados para ETL")
        
        if passage_uuids:
            from verba_extensions.plugins.a2_etl_hook import run_etl_on_passages
            msg.info(f"   🚀 Executando ETL em {len(passage_uuids)} chunks...")
            result = await run_etl_on_passages(client, passage_uuids, tenant=None)
            msg.good(f"✅ ETL pós-chunking concluído: {result}")
        
        # 9. Verifica resultados
        msg.info("\n" + "=" * 80)
        msg.info("📊 VERIFICAÇÃO FINAL")
        msg.info("=" * 80 + "\n")
        
        # Busca chunks atualizados
        updated_chunks = collection_obj.query.fetch_objects(
            filters=Filter.by_property("doc_uuid").equal(doc_uuid),
            limit=20
        )
        
        chunks_with_etl = 0
        total_entity_ids = 0
        chunks_with_section = 0
        
        for chunk in updated_chunks.objects:
            props = chunk.properties
            if props.get("entities_local_ids"):
                chunks_with_etl += 1
                total_entity_ids += len(props.get("entities_local_ids", []))
            if props.get("section_title"):
                chunks_with_section += 1
        
        msg.info(f"📈 Estatísticas:")
        msg.info(f"   - Chunks analisados: {len(updated_chunks.objects)}")
        msg.info(f"   - Chunks com entities_local_ids: {chunks_with_etl}")
        msg.info(f"   - Chunks com section_title: {chunks_with_section}")
        msg.info(f"   - Total de entity_ids encontrados: {total_entity_ids}")
        
        # Mostra exemplos
        if chunks_with_etl > 0:
            msg.info(f"\n📋 Exemplos de chunks com ETL:")
            shown = 0
            for chunk in updated_chunks.objects:
                props = chunk.properties
                if props.get("entities_local_ids") and shown < 3:
                    msg.info(f"\n   Chunk {props.get('chunk_id')}:")
                    msg.info(f"      Content: {props.get('content', '')[:80]}...")
                    msg.info(f"      entities_local_ids: {props.get('entities_local_ids', [])}")
                    msg.info(f"      section_title: {props.get('section_title', 'N/A')}")
                    msg.info(f"      primary_entity_id: {props.get('primary_entity_id', 'N/A')}")
                    shown += 1
        
        if chunks_with_etl > 0:
            msg.good(f"\n✅ SUCESSO! ETL está funcionando completamente!")
            msg.info(f"   - Metadados de ETL foram salvos nos chunks")
            msg.info(f"   - Queries por entidades estão disponíveis")
            msg.info(f"   - Section titles foram identificados")
        else:
            msg.warn(f"\n⚠️  ETL não preencheu metadados")
            msg.info(f"   - Verifique logs do ETL acima")
        
        # 10. Testa query por entidade
        if total_entity_ids > 0:
            msg.info(f"\n🔍 Testando query por entidade...")
            
            # Pega um entity_id de exemplo
            sample_chunk = None
            for chunk in updated_chunks.objects:
                if chunk.properties.get("entities_local_ids"):
                    sample_chunk = chunk
                    break
            
            if sample_chunk:
                sample_entity_id = sample_chunk.properties["entities_local_ids"][0]
                msg.info(f"   Testando com entity_id: {sample_entity_id}")
                
                query_results = collection_obj.query.fetch_objects(
                    filters=Filter.by_property("entities_local_ids").contains_any([sample_entity_id]),
                    limit=5
                )
                
                msg.good(f"   ✅ Query funcionou: {len(query_results.objects)} chunks encontrados")
                
                if query_results.objects:
                    msg.info(f"   Exemplos de chunks encontrados:")
                    for i, result_chunk in enumerate(query_results.objects[:3]):
                        msg.info(f"      {i+1}. Chunk {result_chunk.properties.get('chunk_id')}: {result_chunk.properties.get('content', '')[:60]}...")
        
        client.close()
        
        msg.good(f"\n✅ TESTE CONCLUÍDO!")
        msg.info(f"   Collection: {collection_name}")
        msg.info(f"   Documento: {doc_title}")
        msg.info(f"   Chunks: {inserted_count}")
        msg.info(f"   Chunks com ETL: {chunks_with_etl}")
        
    except Exception as e:
        msg.warn(f"❌ Erro durante importação: {str(e)}")
        import traceback
        traceback.print_exc()
        client.close()
        return

if __name__ == "__main__":
    asyncio.run(main())

