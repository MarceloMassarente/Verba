"""
Weaviate Backup Utility
Exporta e restaura collections completas do Weaviate

Funcionalidades:
- Exportar todos os chunks de uma collection para JSON
- Validar integridade do backup
- Restaurar chunks de um backup
"""

import json
import asyncio
from typing import List, Dict, Optional, Any
from pathlib import Path
from wasabi import msg
from datetime import datetime


async def backup_collection(
    client,
    collection_name: str,
    output_file: str,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Exporta collection completa para backup.
    
    Args:
        client: Cliente Weaviate
        collection_name: Nome da collection a fazer backup
        output_file: Caminho do arquivo de saída (JSON)
        batch_size: Tamanho do batch para exportação (padrão: 100)
    
    Returns:
        Dict com:
        - success: bool
        - total_chunks: int
        - backup_file: str
        - errors: List[str]
    """
    result = {
        "success": False,
        "total_chunks": 0,
        "backup_file": output_file,
        "errors": [],
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Verifica se collection existe
        if not await client.collections.exists(collection_name):
            result["errors"].append(f"Collection '{collection_name}' não existe")
            return result
        
        collection = client.collections.get(collection_name)
        
        # Exporta em batches para não sobrecarregar memória
        all_chunks = []
        offset = 0
        total_exported = 0
        
        msg.info(f"📦 Iniciando backup de '{collection_name}'...")
        
        while True:
            try:
                # Busca batch de chunks
                results = await collection.query.fetch_objects(
                    limit=batch_size,
                    offset=offset
                )
                
                if not results.objects:
                    break
                
                # Processa cada chunk
                for obj in results.objects:
                    chunk_data = {
                        "uuid": str(obj.uuid),
                        "properties": dict(obj.properties) if obj.properties else {},
                        "vector": obj.vector.get("default") if hasattr(obj, "vector") and obj.vector else None
                    }
                    all_chunks.append(chunk_data)
                    total_exported += 1
                
                offset += batch_size
                
                # Log progresso a cada 1000 chunks
                if total_exported % 1000 == 0:
                    msg.info(f"  📦 Exportados {total_exported} chunks...")
                
                # Yield para não bloquear event loop
                await asyncio.sleep(0)
                
            except Exception as e:
                result["errors"].append(f"Erro ao exportar batch (offset {offset}): {str(e)}")
                msg.warn(f"Erro no batch {offset}: {str(e)}")
                break
        
        # Valida integridade do backup
        validation_result = _validate_backup_integrity(all_chunks)
        if not validation_result["valid"]:
            result["errors"].extend(validation_result["errors"])
            msg.warn("⚠️ Backup tem problemas de integridade")
        
        # Salva backup em arquivo
        backup_data = {
            "collection_name": collection_name,
            "timestamp": result["timestamp"],
            "total_chunks": len(all_chunks),
            "chunks": all_chunks,
            "validation": validation_result
        }
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        result["success"] = True
        result["total_chunks"] = len(all_chunks)
        
        msg.good(f"✅ Backup concluído: {len(all_chunks)} chunks salvos em '{output_file}'")
        
        return result
        
    except Exception as e:
        result["errors"].append(f"Erro ao fazer backup: {str(e)}")
        msg.fail(f"Erro ao fazer backup: {str(e)}")
        return result


def _validate_backup_integrity(chunks: List[Dict]) -> Dict[str, Any]:
    """
    Valida integridade do backup.
    
    Args:
        chunks: Lista de chunks do backup
    
    Returns:
        Dict com:
        - valid: bool
        - errors: List[str]
        - warnings: List[str]
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    if not chunks:
        result["warnings"].append("Backup está vazio")
        return result
    
    # Valida UUIDs
    uuids = set()
    for i, chunk in enumerate(chunks):
        if "uuid" not in chunk:
            result["errors"].append(f"Chunk {i} não tem UUID")
            result["valid"] = False
        else:
            uuid = chunk["uuid"]
            if uuid in uuids:
                result["errors"].append(f"UUID duplicado: {uuid}")
                result["valid"] = False
            uuids.add(uuid)
    
    # Valida propriedades obrigatórias
    required_props = ["content", "doc_uuid"]
    for i, chunk in enumerate(chunks):
        props = chunk.get("properties", {})
        for prop in required_props:
            if prop not in props:
                result["warnings"].append(f"Chunk {i} (UUID: {chunk.get('uuid', 'unknown')}) não tem propriedade '{prop}'")
    
    return result


async def restore_collection(
    client,
    backup_file: str,
    collection_name: Optional[str] = None,
    batch_size: int = 50,
    skip_existing: bool = True
) -> Dict[str, Any]:
    """
    Restaura collection de um backup.
    
    Args:
        client: Cliente Weaviate
        backup_file: Caminho do arquivo de backup (JSON)
        collection_name: Nome da collection de destino (usa do backup se None)
        batch_size: Tamanho do batch para inserção (padrão: 50)
        skip_existing: Se True, pula chunks que já existem
    
    Returns:
        Dict com:
        - success: bool
        - total_restored: int
        - errors: List[str]
    """
    result = {
        "success": False,
        "total_restored": 0,
        "errors": [],
        "skipped": 0
    }
    
    try:
        # Carrega backup
        backup_path = Path(backup_file)
        if not backup_path.exists():
            result["errors"].append(f"Arquivo de backup não encontrado: {backup_file}")
            return result
        
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        
        # Valida estrutura do backup
        if "chunks" not in backup_data:
            result["errors"].append("Backup inválido: não contém 'chunks'")
            return result
        
        chunks = backup_data["chunks"]
        target_collection_name = collection_name or backup_data.get("collection_name")
        
        if not target_collection_name:
            result["errors"].append("Nome da collection não especificado e não encontrado no backup")
            return result
        
        msg.info(f"📥 Restaurando {len(chunks)} chunks para '{target_collection_name}'...")
        
        # Verifica se collection existe
        if not await client.collections.exists(target_collection_name):
            result["errors"].append(f"Collection '{target_collection_name}' não existe. Crie a collection antes de restaurar.")
            return result
        
        collection = client.collections.get(target_collection_name)
        
        # Restaura em batches
        restored = 0
        skipped = 0
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            try:
                # Prepara objetos para inserção
                objects_to_insert = []
                for chunk in batch:
                    # Verifica se já existe (se skip_existing)
                    if skip_existing:
                        try:
                            exists = await collection.data.exists(chunk["uuid"])
                            if exists:
                                skipped += 1
                                continue
                        except Exception:
                            # Se erro ao verificar, tenta inserir mesmo assim
                            pass
                    
                    # Prepara objeto
                    obj_data = {
                        "uuid": chunk["uuid"],
                        "properties": chunk.get("properties", {})
                    }
                    
                    # Adiciona vetor se disponível
                    if chunk.get("vector"):
                        obj_data["vector"] = chunk["vector"]
                    
                    objects_to_insert.append(obj_data)
                
                # Insere batch
                if objects_to_insert:
                    # Weaviate v4 usa insert_many para batch
                    try:
                        await collection.data.insert_many(objects_to_insert)
                        restored += len(objects_to_insert)
                    except Exception as e:
                        # Se insert_many falhar, tenta inserir um por um
                        for obj in objects_to_insert:
                            try:
                                await collection.data.insert(**obj)
                                restored += 1
                            except Exception as insert_error:
                                result["errors"].append(f"Erro ao inserir chunk {obj['uuid']}: {str(insert_error)}")
                
                # Log progresso
                if (i + batch_size) % 500 == 0 or (i + batch_size) >= len(chunks):
                    msg.info(f"  📥 Restaurados {restored} chunks (pulados: {skipped})...")
                
                # Yield para não bloquear event loop
                await asyncio.sleep(0)
                
            except Exception as e:
                result["errors"].append(f"Erro ao restaurar batch {i}-{i+batch_size}: {str(e)}")
                msg.warn(f"Erro no batch {i}: {str(e)}")
        
        result["success"] = len(result["errors"]) == 0
        result["total_restored"] = restored
        result["skipped"] = skipped
        
        if result["success"]:
            msg.good(f"✅ Restauração concluída: {restored} chunks restaurados, {skipped} pulados")
        else:
            msg.warn(f"⚠️ Restauração concluída com erros: {restored} chunks restaurados, {len(result['errors'])} erros")
        
        return result
        
    except Exception as e:
        result["errors"].append(f"Erro ao restaurar backup: {str(e)}")
        msg.fail(f"Erro ao restaurar backup: {str(e)}")
        return result


async def verify_backup_file(backup_file: str) -> Dict[str, Any]:
    """
    Verifica integridade de um arquivo de backup sem restaurar.
    
    Args:
        backup_file: Caminho do arquivo de backup
    
    Returns:
        Dict com resultado da verificação
    """
    result = {
        "valid": False,
        "errors": [],
        "warnings": [],
        "total_chunks": 0,
        "collection_name": None,
        "timestamp": None
    }
    
    try:
        backup_path = Path(backup_file)
        if not backup_path.exists():
            result["errors"].append(f"Arquivo não encontrado: {backup_file}")
            return result
        
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        
        # Valida estrutura
        if "chunks" not in backup_data:
            result["errors"].append("Backup inválido: não contém 'chunks'")
            return result
        
        result["collection_name"] = backup_data.get("collection_name")
        result["timestamp"] = backup_data.get("timestamp")
        result["total_chunks"] = len(backup_data["chunks"])
        
        # Valida integridade
        validation = _validate_backup_integrity(backup_data["chunks"])
        result["errors"].extend(validation["errors"])
        result["warnings"].extend(validation["warnings"])
        result["valid"] = validation["valid"] and len(validation["errors"]) == 0
        
        return result
        
    except json.JSONDecodeError as e:
        result["errors"].append(f"Erro ao decodificar JSON: {str(e)}")
        return result
    except Exception as e:
        result["errors"].append(f"Erro ao verificar backup: {str(e)}")
        return result

