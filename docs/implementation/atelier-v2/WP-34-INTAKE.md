# WP-34 — Bring your own French («Vos documents») — handoff

Spec: [INNOVATION-WORK-PACKAGES-2026-09-10.md](INNOVATION-WORK-PACKAGES-2026-09-10.md) §3 WP-34.
Commit: `45d7a5f`. The implementing agent stalled before writing this document; the
integration owner verified and committed its work, so this handoff describes what
was checked, not what was intended.

## What it does

A learner pastes text or photographs a document (menu, landlord letter). One
vision-capable model call reads it into a structured artefact — type, summary
bounded to the learner's band, key facts, unknown words glossed through the
existing gloss resolver in the learner's language — and one Courrier task is
derived from it (`missions.create_artefact_mission`), graded exactly like an
existing Courrier mission. Unknown words join the vocabulary queue as
learner-sourced items with provenance (`UserVocabularyProgress` gains the
provenance columns in migration `3759e1c7098c`); `intake.learner_sourced_targets`
exposes them for WP-29's coverage targets.

## Routes (`/intake`)

| Route | Purpose |
|---|---|
| `GET /` | artefact list + cap state |
| `POST /text` | pasted text → artefact |
| `POST /photo` | image upload (bounded size, readable formats only) → artefact |
| `GET /{artefact_id}` | one artefact |
| `DELETE /{artefact_id}` | permanent deletion |

## Bounds and honesty

- `ATELIER_INTAKE_ENABLED`, `ATELIER_INTAKE_WEEKLY_CAP` (default 5, 0 = off),
  `ATELIER_INTAKE_WEEKLY_COST_CEILING_USD` (default 0.50), `ATELIER_INTAKE_VISION_MODEL`.
- One priced PilotEvent per model call; the digest gets `intake_digest_line`.
- Unreadable image or provider failure → «non lu», never a fake artefact.
- Privacy: artefacts are private to the learner, deletable, never written to serial
  memory (source-scan test), sent nowhere but the model call.

## Verified at commit

- `tests/test_intake.py` + `tests/test_intake_api.py` + `tests/test_missions.py`: 82 passed
  (the six 2026-09-05 corrector P0 pins included).
- `components/courrier/courrier-intake.test.js`: 17 checks passed; `type-check`, `lint` clean.
- `ruff` clean; `alembic heads` = one head.

## Hooks owed / open items

- Home has no entry; Courrier's own intake button is the only way in.
- `npm run test:courrier-intake` exists in `package.json` but is not yet in the CI
  node block.
- Calibration of the reading prompt against real photographs is unproven (no live
  call was made, US$0.00).
- WP-29's guard should read `learner_sourced_targets` when it fills `lexicon["targets"]`
  (not yet wired; `living_story.py` fills targets from errata only).
