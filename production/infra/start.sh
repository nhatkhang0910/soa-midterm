#!/bin/sh
set -eu
if [ "$#" -gt 0 ]; then exec "$@"; fi
python -m common.migrate
python -m "$SERVICE_NAME.seed"
exec uvicorn "$SERVICE_NAME.app:app" --host 0.0.0.0 --port 8000 --no-access-log
