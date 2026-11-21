# L'Atelier

L'Atelier is a daily French lesson built around a serial story. Each day the learner reads
the next page of the story, talks with its characters, practises the day's grammar rule and
words, and comes back tomorrow for the next page. The story is a season: tentpole episodes on
fixed days, with generated days in between that adapt to the learner's level (A1 to C1).

The app has four tabs:

- **La Une**: today's page. The day's plan, the next step, and the recap when the day is done.
- **Feuilleton**: the serial. Every page read so far, and the season's thread.
- **Courrier**: letters from the characters. The learner writes back and gets a reply.
- **Cahier**: the notebook. Words, rules and mistakes the learner has met, for review.

The interface speaks the learner's language (English, German or French); the lesson is French.

## What is in this repository

| Path | What it is |
|---|---|
| `app/` | The API: FastAPI, PostgreSQL through SQLAlchemy, Celery on Redis. Live data files are in `app/data/`. |
| `alembic/` | Database migrations. |
| `scripts/` | Command-line tools: seeding, the lexicon build, the walk servers, the nightly loop. |
| `tests/` | The backend test suite (pytest). |
| `web-frontend/` | The client: Next.js. The iOS app is this client in a Capacitor shell (`web-frontend/ios`, `web-frontend/fastlane`). |
| `docker/`, `Dockerfile`, `render.yaml` | The image and the Render deployment. |
| `docs/` | Plans, specs, walk reports and ops notes. |

## Run it locally

You need Python 3.11, PostgreSQL 15, Redis 7 and Node 18 or newer.

Backend, on port 8010:

```bash
python3.11 -m venv venv
venv/bin/pip install -e '.[dev]'
cp .env.example .env            # then fill in the database URL and the model keys
venv/bin/python -m spacy download fr_core_news_sm
venv/bin/alembic upgrade head
venv/bin/python scripts/sync_core_lexicon.py
CELERY_TASK_ALWAYS_EAGER=true venv/bin/uvicorn app.main:app --port 8010 --timeout-keep-alive 75
```

Without `sync_core_lexicon.py` a fresh database has no words, and the drills have nothing to
deal.

Client, on port 3000:

```bash
cd web-frontend
npm install
API_URL=http://localhost:8010 NEXT_PUBLIC_API_URL=http://localhost:8010/api/v1 npm run dev
```

The same commands are in `.claude/launch.json`. The full backend guide (Docker Compose,
Celery, seeding, the older API) is in [docs/dev/backend.md](docs/dev/backend.md).

## Tests

```bash
TZ=UTC venv/bin/pytest            # backend; test order is shuffled on every run
cd web-frontend && npm test       # client unit tests
```

CI runs both, plus migrations up and down and a Docker build: `.github/workflows/ci.yml`.

## Walks

A walk plays real days in a browser and screenshots every screen.

- The local walk (`npm run walk` in `web-frontend/`) plays seven days on a throwaway stack.
  How it works: [docs/dev/backend.md](docs/dev/backend.md#browser-walk-e-3).
- The live walk plays the production app every night: [docs/ops/live-walk.md](docs/ops/live-walk.md).
- What a walk is scored on: [docs/ops/walk-rubric.md](docs/ops/walk-rubric.md).
- Reports: `docs/ops/walks/` and `docs/ops/live-walks/`.

## Operations

- Deployment and hardening: [docs/production-hardening.md](docs/production-hardening.md)
- Backups: [docs/ops/BACKUP-AND-RESTORE.md](docs/ops/BACKUP-AND-RESTORE.md)
- Images: [docs/ops/image-storage.md](docs/ops/image-storage.md)
- The nightly improvement loop: [docs/ops/improvement-loop.md](docs/ops/improvement-loop.md)
- iOS release: [docs/testflight-production-flip-checklist.md](docs/testflight-production-flip-checklist.md)
- Where the iOS release stands: [docs/ops/release-status.md](docs/ops/release-status.md)

## The repository root

The root holds only what a build, a test run or a deploy reads. `tests/test_repository_root.py`
lists the allowed entries and fails on a new one. Old planning notes are in `docs/archive/`.
