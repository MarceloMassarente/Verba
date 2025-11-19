from goldenverba.components.interfaces import Embedding
from goldenverba.components.types import InputConfig

try:
    from sentence_transformers import SentenceTransformer
except Exception as e:
    pass


class SentenceTransformersEmbedder(Embedding):
    """
    SentenceTransformersEmbedder base class for Verba.
    """

    def __init__(self):
        super().__init__()
        self.name = "SentenceTransformers"
        self.requires_library = ["sentence_transformers"]
        self.description = "Embeds and retrieves objects using SentenceTransformer"
        self.config = {
            "Model": InputConfig(
                type="dropdown",
                value="all-MiniLM-L6-v2",
                description="Select an HuggingFace Embedding Model",
                values=[
                    "all-MiniLM-L6-v2",
                    "mixedbread-ai/mxbai-embed-large-v1",
                    "all-mpnet-base-v2",
                    "BAAI/bge-m3",
                    "all-MiniLM-L12-v2",
                    "paraphrase-MiniLM-L6-v2",
                ],
            ),
        }

    async def vectorize(self, config: dict, content: list[str]) -> list[float]:
        """Vectorize chunks using SentenceTransformer (runs in executor)."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._vectorize_sync, config, content)

    def _vectorize_sync(self, config: dict, content: list[str]) -> list[float]:
        """Synchronous implementation of vectorization."""
        try:
            # Embeddings Cache (RAG2) - integrado para queries únicas
            use_cache = False
            if len(content) == 1:
                try:
                    from verba_extensions.utils.embeddings_cache import (
                        get_cached_embedding,
                        get_cache_key
                    )
                    use_cache = True
                except ImportError:
                    pass
            
            model_name = config.get("Model").value
            
            # Se cache disponível e apenas 1 item (query), usar cache
            if use_cache:
                text = content[0]
                cache_key = get_cache_key(text=text, doc_uuid="", parent_type="query")
                
                def _embed_single(t: str) -> list[float]:
                    model = SentenceTransformer(model_name)
                    return model.encode([t])[0].tolist()
                
                embedding, was_cached = get_cached_embedding(
                    text=text,
                    cache_key=cache_key,
                    embed_fn=_embed_single,
                    enable_cache=True
                )
                return [embedding]
            
            # Para batches, processar normalmente
            model = SentenceTransformer(model_name)
            embeddings = model.encode(content).tolist()
            return embeddings
        except Exception as e:
            raise Exception(f"Failed to vectorize chunks: {str(e)}")
