#!/usr/bin/env bash
# Smoke test against a running server (see scripts/smoke_test.py).
set -euo pipefail
cd "$(dirname "$0")/.."
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}" python3 scripts/smoke_test.py
