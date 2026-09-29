# Work packages — 2026-09-28: from a good first minute to a year worth staying for

Owner brief: find the most important open points in the user experience and the overall
learning experience, and define the best possible way to engineer them — creatively and
beautifully — as work packages.

Method: a first-hand walk as a brand-new learner (landing → taste → sign-up → day 1 →
Home → Courrier → Feuilleton → Cahier; «New», English interface, 375×812, dark theme,
live provider, `backend-e2e` on the `atelier_e2e_0926` copy) plus four read-only audits:
learning science, daily-loop UX, long-horizon motivation, and an inventory of every open
item in the 09-21 … 09-26 plans checked against code. Walk findings (W-n) are first-hand;
file:line citations come from the audits, and the P0s were checked in code.

Numbering continues after WP-87: **WP-88 … WP-102**.

## 1. Verdict

The first minute is now excellent: Romy's two-tap taste, a one-screen sign-up that lands
straight in the day, a cast introduction, and four hand-painted panels that look like a real
graphic novel. The Seal at the end is a genuine keepsake.

Behind the first minute, four things hold the product back:

1. **The conversation is the heart of the product, and it doesn't hold together yet.**
   Characters forget what was said one exchange earlier, talk at B1 to an A1 learner, and
   every exchange is graded like a test. The learner never sees their own lines.
2. **The best features are built but switched off.** Nobody hears a character speak
   (episode audio off). Every panel in production is the same location plate (panel art
   is off and not production-safe). The 153-unit grammar syllabus is dormant. With the
   cohort empty, production serves nobody the journey at all.
3. **Learning plateaus by design.** A Régulier day is about 80 % recognition drills and
   7 % input. The story is never told which grammar to use. Nothing ever stages the level
   check (the épreuve), so the level cannot rise by measurement.
4. **The story does not accumulate.** The learner cannot reread what they lived (day 1 is
   not even in the season), their choices never visibly matter, relationships max out in
   weeks, and the story ends after season 2.

## 2. What the walk showed (2026-09-28, first-hand)

| # | Moment | What happened | Where |
|---|---|---|---|
| W1 | Taste | Excellent: portrait reacts, tiles answer instantly, 2 taps to a win. Lower 60 % of the screen is empty; nobody speaks aloud; Marin and Lila are named but not shown | `pages/index.tsx` taste |
| W2 | Sign-up error | An invalid email shows the raw validator text **twice**, in English: «body -> email: value is not a valid email address: The part after the @-sign is a special-use…» | `pages/auth/signup.tsx` error toasts |
| W3 | Cast intro | Good. Marin's portrait is in a different style (bright, white background) from Romy's and Lila's | `CastIntro`, cast portraits |
| W4 | Reader | The art is strong. But the **Next button jumps** between panels (it follows the height of the speech cards), progress is shown twice (top bar «2/4» and dots), «Le feuilleton» appears as both kicker and title, and on one panel the text changed before the image did | `FeuilletonReader.tsx`, `reader-styles.tsx` |
| W5 | After the scene | The page ends on Margaux's question «Vous vous installez ou c'est à emporter ?», and then **two out-of-context drills** interrupt («Which French phrase means "a coffee"?», unscramble «s'il vous plaît»), both repeating what the taste just taught | `journey_planner.py` step order |
| W6 | Typing an answer | As soon as the learner types, a banner says **«Something you did has not reached the server yet. It is kept on this device.»**. It pushes the Send button down under the thumb. The cause: an unsent *draft* while online maps to `pending_sync` | `lib/journey-recovery.ts:633-641` |
| W7 | First reply | Margaux to an A1.1 «New» learner, 35 words: «Bien sûr, un café arrive tout de suite ; voulez-vous vous asseoir au comptoir, sur la terrasse couverte chauffée ou préférez-vous à emporter ? Bonjour ! On se dit bonjour d'abord ?». That is B1 register, and the greeting nudge is stacked **after** she has served. Verdict «Correct, with help» although no help was used | `journey_conversation.py:1599` (`_MODEL_SYSTEM_PROMPT` has no band or word cap) |
| W8 | Second reply | «Bonjour ! Au comptoir, merci.» → Margaux: «…voulez-vous quelque chose à boire en particulier ?». **She forgot the coffee.** The authored-scene model prompt carries only «Learner's latest message», never the history | `_MODEL_USER_TEMPLATE`, `journey_conversation.py:1606-1620` |
| W9 | Conversation shape | The learner's own lines are never shown. A full verdict band plus «Continue» sits between exchanges. Nothing says how many exchanges remain | `JourneySteps.tsx:687-985, 1260-1318` |
| W10 | Ending | The resolution plate is flat poster art, clashing with the painted panels. The register card says the same thing twice («"vous" tenu avec Margaux.» / «Kept vous with Margaux.») | resolution step |
| W11 | Recap | The Seal is lovely. «+2 words» are the two words the taste already taught. Day 1 = 5 interactions | `JourneyRecap.tsx` |
| W12 | Home after | «A1.1 · 0 %» after a finished day. The primary action is «Look again»; there's no teaser for tomorrow; 60 % of the screen is empty | `HomeScreen.tsx` |
| W13 | Courrier, day 1 | The first letter is from **«Service Client · seller support agent»** about a misdelivered parcel (the cast is absent), with English role/setting/P.S. On first load the generator rejected two drafts as too hard for A1 (≈ US$0.002 wasted) | `missions.py:69-95, 2137` |
| W14 | Feuilleton after day 1 | «The season so far — Your first scene opens in the session.» **The scene just lived is not in the season**, because it only lists `GraphicNovelScene` rows and the authored first day isn't one. Mixed chrome: «La saison / Les personnages» over English body; «Back to La Une» (no longer the Home's name) | `serial.py:893-939`, `SeasonPage.tsx:118` |
| W15 | Cahier | Grammar map after day 1: «0 held · 0 proficient · 0 introduced»; 54 concepts (v1). The rule card's anchor examples are generic («J'ai un frère»), never the learner's own scene | `CahierV2`, rule cards |

## 3. What the audits add (condensed)

**Learning (planner run at 600 s, `test_wp_l9_rhythm_harness`):**
- A Régulier A1 day has 29 steps: **26 recall items (≈ 80 % recognition)**, one scene priced at **39 s** (`scene_seconds` counts only setup and objective, not the 4–6 panels, `journey_planner.py:1437`), one reply, one ending. Input ≈ 7 % of the day.
- **There is no listening in production:**
  - `ATELIER_EPISODE_AUDIO_ENABLED=False` (`config.py:388`), so the listening day shape is never dealt.
  - `character_line_audio_url` is always `None`, so listen_tap is really a reading item.
- **WP-L5 `grammar_plan` has no code.** The director receives vocabulary and errata only (`living_story.py:611-623`), so the new form is never woven into the scene, highlighted, or required.
- **The épreuve is never staged.** `record_checkpoint_result` is only reachable from an endpoint no client calls (`progress.py:111`, `api.ts:690`). Coverage caps at 90 %, so a learner who has covered the band sits at «A1.1 · 90 %» forever.
  - Harness at day 126, v1: Régulier/85 % reaches A1.2 · 41 %; Intensif/95 % B1.1.
  - The harness also *overstates* progress, because it assumes free use at every high-stability review (`simulation.py:40-49`).
- **v2 syllabus dormant.** `ATELIER_GRAMMAR_CATALOG_VERSION="v1"`; all 153 v2 units `review_status=draft`. **58 can-dos exist, and no UI shows them.**
- **Intake is slow.** 4 new words a day on Régulier, so the 360 words of A1.1 take about 92 days. Recycling words into the story is one prompt sentence, with no validator and no metric.

**UX:**
- The panel art is dispatched *after* commit (about a minute), so every panel opens on the plate and swaps with a hard cut. Polling dies when the learner leaves the step, and Home and the recap never show the art.
- A 3-line panel is ≈ 1,060 px tall on a 812 px phone.
- Story lines ship `en: ''`, so «Translate the panel» never appears for A1.
- «Stop here» ends the day with one tap and forfeits the Seal, while ✕ means pause.
- The cold start is a button-only wait: `waiting` is computed but never rendered.
- The ending wait has no face.
- Every French word is a `<button aria-label="Aide pour « … »">` (French labels for A1, and a sentence is never read as a sentence). Panel `alt=""`.
- A failed offline launch says «Your answer was kept».
- Reader faces are always neutral: `Dialogue` has no mood.

**Long horizon:**
- **The story ends after season 2.** `_load_next_season_world_bible` returns `{}` for any season ≠ 2 (`serial.py:1520`), which leaves a permanent interlude from about month 5.
- **The lived story isn't legible.** Chronicle, consequences and threads are never shown, and the season page is a flat list of scenes without the learner's replies.
- **The engine never writes `next_teaser`,** so pushes recycle one authored line per character.
- **Pushes are thin.**
  - Every push says «vous», even after a character has switched to «tu».
  - There is no push when a letter arrives or is about to lapse.
  - Native push is off by default.
- **Absence is only a label.** The director never hears about a gap.
- **Closeness only goes up,** so it hits 5 pips within weeks, while the engine's trust (which can fall) is never shown.
- **Rewards end around day 30:** 8 achievements, and a Seal grid of 4 weeks.

**Operations (learner-facing consequences):**
- `ATELIER_DAILY_JOURNEY_COHORT=""` with `APP_ENV=production` means nobody gets the journey.
- Panel art:
  - it is on only in the local `.env`;
  - the Dockerfile doesn't ship `docs/design-reference/cast`, so faces would drift;
  - it writes no cost-ledger row, even though US$0.20–0.30 a day in art would sit invisible next to a US$0.50 cap.
- When the cap hits, `/attempts` returns 429 mid-day, so the learner cannot finish and the streak breaks.
- The cap's day is UTC while the streak's day is local.

## 4. Packages

Waves: **A** = serve what is built · **B** = the heart of the day (conversation, page,
voice) · **C** = learning that compounds · **D** = a story that lasts · **E** = the frame.
Every package keeps the house rules: the av2 system only (Garamond + Instrument Sans, av2
colour roles, Bauhaus mark, the 3D press as the one primary per screen), no new fonts or
colours, **the mark is the only gauge** (no rings), the streak shown as seals, the
language rule (≤A2 chrome in the learner's language), no social features, and no mascot
beyond the cast. Pronunciation scoring stays out of scope.

---

### Wave A — serve what is built

#### WP-88 · Switch it on, safely
The cheapest large gain: the learner currently never meets half the product.
- **Cohort:** an explicit `ATELIER_DAILY_JOURNEY_COHORT` policy in `ROLLOUT.md`. The API refuses to boot in production with an empty cohort *and* the master switch on, unless `*` is set on purpose.
- **Panel art made production-safe:**
  - ship the cast reference portraits in the image (Dockerfile copy, with a startup assert);
  - write a `cost_usd` ledger row per panel through `spend_guard`;
  - a daily art allowance separate from the text cap;
  - a degrade ladder: above 70 % of the cap, fall back to plates, and never refuse a started day.
- **Reserve the day.** On `POST /daily-journeys` the day's text budget is reserved. Attempts on an open day are never 429'd by the spend cap, only by abuse limits. Align the cap day to the learner's timezone.
- **Audio on for the cohort** (see WP-91 for the experience): `ATELIER_EPISODE_AUDIO_ENABLED`, OpenAI TTS pinned, estimated ≤ US$0.04 per scene, cached per line.
- **v2 syllabus, one slice.** The owner reviews A1.1–A1.2 (34 units, can-dos, lexicon), then the catalogue is flipped per band (`ATELIER_GRAMMAR_CATALOG_VERSION` becomes per-band).
- **Done when:** a clean production deploy serves the journey to the cohort with drawn panels and spoken lines; a scripted day that crosses the cap still finishes and keeps its Seal; the ledger shows art and TTS rows.

---

### Wave B — the heart of the day

#### WP-89 · «Le fil» — the conversation is one conversation
The reply is where a learner learns to *speak*; it has to feel like talking to a person.
- **Memory:**
  - the authored-scene model prompt gets the whole thread (character and learner lines) plus the facts already settled (the drink ordered, the seat chosen);
  - a guard refuses a reply that re-asks a settled fact (W8), in the same way the story engine uses `chapter.already_asked`.
- **Level:**
  - band word caps on authored replies, the same as the story engine's ACTOR caps (A1 ≤ 12 words, one clause);
  - a lexical-coverage check on the reply (the existing 95 % floor), with one retry, then the authored fallback line.
- **Nudges:** a register or greeting nudge *replaces* the model line on the opening turn and is never appended after it (W7).
- **The thread on screen:**
  - the respond step becomes a chat column: character bubbles on the left with their mood portrait, the learner's lines on the right in Garamond italic, as if typed on the page;
  - under the character's name, one small `ShapeToken` per planned exchange, filled as each passes. This is a sequence, not a ring.
- **Verdict only at the close:**
  - continuing turns get no band, no frown and no error sound;
  - a slip becomes a **proofreader's mark**: a red dotted underline on `span_fr`, which opens the correction as a margin note in the learner's language;
  - the band, `CharacterSmiles` and the sound come once, on the closing turn;
  - a light haptic tick per arriving reply.
- **«Relance» (pushed output):** when an answer is correct but minimal, the character asks for one more clause («Et pourquoi ?», «Avec qui ?») within the exchange budget.
- **No false alarm:** a local draft while online is not `pending_sync` (W6). `pending_sync` means only a mutation that actually failed, and the notice never shifts the input: it lives in the header.
- **Done when:**
  - a replayed W7/W8 transcript yields a reply ≤ 12 words that never re-asks the drink;
  - a 4-exchange Intensif conversation shows 4 tokens and one verdict;
  - typing online shows no banner;
  - a test pins "no band on `next_turn`".

#### WP-90 · «La planche» — a page that is ready, fits, and acts
- **Ready before the tap:**
  - panel art is drawn at prefetch time (the warm draft for tomorrow) instead of after commit;
  - the poll moves into the journey controller, so it survives leaving the step.
- **Waiting that looks designed:**
  - a panel still drawing shows the plate as a blue-ink duotone (`color-mix` on the story blue) with a folio ribbon «Planche 3 · sous presse»;
  - the drawing crossfades in over 300 ms, and simply appears under Reduce Motion.
- **Fits a phone:**
  - after panel 1 the headline folds into a running head («Le Mistral · 3/4»);
  - one progress indicator, the dots (drop the bar and the counter);
  - the plate is full-bleed 4:3, speech becomes compact captions with `xs` faces, and «Suivant» is pinned at a fixed position so the thumb never hunts (W4);
  - drop the duplicate «Le feuilleton» kicker.
- **Faces act:**
  - `Dialogue.mood` is added to the director schema and mapped through `expressionForMood`, so the portraits in the page change with the scene;
  - one art style across panels, plates and resolution images, with the resolution plates re-drawn in the panel style (W10); Marin's portrait brought into line (W3).
- **Understanding at A1:** the director emits `text_native` per line for learners up to A2, which brings back «Traduire la case».
- **The ending is the last panel:**
  - the resolution renders inside the reader as the «case finale» (red-triangle dot), not as a separate plain step;
  - its wait shows the speaker's face, with no dead primary.
- **Accessibility:**
  - each line is one focusable element labelled with the whole sentence, with the words as a roving tabindex and labels in the learner's language;
  - panel alt text comes from `visual_direction`;
  - portraits carry alt text such as «Margaux, ravie».
- **Done when:**
  - at 375×812 a 3-line panel fits without scrolling, and «Suivant» never moves;
  - on a prefetched day every panel is drawn on first view;
  - VoiceOver reads a line as a sentence;
  - the gallery has reader states for plate, drawing, drawn and final.

#### WP-91 · «Les voix» — every character has a voice
- **One fixed voice per cast member,** chosen once and listed in the world bible, so learners come to know voices the way they know faces.
- **The portrait is the play button:** tap a face in the page, the thread or a letter and it speaks, with its ring pulsing in the character's accent colour.
- **Replies speak:** the character's reply plays once as it types in (a Réglages setting, on by default on native).
- **Listening becomes real:**
  - listen_tap and a new **dictation** item are built from lines of today's scene;
  - the listening day shape is dealt again;
  - every third day on Soutenu and Intensif is listen-first («Écouter d'abord» already exists).
- **Words speak:** `WordHelpSheet` says the word aloud.
- **Fallback:** on-device `speechSynthesis` when TTS is unavailable or the cap is near (the Forge already uses it).
- **Done when:**
  - a Régulier week has at least 3 real listening items a day;
  - every character line has audio or an on-device fallback;
  - per-line clips are cached (a second play costs nothing).

---

### Wave C — learning that compounds

#### WP-92 · «La règle dans l'histoire» — finish WP-L5
- **Choose before writing:** the new unit is chosen before generation (`concept_life.introduction_for_today`). The director receives `{introduce, weave ≤ 2, allowed, avoid}`.
- **Validator:**
  - the regex detectors (146 of 153 v2 units have one) require the new form at least twice in cast lines;
  - the addressed question must *need* the form;
  - one retry with a named hint, then the scene is accepted with the form flagged «non tissée» for the metrics.
- **The coach speaks it:** the rule's coach (WP-S5) is the character who says the form.
- **«Rayons X» (noticing):**
  - after the first read, a toggle marks the form in the page with the av2 marks (the rule's shape under the words, in its colour);
  - the rule card's anchor examples become **the learner's own lines** from the scene, with the generic sentences kept as fallback (W15).
- **Done when:** in a 14-day fake-provider run, at least 80 % of introduction days carry the form ≥ 2 times and a question that requires it; the rule card shows a scene line.

#### WP-93 · «Plus d'histoire, moins d'exercices» — rebalance the day
- **Price the input:** `scene_seconds` counts the panels and lines actually on the page. An **input floor**: ≥ 35 % of the budget is reading or listening.
- **Cap recall:** about 12 items on Régulier (budget-scaled).
- **Longer rhythms buy input, not more drills:**
  - «Coulisses», the same evening from another cast member's view, with the same words and no new plot;
  - yesterday's page re-heard with audio;
  - a letter to read.
- **Never interrupt a question:**
  - warm-up recall comes *before* the scene, or after the reply, never between a character's question and the learner's answer (W5);
  - day 1 does not repeat the taste's words.
- **Words from the story:**
  - the director receives five «mots à placer» from the band's lemma list;
  - reuse is measured with the `lexical_coverage` lemmatiser and logged;
  - the word biography gains «revu dans l'épisode du 12».
- **Choice and word_bank on engine days:** built from the scene lexicon (closes WP-68 L-1).
- **Done when:** the WP-L9 harness reports the new mix (input share, recall count, reuse rate) per rhythm, and the Régulier p50 still fits 8–10 min.

#### WP-94 · «Numéro spécial» — the épreuve that moves the level
- **Staging:** when `checkpoint_ready`, the director stages a finale-shaped chapter:
  - La Une gets a double-ruled masthead «Numéro spécial»;
  - the scene objectives are the band's can-dos;
  - grading = objective met plus `concept_evidence`, and the result is written server-side (`record_checkpoint_result`).
- **Pass:**
  - an oversized Seal stamped «A1.2» presses into the Relevé;
  - the whole cast appears in their delighted portraits in one panel;
  - `level_up` fires once.
- **Fail:** the épreuve returns in a new situation after 7 days, with no punishment copy.
- **Honest in the meantime:** the Dossier copy and forecast say what is true today, and Home stops showing «0 %» on day 1 (W12). Home shows the next can-do instead (WP-95).
- **Harness honesty:** the pilot's measured avoidance rate feeds `hold_lag_samples`. Past 10 days of stability, the Rappel poses a coach mini-scene (`item_bank.scene_item`), so free use is elicited rather than hoped for.
- **Done when:** a harness learner closes A1.1 by épreuve; an e2e test goes from checkpoint_ready → staged → passed → level shown.

#### WP-95 · «Le Carnet» — what you can do in French
- **One page per sub-band** listing its can-dos (58 in `fr_core_can_dos_v2.json`, in 3 languages).
- **Each can-do is pressed as a Seal** the first time story evidence shows it: «Vous avez commandé au comptoir — Margaux, j1».
- **«Essayez-le pour de vrai»:** a real-world prompt that opens Répétition (WP-31).
- **Home shows the next can-do** instead of a percentage. The Dossier links the Carnet.
- **Done when:** a harness learner's first 30 days press at least 6 can-dos, each linked to its episode.

---

### Wave D — a story that lasts

#### WP-96 · «Les Cahiers du feuilleton» — the story you can reread
- **One archive for the Feuilleton tab** («Archives du journal») replaces the three surfaces: `graphic-novel.tsx` season, `/serial` and `/serial/cast`. The cast becomes «Le trombinoscope».
- **The season is a bound volume:**
  - chapters fold open, headed by their digest line;
  - each day is its planche with **the learner's reply printed in italic** («la réplique de l'abonné·e») and the ending;
  - a «Précédemment» box of three chronicle lines sits above each new scene;
  - a finished chapter gets a «Fin du chapitre» colophon under the Bauhaus mark;
  - a finished season becomes «Tome 1» with a pressed Seal.
- **Day 1 and fallback days belong to the story:** authored scenes are recorded as episodes (W14).
- **Language rule:** fix the mixed chrome and «Back to La Une».
- **Done when:** after 3 walked days the archive shows 3 planches with the learner's own lines; a 126-day harness life renders as chapters.

#### WP-97 · «Les suites» — choices you can see, people who remember
- **Margin notes:** when the engine pays back a consequence or callback, the page prints a dated note in the margin: «Parce que vous avez dit à Marin « vas-y » — Nº 4».
- **What they know:** the trombinoscope card gains «Ce qu'ils savent de vous», drawn from `consequences` where that character is a witness.
- **One relationship meter,** the engine's trust, which can fall. Retire the only-up closeness pips.
- **The «tu» becomes a scene:** the character asks «On se tutoie ?», the learner answers, and a Seal «Le tu de Romy» goes into the Relevé. From then on, pushes and letters use «tu».
- **Done when:** a harness life shows at least one margin note a week after day 10; trust falls in a test where the learner ignores a letter.

#### WP-98 · «La saison suivante» — the story never runs out
- **Near term:** author season 3 (world bible, arcs, interludes) in the existing format.
- **Structural:**
  - season N+1's arcs are generated from this learner's own material (`threads_archive`, unpaid `planted[]`, unresolved branches, world flags), critic-gated, and premiered as a «Nouvelle saison» front page with a poster panel;
  - if nothing is ready, the interlude is named honestly, with a return date.
- **Done when:** a 300-day harness life never enters an unbounded interlude.

#### WP-99 · «Le facteur et les dépêches» — reasons to come back
- **Teasers:** the engine writes one `next_teaser` per resolution, guarded so it must name an open thread or plant (no invented plot).
- **Pushes become «Dépêches»:**
  - in the character's own register (tu/vous), with the mood portrait, deep-linked;
  - «Le facteur est passé» when a letter arrives;
  - «Dernier jour pour répondre à Lila» the day before a deadline.
- **«Pendant votre absence»:** a one-page «Entre-temps» built from `meanwhile` events (no model call). The director is told the gap, and the greeting fits the length of the absence.
- **The Courrier belongs to the cast from day 1:**
  - the first letter is a story-born one from Romy or Margaux, never «Service Client» (W13);
  - English role/setting/P.S. text is translated or removed;
  - a letter is generated at the learner's band on the first try (level-constrained prompt) or served authored.
- **Done when:** the harness shows no teaser repeated within 14 days; a simulator learner receives a letter push; a returning test learner sees «Entre-temps».

#### WP-100 · «L'édition du dimanche» — a weekly rhythm and variety
- **The week as a La Une front page:** the chapters as headlines, the letter of the week, and a strip made from panels already drawn (no new art cost).
- **A monthly «hors-série»:** a new format — petite annonce, radio bulletin, menu, carte postale — built from the existing day shapes.
- **Fallback days become «Hors-série»** featuring the learner's own cast, not three generic families.
- **Tiles vs vocabulary:** errata no longer crowd out vocabulary in recall; re-measure against WP-L3's interleaved queue.
- **Done when:** a 28-day harness shows at least 4 distinct day formats a week and no speech act more than twice a week.

---

### Wave E — the frame

#### WP-101 · «La presse tourne» — waits, exits, the recap and offline
- **Cold start:**
  - the hero card becomes a proof sheet: the day's cast portraits slot in one by one, and the Bauhaus mark assembles its four shapes as the server stages complete;
  - past 8 s, one honest line in the learner's language;
  - a reader skeleton replaces «Getting today ready».
- **Exits:**
  - remove «Stop here» from step screens;
  - ✕ opens a pause sheet: «Reprendre plus tard» as primary, and a quiet «Clore la journée» with the line «le sceau restera en blanc».
- **Recap in two beats:**
  1. the Seal presses full-screen with the day's title and «la planche du jour» (a 2×3 strip of the day's panels);
  2. the words, the face and an «À suivre» box. «Ranger le sceau» flies the Seal into the masthead (FLIP; a fade under Reduce Motion).
  - The push question comes after «Ranger».
- **Home after the day:** tomorrow's teaser is the headline, and panel 1 is the card image.
- **Offline:** «Édition hors ligne» — a correct title, yesterday's cached planche to reread, cached word cards, and the mark in ghost shapes (no «Your answer was kept» at launch).
- **Small but visible:**
  - sign-up errors in the learner's language, deduplicated, and mapped from the validator (W2);
  - the listen-first offer moves into the reader head (not under the notch);
  - `aria-label="Primary"` localised;
  - Back returns to the previous journey step (history state).
- **Done when:** each state has a gallery specimen, and a simulator walk shows no raw server text anywhere.

#### WP-102 · The proof: gallery states, a 7-day walk, three languages
- **Gallery:** add the reader, conversation thread, verdict-at-close, recap beats, offline and pause-sheet states to `atelier-v2-gallery` (none exist today).
- **Scripted walk:** a repeatable 7-day walk on `backend-e2e` (see `.claude/launch.json`: `backend-e2e` + `web-frontend-e2e`) that plays day 1 (authored) through day 7 (engine, prefetch, a practice day, a letter day), with a clock shim. It saves screenshots and a transcript per day.
- **Simulator:** one walk in each of en/de/fr at 320 and 390 px, light and dark. It closes the never-walked items: Forge folded into the day, 4-exchange Intensif, voice mode, day 3+ prefetch.
- **Done when:** the walk report is committed next to this doc and every package above cites its day and screenshot.

## 5. Order

1. **WP-88** first: the owner's switches and the spend reserve cost little and change everything a learner meets.
2. **WP-89 + WP-90** together: the reply and the page are the day. WP-89's memory and level fixes (W7/W8) and the W6 banner fix are the first commits.
3. **WP-93** (it rebalances the day around the page), then **WP-92** (it needs the rebalanced day to place the form).
4. **WP-91** once WP-88's audio decision is taken; it is independent of 92/93.
5. **WP-94 → WP-95** (the épreuve stamps can-dos).
6. **WP-96 → WP-97 → WP-99** (the archive is where margin notes and «Entre-temps» live); **WP-98** in parallel as authoring work.
7. **WP-100, WP-101** as polish on the new surfaces. **WP-102** runs throughout: every package lands with its gallery state and walk day.

## 6. Owner decisions

| # | Decision | Recommendation |
|---|---|---|
| D-1 | Cohort for the pilot | A named list first, then `*` |
| D-2 | Audio on; the voice per cast member | On for the cohort; pick 5 voices once (≈ US$0.04 per scene, cached) |
| D-3 | Panel art in production, and its daily allowance | On for A1–A2 first; allowance US$0.25/day apart from the text cap; plates beyond it |
| D-4 | v2 syllabus review scope | A1.1–A1.2 (34 units) first, flip per band |
| D-5 | Recall cap and input floor | ≈ 12 items and ≥ 35 % input on Régulier |
| D-6 | Season 3: authored, generated, or both | Author season 3 now; generated N+1 behind a flag |
| D-7 | «Stop here» removal and the pause sheet | Remove; ✕ = pause |
| D-8 | The trust meter replaces closeness pips | Yes: one meter, and it can fall |

## 7. Keep (already excellent)

- **The taste and first-day hand-off:** 2 taps to a win, sign-up lands in the scene, the cast intro, pre-drawn panels.
- **The painted panels and the Seal.** They set the art bar every other surface should meet.
- **The lexical coverage guard** (95 / 98 % floors, one unknown word at A1) and **one explicit correction per turn** in the learner's language, with self-repair prompts before retirement.
- **The strict «Tenue»:** free use on two days ≥ 7 apart plus a spaced item. Also the honest ranged forecast and the intake throttle.
- **Voice-first replies with an editable transcript,** never auto-submitted.
- **Reply before verdict** (typing indicator, then typed reply), and honest states that never dress an error as a result.
- **The honest streak with the «jour de relâche»,** and long memory proven over 126 days (callbacks 101 days back).
- **The Courrier's story mechanics:** chains, soft deadlines, and cooling on a lapse.

## 8. Decisions delegated by the owner (2026-09-30)

The owner asked Claude to decide the points left open by WP-92..97:

| # | Decision | Reason |
|---|---|---|
| O-1 | The automatic switch to «tu» at closeness ≥ 3 stays **off** for story-engine characters; «On se tutoie ?» is staged as a scene (WP-97) | The automatic switch made the scene unreachable, and the scene is the better experience |
| O-2 | `closeness` stays counted but deprecated; it is removed in E-6 | Only the legacy non-engine path still reads it |
| O-3 | On introduction days the rule card stays **before** the scene (WP-93) | The reply asks for the form, and before the scene is the only slot that does not split the question from the answer |
| O-4 | The Rappel poses the free-use coach mini-scene from **10** days of stability (was 15), and the measured avoidance rate feeds the live forecast (WP-94 deferral, done in WP-99) | Honest forecasts over flattering ones, even if dates move |
| O-5 | The unused `SeasonPage.tsx` and its tests are deleted in E-6 | Dead code since WP-96's archive |
| O-6 | Season 3 is authored now; the per-learner season writer ships behind `ATELIER_SEASON_WRITER_ENABLED` (off); without it, the interlude names its return date (WP-98, D-6) | A story that never runs out, without an unreviewed model writing whole seasons in production |
