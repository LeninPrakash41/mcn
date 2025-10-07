FROM python:3.11-slim

LABEL maintainer="MCN Foundation <dev@mslang.org>"
LABEL description="MCN - AI-powered scripting language"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCN source
COPY . .

# Install MCN
RUN pip install -e .

# Create non-root user
RUN useradd -m -u 1000 mcn
USER mcn

# Expose port for API server
EXPOSE 8080

# Default command
CMD ["mcn", "run", "examples/hello.mcn"]
