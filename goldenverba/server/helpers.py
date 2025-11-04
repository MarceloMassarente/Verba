from fastapi import WebSocket
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
            try:
                payload: StatusReport = {
                    "fileID": file_Id,
                    "status": status,
                    "message": message,
                    "took": took,
                }
                await self.socket.send_json(payload)
            except RuntimeError as e:
                # WebSocket foi fechado pelo cliente - é normal em imports longos
                # Client pode ter timeout (~30s) enquanto o servidor ainda está processando (pode ser >150s)
                if "close message has been sent" in str(e) or "Cannot call" in str(e):
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
            try:
                payload: CreateNewDocument = {
                    "new_file_id": new_file_id,
                    "filename": document_name,
                    "original_file_id": original_file_id,
                }
                await self.socket.send_json(payload)
            except RuntimeError as e:
                # WebSocket foi fechado - é normal
                if "close message has been sent" in str(e) or "Cannot call" in str(e):
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
            msg.info(f"[BATCH] Receiving batch for {payload.fileID}: chunk {payload.order + 1}/{payload.total}")

            if payload.fileID not in self.batches:
                self.batches[payload.fileID] = {
                    "fileID": payload.fileID,
                    "total": payload.total,
                    "chunks": {},
                }
                msg.info(f"[BATCH] Started new batch collection for {payload.fileID} ({payload.total} chunks expected)")

            self.batches[payload.fileID]["chunks"][payload.order] = payload.chunk

            fileConfig = self.check_batch(payload.fileID)

            if fileConfig is not None or payload.isLastChunk:
                msg.info(f"[BATCH] Removing {payload.fileID} from BatchManager")
                del self.batches[payload.fileID]

            return fileConfig

        except Exception as e:
            import traceback
            msg.fail(f"[BATCH] Failed to add batch to BatchManager: {type(e).__name__}: {str(e)}")
            msg.fail(f"[BATCH] Traceback: {traceback.format_exc()}")
            return None

    def check_batch(self, fileID: str):
        if len(self.batches[fileID]["chunks"].keys()) == self.batches[fileID]["total"]:
            msg.good(f"[BATCH] Collected all batches of {fileID}")
            chunks = self.batches[fileID]["chunks"]
            # Sort chunks by order to ensure correct order
            sorted_chunks = [chunks[order] for order in sorted(chunks.keys())]
            data = "".join(sorted_chunks)
            
            try:
                msg.info(f"[BATCH] Parsing FileConfig JSON for {fileID} (length: {len(data)} chars)")
                fileConfig = FileConfig.model_validate_json(data)
                msg.good(f"[BATCH] Successfully parsed FileConfig for {fileConfig.filename} (Reader: {fileConfig.rag_config.get('Reader', {}).get('selected', 'unknown')})")
                return fileConfig
            except Exception as e:
                import traceback
                msg.fail(f"[BATCH] Failed to parse FileConfig JSON for {fileID}: {type(e).__name__}: {str(e)}")
                msg.fail(f"[BATCH] JSON data preview (first 500 chars): {data[:500]}")
                msg.fail(f"[BATCH] Traceback: {traceback.format_exc()}")
                raise
        else:
            received = len(self.batches[fileID]["chunks"].keys())
            total = self.batches[fileID]["total"]
            msg.info(f"[BATCH] Waiting for more chunks for {fileID}: {received}/{total} received")
            return None
