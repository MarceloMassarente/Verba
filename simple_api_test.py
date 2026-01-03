"""Simple API test to verify the universal generate() fix."""
import requests
import json

VERBA_URL = "https://verba-v2-production.up.railway.app"
API_KEY = "sk-verba-GGZ0wqvOVcdNHx9MHN6K3VH0vk58n4Tj"

def test_query(query: str, preset: str = None):
    """Test external API query."""
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
    }
    payload = {"query": query}
    if preset:
        payload["preset"] = preset
    
    try:
        response = requests.post(
            f"{VERBA_URL}/api/external/query",
            json=payload,
            headers=headers,
            timeout=120
        )
        print(f"[{preset or 'default'}] Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            docs = data.get("documents", [])
            print(f"  Documents: {len(docs)}")
            return True
        else:
            print(f"  Error: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"  Exception: {e}")
        return False

if __name__ == "__main__":
    print("=== Testing External API ===\n")
    
    queries = [
        ("agronegocio", "balanced"),
        ("estrategia competitiva", "speed"),
    ]
    
    passed = 0
    for query, preset in queries:
        print(f"Testing: '{query}' with preset '{preset}'")
        if test_query(query, preset):
            passed += 1
    
    print(f"\n=== Results: {passed}/{len(queries)} passed ===")
