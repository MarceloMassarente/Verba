
import weaviate
import sys

# User provided URL
URL = "https://weaviate-production-0d0e.up.railway.app"

def check_weaviate():
    print(f"Connecting to {URL}...")
    try:
        # v4 helper to connect via minimal params
        # Note: if this fails, we will try v3 client as fallback in same script
        try:
            client = weaviate.Client(URL)
            print("✅ Connected with v3-compat Client!")
            
            schema = client.schema.get()
            classes = schema.get('classes', [])
            print(f"\nFound {len(classes)} collections:")
            
            for cls in classes:
                class_name = cls['class']
                result = client.query.aggregate(class_name).with_meta_count().do()
                count = 0
                try:
                    count = result['data']['Aggregate'][class_name][0]['meta']['count']
                except:
                    pass
                print(f" - {class_name}: {count} objects")
                
        except Exception as v3_err:
            print(f"v3 Client failed: {v3_err}")
            print("Trying v4 connect_to_url...")
            
            # For v4 native connection
            # Depending on exact v4 sub-version, imports might vary, avoiding strict import deps if possible
            # but we assume weaviate package is updated.
            # Using verify=False just in case of cert issues, though railway usually has valid certs.
            client = weaviate.connect_to_url(URL)
            
            try:
                print(f"✅ Connected (v4)!")
                collections = client.collections.list_all()
                print(f"\nFound {len(collections)} collections:")
                
                for name in collections:
                    col = client.collections.get(name)
                    # Count
                    try:
                        count_resp = col.aggregate.over_all(total_count=True)
                        print(f" - {name}: {count_resp.total_count} objects")
                    except Exception as e:
                        print(f" - {name}: (Error counting: {e})")
            finally:
                client.close()

    except Exception as e:
        print(f"❌ Error connecting/querying: {str(e)}")

if __name__ == "__main__":
    check_weaviate()
