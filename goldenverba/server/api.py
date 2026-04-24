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
    DocumentSearchFilters,
    DocumentByFrameworkPayload,
    DocumentByCompanyPayload,
    DocumentBySectorPayload,
    SetThemeConfigPayload,
    SetUserConfigPayload,
    SearchQueryPayload,
    SetRAGConfigPayload,
    GetChunkPayload,
    GetVectorPayload,
    DataBatchPayload,
    ChunksPayload,
    FileStatus,
    GetRerankerPresetsPayload,
    ApplyRerankerPresetPayload,
    GetPresetConfigPayload,
    ExternalQueryPayload,
    SearchDocumentsForAgentsPayload,
    ReadDocumentForAgentsPayload,
    ReadContextAroundPayload,
)

load_dotenv()

# ============================================================================
# SEMÁFORO PARA CONTROLAR IMPORTS SEQUENCIAIS
# ============================================================================
# Limita a 1 import por vez para evitar race conditions quando múltiplos
# arquivos são enviados em rápida sequência
_import_semaphore = asyncio.Semaphore(1)

# ============================================================================

# Carrega extensões ANTES de criar managers
# Isso garante que plugins apareçam na lista de componentes
try:
    import verba_extensions.startup
    from verba_extensions.startup import initialize_extensions
    extension_loader, version_checker = initialize_extensions()
    if extension_loader:
        msg.good(f"Extensoes carregadas: {len(extension_loader.list_plugins())} plugins")
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

            def _extract_generator_iterative_config(rag_config):
                """Extract iterative search settings supporting both dict and object configs."""
                enabled = False
                max_iters = 3
                try:
                    generator_section = rag_config.get("Generator", {}) if isinstance(rag_config, dict) else getattr(rag_config, "Generator", {})

                    selected = None
                    components = {}
                    if isinstance(generator_section, dict):
                        selected = generator_section.get("selected")
                        components = generator_section.get("components", {})
                    else:
                        selected = getattr(generator_section, "selected", None)
                        components = getattr(generator_section, "components", {})

                    selected_component = components.get(selected) if isinstance(components, dict) else None
                    if selected_component is None:
                        return enabled, max_iters

                    if isinstance(selected_component, dict):
                        gen_cfg = selected_component.get("config", {})
                    else:
                        gen_cfg = getattr(selected_component, "config", {})

                    iter_cfg = gen_cfg.get("Enable Iterative Search", False) if isinstance(gen_cfg, dict) else False
                    max_cfg = gen_cfg.get("Max Iterative Searches", 3) if isinstance(gen_cfg, dict) else 3

                    if isinstance(iter_cfg, dict):
                        enabled = bool(iter_cfg.get("value", False))
                    elif hasattr(iter_cfg, "value"):
                        enabled = bool(iter_cfg.value)
                    else:
                        enabled = bool(iter_cfg)

                    if isinstance(max_cfg, dict):
                        max_iters = int(max_cfg.get("value", 3))
                    elif hasattr(max_cfg, "value"):
                        max_iters = int(max_cfg.value)
                    else:
                        max_iters = int(max_cfg)
                except Exception:
                    pass
                return enabled, max_iters
            
            # RAG 2.0: Check if iterative search is enabled
            enable_iterative, max_iterations = _extract_generator_iterative_config(payload.rag_config)
            
            if enable_iterative:
                msg.info(f"  🔄 Iterative Search enabled (max={max_iterations})")
                # We need a client connection for iterative search
                if payload.credentials:
                    creds = payload.credentials
                else:
                    creds = Credentials(
                        deployment=os.getenv("DEFAULT_DEPLOYMENT", "Local"),
                        url=os.getenv("WEAVIATE_URL_VERBA", ""),
                        key=os.getenv("WEAVIATE_API_KEY_VERBA", "")
                    )
                
                client = await client_manager.connect(creds)
                labels = payload.labels or []
                document_uuids = [doc.uuid for doc in (payload.documentFilter or [])]
                
                async for chunk in manager.generate_stream_answer_iterative(
                    client=client,
                    rag_config=payload.rag_config,
                    query=payload.query,
                    context=payload.context,
                    conversation=payload.conversation,
                    labels=labels,
                    document_uuids=document_uuids,
                    max_iterations=max_iterations,
                ):
                    full_text += chunk.get("message", "")
                    if chunk.get("finish_reason") == "stop":
                        chunk["full_text"] = full_text
                    await websocket.send_json(chunk)
            else:
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
                
                # Log file size information for debugging
                file_size_mb = (local_fileConfig.file_size / (1024 * 1024)) if hasattr(local_fileConfig, 'file_size') and local_fileConfig.file_size else 0
                msg.info(f"[IMPORT] File size: {file_size_mb:.1f}MB ({local_fileConfig.file_size} bytes)")
                msg.info(f"[IMPORT] Estimated processing time: {max(60, file_size_mb * 60)}s (~{max(1, file_size_mb)}m)")
                
                # Send STARTING status immediately to update frontend
                try:
                    await logger.send_report(
                        local_fileConfig.fileID,
                        status=FileStatus.STARTING,
                        message=f"Starting import ({file_size_mb:.1f}MB)...",
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
                        
                        # Calcular intervalo de keep-alive baseado no tamanho do arquivo
                        # Arquivos grandes precisam de mais frequência para evitar timeout
                        file_size_mb = (current_fileConfig.file_size / (1024 * 1024)) if hasattr(current_fileConfig, 'file_size') and current_fileConfig.file_size else 0
                        
                        if file_size_mb > 5:
                            keep_alive_interval = 1  # 1 segundo para arquivos > 5MB
                            msg.info(f"[KEEP-ALIVE] Arquivo grande ({file_size_mb:.1f}MB) - usando intervalo de 1s")
                        elif file_size_mb > 1:
                            keep_alive_interval = 2  # 2 segundos para arquivos > 1MB
                            msg.info(f"[KEEP-ALIVE] Arquivo médio ({file_size_mb:.1f}MB) - usando intervalo de 2s")
                        else:
                            keep_alive_interval = 5  # 5 segundos padrão
                            msg.info(f"[KEEP-ALIVE] Arquivo pequeno ({file_size_mb:.1f}MB) - usando intervalo padrão de 5s")
                        
                        # Estimativa de tempo total de processamento
                        # Baseado em benchmarks: ~100KB por segundo em média
                        estimated_seconds = max(60, file_size_mb * 60)  # Mínimo 60s
                        msg.info(f"[KEEP-ALIVE] Tempo estimado: {estimated_seconds}s ({estimated_seconds/60:.1f} minutos)")
                        
                        while True:
                            await asyncio.sleep(keep_alive_interval)
                            if websocket.application_state != WebSocketState.CONNECTED:
                                msg.warn(f"[KEEP-ALIVE] WebSocket desconectado")
                                break
                            try:
                                # Validate fileConfig before using
                                if current_fileConfig is None or not hasattr(current_fileConfig, 'fileID'):
                                    break
                                update_count += 1
                                elapsed_time = update_count * keep_alive_interval
                                
                                # Envia status de progresso para manter conexão viva e mostrar progresso
                                await logger.send_report(
                                    current_fileConfig.fileID,
                                    status=FileStatus.INGESTING,
                                    message=f"Processing ({elapsed_time}s / ~{estimated_seconds}s) - {file_size_mb:.1f}MB",
                                    took=0,
                                )
                            except Exception as e:
                                # Se falhar, para o keep-alive mas não quebra o import
                                msg.warn(f"[KEEP-ALIVE] Erro ao enviar keep-alive: {str(e)[:100]}")
                                break
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        msg.warn(f"[KEEP-ALIVE] Erro na task: {str(e)[:100]}")  # Silently handle keep-alive errors
                
                # Cria task de keep-alive
                keep_alive = asyncio.create_task(keep_alive_task())
                
                # Start import task in background - DON'T await it, let it run while we continue receiving batches
                # This allows multiple files to be imported sequentially
                # Use local_fileConfig to avoid race conditions
                async def import_with_cleanup():
                    """Wrapper para import com cleanup do keep-alive"""
                    import time
                    # Use local_fileConfig from outer scope (captured by closure)
                    current_fileConfig = local_fileConfig
                    
                    # SEMÁFORO: Aguarda que não haja outro import em progresso
                    # Isso evita race conditions quando múltiplos arquivos são enviados rapidamente
                    msg.info(f"[IMPORT] ⏳ Aguardando vez na fila (semáforo)... {current_fileConfig.filename[:50]}...")
                    async with _import_semaphore:
                        msg.info(f"[IMPORT] ✓ Adquiriu semáforo, iniciando import: {current_fileConfig.filename[:50]}...")
                        
                        start_time = time.time()
                        try:
                            # Validate fileConfig before using
                            if current_fileConfig is None or not hasattr(current_fileConfig, 'fileID') or not hasattr(current_fileConfig, 'filename'):
                                msg.fail(f"[IMPORT] ❌ Invalid fileConfig in import_with_cleanup: {type(current_fileConfig)}")
                                return
                            
                            msg.info(f"[IMPORT] 🚀 Starting import: {current_fileConfig.filename[:50]}...")
                            await manager.import_document(client, current_fileConfig, logger)
                        
                            elapsed_time = time.time() - start_time
                            msg.info(f"[IMPORT] ✅ Import completed: {current_fileConfig.filename[:50]}... (took {elapsed_time:.1f}s)")
                            
                            # Send completion status with timing info
                            try:
                                await logger.send_report(
                                    current_fileConfig.fileID,
                                    status=FileStatus.DONE,
                                    message=f"Import completed ({elapsed_time:.1f}s)",
                                    took=elapsed_time,
                                )
                            except Exception:
                                pass
                        except Exception as e:
                            elapsed_time = time.time() - start_time
                            # Validate fileConfig before using in error handling
                            file_id = "unknown"
                            filename = "unknown"
                            if current_fileConfig is not None and hasattr(current_fileConfig, 'fileID'):
                                file_id = current_fileConfig.fileID
                            if current_fileConfig is not None and hasattr(current_fileConfig, 'filename'):
                                filename = current_fileConfig.filename[:50] if len(current_fileConfig.filename) > 50 else current_fileConfig.filename
                            
                            msg.fail(f"[IMPORT] ❌ Import failed for {filename}... ({elapsed_time:.1f}s): {type(e).__name__}: {str(e)[:200]}")
                            # Try to send error report to client if WebSocket is still open
                            try:
                                await logger.send_report(
                                    file_id,
                                    status=FileStatus.ERROR,
                                    message=f"Import failed: {str(e)[:200]}",
                                    took=elapsed_time,
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


### RERANKER PRESETS ENDPOINTS


@app.post("/api/get_reranker_presets")
async def get_reranker_presets(payload: GetRerankerPresetsPayload):
    """Retorna lista de presets de reranker disponíveis com metadados."""
    try:
        presets = manager.get_reranker_presets()
        return JSONResponse(
            status_code=200,
            content={
                "presets": presets,
                "error": ""
            }
        )
    except Exception as e:
        msg.warn(f"Could not retrieve reranker presets: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "presets": [],
                "error": f"Could not retrieve reranker presets: {str(e)}",
            }
        )


@app.post("/api/apply_reranker_preset")
async def apply_reranker_preset(payload: ApplyRerankerPresetPayload):
    """Aplica preset de reranker ao RAG config."""
    if production == "Demo":
        return JSONResponse(
            content={
                "status": "200",
                "status_msg": "Config can't be updated in Production Mode",
            }
        )
    
    try:
        client = await client_manager.connect(payload.credentials)
        
        # Carrega config atual
        current_config = await manager.load_rag_config(client)
        
        # Obtém plugin reranker
        from verba_extensions.plugins.chunk_processor import get_chunk_processor
        chunk_processor = get_chunk_processor()
        reranker = None
        for plugin in chunk_processor.plugins:
            if plugin.name == "Reranker":
                reranker = plugin
                break
        
        if not reranker:
            return JSONResponse(
                status_code=404,
                content={
                    "status": 404,
                    "status_msg": "Reranker plugin not found",
                }
            )
        
        # Aplica preset
        if payload.preset_name == "auto" and payload.query:
            # Auto-seleção baseada na query
            selected_preset = reranker.select_optimal_preset(payload.query)
            applied_config = reranker.apply_preset(selected_preset)
        else:
            applied_config = reranker.apply_preset(payload.preset_name)
        
        # Atualiza config do retriever com preset aplicado
        if "Retriever" in current_config:
            retriever_config = current_config["Retriever"]
            if "components" in retriever_config:
                # IMPORTANTE: Muda o retriever selecionado para Entity-Aware
                # já que os presets são específicos para esse retriever
                if "Entity-Aware" in retriever_config["components"]:
                    retriever_config["selected"] = "Entity-Aware"
                
                # Encontra Entity-Aware retriever
                entity_aware = retriever_config["components"].get("Entity-Aware")
                if entity_aware and "config" in entity_aware:
                    # Atualiza config com valores do preset
                    for key, value in applied_config.items():
                        if key in entity_aware["config"]:
                            if isinstance(entity_aware["config"][key], dict):
                                entity_aware["config"][key]["value"] = value
                            else:
                                entity_aware["config"][key] = value
                    
                    # Atualiza "Reranker Preset" para o preset aplicado
                    preset_to_save = payload.preset_name
                    if payload.preset_name == "auto" and payload.query:
                        preset_to_save = reranker.select_optimal_preset(payload.query)
                    
                    if "Reranker Preset" in entity_aware["config"]:
                        if isinstance(entity_aware["config"]["Reranker Preset"], dict):
                            entity_aware["config"]["Reranker Preset"]["value"] = preset_to_save
                        else:
                            entity_aware["config"]["Reranker Preset"] = preset_to_save
        
        # Salva config atualizada
        await manager.set_rag_config(client, current_config)
        
        return JSONResponse(
            content={
                "status": 200,
                "preset_applied": preset_to_save if payload.preset_name == "auto" and payload.query else payload.preset_name,
                "config": applied_config
            }
        )
    except Exception as e:
        msg.warn(f"Failed to apply reranker preset: {str(e)}")
        return JSONResponse(
            content={
                "status": 400,
                "status_msg": f"Failed to apply reranker preset: {str(e)}",
            }
        )


@app.post("/api/get_preset_config")
async def get_preset_config(payload: GetPresetConfigPayload):
    """
    Retorna RAGConfig completo com preset aplicado ao EntityAware.
    
    Esta é a abordagem recomendada: o backend é o source of truth para presets.
    O frontend apenas aplica o config retornado via setRAGConfig().
    """
    try:
        client = await client_manager.connect(payload.credentials)
        
        # Carrega config atual
        current_config = await manager.load_rag_config(client)
        
        # Carrega presets disponíveis
        from verba_extensions.plugins.reranker import RerankerPresets
        presets = RerankerPresets.get_all_presets()
        
        preset_config = presets.get(payload.preset_name)
        if not preset_config:
            return JSONResponse(
                status_code=404,
                content={
                    "status": 404,
                    "status_msg": f"Preset '{payload.preset_name}' não encontrado",
                }
            )
        
        # Aplica preset ao EntityAware
        if "Retriever" in current_config:
            retriever_config = current_config["Retriever"]
            if "components" in retriever_config:
                # Muda selecionado para EntityAware
                if "EntityAware" in retriever_config["components"]:
                    retriever_config["selected"] = "EntityAware"
                    
                    entity_aware = retriever_config["components"]["EntityAware"]
                    if entity_aware and "config" in entity_aware:
                        # Aplica cada campo do preset
                        for key, value in preset_config.items():
                            # Skip metadados do preset
                            if key in ["name", "display_name", "description", 
                                       "latency_estimate", "quality_estimate", "requirements"]:
                                continue
                            
                            if key in entity_aware["config"]:
                                if isinstance(entity_aware["config"][key], dict):
                                    entity_aware["config"][key]["value"] = value
                                else:
                                    entity_aware["config"][key] = value
                        
                        # Marca qual preset está ativo
                        if "Reranker Preset" in entity_aware["config"]:
                            if isinstance(entity_aware["config"]["Reranker Preset"], dict):
                                entity_aware["config"]["Reranker Preset"]["value"] = payload.preset_name
                            else:
                                entity_aware["config"]["Reranker Preset"] = payload.preset_name
        
        msg.good(f"Preset '{payload.preset_name}' aplicado ao RAGConfig")
        
        return JSONResponse(
            content={
                "status": 200,
                "rag_config": current_config,
                "preset_applied": payload.preset_name,
            }
        )
    except Exception as e:
        msg.warn(f"Failed to get preset config: {str(e)}")
        return JSONResponse(
            content={
                "status": 400,
                "status_msg": f"Failed to get preset config: {str(e)}",
            }
        )


### RAG ENDPOINTS


# Receive query and return chunks and query answer
@app.post("/api/query")
async def query(payload: QueryPayload):
    msg.good(f"Received query: {payload.query}")
    try:
        # Validação básica do payload
        if not payload.query or not payload.query.strip():
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Query cannot be empty",
                    "documents": [],
                    "context": ""
                }
            )
        
        if not payload.RAG:
            return JSONResponse(
                status_code=422,
                content={
                    "error": "RAG configuration is required",
                    "documents": [],
                    "context": ""
                }
            )
        
        client = await client_manager.connect(payload.credentials)
        documents_uuid = [document.uuid for document in payload.documentFilter] if payload.documentFilter else []
        
        # ===================================================================
        # PRESET HANDLING: Aplicar preset se especificado
        # ===================================================================
        # Se o parâmetro 'preset' foi fornecido, carrega e aplica as configurações
        # do preset ao EntityAware Retriever antes de executar a busca.
        # Isso permite controle stateless de qual preset usar via API.
        # ===================================================================
        # Convert RAGConfig to dict to ensure consistent dictionary access throughout the code
        # Pydantic v2 uses model_dump(), v1 uses dict(). Supporting both just in case.
        # Also handling the case where payload.RAG is already a dict (runtime behavior)
        if isinstance(payload.RAG, dict):
            rag_config = payload.RAG
        elif hasattr(payload.RAG, "model_dump"):
            rag_config = payload.RAG.model_dump()
        else:
            rag_config = payload.RAG.dict()
            
        preset_applied = None
        
        if payload.preset:
            msg.info(f"🎯 Preset especificado: {payload.preset}")
            try:
                from verba_extensions.plugins.reranker import RerankerPresets
                presets = RerankerPresets.get_all_presets()
                
                preset_config = presets.get(payload.preset)
                if not preset_config:
                    # Tenta buscar pelo nome sem underscore
                    preset_config = presets.get(payload.preset.replace("-", "_").lower())
                
                if preset_config:
                    if "Retriever" in rag_config:
                        # Safe retrieval of Retriever component
                        retriever = rag_config.get("Retriever") if isinstance(rag_config, dict) else getattr(rag_config, "Retriever", None)

                        if retriever:
                            # Safe retrieval of components
                            components = retriever.get("components", {}) if isinstance(retriever, dict) else getattr(retriever, "components", {})
                            
                            # Detecta nome correto do componente (com ou sem hífen)
                            entity_aware_key = None
                            if "EntityAware" in components:
                                entity_aware_key = "EntityAware"
                            elif "Entity-Aware" in components:
                                entity_aware_key = "Entity-Aware"
                                
                            if entity_aware_key:
                                # Muda retriever selecionado para EntityAware
                                if isinstance(retriever, dict):
                                    retriever["selected"] = entity_aware_key
                                else:
                                    setattr(retriever, "selected", entity_aware_key)
                                
                                entity_aware = components[entity_aware_key]
                                ea_config = entity_aware.get("config", {}) if isinstance(entity_aware, dict) else getattr(entity_aware, "config", {})
                                
                                if ea_config:
                                    # Aplica cada campo do preset
                                    for key, value in preset_config.items():
                                        if key in ["name", "display_name", "description", 
                                                   "latency_estimate", "quality_estimate", "requirements"]:
                                            continue
                                            
                                        if key in ea_config:
                                            item = ea_config[key]
                                            # Handle InputConfig object (Pydantic) or dict with 'value' key
                                            if hasattr(item, "value"):
                                                item.value = value
                                            elif isinstance(item, dict) and "value" in item:
                                                item["value"] = value
                                            else:
                                                ea_config[key] = value
                                    
                                    preset_applied = payload.preset
                                    msg.good(f"✅ Preset '{payload.preset}' aplicado com sucesso")
                            else:
                                msg.warn(f"⚠️ EntityAware não disponível no RAG config, preset ignorado")
                        else:
                            msg.warn(f"⚠️ Retriever não encontrado no RAG config, preset ignorado")
                else:
                    msg.warn(f"⚠️ Preset '{payload.preset}' não encontrado. Presets disponíveis: {list(presets.keys())}")
            except Exception as preset_error:
                msg.warn(f"⚠️ Erro ao aplicar preset '{payload.preset}': {str(preset_error)}")
        
        # Verificar se há chunks disponíveis antes de processar query
        try:
            # Safe access that handles both dict and Pydantic RAGComponentClass objects
            embedder_component = rag_config.get("Embedder") if isinstance(rag_config, dict) else getattr(rag_config, "Embedder", None)
            if embedder_component:
                if isinstance(embedder_component, dict):
                    embedder = embedder_component.get("selected", "")
                elif hasattr(embedder_component, "selected"):
                    embedder = embedder_component.selected
                else:
                    embedder = ""
            else:
                embedder = ""
            if embedder:
                from goldenverba.components.managers import WeaviateManager
                weaviate_manager = WeaviateManager()
                
                # FIX: Use verify_embedding_collection to properly populate the embedding_table
                # This ensures the collection name mapping is set up correctly before we try to access it
                if await weaviate_manager.verify_embedding_collection(client, embedder):
                    # Now embedding_table[embedder] has the correct collection name
                    collection_name = weaviate_manager.embedding_table.get(embedder)
                    if collection_name:
                        embedder_collection = client.collections.get(collection_name)
                        # Verifica se há chunks na collection
                        total_count = await embedder_collection.aggregate.over_all(total_count=True)
                        if total_count.total_count == 0:
                            msg.warn("No chunks available in database - cannot process query")
                            return JSONResponse(
                                content={
                                    "error": "No documents or chunks available in the database. Please import documents first.",
                                    "documents": [],
                                    "context": ""
                                }
                            )
        except Exception as check_error:
            # Não falha a query se a verificação der erro, apenas loga
            msg.warn(f"Could not verify chunks availability: {str(check_error)}")
        
        # Usa rag_config (que pode ter preset aplicado) em vez de payload.RAG
        result = await manager.retrieve_chunks(
            client, payload.query, rag_config, payload.labels, documents_uuid
        )
        
        # Lidar com retorno de 2 ou 3 elementos (compatibilidade)
        if len(result) == 3:
            documents, context, debug_info = result
            # Garantir que documents é uma lista
            if documents is None:
                documents = []
            response_content = {
                "error": "", 
                "documents": documents, 
                "context": context or "",
                "debug_info": debug_info
            }
            # Adiciona info de preset se foi aplicado
            if preset_applied:
                response_content["preset_applied"] = preset_applied
            return JSONResponse(content=response_content)
        else:
            documents, context = result
            # Garantir que documents é uma lista
            response_content = {"error": "", "documents": documents, "context": context or ""}
            if preset_applied:
                response_content["preset_applied"] = preset_applied
            
            # Temporary Debug for Presets
            if "preset_debug" in locals():
                response_content["preset_debug"] = preset_debug
                
            return JSONResponse(content=response_content)
    except Exception as e:
        msg.fail(f"Query failed: {str(e)}")
        import traceback
        msg.fail(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(
            content={"error": str(e), "documents": [], "context": ""}
        )


# =============================================================================
# AGENT TOOLS: grouped search and controlled document read
# =============================================================================


@app.post("/api/agent/search_documents")
async def agent_search_documents(payload: SearchDocumentsForAgentsPayload):
    try:
        if not payload.query or not str(payload.query).strip():
            return JSONResponse(
                status_code=422,
                content={"error": "Query cannot be empty", "documents": []},
            )
        if isinstance(payload.RAG, dict):
            rag_config = payload.RAG
        elif hasattr(payload.RAG, "model_dump"):
            rag_config = payload.RAG.model_dump()
        else:
            rag_config = payload.RAG.dict()

        if payload.preset:
            from verba_extensions.tools.rag_preset import apply_reranker_preset_to_rag
            apply_reranker_preset_to_rag(rag_config, payload.preset)

        client = await client_manager.connect(payload.credentials)
        documents_uuid = [d.uuid for d in payload.documentFilter] if payload.documentFilter else []
        from verba_extensions.tools.document_reader import search_documents_grouped
        out = await search_documents_grouped(
            manager,
            client,
            payload.query,
            rag_config,
            payload.labels,
            documents_uuid,
            limit_docs=max(1, min(100, int(payload.limit_docs or 20))),
            top_hits_per_doc=max(1, min(20, int(payload.top_hits_per_doc or 5))),
        )
        if out.get("error"):
            return JSONResponse(status_code=422, content=out)
        return JSONResponse(content={"error": "", **out})
    except Exception as e:
        msg.fail(f"agent_search_documents failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "documents": []},
        )


@app.post("/api/agent/read_document")
async def agent_read_document(payload: ReadDocumentForAgentsPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        from verba_extensions.tools.document_reader import read_document_controlled
        out = await read_document_controlled(
            manager.weaviate_manager,
            client,
            payload.doc_uuid,
            payload.mode,
            page=payload.page,
            page_size=payload.page_size,
            section=payload.section,
            chunk_id_center=payload.chunk_id,
            radius=payload.radius,
            max_chars=max(1000, int(payload.max_chars or 50_000)),
        )
        if out.get("error") and "document not found" in str(out.get("error", "")):
            return JSONResponse(status_code=404, content=out)
        if out.get("error") and "unknown mode" in str(out.get("error", "")).lower():
            return JSONResponse(status_code=400, content=out)
        if out.get("error"):
            return JSONResponse(status_code=422, content=out)
        return JSONResponse(content={"error": "", **out})
    except Exception as e:
        msg.fail(f"agent_read_document failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.post("/api/agent/read_context_around")
async def agent_read_context_around(payload: ReadContextAroundPayload):
    try:
        client = await client_manager.connect(payload.credentials)
        from verba_extensions.tools.document_reader import read_context_around_chunk
        out = await read_context_around_chunk(
            manager.weaviate_manager,
            client,
            payload.doc_uuid,
            payload.chunk_id,
            radius=payload.radius,
        )
        if out.get("error"):
            st = 404 if "not found" in str(out.get("error", "")) else 422
            return JSONResponse(status_code=st, content=out)
        return JSONResponse(content={"error": "", **out})
    except Exception as e:
        msg.fail(f"agent_read_context_around failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


# =============================================================================
# EXTERNAL API ENDPOINT - Full functionality for external system integration
# =============================================================================

@app.post("/api/external/query")
async def external_query(payload: ExternalQueryPayload):
    """
    Endpoint para acesso externo completo à API de busca.
    
    Este endpoint carrega automaticamente o RAG config do servidor,
    mantendo todas as capacidades avançadas de retrieval e reranking
    do EntityAware Retriever.
    
    Args:
        query: Texto da busca
        preset: (Optional) speed, balanced, max_quality,
                consulting_frameworks, company_research, sector_analysis
        labels: (Optional) Labels para filtrar documentos
        documentFilter: (Optional) Filtros de documentos específicos
        credentials: Credenciais de conexão
    
    Returns:
        documents: Lista de documentos/chunks encontrados
        context: Contexto agregado para RAG
        preset_applied: Nome do preset aplicado (se houver)
    """
    msg.good(f"[EXTERNAL] Received query: {payload.query}")
    try:
        # Validação básica
        if not payload.query or not payload.query.strip():
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Query cannot be empty",
                    "documents": [],
                    "context": ""
                }
            )
        
        # Conectar ao Weaviate
        client = await client_manager.connect(payload.credentials)
        
        # IMPORTANTE: Carregar RAG config do servidor
        # Isso garante que temos a estrutura completa com todos os campos obrigatórios
        rag_config = await manager.load_rag_config(client)
        
        if not rag_config:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Failed to load RAG configuration from server",
                    "documents": [],
                    "context": ""
                }
            )
        
        msg.info(f"[EXTERNAL] Loaded RAG config with components: {list(rag_config.keys())}")
        
        # Processar filtros
        documents_uuid = []
        if payload.documentFilter:
            documents_uuid = [doc.uuid for doc in payload.documentFilter]
        
        labels = payload.labels or []
        
        # Aplicar preset se especificado
        preset_applied = None
        if payload.preset:
            msg.info(f"[EXTERNAL] Applying preset: {payload.preset}")
            try:
                from verba_extensions.plugins.reranker import RerankerPresets
                presets = RerankerPresets.get_all_presets()
                
                preset_config = presets.get(payload.preset)
                if not preset_config:
                    # Tenta buscar pelo nome normalizado
                    preset_config = presets.get(payload.preset.replace("-", "_").lower())
                
                if preset_config:
                    if "Retriever" in rag_config:
                        retriever = rag_config["Retriever"]
                        components = retriever.get("components", {})
                        
                        # Encontrar EntityAwareRetriever
                        entity_aware_key = None
                        for key in components:
                            if "EntityAware" in key or "entity_aware" in key.lower():
                                entity_aware_key = key
                                break
                        
                        if entity_aware_key:
                            entity_config = components[entity_aware_key].get("config", {})
                            
                            # Aplicar configurações do preset
                            preset_settings = preset_config.get("settings", {})
                            for setting_name, setting_value in preset_settings.items():
                                if setting_name in entity_config:
                                    entity_config[setting_name]["value"] = setting_value
                            
                            preset_applied = payload.preset
                            msg.good(f"[EXTERNAL] Preset '{payload.preset}' applied successfully")
                else:
                    msg.warn(f"[EXTERNAL] Preset '{payload.preset}' not found")
                    
            except Exception as preset_error:
                msg.warn(f"[EXTERNAL] Failed to apply preset: {str(preset_error)}")
        
        # Executar busca com todas as capacidades avançadas
        result = await manager.retrieve_chunks(
            client, payload.query, rag_config, labels, documents_uuid
        )
        
        # Processar resultado (compatível com 2 ou 3 elementos)
        if len(result) == 3:
            documents, context, debug_info = result
            response_content = {
                "error": "",
                "documents": documents or [],
                "context": context or "",
                "debug_info": debug_info
            }
        else:
            documents, context = result
            response_content = {
                "error": "",
                "documents": documents or [],
                "context": context or ""
            }
        
        if preset_applied:
            response_content["preset_applied"] = preset_applied
        
        msg.good(f"[EXTERNAL] Query completed: {len(response_content.get('documents', []))} documents found")
        return JSONResponse(content=response_content)
        
    except Exception as e:
        msg.fail(f"[EXTERNAL] Query failed: {str(e)}")
        import traceback
        msg.fail(f"[EXTERNAL] Traceback: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
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

# Helper function para buscar documentos por propriedade (framework, company, sector)
async def _get_documents_by_property(
    property_name: str,  # "frameworks", "companies", "sectors"
    property_value: str,
    client: WeaviateAsyncClient,
    weaviate_manager,
    embedder: str = None
) -> dict:
    """
    Helper para buscar documentos que contêm uma propriedade específica.
    
    Args:
        property_name: Nome da propriedade ("frameworks", "companies", "sectors")
        property_value: Valor a buscar (ex: "SWOT Analysis", "Apple")
        client: Cliente Weaviate
        weaviate_manager: Instância do WeaviateManager
        embedder: Nome do embedder (opcional, usa padrão se None)
    
    Returns:
        Dict com informações dos documentos encontrados
    """
    from verba_extensions.utils.aggregation_wrapper import get_aggregation_wrapper
    from verba_extensions.compatibility.weaviate_imports import Filter
    
    # Obter collection name
    if embedder:
        normalized = weaviate_manager._normalize_embedder_name(embedder)
        collection_name = weaviate_manager.embedding_table.get(embedder, f"VERBA_Embedding_{normalized}")
    else:
        # Usar primeiro embedder disponível como padrão
        if not weaviate_manager.embedding_table:
            return {
                "error": "Nenhum embedder configurado",
                "total_documents": 0,
                "total_chunks": 0,
                "documents": []
            }
        collection_name = list(weaviate_manager.embedding_table.values())[0]
    
    # Verificar se collection existe
    try:
        if not await client.collections.exists(collection_name):
            return {
                "error": f"Collection {collection_name} não encontrada",
                "total_documents": 0,
                "total_chunks": 0,
                "documents": []
            }
    except Exception as e:
        return {
            "error": f"Erro ao verificar collection: {str(e)}",
            "total_documents": 0,
            "total_chunks": 0,
            "documents": []
        }
    
    # Executar aggregation com filtro
    aggregation_wrapper = get_aggregation_wrapper()
    result = await aggregation_wrapper.aggregate_with_filters(
        client=client,
        collection_name=collection_name,
        filters=Filter.by_property(property_name).contains_any([property_value]),
        group_by=["doc_uuid"],
        total_count=True,
        use_http_fallback=True
    )
    
    # Buscar títulos dos documentos
    documents = []
    
    # Lidar com resultado do SDK (objeto) ou HTTP fallback (dict)
    groups = []
    total_chunks = 0
    
    if hasattr(result, 'groups'):
        # Resultado do SDK (objeto)
        groups = result.groups
        total_chunks = result.total_count if hasattr(result, 'total_count') else 0
    elif isinstance(result, dict) and 'data' in result:
        # Resultado do HTTP fallback (formato GraphQL)
        groups = result.get('data', {}).get('Aggregate', {}).get(collection_name, [])
        total_chunks = result.get('data', {}).get('Aggregate', {}).get('meta', {}).get('count', 0)
    elif isinstance(result, dict) and 'groups' in result:
        # Resultado do HTTP fallback (formato direto)
        groups = result.get('groups', [])
        total_chunks = result.get('total_count', 0)
    
    for group in groups:
        # Extrair doc_uuid (pode ser objeto ou dict)
        if isinstance(group, dict):
            grouped_by = group.get('groupedBy', {})
            if isinstance(grouped_by, dict):
                doc_uuid = grouped_by.get('value') or grouped_by.get('doc_uuid')
            else:
                doc_uuid = str(grouped_by)
            chunk_count = group.get('total_count') or group.get('count', 0)
        else:
            # Objeto do SDK
            doc_uuid = group.grouped_by.value if hasattr(group.grouped_by, 'value') else str(group.grouped_by)
            chunk_count = group.total_count if hasattr(group, 'total_count') else (group.count if hasattr(group, 'count') else 0)
        
        if not doc_uuid:
            continue
        
        # Buscar documento
        doc = await weaviate_manager.get_document(client, doc_uuid)
        if doc:
            documents.append({
                "doc_uuid": str(doc_uuid),
                "title": doc.get("title", "Sem título"),
                "chunk_count": chunk_count,
                "metadata": doc.get("metadata", {})
            })
    
    return {
        property_name: property_value,
        "total_documents": len(documents),
        "total_chunks": total_chunks,
        "documents": documents
    }


@app.post("/api/documents/by-framework/{framework}")
async def get_documents_by_framework(
    framework: str,
    payload: DocumentByFrameworkPayload
):
    """
    Lista documentos que contêm um framework específico.
    
    Args:
        framework: Nome do framework (ex: "SWOT Analysis")
        credentials: Credenciais do Weaviate
    
    Returns:
    {
        "framework": "SWOT Analysis",
        "total_documents": 5,
        "total_chunks": 23,
        "documents": [
            {
                "doc_uuid": "...",
                "title": "Análise Estratégica",
                "chunk_count": 5,
                "metadata": {...}
            }
        ]
    }
    """
    try:
        client = await client_manager.connect(payload.credentials)
        result = await _get_documents_by_property(
            property_name="frameworks",
            property_value=framework,
            client=client,
            weaviate_manager=manager.weaviate_manager
        )
        return JSONResponse(content=result)
    except Exception as e:
        msg.warn(f"Erro ao buscar documentos por framework: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "framework": framework,
                "total_documents": 0,
                "total_chunks": 0,
                "documents": []
            }
        )


@app.post("/api/documents/by-company/{company}")
async def get_documents_by_company(
    company: str,
    payload: DocumentByCompanyPayload
):
    """
    Lista documentos que mencionam uma empresa específica.
    
    Args:
        company: Nome da empresa (ex: "Apple")
        credentials: Credenciais do Weaviate
    
    Returns:
        JSON com lista de documentos
    """
    try:
        client = await client_manager.connect(payload.credentials)
        result = await _get_documents_by_property(
            property_name="companies",
            property_value=company,
            client=client,
            weaviate_manager=manager.weaviate_manager
        )
        return JSONResponse(content=result)
    except Exception as e:
        msg.warn(f"Erro ao buscar documentos por empresa: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "company": company,
                "total_documents": 0,
                "total_chunks": 0,
                "documents": []
            }
        )


@app.post("/api/documents/by-sector/{sector}")
async def get_documents_by_sector(
    sector: str,
    payload: DocumentBySectorPayload
):
    """
    Lista documentos que mencionam um setor específico.
    
    Args:
        sector: Nome do setor (ex: "technology")
        credentials: Credenciais do Weaviate
    
    Returns:
        JSON com lista de documentos
    """
    try:
        client = await client_manager.connect(payload.credentials)
        result = await _get_documents_by_property(
            property_name="sectors",
            property_value=sector,
            client=client,
            weaviate_manager=manager.weaviate_manager
        )
        return JSONResponse(content=result)
    except Exception as e:
        msg.warn(f"Erro ao buscar documentos por setor: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "sector": sector,
                "total_documents": 0,
                "total_chunks": 0,
                "documents": []
            }
        )


@app.post("/api/documents/search")
async def search_documents(
    payload: DocumentSearchFilters
):
    """
    Busca documentos com múltiplos filtros.
    
    Body:
    {
        "frameworks": ["SWOT"],
        "companies": ["Apple"],
        "sectors": ["technology"],
        "limit": 10,
        "offset": 0
    }
    
    Returns:
        JSON com lista de documentos que atendem aos filtros
    """
    try:
        from verba_extensions.utils.aggregation_wrapper import get_aggregation_wrapper
        from verba_extensions.compatibility.weaviate_imports import Filter
        
        client = await client_manager.connect(payload.credentials)
        weaviate_manager = manager.weaviate_manager
        
        # Obter collection name (usar primeiro embedder disponível)
        if not weaviate_manager.embedding_table:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Nenhum embedder configurado",
                    "total_documents": 0,
                    "total_chunks": 0,
                    "documents": []
                }
            )
        
        collection_name = list(weaviate_manager.embedding_table.values())[0]
        
        # Construir filtros combinados
        framework_filters = []
        if payload.frameworks:
            framework_filters.append(
                Filter.by_property("frameworks").contains_any(payload.frameworks)
            )
        if payload.companies:
            framework_filters.append(
                Filter.by_property("companies").contains_any(payload.companies)
            )
        if payload.sectors:
            framework_filters.append(
                Filter.by_property("sectors").contains_any(payload.sectors)
            )
        
        # Combinar filtros (AND - todos devem estar presentes)
        combined_filter = None
        if len(framework_filters) == 1:
            combined_filter = framework_filters[0]
        elif len(framework_filters) > 1:
            combined_filter = Filter.all_of(framework_filters)
        
        if not combined_filter:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Nenhum filtro especificado",
                    "total_documents": 0,
                    "total_chunks": 0,
                    "documents": []
                }
            )
        
        # Executar aggregation
        aggregation_wrapper = get_aggregation_wrapper()
        result = await aggregation_wrapper.aggregate_with_filters(
            client=client,
            collection_name=collection_name,
            filters=combined_filter,
            group_by=["doc_uuid"],
            total_count=True,
            use_http_fallback=True
        )
        
        # Buscar títulos dos documentos
        documents = []
        
        # Lidar com resultado do SDK (objeto) ou HTTP fallback (dict)
        groups = []
        total_chunks = 0
        
        if hasattr(result, 'groups'):
            # Resultado do SDK (objeto)
            groups = result.groups
            total_chunks = result.total_count if hasattr(result, 'total_count') else 0
        elif isinstance(result, dict) and 'data' in result:
            # Resultado do HTTP fallback (formato GraphQL)
            groups = result.get('data', {}).get('Aggregate', {}).get(collection_name, [])
            total_chunks = result.get('data', {}).get('Aggregate', {}).get('meta', {}).get('count', 0)
        elif isinstance(result, dict) and 'groups' in result:
            # Resultado do HTTP fallback (formato direto)
            groups = result.get('groups', [])
            total_chunks = result.get('total_count', 0)
        
        # Aplicar paginação
        start_idx = payload.offset
        end_idx = start_idx + payload.limit
        groups_slice = groups[start_idx:end_idx] if groups else []
        
        for group in groups_slice:
            # Extrair doc_uuid (pode ser objeto ou dict)
            if isinstance(group, dict):
                grouped_by = group.get('groupedBy', {})
                if isinstance(grouped_by, dict):
                    doc_uuid = grouped_by.get('value') or grouped_by.get('doc_uuid')
                else:
                    doc_uuid = str(grouped_by)
                chunk_count = group.get('total_count') or group.get('count', 0)
            else:
                # Objeto do SDK
                doc_uuid = group.grouped_by.value if hasattr(group.grouped_by, 'value') else str(group.grouped_by)
                chunk_count = group.total_count if hasattr(group, 'total_count') else (group.count if hasattr(group, 'count') else 0)
            
            if not doc_uuid:
                continue
            
            # Buscar documento
            doc = await weaviate_manager.get_document(client, doc_uuid)
            if doc:
                documents.append({
                    "doc_uuid": str(doc_uuid),
                    "title": doc.get("title", "Sem título"),
                    "chunk_count": chunk_count,
                    "metadata": doc.get("metadata", {})
                })
        
        return JSONResponse(content={
            "filters": {
                "frameworks": payload.frameworks or [],
                "companies": payload.companies or [],
                "sectors": payload.sectors or []
            },
            "total_documents": len(groups),
            "total_chunks": total_chunks,
            "limit": payload.limit,
            "offset": payload.offset,
            "documents": documents
        })
        
    except Exception as e:
        msg.warn(f"Erro ao buscar documentos: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "total_documents": 0,
                "total_chunks": 0,
                "documents": []
            }
        )


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
        # Log para debug
        if payload.chunkScores:
            msg.info(f"get_content: {len(payload.chunkScores)} chunks, tipos: {[(cs.uuid, type(cs.chunk_id).__name__, cs.chunk_id) for cs in payload.chunkScores[:3]]}")
        else:
            msg.info(f"get_content: No chunkScores provided, will fetch chunks directly from document {payload.uuid}")
        
        client = await client_manager.connect(payload.credentials)
        content, maxPage = await manager.get_content(
            client, payload.uuid, payload.page - 1, payload.chunkScores or []
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
