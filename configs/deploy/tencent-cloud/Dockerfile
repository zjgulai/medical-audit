FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple

COPY pyproject.toml README.md ./
COPY configs ./configs
COPY scripts ./scripts
COPY sql ./sql
COPY src ./src
COPY web/out ./web/out

RUN uv venv /app/.venv \
    && uv pip install --python /app/.venv/bin/python --index-url "${UV_INDEX_URL}" . \
    && chmod +x scripts/serve-chat-workbench-container.py

EXPOSE 8000

CMD ["python", "scripts/serve-chat-workbench-container.py"]
