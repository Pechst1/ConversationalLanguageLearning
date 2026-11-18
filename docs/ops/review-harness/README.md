# Review harness: playing several days on real model output

Used for the experience review of 17 Nov 2026 and the walks of the pilot integration branch. It is test tooling, never shipped.

## Pieces

- `scripts/review_walk_server.py` — the API with production's story settings from `render.yaml`, a test clock, and a **hard spend cap**: every model call is reserved against `SEASON_END_MAX_USD` before it leaves, and refused over the cap. It refuses any database not named `atelier_walk_*`. Extra routes: `POST /__walk/prefetch {email}` (the night run for one learner), `GET /__walk/spend`, `POST /__walk/jump {email, day}`, `POST /__walk/writer {model}`, `GET /__walk/live?email=`.
- `web-frontend/e2e/explore.mjs` — a phone-sized browser driven over a small local HTTP API (`snap`, `click`, `type`, `key`, `goto`, `scroll`, `shot`, `wait`, `clock`, `learner`, `resume`, `walk`, `tap`, `drag`, `hold`, `offline`, `slow`, `note`, `stop`).
- `web-frontend/e2e/lib/stack.mjs` — honours `WALK_API_SERVER` (which server script to start), `WALK_REUSE_DB` (restart on an existing walk database) and `WALK_KEEP_DB` (do not drop it on stop).
- `p` in this folder — a shell helper that prints a compact view of a screen: `./p PORT snap`, `./p PORT click '{"text":"…"}'`.
- `BRIEF.md` — how a player plays and records. `PACKAGE-RULES.md`, `CI-RULES.md`, `ROUND2.md`, `ROUND3.md` — the rules the implementing agents were given.

The files above were written on a Mac; they contain absolute paths under a scratch folder. Wherever a brief names `…/scratchpad/BRIEF.md`, `…/scratchpad/p` and so on, use the copy in this folder; play logs and screenshots go wherever the session can write.

## Start a stack

Needs PostgreSQL reachable at `postgresql://localhost/postgres` (or `WALK_PG_ADMIN_URL`), Playwright's Chromium, the repo's Python environment, and `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`. On the Mac the server reads the two keys from the shared checkout's `.env`; elsewhere export them in the environment before starting (the server only overwrites them when that `.env` has them).

```bash
cd web-frontend
SECRET_KEY=review-walk-secret-not-for-production \
WALK_API_SERVER=scripts/review_walk_server.py \
SEASON_END_MODE=live SEASON_END_MAX_USD=2.0 SEASON_END_OUT=/tmp/walk/a1-server \
WALK_KEEP_DB=1 WALK_PYTHON=$(which python) \
npm run explore -- --native de --level A1.1 --out /tmp/walk/a1 --port 7791
```

`SEASON_END_MODE=fake` runs the same stack on the fake provider at no cost.

## Rules that cost money when broken

- The story writer only writes in the night run. To play the next day: finish the day, `clock {"days": N}`, then `walk {"path":"/__walk/prefetch","body":{"email":…}}` **once**. If the call times out, do not call again: poll `/__walk/spend` until `calls` stops rising, then call once more (it answers «cached»).
- A day's cost on Sonnet 5.5 is about US$0.25–0.45, nearly all of it the night run.
- Each night run logs one line `journey_latency: night_run {json}` and each accepted page one `hook_observation {json}` in the stack's `logs/api.log`.
