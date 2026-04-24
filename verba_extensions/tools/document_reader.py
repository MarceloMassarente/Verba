"""
Search and read tools for analytical agents: grouped search, then controlled read.

Modes for read_document_controlled:
- page: paginate chunks in document order
- window: read chunk_id +/- radius
- section: filter chunks by section_title / section path (substring match)
- outline: list distinct section_title values (and optional section_level)
- full_if_small: concatenate all chunk text if under max_chars; otherwise return error hint
"""
from __future__ import annotations

import json
import math
from typing import Any, Optional

ReadMode = str


def _chunk_text(chunk: dict) -> str:
    if not chunk:
        return ""
    return (
        chunk.get("content_without_overlap")
        or chunk.get("content")
        or ""
    )


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _normalize_rag_config(rag: Any) -> dict[str, Any]:
    if isinstance(rag, dict):
        return rag
    if hasattr(rag, "model_dump"):
        return rag.model_dump()
    return rag.dict()


async def search_documents_grouped(
    verba_manager: Any,
    client: Any,
    query: str,
    rag_config: Any,
    labels: list[str],
    document_uuids: list[str],
    limit_docs: int = 20,
    top_hits_per_doc: int = 5,
) -> dict[str, Any]:
    """
    Run normal retrieval, then return documents ranked with top per-document hits
    and stable evidence handles (doc_uuid, chunk_id) for read_document.
    """
    q = (query or "").strip()
    if not q:
        return {
            "error": "query is empty",
            "documents": [],
            "evidence": {"query": "", "total_groups": 0},
        }

    rag = _normalize_rag_config(rag_config)
    result = await verba_manager.retrieve_chunks(
        client, q, rag, labels, document_uuids
    )
    if len(result) == 3:
        documents, _context, debug_info = result
    else:
        documents, _context = result
        debug_info = None

    if not documents:
        return {
            "documents": [],
            "raw_query_response_count": 0,
            "evidence": {"query": q, "total_groups": 0},
            "debug_info": debug_info,
        }

    # Retriever may return more than limit_docs; we slice after stable sort
    def doc_score(d: dict) -> float:
        return _safe_float(d.get("score", 0.0), 0.0)

    sorted_docs = sorted(documents, key=doc_score, reverse=True)[: max(1, limit_docs)]
    out: list[dict[str, Any]] = []

    for doc in sorted_docs:
        d_uuid = doc.get("uuid") or doc.get("doc_uuid")
        if d_uuid is None:
            continue
        d_uuid = str(d_uuid)
        chunks: list[dict] = list(doc.get("chunks") or [])
        if not chunks and doc.get("content"):
            # Some paths may return flat structure; skip or wrap
            continue

        def ch_score(c: dict) -> float:
            return _safe_float(c.get("score", 0.0), 0.0)

        top = sorted(chunks, key=ch_score, reverse=True)[: max(1, top_hits_per_doc)]
        max_ch = max((ch_score(c) for c in chunks), default=0.0)
        top_hits: list[dict[str, Any]] = []
        for c in top:
            text = c.get("content", "") or ""
            top_hits.append(
                {
                    "chunk_id": c.get("chunk_id"),
                    "uuid": c.get("uuid"),
                    "score": c.get("score"),
                    "content_preview": text[:500],
                    "section_title": c.get("section_title"),
                }
            )

        out.append(
            {
                "document": {
                    "doc_uuid": d_uuid,
                    "title": doc.get("title", "") or "",
                    "metadata": doc.get("metadata", "") or "",
                    "aggregated_score": doc_score(doc),
                },
                "confidence": {
                    "aggregated_score": doc_score(doc),
                    "max_chunk_score": max_ch,
                },
                "top_hits": top_hits,
                "navigation": {
                    "read_document_example": {
                        "doc_uuid": d_uuid,
                        "mode": "page",
                        "page": 1,
                    }
                },
            }
        )

    return {
        "documents": out,
        "raw_query_response_count": len(documents),
        "evidence": {"query": q, "total_groups": len(out)},
        "debug_info": debug_info,
    }


async def read_context_around_chunk(
    weaviate_manager: Any,
    client: Any,
    doc_uuid: str,
    chunk_id_center: int,
    radius: int = 5,
) -> dict[str, Any]:
    """
    Return ordered chunk texts around a chunk_id (inclusive).
    """
    document = await weaviate_manager.get_document(
        client, doc_uuid, properties=["meta", "title"]
    )
    if not document:
        return {"error": "document not found", "doc_uuid": doc_uuid}

    config = json.loads(document["meta"])
    embedder = config["Embedder"]["config"]["Model"]["value"]
    r = max(0, int(radius))
    lo = max(0, int(chunk_id_center) - r)
    hi = int(chunk_id_center) + r
    ids = list(range(lo, hi + 1))
    objects = await weaviate_manager.get_chunk_by_ids(
        client, embedder, doc_uuid, ids
    )
    parts: list[dict[str, Any]] = []
    for obj in objects or []:
        p = obj.properties
        p.setdefault("doc_uuid", str(doc_uuid))
        cid = p.get("chunk_id", 0)
        try:
            cid = int(cid)
        except (TypeError, ValueError):
            cid = 0
        text = _chunk_text(p)
        parts.append(
            {
                "chunk_id": cid,
                "text": text,
                "section_title": p.get("section_title"),
            }
        )
    parts.sort(key=lambda x: x["chunk_id"])
    combined = "\n\n".join(x["text"] for x in parts if x.get("text"))
    return {
        "mode": "window",
        "doc_uuid": doc_uuid,
        "title": document.get("title", ""),
        "center_chunk_id": int(chunk_id_center),
        "radius": r,
        "chunks": parts,
        "text": combined,
        "evidence": {
            "location": {
                "chunk_id_range": [lo, hi],
            }
        },
    }


async def read_document_controlled(
    weaviate_manager: Any,
    client: Any,
    doc_uuid: str,
    mode: ReadMode,
    page: int = 1,
    page_size: int = 10,
    section: Optional[str] = None,
    chunk_id_center: Optional[int] = None,
    radius: int = 5,
    max_chars: int = 50_000,
) -> dict[str, Any]:
    document = await weaviate_manager.get_document(
        client, doc_uuid, properties=["meta", "title", "metadata"]
    )
    if not document:
        return {"error": "document not found", "doc_uuid": doc_uuid}
    try:
        config = json.loads(document["meta"])
    except (json.JSONDecodeError, TypeError) as e:
        return {
            "error": f"invalid document meta: {e}",
            "doc_uuid": doc_uuid,
        }

    embedder = config["Embedder"]["config"]["Model"]["value"]
    total = await weaviate_manager.get_chunk_count(client, embedder, doc_uuid)
    base_evidence = {
        "document": {
            "doc_uuid": doc_uuid,
            "title": document.get("title", ""),
        },
    }

    if mode == "page":
        p = max(1, int(page))
        ps = max(1, int(page_size))
        chunks = await weaviate_manager.get_chunks(
            client, doc_uuid, p, ps
        ) or []
        text = "".join(_chunk_text(c) for c in chunks)
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars]
        has_more = p * ps < total
        return {
            "mode": "page",
            "doc_uuid": doc_uuid,
            "title": document.get("title", ""),
            "page": p,
            "page_size": ps,
            "total_chunks": total,
            "chunks_returned": len(chunks),
            "has_more": has_more,
            "next_page": p + 1 if has_more else None,
            "text": text,
            "truncated": truncated,
            "chunks": [
                {
                    "chunk_id": c.get("chunk_id"),
                    "section_title": c.get("section_title"),
                }
                for c in chunks
            ],
            "evidence": {
                **base_evidence,
                "navigation": {
                    "next_page": p + 1 if has_more else None,
                },
            },
        }

    if mode == "window":
        if chunk_id_center is None:
            return {
                "error": "chunk_id is required for mode=window",
                "doc_uuid": doc_uuid,
            }
        return await read_context_around_chunk(
            weaviate_manager, client, doc_uuid, int(chunk_id_center), radius=radius
        )

    if mode == "section":
        if not section or not str(section).strip():
            return {
                "error": "section (substring) is required for mode=section",
                "doc_uuid": doc_uuid,
            }
        q = str(section).strip().lower()
        collected: list[dict] = []
        psize = 50
        max_pages = int(math.ceil(total / psize)) if total else 0
        for pg in range(1, max_pages + 1):
            batch = await weaviate_manager.get_chunks(
                client, doc_uuid, pg, psize
            ) or []
            for c in batch:
                st = (c.get("section_title") or "") or ""
                sp = c.get("section_path") or []
                sp_text = " ".join(sp) if isinstance(sp, list) else str(sp)
                if q in st.lower() or q in str(sp_text).lower():
                    collected.append(c)
        text = "".join(_chunk_text(c) for c in collected)
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars]
        return {
            "mode": "section",
            "doc_uuid": doc_uuid,
            "title": document.get("title", ""),
            "section_filter": section,
            "chunks_matched": len(collected),
            "text": text,
            "truncated": truncated,
            "evidence": base_evidence,
        }

    if mode == "outline":
        seen: set[tuple[Any, ...]] = set()
        outline: list[dict[str, Any]] = []
        psize = 100
        max_pages = int(math.ceil(total / psize)) if total else 0
        for pg in range(1, max_pages + 1):
            batch = await weaviate_manager.get_chunks(
                client, doc_uuid, pg, psize
            ) or []
            for c in batch:
                st = c.get("section_title") or ""
                if not st:
                    continue
                key = (st, c.get("section_level"))
                if key in seen:
                    continue
                seen.add(key)
                outline.append(
                    {
                        "section_title": st,
                        "section_level": c.get("section_level"),
                        "first_chunk_id": c.get("chunk_id"),
                    }
                )
        outline.sort(key=lambda x: (x.get("first_chunk_id") is None, x.get("first_chunk_id", 0)))
        return {
            "mode": "outline",
            "doc_uuid": doc_uuid,
            "title": document.get("title", ""),
            "total_chunks": total,
            "sections": outline,
            "evidence": base_evidence,
        }

    if mode == "full_if_small":
        psize = 50
        all_chunks: list[dict] = []
        max_pages = int(math.ceil(total / psize)) if total else 0
        for pg in range(1, max_pages + 1):
            batch = await weaviate_manager.get_chunks(
                client, doc_uuid, pg, psize
            ) or []
            if not batch:
                break
            all_chunks.extend(batch)
        text = "".join(_chunk_text(c) for c in all_chunks)
        if len(text) > max_chars:
            return {
                "mode": "full_if_small",
                "doc_uuid": doc_uuid,
                "title": document.get("title", ""),
                "error": "document exceeds max_chars; use mode=page or window",
                "total_chars": len(text),
                "max_chars": max_chars,
                "suggestion": {"mode": "page", "page": 1, "page_size": 10},
            }
        return {
            "mode": "full_if_small",
            "doc_uuid": doc_uuid,
            "title": document.get("title", ""),
            "text": text,
            "total_chunks": total,
            "truncated": False,
            "evidence": base_evidence,
        }

    return {
        "error": f"unknown mode: {mode}",
        "valid_modes": [
            "page",
            "window",
            "section",
            "outline",
            "full_if_small",
        ],
    }
