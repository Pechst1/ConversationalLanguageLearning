#!/usr/bin/env bash
# A walkable local database in one command (2026-10-09).
#
#   scripts/dev_walk_db.sh NAME [--learners en,de,fr] [--reuse]
#
# createdb NAME → alembic upgrade head → the core lexicon (the drill's only source
# of new words: without it «5 more minutes» and the drill are empty) → the grammar
# catalogue → one fresh learner per listed chrome language. Learner emails and
# passwords go to .dev-learners-NAME (gitignored), never to the terminal. Prints the
# DATABASE_URL to put in a .claude/launch.json backend entry.
#
# Mirrors docker/entrypoint.sh (RUN_MIGRATIONS + BOOTSTRAP_REFERENCE_DATA). Refuses
# the owner's language_learning database and any name that already exists unless
# --reuse is given.
set -euo pipefail

name="${1:-}"
shift || true
learners="en"
reuse=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --learners) learners="$2"; shift 2 ;;
    --reuse) reuse=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
if [ -z "$name" ] || ! [[ "$name" =~ ^[a-z0-9_]+$ ]]; then
  echo "usage: scripts/dev_walk_db.sh NAME [--learners en,de,fr] [--reuse]  (NAME: [a-z0-9_]+)" >&2
  exit 2
fi
if [ "$name" = "language_learning" ]; then
  echo "refusing the owner's database" >&2
  exit 2
fi

root="$(cd "$(dirname "$0")/.." && pwd)"
python="${PYTHON:-$root/venv/bin/python}"
[ -x "$python" ] || python="$(git -C "$root" rev-parse --path-format=absolute --git-common-dir)/../venv/bin/python"
[ -x "$python" ] || { echo "no venv python found; set PYTHON=" >&2; exit 2; }
url="postgresql+psycopg2://${PGUSER:-$USER}@localhost:5432/$name"

if psql -lqt | cut -d'|' -f1 | tr -d ' ' | grep -qx "$name"; then
  if [ "$reuse" != 1 ]; then echo "database $name exists (pass --reuse to migrate and seed it anyway)" >&2; exit 2; fi
else
  createdb "$name"
fi

cd "$root"
export DATABASE_URL="$url" PYTHONPATH="$root"
echo "migrating $name"
"$python" -m alembic upgrade head >/dev/null
echo "syncing the core lexicon"
"$python" scripts/sync_core_lexicon.py | tail -1
echo "installing the grammar catalogue"
"$python" scripts/import_french_core_grammar.py --backfill-blueprints >/dev/null

creds="$root/.dev-learners-$name"
LEARNERS="$learners" CREDS="$creds" "$python" - <<'EOF'
import os, secrets
from app.db.session import SessionLocal
from app.schemas.user import UserCreate
from app.services.auth import AuthService, EmailAlreadyExistsError

db = SessionLocal()
lines = []
for native in [x for x in os.environ["LEARNERS"].split(",") if x]:
    email = f"walk-{native}-{secrets.token_hex(3)}@atelier-qa.dev"
    password = secrets.token_hex(12)
    try:
        AuthService(db).register_user(UserCreate(email=email, password=password, native_language=native))
    except EmailAlreadyExistsError:
        continue
    lines.append(f"{native}\t{email}\t{password}")
db.commit()
with open(os.environ["CREDS"], "a", encoding="utf-8") as handle:
    handle.write("".join(f"{line}\n" for line in lines))
os.chmod(os.environ["CREDS"], 0o600)
print(f"{len(lines)} learner(s) written to {os.environ['CREDS']}")
EOF

words="$(psql -d "$name" -Atc "select count(*) from vocabulary_words where deck_name = 'Lexique de base'")"
echo "ready: $words core words"
echo "DATABASE_URL=$url"
