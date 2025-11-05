"""
Integração: Hook no import_document para capturar passage_uuids
e disparar ETL A2 após importação

⚠️ PATCH/MONKEY PATCH - Documentado em verba_extensions/patches/README_PATCHES.md

Este é um monkey patch que modifica WeaviateManager.import_document() sem alterar código original.
Ao atualizar Verba, verificar se método ainda existe e reaplicar se necessário.

Aplicado via: verba_extensions/startup.py (durante inicialização)
"""

import os
from typing import List, Dict
from wasabi import msg

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
            
            # Chama método original (NÃO retorna doc_uuid - método original não retorna)
            # Precisamos buscar doc_uuid após o import
            doc_uuid = None
            try:
                await original_import(self, client, document, embedder)
                # Método original não retorna doc_uuid, então buscamos pelo título
                if Filter is not None:
                    try:
                        import asyncio
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
                    except Exception as recovery_error:
                        msg.warn(f"[ETL-POST] ⚠️ Erro ao buscar doc_uuid após import: {str(recovery_error)}")
            except Exception as import_error:
                # Se falhar, tenta recuperar doc_uuid pela busca do documento
                # (alguns chunks podem ter sido inseridos mesmo com erro)
                msg.warn(f"[ETL-POST] Import teve erro, mas tentando recuperar doc_uuid: {str(import_error)}")
                
                # Verifica se o cliente está conectado antes de tentar recuperar
                if Filter is not None:
                    try:
                        # Verifica se cliente está conectado
                        if not await client.is_ready():
                            msg.warn("Cliente não está conectado, não é possível recuperar doc_uuid")
                        else:
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
                        if "closed" in str(recovery_error).lower() or "not connected" in str(recovery_error).lower():
                            msg.warn("Cliente fechado durante recuperação, não foi possível recuperar doc_uuid")
                        else:
                            msg.warn(f"Não foi possível recuperar doc_uuid: {str(recovery_error)}")
                # Re-raise para não mascarar o erro original
                raise import_error
            
            # Se ETL habilitado e doc_uuid obtido, dispara ETL
            msg.info(f"[ETL-POST] Verificando ETL pós-chunking: enable_etl={enable_etl}, doc_uuid={'present' if doc_uuid else 'None'}")
            if enable_etl and doc_uuid:
                try:
                    import asyncio
                    
                    msg.info(f"[ETL-POST] ETL A2 habilitado - buscando chunks importados para doc_uuid: {doc_uuid[:50]}...")
                    embedder_collection_name = self.embedding_table.get(embedder)
                    if embedder_collection_name:
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
                            msg.info(f"[ETL] ✅ {len(passage_uuids)} chunks encontrados - executando ETL A2 (NER + Section Scope) em background")
                            # Dispara ETL via hook (async, não bloqueia import)
                            from verba_extensions.hooks import global_hooks
                            tenant = os.getenv("WEAVIATE_TENANT")
                            
                            # Executa em background para não bloquear
                            async def run_etl_hook():
                                msg.info(f"[ETL] 🚀 Iniciando ETL A2 em background para {len(passage_uuids)} chunks")
                                try:
                                    await global_hooks.execute_hook_async(
                                        'import.after',
                                        client,
                                        doc_uuid,
                                        passage_uuids,
                                        tenant=tenant,
                                        enable_etl=True
                                    )
                                    msg.good(f"[ETL] ✅ ETL A2 concluído para {len(passage_uuids)} chunks")
                                except Exception as etl_error:
                                    msg.warn(f"[ETL] ⚠️ ETL A2 falhou (não crítico): {str(etl_error)}")
                            
                            asyncio.create_task(run_etl_hook())
                        else:
                            msg.warn(f"[ETL] ⚠️ Nenhum chunk encontrado para doc_uuid {doc_uuid[:50]}... - ETL não será executado")
                                
                except Exception as e:
                    # Não falha o import se ETL der erro
                    import traceback
                    msg.warn(f"[ETL-POST] ETL A2 não executado (não crítico): {type(e).__name__}: {str(e)}")
                    msg.warn(f"[ETL-POST] Traceback: {traceback.format_exc()}")
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
