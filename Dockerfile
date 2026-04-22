FROM python:3.10-slim

# System dependencies for lxml, matplotlib, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=1.7.1
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Set working directory
WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev dependencies, no virtualenv in container)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --only main

# Copy source code
COPY src/ ./src/
COPY front/ ./front/

# Create data directory (actual data comes from volume mount)
RUN mkdir -p ./data

# Set Python path so imports work
ENV PYTHONPATH=/app/src

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "front/MLTrail.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
