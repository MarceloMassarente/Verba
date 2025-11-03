"""
Integração: Hook no import_document para capturar passage_uuids
e disparar ETL A2 após importação
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
            
            # Chama método original (retorna doc_uuid)
            doc_uuid = None
            try:
                doc_uuid = await original_import(self, client, document, embedder)
            except Exception as import_error:
                # Se falhar, tenta recuperar doc_uuid pela busca do documento
                # (alguns chunks podem ter sido inseridos mesmo com erro)
                msg.warn(f"Import teve erro, mas tentando executar ETL: {str(import_error)}")
                if Filter is not None:
                    try:
                        # Tenta buscar documento pelo nome para recuperar doc_uuid
                        document_collection = client.collections.get(self.document_collection_name)
                        results = await document_collection.query.fetch_objects(
                            filters=Filter.by_property("title").equal(document.title),
                            limit=1
                        )
                        if results.objects:
                            doc_uuid = str(results.objects[0].uuid)
                            msg.info(f"Recuperado doc_uuid após erro: {doc_uuid}")
                    except Exception as recovery_error:
                        msg.warn(f"Não foi possível recuperar doc_uuid: {str(recovery_error)}")
                # Re-raise para não mascarar o erro original
                raise import_error
            
            # Se ETL habilitado e doc_uuid obtido, dispara ETL
            if enable_etl and doc_uuid:
                try:
                    import asyncio
                    
                    embedder_collection_name = self.embedding_table.get(embedder)
                    if embedder_collection_name:
                        embedder_collection = client.collections.get(embedder_collection_name)
                        
                        # Pequeno delay para garantir que chunks foram inseridos
                        await asyncio.sleep(0.2)
                        
                        # Busca passages por doc_uuid
                        passages = await embedder_collection.query.fetch_objects(
                            filters=Filter.by_property("doc_uuid").equal(doc_uuid),
                            limit=10000
                        )
                        
                        passage_uuids = [str(p.uuid) for p in passages.objects]
                        
                        if passage_uuids:
                            # Dispara ETL via hook (async, não bloqueia import)
                            from verba_extensions.hooks import global_hooks
                            tenant = os.getenv("WEAVIATE_TENANT")
                            
                            # Executa em background para não bloquear
                            async def run_etl_hook():
                                await global_hooks.execute_hook_async(
                                    'import.after',
                                    client,
                                    doc_uuid,
                                    passage_uuids,
                                    tenant=tenant,
                                    enable_etl=True
                                )
                            
                            asyncio.create_task(run_etl_hook())
                                
                except Exception as e:
                    # Não falha o import se ETL der erro
                    msg.warn(f"ETL A2 não executado (não crítico): {str(e)}")
        
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
