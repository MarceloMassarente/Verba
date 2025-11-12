from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
import asyncio
import copy
import warnings

# Suppress websockets deprecation warnings from uvicorn
# This is a known issue: uvicorn uses websockets.legacy API which is deprecated
# The warning doesn't affect functionality and will be fixed in future uvicorn updates
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="uvicorn.protocols.websockets")
warnings.filterwarnings("ignore", message=".*websockets.legacy.*")
warnings.filterwarnings("ignore", message=".*remove second argument of ws_handler.*")
warnings.filterwarnings("ignore", message=".*WebSocketServerProtocol.*")

from goldenverba.server.helpers import LoggerManager, BatchManager
from weaviate.client import WeaviateAsyncClient

import os
from pathlib import Path

from dotenv import load_dotenv
from starlette.websockets import WebSocketDisconnect, WebSocketState
from wasabi import msg  # type: ignore[import]

# Fix: Adicionar método debug ao msg se não existir (compatibilidade)
# O objeto Printer do wasabi não tem método debug, mas alguns códigos podem tentar usá-lo
if not hasattr(msg, 'debug'):
    def debug_wrapper(*args, **kwargs):
        # Fallback para info se debug não existir
        msg.info(*args, **kwargs)
    msg.debug = debug_wrapper

from goldenverba import verba_manager

from goldenverba.server.types import (
    ResetPayload,
    QueryPayload,
    GeneratePayload,
    Credentials,
    GetDocumentPayload,
    ConnectPayload,
    DatacountPayload,
    GetSuggestionsPayload,
    GetAllSuggestionsPayload,
    DeleteSuggestionPayload,
    GetContentPayload,
    SetThemeConfigPayload,
    SetUserConfigPayload,
    SearchQueryPayload,
    SetRAGConfigPayload,
    GetChunkPayload,
    GetVectorPayload,
    DataBatchPayload,
    ChunksPayload,
    FileStatus,
)

load_dotenv()

# Carrega extensões ANTES de criar managers
# Isso garante que plugins apareçam na lista de componentes
try:
    import verba_extensions.startup
    from verba_extensions.startup import initialize_extensions
    plugin_manager, version_checker = initialize_extensions()
    if plugin_manager:
        msg.good(f"Extensoes carregadas: {len(plugin_manager.list_plugins())} plugins")
except ImportError:
    msg.info("Extensoes nao disponiveis (continuando sem extensoes)")
except Exception as e:
    msg.warn(f"Erro ao carregar extensoes: {str(e)} (continuando sem extensoes)")

# Check if runs in production
production_key = os.environ.get("VERBA_PRODUCTION")
tag = os.environ.get("VERBA_GOOGLE_TAG", "")


if production_key:
    msg.info(f"Verba runs in {production_key} mode")
    production = production_key
else:
    production = "Local"

manager = verba_manager.VerbaManager()

client_manager = verba_manager.ClientManager()

### Lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await client_manager.disconnect()


# FastAPI App
app = FastAPI(lifespan=lifespan)

# TelemetryMiddleware para observabilidade (RAG2)
try:
    from verba_extensions.middleware.telemetry import TelemetryMiddleware
    app.add_middleware(
        TelemetryMiddleware,
        enable_logging=True
    )
    msg.good("TelemetryMiddleware integrado - observabilidade ativada")
except ImportError:
    msg.info("TelemetryMiddleware não disponível (continuando sem telemetria)")
except Exception as e:
    msg.warn(f"Erro ao integrar TelemetryMiddleware: {str(e)} (continuando sem telemetria)")

# Allow requests only from the same origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # This will be restricted by the custom middleware
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom middleware to check if the request is from the same origin
@app.middleware("http")
async def check_same_origin(request: Request, call_next):
    # Allow public access to /api/health
    if request.url.path == "/api/health":
        return await call_next(request)

    origin = request.headers.get("origin")
    base_url_str = str(request.base_url).rstrip("/")
    
    # Get allowed origins from environment (for Railway, etc.)
    allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
    allowed_origins = []
    if allowed_origins_env:
        if allowed_origins_env == "*":
            # Allow all origins if explicitly set
            allowed_origins = ["*"]
        else:
            allowed_origins = [o.strip() for o in allowed_origins_env.split(",")]
    
    # Check if origin is allowed
    origin_allowed = False
    
    # Normalize URLs for comparison (remove scheme, trailing slash)
    def normalize_url(url):
        """Normalize URL for comparison (remove scheme, port, trailing slash)"""
        if not url:
            return ""
        # Remove scheme
        url = url.replace("https://", "").replace("http://", "")
        # Remove trailing slash
        url = url.rstrip("/")
        # Remove port if present
        if ":" in url and "/" in url:
            # Port is before first /
            parts = url.split("/", 1)
            if ":" in parts[0]:
                host_port = parts[0].split(":")[0]
                url = host_port + "/" + parts[1] if len(parts) > 1 else host_port
        elif ":" in url:
            url = url.split(":")[0]
        return url.lower()
    
    origin_normalized = normalize_url(origin)
    base_url_normalized = normalize_url(base_url_str)
    
    # Check exact match (normalized)
    if origin_normalized == base_url_normalized:
        origin_allowed = True
    # Check localhost (for development)
    elif origin and origin.startswith("http://localhost:") and request.base_url.hostname == "localhost":
        origin_allowed = True
    # Check allowed origins from env
    elif allowed_origins:
        if "*" in allowed_origins:
            origin_allowed = True
        elif origin:
            # Check if origin matches any allowed origin (normalized)
            for allowed in allowed_origins:
                if allowed == "*":
                    origin_allowed = True
                    break
                allowed_normalized = normalize_url(allowed)
                if origin_normalized == allowed_normalized or origin_normalized.startswith(allowed_normalized.rstrip("*")):
                    origin_allowed = True
                    break
    # Check if origin matches base URL domain (for Railway subdomain variations)
    if not origin_allowed and origin and base_url_str:
        base_host = request.base_url.hostname or ""
        origin_host = ""
        if "://" in origin:
            origin_host = origin.split("://")[1].split("/")[0].split(":")[0]
        # Allow if same hostname (ignoring scheme)
        if base_host and origin_host and base_host.lower() == origin_host.lower():
            origin_allowed = True
        # Allow if both on railway.app (same domain)
        elif base_host and origin_host and (base_host.endswith(".railway.app") and origin_host.endswith(".railway.app")):
            origin_allowed = True
    
    if origin_allowed:
        return await call_next(request)
    else:
        # Only apply restrictions to /api/ routes (except /api/health)
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Not allowed",
                    "details": {
                        "request_origin": origin,
                        "expected_origin": str(request.base_url),
                        "request_method": request.method,
                        "request_url": str(request.url),
                        "request_headers": dict(request.headers),
                        "expected_header": "Origin header matching the server's base URL or localhost",
                    },
                },
            )

        # Allow non-API routes to pass through
        return await call_next(request)


BASE_DIR = Path(__file__).resolve().parent

# Serve the assets (JS, CSS, images, etc.)
app.mount(
    "/static/_next",
    StaticFiles(directory=BASE_DIR / "frontend/out/_next"),
    name="next-assets",
)

# Serve the main page and other static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend/out"), name="app")


@app.get("/")
@app.head("/")
async def serve_frontend():
    return FileResponse(os.path.join(BASE_DIR, "frontend/out/index.html"))


### INITIAL ENDPOINTS


# Define health check endpoint
@app.get("/api/health")
async def health_check():

    await client_manager.clean_up()

    if production == "Local":
        deployments = await manager.get_deployments()
    else:
        deployments = {"WEAVIATE_URL_VERBA": "", "WEAVIATE_API_KEY_VERBA": ""}

    return JSONResponse(
        content={
            "message": "Alive!",
            "production": production,
            "gtag": tag,
            "deployments": deployments,
            "default_deployment": os.getenv("DEFAULT_DEPLOYMENT", ""),
        }
    )


@app.post("/api/connect")
async def connect_to_verba(payload: ConnectPayload):
    try:
        client = await client_manager.connect(payload.credentials, payload.port)
        if isinstance(
            client, WeaviateAsyncClient
        ):  # Check if client is an AsyncClient object
            config = await manager.load_rag_config(client)
            user_config = await manager.load_user_config(client)
            theme, themes = await manager.load_theme_config(client)
            return JSONResponse(
                status_code=200,
                content={
                    "connected": True,
                    "error": "",
                    "rag_config": config,
                    "user_config": user_config,
                    "theme": theme,
                    "themes": themes,
                },
            )
        else:
            raise TypeError(
                "Couldn't connect to Weaviate, client is not an AsyncClient object"
            )
    except Exception as e:
        msg.fail(f"Failed to connect to Weaviate {str(e)}")
        return JSONResponse(
            status_code=400,
            content={
                "connected": False,
                "error": f"Failed to connect to Weaviate {str(e)}",
                "rag_config": {},
                "theme": {},
                "themes": {},
            },
        )


### WEBSOCKETS


@app.websocket("/ws/generate_stream")
async def websocket_generate_stream(websocket: WebSocket):
    await websocket.accept()
    while True:  # Start a loop to keep the connection alive.
        try:
            data = await websocket.receive_text()
            # Parse and validate the JSON string using Pydantic model
            payload = GeneratePayload.model_validate_json(data)

            msg.good(f"Received generate stream call for {payload.query}")

            full_text = ""
            async for chunk in manager.generate_stream_answer(
                payload.rag_config,
                payload.query,
                payload.context,
                payload.conversation,
            ):
                full_text += chunk["message"]
                if chunk["finish_reason"] == "stop":
                    chunk["full_text"] = full_text
                await websocket.send_json(chunk)

        except WebSocketDisconnect:
            msg.warn("WebSocket connection closed by client.")
            break  # Break out of the loop when the client disconnects

        except Exception as e:
            msg.fail(f"WebSocket Error: {str(e)}")
            await websocket.send_json(
                {"message": e, "finish_reason": "stop", "full_text": str(e)}
            )
        msg.good("Succesfully streamed answer")


@app.websocket("/ws/import_files")
async def websocket_import_files(websocket: WebSocket):

    if production == "Demo":
        return

    await websocket.accept()
    msg.info("[WEBSOCKET] Import WebSocket connection accepted")
    logger = LoggerManager(websocket)
    batcher = BatchManager()

    while True:
        try:
            # Check WebSocket state before attempting to receive data
            if websocket.application_state != WebSocketState.CONNECTED:
                msg.info(f"[WEBSOCKET] WebSocket not connected (state: {websocket.application_state}), waiting for reconnection or closing...")
                await asyncio.sleep(1)
                # Check if there are incomplete batches that can still be processed
                if batcher.batches:
                    msg.warn(f"[WEBSOCKET] ⚠️ WebSocket disconnected but {len(batcher.batches)} batch(es) still incomplete - will wait briefly")
                    await asyncio.sleep(2)
                break
            
            data = await websocket.receive_text()
            # Drastically reduce logging to avoid Railway rate limit (500 logs/sec)
            # Only log first chunk, every 500th chunk, or last chunk
            try:
                batch_data = DataBatchPayload.model_validate_json(data)
                # Log only first chunk, every 500th chunk, or last chunk (reduced from 100 to 500)
                if batch_data.order == 0 or batch_data.order % 500 == 0 or batch_data.isLastChunk:
                    msg.info(f"[WEBSOCKET] Chunk {batch_data.order + 1}/{batch_data.total} for {batch_data.fileID[:50]}...")
            except Exception as e:
                import traceback
                msg.fail(f"[WEBSOCKET] Failed to parse batch data: {type(e).__name__}: {str(e)}")
                msg.fail(f"[WEBSOCKET] Data preview (first 200 chars): {data[:200]}")
                msg.fail(f"[WEBSOCKET] Traceback: {traceback.format_exc()}")
                raise
            
            fileConfig = batcher.add_batch(batch_data)
            
            # Log detalhado sobre status do batch
            if batch_data.isLastChunk:
                msg.info(f"[WEBSOCKET] Last chunk received (order {batch_data.order}, total {batch_data.total})")
                # Verifica se todos os chunks foram recebidos
                if batch_data.order + 1 != batch_data.total:
                    msg.warn(f"[WEBSOCKET] ⚠️ Last chunk order ({batch_data.order + 1}) doesn't match total ({batch_data.total})")
            
            if fileConfig is not None:
                # CRITICAL: Create a local copy of fileConfig to prevent race conditions
                # when multiple files are processed simultaneously. Each async task needs
                # its own copy to avoid None reference errors.
                local_fileConfig = copy.deepcopy(fileConfig)
                
                # Validate fileConfig before proceeding
                if local_fileConfig is None or not hasattr(local_fileConfig, 'fileID') or not hasattr(local_fileConfig, 'filename'):
                    msg.fail(f"[WEBSOCKET] ❌ Invalid fileConfig received: {type(local_fileConfig)}")
                    continue
                
                msg.info(f"[WEBSOCKET] ✅ FileConfig ready - starting import for: {local_fileConfig.filename[:50]}...")
                # Send STARTING status immediately to update frontend
                try:
                    await logger.send_report(
                        local_fileConfig.fileID,
                        status=FileStatus.STARTING,
                        message="Starting import...",
                        took=0,
                    )
                except Exception as e:
                    msg.warn(f"[IMPORT] Failed to send STARTING status (WebSocket may be closed): {str(e)}")
                
                # Get client and ensure it's connected
                client = await client_manager.connect(batch_data.credentials)
                if client is None:
                    raise Exception("Failed to connect to Weaviate")
                
                # Verify client is ready before import
                if not await client.is_ready():
                    msg.warn("Client not ready, reconnecting...")
                    client = await client_manager.connect(batch_data.credentials)
                    if client is None or not await client.is_ready():
                        raise Exception("Failed to reconnect to Weaviate")
                
                # Task de keep-alive para manter WebSocket vivo durante import longo
                # Use local_fileConfig to avoid race conditions
                async def keep_alive_task():
                    """Envia pings periódicos para manter WebSocket conectado"""
                    try:
                        update_count = 0
                        # Use local_fileConfig from outer scope (captured by closure)
                        current_fileConfig = local_fileConfig
                        while True:
                            await asyncio.sleep(5)  # Atualiza a cada 5 segundos (mais frequente)
                            if websocket.application_state != WebSocketState.CONNECTED:
                                break
                            try:
                                # Validate fileConfig before using
                                if current_fileConfig is None or not hasattr(current_fileConfig, 'fileID'):
                                    break
                                update_count += 1
                                # Envia status de progresso para manter conexão viva e mostrar progresso
                                await logger.send_report(
                                    current_fileConfig.fileID,
                                    status=FileStatus.INGESTING,
                                    message=f"Processando... ({update_count * 5}s)",
                                    took=0,
                                )
                            except Exception:
                                # Se falhar, para o keep-alive
                                break
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        pass  # Silently handle keep-alive errors
                
                # Cria task de keep-alive
                keep_alive = asyncio.create_task(keep_alive_task())
                
                # Start import task in background - DON'T await it, let it run while we continue receiving batches
                # This allows multiple files to be imported sequentially
                # Use local_fileConfig to avoid race conditions
                async def import_with_cleanup():
                    """Wrapper para import com cleanup do keep-alive"""
                    # Use local_fileConfig from outer scope (captured by closure)
                    current_fileConfig = local_fileConfig
                    try:
                        # Validate fileConfig before using
                        if current_fileConfig is None or not hasattr(current_fileConfig, 'fileID') or not hasattr(current_fileConfig, 'filename'):
                            msg.fail(f"[IMPORT] ❌ Invalid fileConfig in import_with_cleanup: {type(current_fileConfig)}")
                            return
                        
                        await manager.import_document(client, current_fileConfig, logger)
                        msg.info(f"[IMPORT] ✅ Import completed: {current_fileConfig.filename[:50]}...")
                    except Exception as e:
                        # Validate fileConfig before using in error handling
                        file_id = "unknown"
                        filename = "unknown"
                        if current_fileConfig is not None and hasattr(current_fileConfig, 'fileID'):
                            file_id = current_fileConfig.fileID
                        if current_fileConfig is not None and hasattr(current_fileConfig, 'filename'):
                            filename = current_fileConfig.filename[:50] if len(current_fileConfig.filename) > 50 else current_fileConfig.filename
                        
                        msg.fail(f"[IMPORT] ❌ Import failed for {filename}...: {type(e).__name__}: {str(e)}")
                        # Try to send error report to client if WebSocket is still open
                        try:
                            await logger.send_report(
                                file_id,
                                status=FileStatus.ERROR,
                                message=f"Import failed: {str(e)}",
                                took=0,
                            )
                        except Exception:
                            pass  # WebSocket may be closed, ignore
                    finally:
                        # Cancela keep-alive após import concluir
                        keep_alive.cancel()
                        try:
                            await keep_alive
                        except asyncio.CancelledError:
                            pass
                
                # Start import in background - continue loop to receive more batches
                asyncio.create_task(import_with_cleanup())

        except WebSocketDisconnect:
            msg.info("[WEBSOCKET] Client disconnected (normal during long imports)")
            # Verifica se há batches incompletos antes de fechar
            if batcher.batches:
                msg.warn(f"[WEBSOCKET] ⚠️ {len(batcher.batches)} batch(es) incomplete:")
                for fileID, batch_info in batcher.batches.items():
                    received = len(batch_info["chunks"].keys())
                    total = batch_info["total"]
                    msg.warn(f"[WEBSOCKET]   - {fileID[:50]}...: {received}/{total} chunks")
            # Don't break immediately - the import might still be running in background
            await asyncio.sleep(1)
            break
        except RuntimeError as e:
            error_str = str(e).lower()
            # Handle WebSocket state errors gracefully
            if "not connected" in error_str or "need to call" in error_str or "cannot call" in error_str:
                msg.info(f"[WEBSOCKET] WebSocket connection lost: {str(e)}")
                # Check if there are incomplete batches
                if batcher.batches:
                    msg.warn(f"[WEBSOCKET] ⚠️ {len(batcher.batches)} batch(es) incomplete")
                await asyncio.sleep(1)
                break
            else:
                # Other RuntimeErrors - log and break
                msg.fail(f"[WEBSOCKET] RuntimeError: {type(e).__name__}: {str(e)}")
                await asyncio.sleep(1)
                break
        except Exception as e:
            error_str = str(e).lower()
            # Check if it's a WebSocket-related error (desconexão é normal em imports longos)
            websocket_error_keywords = [
                "websocket",
                "not connected",
                "need to call",
                "cannot call",
                "connection closed",
                "connection lost",
                "close message has been sent"
            ]
            is_websocket_error = any(keyword in error_str for keyword in websocket_error_keywords)
            
            if is_websocket_error:
                # WebSocket desconectado - é comportamento esperado em imports longos
                # Não logar como erro crítico, apenas como info
                msg.info(f"[WEBSOCKET] Connection lost during import (normal for long imports): {type(e).__name__}: {str(e)}")
            else:
                # Outros erros - logar como erro
                msg.fail(f"[WEBSOCKET] Error: {type(e).__name__}: {str(e)}")
            
            # Try to notify client about the error if connection is still open
            # Mas não tentar se já sabemos que é erro de WebSocket desconectado
            if not is_websocket_error:
                try:
                    if websocket.application_state == WebSocketState.CONNECTED:
                        await logger.send_report(
                            "unknown",
                            status=FileStatus.ERROR,
                            message=f"WebSocket error: {str(e)}",
                            took=0,
                        )
                except Exception:
                    pass  # Connection already closed, ignore
            
            await asyncio.sleep(1)
            break


### CONFIG ENDPOINTS


# Get Configuration
@app.post("/api/get_rag_config")
async def retrieve_rag_config(payload: Credentials):
    try:
        client = await client_manager.connect(payload)
        config = await manager.load_rag_config(client)
        return JSONResponse(
            status_code=200, content={"rag_config": config, "error": ""}
        )

    except Exception as e:
        msg.warn(f"Could not retrieve configuration: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "rag_config": {},
                "error": f"Could not retrieve rag configuration: {str(e)}",
            },
        )


@app.post("/api/set_rag_config")
async def update_rag_config(payload: SetRAGConfigPayload):
    if production == "Demo":
        return JSONResponse(
            content={
                "status": "200",
                "status_msg": "Config can't be updated in Production Mode",
            }
        )

    try:
        client = await client_manager.connect(payload.credentials)
        await manager.set_rag_config(client, payload.rag_config.model_dump())
        return JSONResponse(
            content={
                "status": 200,
            }
        )
    except Exception as e:
        msg.warn(f"Failed to set new RAG Config {str(e)}")
        return JSONResponse(
            content={
                "status": 400,
                "status_msg": f"Failed to set new RAG Config {str(e)}",
            }
        )


@app.post("/api/get_user_config")
async def retrieve_user_config(payload: Credentials):
    try:
        client = await client_manager.connect(payload)
        config = await manager.load_user_config(client)
        return JSONResponse(
            status_code=200, content={"user_config": config, "error": ""}
        )

    except Exception as e:
        msg.warn(f"Could not retrieve user configuration: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "user_config": {},
                "error": f"Could not retrieve rag configuration: {str(e)}",
            },
        )


# Telemetry endpoints (RAG2)
@app.get("/api/telemetry/stats")
async def get_telemetry_stats():
    """Retorna estatísticas de telemetria da API"""
    try:
        from verba_extensions.middleware.telemetry import TelemetryMiddleware
        stats = TelemetryMiddleware.get_shared_stats()
        return JSONResponse(
            status_code=200,
            content={"stats": stats, "error": ""}
        )
    except ImportError:
        return JSONResponse(
            status_code=200,
            content={"stats": {}, "error": "TelemetryMiddleware não disponível"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"stats": {}, "error": f"Erro ao obter stats: {str(e)}"}
        )


@app.get("/api/telemetry/slo")
async def check_slo(threshold_ms: float = 350.0):
    """Verifica se SLO está sendo atendido (p95 < threshold_ms)"""
    try:
        from verba_extensions.middleware.telemetry import TelemetryMiddleware
        is_ok, details = TelemetryMiddleware.check_shared_slo(threshold_ms)
        return JSONResponse(
            status_code=200,
            content={
                "is_ok": is_ok,
                "threshold_ms": threshold_ms,
                **details,
                "error": ""
            }
        )
    except ImportError:
        return JSONResponse(
            status_code=200,
            content={"is_ok": False, "error": "TelemetryMiddleware não disponível"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"is_ok": False, "error": f"Erro ao verificar SLO: {str(e)}"}
        )


@app.post("/api/set_user_config")
async def update_user_config(payload: SetUserConfigPayload):
    if production == "Demo":
        return JSONResponse(
            content={
                "status": "200",
                "status_msg": "Config can't be updated in Production Mode",
            }
        )

    try:
        client = await client_manager.connect(payload.credentials)
        await manager.set_user_config(client, payload.user_config)
        return JSONResponse(
            content={
                "status": 200,
                "status_msg": "User config updated",
            }
        )
    except Exception as e:
        msg.warn(f"Failed to set new RAG Config {str(e)}")
        return JSONResponse(
            content={
                "status": 400,
                "status_msg": f"Failed to set new RAG Config {str(e)}",
            }
        )


# Get Configuration
@app.post("/api/get_theme_config")
async def retrieve_theme_config(payload: Credentials):
    try:
        client = await client_manager.connect(payload)
        theme, themes = await manager.load_theme_config(client)
        return JSONResponse(
            status_code=200, content={"theme": theme, "themes": themes, "error": ""}
        )

    except Exception as e:
        msg.warn(f"Could not retrieve configuration: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "theme": None,
                "themes": None,
                "error": f"Could not retrieve theme configuration: {str(e)}",
            },
        )


@app.post("/api/set_theme_config")
async def update_theme_config(payload: SetThemeConfigPayload):
    if production == "Demo":
        return JSONResponse(
            content={
                "status": "200",
                "status_msg": "Config can't be updated in Production Mode",
            }
        )

    try:
        client = await client_manager.connect(payload.credentials)
        await manager.set_theme_config(
            client, {"theme": payload.theme, "themes": payload.themes}
        )
        return JSONResponse(
            content={
                "status": 200,
            }
        )
    except Exception as e:
        msg.warn(f"Failed to set new RAG Config {str(e)}")
        return JSONResponse(
            content={
                "status": 400,
                "status_msg": f"Failed to set new RAG Config {str(e)}",
            }
        )


### RAG ENDPOINTS


# Receive query and return chunks and query answer
@app.post("/api/query")
async def query(payload: QueryPayload):
    msg.good(f"Received query: {payload.query}")
    try:
        client = await client_manager.connect(payload.credentials)
        documents_uuid = [document.uuid for document in payload.documentFilter]
        result = await manager.retrieve_chunks(
            client, payload.query, payload.RAG, payload.labels, documents_uuid
        )
        
        # Lidar com retorno de 2 ou 3 elementos (compatibilidade)
        if len(result) == 3:
            documents, context, debug_info = result
            return JSONResponse(
                content={
                    "error": "", 
                    "documents": documents, 
                    "context": context,
                    "debug_info": debug_info  # Informações de debug para exibir no frontend
                }
            )
        else:
            documents, context = result
            return JSONResponse(
                content={"error": "", "documents": documents, "context": context}
            )
    except Exception as e:
        msg.fail(f"Query failed: {str(e)}")
        return JSONResponse(
            content={"error": str(e), "documents": [], "context": ""}
        )


@app.post("/api/query/validate")
async def validate_query(payload: QueryPayload):
    """
    Valida query usando QueryBuilder antes de executar.
    Retorna query estruturada para validação do usuário.
    """
    try:
        client = await client_manager.connect(payload.credentials)
        
        # Obter collection name do embedder
        embedder_name = payload.RAG.get("Embedder", {}).get("selected", "")
        if not embedder_name:
            return JSONResponse(
                content={
                    "error": "Embedder não especificado",
                    "query_plan": None
                }
            )
        
        # Normalizar nome da collection
        from goldenverba.components.managers import WeaviateManager
        weaviate_manager = WeaviateManager()
        normalized = weaviate_manager._normalize_embedder_name(embedder_name)
        collection_name = f"VERBA_Embedding_{normalized}"
        
        # Usar QueryBuilder
        try:
            from verba_extensions.plugins.query_builder import QueryBuilderPlugin
            builder = QueryBuilderPlugin()
            
            query_plan = await builder.build_query(
                user_query=payload.query,
                client=client,
                collection_name=collection_name,
                use_cache=True,
                validate=True  # Modo validação
            )
            
            return JSONResponse(
                content={
                    "error": "",
                    "query_plan": query_plan,
                    "requires_validation": query_plan.get("requires_validation", False)
                }
            )
        except ImportError:
            return JSONResponse(
                content={
                    "error": "QueryBuilder não disponível",
                    "query_plan": None
                }
            )
        
    except Exception as e:
        msg.warn(f"Erro ao validar query: {str(e)}")
        return JSONResponse(
            content={
                "error": str(e),
                "query_plan": None
            }
        )


@app.post("/api/query/execute")
async def execute_validated_query(payload: QueryPayload):
    """
    Executa query já validada pelo usuário.
    Aceita query_plan opcional para usar filtros customizados.
    """
    msg.good(f"Executing validated query: {payload.query}")
    try:
        client = await client_manager.connect(payload.credentials)
        documents_uuid = [document.uuid for document in payload.documentFilter]
        
        # Se query_plan fornecido, usar filtros customizados
        # (Isso pode ser expandido no futuro)
        
        documents, context = await manager.retrieve_chunks(
            client, payload.query, payload.RAG, payload.labels, documents_uuid
        )

        return JSONResponse(
            content={"error": "", "documents": documents, "context": context}
        )
    except Exception as e:
        msg.warn(f"Query failed: {str(e)}")
        return JSONResponse(
            content={"error": f"Query failed: {str(e)}", "documents": [], "context": ""}
        )


@app.post("/api/query/aggregate")
async def aggregate_query(payload: QueryPayload):
    """
    Executa query de agregação usando GraphQL Builder.
    
    Payload:
    {
        "query": "quantos chunks têm Apple vs Microsoft",
        "RAG": {
            "Embedder": {"selected": "SentenceTransformers"},
            "Aggregation": {
                "type": "entity_stats",  # entity_stats, document_stats, multi_collection, complex_filter
                "filters": {"entities_local_ids": ["Q312"]},  # Opcional
                "group_by": ["doc_uuid"],  # Opcional
                "top_occurrences_limit": 10  # Opcional
            }
        },
        "credentials": {...}
    }
    """
    try:
        client = await client_manager.connect(payload.credentials)
        
        # Obter collection name do embedder
        embedder_name = payload.RAG.get("Embedder", {}).get("selected", "")
        if not embedder_name:
            return JSONResponse(
                content={
                    "error": "Embedder não especificado",
                    "results": None
                }
            )
        
        # Normalizar nome da collection
        from goldenverba.components.managers import WeaviateManager
        weaviate_manager = WeaviateManager()
        normalized = weaviate_manager._normalize_embedder_name(embedder_name)
        collection_name = weaviate_manager.embedding_table.get(embedder_name, f"VERBA_Embedding_{normalized}")
        
        # Extrair parâmetros de agregação do payload
        aggregation_config = payload.RAG.get("Aggregation", {})
        aggregation_type = aggregation_config.get("type", "entity_stats")
        filters = aggregation_config.get("filters")
        group_by = aggregation_config.get("group_by")
        top_occurrences_limit = aggregation_config.get("top_occurrences_limit", 10)
        
        # Usar QueryBuilder para construir query de agregação
        try:
            from verba_extensions.plugins.query_builder import QueryBuilderPlugin
            builder = QueryBuilderPlugin()
            
            query_info = await builder.build_aggregation_query(
                aggregation_type=aggregation_type,
                client=client,
                collection_name=collection_name,
                filters=filters,
                group_by=group_by,
                top_occurrences_limit=top_occurrences_limit
            )
            
            if "error" in query_info:
                return JSONResponse(
                    content={
                        "error": query_info["error"],
                        "results": None
                    }
                )
            
            # Executar query
            raw_results = await query_info["execute"]()
            
            # Parsear resultados
            parsed_results = query_info["parse"](raw_results)
            
            return JSONResponse(
                content={
                    "error": "",
                    "query": query_info["query"],
                    "results": parsed_results,
                    "raw_results": raw_results  # Para debug
                }
            )
            
        except ImportError:
            return JSONResponse(
                content={
                    "error": "QueryBuilder não disponível",
                    "results": None
                }
            )
        
    except Exception as e:
        msg.warn(f"Erro ao executar agregação: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            content={
                "error": str(e),
                "results": None
            }
        )


### DOCUMENT ENDPOINTS


# Retrieve specific document based on UUID
@app.post("/api/get_document")
async def get_document(payload: GetDocumentPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        document = await manager.weaviate_manager.get_document(
            client,
            payload.uuid,
            properties=[
                "title",
                "extension",
                "fileSize",
                "labels",
                "source",
                "meta",
                "metadata",
            ],
        )
        if document is not None:
            document["content"] = ""
            msg.good(f"Succesfully retrieved document: {document['title']}")
            return JSONResponse(
                content={
                    "error": "",
                    "document": document,
                }
            )
        else:
            msg.warn(f"Could't retrieve document")
            return JSONResponse(
                content={
                    "error": "Couldn't retrieve requested document",
                    "document": None,
                }
            )
    except Exception as e:
        msg.fail(f"Document retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "error": str(e),
                "document": None,
            }
        )


@app.post("/api/get_datacount")
async def get_document_count(payload: DatacountPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        document_uuids = [document.uuid for document in payload.documentFilter]
        datacount = await manager.weaviate_manager.get_datacount(
            client, payload.embedding_model, document_uuids
        )
        return JSONResponse(
            content={
                "datacount": datacount,
            }
        )
    except Exception as e:
        msg.fail(f"Document Count retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "datacount": 0,
            }
        )


@app.post("/api/get_labels")
async def get_labels(payload: Credentials):
    try:
        client = await client_manager.connect(payload)
        labels = await manager.weaviate_manager.get_labels(client)
        return JSONResponse(
            content={
                "labels": labels,
            }
        )
    except Exception as e:
        msg.fail(f"Document Labels retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "labels": [],
            }
        )


# Retrieve specific document based on UUID
@app.post("/api/get_content")
async def get_content(payload: GetContentPayload):
    try:
        # Validar chunkScores
        if not payload.chunkScores:
            msg.warn("No chunkScores provided")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "No chunks provided",
                    "content": None,
                }
            )
        
        # Log para debug
        msg.info(f"get_content: {len(payload.chunkScores)} chunks, tipos: {[(cs.uuid, type(cs.chunk_id).__name__, cs.chunk_id) for cs in payload.chunkScores[:3]]}")
        
        client = await client_manager.connect(payload.credentials)
        content, maxPage = await manager.get_content(
            client, payload.uuid, payload.page - 1, payload.chunkScores
        )
        msg.good(f"Succesfully retrieved content from {payload.uuid}")
        return JSONResponse(
            content={"error": "", "content": content, "maxPage": maxPage}
        )
    except Exception as e:
        # Log error - usar msg.warn se msg.fail não funcionar (compatibilidade)
        try:
            msg.fail(f"Document retrieval failed: {str(e)}")
        except AttributeError:
            # Fallback se msg não tiver método fail (compatibilidade)
            msg.warn(f"Document retrieval failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "document": None,
            }
        )


# Retrieve specific document based on UUID
@app.post("/api/get_vectors")
async def get_vectors(payload: GetVectorPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        vector_groups = await manager.weaviate_manager.get_vectors(
            client, payload.uuid, payload.showAll
        )
        return JSONResponse(
            content={
                "error": "",
                "vector_groups": vector_groups,
            }
        )
    except Exception as e:
        msg.fail(f"Vector retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "error": str(e),
                "payload": {"embedder": "None", "vectors": []},
            }
        )


# Retrieve specific document based on UUID
@app.post("/api/get_chunks")
async def get_chunks(payload: ChunksPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        chunks = await manager.weaviate_manager.get_chunks(
            client, payload.uuid, payload.page, payload.pageSize
        )
        return JSONResponse(
            content={
                "error": "",
                "chunks": chunks,
            }
        )
    except Exception as e:
        msg.fail(f"Chunk retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "error": str(e),
                "chunks": None,
            }
        )


# Retrieve specific document based on UUID
@app.post("/api/get_chunk")
async def get_chunk(payload: GetChunkPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        chunk = await manager.weaviate_manager.get_chunk(
            client, payload.uuid, payload.embedder
        )
        return JSONResponse(
            content={
                "error": "",
                "chunk": chunk,
            }
        )
    except Exception as e:
        msg.fail(f"Chunk retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "error": str(e),
                "chunk": None,
            }
        )


## Retrieve and search documents imported to Weaviate
@app.post("/api/get_all_documents")
async def get_all_documents(payload: SearchQueryPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        documents, total_count = await manager.weaviate_manager.get_documents(
            client,
            payload.query,
            payload.pageSize,
            payload.page,
            payload.labels,
            properties=["title", "extension", "fileSize", "labels", "source", "meta"],
        )
        labels = await manager.weaviate_manager.get_labels(client)

        msg.good(f"Succesfully retrieved document: {len(documents)} documents")
        return JSONResponse(
            content={
                "documents": documents,
                "labels": labels,
                "error": "",
                "totalDocuments": total_count,
            }
        )
    except Exception as e:
        msg.fail(f"Retrieving all documents failed: {str(e)}")
        return JSONResponse(
            content={
                "documents": [],
                "label": [],
                "error": f"All Document retrieval failed: {str(e)}",
                "totalDocuments": 0,
            }
        )


# Delete specific document based on UUID
@app.post("/api/delete_document")
async def delete_document(payload: GetDocumentPayload):
    if production == "Demo":
        msg.warn("Can't delete documents when in Production Mode")
        return JSONResponse(status_code=200, content={})

    try:
        client = await client_manager.connect(payload.credentials)
        msg.info(f"Deleting {payload.uuid}")
        await manager.weaviate_manager.delete_document(client, payload.uuid)
        return JSONResponse(status_code=200, content={})

    except Exception as e:
        msg.fail(f"Deleting Document with ID {payload.uuid} failed: {str(e)}")
        return JSONResponse(status_code=400, content={})


### ADMIN


@app.post("/api/reset")
async def reset_verba(payload: ResetPayload):
    if production == "Demo":
        return JSONResponse(status_code=200, content={})

    try:
        client = await client_manager.connect(payload.credentials)
        if payload.resetMode == "ALL":
            await manager.weaviate_manager.delete_all(client)
        elif payload.resetMode == "DOCUMENTS":
            await manager.weaviate_manager.delete_all_documents(client)
        elif payload.resetMode == "CONFIG":
            await manager.weaviate_manager.delete_all_configs(client)
        elif payload.resetMode == "SUGGESTIONS":
            await manager.weaviate_manager.delete_all_suggestions(client)

        msg.info(f"Resetting Verba in ({payload.resetMode}) mode")

        return JSONResponse(status_code=200, content={})

    except Exception as e:
        msg.warn(f"Failed to reset Verba {str(e)}")
        return JSONResponse(status_code=500, content={})


# Get Status meta data
@app.post("/api/get_meta")
async def get_meta(payload: Credentials):
    try:
        client = await client_manager.connect(payload)
        node_payload, collection_payload = await manager.weaviate_manager.get_metadata(
            client
        )
        return JSONResponse(
            content={
                "error": "",
                "node_payload": node_payload,
                "collection_payload": collection_payload,
            }
        )
    except Exception as e:
        return JSONResponse(
            content={
                "error": f"Couldn't retrieve metadata {str(e)}",
                "node_payload": {},
                "collection_payload": {},
            }
        )


### Suggestions


@app.post("/api/get_suggestions")
async def get_suggestions(payload: GetSuggestionsPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        suggestions = await manager.weaviate_manager.retrieve_suggestions(
            client, payload.query, payload.limit
        )
        return JSONResponse(
            content={
                "suggestions": suggestions,
            }
        )
    except Exception:
        return JSONResponse(
            content={
                "suggestions": [],
            }
        )


@app.post("/api/get_all_suggestions")
async def get_all_suggestions(payload: GetAllSuggestionsPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        suggestions, total_count = (
            await manager.weaviate_manager.retrieve_all_suggestions(
                client, payload.page, payload.pageSize
            )
        )
        return JSONResponse(
            content={
                "suggestions": suggestions,
                "total_count": total_count,
            }
        )
    except Exception:
        return JSONResponse(
            content={
                "suggestions": [],
                "total_count": 0,
            }
        )


@app.post("/api/delete_suggestion")
async def delete_suggestion(payload: DeleteSuggestionPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        await manager.weaviate_manager.delete_suggestions(client, payload.uuid)
        return JSONResponse(
            content={
                "status": 200,
            }
        )
    except Exception:
        return JSONResponse(
            content={
                "status": 400,
            }
        )
