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
            enable_etl = document.meta.get("enable_etl", True) if hasattr(document, 'meta') and document.meta else True
            
            # Chama método original (retorna doc_uuid)
            doc_uuid = await original_import(self, client, document, embedder)
            
            # Se ETL habilitado e doc_uuid obtido, dispara ETL
            if enable_etl and doc_uuid:
                try:
                    import asyncio
                    from weaviate.classes.query import Filter
                    
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
