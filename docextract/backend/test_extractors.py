import asyncio, os, sys
from dotenv import load_dotenv
load_dotenv()

print(f"Python: {sys.version}")
print(f"GEMINI_API_KEY set: {bool(os.getenv('GEMINI_API_KEY'))}")
print(f"LLAMA_CLOUD_API_KEY set: {bool(os.getenv('LLAMA_CLOUD_API_KEY'))}")

async def main():
    # Test 1: PaddleOCR import
    print("\n--- PaddleOCR ---")
    try:
        from paddleocr import PaddleOCR
        print("Import OK")
        ocr = PaddleOCR(use_textline_orientation=True, lang="en")
        print("Initialized OK")
    except Exception as e:
        print(f"FAILED: {e}")

    # Test 2: Gemini SDK
    print("\n--- Gemini ---")
    try:
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        models = list(client.models.list())
        names = [m.name for m in models]
        print(f"Available models: {names[:20]}")
    except Exception as e:
        print(f"FAILED: {e}")

    # Test 3: LlamaParse import
    print("\n--- LlamaParse ---")
    try:
        from llama_parse import LlamaParse
        print("Import OK")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
