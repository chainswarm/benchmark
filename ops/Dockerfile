

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy package source code
COPY packages ./packages
COPY scripts ./scripts

# Create benchmark directories
RUN mkdir -p /var/benchmark/repos /var/benchmark/data

# Add PYTHONPATH
ENV PYTHONPATH=/app

# Default command placeholder
CMD ["python", "-c", "print('Benchmark system ready. Specify service command in docker compose.')"]