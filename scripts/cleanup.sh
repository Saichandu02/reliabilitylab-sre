#!/usr/bin/env bash
# Remove local runtime artifacts (never touches tracked files).
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf .venv .pytest_cache data
find . -name __pycache__ -type d -prune -exec rm -rf {} +
echo "Cleaned. For the Compose path: docker compose down -v"
