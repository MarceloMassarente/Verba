
import sys
import os
import asyncio

# Ensure Verba root is in path
sys.path.append(os.getcwd())

from verba_extensions.utils.framework_detector import FrameworkDetector

sample_text = """
A empresa Petrobras está avaliando o uso de Caminhões a GNL para reduzir a pegada de carbono.
Foi realizada uma análise SWOT e utilizado o Business Model Canvas.
O setor de óleo e gás está em transição energética.
"""

async def main():
    print("--- Initializing FrameworkDetector ---")
    try:
        detector = FrameworkDetector()
        print("✅ FrameworkDetector initialized.")
    except Exception as e:
        print(f"❌ Failed to initialize FrameworkDetector: {e}")
        return

    print("\n--- Checking loaded models ---")
    if detector.gliner_model:
        print("✅ GLiNER model is loaded.")
    else:
        print("⚠️ GLiNER model NOT loaded (using fallback).")

    if detector.spacy_nlp:
        print("✅ spaCy model is loaded.")
    else:
        print("⚠️ spaCy model NOT loaded.")

    print("\n--- Running detect_frameworks on sample text ---")
    try:
        result = await detector.detect_frameworks(sample_text)
        print("Result:")
        print(result)
        
        if result.get("frameworks") or result.get("companies") or result.get("sectors"):
            print("\n✅ DETECTOR WORKING: Found entities.")
        else:
            print("\n⚠️ DETECTOR WARNING: No entities found in clear sample text.")
            
    except Exception as e:
        print(f"❌ Error running detection: {e}")

if __name__ == "__main__":
    asyncio.run(main())
