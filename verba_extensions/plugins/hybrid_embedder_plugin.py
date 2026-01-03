from goldenverba.components.interfaces import EmbedderPlugin
from goldenverba.components.interfaces import Embedder
from verba_extensions.embedders.hybrid_embedder import HybridConsultingEmbedder

class HybridEmbedderPlugin(EmbedderPlugin):
    """
    Plugin para o Hybrid Consulting Embedder.
    Roteia automaticamente entre Voyage (default) e MiniLM (named vectors).
    """

    def __init__(self):
        super().__init__()
        self.name = "HybridConsultingEmbedder"
        self.description = "Premium Default (Voyage AI) + Universal Named Vectors (MiniLM L12-v2). Adaptive Context."

    def get_embedder(self) -> Embedder:
        return HybridConsultingEmbedder()
