"""
Acessa Weaviate via HTTPS
"""
import requests
import json

# Tentando com HTTPS
WEAVIATE_HTTPS = "https://weaviate-production-0d0e.up.railway.app"

print("=" * 80)
print("🔍 ACESSANDO WEAVIATE VIA HTTPS")
print("=" * 80)
print(f"URL: {WEAVIATE_HTTPS}\n")

# Get schema
print("[1] Buscando schema via HTTPS...")
try:
    response = requests.get(f"{WEAVIATE_HTTPS}/v1/schema", timeout=15)
    print(f"    Status: {response.status_code}")
    
    if response.status_code == 200:
        schema = response.json()
        classes = schema.get("classes", [])
        print(f"    ✅ {len(classes)} classes encontradas\n")
        
        print("[2] Collections com dados:")
        print("-" * 80)
        for cls in sorted(classes, key=lambda x: x.get("class", "")):
            name = cls.get("class", "N/A")
            
            # Contar objetos
            try:
                agg_query = {
                    "query": f"""
                    {{
                        Aggregate {{
                            {name} {{
                                meta {{ count }}
                            }}
                        }}
                    }}
                    """
                }
                agg_response = requests.post(
                    f"{WEAVIATE_HTTPS}/v1/graphql",
                    json=agg_query,
                    timeout=15
                )
                
                if agg_response.status_code == 200:
                    agg_data = agg_response.json()
                    count = agg_data.get("data", {}).get("Aggregate", {}).get(name, [{}])[0].get("meta", {}).get("count", 0)
                    
                    if count > 0:
                        print(f"\n✅ {name}: {count} objects")
                        
                        # Se for embedding, pegar exemplo
                        if "Embedding" in name:
                            try:
                                sample_query = {
                                    "query": f"""
                                    {{
                                        Get {{
                                            {name}(limit: 1) {{
                                                text
                                                doc_name
                                            }}
                                        }}
                                    }}
                                    """
                                }
                                sample_resp = requests.post(
                                    f"{WEAVIATE_HTTPS}/v1/graphql",
                                    json=sample_query,
                                    timeout=10
                                )
                                if sample_resp.status_code == 200:
                                    sample_data = sample_resp.json()
                                    samples = sample_data.get("data", {}).get("Get", {}).get(name, [])
                                    if samples:
                                        text = samples[0].get("text", "")[:80]
                                        doc = samples[0].get("doc_name", "N/A")
                                        print(f"   📄 Exemplo: {doc}")
                                        print(f"      {text}...")
                            except:
                                pass
            except Exception as e:
                print(f"   ⚠️ Erro: {str(e)[:50]}")
    else:
        print(f"    ❌ Erro: {response.text[:300]}")
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
