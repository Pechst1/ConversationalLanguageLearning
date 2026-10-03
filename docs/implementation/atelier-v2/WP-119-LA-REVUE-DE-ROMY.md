# WP-119 · La Revue de Romy: real-world French inside the learner's fictional life

*Defined 2026-10-02 from the owner's idea: a segment in which a session walks the learner through
something true about France this week, drawn in the app's own style, with the learner's character on
site and the cast taking part. Revised the same day after the owner's review: the first draft scripted
every moment before the learner arrived. This version makes the facts dependable and lets the
encounter develop around the learner. The owner also asked for the old `use_news` path to be
re-engineered rather than extended.*

## 1. Goal

Romy, the journalist of the cast, is working on a piece and has an **editorial purpose**: understand
a change, explain a disagreement, choose an angle, or prepare a short dispatch. The learner joins her
on site, in a painted place, dressed for it. Romy has sourced facts she is sure of and open questions
she is not. The learner can ask, challenge an interpretation, compare with home, pursue a detail, or
help her decide. Along the way the learner uses French, picks up words that the facts needed, and the
encounter ends with something made: a headline, a reader question, a short report, a message to
Margaux. Romy does something with what the learner said. The words and the facts go to the Relevé.

**The central acceptance test.** *When the learner asks a relevant, unexpected question, Romy
follows it coherently, preserves factual grounding, and still helps them finish something meaningful
in French.* Every phase in §10 is measured against this sentence before anything else.

What the package builds underneath is the **news-to-story pipeline** the generated-seasons vision
(WP-116 §12) depends on: intake → an **editorial dossier** → checks on meaning → a **session plan**
→ a **stage**. La Revue is its first consumer. A season gap day is its second (§11).

**Non-goals.**
- **No real person is ever drawn.** Not by the image model, not as a rig, not as a silhouette.
  Places are drawn; people are told. This is a *staging* decision (§8), not a dossier rule: the
  dossier keeps the names a story needs.
- No season progression. A cast member in La Revue can care, ask, disagree and remember; the
  season's beats, reveals and arcs stay with their owner (`season/director.py`, WP-111).
- No new fonts or colours ([[design-proposals-stay-in-av2]]). One 3D-press primary.
- No republishing. The learner reads our French, anchored to the source by short verbatim quotes
  with attribution (§4.2).
- No second story engine. Conversation, grading, memory and the Relevé are the existing ones
  (CONTINUOUS-STORY.md, WP-14 lineage; WP-62 long memory; WP-66 day shapes).

## 2. What exists today (inventory of 2026-10-02, branch codex/serial-season-engine-production)

### The news path, and why it is re-engineered rather than extended
- `app/services/news_service.py` (`NewsService`, 1 000 lines). Four French factual RSS sources
  (`FRANCE_SOURCE_REGISTRY:28`: Le Monde, RFI, France 24, Franceinfo) and satire feeds
  (`FEUILLETON_SATIRE_SOURCE_REGISTRY:58`) as tone references. Three entry points:
  - `fetch_news_context:140` — English-leaning Google News / Substack digest for the old conversation
    sessions (`endpoints/sessions.py:126`, `auto_context_service.py:81`). Legacy.
  - `fetch_france_context:190` — three French headlines for mission prompts (`missions.py:2134`).
  - `fetch_feuilleton_daily_seed:280` — the one the serial uses. One seed per day for all learners,
    keyed by date + interests, 28 h TTL, version `feuilleton-daily-seed-v2`.
- **How the seed reaches a story.** `serial.py:671` sets `thread.news_seed` only when the authored
  brief says `include_news_panel`; `GraphicNovelScheduler.create(use_news=…)` calls
  `_source_snapshot` (`graphic_novel.py:1582`), which tags the snapshot `learner_visible` and formats
  a digest into the episode prompt (`:4164 source_usage`). The learner-facing source card is built
  in `graphic_novel.py:7051` only for those editions.
- **What is wrong with it for this package.**
  1. **It is a boolean.** `use_news=True/False` at creation time. A consumer cannot ask for a topic,
     a week, an angle or a place; it gets "today's top cluster".
  2. **It is an untyped dict.** Every consumer re-reads `snapshot.get("items")[0].get(...)`.
  3. **It mixes evidence with presentation.** Title, summary, satire references, digest text and
     interests live in one cached object, so one cache entry decides what every learner gets.
  4. **Title + summary only.** `article_fetch_policy: "No full article scraping in v1"`. Claims
     cannot be anchored to anything a learner could check.
  5. **No week, no language in the cache key**, and the TTL is 28 hours for a weekly idea.
  6. **Safety is a term list** (`FEUILLETON_SENSITIVE_TERMS:68`) on the headline plus a regex for
     names (`_extract_named_people:494`). Adequate as a first filter, not as the only check.
  7. **Scoring encodes the feuilleton's taste** (`_score_feuilleton_item:544`: +2 politics, +2
     named people). Taste belongs to the consumer, not the intake.
- **What is kept.** RSS fetch and parse (`_fetch_rss_items:784`, `_parse_rss_items:808`), the
  language check (`_looks_like_language:946`), dedupe and clustering, the sensitive list as a first
  filter, the cache backend (`app/utils/cache.py`, Redis when configured).
- **Phase 5 landed (2026-10-03).** The serial reads the week's `EditorialDossier` through
  `app/services/revue/feuilleton_bridge.py`: `dossier_for_feuilleton(user, week)` (via
  `weekly.available_for_week`, ranked by the Revue's topic-recency rule, copied, not imported),
  `snapshot_for_prompt` (the old seed's keys + `learner_visible`), `source_card`, `thread_seed`
  (`thread.news_seed` = snapshot + the dossier JSON). `GraphicNovelScheduler.create(dossier=…)`;
  `use_news=True` is deprecated for one release (logs, picks the recommended dossier).
  `fetch_feuilleton_daily_seed` and its seed-only helpers (satire references, curated seed,
  summary, digest) are deleted; dedupe, clustering, scoring, cleaning, named-people and the
  sensitive filter stay marked `# kept for revue.intake`. `fetch_news_context` and
  `fetch_france_context` are listed in `news_service.LEGACY_ENTRY_POINTS` with their callers.

### The world this plugs into
- **Romy Tremblay** — Québécoise journalist investigating Solvel's purchase of cafés in the 10th
  and 11th (`app/data/season/s1/world.json:86`). Her newsroom has a plate
  (`season/world.py:44 "newsroom"`). The item bank's "Romy texts you from the newsroom" family
  (`item_bank.py:2074`) was found by WP-107 to come "from nowhere in the learner's story" (`:2509`).
  This package gives it somewhere to come from.
- **Conversation.** `journey_conversation.py` grades respond turns against a versioned rubric with
  the register dimension (WP-33, shown since WP-66). CONTINUOUS-STORY.md §14D specifies extracting
  proposals, questions and choices from an exchange and adapting the current conversation to a
  relevant unexpected proposal. La Revue is the first surface that needs exactly that at full width.
- **Memory.** `NPCMemory` (`app/db/models/npc.py:129`, WP-62): what each character knows, with
  provenance. `trust_of`, `known_about_learner`, `tu_since` per cast member (WP-96).
- **Forbidden reveals.** `season/director.py:147 _must_not` applies `gaps.json must_not[].patterns`
  plus `unless` flags to a draft. That is the existing check for "does this line reveal something
  the learner should not know yet". (`season/fidelity.py` is the bible-text checker, a different
  thing.)
- **The drawn cast** (WP-116). Nine rigs, `RigProps {mood, mouth, blink, hold?, variant?}`
  (`rig-kit.ts:41`), `PanelStage.tsx` draws plate + up to three speakers. There is no `outfit`.
  WP-118 makes Toi parametric and keeps the heavy coat canon in the story.
- **Plates.** `scripts/art/atelier_art.py:54 PLATE_STYLE`: risograph, palette lock, "No people, no
  animals, no readable text or signage." No "paint a new place from a brief" entry yet.
- **Exercises.** `journey_contracts.py` formats `CHOICE, TILES, SHORT_ANSWER, TRANSFORM, CLASSIFY,
  WORD_BANK, MATCH_PAIRS, LISTEN_TAP, UNSCRAMBLE, WHO_SAID`; step kinds `SCENE, RECALL, RESPOND,
  RESOLUTION, RULE, FORGE, READ`; five validated `DayShape`s (WP-66). The no-spoil gates
  ([[atelier-no-spoil-three-gates]]) and the critic are the quality bar.
- **Level.** `chrome_language.level_band(level)`; `daily_journey.level_band` per day.
- **Schedules.** Celery beat in `app/celery_app.py:57` (nightly, weekly, every 15 min).

## 3. Three parts, not one object

The first draft had one cached "dossier" carrying facts, level, translations, outfit, guest and
exercises. One cache entry then decided too much, and every learner at a band got the same
encounter. This version separates three concerns. Both La Revue and future seasons reuse the first;
each encounter gets its own second and third.

### 3.1 Editorial dossier — what is true, with provenance (`revue/dossier.py`)
Shared by every learner and every consumer. Built once per story per week, cached under
`revue:dossier` by `(week, story_id)`, 8-day TTL, version `dossier_version = "revue-v1"`.

```json
{
  "id": "2026-w40-vendanges-bourgogne",
  "week": "2026-W40",
  "topic": "food",
  "title_fr": "Des vendanges précoces et courtes en Bourgogne",
  "summary_fr": "…",
  "claims": [
    {"id": "c1", "kind": "fact",
     "fr": "Les vendanges ont commencé fin août dans plusieurs domaines, deux semaines plus tôt que la moyenne.",
     "quote": "ont commencé fin août, deux semaines plus tôt", "source_id": "le_monde_front",
     "url": "https://…", "published_at": "2026-09-29", "confidence": "reported"},
    {"id": "c2", "kind": "interpretation",
     "fr": "Pour certains vignerons, c'est un signe du climat qui change.", "attributed_to": "plusieurs vignerons cités",
     "quote": "…", "source_id": "rfi_france", "url": "…", "published_at": "2026-09-28"}
  ],
  "entities": [{"name": "Bourgogne", "kind": "place"}, {"name": "…", "kind": "person", "role": "président du syndicat"}],
  "uncertainties": ["Les sources ne disent pas si les prix vont changer."],
  "angles": [
    {"id": "a1", "fr": "Ce que ça change pour qui achète du vin", "purpose": "understand_change"},
    {"id": "a2", "fr": "Les vignerons sont-ils d'accord entre eux ?", "purpose": "explain_disagreement"}
  ],
  "places": [{"id": "vignoble_bourgogne", "name_fr": "Un vignoble en Bourgogne",
              "brief": "rows of vines on a slope, a stone hut, late-summer light", "known": false}],
  "time_scope": {"happening": "2026-08-25/2026-10-05", "relevant_until": "2026-10-20"},
  "sources": [{"id": "le_monde_front", "name": "Le Monde", "url": "…", "published_at": "…"}],
  "evergreen": false
}
```

- **Claims are typed** `fact | interpretation | forecast`, each with a verbatim `quote` (≤ 40 words
  after whitespace and quote-mark folding, [[ios-smart-quote-normalization]]) and, for
  interpretations and forecasts, an `attributed_to`. This is the fact-versus-interpretation
  distinction the Tone check relies on (§4.2).
- **Entities keep names.** A story about a minister needs the minister's name to be understood.
  Whether anyone appears in an illustration is decided on the stage (§8), never here.
- **Uncertainties are first-class.** Romy can say "les sources ne le disent pas" because the dossier
  says so. They are also where reader questions come from (§5.4).
- **Angles** are the editorial purposes available for this story. A session picks one, or the
  learner does.
- **No level, no language, no outfit, no exercises.** Those are the session plan's.

### 3.2 Session plan — this learner, this time (`revue/session.py`)
Built on entry, persisted with the journey (`DailyJourney` row, shape `REVUE`, §5), pinned for
resume. Versioned `plan_version`.

```json
{
  "dossier_id": "2026-w40-vendanges-bourgogne",
  "learner": {"band": "A2", "ui_language": "de", "interests": ["cuisine", "voyage"]},
  "chosen_by": "learner | recommended",
  "angle_id": "a1",
  "purpose": "understand_change",
  "support": {"glosses": "tap", "translation": "on_request", "simplify_on_breakdown": true,
              "reading_target_words": 90, "vocab_target": 5},
  "vocabulary": [{"fr": "la vendange", "gloss": {"de": "die Weinlese"}, "claim_id": "c1"}],
  "activities": {"default": ["arrive", "facts", "pursue", "make", "close"],
                 "make_options": ["headline_choice", "reader_question", "tell_margaux", "short_report"]},
  "stage": {"place_id": "vignoble_bourgogne", "plate_url": "…", "dress": "apron",
            "cast": [{"id": "romy_tremblay", "hold": "notebook"}, {"id": "user"}],
            "guests_available": [{"id": "margaux_barman", "reason": "she buys her wine from a Bourgogne cousin"}]},
  "budget": {"turns": 14, "minutes": 8}
}
```

### 3.3 Conversation state — what happened (`revue/state.py`, on the journey row)
Appended per turn, never regenerated: what was discussed (claim ids touched), questions the
learner raised and whether the dossier could answer them, choices made (angle changed, activity
picked), the guest's entrances and positions, the artefact being made and its revisions, and
learning evidence (words used correctly, rubric results) through the **existing evidence policy**.
Reopening a Revue replays this state; nothing is re-generated except the next turn.

## 4. Intake and checks on meaning (`app/services/revue/`)

```
revue/
  policy.py      topics, sensitive first filter (moved here, imported by news_service), support defaults per band
  intake.py      RSS → candidates → clusters → sourced stories for the week
  sources.py     article text fetch, excerpt store (§4.1)
  dossier.py     the editorial dossier and its builder (one structured LLM call)
  checks.py      the checks on meaning (§4.2)
  evergreen/     authored editorial dossiers (§4.3)
  session.py     dossier + learner → session plan (§5, §6)
  state.py       conversation state
  encounter.py   the turn loop: Romy, the learner, guests (§5, §7)
  stage.py       plan → stage (plate key, dress, cast, props) (§8)
  plates.py      "paint a new place" on top of scripts/art/atelier_art.py (§8.1)
```

### 4.1 Intake and sources
- Runs **weekly** (Celery beat, Monday 05:00 Europe/Paris) and on demand with `refresh=True`. It
  produces **several** editorial dossiers per week (target 6: two food or culture, two city or
  society, one sport or nature, one politics), not one per band. Cached by `(week, story_id)`.
- Candidates come from `NewsService._fetch_rss_items` over a grown `FRANCE_SOURCE_REGISTRY` (add
  culture, gastronomy and sport feeds with `topic_tags`). Ranking is recency, cluster size and
  topic spread. The feuilleton's taste (+2 politics, +2 names) leaves the intake.
- For each chosen story, fetch the article page (`httpx`, 6 s, respects `robots.txt`, one attempt),
  extract main text (`trafilatura`, new dependency; `readability-lxml` fallback). **Store only** the
  `quote`s and a hash of the full text; the full text is held for the build and discarded. If the
  fetch fails, build from title + summary; if fewer than two claims anchor, try the next candidate.
- Sensitive stories (`policy.SENSITIVE`, the existing list) are excluded at intake as a first
  filter. This is a product choice about what a language lesson is for, not a factuality check.

### 4.2 Checks on meaning
Each check answers one question about one generated thing. A failed check names its reason
(`revue_check_failed`, reason code) the way `gaps.json` refusals do.

| Check | Question | On failure |
|---|---|---|
| **Anchor** | Is every `quote` a verbatim substring of the source text (folded)? Is every claim's `fr` entailed by its quote (critic, yes/no)? | drop the claim; < 2 claims → drop the dossier |
| **Attribution** | Does every `interpretation` and `forecast` carry `attributed_to`? Does the `fr` of a `fact` contain no evaluative adjective or verb of judgement (critic rubric: *is this a report or an opinion?*)? | retype the claim as `interpretation` with attribution, or drop it |
| **Temporal** | Does `time_scope.happening` fit the week? Is nothing in the `fr` phrased relative to a date the session cannot know ("jeudi", "demain") unless `time_scope` pins it? Is `relevant_until` ≥ the week's Sunday? | rewrite with absolute dates; expired → drop |
| **Knowledge** | For every cast line: does the speaker know what they say? Provenance from `NPCMemory` and `world.json`; reveals via `director._must_not` with the season's global list for the learner's current position. | regenerate once with the knowledge context tightened; then the authored default line |
| **Distinguishable** | For every exercise with options: is exactly one option supported by the claims shown and is every distractor contradicted by at least one shown claim? For a `SHORT_ANSWER`: does the private rubric name the claims a correct answer must reflect? | regenerate the exercise; then skip it (an exercise is optional, §5.3) |
| **Render** | Is `dress` in the catalogue, is `place_id` registered or paintable, is every `hold` an authored prop, are all cast ids real, is Camille's look chosen if Camille is on stage? | drop the unknown field; the rig renders what it knows |
| **Credit** | Is every evidence write routed through the existing evidence policy with a rubric version? Unknown capability → unknown, never mastery. | the turn is unscored, the conversation continues |

What is **not** a check: whether both sides would nod (agreement is a poor factuality test), whether
a word like "lettre" or "feu" appears (ordinary words are a weak substitute for the reveal check),
whether counts are exact (targets, §6).

### 4.3 Evergreen dossiers
`revue/evergreen/*.json`: 12 authored editorial dossiers in the same schema with real, dated public
sources (`la rentrée`, `le Beaujolais nouveau`, `la galette des rois`, `les soldes`, `la Fête de la
musique`, `le Tour`, `la Toussaint`, `le marché du dimanche`, `une grève`, `le bac`, `le 14 juillet`,
`Noël au marché`), each with `time_scope` so the Temporal check picks the right ones. They pass every
check in CI (`tests/test_revue_evergreen.py`), fill a thin week, and are the only content in the
test and walk harnesses ([[story-engine-fake-provider-harness]]).

## 5. The encounter: a default route with room to leave it

### 5.1 Entry: a recommendation, alternatives, a request
The Revue card on La Une shows **one recommended story** (by topic spread and the learner's
interests), **two alternatives**, and a free-text line «Autre chose ?». A free request is matched
against the week's dossiers; if nothing fits, Romy says so in French and offers what she has. The
choice is recorded as `chosen_by`.

### 5.2 Romy's purpose
Each dossier angle carries a `purpose`: `understand_change`, `explain_disagreement`, `choose_angle`,
`prepare_dispatch`. Romy opens with it as a need, not a lesson: *"Je dois expliquer ça en trois
lignes pour demain et je n'y arrive pas. Tu m'aides ?"* The purpose is what the ending resolves.

### 5.3 The route
The default order is `arrive → facts → pursue → make → close`. **Opening and ending are fixed; the
middle adapts.**

| Beat | Fixed? | What happens |
|---|---|---|
| **arrive** | yes | Plate, Romy, Toi in the dress. Two narrator sentences set the place. Romy states her purpose and the summary, read aloud. |
| **facts** | yes, but short | Romy puts the claims she is sure of on the table, one or two at a time, in the session's French, with tap-glosses. Interpretations are introduced as such («d'après plusieurs vignerons…»). The source line sits under them. |
| **pursue** | no | The learner's turn drives: a question, a challenge, a comparison with home, a detail to follow. Romy answers from the claims, names an uncertainty when the sources are silent, proposes to formulate the question together, or changes angle. A guest may enter here (§7). The budget bounds it, not a script. |
| **make** | one of several | Something gets made, chosen by the plan or by the learner: pick or write the headline; formulate the reader question Romy will send to the desk; explain the story to Margaux in three sentences (she replies); record a 30-second report (speak). |
| **close** | yes | Romy does something with the contribution (§5.4). The words and claims go to the Relevé with their source line. «La suite la semaine prochaine.» |

- **Exercises appear when useful.** A `MATCH_PAIRS` over the vocabulary is offered only for words
  the learner has not yet used correctly in the conversation (evidence from the state). A learner
  who has already used «la vendange» right is not asked to match it.
- **Simplify on breakdown.** Two failed comprehension turns in a row (unscored, off-topic, or an
  explicit «je ne comprends pas») switch the session to the next support level: shorter French,
  glosses shown, translation offered. The dossier does not change; the plan does.
- **Budget.** `turns` and `minutes` from the plan. At 80 % Romy steers to `make`; at 100 % she
  closes with what exists. A Revue is never longer than a standard day.

### 5.4 Romy does something with it
The `close` beat is generated from the conversation state, not from a template: she revises the
headline with the learner's angle, adds the learner's question to her list for the desk, writes a
three-line dispatch that incorporates what the learner noticed, or admits the sources did not
answer and keeps the question. Worked example, from the review: in a story about a market moving,
the learner asks whether older residents can reach the new site. The dossier has no claim on it; it
is an uncertainty. Romy acknowledges the gap, they phrase the question together in French, and the
session ends with a reader question instead of a headline exercise. That is agency with a bounded
outcome, and it is the acceptance test.

## 6. Level sets support and depth, not topics

The first draft banned politics below B1. That was paternalistic: an A1 learner can care about an
election, a B2 learner can want to talk about bread. Level now decides **how much help** and **how
deep the default goes**; every story is open at every band.

| Band | Default support | Default depth | Planning targets (not caps) |
|---|---|---|---|
| A1 | glosses shown, translation one tap away, Romy repeats in simpler words unasked | the change and who it touches, in the present tense | ~60 words read, 5 words |
| A2 | glosses on tap, translation on request | + one interpretation, attributed | ~90 words, 5 words |
| B1 | glosses on tap | + the disagreement, in café register: what changes for a person | ~140 words, 7 words |
| B2+ | none by default, «plus» for the procedure and institutional vocabulary | the procedure and the actors | ~200 words, 7 words |

- **"Tell me more."** Every band can ask for more; depth is a stretch the learner chose, and the
  support level stays. Curiosity justifies a manageable stretch; breakdown triggers §5.3's simplify.
- **Targets flex.** The builder aims at the targets; the checks do not enforce counts. A story with
  two strong claims is two claims.
- The `REVUE_POLITICS_MIN_BAND` flag from the first draft is gone. What remains is the sensitive
  first filter at intake (§4.1), which is about subject matter, not level.

## 7. The cast: agency and relevant memory

- **Preference, not table.** `policy.GUEST_AFFINITY` becomes a *preference* the plan consults
  (`guests_available` with a `reason`). A guest enters during `pursue` or `make` **because they have
  a reason to care**, stated in the plan and spoken on entry: Margaux because she buys from that
  region, Marin because the NGO works on it, Gus because there is money in it, Camille because it
  is her quartier, Lila because her pupils asked. A guest can ask a follow-up, disagree with Romy or
  the learner, and change their mind when the learner makes a point. One guest per Revue in v1.
- **Memory, bounded, not banned.** The first draft forbade reading season memory. Instead the
  encounter gets a **small knowledge context** per cast member on stage: what this character knows
  about the learner (`known_about_learner`, `trust_of`, `tu_since`), the `NPCMemory` rows with
  provenance that mention the learner or this topic, and nothing marked as a future reveal. The
  Knowledge check (§4.2) runs `director._must_not` on every generated line with the learner's
  current season position, so unrevealed events stay protected without word bans.
- **Writing back.** The encounter writes `NPCMemory` rows for what the character witnessed: *"semaine
  40, au vignoble : tu as dit à Margaux que tu goûterais"*. A season day may read them through the
  normal retrieval. Season progression (episode, arc, flags) is never written from here.
- **Fallback.** If generation fails or a line fails the Knowledge check twice, an authored line per
  cast member and topic (`evergreen/guest_lines.json`) keeps the guest in character.

## 8. The stage

### 8.1 Plates for new places
- `revue/plates.py:paint(place)` builds a prompt from **`PLATE_STYLE` + a place template** and
  nothing else: `"{brief}, France, seen from where a visitor would stand."` The brief goes through
  the Render check and a staging rule: it may contain no entity of `kind: person` from the dossier
  and no word from `policy.PLATE_FORBIDDEN` (person, crowd, face, portrait, party flag, logo). One
  image call (as `atelier_art.py:_call`), `palette_lock`, WebP, uploaded next to the season plates,
  cached by `place_id` forever, shared by every learner.
- Known places reuse `SEASON_ONE_LOCATIONS`. New place ids go in a `revue_places` table
  (`id, name_fr, plate_url, brief, created_at`) so a season day can reuse "the vineyard the Revue
  painted in week 40".
- Flag `REVUE_PLATE_GENERATION_ENABLED` (default off). Off: an unknown place falls back to the
  nearest known plate by `policy.PLACE_FALLBACKS`, and Romy says where they really are.
- **Feasibility, 2026-10-02 (owner asked).** Five news-style briefs went through the existing pipeline
  (`PLATE_STYLE` + the template above, 1536×1024, medium): the empty hémicycle, a strike-day metro
  platform, a Nuit Blanche facade, a Bourgogne vineyard at harvest, a press room with an empty podium.
  All five rendered, no refusals, 31–39 s each, no people in any of them, and they sit beside the
  existing newsroom plate without a seam (`docs/design-reference/revue/plates/`, `contact-sheet.webp`,
  `log.json`). Two things the model added unasked: readable minutes on the metro board, and national
  flags in the press room and the hémicycle. So the template gains a negative clause the style lock
  did not carry: *"no flags, emblems or logos, no readable text or numbers"*, and the Render check
  gets a cheap post-check for large saturated tricolour bands near a podium (drop and repaint once).
  National colours in architecture are fine; party emblems are not, and the model does reach for them.
- **Specificity (owner's question, same day).** A brief written as a *kind* of place paints a kind of
  place: the generic Aligre brief gave an anonymous iron market hall. A brief that **names the place
  and its landmarks** («le marché d'Aligre, place d'Aligre, 12e: the stalls in the small square, the
  brocante tables of books and crockery, the low marché Beauvau hall with its tiled roof and
  iron-and-glass lantern, the rue d'Aligre with its cafés») paints Aligre; Longchamp named with its
  cantilevered grandstand and the moulin came back recognisable
  (`docs/design-reference/revue/plates/contact-sheet-specificity.webp`). Rules that follow:
  1. The dossier builder writes `place.brief` as *name + three distinctive, checkable landmarks +
     light*, never as a type. The Render check refuses a brief for a `kind: place` entity that does
     not contain that entity's name.
  2. Well-known public places are named; a private or unremarkable place (a kitchen, a classroom) is
     typed, because naming would invent.
  3. The staging rule is unchanged: landmarks yes, people never, and the negative clause above.
- **Per-beat plates (owner's question).** One plate per dossier for the whole encounter is the
  phase-1 behaviour (the stage shrinks from full to band to a strip; the image stays). The cost
  argument for one plate is weak once plates are per place and shared: a second plate per dossier is
  cents. Proposed, as an open decision in §12: a dossier may carry **two places**, the site of the
  story for `arrive` and `facts`, and a second view for `pursue`/`make` (an interior, the other end
  of the square, the place where the guest belongs) switched at the guest's entrance. Not more than
  two: the plate is the room the conversation happens in, not a slideshow.
- **Real people (owner's decision, same evening).** Three briefs with people went through the same
  pipeline with the style lock's "no people" clause replaced by *"people in the same flat screen-print
  style, from a distance or from behind, never as portraits"*: Macron and Le Pen named and «recognisable»
  at the rostrum, a generic minister before a full chamber, a named chef at a bistro pass
  (`contact-sheet-people.webp`). No refusals, 36–37 s each. The named politicians came out as two
  small anonymous figures; the chef is a chef. In this style and at this distance the model does not
  produce likenesses, so a plate with people is lively and safe, and it never identifies anyone: Romy
  and the narrator do («regarde, à la tribune, c'est…»). Rules that follow: `PLATE_FORBIDDEN` keeps
  only what clashes or misleads (portrait, close-up, party emblem, logo, readable text); people,
  crowds and national colours are allowed; the plate style used for Le Papier is `PLATE_STYLE` with
  the people clause above instead of "No people". The authored season plates keep "no people"
  because the drawn cast is their people.

### 8.2 `outfit`: the first new field of the stage language
- `RigProps.outfit?: Outfit` with the catalogue `coat` (default, canon), `suit`, `apron`,
  `raincoat`, `sport`, `scarf_only`, `chef`, `hi_vis`. Toi draws the torso from it; head, tuque and
  posture do not change. Other rigs ignore it in v1.
- **Canon boundary with WP-118.** The heavy coat stays canon in the story. `outfit` applies **only on
  the Revue stage**; season panels never pass it. One test in `cast-rig.test.js` asserts `PanelStage`
  drops `outfit` unless `surface === "revue"`.
- `dress` comes from `policy.DRESS_FOR_PLACE` (chamber → suit, cellar or kitchen → apron, stadium →
  sport, rain → raincoat, worksite → hi_vis), validated by the Render check.

### 8.3 Who stands where
Romy in front with `notebook` (an authored prop, WP-116 §12.3 tier 1). Toi from behind in the
dress. A guest enters when §7 says so and stands beside Romy. Camille obeys the WP-116 phase-2 rule.

## 9. Flags, cost, caching

| Flag | Default | Meaning |
|---|---|---|
| `REVUE_ENABLED` | off | the card, the page, the weekly beat |
| `REVUE_PLATE_GENERATION_ENABLED` | off | §8.1; off → known-plate fallback |
| `REVUE_ARTICLE_FETCH_ENABLED` | on | §4.1; off → RSS only |
| `REVUE_STORIES_PER_WEEK` | 6 | intake target |
| `REVUE_CADENCE` | `weekly` | `weekly` or `daily` (§12) |

Cost: per week for all learners, one builder call per story and one plate per new place. Per
learner per Revue, a conversation of ~14 turns through the existing respond pipeline plus a guest's
lines and the close. Target: at most the cost of a standard day plus 30 %; the cost report
(`atelier_correction_cost.py`) gets a `revue` line and phase 1 measures it before phase 2 starts.

## 10. Phases and acceptance — conversation first

The first draft postponed the conversation to phase 2 and the learner's choice to phase 3. Those
are the two things that tell us whether the experience works, so they come first, on known plates
and a small set of sourced stories.

| Phase | What lands | Done when |
|---|---|---|
| **0 · The three parts** | `dossier.py`, `session.py`, `state.py`, `policy.py`; `checks.py` with Anchor, Attribution, Temporal, Distinguishable, Render, Credit; 12 evergreens passing in CI; `news_service` imports the sensitive list from policy | `pytest tests/test_revue_dossier.py tests/test_revue_checks.py tests/test_revue_evergreen.py` green; a claim with a relative date fails Temporal; a headline exercise with an uncontradicted distractor fails Distinguishable |
| **1 · The encounter** | `encounter.py` on the existing conversation and grading; `/revue` page behind the flag with entry (recommendation, alternatives, free request), the five-beat default route, adaptable `pursue`, two `make` options (headline, reader question), `close` from state; 6 hand-sourced dossiers for the current week plus evergreens; known plates only; Toi with `outfit`, Romy with `notebook`; Knowledge check for Romy's lines | **the acceptance test passes in a scripted walk** (E-3): the learner asks a question the dossier cannot answer, Romy names the gap, they phrase the reader question, the session closes with it; resume replays state; cost line reported |
| **2 · The cast** | guests with reasons, knowledge context from `NPCMemory`, guest lines through `director._must_not`, `NPCMemory` write-back, authored guest defaults, `tell_margaux` and `short_report` make options | a guest line that would reveal a future tentpole is refused in test and the default line shows; a guest changes position after a learner's point in a scripted walk |
| **3 · The weekly intake** | `intake.py`, `sources.py`, Celery beat, the grown source registry, the La Une card, Relevé source lines, `DayShape.REVUE` in planner and player (5 steps, within budget, never on a tentpole day, at most once a week) | fixture RSS → 6 dossiers for a week, every one passing the checks; the 59-day life test (WP-111) still green with one Revue a week on gap days |
| **4 · New plates** | `plates.py`, `revue_places`, `PLATE_FORBIDDEN` and the person-entity staging rule; owner reviews the first six plates | a brief with a person entity never reaches `_call`; the week's cost report |
| **5 · The feuilleton moves over** | `GraphicNovelScheduler.create(dossier=…)`, `serial._news_seed` → intake, `_source_snapshot` typed, `fetch_feuilleton_daily_seed` deleted, `fetch_france_context` and `fetch_news_context` marked legacy with callers listed | `tests/test_feuilleton_audit_regression.py` unchanged and green; the source card renders the same fields |

Each phase is one commit, `feat(wp-119 phase N): …`, with its row added to §13. A phase is done
only when used (owner walk or E-3 screenshots), per the process rule in the running log.

## 10b. Phases 2–5 in detail (after the owner's decisions of 2026-10-02)

The table in §10 stays the summary. This section is the brief each phase lead works from; every
item names its files so the leases do not overlap.

### Phase 2 · «Les invités» (guests, grading, outfits per angle)
- **Guests with a reason** (`revue/encounter.py`, `revue/policy.py`): `guests_available` from
  `GUEST_AFFINITY` as a preference; a guest enters during `pursue` or `make` when their reason fits
  the dossier's angle (the builder sets `guest_fit: cast_id|null` per angle). On entry: one spoken
  reason; afterwards the guest can ask a follow-up, disagree with Romy or the learner, and change
  position after a learner's point (the provider returns `guest_position: for|against|moved`).
  One guest per Papier. Camille only once her look is chosen.
- **Knowledge context** (`revue/knowledge.py`): per cast member on stage, `known_about_learner`,
  `trust_of`, `tu_since` (WP-96) and the `NPCMemory` rows mentioning the learner or the topic, with
  provenance, minus anything the season marks as a future reveal. Every guest line through
  `check_knowledge` (`director._must_not` with the learner's position). Authored default lines per
  cast member and topic in `revue/evergreen/guest_lines.json`. Write-back: one `NPCMemory` row per
  guest for what they witnessed. Season progression is never written.
- **Grading, real** (`revue/grading.py`): a Papier rubric built from the claims shown and the plan's
  vocabulary (did the learner's French say something the claims support, in the register the band
  expects, using which target words); scored by the critic model with a versioned rubric id; the
  evidence policy gets `capability_known` from a vocabulary → capability registry lookup where one
  exists, else unknown. Replaces the `unscored` adapter; `simplify on breakdown` can then count
  unscored turns as §5.3 says. If `journey_conversation` exposes a reusable rubric scorer by then,
  reuse it; do not fork its grading.
- **Make options**: `headline_write` (B1+, graded by fact-fit and band through the rubric) and
  `short_report` (30-second spoken report; transcription through the existing audio route).
- **Outfits per angle** (`revue/session.py`): `dress` from the angle's `participation` field set by
  the builder (`none|helps|works|formal`) → coat / apron / hi-vis / suit. Setting alone never dresses.
- **Wire** (`WP-119-WIRE.md`, `schemas/revue.py`): `reason` on fallback lines (`model_down`,
  `knowledge_refused`), Romy's make and close lines from the server, `guest` thread item kind.
- **Cost line**: `cost_usd` per session summed into the cost report's `revue` line.
- **Tests**: a guest line that would reveal a future tentpole is refused and the default shows; a
  guest changes position after a learner's point; a real rubric scores a correct use of a target
  word as evidence; outfit follows participation, not place.

### Phase 3 · «Le kiosque» (intake, the Revue day, the Relevé)
- **Intake** (`revue/intake.py`, `revue/sources.py`, `app/tasks/revue.py`): Monday 05:00
  Europe/Paris; grown `FRANCE_SOURCE_REGISTRY` with culture, gastronomy, sport feeds and a
  `fetch_policy` note per source (allows / refuses bots); the dossier builder from RSS + article
  text (one structured call per story), all checks on meaning, target `REVUE_STORIES_PER_WEEK`,
  topic spread 2/2/1/1, evergreen top-up. `refresh=True` from an admin route.
- **The Revue day**: `DayShape.REVUE` in `journey_contracts` and the planner (5 steps, within budget,
  never on a tentpole day, at most once a week); the journey player mounts `RvEncounter`; La Une's
  hero on that day (already wired, `lib/revue-une.ts isRevueDay`).
- **Second Papier in a week**: allowed from the chip; counts for evidence; does not change `filed`.
- **Daily-ready**: `revue_sessions.week` → `period` (ISO week or ISO date by `REVUE_CADENCE`); the
  partial unique index follows; the kiosk shows the last seven when daily.
- **The Relevé**: `RvReleveSection` with claims and words and their source lines, after Le Registre.
- **Migrations**: the merge revision once the password-reset migration has landed.
- **Tests**: fixture RSS → six dossiers passing every check; the 59-day life test with one Papier a
  week on gap days; daily mode in a unit test flips the period column.

### Phase 4 · «Les planches» (plates)
- `revue/plates.py`: `PLATE_STYLE` with the people clause (§8.1), the brief rule name + three
  landmarks + light, the Render check that a `kind: place` entity's name appears in the brief,
  `PLATE_FORBIDDEN` as decided (§12.4), one paint per place cached in `revue_places`, S3 upload,
  `REVUE_PLATE_GENERATION_ENABLED` on in staging first.
- **Two places per dossier** (§12.7): the builder names a second view; the stage switches at the
  guest's entrance (phase 2) or at `make`.
- **Owner review**: the first six new plates and the W40 set as a contact sheet before the flag is
  on in production.

### Phase 5 · «Le feuilleton» (the old path moves over)
- `GraphicNovelScheduler.create(dossier: EditorialDossier | None)`; `serial._news_seed` → intake;
  `_source_snapshot` and the source card typed; `fetch_feuilleton_daily_seed` deleted;
  `fetch_france_context` and `fetch_news_context` marked legacy with their callers listed;
  `tests/test_feuilleton_audit_regression.py` unchanged and green.

### After phase 5
WP-120 «La Carte» (places on a map, the vignette) builds on phases 2–4: it needs closed sessions
with a place (done), geo on places (its own phase A), and the second plate for the card's band.

## 10c. Leftovers after phases 2, A, B and C (one lead, about an hour)

Small items that landed as follow-ups in the reports of 2026-10-02. One agent, one commit,
`chore(wp-119/120): leftovers`.
- **Copy**: the close press reads «Classer la Revue»; rename to «Classer le Papier» in
  `web-frontend/components/revue/revue-copy.ts` (fr/en/de) and the tests that assert it.
- **Wire doc**: `closing.vignette` (`VignetteView | null`) in `WP-119-WIRE.md` §3.8; the guest
  `reason` values (all four) and `cast_id` as a plain string in §6, as the schema has them.
- **Cost line**: `scripts/pilot_digest.py` reads the `revue_session` ledger rows (written at close)
  into a `revue` line: sessions, turns, guests, cost.
- **This week's dossiers**: set `vignette_object_fr`, and per angle `participation` and `guest_fit`
  on the six `weekly/2026-W40/*.json` (the evergreens have the vignette object; none has the two
  angle fields yet). Run `tests/test_revue_weekly.py`.
- **Weak pictograms**: regenerate the bac, the guitar, the maillot jaune and the fireworks with a
  tighter object description (a flat view, one object, no scene), through `pictogram_for` with
  `refresh=True` (add the flag); the owner picks on a new contact sheet.
- **Replayable evidence**: `outcome` on `RvClosedWord` so the kept-word marks and the register
  notes survive a reload (frontend lead's finding #5).
- **Read-only head**: a read-only replay of an active session shows the real beat bar, not the
  ended one.
- **Migration merge**: once the other session's password-reset migration (`b9d1f3a5c7e0`) is
  committed, one merge revision over it and `d4f6a8c0e2b4`; the WP-69 schema guard goes green.
- **Mock dress**: the dev mock still dresses Toi in an apron at the market; align with §12.5.

## 10d. Two quality passes (after phase 3)

- **Full-suite stability.** The backend suite grew by about 400 tests this week. Run the full
  suite twice (`pytest -p no:randomly` and with random order), watch the known order-dependent
  and midnight flakes, and fix any revue test that depends on the wall clock (the week helpers
  take `today`; use them). Owner: E-2's lead.
- **Real-model sample.** Ten Papier sessions against this week's six dossiers with the real
  provider and the real critic, three bands, read for: natural French, grounding (every Romy
  claim traceable to a dossier claim), the guest's voice against `world.json`, the rubric's
  fairness on a correct and an incorrect use of a target word, and cost per session. Transcripts
  under `docs/implementation/atelier-v2/evidence/revue-sample-<date>/`, with models, prompt
  versions and cost, the way CONTINUOUS-STORY §14F does it for the season. Report what fails;
  no expected-failure markers.

## 10e. Phase 6 · «La voix de Romy» (from the real-model sample of 2026-10-03)

The sample (`docs/implementation/atelier-v2/evidence/revue-sample-2026-10-03/`, ten sessions, real
provider and critic, US$0.16) passed grounding, the rubric, the knowledge check and relative dates,
and failed natural French in 10/10. The causes are mechanical. Decisions taken by the lead.

1. **No ids in anything the learner reads.** The reply prompt says «cite claims by id»; Romy says
   «d'après c2». Fix: the provider returns `claims_cited` separately and the text must name the
   *source* («d'après Le Monde», «selon l'Insee») or nothing; a deterministic check over reply,
   guest, close, question-proposal and translation text refuses any token matching `\b[cau]\d+\b`,
   «incert.», «incertitude N», «(a1)»: one regeneration, then strip and log `revue_id_leak`.
2. **Uncertainties by stable id.** `uncertainties` become `[{id: "u1", fr}]` (loader migration for
   the stored JSON); the provider cites `u1`; a fallback matches the learner's question to an
   uncertainty by shared content words when the reply says the sources are silent. The acceptance
   test gains the session-6 case («Quels légumes sont plus chers ?»).
3. **Conversation, not recitation.** Reply rules in the prompt and enforced where possible:
   answer the learner's last line first; at most two new claims per turn and never a shown claim
   restated (the service drops restated claim ids from the context); the reader question proposed at
   most once per session (state knows); no imperatives addressed to the learner («Dis…»); no symbols
   (→ ≈ ~ > /) at A1–A2 (deterministic check → regenerate); the angle changes at most once and only
   on a learner turn that names the other angle's topic; the learner is never confused with a
   guest's world («tes élèves»: the prompt names who is who).
4. **Guests take a stance.** The guest prompt requires `position` ∈ {for, against} on entry with one
   reason from their own life, forbids offers of service («Voulez-vous que je…»), and allows `moved`
   only after a learner statement. A deterministic check refuses a guest line that is a question
   offering help.
5. **Vocabulary worth learning.** The vocabulary builder excludes proper nouns, contractions
   («du»), numbers and words outside the catalogue unless they carry a gloss; prefers words the
   can-do catalogue knows so the evidence counts (1/40 turns today).
6. **Closing in the world's words.** Close lines may not contain app words («artefact», «session»,
   «dossier»); authored close templates are the fallback.
7. **Prompt versions.** `PROMPT_VERSION` constants on every encounter prompt, recorded on each
   `cost_usd` event, so a sample can be compared with the next.
8. **Latency.** The fourth turn runs reply, guest and critic sequentially (p50 11 s). Run the critic
   after the reply is returned (background, the evidence event lands on the next turn), and the
   guest line in parallel with Romy's reply when a guest is on stage. Target p50 ≤ 6 s per turn.

Acceptance: rerun the sample harness (`revue_sample.py`) on the same ten sessions; French passes in
≥ 8/10 by the same reader's criteria, the acceptance test passes 10/10, no id leak, guests take a
stance in every entrance, p50 turn latency ≤ 6 s, cost per session ≤ US$0.02.

## 11. The bridge to generated seasons

A season gap day needs "something true from the city this week" (WP-116 §12). After phase 3 it can
ask `intake.dossiers_for(week, topic=…)` and get the same editorial dossiers, the same checks, the
same place registry and the same staging rule. The season writes its own plan and state; the
evidence is shared. La Revue is where the pipeline is proven on learners before any season day
depends on it. The day the season reads a dossier is a WP of its own.

## 12. Decisions (owner, 2026-10-02 evening)

The owner answered the open questions of the first two drafts. Each decision and what it changes:

1. **Name: «Le Papier».** In the chrome: «Le Papier» for labels, chips and the beats bar; «Le Papier de
   Romy» only in the dispatch kicker and on the chooser. Code names stay `revue` (route `/revue`,
   `components/revue`, `app/services/revue`, the `Rv*` components): a rename of code for a label is
   churn. Done in the same commit as these decisions; the design doc keeps «La Revue» in its mockups
   as a historical artefact and says so.
2. **Cadence: weekly now, nearly daily later.** How weekly works with six stories: the six are the
   week's *kiosk*, not six sessions. Each learner gets one recommended story (topic they have seen
   least recently, then interests), two alternatives and «Autre chose ?». One Papier a week is the
   default rhythm: the planner deals one `REVUE` day (phase 3). The other stories stay open behind
   the chip for a learner who wants a second one; a second Papier in the same week is a normal
   session that counts for evidence but does not move the week's "filed" state. Going daily later
   means the kiosk rolls: one new story a day, the chooser shows the last seven, and a learner can
   have one active Papier per *day* instead of per week. The data model already allows it
   (`revue_sessions.week` becomes the ISO date; the partial unique index changes its column), and
   `REVUE_CADENCE` is the switch. The costs that scale with daily are the builder calls (one per
   story) and the plates (two per story, §12.7); both are shared across learners.
3. **Article fetching: fetch the article.** It yields the better dossier by a wide margin: RSS
   teasers are one or two sentences, so claims built from them are shallow and the quotes repeat the
   headline. The evergreen and W40 leads both fetched live pages and verified quotes against them.
   Rules: respect `robots.txt`, one attempt, six seconds, store only the quotes and a hash of the
   text (§4.1); prefer sources that allow fetching (service-public, insee, paris.fr, franceinfo,
   RFI, Le Monde teasers) and keep a registry note on those that refuse (France 24, education.gouv,
   ratp, L'Équipe's live pages). When the fetch fails the dossier is built from the teaser with
   fewer claims; when fewer than two anchor, the story is skipped.
4. **Staging: real people and real places are allowed.** This replaces the first drafts' absolute
   rule. Plates may show the people a story is about and the places it happens in, named. What
   stays: the brief is name + landmarks + light (§8.1), no party emblems or logos, no readable text,
   and figures are drawn in the same screen-print style, from a distance or from behind, never as
   portraits, because the drawn SVG cast stands in front of the plate and a painted face at the same
   scale would clash. See §8.1 for the test that measured what the image model does with a named
   politician and with a named chef, and the fallback it implies.
5. **Outfits: only when it really fits.** `dress` defaults to the coat. Toi changes only when the
   learner takes part in the place's work (an apron when helping at a stall or in a kitchen, a
   hi-vis on a worksite, a suit when the story puts the learner in a formal role), never for the
   setting alone. Phase 2 decides it per dossier angle; until then `dress_for` returns `coat`
   except for the apron on kitchen and cellar when the angle is `prepare_dispatch` from inside.
6. **Guests: phase 2**, as planned. One guest with a reason; the knowledge context from `NPCMemory`.
7. **Two plates per dossier.** The site for `arrive` and `facts`, a second view for `pursue` and
   `make`, switched at the guest's entrance (phase 2) or at `make` until then. Phase 4 builds it;
   the dossier schema already carries `places: list`.

## 13. Status

| Phase | Commit | What landed |
|---|---|---|
| — | — | Defined 2026-10-02; revised the same day after the owner's review |
| 0 | cbc3966 | `app/services/revue/` (dossier, session, state, checks, policy, evergreen loader + 12 sourced evergreens), five `REVUE_*` flags, sensitive list moved to policy; Toi's eight outfits and the Revue-only rule in `PanelStage`; the design spec `WP-119-DESIGN.md` and 8 mockup pages under `docs/design-reference/revue/`. 85 revue tests. Known limits: evergreen windows are 2026 only (README); the anchor entailment and attribution opinion tests are lexical heuristics until the phase-1 critic judge; the design's compact La Une card supersedes §5.1's three-story card (Home budget, `home.test.js`) |
| 1 | e43b168 | The encounter end to end on known plates: `WP-119-WIRE.md`, `app/schemas/revue.py`, `encounter.py` (offer, start, turns with knowledge check on the learner's real season position, simplify, bouclage, make, close), `weekly.py` + six live 2026-W40 dossiers, `/api/v1/revue/*` (404 while off; POSTs paid), `revue_sessions` (c3e5a7b9d1f2); `pages/revue.tsx` + `components/revue/*`, typed client, dev mock at `/revue?mock=1`, La Une chip (hero on a Revue day, dealt from phase 3), Romy's notebook, Toi half crop. Acceptance test passes at service, HTTP and page level. 198 backend + 745 frontend tests. Known: grading is an `unscored` adapter; cost line not reported; two alembic heads in the shared tree until the password-reset migration lands; `headline_write`/`short_report` make options not built |
| 2 | ab42eda + 148e2ee | Guests with a reason, knowledge context from the serial ledger and `NPCMemory`, `grading.py` (`revue-rubric-v1`) replacing the unscored adapter, `headline_write` and `short_report` for B1+, outfits per angle participation, wire §6, cost per session; frontend: guest on stage and in the thread, make flows, register note, the vignette at close and in the Relevé, read-only replay. Backend 345 tests; frontend suites green. Known: `pilot_digest` has no `revue` line yet; W40 dossiers lack `participation`/`guest_fit`; close copy still «Classer la Revue» (§10c) |
| 3 | (this commit) | `intake.py`/`sources.py`/`builder.py`, `revue_dossiers` table (migration f6b8d0a2c4e7; `week` holds the period), Monday 05:00 beat + admin refresh, six more feeds with `fetch_policy`, `DayShape.REVUE` dealt once a week on a gap day (the Papier mounts after the day's ending; 59-day life test green with 9 Papiers), the Relevé «Le Papier» section, daily-ready period pattern, the second-Papier chip |
| 4 | (this commit) | `plates.py` with the people clause (v2: few, far, under a tenth of the frame) and the name + landmarks + light rule, `revue_places` (e5a7c9b1d3f6), two plates switched at the guest's entrance, `looks_wrong` tricolour check; eight plates in `docs/design-reference/revue/plates/phase4/` for the owner |
| 5 | (this commit) | `feuilleton_bridge.py`: the serial reads the week's dossier; `fetch_feuilleton_daily_seed` deleted; legacy entry points marked; audit regression unchanged |
| 10c | (this commit) | leftovers: «Classer le Papier», wire doc, pilot digest `revue` line, W40 fields, pictogram refresh (guitar kept), mock dress; read-only head and replayable evidence still open |
