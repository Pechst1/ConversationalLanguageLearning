#!/usr/bin/env bash
set -euo pipefail

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Running database migrations"
  alembic upgrade head
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
else
  exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}"
fi
