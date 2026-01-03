"""
Teste final simples - SEM EMOJIS para funcionar no Windows
"""
import requests
import json

BASE_URL = "https://verba-production-c347.up.railway.app"

# Headers para bypass CORS
headers = {
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/"
}

print("="*60)
print("TESTE FINAL - Query Endpoint")
print("="*60)

# Get config
print("\n[1] Get RAG Config...")
config_resp = requests.post(
    f"{BASE_URL}/api/get_rag_config",
    headers=headers,
    json={"deployment":"Custom", "url":"weaviate.railway.internal", "key":""},
    timeout=30
)
print(f"Status: {config_resp.status_code}")

if config_resp.status_code == 200:
    rag_config = config_resp.json().get("rag_config", {})
    print(f"OK - Config loaded: {len(rag_config)} components")
else:
    print(f"ERRO: {config_resp.text[:200]}")
    exit(1)

# Query
print("\n[2] Query: caminhoes a gas...")
query_payload = {
    "query": "caminhoes a gas",
    "labels": [],
    "documentFilter": [],
    "deployment": "Custom",
    "url": "weaviate.railway.internal",
    "key": "",
    "RAG": rag_config
}

query_resp = requests.post(
    f"{BASE_URL}/api/query",
    headers=headers,
    json=query_payload,
    timeout=30
)

print(f"Status: {query_resp.status_code}")

if query_resp.status_code == 200:
    result = query_resp.json()
    docs = result.get("documents", [])
    error = result.get("error", "")
    
    print(f"\nRESULTADO:")
    print(f"Documentos: {len(docs)}")
    
    if error:
        print(f"Erro: {error}")
    
    if len(docs) > 0:
        print(f"\n>>> SUCESSO! {len(docs)} documentos!")
        for i, doc in enumerate(docs[:3], 1):
            print(f"  {i}. {doc.get('doc_name', 'N/A')}")
    else:
        print("\n>>> ZERO documentos")
else:
    print(f"ERRO HTTP: {query_resp.text[:300]}")

print("\n" + "="*60)
