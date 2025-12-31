import requests
import json
import os

def verify_ingestion_rest(filename):
    # Verify class name first
    schema_url = "https://weaviate-production-0d0e.up.railway.app/v1/schema"
    class_name = "VERBA_Embedding_all_MiniLM_L6_v2"
    
    try:
        schema_resp = requests.get(schema_url)
        classes = [c["class"] for c in schema_resp.json().get("classes", [])]
        if class_name not in classes:
            print(f"Error: Class {class_name} not found in schema. Available: {classes[:5]}")
            return
    except Exception as e:
        print(f"Schema check failed: {e}")
        return

    url = "https://weaviate-production-0d0e.up.railway.app/v1/graphql"
    query = """
    {
      Get {
        %s (
          limit: 1
        ) {
          title
          content
          companies
          sectors
          frameworks
          _additional {
            vector
          }
        }
      }
    }
    """ % (class_name)

    try:
        response = requests.post(url, json={"query": query})
        data = response.json()
        if "errors" in data:
            print("GraphQL Errors:", data["errors"])
            return

        chunks = data.get("data", {}).get("Get", {}).get(class_name, [])
        print(f"Found {len(chunks)} chunks in {class_name}.")

        if chunks:
            chunk = chunks[0]
            print("\n--- First Chunk Metadata ---")
            print(f"Doc Name: {chunk.get('doc_name')}")
            print(f"Companies: {chunk.get('companies')}")
            print(f"Sectors: {chunk.get('sectors')}")
            print(f"Frameworks: {chunk.get('frameworks')}")
            vector = chunk.get("_additional", {}).get("vector")
            if vector:
                print(f"Vector present. Length: {len(vector)}")
            else:
                print("Vector missing or not returned.")
            
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    verify_ingestion_rest("20240814_Qualificações_Agronegócio.pptx")

if __name__ == "__main__":
    verify_ingestion_rest("20240814_Qualificações_Agronegócio.pptx")
