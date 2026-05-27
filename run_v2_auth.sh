#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/.venv/bin/activate"

export AUTH_ENABLED="${AUTH_ENABLED:-true}"
export AUTH_ISSUER="${AUTH_ISSUER:-https://aac.platform.smartcommunitylab.it}"
export AUTH_JWKS_URL="${AUTH_JWKS_URL:-https://aac.platform.smartcommunitylab.it/jwk}"
export AUTH_AUDIENCE="${AUTH_AUDIENCE:-c_e550ec7f86174720872ac9c36fbecdcb}"
export AUTH_TENANT_CLAIM="${AUTH_TENANT_CLAIM:-tenant_id}"
export AUTH_ALGORITHMS="${AUTH_ALGORITHMS:-RS256}"
export AUTH_LEEWAY_SECONDS="${AUTH_LEEWAY_SECONDS:-30}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

exec fastapi run ./overtourism/overtourism/app_v2.py --host "$HOST" --port "$PORT"
