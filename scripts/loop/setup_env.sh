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
# No `-q` here: spaCy reads it as the model name («No compatible package found for
# '-q'»), the script then exited 1 under `set -e`, `&& source …activate` never ran,
# and pytest fell back to the system Python without fastapi (night shift 16 Oct).
"$VENV/bin/python" -c 'import fr_core_news_sm' 2>/dev/null \
  || "$VENV/bin/python" -m spacy download fr_core_news_sm >/dev/null

# A night-shift worktree shares the main checkout's node_modules when the lockfile is the
# same: a fresh `npm ci` per worktree took minutes, and 5 fixers plus 5 verifiers run at once.
MAIN_CHECKOUT="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)"
if [ ! -e web-frontend/node_modules ] && [ "$MAIN_CHECKOUT" != "$PWD" ] \
  && [ -d "$MAIN_CHECKOUT/web-frontend/node_modules" ] \
  && cmp -s web-frontend/package-lock.json "$MAIN_CHECKOUT/web-frontend/package-lock.json"; then
  ln -s "$MAIN_CHECKOUT/web-frontend/node_modules" web-frontend/node_modules
fi
if [ ! -d web-frontend/node_modules ]; then
  (cd web-frontend && npm ci --no-audit --no-fund --loglevel=error)
fi
echo "ready: source $VENV/bin/activate"
