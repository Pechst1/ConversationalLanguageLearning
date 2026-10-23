# WP-119 phases 1–2 · Le Papier de Romy — the wire (frozen 2026-10-02; phase 2 «Les invités» added the same day, §6; the story's own picture 2026-10-14, §8)

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
  plate_kind: "story" | "painted" | "season" | "stand_in";   // §8: "story" = the story's own picture; absent before → "season"
  picture_words: RvGloss[];    // §8: on the story's picture, the words it shows (glossed); else []
  dress: "coat" | "suit" | "apron" | "raincoat" | "sport" | "scarf_only" | "chef" | "hi_vis";  // Toi's outfit
  cast: RvStageMember[];       // [{id: "romy_tremblay", hold: "notebook"}, {id: "user", hold: null}]
                               // phase 2: a guest on stage stands right after Romy: [romy, {id: "margaux_barman", hold: null}, user]
};

type RvStoryCard = {
  dossier_id: string;
  title_fr: string;
  headline_fr: string | null;  // 2026-10-18: six words or fewer, for Home's «À la une !» card (else title_fr)
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

type RvMakeKind = "headline_choice" | "headline_write" | "reader_question" | "short_report" | "caption";   // phase 2: + headline_write (B1+), short_report (B1+); §8: + caption («La légende»)

type RvMade = {
  kind: RvMakeKind;
  text_fr: string;             // the headline, or the reader question as sent to the desk
  contribution: [number, number][];   // the learner's part of text_fr (yellow underline + «toi»)
  learner_fr: string | null;   // what the learner wrote (reader_question, a written headline or caption), null for a pick
};

type RvDispatch = {
  kicker_fr: string;           // "Le Papier de Romy · semaine 40"
  headline_fr: string;
  body_fr: string[];           // three lines
  contribution: [number, number][];   // spans into headline_fr
  byline_fr: string;           // "Romy Tremblay, avec toi · d'après Ville de Paris (paris.fr) et Wikipédia…"
  sources: RvSource[];
  picture_url: string | null;  // §8: the story's own picture, printed under the headline; null when none was painted
  caption_fr: string | null;   // §8: its caption (the learner's after «La légende», else the desk's); null without a picture
  caption_by_learner: boolean; // §8: the caption is the learner's (marked «toi»)
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
| `summary` | `speaker: "romy_tremblay"`, `text_fr`, `translation: string \| null`, `glosses: RvGloss[]` | `RvLead` «Ce qui s'est passé»: the text, a listen chip and, where the band translates, «Traduire» (2026-10-18; it was `HeardLine` «Écouter le résumé») | the `arrive` beat: the dossier's lead at the learner's band (`leads.a1` / `leads.a2`), B1+ its `summary_fr` |
| `line` | `speaker`, `text_fr`, `role`, `translation: string \| null`, `glosses: RvGloss[]` | `RvLine` (speech bubble) | every Romy turn |
| `mine` | `text_fr`, `mode: "text" \| "voice"`, `register_note: "vous_to_tu" \| "tu_to_vous" \| null` | the learner's bubble (and, with a note, the register note under it) | every learner turn; `register_note` from that turn's `evidence` event (2026-10-03), so the note survives a reload |
| `claims` | `claims: RvClaim[]` (1–2) | `RvClaim` cards (the client folds them into «2 faits sur la table» once the learner speaks) | the claims Romy cites in that turn, first time shown only |
| `uncertainty` | `text_fr` | `RvUncertainty` (dashed, «Les sources ne le disent pas») | Romy names a gap the dossier lists |
| `shift` | `reason: "simplify" \| "angle" \| "bouclage" \| "boucle"`, `angle: {id, fr} \| null` | `RvShift` hairline (`role="status"`) | support changed / angle changed / the column reached 80 % or 100 % |
| `made` | `made: RvMade` | the artefact as filed (headline or reader question) | the `make` beat |
| `guest` | `cast_id`, `text_fr`, `move`, `position`, `reason_fr`, `reason`, `glosses` | the guest's bubble (phase 2, §6.2) | a guest's line |

`line.role`: `"purpose"` (the arrive headline bubble), `"place_note"` (phase-1 honest stand-in plate line),
`"look"` (§8: on the story's own picture, Romy points at what it shows, before her purpose; its `glosses` are the picture's words),
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
                                             // B1+: ["headline_write", "reader_question", "short_report"]
                                             // (headline_choice is A1–A2 only since 2026-10-23)
    budget: { turns: number; minutes: number };
  };
  stage: RvStage;
  beat: RvBeat;                              // arrive (0 learner turns) · facts (1) · pursue (≥2) · make (a make started) · close (closed)
  room: RvRoom;
  thread: RvThreadItem[];
  quick_replies: RvQuickReply[];
  steer_to_make: boolean;                    // the column is at bouclage/bouclé, nothing is made yet and own_line
  own_line: boolean;                         // 2026-10-23: the learner typed or said a line of their own (a quick-reply
                                             // chip is not one); «Écrire le papier» and the make wait for it
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
  own_line: boolean;           // 2026-10-23: as on the session view
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
                               // else caption when the story's own picture is painted (§8; the headline when the
                               // learner's last Papier was a caption), else headline_write (B1+), else headline_choice
  options: (
    | { kind: "headline_choice"; options: { id: string; text_fr: string }[] /* 3 */ }
    | { kind: "headline_write"; max_words: number }          // phase 2, B1+
    | { kind: "reader_question"; seed_fr: string | null /* the learner's open question */; uncertainty_fr: string | null }
    | { kind: "short_report"; seconds: number /* 30 */ }      // phase 2, B1+
    | { kind: "caption"; format: "choice" | "write"; picture_url: string;   // §8: only with the story's own picture
        options: { id: string; text_fr: string }[]; words: RvGloss[]; max_words: number }
        // 2026-10-23: always "write"; options are the three captions to pick from at A1–A2 only after a refused try, else []
  )[];                          // an unavailable option is absent, never greyed; order as listed
  intro: RvThreadItem /* line, role "make_intro" */ | null;  // phase 2: written once, on the first GET
};
```
`headline_choice` is absent when the Distinguishable check fails (a distractor no shown claim contradicts, or
the answer is unsupported), after one regeneration, and from B1 (2026-10-23). `409 revue_session_closed` after the
close; `409 revue_make_needs_a_line` until the learner has typed or said a line of their own (`own_line`).

### 3.7 `POST /revue/sessions/{id}/make` — make something
Body, discriminated by `kind` + `action`:
```ts
| { kind: "headline_choice"; action: "pick"; option_id: string }
| { kind: "reader_question"; action: "propose"; text?: string /* ≤ 400, any language; default: the open question */ }
| { kind: "reader_question"; action: "send"; text_fr: string /* 1..300: the proposal, possibly edited */ }
| { kind: "headline_write"; action: "write"; text_fr: string /* 1..160 */ }                       // phase 2
| { kind: "short_report"; action: "report"; transcript: string /* 1..1200 */; mode?: "voice" | "text" /* default voice */ }  // phase 2
| { kind: "caption"; action: "caption"; option_id?: string /* choice */; text_fr?: string /* write, 1..200 */ }       // §8
```
The body is discriminated by `action` (`pick | propose | send | write | report | caption`); a `kind` that does not go
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
// caption (§8)
{ kind: "caption"; format: "choice" | "write"; accepted: boolean;
  correct: boolean | null; answer_id: string | null;    // choice only
  evidence: RvEvidence | null;                          // write only
  made: RvMade | null; line: RvLineItem | null /* make_done */;
  options: { id: string; text_fr: string }[] }          // 2026-10-23: a refused written caption at A1–A2: the three to pick from
```
`pick` also returns `line` (phase 2): Romy's `make_done` line.
Errors: `409 {"detail": {"code": "revue_make_unavailable", "kind": "headline_choice"}}` (also for
`headline_write` / `short_report` below B1, `headline_choice` from B1, and `caption` without the story's picture);
`409 revue_make_needs_a_line` before a line of the learner's own; `409 revue_caption_write_first` for a caption
pick before a refused written try (2026-10-23); `422 {"detail": {"code": "revue_unknown_option"}}`; `409
revue_session_closed`. A pick (headline or caption) is never credited: `contribution: []`, and the close's byline
says «Romy Tremblay» without «avec toi» unless the filed thing holds words the learner wrote.

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
  colophon_fr: "La suite la semaine prochaine." | "La suite demain.";  // «demain» when the Papier is daily (§12.2)
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
| 409 | `{code: "revue_session_active", session_id}` · `{code: "revue_week_filed", session_id}` · `{code: "revue_session_closed"}` · `{code: "revue_make_unavailable", kind}` · `{code: "revue_make_needs_a_line"}` · `{code: "revue_caption_write_first"}` (2026-10-23) | |
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
| `relecture` | `relecture.offer(db, user)` — the oldest Papier closed ≥ 6 weeks ago with a kept question, a written headline or (§8) a written caption, never re-read | `CarteRelecture` on `relecture` (a pair already stored is fetched with `GET /revue/relecture/{id}` and shown) | `POST /revue/relecture/{session_id}` (`carteClient().relectureAnswer`) |
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

## 8. The story's own picture (WP-119 §8.4, 2026-10-14)

Each story's picture is painted once at the morning intake (`plates.paint_story`, `revue_story_pictures`) and is
final; a session never paints. Every shape below is optional to read: a payload from before has none of it
(`plate_kind` reads as `"season"`, `picture_words` as `[]`, the dispatch's picture as `null`).

### 8.1 The stage and Romy's «Regarde»
On the site (`places[0]`) with its picture painted, the stage carries it: `plate_url` is the picture,
`plate_kind: "story"`, `place_is_real: true` (nothing stands in, so no `place_note`), and `picture_words` lists
the words the picture shows, glossed in `plan.gloss_language`; they also lead `plan.vocabulary`. The desk's
caption is **not** on the stage: it is the answer of «La légende» (§8.2), sent after the pick. `plate_url_second`
(§1) is always set with the picture: the second place's plate, else the site's own, so the band has moved on
(`plate_switched`, at the guest's entrance or at make) by the time «La légende» and the dispatch print the picture.
```json
{"place_id": "marche_aligre", "place_fr": "Le marché d'Aligre, un matin", "plate_url": "https://…/revue-stories/evergreen-marche-du-dimanche-3f9c….webp",
 "plate_place_id": "marche_aligre", "place_is_real": true, "dress": "coat", "plate_kind": "story",
 "picture_words": [{"fr": "marché couvert", "gloss": "Markthalle", "claim_id": "c3"}, {"fr": "en plein air", "gloss": "im Freien", "claim_id": "c3"}],
 "plate_url_second": "/assets/serial/locations/marche_canal.webp", "plate_switched": false,
 "cast": [{"id": "romy_tremblay", "hold": "notebook"}, {"id": "user", "hold": null}]}
```
The arrive beat's lines are then `look`, `purpose`:
```json
{"id": "1.l", "seq": 1, "at": "…", "kind": "line", "speaker": "romy_tremblay", "role": "look",
 "text_fr": "Regarde : le marché en plein air, et derrière, le marché couvert.", "translation": null,
 "glosses": [{"fr": "marché couvert", "gloss": "Markthalle", "claim_id": "c3"}, {"fr": "en plein air", "gloss": "im Freien", "claim_id": "c3"}], "reason": null}
```
`plate_kind` otherwise: `"season"` (a season plate), `"painted"` (a place plate painted for the Revue),
`"stand_in"` (another place's plate, with Romy's `place_note`).

### 8.2 «La légende» (`caption`)
**Since 2026-10-23 every band writes it first** (`format: "write"`, the picture's words as tiles); a caption
under the band's fewest words (`grading.CAPTION_WORDS`: 2 · 3 · 4 · 5) is refused like a contradicted one
(«Un peu court pour une légende…»), and at A1–A2 a refused try returns the three captions in `options` (and the
make offer carries them on a resume): a pick then files the picture's own caption, never credited
(`contribution: []`, «La légende que tu as choisie part sous l'image»). What follows describes the first build.

Offered (and listed in `plan.make_options`) only while the story's picture is on the stage (at A1–A2, only when
the builder gave its two decoy captions). `choice` at A1–A2:
three captions, one says what the picture shows (the order fixed per session, the answer kept by the server until
the pick). `write` at B1+: `options` is empty, `max_words` is the band's (`grading.CAPTION_WORDS`: 10 · 12 · 16 ·
20), `words` are the tiles.
```json
// GET /revue/sessions/{id}/make (A2): the caption option
{"kind": "caption", "format": "choice", "picture_url": "https://…/revue-stories/….webp",
 "options": [{"id": "l1", "text_fr": "Un marché en plein air, un matin, entre les étals de fruits et légumes."},
             {"id": "l2", "text_fr": "Un marché fermé, un soir de pluie."},
             {"id": "l3", "text_fr": "Un supermarché vide, un lundi matin."}],
 "words": [{"fr": "marché couvert", "gloss": "marché sous un toit", "claim_id": "c3"}, {"fr": "en plein air", "gloss": "dehors", "claim_id": "c3"}],
 "max_words": 12}
```
```json
// POST … {"kind": "caption", "action": "caption", "option_id": "l2"}: a wrong pick files the picture's own caption, uncredited
{"kind": "caption", "format": "choice", "accepted": true, "correct": false, "answer_id": "l1", "evidence": null,
 "made": {"kind": "caption", "text_fr": "Un marché en plein air, un matin, entre les étals de fruits et légumes.", "contribution": [], "learner_fr": null},
 "line": {"…": "…", "role": "make_done", "text_fr": "Celle-là, l'image la contredit. On garde l'autre."}}
```
```json
// POST … {"kind": "caption", "action": "caption", "text_fr": "Un marché en plein air, devant le marché couvert, un matin."} (B1)
{"kind": "caption", "format": "write", "accepted": true, "correct": null, "answer_id": null,
 "evidence": {"outcome": "correct", "capability_known": true, "grader": "revue-rubric-v1", "words": [{"fr": "marché couvert", "outcome": "correct", "capability_known": true}, {"fr": "en plein air", "outcome": "correct", "capability_known": true}], "fact_fit": "supported", "register_note": "ok"},
 "made": {"kind": "caption", "text_fr": "Un marché en plein air, devant le marché couvert, un matin.", "contribution": [[0, 59]], "learner_fr": "Un marché en plein air, devant le marché couvert, un matin."},
 "line": {"…": "…", "role": "make_done", "text_fr": "C'est ta légende. Elle part sous l'image."}}
```
- A written caption is graded by the rubric (`kind: "caption"`) against the claims shown plus what the picture
  shows (the desk's caption as a claim `picture`); a contradicted one is not filed (`accepted: false`, `made:
  null`, Romy: «Attention : l'image ou les sources disent autre chose. Tu réessaies ?»). A choice body without
  `option_id`, or with an unknown one, is `422 revue_unknown_option`; an empty `text_fr` too.
- A caption is not a headline: the dispatch keeps its own and prints the picture under the caption (§8.3); the
  vignette rings `headline`; the words a written caption uses are kept as `used`.

### 8.3 The dispatch, Le Relevé, La Relecture
`RvDispatch` (and every `ReleveEntry` of `GET /revue/releve`) carries `picture_url`, `caption_fr` and
`caption_by_learner` (§1): the picture as the close printed it, under the learner's caption after «La légende»
(a filed written caption; a right pick before 2026-10-23), else under the desk's. A caption is never sent without its picture. The
client prints the credit «Illustration · Le Papier» under every caption. `RelectureOffer.kind` gains `"caption"`:
a Papier whose written caption was filed comes back after six weeks with its `plate_url` (the picture) and
`prompt_fr` «Regarde l'image : quelle légende écrirais-tu aujourd'hui ?»; the new caption is graded as a caption.

### 8.4 The painter's admin route
`POST /revue/admin/paint` (admin only): paints what the period's kiosk is missing, each picture once and final,
within the service's daily cap. `?period=` (default the current one), `?limit=1..40`, `?enqueue=true` (default:
`{"status": "enqueued", "task_id": …}`) or `false` (paints in the request, about 35 s a picture, and returns the
report `{"period", "status": "painted" | "limit" | "budget" | "off: <reason>", "painted", "pictures": {dossier_id:
{"story": url | reason, <place_id>: url | reason}}, "cost_usd"}`). The morning intake queues the same painting.


## 9. «Au comptoir» (WP-119, owner 2026-10-19)

The Papier as five short screens (spec `WP-119-AU-COMPTOIR.md`). Behind `REVUE_COMPTOIR_ENABLED` (off): while
it is off nothing below is served — no route, the new fields keep their defaults (`mode: "chat"`, `comptoir:
null`, `question_fr: null`, `cast: null`, `comptoir_page: null`), no morning call.

### 9.1 What changes on the existing shapes
```ts
type RvStoryCard = { /* §3.1 */
  question_fr: string | null;   // the question of the day, when the switch is on and the story has takes
  cast: string[] | null;        // the three regulars at the counter, in seat order (Romy, the topic's guest, Gus)
};
type RvSessionView = { /* §3.4 */
  mode: "chat" | "comptoir";    // fixed at the start (the first `choice` event), for the session's life
  comptoir: RvComptoirView | null;
};
type RvClosing = { /* §3.8 */ comptoir_page: RvComptoirPage | null };
type RvMade = { kind: /* … */ | "opinion" };  // the learner's quote; text_fr = what printed, learner_fr = only what they typed or said
```
A comptoir session has no thread (no Romy arrival): `thread: []`, and `turns`, `GET/POST make` answer `409
{code: "revue_comptoir_session"}`. `POST /close` builds «La page» without a model call (needs the opinion: else
`409 revue_comptoir_out_of_order`).

### 9.2 `RvComptoirView`
Only the learner's band (`a1`, `a2`, `b1`; B2 reads b1) and translations in the learner's gloss language (`tr`,
`null` for a French gloss language). Nothing is sent before its step: the liar (`intox.by`), the true value and
the distractor (`options`, `fix`) only once the learner named the liar or used two tries; the
step-4 material (`kit`) from the opinion step; the reply only once the opinion is settled (2026-10-23: no longer
after Romy's marks); Romy's corrected sentence never before it prints.
```ts
type RvComptoirText = { fr: string; tr: string | null };
type RvComptoirView = {
  step: "read" | "takes" | "intox" | "opinion" | "page";   // derived from the acts by replay
  steps: ("read" | "takes" | "intox" | "opinion" | "page")[];  // the dots: four when the band has no intox
  band: "a1" | "a2" | "b1";
  question: RvComptoirText;                     // «Aligre ouvre six jours sur sept. Bonne idée ?»
  read: { dateline_fr: string; lead: RvComptoirText; sources: RvSource[] };
  cast: { id: string; name_fr: string; role_fr: string; stance: "pour" | "contre" | "nuance";
          take: RvComptoirText; reaction: "agree" | "disagree" | null }[];   // seat order
  has_intox: boolean;                           // «3 avis · 1 intox cachée»
  vote: "pour" | "contre" | "nuance" | null;    // the gut vote
  intox: {                                      // from the intox step on, when the band has one
    quotes: { cast_id: string; name_fr: string; role_fr: string; stance: string; quote_fr: string }[];
    tries: string[]; resolved: boolean; found: boolean | null; by: string | null;
    hint_claim: RvClaim | null;                 // after a wrong guess: the claim to reread
    ask: RvComptoirText | null;                 // «Combien de jours par semaine, en vrai ?»
    options: string[];                          // A1–A2: right and distractor, in a per-session order
                                                // (B1+ writes the correction from an empty field: no prefill since 2026-10-23)
    fix: { correct: boolean; answer_fr: string; line_fr: string /* the right sentence, always */;
           wrong_fr: string; right_fr: string; claim: RvClaim | null; caught: RvComptoirText } | null;
  } | null;
  kit: { input: "tiles" | "frame" | "free"; phrase: RvComptoirText;
         reasons: Record<Stance, RvComptoirText[]>; frames: Record<Stance, RvComptoirText>;
         bank: RvComptoirText[] /* A2 only */; opponents: Record<Stance, string> /* who answers each side */ } | null;
  opinion: { stance: Stance; learner_fr: string /* as first given, with the A2 frame */;
             draft_fr: string;                  // the learner's words at their last try
             proof: "clean" | "marked" | "fixed" | "corrected" | "as_written";   // 2026-10-23, §9.5
             marks: { span_fr: string; start: number; kind: "accord" | "conjugaison" | "genre" | "orthographe"
                      | "mot" | "ordre" | "manque" }[];   // `marked` only: the learner's words to fix, at most three
             tries: number; max_tries: number /* 2 */;
             printed_fr: string | null;         // what goes to print, once settled; null while `marked`
             reply: { by: string; name_fr: string; line: RvComptoirText } | null;   // once settled
             comebacks: RvComptoirText[] /* A1–A2: «Pas du tout !», «Un peu…», the desk's */;
             comeback: { text_fr: string; index: number | null; last_word: RvComptoirText } | null } | null;
};
```

### 9.3 `POST /revue/sessions/{id}/comptoir` — one act
Body `RvComptoirRequest {act, guest_id?, value?, text?, mode?: "text" | "voice", reason_index?, index?}`:

| act | fields | when |
|---|---|---|
| `vote` | `value`: pour · contre · nuance | until the opinion is given (may change) |
| `react` | `guest_id`, `value`: agree · disagree | after the vote; a guest only after the ones before them |
| `intox_who` | `guest_id` | the intox step; two tries, then `by` is revealed |
| `intox_fix` | A1–A2 `value` (one of `options`); B1+ `text` | after the liar is named or revealed; once |
| `opinion` | `value` (the side, default the vote); A1 `reason_index`; A2+ `text` | after the reactions and the fix; once |
| `opinion_fix` | `text` (the whole sentence again); or `value: "romy"` after one try | while the opinion is `marked` (2026-10-23) |
| `comeback` | A1–A2 `index` (0–2); B1+ `text` | after the opinion; once |

Response `200 RvComptoirResult {session: RvSessionView, error_fr: string | null}`. An act already recorded
(`intox_fix`, `opinion`, `comeback`, the same vote or reaction) returns the session unchanged: a double submit
never calls the model twice. `error_fr` says why an act the learner can fix was not recorded: since 2026-10-23
an opinion under the band's floor (A2 4 words after the frame, B1+ 12: «C'est un début ! Encore un peu :
pourquoi ? 4 mots au moins.»), a B1+ intox correction under 4 words («Une phrase entière, s'il te plaît : dis à
Gus ce qui est vrai.»), a fix that changed nothing («Rien n'a changé : regarde les mots soulignés.»). §9.5 says
how the opinion is checked.

| Status | `detail` | When |
|---|---|---|
| 404 | `"Not Found"` | `REVUE_ENABLED` is false (before auth). `REVUE_COMPTOIR_ENABLED` only decides which sessions start at the counter: a session started while it was on plays to its end after it is turned off |
| 409 | `{code: "revue_not_comptoir"}` | a chat session |
| 409 | `{code: "revue_comptoir_out_of_order", step, act}` | an act before its step, or after the close; re-render from `GET` |
| 422 | FastAPI validation list, or `{code: "revue_comptoir_bad_act", act}` | an unknown act, guest, side, option or chip |

Listed in `PAID_ROUTES`.

### 9.4 `RvComptoirPage` («La page», at the close)
```ts
type RvComptoirPage = {
  question_fr: string; dateline_fr: string; standfirst_fr: string;   // the lead's first sentence
  quotes: { cast_id: string; name_fr: string; role_fr: string; stance: Stance; quote_fr: string }[];  // ×3
  mine: { cast_id: "user"; name_fr: "Toi"; role_fr: ""; stance: Stance; quote_fr: string };  // what printed
  proof: "clean" | "fixed" | "corrected" | "as_written" | null;   // 2026-10-23: how it reached print (null before)
  votes: { pour: number; contre: number; nuance: number };   // the three regulars and the learner
  intox: { by: string; name_fr: string; wrong_fr: string; right_fr: string; source_name: string } | null;
  phrase_fr: string;   // the phrase of the day at the learner's band
  words: string[];     // the kept words (also in `kept.words`)
};
```
The dispatch: kicker «Le micro-trottoir de Romy», headline = the question, body = [the standfirst, «Toi : « … »»],
`contribution: []`, byline «Romy Tremblay, avec toi» only when words the learner typed or said are printed (never
for A1's tiles). Romy's line: «Merci ! Ta voix est dans le micro-trottoir.» The vignette rings `report`. The kept
words (2026-10-23) are only the plan's words the learner met at the counter (the lead, the takes, the facts
shown, the question), the ones they used first, plus one word of the A2 bank they used when they used none.

### 9.5 Romy's proof (2026-10-23)
The opinion at A2+ makes one model call (`comptoir_edit`, prompt `comptoir-edit-v3`): Romy's corrected sentence
(kept back as the target, never shown before print), her hints and the reply of `opponents[side]`. The marks are
the learner's own words where they differ from the target (a word diff; typography, the first capital and the
punctuation aside), with the kind of slip, the model's hint winning where it covers them; at most three.
- No marks: `clean`, printed as the target («Dans le journal · relu par Romy»).
- Marks: `marked`. Nothing prints and nobody answers; the learner sends the sentence again (`opinion_fix`). A fix
  that matches the target, or that a new check finds clean, is `fixed` («corrigé par toi»); after the second try
  still wrong, or `value: "romy"` after one, `corrected` (her target prints, the words she changed lit, «corrigé
  par Romy»).
- The call fails or its checks refuse the edit: `as_written`, the learner's sentence prints with typography only
  («tel que tu l'as écrit»), never «relu par Romy». An A1 learner who types instead of the tiles: `as_written`.
- A1's tiles: `clean` (correct by construction), plain «Dans le journal».
`POST /close` needs a settled opinion (`409 revue_comptoir_out_of_order` while `marked`).
