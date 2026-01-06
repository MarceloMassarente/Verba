"""
DEBUG: Ver o que o servidor retorna no RAG config
"""
import requests
import json

BASE_URL = "https://verba-production-c347.up.railway.app"

headers = {
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/"
}

config_resp = requests.post(
    f"{BASE_URL}/api/get_rag_config",
    headers=headers,
    json={"deployment":"Custom", "url":"weaviate.railway.internal", "key":""},
    timeout=30
)

if config_resp.status_code == 200:
    data = config_resp.json()
    rag_config = data.get("rag_config", {})
    
    print("RAG CONFIG RETORNADO:")
    print("="*70)
    print(json.dumps(rag_config, indent=2, ensure_ascii=False))
else:
    print(f"ERRO: {config_resp.status_code}")
