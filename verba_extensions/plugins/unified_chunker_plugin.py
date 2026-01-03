from verba_extensions.plugins.slides_semantica_visual_chunker import SlidesSemanticaVisualChunker

# Alias para Unified Architecture
class UnifiedSemanticChunker(SlidesSemanticaVisualChunker):
    def __init__(self):
        super().__init__()
        self.name = "Unified Semantic Chunker"
        self.description = "Chunker Unificado (Slides Semântica Visual) com suporte a frameworks, stakeholders e guarda-corpos."

def register():
    """Register the Unified Semantic Chunker plugin"""
    return {
        'name': 'UnifiedSemanticChunker',
        'version': '1.0.0',
        'description': 'Unified Chunker alias for SlidesSemanticaVisualChunker',
        'chunkers': [UnifiedSemanticChunker()],
        'compatible_verba_version': '>=2.0.0'
    }
