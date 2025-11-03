"""
Query Parser: Separa entidades de conceitos semânticos em queries

Estratégia Híbrida:
1. POS Tagging (Part-of-Speech) + NER (Named Entity Recognition)
2. Dependency Parsing para entender estrutura
3. Intent Classification
4. Gazetteer Fuzzy Matching
"""

from typing import Dict, List, Any, Optional
from wasabi import msg

# Lazy load
_nlp = None
_gazetteer = None


def get_nlp():
    """Lazy load spaCy"""
    global _nlp
    if _nlp is not None:
        return _nlp
    
    try:
        import spacy
        try:
            _nlp = spacy.load("pt_core_news_sm")
        except OSError:
            msg.warn("spaCy model not found, NLP parsing disabled")
            return None
        return _nlp
    except:
        return None


def load_gazetteer(path: str = None) -> Dict:
    """Carrega gazetteer"""
    global _gazetteer
    if _gazetteer is not None:
        return _gazetteer
    
    import json
    import os
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


def classify_token(token) -> str:
    """Classifica um token em: ENTITY, SEMANTIC, CONNECTOR, OTHER"""
    
    # 1. NER labels
    if token.ent_type_ in ["ORG", "PERSON", "GPE", "LOC"]:
        return "ENTITY"
    
    # 2. Proper nouns (mesmo sem NER)
    if token.pos_ == "PROPN":
        return "ENTITY"
    
    # 3. Conceitos semânticos (substantivos e adjetivos)
    if token.pos_ in ["NOUN", "ADJ"]:
        return "SEMANTIC"
    
    # 4. Conectores
    if token.pos_ in ["CCONJ", "ADP", "DET", "AUX"]:
        return "CONNECTOR"
    
    return "OTHER"


def classify_query_intent(query: str) -> str:
    """Classifica a intenção da query"""
    
    query_lower = query.lower()
    
    # Comparação
    if any(word in query_lower for word in ["vs", "versus", "diferença", "comparação", "contra"]):
        return "COMPARISON"
    
    # Combinação (AND)
    if any(word in query_lower for word in [" e ", " com ", " ambos", " juntos"]):
        return "COMBINATION"
    
    # Pergunta
    if any(word in query_lower for word in ["qual", "o que", "como", "por que", "quem", "onde"]):
        return "QUESTION"
    
    # Busca geral
    return "GENERAL_SEARCH"


def parse_query(query: str) -> Dict[str, Any]:
    """
    Faz parsing completo da query separando entidades de conceitos semânticos
    
    Retorna:
    {
        "original_query": str,
        "entities": [{"text": str, "entity_id": Optional[str], "confidence": float}],
        "semantic_concepts": [str],
        "intent": str,  # ENTITY, SEMANTIC, COMPARISON, COMBINATION, QUESTION, GENERAL
        "tokens": [{"text": str, "pos": str, "ent_type": str, "classification": str}]
    }
    """
    
    nlp = get_nlp()
    if not nlp:
        # Fallback: sem NLP, trata tudo como semântico
        return {
            "original_query": query,
            "entities": [],
            "semantic_concepts": [query],
            "intent": "GENERAL_SEARCH",
            "tokens": [],
            "error": "NLP not available"
        }
    
    try:
        doc = nlp(query)
        
        result = {
            "original_query": query,
            "entities": [],
            "semantic_concepts": [],
            "intent": classify_query_intent(query),
            "tokens": [],
            "error": None
        }
        
        # Processa cada token
        for token in doc:
            classification = classify_token(token)
            
            token_info = {
                "text": token.text,
                "pos": token.pos_,
                "ent_type": token.ent_type_,
                "dep": token.dep_,
                "classification": classification
            }
            
            result["tokens"].append(token_info)
            
            # Classifica e agrupa
            if classification == "ENTITY":
                entity_id = _lookup_entity_in_gazetteer(token.text)
                result["entities"].append({
                    "text": token.text,
                    "entity_id": entity_id,
                    "confidence": 0.95 if entity_id else 0.80,
                    "source": "NER"
                })
            
            elif classification == "SEMANTIC" and token.text.lower() not in ["que", "como", "qual"]:
                # Evita palavras muito genéricas
                result["semantic_concepts"].append(token.text.lower())
        
        # Remove duplicatas em semantic_concepts
        result["semantic_concepts"] = list(set(result["semantic_concepts"]))
        
        return result
    
    except Exception as e:
        msg.warn(f"Erro ao fazer parsing da query: {str(e)}")
        return {
            "original_query": query,
            "entities": [],
            "semantic_concepts": [query],
            "intent": "GENERAL_SEARCH",
            "tokens": [],
            "error": str(e)
        }


def _lookup_entity_in_gazetteer(text: str) -> Optional[str]:
    """Procura um texto no gazetteer"""
    
    gaz = load_gazetteer()
    text_lower = text.lower()
    
    for entity_id, aliases in gaz.items():
        for alias in aliases:
            if alias.lower() == text_lower:
                return entity_id
    
    return None


def format_query_for_display(parsed_query: Dict[str, Any]) -> str:
    """Formata resultado do parsing para exibição"""
    
    lines = [
        f"Query Original: {parsed_query['original_query']}",
        f"Intent: {parsed_query['intent']}",
    ]
    
    if parsed_query["entities"]:
        lines.append(f"Entidades: {', '.join([e['text'] for e in parsed_query['entities']])}")
    
    if parsed_query["semantic_concepts"]:
        lines.append(f"Conceitos: {', '.join(parsed_query['semantic_concepts'])}")
    
    return "\n".join(lines)


# Exemplo de uso/testes
if __name__ == "__main__":
    test_queries = [
        "Apple",
        "inovação",
        "Apple e inovação",
        "Apple vs Microsoft",
        "qual é a estratégia de inovação da Apple?",
        "empresas de tecnologia em São Paulo",
    ]
    
    for query in test_queries:
        parsed = parse_query(query)
        print(f"\n{format_query_for_display(parsed)}")
        print("-" * 60)
