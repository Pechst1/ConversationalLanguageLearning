# iPhone daily testing → pilot: the runbook

**Goal:** the app on your iPhone for daily use now, and a clean path to a
TestFlight pilot. Architecture (decided in `docs/ios-app-implementation-plan.md`):
the Capacitor iOS shell bundles the static web build; only the **API** lives on
a server. Auth is JWT-in-Keychain (entitlement already configured), so no
NextAuth/Node server is needed on the phone path.

Everything below is prepared in the repo. The only steps that need **you** are
the ones marked 🧍 (accounts, secrets, Xcode signing).

---

## Phase 1 — Host the backend (once, ~30 min)

Two prepared options. **A is recommended** for speed: no VPS, no domain, HTTPS
included.

### Option A — Render (recommended; `render.yaml` is in the repo root)

1. 🧍 Push the current branch to GitHub (or merge to main).
2. 🧍 Create a Render account (render.com) → **New → Blueprint** → pick the
   `ConversationalLanguageLearning` repo. Render reads `render.yaml` and
   provisions: API (with datastore readiness checks + migrations on boot), Celery
   worker (with beat), Postgres, Redis. The API also installs the curated grammar
   catalog, approved exercise blueprints, and starter vocabulary idempotently;
   a fresh database therefore has usable learning content before the first login.
3. 🧍 When prompted, fill the dashboard values (`sync: false` in the
   blueprint). The API refuses to start in production without the starred ones:
   - `OPENAI_API_KEY`\* — copy it from your local `.env`.
   - `SMTP_HOST`\*, `SMTP_FROM_EMAIL`\*, `SMTP_USERNAME`, `SMTP_PASSWORD` — any
     relay (Resend, Mailgun, your mailbox's SMTP); password reset emails a code.
   - `ATELIER_DAILY_JOURNEY_COHORT`\* — your own email first (who gets the
     daily journey; `*` everyone, `none` nobody on purpose).
   - `REGISTRATION_ALLOWED_EMAILS` — your own email, plus the study accounts
     later. Sign-up is closed (`REGISTRATION_OPEN=false`), so an address not
     listed here cannot create an account; the cohort is not an invite gate.
   - Optional: `SENTRY_DSN`, the `APNS_*` key, the `GRAPHIC_NOVEL_IMAGE_*`
     S3 storage (needed before panel art can draw).
   The worker inherits the secrets from the API service, so each is entered
   only once. Anthropic remains optional.
4. Note the API URL it assigns, e.g. `https://atelier-api.onrender.com`.
   Check `https://<that-url>/health` returns `{"status":"ok"}` and
   `https://<that-url>/ready` returns `{"status":"ready"}`.
5. The blueprint keeps all services in Frankfurt and starts generated panel
   images off; deterministic panels are used during the first test so image
   costs and database growth stay bounded. Configure durable S3-compatible
   image storage before enabling `GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED`.
   Check Render's current price summary before confirming. The blueprint runs
   `APP_ENV=production` from the first deploy, so the production guards are on
   and SMTP is required (step 3). Password reset emails a six-digit code typed
   in the app; `PASSWORD_RESET_BASE_URL` stays unset until a public web reset
   page exists (the API hostname does not serve one), and then adds a link.

### Option B — any VPS with Docker (Hetzner/DigitalOcean, ~$6/mo + domain)

1. 🧍 Create the VPS, point a domain/subdomain at it (HTTPS is mandatory —
   the native build refuses plain HTTP), install Docker + a TLS proxy
   (Caddy is the least work: two lines of Caddyfile reverse-proxying :8000).
2. On the server:
   ```bash
   git clone https://github.com/Pechst1/ConversationalLanguageLearning.git && cd ConversationalLanguageLearning
   cp .env.prod.example .env.prod   # 🧍 fill every <...> (secrets, keys)
   export APP_IMAGE=ghcr.io/pechst1/conversational-language-learning:sha-<tested-commit>
   bash scripts/production_compose.sh pull    # the tested image from GHCR
   bash scripts/production_compose.sh up -d   # api, worker(+beat), db, redis
   ```
   `.env.prod.example` carries the same values as `render.yaml`; the API
   listens on `127.0.0.1:8000` only, behind the TLS proxy. The GHCR image is
   published by CI's publish job (`.github/workflows/publish-image.yml`) after
   every check passed on a push to main, tagged `sha-<full commit>`; the wrapper
   refuses `latest` (first run: 🧍 make sure the repo's package visibility
   allows your server to pull, or `docker login ghcr.io` with a token).

### Seed your account and data (either option)

From your Mac, against the hosted API:
```bash
# create your user (signup endpoint), then import your Anki deck:
python scripts/import_anki_csv.py --user-email <you> --csv Anki_cards___2025-11-01T13-09-36.csv \
  # (run with DATABASE_URL pointed at the hosted Postgres, or use the API import endpoint)
```
Sign-up is closed to everyone not in `REGISTRATION_ALLOWED_EMAILS`, so put
your email there first. Simplest: sign up in the app once it's on your phone,
then run the Anki import
with `DATABASE_URL` set to the hosted database's external connection string.

For the pilot owner account, set `users.role = 'admin'` once in the hosted
database (Render Postgres console or `psql`). After the next sign-in, Settings
shows **Pilot cost & quality**, the admin-only dashboard for weekly per-learner
generation spend, guardrail breaches, reports, and automatically retired
exercise sets. Keep tester accounts on the default `user` role.

---

## Phase 2 — The app on your iPhone (same day)

1. Install and sync native push support (once):
   ```bash
   cd web-frontend
   npm install @capacitor/push-notifications@8.1.2
   ```
   The registration bridge, tap routing, `AppDelegate` callbacks, and
   `aps-environment` entitlement are already in the repo. The package install
   is intentionally explicit because it updates both `package-lock.json` and
   the generated Swift package references.
2. Bake the hosted API into the native bundle and sync the Xcode project
   (from `web-frontend/`):
   ```bash
   NEXT_PUBLIC_API_BASE_URL=https://<your-api-host>/api/v1 \
   NEXT_PUBLIC_APNS_ENVIRONMENT=sandbox \
   npm run cap:sync:ios
   ```
   (The build **fails on purpose** if the URL is http:// or localhost. It also
   derives the matching secure WebSocket URL, so a local developer setting
   cannot leak into the iPhone bundle. Placeholder `example.com` hosts are also
   rejected, and the Xcode target refuses to install a previously synced
   rehearsal bundle.)
3. 🧍 Open Xcode: `npm run cap:open:ios`
   - Signing & Capabilities → Team: your Apple ID (a free account works).
   - Add the **Push Notifications** capability. In the Apple Developer portal,
     create an APNs authentication key (`.p8`) and put its team ID, key ID, and
     full key into the backend `APNS_*` environment variables. The blueprint
     defaults to production APNs (`APNS_USE_SANDBOX=false`, what TestFlight
     needs); for this direct Xcode build set it to `true` on both the API and
     the worker, and back to `false` before TestFlight.
   - Plug in your iPhone (or use WiFi pairing), select it as the run target, ▶ Run.
   - First run on device: on the phone, Settings → General → VPN & Device
     Management → trust your developer certificate.
4. Daily use notes:
   - With a **free** Apple ID the install expires after 7 days — re-run from
     Xcode weekly. With the paid Apple Developer Program ($99/yr) it lasts a
     year, and TestFlight becomes available.
   - The keychain entitlement is already configured
     (`web-frontend/ios/App/App/App.entitlements`), so your sign-in survives
     cold starts.
   - When you pull new frontend code: re-run step 1, then Xcode ▶ Run again.
     Backend changes deploy independently (Render: auto-deploys on push;
     VPS: `docker compose ... pull && up -d`).

---

## Phase 3 — Pilot via TestFlight (when ready)

1. 🧍 Apple Developer Program enrollment ($99/yr) — takes ~1–2 days.
2. 🧍 App Store Connect: create the app record for `com.pixellab.feuilleton`.
3. In Xcode: Product → Archive → Distribute → TestFlight (internal testers
   first — up to 100, instant; external testers need a light Beta review).
   Rebuild with `NEXT_PUBLIC_NATIVE_PUSH_ENABLED=true` and
   `NEXT_PUBLIC_APNS_ENVIRONMENT=production`, and confirm the API and
   worker have `APNS_USE_SANDBOX=false` (the blueprint default); TestFlight
   device tokens use production APNs.
4. Before inviting testers, add their emails to `REGISTRATION_ALLOWED_EMAILS`
   (sign-up) and `ATELIER_DAILY_JOURNEY_COHORT` (the journey), confirm the
   backend runs `APP_ENV=production` (SMTP configured,
   `AUTO_CREATE_USERS_ON_LOGIN=false` — the API enforces both at boot) and re-check `docs/audit-2026-07-18-status-and-work-packages.md`
   for open pilot-blocking items. Open **Settings → Pilot cost & quality** and
   confirm no weekly learner row exceeds
   `PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD` and no reported exercise set
   remains active past the daily quality sweep.
5. Archive automation is ready in `web-frontend/fastlane/Fastfile`; follow
   `docs/testflight-production-flip-checklist.md` for the local archive and internal
   TestFlight upload lanes.

---

## What's already verified in the repo

- `docker/docker-compose.prod.yml`: API (`/ready` checks, migrations on boot)
  + **Celery worker with beat** (was missing — without it
  feuilleton episodes and nightly jobs never generate) + Postgres + Redis,
  all with healthchecks and restart policies. Staging compose got the worker
  too. Fresh databases receive the grammar/blueprint/starter-vocabulary
  reference data automatically. `/health` and datastore-aware `/ready`
  endpoints are available.
- `.env.prod.example` — hardened template; `.env.prod`/`.env.staging` are now
  git-ignored so secrets can't be committed.
- `.github/workflows/publish-image.yml` — builds/pushes the GHCR image the
  compose files pull (previously nothing published it).
- `render.yaml` — one-click full-stack blueprint.
- Native chain (`npm run cap:sync:ios`: guarded static export → Capacitor
  sync) — run green locally; see `docs/ios-app-implementation-plan.md` for the
  remaining device-validation caveats (WebSockets, full episode scroll on
  device).

## Your action list (in order)

1. Render account + blueprint deploy + the dashboard values of Phase 1 step 3
   (OpenAI key, SMTP, cohort, registration allowlist; ~20 min) — or the VPS
   path if you prefer owning the box.
2. `NEXT_PUBLIC_API_BASE_URL=https://… npm run cap:sync:ios` then Xcode ▶ onto
   your iPhone (~15 min).
3. Sign up in the app, import your Anki deck, start the daily loop.
4. When pilot-ready: Apple Developer enrollment → TestFlight; add the testers
   to the registration allowlist and the cohort.
