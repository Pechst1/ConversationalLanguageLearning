#!/usr/bin/env bash
# WP-73 — restore drill: prove a dump restores and the app's schema is intact.
#
#   scripts/restore_drill.sh <dump-file> [--keep]
#
# Restores <dump-file> (pg_dump custom format, -Fc; a plain .sql also works) into
# a NEW throwaway database named wp73_drill_<timestamp>, verifies migration
# heads, core columns and ownership links, prints counts, and drops it
# again unless --keep is given. It never writes to any database it did not
# create: the target name is generated here and must start with wp73_drill_.
#
# Connection: PGHOST / PGPORT / PGUSER / PGPASSWORD as for psql (default: local
# socket, current user). Needs pg_restore/psql/createdb/dropdb on PATH and the
# repo's Python runtime (RESTORE_PYTHON, venv/bin/python, or python3).
set -euo pipefail

usage() { echo "usage: $0 <dump-file> [--keep]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
DUMP="$1"; shift || true
KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1
[[ $# -eq 0 || ( $# -eq 1 && "$1" == "--keep" ) ]] || usage
[[ -r "$DUMP" ]] || { echo "cannot read dump: $DUMP" >&2; exit 2; }

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${RESTORE_PYTHON:-$REPO/venv/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON="${RESTORE_PYTHON:-python3}"

DB="wp73_drill_$(date +%Y%m%d%H%M%S)_$$"
[[ "$DB" == wp73_drill_* ]] || { echo "refusing target $DB" >&2; exit 3; }

CREATED=0
cleanup() {
  [[ $CREATED -eq 1 ]] || return 0
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
CREATED=1

echo "== restoring $DUMP"
if head -c 5 "$DUMP" | grep -q PGDMP; then
  pg_restore --no-owner --no-acl --exit-on-error -d "$DB" "$DUMP"
else
  psql -v ON_ERROR_STOP=1 -q -d "$DB" -f "$DUMP" >/dev/null
fi
echo "   restored in $(( $(date +%s) - started ))s"

echo "== verifying restored database"
"$PYTHON" "$REPO/scripts/verify_restored_database.py" "$DB"
echo "== drill finished in $(( $(date +%s) - started ))s"
