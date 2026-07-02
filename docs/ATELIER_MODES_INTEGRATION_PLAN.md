# Atelier — Package F (detailed): Missions & Story Mode

Builds on `ATELIER_UIUX_OVERHAUL_PLAN.md` (E) and `ATELIER_AI_FIRST_GENERATION_PLAN.md`.
This is the detailed, audit-driven version. Two decisions are made up front (the owner
delegated both):

1. **Mission cadence:** missions are an **opt-in spine the resolver surfaces** (≈2–3×/week,
   or when the learner's grammar is ready to apply) — **not** a mandatory daily fixture.
   Rationale: keep the core daily loop short and finishable ("one quick beat"); missions
   are the rewarding applied-output capstone, available anytime but not forced every
   session.
2. **Story mode:** do **not** extend the existing interactive-fiction engine. Reuse its
   ingestion plumbing; build guided reading on the AI-first exercise engine with a
   **user-owned** library (see audit).

## The unifying model: the daily edition is a playlist

Atelier is the assembler; the grammar path, the Feuilleton serial, the learner's
library, and missions are **content spines** feeding one AI engine and one daily path.
`resolveRecommendedNext(...)` / `select_today(...)` choose today's mix and one soft,
highlighted next step. Nothing is a separate app.

---

## Audit: existing story-mode implementation (why we're not extending it)

| Area | Finding | Verdict |
| --- | --- | --- |
| Ingestion (`book_parser.py`) | txt/epub/pdf/html via PyMuPDF, ebooklib, BeautifulSoup | **Reuse** (with cleanup fixes) |
| Upload (`stories.py` `/upload-book`) | async endpoint, size/type validation | **Reuse** the endpoint shape |
| Experience model (`story.py`, `story_service.py`) | interactive fiction: `branching_choices`, NPCs, `narrative_goals`, `cliffhanger`, XP, scenes/consequences | **Wrong model** for guided reading — do not extend |
| Ownership | `Story` has no `user_id`; `/upload-book` never passes `current_user` → uploads become **global** content | **Broken** for a personal library; privacy issue |
| Coverage | `max_chapters` default **5** (endpoint) / 10 (parser), hard-sliced | **Broken** for "walk through the book" |
| Engine | own narrative-goal mechanic, **not** the AI-first exercise engine | **Inconsistent** — unify on the AI engine |
| Robustness | in-memory `upload_tasks` dict (lost on restart, single-worker); silent `return ""` if PyMuPDF missing; raw PDF text (page numbers/headers/hyphenation) | **Not production-ready** |

Conclusion: keep the file-ingestion layer; replace the experience with guided-reading
episodes on the AI engine; add user ownership; fix coverage + robustness. The
interactive-fiction `StoryService` can remain a **separate** feature for curated
choose-your-own stories, or be deprecated — it is not the thing the owner is describing.

---

## Part 1 — Missions = interactive messaging (applied output)

One mechanic: an AI **persona** the learner texts toward a goal, in a register; the AI
replies in character and gives end-of-thread feedback. Two context sources, one engine.

- **Life missions** — vivid standalone scenarios at the learner's level (reply to your
  landlord about a leak, decline an invite politely, fix a wrong delivery). Persona,
  goal, register and target grammar/vocab generated from the learner's CEFR + due
  concepts/errors (AI-first), replacing the current generic news snapshot.
- **Story missions** — the Feuilleton "act in French" beat *is* a mission; the message
  changes the next scene.

### Tasks
- **F1 — Unify the messaging engine.** One service/contract powers both the mission
  messenger (`missions.py` `_messenger_payload`/`conversation_opening`) and the
  `graphic_novel.py` act-beat. One thread model, one turn loop, one evaluator.
  - Data: a `mission_thread` (turns: role, text, timestamp; goal; persona; register;
    target concept/vocab ids; status). Reuse `AtelierAttempt`-style storage or a new
    table.
- **F2 — AI-first scenario generation (life missions).** Generate
  `{persona, goal, register, constraints, target_grammar, target_vocab}` from the
  learner's state. Keep `travel_work`/`message` templates as seeds; keep the news
  source as one optional flavor, not the default.
- **F3 — Mission evaluation + resolver placement.** AI evaluates each turn in-character
  and produces end feedback (reuse the AI correction infra: `_llm_correction`,
  `_correction_system_prompt`). Wire into `select_today`/`resolveRecommendedNext` as an
  **opt-in** spine surfaced ≈2–3×/week or when the learner has grammar ready to apply;
  also reachable on demand.

Acceptance: a learner completes a short in-character thread, gets contextual end
feedback targeting their weak grammar/vocab; the serial's act-beat runs on the same
engine; missions appear as a soft suggestion, never a forced gate.

---

## Part 2 — Story mode = guided reading from your library (rebuilt on the AI engine)

Goal: upload a book → a paced run of episodes that walk you through it, each grounding
**comprehension + vocab + grammar + production** exercises in that passage.

### F4 — User-owned library model
- New `UserBook` (or add ownership): `user_id` (FK, indexed), title, author,
  source_type, source_hash (dedupe), status (parsing/ready/failed), total_episodes,
  created_at. Private to the uploader by default.
- New `BookEpisode`: `user_book_id` (FK), order_index, passage_text, est_reading_minutes,
  cefr_level, vocab_seed (jsonb), grammar_seed (jsonb), exercise_payload (jsonb,
  AI-generated, nullable until generated), status.
- Keep the curated interactive `Story`/`Chapter`/`Scene` model untouched (separate
  feature). Do not overload it.
- Migration (Alembic).

### F5 — Ingestion: whole book, level-sized, robust
- Reuse `book_parser` extraction (PyMuPDF/ebooklib/bs4) but: **remove the 5/10-chapter
  cap** — process the whole book; **clean** extracted text (strip page numbers, running
  headers/footers, de-hyphenate line breaks); segment into episodes by **reading size at
  the learner's level** (e.g. ~150–400 words/episode by CEFR), not only by detected
  chapter boundaries.
- Make `/upload-book` (or a new `/library/upload`) **pass `current_user`** and create a
  `UserBook` owned by them. Replace the in-memory `upload_tasks` dict with a **durable
  Celery task** (the project already has `app/celery_app.py`) writing status to
  `UserBook.status`. Surface real errors (no silent `return ""` when PyMuPDF is
  missing — fail the task with a clear message).

### F6 — Episode exercises on the AI engine
- For each episode, feed the **passage** into the AI-first generator as context so the
  exercises are specific to that text: comprehension questions, vocab-from-the-passage,
  grammar instances found in the passage, and a production task referencing the scene.
  Reuse `ExerciseGenerationService` + the AI self-critique from the AI-first package.
- **Background pre-generate** the next episode while the learner reads the current one
  (same pattern as the daily edition), so it's instant.

### F7 — Arc + Library surface
- Surface "continue *[book]* — episode X of Y" as a **soft daily option** via the
  resolver; reading progress like the serial.
- Library lives in **Notebook** (read mode): the learner's uploaded books with progress,
  plus the serial archive and past missions.

Acceptance: a fresh user uploads a PDF, gets a `UserBook` owned by them with the whole
book segmented into level-sized episodes; each episode's exercises are visibly drawn
from that passage; the next episode is ready without a wait; upload status survives a
server restart; failures surface a clear error.

---

## Part 3 — UI/UX alignment (Package E)

- **Missions:** a new core component — a clean **messaging Thread** (do mode: one input,
  one Send, in-character replies, an end-of-thread `FeedbackSheet`). Add to the E-0 set
  (the feedback sheet + tokens already exist in `globals.css`).
- **Story episodes:** **read mode** (passage, editorial, calm) → **do mode** (the
  passage-grounded exercises on the existing `.atelier-exercise-shell`) → E-3 feedback.
- **Library:** in Notebook, read mode.
- The daily cover (E-1) can teaser any spine: "today's message", "today's scene",
  "continue *[book]*" — always one highlighted next step.

---

## Robustness fixes carried from the audit (do alongside F4–F6)
- Durable upload/generation task tracking (Celery + `UserBook.status`), not the
  in-memory `upload_tasks` dict.
- Surfaced ingestion errors; no silent empty-string returns.
- PDF text cleanup (page numbers, headers, hyphenation).
- Whole-book coverage + CEFR-sized episode segmentation.
- Per-user ownership + privacy on uploads.

## Suggested PRs
1. PR F-1: unify the messaging engine (missions + Feuilleton act-beat).
2. PR F-2/F-3: AI-first mission scenarios + evaluation + opt-in resolver placement.
3. PR F-4: user-owned `UserBook`/`BookEpisode` model + migration.
4. PR F-5: robust ingestion (whole book, cleanup, level-sized episodes, Celery task,
   user-scoped upload).
5. PR F-6: passage-grounded episode exercises on the AI engine + background pre-gen.
6. PR F-7: Library surface + resolver wiring + messaging Thread / reading components.

## Definition of done
A daily edition can weave in a personalized opt-in mission and/or a book episode;
missions are interactive AI threads with end feedback that target the learner's weak
spots; uploading a book yields a user-owned, paced run of passage-grounded episodes that
covers the whole book and survives restarts; every mode reuses the one AI engine and the
E design system; the interactive-fiction engine stays a separate concern; nothing reads
as a separate app.
