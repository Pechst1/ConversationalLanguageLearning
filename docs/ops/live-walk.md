# The live walk

The explore walk (`npm run explore`) plays a throwaway local stack with the fake story
provider, so it cannot judge what learners really get from the model. The live walk plays
the same app against the production API, with a dedicated test account, from a machine
that can reach Render (the owner's Mac; cloud sessions cannot).

```
 browser (375×812, Capacitor platform = ios)
   │  same origin
   ▼
 e2e/lib/live-proxy.mjs  ── static native bundle (out/)
   │  /api/*  (Origin dropped)
   ▼
 https://atelier-api-3njh.onrender.com
```

- Production allows only the app's own origin (`capacitor://localhost`) for CORS. The proxy
  keeps every request same-origin, so no production setting changes.
- The page runs with `window.CapacitorCustomPlatform = { name: 'ios' }`: sign-in uses the
  phone's token flow and plugins fall back to their web implementations (secure storage →
  localStorage). Without it the bundle tries next-auth, which needs a Next server.
- It signs in through the sign-in screen with `ATELIER_WALK_EMAIL` / `ATELIER_WALK_PASSWORD`.
  On the Mac the password lives in the login keychain under `atelier-walk`, never in the
  repository.

```
cd web-frontend
ATELIER_WALK_EMAIL=… ATELIER_WALK_PASSWORD="$(security find-generic-password -s atelier-walk -w)" \
  npm run explore:live -- [--skip-build] [--out DIR]
```

The control API on `127.0.0.1:7778` is the explore walk's (`snap`, `click`, `type`, `key`,
`goto`, `scroll`, `wait`, `note`, `stop`), without `clock` and `learner`: the server's day is
the real day, and the learner is the test account, so the walk moves one real day per night.
Score each walk with `docs/ops/walk-rubric.md`; Q19 (keyboard, safe area, audio, login after
restart) needs the iOS Simulator and is checked separately.

Every answer is written to the production database and every model call is paid: use the
test account only, and keep it on the registration allowlist.
