# Engine/frontend coordination — active, 2026-09-06

Engine owner is implementing backend, prompts, shared API services/types and backend tests. Frontend owner retains all presentation, page and reader interaction files. Do not edit the engine-owned files in parallel.

## Integration being implemented

- Existing daily-journey create/resume/help/attempt/advance/finish calls remain the mutation authority.
- `scenario_key` becomes an opaque string, independent of the three known capability keys. Do not switch rendering on those three values.
- Scenes remain pinned. New narration and replies require AI; unavailable generation returns the existing unavailable/pending states, never canned dialogue.
- `GET /api/v1/story-engine/episodes` lists owned generated episodes (no generation or completion on GET).
- `GET /api/v1/story-engine/episodes/{id}` returns the same episode's ordered panels, title, status, chapter, scene_id, journey_id, and resume position. Each panel has stable id/index, narration_fr, dialogue [{character_id,text_fr}], image_url and image_status. Image assets may be reused as clearly identified setting art; no claim of a newly generated illustration.
- `PUT /api/v1/story-engine/episodes/{id}/position` with `{panel_index: number}` saves position only. Reading, back/next navigation and word help never advance canon or apply learning credit. Negative/out-of-range indices fail validation.
- Responses are learner-owned. Pending story/rubric/model details remain server-private. Episode panels contain published scene content only; generated endings are exposed only after the conversation actually resolves.
- Continue/respond by `journey_id` through the daily API, using its actual active step and revision. Do not build a second conversation controller/state machine.
- Existing legacy scene routes remain compatible. New generated episodes use the same SerialThread/SerialEpisode spine. Full contract examples and verification will be added after integration tests.

Production stays default-off under the existing daily-journey flag/cohort. Existing active authored journeys may finish; new production journey content uses the AI engine. Test fixtures may explicitly exercise the legacy authored path.

## Ready for frontend integration — 2026-09-06

The routes and shared TypeScript methods above now exist and pass assembled API tests. Import `getStoryEpisodes`, `getStoryEpisode`, `getStoryEpisodeForJourney`, and `saveStoryReadingPosition` from `services/daily-journey`, or call the same methods on `apiService`.

1. On a daily journey's scene step, call `getStoryEpisodeForJourney(journey.id)`. It uses `GET /story-engine/episodes?journey_id=UUID`, scoped to the authenticated learner; absent/legacy content returns null. Render returned panels in the existing immersive reader. Do not assume a serial episode id is a scene id: an active legacy episode can have a generated daily side scene.
2. At the end of the panels, continue through the existing daily journey controller. Recall steps may precede the response. Resolve the actual `current_step_id`; never manufacture a respond request from the reader's panel index.
3. Bind Next/Previous to local stable panel IDs and persist the selected index with `saveStoryReadingPosition`. That PUT does not increment the daily revision. Restore server position on another device. A completed or abandoned scene is replay-only.
4. Query `getStoryEpisodes(before?)` for the archive. The page holds up to 20 rows and a `next_cursor`. A scene's title, chapter, ordered panels and generated ending come from this API. `resolution` is null until an actual exchange settles it.
5. For engine-managed learners, `/serial/today` includes `story_engine`, `continue_href: '/atelier'` and `episodes_href`. With an available current episode it retains the episode descriptor. Without one it returns `status: 'journey_required'`, `kind: 'feuilleton'`, `scene_id: null`; do not keep polling for background legacy generation. `/graphic-novel/today` places those links in `recommendation` and does not offer a separate scene generator.
6. Legacy create/attempt/complete calls refuse new engine scenes with 409 `story_journey_required`. Legacy GET of an engine scene returns 409 `story_episode_route` with its `episode_href`. Handle these as a route transition, not a superseded scene to regenerate. The shared reader API is the preferred initial lookup.
7. The reader labels `image_status: 'setting_reference'` honestly. Reused location art is not a newly generated illustration. Keep readable panels if an image is absent.

The backend does not provide a scheduled next-release date or an eight-minute reading estimate. Omit them. Production is still disabled; use a disposable dev account and explicit cohort configuration for integration, with an injected provider for ordinary tests.

## Combined-suite failures for the frontend owner

The full backend pytest command also scans frontend source. The following assertions fail after the parallel UI migration; assess the behavior and update appropriate tests rather than reintroducing rejected design components:

- `test_atelier_honest_edition.py`: prescription budget prop, studio reply-mode prop, two raw pixel font sizes in `Feuilleton.tsx`.
- `test_core_mobile_edge_flows.py`: old `<LuNotice>` recovery markup.
- `test_frontend_atelier_phrase_of_day.py`: removed phrase-of-day row.
- `test_frontend_atelier_thread.py`: old La Une styles and mission prop (two failures).
- `test_frontend_pilot_experience.py`: old `<LuManchette>` prescription component.
- `test_frontend_serial_surfaces.py`: old archive copy and `<LuEnBref>` row (two failures).
- `test_frontend_vocabulary_biography.py`: vocabulary entry expected inside `<LuEnBref>`.

Recovery, studio reachability, honest duration and vocabulary entry are behavioral requirements even when their old component-name assertions become obsolete. The engine owner has left the frontend owner's files untouched.

## Verified in a browser — 2026-09-06 (evening)

Points 1–7 above were walked on the authenticated `/atelier` route against `scripts/dev_story_engine_server.py` (fake provider, throwaway PostgreSQL). Reader, position save/restore, continue through the daily controller, 409 route transitions and the archive all behave as specified; see ENGINE-IMPLEMENTATION.md for the run log.

**Additive field:** each `panels[].dialogue[]` line now also carries `character_name` (display name from the world bible, or `null`). Prefer it over any client-side id→name table; `character_id` is unchanged.

**For the frontend owner — one blocking defect:** after the last `advance` the controller auto-finishes with the pre-advance revision (`useDailyJourney.ts`, `continueJourney` → `finish`), gets 409 `journey_version_conflict`, and leaves an empty "Step 3 of 3" screen with no retry. Details in ENGINE-IMPLEMENTATION.md. Reproduce with `.claude/launch.json` → `backend-story-fake` + `web-frontend`, sign in with any account registered against that backend, Start today, Next ×2, Continue, Send any French sentence, Continue, Continue.
