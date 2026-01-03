"""
Acessa Weaviate diretamente via HTTP API para inspecionar collections
"""
import requests
import json

WEAVIATE_URL = "http://weaviate-production-0d0e.up.railway.app:8080"

def inspect_weaviate():
    print("=" * 80)
    print("🔍 ACESSANDO WEAVIATE DIRETAMENTE VIA HTTP")
    print("=" * 80)
    print(f"URL: {WEAVIATE_URL}\n")
    
    # 1. Get schema/meta info
    print("[1] Buscando schema...")
    try:
        response = requests.get(f"{WEAVIATE_URL}/v1/schema", timeout=10)
        if response.status_code == 200:
            schema = response.json()
            classes = schema.get("classes", [])
            print(f"    ✅ {len(classes)} classes encontradas\n")
            
            # Listar todas as classes
            print("[2] Collections existentes:")
            print("-" * 80)
            for cls in classes:
                name = cls.get("class", "N/A")
                props = cls.get("properties", [])
                vectorizer = cls.get("vectorizer", "N/A")
                print(f"\n📦 {name}")
                print(f"   Vectorizer: {vectorizer}")
                print(f"   Properties: {len(props)}")
                
                # Contar objetos nesta collection
                try:
                    agg_response = requests.post(
                        f"{WEAVIATE_URL}/v1/graphql",
                        json={
                            "query": f"""
                            {{
                                Aggregate {{
                                    {name} {{
                                        meta {{
                                            count
                                        }}
                                    }}
                                }}
                            }}
                            """
                        },
                        timeout=10
                    )
                    if agg_response.status_code == 200:
                        agg_data = agg_response.json()
                        count = agg_data.get("data", {}).get("Aggregate", {}).get(name, [{}])[0].get("meta", {}).get("count", 0)
                        print(f"   📊 Objects: {count}")
                        
                        # Se for embedding collection com dados, buscar exemplos
                        if "Embedding" in name and count > 0:
                            try:
                                sample_response = requests.post(
                                    f"{WEAVIATE_URL}/v1/graphql",
                                    json={
                                        "query": f"""
                                        {{
                                            Get {{
                                                {name}(limit: 2) {{
                                                    text
                                                    doc_name
                                                }}
                                            }}
                                        }}
                                        """
                                    },
                                    timeout=10
                                )
                                if sample_response.status_code == 200:
                                    sample_data = sample_response.json()
                                    samples = sample_data.get("data", {}).get("Get", {}).get(name, [])
                                    if samples:
                                        print(f"   📄 Exemplos:")
                                        for i, sample in enumerate(samples[:2], 1):
                                            text = sample.get("text", "")[:50]
                                            doc = sample.get("doc_name", "N/A")
                                            print(f"      {i}. {doc}: {text}...")
                            except Exception as e:
                                print(f"   ⚠️ Erro ao buscar exemplos: {str(e)[:50]}")
                except Exception as e:
                    print(f"   ⚠️ Erro ao contar: {str(e)[:50]}")
        else:
            print(f"    ❌ Erro: {response.status_code}")
            print(f"    {response.text[:200]}")
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    inspect_weaviate()
