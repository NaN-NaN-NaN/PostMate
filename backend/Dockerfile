# PostMate Backend - Multi-stage Docker Build
# Purpose: Production-ready container with Tesseract OCR for local dev/fallback
# Testing: docker build -t postmate-backend . && docker run -p 8080:8080 postmate-backend
# AWS Deployment: Used by deploy_aws.sh to build and push to ECR

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.10-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies including Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    poppler-utils \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY ./app /app/app
COPY ./lambda /app/lambda

# Create directories for local storage (if using local mode)
RUN mkdir -p /app/local_data/images /app/local_data/pdfs /app/local_data/textract /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TESSERACT_PATH=/usr/bin/tesseract

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
