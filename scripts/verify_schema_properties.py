
import os
import sys
import asyncio
import weaviate
from weaviate.classes.init import Auth

# Tenta carregar variáveis de ambiente do .env se não existirem
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Debug: Print env vars
print("Environment Variables:")
for k, v in os.environ.items():
    if "WEAVIATE" in k or "VERBA" in k:
        masked = v[:4] + "..." if len(v) > 4 else v
        print(f"  {k}: {masked}")

WEAVIATE_URL = os.getenv("VERBA_URL", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "")

async def main():
    print(f"--- Verifying Schema for {WEAVIATE_URL} ---")
    
    headers = {}
    if "api.weaviate.io" in WEAVIATE_URL:
        # Weaviate Cloud requires specific headers
        print("Using Weaviate Cloud configuration")
    
    try:
        if WEAVIATE_API_KEY:
             client = weaviate.connect_to_custom(
                http_host=WEAVIATE_URL.replace("http://", "").replace("https://", "").split(":")[0],
                http_port=8080 if ":" not in WEAVIATE_URL.replace("http://", "").replace("https://", "") else int(WEAVIATE_URL.split(":")[-1]),
                http_secure=WEAVIATE_URL.startswith("https"),
                headers=headers,
                auth_credentials=Auth.api_key(WEAVIATE_API_KEY)
            )
        else:
            client = weaviate.connect_to_local()
    except Exception as e:
        print(f"Error connecting: {e}")
        # Tente conectar genericamente
        try:
             client = weaviate.connect_to_local(port=8080)
        except:
             print("Could not connect to local Weaviate.")
             return

    try:
        # Check standard collections
        collections_to_check = ["Passage", "Chunk", "Document"]
        
        # Also check for any VERBA_Embedding collection
        all_collections = client.collections.list_all()
        for c in all_collections:
            if "VERBA_Embedding" in c:
                collections_to_check.append(c)

        print(f"Checking collections: {collections_to_check}")

        for col_name in collections_to_check:
            print(f"\n--- Collection: {col_name} ---")
            if col_name not in all_collections:
                print(f"Collection {col_name} NOT FOUND.")
                continue

            col = client.collections.get(col_name)
            config = col.config.get()
            
            props = sorted([p.name for p in config.properties])
            print(f"Properties ({len(props)}):")
            for p in props:
                print(f" - {p}")
            
            # Check specifically for target props
            target_props = ["frameworks", "companies", "sectors", "persons"]
            missing = [tp for tp in target_props if tp not in props]
            
            if missing:
                print(f"❌ MISSING TARGET PROPERTIES: {missing}")
            else:
                print(f"✅ All target properties present.")

    except Exception as e:
        print(f"Error inspecting schema: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
