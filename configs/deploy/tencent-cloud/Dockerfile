FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=180 \
    UV_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy manifests and source together: uv sync --no-editable installs the
# local package from src/, so src/ must be present at sync time.
# Static assets (configs/scripts/sql/web/out) are copied after sync so
# that code-only changes reuse the cached dependency layer above.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable

COPY configs ./configs
COPY scripts ./scripts
COPY sql ./sql
COPY web/out ./web/out

RUN chmod +x scripts/serve-chat-workbench-container.py

EXPOSE 8000

CMD ["python", "scripts/serve-chat-workbench-container.py"]
