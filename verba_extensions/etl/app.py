"""
Minisserviço de Ingestão Verba A2
Interface leve para ingestão direta no Weaviate com ETL opcional
"""

import os, json, hashlib, re, asyncio, datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .deps import get_weaviate
from .fetcher import fetch_url_to_text
from .chunker import split_into_passages
from .etl_a2 import run_etl_patch_for_passage_uuids
from .utils import url_host, sha1

TENANT_DEFAULT = os.getenv("WEAVIATE_TENANT", "news_v1")
ETL_ON_INGEST = os.getenv("ETL_ON_INGEST", "true").lower() == "true"
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://weaviate:8080")

app = FastAPI(title="Verba A2 Ingestor", version="1.0.0")

# Templates
templates_dir = Path(__file__).parent / "templates"
if templates_dir.exists():
    templates = Jinja2Templates(directory=str(templates_dir))
else:
    templates = None

# Estado simples (em produção, use Redis ou similar)
STATE = {"jobs": [], "last": None, "queue": []}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if templates:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "tenant": TENANT_DEFAULT,
            "weaviate_url": WEAVIATE_URL
        })
    return HTMLResponse("""
    <html>
    <head><title>Verba A2 Ingestor</title></head>
    <body>
        <h1>Verba A2 Ingestor</h1>
        <p>Use POST /ingest/urls ou POST /ingest/results</p>
        <p>GET /status para status</p>
    </body>
    </html>
    """)

@app.get("/status")
async def status():
    return {
        "tenant": TENANT_DEFAULT,
        "weaviate_url": WEAVIATE_URL,
        "etl_on_ingest": ETL_ON_INGEST,
        "jobs": STATE["jobs"][-20:],
        "last": STATE["last"],
        "queue_size": len(STATE["queue"])
    }

@app.post("/ingest/urls")
async def ingest_urls(payload: Dict[str, Any]):
    """Ingere URLs diretamente no Weaviate"""
    urls: List[str] = payload.get("urls") or []
    tenant = payload.get("tenant") or TENANT_DEFAULT
    run_etl = bool(payload.get("run_etl", ETL_ON_INGEST))
    language_hint = payload.get("language_hint") or "und"
    batch_tag = payload.get("batch_tag") or f"batch_{datetime.datetime.utcnow().isoformat()}"
    
    client = get_weaviate()
    art_coll = client.collections.get("Article")
    pas_coll = client.collections.get("Passage")
    
    created_articles, created_passages, passage_uuids = 0, 0, []
    
    for url in urls:
        try:
            text, meta = await fetch_url_to_text(url)
            if not text:
                text = f"(Stub) conteúdo não extraído; URL: {url}"
            
            aid = sha1(url)
            art_props = {
                "article_id": aid,
                "url_final": url,
                "source_domain": url_host(url),
                "title": meta.get("title") or "",
                "language": meta.get("language") or language_hint,
                "published_at": meta.get("published_at") or "",
                "batch_tag": batch_tag
            }
            
            art_uuid = art_coll.data.insert(properties=art_props, tenant=tenant)
            created_articles += 1
            
            for section_title, section_first_para, chunk in split_into_passages(text):
                props = {
                    "text": chunk,
                    "language": art_props["language"],
                    "meta_tenant": tenant,
                    "etl_version": "seed_v0",
                    "text_hash": sha1(chunk),
                    "section_title": section_title or "",
                    "section_first_para": section_first_para or "",
                    "batch_tag": batch_tag
                }
                
                res = pas_coll.data.insert(
                    properties=props,
                    references={"article_ref": [{"from": "Passage", "to": art_uuid}]},
                    tenant=tenant
                )
                passage_uuids.append(res.uuid)
                created_passages += 1
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Erro ao processar URL {url}: {str(e)}"}
            )
    
    # Roda ETL A2 se solicitado
    if run_etl and passage_uuids:
        try:
            await run_etl_patch_for_passage_uuids(get_weaviate, passage_uuids, tenant)
        except Exception as e:
            # Log mas não falha a ingestão
            print(f"Erro no ETL (não crítico): {str(e)}")
    
    STATE["last"] = {
        "articles": created_articles,
        "passages": created_passages,
        "etl": run_etl,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    return {
        "ok": True,
        "articles": created_articles,
        "passages": created_passages,
        "etl_run": run_etl,
        "passage_uuids_count": len(passage_uuids)
    }

@app.post("/ingest/results")
async def ingest_results(payload: Dict[str, Any]):
    """Ingere resultados já processados (content já extraído)"""
    items = payload.get("results") or []
    tenant = payload.get("tenant") or TENANT_DEFAULT
    run_etl = bool(payload.get("run_etl", ETL_ON_INGEST))
    batch_tag = payload.get("batch_tag") or f"batch_{datetime.datetime.utcnow().isoformat()}"
    
    client = get_weaviate()
    art_coll = client.collections.get("Article")
    pas_coll = client.collections.get("Passage")
    
    created_articles, created_passages, passage_uuids = 0, 0, []
    
    for it in items:
        try:
            url = it.get("url") or ""
            content = (it.get("content") or "").strip() or f"(Stub) sem conteúdo; URL: {url}"
            title = it.get("title") or ""
            meta = it.get("metadata") or {}
            lang = meta.get("language") or "und"
            published = it.get("published_at") or meta.get("published_at") or ""
            
            aid = sha1(url or title)
            art_props = {
                "article_id": aid,
                "url_final": url,
                "source_domain": url_host(url),
                "title": title,
                "language": lang,
                "published_at": published,
                "batch_tag": batch_tag
            }
            
            art_uuid = art_coll.data.insert(properties=art_props, tenant=tenant)
            created_articles += 1
            
            for section_title, section_first_para, chunk in split_into_passages(content):
                props = {
                    "text": chunk,
                    "language": lang,
                    "meta_tenant": tenant,
                    "etl_version": "seed_v0",
                    "text_hash": sha1(chunk),
                    "section_title": section_title or "",
                    "section_first_para": section_first_para or "",
                    "batch_tag": batch_tag
                }
                
                res = pas_coll.data.insert(
                    properties=props,
                    references={"article_ref": [{"from": "Passage", "to": art_uuid}]},
                    tenant=tenant
                )
                passage_uuids.append(res.uuid)
                created_passages += 1
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Erro ao processar item: {str(e)}"}
            )
    
    if run_etl and passage_uuids:
        try:
            await run_etl_patch_for_passage_uuids(get_weaviate, passage_uuids, tenant)
        except Exception as e:
            print(f"Erro no ETL (não crítico): {str(e)}")
    
    STATE["last"] = {
        "articles": created_articles,
        "passages": created_passages,
        "etl": run_etl,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    return {
        "ok": True,
        "articles": created_articles,
        "passages": created_passages,
        "etl_run": run_etl,
        "passage_uuids_count": len(passage_uuids)
    }

@app.post("/etl/patch")
async def etl_patch(payload: Dict[str, Any]):
    """Reprocessa ETL A2 em lote"""
    tenant = payload.get("tenant") or TENANT_DEFAULT
    limit = int(payload.get("limit", 500))
    since = payload.get("since")
    
    client = get_weaviate()
    pas_coll = client.collections.get("Passage")
    
    res = pas_coll.query.fetch_objects(limit=limit, tenant=tenant)
    uuids = [o.uuid for o in res.objects]
    
    try:
        await run_etl_patch_for_passage_uuids(get_weaviate, uuids, tenant)
        return {"ok": True, "processed": len(uuids)}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "processed": 0}
        )

@app.on_event("startup")
async def startup():
    """Verifica conexão com Weaviate no startup"""
    try:
        client = get_weaviate()
        if await client.is_ready():
            print(f"✅ Conectado ao Weaviate: {WEAVIATE_URL}")
        else:
            print(f"⚠️ Weaviate não está pronto: {WEAVIATE_URL}")
    except Exception as e:
        print(f"⚠️ Erro ao conectar Weaviate: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

