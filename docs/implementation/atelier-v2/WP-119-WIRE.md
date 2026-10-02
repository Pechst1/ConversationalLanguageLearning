# WP-119 phase 1 · Le Papier de Romy — the wire (frozen 2026-10-02)

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

type RvMakeKind = "headline_choice" | "reader_question";   // phase 1; phase-2 kinds are never sent

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
| `mine` | `text_fr`, `mode: "text" \| "voice"` | the learner's bubble | every learner turn |
| `claims` | `claims: RvClaim[]` (1–2) | `RvClaim` cards (the client folds them into «2 faits sur la table» once the learner speaks) | the claims Romy cites in that turn, first time shown only |
| `uncertainty` | `text_fr` | `RvUncertainty` (dashed, «Les sources ne le disent pas») | Romy names a gap the dossier lists |
| `shift` | `reason: "simplify" \| "angle" \| "bouclage" \| "boucle"`, `angle: {id, fr} \| null` | `RvShift` hairline (`role="status"`) | support changed / angle changed / the column reached 80 % or 100 % |
| `made` | `made: RvMade` | the artefact as filed (headline or reader question) | the `make` beat |

`line.role`: `"purpose"` (the arrive headline bubble), `"place_note"` (phase-1 honest stand-in plate line),
`"reply"` (a pursue answer), `"steer"` (the bouclage steer, its own bubble right after the reply), `"fallback"`
(an authored line: knowledge check refused twice, or the model is down), `"close"` (Romy's closing line).
`speaker` is always `"romy_tremblay"` in phase 1 (guests are phase 2: a `guest` kind will be added, never
`line` with another speaker before then). `glosses` lists the plan's vocabulary items that occur in `text_fr`.
`translation` is present only when the provider gave one and `support.translation != "none"`.

Client-only kinds from the design (`claimsFolded`, `typing`) are never sent.

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
    make_options: RvMakeKind[];              // phase 1: ["headline_choice", "reader_question"]
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
  evidence: { outcome: "correct" | "incorrect" | "unscored"; capability_known: boolean; grader: string };
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
   "text_fr": "Et là, je n'ai rien. Les sources ne le disent pas. On formule la question ensemble ?", "translation": null, "glosses": []},
  {"id": "11.u", "seq": 11, "at": "…", "kind": "uncertainty", "text_fr": "Les sources ne disent pas si les prix au marché sont plus bas qu'au supermarché."}],
 "beat": "pursue", "room": {"used": 2, "phase": "open", "remaining_turns": 10},
 "support": {"glosses": "tap", "translation": "on_request", "reading_target_words": 90, "vocab_target": 5, "level": 0},
 "quick_replies": [{"label": "On formule la question", "send_fr": "On formule la question ensemble ?"}, {"label": "Plus", "send_fr": "Dis-m'en plus."}],
 "steer_to_make": false,
 "evidence": {"outcome": "unscored", "capability_known": false, "grader": "revue-unscored-adapter-v1"}}
```

### 3.6 `GET /revue/sessions/{id}/make` — the make options
Builds the headline exercise on the first call and stores it in the session's state (the one GET that writes;
later calls reuse it, so the options never change under the learner); never exposes its answer.
```ts
type RvMakeOffer = {
  recommended: RvMakeKind;     // reader_question when the learner raised a question the sources cannot answer
  options: (
    | { kind: "headline_choice"; options: { id: string; text_fr: string }[] /* 3 */ }
    | { kind: "reader_question"; seed_fr: string | null /* the learner's open question */; uncertainty_fr: string | null }
  )[];                          // an unavailable option is absent, never greyed
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
```
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
{ kind: "reader_question"; made: RvMade }
```
Errors: `409 {"detail": {"code": "revue_make_unavailable", "kind": "headline_choice"}}`;
`422 {"detail": {"code": "revue_unknown_option"}}`; `409 revue_session_closed`.

### 3.8 `POST /revue/sessions/{id}/close` — Romy does something with it
Body `{}`. Idempotent: a second call returns the stored closing. Writes Romy's `NPCMemory`
(`memory_type="interaction"`, French, `scene_id` = the session id) and sets `status: "closed"`.
```ts
type RvClosing = {
  romy_line_fr: string;        // what she did with the contribution («J'ai mis ta question dans ma liste pour la rédaction.»)
  dispatch: RvDispatch;        // the clipping; the learner's part is in `contribution`
  kept: { words: { fr: string; gloss: string; claim_id: string; used: boolean }[]; claims: RvClaim[] };   // «Pour ton Relevé»: words + claims shown, with source lines
  question_kept_fr: string | null;   // an open question Romy keeps for the desk / next week
  colophon_fr: "La suite la semaine prochaine.";
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
