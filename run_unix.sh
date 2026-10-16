#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.txt
printf 'Open http://127.0.0.1:8000 in your browser. Stop with Ctrl+C.\n'
exec .venv/bin/python -m uvicorn clientflow.api:app --host 127.0.0.1 --port 8000
