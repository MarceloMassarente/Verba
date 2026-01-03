from verba_extensions.embedders.hybrid_embedder import HybridConsultingEmbedder

def register():
    """Register the Hybrid Consulting Embedder plugin"""
    return {
        'name': 'HybridConsultingEmbedder',
        'version': '1.0.0',
        'description': 'Premium Default (Voyage AI) + Universal Named Vectors (MiniLM L12-v2). Adaptive Context.',
        'embedders': [HybridConsultingEmbedder()],
        'compatible_verba_version': '>=2.0.0'
    }
