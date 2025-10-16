# Multi-stage build for optimization
# Stage 1: Build stage
FROM public.ecr.aws/docker/library/python:3.12-slim AS builder

# Copy uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables for build stage
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_CACHE_DIR=/root/.cache/uv

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies in a virtual environment with cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --package sana-agent

# Copy source code
COPY ./sana ./sana

# Install the workspace package with cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package sana-agent

# Stage 2: Runtime stage - minimal final image
FROM public.ecr.aws/docker/library/python:3.12-slim AS runtime

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY --from=builder /app/sana ./sana

# Set environment variables for runtime
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["opentelemetry-instrument", "python", "-m", "sana.main"]