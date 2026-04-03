# syntax=docker/dockerfile:1

# --- build dependencies (has pip, shells) ---
FROM cgr.dev/chainguard/python:latest-dev AS builder

USER root
WORKDIR /app

RUN python -m venv /app/venv \
    && /app/venv/bin/pip install --no-cache-dir --upgrade pip

COPY pyproject.toml .
COPY dependency_analysis_mcp ./dependency_analysis_mcp

RUN /app/venv/bin/pip install --no-cache-dir .

# --- minimal runtime (distroless-style, no shell) ---
FROM cgr.dev/chainguard/python:latest AS runtime

WORKDIR /app

COPY --from=builder --chown=nonroot:nonroot /app/venv /app/venv

USER nonroot:nonroot

ENV PATH="/app/venv/bin:${PATH}"
# Fly.io sets PORT at runtime; default matches fly.toml internal_port for local runs.
ENV PORT=8080
ENV FASTMCP_HOST=0.0.0.0

EXPOSE 8080

ENTRYPOINT ["/app/venv/bin/python", "-m", "dependency_analysis_mcp.server"]
