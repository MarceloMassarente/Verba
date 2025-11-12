"""
Hook ETL A2 - Executa ETL inteligente após importação no Verba
Integrado no fluxo normal do Verba via hooks
NOVO: Multi-idioma, detecção automática de entidades sem gazetteer obrigatório
"""

import os
from typing import List, Dict, Any, Callable
from wasabi import msg

# Importações do ETL inteligente
_etl_module = None
_nlp = None  # Cache global para modelo spaCy

def get_etl_module():
    """Carrega módulo ETL inteligente com lazy import"""
    global _etl_module
    if _etl_module is not None:
        return _etl_module
    
    try:
        import sys
        # Adicionar ingestor ao path
        if "ingestor" not in sys.modules:
            ingestor_path = os.path.join(os.path.dirname(__file__), "..", "..", "ingestor")
            if os.path.exists(ingestor_path):
                sys.path.insert(0, ingestor_path)
        
        # Tentar importar ETL inteligente
        try:
            from etl_a2_intelligent import (
                extract_entities_intelligent,
                extract_entities_with_gazetteer,
                run_etl_patch_for_passage_uuids,
                load_gazetteer as load_gaz,
            )
            _etl_module = {
                "extract_entities_intelligent": extract_entities_intelligent,
                "extract_entities_with_gazetteer": extract_entities_with_gazetteer,
                "run_etl_patch_for_passage_uuids": run_etl_patch_for_passage_uuids,
                "load_gazetteer": load_gaz,
            }
            msg.info("✅ ETL inteligente (multi-idioma) carregado com sucesso")
            return _etl_module
        except ImportError:
            # Fallback para ETL legado
            msg.warn("⚠️ ETL inteligente não encontrado, usando versão legada")
            from etl_a2 import (
                load_gazetteer as load_gaz,
                run_etl_patch_for_passage_uuids,
            )
            _etl_module = {
                "load_gazetteer": load_gaz,
                "run_etl_patch_for_passage_uuids": run_etl_patch_for_passage_uuids,
            }
            return _etl_module
    except Exception as e:
        msg.warn(f"⚠️ Erro ao carregar ETL: {str(e)}")
        return None

def load_gazetteer(path: str = None) -> Dict:
    """Carrega gazetteer (opcional, para modo legado)"""
    etl = get_etl_module()
    if etl and "load_gazetteer" in etl:
        return etl["load_gazetteer"](path if path else "ingestor/resources/gazetteer.json")
    return {}

def get_nlp():
    """Lazy load spaCy"""
    global _nlp
    if _nlp is not None:
        return _nlp
    
    model = os.getenv("SPACY_MODEL", "pt_core_news_sm")
    try:
        import spacy
        _nlp = spacy.load(model)
        return _nlp
    except Exception as e:
        msg.warn(f"spaCy não disponível para ETL: {str(e)}")
        return None

def match_aliases(text: str, gaz: Dict) -> List[str]:
    """Encontra entity_ids no texto"""
    if not text or not gaz:
        return []
    
    t_lower = text.lower()
    hits = []
    
    for eid, aliases in gaz.items():
        for alias in aliases:
            if alias.lower() in t_lower:
                hits.append(eid)
                break
    
    return sorted(set(hits))

def extract_entities_nlp(text: str) -> List[Dict]:
    """Extrai entidades via spaCy NER
    
    IMPORTANTE: Filtra apenas PERSON e ORG (alto valor, específicas)
    Evita GPE/LOC/MISC que são genéricas e poluem os filtros
    """
    nlp_model = get_nlp()
    if not nlp_model:
        return []
    
    doc = nlp_model(text or "")
    return [
        {"text": e.text, "label": e.label_}
        for e in doc.ents
        if e.label_ in ("ORG", "PERSON", "PER")  # PER para modelos PT, PERSON para EN
    ]

def normalize_entities(mentions: List[Dict], gaz: Dict) -> List[str]:
    """Normaliza menções para entity_ids"""
    if not mentions or not gaz:
        return []
    
    text_mentions = {m["text"].lower() for m in mentions}
    ids = []
    
    for eid, aliases in gaz.items():
        if any(a.lower() in text_mentions for a in aliases):
            ids.append(eid)
    
    return sorted(set(ids))


async def run_etl_on_passages(
    client,
    passage_uuids: List[str],
    tenant: str = None,
    collection_name: str = None
) -> Dict:
    """
    Executa ETL A2 inteligente em passages recém-criados
    NOVO: Multi-idioma, detecção automática de entidades
    
    Chamado via hook após import_document
    
    Args:
        client: Cliente Weaviate
        passage_uuids: Lista de UUIDs dos chunks
        tenant: Tenant (opcional)
        collection_name: Nome da collection de embedding (ex: VERBA_Embedding_all_MiniLM_L6_v2)
                        Se None, tenta detectar automaticamente
    
    Returns:
        {"patched": count, "total": total, "error": str or None}
        
    NOVO: Salva também `entity_mentions` com estrutura JSON:
        [{"text": "China", "label": "GPE", "confidence": 0.95}, ...]
    """
    # Tentar usar ETL inteligente
    etl = get_etl_module()
    if etl and "run_etl_patch_for_passage_uuids" in etl:
        try:
            msg.info(f"📊 Executando ETL inteligente (multi-idioma) em {len(passage_uuids)} chunks...")
            # ETL inteligente do ingestor
            from ingestor.etl_a2_intelligent import run_etl_patch_for_passage_uuids as run_etl_intelligent
            result = await run_etl_intelligent(
                lambda: client,
                passage_uuids,
                tenant,
                collection_name=collection_name  # Passar collection_name correto para qualquer modelo de embedding
            )
            msg.good(f"✅ ETL inteligente concluído: {result.get('patched', 0)} chunks processados")
            return result
        except Exception as e:
            msg.warn(f"⚠️ Erro no ETL inteligente: {str(e)}, usando fallback...")
    
    # Fallback para ETL legado
    try:
        from verba_extensions.compatibility.weaviate_imports import Filter, WEAVIATE_V4
        
        # Para v3, precisa usar API diferente
        coll = None
        if WEAVIATE_V4:
            if collection_name:
                try:
                    coll = client.collections.get(collection_name)
                except Exception as e:
                    msg.warn(f"Erro ao obter collection {collection_name}: {str(e)}")
            else:
                # Tenta detectar collection automaticamente (procura por VERBA_Embedding_*)
                try:
                    all_collections = await client.collections.list_all()
                    embedding_collections = [c for c in all_collections if "VERBA_Embedding" in c]
                    if embedding_collections:
                        # Usa a primeira collection de embedding encontrada
                        # (idealmente deveria receber o nome correto via parâmetro)
                        coll = client.collections.get(embedding_collections[0])
                        msg.info(f"[ETL] Usando collection detectada: {embedding_collections[0]}")
                    else:
                        msg.warn("Nenhuma collection VERBA_Embedding encontrada")
                except Exception as e:
                    msg.warn(f"Erro ao detectar collection automaticamente: {str(e)}")
        
        gaz = load_gazetteer()
        
        if not gaz:
            msg.warn("Gazetteer nao encontrado, ETL A2 nao executado")
            return {"patched": 0, "error": "gazetteer not found"}
        
        if not WEAVIATE_V4 or not coll:
            msg.warn("ETL A2 requer Weaviate v4 (collections API)")
            return {"patched": 0, "error": "ETL A2 requer Weaviate v4"}
        
        changed = 0
        
        # Busca objetos pelos UUIDs específicos
        try:
            # Busca objetos por UUID usando filtro "containsAny" para UUIDs
            # Weaviate v4 suporta buscar múltiplos UUIDs
            from weaviate.classes.query import Filter
            
            # Busca todos os objetos que correspondem aos UUIDs
            # Limita a busca ao número de UUIDs (mais eficiente)
            fetch_kwargs = {
                "limit": len(passage_uuids),
            }
            if tenant:
                fetch_kwargs["tenant"] = tenant
            
            # Busca todos e filtra pelos UUIDs desejados
            res = await coll.query.fetch_objects(**fetch_kwargs)
            objs = {str(o.uuid): o for o in res.objects if str(o.uuid) in passage_uuids}
            
            # Se não encontrou todos, avisa (mas continua)
            if len(objs) < len(passage_uuids):
                msg.warn(f"[ETL] Apenas {len(objs)}/{len(passage_uuids)} chunks encontrados na collection")
        except Exception as e:
            msg.warn(f"Erro ao buscar passages para ETL: {str(e)}")
            return {"patched": 0, "error": str(e)}
        
        for uid_str in passage_uuids:
            # Tenta encontrar objeto
            obj = None
            for o in objs.values():
                if str(o.uuid) == uid_str:
                    obj = o
                    break
            
            if not obj:
                continue
            
            try:
                p = obj.properties
                # Safely access properties that may not exist in the schema
                # Use .get() with default values to avoid errors
                text = p.get("text") or p.get("chunk_text") or ""
                sect_title = p.get("section_title") or ""
                first_para = p.get("section_first_para") or ""
                parent_ents = p.get("parent_entities") or []
                
                # If text is empty, skip this chunk (no content to process)
                if not text:
                    continue
                
                # NER + normalização
                mentions = extract_entities_nlp(text)
                local_ids = normalize_entities(mentions, gaz)
                
                # SectionScope
                sect_ids = []
                scope_conf = 0.0
                
                h_hits = match_aliases(sect_title, gaz)
                fp_hits = match_aliases(first_para, gaz)
                
                if h_hits:
                    sect_ids, scope_conf = h_hits, 0.9
                elif fp_hits:
                    sect_ids, scope_conf = fp_hits, 0.7
                elif parent_ents:
                    sect_ids, scope_conf = parent_ents, 0.6
                
                # Primary entity + focus
                primary = local_ids[0] if local_ids else (sect_ids[0] if sect_ids else None)
                focus = 1.0 if primary and primary in local_ids else (0.7 if primary else 0.0)
                
                # Patch
                props = {
                    "entities_local_ids": local_ids,
                    "section_entity_ids": sect_ids,
                    "section_scope_confidence": scope_conf,
                    "primary_entity_id": primary or "",
                    "entity_focus_score": focus,
                    "etl_version": "entity_scope_v1"
                }
                
                update_kwargs = {"uuid": obj.uuid, "properties": props}
                if tenant:
                    update_kwargs["tenant"] = tenant
                
                try:
                    await coll.data.update(**update_kwargs)
                    changed += 1
                    if changed % 100 == 0:
                        msg.info(f"[ETL] Progresso: {changed}/{len(passage_uuids)} chunks atualizados...")
                except Exception as update_error:
                    error_str = str(update_error).lower()
                    # Silently handle missing properties or schema mismatches
                    # These are expected if schema hasn't been updated yet
                    if any(keyword in error_str for keyword in [
                        "property", "schema", "field", "missing", "not found",
                        "does not exist", "unknown property"
                    ]):
                        # Schema mismatch - silently skip (not an error)
                        continue
                    # Log other errors but continue processing
                    if changed % 100 == 0:  # Only log periodically to avoid spam
                        msg.warn(f"[ETL] Erro ao atualizar chunk (pode ser schema mismatch): {str(update_error)[:100]}")
                    # Continua mesmo se falhar
                
            except Exception as e:
                msg.warn(f"Erro ao processar passage {uid_str}: {str(e)}")
                continue
        
        if changed > 0:
            msg.good(f"ETL A2: {changed} passages atualizados")
        
        return {"patched": changed, "total": len(passage_uuids)}
        
    except Exception as e:
        msg.warn(f"Erro no ETL A2: {str(e)}")
        return {"patched": 0, "error": str(e)}


def register_hooks():
    """
    Registra hooks para executar ETL após importação
    """
    from verba_extensions.hooks import global_hooks
    
    async def after_import_document(client, document_uuid, passage_uuids, **kwargs):
        """Hook executado após import_document"""
        # Verifica se ETL está habilitado (via doc_meta ou config)
        enable_etl = kwargs.get('enable_etl', True)
        
        if not enable_etl:
            return
        
        # Pega tenant se disponível
        tenant = kwargs.get('tenant', None)
        
        # Pega collection_name se disponível (nome da collection de embedding)
        collection_name = kwargs.get('collection_name', None)
        
        # Pega logger e file_id para notificação de conclusão
        logger = kwargs.get('logger', None)
        file_id = kwargs.get('file_id', None)
        
        # Roda ETL
        import asyncio
        start_time = asyncio.get_event_loop().time()
        result = await run_etl_on_passages(client, passage_uuids, tenant, collection_name)
        end_time = asyncio.get_event_loop().time()
        took = round(end_time - start_time, 2)
        
        # Envia notificação de conclusão se logger disponível e WebSocket conectado
        if logger is not None and file_id:
            try:
                from goldenverba.server.types import FileStatus
                patched_count = result.get('patched', 0) if result else 0
                total_count = result.get('total', len(passage_uuids)) if result else len(passage_uuids)
                
                if patched_count > 0:
                    await logger.send_report(
                        file_id,
                        status=FileStatus.INGESTING,  # Usa INGESTING para não sobrescrever DONE
                        message=f"ETL concluído: {patched_count}/{total_count} chunks processados",
                        took=took,
                    )
                    msg.info(f"[ETL] Notificação enviada: ETL concluído para {patched_count} chunks")
                else:
                    msg.info(f"[ETL] ETL concluído mas nenhum chunk foi atualizado (não enviando notificação)")
            except Exception as notify_error:
                # Não falha o ETL se notificação falhar
                msg.warn(f"[ETL] Erro ao enviar notificação de conclusão: {str(notify_error)}")
    
    # Registra hook (precisa ser chamado após o plugin ser carregado)
    global_hooks.register_hook('import.after', after_import_document, priority=100)
    
    return {
        'name': 'a2_etl_hook',
        'version': '1.0.0',
        'description': 'Hook para executar ETL A2 após importação',
        'hooks': ['import.after'],
        'compatible_verba_version': '>=2.1.0',
    }


def register():
    """
    Registra este plugin
    """
    return register_hooks()

