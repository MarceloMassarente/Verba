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
        self._model_cache = {}  # Cache de modelos para evitar recarregamento
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

    def _get_or_load_model(self, model_name: str):
        """
        Obtém modelo do cache ou carrega uma única vez.
        Evita problemas de meta tensor ao recarregar modelo várias vezes.
        """
        if model_name not in self._model_cache:
            try:
                # Importar wasabi para logging
                from wasabi import msg
                
                msg.info(f"[SentenceTransformersEmbedder] Carregando modelo: {model_name}")
                
                # Forçar device explícito para evitar meta tensor issues
                device = self._get_device()
                
                model = SentenceTransformer(
                    model_name,
                    device=device,
                    trust_remote_code=True
                )
                
                # Garantir que modelo está em modo de inferência
                model.eval()
                
                self._model_cache[model_name] = model
                msg.good(f"[SentenceTransformersEmbedder] ✅ Modelo carregado em device: {device}")
            except Exception as e:
                from wasabi import msg
                msg.fail(f"[SentenceTransformersEmbedder] ❌ Erro ao carregar modelo: {str(e)}")
                raise
        
        return self._model_cache[model_name]
    
    def _get_device(self) -> str:
        """
        Detecta device disponível de forma segura.
        Prioriza CPU por default para evitar meta tensor issues.
        """
        try:
            import torch
            
            # Verificar se CUDA está disponível (mas usar CPU por default)
            if torch.cuda.is_available():
                # Tentar usar CUDA apenas se explicitamente configurado
                try:
                    # Test CUDA
                    _ = torch.zeros(1).to("cuda")
                    return "cuda"
                except Exception:
                    # Fallback para CPU se CUDA falhar
                    pass
        except Exception:
            pass
        
        return "cpu"

    async def vectorize(self, config: dict, content: list[str]) -> list[float]:
        """Vectorize chunks using SentenceTransformer (runs in executor)."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._vectorize_sync, config, content)

    def _vectorize_sync(self, config: dict, content: list[str]) -> list[float]:
        """Synchronous implementation of vectorization."""
        try:
            from wasabi import msg
            
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
                    model = self._get_or_load_model(model_name)
                    return model.encode([t], convert_to_tensor=False)[0].tolist()
                
                embedding, was_cached = get_cached_embedding(
                    text=text,
                    cache_key=cache_key,
                    embed_fn=_embed_single,
                    enable_cache=True
                )
                return [embedding]
            
            # Para batches, usar modelo do cache
            msg.info(f"[SentenceTransformersEmbedder] Vetorizando {len(content)} chunks com modelo: {model_name}")
            
            model = self._get_or_load_model(model_name)
            
            # Encoding com convert_to_tensor=False evita meta tensor issues
            embeddings = model.encode(
                content,
                convert_to_tensor=False,
                show_progress_bar=False
            )
            
            # Converter para lista se necessário
            if hasattr(embeddings, 'tolist'):
                return embeddings.tolist()
            else:
                return embeddings.tolist() if isinstance(embeddings, list) else list(embeddings)
            
        except Exception as e:
            from wasabi import msg
            msg.fail(f"[SentenceTransformersEmbedder] ❌ Erro na vetorização: {str(e)}")
            import traceback
            msg.fail(f"[SentenceTransformersEmbedder] Traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to vectorize chunks: {str(e)}")
