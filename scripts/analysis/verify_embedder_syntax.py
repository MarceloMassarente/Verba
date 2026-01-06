
try:
    from verba_extensions.embedders.hybrid_embedder import HybridConsultingEmbedder
    print("✅ Import bem sucedido")
    embedder = HybridConsultingEmbedder()
    print("✅ Instanciação bem sucedida")
    
    # Check if critical methods exist
    if hasattr(embedder, 'vectorize_with_named_vectors'):
        print("✅ Método vectorize_with_named_vectors existe")
    if hasattr(embedder, '_embed_voyage_contextual_batch'):
        print("✅ Método _embed_voyage_contextual_batch existe")
        
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
