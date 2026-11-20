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
# PG_BINDIR=<dir> puts that PostgreSQL's client tools first on PATH, e.g.
# /opt/homebrew/opt/postgresql@16/bin or /usr/lib/postgresql/16/bin.
#
# Versions: a custom-format dump only restores into a server whose major version
# is >= the server it was dumped from, and with a pg_restore whose major version
# is the target server's. A newer pg_restore writes settings an older server does
# not know (pg_restore 17+ sends `SET transaction_timeout`, which PostgreSQL 16
# and older reject). Both are checked before anything is created, so a drill on
# the wrong tools fails with the reason instead of half-way through a restore.
set -euo pipefail

usage() { echo "usage: $0 <dump-file> [--keep]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
DUMP="$1"; shift || true
KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1
[[ $# -eq 0 || ( $# -eq 1 && "$1" == "--keep" ) ]] || usage
[[ -r "$DUMP" ]] || { echo "cannot read dump: $DUMP" >&2; exit 2; }
[[ -n "${PG_BINDIR:-}" ]] && export PATH="$PG_BINDIR:$PATH"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${RESTORE_PYTHON:-$REPO/venv/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON="${RESTORE_PYTHON:-python3}"

IS_ARCHIVE=0
head -c 5 "$DUMP" | grep -q PGDMP && IS_ARCHIVE=1

if [[ $IS_ARCHIVE -eq 1 ]]; then
  server_num="$(psql -X -At -d postgres -c 'SHOW server_version_num')" || { echo "cannot reach the target server" >&2; exit 4; }
  server_major=$(( server_num / 10000 ))
  client_major="$(pg_restore --version | sed -E 's/^[^0-9]*([0-9]+).*/\1/')"
  source_version="$(pg_restore -l "$DUMP" | sed -n 's/^;[[:space:]]*Dumped from database version: //p' | head -1)"
  source_major="$(sed -E 's/^([0-9]+).*/\1/' <<<"$source_version")"
  echo "== versions: dump from server ${source_major:-?}, pg_restore $client_major, target server $server_major"
  if [[ -n "$source_major" && "$source_major" -gt "$server_major" ]]; then
    echo "version mismatch: the dump comes from PostgreSQL $source_major but the target server is $server_major;" >&2
    echo "restore it into a PostgreSQL $source_major (or newer) server (PGHOST/PGPORT)." >&2
    exit 5
  fi
  if [[ "$client_major" -ne "$server_major" ]]; then
    echo "version mismatch: pg_restore is $client_major but the target server is $server_major;" >&2
    echo "use PostgreSQL $server_major's client tools (PG_BINDIR=<its bin directory>)." >&2
    exit 5
  fi
fi

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
if [[ $IS_ARCHIVE -eq 1 ]]; then
  pg_restore --no-owner --no-acl --exit-on-error -d "$DB" "$DUMP"
else
  psql -v ON_ERROR_STOP=1 -q -d "$DB" -f "$DUMP" >/dev/null
fi
echo "   restored in $(( $(date +%s) - started ))s"

echo "== verifying restored database"
"$PYTHON" "$REPO/scripts/verify_restored_database.py" "$DB"
echo "== drill finished in $(( $(date +%s) - started ))s"
