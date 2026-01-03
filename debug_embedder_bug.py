"""
Quick test to verify the embedder name normalization bug
"""

# Simula o que acontece no código
embedder_sent_from_test = "SentenceTransformers"

# O que o código faz (BUGADO):
def normalize_bad(embedder):
    normalized = embedder.replace("-", "_")
    return normalized

# embedding_table vazio inicialmente
embedding_table = {}

# Linha 1218: normalized = weaviate_manager._normalize_embedder_name(embedder)
normalized = normalize_bad(embedder_sent_from_test)
print(f"1. Embedder enviado pelo teste: '{embedder_sent_from_test}'")
print(f"2. Normalizado: '{normalized}'")

# Linha 1219: collection_name = weaviate_manager.embedding_table.get(embedder, f"VERBA_Embedding_{normalized}")
# BUG: Usa 'embedder' (não normalizado) como key, mas fallback com 'normalized'
collection_name = embedding_table.get(embedder_sent_from_test, f"VERBA_Embedding_{normalized}")
print(f"3. Collection procurada: '{collection_name}'")

print(f"\n❌ PROBLEMA: O teste envia 'SentenceTransformers'")
print(f"             Mas a collection real é 'VERBA_Embedding_all_MiniLM_L6_v2'")
print(f"             Não tem correspondência!")

# Mas a collection REAL no Weaviate (que vimos nos logs) é:
real_collection = "VERBA_Embedding_all_MiniLM_L6_v2"
print(f"\n🔍 Collection real no Weaviate: '{real_collection}'")
print(f"   Collection que o código busca: '{collection_name}'")
print(f"   Match: {real_collection == collection_name}")
