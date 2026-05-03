# Backend Dockerfile for Experience Extraction AI
# Uses python:3.11-slim for weasyprint compatibility

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for weasyprint, fonts, and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-noto-cjk \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-build jieba dictionary cache to avoid lazy download at runtime
RUN python -c "import jieba; jieba.initialize()"

# Copy application code
COPY . .

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with 2 workers (production, no --reload)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
