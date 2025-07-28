# AI Personal Health Companion Processor - Dockerfile
# Background processing service for health data analysis

FROM python:3.11-slim

# Create non-root user for security
RUN groupadd -r processor && useradd -r -g processor processor

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY processor.py .
COPY *.py ./

# Set ownership and permissions
RUN chown -R processor:processor /app
USER processor

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check (processor doesn't expose HTTP endpoint, so check process)
HEALTHCHECK --interval=60s --timeout=30s --start-period=10s --retries=3 \
    CMD python -c "import psutil; exit(0 if any('processor.py' in p.cmdline() for p in psutil.process_iter()) else 1)" || exit 1

# Run the processor
CMD ["python", "processor.py"]
