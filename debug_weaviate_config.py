
import requests
import json

# User provided URL
URL = "https://weaviate-production-0d0e.up.railway.app"

def check_config():
    print(f"--- Checking VERBA_CONFIGURATION at {URL} ---")
    
    gql_query = {
        "query": """
        {
            Get {
                VERBA_CONFIGURATION {
                    embedder
                    retriever
                    _additional {
                        id
                    }
                }
            }
        }
        """
    }
    
    try:
        resp = requests.post(f"{URL}/v1/graphql", json=gql_query, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            try:
                objs = data['data']['Get']['VERBA_CONFIGURATION']
                if not objs:
                    print("❌ VERBA_CONFIGURATION is empty!")
                else:
                    print(f"✅ Found {len(objs)} config objects:")
                    for idx, obj in enumerate(objs):
                        print(f"   [{idx}] Embedder: {obj.get('embedder')}")
                        print(f"       Retriever: {obj.get('retriever')}")
            except Exception as e:
                 print(f"⚠️ Error parsing config: {e}. Raw: {data}")
        else:
            print(f"❌ Request failed: {resp.status_code}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_config()
