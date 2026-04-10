"""LlamaParse extractor — cloud-based document parsing via LlamaCloud API."""

import os
import time
from utils.file_handler import is_text_file, extract_text_from_file


async def extract(file_path: str) -> dict:
    start = time.monotonic()

    try:
        if is_text_file(file_path):
            text = extract_text_from_file(file_path)
            return {
                "model": "llamaparse",
                "text": text if text.strip() else None,
                "pages": 1,
                "processing_time_ms": int((time.monotonic() - start) * 1000),
                "note": "Text file — read directly",
                "error": None if text.strip() else "Empty result returned",
            }

        api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not api_key or api_key.startswith("llx-xxxx"):
            return {
                "model": "llamaparse",
                "text": None,
                "pages": 0,
                "processing_time_ms": int((time.monotonic() - start) * 1000),
                "error": "LLAMA_CLOUD_API_KEY not configured. Set it in .env",
            }

        from llama_parse import LlamaParse

        parser = LlamaParse(
            api_key=api_key,
            result_type="markdown",
            verbose=False,
        )

        documents = await parser.aload_data(file_path)
        full_text = "\n\n".join(doc.text for doc in documents)

        return {
            "model": "llamaparse",
            "text": full_text if full_text.strip() else None,
            "pages": len(documents),
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "error": None if full_text.strip() else "Empty result returned",
        }

    except Exception as e:          # ← single except block only
        return {
            "model": "llamaparse",
            "text": None,
            "pages": 0,
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "error": str(e),
        }