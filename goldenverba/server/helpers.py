from fastapi import WebSocket
from starlette.websockets import WebSocketState
from goldenverba.server.types import (
    FileStatus,
    StatusReport,
    DataBatchPayload,
    FileConfig,
    CreateNewDocument,
)
from wasabi import msg


class LoggerManager:
    def __init__(self, socket: WebSocket = None):
        self.socket = socket

    def _is_websocket_ready(self) -> bool:
        """Verifica se WebSocket está pronto para enviar mensagens"""
        if self.socket is None:
            return False
        try:
            # Verifica estado da aplicação
            if self.socket.application_state != WebSocketState.CONNECTED:
                return False
            # Verifica se o WebSocket foi aceito (client_state)
            # Se client_state não for CONNECTED, o WebSocket não está pronto
            if hasattr(self.socket, 'client_state'):
                if self.socket.client_state != WebSocketState.CONNECTED:
                    return False
            return True
        except Exception:
            # Se houver qualquer erro ao verificar, assumir que não está pronto
            return False

    async def send_report(
        self, file_Id: str, status: FileStatus, message: str, took: float
    ):
        # Reduce logging frequency - only log important status changes
        if status in (FileStatus.STARTING, FileStatus.DONE, FileStatus.ERROR):
            msg.info(f"{status} | {file_Id} | {message} | {took}")
        # Skip logging for intermediate statuses to reduce log spam
        
        if self.socket is None:
            return
        
        # Try to send even if WebSocket check fails - the actual send will handle errors
        # This ensures progress updates are sent when possible
        try:
            payload: StatusReport = {
                "fileID": file_Id,
                "status": status,
                "message": message,
                "took": took,
            }
            # Attempt to send - don't pre-check, let the actual send handle errors
            await self.socket.send_json(payload)
        except (RuntimeError, ConnectionError, OSError) as e:
            error_str = str(e).lower()
            # WebSocket foi fechado pelo cliente - é normal em imports longos
            # Client pode ter timeout (~30s) enquanto o servidor ainda está processando (pode ser >150s)
            if any(keyword in error_str for keyword in [
                "close message has been sent", 
                "cannot call", 
                "not connected", 
                "need to call",
                "websocket is not connected",
                "connection closed",
                "connection lost"
            ]):
                # Não logar como erro - é comportamento esperado em imports longos
                # Apenas logar para status importantes para evitar spam
                if status in (FileStatus.STARTING, FileStatus.DONE, FileStatus.ERROR):
                    msg.info(f"[WEBSOCKET] Client disconnected before receiving report: {message}")
            else:
                # Outros RuntimeErrors - logar como warning apenas para status importantes
                if status in (FileStatus.STARTING, FileStatus.DONE, FileStatus.ERROR):
                    msg.warn(f"[WEBSOCKET] RuntimeError sending report: {type(e).__name__}: {str(e)}")
        except Exception as e:
            # Outros erros - log apenas para não quebrar o processamento
            # Não logar como erro crítico - apenas como info para imports intermediários
            if status in (FileStatus.STARTING, FileStatus.DONE, FileStatus.ERROR):
                msg.warn(f"[WEBSOCKET] Failed to send report to client: {type(e).__name__}: {str(e)}")

    async def create_new_document(
        self, new_file_id: str, document_name: str, original_file_id: str
    ):
        msg.info(f"Creating new file {new_file_id} from {original_file_id}")
        if self.socket is not None:
            # Verifica se WebSocket está pronto antes de tentar enviar
            if not self._is_websocket_ready():
                state_info = "unknown"
                try:
                    state_info = str(self.socket.application_state)
                except:
                    pass
                msg.info(f"[WEBSOCKET] WebSocket not ready (state: {state_info}) - skipping document creation: {new_file_id}")
                return
            
            try:
                payload: CreateNewDocument = {
                    "new_file_id": new_file_id,
                    "filename": document_name,
                    "original_file_id": original_file_id,
                }
                await self.socket.send_json(payload)
            except (RuntimeError, ConnectionError, OSError) as e:
                error_str = str(e).lower()
                # WebSocket foi fechado - é normal
                if any(keyword in error_str for keyword in [
                    "close message has been sent", 
                    "cannot call", 
                    "not connected", 
                    "need to call",
                    "websocket is not connected",
                    "connection closed",
                    "connection lost"
                ]):
                    msg.info(f"[WEBSOCKET] Client disconnected before receiving document creation: {new_file_id}")
                else:
                    msg.warn(f"[WEBSOCKET] RuntimeError sending document creation: {type(e).__name__}: {str(e)}")
            except Exception as e:
                # Outros erros - log apenas
                msg.warn(f"[WEBSOCKET] Failed to send document creation to client: {type(e).__name__}: {str(e)}")


class BatchManager:
    def __init__(self):
        self.batches = {}

    def add_batch(self, payload: DataBatchPayload) -> FileConfig:
        try:
            # Drastically reduce logging to avoid Railway rate limit (500 logs/sec)
            # Only log first batch, every 500 batches, or last batch
            should_log = (
                payload.order == 0 or 
                payload.order % 500 == 0 or 
                payload.isLastChunk or 
                payload.order == payload.total - 1
            )

            if payload.fileID not in self.batches:
                self.batches[payload.fileID] = {
                    "fileID": payload.fileID,
                    "total": payload.total,
                    "chunks": {},
                }
                msg.info(f"[BATCH] Started collection for {payload.fileID[:50]}... ({payload.total} chunks)")

            self.batches[payload.fileID]["chunks"][payload.order] = payload.chunk
            
            if should_log:
                received = len(self.batches[payload.fileID]["chunks"].keys())
                msg.info(f"[BATCH] Progress: {received}/{payload.total} chunks received ({round(received/payload.total*100, 1)}%)")

            fileConfig = self.check_batch(payload.fileID)

            if fileConfig is not None or payload.isLastChunk:
                msg.info(f"[BATCH] Completed collection for {payload.fileID[:50]}...")
                del self.batches[payload.fileID]

            return fileConfig

        except Exception as e:
            import traceback
            msg.fail(f"[BATCH] Failed to add batch: {type(e).__name__}: {str(e)}")
            msg.fail(f"[BATCH] Traceback: {traceback.format_exc()}")
            return None

    def check_batch(self, fileID: str):
        if fileID not in self.batches:
            msg.warn(f"[BATCH] FileID {fileID[:50]}... not found in batches")
            return None
            
        received = len(self.batches[fileID]["chunks"].keys())
        total = self.batches[fileID]["total"]
        
        if received == total:
            msg.good(f"[BATCH] All batches collected for {fileID[:50]}... ({received}/{total})")
            chunks = self.batches[fileID]["chunks"]
            
            # Verifica se há gaps na sequência
            missing_chunks = []
            for i in range(total):
                if i not in chunks:
                    missing_chunks.append(i)
            
            if missing_chunks:
                msg.fail(f"[BATCH] Missing chunks: {missing_chunks[:10]}... (total missing: {len(missing_chunks)})")
                return None
            
            # Sort chunks by order to ensure correct order
            sorted_chunks = [chunks[order] for order in sorted(chunks.keys())]
            data = "".join(sorted_chunks)
            msg.info(f"[BATCH] Assembled JSON data: {len(data)} chars")
            
            try:
                fileConfig = FileConfig.model_validate_json(data)
                # rag_config is dict[str, RAGComponentClass], so access selected attribute directly
                reader_name = "unknown"
                if "Reader" in fileConfig.rag_config and fileConfig.rag_config["Reader"]:
                    reader_name = fileConfig.rag_config["Reader"].selected
                msg.good(f"[BATCH] ✅ Parsed FileConfig: {fileConfig.filename[:50]}... (Reader: {reader_name})")
                return fileConfig
            except Exception as e:
                import traceback
                msg.fail(f"[BATCH] Failed to parse FileConfig JSON: {type(e).__name__}: {str(e)}")
                msg.fail(f"[BATCH] JSON preview (first 500 chars): {data[:500]}")
                msg.fail(f"[BATCH] JSON preview (last 500 chars): {data[-500:]}")
                msg.fail(f"[BATCH] Traceback: {traceback.format_exc()}")
                raise
        else:
            # Log periodicamente se ainda está esperando (reduzido drasticamente para evitar rate limit)
            # Apenas a cada 1000 chunks ou no último chunk
            if received % 1000 == 0 or received == total - 1:
                missing = total - received
                msg.info(f"[BATCH] Still waiting: {received}/{total} chunks received ({missing} missing)")
            return None
