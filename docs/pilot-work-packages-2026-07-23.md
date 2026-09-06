# Pilot work packages — 2026-07-23

Successor to `docs/audit-2026-07-18-status-and-work-packages.md` (all 14 WPs there are
done). Scope: from "code complete" to **daily iPhone use now, TestFlight pilot next**.
Each WP is self-contained for an implementation agent.

## Verified current state (2026-07-23)

Landed since the product review and confirmed in code this session:

- **Prescription line** on La Une (`LuPrescription` in `components/laune/LaUne.tsx`,
  wired at `pages/atelier.tsx:1664`) incl. the "Choisie pour vous …" because-line and
  time-budget link.
- **Time-budget-aware session assembly** — `atelier.py` `concept_limit(user)` replaced
  the hardcoded 3-concept cap.
- **XP error penalties removed** (audio + stories), **achievements auto-unlock**
  ("Check Progress" gone).
- **Smart-start audio** — primary "Start Talking" starts immediately; scene picker is
  secondary.
- **Asset diet** — static bundle 54 MB → **7.6 MB**, serial art → WebP, zero >1 MB
  images left.
- Journal design system complete on 5 of 6 surfaces (La Une, Courrier, Feuilleton,
  Épreuve, Cahiers); brand + headers unified; full-colour logo in nav.
- Deployment prepped: hardened `render.yaml` (Frankfurt, `/ready`, reference-data
  bootstrap), prod compose with worker+beat, GHCR publish workflow, runbook
  (`docs/iphone-daily-testing-runbook.md`).

**Owner-only actions (not agent work), in order:**
1. Render Blueprint deploy + paste `OPENAI_API_KEY` (~20 min, runbook Phase 1).
2. `NEXT_PUBLIC_API_BASE_URL=https://… npm run cap:sync:ios` → Xcode ▶ onto iPhone
   (runbook Phase 2).
3. Later: Apple Developer enrollment for TestFlight (runbook Phase 3).

---

## Wave A — while the first device week starts (highest value now)

### WP-A1 — Native push: "L'édition de demain"
**Why.** The single strongest retention lever for a daily-edition app; the review and
my assessment both rank it top. Backend `push_subscriptions` exists (web push);
`capacitor.config.json` already carries a `PushNotifications` plugin block, but the
npm plugin is **not installed** and no APNs/native path exists.
**Task.** (a) `@capacitor/push-notifications` + iOS registration flow (permission
prompt staged after first completed session, not on first launch); (b) backend: accept
APNs device tokens on the existing subscription model, send via APNs (token-based
auth); (c) a Celery-beat "édition du matin" notification at the user's preferred hour
— French fiction copy ("Votre édition du 24 juillet est parue — M. Marchand attend une
réponse"), honest content from the real prescription; (d) tap deep-links to `/atelier`.
**Acceptance.** On a physical device: permission granted → token stored → next
morning's notification arrives with real prescription content → tap opens La Une.
Owner note: APNs key setup needs the paid Apple account; until then, gate behind a
capability check so the free-signing build simply skips it.

### WP-A2 — Pilot telemetry + cost ledger
**Why.** Before inviting anyone: know what a day of use costs and what the learner
actually did. `serial_costs.py` exists but nothing rolls it up per user/day; no event
instrumentation for the loop.
**Task.** (a) Server-side event log (plan_started/completed/adjusted, speaking turns,
erratum repairs, slate triples, notification taps) — a slim table + hooks in the
existing completion paths, no client SDK; (b) per-user/per-day LLM+image cost rollup
endpoint reusing `serial_costs` + token accounting already logged on generation
events; (c) a `scripts/pilot_digest.py` that prints yesterday's usage + cost + failure
count (generation fallbacks, delayed episodes) — run manually or via beat.
**Acceptance.** After one simulated day: one command answers "what did today cost,
what did the learner do, did anything fail". Backend tests for the rollup.

### WP-A3 — Resume + interruption resilience (minimal offline)
**Why.** Phone use = constant interruption. Atelier attempts already persist
(submit-as-you-go); missions composer text, review-deck position, and feuilleton
scroll do not. Cold start on flaky mobile network currently blocks on `/atelier/today`.
**Task.** (a) Persist mission composer drafts + review-deck queue position + reader
position (local storage keyed by entity id); (b) cache the last good `/atelier/today`
+ due-context payloads and render them instantly with a "édition d'hier — mise à jour…"
marginal note while revalidating; (c) exact-activity resume: reopening the app returns
to the in-progress exercise/mission, not the section root.
**Acceptance.** Kill the app mid-exercise, mid-mission-draft, mid-review → reopen
lands exactly where you were with text intact; airplane-mode cold start shows the
cached edition instead of a spinner.

### WP-A4 — Fix the dev-preview auth flow (agent velocity, carried from WP-14)
Still unfixed; every design/UI agent has had to build throwaway harnesses. Diagnose
the NextAuth-equivalent web session flow against a local backend, or add a dev-only
bypass consistent with `AUTO_CREATE_USERS_ON_LOGIN` (prod-gated like `main.py`'s
startup guard). Document the login recipe. **Acceptance:** an agent can load
`/atelier`, `/graphic-novel`, `/notebook` signed-in in the preview, both themes.

## Wave B — coach + craft, during daily testing

### WP-B1 — "Le Studio": bring the audio surface into the journal system
**Why.** `pages/audio-session.tsx` is now the worst remaining off-system surface:
neo-brutal borders/offset shadows, English copy inside the experience, generic end
screen. Speaking is also the pilot's most fragile habit — the surface should feel as
crafted as the Épreuve.
**Task.** (a) Reskin to `--app-*` tokens + journal furniture (this is a small surface;
no Claude Design package needed — reuse Épreuve/Courrier primitives; recording states
already exist); (b) French fiction copy; (c) the honest end summary from existing
credit/transcript data: spoke N turns / longest answer / due words reused /
"communiqué malgré N fautes de forme" / one tomorrow-focus line; (d) keep smart-start
as the only primary action.
**Acceptance.** tsc/lint/build green; static test for the summary fields; both themes
verified; zero hardcoded hex.

### WP-B2 — Language-layer consistency sweep
**Why.** The contract is French for the publication world, native-language chrome only
for instruction — but German scheduler keys leak (`grammar.py:40` returns
"gemeistert"/"ausbaufähig" as `state_label` shown in the Cahiers), and scattered
English survives inside fiction surfaces.
**Task.** (a) Keep internal state keys, localize every learner-facing `state_label`
through the existing grammar localization layer; (b) sweep all six surfaces for
in-fiction English/German (grep-driven audit checklist in the PR); (c) add a static
test pinning the worst offenders fixed.
**Acceptance.** No raw German scheduler labels reach any page; static test green.

### WP-B3 — "Choisie pour vous" beyond the prescription
**Why.** The because-line exists on the prescription; the same transparency belongs on
the review deck (why this card: slate/fragile/anchor), missions ("pourquoi ce
courrier"), and feuilleton tasks. This is the pragmatic path to the review's "learner
passport" — explanations force signal convergence without a schema rewrite.
**Task.** Generalize the backend reason-building into a small shared helper; surface a
one-line marginal note on review cards (data mostly present via slate anchors +
buckets), the mission desk header, and panel tasks. French, graphite tone, never
blocking.
**Acceptance.** Each surface shows an honest reason mapped to named fields; tests.

### WP-B4 — Print-theater motion pack (and retire the neo-brutal shadows)
**Why.** The agreed design direction: playfulness from print-shop theater, not softer
geometry; the offset block shadows are the one off-world element left in the system.
**Task.** (a) Stamp "thud" (scale-settle ~120ms) + `pulseAppHaptic` wherever `LuStamp`
/ RÉSOLU / BON À TIRER land; (b) print-in colour transition on completion states;
(c) motif settle-bounce when a concept completes in the Épreuve; (d) replace remaining
`box-shadow: Npx Npx 0` CTA treatments (Cahiers `nc-cta`, audio page after WP-B1)
with an ink-impression press state (translate+shade on :active); (e) every animation
transform/opacity only with reduced-motion variants.
**Acceptance.** No offset block shadows left in the five journal surfaces; motion
inventory documented; reduced-motion verified.

### WP-B5 — Graphite-first correction tone
**Why.** Wrong-answer moments over-use red; the design spec already calls for
graphite "why" notes. Softens the emotional tone without touching geometry — pairs
with the removed penalties.
**Task.** Audit `FeedbackSheet`, `EpGalley`/`EpFix`, `TurnRepair`, Cahiers `NcErrRow`:
red reserved for the mark itself (strike/caret), all explanation text moves to
ink-2/ink-3 graphite; identical hierarchy both themes.
**Acceptance.** Screenshot pass of all correction states; static tests updated.

### WP-B6 — Cast omnipresence (the anti-mascot)
**Why.** Agreed direction: the serial cast is the app's "characters" — put their faces
where a mascot would live. `model_sheet_url` art + relationship data already exist.
**Task.** (a) Portrait chips (not initials) in the La Une lead byline and the
prescription when the reply targets a character; (b) session recap line with portrait
("M. Marchand a lu votre lettre") when the day's mission completed; (c) review-deck
episodic anchors get the character's portrait chip; (d) reuse `FeCastCard` accent
system for tinting.
**Acceptance.** Portraits render from real cast payloads with graceful fallback to
initials; static tests; both themes.

### WP-B7 — Density & hierarchy pass on chrome
**Why.** The "sterile" perception source: too many simultaneous 8–10px uppercase
micro-labels per viewport. Fix hierarchy, not geometry.
**Task.** Per surface, cap concurrent kicker-level labels visible in one viewport
(target ≤3), consolidate stacked marginalia, add breathing room around serif hero
text. Pure CSS/structure; no copy or token changes. Do after B4/B5 to batch visual QA.
**Acceptance.** Before/after screenshots per surface; no functional diffs.

## Wave C — pre-TestFlight

### WP-C1 — Onboarding lite
Better signup (why French · correction style · speaking comfort · minutes/day) feeding
the existing user prefs; first session stays the one-concept short win but themed by
the stated goal. **No** anonymous pre-signup LLM placement (cost/abuse; testers are
invited). **Acceptance:** answers persist to the user model and visibly shape the
first prescription's because-line.

### WP-C2 — Settings reskin ("L'administration") — the last overhaul surface
Already token-clean; needs the journal treatment + French fiction copy. Follow the
per-surface method (audit → brief → owner design pass) or, given its size, a direct
port reusing Cahiers primitives — owner's call in the PR.

### WP-C3 — Serial cast in voice calls
Extend the audio session to be *with* a cast member: opener from the relationship
state, quiet corrections, closeness/callback writes through the existing serial
memory (no parallel memory store). Same character across Feuilleton, Courrier, and
voice. **Acceptance:** a call with Romy updates her relationship ledger and can be
referenced by the next episode.

### WP-C4 — TestFlight ops
Owner: Apple enrollment, App Store Connect record. Agent: archive automation
(Fastlane lane or documented manual), Sentry (or equivalent) crash reporting in the
shell, `APP_ENV=production` flip checklist (SMTP, reset page/deep link per runbook).

## Explicit non-goals (do not build now)

- Social features (friend streaks, co-op missions) — nothing before retention data.
- Learner-selected season tone — risks arc-planner coherence.
- Mascots / faces on the geometric forms — the cast is the character system (WP-B6).
- Anonymous pre-signup placement; native-language navigation (contract stays
  French-fiction / native-chrome).
- A monolithic "learner passport" schema — WP-B3 is the path.

## Suggested order

| When | Packages | Note |
|---|---|---|
| Now (parallel with owner's deploy) | A2, A3, A4 | A1 needs paid Apple acct for APNs — prep code, gate capability |
| First device week | A1 finish, B1, B2 | B1/B2 are independent |
| Weeks 2–3 | B3, B4, B5, B6, then B7 | B4/B5/B6 batch one visual QA pass |
| Pre-TestFlight | C1–C4 | C4 last |
