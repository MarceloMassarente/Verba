"""
Teste simples e direto: query na API do Railway
"""
import requests
import json

BASE_URL = "https://verba-production-c347.up.railway.app"

print("🔍 TESTE SIMPLES - QUERY NO RAILWAY")
print("=" * 60)

# 1. Get RAG config
print("\n[1] Buscando configuração...")
config_resp = requests.post(
    f"{BASE_URL}/api/get_rag_config",
    json={"deployment":"Custom", "url":"weaviate.railway.internal", "key":""},
    timeout=30
)
print(f"Status: {config_resp.status_code}")

if config_resp.status_code != 200:
    print(f"ERRO: {config_resp.text[:500]}")
    exit(1)

data = config_resp.json()
rag_config = data.get("rag_config", {})
print(f"✅ Config loaded")
print(f"   Embedder selecionado: {rag_config.get('Embedder', {}).get('selected', 'N/A')}")

# 2. Query simples
print("\n[2] Fazendo query...")
query_payload = {
    "query":"caminhões a gás",
    "labels":[],
    "documentFilter":[],
    "deployment":"Custom",
    "url":"weaviate.railway.internal", 
    "key":"",
    "RAG":rag_config
}

query_resp = requests.post(
    f"{BASE_URL}/api/query",
    json=query_payload,
    timeout=30
)

print(f"Status: {query_resp.status_code}")

if query_resp.status_code == 200:
    result = query_resp.json()
    docs = result.get("documents", [])
    error = result.get("error", "")
    
    print(f"\n📊 RESULTADO:")
    print(f"   Documentos: {len(docs)}")
    if error:
        print(f"   ⚠️ Erro: {error}")
    
    if len(docs) > 0:
        print(f"\n🎉 SUCESSO! {len(docs)} documentos encontrados!")
        for i, doc in enumerate(docs[:3], 1):
            print(f"   {i}. {doc.get('doc_name', 'N/A')}")
    else:
        print(f"\n❌ ZERO documentos")
        print(f"\n💡 Resposta completa:")
        print(json.dumps(result, indent=2)[:500])
else:
    print(f"❌ Erro: {query_resp.text[:500]}")
