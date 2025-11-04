from wasabi import msg

import weaviate
from weaviate.client import WeaviateAsyncClient
from weaviate.auth import AuthApiKey
from weaviate.classes.query import Filter, Sort, MetadataQuery
from weaviate.collections.classes.data import DataObject
from weaviate.classes.aggregate import GroupByAggregate
from weaviate.classes.init import AdditionalConfig, Timeout

import os
import asyncio
import json
import re
import logging
from datetime import datetime

# Reduz logging excessivo do Weaviate SDK para evitar rate limits
# Logs de vetores individuais são muito verbosos e causam rate limit no Railway
logging.getLogger("weaviate").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)  # HTTP requests também logam muito

from sklearn.decomposition import PCA


from goldenverba.components.document import Document
from goldenverba.components.interfaces import (
    Reader,
    Chunker,
    Embedding,
    Retriever,
    Generator,
)
from goldenverba.server.helpers import LoggerManager
from goldenverba.server.types import FileConfig, FileStatus

# Import Readers
from goldenverba.components.reader.BasicReader import BasicReader
from goldenverba.components.reader.GitReader import GitReader
from goldenverba.components.reader.UnstructuredAPI import UnstructuredReader
from goldenverba.components.reader.AssemblyAIAPI import AssemblyAIReader
from goldenverba.components.reader.HTMLReader import HTMLReader
from goldenverba.components.reader.FirecrawlReader import FirecrawlReader
from goldenverba.components.reader.UpstageDocumentParse import (
    UpstageDocumentParseReader,
)

# Import Chunkers
from goldenverba.components.chunking.TokenChunker import TokenChunker
from goldenverba.components.chunking.SentenceChunker import SentenceChunker
from goldenverba.components.chunking.RecursiveChunker import RecursiveChunker
from goldenverba.components.chunking.HTMLChunker import HTMLChunker
from goldenverba.components.chunking.MarkdownChunker import MarkdownChunker
from goldenverba.components.chunking.CodeChunker import CodeChunker
from goldenverba.components.chunking.JSONChunker import JSONChunker
from goldenverba.components.chunking.SemanticChunker import SemanticChunker

# Import Embedders
from goldenverba.components.embedding.OpenAIEmbedder import OpenAIEmbedder
from goldenverba.components.embedding.CohereEmbedder import CohereEmbedder
from goldenverba.components.embedding.OllamaEmbedder import OllamaEmbedder
from goldenverba.components.embedding.UpstageEmbedder import UpstageEmbedder
from goldenverba.components.embedding.WeaviateEmbedder import WeaviateEmbedder
from goldenverba.components.embedding.VoyageAIEmbedder import VoyageAIEmbedder
from goldenverba.components.embedding.SentenceTransformersEmbedder import (
    SentenceTransformersEmbedder,
)

# Import Retrievers
from goldenverba.components.retriever.WindowRetriever import WindowRetriever

# Import Generators
from goldenverba.components.generation.CohereGenerator import CohereGenerator
from goldenverba.components.generation.AnthrophicGenerator import AnthropicGenerator
from goldenverba.components.generation.OllamaGenerator import OllamaGenerator
from goldenverba.components.generation.OpenAIGenerator import OpenAIGenerator
from goldenverba.components.generation.GroqGenerator import GroqGenerator
from goldenverba.components.generation.NovitaGenerator import NovitaGenerator
from goldenverba.components.generation.UpstageGenerator import UpstageGenerator

try:
    import tiktoken
except Exception:
    msg.warn("tiktoken not installed, your base installation might be corrupted.")

### Add new components here ###

production = os.getenv("VERBA_PRODUCTION")
if production != "Production":
    readers = [
        BasicReader(),
        HTMLReader(),
        GitReader(),
        UnstructuredReader(),
        AssemblyAIReader(),
        FirecrawlReader(),
        UpstageDocumentParseReader(),
    ]
    chunkers = [
        TokenChunker(),
        SentenceChunker(),
        RecursiveChunker(),
        SemanticChunker(),
        HTMLChunker(),
        MarkdownChunker(),
        CodeChunker(),
        JSONChunker(),
    ]
    embedders = [
        OllamaEmbedder(),
        SentenceTransformersEmbedder(),
        WeaviateEmbedder(),
        UpstageEmbedder(),
        VoyageAIEmbedder(),
        CohereEmbedder(),
        OpenAIEmbedder(),
    ]
    retrievers = [WindowRetriever()]
    generators = [
        OllamaGenerator(),
        OpenAIGenerator(),
        AnthropicGenerator(),
        CohereGenerator(),
        GroqGenerator(),
        NovitaGenerator(),
        UpstageGenerator(),
    ]
else:
    readers = [
        BasicReader(),
        HTMLReader(),
        GitReader(),
        UnstructuredReader(),
        AssemblyAIReader(),
        FirecrawlReader(),
        UpstageDocumentParseReader(),
    ]
    chunkers = [
        TokenChunker(),
        SentenceChunker(),
        RecursiveChunker(),
        SemanticChunker(),
        HTMLChunker(),
        MarkdownChunker(),
        CodeChunker(),
        JSONChunker(),
    ]
    embedders = [
        WeaviateEmbedder(),
        VoyageAIEmbedder(),
        UpstageEmbedder(),
        CohereEmbedder(),
        OpenAIEmbedder(),
    ]
    retrievers = [WindowRetriever()]
    generators = [
        OpenAIGenerator(),
        AnthropicGenerator(),
        CohereGenerator(),
        UpstageGenerator(),
    ]


### ----------------------- ###


class WeaviateManager:
    def __init__(self):
        self.document_collection_name = "VERBA_DOCUMENTS"
        self.config_collection_name = "VERBA_CONFIGURATION"
        self.suggestion_collection_name = "VERBA_SUGGESTIONS"
        self.embedding_table = {}

    ### Connection Handling

    async def connect_to_cluster(self, w_url, w_key):
        """
        Connect to Weaviate cluster (WCS or custom deployment).
        
        Prioriza configuração PaaS explícita (Railway, etc.) que requer
        portas HTTP e gRPC separadas para suportar gRPC.
        """
        if w_url is None or w_url == "":
            raise Exception("No URL provided")
        
        # PRIORIDADE 1: Verificar se há configuração PaaS explícita (Railway, etc.)
        # Isso permite usar rede privada e portas HTTP/gRPC separadas
        http_host = os.getenv("WEAVIATE_HTTP_HOST")
        grpc_host = os.getenv("WEAVIATE_GRPC_HOST")
        
        if http_host and grpc_host:
            # Configuração PaaS explícita - usar connect_to_custom com portas separadas
            msg.info(f"Connecting to Weaviate via PaaS configuration (Railway/Private Network)")
            msg.info(f"  HTTP Host: {http_host}")
            msg.info(f"  gRPC Host: {grpc_host}")
            
            http_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
            grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
            
            http_secure = os.getenv("WEAVIATE_HTTP_SECURE", "False").lower() == "true"
            grpc_secure = os.getenv("WEAVIATE_GRPC_SECURE", "False").lower() == "true"
            
            # Usar API key se disponível
            api_key = w_key or os.getenv("WEAVIATE_API_KEY_VERBA")
            # Usar AuthApiKey (mantém compatibilidade com código existente)
            auth_creds = AuthApiKey(api_key) if api_key else None
            
            try:
                # Usar connect_to_custom para PaaS (permite portas HTTP e gRPC separadas)
                client = weaviate.connect_to_custom(
                    http_host=http_host,
                    http_port=http_port,
                    http_secure=http_secure,
                    grpc_host=grpc_host,
                    grpc_port=grpc_port,
                    grpc_secure=grpc_secure,
                    auth_credentials=auth_creds,
                    skip_init_checks=False,  # Forçar verificação de saúde para debug
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=60, query=300, insert=300)
                    )
                )
                return client
            except Exception as e:
                msg.warn(f"PaaS connection failed: {str(e)[:200]}")
                msg.info("Falling back to URL-based connection...")
                # Continua para tentar método baseado em URL
        
        # PRIORIDADE 2: Weaviate Cloud (WCS) com API key
        if w_key is not None and w_key != "":
            msg.info(f"Connecting to Weaviate Cloud at {w_url} with Auth")
            return weaviate.use_async_with_weaviate_cloud(
                cluster_url=w_url,
                auth_credentials=AuthApiKey(w_key),
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=60, query=300, insert=300)
                ),
            )
        
        # PRIORIDADE 3: Conexão baseada em URL (fallback para compatibilidade)
        # Connect without auth (for Railway and other deployments without auth)
        msg.info(f"Connecting to Weaviate at {w_url} without Auth (URL-based)")
        from urllib.parse import urlparse
        parsed = urlparse(w_url)
        host = parsed.hostname or parsed.netloc.split(':')[0]
        # Default ports based on scheme
        if parsed.port:
            port = str(parsed.port)
        elif parsed.scheme == 'https':
            port = "443"
        elif parsed.scheme == 'http':
            port = "80"
        else:
            port = "8080"  # Default Weaviate port
        
        # For HTTPS or external URLs, use local connection without auth
        # NOTA: use_async_with_local não suporta gRPC adequadamente para PaaS
        # Use configuração PaaS explícita (WEAVIATE_HTTP_HOST/GRPC_HOST) para melhor performance
        return weaviate.use_async_with_local(
            host=host,
            port=int(port),
            skip_init_checks=True,
            additional_config=AdditionalConfig(
                timeout=Timeout(init=60, query=300, insert=300)
            ),
        )

    async def connect_to_docker(self, w_url):
        msg.info(f"Connecting to Weaviate Docker")
        return weaviate.use_async_with_local(
            host=w_url,
            additional_config=AdditionalConfig(
                timeout=Timeout(init=60, query=300, insert=300)
            ),
        )

    async def connect_to_custom(self, host, w_key, port):
        # Extract the port from the host
        msg.info(f"Connecting to Weaviate Custom")

        if host is None or host == "":
            raise Exception("No Host URL provided")

        # Detecta se host é URL completa ou apenas hostname
        from urllib.parse import urlparse
        is_full_url = "://" in host
        parsed_host = None
        
        if is_full_url:
            # Parse URL completa
            parsed_host = urlparse(host)
            actual_host = parsed_host.hostname or parsed_host.netloc.split(':')[0]
            scheme = parsed_host.scheme or "http"
            url_port = parsed_host.port
            
            # Se porta na URL, usa ela; senão usa a porta fornecida ou padrão baseado no scheme
            if url_port:
                port_int = url_port
            elif port:
                port_int = int(port)
            elif scheme == "https":
                port_int = 443
            else:
                port_int = 8080
                
            # Constrói URL completa
            if scheme == "https" or port_int == 443:
                url = f"https://{actual_host}"
                if port_int != 443:
                    url = f"{url}:{port_int}"
                use_https = True
            else:
                url = f"http://{actual_host}"
                if port_int != 80:
                    url = f"{url}:{port_int}"
                use_https = False
        else:
            # Apenas hostname - constrói URL baseado na porta
            actual_host = host
            port_int = int(port) if port else 8080
            
            # Remove http:// ou https:// se presente (mas não detectou antes)
            if actual_host.startswith("http://"):
                actual_host = actual_host.replace("http://", "")
                # Preserva o protocolo HTTP se explicitamente indicado
                use_https = False
                if not port:
                    port_int = 80 if port_int == 8080 else port_int
            elif actual_host.startswith("https://"):
                actual_host = actual_host.replace("https://", "")
                # Preserva o protocolo HTTPS se explicitamente indicado
                use_https = True
                if not port or port_int == 8080:
                    port_int = 443
            else:
                # Hostname puro - tenta detectar automaticamente
                # Railway na porta 8080 geralmente é HTTP, mas pode aceitar HTTPS também
                if port_int == 443:
                    use_https = True
                elif port_int == 80:
                    use_https = False
                elif ".railway.internal" in actual_host.lower():
                    # Rede interna Railway - usa HTTP direto na porta 8080
                    use_https = False
                    if port_int == 443 or not port_int:
                        port_int = 8080  # Porta padrão interna Railway
                    msg.info("Rede interna Railway detectada - usando HTTP porta 8080")
                elif ".railway.app" in actual_host.lower() and port_int == 8080:
                    # Railway porta 8080 é interna - acesso externo é via HTTPS porta 443
                    # Railway mostra porta 8080 na config, mas expõe via HTTPS na porta padrão
                    use_https = True
                    port_int = 443  # Railway expõe serviços via HTTPS na porta 443
                    msg.info("Railway porta 8080 detectado - usando HTTPS porta 443 (porta 8080 é interna)")
                elif ".railway.app" in actual_host.lower():
                    # Railway outras portas: assume HTTPS se não especificado
                    use_https = True
                    if port_int != 443:
                        port_int = 443
                else:
                    use_https = False
            
            # Reconstrói URL
            if use_https:
                url = f"https://{actual_host}" if port_int == 443 else f"https://{actual_host}:{port_int}"
            else:
                url = f"http://{actual_host}" if port_int == 80 else f"http://{actual_host}:{port_int}"

        msg.info(f"URL Weaviate: {url} (port: {port_int}, HTTPS: {use_https})")
        
        # Para HTTPS externo, usa conexão direta com URL completa
        if use_https:
            msg.info("Usando conexao HTTPS externa")
            try:
                # Para HTTPS externo (Railway, Weaviate Cloud), usa URL completa
                # weaviate-client v4 suporta HTTPS via URL completa
                if w_key is None or w_key == "":
                    # Tenta conexão via URL completa sem auth
                    # Para Railway HTTPS, tenta connect_to_custom primeiro (mais confiável)
                    try:
                        client = weaviate.connect_to_custom(
                            http_host=actual_host,
                            http_port=port_int,
                            http_secure=True,
                            grpc_host=actual_host,
                            grpc_port=50051,
                            grpc_secure=True,
                            skip_init_checks=False,
                            additional_config=AdditionalConfig(
                                timeout=Timeout(init=60, query=300, insert=300)
                            ),
                        )
                        await client.connect()
                        if await client.is_ready():
                            msg.good("Conexao HTTPS estabelecida via connect_to_custom")
                            return client
                        await client.close()
                    except Exception as e_custom:
                        msg.warn(f"connect_to_custom falhou: {str(e_custom)[:100]}")
                        
                        # Fallback: use_async_with_local
                        try:
                            client = weaviate.use_async_with_local(
                                host=actual_host,
                                port=port_int,
                                skip_init_checks=True,
                                additional_config=AdditionalConfig(
                                    timeout=Timeout(init=60, query=300, insert=300)
                                ),
                            )
                            await client.connect()
                            if await client.is_ready():
                                msg.good("Conexao HTTPS estabelecida via use_async_with_local")
                                return client
                            await client.close()
                        except Exception as e_local:
                            msg.warn(f"use_async_with_local falhou: {str(e_local)[:100]}")
                            raise e_custom  # Re-raise erro do connect_to_custom
                else:
                    # Com API key, usa auth
                    client = weaviate.use_async_with_local(
                        host=actual_host,
                        port=port_int,
                        skip_init_checks=True,
                        auth_credentials=AuthApiKey(w_key),
                        additional_config=AdditionalConfig(
                            timeout=Timeout(init=60, query=300, insert=300)
                        ),
                    )
                    await client.connect()
                    if await client.is_ready():
                        msg.good("Conexao HTTPS com auth estabelecida")
                        return client
                    await client.close()
                    raise Exception("Cliente conectado mas nao esta pronto")
            except Exception as e:
                error_str = str(e).lower()
                msg.warn(f"Tentativa HTTPS falhou: {str(e)[:150]}")
                
                # Se chegou aqui, todos os métodos falharam
                msg.warn("Todos os metodos de conexao falharam. Verifique:")
                msg.warn("  - URL do Weaviate esta correta?")
                msg.warn("  - API key esta correta?")
                msg.warn("  - Servidor Weaviate esta acessivel?")
                
                raise  # Re-raise erro original se todos os métodos falharam
        else:
            # HTTP normal - usa método padrão
            try:
                if w_key is None or w_key == "":
                    return weaviate.use_async_with_local(
                        host=actual_host,
                        port=port_int,
                        skip_init_checks=True,
                        additional_config=AdditionalConfig(
                            timeout=Timeout(init=60, query=300, insert=300)
                        ),
                    )
                else:
                    return weaviate.use_async_with_local(
                        host=actual_host,
                        port=port_int,
                        skip_init_checks=True,
                        auth_credentials=AuthApiKey(w_key),
                        additional_config=AdditionalConfig(
                            timeout=Timeout(init=60, query=300, insert=300)
                        ),
                    )
            except Exception as e:
                error_str = str(e).lower()
                
                # Para Railway porta 8080, se HTTP falhou, tenta HTTPS como fallback
                if is_railway_8080 and not use_https:
                    msg.warn(f"Conexao HTTP falhou: {str(e)[:100]}")
                    msg.info("Tentando HTTPS como fallback para Railway porta 8080...")
                    try:
                        # Tenta connect_to_custom com HTTPS
                        client = weaviate.connect_to_custom(
                            http_host=actual_host,
                            http_port=443,
                            http_secure=True,
                            grpc_host=actual_host,
                            grpc_port=50051,
                            grpc_secure=True,
                            skip_init_checks=False,
                            additional_config=AdditionalConfig(
                                timeout=Timeout(init=60, query=300, insert=300)
                            ),
                        )
                        await client.connect()
                        if await client.is_ready():
                            msg.good("Conexao HTTPS estabelecida como fallback")
                            return client
                        await client.close()
                    except Exception as e_https:
                        msg.warn(f"Tentativa HTTPS fallback falhou: {str(e_https)[:100]}")
                
                # Se falhar, re-raise erro original
                raise

    async def connect_to_embedded(self):
        msg.info(f"Connecting to Weaviate Embedded")
        return weaviate.use_async_with_embedded(
            additional_config=AdditionalConfig(
                timeout=Timeout(init=60, query=300, insert=300)
            )
        )

    async def connect(
        self, deployment: str, weaviateURL: str, weaviateAPIKey: str, port: str = "8080"
    ) -> WeaviateAsyncClient:
        try:

            if deployment == "Weaviate":
                if weaviateURL == "" and os.environ.get("WEAVIATE_URL_VERBA"):
                    weaviateURL = os.environ.get("WEAVIATE_URL_VERBA")
                if weaviateAPIKey == "" and os.environ.get("WEAVIATE_API_KEY_VERBA"):
                    weaviateAPIKey = os.environ.get("WEAVIATE_API_KEY_VERBA")
                client = await self.connect_to_cluster(weaviateURL, weaviateAPIKey)
            elif deployment == "Docker":
                client = await self.connect_to_docker("weaviate")
            elif deployment == "Local":
                client = await self.connect_to_embedded()
            elif deployment == "Custom":
                client = await self.connect_to_custom(weaviateURL, weaviateAPIKey, port)
            else:
                raise Exception(f"Invalid deployment type: {deployment}")

            if client is not None:
                # Clientes v4 já estão conectados após connect_to_*, mas verificamos ready
                # Se cliente não tem connect(), já está conectado (comportamento v4)
                try:
                    if hasattr(client, 'connect'):
                        await client.connect()
                except AttributeError:
                    # Cliente já está conectado (comportamento padrão v4)
                    pass
                
                if await client.is_ready():
                    msg.good("Succesfully Connected to Weaviate")
                    return client

            return None

        except Exception as e:
            msg.fail(f"Couldn't connect to Weaviate, check your URL/API KEY: {str(e)}")
            raise Exception(
                f"Couldn't connect to Weaviate, check your URL/API KEY: {str(e)}"
            )

    async def disconnect(self, client: WeaviateAsyncClient):
        try:
            await client.close()
            return True
        except Exception as e:
            msg.fail(f"Couldn't disconnect Weaviate: {str(e)}")
            return False

    ### Metadata

    async def get_metadata(self, client: WeaviateAsyncClient):

        # Node Information
        nodes = await client.cluster.nodes(output="verbose")
        node_payload = {"node_count": 0, "weaviate_version": "", "nodes": []}
        for node in nodes:
            node_payload["nodes"].append(
                {
                    "status": node.status,
                    "shards": len(node.shards),
                    "version": node.version,
                    "name": node.name,
                }
            )
        node_payload["node_count"] = len(nodes)
        node_payload["weaviate_version"] = nodes[0].version

        # Collection Information

        collections = await client.collections.list_all()
        collection_payload = {"collection_count": 0, "collections": []}
        for collection_name in collections:
            collection_objects = await client.collections.get(collection_name).length()
            collection_payload["collections"].append(
                {"name": collection_name, "count": collection_objects}
            )
        collection_payload["collections"].sort(key=lambda x: x["count"], reverse=True)
        collection_payload["collection_count"] = len(collections)

        return node_payload, collection_payload

    ### Collection Handling

    async def verify_collection(
        self, client: WeaviateAsyncClient, collection_name: str
    ):
        if not await client.collections.exists(collection_name):
            msg.info(
                f"Collection: {collection_name} does not exist, creating new collection."
            )
            returned_collection = await client.collections.create(name=collection_name)
            if returned_collection:
                return True
            else:
                return False
        else:
            return True

    def _normalize_embedder_name(self, embedder: str) -> str:
        """Normalize embedder name to create a valid collection name.
        
        Removes error messages and invalid characters from embedder names.
        """
        if not embedder or not isinstance(embedder, str):
            return "unknown"
        
        # Remove common error message patterns
        error_patterns = [
            r"Couldn't connect to.*",
            r"Failed to.*",
            r"Error.*",
            r"Connection.*failed.*",
            r"http://.*",
            r"https://.*",
        ]
        
        normalized = embedder
        for pattern in error_patterns:
            normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)
        
        # Remove leading/trailing whitespace and common error words
        normalized = normalized.strip()
        if not normalized or normalized.lower() in ["no config found", "unknown", ""]:
            return "unknown"
        
        # Clean up the name - only allow alphanumeric and underscore (NO HYPHENS - Weaviate doesn't allow them)
        # Replace hyphens with underscores first
        normalized = normalized.replace("-", "_")
        # Replace any other invalid characters with underscore
        normalized = re.sub(r"[^a-zA-Z0-9_]", "_", normalized)
        # Remove multiple underscores
        normalized = re.sub(r"_+", "_", normalized)
        # Remove leading/trailing underscores
        normalized = normalized.strip("_")
        
        return normalized if normalized else "unknown"

    async def verify_embedding_collection(self, client: WeaviateAsyncClient, embedder):
        if embedder not in self.embedding_table:
            normalized = self._normalize_embedder_name(embedder)
            self.embedding_table[embedder] = "VERBA_Embedding_" + normalized
            return await self.verify_collection(client, self.embedding_table[embedder])
        else:
            return True

    async def verify_cache_collection(self, client: WeaviateAsyncClient, embedder):
        if embedder not in self.embedding_table:
            normalized = self._normalize_embedder_name(embedder)
            self.embedding_table[embedder] = "VERBA_Cache_" + normalized
            return await self.verify_collection(client, self.embedding_table[embedder])
        else:
            return True

    async def verify_embedding_collections(
        self, client: WeaviateAsyncClient, environment_variables, libraries
    ):
        for embedder in embedders:
            if embedder.check_available(environment_variables, libraries):
                if "Model" in embedder.config:
                    for _embedder in embedder.config["Model"].values:
                        normalized = self._normalize_embedder_name(_embedder)
                        self.embedding_table[_embedder] = "VERBA_Embedding_" + normalized
                        await self.verify_collection(
                            client, self.embedding_table[_embedder]
                        )

    async def verify_collections(
        self, client: WeaviateAsyncClient, environment_variables, libraries
    ):
        await self.verify_collection(client, self.document_collection_name)
        await self.verify_collection(client, self.suggestion_collection_name)
        await self.verify_collection(client, self.config_collection_name)
        await self.verify_embedding_collections(
            client, environment_variables, libraries
        )
        return True

    ### Configuration Handling

    async def get_config(self, client: WeaviateAsyncClient, uuid: str) -> dict:
        if await self.verify_collection(client, self.config_collection_name):
            config_collection = client.collections.get(self.config_collection_name)
            if await config_collection.data.exists(uuid):
                config = await config_collection.query.fetch_object_by_id(uuid)
                return json.loads(config.properties["config"])
            else:
                return None

    async def set_config(self, client: WeaviateAsyncClient, uuid: str, config: dict):
        if await self.verify_collection(client, self.config_collection_name):
            config_collection = client.collections.get(self.config_collection_name)
            if await config_collection.data.exists(uuid):
                if await config_collection.data.delete_by_id(uuid):
                    await config_collection.data.insert(
                        properties={"config": json.dumps(config)}, uuid=uuid
                    )
            else:
                await config_collection.data.insert(
                    properties={"config": json.dumps(config)}, uuid=uuid
                )

    async def reset_config(self, client: WeaviateAsyncClient, uuid: str):
        if await self.verify_collection(client, self.config_collection_name):
            config_collection = client.collections.get(self.config_collection_name)
            if await config_collection.data.exists(uuid):
                await config_collection.data.delete_by_id(uuid)

    ### Import Handling

    async def import_document(
        self, client: WeaviateAsyncClient, document: Document, embedder: str
    ):
        # Verify client is connected
        try:
            if not await client.is_ready():
                raise Exception("The `WeaviateClient` is closed. Run `client.connect()` to (re)connect!")
        except Exception as e:
            if "closed" in str(e).lower() or "not connected" in str(e).lower():
                raise Exception("The `WeaviateClient` is closed. Run `client.connect()` to (re)connect!")
            raise
        
        if await self.verify_collection(
            client, self.document_collection_name
        ) and await self.verify_embedding_collection(client, embedder):
            document_collection = client.collections.get(self.document_collection_name)
            embedder_collection = client.collections.get(self.embedding_table[embedder])

            ### Import Document
            document_obj = Document.to_json(document)
            doc_uuid = await document_collection.data.insert(document_obj)

            chunk_ids = []

            try:
                for chunk in document.chunks:
                    chunk.doc_uuid = doc_uuid
                    chunk.labels = document.labels
                    chunk.title = document.title

                chunk_response = await embedder_collection.data.insert_many(
                    [
                        DataObject(properties=chunk.to_json(), vector=chunk.vector)
                        for chunk in document.chunks
                    ]
                )
                chunk_ids = [
                    chunk_response.uuids[uuid] for uuid in chunk_response.uuids
                ]

                if chunk_response.has_errors:
                    raise Exception(
                        f"Failed to ingest chunks into Weaviate: {chunk_response.errors}"
                    )

                if doc_uuid and chunk_response:
                    response = await embedder_collection.aggregate.over_all(
                        filters=Filter.by_property("doc_uuid").equal(doc_uuid),
                        total_count=True,
                    )
                    if response.total_count != len(document.chunks):
                        await document_collection.data.delete_by_id(doc_uuid)
                        for _id in chunk_ids:
                            await embedder_collection.data.delete_by_id(_id)
                        raise Exception(
                            f"Chunk Mismatch detected after importing: Imported:{response.total_count} | Existing: {len(document.chunks)}"
                        )

            except Exception as e:
                if doc_uuid:
                    await self.delete_document(client, doc_uuid)
                raise Exception(f"Chunk import failed with : {str(e)}")

    ### Document CRUD

    async def exist_document_name(self, client: WeaviateAsyncClient, name: str) -> str:
        if await self.verify_collection(client, self.document_collection_name):
            document_collection = client.collections.get(self.document_collection_name)
            aggregation = await document_collection.aggregate.over_all(total_count=True)

            if aggregation.total_count == 0:
                return None
            else:
                documents = await document_collection.query.fetch_objects(
                    filters=Filter.by_property("title").equal(name)
                )
                if len(documents.objects) > 0:
                    return documents.objects[0].uuid

            return None

    async def delete_document(self, client: WeaviateAsyncClient, uuid: str):
        if await self.verify_collection(client, self.document_collection_name):
            document_collection = client.collections.get(self.document_collection_name)

            if not await document_collection.data.exists(uuid):
                return

            document_obj = await document_collection.query.fetch_object_by_id(uuid)
            embedding_config = json.loads(document_obj.properties.get("meta"))[
                "Embedder"
            ]
            embedder = embedding_config["config"]["Model"]["value"]

            if await self.verify_embedding_collection(client, embedder):
                if await document_collection.data.delete_by_id(uuid):
                    embedder_collection = client.collections.get(
                        self.embedding_table[embedder]
                    )
                    await embedder_collection.data.delete_many(
                        where=Filter.by_property("doc_uuid").equal(uuid)
                    )

    async def delete_all_documents(self, client: WeaviateAsyncClient):
        if await self.verify_collection(client, self.document_collection_name):
            document_collection = client.collections.get(self.document_collection_name)
            async for item in document_collection.iterator():
                await self.delete_document(client, item.uuid)

    async def delete_all_configs(self, client: WeaviateAsyncClient):
        if await self.verify_collection(client, self.config_collection_name):
            config_collection = client.collections.get(self.config_collection_name)
            async for item in config_collection.iterator():
                await config_collection.data.delete_by_id(item.uuid)

    async def delete_all(self, client: WeaviateAsyncClient):
        node_payload, collection_payload = await self.get_metadata(client)
        for collection in collection_payload["collections"]:
            if "VERBA" in collection["name"]:
                await client.collections.delete(collection["name"])

    async def get_documents(
        self,
        client: WeaviateAsyncClient,
        query: str,
        pageSize: int,
        page: int,
        labels: list[str],
        properties: list[str] = None,
    ) -> list[dict]:
        if await self.verify_collection(client, self.document_collection_name):
            offset = pageSize * (page - 1)
            document_collection = client.collections.get(self.document_collection_name)

            if len(labels) > 0:
                filter = Filter.by_property("labels").contains_all(labels)
            else:
                filter = None

            response = await document_collection.aggregate.over_all(
                total_count=True, filters=filter
            )

            if response.total_count == 0:
                return [], 0

            total_count = response.total_count

            if query == "":
                total_count = response.total_count
                response = await document_collection.query.fetch_objects(
                    limit=pageSize,
                    offset=offset,
                    return_properties=properties,
                    sort=Sort.by_property("title", ascending=True),
                    filters=filter,
                )
            else:
                response = await document_collection.query.bm25(
                    query=query,
                    limit=pageSize,
                    offset=offset,
                    filters=filter,
                    return_properties=properties,
                )

            return [
                {
                    "title": doc.properties["title"],
                    "uuid": str(doc.uuid),
                    "labels": doc.properties["labels"],
                }
                for doc in response.objects
            ], total_count

    async def get_document(
        self, client: WeaviateAsyncClient, uuid: str, properties: list[str] = None
    ) -> list[dict]:
        if await self.verify_collection(client, self.document_collection_name):
            document_collection = client.collections.get(self.document_collection_name)

            if await document_collection.data.exists(uuid):
                response = await document_collection.query.fetch_object_by_id(
                    uuid, return_properties=properties
                )
                return response.properties
            else:
                msg.warn(f"Document not found ({uuid})")
                return None

    ### Labels

    async def get_labels(self, client: WeaviateAsyncClient) -> list[str]:
        if await self.verify_collection(client, self.document_collection_name):
            document_collection = client.collections.get(self.document_collection_name)
            aggregation = await document_collection.aggregate.over_all(
                group_by=GroupByAggregate(prop="labels"), total_count=True
            )
            return [
                aggregation_group.grouped_by.value
                for aggregation_group in aggregation.groups
            ]

    ### Chunks Retrieval

    async def get_chunk(
        self, client: WeaviateAsyncClient, uuid: str, embedder: str
    ) -> list[dict]:
        if await self.verify_embedding_collection(client, embedder):
            embedder_collection = client.collections.get(self.embedding_table[embedder])
            if await embedder_collection.data.exists(uuid):
                response = await embedder_collection.query.fetch_object_by_id(uuid)
                response.properties["doc_uuid"] = str(response.properties["doc_uuid"])
                return response.properties
            else:
                return None

    async def get_chunks(
        self, client: WeaviateAsyncClient, uuid: str, page: int, pageSize: int
    ) -> list[dict]:

        if await self.verify_collection(client, self.document_collection_name):

            offset = pageSize * (page - 1)

            document = await self.get_document(client, uuid, properties=["meta"])
            if document is None:
                return []

            embedding_config = json.loads(document.get("meta"))["Embedder"]
            embedder = embedding_config["config"]["Model"]["value"]

            if await self.verify_embedding_collection(client, embedder):
                embedder_collection = client.collections.get(
                    self.embedding_table[embedder]
                )

                weaviate_chunks = await embedder_collection.query.fetch_objects(
                    filters=Filter.by_property("doc_uuid").equal(uuid),
                    limit=pageSize,
                    offset=offset,
                    sort=Sort.by_property("chunk_id", ascending=True),
                )
                chunks = [obj.properties for obj in weaviate_chunks.objects]
                for chunk in chunks:
                    chunk["doc_uuid"] = str(chunk["doc_uuid"])
                return chunks

    async def get_vectors(
        self, client: WeaviateAsyncClient, uuid: str, showAll: bool
    ) -> dict:

        document = await self.get_document(client, uuid, properties=["meta", "title"])

        if document is None:
            return None

        embedding_config = json.loads(document.get("meta"))["Embedder"]
        embedder = embedding_config["config"]["Model"]["value"]

        if await self.verify_embedding_collection(client, embedder):
            embedder_collection = client.collections.get(self.embedding_table[embedder])

            if not showAll:
                batch_size = 250
                all_chunks = []
                offset = 0
                total_time = 0
                call_count = 0

                while True:
                    call_start_time = asyncio.get_event_loop().time()
                    weaviate_chunks = await embedder_collection.query.fetch_objects(
                        filters=Filter.by_property("doc_uuid").equal(uuid),
                        limit=batch_size,
                        offset=offset,
                        return_properties=["chunk_id", "pca"],
                        include_vector=True,
                    )
                    call_end_time = asyncio.get_event_loop().time()
                    call_duration = call_end_time - call_start_time
                    total_time += call_duration
                    call_count += 1

                    all_chunks.extend(weaviate_chunks.objects)

                    if len(weaviate_chunks.objects) < batch_size:
                        break

                    offset += batch_size

                dimensions = len(all_chunks[0].vector["default"])

                chunks = [
                    {
                        "vector": {"x": pca[0], "y": pca[1], "z": pca[2]},
                        "uuid": str(item.uuid),
                        "chunk_id": item.properties["chunk_id"],
                    }
                    for item in all_chunks
                    if (pca := item.properties["pca"]) is not None
                ]
                return {
                    "embedder": embedder,
                    "dimensions": dimensions,
                    "groups": [{"name": document["title"], "chunks": chunks}],
                }

            # Generate PCA for all embeddings
            else:
                vector_map = {}
                vector_list, vector_ids, vector_chunk_uuids, vector_chunk_ids = (
                    [],
                    [],
                    [],
                    [],
                )
                dimensions = 0

                async for item in embedder_collection.iterator(include_vector=True):
                    doc_uuid = item.properties["doc_uuid"]
                    chunk_uuid = item.uuid
                    if doc_uuid not in vector_map:
                        _document = await self.get_document(client, doc_uuid)
                        if _document:
                            vector_map[doc_uuid] = {
                                "name": _document["title"],
                                "chunks": [],
                            }
                        else:
                            continue
                    vector_list.append(item.vector["default"])
                    dimensions = len(item.vector["default"])
                    vector_ids.append(doc_uuid)
                    vector_chunk_uuids.append(chunk_uuid)
                    vector_chunk_ids.append(item.properties["chunk_id"])

                if len(vector_ids) > 3:
                    pca = PCA(n_components=3)
                    generated_pca_embeddings = pca.fit_transform(vector_list)
                    pca_embeddings = [
                        pca_.tolist() for pca_ in generated_pca_embeddings
                    ]

                    for pca_embedding, _uuid, _chunk_uuid, _chunk_id in zip(
                        pca_embeddings,
                        vector_ids,
                        vector_chunk_uuids,
                        vector_chunk_ids,
                    ):
                        vector_map[_uuid]["chunks"].append(
                            {
                                "vector": {
                                    "x": pca_embedding[0],
                                    "y": pca_embedding[1],
                                    "z": pca_embedding[2],
                                },
                                "uuid": str(_chunk_uuid),
                                "chunk_id": _chunk_id,
                            }
                        )

                    return {
                        "embedder": embedder,
                        "dimensions": dimensions,
                        "groups": list(vector_map.values()),
                    }
                else:
                    return {
                        "embedder": embedder,
                        "dimensions": dimensions,
                        "groups": [],
                    }

        return None

    async def hybrid_chunks(
        self,
        client: WeaviateAsyncClient,
        embedder: str,
        query: str,
        vector: list[float],
        limit_mode: str,
        limit: int,
        labels: list[str],
        document_uuids: list[str],
    ):
        if await self.verify_embedding_collection(client, embedder):
            embedder_collection = client.collections.get(self.embedding_table[embedder])

            filters = []

            if labels:
                filters.append(Filter.by_property("labels").contains_all(labels))

            if document_uuids:
                filters.append(
                    Filter.by_property("doc_uuid").contains_any(document_uuids)
                )

            if filters:
                apply_filters = filters[0]
                for filter in filters[1:]:
                    apply_filters = apply_filters & filter
            else:
                apply_filters = None

            if limit_mode == "Autocut":
                chunks = await embedder_collection.query.hybrid(
                    query=query,
                    vector=vector,
                    alpha=0.5,
                    auto_limit=limit,
                    return_metadata=MetadataQuery(score=True, explain_score=False),
                    filters=apply_filters,
                )
            else:
                chunks = await embedder_collection.query.hybrid(
                    query=query,
                    vector=vector,
                    alpha=0.5,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True, explain_score=False),
                    filters=apply_filters,
                )

            return chunks.objects

    async def hybrid_chunks_with_filter(
        self,
        client: WeaviateAsyncClient,
        embedder: str,
        query: str,
        vector: list[float],
        limit_mode: str,
        limit: int,
        labels: list[str],
        document_uuids: list[str],
        filters: "Filter" = None,
        alpha: float = 0.5,
    ):
        """
        Hybrid search com filtros entity-aware aplicados PRIMEIRO.
        
        Fluxo:
        1. Aplica WHERE filter (entity-aware)
        2. Dentro dos resultados, faz busca híbrida (BM25 + Vector)
        3. Retorna chunks filtrados + ordenados por relevância
        
        Exemplo:
        filters = Filter.by_property("entities_local_ids").contains_any(["Q123"])
        chunks = await weaviate_manager.hybrid_chunks_with_filter(
            client=client,
            embedder=embedder,
            query="inovação",
            vector=vector,
            filters=filters,
            alpha=0.6
        )
        # Retorna chunks sobre Apple (Q123) ordenados por "inovação"
        """
        if await self.verify_embedding_collection(client, embedder):
            embedder_collection = client.collections.get(self.embedding_table[embedder])

            # Constrói lista de filtros combinados
            all_filters = []

            # 1. Filtro entity-aware (principal)
            if filters:
                all_filters.append(filters)

            # 2. Filtros de labels
            if labels:
                all_filters.append(Filter.by_property("labels").contains_all(labels))

            # 3. Filtros de documentos
            if document_uuids:
                all_filters.append(
                    Filter.by_property("doc_uuid").contains_any(document_uuids)
                )

            # Combina todos os filtros com AND
            apply_filters = None
            if all_filters:
                apply_filters = all_filters[0]
                for f in all_filters[1:]:
                    apply_filters = apply_filters & f

            # Executa busca híbrida COM os filtros
            if limit_mode == "Autocut":
                chunks = await embedder_collection.query.hybrid(
                    query=query,
                    vector=vector,
                    alpha=alpha,
                    auto_limit=limit,
                    return_metadata=MetadataQuery(score=True, explain_score=False),
                    filters=apply_filters,
                )
            else:
                chunks = await embedder_collection.query.hybrid(
                    query=query,
                    vector=vector,
                    alpha=alpha,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True, explain_score=False),
                    filters=apply_filters,
                )

            return chunks.objects

    async def get_chunk_by_ids(
        self, client: WeaviateAsyncClient, embedder: str, doc_uuid: str, ids: list[int]
    ):
        if await self.verify_embedding_collection(client, embedder):
            embedder_collection = client.collections.get(self.embedding_table[embedder])
            try:
                weaviate_chunks = await embedder_collection.query.fetch_objects(
                    filters=(
                        Filter.by_property("doc_uuid").equal(str(doc_uuid))
                        & Filter.by_property("chunk_id").contains_any(list(ids))
                    ),
                    sort=Sort.by_property("chunk_id", ascending=True),
                )
                return weaviate_chunks.objects
            except Exception as e:
                msg.fail(f"Failed to fetch chunks: {str(e)}")
                raise e

    ### Suggestion Logic

    async def add_suggestion(self, client: WeaviateAsyncClient, query: str):
        if await self.verify_collection(client, self.suggestion_collection_name):
            suggestion_collection = client.collections.get(
                self.suggestion_collection_name
            )
            aggregation = await suggestion_collection.aggregate.over_all(
                total_count=True
            )
            if aggregation.total_count > 0:
                does_suggestion_exists = (
                    await suggestion_collection.query.fetch_objects(
                        filters=Filter.by_property("query").equal(query)
                    )
                )
                if len(does_suggestion_exists.objects) > 0:
                    return
            await suggestion_collection.data.insert(
                {"query": query, "timestamp": datetime.now().isoformat()}
            )

    async def retrieve_suggestions(
        self, client: WeaviateAsyncClient, query: str, limit: int
    ):
        if await self.verify_collection(client, self.suggestion_collection_name):
            suggestion_collection = client.collections.get(
                self.suggestion_collection_name
            )
            suggestions = await suggestion_collection.query.bm25(
                query=query, limit=limit
            )
            return_suggestions = [
                {
                    "query": suggestion.properties["query"],
                    "timestamp": suggestion.properties["timestamp"],
                    "uuid": str(suggestion.uuid),
                }
                for suggestion in suggestions.objects
            ]
            return return_suggestions

    async def retrieve_all_suggestions(
        self, client: WeaviateAsyncClient, page: int, pageSize: int
    ):
        if await self.verify_collection(client, self.suggestion_collection_name):
            suggestion_collection = client.collections.get(
                self.suggestion_collection_name
            )
            offset = pageSize * (page - 1)
            suggestions = await suggestion_collection.query.fetch_objects(
                limit=pageSize,
                offset=offset,
                sort=Sort.by_property("timestamp", ascending=False),
            )
            aggregation = await suggestion_collection.aggregate.over_all(
                total_count=True
            )
            return_suggestions = [
                {
                    "query": suggestion.properties["query"],
                    "timestamp": suggestion.properties["timestamp"],
                    "uuid": str(suggestion.uuid),
                }
                for suggestion in suggestions.objects
            ]
            return return_suggestions, aggregation.total_count

    async def delete_suggestions(self, client: WeaviateAsyncClient, uuid: str):
        if await self.verify_collection(client, self.suggestion_collection_name):
            suggestion_collection = client.collections.get(
                self.suggestion_collection_name
            )
            await suggestion_collection.data.delete_by_id(uuid)

    async def delete_all_suggestions(self, client: WeaviateAsyncClient):
        if await self.verify_collection(client, self.suggestion_collection_name):
            await client.collections.delete(self.suggestion_collection_name)

    ### Cache Logic

    # TODO: Implement Cache Logic

    ### Metadata Retrieval

    async def get_datacount(
        self, client: WeaviateAsyncClient, embedder: str, document_uuids: list[str] = []
    ) -> int:
        try:
            # Validate embedder name first
            normalized = self._normalize_embedder_name(embedder)
            if normalized == "unknown":
                msg.warn(f"Invalid embedder name: {embedder}, returning 0")
                return 0
            
            # Verify collection exists
            if embedder not in self.embedding_table:
                self.embedding_table[embedder] = "VERBA_Embedding_" + normalized
            
            collection_name = self.embedding_table[embedder]
            
            # Check if collection exists before querying
            if not await client.collections.exists(collection_name):
                msg.warn(f"Collection {collection_name} does not exist, returning 0")
                return 0
            
            embedder_collection = client.collections.get(collection_name)

            if document_uuids:
                filters = Filter.by_property("doc_uuid").contains_any(document_uuids)
            else:
                filters = None
            
            response = await embedder_collection.aggregate.over_all(
                filters=filters,
                group_by=GroupByAggregate(prop="doc_uuid"),
                total_count=True,
            )
            return len(response.groups)
        except Exception as e:
            msg.fail(f"Failed to retrieve data count: Query call with protocol GQL Aggregate failed with message {str(e)}")
            return 0

    async def get_chunk_count(
        self, client: WeaviateAsyncClient, embedder: str, doc_uuid: str
    ) -> int:
        if await self.verify_embedding_collection(client, embedder):
            embedder_collection = client.collections.get(self.embedding_table[embedder])
            response = await embedder_collection.aggregate.over_all(
                filters=Filter.by_property("doc_uuid").equal(doc_uuid),
                group_by=GroupByAggregate(prop="doc_uuid"),
                total_count=True,
            )
            if response.groups:
                return response.groups[0].total_count
            else:
                return 0


class ReaderManager:
    def __init__(self):
        self.readers: dict[str, Reader] = {reader.name: reader for reader in readers}

    async def load(
        self, reader: str, fileConfig: FileConfig, logger: LoggerManager
    ) -> list[Document]:
        try:
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            if reader in self.readers:
                config = fileConfig.rag_config["Reader"].components[reader].config
                documents: list[Document] = await self.readers[reader].load(
                    config, fileConfig
                )
                for document in documents:
                    document.meta["Reader"] = (
                        fileConfig.rag_config["Reader"].components[reader].model_dump()
                    )
                elapsed_time = round(loop.time() - start_time, 2)
                if len(documents) == 1:
                    await logger.send_report(
                        fileConfig.fileID,
                        FileStatus.LOADING,
                        f"Loaded {fileConfig.filename}",
                        took=elapsed_time,
                    )
                else:
                    await logger.send_report(
                        fileConfig.fileID,
                        FileStatus.LOADING,
                        f"Loaded {fileConfig.filename} with {len(documents)} documents",
                        took=elapsed_time,
                    )
                await logger.send_report(
                    fileConfig.fileID, FileStatus.CHUNKING, "", took=0
                )
                return documents
            else:
                raise Exception(f"{reader} Reader not found")

        except Exception as e:
            raise Exception(f"Reader {reader} failed with: {str(e)}")


class ChunkerManager:
    def __init__(self):
        self.chunkers: dict[str, Chunker] = {
            chunker.name: chunker for chunker in chunkers
        }

    async def chunk(
        self,
        chunker: str,
        fileConfig: FileConfig,
        documents: list[Document],
        embedder: Embedding,
        logger: LoggerManager,
    ) -> list[Document]:
        try:
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            if chunker in self.chunkers:
                config = fileConfig.rag_config["Chunker"].components[chunker].config
                embedder_config = (
                    fileConfig.rag_config["Embedder"].components[embedder.name].config
                )
                chunked_documents = await self.chunkers[chunker].chunk(
                    config=config,
                    documents=documents,
                    embedder=embedder,
                    embedder_config=embedder_config,
                )
                for chunked_document in chunked_documents:
                    chunked_document.meta["Chunker"] = (
                        fileConfig.rag_config["Chunker"]
                        .components[chunker]
                        .model_dump()
                    )
                elapsed_time = round(loop.time() - start_time, 2)
                if len(documents) == 1:
                    await logger.send_report(
                        fileConfig.fileID,
                        FileStatus.CHUNKING,
                        f"Split {fileConfig.filename} into {len(chunked_documents[0].chunks)} chunks",
                        took=elapsed_time,
                    )
                else:
                    await logger.send_report(
                        fileConfig.fileID,
                        FileStatus.CHUNKING,
                        f"Chunked all {len(chunked_documents)} documents with a total of {sum([len(document.chunks) for document in chunked_documents])} chunks",
                        took=elapsed_time,
                    )

                await logger.send_report(
                    fileConfig.fileID, FileStatus.EMBEDDING, "", took=0
                )
                return chunked_documents
            else:
                raise Exception(f"{chunker} Chunker not found")
        except Exception as e:
            raise e


class EmbeddingManager:
    def __init__(self):
        self.embedders: dict[str, Embedding] = {
            embedder.name: embedder for embedder in embedders
        }

    async def vectorize(
        self,
        embedder: str,
        fileConfig: FileConfig,
        documents: list[Document],
        logger: LoggerManager,
    ) -> list[Document]:
        """Vectorizes chunks in batches
        @parameter: documents : Document - Verba document
        @returns Document - Document with vectorized chunks
        """
        try:
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            msg.info(f"[EMBEDDER] Starting vectorize: embedder={embedder}, documents={len(documents)}")
            
            if embedder not in self.embedders:
                raise Exception(f"{embedder} Embedder not found")
            
            config = fileConfig.rag_config["Embedder"].components[embedder].config
            msg.info(f"[EMBEDDER] Config loaded for embedder: {embedder}")

                for doc_idx, document in enumerate(documents):
                    msg.info(f"[EMBEDDER] Processing document {doc_idx+1}/{len(documents)}: {document.title[:50]}...")
                    content = [
                        document.metadata + "\n" + chunk.content
                        for chunk in document.chunks
                    ]
                    msg.info(f"[EMBEDDER] Document has {len(content)} chunks to vectorize")
                    
                    try:
                        # Pass logger and file_id to enable progress updates (keep-alive)
                        embeddings = await self.batch_vectorize(
                            embedder, config, content, logger, fileConfig.fileID
                        )
                        msg.info(f"[EMBEDDER] Generated {len(embeddings)} embeddings for document {doc_idx+1}")
                    except Exception as e:
                        msg.fail(f"[EMBEDDER] Batch vectorize failed for document {doc_idx+1}: {type(e).__name__}: {str(e)}")
                        import traceback
                        msg.fail(f"[EMBEDDER] Traceback: {traceback.format_exc()}")
                        raise

                    if len(embeddings) >= 3:
                        pca = PCA(n_components=3)
                        generated_pca_embeddings = pca.fit_transform(embeddings)
                        pca_embeddings = [
                            pca_.tolist() for pca_ in generated_pca_embeddings
                        ]
                    else:
                        pca_embeddings = [embedding[0:3] for embedding in embeddings]

                    for vector, chunk, pca_ in zip(
                        embeddings, document.chunks, pca_embeddings
                    ):
                        chunk.vector = vector
                        chunk.pca = pca_

                    document.meta["Embedder"] = (
                        fileConfig.rag_config["Embedder"]
                        .components[embedder]
                        .model_dump()
                    )

                elapsed_time = round(loop.time() - start_time, 2)
                msg.info(f"[EMBEDDER] Vectorization completed in {elapsed_time}s")
                
                try:
                    await logger.send_report(
                        fileConfig.fileID,
                        FileStatus.EMBEDDING,
                        f"Vectorized all chunks",
                        took=elapsed_time,
                    )
                except Exception as e:
                    msg.warn(f"[EMBEDDER] Failed to send embedding report: {str(e)}")
                
                try:
                    await logger.send_report(
                        fileConfig.fileID, FileStatus.INGESTING, "", took=0
                    )
                except Exception as e:
                    msg.warn(f"[EMBEDDER] Failed to send ingesting report: {str(e)}")
                
                return documents
        except Exception as e:
            msg.fail(f"[EMBEDDER] Vectorize failed: {type(e).__name__}: {str(e)}")
            import traceback
            msg.fail(f"[EMBEDDER] Full traceback: {traceback.format_exc()}")
            raise

    async def batch_vectorize(
        self, embedder: str, config: dict, content: list[str], logger: LoggerManager = None, file_id: str = None
    ) -> list[list[float]]:
        """Vectorize content in batches with progress updates to keep WebSocket alive"""
        try:
            max_batch_size = self.embedders[embedder].max_batch_size
            batches = [
                content[i : i + max_batch_size]
                for i in range(0, len(content), max_batch_size)
            ]
            msg.info(f"[BATCH_VECTORIZE] Vectorizing {len(content)} chunks in {len(batches)} batches (batch_size={max_batch_size})")
            
            # Send initial progress update
            if logger and file_id:
                try:
                    await logger.send_report(
                        file_id,
                        FileStatus.EMBEDDING,
                        f"Starting vectorization: {len(batches)} batches",
                        took=0,
                    )
                except Exception:
                    pass  # Ignore if WebSocket is closed
            
            # Create tasks for parallel processing
            tasks = [
                self.embedders[embedder].vectorize(config, batch) for batch in batches
            ]
            msg.info(f"[BATCH_VECTORIZE] Created {len(tasks)} vectorization tasks")
            
            # Start progress monitoring task to keep WebSocket alive
            async def send_progress_updates():
                """Send periodic progress updates during vectorization"""
                completed = 0
                total = len(batches)
                while completed < total:
                    await asyncio.sleep(5)  # Send update every 5 seconds
                    if logger and file_id:
                        progress = round((completed / total) * 100, 1) if total > 0 else 0
                        try:
                            await logger.send_report(
                                file_id,
                                FileStatus.EMBEDDING,
                                f"Vectorizing: {completed}/{total} batches completed ({progress}%)",
                                took=0,
                            )
                        except Exception:
                            pass  # Ignore if WebSocket is closed
            
            # Start progress monitoring (will run until all tasks complete)
            progress_task = asyncio.create_task(send_progress_updates())
            
            # Execute all tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Cancel progress monitoring
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            
            msg.info(f"[BATCH_VECTORIZE] All {len(results)} batches processed")

            # Check if all tasks were successful
            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                error_messages = [f"{type(e).__name__}: {str(e)}" for e in errors]
                msg.fail(f"[BATCH_VECTORIZE] {len(errors)}/{len(results)} batches failed")
                for idx, error in enumerate(errors):
                    msg.fail(f"[BATCH_VECTORIZE] Batch {idx} error: {type(error).__name__}: {str(error)}")
                raise Exception(
                    f"Vectorization failed for {len(errors)}/{len(results)} batches: {', '.join(error_messages[:3])}"
                )

            # Flatten the results
            flattened_results = [item for sublist in results for item in sublist]
            msg.info(f"[BATCH_VECTORIZE] Flattened results: {len(flattened_results)} vectors from {len(results)} batches")

            # Verify the number of vectors matches the input content
            if len(flattened_results) != len(content):
                msg.fail(f"[BATCH_VECTORIZE] Mismatch: expected {len(content)} vectors, got {len(flattened_results)}")
                raise Exception(
                    f"Mismatch in vectorization results: expected {len(content)} vectors, got {len(flattened_results)}"
                )

            msg.info(f"[BATCH_VECTORIZE] Successfully vectorized {len(flattened_results)} chunks")
            return flattened_results
        except Exception as e:
            msg.fail(f"[BATCH_VECTORIZE] Batch vectorization failed: {type(e).__name__}: {str(e)}")
            import traceback
            msg.fail(f"[BATCH_VECTORIZE] Traceback: {traceback.format_exc()}")
            raise Exception(f"Batch vectorization failed: {str(e)}")

    async def vectorize_query(
        self, embedder: str, content: str, rag_config: dict
    ) -> list[float]:
        try:
            if embedder in self.embedders:
                config = rag_config["Embedder"].components[embedder].config
                embeddings = await self.embedders[embedder].vectorize(config, [content])
                return embeddings[0]
            else:
                raise Exception(f"{embedder} Embedder not found")
        except Exception as e:
            raise e


class RetrieverManager:
    def __init__(self):
        self.retrievers: dict[str, Retriever] = {
            retriever.name: retriever for retriever in retrievers
        }

    async def retrieve(
        self,
        client,
        retriever: str,
        query: str,
        vector: list[float],
        rag_config: dict,
        weaviate_manager: WeaviateManager,
        labels: list[str],
        document_uuids: list[str],
    ):
        try:
            if retriever not in self.retrievers:
                raise Exception(f"Retriever {retriever} not found")

            embedder_model = (
                rag_config["Embedder"]
                .components[rag_config["Embedder"].selected]
                .config["Model"]
                .value
            )
            config = rag_config["Retriever"].components[retriever].config
            documents, context = await self.retrievers[retriever].retrieve(
                client,
                query,
                vector,
                config,
                weaviate_manager,
                embedder_model,
                labels,
                document_uuids,
            )
            return (documents, context)

        except Exception as e:
            raise e


class GeneratorManager:
    def __init__(self):
        self.generators: dict[str, Generator] = {
            generator.name: generator for generator in generators
        }

    async def generate_stream(self, rag_config, query, context, conversation):
        """Generate a stream of response dicts based on a list of queries and list of contexts, and includes conversational context
        @parameter: queries : list[str] - List of queries
        @parameter: context : list[str] - List of contexts
        @parameter: conversation : dict - Conversational context
        @returns Iterator[dict] - Token response generated by the Generator in this format {system:TOKEN, finish_reason:stop or empty}.
        """

        generator = rag_config["Generator"].selected
        generator_config = (
            rag_config["Generator"].components[rag_config["Generator"].selected].config
        )

        if generator not in self.generators:
            raise Exception(f"Generator {generator} not found")

        async for result in self.generators[generator].generate_stream(
            generator_config, query, context, conversation
        ):
            yield result

    def truncate_conversation_dicts(
        self, conversation_dicts: list[dict[str, any]], max_tokens: int
    ) -> list[dict[str, any]]:
        """
        Truncate a list of conversation dictionaries to fit within a specified maximum token limit.

        @parameter conversation_dicts: List[Dict[str, any]] - A list of conversation dictionaries that may contain various keys, where 'content' key is present and contains text data.
        @parameter max_tokens: int - The maximum number of tokens that the combined content of the truncated conversation dictionaries should not exceed.

        @returns List[Dict[str, any]]: A list of conversation dictionaries that have been truncated so that their combined content respects the max_tokens limit. The list is returned in the original order of conversation with the most recent conversation being truncated last if necessary.

        """
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        accumulated_tokens = 0
        truncated_conversation_dicts = []

        # Start with the newest conversations
        for item_dict in reversed(conversation_dicts):
            item_tokens = encoding.encode(item_dict["content"], disallowed_special=())

            # If adding the entire new item exceeds the max tokens
            if accumulated_tokens + len(item_tokens) > max_tokens:
                # Calculate how many tokens we can add from this item
                remaining_space = max_tokens - accumulated_tokens
                truncated_content = encoding.decode(item_tokens[:remaining_space])

                # Create a new truncated item dictionary
                truncated_item_dict = {
                    "type": item_dict["type"],
                    "content": truncated_content,
                    "typewriter": item_dict["typewriter"],
                }

                truncated_conversation_dicts.append(truncated_item_dict)
                break

            truncated_conversation_dicts.append(item_dict)
            accumulated_tokens += len(item_tokens)

        # The list has been built in reverse order so we reverse it again
        return list(reversed(truncated_conversation_dicts))
