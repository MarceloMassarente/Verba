import os
import asyncio
from typing import List, Optional
from wasabi import msg

# Dependências opcionais
try:
    import voyageai
    VOYAGE_AVAILABLE = True
except ImportError:
    VOYAGE_AVAILABLE = False
    
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_AVAILABLE = True
except ImportError:
    SENTENCE_AVAILABLE = False

from goldenverba.components.interfaces import Embedder
from goldenverba.components.types import InputConfig

class HybridMultiEmbedder(Embedder):
    """
    HybridMultiEmbedder: Estratégia de Embedding Assimétrica
    
    1. Default Vector: Usa Voyage 3.5 (Premium, 1024 dims)
       - Para busca semântica principal de alta qualidade.
       
    2. Named Vectors (concept, company, sector): Usa MiniLM (Local, 384 dims)
       - Para filtros rápidos e alta eficiência.
       - Custo zero, executa localmente.
       
    Requires:
    - voyageai (pip install voyageai)
    - sentence-transformers (pip install sentence-transformers)
    - VOYAGE_API_KEY env var
    """

    def __init__(self):
        super().__init__()
        self.name = "HybridMultiEmbedder"
        self.description = "Premium Default (Voyage AI) + Fast Named Vectors (MiniLM). Best for Unified Consulting Ingestor."
        self.requires_library = ["voyageai", "sentence_transformers"]
        
        # Configs
        self.config = {
            "Voyage Model": InputConfig(
                type="text",
                value="voyage-3.5",
                description="Model for default vector",
                values=["voyage-large-2", "voyage-code-2", "voyage-2", "voyage-lite-02-instruct", "voyage-3.5"],
            ),
            "Local Model": InputConfig(
                type="text",
                value="all-MiniLM-L6-v2",
                description="Model for named vectors (concept, company, sector)",
                values=["all-MiniLM-L6-v2", "paraphrase-multilingual-MiniLM-L12-v2"],
            )
        }
        
        # Clients (Lazy Loaded)
        self.voyage_client = None
        self.local_model = None

    def _get_voyage_client(self):
        if not VOYAGE_AVAILABLE:
            raise ImportError("voyageai library is missing")
            
        if self.voyage_client is None:
            api_key = os.environ.get("VOYAGE_API_KEY")
            if not api_key:
                msg.fail("[HybridMultiEmbedder] VOYAGE_API_KEY not found in env")
                # Não lança erro aqui para não quebrar init, falha no vectorize
                return None
            self.voyage_client = voyageai.Client(api_key=api_key)
            msg.good("[HybridMultiEmbedder] Voyage Client initialized")
        return self.voyage_client

    def _get_local_model(self, model_name="all-MiniLM-L6-v2"):
        if not SENTENCE_AVAILABLE:
            raise ImportError("sentence-transformers library is missing")
            
        if self.local_model is None:
            msg.info(f"[HybridMultiEmbedder] Loading local model: {model_name}...")
            self.local_model = SentenceTransformer(model_name)
            msg.good(f"[HybridMultiEmbedder] Local model {model_name} loaded")
        return self.local_model

    async def vectorize(self, config: dict, content: List[str]) -> List[List[float]]:
        """
        Default vectorization (assume 'default' target).
        Uses Voyage AI.
        """
        return await self.vectorize_named(config, content, vector_name="default")

    async def vectorize_named(self, config: dict, content: List[str], vector_name: str = "default") -> List[List[float]]:
        """
        Smart routing based on vector_name.
        """
        try:
            # 1. Default Vector -> Voyage AI (Premium)
            if vector_name == "default":
                client = self._get_voyage_client()
                if not client:
                     raise ValueError("Voyage Client not available (check API Key)")
                     
                model = config.get("Voyage Model", {}).get("value", "voyage-3.5")
                
                # Voyage sync call mapped to async
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: client.embed(content, model=model, input_type="document")
                )
                return result.embeddings

            # 2. Named Vectors -> Local MiniLM (Fast/Free)
            else:
                local_model_name = config.get("Local Model", {}).get("value", "all-MiniLM-L6-v2")
                model = self._get_local_model(local_model_name)
                
                # Check for empty content to avoid errors
                if not content or not content[0].strip():
                    return [[0.0] * 384 for _ in content] # Return zero vector if empty

                # SentenceTransformers runs on CPU/GPU
                loop = asyncio.get_event_loop()
                embeddings = await loop.run_in_executor(
                    None,
                    lambda: model.encode(content).tolist()
                )
                return embeddings

        except Exception as e:
            msg.fail(f"[HybridMultiEmbedder] Error in vectorize_named ({vector_name}): {str(e)}")
            # Fallback para evitar crash total: retorna vetor dummy ou erro
            raise e

def register():
    """Register the plugin"""
    return {
        'name': 'HybridMultiEmbedder',
        'version': '1.0.0',
        'description': 'Hybrid Embedder (Voyage + MiniLM) for Cost Optimization',
        'embedders': [HybridMultiEmbedder()],
        'compatible_verba_version': '>=2.0.0'
    }
