# Use official Python runtime as base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Install system dependencies and Poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get purge -y --auto-remove curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Add Poetry to PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files first (for Docker layer caching)
COPY pyproject.toml poetry.lock* ./

# Install Python dependencies using Poetry
RUN poetry install --no-root --only main --no-interaction --no-ansi

# Copy application code
COPY ./app ./app

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (Cloud Run will inject PORT env variable, default to 8080)
ENV PORT=8080
EXPOSE $PORT

# Health check (optional but recommended)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/')"

# Run the application
# Cloud Run requires listening on 0.0.0.0 and the PORT environment variable
# Using exec form for proper signal handling and graceful shutdown
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
