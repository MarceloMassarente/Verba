import weaviate
import os
from dotenv import load_dotenv
import json

load_dotenv()

# Weaviate v4 Connection
def get_client():
    url = os.getenv("WEAVIATE_URL_VERBA", "http://localhost:8080")
    # Parse URL to get host and port
    if "http" in url:
        host = url.split("://")[1].split(":")[0]
        port = int(url.split(":")[2]) if len(url.split(":")) > 2 else 8080
    else:
        host = "localhost"
        port = 8080
    
    # Try connecting to local
    try:
        client = weaviate.connect_to_local(
            port=port,
            grpc_port=50051 # Default gRPC port
        )
        return client
    except Exception as e:
        print(f"Failed to connect to local: {e}")
        # Fallback manual connection if needed, but local usually works for Docker
        return None

def verify_ingestion(filename):
    client = get_client()
    if not client:
        print("Could not connect to Weaviate.")
        return

    try:
        print(f"Verifying ingestion for: {filename}")
        collection = client.collections.get("VerbaChunk")
        
        # Query
        from weaviate.classes.query import Filter
        
        # v4 Query Syntax
        response = collection.query.fetch_objects(
            filters=Filter.by_property("doc_name").equal(filename),
            limit=5,
            include_vector=True # This might be heavy, but we need to check existence
        )
        
        chunks = response.objects
        print(f"Found {len(chunks)} chunks.")
        
        if not chunks:
            print("No chunks found! Ingestion might have failed to persist.")
            return

        first_chunk = chunks[0]
        props = first_chunk.properties
        
        print("\n--- Insight into First Chunk ---")
        print(f"Text Preview: {props.get('text', '')[:100]}...")
        print(f"Companies: {props.get('companies', [])}")
        print(f"Sectors: {props.get('sectors', [])}")
        print(f"Frameworks: {props.get('frameworks', [])}")
        
        # Vectors in v4 are accessed differently depending on configuration
        # If named vectors are used, vectors is a dict. If single, it's a list.
        vectors = first_chunk.vector
        
        print("\n--- Vector Analysis ---")
        if isinstance(vectors, dict):
            print(f"Named Vectors Found: {list(vectors.keys())}")
            expected = ["company_vec", "sector_vec", "concept_vec"]
            present = [v for v in expected if v in vectors]
            print(f"Confirmed Expected: {present}")
        else:
             print("Single unnamed vector found (default).")
             print(f"Vector length: {len(vectors) if vectors else 0}")
             
        # Check metadata
        has_metadata = any(props.get(k) for k in ["companies", "sectors", "frameworks"])
        if has_metadata:
            print("SUCCESS: ETL Metadata (NER) appears to be populated.")
        else:
            print("WARNING: No ETL metadata (companies/sectors/frameworks) found in the first chunk.")

    except Exception as e:
        print(f"Error during verification: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    verify_ingestion("20250319_Caminhões a GNL_v1.pptx")
