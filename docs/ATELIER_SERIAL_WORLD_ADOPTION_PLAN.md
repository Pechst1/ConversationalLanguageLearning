# Atelier — Package J: Serial World Adoption (A1–A5)

Adopt the Claude Design "Serial World" screens as implementation targets. Faithful
design source is vendored in `docs/design-reference/` (`serial-screens.jsx`,
`serial-components.jsx`, `serial.css`, plus `serial-world-design-package.md`). Reimplement
on the real Next.js/Tailwind stack + the design tokens — **do not paste the Claude
Design JSX/CSS** (it's generic React with its own classes); use it as the spec.

| Screen | What it is | Status |
|---|---|---|
| **A5 — The story so far** | character-accented episode timeline | ✅ done (`web-frontend/pages/serial/index.tsx`) |
| **A1 — The serial on-ramp** | the daily home card; serial is the hero, grammar is "also in today's edition", 4 states | ⬜ blocked-then-do (lives in `atelier.tsx`; coordinate with the active agent) |
| **A2 — The act (reply, not grade)** | the in-fiction reply UI; the NPC's reply is the payoff, the 0–4 score recedes to a footnote | ⬜ needs backend (see Package F) |
| **A3 — The serial reader** | vertical-scroll reader on phone (comic-page as option), with embedded "you write the next line" act beats | ⬜ big pass (`graphic-novel.tsx`) |
| **A4 — The cliffhanger** | the hero surface: the unresolved question + one CTA that seeds the next act | ⬜ part of the reader flow |

## J1 — A1 the serial on-ramp (daily home card)
Restyle the Atelier home so the serial is the hero card (`THE SERIAL · your turn` →
`Reply to Marchand`, with grammar demoted to `also in today's edition · Grammar session`).
Four states: act-pending, see-pending (new episode ready), brand-new (episode 1
invitation), all-caught-up. Source: `serial-screens.jsx` `AtelierHome` + `serial.css`.
Lives in `web-frontend/pages/atelier.tsx` — coordinate with the parallel agent before
editing.

## J2 — A2 the act screen (reply, not grade)
The interactive in-fiction reply. The visible payoff is the **NPC's in-character reply**;
the 0–4 correctness score is demoted to a footnote. Frontend source:
`serial-screens.jsx` `ActScreen` + `serial-components.jsx` `ReplyCard`/`RepairSlip`.
**Backend:** the in-character reply generation + scoring is the unified messaging engine
in `ATELIER_MODES_INTEGRATION_PLAN.md` (Package F, F1/F2) — build that first; this is its
serial face. Story-seal mint on beat-complete ties to Package I (I2/I4).

## J3 — A3 the serial reader (vertical, with embedded acts)
The core reading surface. Vertical-scroll-first on phone; comic-page as a mode for the
printed feel. Panels, speech bubbles, character avatars with their `--char` accent ink,
a "previously on" header, embedded "you write the next line" act beats, choice forks, and
a vocab recap. Source: `serial-screens.jsx` `ReaderVertical`/`ReaderComic` +
`serial-components.jsx` (`ReaderMast`, `PreviouslyOn`, `Panel`, `ChoiceFork`,
`VocabRecap`) + `serial.css`. Target: `web-frontend/pages/graphic-novel.tsx` (~4,900
lines — a careful, staged pass on the core reader). Lead with vertical mode; ship
comic-page behind a toggle.

## J4 — A4 the cliffhanger
The episode's closing hero: the unresolved question large, one CTA that seeds the next
act (`Answer Romy`), recap demoted below. Source: `serial-screens.jsx` `CliffScreen` +
`serial-components.jsx` `Cliffhanger`. Often the last beat of the reader (J3).

## System — character accent palette
"One spot ink per character" is **already in `globals.css`** (`--char-marin/-lila/-gus/
-romy/-margaux/-marchand/-toi` + the `[data-char]` rules). A5 already uses it; A1–A4
should set `data-char` on character-led elements to inherit `--accent`.

## Suggested PRs
1. PR J-1: A1 on-ramp (after the agent's `atelier.tsx` work lands).
2. PR J-2: A2 act screen — after Package F messaging engine.
3. PR J-3: A3 reader (staged: vertical mode first, then comic-page, then embedded acts).
4. PR J-4: A4 cliffhanger.

## Definition of done
The serial reads as the spine of the daily edition across the home (A1), the act (A2),
the reader (A3), the cliffhanger (A4), and the archive (A5) — all on the real stack and
the `--char` accent system, matching the vendored design reference.
