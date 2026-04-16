# Use Python 3.10 slim as base
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK True
ENV FLAGS_use_mkldnn 0
ENV MAGIC_PDF_CONFIG /app/magic-pdf.json
ENV OLLAMA_HOST http://172.17.0.1:11434

# Set working directory
WORKDIR /app

# Install system dependencies
# - tesseract-ocr: for pymupdf4llm / OCR tasks
# - libgl1 & libglib2.0-0: for PaddleOCR & MinerU (OpenCV/GUI libs)
# - build-essential & python3-dev: for compiling certain packages if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Copy MinerU config to both app directory and root
COPY magic-pdf.json /app/magic-pdf.json
COPY magic-pdf.json /root/magic-pdf.json

# Create tmp directory for uploads
RUN mkdir -p tmp

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
