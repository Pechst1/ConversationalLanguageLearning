# iOS App — Implementation Plan

**Status:** Decision + roadmap · **Audience:** owner + implementing agent · **Date:** 2026-06-12

## The decision that governs everything: how do we get to iOS?

The product is a phone-first Next.js web app (`web-frontend/`, ~38.7k lines of TSX). It is already designed for 319–390px viewports, signed-in mobile smoke-tested, and changing **weekly** (F-series Feuilleton fixes, X/Y product packages all in flight). The FastAPI backend already issues JWT **access + refresh tokens** (`/api/v1/auth/login|refresh|logout`) — so it is already native-client-ready; NextAuth is only a web wrapper around those same endpoints.

Three architectures, with the trade that matters:

| Option | What it is | Time to TestFlight | Keeps the 38.7k-line frontend? | Risk |
|---|---|---|---|---|
| **A. Full React Native rewrite** | Rebuild every screen in RN/Expo (the `mobile/` scaffold's direction) | 6–12 months | **No** — rebuild Atelier, Feuilleton comic renderer, Missions, Notebook from scratch | Freezes product development for months; the bespoke editorial/comic UI is the hardest possible thing to port; throws away the current investment while it's still changing |
| **B. Capacitor WebView shell + native plugins** ✅ **recommended** | Wrap the existing Next.js build in a native iOS container; add native plugins only for device capabilities (push, audio, secure storage, IAP, haptics) | 2–4 weeks to TestFlight | **Yes — 100%** | WebView "feel"; Apple §4.2 "minimum functionality" scrutiny (mitigated by real native push/audio/IAP); WKWebView audio/push quirks |
| **C. Capacitor now → selectively go native later** | Ship B, then replace only the highest-value screens with native over time | Same 2–4 weeks, then incremental | Yes, then partial | Mixing WebView + RN in one binary is painful; only pursue if a specific screen proves it needs native |

**Recommendation: B (Capacitor), with the discipline of C as a later option.** Rationale: the entire product thesis (the serial, the Feuilleton comic, the editorial day-loop) lives in that bespoke web UI; a rewrite would stop product progress cold for half a year to reproduce what already works. Capacitor ships the *same* codebase to the App Store in weeks, keeps web and iOS automatically in sync, and lets us add the genuinely-native pieces (push for the "tomorrow's edition" retention loop, mic for voice missions, audio for TTS, IAP for subscriptions) as real plugins so the app clears Apple's minimum-functionality bar. If, post-launch, a specific surface (e.g. the comic reader) demonstrably needs native, replace *that one* screen — don't pre-pay for a full rewrite.

> If the owner wants a native *feel* as a hard requirement from day one, that's the one input that would flip this to A — and it should be made consciously, because it is a 6-month decision. Everything below assumes B.

**Housekeeping:** the existing `mobile/` Expo app is a broken skeleton (duplicate imports, undefined `LearnScreen`, only Reviews+Profile, an Anki-only API client). Under Plan B it is not a foundation. **Delete it** (salvage only the `eas.json`/bundle-id knowledge) to avoid two competing "mobile" directories. Keep this decision reversible by not deleting until P0 proves out.

---

# Phase 0 — Foundation: make the web app shippable as a native binary

## WP-M1 — Capacitor shell + iOS project (blocking; ship first)
1. Add Capacitor to `web-frontend/` (`@capacitor/core`, `@capacitor/cli`, `@capacitor/ios`). Create `capacitor.config.ts` (appId e.g. `com.<org>.feuilleton`, appName, `webDir`).
2. **Decide load mode** (see WP-M2): bundled static assets (preferred) vs. `server.url` remote load. Default plan: bundled.
3. `npx cap add ios`; commit the generated `web-frontend/ios/` Xcode project. Open in Xcode, run on simulator + a real device, confirm the app boots to `/atelier` signed-out → sign-in.
4. CI/build: document the `next build` → asset-sync → `cap sync ios` flow in a `web-frontend/README` section and a `scripts/` helper.
**Acceptance:** the current app runs in the iOS simulator and on a physical device, no white screen, navigation works.

## WP-M1 Spike Findings — 2026-06-13

**Implementation:** Added Capacitor 8 to `web-frontend/` with `@capacitor/core`, `@capacitor/cli`, and `@capacitor/ios`; generated and committed the `web-frontend/ios/` Xcode project. The spike uses Capacitor `server.url` pointed at the running Next app (`CAPACITOR_SERVER_URL`, default `http://127.0.0.1:3000`) and keeps static export/auth bridge work out of scope for Phase 1.

**Build result:** `npx cap add ios` and `npx cap sync ios` succeeded. `xcodebuild -project ios/App/App.xcodeproj -scheme App -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.2' -derivedDataPath /private/tmp/capacitor-ios-derived CODE_SIGNING_ALLOWED=NO build` succeeded.

**Boot result:** Initial `http://localhost:3000` simulator launch showed a white screen. Switching the default to `http://127.0.0.1:3000` reached Next, but the already-running port-3000 server returned `500 Internal Server Error` for full GETs to `/` and `/atelier`. A fresh Next dev server on `http://127.0.0.1:3001` returned `200 OK`; syncing with `CAPACITOR_SERVER_URL=http://127.0.0.1:3001` rendered the signed-out Atelier/Learning hub in the iPhone 16 simulator with no white screen.

**NextAuth session:** Not proven. In this server-url spike the origin is the configured HTTP URL, not `capacitor://localhost`; the signed-out shell rendered, but the sign-in flow was not completed in simulator. During the port-3001 retest, the dev server logged a NextAuth client fetch error because the local `NEXTAUTH_URL` still pointed at `http://localhost:3000/api/auth/session`, so any non-default spike URL must keep `NEXTAUTH_URL` aligned or the session endpoint will be wrong.

**WebSocket session:** Not proven. Requires signed-in traversal after the auth path is validated.

**Six-panel episode + memory:** Not proven end-to-end in simulator. The image URL migration was implemented in this same Phase-1 pass so new locally stored panels can use served URLs instead of base64 data URIs, but a full signed-in six-panel episode scroll still needs device validation.

**Physical device:** Not tested in this environment. A physical iPhone needs a LAN-reachable or hosted HTTPS `CAPACITOR_SERVER_URL`; device `localhost` will not point at the Mac.

**Recommendation:** **GO-WITH-CAVEATS** for Phase 2. The Capacitor native shell builds and can render the existing web UI in iOS Simulator when pointed at a healthy Next server, so the approach remains viable. Phase 2 must still do the real work: static/API decoupling (WP-M2), native JWT auth bridge (WP-M3), an explicit initial route strategy, and signed-in simulator/physical-device validation for NextAuth-equivalent session behavior, WebSockets, and full Feuilleton episode scrolling.

## WP-M2 — Build-output + API strategy (blocking; the trickiest backend-coupling fix)
The app has SSR-ish coupling that WebView packaging must resolve: `pages/api/*` (NextAuth route, `pages/api/proxy/stories`, `pages/api/anki`) and `next.config.js` `rewrites`/`redirects` assume a Node server.
1. Audit every `pages/api/*` route and `next.config.js` rewrite. For each, either (a) move the logic client-side to call the FastAPI backend directly, or (b) keep it only for the web deployment and stop depending on it in the native build.
2. Target **`next build` + static export** for the native bundle (`output: 'export'` or per-page static) so Capacitor ships offline-capable assets. Where a page can't be static, fall back to Capacitor `server.url` pointing at the hosted Next deployment **only** for that path (last resort — it breaks offline and invites §4.2 scrutiny).
3. Point all data calls at the hosted FastAPI base URL via a single config (`NEXT_PUBLIC_API_BASE_URL`); kill the `pages/api/proxy/*` indirection in the native path.
**Acceptance:** native build loads with zero calls to a Next.js Node server; all data flows go straight to FastAPI.

## WP-M3 — Auth bridge: NextAuth → direct JWT in the native shell (blocking)
NextAuth (cookies, server session) is awkward at the `capacitor://localhost` origin. The backend already exposes `/auth/login`, `/auth/refresh`, `/auth/logout` with access+refresh JWTs.
1. In the native build, replace NextAuth session usage with a direct JWT client: login posts to `/auth/login`, stores tokens in **`@capacitor/preferences` + Keychain via a secure-storage plugin** (not `localStorage`), attaches `Authorization: Bearer` to API + WS calls, and auto-refreshes on 401 using the rotating refresh-token endpoint.
2. Abstract the auth layer so web keeps NextAuth and native uses the JWT client behind one interface (`lib/auth.ts` already exists as the seam; `services/websocket.ts` currently pulls the token from `useSession` — give it a token provider).
3. Handle token expiry, logout, and the "session restored on cold start" path (the `mobile/` scaffold's `loadTokens` hydration pattern is the right idea — reuse the concept).
**Acceptance:** sign in on device, kill+reopen the app stays signed in, a 401 transparently refreshes, logout clears Keychain.

## WP-M4 — Safe areas, status bar, gestures, offline (foundation polish)
1. `@capacitor/status-bar`, `@capacitor/splash-screen`, `@capacitor/keyboard`; respect notch/home-indicator safe areas across the editorial layouts (the masthead + sticky CTAs + bottom nav need `env(safe-area-inset-*)` audits).
2. iOS back-swipe / scroll-bounce behavior; disable rubber-banding where it breaks the fixed mastheads.
3. Offline + error states: a native-aware offline banner (the web app already has an offline panel concept); cache the last `/atelier/today` for a graceful cold-open offline.
**Acceptance:** no content under the notch or home indicator on iPhone 13/15; keyboard doesn't cover mission/feuilleton inputs; airplane-mode shows a clean offline state, not a white screen.

---

# Phase 1 — The native capabilities that justify an app (and clear App Review §4.2)

## WP-M5 — Push notifications: wire the retention loop (high value; pairs with WP-X2)
The serial's "tomorrow's edition is out" pull dies on web when the tab closes — push is the fix and the single biggest reason this should be an app.
1. `@capacitor/push-notifications` + APNs setup (Apple Developer push key, entitlement). On grant, register the device token to the existing `push_subscription` model/endpoints (already in the backend; currently web-push-shaped — add an APNs token type).
2. Backend: when a background-generated episode flips to `available` (WP-X2's hook), send an APNs notification with in-fiction copy ("Épisode 5 est paru — Romy n'a pas fini sa phrase."). Respect quiet hours + the `serial_edition_notifications` preference.
3. Deep-link the tap straight into the new episode (`/graphic-novel?...` or `/missions?...`).
**Acceptance:** completing a beat on device with push enabled delivers one notification; tapping it opens the episode; idempotent (re-render doesn't re-notify).

## WP-M6 — Microphone & audio: voice missions + TTS playback (high value; pairs with WP-X3/Y1)
Web `MediaRecorder`/`getUserMedia` (used in `VoiceInput`, missions, `audio-session`) is unreliable in WKWebView; TTS playback (WP-X3) and voicemail missions (WP-Y1) are core.
1. Mic capture via `@capacitor/microphone` (or a community recorder plugin) feeding the same transcription→correction backend path the web `VoiceInput` uses; `NSMicrophoneUsageDescription` in Info.plist.
2. Audio playback for Feuilleton TTS + voiced NPC replies via a native audio plugin (background-audio-safe, respects the silent switch appropriately for speech).
3. Bridge so the existing React audio components call native capture/playback in the native build, web APIs on web (one `useAudio` seam).
**Acceptance:** record a voicemail-reply mission on device → transcript → graded; play a Feuilleton panel's audio; both work where the web WebView APIs fail.

## WP-M7 — In-App Purchase / subscriptions (required before monetizing on iOS)
Apple requires IAP for digital subscriptions; this gates revenue and shapes the paywall.
1. Integrate StoreKit via a plugin (RevenueCat strongly recommended for receipt validation, entitlements, and cross-platform later). Define the subscription product(s) matching the "20 min/day → A-level" promise (e.g. monthly/annual).
2. Backend: entitlement sync endpoint; gate premium features (unlimited missions? Bibliothèque? extra episodes?) behind server-checked entitlement, not client trust.
3. Paywall screen consistent with the editorial style; restore-purchases; sandbox testing.
**Acceptance:** sandbox purchase unlocks the entitlement server-side; restore works; no non-IAP payment path on iOS.

## WP-M8 — Native niceties (polish that earns the "app" label)
Haptics on key moments (mission graded, episode filed, streak), `@capacitor/share` for sharing an episode, app icon + launch screen in the editorial brand, optional home-screen quick actions ("Today's edition"). App Badge for unread editions.
**Acceptance:** haptic on submit/file; branded icon + splash; share sheet from a finished episode.

---

# Phase 2 — App Store readiness & launch

## WP-M9 — Compliance & metadata
1. Privacy: `PrivacyInfo.xcprivacy` manifest (data types collected — account, audio, usage), App Privacy "nutrition label", and a privacy policy URL. Account deletion path (App Store requires it for accounts) — confirm the backend has user-deletion and surface it in Settings.
2. Permissions usage strings (mic, notifications, tracking if any). Sign-in with Apple is **required** if any third-party social login is offered (currently credentials-only, so likely exempt — verify before adding any social provider).
3. §4.2 minimum-functionality: the native push + mic + audio + IAP above are the evidence the app isn't "just a website."
**Acceptance:** clean privacy manifest; account deletion reachable in-app; no missing-usage-string rejections.

## WP-M10 — Build, sign, ship
1. Apple Developer account, App ID, certificates/profiles; choose Xcode Cloud, EAS Build, or Fastlane for CI (Fastlane + GitHub Actions is the pragmatic default). Automate `next build → cap sync → archive → TestFlight`.
2. TestFlight internal → external beta; crash reporting (Sentry) + analytics wired to the same backend events.
3. App Store listing (screenshots of the Feuilleton — they sell themselves), phased release.
**Acceptance:** a tagged commit produces a TestFlight build via CI; external testers install and run the full day-loop on device.

## WP-M11 — Performance pass on device
The three giant screens (Atelier 5.2k, Feuilleton 4.9k, Missions 4.6k lines) plus base64-inlined panel images (~1MB each, six per episode — seen in the DB) will stress a WebView.
1. Serve panel images as URLs (object storage), not base64 data-URIs, to cut WebView memory + DOM weight (also helps web).
2. Bundle-size + first-paint audit; lazy-load the comic renderer; virtualize long lists (vocabulary 2.4k-line page).
3. Memory profile a full Feuilleton on an older device (iPhone 11-class).
**Acceptance:** a 6-panel episode loads < 3s on device and doesn't crash on memory; smooth 60fps scroll on the day-loop.

---

# Sequencing & ownership

| Phase | Packages | Notes |
|---|---|---|
| 0 (blocking) | M1 → M2 → M3 → M4 | Get the existing app running natively + signed-in. M2/M3 are the real work (build output + auth bridge). |
| 1 (capabilities) | M5, M6, M7 (parallel) ; M8 polish | These justify the app and clear §4.2. M5 pairs with WP-X2, M6 with WP-X3/Y1 — coordinate so backend is built once. |
| 2 (launch) | M9 → M10 ; M11 throughout | Compliance, CI/TestFlight, on-device performance. |

**Hard dependencies:** M1 before all; M2+M3 before any data-driven screen works natively; M5 needs WP-X2's "episode available" backend hook; M6 needs WP-X3's audio assets. **Image-URL migration (M11.1) should be pulled early** — it helps both web and native and unblocks WebView memory.

**Cross-plan coordination:** build the push hook (M5) and audio pipeline (M6) *with* their web counterparts (X2/X3/Y1), not twice. The native layer consumes the same backend.

# Definition of done (iOS v1)
1. The existing web app runs as a signed iOS binary from CI to TestFlight, no Node server dependency in the bundle.
2. Sign-in uses backend JWT in Keychain; sessions survive cold start; 401 auto-refreshes.
3. Push delivers "new edition" and deep-links into it; mic-based voice missions and TTS playback work on device where WebView APIs don't.
4. IAP subscription gates premium server-side; restore works; account deletion in-app.
5. Privacy manifest + labels complete; passes App Review.
6. A 6-panel Feuilleton loads fast and stably on an iPhone 11-class device (images as URLs, not base64).
7. Android is a near-free follow-on (Capacitor `cap add android`) — note but out of scope for v1.
