# WP-119 phases 1–2 · Le Papier de Romy — the wire (frozen 2026-10-02; phase 2 «Les invités» added the same day, §6)

*Backend lead. The frontend builds `web-frontend/components/revue/` (WP-119-DESIGN.md §4) against this
file. Pydantic models: `app/schemas/revue.py`. Router: `app/api/v1/endpoints/revue.py`. Service:
`app/services/revue/encounter.py`. Any change to a shape below is a change to this file first.*

## 0. Conventions

- Base path `/api/v1/revue`. JSON, `snake_case` keys, like the rest of the API.
- **Auth.** Every route takes `Authorization: Bearer <access token>` (`get_current_user`). No token → `401`.
- **Flag.** When `settings.REVUE_ENABLED` is false **every** route answers `404 {"detail": "Not Found"}`,
  before auth, so the feature is invisible (the client hides the chip and the page on a 404 from `GET /revue/week`).
- **French only in the story.** Everything named `*_fr` is French. Chrome (labels, kickers, notices) is the
  client's `revue-copy.ts`; the server sends codes (`reason`, `role`, `kind`), never chrome strings, except
  the few French publication words the design fixes («Semaine 40», the dispatch kicker, the colophon).
- Dates are ISO strings: `YYYY-MM-DD` for publication dates, full ISO-8601 with offset for timestamps.
- Spans (`RvSpan`) are `[start, end]` character offsets (Python `str` indices = UTF-16 code units for every
  character the Revue uses; no astral characters are produced) into the string they annotate, `end` exclusive.
- Nothing private travels: a headline exercise's answer and `contradicted_by` map, the provider prompt, the
  raw state log. Responses are built only from the models below.

## 1. Shared types

```ts
type RvWeek = { iso: string /* "2026-W40" */; label: string /* "Semaine 40" */; range: string /* "du 28 sept. au 4 oct." */ };

type RvSource = { id: string; name: string; url: string; published_at: string /* YYYY-MM-DD */ };

type RvClaim = {
  id: string;                                   // "c1", unique inside a dossier
  kind: "fact" | "interpretation" | "forecast";
  fr: string;                                   // Romy's French for the claim
  quote: string;                                // verbatim anchor, ≤ 40 words («La citation»)
  attributed_to: string | null;                 // always set for interpretation / forecast
  source: RvSource;
};

type RvGloss = { fr: string; gloss: string; claim_id: string };   // gloss in plan.gloss_language

type RvStageMember = { id: string /* "romy_tremblay" | "user" */; hold: string | null /* "notebook" */ };

type RvStage = {
  place_id: string;            // the dossier's place ("marche_aligre")
  place_fr: string;            // "Le marché d'Aligre, un matin"
  plate_url: string | null;    // "/assets/serial/locations/marche_canal.webp" (phase 1: known plates only)
  plate_place_id: string;      // the known location whose plate stands in ("marche_canal")
  place_is_real: boolean;      // false → the plate is a stand-in and Romy says so (a `place_note` line)
  dress: "coat" | "suit" | "apron" | "raincoat" | "sport" | "scarf_only" | "chef" | "hi_vis";  // Toi's outfit
  cast: RvStageMember[];       // [{id: "romy_tremblay", hold: "notebook"}, {id: "user", hold: null}]
                               // phase 2: a guest on stage stands right after Romy: [romy, {id: "margaux_barman", hold: null}, user]
};

type RvStoryCard = {
  dossier_id: string;
  title_fr: string;
  summary_fr: string;
  topic: "food" | "culture" | "city" | "sport" | "nature" | "work" | "politics";
  place_fr: string;
  plate_url: string | null;
  evergreen: boolean;          // true → label it «Hors actualité · un classique de saison»
  stage: RvStage;
};

type RvSupport = {
  glosses: "shown" | "tap" | "none";
  translation: "one_tap" | "on_request" | "none";
  reading_target_words: number;
  vocab_target: number;
  level: number;               // 0 = the band's default; +1 per "simplify on breakdown"
};

type RvBeat = "arrive" | "facts" | "pursue" | "make" | "close";

type RvRoom = {
  used: number;                // 0..7 inked lines of the column
  phase: "open" | "bouclage" | "boucle";   // bouclage ≥ 80 % of budget.turns, boucle = 100 %
  remaining_turns: number;     // for the screen-reader sentence only («environ quatre échanges»); never shown as a number
};

type RvMakeKind = "headline_choice" | "headline_write" | "reader_question" | "short_report";   // phase 2: + headline_write (B1+), short_report (B1+)

type RvMade = {
  kind: RvMakeKind;
  text_fr: string;             // the headline, or the reader question as sent to the desk
  contribution: [number, number][];   // the learner's part of text_fr (yellow underline + «toi»)
  learner_fr: string | null;   // what the learner wrote (reader_question), null for a picked headline
};

type RvDispatch = {
  kicker_fr: string;           // "Le Papier de Romy · semaine 40"
  headline_fr: string;
  body_fr: string[];           // three lines
  contribution: [number, number][];   // spans into headline_fr
  byline_fr: string;           // "Romy Tremblay, avec toi · d'après Ville de Paris (paris.fr) et Wikipédia…"
  sources: RvSource[];
};

type RvQuickReply = { label: string; send_fr: string };   // label may differ from the French sent («Plus» → «Dis-m'en plus.»)
```

## 2. The thread item union (`RvThreadItem`)

The thread is **a projection of the append-only state** (WP-119 §3.3): the same state always gives the
same items with the same ids, so resume is a replay. Every item has:

```ts
type RvItemBase = { id: string /* "<seq>" or "<seq>.<n>" — stable across replays */; seq: number; at: string /* ISO timestamp of the event */ };
```

| `kind` | Extra fields | Renders as | Comes from |
|---|---|---|---|
| `narration` | `text_fr` | `RvNarration` (sans, no face) | the `arrive` beat: two sentences from place + time scope |
| `summary` | `speaker: "romy_tremblay"`, `text_fr` | `HeardLine` «Écouter le résumé» | the `arrive` beat: the dossier's `summary_fr` |
| `line` | `speaker`, `text_fr`, `role`, `translation: string \| null`, `glosses: RvGloss[]` | `RvLine` (speech bubble) | every Romy turn |
| `mine` | `text_fr`, `mode: "text" \| "voice"`, `register_note: "vous_to_tu" \| "tu_to_vous" \| null` | the learner's bubble (and, with a note, the register note under it) | every learner turn; `register_note` from that turn's `evidence` event (2026-10-03), so the note survives a reload |
| `claims` | `claims: RvClaim[]` (1–2) | `RvClaim` cards (the client folds them into «2 faits sur la table» once the learner speaks) | the claims Romy cites in that turn, first time shown only |
| `uncertainty` | `text_fr` | `RvUncertainty` (dashed, «Les sources ne le disent pas») | Romy names a gap the dossier lists |
| `shift` | `reason: "simplify" \| "angle" \| "bouclage" \| "boucle"`, `angle: {id, fr} \| null` | `RvShift` hairline (`role="status"`) | support changed / angle changed / the column reached 80 % or 100 % |
| `made` | `made: RvMade` | the artefact as filed (headline or reader question) | the `make` beat |
| `guest` | `cast_id`, `text_fr`, `move`, `position`, `reason_fr`, `reason`, `glosses` | the guest's bubble (phase 2, §6.2) | a guest's line |

`line.role`: `"purpose"` (the arrive headline bubble), `"place_note"` (phase-1 honest stand-in plate line),
`"reply"` (a pursue answer), `"steer"` (the bouclage steer, its own bubble right after the reply), `"fallback"`
(an authored line: knowledge check refused twice, the model is down, the column is full, or a free request
matched nothing), `"make_intro"` / `"make_done"` (phase 2: Romy's lines around the `make` beat, from the
server), `"close"` (Romy's closing line). `line.reason` (phase 2) is set on every `fallback` line and null on
every other: `"model_down" | "knowledge_refused" | "budget" | "no_match"`. `speaker` is always
`"romy_tremblay"`: guests speak in their own `guest` items, never as a `line`. `glosses` lists the plan's vocabulary items that occur in `text_fr`.
`translation` is present only when the provider gave one and `support.translation != "none"`.

Client-only kinds from the design (`claimsFolded`, `typing`) are never sent.

**Evidence may arrive one turn late (WP-119 §10e.8, 2026-10-03).** With the real provider, Romy's reply, the
guest's line and the rubric critic run side by side; the turn waits for the critic at most 2 s after the reply
is assembled. When the critic is slower, the turn's `evidence` is sent as `{"outcome": "unscored", "pending":
true, …}` and the graded evidence is written at the start of the learner's **next** turn (or at `make` / `close`,
whichever comes first), as a second `evidence` event for the same turn (`late: true`). The thread is unaffected:
`register_note` on a `mine` item and the kept words' `outcome` at the close read the latest evidence of each
turn, so a reload after the next turn shows the graded result. A client that shows the word marks of the
current turn should treat `pending: true` as "not graded yet", never as "wrong".

**What the learner reads (WP-119 §10e, «La voix de Romy»).** Every text field Romy or a guest writes —
`line.text_fr`, `line.translation`, `guest.text_fr`, the reader-question proposal, the close line, the dispatch
headline and body — is checked before it is stored: no dossier id («c2», «a1», «u1», «incert. 1»), no symbols
(→ ≈ ~ > < / ×) at A1–A2, no orders to the learner («Dis…», «Écris…»), no app words in the close («artefact»,
«session», «dossier»), and no guest offering a service («Voulez-vous que je…»). One regeneration names the
problem; then the line is repaired (ids stripped, symbols in words, the order dropped) or the authored line
stands. Romy brings at most two new claims per reply (`claims` items carry only those), proposes the reader
question once per Papier, and changes the angle at most once, on a learner turn that names the other angle's
topic.

## 3. Endpoints

### 3.1 `GET /revue/week` — the week's offer
Query: `week` (optional, `^\d{4}-W\d{2}$`; default: the current ISO week in Europe/Paris).
Never creates anything, never calls a model.

```ts
type RvOffer = {
  week: RvWeek;
  recommended: RvStoryCard | null;          // null only if the week has no dossier at all
  recommended_reason: "topic_least_recent" | "interests" | "first";
  alternatives: RvStoryCard[];              // 0..2 (a thin week may have fewer)
  evergreen_only: boolean;                  // every card is an evergreen → «hors actualité» state
  resume: { session_id: string; dossier_id: string; title_fr: string; started_at: string;
            beat: RvBeat; open_question_fr: string | null } | null;   // an active session this week
  filed: { session_id: string; dossier_id: string; title_fr: string; closed_at: string;
           made: RvMade | null; dispatch: RvDispatch | null } | null;   // this week's Revue is closed
};
```
Recommendation: the topic the learner has seen least recently in their closed Revues (never seen first), then
the overlap with `users.interests`, then the order the week lists them.

Example:
```json
{"week": {"iso": "2026-W40", "label": "Semaine 40", "range": "du 28 sept. au 4 oct."},
 "recommended": {"dossier_id": "evergreen-marche-du-dimanche", "title_fr": "Le marché du dimanche à Aligre",
   "summary_fr": "Paris a 91 marchés. …", "topic": "food", "place_fr": "Le marché d'Aligre, un matin",
   "plate_url": "/assets/serial/locations/marche_canal.webp", "evergreen": true,
   "stage": {"place_id": "marche_aligre", "place_fr": "Le marché d'Aligre, un matin",
     "plate_url": "/assets/serial/locations/marche_canal.webp", "plate_place_id": "marche_canal",
     "place_is_real": false, "dress": "apron",
     "cast": [{"id": "romy_tremblay", "hold": "notebook"}, {"id": "user", "hold": null}]}},
 "recommended_reason": "interests",
 "alternatives": [{"dossier_id": "evergreen-greve-transports", "…": "…"}],
 "evergreen_only": true, "resume": null, "filed": null}
```

### 3.2 `POST /revue/match` — «Autre chose ?» in the sheet
Body `{ "text": string (1..300), "week"?: string }`. No model call, nothing stored.
Response `{ "match": string | null /* dossier_id */, "romy_line_fr": string | null }` — `romy_line_fr` only on a miss.
```json
{"match": null, "romy_line_fr": "Je n'ai que ça cette semaine, désolée. Le marché du dimanche à Aligre, ça te dit ?"}
```

### 3.3 `POST /revue/sessions` — start
Body:
```ts
{ week?: string; dossier_id?: string; free_request?: string /* ≤ 300 */; angle_id?: string }
```
`dossier_id` wins over `free_request`; neither → the recommended story. A free request is matched by word overlap
with title, summary and angles; a miss starts the recommended story and the `arrive` beat begins with Romy's
«Je n'ai que ça cette semaine…» line (`role: "fallback"`). `chosen_by` is `learner` for an explicit or matched
dossier, `recommended` otherwise.
Response `201` → `RvSessionView` (§3.4) at beat `arrive` (the thread holds narration ×2, an optional place_note,
the purpose line and the summary).

Errors (`detail` is an object with a `code`):
- `404 {"detail": {"code": "revue_dossier_not_found", "dossier_id": "…"}}` — not a dossier of that week
  (with `"angle_id"` too when the dossier exists but the angle does not).
- `409 {"detail": {"code": "revue_session_active", "session_id": "…"}}` — resume it instead (one active per user per week).
- `409 {"detail": {"code": "revue_week_filed", "session_id": "…"}}` — this week's Revue is closed (`ended` state).
- `422` — pydantic validation (`week` pattern, lengths).

### 3.4 `GET /revue/sessions/{id}` — resume
Pure replay: no model call, nothing written. `404 {"detail": {"code": "revue_session_not_found"}}` for an unknown
id or another learner's session.

```ts
type RvSessionView = {
  id: string;
  week: RvWeek;
  status: "active" | "closed" | "abandoned";   // abandoned is reserved (phase 3 files Sunday-night leftovers)
  started_at: string;
  closed_at: string | null;
  dossier: { id: string; title_fr: string; summary_fr: string; topic: string; evergreen: boolean; sources: RvSource[] };
  plan: {
    band: "A1" | "A2" | "B1" | "B2";
    ui_language: "en" | "de" | "fr";         // chrome language (one-language rule)
    gloss_language: "en" | "de" | "fr";      // the learner's native language, folded; glosses and translations use it
    chosen_by: "learner" | "recommended";
    angle: { id: string; fr: string; purpose: "understand_change" | "explain_disagreement" | "choose_angle" | "prepare_dispatch" };
    support: RvSupport;                      // current (after any simplify)
    vocabulary: RvGloss[];                   // 5 (A1/A2) or 7 (B1+) words, each tied to a claim
    make_options: RvMakeKind[];              // A1/A2: ["headline_choice", "reader_question"];
                                             // B1+: ["headline_choice", "headline_write", "reader_question", "short_report"]
    budget: { turns: number; minutes: number };
  };
  stage: RvStage;
  beat: RvBeat;                              // arrive (0 learner turns) · facts (1) · pursue (≥2) · make (a make started) · close (closed)
  room: RvRoom;
  thread: RvThreadItem[];
  quick_replies: RvQuickReply[];
  steer_to_make: boolean;                    // the column is at bouclage/bouclé and nothing is made yet
  artifact: RvMade | null;                   // the latest made thing
  closing: RvClosing | null;                 // set once closed (the `ended` read-only page)
};
```

### 3.5 `POST /revue/sessions/{id}/turns` — one learner turn
Body `{ "text": string (1..600), "mode": "text" | "voice" (default "text"), "client_turn_id"?: string (≤ 64) }`.
`client_turn_id` makes a retry safe: the same id as the last learner turn returns the stored result, no new turn.

```ts
type RvTurnResult = {
  items: RvThreadItem[];       // the new items, in order: mine, [shift simplify], line(reply|fallback), [uncertainty], [claims], [shift angle], [shift simplify — when Romy noticed the breakdown herself], [shift bouclage|boucle], [line steer]
  beat: RvBeat;
  room: RvRoom;
  support: RvSupport;
  quick_replies: RvQuickReply[];
  steer_to_make: boolean;
  evidence: RvEvidence;        // phase 2: the Papier rubric, §6.3
};
```
The facts beat: when no claim is on the table yet, the first reply comes with the dossier's first two facts
(a `claims` item). Simplify on breakdown: two learner turns in a row that are «je ne comprends pas»-like (or that
Romy herself answers with `shift: simplify`) raise `support.level` by one; a `shift` `simplify` item marks it and
Romy's next line starts «Pardon, je vais trop vite.». What the server guarantees about Romy's reply: it cites only claims of the dossier; it is at most
`support.reading_target_words / 2` words (one regeneration, then cut at a sentence end); it has no relative date
(«demain», «cette semaine»…); it passed the season's Knowledge check for the learner's position (one regeneration,
then the authored line «Je ne sais pas encore. On regarde ce que disent les sources ?»). From 80 % of the budget a
`steer` line follows the reply. After 100 % Romy no longer calls the model: she keeps the question for next week.

Errors: `404 revue_session_not_found`; `409 {"detail": {"code": "revue_session_closed"}}`; `422`.

Example (the acceptance test's turn):
```json
{"items": [
  {"id": "9", "seq": 9, "at": "…", "kind": "mine", "text_fr": "Est-ce que les prix sont plus bas qu'au supermarché ?", "mode": "text"},
  {"id": "11", "seq": 11, "at": "…", "kind": "line", "speaker": "romy_tremblay", "role": "reply",
   "text_fr": "Et là, je n'ai rien. Les sources ne le disent pas. On formule la question ensemble ?", "translation": null, "glosses": [], "reason": null},
  {"id": "11.u", "seq": 11, "at": "…", "kind": "uncertainty", "text_fr": "Les sources ne disent pas si les prix au marché sont plus bas qu'au supermarché."},
  {"id": "13", "seq": 13, "at": "…", "kind": "guest", "cast_id": "margaux_barman", "move": "enter", "position": "for",
   "text_fr": "Ce que je sers au comptoir, ça vient de quelque part. Alors ça me regarde.", "reason_fr": null, "reason": null, "glosses": []}],
 "beat": "pursue", "room": {"used": 2, "phase": "open", "remaining_turns": 10},
 "support": {"glosses": "tap", "translation": "on_request", "reading_target_words": 90, "vocab_target": 5, "level": 0},
 "quick_replies": [{"label": "On formule la question", "send_fr": "On formule la question ensemble ?"}, {"label": "Plus", "send_fr": "Dis-m'en plus."}],
 "steer_to_make": false,
 "evidence": {"outcome": "unscored", "capability_known": false, "grader": "revue-rubric-v1",
              "words": [{"fr": "compte", "outcome": "unscored", "capability_known": false}, {"fr": "marchés", "outcome": "unscored", "capability_known": true}],
              "fact_fit": "not_applicable", "register_note": "ok"}}
```

### 3.6 `GET /revue/sessions/{id}/make` — the make options
Builds the headline exercise on the first call and stores it in the session's state (the one GET that writes;
later calls reuse it, so the options never change under the learner); never exposes its answer.
```ts
type RvMakeOffer = {
  recommended: RvMakeKind;     // reader_question when the learner raised a question the sources cannot answer,
                               // else headline_write (B1+), else headline_choice
  options: (
    | { kind: "headline_choice"; options: { id: string; text_fr: string }[] /* 3 */ }
    | { kind: "headline_write"; max_words: number }          // phase 2, B1+
    | { kind: "reader_question"; seed_fr: string | null /* the learner's open question */; uncertainty_fr: string | null }
    | { kind: "short_report"; seconds: number /* 30 */ }      // phase 2, B1+
  )[];                          // an unavailable option is absent, never greyed; order as listed
  intro: RvThreadItem /* line, role "make_intro" */ | null;  // phase 2: written once, on the first GET
};
```
`headline_choice` is absent when the Distinguishable check fails (a distractor no shown claim contradicts, or
the answer is unsupported), after one regeneration. `409 revue_session_closed` after the close.

### 3.7 `POST /revue/sessions/{id}/make` — make something
Body, discriminated by `kind` + `action`:
```ts
| { kind: "headline_choice"; action: "pick"; option_id: string }
| { kind: "reader_question"; action: "propose"; text?: string /* ≤ 400, any language; default: the open question */ }
| { kind: "reader_question"; action: "send"; text_fr: string /* 1..300: the proposal, possibly edited */ }
| { kind: "headline_write"; action: "write"; text_fr: string /* 1..160 */ }                       // phase 2
| { kind: "short_report"; action: "report"; transcript: string /* 1..1200 */; mode?: "voice" | "text" /* default voice */ }  // phase 2
```
The body is discriminated by `action` (`pick | propose | send | write | report`); a `kind` that does not go
with the action is a `422`.
Responses:
```ts
// pick
{ kind: "headline_choice"; correct: boolean; answer_id: string;
  evidence: { claim_id: string; quote: string; source: RvSource };   // FeedbackBand cites it
  made: RvMade }                // the correct headline is filed either way; a wrong pick books no SRS lapse
// propose (nothing filed yet)
{ kind: "reader_question"; draft: { learner_fr: string; proposal_fr: string; contribution: [number, number][];
                                     why_native: string | null /* in gloss_language */ } }
// send
{ kind: "reader_question"; made: RvMade; line: RvLineItem | null /* make_done */ }
// write (phase 2)
{ kind: "headline_write"; accepted: boolean;   // false: a shown claim contradicts it — nothing filed, write again
  evidence: RvEvidence; made: RvMade | null; line: RvLineItem | null /* make_done */ }
// report (phase 2)
{ kind: "short_report"; evidence: RvEvidence; made: RvMade; line: RvLineItem | null /* make_done */ }
```
`pick` also returns `line` (phase 2): Romy's `make_done` line.
Errors: `409 {"detail": {"code": "revue_make_unavailable", "kind": "headline_choice"}}` (also for
`headline_write` / `short_report` below B1);
`422 {"detail": {"code": "revue_unknown_option"}}`; `409 revue_session_closed`.

### 3.8 `POST /revue/sessions/{id}/close` — Romy does something with it
Body `{}`. Idempotent: a second call returns the stored closing. Writes Romy's `NPCMemory`
(`memory_type="interaction"`, French, `scene_id` = the session id) — and, phase 2, one row per guest who came
on stage, for what they witnessed — sets `status: "closed"`, and writes the session's cost row (§6.5).
```ts
type RvClosing = {
  romy_line_fr: string;        // what she did with the contribution («J'ai mis ta question dans ma liste pour la rédaction.»)
  dispatch: RvDispatch;        // the clipping; the learner's part is in `contribution`
  kept: { words: { fr: string; gloss: string; claim_id: string; used: boolean;
                  outcome: "correct" | "incorrect" | "unscored" | null }[];  // 2026-10-03: the word's best rubric outcome over the session's evidence events («correct» once stays correct), stored at close so the kept-word mark survives a reload; null = never graded (and on closings stored before)
          claims: RvClaim[] };   // «Pour ton Relevé»: words + claims shown, with source lines
  question_kept_fr: string | null;   // an open question Romy keeps for the desk / next week
  vignette: VignetteView | null;     // WP-120 §4.3: the stamp minted at close; null when minting failed or is off
  colophon_fr: "La suite la semaine prochaine.";
};

// app/schemas/revue_vignette.py — also the items of GET /revue/vignettes ({ vignettes: VignetteView[] })
type VignetteView = {
  id: string;
  session_id: string;
  dossier_id: string;
  week: string;                      // ISO week, "2026-W40"; the stamp prints its number
  place_label_fr: string;
  ring: "headline" | "question" | "report";
  kept_contribution: boolean;
  pictogram_svg: string;             // the normalised pictogram, <svg viewBox="0 0 100 100">, house grammar
  headline_fr: string;               // the dispatch's headline as filed, else the dossier's title
  minted_at: string;                 // ISO datetime
};
```
Response `200 { "session": RvSessionView, "closing": RvClosing }`.

## 4. Errors (all routes)

| Status | `detail` | When |
|---|---|---|
| 401 | `"Not authenticated"` / `"Could not validate credentials"` | no or bad token (flag on) |
| 404 | `"Not Found"` (a string) | `REVUE_ENABLED` is false — every route |
| 404 | `{code: "revue_session_not_found"}` · `{code: "revue_dossier_not_found", dossier_id}` | flag on |
| 409 | `{code: "revue_session_active", session_id}` · `{code: "revue_week_filed", session_id}` · `{code: "revue_session_closed"}` · `{code: "revue_make_unavailable", kind}` | |
| 422 | FastAPI validation list, or `{code: "revue_unknown_option"}` | |
| 429 | the paid-route limiter (`rate_limited`) | once the Revue POSTs are listed in `PAID_ROUTES` |

## 5. The resume contract

1. The state (`revue_sessions.state`) is an append-only event log (`app/services/revue/state.py`). Only POSTs append.
2. `GET /revue/sessions/{id}` replays it: the same events give the same `thread` (same ids, same order),
   `beat`, `room`, `support`, `artifact` and `closing`. No model is called on a GET.
3. The client may drop its local copy at any time; reopening `/revue` calls `GET /revue/week`, sees `resume`, and
   loads the session. Romy's next turn picks up from the last six thread items (the provider's only memory).
4. One active session per learner per ISO week, enforced by a partial unique index
   (`uq_revue_sessions_one_active_per_week`, `WHERE status = 'active'`, PostgreSQL and SQLite) **and** a service check
   before insert (which returns `409 revue_session_active`).
5. Once closed, the session is read-only (`409 revue_session_closed` on turns and make); `GET` shows the `ended` page.

## 6. Phase 2 · «Les invités» (2026-10-02)

Everything below is additive: a phase-1 client that ignores unknown kinds, roles and fields keeps working.
A phase-1 session replays with the same items, except that the column-full line (`KEPT_LINE`) now projects as
`role: "fallback", reason: "budget"` (it was `reply`).

### 6.1 `reason` on fallback lines
| `reason` | When |
|---|---|
| `model_down` | the provider raised, answered nothing usable, or the cut reply was empty → «Je ne sais pas encore. On regarde ce que disent les sources ?» |
| `knowledge_refused` | the reply failed the season's Knowledge check twice (one regeneration) → the same authored line |
| `budget` | the column is full (100 % of `budget.turns`): no model call, the question is kept |
| `no_match` | a free request matched no dossier («Je n'ai que ça cette semaine…», in the `arrive` beat) |

```json
{"id": "5", "seq": 5, "at": "…", "kind": "line", "speaker": "romy_tremblay", "role": "fallback",
 "text_fr": "Je ne sais pas encore. On regarde ce que disent les sources ?", "translation": null, "glosses": [],
 "reason": "model_down"}
```

### 6.2 The `guest` item
```ts
type RvGuestItem = RvItemBase & {
  kind: "guest";
  cast_id: string;   // a plain string on the wire; today one of margaux_barman, lila_bonnet, camille_marchand, landlord_marchand, marin_leveque, augustin_de_roncourt
  text_fr: string;
  move: "enter" | "follow_up" | "disagree" | "moved";
  position: "for" | "against" | "moved" | null;   // the guest's stance after this line; "moved" stays moved
  reason_fr: string | null;   // on "enter" only, and only when the line does not already say it: the caption under the guest
  reason: "model_down" | "knowledge_refused" | "budget" | "no_match" | null;   // the schema's FallbackReason (all four);
                                                // a guest line only ever carries model_down or knowledge_refused (an authored line
                                                // from evergreen/guests/guest_lines.json stands in), else null
  glosses: RvGloss[];
};
```
Rules the server guarantees:
- **One guest per Papier.** A guest enters in `pursue` only (from the second learner turn, never in `facts`),
  never after the column is full: the angle's `guest_fit` brings that guest at the first `pursue` turn;
  otherwise the first guest of the topic (`policy.GUEST_AFFINITY`) whose topic words
  (`policy.GUEST_TOPIC_WORDS`) the learner's turn touches. Camille only once the learner chose her look
  (WP-116: `cast_variants` has `camille_marchand`).
- On entry the guest speaks their reason. Afterwards they may ask a follow-up, disagree, or change position
  after a learner's point (`move: "moved"`, `position: "moved"`), at most three lines after the entrance;
  a turn where they have nothing to add sends no `guest` item.
- Every guest line passed the Knowledge check for the learner's season position, has no relative date and
  is at most 25 words (one regeneration, then the authored line with `reason`).
- The stage lists the guest beside Romy from their entrance on (`stage.cast`).
- Order inside a turn's `items`: `mine, [shift simplify], line(reply|fallback), [uncertainty], [claims], [guest], [shift angle], [shift simplify], [shift bouclage|boucle], [line steer]`.

```json
{"id": "10", "seq": 10, "at": "…", "kind": "guest", "cast_id": "margaux_barman",
 "text_fr": "Ce que je sers au comptoir, ça vient de quelque part. Alors ça me regarde.",
 "move": "enter", "position": "for", "reason_fr": null, "reason": null, "glosses": []}
```
```json
{"id": "19", "seq": 19, "at": "…", "kind": "guest", "cast_id": "margaux_barman",
 "text_fr": "Bon. Vu comme ça, tu n'as pas tort.", "move": "moved", "position": "moved",
 "reason_fr": null, "reason": null, "glosses": []}
```

### 6.3 `RvEvidence` (the Papier rubric, `revue-rubric-v1`)
```ts
type RvEvidence = {
  outcome: "correct" | "incorrect" | "unscored";
  capability_known: boolean;          // the target word's can-do exists in the WP-L2 catalogue
  grader: "revue-rubric-v1";
  words: { fr: string; outcome: "correct" | "incorrect" | "unscored"; capability_known: boolean }[];   // every plan word
  fact_fit: "supported" | "unsupported" | "contradicted" | "not_applicable";
  register_note: "ok" | "vous_to_tu" | "tu_to_vous";   // a code; the client words it («Avec Romy, on se tutoie.»)
  pending: boolean;                   // §10e.8: the critic had not answered within 2 s; graded on the next turn (§2)
};
```
- `correct` needs a target word used correctly (grounded in a quote of the learner's own words) and no
  contradicted fact; `incorrect` an incorrectly used target word or a fact a shown claim contradicts; else
  `unscored`. A turn without any target word is `unscored` without a critic call.
- The Credit check runs on the turn and on each word: a correct use of a word no can-do lists is sent as
  `unscored`, `capability_known: false` — never mastery.
- Simplify on breakdown also counts an `unscored` turn that shows no grasp of the story (not a question, not a
  quick reply, no content word shared with the dossier), two in a row.

```json
{"outcome": "correct", "capability_known": true, "grader": "revue-rubric-v1",
 "words": [{"fr": "compte", "outcome": "unscored", "capability_known": false},
           {"fr": "marchés", "outcome": "correct", "capability_known": true}],
 "fact_fit": "supported", "register_note": "ok"}
```

### 6.4 Make: `headline_write`, `short_report`, Romy's lines
```json
// GET /revue/sessions/{id}/make (B1)
{"recommended": "headline_write",
 "options": [{"kind": "headline_choice", "options": [{"id": "h1", "text_fr": "…"}, {"id": "h2", "text_fr": "…"}, {"id": "h3", "text_fr": "…"}]},
             {"kind": "headline_write", "max_words": 14},
             {"kind": "reader_question", "seed_fr": null, "uncertainty_fr": null},
             {"kind": "short_report", "seconds": 30}],
 "intro": {"id": "12", "seq": 12, "at": "…", "kind": "line", "speaker": "romy_tremblay", "role": "make_intro",
           "text_fr": "Il me faut un titre. Tu l'écris ? Court, et vrai.", "translation": null, "glosses": [], "reason": null}}
```
```json
// POST … {"kind": "headline_write", "action": "write", "text_fr": "Paris et ses 91 marchés en plein air"}
{"kind": "headline_write", "accepted": true,
 "evidence": {"outcome": "correct", "capability_known": true, "grader": "revue-rubric-v1", "words": [{"fr": "marchés", "outcome": "correct", "capability_known": true}], "fact_fit": "supported", "register_note": "ok"},
 "made": {"kind": "headline_write", "text_fr": "Paris et ses 91 marchés en plein air", "contribution": [[0, 36]], "learner_fr": "Paris et ses 91 marchés en plein air"},
 "line": {"id": "14", "seq": 14, "at": "…", "kind": "line", "speaker": "romy_tremblay", "role": "make_done",
          "text_fr": "Je le prends. C'est ton titre.", "translation": null, "glosses": [], "reason": null}}
```
```json
// POST … {"kind": "short_report", "action": "report", "transcript": "Je suis au marché d'Aligre…", "mode": "voice"}
{"kind": "short_report", "evidence": {"…": "…"},
 "made": {"kind": "short_report", "text_fr": "Je suis au marché d'Aligre…", "contribution": [[0, 27]], "learner_fr": "Je suis au marché d'Aligre…"},
 "line": {"…": "…", "role": "make_done", "text_fr": "C'est enregistré. Je le mets dans mon papier."}}
```
- `headline_write` is graded by the rubric for fact fit and band (`grading.HEADLINE_WORDS`); a headline a shown
  claim contradicts is not filed (`accepted: false`, `made: null`, Romy: «Attention : les sources disent autre
  chose. Tu réessaies ?»). The dispatch takes the filed headline as written.
- `short_report` takes the transcript (the recording and its transcription are the client's, through the
  existing audio route) and grades it like a respond turn; it is filed as the artefact, and the dispatch keeps
  a headline of its own (a report is not a headline).
- `make_intro` and `make_done` are thread items like any line: they replay on resume.

### 6.5 Cost
Every model call the session makes records its `cost_usd` on its event (reply, guest line, rubric critic,
vocabulary, headline exercise, question, close). The close writes one pilot-ledger row
`event_type = "revue_session"`, `entity_type = "revue_session"`, `entity_id` = the session id,
`cost_usd` = the sum, `payload = {week, dossier_id, turns, guests, provider, grader}` — the cost report's
`revue` line reads it by event type.

## 7. Steps the planner deals («Le bureau», 2026-10-03)

The Revue's other desks reach the daily journey as **one optional step** after the ending (before the
«Lecture»), `kind: "desk"` in the journey snapshot (`app/schemas/daily_journey.py` `DeskStep`/`DeskPrompt`).
Advanced, never answered: each desk grades on its own routes; «Passer» or the desk's own end advances the day.

```ts
type DeskPrompt = {
  desk: "relecture" | "radio" | "correcteur";
  title_fr: string;                      // the dossier's title
  dossier_id: string | null;             // radio, correcteur
  relecture: RelectureOffer | null;      // relecture: the offer of GET /revue/relecture/offer
  seconds: number | null;                // radio: the bulletin's length, rounded to 5 s
};
```

| `desk` | Target (read at planning time, nothing created) | The client mounts (`components/atelier-v2/journey/DeskStep.tsx`) | Grades through |
|---|---|---|---|
| `relecture` | `relecture.offer(db, user)` — the oldest Papier closed ≥ 6 weeks ago with a kept question or headline, never re-read | `CarteRelecture` on `relecture` (a pair already stored is fetched with `GET /revue/relecture/{id}` and shown) | `POST /revue/relecture/{session_id}` (`carteClient().relectureAnswer`) |
| `radio` | `radio.radio_week(...)` — the rotation's next unheard bulletin, none heard today (the chip's rule) | `RadioBulletin` (listen first → read → the dictée → «C'est entendu») | `GET /revue/radio/{id}`, `POST …/dictee`, `POST …/heard` |
| `correcteur` | `correcteur.week_for(...)` — the week's first dossier not yet corrected | `CorrecteurDesk` on a new draft (`POST /revue/correcteur/{id}`); «Dans le Relevé» at the result continues the day | `POST /revue/correcteur/{id}/marks` |

**The rule** (`journey_day_shapes.due_desks` / `choose_desk`, `journey_planner._desk_step`):
at most one desk a day; each desk at most once an ISO week, on or after its own seeded weekday (Mon–Fri, so a
missed one still has the weekend); only on an ordinary practice day — never «jour du Papier», «jour court», a
season tentpole or the first day, never on a classic (non-practice) day; only while its flag is on
(`REVUE_ENABLED` for La Relecture, plus `REVUE_RADIO_ENABLED` for La Radio, `REVUE_CORRECTEUR_ENABLED` for Le
Correcteur) and its offer is non-empty. A desk is priced at 120 s (Relecture) or 150 s (Radio, Correcteur),
reserved from the day's drills, and the day gives up one ordinary recall item for it (the last item after the
ending); a day whose budget cannot hold it, or whose shape needs every recall it has, plans no desk. «Dealt this
week» is read from the learner's earlier journeys' `desk` steps.

