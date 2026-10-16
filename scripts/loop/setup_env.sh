#!/usr/bin/env bash
# Make a cloud session able to run the focused checks the night shift needs:
# Python 3.11 venv like CI (`pip install -c constraints.txt -e .[dev]` + the spaCy model)
# and web-frontend's node_modules. Safe to run twice. Prints the line to activate it.
#
#   bash scripts/loop/setup_env.sh && source "$HOME/.venvs/atelier/bin/activate"
#
# In a git worktree run pytest as `python -m pytest` from the worktree root, so the
# worktree's `app` is imported, not the checkout the editable install points at.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
VENV="${ATELIER_VENV:-$HOME/.venvs/atelier}"

if [ ! -x "$VENV/bin/python" ]; then
  if command -v uv >/dev/null; then
    uv venv -q -p python3.11 "$VENV"
  else
    python3.11 -m venv "$VENV"
  fi
fi
if command -v uv >/dev/null; then
  VIRTUAL_ENV="$VENV" uv pip install -q pip
  VIRTUAL_ENV="$VENV" uv pip install -q -c constraints.txt -e '.[dev]'
else
  "$VENV/bin/python" -m pip install -q -c constraints.txt -e '.[dev]'
fi
"$VENV/bin/python" -c 'import fr_core_news_sm' 2>/dev/null \
  || "$VENV/bin/python" -m spacy download -q fr_core_news_sm >/dev/null

if [ ! -d web-frontend/node_modules ]; then
  (cd web-frontend && npm ci --no-audit --no-fund --loglevel=error)
fi
echo "ready: source $VENV/bin/activate"
