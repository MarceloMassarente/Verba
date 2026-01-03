from verba_extensions.readers.unified_consulting_ingestor import UnifiedConsultingIngestor

def register():
    """Register the Unified Consulting Ingestor plugin"""
    return {
        'name': 'UnifiedConsultingIngestor',
        'version': '1.0.0',
        'description': 'Unified Reader for PPTX/PDF (Visual API, Docling) and Markdown',
        'readers': [UnifiedConsultingIngestor()],
        'compatible_verba_version': '>=2.0.0'
    }
