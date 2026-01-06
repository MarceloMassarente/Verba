
import requests
import json

WEAVIATE_URL = "https://weaviate-production-0d0e.up.railway.app"

def get_schema():
    print(f"Fetching schema from {WEAVIATE_URL}...")
    try:
        response = requests.get(f"{WEAVIATE_URL}/v1/schema")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching schema: {e}")
        return None

def get_object_count(class_name):
    query = f"""
    {{
        Aggregate {{
            {class_name} {{
                meta {{
                    count
                }}
            }}
        }}
    }}
    """
    try:
        response = requests.post(
            f"{WEAVIATE_URL}/v1/graphql",
            json={'query': query}
        )
        response.raise_for_status()
        data = response.json()
        return data['data']['Aggregate'][class_name][0]['meta']['count']
    except Exception as e:
        print(f"Error counting {class_name}: {e}")
        return -1

def main():
    schema = get_schema()
    if not schema:
        return

    print("\n--- Available Classes ---")
    classes = schema.get('classes', [])
    if not classes:
        print("No classes found in schema.")
    
    for cls in classes:
        name = cls['class']
        desc = cls.get('description', 'No description')
        count = get_object_count(name)
        if count > 0:
            print(f"Class: {name:<40} | Count: {count:<10} | Desc: {desc}")

if __name__ == "__main__":
    main()
