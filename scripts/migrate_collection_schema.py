#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Migração Segura de Schema do Weaviate
Migra collections existentes para incluir propriedades de framework

Fluxo:
1. Backup completo da collection
2. Validação do backup
3. Criação de nova collection com schema atualizado
4. Migração de dados em batches
5. Validação de integridade
6. Rollback se necessário

⚠️  ATENÇÃO: Este script requer acesso direto ao Weaviate e pode levar tempo
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from wasabi import msg

# Adiciona diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


async def migrate_collection_schema(
    collection_name: str,
    backup_dir: str = "backups",
    delete_old: bool = False,
    skip_backup: bool = False
) -> bool:
    """
    Migra collection para ter propriedades de framework.
    
    Args:
        collection_name: Nome da collection a migrar
        backup_dir: Diretório para salvar backups
        delete_old: Se True, deleta collection antiga após migração bem-sucedida
        skip_backup: Se True, pula backup (NÃO RECOMENDADO)
    
    Returns:
        True se migração foi bem-sucedida
    """
    try:
        from verba_extensions.compatibility.weaviate_imports import get_weaviate_client
        from verba_extensions.integration.schema_updater import get_all_embedding_properties
        from verba_extensions.integration.schema_validator import (
            validate_collection_schema,
            collection_has_framework_properties
        )
        from verba_extensions.utils.weaviate_backup import (
            backup_collection,
            restore_collection,
            verify_backup_file
        )
        
        # Conecta ao Weaviate
        client = await get_weaviate_client()
        if not client:
            msg.fail("❌ Não foi possível conectar ao Weaviate")
            return False
        
        msg.info(f"🔍 Verificando collection '{collection_name}'...")
        
        # Verifica se collection existe
        if not await client.collections.exists(collection_name):
            msg.fail(f"❌ Collection '{collection_name}' não existe")
            return False
        
        # Verifica se já tem propriedades de framework
        if await collection_has_framework_properties(client, collection_name):
            msg.good(f"✅ Collection '{collection_name}' já tem propriedades de framework")
            return True
        
        msg.warn(f"⚠️  Collection '{collection_name}' não tem propriedades de framework")
        msg.info("📋 Iniciando migração...")
        
        # 1. BACKUP
        backup_file = None
        if not skip_backup:
            backup_dir_path = Path(backup_dir)
            backup_dir_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir_path / f"{collection_name}_backup_{timestamp}.json"
            
            msg.info(f"📦 Fazendo backup de '{collection_name}'...")
            backup_result = await backup_collection(
                client,
                collection_name,
                str(backup_file)
            )
            
            if not backup_result["success"]:
                msg.fail(f"❌ Falha no backup: {', '.join(backup_result['errors'])}")
                return False
            
            msg.good(f"✅ Backup concluído: {backup_result['total_chunks']} chunks salvos")
            
            # Valida backup
            msg.info("🔍 Validando backup...")
            validation = await verify_backup_file(str(backup_file))
            if not validation["valid"]:
                msg.warn(f"⚠️  Backup tem problemas: {', '.join(validation['errors'])}")
                response = input("Continuar mesmo assim? (s/N): ")
                if response.lower() != 's':
                    return False
        else:
            msg.warn("⚠️  Backup pulado (NÃO RECOMENDADO)")
        
        # 2. CRIA NOVA COLLECTION COM SCHEMA ATUALIZADO
        new_collection_name = f"{collection_name}_migrated"
        
        # Verifica se já existe
        if await client.collections.exists(new_collection_name):
            msg.warn(f"⚠️  Collection '{new_collection_name}' já existe")
            response = input("Deletar e recriar? (s/N): ")
            if response.lower() == 's':
                await client.collections.delete(new_collection_name)
                msg.info(f"🗑️  Collection '{new_collection_name}' deletada")
            else:
                msg.info("❌ Migração cancelada")
                return False
        
        msg.info(f"🔧 Criando nova collection '{new_collection_name}' com schema atualizado...")
        
        # Obtém propriedades completas (padrão + ETL + framework)
        all_properties = get_all_embedding_properties()
        
        # Obtém configuração da collection antiga para preservar vectorizer
        old_collection = client.collections.get(collection_name)
        old_config = await old_collection.config.get()
        
        try:
            # Cria nova collection
            new_collection = await client.collections.create(
                name=new_collection_name,
                properties=all_properties,
                # Preserva configuração de vectorizer se disponível
                vectorizer_config=old_config.vectorizer_config if hasattr(old_config, 'vectorizer_config') else None,
                vector_index_config=old_config.vector_index_config if hasattr(old_config, 'vector_index_config') else None,
            )
            
            msg.good(f"✅ Collection '{new_collection_name}' criada com {len(all_properties)} propriedades")
        except Exception as e:
            msg.fail(f"❌ Erro ao criar collection: {str(e)}")
            return False
        
        # 3. MIGRA DADOS EM BATCHES
        msg.info(f"📦 Migrando dados de '{collection_name}' para '{new_collection_name}'...")
        
        new_collection = client.collections.get(new_collection_name)
        migrated_count = 0
        error_count = 0
        batch_size = 50
        
        offset = 0
        limit = 100
        
        while True:
            try:
                # Busca batch da collection antiga
                results = await old_collection.query.fetch_objects(
                    limit=limit,
                    offset=offset
                )
                
                if not results.objects:
                    break
                
                # Prepara objetos para inserção
                objects_to_insert = []
                for obj in results.objects:
                    try:
                        obj_data = {
                            "uuid": obj.uuid,
                            "properties": dict(obj.properties) if obj.properties else {}
                        }
                        
                        # Adiciona vetor se disponível
                        if hasattr(obj, "vector") and obj.vector:
                            obj_data["vector"] = obj.vector.get("default") if isinstance(obj.vector, dict) else obj.vector
                        
                        objects_to_insert.append(obj_data)
                    except Exception as e:
                        error_count += 1
                        msg.warn(f"⚠️  Erro ao preparar objeto: {str(e)}")
                
                # Insere batch
                if objects_to_insert:
                    try:
                        # Tenta insert_many primeiro
                        await new_collection.data.insert_many(objects_to_insert)
                        migrated_count += len(objects_to_insert)
                    except Exception as e:
                        # Se falhar, tenta inserir um por um
                        msg.warn(f"⚠️  insert_many falhou, inserindo individualmente: {str(e)}")
                        for obj in objects_to_insert:
                            try:
                                await new_collection.data.insert(**obj)
                                migrated_count += 1
                            except Exception as insert_error:
                                error_count += 1
                                msg.warn(f"⚠️  Erro ao inserir objeto {obj.get('uuid', 'unknown')}: {str(insert_error)}")
                
                offset += limit
                
                # Log progresso
                if migrated_count % 500 == 0:
                    msg.info(f"  📦 Migrados {migrated_count} chunks...")
                
                await asyncio.sleep(0)
                
            except Exception as e:
                msg.warn(f"⚠️  Erro no batch (offset {offset}): {str(e)}")
                error_count += 1
                break
        
        msg.info(f"📊 Migração concluída: {migrated_count} chunks migrados, {error_count} erros")
        
        # 4. VALIDAÇÃO DE INTEGRIDADE
        msg.info("🔍 Validando integridade da migração...")
        
        # Conta chunks na collection antiga e nova
        old_count = await old_collection.query.fetch_objects(limit=1)
        old_total = old_count.total if hasattr(old_count, 'total') else None
        
        new_count = await new_collection.query.fetch_objects(limit=1)
        new_total = new_count.total if hasattr(new_count, 'total') else None
        
        if old_total and new_total:
            if new_total < old_total * 0.95:  # Permite 5% de perda
                msg.fail(f"❌ Validação falhou: {new_total} chunks na nova collection vs {old_total} na antiga")
                msg.info("🔄 Iniciando rollback...")
                
                # ROLLBACK
                if backup_file and backup_file.exists():
                    msg.info("🗑️  Deletando collection migrada...")
                    await client.collections.delete(new_collection_name)
                    
                    msg.info("📥 Restaurando backup...")
                    restore_result = await restore_collection(
                        client,
                        str(backup_file),
                        collection_name
                    )
                    
                    if restore_result["success"]:
                        msg.good("✅ Rollback concluído com sucesso")
                    else:
                        msg.fail(f"❌ Rollback falhou: {', '.join(restore_result['errors'])}")
                        msg.warn(f"⚠️  Backup disponível em: {backup_file}")
                
                return False
            else:
                msg.good(f"✅ Validação passou: {new_total} chunks na nova collection")
        
        # 5. VALIDA SCHEMA
        validation_result = await validate_collection_schema(
            client,
            new_collection_name,
            ["frameworks", "companies", "sectors", "framework_confidence"]
        )
        
        if not validation_result["valid"]:
            msg.warn(f"⚠️  Schema não tem todas as propriedades: {', '.join(validation_result['missing'])}")
        else:
            msg.good("✅ Schema validado: todas as propriedades de framework presentes")
        
        # 6. OPÇÃO DE DELETAR COLLECTION ANTIGA
        if delete_old:
            response = input(f"Deletar collection antiga '{collection_name}'? (s/N): ")
            if response.lower() == 's':
                await client.collections.delete(collection_name)
                msg.info(f"🗑️  Collection '{collection_name}' deletada")
                
                # Renomeia nova collection para nome original (se possível)
                # Nota: Weaviate não permite renomear, então usuário precisa atualizar referências manualmente
                msg.info(f"💡 Collection migrada está em '{new_collection_name}'")
                msg.info(f"💡 Atualize referências para usar '{new_collection_name}' ou recrie '{collection_name}' manualmente")
            else:
                msg.info(f"💡 Collection antiga mantida. Nova collection: '{new_collection_name}'")
        else:
            msg.info(f"💡 Collection antiga mantida. Nova collection: '{new_collection_name}'")
            msg.info(f"💡 Para usar a nova collection, atualize referências ou recrie '{collection_name}' manualmente")
        
        msg.good("✅ Migração concluída com sucesso!")
        if backup_file:
            msg.info(f"💾 Backup salvo em: {backup_file}")
        
        return True
        
    except Exception as e:
        msg.fail(f"❌ Erro durante migração: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Tenta rollback se backup existe
        if backup_file and backup_file.exists():
            msg.info("🔄 Tentando rollback...")
            try:
                await client.collections.delete(new_collection_name)
                msg.info("✅ Collection migrada deletada")
            except:
                pass
        
        return False


async def main():
    """Função principal"""
    parser = argparse.ArgumentParser(
        description="Migra collection do Weaviate para incluir propriedades de framework"
    )
    parser.add_argument(
        "collection_name",
        help="Nome da collection a migrar"
    )
    parser.add_argument(
        "--backup-dir",
        default="backups",
        help="Diretório para salvar backups (padrão: backups)"
    )
    parser.add_argument(
        "--delete-old",
        action="store_true",
        help="Deletar collection antiga após migração bem-sucedida"
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Pular backup (NÃO RECOMENDADO)"
    )
    
    args = parser.parse_args()
    
    if args.skip_backup:
        response = input("⚠️  Backup será pulado. Continuar? (s/N): ")
        if response.lower() != 's':
            msg.info("❌ Migração cancelada")
            return
    
    success = await migrate_collection_schema(
        args.collection_name,
        args.backup_dir,
        args.delete_old,
        args.skip_backup
    )
    
    if success:
        msg.good("✅ Migração concluída com sucesso!")
        sys.exit(0)
    else:
        msg.fail("❌ Migração falhou")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

