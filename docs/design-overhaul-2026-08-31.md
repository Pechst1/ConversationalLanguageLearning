# Design overhaul — 2026-08-31 pass ("simplistic beauty")

**Trigger:** owner feedback — "too overcrowded, the simplistic beauty is missing, a lot of
stuff is all over the place." Full live walkthrough (fresh seeded account, mobile viewport,
light+dark) preceded the changes; every fix below was verified in the running app.

## Principles this pass encodes (keep them for every future surface)

1. **One primary action per screen.** When the La Une prescription CTA already opens the
   séance, the séance block renders a quiet text link (`LuSeance quiet`), never a second
   press bar.
2. **No internal inventory as learner copy.** Drill counts ("46 exercices · 0/46") read as
   a threat and describe internals; time (~min) plus the rule list is the whole story. The
   progress bar carries resume state silently.
3. **Publication surfaces speak French.** Concept titles now have authored `name_fr` in the
   catalog (54/54), served as `title_fr`/`category_label_fr` on atelier, grammar by-level,
   and grammar notebook payloads; the frontend prefers them on La Une, l'Épreuve, and the
   Cahier index. Instructional explanations stay in the learner's language (unchanged
   contract).
4. **No machine keys or corrector internals on the page.** `source_label` snake_case keys
   are mapped (`pilot_capture` → "Capture pilote"); provenance reasons that contain a
   "learner → target" mapping fall back to the short label instead of spoiling the coming
   repair; LLM markdown backticks print as « guillemets » (`printableWhy`); mission
   corrections whose corrected text equals the learner's text are dropped server-side
   (no card, no erratum, no "réparation enregistrée").
5. **Delete dead eras, don't let them coexist.** 68 unreferenced functions (~52 KB) and 82
   dead CSS rule blocks (parcours map, day badges, edition covers, fake streak widgets)
   removed from `pages/atelier.tsx` (8,650 → ~6,580 lines). Static tests that pinned dead
   code were updated to pin the live implementation instead.

## Shipped in this pass

| Area | Change |
|---|---|
| Landing `/` | Rewritten: French, on-system, honest (no "~15 min", no fake queue); calmest screen in the app |
| La Une | Séance meta reduced to `~N min`; single-CTA rule; DEMAIN teaser suppressed when it repeats tonight's headline; `1ᵉʳ jour de suite` ordinal |
| L'Épreuve | Provenance shown once on arrival (not above every drill); machine keys/spoilers/backticks cleaned; recap uses French titles; "1 jour" plural |
| Cahier | Progrès tab removed (it embedded the pre-journal English Anki dashboard incl. a global 10k-word dump); grammar index fully French |
| `/serial/episode/[index]` | On-system reskin: tokens (dark-mode capable), French chrome, ASSISTANT/USER/ACT → LA CORRESPONDANCE/VOUS/L'ACTE |
| Le Studio | Kicker no longer renders dangling "APPEL N°"; end summary now reports real tracked corrections (in-flight turn no longer clobbers the recap) |
| Vocabulary | `fr_to_de` no longer hardcoded anywhere: registration derives direction from native language, due-context endpoint falls back to the stored preference, arrows are typographic (→) |
| Infra | uvicorn `--timeout-keep-alive 75` everywhere (dev launch, start-backend.sh, docker/entrypoint.sh) — root cause of ECONNRESET through the Next proxy that hung La Une's skeleton and silently broke session completion |
| Catalog | TSV row FR_A1_PRON_001 repaired (was missing anchor_examples + exercise_tags, shifting 3 columns); `name_fr` column authored for all 54 concepts |

## Second wave — shipped 2026-08-31 (evening)

Every "still open" item from the first pass landed the same day:

| Area | Change |
|---|---|
| Review deck (WP-B7) | Header 9 kicker-level elements → 3 (one count line "11 cartes · environ 4 min" + hairline progress rule + quiet bucket sentence); "NEW PICK" → "La pioche du jour"; French dates/toasts; English rating hints dropped |
| Épreuve furniture | "RULE"/"NOTEBOOK ↗" kickers → "LA RÈGLE"/"CAHIER ↗"; correction frame labels restyled from debug-mono to the standard kicker treatment |
| Le Relevé | New third Cahier tab replacing the parked English Anki dashboard: Le Cours (CEFR + forecast + gauges), Le Registre (learner-scoped counts, dotted-leader ledger, state bar), La Collection (achievements/collectibles, honest empty state). `/grammar/summary` now counts only the active catalog (was 368 incl. archived legacy; now 56) |
| Feuilleton tab | L'ÉPISODE dispatches on the serial beat: readable → the reader; sous presse → honest wait card; **delayed → new press-notice state with Réessayer** (the frontend previously had no delayed handling); filed → Classé + saison reliée; the standalone supplément demoted to an "En marge" aside |
| Serial backend | Celery beat task (`*/15`) retries delayed episodes (idempotent claim, 6/day budget, `serial_episode_retry`/`episode_delayed` pilot events — the digest's failure counters are now real); after the last authored season the planner serves rotating authored "entre deux saisons" interlude beats instead of looping finales |
| QA seeder | French titles/copy throughout, current prompt version stamped (reader 409 gone), accents fixed |
| CI | `build:native` unwedged (`ALLOW_PLACEHOLDER_NATIVE_API` for the placeholder host) + `test:native-env` wired in |
| La Une streak | Idiomatic: "1ᵉʳ jour" / "N jours de suite" |

A Claude Design canvas with the proposed La Une "manchette" redesign (calm 4-block
composition, dark variant, two alternates) is published for the owner to refine:
see the "La Une — refonte" artifact. Implementation of whichever direction wins is
the next pass.

## 2026-09-02 — La Une « La manchette » implemented, buttons softened

Owner picked Option A on the canvas. `components/laune/LaUne.tsx` now composes the front
page from four blocks: folio · **LuManchette** (episode art + headline + byline, the day's
ask folded in — "À vous d'écrire : une réponse à Romy." / "À vous de jouer : la séance du
jour." — one meta line `concept · ~N min`, the because-line only on the first edition, the
honest overrun note, ONE pill CTA) · **LuEnBref** (three hairline rows: La séance · Le
lexique · Le cours, each a real tap target) · **LuDemain** as a one-line colophon under a
double rule. `LuPrescription`, `LuLead`, `LuSeance`, `LuLexique`, `LuErrata`, `LuCours` and
the MotsDuJour strip are gone from La Une (the day's words are counted in the lexique row
and dealt in the review deck; the CEFR block lives in Le Relevé).

**Buttons:** owner feedback — "too edgy, not soft enough." Primary actions are now pills:
`border-radius: 999px`, solid ink, 54px, sentence case, `letter-spacing: .01em`, weight 600,
`var(--t-body)`; secondary = outlined pill. Stamps, kickers, tabs and the bottom nav stay
sharp. Applied on La Une and swept across the other journal surfaces the same day.

## 2026-09-04 — Feuilleton: the two failures that made it "rubbish"

A live read of a freshly generated episode showed the story and the art are good; two
engineering failures ruined the experience:

1. **Superseded scenes bricked the tab.** `/serial/today` still handed out the episode's
   old `scene_id` after a prompt-version bump; the reader's scene fetch answered
   `409 feuilleton_scene_superseded` and the page spun forever. 66 of 83 scenes in the dev DB
   were stale versions — every legacy account hit this. Fix: `SerialThreadService.
   _supersede_incompatible_scene` (called from `today()` and `start_feuilleton_beat`)
   detaches a stale scene from an unread episode and sets it back to `available`, so the
   next open recomposes it; completed episodes keep their scene as history. The reader now
   treats a 409 as "recompose", never as a spinner (`loadInitial`, `openSerialSceneFromQuery`).
   Tests: `test_today_supersedes_incompatible_scene_on_unread_episode`,
   `test_today_keeps_incompatible_scene_on_completed_episode`.
2. **A 64 MB episode payload.** Six 1024² PNGs inlined as base64 (`GRAPHIC_NOVEL_IMAGE_STORAGE
   = data_uri` default) plus a second copy of each image inside `generation_metadata.seal_crop`,
   re-fetched by the reader's 3.5 s polling. Fixes: storage default is now `local` (files under
   `var/graphic-novel-images`, served at `/media/graphic-novel`; prod sets `s3`), panels are
   re-encoded as capped WebP on persist (`optimise_image`, Pillow — ~3 MB → ~260 KB), the panel
   serializer ships only a whitelist of metadata (`_public_generation_metadata`), the 174
   existing inline panels were backfilled and 42 seal crops re-pointed. Episode payload:
   **64 MB → 168 KB**. The web build proxies `/media/*` to the API (next.config rewrite) and
   the native build resolves it via `lib/media-url.ts`. Tests:
   `test_public_generation_metadata_never_ships_inline_images`,
   `test_optimise_image_reencodes_raster_panels_as_capped_webp`.
3. **La Une lead art.** The episode payload now carries `lead_image_url` (first printed
   panel), so the front page shows the actual episode art instead of the location plate.

The reader's presentation (P1 of the July audit: duplicated furniture, news kicker with no
news, per-panel kickers, the prompt printed three times, an English "YOUR QUEUE" vocabulary
dump with deck names, a counter bar) is being rebuilt in the same pass.

## 2026-09-04/05 — Feature-by-feature QA-and-fix pass

Owner mandate: "go through each separate feature completely and fix anything that is still
not working perfectly." One Opus agent per feature drove the real API as a learner (QA
account), read every state of the page, fixed what it found, and pinned it with tests.
Headline finds per feature:

| Feature | Worst finds (all fixed unless noted) |
|---|---|
| **Feuilleton** | Superseded scenes bricked the tab (409 → infinite spinner; 66/83 scenes stale) → supersede guard + reader 409 state. 64 MB episode payload → WebP files + metadata whitelist → 168 KB. Reader rebuilt per audit P1: one header, art + numeral + dialogue lines + additive caption per panel, one active task with the prompt said once, sentence-case teaser, no vocabulary dump, counter-free bar; 6,622 → 3,627 lines, one stylesheet; 13 regression tests. La Une shows the real first panel (`lead_image_url`). |
| **Le Studio** | Feature was dead: `/audio-session/start` 500 for every user (wrong SRS column names); gpt-5-mini reasoning starvation made every reply/opening canned and every detection empty; ElevenLabs 402 → no voice; `/end` not idempotent (double `plan_completed`); learners charged for Whisper punctuation/spelling and duplicate repairs. All fixed; French scenario copy; honest recap. Config note: `.env` sets `TTS_PROVIDER=elevenlabs` with a free key — falls back to OpenAI now, but the owner should set `TTS_PROVIDER=openai`. |
| **Le Lexique (review deck)** | Cards were permanently due (`mark_review` never moved `due_at`); rating order broken on new cards (Dur later than Facile, Easy never graduated); server-resolved gloss dropped by the schema (English learners saw the wrong side); fragile shelf refilled with cards just rated; cloze printed the answer when the blank failed; œ/æ and articles mis-graded; keyboard support; stale resume cache; whole biography sheet English. 6 new SRS tests. |
| **Les Cahiers** | Relevé "4/56" vs index "54": two legacy rows with `language='French'` escaped archival; learner notes silently overwritten by session provenance stamps; "Composer à l'Atelier" linked to the generic session (now seats the concept); English word sheet, English conjugation drill that was also orphaned (now linked); deck rows read the German column first; gloss language added to cache keys. Data debt reported: heuristic part-of-speech is wrong for ~11 % of -er/-ir words. |
| **L'Épreuve** | Transform items whose answer equalled their source (printing their own answer; a wrong rewrite graded 4.0) and 18 items whose answer key was a `source -> target` mapping (typing the real answer scored 0 and booked a lapse) — both now rejected by a shared validator on generation AND on cached sets; no-op errata dropped; "Lire Réviser maintenant" handoff copy; adaptive lock removed already-classed drills (stick ran backwards); empty errata answers graded wrong (now 422); errata task shipped `target_answer` with the question; phrase du jour published the uncorrected sentence and was filed under the UTC day; `repair_hint` computed but never rendered; failed relecture rendered nothing; blank sheet on a failed set; French concept titles inside the session payload and rule furniture. Open: ~30 deterministic corrector strings are English-only (a localization pass across en/de/fr). |
| **Le Courrier** | Six P0 corrector faults: hallucinated errata on correct French (whole-sentence "preferences", one deleting the mission's own Si-clause), invented replies with `[votre adresse]`, fabricated learner quotes persisted to error memory, "write more" typed as grammar, phantom "1 réparation enregistrée", penalties for target words never shown; debrief scored from the last turn only; English scenario/objectives/toasts; two primary CTAs. 15 new tests. Open: explanations occasionally come back French for a German learner (model behaviour), authored fallback erratum prose still English. |
| **Account surfaces** | Settings save returned 422 for every English-native account (`fr_to_en` missing from the direction literal — no preference could be changed); data export 500; hardcoded German direction options; doubled labels; dead "durée" slider; Tailwind palette panels unreadable in dark; system-dark `rgb` tokens never redefined; font-size control inert (6 % span). |
| **Cross-cutting** | Error-detector explanations were hardcoded German → now follow `native_language`. Anki deck rows whose `english_translation` merely duplicated the German gloss were nulled (5,388 rows) so the gloss resolver reports honestly. `/media/*` proxied on web, resolved against the API origin on native. |

## Still open (next passes)
- **Remaining English** in instructional-adjacent corners: review-card visual-cue badge
  labels (pinned by test_frontend_vocabulary_biography), mic/transcription failure toasts.
- **Anki dashboard** (`pages/progress.tsx`, off-nav): still dumps the global
  `vocabulary_words` table if ever relinked — scope to the learner's imports before any
  re-entry.
