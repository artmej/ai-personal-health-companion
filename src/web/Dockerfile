# AI Personal Health Companion Web - Dockerfile
# Streamlit web application container

FROM python:3.11-slim

# Create non-root user for security
RUN groupadd -r streamlit && useradd -r -g streamlit streamlit

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY *.py ./

# Create necessary directories
RUN mkdir -p /app/.streamlit

# Create Streamlit config
RUN echo '[server]\n\
port = 8080\n\
address = "0.0.0.0"\n\
headless = true\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
\n\
[theme]\n\
primaryColor = "#1f77b4"\n\
backgroundColor = "#ffffff"\n\
secondaryBackgroundColor = "#f0f2f6"\n\
textColor = "#262730"' > /app/.streamlit/config.toml

# Set ownership and permissions
RUN chown -R streamlit:streamlit /app
USER streamlit

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/_stcore/health || exit 1

# Expose port
EXPOSE 8080

# Run the application
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
