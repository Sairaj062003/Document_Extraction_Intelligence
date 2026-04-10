import os
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import time
import asyncio
from pathlib import Path
from utils.file_handler import is_text_file, extract_text_from_file

_ocr = None
_paddle_error = None


def _load_paddle():
    global _ocr, _paddle_error
    if _ocr is not None or _paddle_error is not None:
        return
    try:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(
            use_angle_cls=True,   # v2.x argument
            lang="en",
            use_gpu=False,
            show_log=False,
        )
    except Exception as e:
        _paddle_error = str(e)


def _ocr_on_image(img) -> str:
    import numpy as np
    img_array = np.array(img)
    result = _ocr.ocr(img_array, cls=True)
    lines = []
    if result:
        for page in result:
            if not page:
                continue
            for line in page:
                if not line or len(line) < 2:
                    continue
                text_info = line[1]
                if isinstance(text_info, (list, tuple)) and len(text_info) > 0:
                    lines.append(str(text_info[0]))
                elif isinstance(text_info, str):
                    lines.append(text_info)
    return "\n".join(lines)


async def extract(file_path: str) -> dict:
    start = time.monotonic()
    ext = Path(file_path).suffix.lower()

    try:
        if is_text_file(file_path):
            text = extract_text_from_file(file_path)
            return {
                "model": "paddleocr",
                "text": text,
                "pages": 1,
                "processing_time_ms": int((time.monotonic() - start) * 1000),
                "note": "Text file — read directly",
                "error": None,
            }

        await asyncio.to_thread(_load_paddle)
        if _paddle_error:
            return {
                "model": "paddleocr",
                "text": None,
                "pages": 0,
                "processing_time_ms": int((time.monotonic() - start) * 1000),
                "error": f"PaddleOCR load error: {_paddle_error}",
            }

        if ext == ".pdf":
            from utils.file_handler import pdf_to_images
            images = pdf_to_images(file_path)
        else:
            from PIL import Image
            images = [Image.open(file_path)]

        all_text = []
        for img in images:
            page_text = await asyncio.to_thread(_ocr_on_image, img)
            all_text.append(page_text)

        full_text = "\n\n--- Page Break ---\n\n".join(all_text)
        return {
            "model": "paddleocr",
            "text": full_text if full_text.strip() else None,
            "pages": len(images),
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "error": None if full_text.strip() else "No text extracted",
        }

    except Exception as e:
        return {
            "model": "paddleocr",
            "text": None,
            "pages": 0,
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "error": str(e),
        }