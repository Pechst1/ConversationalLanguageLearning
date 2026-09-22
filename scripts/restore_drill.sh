#!/usr/bin/env bash
# WP-73 — restore drill: prove a dump restores and the app's schema is intact.
#
#   scripts/restore_drill.sh <dump-file> [--keep]
#
# Restores <dump-file> (pg_dump custom format, -Fc; a plain .sql also works) into
# a NEW throwaway database named wp73_drill_<timestamp>, then prints
# `alembic current` against it and row counts for every table, and drops it
# again unless --keep is given. It never writes to any database it did not
# create: the target name is generated here and must start with wp73_drill_.
#
# Connection: PGHOST / PGPORT / PGUSER / PGPASSWORD as for psql (default: local
# socket, current user). Needs pg_restore/psql/createdb/dropdb on PATH and the
# repo's venv (venv/bin/alembic).
set -euo pipefail

usage() { echo "usage: $0 <dump-file> [--keep]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
DUMP="$1"; shift || true
KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1
[[ -r "$DUMP" ]] || { echo "cannot read dump: $DUMP" >&2; exit 2; }

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ALEMBIC="$REPO/venv/bin/alembic"
[[ -x "$ALEMBIC" ]] || ALEMBIC="alembic"

DB="wp73_drill_$(date +%Y%m%d%H%M%S)_$$"
[[ "$DB" == wp73_drill_* ]] || { echo "refusing target $DB" >&2; exit 3; }

cleanup() {
  if [[ $KEEP -eq 0 ]]; then
    dropdb --if-exists "$DB" && echo "dropped $DB"
  else
    echo "kept $DB (drop it with: dropdb $DB)"
  fi
}
trap cleanup EXIT

started=$(date +%s)
echo "== creating throwaway database $DB"
createdb "$DB"

echo "== restoring $DUMP"
if head -c 5 "$DUMP" | grep -q PGDMP; then
  pg_restore --no-owner --no-acl --exit-on-error -d "$DB" "$DUMP"
else
  psql -v ON_ERROR_STOP=1 -q -d "$DB" -f "$DUMP" >/dev/null
fi
echo "   restored in $(( $(date +%s) - started ))s"

if [[ -n "${PGHOST:-}" ]]; then
  URL="postgresql://${PGUSER:-$USER}${PGPASSWORD:+:$PGPASSWORD}@${PGHOST}:${PGPORT:-5432}/$DB"
else
  URL="postgresql:///$DB"
fi

echo "== alembic current"
(cd "$REPO" && DATABASE_URL="$URL" "$ALEMBIC" current 2>&1 | grep -v "^INFO" || true)

echo "== row counts"
psql -X -q -At -d "$DB" <<'SQL'
DO $$
DECLARE r record; n bigint;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename LOOP
    EXECUTE format('SELECT count(*) FROM public.%I', r.tablename) INTO n;
    RAISE NOTICE '%', rpad(r.tablename, 48) || n;
  END LOOP;
END $$;
SQL
echo "== drill finished in $(( $(date +%s) - started ))s"
