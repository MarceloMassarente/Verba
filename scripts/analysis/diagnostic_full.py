"""
Diagnóstico completo da API - mostra exatamente qual collection está sendo usada
"""
import requests
import json

BASE_URL = "https://verba-production-c547.up.railway.app"

def main():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO COMPLETO DA API")
    print("=" *80)
    
    # 1. Buscar RAG config do servidor
    print("\n[1] Buscando RAG config...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/get_rag_config",
            json={"credentials": {"deployment": "Weaviate"}},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            rag_config = data.get("rag_config", {})
            
            # Extrair embedder configurado
            embedder_comp = rag_config.get("Embedder", {})
            embedder_selected = embedder_comp.get("selected", "N/A")
            embedder_components = embedder_comp.get("components", {})
            
            print(f"   ✅ Embedder selecionado: {embedder_selected}")
            print(f"   📋 Embedders disponíveis: {list(embedder_components.keys())}")
            
            # Mostrar config do embedder selecionado
            if embedder_selected in embedder_components:
                selected_config = embedder_components[embedder_selected]
                if isinstance(selected_config, dict) and "config" in selected_config:
                    model_config = selected_config["config"].get("model", {})
                    if isinstance(model_config, dict):
                        model_value = model_config.get("value", "N/A")
                    else:
                        model_value = str(model_config)
                    print(f"   🔧 Modelo: {model_value}")
        else:
            print(f"   ❌ Erro: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return
    
    # 2. Tentar query simples
    print("\n[2] Testando query")
    query_payload = {
        "query": "caminhões a gás  ",
        "labels": [],
        "documentFilter": [],
        "credentials": {"deployment": "Weaviate"},
        "RAG": rag_config
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/query",
            json=query_payload,
            timeout=30
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            docs = data.get("documents", [])
            error = data.get("error", "")
            
            print(f"   📊 Documentos retornados: {len(docs)}")
            
            if error:
                print(f"   ⚠️ Erro: {error}")
            
            if len(docs) > 0:
                print(f"   ✅ SUCESSO! Query retornou {len(docs)} documentos")
                for i, doc in enumerate(docs[:3], 1):
                    print(f"      {i}. {doc.get('doc_name', 'N/A')[:50]}")
            else:
                print(f"   ❌ ZERO documentos retornados")
                print(f"\n   💡 Possíveis causas:")
                print(f"      1. Collection configurada está vazia")
                print(f"      2. Embedder '{embedder_selected}' não corresponde aos dados ingeridos")
                print(f"      3. Dados foram ingeridos com outro embedder/modelo")
                
        else:
            print(f"   ❌ Erro HTTP: {response.text[:500]}")
            
    except Exception as e:
        print(f"   ❌ Erro na query: {e}")
    
    print("\n" + "==" * 40)
    print("📋 RESUMO")
    print("=" * 80)
    print(f"\nEmbedder configurado no servidor: {embedder_selected}")
    print(f"\n💡 AÇÃO NECESSÁRIA:")
    print(f"   1. Verificar via Railway logs qual collection tem dados")
    print(f"   2. Configurar o Verba para usar o embedder correspondente")
    print(f"   3. Ou re-ingerir os dados com o embedder atual")

if __name__ == "__main__":
    main()
