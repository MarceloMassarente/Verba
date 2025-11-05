#!/usr/bin/env python3
"""
Script para apagar e recriar collections com schema ETL-aware
IMPORTANTE: Isso apagará TODOS os dados (chunks e documentos)!

USO:
    # Com API key configurada
    export WEAVIATE_API_KEY="sua-api-key"
    python scripts/recreate_collections_etl_aware.py --force
    
    # Ou via variável de ambiente
    FORCE_RECREATE=1 python scripts/recreate_collections_etl_aware.py
    
    # No Railway (via terminal)
    railway run python scripts/recreate_collections_etl_aware.py --force
"""

import os
import sys
import asyncio
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
        
        if api_key:
            # Weaviate Cloud com API key - usa HTTP apenas
            msg.info(f"Connecting to Weaviate Cloud at {url} with Auth (HTTP only)")
            client = weaviate.connect_to_weaviate_cloud(
                cluster_url=url,
                auth_credentials=AuthApiKey(api_key),
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=60, query=300, insert=300)
                )
            )
        else:
            # Sem auth - tenta via URL
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


async def list_embedding_collections(client):
    """Lista todas as collections de embedding"""
    try:
        all_collections = client.collections.list_all()
        embedding_collections = [c for c in all_collections if "VERBA_Embedding" in c]
        
        msg.info(f"\n📚 Collections de embedding encontradas: {len(embedding_collections)}")
        for coll_name in embedding_collections:
            coll = client.collections.get(coll_name)
            # Conta objetos
            try:
                count_result = await coll.aggregate.over_all(total_count=True)
                count = count_result.total_count if hasattr(count_result, 'total_count') else 0
            except:
                count = 0
            msg.info(f"   - {coll_name}: {count} objetos")
        
        return embedding_collections
    except Exception as e:
        msg.fail(f"Erro ao listar collections: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


async def delete_collection(client, collection_name: str):
    """Deleta uma collection"""
    try:
        if not client.collections.exists(collection_name):
            msg.warn(f"Collection {collection_name} não existe - pulando")
            return False
        
        msg.info(f"🗑️  Deletando collection: {collection_name}...")
        client.collections.delete(collection_name)
        msg.good(f"✅ Collection {collection_name} deletada com sucesso")
        return True
    except Exception as e:
        msg.fail(f"❌ Erro ao deletar {collection_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def verify_collection_has_etl_schema(client, collection_name: str):
    """Verifica se collection tem schema ETL-aware"""
    try:
        if not client.collections.exists(collection_name):
            return False
        
        collection = client.collections.get(collection_name)
        config = await collection.config.get()
        
        etl_props = [
            "entities_local_ids",
            "section_title",
            "section_entity_ids",
            "section_scope_confidence",
            "primary_entity_id",
            "entity_focus_score",
            "etl_version",
        ]
        
        schema_props = [p.name for p in config.properties]
        has_etl = any(prop in schema_props for prop in etl_props)
        
        return has_etl
    except Exception as e:
        msg.warn(f"Erro ao verificar schema de {collection_name}: {str(e)}")
        return False


async def main():
    """Função principal"""
    import sys
    
    msg.info("🔄 Script para recriar collections com schema ETL-aware\n")
    msg.warn("⚠️  ATENÇÃO: Isso apagará TODOS os dados (chunks e documentos)!")
    msg.warn("⚠️  As collections serão recriadas automaticamente na próxima importação")
    msg.warn("⚠️  O patch de schema garantirá que sejam criadas com schema ETL-aware\n")
    
    # Confirmação via argumento ou variável de ambiente
    force = os.getenv("FORCE_RECREATE", "").lower() in ("1", "true", "yes")
    if not force and len(sys.argv) > 1:
        force = sys.argv[1].lower() in ("--force", "-f", "sim", "yes")
    
    if not force:
        msg.warn("💡 Para executar sem confirmação, use:")
        msg.warn("   FORCE_RECREATE=1 python scripts/recreate_collections_etl_aware.py")
        msg.warn("   OU")
        msg.warn("   python scripts/recreate_collections_etl_aware.py --force")
        msg.info("\n⚠️  Operação não executada - use --force para confirmar")
        return
    
    # Conecta ao Weaviate
    client = await get_weaviate_client()
    if not client:
        msg.fail("Não foi possível conectar ao Weaviate")
        return
    
    try:
        # Lista collections existentes
        embedding_collections = await list_embedding_collections(client)
        
        if not embedding_collections:
            msg.warn("Nenhuma collection de embedding encontrada")
            msg.info("💡 Collections serão criadas automaticamente na próxima importação com schema ETL-aware")
            return
        
        # Verifica quais têm schema ETL
        msg.info("\n🔍 Verificando schema das collections...")
        collections_without_etl = []
        for coll_name in embedding_collections:
            has_etl = await verify_collection_has_etl_schema(client, coll_name)
            if has_etl:
                msg.good(f"✅ {coll_name} já tem schema ETL-aware")
            else:
                msg.warn(f"⚠️  {coll_name} NÃO tem schema ETL-aware")
                collections_without_etl.append(coll_name)
        
        if not collections_without_etl:
            msg.good("\n✅ Todas as collections já têm schema ETL-aware!")
            return
        
        # Deleta collections sem schema ETL
        msg.info(f"\n🗑️  Deletando {len(collections_without_etl)} collection(s) sem schema ETL...")
        deleted_count = 0
        for coll_name in collections_without_etl:
            if await delete_collection(client, coll_name):
                deleted_count += 1
            await asyncio.sleep(0.5)  # Pequeno delay entre deletions
        
        msg.good(f"\n✅ {deleted_count} collection(s) deletada(s) com sucesso")
        
        # Informações sobre recriação
        msg.info("\n" + "="*60)
        msg.info("📋 Próximos passos:")
        msg.info("1. Collections serão recriadas automaticamente quando:")
        msg.info("   - Verba iniciar e verificar collections")
        msg.info("   - OU quando você importar um novo documento")
        msg.info("2. O patch de schema ETL-aware garantirá que sejam criadas")
        msg.info("   com todas as propriedades (13 padrão + 7 ETL)")
        msg.info("3. Após recriar, re-importe seus documentos para ter")
        msg.info("   metadados ETL salvos corretamente")
        msg.info("="*60)
        
        # Lista collections restantes
        msg.info("\n📚 Collections restantes:")
        remaining = await list_embedding_collections(client)
        if not remaining:
            msg.info("   (nenhuma - serão criadas na próxima importação)")
        
    except Exception as e:
        msg.fail(f"Erro: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    # Permite forçar execução sem confirmação
    # Use: FORCE_RECREATE=1 python scripts/recreate_collections_etl_aware.py
    asyncio.run(main())

