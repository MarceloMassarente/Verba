import requests
import sys
import os
import time

# Import the test modules
import test_api_production
import simple_api_test

CANDIDATE_URLS = [
    ("Railway Prod (c347)", "https://verba-production-c347.up.railway.app"),
]

def check_url(name, url, retries=3):
    print(f"Checking {name} at {url}...")
    for i in range(retries):
        try:
            print(f"  Attempt {i+1}/{retries}...", end="", flush=True)
            resp = requests.get(f"{url}/api/health", timeout=20)
            if resp.status_code == 200:
                print(f" ✅ UP!")
                return True
            else:
                print(f" ❌ Status {resp.status_code}")
                # If 404, it might be a valid server but wrong endpoint, or just not ready. 
                # But /api/health should exist.
                if resp.status_code == 404:
                     # Fail fast on 404 if we are sure about the endpoint
                     return False
        except Exception as e:
            print(f" ⏳ Error: {e}")
            time.sleep(2)
    return False

def main():
    print("=== Verba API Auto-Tester Sequence ===\n")
    
    active_url = None
    active_name = None
    
    # 1. Detect active environment
    for name, url in CANDIDATE_URLS:
        if check_url(name, url):
            active_url = url
            active_name = name
            break
            
    if not active_url:
        print("\n❌ No active Verba instance found! Verified Local, Prod (c347), and V2.")
        sys.exit(1)
        
    print(f"\n🚀 Starting tests against: {active_name} ({active_url})\n")
    
    # 2. Patch and run test_api_production
    print("\n" + "="*60)
    print(">>> 1. INTERNAL API TESTS (test_api_production.py) <<<")
    print("="*60 + "\n")
    
    # Patch globals
    test_api_production.BASE_URL = active_url
    
    # Patch session headers
    test_api_production.session.headers.update({
        "Origin": active_url,
        "Referer": active_url + "/"
    })
    
    try:
        test_api_production.main()
    except Exception as e:
        print(f"❌ Error running test_api_production: {e}")

    # 3. Patch and run simple_api_test (External API)
    print("\n" + "="*60)
    print(">>> 2. EXTERNAL API TESTS (simple_api_test.py) <<<")
    print("="*60 + "\n")
    
    # Patch global
    simple_api_test.VERBA_URL = active_url
    
    print(f"Using API Key: {simple_api_test.API_KEY[:5]}...")
    
    try:
        queries = [
            ("agronegocio", "balanced"),
            ("test query", None)
        ]
        
        passed = 0
        for query, preset in queries:
            print(f"Testing: '{query}' with preset '{preset}'")
            if simple_api_test.test_query(query, preset):
                passed += 1
        
        print(f"\n=== External API Results: {passed}/{len(queries)} passed ===")
        
    except Exception as e:
        print(f"❌ Error running simple_api_test: {e}")

if __name__ == "__main__":
    main()
