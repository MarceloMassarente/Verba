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

    async def send_report(
        self, file_Id: str, status: FileStatus, message: str, took: float
    ):
        msg.info(f"{status} | {file_Id} | {message} | {took}")
        if self.socket is not None:
            # Verifica se WebSocket está conectado antes de tentar enviar
            if self.socket.application_state != WebSocketState.CONNECTED:
                msg.info(f"[WEBSOCKET] WebSocket not connected (state: {self.socket.application_state}) - skipping report: {message}")
                return
            
            try:
                payload: StatusReport = {
                    "fileID": file_Id,
                    "status": status,
                    "message": message,
                    "took": took,
                }
                await self.socket.send_json(payload)
            except RuntimeError as e:
                error_str = str(e).lower()
                # WebSocket foi fechado pelo cliente - é normal em imports longos
                # Client pode ter timeout (~30s) enquanto o servidor ainda está processando (pode ser >150s)
                if "close message has been sent" in error_str or "cannot call" in error_str or "not connected" in error_str or "need to call" in error_str:
                    msg.info(f"[WEBSOCKET] Client disconnected before receiving report: {message}")
                else:
                    msg.warn(f"[WEBSOCKET] RuntimeError: {str(e)}")
            except Exception as e:
                # Outros erros - log apenas para não quebrar o processamento
                msg.warn(f"[WEBSOCKET] Failed to send report to client: {type(e).__name__}: {str(e)}")

    async def create_new_document(
        self, new_file_id: str, document_name: str, original_file_id: str
    ):
        msg.info(f"Creating new file {new_file_id} from {original_file_id}")
        if self.socket is not None:
            # Verifica se WebSocket está conectado antes de tentar enviar
            if self.socket.application_state != WebSocketState.CONNECTED:
                msg.info(f"[WEBSOCKET] WebSocket not connected (state: {self.socket.application_state}) - skipping document creation: {new_file_id}")
                return
            
            try:
                payload: CreateNewDocument = {
                    "new_file_id": new_file_id,
                    "filename": document_name,
                    "original_file_id": original_file_id,
                }
                await self.socket.send_json(payload)
            except RuntimeError as e:
                error_str = str(e).lower()
                # WebSocket foi fechado - é normal
                if "close message has been sent" in error_str or "cannot call" in error_str or "not connected" in error_str or "need to call" in error_str:
                    msg.info(f"[WEBSOCKET] Client disconnected before receiving document creation: {new_file_id}")
                else:
                    msg.warn(f"[WEBSOCKET] RuntimeError: {str(e)}")
            except Exception as e:
                # Outros erros - log apenas
                msg.warn(f"[WEBSOCKET] Failed to send document creation to client: {type(e).__name__}: {str(e)}")


class BatchManager:
    def __init__(self):
        self.batches = {}

    def add_batch(self, payload: DataBatchPayload) -> FileConfig:
        try:
            # Log only first batch, every 50 batches, or last batch to reduce log spam
            should_log = (
                payload.order == 0 or 
                payload.order % 50 == 0 or 
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
            # Log periodicamente se ainda está esperando
            if received % 50 == 0 or received == total - 1:
                missing = total - received
                msg.info(f"[BATCH] Still waiting: {received}/{total} chunks received ({missing} missing)")
            return None
