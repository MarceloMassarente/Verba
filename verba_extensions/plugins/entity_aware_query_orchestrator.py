"""
Orquestrador de Query Entity-Aware
Extrai entidades da query e fornece para o EntityAwareRetriever
"""

import os
import re
from typing import Dict, List, Any
from wasabi import msg

# Lazy load - cache de modelos por idioma
_nlp_models = {}  # {"pt": nlp_pt, "en": nlp_en}
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

def detect_query_language(query: str) -> str:
    """Detecta idioma da query (pt, en, etc.)"""
    try:
        from langdetect import detect
        lang = detect(query)
        # Normalizar códigos de idioma
        if lang in ["pt", "pt-BR", "pt-PT"]:
            return "pt"
        elif lang in ["en", "en-US", "en-GB"]:
            return "en"
        return lang
    except:
        # Fallback: heurística simples
        # Contar palavras comuns em português vs inglês
        query_lower = query.lower()
        pt_words = ["de", "da", "do", "em", "para", "com", "que", "não", "é", "são"]
        en_words = ["the", "of", "to", "in", "for", "with", "that", "not", "is", "are"]
        pt_count = sum(1 for word in pt_words if word in query_lower)
        en_count = sum(1 for word in en_words if word in query_lower)
        if pt_count > en_count:
            return "pt"
        elif en_count > pt_count:
            return "en"
        return "pt"  # Default para português

def get_nlp(language: str = None):
    """Lazy load spaCy com suporte multi-idioma
    
    Args:
        language: Código do idioma ("pt", "en"). Se None, usa default ou detecta.
    
    Returns:
        Modelo spaCy apropriado ou None se não disponível
    """
    global _nlp_models
    
    # Se language não fornecido, tentar usar default da env var
    if language is None:
        model_name = os.getenv("SPACY_MODEL", "pt_core_news_sm")
        # Inferir idioma do nome do modelo
        if "pt_core" in model_name or "pt" in model_name:
            language = "pt"
        elif "en_core" in model_name or "en" in model_name:
            language = "en"
        else:
            language = "pt"  # Default
    
    # Retornar modelo já carregado
    if language in _nlp_models:
        return _nlp_models[language]
    
    # Mapear idioma para modelo spaCy
    model_map = {
        "pt": "pt_core_news_sm",
        "en": "en_core_web_sm",
    }
    
    model_name = model_map.get(language, "pt_core_news_sm")
    
    try:
        import spacy
        msg.info(f"  Carregando modelo spaCy: {model_name} (idioma: {language})")
        nlp = spacy.load(model_name)
        _nlp_models[language] = nlp
        return nlp
    except OSError as e:
        msg.warn(f"  ⚠️ Modelo spaCy '{model_name}' não encontrado para idioma '{language}'")
        msg.warn(f"  💡 Instale: python -m spacy download {model_name}")
        # Tentar fallback para português se não for pt
        if language != "pt" and "pt" in model_map:
            try:
                fallback_model = model_map["pt"]
                msg.info(f"  Tentando fallback: {fallback_model}")
                nlp = spacy.load(fallback_model)
                _nlp_models["pt"] = nlp
                return nlp
            except:
                pass
        return None
    except Exception as e:
        msg.warn(f"  ⚠️ Erro ao carregar spaCy: {str(e)}")
        return None

def extract_entities_from_query(query: str, use_gazetteer: bool = False) -> List[str]:
    """Extrai entidades da QUERY usando SpaCy (inteligente, sem gazetteer obrigatório)
    
    ⚠️ IMPORTANTE: Esta função é APENAS para queries (textos curtos do usuário).
    NÃO é usada para processar chunks durante o ETL. Os chunks usam extract_entities_intelligent()
    que tem filtros e limites diferentes.
    
    NOVO: Modo inteligente que detecta entidades automaticamente sem precisar de gazetteer.
    Retorna as menções de texto diretamente para fazer match com conteúdo dos chunks.
    
    LIMITES DE SEGURANÇA:
    - Máximo 5 entidades por query (evita filtros muito restritivos)
    - Prioriza PERSON/ORG sobre GPE/LOC
    - Heurística de fallback apenas para queries curtas (< 50 palavras)
    - Máximo 3 entidades por heurística
    
    Suporta:
    - Entidades nomeadas (ORG, PERSON, GPE, LOC): "Apple", "China", "São Paulo"
    - Múltiplas entidades: "apple e microsoft"
    - Detecção automática de idioma (pt/en) e uso do modelo spaCy apropriado
    - Modo inteligente: retorna menções de texto (não precisa de gazetteer)
    - Modo gazetteer (opcional): retorna entity_ids se gazetteer disponível
    
    Args:
        query: Query do usuário (texto curto, não chunk completo)
        use_gazetteer: Se True, tenta mapear para entity_ids via gazetteer (modo legado)
    
    Returns:
        Lista de entidades detectadas:
        - Modo inteligente (use_gazetteer=False): retorna menções de texto ["China", "Apple"]
        - Modo gazetteer (use_gazetteer=True): retorna entity_ids ["ent:loc:china", "ent:org:apple"]
    """
    # Detectar idioma da query
    query_language = detect_query_language(query)
    msg.info(f"  🌐 Idioma da query detectado: {query_language.upper()}")
    
    # Carregar modelo spaCy apropriado para o idioma
    nlp_model = get_nlp(language=query_language)
    
    if not nlp_model:
        msg.warn(f"  ⚠️ spaCy não disponível para extração de entidades (idioma: {query_language})")
        return []
    
    try:
        doc = nlp_model(query)
        
        # IMPORTANTE: Para queries, priorizar entidades de alto valor (PERSON, ORG)
        # GPE/LOC só são incluídas se não houver PERSON/ORG (evitar poluição)
        # Isso mantém filtros precisos e evita explosão de entidades
        
        # Primeiro: buscar apenas PERSON e ORG (alto valor, específicas)
        high_value_mentions = [
            {"text": e.text, "label": e.label_} for e in doc.ents 
            if e.label_ in ("ORG", "PERSON", "PER")
        ]
        
        # Se não encontrou PERSON/ORG, então incluir GPE/LOC (útil para queries geográficas)
        if high_value_mentions:
            mentions = high_value_mentions
        else:
            # Incluir GPE/LOC apenas se não há PERSON/ORG
            mentions = [
                {"text": e.text, "label": e.label_} for e in doc.ents 
                if e.label_ in ("GPE", "LOC")
            ]
        
        # Log detalhado das menções detectadas pelo spaCy
        if mentions:
            msg.info(f"  🔍 Menções detectadas pelo spaCy: {[m['text'] for m in mentions]} (labels: {[m['label'] for m in mentions]})")
        else:
            msg.info(f"  ⚠️ Nenhuma menção detectada pelo spaCy na query: '{query}'")
            # Heurística de fallback APENAS para queries curtas (< 50 palavras)
            # e apenas se não há menções do spaCy (evitar falsos positivos)
            query_words = query.split()
            if len(query_words) < 50:  # Apenas queries curtas
                capitalized_words = [w for w in query_words if w and w[0].isupper() and len(w) > 2]
                if capitalized_words:
                    msg.info(f"  💡 Tentando heurística (query curta): palavras capitalizadas encontradas: {capitalized_words}")
                    # Filtrar palavras comuns que não são entidades
                    common_words = {"O", "A", "Os", "As", "De", "Da", "Do", "Das", "Dos", "Em", "No", "Na", "Nos", "Nas", "Para", "Por", "Com", "Sem", "Sobre", "Como", "Que", "Qual", "Onde", "Quando", "The", "A", "An", "Of", "In", "On", "At", "To", "For", "With", "From"}
                    potential_entities = [w for w in capitalized_words if w not in common_words]
                    # LIMITE: máximo 3 entidades por heurística (evitar explosão)
                    if potential_entities:
                        potential_entities = potential_entities[:3]
                        msg.info(f"  💡 Possíveis entidades (heurística, limitado a 3): {potential_entities}")
                        # Retornar como menções se não há menções do spaCy
                        mentions = [{"text": e, "label": "UNKNOWN"} for e in potential_entities]
        
        if not mentions:
            return []
        
        # LIMITE DE SEGURANÇA: máximo 5 entidades por query (evitar filtros muito restritivos)
        if len(mentions) > 5:
            # Priorizar PERSON/ORG sobre GPE/LOC
            priority_mentions = [m for m in mentions if m["label"] in ("ORG", "PERSON", "PER")]
            if priority_mentions:
                mentions = priority_mentions[:5]
            else:
                mentions = mentions[:5]
            msg.info(f"  ⚠️ Limite de 5 entidades aplicado (havia {len(mentions)}), priorizando PERSON/ORG")
        
        # MODO INTELIGENTE (padrão): Retornar menções de texto diretamente
        # Isso permite fazer match com conteúdo dos chunks sem precisar de gazetteer
        if not use_gazetteer:
            entity_texts = [m["text"] for m in mentions]
            msg.info(f"  ✅ Modo inteligente: {len(entity_texts)} entidades detectadas automaticamente: {entity_texts}")
            return entity_texts
        
        # MODO GAZETTEER (opcional, legado): Tentar mapear para entity_ids
        gaz = load_gazetteer()
        if not gaz:
            msg.warn("  ⚠️ Gazetteer não disponível - usando modo inteligente (menções de texto)")
            return [m["text"] for m in mentions]
        
        # Normaliza para entity_ids usando gazetteer
        entity_ids = []
        query_lower = query.lower()
        mention_texts_lower = [m["text"].lower() for m in mentions]
        
        for entity_id, aliases in gaz.items():
            matched = False
            matched_alias = None
            
            for alias in aliases:
                alias_lower = alias.lower()
                alias_words = alias_lower.split()
                
                # Verifica match exato ou parcial
                if alias_lower in query_lower:
                    matched = True
                    matched_alias = alias
                    break
                
                # Verifica se alias está em alguma menção
                if any(alias_lower in m for m in mention_texts_lower):
                    matched = True
                    matched_alias = alias
                    break
                
                # Busca parcial: verifica se palavras-chave do alias estão na query
                if len(alias_words) > 1:
                    words_in_query = sum(1 for word in alias_words if word in query_lower)
                    if words_in_query >= min(2, len(alias_words)):
                        matched = True
                        matched_alias = alias
                        break
            
            if matched:
                if entity_id not in entity_ids:
                    entity_ids.append(entity_id)
                    msg.info(f"  ✅ Entidade mapeada: '{matched_alias}' → {entity_id}")
        
        # Log final
        if entity_ids:
            msg.info(f"  ✅ Entidades extraídas via gazetteer ({len(entity_ids)}): {entity_ids}")
        else:
            if mentions:
                msg.warn(f"  ⚠️ Menções detectadas mas não encontradas no gazetteer: {[m['text'] for m in mentions]}")
                msg.info(f"  💡 Usando modo inteligente: retornando menções de texto diretamente")
                return [m["text"] for m in mentions]
            else:
                msg.info(f"  ℹ️ Nenhuma entidade detectada na query")
        
        return entity_ids
    except Exception as e:
        msg.warn(f"Erro ao extrair entidades da query: {str(e)}")
        import traceback
        msg.info(f"Traceback: {traceback.format_exc()}")
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

