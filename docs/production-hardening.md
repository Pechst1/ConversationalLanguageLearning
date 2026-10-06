# Production hardening — 2026-09-30

This batch covers release gates, password recovery, import boundaries and database
restore verification. Vocabulary learning and SRS changes are owned by the other
implementation and are not part of this batch.

## Release contract

CI calls the browser walk for the same commit as its backend, PostgreSQL,
frontend, generated-types and Docker checks. All checks must pass before its
publish job can call `publish-image.yml`. There is no independent publish trigger.
Published images include `sha-<full 40-character commit>` tags.

For production Compose, put production credentials in `.env.prod`, then use:

```sh
export APP_IMAGE=ghcr.io/pechst1/conversational-language-learning:sha-<tested-commit>
bash scripts/production_compose.sh config
bash scripts/production_compose.sh pull
bash scripts/production_compose.sh up -d
```

The wrapper accepts full commit tags and image digests, and rejects `latest`.
The API and worker share the same reference. To roll back, choose the previous
tested image and run the wrapper again. Do not downgrade the learner database
as a routine image rollback; the new outbox migration is additive.

Require the CI checks in branch protection. The Render blueprint now sets
`autoDeployTrigger: checksPass` for both API and worker, using Render's
[documented CI gate](https://render.com/docs/blueprint-spec#autodeploytrigger).
Sync and verify this setting on existing services before relying on it. Hosting
account settings and running deployments have not been changed by this batch.

## Password recovery

Migration `b9d1f3a5c7e0` adds `password_reset_deliveries`. Run migrations before
starting the new API and worker. Requests store the reset digest and encrypted
email payload in one transaction, then try SMTP immediately. Failed delivery is
retried from the database every 30 seconds by Celery beat with exponential backoff.
Five unsuccessful attempts end delivery; recovery messages expire after 15 minutes.

Both API and worker need the same `SECRET_KEY` and SMTP settings. Render inherits
the worker's credentials from the API. API/worker restarts and broker failures
do not lose the message. SMTP may deliver before a process dies; a retry can send
the same email twice, but never issues another reset code.

The payload is encrypted using a purpose-specific key derived from `SECRET_KEY`.
It is erased on delivery, cancellation or exhausted retries; terminal metadata
is deleted after seven days. Changing `SECRET_KEY` cancels pending encrypted
messages, so users need to request a fresh code. Authentication payloads are
excluded from account data exports.

Account row locks serialize issuance, guesses, link/code confirmation, refreshes,
and delivery. Password replacement and refresh revocation commit together. The
cooldown also applies after exhausted guesses.

## Imports

Book uploads accept at most 10 MB; Anki CSV uploads/text accept at most 20 MB.
Request-body limits apply before multipart spooling or JSON parsing and also
cover chunked requests. Multipart/JSON transport overhead is bounded to 64 KiB.
Oversized imports return 413; empty files return 400. EPUB archives may contain
at most 2,000 entries and 40 MB of uncompressed data.

The web server's `/api/anki` and `/anki-connect` localhost bridges are disabled in
production. Local development retains the bridge with a five-second timeout.

## Recovery verification

```sh
PGHOST=<backup-test-host> PGUSER=<backup-test-user> \
  bash scripts/restore_drill.sh /path/to/backup.dump
```

Use libpq environment variables for credentials. The script creates its own
`wp73_drill_*` database and removes it on success or failure. `--keep` preserves
it for inspection. It fails on a restore error, incorrect migration heads,
missing core columns, or orphaned ownership links. Verification loads no app
`.env` and prints table counts, never learner content.

CI restores an actual PostgreSQL dump, rejects outdated/incomplete/broken dumps,
and checks cleanup. It also runs real PostgreSQL password-recovery races.
Locally, set `PRODUCTION_READINESS_PG_URL` to a migrated database whose name starts
with `atelier_ci_` or `atelier_readiness_` and run:

```sh
venv/bin/python -m pytest -q tests/test_production_auth_pg.py tests/test_production_recovery_pg.py
```

This verifies the database backup path. Production backup scheduling, retention,
off-host storage and a restore of a real production backup still require the
hosting configuration. With S3/local media, back up and restore the corresponding
objects/files as well; this database drill does not restore external artwork.
