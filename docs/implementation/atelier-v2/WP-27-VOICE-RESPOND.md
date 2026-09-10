# WP-27 — speaking as the default output

**2026-09-10.** The daily journey's respond beat now opens on «Parler». The
learner speaks, the recording is transcribed by the existing stateless
`POST /audio/transcribe`, the transcript lands **in the answer field**, and the
learner sends it through the same respond call with `mode: 'voice'`.

## The owner decision this package is built on

**No pronunciation scoring, ever.** Speech is turned into text and graded
exactly like typed text. Nothing in this path measures, scores or describes how
a sentence sounded, and the French hint on screen says so to the learner:

> Dites votre réponse à voix haute. Nous la transcrivons — rien ici ne juge
> votre prononciation.

`test_no_pronunciation_scoring_exists_on_the_journey_voice_path` fails if a
later package adds a score field to any file on this path.

## What changed, and why

### 1. The transcript is a draft, not a submission

The previous voice path (in `useDailyJourney.ts`) sent the transcript the
instant it arrived. A misheard word therefore became a wrong answer the learner
never saw coming, and the grading was of a sentence they never wrote. Now the
transcript fills the answer field under «Ce que nous avons entendu», with
«Corrigez ce qui a été mal compris, puis envoyez.» — the learner presses Send.

Correcting a transcription error does **not** demote the answer to typed:
`submittedMode()` keeps `voice` for as long as the spoken sentence is still
there, and falls back to `text` only when the field has been emptied.

### 2. Voice is the default, text is one tap away and remembered

`voice-answer.ts` holds the preference: `atelier.journey.answer-mode` in
`localStorage`, defaulting to **voice** whenever the server offers voice for the
step. «Écrire plutôt» writes `text` and is honoured on every later turn. The
first render deliberately agrees with the server (voice when offered) and the
stored preference is applied in an effect, so a text-preferring learner gets no
hydration mismatch.

A step whose `input_modes` do not include voice is text from the first frame,
unchanged.

### 3. Five honest states, no dead ends

| State | What the learner sees |
|---|---|
| recording | «Arrêter» on the primary, plus a live notice |
| transcribing | the primary goes pending with «Transcription…» |
| transcription failed | «Cet enregistrement n'a pas pu être transcrit. C'est toujours votre tour.» |
| permission denied | dropped onto the written path, explained **once** in French, and the preference remembers the device's answer |
| unsupported device | same, with its own sentence |
| offline | said **before** recording — transcription is a network call, and recording first would waste the sentence |
| empty recording | «Rien n'a été enregistré. C'est toujours votre tour.» |

None of these is ever a wrong answer, and every one of them leaves the turn
open with the written path available.

### 4. The capture hook cannot submit

`useVoiceAnswer.ts` owns `getUserMedia`, `MediaRecorder` and the transcription
call, and has no access to `submitAnswer` at all —
`test_the_transcript_is_never_submitted_by_the_microphone_itself` pins that. It
lives beside `useDailyJourney.ts` rather than inside it because that file is
under a concurrent lease; the controller's own (now unused) voice fields were
left untouched for the same reason and can be removed by their owner.

## Backend

Nothing about grading needed to change, and nothing did. `mode: 'voice'` and the
transcript already flow through `AttemptAnswer` → `classify_observation` →
`TargetObservation.modality` / `learner_text` → `journey_capabilities`, which
reports a capability as demonstrated in voice only when a voice observation
actually backs it. A voice attempt that carries no text is already treated as an
infrastructure failure, never a learner mistake.

What was missing was the money. `POST /audio/transcribe` is now a paid endpoint
on the learner's main path and had **no cost telemetry at all**:
`PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD` did not cover it and `pilot_digest`
had nothing to print. `app/services/transcription_cost.py` writes one priced
`audio_transcription` row per successful call, with the `surface` that produced
it (`journey_respond` for the journey).

**The cost is an estimate and every row says so.** Whisper returns neither a
duration nor a usage block, so the row is priced from the upload size against a
written-down bitrate (`ASSUMED_BYTES_PER_SECOND = 4000`, `USD_PER_MINUTE =
0.006`), capped at five minutes, and carries `estimated: true` plus its
`cost_basis`. The digest line repeats it: *"estimated from upload size, not a
provider bill"*. A modelled cost printed as a bill would be worse than no line;
a `0.0` would read as free.

## Tests

* `web-frontend/components/atelier-v2/journey/journey.test.js` — the pure state
  machine including all five failure paths, the French chrome, the remembered
  preference, and the whole device path driven through the real component with a
  fake `MediaRecorder`: record → transcript in the field → edit → submitted as
  `{ mode: 'voice' }`. Plus the refusal path (text field appears, preference
  written, explained once, in French) and the offline path.
* `tests/test_wp27_voice_respond.py` — 12 tests: voice and text observations are
  identical but for the modality, the transcript is what the evidence keeps, the
  priced row and its declared basis, the digest line, and source scans for the
  written fallback and the absence of pronunciation scoring.
* `tests/test_audio_story_regressions.py` re-pinned for the endpoint's new
  ledger dependency: the oversized upload writes no row, the real call writes
  exactly one.

## Not done

* **The iOS simulator walk was not run.** A meaningful walk needs the fake-provider
  backend, a native rebuild and a sign-in, and the mic-denied path is the one
  the simulator can actually show. The refusal path is covered by a test that
  drives the real component through a rejecting `getUserMedia`, but that is not
  a device proof. Worth 20 minutes on the next device pass.
* The controller's dead voice fields (`VoiceState`, `startRecording`,
  `stopRecording`, `resetVoice` in `useDailyJourney.ts`) are still exported and
  now unused; removing them belongs to that file's owner.
* Live model/STT spend for this package: **US$0.00** — every test runs against a
  fake recorder and a stubbed transcription call.
