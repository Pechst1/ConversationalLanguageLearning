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
  #
  # WP-70: more than one worker, so a request stuck on a provider (or a crash)
  # never takes the whole API with it. --factory is compatible with --workers:
  # each worker process calls create_app() itself. Each worker is its own
  # Python process (~150-250 MB resident with the app loaded), so on Render's
  # 512 MB starter plan keep WEB_CONCURRENCY at 2; raise it with the plan.
  # Rate-limit counters live in Redis so every worker shares them.
  exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" --timeout-keep-alive 75
fi
