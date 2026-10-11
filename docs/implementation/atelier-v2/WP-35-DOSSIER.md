# WP-35 — The inspectable learner model («Votre dossier») — handoff

Spec: [INNOVATION-WORK-PACKAGES-2026-09-10.md](INNOVATION-WORK-PACKAGES-2026-09-10.md) §3 WP-35.
Commit: `7dd15d4`. The implementing agent stalled while finishing its surface-scan
test; the integration owner verified and committed its work.

## What it does

`learner_model.build_dossier` composes, by import only, what the app believes:

- **Level** — estimate, `estimate_source` (declared / placement / measured),
  confidence and the WP-25 breakdown, with the placement record as evidence.
- **Capabilities** — `journey_capabilities.build_capability_summary`, the one rubric
  (CONTRACTS §8); never re-scored here. Each state links to the journey and date.
- **Errata** — WP-24 states open / repairing / mastered with next due and the
  «faux → juste» example.
- **Vocabulary stock** — FSRS counts (known set via WP-29 where cheap).
- **Today** — the `because` payload read from the plan (WP-28), else «Pas encore de
  scène aujourd'hui.» with no promise about what tomorrow will target.

«Je connais déjà» on an erratum or a word opens a two-question check
(`build_claim_check` → `record_claim_opened` → `verify_claim`). A pass advances the
schedule through the existing SRS / error-memory APIs (`_advance_after_pass`), a
fail records «pas encore» with no penalty. No path trusts the claim without the
check (source-scan test).

## Routes (`/dossier`)

| Route | Purpose |
|---|---|
| `GET /state` | the dossier envelope |
| `POST /claims` | open a claim, returns its two items |
| `POST /claims/verify` | grade the two answers, advance or decline |

Frontend: `pages/dossier.tsx` → `components/atelier-v2/dossier/DossierScreen.tsx`,
state in `dossier-state.ts`; entry from Réglages («Votre dossier · Ouvrir»).

## Verified at commit

- `tests/test_learner_model.py` + `tests/test_dossier_api.py` + `tests/test_dossier_surface.py`: 45 passed.
- `dossier.test.js`: pass; `type-check`, `lint` clean.

## Hooks owed / open items

- Home entry (HomeScreen.tsx) and a `test:dossier` script in `package.json` + CI.
- The register dimension (WP-33) appears only once `CapabilityKey.REGISTER` lands.
- Not walked in a browser or on the simulator.
