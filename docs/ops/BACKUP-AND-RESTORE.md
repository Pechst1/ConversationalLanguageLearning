# Backup and restore — L'Atelier (WP-73)

Owner-facing runbook. Last drill: **2026-09-22**, local, `scripts/restore_drill.sh`
on a `pg_dump -Fc` of the dev database (8 MB, 60+ tables): restore 1 s,
`alembic current` = `2face6b8f71e (head)`, row counts printed, throwaway DB dropped.

## 1. What Render already does

`render.yaml` provisions `atelier-db` on plan **`basic-256mb`** (a paid plan, Frankfurt).
On paid Render Postgres plans (check the database's **Recovery** tab — Render changes these
terms; confirm them there before relying on them):

- **Point-in-time recovery (PITR)**: restore to any moment inside the retention window
  (3 days on a Hobby workspace, 7 days on Professional and up). A PITR restore creates a
  **new** database; the old one is untouched until you repoint `DATABASE_URL`.
- **Exports (logical backups)**: downloadable `pg_dump` files from the dashboard's
  Recovery/Backups tab.
- Free-plan databases have neither and expire — never run the pilot on one.

The Redis key-value store (`atelier-redis`) holds only the Celery broker, rate-limit
windows and the worker heartbeat. It is **not** backed up and does not need to be.

## 2. Manual dump (before every migration-bearing deploy, and weekly)

From the Render dashboard → `atelier-db` → *Connect* → copy the **External Database URL**
(add your IP to the database's access control first).

```bash
export PROD_URL='postgresql://atelier:…@….frankfurt-postgres.render.com/language_learning'
pg_dump -Fc --no-owner --no-acl "$PROD_URL" -f "atelier-$(date +%Y%m%d-%H%M).dump"
```

- `-Fc` (custom format) is compressed and restores selectively with `pg_restore`.
- Use a `pg_dump` whose major version is ≥ the server's (`SELECT version();`).
- The dump contains learner data (emails, French writing). Store it encrypted
  (e.g. an encrypted disk image or `age -r … file.dump`), never in the repo, and delete
  old copies — keep the last 4 weekly dumps.

## 3. Restore drill (monthly, and after changing the backup setup)

```bash
scripts/restore_drill.sh atelier-20260922-0900.dump          # restore, check, drop
scripts/restore_drill.sh atelier-20260922-0900.dump --keep   # keep it to inspect
```

The script creates a new database `wp73_drill_<timestamp>_<pid>`, restores into it,
prints `alembic current` (must say `(head)` for the release you run) and a row count
for every table, then drops it. It never writes to a database it did not create.
Compare the counts with production (`users`, `pilot_events`, `serial_episodes`,
`user_vocabulary_progress` are the ones that matter), note the duration and date at the
top of this file.

## 4. Real restore (production incident)

1. **Stop writers**: suspend `atelier-worker` and scale/suspend `atelier-api` in the dashboard.
2. **Choose the source**: PITR to just before the incident (preferred), or the newest dump.
3. PITR → Render creates a new database. Dump → create a new Render Postgres and
   `pg_restore --no-owner --no-acl -d "$NEW_URL" file.dump`.
4. Run `scripts/restore_drill.sh`-style checks against it: `DATABASE_URL=$NEW_URL venv/bin/alembic current`
   and the row counts.
5. Point `DATABASE_URL` of **both** `atelier-api` and `atelier-worker` at the new database
   (in `render.yaml` via `fromDatabase` name, or the dashboard env var), redeploy the API
   first (`RUN_MIGRATIONS=1` brings the schema to head), then resume the worker.
6. Check `/ready` (API + schema) and `/health/worker` (heartbeat within 5 min).
7. Write down what was lost (window between restore point and incident) for the learners.

## 5. Seeing production (related WP-73 signals)

- `GET /ready` — database reachable and schema at head (Render health check).
- `GET /health/worker` — `200 {"status":"ok","age_seconds":…}` while beat and a worker
  run; `503` with `stale` / `missing` / `unreachable` otherwise. Not part of `/ready`,
  so a dead worker never takes the API down; point an uptime monitor at it.
- Logs are JSON in production (`LOG_FORMAT=json`): each line has `request_id` and the
  call's extra fields under `extra`. Every response carries `X-Request-ID`; search
  logs and Sentry by it.
- Sentry: set `SENTRY_DSN` (API + worker) and `NEXT_PUBLIC_SENTRY_DSN` (web/native build).
  Without them everything is a no-op.
