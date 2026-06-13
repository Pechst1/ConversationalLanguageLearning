# Master Roadmap — product + iOS, one sequence

**Status:** Active sequencing plan · **Audience:** owner + implementing agents · **Date:** 2026-06-12

This is the single ordering across all in-flight workstreams. The per-area specs hold the detailed work packages; this doc decides **what gets built when, and where the streams must share a backend.** When the two conflict, this doc wins on ordering and the spec wins on implementation detail.

**Source specs:**
- `docs/serial-season-engine-and-production-plan.md` — Feuilleton craft fixes (WP-F1..F6), UX packages (WP-X1..X7), product packages (WP-Y1..Y4).
- `docs/ios-app-implementation-plan.md` — iOS conversion via Capacitor (WP-M1..M11).

## The four workstreams (lanes)
- **Daily experience (F-series):** fix what every learner sees every session — the Feuilleton read.
- **Product bets (X/Y):** the engagement loop and the positioning claim ("20 min/day → A-level").
- **iOS platform (M-series):** ship the existing web app as a native iOS binary via Capacitor.
- **Backend / shared:** the data + generation work the other three lanes consume.

## Three rules that govern the order
1. **Never build a backend twice.** The native capabilities share their backend with product features (push ↔ serial notifications; audio ↔ TTS ↔ voicemail missions). Build the backend once; the web feature and the native plugin both consume it. These are the dashed links in Phase 3.
2. **Pull the image-URL migration early.** It improves the web app immediately *and* removes the single biggest WebView memory risk before anything is built on top of it. It lives in Phase 1 even though it reads like "launch perf."
3. **F-series outranks almost everything.** It's cheap, it's the daily experience, and a polished core loop is what makes the Phase-4 paywall defensible. The only Phase-1 product item that competes is X1 (making the serial discoverable at all).

---

# Phase 1 — Fix the daily read · de-risk iOS

**Goal:** the core Feuilleton loop stops looking like a templated prototype, and the Capacitor approach is proven on a device before any platform commitment.

| Lane | Packages |
|---|---|
| Daily experience | **F1** story-true tasks + dialogue (root fix) → **F4** declutter the page · **F2** speech bubbles on art · **F6** image-craft guardrails (parallel) |
| Product bets | **X1** serial discoverability |
| iOS platform | **M1** Capacitor spike — boot the existing app in the iOS simulator + on a physical device |
| Backend / shared | panel images → object-storage URLs (replaces base64 data-URIs; helps web now, unblocks WebView memory; = WP-M11.1) |

**Why first:** F1 is the root cause of the screenshot problems (tasks/dialogue are still episode-1 template furniture); F2/F4/F6 ride on or beside it. M1 is a few days and tells us if Capacitor is viable before Phase 2's real work. The image migration is the cheapest high-value backend change available.

**Exit criteria:** an episode ≥2 renders story-true tasks + on-art bubbles, decluttered; the unchanged web app runs on a real iPhone; panel images load from URLs.

# Phase 2 — The promise · the native shell

**Goal:** ship the positioning claim (a credible CEFR path) and do the real iOS engineering (decoupling + auth).

| Lane | Packages |
|---|---|
| Daily experience | **F5** inline anchored tasks (revises the read-first default) · **F3** avatar builder (long-lead image track) |
| Product bets | **Y2** CEFR meter + forecast — the differentiator |
| iOS platform | **M2** decouple from the Next.js Node server (static build + direct FastAPI calls) → **M3** NextAuth → JWT-in-Keychain auth bridge → **M4** safe areas, keyboard, offline |
| Backend / shared | CEFR threshold + forecast engine (feeds Y2) |

**Why here:** Y2 is platform-independent and is the product's actual reason-to-pay; build it while the iOS team does M2/M3 — the two packages where the surprises hide, so they get a dedicated phase rather than being rushed. F3 (avatar) starts now because the image pipeline is long-lead.

**Exit criteria:** the level meter + honest forecast render on Atelier/Notebook; the app runs natively with no Node-server dependency, signed-in via Keychain JWT surviving cold start.

# Phase 3 — The retention loop (build once, web + native)

**Goal:** the loop that makes the app worth installing — and the evidence it's "not just a website" for App Review §4.2.

| Lane | Packages |
|---|---|
| Product bets | **X2** new-edition notifications · **Y3** the 20-minute edition · **X3** Feuilleton TTS · **Y1** voicemail/email mission formats |
| iOS platform | **M5** APNs push · **M6** native mic + audio playback |
| Backend / shared | **(shared)** "episode available" notification hook → feeds X2 + M5 · audio/TTS pipeline → feeds X3 + Y1 + M6 |

**The pairings (rule 1 in action):**
- **X2 ↔ M5** are the same backend event (the serial flips an episode to `available`). Build the hook once; web fires a web/push notification, native fires APNs. Deep-link the tap into the episode.
- **X3 ↔ Y1 ↔ M6** share one audio pipeline (character voice map → TTS). The Feuilleton playback, the voicemail mission, and the native audio plugin all consume it.

**Exit criteria:** completing a beat delivers a "new edition" notification that deep-links in; a voicemail mission round-trips voice → transcription → grading on device; Feuilleton panels play audio; the day-loop visibly fits ~20 minutes.

# Phase 4 — Monetize · expand · launch

**Goal:** turn the loop into revenue and get to TestFlight/App Store.

| Lane | Packages |
|---|---|
| Product bets | **X4** first-run that states the promise (with the user's own numbers) · **X5** cast memory · **Y4** la Bibliothèque v1 (absorbs the X7 Stories/Serial IA cleanup) · **X6** read-first polish |
| iOS platform | **M7** IAP / subscriptions (StoreKit + RevenueCat) · **M8** haptics, share, icon/splash · **M9–M11** privacy manifest, account deletion, CI → TestFlight, on-device performance |
| Backend / shared | entitlement sync (server-checked premium gating) |

**Why last:** IAP gates the subscription that the CEFR promise sells, so it follows Y2 + the loop. X4 can only "state the promise" once Y2 exists. Y4 (Bibliothèque) is the content-expansion bet and folds in the Stories-vs-Serial naming cleanup (WP-X7).

**Exit criteria:** sandbox purchase unlocks a server-side entitlement; account deletion reachable in-app; privacy manifest complete; a tagged commit produces a TestFlight build via CI; a 6-panel episode loads fast and stably on an iPhone 11-class device.

---

# Cross-stream dependency summary

| Depends on | Blocks |
|---|---|
| panel images → URLs (P1) | M11 perf, WebView stability (P4) |
| M1 spike (P1) | all of M2–M11 (P2–P4) |
| M2 → M3 (P2) | every data-driven screen working natively |
| CEFR engine (P2) | Y2 meter, X4 first-run promise (P4) |
| "episode available" hook (P3) | X2 web alerts **and** M5 APNs |
| audio pipeline (P3) | X3 TTS, Y1 voicemail, M6 native audio |
| Y2 + the loop (P2–P3) | M7 paywall (P4) |

# Open decisions for the owner
- **Architecture confirmation:** plan assumes Capacitor (web shell + native plugins), not a Swift/RN rewrite. A "native feel from day one" hard requirement is the only thing that flips this — see `docs/ios-app-implementation-plan.md`.
- **Monetization timing:** M7 (IAP) is placed in Phase 4. If validating willingness-to-pay earlier matters more than feature completeness, M7 + a minimal paywall can move to late Phase 3 behind the existing loop.
- **`mobile/` Expo scaffold:** recommended for deletion once M1 proves out (it's a broken, ~2%-coverage skeleton and not the foundation under the Capacitor plan).

# Out of scope for this roadmap (noted, not scheduled)
- Android (near-free Capacitor follow-on after iOS v1).
- Bibliothèque v2 (the interactive "live inside the book" side-door mode).
- Serial season 3+ content authoring (ongoing content track, not engineering).
