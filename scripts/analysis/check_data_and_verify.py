import requests
import json

BASE_URL = "https://verba-production-c347.up.railway.app"
API_KEY = "sk-verba-GGZ0wqvOVcdNHx9MHN6K3VH0vk58n4Tj"
CREDENTIALS = {
    "deployment": "Weaviate",
    "url": "http://weaviate.railway.internal:8080",
    "key": ""
}

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
    "Origin": BASE_URL,
}

def main():
    print("=== System Verification ===\n")
    
    # 1. Health
    try:
        resp = requests.get(f"{BASE_URL}/api/health", headers=HEADERS, timeout=10)
        print(f"Health: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  Info: {resp.json()}")
    except Exception as e:
        print(f"Health Error: {e}")
        
    # 2. List Documents
    print("\n[Listing Documents...]")
    try:
        payload = {
            "credentials": CREDENTIALS,
            "query": "",
            "labels": [],
            "page": 1,
            "pageSize": 5
        }
        resp = requests.post(f"{BASE_URL}/api/get_all_documents", json=payload, headers=HEADERS, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", 0)
            docs = data.get("documents", [])
            print(f"Total Documents: {total}")
            print(f"Returned: {len(docs)}")
            if docs:
                print(f"Sample Doc: {docs[0].get('name')}")
        else:
            print(f"List Docs Failed: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        print(f"List Docs Error: {e}")

    # 3. Test External Query Again
    print("\n[External Query Test]")
    try:
        q_payload = {
            "query": "test",
            "credentials": CREDENTIALS
        }
        q_resp = requests.post(f"{BASE_URL}/api/external/query", json=q_payload, headers=HEADERS, timeout=30)
        print(f"Query Status: {q_resp.status_code}")
        if q_resp.status_code == 200:
            q_data = q_resp.json()
            print(f"Results: {len(q_data.get('documents', []))}")
            if q_data.get("error"):
                print(f"Logic Error: {q_data.get('error')}")
        else:
            print(f"Query Failed: {q_resp.text[:200]}")
    except Exception as e:
        print(f"Query Error: {e}")

if __name__ == "__main__":
    main()
