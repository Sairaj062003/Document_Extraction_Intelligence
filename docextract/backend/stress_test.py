import asyncio
import httpx
import time
import os
import sys

# Configuration
API_URL = "http://localhost:8000/extract"
# Use any PDF file present in the tmp directory
TMP_DIR = "tmp"
CONCURRENT_REQUESTS = 3       # Number of simultaneous uploads

async def run_extraction(idx, test_file):
    async with httpx.AsyncClient(timeout=300.0) as client:
        print(f"[{idx}] 🚀 Starting extraction of {os.path.basename(test_file)}...")
        with open(test_file, 'rb') as f:
            files = {'file': f}
            start = time.monotonic()
            try:
                resp = await client.post(API_URL, files=files)
                duration = int((time.monotonic() - start) * 1000)
                if resp.status_code == 200:
                    results = resp.json().get('results', {})
                    mineru_res = results.get('mineru_qwen', {})
                    error = mineru_res.get('error')
                    status = "SUCCESS" if not error else f"FAILED: {error}"
                    print(f"[{idx}] ✅ Completed in {duration}ms. MinerU: {status}")
                else:
                    print(f"[{idx}] ❌ API Error {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[{idx}] ❌ Network/Timeout Error: {e}")

async def main():
    # Find a PDF in tmp directory
    pdfs = [f for f in os.listdir(TMP_DIR) if f.lower().endswith(".pdf")]
    if not pdfs:
        print(f"ERROR: No PDF files found in {TMP_DIR} directory. Please upload one via UI first.")
        return
    
    test_file = os.path.join(TMP_DIR, pdfs[0])
    print(f"🔥 Stress testing {CONCURRENT_REQUESTS} parallel requests using {test_file}...")
    
    tasks = [run_extraction(i, test_file) for i in range(CONCURRENT_REQUESTS)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    if not os.path.exists(TMP_DIR):
        os.makedirs(TMP_DIR)
        
    asyncio.run(main())
