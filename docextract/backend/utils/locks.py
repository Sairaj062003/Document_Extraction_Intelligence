import asyncio

# Global semaphore to prevent concurrent access to non-thread-safe OCR libraries (Leptonica/Tesseract)
# We use a semaphore of 1 (essentially a Lock) to ensure local OCR engines run sequentially.
ocr_lock = asyncio.Lock()
