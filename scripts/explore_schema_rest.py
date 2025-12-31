import requests
import json

def get_schema():
    url = "https://weaviate-production-0d0e.up.railway.app/v1/schema"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            target_class = "VERBA_Embedding_all_MiniLM_L6_v2"
            for cls in data.get('classes', []):
                if cls['class'] == target_class:
                    print(f"Class: {cls['class']}")
                    props = [p['name'] for p in cls.get('properties', [])]
                    print(f"Properties ({len(props)}):")
                    for p in props:
                        print(f"  - {p}")
                    return
            print(f"Class {target_class} not found in classes: {[c['class'] for c in data.get('classes', [])]}")
        else:
            print(f"Failed to fetch schema. Status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    get_schema()
