"""
Plugin: EntitySemanticChunker

Combina:
- Section scope (limites de seção) para evitar contaminação entre assuntos/empresas
- Guard-rails de entidades (entity_spans do ETL-PRE) para não cortar entidades
- Quebras semânticas intra-seção (mesmas configs do SemanticChunker)

Requisitos opcionais: numpy, scikit-learn (para cosine similarity)
Se indisponíveis, cai em fallback por tamanho máximo de sentenças.
"""

import asyncio
import contextlib
import re
from typing import List, Dict, Any, Tuple, Optional

with contextlib.suppress(Exception):
    import numpy as np  # type: ignore
with contextlib.suppress(Exception):
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

from wasabi import msg

from goldenverba.components.chunk import Chunk
from goldenverba.components.document import Document
from goldenverba.components.interfaces import Chunker, Embedding
from goldenverba.components.types import InputConfig


def _sentences_with_offsets(document: Document) -> List[Dict[str, Any]]:
    """Extrai sentenças com offsets de caractere do spaCy doc do documento."""
    sentences: List[Dict[str, Any]] = []
    if not hasattr(document, "spacy_doc") or document.spacy_doc is None:
        return sentences
    for idx, sent in enumerate(document.spacy_doc.sents):
        # spaCy fornece start_char/end_char relativos ao documento inteiro
        sentences.append(
            {
                "index": idx,
                "text": sent.text,
                "start": sent.start_char,
                "end": sent.end_char,
            }
        )
    return sentences


def _filter_sentences_in_section(
    all_sentences: List[Dict[str, Any]], section_start: int, section_end: int
) -> List[Dict[str, Any]]:
    """Filtra sentenças contidas dentro de [section_start, section_end)."""
    return [
        s for s in all_sentences if s["start"] >= section_start and s["end"] <= section_end
    ]


def detect_hierarchical_sections(text: str) -> List[Dict[str, Any]]:
    """
    Detecta seções hierárquicas no texto usando Markdown (# ## ###) e numeração (1. 1.1 1.1.1).

    Complexidade: O(n) onde n = número de linhas
    Otimizações:
    - Regex pré-compiladas (não implementadas ainda, mas recomendadas)
    - Fast-checks antes de regex
    - Stack-based hierarchy tracking
    """
    """
    Detecta seções hierárquicas no texto usando Markdown (# ## ###) e numeração (1. 1.1 1.1.1).
    
    Retorna lista de seções com metadados hierárquicos:
    - level: Nível hierárquico (0=documento, 1=H1, 2=H2, 3=H3)
    - parent: Título da seção pai (None se level=1)
    - path: Array de títulos do caminho completo
    - document_context: String legível do caminho completo
    - title, content, start, end: Campos padrão de seção
    """
    sections: List[Dict[str, Any]] = []
    lines = text.split('\n')
    
    # Stack de seções ativas (última seção de cada nível)
    # stack[i] = última seção do nível i+1 (índice 0 = nível 1)
    stack: List[Dict[str, Any]] = []
    
    # Acumula conteúdo da seção atual
    current_content_lines: List[str] = []
    current_section: Optional[Dict[str, Any]] = None
    current_pos = 0
    
    def _detect_heading_level(line: str) -> Tuple[int, str]:
        """
        Detecta nível de heading e retorna (level, title).
        Retorna (0, "") se não for heading.

        Otimizações aplicadas:
        - Verifica se linha começa com caracteres relevantes antes de regex
        - Regex compiladas para melhor performance
        """
        line_stripped = line.strip()

        # Fast check: se não começa com # ou dígito, não é heading
        if not line_stripped or not (
            line_stripped.startswith('#') or
            line_stripped[0].isdigit()
        ):
            return (0, "")

        # Markdown headings: # H1, ## H2, ### H3
        if line_stripped.startswith('#'):
            markdown_match = re.match(r'^(#{1,6})\s+(.+)$', line_stripped)
            if markdown_match:
                level = len(markdown_match.group(1))
                title = markdown_match.group(2).strip()
                return (level, title)

        # Numeração: 1., 1.1, 1.1.1, etc.
        if line_stripped[0].isdigit():
            numbering_match = re.match(r'^(\d+(?:\.\d+)*)[\.)]\s+(.+)$', line_stripped)
            if numbering_match:
                numbering = numbering_match.group(1)
                title = numbering_match.group(2).strip()
                # Conta quantos pontos há na numeração para determinar nível
                level = numbering.count('.') + 1
                return (level, title)

        # Heurísticas para títulos (fallback) - apenas se parece com título
        if (len(line_stripped) < 100 and
            not line_stripped.endswith('.') and
            len(line_stripped.split()) <= 15 and
            (line_stripped.isupper() or
             re.match(r'^[A-Z][^\.]*:', line_stripped))):
            # Assume nível 1 para heurísticas
            return (1, line_stripped)

        return (0, "")
    
    def _finalize_section():
        """Finaliza seção atual e adiciona à lista."""
        nonlocal current_section, current_content_lines, current_pos
        
        if current_section is None:
            return
        
        # Adiciona conteúdo acumulado
        content = '\n'.join(current_content_lines).strip()
        if content or current_section.get("title"):
            # Atualiza conteúdo e end da seção
            current_section["content"] = content
            # End é a posição atual (último caractere processado)
            current_section["end"] = current_pos
            sections.append(current_section)
        
        current_content_lines = []
        current_section = None
    
    for line_idx, line in enumerate(lines):
        line_start_pos = current_pos
        line_end_pos = current_pos + len(line)
        
        # Detecta se é heading
        level, title = _detect_heading_level(line)
        
        if level > 0:
            # Finaliza seção anterior
            _finalize_section()
            
            # Remove seções do stack com nível >= nível atual
            # Isso garante que apenas seções ancestrais permanecem
            while stack and stack[-1].get("level", 0) >= level:
                stack.pop()
            
            # Determina parent (última seção do nível anterior)
            parent = None
            parent_title = ""
            if level > 1 and stack:
                # Otimização: busca reversa do stack (mais eficiente que loop completo)
                # Como stack está ordenado por nível, podemos buscar do final para o início
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i].get("level", 0) < level:
                        parent = stack[i]
                        parent_title = parent.get("title", "")
                        break
            
            # Constrói path completo
            path = [s.get("title", "") for s in stack if s.get("title")]
            path.append(title)
            
            # Constrói document_context (string legível)
            document_context = " > ".join(path) if path else title
            
            # Start da seção é após o heading (próxima linha)
            section_start = line_end_pos + 1  # +1 para pular \n
            
            # Cria nova seção
            current_section = {
                "title": title,
                "content": "",
                "start": section_start,
                "end": section_start,
                "level": level,
                "parent": parent_title,
                "path": path,
                "document_context": document_context
            }
            
            # Adiciona ao stack
            stack.append(current_section)
            
            current_pos = line_end_pos + 1  # +1 para \n
        else:
            # Linha normal, adiciona ao conteúdo da seção atual
            if current_section is None:
                # Se não há seção atual, cria seção raiz (nível 0)
                current_section = {
                    "title": "",
                    "content": "",
                    "start": 0,
                    "end": 0,
                    "level": 0,
                    "parent": "",
                    "path": [],
                    "document_context": ""
                }
            
            current_content_lines.append(line)
            current_pos = line_end_pos + 1  # +1 para \n
    
    # Finaliza última seção
    _finalize_section()
    
    # Se não detectou nenhuma seção, retorna documento inteiro como seção raiz
    if not sections:
        return [{
            "title": "",
            "content": text,
            "start": 0,
            "end": len(text),
            "level": 0,
            "parent": "",
            "path": [],
            "document_context": ""
        }]

    # Otimização: garante que seções estão ordenadas por posição
    sections.sort(key=lambda s: s.get("start", 0))

    return sections
    
    return sections


def _has_library(lib_name: str) -> bool:
    try:
        __import__(lib_name)
        return True
    except Exception:
        return False


def _entity_crosses_boundary(entity_spans: List[Dict[str, Any]], boundary_char: int) -> bool:
    """
    Retorna True se existe alguma entidade cujo span cruza o boundary_char.
    Uma entidade cruza o boundary se start < boundary < end.
    """
    for ent in entity_spans:
        try:
            if int(ent.get("start", -1)) < boundary_char < int(ent.get("end", -1)):
                return True
        except Exception:
            # Ignora spans mal-formados
            continue
    return False


def _get_frequent_entities(
    entity_spans: List[Dict[str, Any]],
    min_frequency: int = 2
) -> set:
    """
    Retorna entidades que aparecem pelo menos min_frequency vezes.
    Essas são as entidades "âncoras" do documento.
    """
    from collections import Counter
    
    entity_counts = Counter()
    for ent in entity_spans:
        text = ent.get("text", "").lower().strip()
        if text and len(text) > 2:  # Ignora entidades muito curtas
            entity_counts[text] += 1
    
    return {ent for ent, count in entity_counts.items() if count >= min_frequency}


def _normalize_company(text: str) -> List[str]:
    """
    Normaliza nomes de empresas usando gazetteer (se disponível).
    Retorna lista com variações: [normalizada, original] (dedup).
    """
    # Cache simples para evitar recarregar gazetteer a cada chamada
    if not hasattr(_normalize_company, "_gazetteer_cache"):
        _normalize_company._gazetteer_cache = None  # type: ignore
    if not hasattr(_normalize_company, "_gazetteer_loaded"):
        _normalize_company._gazetteer_loaded = False  # type: ignore

    variants = set()
    norm = text.strip().lower()
    if norm:
        variants.add(norm)
    # Tenta gazetteer do a2_etl_hook (aliases)
    try:
        if not _normalize_company._gazetteer_loaded:  # type: ignore
            from verba_extensions.plugins.a2_etl_hook import load_gazetteer
            _normalize_company._gazetteer_cache = load_gazetteer()  # type: ignore
            _normalize_company._gazetteer_loaded = True  # type: ignore
        gaz = _normalize_company._gazetteer_cache  # type: ignore
        for eid, aliases in gaz.items():
            for alias in aliases:
                if alias.strip().lower() == norm:
                    variants.add(eid.lower())
                    # também inclui alias canônico (primeiro)
                    if aliases:
                        variants.add(aliases[0].strip().lower())
                    break
    except Exception:
        pass
    return list(variants) if variants else ([norm] if norm else [])


def _extract_companies_from_spans(entity_spans: List[Dict[str, Any]]) -> List[str]:
    """
    Extrai empresas (ORG) dos spans e normaliza (aliases/gazetteer).
    """
    companies: set[str] = set()
    for ent in entity_spans or []:
        try:
            label = ent.get("label", "").upper()
            if label != "ORG":
                continue
            text = ent.get("text", "")
            if not text or not text.strip():
                continue
            for variant in _normalize_company(text):
                if variant:
                    companies.add(variant)
            # preserva texto original normalizado também
            companies.add(text.strip().lower())
        except Exception:
            continue
    return sorted(companies)


def _merge_small_chunks(chunks: List[Chunk], min_chars: int) -> List[Chunk]:
    """
    Mescla chunks muito pequenos com o anterior quando possível.
    Regras conservadoras:
    - Só mescla se chunk atual < min_chars
    - Não altera ordem
    """
    if not chunks or len(chunks) < 2:
        return chunks
    
    merged: List[Chunk] = []
    for chunk in chunks:
        if merged and len(chunk.content or "") < min_chars:
            prev = merged[-1]
            # Concatena conteúdos
            new_content = f"{prev.content} {chunk.content}".strip()
            prev.content = new_content
            prev.content_without_overlap = new_content
            # Atualiza end_i se disponível
            if hasattr(prev, "end_i") and hasattr(chunk, "end_i"):
                try:
                    prev.end_i = chunk.end_i
                except Exception:
                    pass
            # Merge metadados básicos (companies)
            if hasattr(prev, "meta") or hasattr(chunk, "meta"):
                prev.meta = prev.meta or {}
                for key in ["companies"]:
                    vals = []
                    if key in (prev.meta or {}):
                        vals.extend(prev.meta.get(key, []))
                    if hasattr(chunk, "meta") and chunk.meta and key in chunk.meta:
                        vals.extend(chunk.meta.get(key, []))
                    if vals:
                        prev.meta[key] = sorted(set(vals))
            # end_i já ajustado, start_i mantém
        else:
            merged.append(chunk)
    return merged


def _get_anchor_entities_in_range(
    start_char: int,
    end_char: int,
    entity_spans: List[Dict[str, Any]],
    anchor_entities: set
) -> set:
    """
    Retorna entidades âncora (frequentes) que aparecem no range de caracteres.
    """
    entities = set()
    for ent in entity_spans:
        try:
            ent_start = int(ent.get("start", -1))
            ent_end = int(ent.get("end", -1))
            ent_text = ent.get("text", "").lower().strip()
            
            # Verifica overlap e se é entidade âncora
            if ent_start < end_char and ent_end > start_char:
                if ent_text in anchor_entities:
                    entities.add(ent_text)
        except Exception:
            continue
    return entities


def _adjust_boundary_with_entities(
    sentences: List[Dict[str, Any]],
    boundary_idx_exclusive: int,
    entity_spans: List[Dict[str, Any]],
) -> int:
    """
    Ajusta o índice de boundary (exclusivo) para não cortar entidades no meio.
    Tenta mover para frente uma sentença (quando possível). Se ainda cruzar, tenta recuar uma.
    Retorna novo índice exclusivo.
    """
    if not sentences:
        return boundary_idx_exclusive

    # Boundary em caracteres é o end da sentença anterior (boundary_idx_exclusive - 1)
    safe_idx = max(1, min(boundary_idx_exclusive, len(sentences)))
    boundary_char = sentences[safe_idx - 1]["end"]

    if not _entity_crosses_boundary(entity_spans, boundary_char):
        return boundary_idx_exclusive

    # 1) Tentar avançar 1 sentença
    if safe_idx < len(sentences):
        boundary_char_fwd = sentences[safe_idx]["end"]
        if not _entity_crosses_boundary(entity_spans, boundary_char_fwd):
            return boundary_idx_exclusive + 1

    # 2) Tentar recuar 1 sentença
    if safe_idx - 1 > 0:
        boundary_char_back = sentences[safe_idx - 2]["end"]
        if not _entity_crosses_boundary(entity_spans, boundary_char_back):
            return max(1, boundary_idx_exclusive - 1)

    # 3) Se não for possível garantir, mantém boundary original
    return boundary_idx_exclusive


class EntitySemanticChunker(Chunker):
    """
    Chunker híbrido: seções + guard-rails de entidades + quebras semânticas intra-seção.
    
    REQUISITOS:
    - numpy: Para cálculo de percentis em breakpoints
    - scikit-learn: Para cálculo de similaridade de cosseno
    
    Se não disponíveis, usa fallback por tamanho máximo de sentenças.
    Para melhor qualidade de chunking, instale: pip install numpy scikit-learn
    """

    # Flag de classe para verificação de dependências (verificado uma vez)
    _dependencies_checked = False
    _has_numpy = False
    _has_sklearn = False

    def __init__(self) -> None:
        super().__init__()
        self.name = "Entity-Semantic"
        self.requires_library = ["numpy", "sklearn"]
        self.description = (
            "Semantic breakpoints + entity anchors (frequent entities keep text together)"
        )
        
        # Verificar dependências uma vez na inicialização
        self._check_dependencies()
        
        # Reaproveita configs do SemanticChunker
        self.config = {
            "Breakpoint Percentile Threshold": InputConfig(
                type="number",
                value=95,  # Aumentado de 80 para 95 - menos fragmentação
                description=(
                    "Percentil do drop de similaridade para split; maior → menos splits (95 recomendado)"
                ),
                values=[],
            ),
            "Max Sentences Per Chunk": InputConfig(
                type="number",
                value=30,  # Aumentado de 20 para 30
                description="Máximo de sentenças por chunk (fallback/capping)",
                values=[],
            ),
            "Min Chunk Chars": InputConfig(
                type="number",
                value=200,  # Novo: tamanho mínimo de chunk
                description="Tamanho mínimo de chunk em caracteres (chunks menores são mesclados)",
                values=[],
            ),
            "Overlap": InputConfig(
                type="number",
                value=0,
                description="Overlap em sentenças entre chunks (opcional)",
                values=[],
            ),
        }
    
    @classmethod
    def _check_dependencies(cls):
        """
        Verifica se numpy e sklearn estão disponíveis.
        Emite warning se não estiverem (apenas uma vez).
        """
        if cls._dependencies_checked:
            return
        
        cls._dependencies_checked = True
        cls._has_numpy = _has_library("numpy")
        cls._has_sklearn = _has_library("sklearn")
        
        if not cls._has_numpy or not cls._has_sklearn:
            missing = []
            if not cls._has_numpy:
                missing.append("numpy")
            if not cls._has_sklearn:
                missing.append("scikit-learn")
            
            msg.warn(
                f"⚠️  EntitySemanticChunker: Dependências opcionais não encontradas: {', '.join(missing)}"
            )
            msg.warn(
                f"   💡 Para chunking semântico de alta qualidade, instale: pip install {' '.join(missing)}"
            )
            msg.warn(
                f"   📝 Usando fallback por tamanho máximo de sentenças (funciona, mas menos preciso)"
            )
        else:
            msg.info("✅ EntitySemanticChunker: numpy e sklearn disponíveis - chunking semântico habilitado")

    async def chunk(
        self,
        config: Dict,
        documents: List[Document],
        embedder: Embedding | None = None,
        embedder_config: Dict | None = None,
    ) -> List[Document]:
        # Helper function to safely get config value (supports both InputConfig and dict)
        def get_cfg(key, default):
            item = config.get(key, {})
            if hasattr(item, 'value'):
                return item.value
            elif isinstance(item, dict):
                return item.get('value', default)
            return default
        
        # Lê configs usando helper seguro
        breakpoint_percentile_threshold = int(get_cfg("Breakpoint Percentile Threshold", 95))
        max_sentences_per_chunk = int(get_cfg("Max Sentences Per Chunk", 30))
        min_chunk_chars = int(get_cfg("Min Chunk Chars", 200))
        overlap_sentences = int(get_cfg("Overlap", 0))
        
        # Constante: tamanho mínimo de sentença para não ser descartada
        MIN_SENTENCE_CHARS = 10

        for document in documents:
            if len(document.chunks) > 0:
                continue

            text = document.content or ""
            if not text:
                continue

            # Entidades do ETL-PRE (guard-rails)
            entity_spans: List[Dict[str, Any]] = []
            if hasattr(document, "meta") and document.meta:
                entity_spans = document.meta.get("entity_spans", []) or []
                # Ordena por start para processamento mais eficiente
                try:
                    entity_spans = sorted(entity_spans, key=lambda e: int(e.get("start", 0)))
                except Exception:
                    pass
            
            # Extrai empresas normalizadas para enriquecer metadados (named vectors)
            companies_doc: List[str] = _extract_companies_from_spans(entity_spans)

            # Sentenças com offsets (para mapear seções e spans)
            all_sentences_raw = _sentences_with_offsets(document)
            
            # Filtra sentenças muito curtas (números, bullets, linhas vazias)
            # Essas "sentenças" fragmentam o documento desnecessariamente
            all_sentences = [
                s for s in all_sentences_raw 
                if len(s["text"].strip()) >= MIN_SENTENCE_CHARS
            ]
            
            # Log se filtrou muitas sentenças
            filtered_count = len(all_sentences_raw) - len(all_sentences)
            if filtered_count > 0:
                msg.info(f"[Entity-Semantic] Filtradas {filtered_count} sentenças curtas (<{MIN_SENTENCE_CHARS} chars)")
            
            if not all_sentences:
                # Fallback: cria um único chunk
                document.chunks.append(
                    Chunk(
                        content=text,
                        chunk_id=0,
                        start_i=0,
                        end_i=len(text),
                        content_without_overlap=text,
                    )
                )
                continue

            # Detecta seções hierárquicas (se disponível); caso contrário, usa documento inteiro
            sections: List[Dict[str, Any]] = []
            try:
                sections = detect_hierarchical_sections(text)
                msg.info(f"[Entity-Semantic] Detectadas {len(sections)} seções hierárquicas no documento")
                for i, sec in enumerate(sections):
                    sec_title = sec.get("title", "(sem título)")[:50]
                    sec_level = sec.get("level", 0)
                    sec_size = sec.get("end", 0) - sec.get("start", 0)
                    sec_context = sec.get("document_context", "")[:80]
                    msg.info(f"[Entity-Semantic]   Seção {i+1} (nível {sec_level}): '{sec_title}' ({sec_size} chars) - {sec_context}")
            except Exception as e:
                msg.warn(f"[Entity-Semantic] Erro ao detectar seções hierárquicas: {str(e)}, usando documento inteiro")
                sections = [{
                    "title": "", 
                    "content": text, 
                    "start": 0, 
                    "end": len(text),
                    "level": 0,
                    "parent": "",
                    "path": [],
                    "document_context": ""
                }]

            chunk_id_counter = 0

            for section in sections:
                section_start = int(section.get("start", 0))
                section_end = int(section.get("end", len(text)))

                sentences = _filter_sentences_in_section(
                    all_sentences, section_start, section_end
                )
                if not sentences:
                    continue

                # Vetorização das sentenças (se possível)
                use_semantic = (
                    embedder is not None
                    and _has_library("numpy")
                    and _has_library("sklearn")
                )

                embeddings = None
                if use_semantic:
                    try:
                        sentence_texts = [s["text"] for s in sentences]
                        embeddings = await embedder.vectorize(
                            embedder_config, sentence_texts
                        )
                    except Exception as e:
                        msg.warn(
                            f"[Entity-Semantic] Falha ao gerar embeddings (fallback por tamanho): {type(e).__name__}: {str(e)}"
                        )
                        use_semantic = False

                # ========================================
                # LÓGICA SIMPLIFICADA: Semantic-first, Entities como guard-rails
                # ========================================
                # 1. Breakpoints semânticos como critério principal (mudança de assunto)
                # 2. Entidades FREQUENTES como âncoras (refinamento)
                # 3. Guard-rails: não cortar no MEIO de uma entidade
                # 4. Max sentences como cap de segurança
                
                breakpoints: List[int] = []
                
                # Identifica entidades frequentes (aparecem 2+ vezes) = âncoras
                anchor_entities = _get_frequent_entities(entity_spans, min_frequency=2)
                if anchor_entities:
                    msg.info(f"[Entity-Semantic] {len(anchor_entities)} entidades âncora: {list(anchor_entities)[:5]}...")
                
                # PASSO 1: Breakpoints semânticos (critério principal)
                if use_semantic and embeddings is not None and len(embeddings) > 1:
                    try:
                        # Similaridade de sentenças adjacentes
                        sims = []
                        for i in range(len(embeddings) - 1):
                            sim = cosine_similarity(
                                [embeddings[i]], [embeddings[i + 1]]
                            )[0][0]
                            sims.append(sim)
                        distances = [1.0 - s for s in sims]

                        # Threshold pelo percentil configurado (95 = top 5% de mudanças)
                        threshold = float(np.percentile(distances, breakpoint_percentile_threshold))  # type: ignore[name-defined]

                        # Breakpoints onde há mudança semântica significativa
                        for i, d in enumerate(distances, start=1):
                            if d >= threshold:
                                breakpoints.append(i)
                        
                        msg.info(f"[Entity-Semantic] {len(breakpoints)} breakpoints semânticos (threshold={threshold:.3f})")
                    except Exception as e:
                        msg.warn(
                            f"[Entity-Semantic] Erro no cálculo semântico: {type(e).__name__}: {str(e)}"
                        )
                
                # PASSO 2: Refinamento com entidades âncora
                # Remove breakpoints que separariam texto sobre a MESMA entidade âncora
                if breakpoints and anchor_entities:
                    refined_breakpoints = []
                    for bp in breakpoints:
                        # Verifica entidades antes e depois do breakpoint
                        if bp > 0 and bp < len(sentences):
                            before_start = sentences[max(0, bp-3)]["start"]
                            before_end = sentences[bp-1]["end"]
                            after_start = sentences[bp]["start"]
                            after_end = sentences[min(len(sentences)-1, bp+2)]["end"]
                            
                            ents_before = _get_anchor_entities_in_range(
                                before_start, before_end, entity_spans, anchor_entities
                            )
                            ents_after = _get_anchor_entities_in_range(
                                after_start, after_end, entity_spans, anchor_entities
                            )
                            
                            # Se compartilham entidade âncora, NÃO quebra
                            shared = ents_before & ents_after
                            if shared:
                                msg.info(f"[Entity-Semantic] Breakpoint {bp} removido - mesma entidade: {shared}")
                                continue
                        
                        refined_breakpoints.append(bp)
                    
                    if len(refined_breakpoints) < len(breakpoints):
                        msg.info(f"[Entity-Semantic] Refinado: {len(breakpoints)} → {len(refined_breakpoints)} breakpoints")
                    breakpoints = refined_breakpoints

                # Sempre aplica cap por tamanho máximo de sentenças
                if max_sentences_per_chunk > 0:
                    idx = max_sentences_per_chunk
                    while idx < len(sentences):
                        breakpoints.append(idx)
                        idx += max_sentences_per_chunk

                # Ordena e remove duplicados
                breakpoints = sorted(set(breakpoints))
                
                # Log para debug
                section_title = section.get("title", "(sem título)")[:50]
                msg.info(f"[Entity-Semantic] Seção '{section_title}': {len(sentences)} sentenças, {len(breakpoints)} breakpoints semânticos, max_sentences={max_sentences_per_chunk}")

                # Constrói chunks respeitando guard-rails de entidades e overlap (em sentenças)
                start_idx = 0
                for bp in breakpoints + [len(sentences)]:
                    # Boundary exclusivo proposto
                    proposed_end_exclusive = bp

                    # Ajuste para não cortar entidades
                    adjusted_end_exclusive = _adjust_boundary_with_entities(
                        sentences, proposed_end_exclusive, entity_spans
                    )

                    end_idx_exclusive = max(start_idx + 1, adjusted_end_exclusive)

                    # Aplica overlap em sentenças (se configurado e se não for o primeiro chunk)
                    chunk_start_idx = start_idx
                    chunk_end_idx_exclusive = end_idx_exclusive
                    if overlap_sentences > 0 and start_idx > 0:
                        chunk_start_idx = max(0, start_idx - overlap_sentences)

                    # Monta conteúdo pelo range de caracteres
                    chunk_start_char = sentences[chunk_start_idx]["start"]
                    chunk_end_char = sentences[chunk_end_idx_exclusive - 1]["end"]
                    chunk_text = text[chunk_start_char:chunk_end_char]

                    # Cria chunk
                    chunk = Chunk(
                        content=chunk_text,
                        chunk_id=chunk_id_counter,
                        start_i=chunk_start_char,
                        end_i=chunk_end_char,
                        content_without_overlap=chunk_text,
                    )
                    
                    # Inicializa meta se necessário
                    if not hasattr(chunk, "meta") or chunk.meta is None:
                        chunk.meta = {}
                    
                    # Adiciona metadados hierárquicos da seção
                    chunk.meta.update({
                        "section_level": section.get("level", 0),
                        "parent_section": section.get("parent", ""),
                        "document_context": section.get("document_context", ""),
                        "section_path": section.get("path", [])
                    })
                    
                    # NOTA: Detecção de frameworks removida deste chunker genérico
                    # Para slides de consultoria, usar SlidesSemanticaVisualReader + SlidesSemanticaVisualChunker
                    # que já fazem detecção de frameworks no reader e preservam no chunker
                    # Enriquecer metadados com companies extraídas do documento
                    if companies_doc:
                        existing_companies = set(chunk.meta.get("companies", [])) if isinstance(chunk.meta.get("companies", []), list) else set()
                        merged_companies = sorted(existing_companies.union(set(companies_doc)))
                        chunk.meta["companies"] = merged_companies
                    
                    document.chunks.append(chunk)
                    chunk_id_counter += 1
                    msg.debug(f"[Entity-Semantic] Chunk {chunk_id_counter} criado: {len(chunk_text)} chars, {end_idx_exclusive - chunk_start_idx} sentenças")

                    start_idx = end_idx_exclusive

                    # yield para não bloquear event loop em documentos longos
                    if chunk_id_counter % 10 == 0:
                        await asyncio.sleep(0)

            if chunk_id_counter == 0:
                # Fallback de segurança: um único chunk
                chunk = Chunk(
                    content=text,
                    chunk_id=0,
                    start_i=0,
                    end_i=len(text),
                    content_without_overlap=text,
                )
                if not hasattr(chunk, "meta") or chunk.meta is None:
                    chunk.meta = {}
                
                # Adiciona metadados hierárquicos (seção raiz)
                if sections and len(sections) > 0:
                    first_section = sections[0]
                    chunk.meta.update({
                        "section_level": first_section.get("level", 0),
                        "parent_section": first_section.get("parent", ""),
                        "document_context": first_section.get("document_context", ""),
                        "section_path": first_section.get("path", [])
                    })
                else:
                    chunk.meta.update({
                        "section_level": 0,
                        "parent_section": "",
                        "document_context": "",
                        "section_path": []
                    })
                
                if companies_doc:
                    chunk.meta["companies"] = sorted(set(companies_doc))
                document.chunks.append(chunk)

            # Pós-processamento: mesclar chunks minúsculos
            document.chunks = _merge_small_chunks(document.chunks, min_chunk_chars)

        return documents


def register():
    """Registra plugin para o PluginManager."""
    return {
        "name": "entity_semantic_chunker",
        "version": "1.0.0",
        "description": (
            "EntitySemanticChunker: seções + entidades + breakpoints semânticos"
        ),
        "chunkers": [EntitySemanticChunker()],
        "compatible_verba_version": ">=2.1.0",
    }


