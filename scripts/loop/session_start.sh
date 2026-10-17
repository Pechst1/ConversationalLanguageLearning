#!/usr/bin/env bash
# SessionStart hook (.claude/settings.json): every cloud session, the night shift's fixers and
# verifiers included, starts with the checks CI runs already installed: the Python 3.11 venv
# with fastapi and the spaCy model, web-frontend's node_modules, and a local Postgres for the
# walk and the postgres tests. Night shift 16 Oct: 6 of 8 PRs failed their own check because
# the fixer's sandbox had no fastapi; setup_env.sh existed but each agent had to remember it.
#
# Local sessions are left alone (CLAUDE_CODE_REMOTE is only set in the cloud).
set -uo pipefail
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"
VENV="${ATELIER_VENV:-$HOME/.venvs/atelier}"

if ! bash scripts/loop/setup_env.sh >/tmp/atelier-setup.log 2>&1; then
  echo "setup_env.sh failed; see /tmp/atelier-setup.log" >&2
  tail -5 /tmp/atelier-setup.log >&2
fi

# Postgres: CI's walk and postgres jobs use postgres:postgres@localhost:5432.
if command -v pg_ctlcluster >/dev/null; then
  for cluster in $(pg_lsclusters -h 2>/dev/null | awk '$4 != "online" {print $1 "/" $2}'); do
    pg_ctlcluster "${cluster%/*}" "${cluster#*/}" start >/dev/null 2>&1 || true
  done
  su postgres -c "psql -qc \"ALTER USER postgres PASSWORD 'postgres'\"" >/dev/null 2>&1 || true
fi

if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -x "$VENV/bin/python" ]; then
  {
    echo "export VIRTUAL_ENV=\"$VENV\""
    echo "export PATH=\"$VENV/bin:\$PATH\""
    echo "export WALK_PG_ADMIN_URL=postgresql://postgres:postgres@localhost:5432/postgres"
    echo "export WALK_PYTHON=\"$VENV/bin/python\""
  } >>"$CLAUDE_ENV_FILE"
fi
echo "Atelier test environment ready: python -m pytest, npm test in web-frontend, Postgres on :5432."
