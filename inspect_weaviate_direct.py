"""
Direct Weaviate inspection to understand data distribution across collections
"""
import requests
import json

# Railway Weaviate public endpoint
WEAVIATE_URL = "http://weaviate-production-0d0e.up.railway.app:8080"

def get_schema():
    """Get the full Weaviate schema"""
    try:
        response = requests.get(f"{WEAVIATE_URL}/v1/schema")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Failed to get schema: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting schema: {e}")
        return None

def count_objects_in_collection(collection_name):
    """Count objects in a specific collection"""
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
            if 'data' in data and 'Aggregate' in data['data']:
                agg = data['data']['Aggregate'].get(collection_name, [])
                if agg and len(agg) > 0:
                    return agg[0]['meta']['count']
        return 0
    except Exception as e:
        print(f"  ⚠️ Error counting {collection_name}: {e}")
        return 0

def sample_objects(collection_name, limit=3):
    """Get sample objects from a collection"""
    try:
        query = {
            "query": f"""
            {{
                Get {{
                    {collection_name}(limit: {limit}) {{
                        _additional {{
                            id
                        }}
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
            if 'data' in data and 'Get' in data['data']:
                return data['data']['Get'].get(collection_name, [])
        return []
    except Exception as e:
        print(f"  ⚠️ Error sampling {collection_name}: {e}")
        return []

def main():
    print("=" * 80)
    print("🔍 WEAVIATE DIRECT INSPECTION")
    print("=" * 80)
    
    # Get schema
    print("\n[1] Fetching Weaviate schema...")
    schema = get_schema()
    
    if not schema or 'classes' not in schema:
        print("❌ Could not retrieve schema")
        return
    
    # Find all embedding collections
    embedding_collections = []
    other_collections = []
    
    for cls in schema['classes']:
        name = cls['class']
        if name.startswith('VERBA_Embedding_'):
            embedding_collections.append(name)
        else:
            other_collections.append(name)
    
    print(f"\n[2] Found {len(embedding_collections)} embedding collections")
    print(f"    Found {len(other_collections)} other collections")
    
    # Count objects in each embedding collection
    print("\n[3] Counting documents in each EMBEDDING collection:")
    print("-" * 80)
    
    collection_counts = []
    for collection in sorted(embedding_collections):
        count = count_objects_in_collection(collection)
        collection_counts.append((collection, count))
        
        # Extract the embedder name from collection name
        embedder_model = collection.replace('VERBA_Embedding_', '').replace('_', '-')
        
        if count > 0:
            print(f"✅ {collection}")
            print(f"   📊 Count: {count} documents")
            print(f"   🔧 Model: {embedder_model}")
            
            # Sample a few documents
            samples = sample_objects(collection, limit=2)
            if samples:
                for i, sample in enumerate(samples[:2], 1):
                    text = sample.get('text', '')[:100]
                    doc_name = sample.get('doc_name', 'N/A')
                    print(f"   📄 Sample {i}: {doc_name}")
                    print(f"      Text: {text}...")
            print()
        else:
            print(f"⚪ {collection}: 0 documents")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    
    populated = [(name, count) for name, count in collection_counts if count > 0]
    empty = [(name, count) for name, count in collection_counts if count == 0]
    
    print(f"\n✅ Populated collections: {len(populated)}")
    for name, count in populated:
        model = name.replace('VERBA_Embedding_', '').replace('_', '-')
        print(f"   - {model}: {count} docs")
    
    print(f"\n⚪ Empty collections: {len(empty)}")
    
    # Check other collections
    print(f"\n[4] Checking other collections:")
    print("-" * 80)
    for collection in other_collections:
        count = count_objects_in_collection(collection)
        print(f"   {collection}: {count} documents")
    
    print("\n" + "=" * 80)
    print("✅ INSPECTION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
