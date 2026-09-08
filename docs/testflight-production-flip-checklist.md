# TestFlight and production flip checklist

The Apple enrollment and App Store Connect app record remain owner actions. Everything
below is the repeatable release contract for `com.pixellab.feuilleton`.

## 1. Backend production gate

- Set `APP_ENV=production`.
- Set a unique production `SECRET_KEY`.
- Keep `AUTO_CREATE_USERS_ON_LOGIN=false`.
- Keep `PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE=false`.
- Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, credentials, and TLS.
- Point `PASSWORD_RESET_BASE_URL` at the publicly reachable reset page and complete
  one end-to-end reset from the emailed link.
- Set the final `BACKEND_CORS_ORIGINS`, including `capacitor://localhost`.
- Run migrations and confirm `/health` and datastore-aware `/ready` both return 200.
- Run `python scripts/pilot_digest.py --day YYYY-MM-DD` and inspect failures/cost.

The API startup guard refuses production if auto-created users, reset-token echoing,
or required SMTP settings remain unsafe.

## 2. Production native build

```sh
cd web-frontend
NEXT_PUBLIC_API_BASE_URL=https://<api-host>/api/v1 \
NEXT_PUBLIC_NATIVE_PUSH_ENABLED=true \
NEXT_PUBLIC_APNS_ENVIRONMENT=production \
npm run cap:sync:ios
```

- Set the Xcode signing team and verify the bundle ID is
  `com.pixellab.feuilleton`.
- Confirm Push Notifications capability and the `aps-environment` entitlement.
- Set backend `APNS_USE_SANDBOX=false` for TestFlight tokens.
- Sign in, complete one session, grant the staged notification prompt, and confirm
  the token appears in `push_subscriptions`.
- Force one first-party client error in a private build and confirm it appears as a
  `client_crash` in the pilot daily ledger.

## 3. Archive automation

Install Fastlane once:

```sh
cd web-frontend
bundle install
```

Archive locally:

```sh
bundle exec fastlane ios archive
```

Upload an internal TestFlight build with an App Store Connect API key:

```sh
export APP_STORE_CONNECT_KEY_ID=...
export APP_STORE_CONNECT_ISSUER_ID=...
export APP_STORE_CONNECT_KEY_CONTENT=<base64-p8-content>
export APPLE_TEAM_ID=...
bundle exec fastlane ios beta
```

`CI_BUILD_NUMBER` can override the generated UTC build number. Archives are written
to `web-frontend/build/testflight`.

## 4. Pilot smoke test

- Fresh install → sign in → La Une renders without a development bypass.
- Kill/reopen during Épreuve, mission composition, review, and Feuilleton reading;
  each resumes at the exact activity.
- Airplane-mode cold start shows the cached edition with its revalidation note.
- Complete Studio call with a cast member; verify the canonical serial relationship
  ledger contains the callback.
- Confirm light and dark themes for La Une, Studio, correction states, Cahiers,
  Feuilleton, and L’administration.
- Confirm morning notification copy reflects the real prescription and its tap opens
  `/atelier`.
- Export account data, reset a password from email, and close all sessions.

## 5. Dependency advisory gate

`npm audit --omit=dev` on 2026-07-23 reports six advisory groups. The Capacitor
pilot consumes the static export and does not expose a Next.js server, so the
server-only Next advisories do not block the iPhone test. Do not publish the
Next.js web server publicly until the planned Next 16 migration is complete.

The remaining non-major `tar`, `brace-expansion`, and `next-auth`/`uuid`
remediations should be applied with `npm audit fix --omit=dev`, then followed by
type-check, lint, production build, native sync, and this smoke test. Codex's
approval reviewer rejected that package mutation in the current session, so it
is recorded here rather than silently treated as fixed.
