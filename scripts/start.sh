#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python || ! -d frontend/node_modules ]]; then
  echo "Install the dependencies in README.md first."
  exit 1
fi
.venv/bin/python - <<'PY'
import socket
for port in [8000, 5173]:
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'Port {port} is already in use. Stop the existing service or use the separate-terminal commands in README.md.')
PY
if [[ ! -f backend/artifacts/models.joblib || ! -f backend/artifacts/forecast_models.joblib ]]; then
  .venv/bin/python -m backend.app.ml
fi
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!
(cd frontend && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort) &
ui_pid=$!
cleanup() {
  kill "$api_pid" "$ui_pid" 2>/dev/null || true
  wait "$api_pid" "$ui_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
echo "Dashboard: http://127.0.0.1:5173"
echo "API documentation: http://127.0.0.1:8000/docs"
while kill -0 "$api_pid" 2>/dev/null && kill -0 "$ui_pid" 2>/dev/null; do
  sleep 1
done
echo "A service stopped. Check its output above."
exit 1
