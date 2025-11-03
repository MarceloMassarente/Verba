"""
Hook ETL A2 - Executa ETL após importação no Verba
Integrado no fluxo normal do Verba via hooks
"""

import os
from typing import List, Dict, Any, Callable
from wasabi import msg

# Importações do ETL (lazy para não quebrar se não tiver spacy)
_nlp = None
_gazetteer = None

def load_gazetteer(path: str = None) -> Dict:
    """Carrega gazetteer"""
    global _gazetteer
    if _gazetteer is not None:
        return _gazetteer
    
    import json
    if path is None:
        # Tenta vários caminhos possíveis
        possible_paths = [
            "ingestor/resources/gazetteer.json",
            "verba_extensions/resources/gazetteer.json",
            "resources/gazetteer.json",
        ]
        for p in possible_paths:
            if os.path.exists(p):
                path = p
                break
    
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            _gazetteer = {item["entity_id"]: item["aliases"] for item in raw}
            return _gazetteer
        except:
            pass
    
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
    """Extrai entidades via spaCy NER"""
    nlp_model = get_nlp()
    if not nlp_model:
        return []
    
    doc = nlp_model(text or "")
    return [
        {"text": e.text, "label": e.label_}
        for e in doc.ents
        if e.label_ in ("ORG", "PERSON", "GPE", "LOC")
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
    tenant: str = None
) -> Dict:
    """
    Executa ETL A2 em passages recém-criados
    Chamado via hook após import_document
    """
    try:
        from verba_extensions.compatibility.weaviate_imports import Filter, WEAVIATE_V4
        
        # Para v3, precisa usar API diferente
        coll = None
        if WEAVIATE_V4:
            try:
                coll = client.collections.get("Passage")
            except:
                pass
        
        gaz = load_gazetteer()
        
        if not gaz:
            msg.warn("Gazetteer nao encontrado, ETL A2 nao executado")
            return {"patched": 0, "error": "gazetteer not found"}
        
        if not WEAVIATE_V4 or not coll:
            msg.warn("ETL A2 requer Weaviate v4 (collections API)")
            return {"patched": 0, "error": "ETL A2 requer Weaviate v4"}
        
        changed = 0
        
        # Busca objetos
        try:
            # Se tenant disponível, usa
            fetch_kwargs = {"limit": len(passage_uuids)}
            if tenant:
                fetch_kwargs["tenant"] = tenant
            
            res = coll.query.fetch_objects(**fetch_kwargs)
            objs = {o.uuid: o for o in res.objects if str(o.uuid) in passage_uuids}
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
                text = p.get("text") or ""
                sect_title = p.get("section_title") or ""
                first_para = p.get("section_first_para") or ""
                parent_ents = p.get("parent_entities") or []
                
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
                
                coll.data.update(**update_kwargs)
                changed += 1
                
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
        
        # Roda ETL
        await run_etl_on_passages(client, passage_uuids, tenant)
    
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

