"""
Script para descobrir qual collection tem dados de "caminhões"
"""
import requests
import json

BASE_URL = "https://verba-production-c547.up.railway.app"

# Lista de collections que vimos nos logs
COLLECTIONS_TO_TEST = [
    "SentenceTransformers",
    "all-MiniLM-L6-v2",
    "all_MiniLM_L6_v2",
    "voyage-multilingual-2",
    "text-embedding-3-small",
]

def test_query_with_embedder(embedder_name):
    """Testa query forçando um embedder específico"""
    print(f"\n{'='*60}")
    print(f"🔍 Testando com embedder: {embedder_name}")
    print('='*60)
    
    try:
        # Primeiro, pegar o RAG config
        config_response = requests.post(
            f"{BASE_URL}/api/get_rag_config",
            json={"credentials": {"deployment": "Weaviate"}},
            timeout=30
        )
        
        if config_response.status_code != 200:
            print(f"❌ Falha ao buscar config: {config_response.status_code}")
            return
        
        rag_config = config_response.json().get("rag_config", {})
        
        # Forçar o embedder
        if "Embedder" in rag_config:
            rag_config["Embedder"]["selected"] = embedder_name
            print(f"✅ Embedder configurado: {embedder_name}")
        
        # Query
        query_payload = {
            "query": "caminhões a gás",
            "labels": [],
            "documentFilter": [],
            "credentials": {"deployment": "Weaviate"},
            "RAG": rag_config
        }
        
        response = requests.post(
            f"{BASE_URL}/api/query",
            json=query_payload,
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            docs = data.get("documents", [])
            error = data.get("error", "")
            
            print(f"📊 Documentos: {len(docs)}")
            
            if error:
                print(f"⚠️ Erro: {error}")
            
            if len(docs) > 0:
                print(f"\n🎉 SUCESSO! Encontrou {len(docs)} documentos!")
                print(f"✅ Collection correta: {embedder_name}")
                for i, doc in enumerate(docs[:3], 1):
                    print(f"   {i}. {doc.get('doc_name', 'N/A')[:60]}")
                return True
            else:
                print(f"❌ 0 documentos retornados")
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            print(f"   {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Exceção: {e}")
    
    return False

def main():
    print("=" * 60)
    print("🔍 DESCOBRINDO A COLLECTION CORRETA")
    print("=" * 60)
    
    success_embedders = []
    
    for embedder in COLLECTIONS_TO_TEST:
        if test_query_with_embedder(embedder):
            success_embedders.append(embedder)
    
    print("\n" + "=" * 60)
    print("📋 RESULTADO FINAL")
    print("=" * 60)
    
    if success_embedders:
        print(f"\n✅ Embedders que retornaram dados:")
        for emb in success_embedders:
            print(f"   - {emb}")
        print(f"\n💡 Use qualquer um destes no Settings do Verba!")
    else:
        print(f"\n❌ Nenhum embedder retornou dados")
        print(f"   Possíveis causas:")
        print(f"   1. Database realmente está vazio")
        print(f"   2. Nome do embedder está errado")
        print(f"   3. Problema com a API")

if __name__ == "__main__":
    main()
