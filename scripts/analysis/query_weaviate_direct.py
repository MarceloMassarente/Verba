"""
Query Weaviate diretamente para verificar collections e dados
"""
import requests
import json

# Usar a URL INTERNA do Railway (mesma rede)
WEAVIATE_URL = "http://weaviate.railway.internal:8080"

def list_collections():
    """Lista todas as collections no Weaviate"""
    try:
        response = requests.get(f"{WEAVIATE_URL}/v1/schema")
        if response.status_code == 200:
            schema = response.json()
            classes = schema.get("classes", [])
            
            print(f"\n📊 Total de collections: {len(classes)}")
            print("=" * 80)
            
            # Separar por tipo
            embedding_collections = []
            other_collections = []
            
            for cls in classes:
                name = cls["class"]
                if "VERBA_Embedding_" in name:
                    embedding_collections.append(name)
                else:
                    other_collections.append(name)
            
            print(f"\n🔹 Embedding Collections ({len(embedding_collections)}):")
            for name in sorted(embedding_collections):
                model = name.replace("VERBA_Embedding_", "")
                print(f"   - {model}")
            
            print(f"\n🔹 Other Collections ({len(other_collections)}):")
            for name in sorted(other_collections):
                print(f"   - {name}")
            
            return embedding_collections
        else:
            print(f"❌ Erro ao listar schema: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Erro: {e}")
        return []

def count_objects(collection_name):
    """Conta objetos em uma collection usando GraphQL"""
    try:
        query = {
            "query": f"""
            {{
                Aggregate {{
                    {collection_name} {{
                        meta {{
                            count
                        }}
                    }}
                }}
            }}
            """
        }
        
        response = requests.post(
            f"{WEAVIATE_URL}/v1/graphql",
            json=query,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and "Aggregate" in data["data"]:
                agg_data = data["data"]["Aggregate"].get(collection_name, [])
                if agg_data and len(agg_data) > 0:
                    return agg_data[0]["meta"]["count"]
        return 0
    except Exception as e:
        print(f"  ⚠️ Erro ao contar {collection_name}: {e}")
        return 0

def search_in_collection(collection_name, query_text="caminhões"):
    """Tenta buscar na collection"""
    try:
        query = {
            "query": f"""
            {{
                Get {{
                    {collection_name}(
                        limit: 3
                        bm25: {{
                            query: "{query_text}"
                        }}
                    ) {{
                        text
                        doc_name
                        chunk_id
                    }}
                }}
            }}
            """
        }
        
        response = requests.post(
            f"{WEAVIATE_URL}/v1/graphql",
            json=query,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and "Get" in data["data"]:
                results = data["data"]["Get"].get(collection_name, [])
                return results
        return []
    except Exception as e:
        print(f"  ⚠️ Erro ao buscar em {collection_name}: {e}")
        return []

def main():
    print("=" * 80)
    print("🔍 QUERY DIRETO NO WEAVIATE (Railway Internal)")
    print("=" * 80)
    
    # Lista collections
    embedding_collections = list_collections()
    
    if not embedding_collections:
        print("\n❌ Não conseguiu listar collections")
        return
    
    # Conta documentos em cada collection de embedding
    print("\n" + "=" * 80)
    print("📊 CONTAGEM DE DOCUMENTOS")
    print("=" * 80)
    
    populated = []
    for collection in sorted(embedding_collections):
        count = count_objects(collection)
        model = collection.replace("VERBA_Embedding_", "")
        
        if count > 0:
            populated.append((collection, model, count))
            print(f"\n✅ {model}")
            print(f"   Collection: {collection}")
            print(f"   Documentos: {count}")
            
            # Tentar buscar
            results = search_in_collection(collection, "caminhões")
            if results:
                print(f"   🔍 Busca 'caminhões': {len(results)} resultados")
                for i, result in enumerate(results[:2], 1):
                    text = result.get("text", "")[:80]
                    doc = result.get("doc_name", "N/A")
                    print(f"      {i}. {doc}: {text}...")
        else:
            print(f"⚪ {model}: 0 docs")
    
    # Resumo
    print("\n" + "=" * 80)
    print("📋 RESUMO")
    print("=" * 80)
    print(f"\nCollections com dados: {len(populated)}")
    for collection, model, count in populated:
        print(f"  ✅ {model}: {count} documentos")
    
    if populated:
        main_collection, main_model, main_count = populated[0]
        print(f"\n💡 Collection principal: {main_model}")
        print(f"   Use este embedder no RAG config para queries funcionarem!")

if __name__ == "__main__":
    main()
