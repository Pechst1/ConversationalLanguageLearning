# Production hardening verification — 2026-09-30

Implemented batch: verified-image publication, blocking browser CI, pinned
production Compose deployment, Render CI gates, transactional password recovery,
encrypted durable SMTP retries, bounded imports, production Anki bridge removal,
and strict database restore verification.

## Passed

- 130 affected backend tests: accounts, exports, schema guards, imports, book
  parsing, Celery, SQLite UUID handling and CI tooling.
- 63 focused tests repeated after the final delivery safeguard, including
  cancellation of email containing an exhausted reset code.
- Eight real PostgreSQL tests: link/code confirmation race, parallel guesses,
  concurrent requests, duplicate delivery workers, actual dump restoration,
  and rejection/cleanup of outdated, incomplete and invalid dumps.
- The two new frontend production-boundary tests.
- The outbox migration was reversed and reapplied successfully on PostgreSQL;
  the final four release/Render-manifest checks passed.
- Frontend TypeScript checking and ESLint (one existing notebook hook warning).
- Ruff for every Python file changed in this batch; shell syntax and diff checks.

The PostgreSQL work used a separate cluster on port 25439, a disposable
`atelier_readiness_ci` database, generated authentication schemas, and generated
`wp73_drill_*` restore databases. No application/production database was migrated.
SMTP and model providers were faked; no real email was sent.

## Release checks still failing

- The full browser walk completed its learner/season flows but reported one
  `no-english-on-french-b1` failure on the B1 settings screen. Its report and
  screenshots are at `/private/tmp/cll-readiness-walk/index.html`.
- Repository-wide Ruff found 49 findings outside this batch's changed Python
  files, including learning files being edited by the vocabulary agent.
- The full frontend test run passed 678/679 tests. The failure is generated API
  type freshness, while the other agent is changing vocabulary schemas.

These checks remain blocking. The vocabulary drill, SRS services, vocabulary
schemas and browser walkthrough implementation have not been edited by this
batch. Re-run the full release checks after that implementation is integrated;
do not treat the passing focused checks as a production-launch declaration.

## Deployment work remaining

Apply migration `b9d1f3a5c7e0` before starting the new API and worker. Sync the
Render blueprint or use the pinned Compose wrapper, verify SMTP in the deployed
environment, require branch-protection checks, and configure off-host production
backups plus external media recovery. Nothing was deployed or published here.
