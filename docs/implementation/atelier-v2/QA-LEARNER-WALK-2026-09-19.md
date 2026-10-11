# QA — a learner's first day, end to end (2026-09-19)

Walked as a brand-new German-native learner on the real stack (backend 8010 with
the OpenAI provider, frontend dev server on 3000, 390 × 844 phone viewport,
dark theme): landing → sign-up → sign-in → placement (5 questions) → Home →
the daily journey (read, listen-first, respond, resolution, summary) → Home
again → Feuilleton (season, reader, cast) → Courrier (one exchange) → Cahier
(Règles, Journal, Relevé) → Dossier → Lexique review → Réglages. Account
`lena.walk.20260919@example.com`, A2 declared, interests travel + food.
Spend ≈ US$0.10 (placement grading, one journey, one courrier turn, one
translation).

Everything below was seen on screen or in the network log. Items marked
**harness** were caused by the test browser (a hidden pane throttles
hydration to a crawl) and are not app bugs.

## Findings

| # | Where | What a learner sees | Cause | WP |
|---|---|---|---|---|
| F-02 | Sign-up | «Ouvrir ma première édition» lands on an **empty sign-in form**. The success toast is gone before it is read; the address must be retyped. | `signup.tsx` registers, then `router.push('/auth/signin')` — never signs in, never carries the address. | WP-47 |
| F-21 | Sign-up | Interest chips read `technology`, `business`, `travel`… on an otherwise French form; Réglages shows a different French list, so the two never agree. | Two vocabularies for one field (`interestPresets` English keys in signup, French words in settings). | WP-47 |
| F-11 | Réglages | «Gewählt: travel, food» prints raw keys under French chips. | Same as F-21. | WP-47 |
| F-03a | Journey / reader word help | Tapping a word with no dictionary entry pops a red English toast **«Resource not found.»** over the French sheet. | Global axios 404 interceptor; `lookupVocabulary` is not a silent request. | WP-48 |
| F-03b | Word help | The fallback sentence translation is **English** for a German learner. | `/atelier/translate` is French → English only; client calls `translateToEnglish`. | WP-48 |
| F-04 | Journey «Écouter d'abord» | The link is offered, the learner picks a prediction, and the next screen says «Audio ist für dieses Konto nicht eingeschaltet» — a dead end. Réglages also shows «Zuerst hören · an». | `ATELIER_EPISODE_AUDIO_ENABLED` is off; the client cannot know before the click. | WP-49 |
| F-27 | Journey | «Écouter d'abord» appears *after* the whole scene was read, then asks to predict how it ends. | The link sits on the reader's foot instead of before the first planche. | WP-49 |
| F-05 | Home eyebrow, journey header, summary, season list, dossier evidence | English world-bible location names inside French/German sentences: «Your apartment», «Romy's newsroom», «Ein Treffen … im Your apartment vereinbart». | `world_bible_paris_v*.json` names are English; `living_story` copies `location["name"]`. | WP-50 |
| F-06 | Home hero | «Dein nächstes Kapitel / Setze deine Geschichte…» in German on the French Home. | `describe_next` puts the native title into `title_fr`. | WP-51 |
| F-07 | Journey respond step | «Hilfe bereits genutzt: **hint**» — a raw internal key. | `JourneySteps` joins `assistance_used` values instead of their labels. | WP-51 |
| F-08 | Journey | German buttons beside French rows: «Tipp / Übersetzung / Antwort vorschlagen», «Weiter» after a verdict. | `help_*` keys and `action_continue` are not in `CHROME_KEYS`. | WP-51 |
| F-14 | Home after the journey | «Die heutige Szene ist erledigt.» with a **«Continuer»** pill that only reopens the summary. | Finished card reuses the `continue` label. | WP-51 |
| F-09 | Feuilleton › La saison | The episode row is titled with its resolution line («Rendez-vous demain 9h au newsroom; départ 11h; …») instead of «Une proposition imprévue». | `firstText(episode.hook_text, episode.title)` prefers the hook. | WP-52 |
| F-16 | Feuilleton | No `<title>`; the tab reads `localhost:3000/graphic-novel`. | Missing `<Head>`. | WP-52 |
| F-15 | Feuilleton › reader | Three 409s in the console on every engine episode open. | The reader probes the legacy scene route first. Harmless; left as is. | — |
| F-10 | Lexique review | Kicker leaks the Anki path «Mot du jour · Französisch 5000::1. FR → DE» and repeats «FR → DE». | `deck_name` printed verbatim next to the direction badge. | WP-53 |
| F-12 | Placement result | Sentence starts lowercase: «estimation raisonnable, sur 5 réponses…». | `confidenceLabel` is not capitalised at sentence start. | WP-54 |
| F-24 | Placement, journey | After every answer the next question / step opens **scrolled** by 80–120 px: the title sits half under the top edge. | State changes inside one page keep the previous scroll offset. | WP-54 |
| F-13 | Reader / journey | Punctuation breaks away from its word: «c'est rapide<br>. Tu me dis». | Every word is an inline-block `<button>`; a line may break between the atomic inline and the «.» run. | WP-55 |
| F-17 | Courrier | The German explanation for «je ne comprend» says «3. Person Singular fehlt ‚s'» (it is first person). | LLM explanation quality; corrector output is otherwise right. | note |
| F-18 | Feuilleton › season | Commitment reads «Le locuteur viendra demain…». | Generated commitment phrasing; prompt-level. | note |
| F-19 | Journey / reader | Every planche shows the same static apartment image. | Known: engine scenes use `existing-setting-art`; Codex holds `living_story.py`. | note |
| F-26 | Lexique | «exemplaire · verbe» with an example that does not contain the word; Home says «1 mot du jour», the deck holds 8. | POS/gloss data debt (known); Home counts the new-word slate, the deck adds due/new fill. | note |
| F-20 | Every page | `/api/auth/session` is requested 8–9 times per page load. | One `useSession` per component; dev-only cost is small. | note |
| — | Cahier › Règles | «Classement en cours…» for 20 s+ on the first walk. | **harness** — loads in 6 s once the pane is fronted; requests complete in < 250 ms. | — |
| — | Every route | 10–30 s spinners. | **harness** (hidden pane + first dev compile). Real waits: journey creation 25 s, placement grading 15–18 s/answer, `/atelier/today` 50 s the first time (three exercise generations rejected by the critic). | note |

What worked as designed: the placement ladder and its evidence sheet, the
journey's grading («Richtig, mit Hilfe», the story reply), the resolution and
summary, the Courrier corrector (one real repair, a good reply), Dossier,
Relevé, Journal's «revenez demain», Réglages in German (WP-46), the review
deck's flip and grades, the cast page, dark theme throughout.

## Work packages

- **WP-47 Onboarding hand-off.** After `register`, sign the learner in with the
  credentials they just typed and push them to the placement (the existing
  `afterSignUp` destination); if the sign-in fails, land on the sign-in form
  with the address prefilled. One shared interest list (`lib/interest-topics.ts`:
  key + French label) for the sign-up chips, the Réglages chips and the
  «Gewählt» line; stored keys stay English.
- **WP-48 Word help in the learner's language.** `lookupVocabulary` becomes a
  silent request (no global toast). `/atelier/translate` takes the learner's
  `native_language` (German, English, …), the client calls it as
  `translateForLearner`; the help sheet's label says which language.
- **WP-49 Listen-first only when it exists.** The scene step's prompt carries
  `audio_available` and `/users/me/settings` a read-only `episode_audio_enabled`;
  the journey hides «Écouter d'abord» and Réglages hides «Zuerst hören» when
  they are false. Moving the offer *before* the first planche (F-27) is left
  for when audio is switched on.
- **WP-50 French place names.** `name_fr` on every recurring location of both
  world bibles; `living_story` prefers it for `location_name`.
- **WP-51 Journey chrome.** `describe_next` sends the French title in
  `title_fr` (the objective stays native); `assistance_used` prints labels; the
  help chips and the post-verdict «Continuer» join the chrome keys; the finished
  card's action reads «Revoir».
- **WP-52 Feuilleton polish.** Season rows show the episode title first;
  `<title>` on the Feuilleton page.
- **WP-53 Lexique kicker.** Deck path reduced to its leaf, direction printed once.
- **WP-54 Scroll and copy.** Placement and journey scroll to the top on every
  question / step change; the confidence sentence is capitalised.
- **WP-55 Glued punctuation.** `.fr-word` renders `display: inline`, so a line
  never breaks between a word and its punctuation.

Notes only (no package): F-15, F-17, F-18, F-19, F-20, F-26 and the latency
figures — the first-day journey creation (25 s behind «Envoi…») is the one a
pilot learner will feel; WP-26 prefetch cannot warm day one.

## Results (same evening)

All nine packages implemented; see STATUS.md for the file-level summary.
Green: `tsc --noEmit`, `npm run lint`, thirteen node suites, and the backend
suites for placement, journey planner/API/state, living story, serial, atelier,
settings language and the frontend-scanning hooks (one order-dependent
`test_atelier` starter test fails only inside a long run). Verified live:
Home's finished card reads «Revoir»; the season row is titled «Une proposition
imprévue» with «avec Romane « Romy » Tremblay · Votre appartement»; the
Feuilleton tab is titled; `/users/me/settings` answers `episode_audio_enabled:
false`; the scene step carries `audio_available: false`; `/atelier/translate`
returns German for the German learner; the stored journey and the serial
archive both name «Votre appartement». Not walked in a browser (the hidden pane
stopped hydrating): the sign-up hand-off, Réglages topic labels and the hidden
listen-first row, the word-help sheet, the scroll reset, the Lexique kicker —
all type-checked and covered by the re-pinned tests. F-27 (offer the listening
mode before the first planche) stays open; with audio off it is not reachable.

## Second pass (same evening): the Séance rounds and the story's continuity

**Two Séance rounds, both complete.** The daily journey was walked in the
browser in the first pass (read → listen-first → respond → resolution →
summary). In this pass a second fresh account ran the whole journey through
the API on the fixed engine: create (13.5 s), scene, respond («Oui, c'est ma
clé !» → «Ah, c'est la tienne ! Voilà, je te la rends.», 11 s, outcome met),
resolution, finish with a recap and a serial episode filed. The legacy
«Plus de pratique» Séance was also played through the API: fill, classify,
word-bank, transform and produce attempts, one real erratum on «un grand
chaise» with a German explanation and repair hint, and a recap that schedules
the rule for 2 October. New defects from that round:

| # | Where | What a learner sees | Cause | WP |
|---|---|---|---|---|
| F-29 | Practice Séance › recognize round | Feedback in **English**: «You chose `petit`; this item requires `petite`. French nouns carry gender…», rule «Gender and number basics» — while the produce round and the recap explain in German. | The deterministic recognize corrector has English templates and uses `concept.name`; only the LLM corrections follow `native_language`. | WP-56 (labels done, sentences open) |
| F-30 | Practice Séance | An A2.2-placed learner is started on the A1 rule «Genre et nombre : les bases». | The legacy ladder does not read the placement estimate. | note |
| F-31 | Journey respond | A clean reply was rejected twice by the `inclusive_dot_form` guard because the model wrote «Le·la apprenant·e» in `understood_intent`, a private field — the learner gets a failed send. Seen by the owner on 09-19 and reproduced by the live review. | The guard scanned the private field. | WP-57 (fixed) |

**Is the Feuilleton coherent, or random?** Coherent, and fragile. The engine
keeps a chapter with a dramatic question, open commitments with the learner's
own words as evidence, witnessed events, and the last situations; every new
day's premise cites yesterday («Tu as dit que tu as du travail demain matin —
Lila hésite, mais insiste»). Two live six-day reviews at A2 today
(`var/reviews/atelier-story-review-A2-2026-09-19{,b}.json`, ≈US$0.06):

- Run 1 died on day 2 — the `understood_intent` rejection above (F-31).
- Run 2, after the fix: day 1 «Un petit dîner, une grosse question» (Marin
  rehearses an announcement at Le Mistral; the learner has work tomorrow), day
  2 «Lila propose un plan» (Lila picks up that exact constraint and offers a
  rehearsal tonight) — genuine continuity. Day 3 died: the critic rejected both
  drafts for inventing a reply from Gus that no one had spoken.
- The 14-day run of 2026-09-07 (`atelier-longitudinal-A2-turns.json`) shows the
  other failure mode: causally chained but **stuck** — one leaking radiator and
  the same plumber's deposit for fourteen days, the boxes wet from day 1 to 14.

So: not random nonsense, but a story that either loops on one problem or
aborts when two drafts in a row fail a guard. Both are engine-prompt matters
in `living_story.py`, which Codex holds uncommitted (its DIRECTOR diff targets
the «no storyline» loop). What landed here is the guard scope (WP-57) and a
recommendation: `ATELIER_STORY_MAX_ATTEMPTS=3` in production until the critic's
rejection rate is measured, because one rejected day is a learner's failed
Séance.

- **WP-56 Practice Séance in the learner's language.** Done: every
  learner-facing rule label reads the French `title_fr` (`_concept_label`).
  Open: the recognize/fill/classify «why» sentences and grammar-profile
  principles are English templates (≈40 strings in `atelier.py`); either route
  them through the correction model like the produce round, or author de/en/fr
  variants.
- **WP-57 Guards judge what the learner reads.** `inclusive_dot_form` checks
  `reply_fr` and `resolution_fr`; a dotted form in `understood_intent` is
  scrubbed, not fatal. Test re-pinned in `tests/test_living_story.py`.

## Third pass: the loop and the abort (WP-58)

Both fixed at the engine, see [WP-58-STORY-SHAPE.md](WP-58-STORY-SHAPE.md).
The loop: chapters are now four-scene arcs that must reach a resolution beat,
a new chapter cannot reuse the last one's problem, and the season arcs and
character secrets the bible authored finally drive the chapters. The abort: a
refused turn settles an honest authored ending instead of a failed send, and a
refused scene retries or serves the prefetched one. Live A2 run on the new
engine (`atelier-story-review-A2-2026-09-19c.json`): day 1 opened «Rester ou
partir ?» anchored in the `user_settling_in` arc, day 2 reached for Marin's
ring (`marin_proposal`) — the depth material is reaching the page; the run
itself stopped on a transient OpenAI failure that production would have
absorbed with the fallback, and it exposed the actor closing a chapter after
one scene, now gated on the beat.

**Final live reading (`atelier-story-review-A2-2026-09-19g.json`, six days,
≈US$0.06):** six of six days accepted, no authored fallback, two provider
timeouts absorbed by the retry. Chapter 1 «La tension Romy» ran setup (a look
held too long at Le Mistral, a café promised for ten o'clock) → complication
(the scripted refusal; Romy «un peu déçue, mais je comprends») → turn (she
says she may go back to Canada; the learner promises to keep seeing her) →
resolution (a walk with Marin who offers to stand by the learner). Chapter 2
opened on a new problem in the `marin_proposal` arc: the ring in the pocket,
Lila painting downstairs, and on day 6 Lila coming home early with her hand on
his coat. Commitments were recorded from the learner's own words on days 1, 3,
4 and 5. One slip caught by reading, now guarded: «Tu n'es pas seule» to a
neutral learner (the agreement guard watched only «tu es»).

## Fourth pass: B1/B2/C1 and the loop (WP-59)

B1 and B2 four-day live runs on the WP-58 engine were stable (4/4 each) but
level-false: every objective «in one sentence», every life opening on Romy
with Montréal by day 3, a B2 reply with «prêt(e)». WP-59 fixes those at the
engine (see its handoff) and the seeded B1 rerun opened on Lila's envelope
with move-shaped objectives, 4/4. C1 is now a band; no C1 live run yet.
