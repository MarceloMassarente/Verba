"""
ETL A2 Inteligente - Multi-idioma, detecção automática de entidades
Detecta entidades sem depender de gazetteer, adaptável ao idioma do chunk
"""

import os
import re
import time
import json
from typing import List, Callable, Dict, Optional, Set


# Labels de entidades considerados relevantes para entity-aware retrieval
PRIMARY_ENTITY_LABELS = {"ORG", "PERSON", "PER", "GPE", "LOC"}
# Alguns modelos classificam empresas ou produtos como FAC/PRODUCT/EVENT – manter numa lista separada
SECONDARY_ENTITY_LABELS = {"FAC", "PRODUCT", "EVENT"}
ALLOWED_ENTITY_LABELS = PRIMARY_ENTITY_LABELS | SECONDARY_ENTITY_LABELS

# Cache de modelos spaCy por idioma
_nlp_models = {}

def detect_text_language(text: str) -> str:
    """
    Detecta idioma do texto com suporte a code-switching (PT+EN)
    
    Returns:
        "pt", "en", "pt-en", ou "en-pt"
    """
    try:
        # Tentar detector de code-switching primeiro (melhor para textos corporativos)
        from verba_extensions.utils.code_switching_detector import get_detector
        detector = get_detector()
        language_code, stats = detector.detect_language_mix(text)
        return language_code
    except Exception:
        # Fallback 1: langdetect (sem code-switching)
        try:
            from langdetect import detect
            lang = detect(text)
            if lang in ["pt", "pt-BR", "pt-PT"]:
                return "pt"
            elif lang in ["en", "en-US", "en-GB"]:
                return "en"
            return lang
        except:
            # Fallback 2: heurística simples
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
    ⭐ NOVO: Suporta code-switching (PT+EN) com NER bilíngue
    
    Retorna lista de {text, label, confidence} sem depender de gazetteer
    
    Returns:
        [{"text": "Apple", "label": "ORG", "confidence": 0.95}, ...]
    """
    if not text or len(text.strip()) < 10:
        return []
    
    # Detectar idioma do texto (pode retornar "pt-en" ou "en-pt")
    language = detect_text_language(text)
    
    # Verificar se é code-switching (bilíngue)
    try:
        from verba_extensions.utils.code_switching_detector import get_detector
        detector = get_detector()
        is_bilingual = detector.is_bilingual(language)
        
        if is_bilingual:
            # MODO BILÍNGUE: Usar NER de ambos idiomas e combinar resultados
            languages = detector.get_language_list(language)
            all_entities = []
            seen_spans = set()  # Evitar duplicatas
            
            for lang in languages:
                nlp_model = get_nlp_for_language(lang)
                if not nlp_model:
                    continue
                
                try:
                    doc = nlp_model(text)
                    for e in doc.ents:
                        # Filtrar apenas labels relevantes (inclui LOC/GPE por causa de falsos-positivos do spaCy-PT)
                        if e.label_ not in ALLOWED_ENTITY_LABELS:
                            continue
                        
                        # Evitar duplicatas por span (start, end, text)
                        span_key = (e.start_char, e.end_char, e.text)
                        if span_key in seen_spans:
                            continue
                        seen_spans.add(span_key)
                        
                        all_entities.append({
                            "text": e.text,
                            "label": e.label_,
                            "confidence": 0.95
                        })
                except Exception as e:
                    print(f"⚠️ Erro ao extrair entidades com modelo {lang}: {str(e)}")
                    continue
            
            return all_entities
        
        else:
            # MODO MONOLÍNGUE: Usar apenas 1 modelo NER
            nlp_model = get_nlp_for_language(language)
            if not nlp_model:
                return []
            
            try:
                doc = nlp_model(text)
                entities = [
                    {
                        "text": e.text,
                        "label": e.label_,
                        "confidence": 0.95
                    }
                    for e in doc.ents
                    if e.label_ in ALLOWED_ENTITY_LABELS  # Filtrar apenas labels com alto sinal empresarial
                ]
                return entities
            except Exception as e:
                print(f"Erro ao extrair entidades: {str(e)}")
                return []
    
    except Exception:
        # Fallback: modo monolíngue simples
        nlp_model = get_nlp_for_language(language if language in ["pt", "en"] else "pt")
        if not nlp_model:
            return []
        
        try:
            doc = nlp_model(text)
            entities = [
                {
                    "text": e.text,
                    "label": e.label_,
                    "confidence": 0.95
                }
                for e in doc.ents
                if e.label_ in ALLOWED_ENTITY_LABELS
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
    tenant: str,
    collection_name: Optional[str] = None
) -> Dict:
    """
    Executa ETL A2 inteligente em uma lista de passage UUIDs
    
    NOVO: Detecta entidades de forma automática e inteligente:
    - Multi-idioma (detecta PT/EN automaticamente)
    - Sem gazetteer obrigatório (usa modo inteligente)
    - Salva entidades em `entity_mentions` com estrutura {text, label, confidence}
    - Mantém compatibilidade com gazetteer se existir (salva também `entities_local_ids`)
    
    Args:
        get_weaviate: Função que retorna cliente Weaviate
        uuids: Lista de UUIDs dos chunks
        tenant: Tenant do Weaviate
        collection_name: Nome da collection (opcional, tenta detectar se não fornecido)
    """
    client = get_weaviate()
    
    # Tentar obter collection name se não fornecido
    if not collection_name:
        try:
            all_collections = await client.collections.list_all()
            embedding_collections = [c for c in all_collections if "VERBA_Embedding" in c]
            if embedding_collections:
                collection_name = embedding_collections[0]
                print(f"[ETL] Collection detectada: {collection_name}")
            else:
                # Fallback para "Passage" se nenhuma collection VERBA_Embedding encontrada
                collection_name = "Passage"
        except:
            collection_name = "Passage"
    
    coll = client.collections.get(collection_name)
    gaz = load_gazetteer()

    changed = 0

    schema_props: Set[str] = set()
    missing_update_notified: Set[str] = set()

    # Busca objetos - usando apenas propriedades garantidas no schema
    try:
        requested_props = [
            "content",
            "section_title",
            "section_first_para",
            "parent_entities",
            "text",
            "chunk_text",
        ]
        schema_props = set()
        try:
            config = await coll.config.get()
            schema_props = {
                prop.name
                for prop in getattr(config, "properties", [])
                if getattr(prop, "name", None)
            }
        except Exception as schema_err:
            print(f"⚠️ Não foi possível obter propriedades do schema ({collection_name}): {schema_err}")

        if schema_props:
            return_props = [prop for prop in requested_props if prop in schema_props]
            missing_props = [prop for prop in requested_props if prop not in schema_props]
            if missing_props:
                print(
                    f"⚠️ Propriedades ausentes na collection {collection_name}: "
                    + ", ".join(missing_props)
                )
            if not return_props:
                print(
                    f"⚠️ Nenhuma das propriedades solicitadas está presente em {collection_name}. "
                    "A busca retornará todos os campos disponíveis."
                )
        else:
            return_props = []
            print(
                f"⚠️ Schema da collection {collection_name} não pôde ser determinado - "
                "buscando chunks sem limitar propriedades"
            )

        fetch_kwargs = {"limit": len(uuids)}
        if tenant:
            fetch_kwargs["tenant"] = tenant
        if return_props:
            fetch_kwargs["return_properties"] = return_props

        try:
            res = await coll.query.fetch_objects(**fetch_kwargs)
        except TypeError as err:
            # Algumas versões do client ainda não expõem o parâmetro tenant
            if "tenant" in fetch_kwargs and "tenant" in str(err):
                fetch_kwargs.pop("tenant", None)
                res = await coll.query.fetch_objects(**fetch_kwargs)
            else:
                raise
        except Exception as prop_err:
            # Se falhou por propriedade inexistente, tentar sem return_properties (retorna todas)
            print(f"⚠️ Erro ao buscar com propriedades específicas, tentando sem filtro: {str(prop_err)}")
            fetch_kwargs = {"limit": len(uuids)}
            if tenant:
                fetch_kwargs["tenant"] = tenant
            res = await coll.query.fetch_objects(**fetch_kwargs)
        
        objs = {str(o.uuid): o for o in res.objects if str(o.uuid) in uuids}
    except Exception as e:
        print(f"Erro ao buscar passages: {str(e)}")
        return {"patched": 0, "error": str(e)}
    
    for uid in uuids:
        o = objs.get(uid)
        if not o:
            continue
        
        try:
            p = o.properties
            text = p.get("content") or p.get("text") or p.get("chunk_text") or ""
            sect_title = p.get("section_title") or ""
            first_para = p.get("section_first_para") or ""
            parent_ents = p.get("parent_entities") or []
            
            # NOVO: Extração inteligente de entidades (sem gazetteer obrigatório)
            entity_mentions = extract_entities_intelligent(text)
            
            # Modo legado: tentar mapear para entity_ids se gazetteer disponível
            local_ids = []
            if gaz:
                local_ids = extract_entities_with_gazetteer(text, gaz)
            
            # MODO INTELIGENTE: Se não há gazetteer, usar textos das entidades diretamente
            # IMPORTANTE: Priorizar labels com alto valor empresarial (ORG/PER/LOC/GPE)
            # Mantemos LOC/GPE porque spaCy-pt costuma classificar empresas brasileiras como locais
            if not local_ids and entity_mentions:
                local_ids = [
                    m["text"] for m in entity_mentions 
                    if m.get("label") in PRIMARY_ENTITY_LABELS
                ]
            
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
            else:
                # MODO INTELIGENTE: Sem gazetteer, usar textos das entidades do chunk
                # IMPORTANTE: Priorizar labels empresariais (ver PRIMARY_ENTITY_LABELS)
                if entity_mentions:
                    sect_ids = [
                        m["text"] for m in entity_mentions 
                        if m.get("label") in PRIMARY_ENTITY_LABELS
                    ]
                    scope_conf = 0.85 if sect_ids else 0.0  # Alta confiança pois vem diretamente do chunk
            
            # Primary entity + focus score
            primary = local_ids[0] if local_ids else (sect_ids[0] if sect_ids else None)
            focus = 1.0 if primary and primary in local_ids else (0.7 if primary else 0.0)
            
            # Prepara properties para salvar
            full_props = {
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

            if schema_props:
                props = {
                    key: value for key, value in full_props.items() if key in schema_props
                }
                skipped = [
                    key
                    for key in full_props.keys()
                    if key not in schema_props and key not in missing_update_notified
                ]
                if skipped:
                    missing_update_notified.update(skipped)
                    print(
                        f"⚠️ Collection {collection_name} não possui campos "
                        + ", ".join(skipped)
                        + " - ignorando nos updates ETL."
                    )
            else:
                props = full_props

            if not props:
                print(
                    f"⚠️ Nenhuma propriedade ETL disponível no schema de {collection_name}; "
                    f"chunk {uid[:8]} não será atualizado."
                )
                continue
            
            update_kwargs = {
                "uuid": uid,
                "properties": props,
            }
            if tenant:
                update_kwargs["tenant"] = tenant

            try:
                await coll.data.update(**update_kwargs)
            except TypeError as err:
                if "tenant" in update_kwargs and "tenant" in str(err):
                    update_kwargs.pop("tenant", None)
                    await coll.data.update(**update_kwargs)
                else:
                    raise
            except Exception as update_err:
                err_text = str(update_err)
                err_lower = err_text.lower()
                if "no such prop" in err_lower and update_kwargs.get("properties"):
                    missing_field = None
                    match = re.search(r"'([^']+)'", err_text)
                    if match:
                        missing_field = match.group(1)
                    if missing_field:
                        if missing_field in update_kwargs["properties"]:
                            update_kwargs["properties"].pop(missing_field, None)
                        if missing_field not in missing_update_notified:
                            missing_update_notified.add(missing_field)
                            print(
                                f"⚠️ Ignorando campo {missing_field} no update do chunk {uid[:8]} "
                                f"porque não existe em {collection_name}."
                            )
                    if update_kwargs["properties"]:
                        await coll.data.update(**update_kwargs)
                        # Reutiliza props filtradas para futuros logs
                        props = update_kwargs["properties"]
                    else:
                        print(
                            f"⚠️ Nenhuma propriedade restante para atualizar o chunk {uid[:8]} "
                            f"após remover campos inexistentes."
                        )
                        continue
                else:
                    raise
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

