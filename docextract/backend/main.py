"""DocExtract — FastAPI backend for parallel document extraction."""

import asyncio
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from extractors import paddle_ocr, llama_parse, gemini_vision  # noqa: E402
from extractors import pymupdf4llm_extractor, mineru_qwen_extractor  # noqa: E402
from extractors import azure_di_extractor  # noqa: E402

app = FastAPI(
    title="DocExtract API",
    description="Extract text from documents using PaddleOCR, LlamaParse, Gemini Vision, PyMuPDF4LLM, MinerU+Qwen, and Azure Document Intelligence in parallel",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use a local tmp directory (Windows-compatible)
UPLOAD_DIR = Path(__file__).parent / "tmp"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".docx", ".txt"}


@app.get("/")
async def health():
    return {"status": "ok", "service": "DocExtract API"}


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    """
    Upload a document and extract text using all six extractors in parallel.
    Supported formats: PDF, PNG, JPG, JPEG, TIFF, DOCX, TXT
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    # Save uploaded file
    file_id = uuid.uuid4().hex
    save_path = UPLOAD_DIR / f"{file_id}{ext}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    path_str = str(save_path)

    # Run all six extractors in parallel with per-extractor timeouts
    results = await asyncio.gather(
        asyncio.wait_for(paddle_ocr.extract(path_str), timeout=60),
        asyncio.wait_for(llama_parse.extract(path_str), timeout=60),
        asyncio.wait_for(gemini_vision.extract(path_str), timeout=60),
        asyncio.wait_for(pymupdf4llm_extractor.extract(path_str), timeout=90),
        asyncio.wait_for(mineru_qwen_extractor.extract(path_str), timeout=180),
        asyncio.wait_for(azure_di_extractor.extract(path_str), timeout=120),
        return_exceptions=True,
    )

    def safe(r, name):
        if isinstance(r, Exception):
            return {
                "model": name,
                "text": None,
                "error": str(r),
                "processing_time_ms": 0,
            }
        return r

    return {
        "file_id": file_id,
        "filename": file.filename,
        "results": {
            "paddleocr": safe(results[0], "paddleocr"),
            "llamaparse": safe(results[1], "llamaparse"),
            "gemini": safe(results[2], "gemini"),
            "pymupdf4llm": safe(results[3], "pymupdf4llm"),
            "mineru_qwen": safe(results[4], "mineru_qwen"),
            "azure_di": safe(results[5], "azure_di"),
        },
    }
