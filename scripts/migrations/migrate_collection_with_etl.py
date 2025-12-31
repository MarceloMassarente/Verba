#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para migrar collection existente para ter propriedades de ETL
Como Weaviate v4 não permite adicionar propriedades depois, este script:
1. Cria nova collection com propriedades de ETL
2. Copia dados da collection antiga
3. Atualiza referências (se necessário)
4. Opcionalmente deleta collection antiga

⚠️  ATENÇÃO: Este script requer acesso direto ao Weaviate e pode levar tempo
"""

import sys
import os
import asyncio
from wasabi import msg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def migrate_collection(old_collection_name: str, new_collection_name: str = None):
    """
    Migra collection para ter propriedades de ETL
    
    Args:
        old_collection_name: Nome da collection existente
        new_collection_name: Nome da nova collection (opcional, usa sufixo _etl se não fornecido)
    """
    try:
        from verba_extensions.compatibility.weaviate_imports import get_weaviate_client
        from verba_extensions.integration.schema_updater import get_etl_properties
        from weaviate.classes.config import Configure, Property, DataType
        
        client = await get_weaviate_client()
        if not client:
            msg.warn("❌ Não foi possível conectar ao Weaviate")
            return False
        
        # Verifica se collection antiga existe
        if not await client.collections.exists(old_collection_name):
            msg.warn(f"❌ Collection {old_collection_name} não existe")
            return False
        
        # Define nome da nova collection
        if not new_collection_name:
            new_collection_name = f"{old_collection_name}_etl"
        
        # Verifica se nova collection já existe
        if await client.collections.exists(new_collection_name):
            msg.warn(f"⚠️  Collection {new_collection_name} já existe")
            response = input("Deseja deletar e recriar? (s/N): ")
            if response.lower() == 's':
                client.collections.delete(new_collection_name)
                msg.info(f"🗑️  Collection {new_collection_name} deletada")
            else:
                msg.info("❌ Migração cancelada")
                return False
        
        msg.info(f"📋 Migrando {old_collection_name} → {new_collection_name}")
        
        # Pega configuração da collection antiga
        old_collection = client.collections.get(old_collection_name)
        old_config = old_collection.config.get()
        
        # Prepara propriedades: antigas + ETL
        all_properties = list(old_config.properties) + get_etl_properties()
        
        # Cria nova collection com todas as propriedades
        msg.info(f"🔧 Criando nova collection {new_collection_name}...")
        
        # Usa mesma configuração de vectorizer
        vectorizer_config = old_config.vectorizer_config
        
        new_collection = client.collections.create(
            name=new_collection_name,
            vectorizer_config=vectorizer_config,
            vector_index_config=old_config.vector_index_config,
            properties=all_properties,
        )
        
        msg.good(f"✅ Collection {new_collection_name} criada")
        
        # Copia dados
        msg.info(f"📦 Copiando dados de {old_collection_name}...")
        
        # Busca todos os objetos
        all_objects = []
        offset = 0
        limit = 100
        
        while True:
            batch = old_collection.query.fetch_objects(limit=limit, offset=offset)
            if not batch.objects:
                break
            
            all_objects.extend(batch.objects)
            offset += limit
            
            if len(batch.objects) < limit:
                break
        
        msg.info(f"   📊 {len(all_objects)} objetos encontrados")
        
        # Insere objetos na nova collection (em batches)
        batch_size = 100
        for i in range(0, len(all_objects), batch_size):
            batch = all_objects[i:i+batch_size]
            
            # Prepara objetos para inserção
            objects_to_insert = []
            for obj in batch:
                props = dict(obj.properties)
                # Adiciona propriedades de ETL vazias (serão preenchidas pelo ETL depois)
                props['entities_local_ids'] = []
                props['section_entity_ids'] = []
                props['section_title'] = ""
                props['section_scope_confidence'] = 0.0
                props['primary_entity_id'] = ""
                props['entity_focus_score'] = 0.0
                props['etl_version'] = ""
                
                objects_to_insert.append({
                    'properties': props,
                    # Mantém formato original do vetor (named vectors ou simples)
                    'vector': obj.vector
                })
            
            # Insere batch
            # Nota: o formato do vetor é passado como está - se a collection antiga
            # tinha named vectors, a nova também terá (criada com mesma config)
            new_collection.data.insert_many(objects_to_insert)
            msg.info(f"   ✅ {min(i+batch_size, len(all_objects))}/{len(all_objects)} objetos copiados")
        
        msg.good(f"✅ Migração concluída: {len(all_objects)} objetos migrados")
        
        msg.info(f"\n💡 Próximos passos:")
        msg.info(f"   1. Atualize código para usar {new_collection_name}")
        msg.info(f"   2. Execute ETL nos novos objetos")
        msg.info(f"   3. Teste queries")
        msg.info(f"   4. Se tudo OK, delete {old_collection_name}")
        
        await client.close()
        return True
        
    except Exception as e:
        msg.warn(f"❌ Erro na migração: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Função principal"""
    print("=" * 80)
    print("🔄 Migração de Collection: Adicionar Propriedades de ETL")
    print("=" * 80 + "\n")
    
    if len(sys.argv) < 2:
        print("Uso: python migrate_collection_with_etl.py <collection_name> [new_collection_name]")
        print("\nExemplo:")
        print("  python migrate_collection_with_etl.py VERBA_Embedding_all_MiniLM_L6_v2")
        sys.exit(1)
    
    old_name = sys.argv[1]
    new_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = await migrate_collection(old_name, new_name)
    
    if success:
        print("\n✅ Migração concluída com sucesso!")
    else:
        print("\n❌ Migração falhou")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())


