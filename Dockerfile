# Multi-stage Dockerfile for LiveKit Python voice agent.
# Based on the LiveKit official template for pip-based projects.

# ---- Build stage ----
FROM python:3.11-slim AS builder

# Build tools for any C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create venv and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# ---- Production stage ----
FROM python:3.11-slim

# Runtime deps only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /bin/bash agent

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy source code (respect .dockerignore)
COPY --chown=agent:agent agent.py prompt.py tools.py kb.txt ./

USER agent

# LiveKit Python agents run with the "start" subcommand in production
CMD ["python", "agent.py", "start"]
