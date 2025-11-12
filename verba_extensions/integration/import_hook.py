"""
Integração: Hook no import_document para capturar passage_uuids
e disparar ETL A2 após importação

⚠️ PATCH/MONKEY PATCH - Documentado em verba_extensions/patches/README_PATCHES.md

Este é um monkey patch que modifica WeaviateManager.import_document() sem alterar código original.
Ao atualizar Verba, verificar se método ainda existe e reaplicar se necessário.

Aplicado via: verba_extensions/startup.py (durante inicialização)
"""

import os
from typing import List, Dict, Set, Optional
from wasabi import msg

# Track ETL executions to prevent duplicates
_etl_executions_in_progress: Set[str] = set()

# Store logger per doc_uuid for ETL completion notifications
_logger_registry: Dict[str, any] = {}  # doc_uuid -> LoggerManager

def patch_weaviate_manager():
    """
    Aplica patch no WeaviateManager.import_document para capturar passage_uuids
    e disparar ETL via hook
    """
    try:
        from goldenverba.components import managers
        
        # Guarda método original
        original_import = managers.WeaviateManager.import_document
        
        async def patched_import_document(
            self,
            client,
            document: "Document",
            embedder: str,
        ):
            """Importa documento e captura passage_uuids para ETL"""
            # Verifica se ETL está habilitado ANTES de importar
            # Padrão: True (ETL sempre ativo por padrão, a menos que explicitamente desabilitado)
            enable_etl = document.meta.get("enable_etl", True) if hasattr(document, 'meta') and document.meta else True
            
            # Tenta obter logger do document.meta (passado temporariamente por process_single_document)
            logger = document.meta.get("_temp_logger") if hasattr(document, 'meta') and document.meta else None
            file_id = document.meta.get("file_id") if hasattr(document, 'meta') and document.meta else None
            
            # Remove logger de document.meta IMEDIATAMENTE após usar para evitar problemas de serialização
            # (não deve estar presente quando documento for serializado em JSON)
            if hasattr(document, 'meta') and document.meta:
                document.meta.pop('_temp_logger', None)
            
            # Se não há meta ou não tem enable_etl, assume True (ETL universal)
            if not hasattr(document, 'meta') or not document.meta:
                enable_etl = True
            elif "enable_etl" not in document.meta:
                # Se não especificado, assume True para aplicar ETL universalmente
                enable_etl = True
            
            # Importa Filter antes (necessário para recuperação)
            try:
                from weaviate.classes.query import Filter
            except ImportError:
                # Fallback para v3 - usa estrutura de filtro v3
                Filter = None
            
            # Helper para verificar se cliente está conectado
            def _is_client_connected(client):
                """Verifica se cliente está conectado de forma segura"""
                try:
                    # Tenta acessar uma propriedade que só existe se conectado
                    # Se o cliente está fechado, isso lançará uma exceção
                    _ = client.collections
                    return True
                except (AttributeError, RuntimeError, Exception) as e:
                    error_str = str(e).lower()
                    if "closed" in error_str or "not connected" in error_str or "disconnect" in error_str:
                        return False
                    # Outros erros podem indicar problema diferente, mas assumimos desconectado
                    return False
            
            # Helper para obter novo cliente se necessário
            async def _get_working_client():
                """Obtém cliente funcionando, reconecta automaticamente se necessário"""
                if _is_client_connected(client):
                    return client
                
                # Cliente fechado - tenta reconectar usando credenciais do ambiente ou manager
                msg.warn("[ETL-POST] Cliente fechado, tentando reconectar automaticamente...")
                try:
                    # Tenta obter credenciais de várias fontes
                    deployment = os.getenv("DEFAULT_DEPLOYMENT", "Custom")
                    
                    # Prioridade: WEAVIATE_HTTP_HOST (Railway interno) > WEAVIATE_URL_VERBA > other
                    http_host = os.getenv("WEAVIATE_HTTP_HOST")
                    url = os.getenv("WEAVIATE_URL_VERBA")
                    
                    # Se temos WEAVIATE_HTTP_HOST (Railway), usa ele com configuração Custom
                    if http_host:
                        url = http_host
                        deployment = "Custom"
                        port = os.getenv("WEAVIATE_HTTP_PORT", "8080")
                    else:
                        port = os.getenv("WEAVIATE_PORT", "8080")
                    
                    key = os.getenv("WEAVIATE_API_KEY_VERBA", "")
                    
                    if not url:
                        msg.warn("[ETL-POST] Não foi possível determinar URL do Weaviate para reconexão")
                        return None
                    
                    # Reconecta usando o manager
                    from goldenverba.components import managers
                    weaviate_manager = managers.WeaviateManager()
                    
                    # Tenta reconectar baseado no deployment type
                    if deployment == "Custom":
                        new_client = await weaviate_manager.connect_to_custom(url, key, port)
                    elif deployment == "Weaviate":
                        new_client = await weaviate_manager.connect_to_cluster(url, key)
                    else:
                        msg.warn(f"[ETL-POST] Deployment type '{deployment}' não suportado para reconexão automática")
                        return None
                    
                    # Verifica se conectou
                    if new_client:
                        # Cliente v4 já está conectado, mas verificamos
                        try:
                            if hasattr(new_client, 'connect'):
                                await new_client.connect()
                            if await new_client.is_ready():
                                msg.good("[ETL-POST] ✅ Reconectado automaticamente com sucesso")
                                return new_client
                        except Exception as e:
                            msg.warn(f"[ETL-POST] Cliente reconectado mas não está pronto: {str(e)}")
                    
                    return None
                except Exception as e:
                    msg.warn(f"[ETL-POST] Erro ao tentar reconectar: {str(e)}")
                    return None
            
            # Chama método original (NÃO retorna doc_uuid - método original não retorna)
            # Precisamos buscar doc_uuid após o import
            doc_uuid = None
            try:
                await original_import(self, client, document, embedder)
                # Método original não retorna doc_uuid, então buscamos pelo título
                if Filter is not None:
                    try:
                        import asyncio
                        # Verifica se cliente ainda está conectado após import
                        if not _is_client_connected(client):
                            msg.warn("[ETL-POST] Cliente fechado após import - tentando reconectar...")
                            working_client = await _get_working_client()
                            if not working_client:
                                msg.warn("[ETL-POST] Não foi possível reconectar - doc_uuid não será obtido")
                                doc_uuid = None
                            else:
                                client = working_client
                        
                        if _is_client_connected(client):
                            # Tenta buscar doc_uuid com retry (pode levar um pouco para o Weaviate commit)
                            document_collection = client.collections.get(self.document_collection_name)
                            doc_uuid = None
                            max_retries = 3
                            for attempt in range(max_retries):
                                if attempt > 0:
                                    await asyncio.sleep(0.2)  # Delay entre tentativas
                                
                                results = await document_collection.query.fetch_objects(
                                    filters=Filter.by_property("title").equal(document.title),
                                    limit=1
                                )
                                if results.objects:
                                    doc_uuid = str(results.objects[0].uuid)
                                    msg.info(f"[ETL-POST] ✅ doc_uuid obtido após import (tentativa {attempt + 1}): {doc_uuid[:50]}...")
                                    break
                            
                            if not doc_uuid:
                                msg.warn(f"[ETL-POST] ⚠️ Documento '{document.title}' não encontrado após {max_retries} tentativas - ETL não será executado")
                            else:
                                # Armazena logger para uso no hook ETL (já vem do document.meta)
                                if logger is not None:
                                    _logger_registry[doc_uuid] = logger
                                    temp_doc_uuid_for_logger = doc_uuid
                        else:
                            msg.warn("[ETL-POST] Cliente não conectado - não é possível buscar doc_uuid")
                    except Exception as recovery_error:
                        error_str = str(recovery_error).lower()
                        if "closed" in error_str or "not connected" in error_str:
                            msg.warn("[ETL-POST] ⚠️ Cliente fechado durante busca de doc_uuid - ETL não será executado")
                        else:
                            msg.warn(f"[ETL-POST] ⚠️ Erro ao buscar doc_uuid após import: {str(recovery_error)}")
            except Exception as import_error:
                # Se falhar, tenta recuperar doc_uuid pela busca do documento
                # (alguns chunks podem ter sido inseridos mesmo com erro)
                error_str = str(import_error).lower()
                msg.warn(f"[ETL-POST] Import teve erro: {str(import_error)[:100]}")
                
                # Verifica se o cliente está conectado antes de tentar recuperar
                if Filter is not None and _is_client_connected(client):
                    try:
                        # Tenta buscar documento pelo nome para recuperar doc_uuid
                        document_collection = client.collections.get(self.document_collection_name)
                        results = await document_collection.query.fetch_objects(
                            filters=Filter.by_property("title").equal(document.title),
                            limit=1
                        )
                        if results.objects:
                            doc_uuid = str(results.objects[0].uuid)
                            msg.info(f"[ETL-POST] Recuperado doc_uuid após erro: {doc_uuid[:50]}...")
                    except Exception as recovery_error:
                        # Se o erro for de cliente fechado, não tenta recuperar
                        recovery_str = str(recovery_error).lower()
                        if "closed" in recovery_str or "not connected" in recovery_str:
                            msg.warn("[ETL-POST] Cliente fechado durante recuperação, não foi possível recuperar doc_uuid")
                        else:
                            msg.warn(f"[ETL-POST] Não foi possível recuperar doc_uuid: {str(recovery_error)}")
                elif not _is_client_connected(client):
                    msg.warn("[ETL-POST] Cliente não está conectado, não é possível recuperar doc_uuid")
                # Re-raise para não mascarar o erro original
                raise import_error
            
            # Se ETL habilitado e doc_uuid obtido, dispara ETL
            msg.info(f"[ETL-POST] Verificando ETL pós-chunking: enable_etl={enable_etl}, doc_uuid={'present' if doc_uuid else 'None'}")
            if enable_etl and doc_uuid:
                try:
                    import asyncio
                    
                    # Verifica se cliente está conectado antes de tentar ETL
                    working_client = await _get_working_client()
                    if not working_client:
                        msg.warn("[ETL-POST] Cliente não conectado - ETL pós-chunking será pulado (chunks já foram importados)")
                        msg.warn("[ETL-POST] ETL pode ser executado manualmente mais tarde ou após reconexão")
                    else:
                        client = working_client
                        msg.info(f"[ETL-POST] ETL A2 habilitado - buscando chunks importados para doc_uuid: {doc_uuid[:50]}...")
                        embedder_collection_name = self.embedding_table.get(embedder)
                        if embedder_collection_name:
                            try:
                                embedder_collection = client.collections.get(embedder_collection_name)
                                
                                # Pequeno delay para garantir que chunks foram inseridos
                                await asyncio.sleep(0.2)
                                
                                # Busca passages por doc_uuid
                                msg.info(f"[ETL] Buscando passages no Weaviate após import...")
                                passages = await embedder_collection.query.fetch_objects(
                                    filters=Filter.by_property("doc_uuid").equal(doc_uuid),
                                    limit=10000
                                )
                                
                                passage_uuids = [str(p.uuid) for p in passages.objects]
                                
                                if passage_uuids:
                                    # Verifica se ETL já está em execução para este doc_uuid
                                    # Usa lock thread-safe para evitar race conditions
                                    if doc_uuid in _etl_executions_in_progress:
                                        # Silently skip duplicate execution (no log spam)
                                        # This is expected during concurrent imports
                                        continue
                                    else:
                                        # Marca como em execução ANTES de iniciar task
                                        _etl_executions_in_progress.add(doc_uuid)
                                        
                                        msg.info(f"[ETL] ✅ {len(passage_uuids)} chunks encontrados - executando ETL A2 (NER + Section Scope) em background")
                                        # Dispara ETL via hook (async, não bloqueia import)
                                        from verba_extensions.hooks import global_hooks
                                        tenant = os.getenv("WEAVIATE_TENANT")
                                        
                                        # Executa em background para não bloquear
                                        async def run_etl_hook():
                                            # Obtém cliente novamente dentro da task (pode ter fechado)
                                            # Usa retry com reconexão automática
                                            hook_client = None
                                            max_retries = 3
                                            for retry in range(max_retries):
                                                hook_client = await _get_working_client()
                                                if hook_client:
                                                    break
                                                if retry < max_retries - 1:
                                                    await asyncio.sleep(1)  # Aguarda antes de tentar novamente
                                                    msg.info(f"[ETL] Tentando reconectar (tentativa {retry + 2}/{max_retries})...")
                                            
                                            if not hook_client:
                                                msg.warn("[ETL] ⚠️ Não foi possível reconectar após múltiplas tentativas - ETL será pulado")
                                                msg.warn("[ETL] Chunks já foram importados com sucesso, mas ETL pós-chunking não será executado")
                                                # Limpa logger do registry
                                                if doc_uuid in _logger_registry:
                                                    del _logger_registry[doc_uuid]
                                                return
                                            
                                            msg.info(f"[ETL] 🚀 Iniciando ETL A2 em background para {len(passage_uuids)} chunks")
                                            try:
                                                # Passa logger via kwargs para o hook poder notificar conclusão
                                                etl_logger = _logger_registry.get(doc_uuid)
                                                await global_hooks.execute_hook_async(
                                                    'import.after',
                                                    hook_client,
                                                    doc_uuid,
                                                    passage_uuids,
                                                    tenant=tenant,
                                                    enable_etl=True,
                                                    collection_name=embedder_collection_name,  # Passa nome da collection
                                                    logger=etl_logger,  # Passa logger para notificação
                                                    file_id=file_id  # Para notificação
                                                )
                                                msg.good(f"[ETL] ✅ ETL A2 concluído para {len(passage_uuids)} chunks")
                                            except Exception as etl_error:
                                                error_str = str(etl_error).lower()
                                                # Categoriza erros para logging apropriado
                                                if "closed" in error_str or "not connected" in error_str or "disconnect" in error_str:
                                                    msg.warn(f"[ETL] ⚠️ ETL A2 falhou: cliente desconectado durante execução (não crítico)")
                                                elif any(keyword in error_str for keyword in [
                                                    "property", "schema", "field", "missing", "not found",
                                                    "does not exist", "unknown property", "attributeerror"
                                                ]):
                                                    # Erros de schema/propriedades - são esperados e não críticos
                                                    msg.info(f"[ETL] ⚠️ ETL A2 pulado: schema/propriedade não encontrada (não crítico)")
                                                else:
                                                    # Outros erros - logar mas não falhar
                                                    import traceback
                                                    msg.warn(f"[ETL] ⚠️ ETL A2 falhou (não crítico): {type(etl_error).__name__}: {str(etl_error)[:200]}")
                                                    # Log traceback apenas para erros não esperados
                                                    if "schema" not in error_str and "property" not in error_str:
                                                        msg.warn(f"[ETL] Traceback: {traceback.format_exc()[:500]}")
                                            finally:
                                                # Remove da lista de execuções em progresso
                                                _etl_executions_in_progress.discard(doc_uuid)
                                                # Limpa logger do registry após uso
                                                if doc_uuid in _logger_registry:
                                                    del _logger_registry[doc_uuid]
                                        
                                        asyncio.create_task(run_etl_hook())
                                else:
                                    msg.warn(f"[ETL] ⚠️ Nenhum chunk encontrado para doc_uuid {doc_uuid[:50]}... - ETL não será executado")
                            except Exception as collection_error:
                                error_str = str(collection_error).lower()
                                if "closed" in error_str or "not connected" in error_str:
                                    msg.warn("[ETL-POST] Cliente fechado durante busca de chunks - ETL não será executado")
                                else:
                                    raise
                                
                except Exception as e:
                    # Não falha o import se ETL der erro
                    import traceback
                    error_str = str(e).lower()
                    # Categoriza erros para logging apropriado
                    if "closed" in error_str or "not connected" in error_str or "disconnect" in error_str:
                        msg.warn("[ETL-POST] Cliente desconectado - ETL pós-chunking não executado (não crítico)")
                    elif any(keyword in error_str for keyword in [
                        "property", "schema", "field", "missing", "not found",
                        "does not exist", "unknown property", "attributeerror"
                    ]):
                        # Erros de schema/propriedades - são esperados e não críticos
                        msg.info("[ETL-POST] ETL A2 pulado: schema/propriedade não encontrada (não crítico)")
                    else:
                        # Outros erros - logar mas não falhar
                        msg.warn(f"[ETL-POST] ETL A2 não executado (não crítico): {type(e).__name__}: {str(e)[:200]}")
                        # Log traceback apenas para erros não esperados
                        if "schema" not in error_str and "property" not in error_str:
                            msg.warn(f"[ETL-POST] Traceback: {traceback.format_exc()[:500]}")
            else:
                if not enable_etl:
                    msg.info(f"[ETL-POST] ETL pós-chunking não habilitado (enable_etl=False)")
                if not doc_uuid:
                    msg.warn(f"[ETL-POST] ETL pós-chunking não executado (doc_uuid não disponível)")
        
        # Substitui método (monkey patch)
        managers.WeaviateManager.import_document = patched_import_document
        
        msg.info("✅ Hook ETL A2 integrado no WeaviateManager")
        return True
        
    except Exception as e:
        msg.warn(f"Erro ao aplicar hook ETL: {str(e)}")
        return False


def patch_verba_manager():
    """
    Patch adicional no VerbaManager se necessário
    """
    try:
        from goldenverba import verba_manager
        
        # Aqui podemos adicionar outros patches se necessário
        # Por enquanto, o patch no WeaviateManager é suficiente
        
        return True
    except Exception as e:
        msg.warn(f"Erro no patch VerbaManager: {str(e)}")
        return False
