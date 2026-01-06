
try:
    with open('test_output_full.txt', 'r', encoding='utf-8', errors='replace') as f:
        log = f.read()

    print("--- Log Verification Analysis ---")
    
    # Check for AttributeError
    has_error = "AttributeError" in log
    print(f"AttributeError present: {has_error}")
    
    # Check for Embedder Switching
    has_switch = "Switching Embedder" in log
    print(f"Switching Embedder logic triggered: {has_switch}")
    
    # Check Preset Application
    matches = [l for l in log.splitlines() if "preset_applied" in l]
    for m in matches:
        print(f"Found: {m.strip()}")
        
    # Check specific errors
    if "No chunks available" in log:
        print("Warning: 'No chunks available' detected.")
    
    if "object has no attribute 'get'" in log:
        print("CRITICAL FAILURE: 'object has no attribute get' detected.")
    else:
        print("SUCCESS: RAGComponentClass error NOT found.")

except Exception as e:
    print(f"Error reading log: {e}")
