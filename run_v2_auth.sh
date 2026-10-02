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

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
MAIN_PORT="${MAIN_PORT:-8001}"
HEALTH_CHECK_TIMEOUT_SECONDS="${HEALTH_CHECK_TIMEOUT_SECONDS:-60}"
kill -9 $(lsof -t -i:$MAIN_PORT) >/dev/null 2>&1 || true
kill -9 $(lsof -t -i:$PORT) >/dev/null 2>&1 || true

if ! [[ "$HEALTH_CHECK_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
	printf 'HEALTH_CHECK_TIMEOUT_SECONDS must be a positive integer.\n' >&2
	exit 2
fi

wait_for_readiness() {
	local service_name="$1"
	local service_port="$2"
	local process_id="$3"
	local attempt

	for ((attempt = 0; attempt < HEALTH_CHECK_TIMEOUT_SECONDS; attempt++)); do
		if python -c 'import sys; from urllib.request import urlopen; urlopen(f"http://127.0.0.1:{sys.argv[1]}/health/ready", timeout=1)' "$service_port" >/dev/null 2>&1; then
			return 0
		fi
		if ! kill -0 "$process_id" >/dev/null 2>&1; then
			wait "$process_id" || true
			printf '%s exited before becoming ready.\n' "$service_name" >&2
			return 1
		fi
		sleep 1
	done
	printf '%s did not become ready within %s seconds.\n' \
		"$service_name" "$HEALTH_CHECK_TIMEOUT_SECONDS" >&2
	return 1
}

fastapi run ./overtourism/layer_3/api/main.py --host "$HOST" --port "$MAIN_PORT" &
MAIN_PID=$!
API_PID=""

cleanup() {
	kill "$MAIN_PID" >/dev/null 2>&1 || true
	if [[ -n "$API_PID" ]]; then
		kill "$API_PID" >/dev/null 2>&1 || true
	fi
}

trap cleanup EXIT INT TERM

if ! wait_for_readiness "Layer 3 backend" "$MAIN_PORT" "$MAIN_PID"; then
	exit 1
fi

fastapi run ./overtourism/overtourism/app_v2.py --host "$HOST" --port "$PORT" &
API_PID=$!

if [[ $# -eq 1 ]]; then
	if ! wait_for_readiness "API backend" "$PORT" "$API_PID"; then
		exit 1
	fi
	python -m bootstrap_admin "$1"
fi

wait "$API_PID"
