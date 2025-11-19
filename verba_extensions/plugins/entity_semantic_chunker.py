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
from typing import List, Dict, Any, Tuple

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
    """

    def __init__(self) -> None:
        super().__init__()
        self.name = "Entity-Semantic"
        self.requires_library = ["numpy", "sklearn"]
        self.description = (
            "Section-aware + entity guardrails + semantic breakpoints (intra-section)"
        )
        # Reaproveita configs do SemanticChunker
        self.config = {
            "Breakpoint Percentile Threshold": InputConfig(
                type="number",
                value=80,
                description=(
                    "Percentil do drop de similaridade para split; menor → mais splits"
                ),
                values=[],
            ),
            "Max Sentences Per Chunk": InputConfig(
                type="number",
                value=20,
                description="Máximo de sentenças por chunk (fallback/capping)",
                values=[],
            ),
            "Overlap": InputConfig(
                type="number",
                value=0,
                description="Overlap em sentenças entre chunks (opcional)",
                values=[],
            ),
        }

    async def chunk(
        self,
        config: Dict,
        documents: List[Document],
        embedder: Embedding | None = None,
        embedder_config: Dict | None = None,
    ) -> List[Document]:
        # Lê configs
        breakpoint_percentile_threshold = int(
            config["Breakpoint Percentile Threshold"].value
        )
        max_sentences_per_chunk = int(config["Max Sentences Per Chunk"].value)
        overlap_sentences = int(config.get("Overlap", {}).value if hasattr(config.get("Overlap", {}), "value") else 0)

        # Importa detecção de seções do chunker existente
        with contextlib.suppress(Exception):
            from verba_extensions.plugins.section_aware_chunker import detect_sections  # type: ignore

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

            # Sentenças com offsets (para mapear seções e spans)
            all_sentences = _sentences_with_offsets(document)
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

            # Detecta seções (se disponível); caso contrário, usa documento inteiro
            sections: List[Dict[str, Any]] = []
            try:
                sections = detect_sections(text)  # type: ignore[name-defined]
            except Exception:
                sections = [{"title": "", "content": text, "start": 0, "end": len(text)}]

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

                # Calcula quebras semânticas (ou fallback)
                breakpoints: List[int] = []  # índices exclusivos de boundary (entre sentenças)
                if use_semantic and embeddings is not None and len(embeddings) > 1:
                    try:
                        # Similaridade de sentenças adjacentes
                        # distances[i] mede dissimilaridade entre i e i+1
                        sims = []
                        for i in range(len(embeddings) - 1):
                            sim = cosine_similarity(
                                [embeddings[i]], [embeddings[i + 1]]
                            )[0][0]
                            sims.append(sim)
                        distances = [1.0 - s for s in sims]

                        # Threshold pelo percentil configurado
                        threshold = float(np.percentile(distances, breakpoint_percentile_threshold))  # type: ignore[name-defined]

                        # Define quebras onde distância excede threshold
                        for i, d in enumerate(distances, start=1):
                            if d >= threshold:
                                breakpoints.append(i)
                    except Exception as e:
                        msg.warn(
                            f"[Entity-Semantic] Erro no cálculo semântico (fallback por tamanho): {type(e).__name__}: {str(e)}"
                        )
                        breakpoints = []

                # Sempre aplica cap por tamanho máximo de sentenças
                if max_sentences_per_chunk > 0:
                    idx = max_sentences_per_chunk
                    while idx < len(sentences):
                        breakpoints.append(idx)
                        idx += max_sentences_per_chunk

                # Ordena e remove duplicados
                breakpoints = sorted(set(breakpoints))

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
                    
                    # Detecta frameworks, empresas e setores (opcional, não bloqueia se falhar)
                    try:
                        from verba_extensions.utils.framework_detector import get_framework_detector
                        framework_detector = get_framework_detector()
                        framework_data = await framework_detector.detect_frameworks(chunk_text)
                        
                        # Enriquece metadata do chunk
                        if not hasattr(chunk, "meta") or chunk.meta is None:
                            chunk.meta = {}
                        
                        chunk.meta["frameworks"] = framework_data.get("frameworks", [])
                        chunk.meta["companies"] = framework_data.get("companies", [])
                        chunk.meta["sectors"] = framework_data.get("sectors", [])
                        chunk.meta["framework_confidence"] = framework_data.get("confidence", 0.0)
                    except Exception as e:
                        # Falha na detecção não bloqueia chunking
                        msg.debug(f"[Entity-Semantic] Erro ao detectar frameworks (não crítico): {str(e)}")
                    
                    document.chunks.append(chunk)
                    chunk_id_counter += 1

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
                
                # Detecta frameworks, empresas e setores (opcional, não bloqueia se falhar)
                try:
                    from verba_extensions.utils.framework_detector import get_framework_detector
                    framework_detector = get_framework_detector()
                    framework_data = await framework_detector.detect_frameworks(text)
                    
                    # Enriquece metadata do chunk
                    if not hasattr(chunk, "meta") or chunk.meta is None:
                        chunk.meta = {}
                    
                    chunk.meta["frameworks"] = framework_data.get("frameworks", [])
                    chunk.meta["companies"] = framework_data.get("companies", [])
                    chunk.meta["sectors"] = framework_data.get("sectors", [])
                    chunk.meta["framework_confidence"] = framework_data.get("confidence", 0.0)
                except Exception as e:
                    # Falha na detecção não bloqueia chunking
                    msg.debug(f"[Entity-Semantic] Erro ao detectar frameworks (não crítico): {str(e)}")
                
                document.chunks.append(chunk)

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


