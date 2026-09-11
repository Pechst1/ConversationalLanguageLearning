# WP-39 — QA walk of the 2026-09-10/11 surfaces — 2026-09-11

Walked by the integration owner in the in-app Browser pane against the
fake-provider harness (backend `dev_story_engine_server.py` on a throwaway
PostgreSQL, frontend on 3000), signed in through the harness recipe, two fresh
accounts (`native_language=de`). Commit walked: `9491b8a` plus the working tree
of the fixes below. The independent QA agent dispatched first stalled before
signing in; its screenshots were all the sign-in page and were deleted.

Constraints of the walk: the pane was hidden, so client-side pushes stop
committing after a few routes — each route was reached by full navigation plus
`router.replace`, and text was read from `document.body.innerText`, not from
screenshots. Nothing was walked on the simulator. The fake provider authors
English objectives and slug titles («Scène 2 — broken-oven», «Negotiate a price
or say the bike…»); those are harness artefacts, not product defects, and are
listed separately below.

## Verified working

| Surface | What was seen |
|---|---|
| Home | One primary action («Heute starten»), rows for Séance / Lexique / Errata / Vos documents / Votre dossier, «Demain» line; because-line absent before the first journey (expected). |
| Journey, listen-first | «Zuerst hören» → *Raten* with two French guesses → reader panels → recall («café» accepted) → respond → resolution. |
| Journey, respond beat (after fix D-2) | «Sprechen» primary, «Lieber tippen» secondary, «deine Aussprache wird hier nicht bewertet». |
| Placement | Offer screen, «Commencer le bilan» / «Passer pour l'instant»; skip returns to `/atelier`. Re-run entry in Réglages. |
| Dossier | Level, four counters, capabilities on the rubric (register included), errata rule, vocabulary stock (505 assumed / 0 acquired), «Pas encore de scène aujourd'hui». Claim open + verify: `200` on the API (prior agent's calls). |
| Répétition | Declaration screen, weekly cap line, «Préparer la répétition»; declare → prepare → abandon all `2xx` on the API. |
| Journal | «Rien à raconter aujourd'hui — le journal s'ouvre le lendemain d'une scène.» |
| Vos documents (`/missions?intake=1`) | Paste / photograph, weekly cap, empty state; a pasted landlord letter returns `status: unread` («non lu») because the harness has no vision model — the honest state, as designed. |
| Réglages | «Bilan de niveau · Refaire», «Répéter une vraie situation · Ouvrir», «Votre dossier · Ouvrir», «Écouter d'abord» in *Voix*. |
| Network | Every `/api/v1` call `2xx` after sign-in; the 4xx in the console predate sign-in. |

## Defects

| # | Sev | Where | What | Status |
|---|---|---|---|---|
| D-1 | **P0** | `cefr_progress._estimate_with_declaration` | A day-one learner with zero attempts and declared A1.1 got `estimate_source: "measured"`, `verified: true`; the dossier said «Niveau mesuré dans l'application · vérifié». Cause: strict `>` when the prior equals the measured floor. | **Fixed** (`>=`), pinned by `tests/test_wp39_qa_walk.py`. |
| D-2 | **P0** | `useDailyJourney.ts`, `pages/atelier.tsx` | `preferredInputMode` defaulted to `'text'`, so every journey was created text-only and the server never offered voice: WP-27's «Parler» could not render for anyone. | **Fixed**: hook default `'voice'`, page passes `readAnswerMode('voice')`; verified live on a fresh account; pinned. |
| D-3 | P1 | Home, Dossier | Mixed languages on one screen: the journey card is native-language chrome («Heute · Dein nächstes Kapitel»), capability titles in the dossier are German («Im Café bestellen»), while every other row is French. The native-chrome rule is deliberate, but two chrome languages on one screen is not. | Open — product decision (one chrome language per screen). |
| D-4 | P1 | Home | One Home load issues ~130 backend requests: `rehearsals/state`, `intake`, `words-of-the-day` three times each, `atelier/today` and `sessions/active` twice. | Open — dedupe the fetch effects (likely `useEffect` deps in the new rows). |
| D-5 | P2 | Dossier | Counters read «0 / 300», «0 / 2.6», «0 / 0.42» with no unit or explanation of the denominator. | Open — copy. |
| D-6 | P2 | Recall step | Gloss shown as «coffee; café» (English, with the source separator) to a German native. | Open — gloss resolver falls back to English; data debt (WP-21). |
| D-7 | P2 | Réglages, desktop nav | «Settings» in the desktop masthead and «beginner» as a raw enum under *Niveau actuel*; page title «L'administration · Réglages». | Open — pre-existing English chrome. |
| D-8 | P3 | Listen-first | `atelier.journey.listen-first` was already `"1"` on the first account; WP-37 documents default off. Likely set by the earlier QA agent; not reproduced on the second account. | Watch. |

Harness artefacts (not defects): English objective lines and slug scene titles from the fake provider; intake «non lu» without a vision model; radio *écouter* stage not audible (no synthesizer).

## Not walked

Mic-denied path (needs a visible pane to answer the permission prompt), the
dossier claim UI (API only), the rehearsal turns UI (API only), the +1-day
journal entry (needs a dated scene), the self-repair elicitation (needs an open
erratum on the account), any 320/390 pt viewport rendering (hidden pane), the
simulator.
