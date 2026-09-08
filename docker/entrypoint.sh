#!/usr/bin/env bash
set -euo pipefail

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Running database migrations"
  alembic upgrade head
fi

if [ "${BOOTSTRAP_REFERENCE_DATA:-0}" = "1" ]; then
  echo "Installing idempotent grammar and starter-vocabulary catalogs"
  python scripts/import_french_core_grammar.py --backfill-blueprints
  python scripts/seed_vocabulary.py --csv vocabulary_fr_sample.csv
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
else
  # keep-alive must outlive the Next.js proxy's socket reuse window or pooled
  # connections die mid-flight with ECONNRESET on the web deployment.
  exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}" --timeout-keep-alive 75
fi
