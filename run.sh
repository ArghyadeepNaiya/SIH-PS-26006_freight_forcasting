#!/usr/bin/env bash
# One-command start. Serves API and dashboard on http://localhost:8000
set -e
cd "$(dirname "$0")/ml-service"
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -q -r requirements.txt
echo "Starting. Dashboard will be at http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000
