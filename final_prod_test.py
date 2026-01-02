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

def test_search():
    payload = {
        "query": "agronegocio",
        "credentials": CREDENTIALS
    }
    print(f"Testing search at {BASE_URL}...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/external/query",
            headers=HEADERS,
            json=payload,
            timeout=60
        )
        print(f"Status: {response.status_code}")
        with open("final_test_result.json", "w", encoding="utf-8") as f:
            json.dump(response.json(), f, indent=2, ensure_ascii=False)
        print("Result saved to final_test_result.json")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search()
