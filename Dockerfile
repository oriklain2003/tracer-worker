# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install  -r requirements.txt

# Copy application code
COPY . .

# Create output directories for ML models
RUN mkdir -p \
    ml_deep/output \
    ml_deep_cnn/output \
    ml_transformer/output \
    ml_hybrid/output \
    mlboost

# Set default environment variables (override these at runtime)
ENV PG_HOST="" \
    PG_PORT="5432" \
    PG_DATABASE="" \
    PG_USER="" \
    PG_PASSWORD="" \
    PG_SCHEMA="live"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import psycopg2; psycopg2.connect('postgresql://\${PG_USER}:\${PG_PASSWORD}@\${PG_HOST}:\${PG_PORT}/\${PG_DATABASE}')" || exit 1

# Run the monitor
CMD ["python", "monitor.py"]
