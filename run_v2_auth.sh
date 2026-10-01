#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/.venv/bin/activate"
export OVERTOURISM_DATABASE="sqlite:///overtourism/overtourism/database/overtourism.sqlite"

if [[ $# -gt 1 ]]; then
	printf 'Usage: %s [admin-email]\n' "$0" >&2
	exit 2
fi

#export OVERTOURISM_DATABASE="postgresql+psycopg://postgres:123@localhost:5432/postgres"
export DT_OVERTURISM_STANDALONE_MODE="${DT_OVERTOURISM_STANDALONE_MODE:-true}"
export AUTH_ENABLED="${AUTH_ENABLED:-true}"
export AUTH_ISSUER="${AUTH_ISSUER:-https://aac.platform.smartcommunitylab.it}"
export AUTH_JWKS_URL="${AUTH_JWKS_URL:-https://aac.platform.smartcommunitylab.it/jwk}"
export AUTH_AUDIENCE="${AUTH_AUDIENCE:-c_50e8e205e30243588df8f1ad9425831a}"
export AUTH_ALGORITHMS="${AUTH_ALGORITHMS:-RS256}"
export AUTH_LEEWAY_SECONDS="${AUTH_LEEWAY_SECONDS:-30}"
export MODEL_BACKEND_URL="${MODEL_BACKEND_URL:-http://localhost:8001}"

if [[ $# -eq 1 ]]; then
	python -m overtourism.backend.auth.identity.bootstrap_admin "$1"
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
MAIN_PORT="${MAIN_PORT:-8001}"
STARTUP_DELAY_SECONDS="${STARTUP_DELAY_SECONDS:-5}"
kill -9 $(lsof -t -i:$MAIN_PORT) >/dev/null 2>&1 || true
kill -9 $(lsof -t -i:$PORT) >/dev/null 2>&1 || true

fastapi run ./overtourism/layer_3/api/main.py --host "$HOST" --port "$MAIN_PORT" &
MAIN_PID=$!

sleep "$STARTUP_DELAY_SECONDS"

cleanup() {
	kill "$MAIN_PID" >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

exec fastapi run ./overtourism/overtourism/app_v2.py --host "$HOST" --port "$PORT"
