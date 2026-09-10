# Claude Design brief — the four screens still off the system

**Audit, 2026-09-10.** Every learner-facing page was scored for av2 markers
(`AtelierV2Root`, `--av2-*`) against legacy markers (tracked caps, `--app-ink`,
2px ink boxes, offset shadows). Result:

| Screen | Route | av2 | legacy | Verdict |
|---|---|---:|---:|---|
| Landing | `/` | 0 | 15 | **off-system** — on the older `--app-*` editorial tokens |
| Sign in | `/auth/signin` | 0 | 21 | **off-system** |
| Create account | `/auth/signup` | 0 | 37 | **off-system**, the worst of them |
| Forgot password | `/auth/forgot-password` | 0 | 22 | **off-system** |
| Conversation setup | `/learn/new` | 0 | 23 | off-system, disposal candidate (see below) |
| Conversation session | `/learn/session/[id]` | 0 | 9 | off-system, disposal candidate |
| everything else | — | ✓ | 0 | on the system |

Dev and ops surfaces (`/dev/styleguide`, `/mobile-visual-qa`,
`/atelier-v2-gallery`, `/pilot-ops`) are excluded: nobody but us opens them.

**The `/learn` pair is not in this brief on purpose.** It is the legacy
conversation cluster, reachable only from the Bibliothèque's "discuss this story"
modal, and the Studio plus the daily journey now own conversation. Designing it
would be drawing screens for a path that probably should not exist. Recommend
disposal, the way WP-20 disposed of eleven other legacy pages; it is a decision,
not a design.

**Why these four matter more than their size suggests:** they are the entire
signed-out experience. A learner meets them before anything else, and right now
they meet a different product — English chrome, tracked caps, hard ink boxes with
offset shadows — and then land on the av2 Home. The seam is the first thing the
product says about itself.

---

## The system these screens must join

Tokens are in `web-frontend/styles/atelier-v2.css`. Do not invent values.

**Ground** paper `#f1ece1` · card `#f8f3e8` · line `#e8e0cf` · line-2 `#d8cdb6`
**Ink** ink `#14110d` · ink-2 `#4a4538` · muted `#6f6857`
**Semantic** red `#d8321a` = *action* · blue `#1d3a8a` = *story/info* ·
yellow `#f3c318` = *reward* · green `#2c6a5d` = *correct* · ink = *done*.
Each has a `-deep` press shadow that is **darker than its face**, so the press
reads as depth and never as a second colour. Label on red is `#ffffff` (paper
white measures 4.32:1 there, under AA).

**Type** serif `AtelierSerif / EB Garamond` for headlines, sans
`AtelierSans / Instrument Sans` for everything else. Scale (rem, so the learner's
text-size setting moves it): meta 12 · label 13 · body 15 · **field 16, never
lower — below 16px iOS zooms the viewport and never zooms back** · action 17 ·
rule 19 · option 20 · title 24 · head 30 · screen 32 · display 34.

**Geometry** radius: pill 999 · button/card 16 · tile 18 · episode 22 · hero 24 ·
sheet 28. Press depth: primary 5px · options 3px · icon actions 4px.
Gutter 20px, gap 12px, **44px tap floor — an accessibility floor, never a design
value**.

**Rules that are load-bearing, not taste**

1. **One Garamond italic headline per screen.** Not two.
2. **One 3D-press primary per composition.** Everything else is quiet.
3. **Sentence case everywhere.** Tracked uppercase is retired — it is the single
   most repeated legacy tell on these four screens.
4. **Soft pill buttons**, not the uppercase ink slab (owner preference, settled
   2026-09-02).
5. **Say only what is true.** No invented streaks, counts, testimonials, social
   proof or time promises. The product has been burned by exactly this.
6. Every screen must be drawn **light and dark**. Dark is not an inversion: the
   paper darkens toward its warm brown and each accent lifts until it clears
   4.5:1 (dark paper `#17140f`, card `#221e17`, ink `#f5efe1`, red `#ff6a4d`,
   blue `#7fa0ff`).
7. Phone frame **390 × 844**, safe-area inset top and bottom respected.

---

## Artboard 1 — `/` · La une (signed out)

The masthead of a daily paper, which is the product's whole metaphor.

Content, verbatim — this copy is already French and already honest, keep it:

* nameplate **L'Atelier**, with the four-shape mark (ink square, blue circle,
  yellow square, red triangle)
* folio: `Quotidien de français` · `MERCREDI 9 SEPTEMBRE 2026`
* the one headline: *« Chaque jour, une édition de français dont vous êtes un
  personnage. »*
* standfirst: « Un épisode de feuilleton où vous tenez votre rôle, une courte
  séance d'exercices, des progrès consignés noir sur blanc. »
* actions: **Se connecter** (the one primary) and **Créer un compte** (quiet)

States: just the one. No hero art — the product has none it owns, and a stock
image would be the first lie on the first screen.

## Artboard 2 — `/auth/signin` · Se connecter

Content: email · password with a reveal control · « Mot de passe oublié ? » ·
primary **Se connecter** · a quiet line to sign-up: « Nouveau ici ? Créer un
compte ».

Draw four states: **idle**, **focused** (the field's focus ring is the system's
3px ink outline at 2px offset), **pending** (the primary shows its spinner and is
genuinely disabled), **error** — wrong credentials, stated plainly in one line,
never blaming the learner and never revealing whether the address exists.

The fields carry the 16px floor. This screen is where D-16 came from.

## Artboard 3 — `/auth/signup` · Créer un compte

The heaviest screen and the one most worth rethinking rather than restyling. It
currently asks everything at once. Its real content is two groups:

**The essentials** — full name · email · password · interface language
(English / French).

**Your first edition** — the onboarding that shapes day one:
* *Why French?* — To travel and get by · To work in French · To talk with people
  close to me · To read, watch and listen
* *Minutes a day*
* *Correction style* — Light, keep the thread going · Balanced · Exact, flag
  everything
* *Speaking out loud* — Still warming up · I can answer · Push me

Draw it as **two steps** with an honest progress indication (`1 / 2`), not one
wall of fields. Step 2's answers change the first edition, so say so in one line
rather than leaving them to feel like a survey.

States: step 1, step 2, a validation error on a single field, and pending.

## Artboard 4 — `/auth/forgot-password` · Mot de passe oublié

Two jobs in one route today. Draw both:
* **Request** — email, primary « Envoyer le lien ».
* **Sent** — a confirmation that does **not** disclose whether the address is
  registered.
* **Reset** (arrived with a token) — new password · confirm · primary.
* **Expired link** — stated as infrastructure, with the way back.

---

## What "done" means

Each artboard is a real screen at 390 × 844, light and dark, using only the
tokens above, with the states named. I implement from these directly, so a
decorative flourish that has no token behind it is a bug, not a bonus.
