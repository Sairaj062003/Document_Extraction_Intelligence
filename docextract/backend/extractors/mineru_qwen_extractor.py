"""
MinerU + Qwen2.5-VL Extractor — Local, offline, AI-refined document extraction.

Pipeline:
  Step 1: MinerU (magic-pdf) structural extraction → markdown + images
  Step 2: Detect complex sections (charts, tables, figures)
  Step 3: Qwen2.5-VL refinement via Ollama for complex sections

=== INSTALLATION ===
    pip install magic-pdf[full]
    pip install ollama

    System dependency — Ollama (for Qwen2.5-VL refinement):
      Windows:
        1. Download from: https://ollama.com/download
        2. Pull model: ollama pull qwen2.5vl:3b
        3. Verify: ollama list

    Quick verify (Python one-liner):
        python -c "from magic_pdf.pipe.OCRPipe import OCRPipe; print('MinerU OK')"
        python -c "import ollama; print(ollama.list())"
"""

import os
import re
import time
import asyncio
import shutil
import tempfile
import uuid
from pathlib import Path

from utils.file_handler import is_text_file, extract_text_from_file
from utils.locks import ocr_lock


# ── Ollama connectivity check ─────────────────────────────────────────

def _check_ollama() -> tuple[bool, str]:
    """Check if Ollama is running and qwen2.5vl:3b is available.

    Returns (available: bool, message: str).
    """
    try:
        import ollama
        models = ollama.list()
        # models is a dict with "models" key containing list of model dicts
        model_names = []
        if hasattr(models, "models"):
            model_names = [m.model for m in models.models]
        elif isinstance(models, dict) and "models" in models:
            model_names = [m.get("model", m.get("name", "")) for m in models["models"]]

        # Match qwen2.5vl:3b (could appear as qwen2.5vl:3b or similar)
        for name in model_names:
            if "qwen2.5vl" in name.lower() or "qwen2.5-vl" in name.lower():
                return True, f"Model found: {name}"

        return False, (
            "Ollama is running but qwen2.5vl:3b is not installed. "
            "Pull it with: ollama pull qwen2.5vl:3b"
        )
    except Exception as e:
        return False, (
            f"Ollama not reachable: {e}. "
            "Download from https://ollama.com/download then run: ollama pull qwen2.5vl:3b"
        )


# ── Step 1: MinerU structural extraction ──────────────────────────────

def _mineru_extract(file_path: str, output_dir: str) -> tuple[str, list[str], int]:
    """Run MinerU (magic-pdf) on the file.

    Returns (markdown_text, list_of_image_paths, page_count).
    """
    import fitz  # PyMuPDF — for page count and as dataset reader

    ext = Path(file_path).suffix.lower()

    # MinerU works best with PDFs; convert images to temp PDF if needed
    if ext in {".png", ".jpg", ".jpeg", ".tiff", ".tif"}:
        tmp_pdf = _image_to_temp_pdf_for_mineru(file_path)
        pdf_path = tmp_pdf
    else:
        pdf_path = file_path
        tmp_pdf = None

    try:
        # Get page count
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()

        # Read PDF bytes
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # Try using the modern MinerU API
        md_text, image_paths = _run_mineru_pipeline(pdf_bytes, pdf_path, output_dir)

        return md_text, image_paths, page_count

    finally:
        # Clean up temp PDF if we created one
        if tmp_pdf:
            try:
                Path(tmp_pdf).unlink(missing_ok=True)
            except Exception:
                pass


def _run_mineru_pipeline(pdf_bytes: bytes, pdf_path: str, output_dir: str) -> tuple[str, list[str]]:
    """Execute the MinerU pipeline and return (markdown, image_paths).

    IMPORTANT: magic-pdf's doc_analyze() calls exit(1) on failure, which raises
    SystemExit (a BaseException, NOT Exception). We must catch BaseException at
    every level to prevent it from killing the uvicorn server process.
    """
    try:
        # Try the modern Dataset-based API first (MinerU >= 0.9)
        from magic_pdf.data.dataset import PymuPdfDataset
        from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

        ds = PymuPdfDataset(pdf_bytes)
        infer_result = doc_analyze(ds)

        from magic_pdf.data.data_reader_writer import FileBasedDataWriter

        images_dir = os.path.join(output_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        image_writer = FileBasedDataWriter(images_dir)
        md_writer = FileBasedDataWriter(output_dir)

        from magic_pdf.pipe.UNIPipe import UNIPipe
        pipe = UNIPipe(pdf_bytes, {"_pdf_type": "", "model_list": infer_result}, image_writer)
        pipe.pipe_classify()
        pipe.pipe_analyze()
        pipe.pipe_parse()

        md_content = pipe.pipe_mk_markdown(images_dir, drop_mode="none")
        image_paths = _collect_images(images_dir)
        return md_content, image_paths

    except (ImportError, BaseException) as e:
        # Catch BaseException to intercept SystemExit from doc_analyze
        if isinstance(e, ImportError):
            pass  # Try next pipeline
        else:
            # Log but don't propagate SystemExit — fall through to next attempt
            pass

    try:
        # Fallback: try OCRPipe directly
        from magic_pdf.pipe.OCRPipe import OCRPipe
        from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter

        images_dir = os.path.join(output_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        image_writer = DiskReaderWriter(images_dir)
        pipe = OCRPipe(pdf_bytes, [], image_writer)
        pipe.pipe_classify()
        pipe.pipe_analyze()
        pipe.pipe_parse()

        md_content = pipe.pipe_mk_markdown(images_dir, drop_mode="none")
        image_paths = _collect_images(images_dir)
        return md_content, image_paths

    except (ImportError, BaseException):
        # Catch BaseException here too — OCRPipe also calls doc_analyze
        pass

    # Last resort: use pymupdf4llm as fallback (this never calls exit())
    import pymupdf4llm
    md_text = pymupdf4llm.to_markdown(
        pdf_path,
        write_images=False,
        force_text=False,
        dpi=300,
    )
    return md_text, []


def _collect_images(images_dir: str) -> list[str]:
    """Collect all image files from the MinerU output directory."""
    image_paths = []
    if os.path.isdir(images_dir):
        for f in Path(images_dir).rglob("*"):
            if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}:
                image_paths.append(str(f))
    return image_paths


def _image_to_temp_pdf_for_mineru(image_path: str) -> str:
    """Convert an image file to a temporary single-page PDF using PyMuPDF."""
    import fitz

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()

    doc = fitz.open()
    img = fitz.open(image_path)
    pdfbytes = img.convert_to_pdf()
    img.close()

    img_pdf = fitz.open("pdf", pdfbytes)
    doc.insert_pdf(img_pdf)
    img_pdf.close()

    doc.save(tmp_path)
    doc.close()

    return tmp_path


# ── Step 2: Detect complex sections ──────────────────────────────────

def _detect_complex_images(image_paths: list[str]) -> list[str]:
    """Filter images that are likely charts, tables, or figures.

    Criteria:
      - Filename contains 'chart', 'table', or 'figure'
      - OR image is larger than 100x100 pixels
    """
    from PIL import Image

    complex_images = []
    for img_path in image_paths:
        name_lower = Path(img_path).stem.lower()
        # Check filename patterns
        if any(kw in name_lower for kw in ("chart", "table", "figure")):
            complex_images.append(img_path)
            continue

        # Check image dimensions
        try:
            with Image.open(img_path) as img:
                w, h = img.size
                if w > 100 and h > 100:
                    complex_images.append(img_path)
        except Exception:
            # If we can't open it, skip it
            pass

    return complex_images


# ── Step 3: Qwen2.5-VL refinement ────────────────────────────────────

def _qwen_refine_image(image_path: str) -> str:
    """Send an image to Qwen2.5-VL via Ollama for text/data extraction."""
    import ollama

    response = ollama.chat(
        model="qwen2.5vl:3b",
        messages=[{
            "role": "user",
            "content": (
                "Extract all text and data from this image. "
                "If it is a table, output it as markdown table. "
                "If it is a chart, describe the data and values shown."
            ),
            "images": [image_path],
        }],
    )

    return response.message.content if hasattr(response, "message") else str(response)


def _inject_qwen_results(md_text: str, image_refinements: dict[str, str]) -> str:
    """Replace image placeholders in markdown with Qwen-extracted text.

    MinerU typically inserts image references like:
        ![](images/some_image.png)
    or
        ![description](images/some_image.png)

    We replace these with the Qwen-extracted content.
    """
    if not image_refinements:
        return md_text

    result = md_text
    for img_path, extracted_text in image_refinements.items():
        img_name = Path(img_path).name
        # Match markdown image patterns containing this filename
        # Patterns: ![...](path/to/img_name) or ![...](img_name)
        pattern = rf"!\[([^\]]*)\]\([^\)]*{re.escape(img_name)}[^\)]*\)"
        replacement = (
            f"\n<!-- Qwen2.5-VL extracted from {img_name} -->\n"
            f"{extracted_text}\n"
        )
        result = re.sub(pattern, replacement, result)

    return result


# ── Main extraction orchestrator ──────────────────────────────────────

def _extract_sync(file_path: str) -> dict:
    """Synchronous extraction — runs inside asyncio.to_thread()."""
    start = time.monotonic()
    ext = Path(file_path).suffix.lower()

    try:
        # ── Text files: delegate to existing handler ──────────────
        if is_text_file(file_path):
            text = extract_text_from_file(file_path)
            return {
                "model": "mineru_qwen",
                "text": text,
                "pages": 1,
                "processing_time_ms": int((time.monotonic() - start) * 1000),
                "note": "Text file — read directly",
                "error": None,
            }

        # Create temp output directory
        file_id = uuid.uuid4().hex[:12]
        output_dir = str(Path(__file__).parent.parent / "tmp" / f"mineru_{file_id}")
        os.makedirs(output_dir, exist_ok=True)

        try:
            # ── Step 1: MinerU structural extraction ──────────────
            md_text, image_paths, page_count = _mineru_extract(file_path, output_dir)

            # ── Step 2: Detect complex sections ───────────────────
            complex_images = _detect_complex_images(image_paths)

            # ── Step 3: Qwen2.5-VL refinement ─────────────────────
            note = "MinerU layout analysis + Qwen2.5-VL chart/table refinement"
            ollama_ok, ollama_msg = _check_ollama()

            if complex_images and ollama_ok:
                image_refinements = {}
                for img_path in complex_images:
                    try:
                        extracted = _qwen_refine_image(img_path)
                        if extracted and extracted.strip():
                            image_refinements[img_path] = extracted
                    except Exception:
                        # Skip failed individual image refinements
                        pass

                if image_refinements:
                    md_text = _inject_qwen_results(md_text, image_refinements)
                    note = (
                        f"MinerU layout analysis + Qwen2.5-VL refined "
                        f"{len(image_refinements)}/{len(complex_images)} complex sections"
                    )
            elif complex_images and not ollama_ok:
                note = (
                    "MinerU extraction complete. Qwen refinement skipped — "
                    "Ollama not running. Start with: ollama run qwen2.5vl:3b"
                )
            else:
                note = "MinerU layout analysis (no complex sections detected)"

            return {
                "model": "mineru_qwen",
                "text": md_text if md_text and md_text.strip() else None,
                "pages": page_count,
                "processing_time_ms": int((time.monotonic() - start) * 1000),
                "note": note,
                "error": None if (md_text and md_text.strip()) else "No text extracted",
            }

        finally:
            # ── Cleanup: remove temp directory ────────────────────
            try:
                shutil.rmtree(output_dir, ignore_errors=True)
            except Exception:
                pass

    except BaseException as e:
        # Catch BaseException to handle SystemExit from magic-pdf
        return {
            "model": "mineru_qwen",
            "text": None,
            "pages": 0,
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "note": "MinerU layout analysis + Qwen2.5-VL chart/table refinement",
            "error": f"MinerU error (caught): {type(e).__name__}: {e}",
        }


async def extract(file_path: str) -> dict:
    """Async entry point — matches the interface of all other extractors."""
    async with ocr_lock:
        return await asyncio.to_thread(_extract_sync, file_path)
