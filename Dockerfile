# Stage 1: builder
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (no-dev, frozen)
RUN uv sync --frozen --no-dev --group main

# Stage 2: runtime
FROM python:3.13-slim AS runtime

# Set working directory
WORKDIR /app

# Install uv (required for ENTRYPOINT ["uv", "run", ...])
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create non-root user
RUN groupadd -g 10001 app && \
    useradd -u 10001 -g app -s /bin/bash -m app

# Copy virtualenv from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Copy application code, migrations, and config
# Note: These may fail to build if the source files do not exist yet (expected in early tasks)
COPY --chown=app:app app /app/app
COPY --chown=app:app alembic /app/alembic
COPY --chown=app:app alembic.ini /app/

# Switch to non-root user
USER app

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Healthcheck using python (curl not available in slim)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/livez', timeout=3); sys.exit(0)"]

# Entrypoint to run the API
ENTRYPOINT ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
