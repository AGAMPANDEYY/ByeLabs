# HiLabs Roster Processing - API Service
# Multi-stage build for production-ready FastAPI application

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for PDF processing and other libraries
RUN apt-get update && apt-get install -y \
    # PDF processing dependencies
    libpoppler-cpp-dev \
    poppler-utils \
    libpoppler-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Camelot dependencies
    libcairo2-dev \
    libpango1.0-dev \
    pkg-config \
    python3-dev \
    # Image processing
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    # Network utilities
    curl \
    # Build tools
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/* || true

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/temp

# Change ownership to app user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
