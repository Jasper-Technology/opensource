#!/usr/bin/env bash
# Local-dev entrypoint for the Jasper TEA backend.
# - Sets ENVIRONMENT=development so the CORS guard doesn't refuse to start.
# - Allows every vite dev port (5173/5174/5175) + 127.0.0.1 variants.
# - Runs on 0.0.0.0:8000 so both `localhost` and `127.0.0.1` frontends reach it.
set -euo pipefail

cd "$(dirname "$0")"

export ENVIRONMENT="${ENVIRONMENT:-development}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:3000,http://localhost:4173,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5175}"

PORT="${PORT:-8000}"
RELOAD_FLAG="${RELOAD:---reload}"

echo "→ TEA backend on http://localhost:${PORT}"
echo "→ CORS origins: ${CORS_ORIGINS}"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" ${RELOAD_FLAG}
