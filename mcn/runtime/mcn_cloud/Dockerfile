FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCN runtime
COPY mcn_runtime/ ./mcn_runtime/
COPY mcn_interpreter.py .
COPY mcn_extensions.py .
COPY mcn_server.py .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash mcn
RUN chown -R mcn:mcn /app
USER mcn

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start MCN server
CMD ["python", "mcn_server.py", "--host", "0.0.0.0", "--port", "8000"]
