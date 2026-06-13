# syntax=docker/dockerfile:1

# --- Stage 1: build the frontend -------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Empty base URL = same-origin requests; the API serves the built SPA
ENV VITE_API_BASE_URL=""
# API key baked into the SPA bundle so it can call the protected API
ARG VITE_API_KEY=""
ENV VITE_API_KEY=$VITE_API_KEY
RUN npm run build

# --- Stage 2: resolve Python dependencies with uv --------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS deps
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# --- Stage 3: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 1000 appuser

COPY --from=deps /app/.venv .venv
COPY app/ app/
COPY --from=frontend /build/dist static/

# app/logs must be writable: loguru's file sink lives there
RUN mkdir -p app/logs && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# TCP connect check: /health sits behind the API key, so HTTP status is no signal
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('127.0.0.1', 8000), timeout=4).close()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
