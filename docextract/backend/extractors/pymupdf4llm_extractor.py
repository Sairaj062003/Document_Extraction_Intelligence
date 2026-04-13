"""
PyMuPDF4LLM Extractor — Hybrid OCR with layout-aware markdown output.

Uses pymupdf4llm to extract text from PDFs with native text preservation
and OCR for scanned pages. Outputs markdown format.

=== INSTALLATION ===
    pip install pymupdf4llm

    System dependency — Tesseract OCR (for scanned PDF pages):
      Windows:
        1. Download installer: https://github.com/UB-Mannheim/tesseract/wiki
        2. Install and add to PATH: C:\\Program Files\\Tesseract-OCR\\
        3. Verify: tesseract --version

    Quick verify (Python one-liner):
        python -c "import pymupdf4llm; print('pymupdf4llm OK:', pymupdf4llm.__version__ if hasattr(pymupdf4llm,'__version__') else 'installed')"
"""

import time
import asyncio
import tempfile
from pathlib import Path

from utils.file_handler import is_text_file, extract_text_from_file


def _extract_sync(file_path: str) -> dict:
    """Synchronous extraction — runs inside asyncio.to_thread()."""
    import pymupdf4llm
    import fitz  # PyMuPDF

    start = time.monotonic()
    ext = Path(file_path).suffix.lower()

    try:
        # ── Text files: delegate to existing handler ──────────────────
        if is_text_file(file_path):
            text = extract_text_from_file(file_path)
            return {
                "model": "pymupdf4llm",
                "text": text,
                "pages": 1,
                "processing_time_ms": int((time.monotonic() - start) * 1000),
                "note": "Text file — read directly",
                "error": None,
            }

        # ── Image files: wrap in a temporary single-page PDF ─────────
        if ext in {".png", ".jpg", ".jpeg", ".tiff", ".tif"}:
            tmp_pdf_path = _image_to_temp_pdf(file_path)
            try:
                md_text = pymupdf4llm.to_markdown(
                    tmp_pdf_path,
                    write_images=False,
                    force_text=False,
                    dpi=300,
                )
                # Count pages from the temp PDF
                doc = fitz.open(tmp_pdf_path)
                page_count = len(doc)
                doc.close()
            finally:
                # Clean up temp PDF
                try:
                    Path(tmp_pdf_path).unlink(missing_ok=True)
                except Exception:
                    pass
        else:
            # ── PDF files: process directly ───────────────────────────
            md_text = pymupdf4llm.to_markdown(
                file_path,
                write_images=False,
                force_text=False,
                dpi=300,
            )
            doc = fitz.open(file_path)
            page_count = len(doc)
            doc.close()

        return {
            "model": "pymupdf4llm",
            "text": md_text if md_text and md_text.strip() else None,
            "pages": page_count,
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "note": "Hybrid OCR — native text preserved, scanned pages OCR'd",
            "error": None if (md_text and md_text.strip()) else "No text extracted",
        }

    except Exception as e:
        return {
            "model": "pymupdf4llm",
            "text": None,
            "pages": 0,
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "note": "Hybrid OCR — native text preserved, scanned pages OCR'd",
            "error": str(e),
        }


def _image_to_temp_pdf(image_path: str) -> str:
    """Convert an image file to a temporary single-page PDF using PyMuPDF."""
    import fitz  # PyMuPDF

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()

    doc = fitz.open()
    # Open the image and get its dimensions
    img = fitz.open(image_path)
    # Get the image as a pixmap from the first page (fitz treats images as docs)
    pdfbytes = img.convert_to_pdf()
    img.close()

    # Open the PDF bytes and insert into our new doc
    img_pdf = fitz.open("pdf", pdfbytes)
    doc.insert_pdf(img_pdf)
    img_pdf.close()

    doc.save(tmp_path)
    doc.close()

    return tmp_path


async def extract(file_path: str) -> dict:
    """Async entry point — matches the interface of all other extractors."""
    return await asyncio.to_thread(_extract_sync, file_path)
