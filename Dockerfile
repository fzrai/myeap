# syntax=docker/dockerfile:1
FROM python:3.11-slim as base

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# ============================================
# Builder stage - installs all dependencies
# ============================================
FROM base as builder

# Copy dependency files
COPY --link pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Copy source code
COPY --link src/ ./src/

# ============================================
# Development stage
# ============================================
FROM base as development

# Copy virtual environment from builder
COPY --from=builder /root/.local /root/.local
ENV PATH="/root/.local/bin:$PATH"

# Copy source code
COPY --link src/ ./src/

CMD ["uv", "run", "uvicorn", "myeap.api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# ============================================
# Production stage - minimal image
# ============================================
FROM base as production

# Install ONLY runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder (no dev dependencies)
COPY --from=builder /root/.local /root/.local
ENV PATH="/root/.local/bin:$PATH"

# Copy source code
COPY --from=builder /app/src/ ./src/
COPY --link pyproject.toml ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Production command
CMD ["uv", "run", "uvicorn", "myeap.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
