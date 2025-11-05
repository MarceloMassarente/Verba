"""
Script para corrigir collections sem schema ETL-aware

Este script verifica e corrige collections que foram criadas antes do patch
ser aplicado. Para collections de embedding, deleta e recria com schema ETL-aware.
Para VERBA_DOCUMENTS e VERBA_CONFIGURATION, o aviso é apenas informativo 
(essas collections não precisam do schema ETL completo).

Uso:
    python scripts/fix_collections_schema.py
"""

import os
import asyncio
from dotenv import load_dotenv
from wasabi import msg

# Carrega variáveis de ambiente
load_dotenv()

# Importa Weaviate
try:
    import weaviate
    from weaviate.classes.config import Configure
    from weaviate.auth import AuthApiKey
except ImportError:
    msg.fail("❌ Weaviate não está instalado. Execute: pip install weaviate-client")
    exit(1)

# Importa schema updater
try:
    from verba_extensions.integration.schema_updater import (
        get_all_embedding_properties,
        check_collection_has_etl_properties,
        get_verba_standard_properties,
    )
except ImportError:
    msg.fail("❌ verba_extensions não encontrado. Certifique-se de estar no diretório raiz do projeto.")
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
        
        msg.info(f"🔗 Conectando via Railway (HTTP: {http_host}:{http_port}, gRPC: {grpc_host}:{grpc_port})")
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


async def check_and_fix_collection(client, collection_name: str, is_embedding: bool = False):
    """
    Verifica e corrige uma collection se necessário
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection
        is_embedding: Se True, é uma collection de embedding que precisa do schema ETL
    """
    if not await client.collections.exists(collection_name):
        msg.info(f"📋 Collection {collection_name} não existe (será criada automaticamente quando necessário)")
        return False
    
    has_etl = await check_collection_has_etl_properties(client, collection_name)
    
    if has_etl:
        msg.good(f"✅ {collection_name} já tem schema ETL-aware")
        return True
    
    if not is_embedding:
        # Collections não-embedding não precisam do schema ETL completo
        msg.info(f"ℹ️  {collection_name} não precisa do schema ETL completo (aviso é apenas informativo)")
        return True
    
    # Collection de embedding sem schema ETL - precisa corrigir
    msg.warn(f"⚠️  {collection_name} existe mas NÃO tem schema ETL-aware")
    
    # Pergunta ao usuário se quer deletar e recriar
    msg.info(f"💡 Para corrigir, deletar e recriar {collection_name} com schema ETL-aware")
    msg.warn(f"⚠️  ATENÇÃO: Isso vai deletar TODOS os dados da collection!")
    
    # Para Railway/produção, não deleta automaticamente
    # Usuário precisa fazer manualmente ou confirmar
    return False


async def list_all_collections(client):
    """Lista todas as collections do Weaviate"""
    collections = await client.collections.list_all()
    return collections


async def main():
    """Função principal"""
    msg.info("🔧 Script de Correção de Schema ETL-aware")
    msg.info("=" * 60)
    
    # Conecta ao Weaviate
    try:
        client = await connect_to_weaviate()
        msg.good("✅ Conectado ao Weaviate")
    except Exception as e:
        msg.fail(f"❌ Erro ao conectar ao Weaviate: {str(e)}")
        return
    
    # Lista todas as collections
    try:
        all_collections = await list_all_collections(client)
        msg.info(f"📋 Encontradas {len(all_collections)} collections")
    except Exception as e:
        msg.fail(f"❌ Erro ao listar collections: {str(e)}")
        await client.close()
        return
    
    # Verifica cada collection
    embedding_collections = []
    other_collections = []
    
    for collection_name in all_collections:
        if "VERBA_Embedding" in collection_name:
            embedding_collections.append(collection_name)
        else:
            other_collections.append(collection_name)
    
    msg.info("\n" + "=" * 60)
    msg.info("📊 Verificando Collections de Embedding")
    msg.info("=" * 60)
    
    collections_to_fix = []
    for collection_name in sorted(embedding_collections):
        needs_fix = await check_and_fix_collection(client, collection_name, is_embedding=True)
        if not needs_fix:
            collections_to_fix.append(collection_name)
    
    msg.info("\n" + "=" * 60)
    msg.info("📊 Verificando Outras Collections")
    msg.info("=" * 60)
    
    for collection_name in sorted(other_collections):
        await check_and_fix_collection(client, collection_name, is_embedding=False)
    
    # Resumo
    msg.info("\n" + "=" * 60)
    msg.info("📋 Resumo")
    msg.info("=" * 60)
    
    if collections_to_fix:
        msg.warn(f"⚠️  {len(collections_to_fix)} collections precisam ser corrigidas:")
        for name in collections_to_fix:
            msg.warn(f"   - {name}")
        msg.info("\n💡 Para corrigir:")
        msg.info("   1. Faça backup dos dados (se necessário)")
        msg.info("   2. Delete as collections manualmente via Weaviate UI ou API")
        msg.info("   3. Reinicie o Verba - as collections serão recriadas com schema ETL-aware")
        msg.info("\n⚠️  ATENÇÃO: Deletar collections remove TODOS os dados!")
    else:
        msg.good("✅ Todas as collections estão com schema correto!")
    
    # Fecha conexão
    await client.close()
    msg.good("✅ Script finalizado")


if __name__ == "__main__":
    asyncio.run(main())

