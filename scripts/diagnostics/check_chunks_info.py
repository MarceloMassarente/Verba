#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar quantos chunks foram criados e qual algoritmo foi usado
"""

import sys
import os
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from wasabi import msg
import weaviate
from weaviate.classes.init import AdditionalConfig, Timeout
from weaviate.auth import AuthApiKey

async def get_weaviate_client():
    """Conecta ao Weaviate"""
    try:
        url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
        api_key = os.getenv("WEAVIATE_API_KEY")
        
        msg.info(f"Conectando ao Weaviate: {url}")
        
        if api_key:
            client = weaviate.connect_to_weaviate_cloud(
                cluster_url=url,
                auth_credentials=AuthApiKey(api_key),
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=60, query=300, insert=300)
                )
            )
        else:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname or parsed.netloc.split(':')[0] if parsed.netloc else "localhost"
            port = parsed.port if parsed.port else (443 if parsed.scheme == 'https' else 8080)
            
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
        return None

async def get_document_info(client, doc_uuid: str = None):
    """Obtém informações sobre documentos e chunks"""
    try:
        doc_collection = client.collections.get("VERBA_DOCUMENTS")
        
        # Se doc_uuid fornecido, busca documento específico
        if doc_uuid:
            try:
                doc = doc_collection.query.fetch_object_by_id(doc_uuid)
                documents = [doc] if doc else []
            except:
                documents = []
        else:
            # Busca todos os documentos
            result = doc_collection.query.fetch_objects(limit=100)
            documents = list(result.objects)
        
        if not documents:
            msg.warn("Nenhum documento encontrado")
            return
        
        msg.info(f"\n{'='*80}")
        msg.info(f"📊 INFORMAÇÕES SOBRE CHUNKS")
        msg.info(f"{'='*80}\n")
        
        total_chunks_all = 0
        
        for doc_obj in documents:
            doc_props = doc_obj.properties
            doc_uuid = str(doc_obj.uuid)
            doc_title = doc_props.get("title", "Sem título")
            
            # Extrai informações do chunker do meta
            chunker_name = "Desconhecido"
            chunker_config = {}
            
            if "meta" in doc_props and doc_props["meta"]:
                try:
                    meta = json.loads(doc_props["meta"]) if isinstance(doc_props["meta"], str) else doc_props["meta"]
                    if "Chunker" in meta:
                        chunker_info = meta["Chunker"]
                        chunker_name = chunker_info.get("selected", "Desconhecido")
                        if "components" in chunker_info and chunker_name in chunker_info["components"]:
                            chunker_config = chunker_info["components"][chunker_name].get("config", {})
                except Exception as e:
                    msg.warn(f"Erro ao parsear meta: {str(e)}")
            
            # Conta chunks para este documento
            # Precisa descobrir qual collection de embedding usar
            embedder_name = "Desconhecido"
            if "meta" in doc_props and doc_props["meta"]:
                try:
                    meta = json.loads(doc_props["meta"]) if isinstance(doc_props["meta"], str) else doc_props["meta"]
                    if "Embedder" in meta:
                        embedder_info = meta["Embedder"]
                        embedder_name = embedder_info.get("selected", "Desconhecido")
                        if "components" in embedder_info and embedder_name in embedder_info["components"]:
                            embedder_config = embedder_info["components"][embedder_name].get("config", {})
                            if "Model" in embedder_config:
                                embedder_name = embedder_config["Model"].get("value", embedder_name)
                except:
                    pass
            
            # Normaliza nome do embedder para nome da collection
            from goldenverba.components.managers import WeaviateManager
            weaviate_manager = WeaviateManager()
            normalized = weaviate_manager._normalize_embedder_name(embedder_name)
            collection_name = f"VERBA_Embedding_{normalized}"
            
            chunk_count = 0
            if await client.collections.exists(collection_name):
                embedder_collection = client.collections.get(collection_name)
                from weaviate.classes.query import Filter
                result = await embedder_collection.aggregate.over_all(
                    filters=Filter.by_property("doc_uuid").equal(doc_uuid),
                    total_count=True
                )
                chunk_count = result.total_count
                total_chunks_all += chunk_count
            
            # Exibe informações
            msg.info(f"📄 Documento: {doc_title}")
            msg.info(f"   UUID: {doc_uuid}")
            msg.info(f"   Chunker usado: {chunker_name}")
            
            # Mostra configuração do chunker se disponível
            if chunker_config:
                config_str = ", ".join([
                    f"{k}: {v.get('value', 'N/A')}" 
                    for k, v in chunker_config.items() 
                    if isinstance(v, dict) and 'value' in v
                ])
                if config_str:
                    msg.info(f"   Configuração: {config_str}")
            
            msg.info(f"   Embedder: {embedder_name}")
            msg.info(f"   Collection: {collection_name}")
            msg.info(f"   📊 Total de chunks: {chunk_count}")
            msg.info("")
        
        msg.info(f"{'='*80}")
        msg.good(f"✅ Total geral de chunks: {total_chunks_all}")
        msg.info(f"{'='*80}\n")
        
    except Exception as e:
        msg.fail(f"Erro ao obter informações: {str(e)}")
        import traceback
        traceback.print_exc()

async def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verifica informações sobre chunks criados")
    parser.add_argument("--doc-uuid", type=str, help="UUID do documento específico (opcional)")
    args = parser.parse_args()
    
    client = await get_weaviate_client()
    if not client:
        msg.fail("Não foi possível conectar ao Weaviate")
        return
    
    await get_document_info(client, args.doc_uuid)
    client.close()

if __name__ == "__main__":
    asyncio.run(main())

