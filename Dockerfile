# ============================================================
# ASEF — AI Safety Evaluation Framework
# Multi-stage Docker build
# ============================================================
# WARNING: This framework is for defensive AI alignment
# research only. Do not deploy with real model keys unless
# you understand the security implications.
# ============================================================

# ---------- Stage 1: builder ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy only dependency metadata first (cache-friendly)
COPY pyproject.toml ./

# Install runtime dependencies into a virtual-env we can copy later
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# ---------- Stage 2: runtime ----------
FROM python:3.11-slim AS runtime

LABEL maintainer="ASEF Contributors"
LABEL description="AI Safety Evaluation Framework API server"

# Non-root user for security
RUN groupadd --gid 1001 asef && \
    useradd --uid 1001 --gid asef --create-home asef

WORKDIR /app

# Copy virtual-env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY asef/ ./asef/
COPY .env.example ./.env.example

# Ensure data directory exists
RUN mkdir -p /app/data && chown -R asef:asef /app

USER asef

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health'); r.raise_for_status()"

CMD ["uvicorn", "asef.main:app", "--host", "0.0.0.0", "--port", "8000"]
