import os
import importlib
import math
import json
from datetime import datetime

from dotenv import load_dotenv
from wasabi import msg
# Fix: Adicionar método debug ao msg se não existir (compatibilidade)
if not hasattr(msg, 'debug'):
    def debug_wrapper(*args, **kwargs):
        msg.info(*args, **kwargs)
    msg.debug = debug_wrapper
import asyncio

from copy import deepcopy
import hashlib

from goldenverba.server.helpers import LoggerManager
from weaviate.client import WeaviateAsyncClient

from goldenverba.components.document import Document
from goldenverba.server.types import (
    FileConfig,
    FileStatus,
    ChunkScore,
    Credentials,
)

from goldenverba.components.managers import (
    ReaderManager,
    ChunkerManager,
    EmbeddingManager,
    RetrieverManager,
    GeneratorManager,
    WeaviateManager,
)

# Plugin Manager for chunk enrichment
try:
    from verba_extensions.plugins.plugin_manager import get_plugin_manager
    PLUGINS_AVAILABLE = True
except ImportError:
    PLUGINS_AVAILABLE = False
    msg.warn("Plugin extensions not available - chunk enrichment plugins disabled")

load_dotenv()


class VerbaManager:
    """Manages all Verba Components."""

    def __init__(self) -> None:
        self.reader_manager = ReaderManager()
        self.chunker_manager = ChunkerManager()
        self.embedder_manager = EmbeddingManager()
        self.retriever_manager = RetrieverManager()
        self.generator_manager = GeneratorManager()
        self.weaviate_manager = WeaviateManager()
        self.rag_config_uuid = "e0adcc12-9bad-4588-8a1e-bab0af6ed485"
        self.theme_config_uuid = "baab38a7-cb51-4108-acd8-6edeca222820"
        self.user_config_uuid = "f53f7738-08be-4d5a-b003-13eb4bf03ac7"
        self.environment_variables = {}
        self.installed_libraries = {}

        self.verify_installed_libraries()
        self.verify_variables()

    async def connect(self, credentials: Credentials, port: str = "8080"):
        start_time = asyncio.get_event_loop().time()
        try:
            client = await self.weaviate_manager.connect(
                credentials.deployment, credentials.url, credentials.key, port
            )
        except Exception as e:
            raise e
        if client:
            initialized = await self.weaviate_manager.verify_collection(
                client, self.weaviate_manager.config_collection_name
            )
            if initialized:
                end_time = asyncio.get_event_loop().time()
                msg.info(f"Connection time: {end_time - start_time:.2f} seconds")
                return client

    async def disconnect(self, client):
        start_time = asyncio.get_event_loop().time()
        result = await self.weaviate_manager.disconnect(client)
        end_time = asyncio.get_event_loop().time()
        msg.info(f"Disconnection time: {end_time - start_time:.2f} seconds")
        return result

    async def get_deployments(self):
        deployments = {
            "WEAVIATE_URL_VERBA": (
                os.getenv("WEAVIATE_URL_VERBA")
                if os.getenv("WEAVIATE_URL_VERBA")
                else ""
            ),
            "WEAVIATE_API_KEY_VERBA": (
                os.getenv("WEAVIATE_API_KEY_VERBA")
                if os.getenv("WEAVIATE_API_KEY_VERBA")
                else ""
            ),
        }
        return deployments

    # Import

    async def import_document(
        self, client, fileConfig: FileConfig, logger: LoggerManager = LoggerManager()
    ):
        try:
            loop = asyncio.get_running_loop()
            start_time = loop.time()

            duplicate_uuid = await self.weaviate_manager.exist_document_name(
                client, fileConfig.filename
            )
            if duplicate_uuid is not None and not fileConfig.overwrite:
                raise Exception(f"{fileConfig.filename} already exists in Verba")
            elif duplicate_uuid is not None and fileConfig.overwrite:
                await self.weaviate_manager.delete_document(client, duplicate_uuid)
                await logger.send_report(
                    fileConfig.fileID,
                    status=FileStatus.STARTING,
                    message=f"Overwriting {fileConfig.filename}",
                    took=0,
                )
            else:
                await logger.send_report(
                    fileConfig.fileID,
                    status=FileStatus.STARTING,
                    message="Starting Import",
                    took=0,
                )

            # rag_config is dict[str, RAGComponentClass], so access selected attribute directly
            reader_name = "unknown"
            if "Reader" in fileConfig.rag_config and fileConfig.rag_config["Reader"]:
                reader_name = fileConfig.rag_config["Reader"].selected
            msg.info(f"[IMPORT] Loading file '{fileConfig.filename}' with reader '{reader_name}'")
            try:
                documents = await self.reader_manager.load(
                    reader_name, fileConfig, logger
                )
                msg.good(f"[IMPORT] Successfully loaded {len(documents)} document(s) from '{fileConfig.filename}'")
            except Exception as e:
                import traceback
                msg.fail(f"[IMPORT] Failed to load file '{fileConfig.filename}' with reader '{reader_name}': {type(e).__name__}: {str(e)}")
                msg.fail(f"[IMPORT] Traceback: {traceback.format_exc()}")
                raise

            tasks = [
                self.process_single_document(client, doc, fileConfig, logger)
                for doc in documents
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful_tasks = sum(
                1 for result in results if not isinstance(result, Exception)
            )

            if successful_tasks > 1:
                await logger.send_report(
                    fileConfig.fileID,
                    status=FileStatus.INGESTING,
                    message=f"Imported {fileConfig.filename} and it's {successful_tasks} documents into Weaviate",
                    took=round(loop.time() - start_time, 2),
                )
            elif successful_tasks == 1:
                await logger.send_report(
                    fileConfig.fileID,
                    status=FileStatus.INGESTING,
                    message=f"Imported {fileConfig.filename} and {len(documents[0].chunks)} chunks into Weaviate",
                    took=round(loop.time() - start_time, 2),
                )
            elif (
                successful_tasks == 0
                and len(results) == 1
                and isinstance(results[0], Exception)
            ):
                msg.fail(
                    f"No documents imported {successful_tasks} of {len(results)} succesful tasks"
                )
                raise results[0]
            else:
                raise Exception(
                    f"No documents imported {successful_tasks} of {len(results)} succesful tasks"
                )

            await logger.send_report(
                fileConfig.fileID,
                status=FileStatus.DONE,
                message=f"Import for {fileConfig.filename} completed successfully",
                took=round(loop.time() - start_time, 2),
            )

        except Exception as e:
            await logger.send_report(
                fileConfig.fileID,
                status=FileStatus.ERROR,
                message=f"Import for {fileConfig.filename} failed: {str(e)}",
                took=0,
            )
            return

    async def process_single_document(
        self,
        client,
        document: Document,
        fileConfig: FileConfig,
        logger: LoggerManager,
    ):
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        if fileConfig.isURL:
            currentFileConfig = deepcopy(fileConfig)
            currentFileConfig.fileID = fileConfig.fileID + document.title
            currentFileConfig.isURL = False
            currentFileConfig.filename = document.title
            await logger.create_new_document(
                fileConfig.fileID + document.title,
                document.title,
                fileConfig.fileID,
            )
        else:
            currentFileConfig = fileConfig

        try:
            duplicate_uuid = await self.weaviate_manager.exist_document_name(
                client, document.title
            )
            if duplicate_uuid is not None and not currentFileConfig.overwrite:
                raise Exception(f"{document.title} already exists in Verba")
            elif duplicate_uuid is not None and currentFileConfig.overwrite:
                await self.weaviate_manager.delete_document(client, duplicate_uuid)

            # Check if ETL is enabled BEFORE chunking
            enable_etl = document.meta.get("enable_etl", False) if hasattr(document, 'meta') and document.meta else False
            msg.info(f"[ETL-PRE-CHECK] Verificando ETL para documento '{document.title}': enable_etl={enable_etl}, meta={document.meta if hasattr(document, 'meta') else 'None'}")
            
            # FASE 1: ETL Pré-Chunking (extrai entidades do documento completo)
            # Entity-aware chunking é essencial para o sistema
            # Otimização: usa binary search para filtragem eficiente de entidades
            enable_etl_pre_chunking = True  # HABILITADO - otimizado com binary search
            
            if enable_etl and enable_etl_pre_chunking:
                msg.info(f"[ETL-PRE] ETL habilitado detectado - iniciando extração de entidades pré-chunking")
                try:
                    from verba_extensions.integration.chunking_hook import apply_etl_pre_chunking
                    msg.info(f"[ETL-PRE] Hook importado com sucesso - aplicando ETL pré-chunking")
                    document = apply_etl_pre_chunking(document, enable_etl=True)
                    msg.good(f"[ETL-PRE] ✅ Entidades extraídas antes do chunking - chunking será entity-aware")
                except ImportError as import_err:
                    msg.warn(f"[ETL-PRE] Hook de ETL pré-chunking não disponível (continuando sem): {str(import_err)}")
                except Exception as e:
                    import traceback
                    msg.warn(f"[ETL-PRE] Erro no ETL pré-chunking (não crítico, continuando): {type(e).__name__}: {str(e)}")
                    msg.warn(f"[ETL-PRE] Traceback: {traceback.format_exc()}")
            else:
                msg.info(f"[ETL-PRE] Pré-chunking desabilitado (performance)")
            
            if enable_etl:
                msg.info(f"[ETL] ETL A2 habilitado - será executado APÓS chunking e embedding também")
            else:
                msg.info(f"[ETL] ETL A2 não habilitado para este documento (enable_etl=False)")
            
            msg.info(f"[CHUNKING] Iniciando chunking para '{document.title}' (ETL={'enabled' if enable_etl else 'disabled'})")
            
            # Envia status de início do chunking
            try:
                await logger.send_report(
                    currentFileConfig.fileID,
                    status=FileStatus.CHUNKING,
                    message=f"Chunking {document.title}...",
                    took=0,
                )
            except Exception:
                pass  # Não falha se WebSocket fechar
            
            chunk_task = asyncio.create_task(
                self.chunker_manager.chunk(
                    currentFileConfig.rag_config["Chunker"].selected,
                    currentFileConfig,
                    [document],
                    self.embedder_manager.embedders[
                        currentFileConfig.rag_config["Embedder"].selected
                    ],
                    logger,
                )
            )
            chunked_documents = await chunk_task
            
            # Remove logger de document.meta para evitar problemas de serialização JSON
            for doc in chunked_documents:
                if hasattr(doc, 'meta') and doc.meta:
                    doc.meta.pop('_temp_logger', None)
            
            total_chunks = sum(len(doc.chunks) for doc in chunked_documents)
            msg.info(f"[CHUNKING] Chunking concluído: {total_chunks} chunks criados (ETL será executado após import)")

            # Add chunk_lang to chunks (language detection) + Quality Scoring (RAG2)
            from goldenverba.components.document import detect_language
            for doc in chunked_documents:
                # Quality Scoring (RAG2) - filtrar chunks de baixa qualidade
                try:
                    from verba_extensions.utils.quality import compute_quality_score
                    from verba_extensions.utils.telemetry import get_telemetry
                    use_quality_filter = True
                    quality_threshold = 0.3  # Configurável via env se necessário
                except ImportError:
                    use_quality_filter = False
                
                filtered_chunks = []
                quality_filtered_count = 0
                
                for chunk in doc.chunks:
                    # Language detection
                    if not chunk.chunk_lang:
                        # Detect language from chunk content
                        detected_lang = detect_language(chunk.content)
                        # Normalize to pt/en for bilingual filtering
                        if detected_lang in ["pt", "pt-br", "pt-BR"]:
                            chunk.chunk_lang = "pt"
                        elif detected_lang in ["en", "en-US", "en-GB"]:
                            chunk.chunk_lang = "en"
                        else:
                            # Default to document language or empty
                            chunk.chunk_lang = detected_lang if detected_lang != "unknown" else ""
                    
                    # Quality Scoring (RAG2) - filtrar chunks de baixa qualidade
                    if use_quality_filter:
                        parent_type = chunk.meta.get("parent_type") if hasattr(chunk, 'meta') and chunk.meta else None
                        is_summary = chunk.meta.get("is_summary", False) if hasattr(chunk, 'meta') and chunk.meta else False
                        
                        score, reason = compute_quality_score(
                            text=chunk.content,
                            parent_type=parent_type,
                            is_summary=is_summary
                        )
                        
                        # Filtrar chunks de baixa qualidade
                        if score < quality_threshold:
                            quality_filtered_count += 1
                            try:
                                telemetry = get_telemetry()
                                telemetry.record_chunk_filtered_by_quality(
                                    parent_type=parent_type or "unknown",
                                    score=score,
                                    reason=reason
                                )
                            except:
                                pass  # Telemetria opcional
                            continue  # Pula chunk de baixa qualidade
                    
                    filtered_chunks.append(chunk)
                
                # Atualizar chunks do documento (remover os filtrados)
                if use_quality_filter and quality_filtered_count > 0:
                    doc.chunks = filtered_chunks
                    msg.info(f"[QUALITY] Filtrados {quality_filtered_count} chunks de baixa qualidade (threshold: {quality_threshold})")
            
            # Apply plugin enrichment (e.g., LLMMetadataExtractor)
            if PLUGINS_AVAILABLE:
                try:
                    plugin_manager = get_plugin_manager()
                    if plugin_manager.plugins:
                        msg.info(f"Applying {len(plugin_manager.plugins)} plugin(s) to enrich chunks")
                        enriched_documents = []
                        for doc in chunked_documents:
                            enriched_doc = await plugin_manager.process_document_chunks(doc)
                            enriched_documents.append(enriched_doc)
                        chunked_documents = enriched_documents
                        msg.good(f"Chunks enriched with {plugin_manager.get_enabled_plugins()}")
                except Exception as e:
                    msg.warn(f"Plugin processing failed (non-critical): {str(e)}")
                    # Continue without enrichment if plugins fail

            # Log embedding start
            embedder_name = currentFileConfig.rag_config["Embedder"].selected
            total_chunks = sum(len(doc.chunks) for doc in chunked_documents)
            msg.info(f"[EMBEDDING] Starting vectorization: embedder={embedder_name}, chunks={total_chunks}, docs={len(chunked_documents)}")
            
            # Envia status de início do embedding
            try:
                await logger.send_report(
                    currentFileConfig.fileID,
                    status=FileStatus.EMBEDDING,
                    message=f"Vectorizando {total_chunks} chunks...",
                    took=0,
                )
            except Exception:
                pass  # Não falha se WebSocket fechar
            
            try:
                embedding_task = asyncio.create_task(
                    self.embedder_manager.vectorize(
                        embedder_name,
                        currentFileConfig,
                        chunked_documents,
                        logger,
                    )
                )
                vectorized_documents = await embedding_task
                msg.info(f"[EMBEDDING] Vectorization completed successfully: {len(vectorized_documents)} documents")
                
                # Envia status de conclusão do embedding
                try:
                    await logger.send_report(
                        currentFileConfig.fileID,
                        status=FileStatus.INGESTING,
                        message=f"Vectorização concluída - importando no Weaviate...",
                        took=0,
                    )
                except Exception:
                    pass  # Não falha se WebSocket fechar
            except Exception as e:
                msg.fail(f"[EMBEDDING] Vectorization failed: {type(e).__name__}: {str(e)}")
                import traceback
                msg.fail(f"[EMBEDDING] Traceback: {traceback.format_exc()}")
                # Send error report to client
                await logger.send_report(
                    currentFileConfig.fileID,
                    status=FileStatus.ERROR,
                    message=f"Embedding failed: {str(e)}",
                    took=0,
                )
                raise

            for document in vectorized_documents:
                # Garantir conexão com o Weaviate antes do import
                try:
                    is_ready = False
                    try:
                        is_ready = await client.is_ready()
                    except Exception:
                        is_ready = False

                    if not is_ready:
                        msg.warn("Client disconnected during import, reconnecting...")
                        # Tenta reconectar o cliente existente
                        try:
                            if hasattr(client, "connect"):
                                await client.connect()
                                is_ready = await client.is_ready()
                        except Exception as ce:
                            msg.warn(f"Reconnect attempt failed: {str(ce)}")
                            is_ready = False

                    # Fallback: criar um novo cliente a partir das variáveis de ambiente
                    if not is_ready:
                        try:
                            http_host = os.getenv("WEAVIATE_HTTP_HOST")
                            url = os.getenv("WEAVIATE_URL_VERBA")
                            key = os.getenv("WEAVIATE_API_KEY_VERBA", "")
                            if http_host:
                                # Custom (Railway/private network) com portas separadas
                                port = os.getenv("WEAVIATE_HTTP_PORT", "8080")
                                new_client = await self.weaviate_manager.connect_to_custom(http_host, key, port)
                            elif url:
                                # Cluster/WCS
                                new_client = await self.weaviate_manager.connect_to_cluster(url, key)
                            else:
                                new_client = None

                            if new_client is not None:
                                try:
                                    if hasattr(new_client, "connect"):
                                        await new_client.connect()
                                    if await new_client.is_ready():
                                        client = new_client
                                        msg.good("Reconnected to Weaviate successfully")
                                        is_ready = True
                                except Exception as ne:
                                    msg.warn(f"New client not ready after reconnect: {str(ne)}")
                        except Exception as rec_e:
                            msg.warn(f"Failed to create a new Weaviate client: {str(rec_e)}")

                    if not is_ready:
                        # Não aborta aqui; deixa o import tentar e o hook lidar com ETL/graceful handling
                        msg.warn("Weaviate client still not ready; attempting import may fail")
                except Exception:
                    # Em caso de erro inesperado, continua para tentar importar e reportar erro exato do cliente
                    pass
                
                # Armazena logger e file_id temporariamente no document.meta para uso no hook ETL
                if not hasattr(document, 'meta') or document.meta is None:
                    document.meta = {}
                document.meta['_temp_logger'] = logger
                document.meta['file_id'] = currentFileConfig.fileID
                
                embedder_model = (
                    currentFileConfig.rag_config["Embedder"]
                    .components[fileConfig.rag_config["Embedder"].selected]
                    .config["Model"]
                    .value
                )
                
                ingesting_task = asyncio.create_task(
                    self.weaviate_manager.import_document(
                        client,
                        document,
                        embedder_model,
                    )
                )
                await ingesting_task

            await logger.send_report(
                currentFileConfig.fileID,
                status=FileStatus.INGESTING,
                message=f"Imported {currentFileConfig.filename} into Weaviate",
                took=round(loop.time() - start_time, 2),
            )

            await logger.send_report(
                currentFileConfig.fileID,
                status=FileStatus.DONE,
                message=f"Import for {currentFileConfig.filename} completed successfully",
                took=round(loop.time() - start_time, 2),
            )
        except Exception as e:
            await logger.send_report(
                currentFileConfig.fileID,
                status=FileStatus.ERROR,
                message=f"Import for {fileConfig.filename} failed: {str(e)}",
                took=round(loop.time() - start_time, 2),
            )
            raise Exception(f"Import for {fileConfig.filename} failed: {str(e)}")

    # Configuration

    def create_config(self) -> dict:
        """Creates the RAG Configuration and returns the full Verba Config with also Settings"""

        available_environments = self.environment_variables
        available_libraries = self.installed_libraries

        readers = self.reader_manager.readers
        reader_config = {
            "components": {
                reader: readers[reader].get_meta(
                    available_environments, available_libraries
                )
                for reader in readers
            },
            "selected": list(readers.values())[0].name,
        }

        chunkers = self.chunker_manager.chunkers
        # Preferir nosso chunker híbrido se disponível; caso contrário, usar o primeiro
        selected_chunker_name = (
            "Entity-Semantic" if "Entity-Semantic" in chunkers else list(chunkers.values())[0].name
        )
        chunkers_config = {
            "components": {
                chunker: chunkers[chunker].get_meta(
                    available_environments, available_libraries
                )
                for chunker in chunkers
            },
            "selected": selected_chunker_name,
        }

        embedders = self.embedder_manager.embedders
        # Preferir SentenceTransformers como padrão quando disponível (evita dependência do Ollama)
        selected_embedder_name = (
            "SentenceTransformers" if "SentenceTransformers" in embedders else list(embedders.values())[0].name
        )
        embedder_config = {
            "components": {
                embedder: embedders[embedder].get_meta(
                    available_environments, available_libraries
                )
                for embedder in embedders
            },
            "selected": selected_embedder_name,
        }

        retrievers = self.retriever_manager.retrievers
        retrievers_config = {
            "components": {
                retriever: retrievers[retriever].get_meta(
                    available_environments, available_libraries
                )
                for retriever in retrievers
            },
            "selected": list(retrievers.values())[0].name,
        }

        generators = self.generator_manager.generators
        generator_config = {
            "components": {
                generator: generators[generator].get_meta(
                    available_environments, available_libraries
                )
                for generator in generators
            },
            "selected": list(generators.values())[0].name,
        }

        return {
            "Reader": reader_config,
            "Chunker": chunkers_config,
            "Embedder": embedder_config,
            "Retriever": retrievers_config,
            "Generator": generator_config,
        }

    def create_user_config(self) -> dict:
        return {"getting_started": False}

    async def set_theme_config(self, client, config: dict):
        await self.weaviate_manager.set_config(client, self.theme_config_uuid, config)

    async def set_rag_config(self, client, config: dict):
        await self.weaviate_manager.set_config(client, self.rag_config_uuid, config)

    async def set_user_config(self, client, config: dict):
        await self.weaviate_manager.set_config(client, self.user_config_uuid, config)

    def merge_config(self, loaded_config: dict, new_config: dict) -> dict:
        """
        Merge loaded config with new config, adding missing fields with default values.
        This ensures new fields (like "Reranker Top K") are added to old configs.
        """
        merged_config = deepcopy(loaded_config)
        
        for component_key in new_config.keys():
            if component_key not in merged_config:
                merged_config[component_key] = new_config[component_key]
                continue
            
            new_components = new_config[component_key]["components"]
            merged_components = merged_config[component_key]["components"]
            
            for component_name, new_component in new_components.items():
                if component_name not in merged_components:
                    # Component doesn't exist in loaded config, add it
                    merged_components[component_name] = new_component
                    continue
                
                # Merge config fields: add missing fields with default values
                merged_component = merged_components[component_name]
                new_component_config = new_component["config"]
                merged_component_config = merged_component["config"]
                
                for config_key, new_config_setting in new_component_config.items():
                    if config_key not in merged_component_config:
                        # Field doesn't exist in loaded config, add it with default value
                        default_value = new_config_setting.get('value', 'N/A') if isinstance(new_config_setting, dict) else getattr(new_config_setting, 'value', 'N/A')
                        msg.info(f"Adding missing config field '{config_key}' to {component_key}.{component_name} with default value: {default_value}")
                        merged_component_config[config_key] = new_config_setting
        
        return merged_config

    async def load_rag_config(self, client):
        """Check if a Configuration File exists in the database, if yes, check if corrupted. Returns a valid configuration file"""
        # Garante que todas as coleções de embeddings existem
        # Isso é necessário para que chunks possam ser vetorizados
        await self.weaviate_manager.verify_collections(
            client, 
            self.environment_variables,
            self.installed_libraries
        )
        
        loaded_config = await self.weaviate_manager.get_config(
            client, self.rag_config_uuid
        )
        new_config = self.create_config()
        if loaded_config is not None:
            if self.verify_config(loaded_config, new_config):
                msg.info("Using Existing RAG Configuration")
                return loaded_config
            else:
                # Config structure changed (new fields added), merge instead of replacing
                msg.info("Merging RAG Configuration: adding missing fields with default values")
                merged_config = self.merge_config(loaded_config, new_config)
                # Save merged config to persist new fields
                await self.set_rag_config(client, merged_config)
                return merged_config
        else:
            msg.info("Using New RAG Configuration")
            return new_config

    async def load_theme_config(self, client):
        loaded_config = await self.weaviate_manager.get_config(
            client, self.theme_config_uuid
        )

        if loaded_config is None:
            return None, None

        return loaded_config["theme"], loaded_config["themes"]

    async def load_user_config(self, client):
        loaded_config = await self.weaviate_manager.get_config(
            client, self.user_config_uuid
        )

        if loaded_config is None:
            return self.create_user_config()

        return loaded_config

    def verify_config(self, a: dict, b: dict) -> bool:
        """
        Verify if two RAG configurations are compatible.
        Returns True if compatible, False otherwise.
        Uses key-based comparison (not order-dependent) for flexibility.
        """
        try:
            if os.getenv("VERBA_PRODUCTION") == "Demo":
                return True
            
            # Compare component keys (order-independent)
            if set(a.keys()) != set(b.keys()):
                msg.warn(
                    f"Config Validation: Component type mismatch. Expected: {set(a.keys())}, Got: {set(b.keys())}"
                )
                return False

            for component_key in a.keys():
                a_component = a[component_key]["components"]
                b_component = b[component_key]["components"]

                # Compare component names (order-independent)
                if set(a_component.keys()) != set(b_component.keys()):
                    missing_in_b = set(a_component.keys()) - set(b_component.keys())
                    missing_in_a = set(b_component.keys()) - set(a_component.keys())
                    msg.warn(
                        f"Config Validation: {component_key} components mismatch. "
                        f"Missing in stored: {missing_in_b}, Missing in current: {missing_in_a}. "
                        f"Will use new configuration."
                    )
                    return False

                # Compare each component's config
                for component_name in a_component.keys():
                    if component_name not in b_component:
                        msg.warn(
                            f"Config Validation: Component '{component_name}' not found in stored config for {component_key}. "
                            f"Will use new configuration."
                        )
                        return False
                    
                    a_rag_component = a_component[component_name]
                    b_rag_component = b_component[component_name]

                    a_config = a_rag_component["config"]
                    b_config = b_rag_component["config"]

                    # Compare config keys (order-independent)
                    if set(a_config.keys()) != set(b_config.keys()):
                        msg.warn(
                            f"Config Validation: Config keys mismatch for {component_key}.{component_name}. "
                            f"Will use new configuration."
                        )
                        return False

                    # Compare each config setting
                    for config_key in a_config.keys():
                        if config_key not in b_config:
                            msg.warn(
                                f"Config Validation: Config key '{config_key}' not found in stored config. "
                                f"Will use new configuration."
                            )
                            return False

                        a_setting = a_config[config_key]
                        b_setting = b_config[config_key]

                        # Compare description (non-critical, but log if different)
                        if a_setting.get("description") != b_setting.get("description"):
                            msg.info(
                                f"Config Validation: Description changed for {component_key}.{component_name}.{config_key}"
                            )
                            # Don't fail on description change - it's just metadata

                        # Compare values (order-independent)
                        if sorted(a_setting.get("values", [])) != sorted(b_setting.get("values", [])):
                            msg.warn(
                                f"Config Validation: Values mismatch for {component_key}.{component_name}.{config_key}. "
                                f"Will use new configuration."
                            )
                            return False

            return True

        except Exception as e:
            msg.warn(f"Config Validation failed (will use new config): {str(e)}")
            return False

    async def reset_rag_config(self, client):
        msg.info("Resetting RAG Configuration")
        await self.weaviate_manager.reset_config(client, self.rag_config_uuid)

    async def reset_theme_config(self, client):
        msg.info("Resetting Theme Configuration")
        await self.weaviate_manager.reset_config(client, self.theme_config_uuid)

    async def reset_user_config(self, client):
        msg.info("Resetting User Configuration")
        await self.weaviate_manager.reset_config(client, self.user_config_uuid)

    # Environment and Libraries

    def verify_installed_libraries(self) -> None:
        """
        Checks which libraries are installed and fills out the self.installed_libraries dictionary for the frontend to access, this will be displayed in the status page.
        """
        reader = [
            lib
            for reader in self.reader_manager.readers
            for lib in self.reader_manager.readers[reader].requires_library
        ]
        chunker = [
            lib
            for chunker in self.chunker_manager.chunkers
            for lib in self.chunker_manager.chunkers[chunker].requires_library
        ]
        embedder = [
            lib
            for embedder in self.embedder_manager.embedders
            for lib in self.embedder_manager.embedders[embedder].requires_library
        ]
        retriever = [
            lib
            for retriever in self.retriever_manager.retrievers
            for lib in self.retriever_manager.retrievers[retriever].requires_library
        ]
        generator = [
            lib
            for generator in self.generator_manager.generators
            for lib in self.generator_manager.generators[generator].requires_library
        ]

        required_libraries = reader + chunker + embedder + retriever + generator
        unique_libraries = set(required_libraries)

        for lib in unique_libraries:
            try:
                importlib.import_module(lib)
                self.installed_libraries[lib] = True
            except Exception:
                self.installed_libraries[lib] = False

    def verify_variables(self) -> None:
        """
        Checks which environment variables are installed and fills out the self.environment_variables dictionary for the frontend to access.
        """
        reader = [
            lib
            for reader in self.reader_manager.readers
            for lib in self.reader_manager.readers[reader].requires_env
        ]
        chunker = [
            lib
            for chunker in self.chunker_manager.chunkers
            for lib in self.chunker_manager.chunkers[chunker].requires_env
        ]
        embedder = [
            lib
            for embedder in self.embedder_manager.embedders
            for lib in self.embedder_manager.embedders[embedder].requires_env
        ]
        retriever = [
            lib
            for retriever in self.retriever_manager.retrievers
            for lib in self.retriever_manager.retrievers[retriever].requires_env
        ]
        generator = [
            lib
            for generator in self.generator_manager.generators
            for lib in self.generator_manager.generators[generator].requires_env
        ]

        required_envs = reader + chunker + embedder + retriever + generator
        unique_envs = set(required_envs)

        for env in unique_envs:
            if os.environ.get(env) is not None:
                self.environment_variables[env] = True
            else:
                self.environment_variables[env] = False

    # Document Content Retrieval

    async def get_content(
        self,
        client,
        uuid: str,
        page: int,
        chunkScores: list[ChunkScore],
    ):
        chunks_per_page = 10
        content_pieces = []
        total_batches = 0

        # Return Chunks with surrounding context
        if len(chunkScores) > 0:
            if page > len(chunkScores):
                page = 0

            total_batches = len(chunkScores)
            chunk = await self.weaviate_manager.get_chunk(
                client, chunkScores[page].uuid, chunkScores[page].embedder
            )

            before_ids = [
                i
                for i in range(
                    max(0, chunkScores[page].chunk_id - int(chunks_per_page / 2)),
                    chunkScores[page].chunk_id,
                )
            ]
            if before_ids:
                chunks_before_chunk = await self.weaviate_manager.get_chunk_by_ids(
                    client,
                    chunkScores[page].embedder,
                    uuid,
                    ids=[
                        i
                        for i in range(
                            max(
                                0, chunkScores[page].chunk_id - int(chunks_per_page / 2)
                            ),
                            chunkScores[page].chunk_id,
                        )
                    ],
                )
                before_content = "".join(
                    [
                        chunk.properties["content_without_overlap"]
                        for chunk in chunks_before_chunk
                    ]
                )
            else:
                before_content = ""

            after_ids = [
                i
                for i in range(
                    chunkScores[page].chunk_id + 1,
                    chunkScores[page].chunk_id + int(chunks_per_page / 2),
                )
            ]
            if after_ids:
                chunks_after_chunk = await self.weaviate_manager.get_chunk_by_ids(
                    client,
                    chunkScores[page].embedder,
                    uuid,
                    ids=[
                        i
                        for i in range(
                            chunkScores[page].chunk_id + 1,
                            chunkScores[page].chunk_id + int(chunks_per_page / 2),
                        )
                    ],
                )
                after_content = "".join(
                    [
                        chunk.properties["content_without_overlap"]
                        for chunk in chunks_after_chunk
                    ]
                )
            else:
                after_content = ""

            content_pieces.append(
                {
                    "content": before_content,
                    "chunk_id": 0,
                    "score": 0,
                    "type": "text",
                }
            )
            content_pieces.append(
                {
                    "content": chunk["content_without_overlap"],
                    "chunk_id": chunkScores[page].chunk_id,
                    "score": chunkScores[page].score,
                    "type": "extract",
                }
            )
            content_pieces.append(
                {
                    "content": after_content,
                    "chunk_id": 0,
                    "score": 0,
                    "type": "text",
                }
            )

        # Return Content based on Page
        else:
            document = await self.weaviate_manager.get_document(
                client, uuid, properties=["meta"]
            )
            config = json.loads(document["meta"])
            embedder = config["Embedder"]["config"]["Model"]["value"]
            request_chunk_ids = [
                i
                for i in range(
                    chunks_per_page * (page + 1) - chunks_per_page,
                    chunks_per_page * (page + 1),
                )
            ]

            chunks = await self.weaviate_manager.get_chunk_by_ids(
                client, embedder, uuid, request_chunk_ids
            )

            total_chunks = await self.weaviate_manager.get_chunk_count(
                client, embedder, uuid
            )
            total_batches = int(math.ceil(total_chunks / chunks_per_page))

            content = "".join(
                [chunk.properties["content_without_overlap"] for chunk in chunks]
            )

            content_pieces.append(
                {
                    "content": content,
                    "chunk_id": 0,
                    "score": 0,
                    "type": "text",
                }
            )

        return (content_pieces, total_batches)

    # Retrieval Augmented Generation

    async def retrieve_chunks(
        self,
        client,
        query: str,
        rag_config: dict,
        labels: list[str] = [],
        document_uuids: list[str] = [],
    ):
        retriever = rag_config["Retriever"].selected
        embedder = rag_config["Embedder"].selected

        await self.weaviate_manager.add_suggestion(client, query)

        vector = await self.embedder_manager.vectorize_query(
            embedder, query, rag_config
        )
        result = await self.retriever_manager.retrieve(
            client,
            retriever,
            query,
            vector,
            rag_config,
            self.weaviate_manager,
            labels,
            document_uuids,
        )
        
        # Lidar com retorno de 2 ou 3 elementos (compatibilidade)
        if len(result) == 3:
            documents, context, debug_info = result
            return (documents, context, debug_info)
        else:
            documents, context = result
            return (documents, context)

    async def generate_stream_answer(
        self,
        rag_config: dict,
        query: str,
        context: str,
        conversation: list[dict],
    ):

        full_text = ""
        async for result in self.generator_manager.generate_stream(
            rag_config, query, context, conversation
        ):
            full_text += result["message"]
            yield result


class ClientManager:
    def __init__(self) -> None:
        self.clients: dict[str, dict] = {}
        self.manager: VerbaManager = VerbaManager()
        # Keep clients alive longer to support long-running imports/embeddings
        self.max_time: int = 60
        self.locks: dict[str, asyncio.Lock] = {}

    def hash_credentials(self, credentials: Credentials) -> str:
        cred_string = f"{credentials.deployment}:{credentials.url}:{credentials.key}"
        return hashlib.sha256(cred_string.encode()).hexdigest()

    def get_or_create_lock(self, cred_hash: str) -> asyncio.Lock:
        if cred_hash not in self.locks:
            self.locks[cred_hash] = asyncio.Lock()
        return self.locks[cred_hash]

    def heartbeat(self):
        msg.info(f"{len(self.clients)} clients connected")
        for cred_hash, client in self.clients.items():
            msg.info(f"Client {cred_hash} connected at {client['timestamp']}")

    async def connect(
        self, credentials: Credentials, port: str = "8080"
    ) -> WeaviateAsyncClient:

        _credentials = credentials

        if not _credentials.url and not _credentials.key:
            _credentials.url = os.environ.get("WEAVIATE_URL_VERBA", "")
            _credentials.key = os.environ.get("WEAVIATE_API_KEY_VERBA", "")

        cred_hash = self.hash_credentials(_credentials)

        lock = self.get_or_create_lock(cred_hash)
        async with lock:
            if cred_hash in self.clients:
                msg.info("Found existing Client")
                # Touch last-used timestamp to keep the client from being cleaned up
                self.clients[cred_hash]["timestamp"] = datetime.now()
                return self.clients[cred_hash]["client"]
            else:
                msg.warn("Connecting new Client")
                try:
                    client = await self.manager.connect(_credentials, port)
                    if client:
                        self.clients[cred_hash] = {
                            "client": client,
                            "timestamp": datetime.now(),
                        }
                        return client
                    else:
                        raise Exception("Client not created")
                except Exception as e:
                    raise e

    async def disconnect(self):
        msg.warn("Disconnecting Clients!")
        for cred_hash, client in self.clients.items():
            await self.manager.disconnect(client["client"])

    async def clean_up(self):
        msg.info("Cleaning Clients Cache")
        current_time = datetime.now()
        clients_to_remove = []

        for cred_hash, client_data in self.clients.items():
            time_difference = current_time - client_data["timestamp"]
            client: WeaviateAsyncClient = client_data["client"]

            # Remove only by inactivity threshold; transient readiness issues shouldn't drop active clients
            if time_difference.total_seconds() / 60 > self.max_time:
                clients_to_remove.append(cred_hash)
            else:
                # Try to self-heal if the client reports not ready, but do not remove yet
                try:
                    is_ready = await client.is_ready()
                except Exception:
                    is_ready = False
                if not is_ready:
                    msg.warn(f"Client {cred_hash} reported not ready during cleanup; attempting reconnect")
                    try:
                        if hasattr(client, "connect"):
                            await client.connect()
                    except Exception:
                        pass

        for cred_hash in clients_to_remove:
            await self.manager.disconnect(self.clients[cred_hash]["client"])
            del self.clients[cred_hash]
            msg.warn(f"Removed client: {cred_hash}")

        msg.info(f"Cleaned up {len(clients_to_remove)} clients")
        self.heartbeat()
