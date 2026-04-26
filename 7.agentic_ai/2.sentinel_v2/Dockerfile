# Multi-stage: small, efficient container for SENTINEL services
# Supports: API, Worker, Scheduler

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spacy model for PII detection (Presidio)
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Set Python path for imports
ENV PYTHONPATH=/app

# Default: run API service (can override with docker run CMD)
CMD ["uvicorn", "sentinel.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
