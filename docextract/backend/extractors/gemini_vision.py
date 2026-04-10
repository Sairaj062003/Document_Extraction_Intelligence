"""Gemini Vision extractor — uses google-genai SDK.
Primary: gemini-2.0-flash-lite → Fallback: gemini-flash-latest (1.5) on quota errors.
"""

import os
import io
import time
import base64
import asyncio
from pathlib import Path
from utils.file_handler import pdf_to_images, is_text_file, extract_text_from_file

PRIMARY_MODEL  = "gemini-2.0-flash-lite"
FALLBACK_MODEL = "gemini-flash-latest"

PROMPT = """Extract ALL text from this document exactly as it appears.
Preserve tables, headings, bullet points, and layout structure.
Return plain text only — no commentary."""


def _build_client():
    from google import genai
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))


def _call_model(client, model_name: str, parts: list) -> str:
    from google.genai import types
    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=PROMPT)] + [
                types.Part(
                    inline_data=types.Blob(
                        mime_type=p["mime_type"],
                        data=base64.b64decode(p["data"])   # SDK expects bytes
                    )
                )
                for p in parts
            ],
        )
    ]
    response = client.models.generate_content(
        model=model_name,
        contents=contents,
    )
    return response.text


async def extract(file_path: str) -> dict:
    start = time.monotonic()
    file_ext = Path(file_path).suffix.lower()

    try:
        if is_text_file(file_path):
            text = extract_text_from_file(file_path)
            return {
                "model": "gemini",
                "model_used": "direct-read",
                "text": text,
                "pages": 1,
                "processing_time_ms": int((time.monotonic() - start) * 1000),
                "note": "Text file — read directly",
                "error": None,
            }

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or "xxxx" in api_key:
            return {
                "model": "gemini",
                "model_used": None,
                "text": None,
                "pages": 0,
                "processing_time_ms": int((time.monotonic() - start) * 1000),
                "error": "GEMINI_API_KEY not configured. Add it to backend/.env",
            }

        if file_ext == ".pdf":
            images = pdf_to_images(file_path)
        else:
            from PIL import Image
            images = [Image.open(file_path)]

        parts = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            parts.append({
                "mime_type": "image/png",
                "data": base64.b64encode(buf.getvalue()).decode(),
            })

        client = _build_client()

        for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
            try:
                text = await asyncio.to_thread(_call_model, client, model_name, parts)
                return {
                    "model": "gemini",
                    "model_used": model_name,
                    "text": text,
                    "pages": len(images),
                    "processing_time_ms": int((time.monotonic() - start) * 1000),
                    "error": None,
                }
            except Exception as e:
                err_str = str(e)
                is_quota = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                is_not_found = "404" in err_str

                if model_name == PRIMARY_MODEL and (is_quota or is_not_found):
                    if is_quota:
                        await asyncio.sleep(2)   # brief pause to not hammer the API
                    continue
                return {
                    "model": "gemini",
                    "model_used": model_name,
                    "text": None,
                    "pages": 0,
                    "processing_time_ms": int((time.monotonic() - start) * 1000),
                    "error": err_str,
                }

    except Exception as e:
        return {
            "model": "gemini",
            "model_used": None,
            "text": None,
            "pages": 0,
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "error": str(e),
        }