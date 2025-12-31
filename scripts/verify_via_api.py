import requests
import json
import os
import sys

# Default to Railway as localhost failed
DEFAULT_URL = "https://verba-production-c347.up.railway.app"
BASE_URL = os.getenv("VERBA_URL", DEFAULT_URL).rstrip("/")

# Credential templates to try
DEPLOYMENT_TYPES = ["Weaviate", "Docker", "Local"]

def print_step(msg):
    print(f"\n[STEP] {msg}")

def check_health():
    print_step("Checking API Health...")
    try:
        resp = requests.get(f"{BASE_URL}/api/health")
        if resp.status_code == 200:
            print(f"✅ Health Check Passed: {resp.text}")
            return True
        else:
            print(f"❌ Health Check Failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return False

def find_document_with_deployment(filename, deployment):
    print(f"--- Trying Deployment: {deployment} ---")
    credentials = {
        "deployment": deployment,
        "url": "",
        "key": ""
    }
    
    payload = {
        "query": "",  # Start with empty to list all
        "labels": [],
        "page": 1,
        "pageSize": 10,
        "credentials": credentials
    }
    
    headers = {
        "Origin": BASE_URL,
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/get_all_documents", json=payload, headers=headers)
        if resp.status_code != 200:
            print(f"   ❌ Request Failed: {resp.status_code}")
            return None, credentials
            
        data = resp.json()
        documents = data.get("documents", [])
        print(f"   ℹ️  Found {len(documents)} documents.")
        
        target_doc = None
        for doc in documents:
            if filename in doc.get("title", ""):
                target_doc = doc
                break
        
        if target_doc:
            print(f"   ✅ Document Found: {target_doc.get('title')}")
            return target_doc, credentials
        elif documents:
            print(f"   ⚠️ Documents exist, but specific file not found. Top 1: {documents[0].get('title')}")
            return documents[0], credentials # Return first one just to show connectivity worked
            
        return None, credentials
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None, credentials

def verify_vectors(uuid, credentials):
    print_step(f"Verifying Named Vectors for UUID: {uuid}")
    payload = {
        "uuid": uuid,
        "showAll": True,
        "credentials": credentials
    }
    headers = {
        "Origin": BASE_URL,
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/get_vectors", json=payload, headers=headers)
        if resp.status_code != 200:
            print(f"❌ Get Vectors Request Failed: {resp.status_code} - {resp.text}")
            return
            
        data = resp.json()
        vector_groups = data.get("vector_groups", {})
        
        # Check for named vectors
        expected_vectors = ["company_vec", "sector_vec", "concept_vec"]
        found_vectors = list(vector_groups.keys())
        print(f"ℹ️  Vectors Found: {found_vectors}")
        
        missing = [v for v in expected_vectors if v not in found_vectors]
        if not missing:
            print(f"✅ SUCCESS: All expected named vectors are present.")
        else:
            print(f"⚠️ WARNING: Missing expected vectors: {missing}")
            
    except Exception as e:
        print(f"❌ Vector Verification Error: {e}")

def verify_chunks_metadata(uuid, credentials):
    print_step(f"Verifying Chunk Metadata for UUID: {uuid}")
    payload = {
        "uuid": uuid,
        "page": 1,
        "pageSize": 5,
        "credentials": credentials
    }
    headers = {
        "Origin": BASE_URL,
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/get_chunks", json=payload, headers=headers)
        if resp.status_code != 200:
            print(f"❌ Get Chunks Request Failed: {resp.status_code} - {resp.text}")
            return
            
        data = resp.json()
        chunks = data.get("chunks", [])
        
        if not chunks:
            print("⚠️ No chunks found.")
            return

        print(f"ℹ️  Inspecting {len(chunks)} chunks...")
        first_chunk = chunks[0]
        print(f"   Chunk 0 Text Preview: {first_chunk.get('text', '')[:50]}...")
        
        meta_keys = ["companies", "sectors", "frameworks"]
        found_metadata = False
        
        for key in meta_keys:
            val = first_chunk.get(key)
            if val:
                print(f"   ✅ Found '{key}': {val}")
                found_metadata = True
            else:
                print(f"   ⚠️ '{key}' is empty or missing")
                
        if found_metadata:
            print("✅ SUCCESS: ETL Metadata (NER) appears to be populated.")
        else:
            print("⚠️ WARNING: No ETL metadata (companies/sectors/frameworks) found.")
            
    except Exception as e:
        print(f"❌ Chunk Verification Error: {e}")

def main():
    filename = "20250319_Caminhões a GNL_v1.pptx"
    
    if not check_health():
        print("Aborting due to health check failure.")
        return

    found_doc = None
    working_credentials = None
    
    print_step("Searching for document in all deployment modes...")
    for deployment in DEPLOYMENT_TYPES:
        doc, creds = find_document_with_deployment(filename, deployment)
        if doc:
             # Check if exact match
             if filename in doc.get("title", ""):
                 found_doc = doc
                 working_credentials = creds
                 break
             # Keep partial/fallback
             if not found_doc:
                 found_doc = doc
                 working_credentials = creds

    if found_doc:
        print(f"\n✅ Using Document: {found_doc.get('title')} (UUID: {found_doc.get('uuid')})")
        verify_content_and_search(found_doc.get('uuid'), working_credentials)
    else:
        print("❌ Could not find document in any deployment mode.")

def verify_content_and_search(uuid, credentials):
    print_step(f"Verifying Content and Metadata for UUID: {uuid}")
    payload = {"uuid": uuid, "page": 1, "pageSize": 1, "credentials": credentials}
    headers = {"Origin": BASE_URL, "Content-Type": "application/json"}
    
    chunk_props = {}
    
    try:
        resp = requests.post(f"{BASE_URL}/api/get_chunks", json=payload, headers=headers)
        if resp.status_code == 200:
            chunks = resp.json().get("chunks", [])
            if chunks:
                chk = chunks[0]
                chunk_props = chk
                print(f"   ℹ️  Chunk 0 Keys: {list(chk.keys())}")
                print(f"   ℹ️  Chunk 0 'companies': {chk.get('companies')}")
                print(f"   ℹ️  Chunk 0 'sectors': {chk.get('sectors')}")
                print(f"   ℹ️  Chunk 0 'frameworks': {chk.get('frameworks')}")
                
                # Check if we have any metadata to search for
                meta_search = {}
                if chk.get("companies"): meta_search["companies"] = [chk["companies"][0]]
                if chk.get("sectors"): meta_search["sectors"] = [chk["sectors"][0]]
                
                if meta_search:
                    print(f"\n   ✅ Metadata detected! Verifying Search API with filters: {meta_search}")
                    verify_search_documents(meta_search, credentials)
                else:
                    print("   ⚠️ Metadata fields present but empty/None.")
            else:
                print("   ⚠️ No chunks returned in get_chunks payload.")
        else:
            print(f"   ❌ get_chunks failed: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ inspect error: {e}")

def verify_search_documents(filters, credentials):
    payload = {
        "frameworks": filters.get("frameworks"),
        "companies": filters.get("companies"),
        "sectors": filters.get("sectors"),
        "limit": 10,
        "offset": 0,
        "credentials": credentials
    }
    headers = {"Origin": BASE_URL, "Content-Type": "application/json"}
    
    try:
        resp = requests.post(f"{BASE_URL}/api/documents/search", json=payload, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            docs = data.get("documents", [])
            print(f"   ℹ️  Search returned {len(docs)} documents.")
            if docs:
                print(f"   ✅ Search Verification Successful! Found: {[d.get('title') for d in docs]}")
            else:
                print("   ⚠️ Search returned 0 results matching the metadata.")
        else:
            print(f"   ❌ search_documents failed: {resp.status_code} - {resp.text[:100]}")
    except Exception as e:
        print(f"   ❌ search_documents error: {e}")

if __name__ == "__main__":
    main()
