#!/usr/bin/env bash
# Bootstrap the Docker-free local path: venv + dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "python: $(python3 --version)"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
echo "Bootstrap complete. Run: .venv/bin/python -m pytest -q"
echo "Serve:    DATABASE_PATH=data/orders.db .venv/bin/uvicorn app.main:app --port 8000"
