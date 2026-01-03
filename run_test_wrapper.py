import subprocess
import sys

# Wrapper to run the test and capture output with correct encoding
try:
    result = subprocess.run(
        [sys.executable, "test_preset_api.py", "https://verba-production-c347.up.railway.app"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    with open("test_output_full.txt", "w", encoding="utf-8") as f:
        f.write("STDOUT:\n")
        f.write(result.stdout)
        f.write("\n\nSTDERR:\n")
        f.write(result.stderr)
        
    print("Done. Check test_output_full.txt")
except Exception as e:
    print(f"Error: {e}")
