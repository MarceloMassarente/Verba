
import requests
import json

# User provided URL
URL = "https://weaviate-production-0d0e.up.railway.app"

def run():
    print(f"--- Checking {URL} via raw HTTP ---")
    
    # 1. Check Schema
    try:
        resp = requests.get(f"{URL}/v1/schema", timeout=10)
        if resp.status_code != 200:
            print(f"❌ Failed to get schema: {resp.status_code} {resp.text}")
            return
        
        data = resp.json()
        classes = data.get('classes', [])
        print(f"✅ Schema found with {len(classes)} classes:")
        
        if not classes:
            print("   (Database seems empty of collections)")
            return

        for c in classes:
            class_name = c['class']
            print(f"   - {class_name}")

            # 2. Count objects using GraphQL
            gql_query = {
                "query": f"""
                {{
                    Aggregate {{
                        {class_name} {{
                            meta {{
                                count
                            }}
                        }}
                    }}
                }}
                """
            }
            
            gql_resp = requests.post(f"{URL}/v1/graphql", json=gql_query, timeout=10)
            if gql_resp.status_code == 200:
                gql_data = gql_resp.json()
                try:
                    count = gql_data['data']['Aggregate'][class_name][0]['meta']['count']
                    print(f"     📦 Count: {count}")
                except:
                    print(f"     ⚠️ Count failed parsing: {gql_data}")
            else:
                print(f"     ❌ GraphQL failed: {gql_resp.status_code}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run()
