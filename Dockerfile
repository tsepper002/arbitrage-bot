# Multi-stage build for crypto arbitrage trading bot
# Stage 1: Install dependencies
# Stage 2: Copy application code (slim runtime image)

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # UTF-8 encoding for emoji support in logs
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8

WORKDIR /app

# Install system dependencies for cryptography and performance
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Health check — verifies Python can import the bot
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import main; print('OK')" || exit 1

# Default: dry-run mode for safety
ENV ARB_DRY_RUN=true

# Run the bot
ENTRYPOINT ["python", "main.py"]
CMD ["--mode", "dry"]
