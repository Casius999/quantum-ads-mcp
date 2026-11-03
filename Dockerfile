# syntax=docker/dockerfile:1
# Remote (Streamable HTTP) image: `quantum-ads-mcp` serving on :8080, non-root, no secrets baked in.
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-editable --extra connectors --extra tasks --extra anchoring --extra observability

FROM python:3.14-slim
RUN useradd --system --uid 10001 --home-dir /data --create-home app
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    QUANTUM_ADS_TRANSPORT=http \
    QUANTUM_ADS_HTTP_HOST=0.0.0.0 \
    QUANTUM_ADS_HTTP_PORT=8080 \
    QUANTUM_ADS_AUDIT_DIR=/data/audit
USER app
WORKDIR /data
EXPOSE 8080
ENTRYPOINT ["quantum-ads-mcp"]
