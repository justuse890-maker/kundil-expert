#!/usr/bin/env bash
# One-command run: installs the locked backend environment and serves the API and UI.
# Usage: ./run.sh            (then open http://localhost:8000)
#        PORT=9000 ./run.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/backend"
uv sync --frozen
exec uv run uvicorn api.main:app --host 127.0.0.1 --port "${PORT:-8000}"
