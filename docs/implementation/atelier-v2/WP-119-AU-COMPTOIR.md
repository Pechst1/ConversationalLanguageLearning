# «Au comptoir» v1: the Papier's new goal (WP-119)

Owner decision, 2026-10-19: Vincent chose «Build it» for the concept page published at
https://claude.ai/artifact/N9v75qwPAgTdcMutLrRjXp (the page's source, with the six mock screens, is
`scratchpad/mock/au-comptoir.html`). This spec turns that page into a buildable v1. Where this spec and the
mock disagree, the mock wins on look and the spec wins on behaviour.

## The pitch, in one paragraph (from the mock, keep this framing in UI copy)

Every morning the regulars at Le Mistral argue about one news story. Romy is writing a vox pop
(«micro-trottoir») for her paper and she is one voice short: yours. You read what happened, hear three
opinions, catch the one claim that is false, and say what you think. Romy edits your sentence like a
journalist, a friend answers you back, and your quote is printed next to theirs.

## Why (what this replaces)

The chat-based Papier gives the learner nothing to do except ask Romy questions; the characters are neutral;
the writing task is hidden until turn ~11 of 14; and the screen is crowded. The comptoir is five short
screens, one main button each, the end always visible, and real opinions.

## Scope of v1

In: the takes desk (shared, one call per story each morning), the five-screen player replacing the chat when
the switch is on, Romy's edit plus one answer per learner, «La page» at the close (into the Relevé), the Une
card's «question du jour», evergreen takes shipped with the evergreens, tests, a local walk at A1/A2/B1 in EN
and DE with screenshots.

Out (phase 3, do not build): characters remembering your side the next day, rivalries/allies, «Mes avis» in
the Relevé, aggregate votes of all learners, errata memory from Romy's edit (unless trivially available, see
§6.5).

## 1. The switch

- `REVUE_COMPTOIR_ENABLED: bool = False` in `app/config.py`, next to the other `REVUE_*` settings, with a
  description in the same style. Off: nothing changes anywhere (no route, no field, no morning call).
- `REVUE_COMPTOIR_MODEL: str` for the takes desk (see §2.4 for how the default is chosen).
- On: a new session starts in comptoir mode when its dossier has usable takes (§2); otherwise in chat mode, as
  today. A session keeps the mode it started with for its whole life (resume replays it). An active chat
  session started before the switch resumes as chat.
- The mode is recorded on the session's first `choice` event (`mode="comptoir"`) so replay can derive it.
- `RvSessionView` gains `mode: "chat" | "comptoir"` (default "chat") and `comptoir: RvComptoirView | null`.

## 2. The takes desk (shared, morning)

New module `app/services/revue/comptoir.py`, modelled on `leads.py` (spec string, rules, `write_*`,
`repair_*`, `ensure_*`, called from `app/tasks/revue.py` after `leads_now`, only while the switch is on).
Start from the prototype prompt in `scratchpad/takes/takes_desk_v2.py` (it already produces in-character
takes: «Voyons donc», «mon costume réclame le silence», «C'est un signe, ça»), and its findings:

- The default model's takes are usable but sometimes stiff; `claude-sonnet-5-5` was livelier but once
  returned two JSON objects back to back (parse with `json.JSONDecoder().raw_decode` on the first `{`) and
  once invented an intox that was not a changed fact. The checks below catch both.
- The prototype's `intox:missing_in:a1` failures were mostly a check bug: `fold` does not lowercase, so
  «Un million…» did not match «un million…». Compare case-folded.

### 2.1 Stored shape

`EditorialDossier.comptoir: ComptoirTakes | None = None` (in `dossier.py`, next to `StoryLeads`, same
`_Model` conventions). The session snapshot of the dossier then carries it, like `leads`.

```
ComptoirTakes
  question: Tr                      # «Céline revient en 2027. Bonne nouvelle ?» ≤ 9 words, yes/no, «oui» = pour
  guests: [ComptoirGuest] × 3       # in seat order; stances exactly {pour, contre, nuance}
  intox: ComptoirIntox | None
  reasons: {pour: [Tr]×3, contre: [Tr]×3, nuance: [Tr]×3}   # A1 tiles; each completes «parce que …», ≤ 5 words
  frames: {pour: Tr, contre: Tr, nuance: Tr}                 # A2 frame, ends before the reason:
                                                             # «À mon avis, c'est une bonne nouvelle, parce que»
  bank: [Tr] × 6                                             # A2 word bank («sa voix», «les fans», «trop cher»)
  phrase: {a1: Tr, a2: Tr, b1: Tr, b2: Tr}                   # the phrase of the day per band
  replies: {pour: Reply, contre: Reply, nuance: Reply}       # the counter-line when the learner takes that side
  model: str, written_at: datetime, prompt_version: str

Tr = {fr: str, en: str | None, de: str | None}
ComptoirGuest
  id: cast id; stance: "pour" | "contre" | "nuance"
  take: {a1: Tr, a2: Tr, b1: Tr}     # B2 reads b1
  quote: Tr                          # ≤ 8 words, the line printed on «La page»
ComptoirIntox
  by: cast id (one of the guests; prefer augustin_de_roncourt, who lies by reflex)
  wrong_fr: str      # 2–6 words, inside that guest's take at every band where intox is on
  right_fr: str      # the true value, found in claim_id's French
  claim_id: str
  distractor_fr: str # another true value from the claims, same kind (a number for a number), for the A1–A2 pick
  ask: Tr            # «Combien de spectateurs, en vrai ?»
  caught: Tr         # the liar's admission, in character: «Cinq cent mille, un million… Je suis généreux avec les chiffres.»
  bands: ["a1", "a2", "b1"]   # where the check found wrong_fr in by's take; the intox step runs only there
Reply = {by: cast id whose stance differs, line: Tr, comeback: Tr}
  # line: answers a learner on that side, in character, ≤ 20 words, ends on a question or a jab
  # comeback: one fun learner comeback chip in A2 French («Et toi, tu chantes sous la douche !»)
```

Every `en`/`de` is a faithful translation of its `fr` (the translate chip shows it at every band).

### 2.2 Who sits at the counter

`comptoir_guests(dossier) -> [id, id, id]`, deterministic: Romy (`romy_tremblay`, off duty, so she has
opinions), the topic's guest from `policy.GUEST_AFFINITY` (first one that has a portrait: lila_bonnet,
marin_leveque, margaux_barman, landlord_marchand; never camille_marchand), then Gus
(`augustin_de_roncourt`). If the topic guest is Gus or missing, Margaux. Character sheets come from
`app/prompts/serial/world_bible_paris_v2.json` (`name, role, personality, speech_pattern,
signature_phrases, flaw`), plus a short authored sheet for M. Marchand (see the prototype), and Romy's
«at the counter» note. Each guest has a short `role_fr` for La page («journaliste», «consultant»,
«Le Mistral», «prof», «ONG», «propriétaire»), authored in code, not by the model.

### 2.3 Rules the desk is given (prompt) and the checks that enforce them (`repair_comptoir`)

`fit: "skip"` when the story is a death, a war, a crime with victims, an election or a party's politics, or
anything where taking sides would be cruel or partisan. A skip stores `checks["comptoir"]="skip"` on the row
and the dossier stays chat-only. Opinions are about everyday life (money, noise, pride, fun, the planet,
the neighbourhood, work, taste); no insults, nothing about a real person's private life.

Checks (a failing check drops the smallest thing it can; the whole comptoir is refused only when the
question, the three stances or a band's takes cannot be kept):

| Check | On failure |
|---|---|
| guests == `comptoir_guests(dossier)`, stances exactly {pour, contre, nuance} | refuse |
| question present, ≤ 9 words, ends with «?» | refuse |
| take word limits: a1 ≤ 16, a2 ≤ 28, b1 ≤ 45; quote ≤ 8; reply line ≤ 22; reason ≤ 5 | refuse (a take) / drop a reason or reply (fallbacks in §6) |
| no number in a take, quote or reply that the claims/title/summary do not carry, except inside `wrong_fr` | refuse |
| `voice.id_leaks`, `voice.app_words`/`meta_words`, relative dates (reuse the leads helpers) | refuse |
| intox: `wrong_fr` absent from every claim (case-folded), `right_fr` found in `claim_id`'s French, `distractor_fr` found in the claims and ≠ `right_fr` | drop the intox |
| intox per band: `wrong_fr` (case-folded) inside `by`'s take at that band | that band leaves `intox.bands` |
| every `fr` through `voice.french_typography`; translations clipped like leads | — |

One retry with `retry_feedback` (the problems list), like `encounter.close`, before refusing.

### 2.4 Model and cost

The desk runs once per story per morning (two stories a day under the daily cadence), shared by every
learner, so quality matters more than price. Production already has `ANTHROPIC_API_KEY` (render.yaml, the
story writer runs `claude-haiku-5-5`), and `LLMService` routes `claude*` models to Anthropic. Run the desk on
the twelve evergreens plus the Céline story with `claude-sonnet-5-5` and `claude-haiku-5-5` (and the Revue
default, gpt-6-luna, which the prototype measured), write the outputs and check results side by side to
`/mnt/project-files/au-comptoir/desk-comparison.md`, and default `REVUE_COMPTOIR_MODEL` to the one that passes
the checks most often with the liveliest French. Record its cost per story in that file. Do not change
`render.yaml` values for other features.

### 2.5 Evergreen takes ship with the evergreens

Generate the twelve evergreens' takes with the chosen model, keep only what passes the checks, review them by
eye (fix by hand if a line is wrong), and commit them as `app/services/revue/evergreen/comptoir/<id>.json`,
loaded onto the evergreen dossiers by `evergreen.py`. That makes evergreen weeks call-free, makes the tests
and the walk realistic offline, and gives the e2e harness real French to screenshot.

### 2.6 When the morning did not write them

`ensure_comptoir(db, period)` runs after `ensure_leads` in the beat and records a refusal on `checks` so a
refused row is not asked again. At session start with the switch on, a dossier without takes and without a
recorded refusal gets one synchronous desk call (the player shows Romy's loading line meanwhile); if it fails
or is refused, the session starts in chat mode. With the switch on, `ranked()` puts dossiers that have takes
first.

## 3. The learner's loop (per session)

Five screens. The server owns the state (append-only events, replayed); the view says which step is current,
so resume lands on the right screen and nothing can strand the learner. Every screen has exactly one main
button at the bottom and that button is always enabled once the screen's one required act is done; the
screen tells the learner what that act is.

New `EventKind` `"comptoir"` with payload `{act, ...}`. Learner text is also appended as `turn_learner` (so
the close's «used words», memory and cost code keep working). Model calls record `cost_usd`.

### Step 1 · Lire
- Head: × and five step dots (no beat bar, no column meter, no pinned band).
- The story's picture (the existing `RvPicture`/plate, not pinned, scrolls away), a dateline («Ce qui s'est
  passé · Paris, 18 oct.»), the lead at the learner's band (`dossier.lead_for(band)`), source link.
- Every word tappable at every band (the fixed `glossSegments` + `WordHelpSheet` from the bug-fix branch: the
  word's meaning in its sentence, «+ Garder»). Translate chip («Traduire») at every band; at A1 the
  translation can be one tap away as today. Listen (existing audio, if the lead has it).
- «La question du jour» card with the gut vote: «Oui !» (pour), «Non.» (contre), «Bof…» (nuance).
- Act: `vote {value}`. Main button «Au comptoir →» enabled once voted. The vote can be changed until step 4.

### Step 2 · Les avis
- Three bubbles (CastPortrait, name in their colour, stance tag POUR / CONTRE / ÇA DÉPEND), revealed one at a
  time: the first shows at once; reacting reveals the next. Each take at the learner's band, words
  tappable, translate chip, ▶ voice via `useLineVoice` when the cast has a voice (skip the button otherwise).
- Under each: «d'accord» / «pas d'accord». Act: `react {guest_id, value: agree|disagree}`.
- A quiet line under the cards: «3 avis · 1 intox cachée» (or «3 avis» when this band has no intox).
- Main button «Continuer» enabled after the three reactions.

### Step 3 · L'intox (only when `intox` exists and the band is in `intox.bands`; else skipped)
- Romy: «Attends… quelqu'un a dit un truc faux. Qui ?» The three takes as compact quotes to tap.
- Act `intox_who {guest_id}`. Wrong: «Non, relis bien.» plus the relevant claim shown; second wrong: reveal
  who it was. Never more than two tries.
- Then `intox.ask` with the fix. A1–A2: two options (`right_fr`, `distractor_fr`, order seeded by session);
  B1+: an empty text field under the hint «C'est faux, {name} ! C'est …, pas …» (graded deterministically:
  correct when the part before «, pas …» carries `right_fr`, case/accents-folded; numbers compared digit-only,
  and with the word that says what they count, so «500 000» alone is not enough; under four words is a nudge,
  not a try. Since 2026-10-23, §9; the field was prefilled before). Act `intox_fix {value|text}`.
- Result: the learner's line printed as a bubble («C'est faux, Gus ! C'est plus de 500 000, pas un million.»),
  the claim with its source, then the liar's `caught` line. A wrong fix still shows the right sentence. The
  phrase «C'est faux, c'est…, pas…» is shown as learned.
- Main button «Continuer».

### Step 4 · Ton avis
- Romy: «Et toi ? Il me manque une voix pour mon micro-trottoir.» Side chips Pour / Contre / Ça dépend,
  preselected from the gut vote.
- Per band:
  - A1: tiles. «Je suis pour.» / «Je suis contre.» / «Ça dépend.» + «parce que» + one of the three
    `reasons[stance]` tiles. The built sentence shows as the learner taps. No model call for the edit (the
    sentence is correct by construction).
  - A2: `frames[stance]` + a text field for the reason (RvComposer: text or voice), the `bank` as chips that
    insert the word, and the phrase of the day above it.
  - B1: free text or voice answering someone by name: prompt «Réponds à {opposite guest}» with
    `phrase.b1` as the frame hint.
  - B2: two or three sentences with a concession; `phrase.b2`.
- Act `opinion {stance, text?, reason_index?, mode}`. A floor first (2026-10-23): A2 needs 4 words after the
  frame, B1+ 12; under it Romy asks for more on the same screen and nothing is recorded. One model call at A2+
  (`provider.ask_json`, the Revue's provider and model, label `comptoir_edit`):
  `{edited_fr, marks: [{span_fr, kind}] (≤ 3), reply_fr, reply_en, reply_de}`.
  Romy's correction is a light journalist's edit: fix grammar, agreement, spelling and word order, keep the
  learner's meaning, words and stance, never add facts; at B2 also register and connectors. It is kept back
  as the target; the learner sees only marks on their own words (§9). The reply comes from the guest of
  `replies[stance].by`, in character, answering what the learner actually said. Checks: edit length ≤ 1.6×
  the learner's, no new numbers, no app words/ids; the reply ≤ 22 words with the same checks. On failure or
  a model error: the learner's text prints as written (typography only, «tel que tu l'as écrit») with the
  desk's `replies[stance].line`. A1 always uses the desk's reply. Submitting twice returns the stored result
  (no second call).
- Then on the same screen (step «4 · suite» in the mock). With marks: the learner's own sentence with the
  marked words underlined and the kind of each slip, a field holding that sentence to fix, and nothing printed
  or answered yet (act `opinion_fix {text}`; after one try «Corrige-le, Romy», `{value: "romy"}`). Once
  settled: what prints, labelled by how it got there («relu par Romy», «corrigé par toi», «corrigé par Romy»
  with her changes lit, «tel que tu l'as écrit»; A1's tiles plain «Dans le journal»), then the guest's reply
  bubble, then «Ta réponse»: chips «Pas du tout !», «Un peu…», and `replies[stance].comeback` (A1–A2); a free
  one-line field from B1 (no model call). Act `comeback {index|text}`. After it, the guest has one authored
  last word by band («Touché.» / «On en reparle demain !»), then the main button «Voir la page».

### Step 5 · La page
- Calls `POST /close`. The close for a comptoir session makes no model call and does not print Romy's line
  twice. It builds:
  - `RvClosing.comptoir_page`: `{question_fr, dateline_fr, standfirst_fr (one line from the lead), quotes:
    [{cast_id, name_fr, role_fr, stance, quote_fr}] ×3, mine: {quote_fr (edited), stance}, votes: {pour,
    contre, nuance} (the three guests + the learner), intox: {wrong_fr, right_fr, source_name} | null,
    phrase_fr, words: kept words}`. Since 2026-10-23 `mine.quote_fr` is what printed and `proof` says how
    (§9).
  - `RvClosing.dispatch` for the Relevé: kicker «Le micro-trottoir de Romy», headline = the question, body =
    the standfirst and «Toi : « … »», contribution spans on the learner's quote.
  - The artifact is a new make kind `"opinion"` (`text_fr` = edited, `learner_fr` = raw), so the vignette,
    `keep_papier_words`, Romy's memory («Tu as dit : « … »»), each guest's memory, the cost row and the Carte
    invalidation all run as they do today. Romy's close line is authored («Merci ! Ta voix est dans le
    micro-trottoir.»); the colophon follows the cadence.
- The page as in the mock: the four faces with stance tags (the learner's face is their «Ton personnage»
  character if the app has one, else an initial), the vote tally, «L'intox du jour», the words kept, and one
  main button «Classer» (= the existing exit / Relevé actions; at most two buttons in the foot, both fitting
  at 375 px).

## 4. Wire

- `POST /revue/sessions/{id}/comptoir` body `{act, guest_id?, value?, text?, mode?, reason_index?}` →
  `RvComptoirResult {session: RvSessionView, error_fr?: str}`. Add it to `PAID_ROUTES` like the other POSTs.
  404 while `REVUE_ENABLED` is off (a session already at the counter plays to its end after
  `REVUE_COMPTOIR_ENABLED` is turned off); 409 `revue_not_comptoir` on a chat session; 409 on an act out of order (the
  client then re-renders from the returned view; acts are idempotent where they can be).
- `RvComptoirView` (in the session view): `step: "read" | "takes" | "intox" | "opinion" | "page"`, the band's
  texts only (never another band's, never `wrong_fr`/`right_fr`/`distractor_fr` before the intox is resolved,
  never the reply before the opinion), the learner's acts so far (vote, reactions, intox result, opinion,
  edit, reply, comeback), the cast (`id, name_fr, role_fr, stance`), the phrase of the day, and the
  translations in the learner's gloss language only.
- `RvStoryCard` gains optional `question_fr` and `cast` (ids) when the switch is on and the dossier has
  takes; `RvUneCard` then shows «La question du jour», the question and the three faces (mock screen 0).
- Update `docs/implementation/atelier-v2/WP-119-WIRE.md`, `app/schemas/revue.py`, `lib/revue-types.ts`
  (parsers), `lib/revue-api.ts` (`comptoir(id, body)`), and `lib/revue-mock.ts` (a Céline fixture so the
  page works without a backend).

## 5. Frontend

- `components/revue/comptoir/` : `RvComptoir.tsx` (the player: head with × and dots, one step at a time,
  sticky foot with the one main button), one component per step, `comptoir-model.ts` (pure: step labels,
  the A1 sentence builder, the word diff for Romy's edit, the vote tally; node-tested), `comptoir-copy.ts`
  (fr/en/de UI copy, like `revue-copy.ts`), styles in `styles/revue.css` or a new `styles/revue-comptoir.css`
  using the av2 tokens (light and dark).
- `RvJourneyPapier` and `pages/revue.tsx` render `RvComptoir` when `session.mode === "comptoir"`, else
  `RvEncounter`, with the same props.
- Reuse: `CastPortrait`, `RvPicture`, `glossSegments`/`RvGlossText` and `WordHelpSheet` (after the bug-fix
  merge), `useLineVoice`, `RvComposer`, `RvClose` pieces where they fit.
- Phone first: 375×812 and 390×844 with no horizontal scroll, the main button always on screen, no more than
  two buttons in any foot, text never under the foot.

## 6. Never stuck, never wrong

1. Every step has one visible way forward; every act is accepted or answered with a reason and the same step
   re-rendered; a failed model call falls back to authored or desk text, never to an empty screen.
2. A refused or missing intox skips step 3 cleanly (dots show four steps).
3. Resume at any step re-renders that step from the view with the learner's earlier acts shown.
4. The facts are only on screen 1 (with the source) and in the intox correction (with the source); everything
   else is people talking, in bubbles with faces. The intox is always corrected on screen.
5. If an errata-recording function already exists that takes (learner text, corrected text), record Romy's
   edit through it; otherwise leave it for phase 3 and say so in the PR.

## 7. Tests and walk

- Backend (pytest, SQLite like the other `tests/test_revue_*.py`): the desk's checks one by one (including
  the case-fold intox, a stray number, a skip, a stance mismatch, a missing band's intox), `comptoir_guests`,
  `ensure_comptoir` once per row, the evergreen takes load and pass the checks, start in each mode (switch
  off, on with takes, on without takes → one desk call, desk failing → chat), every act in order and out of
  order, two wrong intox guesses then reveal, the opinion with a fake provider and with a failing one, double
  submit, the close page and dispatch and memory, the route 404 with the switch off, the view never leaking
  answers early.
- Frontend: model tests, wire parse tests, render tests for each step at A1/A2/B1 (in the style of
  `revue-render.test.js`), `npx tsc --noEmit`, eslint on changed files, the existing revue tests still green.
- Walk: `node e2e/explore.mjs --revue` with the switch on (the harness's backend env), a full run at A1 (EN),
  A2 (DE) and B1 (EN), light and dark, 390×844, plus one A1 run at 375×812. Screenshots of every step to
  `/mnt/project-files/au-comptoir/walk/`, named `<band>-<lang>-<theme>-<nn>-<step>.png`.
  As built: `node e2e/explore.mjs --comptoir [--viewport 390x844] [--theme dark]` (§8.3).

## 8. As built (2026-10-19)

### 8.1 What is built, by section

- §1 The switch: `REVUE_COMPTOIR_ENABLED` (off) and `REVUE_COMPTOIR_MODEL`; the mode on the first `choice`
  event; `RvSessionView.mode` / `.comptoir`. Off, the snapshot and the wire are as before.
- §2 The desk: `app/services/revue/comptoir.py` (`write_comptoir`, `repair_comptoir`, `ensure_comptoir`,
  `takes_at_start`, `comptoir_guests`); ten evergreens ship their takes in
  `app/services/revue/evergreen/comptoir/`. Model: `claude-haiku-5-5` (comparison in
  `/mnt/project-files/au-comptoir/desk-comparison.md`: 10/13 on the first pass, 11/13 after the fixes, about
  $0.0057 a story; gpt-6-luna 11/13 at $0.0022 with stiffer French; claude-sonnet-5-5 8/13 on the first pass
  at about $0.058). The comparison cost $0.85 in all.
- §3 The loop: `app/services/revue/comptoir_loop.py` (acts replayed from `comptoir` events, the step derived
  from them, the view redacted until its time, Romy's edit in one `comptoir_edit` call at A2+, «La page» at
  the close with no model call).
- §4 Wire: `POST /revue/sessions/{id}/comptoir`, WIRE §9; `lib/revue-types.ts` (parsers), `lib/revue-api.ts`
  (`comptoir(id, body)`), the dev mock (`/revue?mock=1&comptoir=1`, the Céline story).
- §5 Frontend: `components/revue/comptoir/` — `RvComptoir.tsx` (head, dots, one screen at a time, sticky
  foot), `RvComptoirRead/Takes/Intox/Opinion/Page.tsx`, `RvComptoirParts.tsx` (bubbles, Romy's lines, the
  stance tag, ▶), `comptoir-model.ts`, `comptoir-copy.ts`; styles in `styles/revue-comptoir.css` (av2 tokens,
  light and dark). Mounted by `pages/revue.tsx` and `RvJourneyPapier` (La Carte's «Relire» lands on the filed
  page, read-only). `RvUneCard` and `RvChooser` show «La question du jour», the question and the three faces;
  the Relevé and the thread label the new made kind «Ton avis».
- §6 Never stuck: a refused act (`error_fr`) is said by Romy on the same screen; a 409 re-reads the session
  and shows its step; a failure is one quiet line; the newest part is scrolled into the band between the head
  and the foot. §6.5: no errata-recording function exists in the codebase, so Romy's edit is not recorded as
  errata (phase 3).
- §7 Tests: backend `tests/test_revue_comptoir*.py`; frontend `components/revue/comptoir/comptoir.test.js`
  (model, wire, every step rendered at A1 EN, A2 DE and B1 EN, the clipping, La Une). The walk's screenshots
  are in `/mnt/project-files/au-comptoir/walk/` (A1 EN, A2 DE, B1 EN, light and dark at 390×844) and
  `walk/375x812/` (A1 EN, light).

### 8.2 Deviations, and why

- **Replies never guess who the learner is.** The desk's example taught Gus to call every learner «mon cher»
  and Romy to answer the learner with «Voyons donc, Gus !». The prompt now says a reply speaks to the learner
  (no pet name, no adjective agreeing with «tu») and `address_problem` refuses such a line in the desk and in
  Romy's edit (the authored line stands in).
- **Evergreens fixed by hand.** Weak lines in the shipped takes were rewritten (signature lines copied from
  the prompt's example, a comeback that did not fit its side, the replies' forms of address), in all three
  languages. The transport strike and Toussaint stay chat-only: the desk judged them unfit for an argument.
- **No desk call beside the deterministic provider.** In dev and on the walk (the fake provider) a story
  without takes stays a chat instead of calling the real desk.
- **The route answers while the comptoir switch is off**, for a session that started at the counter: turning
  the switch off stops new sessions starting there and never strands a learner mid-session (a chat session
  answers 409). It answers 404 before auth while `REVUE_ENABLED` is off, like every Revue route.
- **The close needs the opinion**: `POST /close` on a comptoir session without it is `409
  revue_comptoir_out_of_order`; «Voir la page» is the only way there.
- **Comebacks are picked by `index`** (WIRE §9.3), not by text, at A1–A2.
- **The opinion field is the comptoir's own**, not `RvComposer`: at A2 the frame and the reason are one card
  (the phrase of the day, the frame, the field, the bank under it), at B1 the field sits under «Réponds à …»;
  the foot holds the mic and «Donner mon avis». `RvComposer` (which now grows with its text) is used where one
  line is sent: the B1 correction of the intox (empty since 2026-10-23), the fix of Romy's marks and the B1
  comeback.
- **French in every chrome for the publication's words and the feature's name**: «Au comptoir», «La question
  du jour», POUR / CONTRE / ÇA DÉPEND, the side chips, «Dans le journal» and its proof labels (§9), «Les
  corrections de Romy», «Le micro-trottoir de Romy», «L'intox du jour», «Toi». The rest of the chrome follows the learner's control language (from B1
  the app's chrome is French, WP-82).
- **The step names are French** («Lire», «Les avis», «L'intox», «Ton avis», «La page») and only spoken by the
  dots' label; the screens are not titled.
- **«La page»'s foot has two buttons**, «Classer le Papier» and «Voir dans le Relevé»; the chat close's «Voir
  sur la carte» is not offered there (two at most).
- **The learner's face** is their «Ton personnage» avatar, else a «Toi» disc (not an initial).
- **B2** plays the B1 screen (free text, «Réponds à …») with the b2 phrase of the day; Romy's edit may improve
  register and connectors there. No separate «two or three sentences» screen.
- **A1's sentence** is shown twice after the opinion (the learner's line and the printed one, plain «Dans le
  journal» since 2026-10-23: Romy did not read tiles): it is correct by construction, so the paper's version
  only confirms it is printed.
- **A B1 correction already word for word right** is not repeated in the feedback card; its note stays.
- **Romy's notes became marks** (2026-10-23, §9): the kind of each slip is named in the learner's control
  language («très · spelling»); she no longer explains a rewrite the learner did not make.
- **The intox shows its settling claim once**: after a missed guess the claim stays above, and the fix does
  not print it a second time.

### 8.3 The walk harness

`e2e/explore.mjs --comptoir` starts the Revue's server with `REVUE_COMPTOIR_ENABLED` (it implies `--revue`);
`--viewport WxH` and `--theme dark` set the phone and its colour scheme; `POST /shot {name, full}` saves a
named screenshot and lists anything whose right edge passes the viewport. Run with `SECRET_KEY=proto-only` in
the environment (a Python start without it prints a settings error).

### 8.4 Not done, or uncertain

- Errata memory from Romy's edit (§6.5): no function to record it exists.
- The intox's distractor is «another true value from the claims»; in several shipped evergreens it does not
  answer the question («Combien de jours par semaine ?» → «six jours sur sept» / «91 marchés»), which makes the
  A1–A2 pick easy. A same-kind check (a duration for a duration, a date for a date) is a follow-up.
- The walk ran on the fake providers: the takes are the shipped evergreens', Romy's edit and the replies are
  the deterministic provider's. Romy's live edit (`comptoir_edit` on the real model) has not been run yet: its
  checks are tested with scripted answers only.
- The Listen chip uses the device's French voice per character (`useLineVoice`); the lead has no recorded
  audio.

## 9. Phase 0: the learner writes (2026-10-23)

Vincent's walk found that a learner could press through the Papier and the counter without writing a word of
their own, and that the paper then printed Romy's French as theirs. The review behind this is
https://claude.ai/artifact/XfjoQVX9J6c7wqNWcJ11HT («Order of work», Phase 0). Nine fixes, as built:

1. **No headline pick from B1.** `headline_choice` is offered at A1–A2 only (`LOWER_ONLY_MAKE`); a B1+ request
   for it is `409 revue_make_unavailable`. B1+ write the headline.
2. **«Écrire le papier» waits for a line of the learner's own.** `own_line` is true once a `turn_learner` is
   not one of the quick-reply chips. It gates Romy's steer to the make, the write chip, `make_options` and
   `make` (`409 revue_make_needs_a_line`); the foot says why while it is false.
3. **Every band writes the caption.** The picture's words are the tiles; a caption under the band's floor
   (A1 2 words, A2 3, B1 4, B2 5) or contradicting the picture is refused with Romy's reason. At A1–A2 the
   three captions to pick from appear only after a refused try (`409 revue_caption_write_first` before). A
   picked caption is uncredited (`contribution: []`) and Romy's close says «la légende que tu as choisie».
4. **An opinion has a floor**: A2 4 words after the frame, B1+ 12. Under it Romy asks for more and nothing is
   recorded («Oui.» never prints).
5. **Romy marks, the learner fixes.** Her correction is the hidden target; the learner sees up to three marks
   on their own words with the kind of slip (accord, conjugaison, genre, orthographe, mot, ordre, manque) and
   sends the sentence again: two tries, then «Corrige-le, Romy» or her correction. Proof states `clean`,
   `marked`, `fixed`, `corrected`, `as_written` (WIRE §9.5). Nothing she did not read prints as «relu par
   Romy»: a failed check prints «tel que tu l'as écrit». The reply waits until the opinion is settled, and
   `POST /close` waits too.
6. **Every honest take carries a checkable detail.** `repair_comptoir` refuses an intox band where an honest
   take names no detail from the claims (`comptoir:{guest}:{band}:no_detail`), so «who lied?» is not answered
   by elimination. The takes are refused, not repaired by dropping the band, because the liar's take at that
   band would still print the false detail uncorrected; the desk retries once with the problems. The ten evergreens were given a detail each where they lacked one;
   all audit clean.
7. **The B1 intox fix starts empty** and the grader wants the value and what it counts («500 000 personnes»),
   four words at least.
8. **Copy says only what is true.** «Your line» only on a typed fix that matches the right line; «C'est ta
   légende» only on a written caption; the dispatch's byline «avec toi» only when words the learner typed or
   said print (never A1 tiles, never a pick); «Toi, au comptoir · corrigé par Romy» on the page when she
   corrected it.
9. **Kept words are the session's.** The Relevé keeps the plan's words the learner met (the lead, the takes,
   the facts shown, the question; in the chat, what Romy and the guests said and showed), the ones they used
   first, and at least one they used when they used any (the A2 bank's word at the counter, the picture's
   word in the chat).

Not in Phase 0, and still open: a `reader_question` can credit Romy's seed question as the learner's when they
send it unchanged. Phases 1–3 of the review (the job in six moves with Le reportage, then the rubriques and
progression, then Le Quartier) are not started.
