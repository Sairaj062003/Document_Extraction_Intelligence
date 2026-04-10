"""File handling utilities — validation, PDF→image, DOCX→text, TXT→text."""

from pathlib import Path
from PIL import Image

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".docx", ".txt"}


def validate_extension(filename: str) -> bool:
    """Return True if the file extension is supported."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def pdf_to_images(pdf_path: str) -> list:
    """Convert each page of a PDF to a PIL Image (PNG) using PyMuPDF."""
    import fitz  # PyMuPDF
    import io

    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        # Render page to a pixmap (image)
        pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72))  # 300 DPI
        img_data = pix.tobytes("png")
        images.append(Image.open(io.BytesIO(img_data)))
    doc.close()
    return images


def read_docx(file_path: str) -> str:
    """Extract all text from a .docx file."""
    from docx import Document

    doc = Document(file_path)
    return "\n".join(para.text for para in doc.paragraphs)


def read_txt(file_path: str) -> str:
    """Read plain text from a .txt file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def is_text_file(file_path: str) -> bool:
    """Return True if the file is a text-based format (.docx, .txt)."""
    ext = Path(file_path).suffix.lower()
    return ext in {".docx", ".txt"}


def extract_text_from_file(file_path: str) -> str:
    """Extract text from .docx or .txt files."""
    ext = Path(file_path).suffix.lower()
    if ext == ".docx":
        return read_docx(file_path)
    elif ext == ".txt":
        return read_txt(file_path)
    raise ValueError(f"Not a text file: {ext}")
