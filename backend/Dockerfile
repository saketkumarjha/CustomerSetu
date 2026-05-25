FROM python:3.11-slim

# Install system dependencies:
# - tesseract-ocr: required by pytesseract (image text extraction)
# - libgomp1: required by spaCy / numpy
# - gcc g++: required to compile some Python packages
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgomp1 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies before copying code for better layer caching.
# spaCy en_core_web_lg is ~800 MB — this step takes 10-15 minutes on first build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# Single worker: the IMAP poller must run in exactly one process.
# Multiple workers would create duplicate pollers, each processing the same inbox.
# B1 tier has 1 vCPU anyway, so --workers 2 provides no throughput benefit.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
