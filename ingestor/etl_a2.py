"""ETL A2 - NER + Section Scope + Normalização"""

import os
import time
from typing import List, Callable, Dict
import spacy

# Modelo spaCy configurável
SPACY_MODEL = os.getenv("SPACY_MODEL", "pt_core_news_sm")
_nlp = None

def nlp():
    """Lazy load do modelo spaCy"""
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load(SPACY_MODEL)
        except OSError:
            print(f"⚠️ Modelo {SPACY_MODEL} não encontrado. Instale: python -m spacy download {SPACY_MODEL}")
            _nlp = None
    return _nlp

def load_gazetteer(path: str = "ingestor/resources/gazetteer.json") -> Dict:
    """Carrega gazetteer de entidades"""
    import json
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {item["entity_id"]: item["aliases"] for item in raw}
    except:
        return {}

def match_aliases(text: str, gaz: Dict) -> List[str]:
    """Encontra entity_ids que correspondem a aliases no texto"""
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

def _ner_mentions(text: str) -> List[Dict]:
    """Extrai entidades NER usando spaCy"""
    nlp_model = nlp()
    if not nlp_model:
        return []
    
    doc = nlp_model(text or "")
    return [
        {"text": e.text, "label": e.label_}
        for e in doc.ents
        if e.label_ in ("ORG", "PERSON", "GPE", "LOC")
    ]

def _normalize_mentions(mentions: List[Dict], gaz: Dict) -> List[str]:
    """Normaliza menções para entity_ids via gazetteer"""
    if not mentions or not gaz:
        return []
    
    text_mentions = {m["text"].lower() for m in mentions}
    ids = []
    
    for eid, aliases in gaz.items():
        if any(a.lower() in text_mentions for a in aliases):
            ids.append(eid)
    
    return sorted(set(ids))

async def run_etl_patch_for_passage_uuids(
    get_weaviate: Callable,
    uuids: List[str],
    tenant: str
) -> Dict:
    """Executa ETL A2 em uma lista de passage UUIDs"""
    client = get_weaviate()
    coll = client.collections.get("Passage")
    gaz = load_gazetteer()
    
    changed = 0
    
    # Busca objetos
    try:
        res = coll.query.fetch_objects(limit=len(uuids), tenant=tenant)
        objs = {o.uuid: o for o in res.objects if o.uuid in uuids}
    except Exception as e:
        print(f"Erro ao buscar passages: {str(e)}")
        return {"patched": 0, "error": str(e)}
    
    for uid in uuids:
        o = objs.get(uid)
        if not o:
            continue
        
        try:
            p = o.properties
            text = p.get("text") or ""
            sect_title = p.get("section_title") or ""
            first_para = p.get("section_first_para") or ""
            parent_ents = p.get("parent_entities") or []
            
            # NER + normalização
            mentions = _ner_mentions(text)
            local_ids = _normalize_mentions(mentions, gaz)
            
            # SectionScope (heading > first_para > parent)
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
            
            # Primary entity + focus score
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
            
            coll.data.update(uuid=uid, properties=props, tenant=tenant)
            changed += 1
            
            time.sleep(0.002)  # Rate limiting
            
        except Exception as e:
            print(f"Erro ao processar passage {uid}: {str(e)}")
            continue
    
    return {"patched": changed, "total": len(uuids)}

