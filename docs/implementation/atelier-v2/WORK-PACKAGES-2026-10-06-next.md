# Work packages, 6 October 2026: what comes next

The inputs for this doc:
- A fresh day-1 walk at phone size on `backend-test-1003`. A new German-speaking learner went through home, the drill and the first scene.
- Le Papier, walked in dev mock (`/revue?mock=1&lang=de&band=A2`).
- A read of the WP-119 to WP-122 docs and evidence.
- `WAVE3-RESULTS-2026-10-06.md`, `LOSS-RATE-2026-10-06.md` and `docs/status-and-pilot-plan-2026-10-06.md`.

New numbers start after WP-134B.

## 0. Where things stand

- **Unlanded work.**
  - 467 commits sit on `codex/serial-season-engine-production` and are not on `main`.
  - Another 96 sit on the local `exp/wave3-integration`, plus `exp/loss-rate`.
  - Nothing has run in CI since 2026-09-10.
  - The production hardening (password-reset delivery, uploads, auth tests) exists **only in the uncommitted tree**.
  - There are two alembic heads: `b1d3f5a7c9e2` and the untracked `b9d1f3a5c7e0`.
- **The story engine.** The four WP-133b blocking findings are fixed on branches. The loss rate is the remaining gate: 31 of 77 generated days were lost, 64 % of them on the first day of a gap. The fix on `exp/loss-rate` has not been confirmed with a paid read.
- **Le Papier (news).**
  - About 13.7k lines of service code and 349 backend tests, all behind flags that default to off.
  - **No learner has seen it.** The kiosk intake and the dossier builder have never run against real news.
  - The only real weekly set is W40, and it was made by hand.
  - The real-model sample (scripted learner, 10 sessions): French 8/10, acceptance 10/10, cost $0.017 a session with 3 of 10 over the ceiling, p50 turn 4.8 s.
  - Grades: encounter late prototype; intake prototype; plates prototype; vignette beta; Carte beta; Palais, Radio and Correcteur prototype. **None of it is ship-ready.**
- **Immersion.**
  - Painted location plates carry SVG cast rigs on top, with mouths synced to the voice (WP-116 phases 0–4).
  - There is no 3D or WebGL anywhere. WP-117 §Runtime explicitly rejected canvas and WebGL.

## 1. Day-1 design critique (summary)

**What works:**
- The av2 identity is distinctive: Garamond italics, the Bauhaus mark and the warm dark ground.
- The feedback card has the character reacting («Gus lächelt dich an ↑»), which is a good touch.
- Le Papier's fact cards with a source line and «Das Zitat» are honest and look editorial.
- Romy's framing is inventive: she writes for readers in Montréal and asks for your help.

**What breaks trust or immersion:**

| # | Finding | Where | Severity |
|---|---|---|---|
| C-1 | The review eyebrow gives away the answer: «Wiederholung · verkaufen» sits above «vendre — Was bedeutet das?». It happens on every item. | day-1 drill | 🔴 |
| C-2 | A brand-new learner on day 1 sees «Sanfter Wiedereinstieg» (gentle return) on the La Une card. | home card | 🔴 |
| C-3 | The answer options mix articles: «die Wohnung», but «Schlüssel», «appartement» and «clé» are bare. Only three words circulate, so every item can be solved by elimination. | drill | 🟡 |
| C-4 | Cast expressions contradict the scene. In «Le mauvais accueil» all three characters grin broadly, and Lila says «Non.» while laughing. | scene panel 2 | 🟡 |
| C-5 | Panel 3 of 6 is the plate alone, with no caption, sound or character. It reads as broken. | scene | 🟡 |
| C-6 | Two art languages collide: flat vector rigs with hard outlines sit on gouache-textured plates. They share no light, no shadow and no grain. | every panel, the Papier stage | 🟡 |
| C-7 | The reading layout shows a 16:9 plate on a 9:16 screen. The text is small and about 45 % of the screen is empty dark. | scene | 🟡 |
| C-8 | The Papier stage cropped Romy's face out of frame on the first beat. | `/revue` arrive | 🟡 |
| C-9 | The Papier content contradicts itself. The title says «Le marché du dimanche à Aligre». Romy says «On n'est pas à Aligre… c'est le marché du canal». The fact card says the market is open «tous les matins, six jours sur sept». | `/revue` | 🔴 for a news feature |
| C-10 | The Papier looks stale or out of season. On 6 October the edition reads «semaine 40 · du 28 sept. au 4 oct.», one option is «La Fête de la musique» (21 June), every item is «ein Klassiker der Saison», and the eyebrow says «Keine Nachricht». | `/revue` chooser | 🟡 |
| C-11 | The first-run dateline «Quotidien de français · Mardi 6 octobre 2026» is almost invisible in dark mode, which fails contrast. The home card shows a dangling «A1.1 ·». | `/`, `/atelier` | 🟢 |

## 2. The work packages

### Track A — Protect and land (first; nothing else ships without it)

**WP-135 One release candidate**
- Commit the production hardening from the dirty tree with `git commit -- <paths>`, because Codex shares the checkout.
- Add the alembic merge revision over `b1d3f5a7c9e2` and `b9d1f3a5c7e0`.
- Land `codex/serial-season-engine-production`, then wave 1 to 3, then `exp/loss-rate`, through E-1 as reviewable PRs.
- Clear the 70 Ruff findings that block publishing.
- Make `.venv` (Python 3.11) complete. This needs the owner's decision on the missing packages.
- Run the order-dependent and midnight flakes through E-2 first.

Done when: CI is green on `main`, there is one schema head, and the Render staging deploy is prepared but not pushed without approval.

**WP-136 Loss-rate confirmation**
- Run the confirmation read on `exp/loss-rate`: about US$0.60, three runs, after a dry run with `WP133A_DRY_FAIL`.
- Run one continuation-day read: about US$0.10. It must reach day 62 so the Lila guard is checked live.

Done when: the loss rate on the first day of a gap is under 15 %, and the lost days recover in story. If it fails, the cohort stays closed.

### Track B — Day-1 trust (small, high leverage; can run in parallel with A)

**WP-137 Day-1 walk fixes (C-1 to C-5, C-11)**
1. Remove the gloss from the review eyebrow, or show only the category. Add a test that no eyebrow contains any option's text.
2. Gentle return: `missedDays` must count from the first practice. A learner with no practice history is never «returning».
3. Answer options use one article policy: all with the article, or all without.
   - At A1, draw distractors from more than the day's three words, and avoid closed sets the learner can solve by elimination.
4. Expressions per beat: the director writes `mood` per line (it already writes `tone`), and the rigs map it to an expression. Add a walk check that an «accueil froid» beat never renders `smile`.
5. A silent panel gets a caption line, an ambient cue or a slow pan. It is never a bare plate.
6. Raise the dateline contrast to ≥ 4.5:1 and drop the trailing separator when there is no unit name.

Done when: the E-3 walk screenshots for day 1 in three languages, light and dark, read clean.

### Track C — Le Papier: from built to live

**WP-138 Real news, coherent dossiers**
- Run the kiosk intake and the dossier builder against real RSS for W41 and W42. This is their first real-model sample.
- Have the owner read a contact sheet.
- Add a coherence check to `revue/checks.py`. Title, setting, Romy's first line and the claims must agree on place, time and frequency. C-9 would have failed it.
- Evergreens:
  - Give them recurring windows by month and day instead of 2026-only windows.
  - Never offer one out of season (C-10).
  - Name the edition by the current week.
  - When the week has no news, the label is «Hors-série», not «Keine Nachricht».

**WP-139 Sources and rights (owner + legal)**
- Write a source policy covering press publishers' rights (*droits voisins*, L.218-1 CPI), quote length, keeping excerpts, robots.txt versus a licence, and real people on plates.
- Prefer licensed or open sources: open public data, Wikipedia (CC BY-SA, with attribution), and public institutions' press releases. Paraphrase on top.
- Add a per-source `license` field to `FRANCE_SOURCE_REGISTRY` and enforce it at intake.

Done when: a written policy exists and no source lacks a licence class.

**WP-140 Romy speaks**
- Voice Romy's and the guests' lines in the encounter with the existing cast TTS and `useMouth`.
- A1 and A2 listen first, then see the text, as Radio already does. The «Zusammenfassung hören» chip becomes the default way in, not an extra.
- Cache the audio per line, and stay inside the cost ceiling.

**WP-141 Papier quality pass**
- Fix F-1 to F-6 from `evidence/revue-sample-2026-10-03b`:
  - restatement checked on the text, not only on claim ids;
  - guests' facts go through the knowledge check;
  - no offers beyond the sources;
  - vocabulary matched on meaning, not spelling;
  - no conjugated forms in the vocabulary.
- Hold the cost ceiling at $0.02 at p100, and stream turns so p50 is under 3 s to the first token.
- Give C1 real depth: register, implicit stance, procedure. C1 must stop collapsing to B2 (`policy.py:380`).
- Rerun the same 10 sessions plus 5 run by a human.

**WP-142 Papier pilot and pruning**
- Turn on `REVUE_ENABLED` for the owner only.
- Do the pending hands-on acceptances: WP-120 D, WP-121 and WP-122.
- Add the `pilot_digest` line.
- Then decide which satellites earn a place: Carte, Palais, Radio, Correcteur.
  - The status plan says to judge integration before adding destinations.
  - Default proposal: keep the Papier, the Carte and Radio. Fold the Correcteur into the Papier's close. Keep the Palais as a mode of the Carte.

### Track D — Beautiful and immersive (2D, now)

**WP-143 One stage, one light (C-6, C-8)**
- Make the rigs belong to the plate:
  - colour grading sampled from the plate's palette;
  - a shared light direction, a rim light and a contact shadow;
  - the plate's paper grain on top of the rig;
  - a slight depth-of-field softening of the plate behind the speakers.
- Framing rule: a face is never cropped. The stage computes its crop from the rig's head box.
- This stays within av2: no new fonts or colours. The grading is derived from each plate.

**WP-144 The vertical page (C-5, C-7)**
- Show panels full-bleed at 9:16: a crop of the plate chosen per beat, with a slow push-in.
- Show speech as balloons anchored to the speaker inside the panel. The list below the image goes away.
- Reveal lines with the voice, word by word, using the existing timings. Tap a word for its gloss (the dotted underline already exists).
- Respect `prefers-reduced-motion`.
- Done when the owner, comparing blind, prefers it to the current reader.

**WP-145 Sound bed**
- Ambient loops per place (rain on the café window, market murmur, a métro platform), 10–20 s seamless, ducked under the voices.
- Off with the mute switch, and off by default in public mode.
- This is the cheapest gain in immersion.

**WP-146 «Toi» in frame (POV in 2D)**
- When a character speaks to the learner, they face the camera.
- The learner's reply appears as their own balloon at the bottom edge, the point-of-view position.
- Object inserts drawn from the hand's point of view: the key, the letter, the notebook.
- This connects to WP-118 Mon personnage, which is seen only in mirrors and plates, never as a third-person avatar on screen.

### Track E — POV and 3D (future; spikes first)

**WP-147 Spike: «Théâtre de papier» (2.5D POV), feasible now**
- Make a depth map per plate offline, when the plate is created; one model call or a local depth model.
- Render it as a WebGL displacement quad or as 3–5 CSS planes:
  - look around ±5° by gyroscope or drag;
  - a dolly-in when the scene opens;
  - the SVG rigs stand as cut-outs at their depth.
- The look stays a paper diorama, which fits the paper identity.
- Budget: 60 fps on an iPhone 12 in Capacitor, under 300 KB extra per plate, and a static fallback.
- Takes about 1–2 weeks.
- Done when: in a blind A/B on 3 scenes, the owner and 3 testers rate «I was in the room» higher, with no rise in time per page.
- **Requires the owner to reverse WP-117 §Runtime («no WebGL») and the old «no parallax» handoff, for this surface only.**

**WP-148 Research: true 3D POV**
- Turn one location, Odile's café, into an explorable 3D scene. Try either image to 3D world generation or a Gaussian splat built from generated multi-view plates, rendered with a three.js splat viewer.
- Measure the download size, load time, mobile fps, how faithful it stays to the av2 painting and the cost per location.
- Characters stay 2D cut-outs. A rigged 3D cast is out of scope and would replace the WP-116 investment.
- Decision gate: only if WP-147 shows a measurable gain in immersion. Otherwise stop at 2.5D.

## 3. Order

| When | Packages | Parallel? |
|---|---|---|
| Now | WP-135, WP-136, WP-137 | A and B in parallel; the WP-136 read needs WP-135's branch merge or runs on `exp/loss-rate` |
| Next (after the RC) | WP-143, WP-144, WP-138, WP-139 | the design and Papier tracks share no files |
| Then | WP-140, WP-141, WP-145, WP-146, WP-147 spike | WP-147 is isolated (new component behind a flag) |
| Pilot | WP-142, owner walk | — |
| Later | WP-148 | only after the WP-147 gate |

## 4. Owner decisions this doc needs

1. Make `.venv` complete (unblocks WP-135).
2. Spend about US$0.70 on WP-136.
3. Sources policy and legal review (WP-139).
4. Which Papier satellites to keep (WP-142).
5. Allow WebGL and parallax on the scene surface for the WP-147 spike.
6. The still-open Wave 3 decisions: «adieu», T8 B in German, A1/A2 reply exchanges, B1 rule days, a copied example counting as supported, WP-134A wording, pushing the branches.
