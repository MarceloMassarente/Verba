"""
ETL A2 Inteligente - Multi-idioma, detecção automática de entidades
Detecta entidades sem depender de gazetteer, adaptável ao idioma do chunk
"""

import os
import time
import json
from typing import List, Callable, Dict, Optional

# Cache de modelos spaCy por idioma
_nlp_models = {}

def detect_text_language(text: str) -> str:
    """Detecta idioma do texto (pt, en, etc.)"""
    try:
        from langdetect import detect
        lang = detect(text)
        if lang in ["pt", "pt-BR", "pt-PT"]:
            return "pt"
        elif lang in ["en", "en-US", "en-GB"]:
            return "en"
        return lang
    except:
        # Fallback: heurística simples
        text_lower = text.lower()
        pt_words = ["de", "da", "do", "em", "para", "com", "que", "não", "é", "são"]
        en_words = ["the", "of", "to", "in", "for", "with", "that", "not", "is", "are"]
        pt_count = sum(1 for word in pt_words if word in text_lower)
        en_count = sum(1 for word in en_words if word in text_lower)
        return "pt" if pt_count > en_count else ("en" if en_count > pt_count else "pt")

def get_nlp_for_language(language: str):
    """Carrega modelo spaCy apropriado para o idioma"""
    global _nlp_models
    
    if language in _nlp_models:
        return _nlp_models[language]
    
    model_map = {
        "pt": "pt_core_news_sm",
        "en": "en_core_web_sm",
    }
    
    model_name = model_map.get(language, "pt_core_news_sm")
    
    try:
        import spacy
        nlp = spacy.load(model_name)
        _nlp_models[language] = nlp
        return nlp
    except OSError:
        print(f"⚠️ Modelo {model_name} não encontrado para idioma {language}")
        # Tentar fallback para português
        if language != "pt":
            try:
                nlp = spacy.load("pt_core_news_sm")
                _nlp_models["pt"] = nlp
                return nlp
            except:
                pass
        return None
    except Exception as e:
        print(f"⚠️ Erro ao carregar spaCy: {str(e)}")
        return None

def load_gazetteer(path: str = "ingestor/resources/gazetteer.json") -> Dict:
    """Carrega gazetteer de entidades (opcional)"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {item["entity_id"]: item["aliases"] for item in raw}
    except:
        return {}

def extract_entities_intelligent(text: str) -> List[Dict]:
    """
    Detecta entidades de forma inteligente, adaptável ao idioma do texto
    Retorna lista de {text, label, confidence} sem depender de gazetteer
    
    Returns:
        [{"text": "China", "label": "GPE", "confidence": 0.95}, ...]
    """
    if not text or len(text.strip()) < 10:
        return []
    
    # Detectar idioma do texto
    language = detect_text_language(text)
    
    # Carregar modelo spaCy apropriado
    nlp_model = get_nlp_for_language(language)
    if not nlp_model:
        return []
    
    try:
        doc = nlp_model(text)
        entities = [
            {
                "text": e.text,
                "label": e.label_,
                "confidence": 0.95  # spaCy confidence is not directly available, use default
            }
            for e in doc.ents
            if e.label_ in ("ORG", "PERSON", "GPE", "LOC")
        ]
        return entities
    except Exception as e:
        print(f"Erro ao extrair entidades: {str(e)}")
        return []

def extract_entities_with_gazetteer(text: str, gaz: Dict) -> List[str]:
    """
    Detecta entidades e mapeia para entity_ids via gazetteer (modo legado)
    Retorna lista de entity_ids
    """
    if not text or not gaz:
        return []
    
    # Detectar idioma
    language = detect_text_language(text)
    
    # Extrair menções
    mentions = extract_entities_intelligent(text)
    if not mentions:
        return []
    
    # Mapear para entity_ids
    entity_ids = []
    text_lower = text.lower()
    
    for entity_id, aliases in gaz.items():
        matched = False
        for alias in aliases:
            alias_lower = alias.lower()
            # Match exato ou via menções
            if alias_lower in text_lower or any(alias_lower in m["text"].lower() for m in mentions):
                entity_ids.append(entity_id)
                matched = True
                break
        
        if matched:
            continue
    
    return sorted(set(entity_ids))

def match_aliases(text: str, gaz: Dict) -> List[str]:
    """Compatibilidade: encontra entity_ids que correspondem a aliases"""
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

def _normalize_mentions(mentions: List[Dict], gaz: Dict) -> List[str]:
    """Compatibilidade: normaliza menções para entity_ids"""
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
    """
    Executa ETL A2 inteligente em uma lista de passage UUIDs
    
    NOVO: Detecta entidades de forma automática e inteligente:
    - Multi-idioma (detecta PT/EN automaticamente)
    - Sem gazetteer obrigatório (usa modo inteligente)
    - Salva entidades em `entity_mentions` com estrutura {text, label, confidence}
    - Mantém compatibilidade com gazetteer se existir (salva também `entities_local_ids`)
    """
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
            
            # NOVO: Extração inteligente de entidades (sem gazetteer obrigatório)
            entity_mentions = extract_entities_intelligent(text)
            
            # Modo legado: tentar mapear para entity_ids se gazetteer disponível
            local_ids = []
            if gaz:
                local_ids = extract_entities_with_gazetteer(text, gaz)
            
            # SectionScope (heading > first_para > parent)
            sect_ids = []
            scope_conf = 0.0
            
            if gaz:
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
            
            # Prepara properties para salvar
            props = {
                # NOVO: Salvar menções inteligentes
                "entity_mentions": json.dumps(entity_mentions) if entity_mentions else "[]",
                # Modo legado: entity_ids se gazetteer disponível
                "entities_local_ids": local_ids,
                "section_entity_ids": sect_ids,
                "section_scope_confidence": scope_conf,
                "primary_entity_id": primary or "",
                "entity_focus_score": focus,
                "etl_version": "entity_scope_intelligent_v2"
            }
            
            coll.data.update(uuid=uid, properties=props, tenant=tenant)
            changed += 1
            
            time.sleep(0.002)  # Rate limiting
            
        except Exception as e:
            print(f"Erro ao processar passage {uid}: {str(e)}")
            continue
    
    return {"patched": changed, "total": len(uuids)}

# Compatibilidade com código antigo
async def run_etl_patch_for_passage_uuids_legacy(*args, **kwargs):
    """Compatibilidade com versão anterior"""
    return await run_etl_patch_for_passage_uuids(*args, **kwargs)

