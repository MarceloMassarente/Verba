
import weaviate
import requests
import json
import sys

# User provided URL
URL = "https://weaviate-production-0d0e.up.railway.app"

def check_http_raw():
    print(f"\n--- Checking raw HTTP to {URL} ---")
    try:
        # Check meta
        resp = requests.get(f"{URL}/v1/meta", timeout=10)
        if resp.status_code == 200:
            print(f"✅ /v1/meta responding: {resp.json().get('version')}")
        else:
            print(f"❌ /v1/meta failed: {resp.status_code} - {resp.text}")
            return False

        # Check schema
        resp = requests.get(f"{URL}/v1/schema", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            classes = data.get('classes', [])
            print(f"✅ Found {len(classes)} classes via raw HTTP:")
            for c in classes:
                print(f"   - {c['class']}")
            return True
        else:
             print(f"❌ /v1/schema failed: {resp.status_code}")
             return False
    except Exception as e:
        print(f"❌ HTTP request failed: {e}")
        return False

def check_v3_client():
    print(f"\n--- Checking via Weaviate Client (v3) ---")
    try:
        client = weaviate.Client(
            url=URL,
            timeout_config=(5, 15)
        )
        
        if not client.is_ready():
            print("❌ Client.is_ready() returned False")
            return

        print("✅ Client connected!")
        
        schema = client.schema.get()
        classes = schema.get('classes', [])
        
        if not classes:
            print("⚠️ No classes found in schema.")
            return

        print(f"Found {len(classes)} classes. Querying counts (HTTP GraphQL)...")
        
        for cls in classes:
            class_name = cls['class']
            try:
                # Simple aggregation query
                result = client.query.aggregate(class_name).with_meta_count().do()
                count = result['data']['Aggregate'][class_name][0]['meta']['count']
                print(f" 📦 {class_name}: {count} objects")
            except Exception as e:
                print(f" ⚠️ Could not count {class_name}: {e}")

    except Exception as e:
        print(f"❌ Client v3 error: {e}")

if __name__ == "__main__":
    if check_http_raw():
        check_v3_client()
