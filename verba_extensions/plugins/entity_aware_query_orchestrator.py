"""
Orquestrador de Query Entity-Aware
Extrai entidades da query e fornece para o EntityAwareRetriever
"""

import os
import re
from typing import Dict, List, Any
from wasabi import msg

# Lazy load
_nlp = None
_gazetteer = None

def load_gazetteer(path: str = None) -> Dict:
    """Carrega gazetteer"""
    global _gazetteer
    if _gazetteer is not None:
        return _gazetteer
    
    import json
    if path is None:
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
        msg.warn(f"spaCy não disponível para extração de entidades da query: {str(e)}")
        return None

def extract_entities_from_query(query: str) -> List[str]:
    """Extrai entity_ids da query usando SpaCy + Gazetteer
    
    Suporta:
    - Entidades nomeadas (ORG, PERSON, GPE, LOC): "Apple", "Spencer Stuart"
    - Múltiplas entidades: "apple e microsoft"
    - Retorna entity_ids apenas (não palavras-chave)
    
    Nota: Palavras-chave como "inovação" são ignoradas pelo filtro entity-aware.
          Para melhor resultado, combine com busca vetorial.
    """
    nlp_model = get_nlp()
    gaz = load_gazetteer()
    
    if not nlp_model or not gaz:
        return []
    
    try:
        doc = nlp_model(query)
        mentions = [
            e.text for e in doc.ents 
            if e.label_ in ("ORG", "PERSON", "GPE", "LOC")
        ]
        
        # Normaliza para entity_ids
        entity_ids = []
        query_lower = query.lower()
        
        for entity_id, aliases in gaz.items():
            for alias in aliases:
                alias_lower = alias.lower()
                # Verifica se alias está na query
                if alias_lower in query_lower or any(alias_lower in m.lower() for m in mentions):
                    if entity_id not in entity_ids:
                        entity_ids.append(entity_id)
                    break
        
        # Log para debug
        if entity_ids:
            msg.info(f"Entidades extraídas: {entity_ids}")
        
        return entity_ids
    except Exception as e:
        msg.warn(f"Erro ao extrair entidades da query: {str(e)}")
        return []

def register_hooks():
    """Registra hooks para fornecer entity_context ao retriever"""
    from verba_extensions.hooks import global_hooks
    
    async def get_entity_filters(query: str, **kwargs) -> Dict[str, Any]:
        """
        Hook chamado pelo EntityAwareRetriever para obter filtros
        Retorna entity_context com entity_ids extraídos da query
        """
        entity_ids = extract_entities_from_query(query)
        
        if not entity_ids:
            return None
        
        msg.info(f"Entidades detectadas na query '{query}': {len(entity_ids)} entidades")
        
        return {
            'entity_ids': entity_ids,
            'require_section_confidence': 0.7,  # Confiança mínima para filtrar por seção
        }
    
    # Registra hook
    global_hooks.register_hook('entity_aware.get_filters', get_entity_filters, priority=100)
    
    return {
        'name': 'entity_aware_query_orchestrator',
        'version': '1.0.0',
        'description': 'Orquestrador que extrai entidades de queries para EntityAwareRetriever',
        'hooks': ['entity_aware.get_filters'],
        'compatible_verba_version': '>=2.1.0',
    }

def register():
    """Registra plugin"""
    return register_hooks()

