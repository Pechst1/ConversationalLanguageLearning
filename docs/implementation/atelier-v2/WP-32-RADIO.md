# WP-32 — Radio feuilleton: the listening-first episode

Spec: [INNOVATION-WORK-PACKAGES-2026-09-10.md](INNOVATION-WORK-PACKAGES-2026-09-10.md) §3
(WP-32), items 1–3. Delivered 2026-09-10.

## 1. What the evidence actually says, and what this package therefore is

Audio is not the intervention. Metacognitive listening instruction —
**prédire → écouter → vérifier → retenir** — carries a consistent moderate
effect and the largest one for the *weakest* listeners (Vandergrift &
Tafaghodtari 2010; Vandergrift & Goh 2012). Handing a learner a play button and
the same page is the audio-only condition, which is the arm that does least.

So the package is the cycle, and the state machine refuses to let anyone skip
part of it:

* **No listening without a prediction.** `listen` from `predire` with no guess
  is a no-op — the audio button is disabled until the learner has committed.
* **No verifying without having listened.** `verify` needs `heard`. Otherwise
  the *vérifier* stage is just reading, and the guess was never tested.

The honest exception is failure: `heard` is also set when the audio *cannot* be
played, so a provider outage or a muted device degrades to reading the lines
rather than to a dead end. The machine refuses to invent progress; it never
traps anyone behind a working speaker.

## 2. The four stages

| Stage | What the learner does | Where it comes from |
|---|---|---|
| **prédire** | Taps one of two French guesses about how the exchange ends | `buildEpisodeGuesses(episode)` — deterministic, from the episode's own cast. **No model call.** |
| **écouter** | Plays the episode; the words stay hidden, the speaker's *name* does not | `episodeListenLines` + the synthesized clips, one voice per speaker |
| **vérifier** | Sees whether the guess held, with the deciding line quoted; turns lines over one by one | `verifyEpisodeGuess` against the scene's stored outcome |
| **retenir** | One French line: what to listen for tomorrow | `episodeRetainPhrase` — the deciding phrase, else the shortest full character line |

**The guesses.** The counterpart is the first non-learner speaker — the person
the scene's objective is aimed at. With no named counterpart the guess is
impersonal («La personne en face…») rather than a made-up name: this module
never synthesises a character. The two options are «X dit oui.» and «X refuse ou
propose autre chose.», in French in every control language, because the learner
is about to listen to French and a guess phrased in German is a different task.

**The verification** reads, in order, the server's own `resolution.text_fr`
when it has published one, then the dialogue from the end backwards (narration
is skipped — "Romy hésite" describes a beat, it does not answer the question).
Markers are a closed, auditable list matched on folded text, not a classifier:
at A1–B1 the endings this engine writes are short and formulaic, and a *wrong*
verdict at the one stage meant to settle things is worse than no verdict. A line
carrying both («Oui, mais malheureusement…») decides nothing on its own, and an
episode whose lines settle neither way comes back **`unresolved`** — stated to
the learner as «La scène ne tranche pas : aucune des deux prédictions n'est
fausse.»

## 3. Comprehension is measured, never marked

`record_prediction_check` stores `{guess, verdict, supported}` in
`scene.source_snapshot["radio"]` — beside the reading position, which is where
the reader already keeps things true about the learner's *passage* through a
scene — plus a free `episode_audio_prediction` pilot row.

It is deliberately **evidence-adjacent, not evidence**:

* it never reaches `DailyJourneyStep` or the capability rubric. A tapped guess
  is not production, and the product has one rubric. Two rubrics is exactly how
  `recap.capability_evidence` and `GET /capabilities/progress` once came to
  disagree about the same journey (CONTRACTS §8). An **AST scan** in
  `tests/test_episode_audio.py` fails the build if `episode_audio.py` ever
  imports or touches those names;
* it never appears as a mark. There is no score in the response, no «juste /
  faux» on screen, and the `ChoiceList` verdict words are wired to the neutral
  «choisi» rather than to the correct/wrong pair;
* an `unresolved` scene is stored as unresolved rather than silently dropped.
  The denominator matters as much as the numerator.

The second half of the measurement is the one this package does not own: the
next scene's respond evidence, which already exists.

## 4. Synthesis, the cache, and the money

`app/services/episode_audio.py`. Order of refusals, cheapest first:

1. **The flag.** `ATELIER_EPISODE_AUDIO_ENABLED` (new, **default false**) gates
   the first line, not the last: nothing is read, nothing is called, nothing is
   billed, and the caller gets `status: "disabled"` — which the page renders as
   the ordinary text scene.
2. **The cache.** `scene_revision(lines, model=…)` digests the exact text,
   speaker, voice, order and TTS model. A regenerated scene, one corrected line
   or a changed model is a new revision; `(scene_id, revision, line_key)` is
   unique, so a replay finds the rows and makes **no call and no cost row**.
   Nothing ever plays yesterday's recording under today's words.
3. **The budget.** `FEUILLETON_AUDIO_MAX_CHARS_PER_SCENE` cuts **whole lines**
   and the manifest declares `truncated`. Half a spoken sentence is worse than a
   missing one, and a learner is never told they heard an episode they did not.
4. **Only then a provider.**

**Provider pinned to OpenAI** (`TTS_PROVIDER = "openai"` in the module).
The deployed configuration names ElevenLabs, whose plan answers 402. Every other
TTS call site degrades to OpenAI *after* a failed request; on the learner's
daily path that is a wasted round trip and a silent character. `.env` was not
touched — changing the default provider is a configuration decision, and this
constant only records which path the feature was tested on.

**The price is an estimate and every row says so.** The speech endpoint returns
audio and no usage block, so — exactly as `transcription_cost.py` does for
Whisper — the row is priced from the character count against
`FEUILLETON_AUDIO_COST_USD_PER_1K_CHARS` and stamped `estimated: true` with
`cost_basis` beside it. One `episode_audio_synthesis` row per run that actually
synthesized something; a run served entirely from cache writes **nothing**,
because a zero-cost row reads as a free call rather than as no call at all.

**Silence is a state, not a half-episode.** If any line fails, the run is
`failed` and the manifest carries **no clips**: half a scene played aloud is a
comprehension test nobody can pass. Whatever was synthesized before the failure
stays cached and is billed on a `status: "failed"` row, so the retry pays only
for what is still missing.

Voices: `fable` is reserved for the narrator; five voices carry the cast, pinned
by the id's first token so `marin_leveque` and `marin` are one person and a
generated cast member hashes to a stable voice rather than being round-robined.
Five voices and an open cast means two characters can share one — which is why
the écouter stage shows the speaker's **name** while hiding their words. The
voice is a cue, never the only carrier of who is talking.

**No pronunciation, anywhere.** WP-27's owner decision is product-wide, and
adding audio is exactly the moment someone would be tempted to score an accent.
A copy scan in the node suite fails on `pronunciation` / `prononciation` /
`Aussprache` / `accent` in any of the three languages.

## 5. The wire

| Route | Does |
|---|---|
| `GET /story-engine/episodes/{id}/audio` | The cached manifest. **Never starts a paid call.** `disabled` / `absent` / `empty` / `ready` |
| `POST /story-engine/episodes/{id}/audio` | Speak it, or say honestly that it is not spoken. Idempotent by revision, row-locked |
| `GET /story-engine/episodes/{id}/audio/{clip}` | One line as `audio/mpeg`, `private, max-age=86400, immutable` |
| `POST /story-engine/episodes/{id}/audio/prediction` | Record the check. No score comes back |

Ownership, the engine-version filter and the 404 all come from
`story_engine.owned_scene` **by import**, so there is exactly one definition of
"a scene this learner may read" and the audio can never address a scene the
reader cannot. A clip is authorised through its scene, not through its own
`user_id`, so it cannot outlive that permission.

Clips are fetched as blobs rather than handed to `<audio src>`: the route is
bearer-authenticated and an audio element cannot carry a header.

## 6. Files

Backend: `app/services/episode_audio.py`, `app/db/models/episode_audio.py`,
`alembic/versions/907eb914c502_add_episode_audio_clips.py` (+ the merge
`79e0beb6c84b`, §10),
`app/api/v1/endpoints/episode_audio.py`, one flag in `app/config.py`, one router
line in `app/api/v1/api.py`, one model export in `app/db/models/__init__.py`,
two table registrations in `tests/conftest.py`.

Frontend: `story-episode-model.ts` (the cycle, the guesses, the verification,
the remembered preference), `useEpisodeAudio.ts`, `EpisodeRadio` in
`StoryEpisodeReader.tsx`, the mode switch in `StoryEpisodeStep.tsx`, 36 new copy
keys in `journey-copy.ts` (fr/en/de), four additive calls in `services/api.ts`.

Tests: `tests/test_episode_audio.py` (16), `tests/test_episode_audio_api.py`
(9), `components/atelier-v2/journey/episode-audio.test.js` (19, wired as
`npm run test:episode-audio` and into the CI node block).

`llm_service.py` was **not** edited: `LLMService.text_to_speech(text, voice,
model, provider)` already existed and is called through the `Synthesizer`
protocol, which is what the fake in the tests implements.

## 7. Opt-in, and what happens when it is off

`atelier.journey.listen-first` in `localStorage`, same pattern as
`voice-answer.ts`'s `INPUT_MODE_KEY`. **Default off**, deliberately: listening
first is the harder way to meet a scene, and the evidence assumes a learner who
opted into the cycle. Handing the hardest condition to people who never chose it
is how a good idea gets measured as a bad one. A blocked or private store is the
default, never a crash.

With it off, `StoryEpisodeStep` behaves exactly as before and **nothing
audio-shaped is reached** — no manifest read, no synthesis, no request of any
kind. That is pinned by a server render in `episode-audio.test.js` that asserts
the transport recorded zero calls. The offer sits *under* the reader, not in
front of it, and says what the mode costs before it is chosen. «Lire la scène»
is one tap away from every stage of the cycle.

## 8. Verification

* Backend `tests/test_episode_audio.py` + `tests/test_episode_audio_api.py`:
  **25 passed**. Full suite: see STATUS.
* Frontend: `test:episode-audio` **19 tests, 19 pass**; all twelve other node
  suites green; `type-check`, `lint` and `next build` clean.
* Migration rendered offline against PostgreSQL (`alembic upgrade
  e48fd9624811:907eb914c502 --sql`) and exercised against SQLite through the
  test suite.
* **US$0.00 — no live TTS call was made.** Every test uses a fake synthesizer
  that counts its calls; the US$0.20 live-call budget was not drawn on. This is
  also the largest open item (§10).
* **Not walked on the simulator**, and not verified in a browser: the preview's
  auth gate cannot render an authenticated journey step.

## 9. Hooks owed

Nothing is blocked; these are the seams other leases own.

1. **`web-frontend/services/daily-journey.ts`** (not leased) — the typed facade
   the other journey modules use. `useEpisodeAudio.ts` and `StoryEpisodeStep.tsx`
   import `apiService` directly to stay inside the lease. Add:

   ```ts
   export const getEpisodeAudio = (sceneId: string) => apiService.getEpisodeAudio(sceneId);
   export const synthesizeEpisodeAudio = (sceneId: string) =>
     apiService.synthesizeEpisodeAudio(sceneId);
   export const getEpisodeAudioClip = (sceneId: string, clipId: string) =>
     apiService.getEpisodeAudioClip(sceneId, clipId);
   export const recordEpisodePrediction = (
     sceneId: string,
     body: { guess: string; verdict: string; supported?: string | null },
   ) => apiService.recordEpisodePrediction(sceneId, body);
   ```

   …and switch the two imports over. Behaviour-neutral.

2. **`pages/settings.tsx`** (WP-31's lease touched it last) — «Écouter d'abord»
   is currently only offered under the reader. One row in Réglages reading the
   same `LISTEN_FIRST_KEY` would let a learner turn it on without meeting a
   scene first.

3. **`scripts/pilot_digest.py`** — two event types to print:
   `episode_audio_synthesis` (spend per listening learner, and the
   cache-hit rate, which is the number that says whether this is affordable) and
   `episode_audio_prediction` (`confirmed / other / unresolved` counts). The
   prediction line is the package's success metric, alongside the next scene's
   respond evidence.

4. **`app/services/journey_latency.py`'s prefetch beat** — synthesis is ~1 s per
   line on `tts-1-hd`, which lands on the learner's *écouter* tap. If the
   listening cohort grows, a `synthesize_episode_audio` call inside the existing
   prefetch (flag- and cohort-gated exactly as the scene draft is) would make
   the tap instant. Not done here: the beat is not this lease's, and a warm
   cache for a learner who never listens is money burnt.

5. **Retention** — clips are never deleted. A `graphic_novel_scenes` row taking
   its audio with it is handled by the FK cascade, but nothing prunes audio for
   scenes that stay. At ~30 kB × ~8 lines × one scene a day that is ~90 MB per
   learner-year; a monthly prune of clips whose revision is no longer current
   belongs with whoever owns retention.

## 10. Open items

* **The pedagogy is built and its ingredients are unproven.** No live TTS call
  was made, so nothing here has been *heard*: the voices have not been listened
  to at A1 speed, and the deciding question — whether `tts-1-hd`'s French is
  intelligible enough for the listen stage to be a comprehension task and not a
  guessing game — is unanswered. It needs the same kind of bounded paid run
  WP-25's ladder is waiting on. The US$0.20 budget is untouched.
* **The verification's reach is narrow and honest about it.** The marker lists
  cover the formulaic endings this engine writes at A1–B1. A more elaborate
  scene returns `unresolved`, which is correct but uninformative; the fraction
  of episodes landing there is the first thing to read off the digest, and if it
  is high the answer is a scene-side `outcome` field in `source_snapshot`
  (living_story's lease), not a classifier here.
* **The prediction is a two-way choice**, which is generous: a coin flip scores
  50 %. It is measurement, not marking, so this costs nobody anything — but the
  digest must not report it as an accuracy rate without saying so.
* **The migration branched, and is merged.** WP-30's `c7d8e9f0a1b2` (journal)
  landed on the same parent as this package's `907eb914c502`, so the committed
  tree had two heads. `79e0beb6c84b` merges them; it has no operations, because
  `journal_entries` and `episode_audio_clips` are independent additive tables.
  The committed tree now has a single head. **WP-34 owes one line**: its
  untracked `3759e1c7098c` chains onto `907eb914c502` and will read as a second
  head once committed — re-point its `down_revision` to `79e0beb6c84b`.
