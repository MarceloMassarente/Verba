"""
Hook: ETL Pré-Chunking - Extrai entidades ANTES do chunking
Permite chunking entity-aware que evita cortar entidades no meio

⚠️ PATCH/MONKEY PATCH - Documentado em verba_extensions/patches/README_PATCHES.md
   
Este é um patch que modifica o comportamento do Verba core sem alterar código original.
Ao atualizar Verba, verificar compatibilidade e reaplicar se necessário.

Integrado em: goldenverba/verba_manager.py (linha ~241)
"""

import os
from typing import List, Dict
from wasabi import msg

def extract_entities_pre_chunking(document) -> Dict:
    """
    Extrai entidades do documento completo ANTES do chunking
    
    Retorna:
    {
        "entities": [{"text": "Apple", "label": "ORG", "start": 0, "end": 5}],
        "entity_ids": ["Q312"],
        "entity_spans": [(0, 5, "Apple", "ORG")]
    }
    """
    try:
        from verba_extensions.plugins.a2_etl_hook import (
            extract_entities_nlp,
            normalize_entities,
            load_gazetteer,
            get_nlp
        )
        
        text = document.content if hasattr(document, 'content') else ""
        if not text:
            return {"entities": [], "entity_ids": [], "entity_spans": []}
        
        # Extrai entidades via spaCy
        mentions = extract_entities_nlp(text)
        if not mentions:
            return {"entities": [], "entity_ids": [], "entity_spans": []}
        
        # Normaliza para entity_ids via gazetteer
        gaz = load_gazetteer()
        entity_ids = normalize_entities(mentions, gaz)
        
        # Extrai spans (posições) para o chunker usar
        nlp_model = get_nlp()
        entity_spans = []
        seen_spans = set()  # Deduplica entidades por posição para evitar O(n) complexity
        
        if nlp_model:
            doc = nlp_model(text)
            for ent in doc.ents:
                # Filtra por tipo relevante (ORG, PERSON são mais críticos para entity-aware)
                # Excluir GPE/LOC para reduzir de 370 para ~50 entidades
                if ent.label_ in ("ORG", "PERSON"):
                    # Deduplica por span de caracteres (evita múltiplas ocorrências da mesma entidade)
                    span_key = (ent.start_char, ent.end_char, ent.text.lower())
                    if span_key not in seen_spans:
                        seen_spans.add(span_key)
                        entity_spans.append({
                            "text": ent.text,
                            "start": ent.start_char,
                            "end": ent.end_char,
                            "label": ent.label_,
                            "entity_id": None  # Será preenchido depois se normalizado
                        })
        
        # Mapeia spans para entity_ids quando possível
        for span in entity_spans:
            text_lower = span["text"].lower()
            for eid, aliases in gaz.items():
                if any(alias.lower() == text_lower for alias in aliases):
                    span["entity_id"] = eid
                    break
        
        msg.info(f"[ETL-PRE] Extraídas {len(mentions)} entidades do documento completo")
        if entity_ids:
            msg.info(f"[ETL-PRE] {len(entity_ids)} entidades normalizadas: {entity_ids[:5]}...")
        
        return {
            "entities": mentions,
            "entity_ids": entity_ids,
            "entity_spans": entity_spans
        }
        
    except Exception as e:
        msg.warn(f"[ETL-PRE] Erro ao extrair entidades pré-chunking (não crítico): {str(e)}")
        return {"entities": [], "entity_ids": [], "entity_spans": []}


def apply_etl_pre_chunking(document, enable_etl: bool = True):
    """
    Aplica ETL pré-chunking ao documento
    
    Armazena entidades em document.meta para chunker usar
    """
    if not enable_etl:
        return document
    
    # Verifica se já tem entidades (evita reprocessar)
    if hasattr(document, 'meta') and document.meta and document.meta.get("entities_pre_chunking"):
        msg.info(f"[ETL-PRE] Documento já tem entidades pré-extraídas, reutilizando")
        return document
    
    # Extrai entidades
    etl_data = extract_entities_pre_chunking(document)
    
    # Armazena no documento
    if not hasattr(document, 'meta') or document.meta is None:
        document.meta = {}
    
    document.meta["entities_pre_chunking"] = True
    document.meta["entities"] = etl_data["entities"]
    document.meta["entity_ids"] = etl_data["entity_ids"]
    document.meta["entity_spans"] = etl_data["entity_spans"]
    
    msg.good(f"[ETL-PRE] ✅ Entidades armazenadas no documento: {len(etl_data['entity_spans'])} spans")
    
    return document

