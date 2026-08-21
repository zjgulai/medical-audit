#!/usr/bin/env bash
set -euo pipefail

HOST="${MEDICAL_AUDIT_KB_HOST:-127.0.0.1}"
PORT="${MEDICAL_AUDIT_KB_PORT:-8010}"
API_URL="${MEDICAL_AUDIT_KB_API_URL:-http://${HOST}:${PORT}}"
CONFIG_PATH="${MEDICAL_AUDIT_KB_CONFIG:-configs/knowledge-query-engine-dev.yaml}"
APP_MODULE="${MEDICAL_AUDIT_KB_APP_MODULE:-medical_audit_kb.api.app:create_app}"
LOG_LEVEL="${MEDICAL_AUDIT_KB_LOG_LEVEL:-warning}"
LOAD_BACKEND="${MEDICAL_AUDIT_KB_LOAD_BACKEND:-1}"
OPEN_BROWSER="${MEDICAL_AUDIT_KB_OPEN_BROWSER:-0}"
API_ACCESS_MODE="${MEDICAL_AUDIT_API_ACCESS_MODE:-header-transition-test}"

EMBEDDING_PROVIDER="${KIMI_EMBEDDING_PROVIDER:-openai}"
EMBEDDING_MODEL="${KIMI_EMBEDDING_MODEL:-kimi-for-coding}"
EMBEDDING_DIMENSION="${KIMI_EMBEDDING_DIMENSION:-1024}"
EMBEDDING_BASE_URL="${KIMI_EMBEDDING_BASE_URL:-https://api.kimi.com/coding/v1}"
EMBEDDING_BATCH_SIZE="${KIMI_EMBEDDING_BATCH_SIZE:-16}"
API_KEY_ENV="${KIMI_API_KEY_ENV:-KIMI_API_KEY}"
AUDIT_TENANT_ID="${MEDICAL_AUDIT_INTERNAL_TENANT_ID:-hospital-demo}"
AUDIT_PROJECT_KEY="${MEDICAL_AUDIT_INTERNAL_PROJECT_KEY:-SELF-CHECK-FUND-20260607}"
AUDIT_INTERNAL_USER_ID="${MEDICAL_AUDIT_INTERNAL_USER_ID:-local-bootstrap-admin}"
AUDIT_INTERNAL_ROLE="${MEDICAL_AUDIT_INTERNAL_ROLE:-it-admin}"

DEBUG_DIR="${MEDICAL_AUDIT_KB_DEBUG_DIR:-tmp/debug}"
HEALTH_OUTPUT="${DEBUG_DIR}/serve-chat-workbench-health.json"
BACKEND_OUTPUT="${DEBUG_DIR}/serve-chat-workbench-backend.json"

server_pid=""

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

require_backend_env() {
  if [[ "${LOAD_BACKEND}" != "1" || "${EMBEDDING_PROVIDER}" == "fake" ]]; then
    return
  fi

  api_key_value="${!API_KEY_ENV-}"
  if [[ -z "${api_key_value}" ]]; then
    die "missing ${API_KEY_ENV}; export it in the same shell before starting the API"
  fi
}

assert_port_is_not_serving_stale_api() {
  if ! curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
    return
  fi

  curl -fsS \
    -H "X-User-Id: ${AUDIT_INTERNAL_USER_ID}" \
    -H "X-Role: ${AUDIT_INTERNAL_ROLE}" \
    -H "X-Project-Key: ${AUDIT_PROJECT_KEY}" \
    -H "X-Tenant-Id: ${AUDIT_TENANT_ID}" \
    "${API_URL}/index/search-backend" > "${BACKEND_OUTPUT}" || true
  if grep -q '"ready":true' "${BACKEND_OUTPUT}"; then
    printf 'API is already running and search backend is ready: %s/pages/chat\n' "${API_URL}"
    exit 0
  fi

  die "API is already running at ${API_URL}, but search backend is not ready. Stop that process and restart with this script so ${API_KEY_ENV} is available inside the API process."
}

wait_for_health() {
  for _ in $(seq 1 60); do
    if curl -fsS "${API_URL}/health" > "${HEALTH_OUTPUT}" 2>/dev/null; then
      return
    fi
    if ! kill -0 "${server_pid}" 2>/dev/null; then
      die "uvicorn exited before /health became available"
    fi
    sleep 0.5
  done
  die "API did not become healthy within 30 seconds"
}

load_postgres_backend() {
  if [[ "${LOAD_BACKEND}" != "1" ]]; then
    printf 'API started without backend load: %s/pages/chat\n' "${API_URL}"
    return
  fi

  http_code="$(
    curl -sS -o "${BACKEND_OUTPUT}" -w '%{http_code}' \
      -X POST "${API_URL}/index/search-backend/postgres" \
      -H 'Content-Type: application/json' \
      -H "X-User-Id: ${AUDIT_INTERNAL_USER_ID}" \
      -H "X-Role: ${AUDIT_INTERNAL_ROLE}" \
      -H "X-Project-Key: ${AUDIT_PROJECT_KEY}" \
      -H "X-Tenant-Id: ${AUDIT_TENANT_ID}" \
      -d "{
        \"embedding_provider\":\"${EMBEDDING_PROVIDER}\",
        \"embedding_model\":\"${EMBEDDING_MODEL}\",
        \"embedding_dimension\":${EMBEDDING_DIMENSION},
        \"api_key_env\":\"${API_KEY_ENV}\",
        \"embedding_base_url\":\"${EMBEDDING_BASE_URL}\",
        \"embedding_batch_size\":${EMBEDDING_BATCH_SIZE}
      }"
  )"

  if [[ "${http_code}" != "200" ]]; then
    printf 'backend load response:\n' >&2
    cat "${BACKEND_OUTPUT}" >&2
    printf '\n' >&2
    die "backend load failed with HTTP ${http_code}"
  fi

  uv run python - "${BACKEND_OUTPUT}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("ready") is not True:
    raise SystemExit("search backend response is not ready")

matching_count = payload.get("details", {}).get("matching_embedding_count")
if not isinstance(matching_count, int) or matching_count <= 0:
    raise SystemExit("matching_embedding_count must be greater than 0")

print(f"PostgreSQL search backend ready: matching_embedding_count={matching_count}")
PY
}

main() {
  require_command uv
  require_command curl
  require_backend_env
  mkdir -p "${DEBUG_DIR}"
  assert_port_is_not_serving_stale_api

  export MEDICAL_AUDIT_KB_CONFIG="${CONFIG_PATH}"
  export MEDICAL_AUDIT_API_ACCESS_MODE="${API_ACCESS_MODE}"
  trap cleanup EXIT INT TERM

  uv run uvicorn "${APP_MODULE}" \
    --factory \
    --host "${HOST}" \
    --port "${PORT}" \
    --log-level "${LOG_LEVEL}" &
  server_pid="$!"

  wait_for_health
  load_postgres_backend

  printf 'Chat workbench ready: %s/pages/chat\n' "${API_URL}"
  if [[ "${OPEN_BROWSER}" == "1" ]] && command -v open >/dev/null 2>&1; then
    open "${API_URL}/pages/chat"
  fi

  wait "${server_pid}"
}

main "$@"
