
import requests
import json

BASE_URL = "https://verba-production-c347.up.railway.app"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": BASE_URL,
}
CREDENTIALS = {
    "deployment": "Weaviate",
    "url": "http://weaviate.railway.internal:8080",
    "key": ""
}

def test():
    print("--- MINI TEST ---")
    payload = {
        "query": "agronegocio",
        "credentials": CREDENTIALS
    }
    
    try:
        print(f"Sending request to {BASE_URL}/api/external/query...")
        print(f"Payload credentials: {CREDENTIALS}")
        response = requests.post(
            f"{BASE_URL}/api/external/query",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            docs = data.get("documents", [])
            print(f"✅ Found {len(docs)} documents!")
            for d in docs:
                print(f" - [{d.get('score')}] {d.get('text')[:30]}...")
        else:
            print(f"❌ Error Status: {response.status_code}")
            print(f"❌ Response Text: {response.text}")

    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test()
