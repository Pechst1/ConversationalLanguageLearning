# WP-119 · La Revue de Romy — design spec

*Design lead, 2026-10-02. This builds on [WP-119-LA-REVUE-DE-ROMY.md](WP-119-LA-REVUE-DE-ROMY.md)
(the package) and stays inside the av2 contract
([design-overhaul-2026-08-31.md](../../design-overhaul-2026-08-31.md),
`web-frontend/styles/atelier-v2.css`). There are no new fonts and no new colours. Every value in the mockups
is an existing `--av2-*` or `--char-*` token. Mockups:
`docs/design-reference/revue/01…08-*.html`, each with a full-page `.light.webp` and `.dark.webp` at 390 px (re-encoded from the PNG captures).
Story content in the mockups is sample content, not real articles.*

## 1. Design intent

La Une is already a newspaper: a masthead, a date, a manchette and a colophon. La Revue is that
newspaper's **weekly page by its own reporter**, not a news feed. The learner gets one story a week,
chosen with Romy rather than scrolled. The story happens in a drawn place, and Romy needs help to finish
her piece. The newspaper vocabulary does real work: the room left in the conversation is **a column
filling up**, the ending is **le bouclage**, the thing made is **a clipping** (*la coupure*) filed in the
Relevé, and what is uncertain is **set in a dashed box, the way an absence is set everywhere in av2**.
What it must not become: a headline list, a feed of cards, a ticker, «breaking», a dateline that implies
live news, a red badge, a count of unread stories. The learner reads Romy's French, never the outlet's
page. Sources are cited the way a paper cites a confrère: «D'après Le Monde, 29 sept.».

## 2. Information architecture

| Where | What | Phase |
|---|---|---|
| **La Une, Revue day** (`DayShape.REVUE` dealt) | `RvUneCard` in the `hero` slot. The plan row is hidden (`planHidden`) because the card is the route. One red press under the card | 3 |
| **La Une, any other day of the week** | One chip «La Revue · sem. 40» in WP-81's quiet chip row (letter first, then Revue, then words due) until this week's Revue is filed | 1 |
| **La Une, after the close** | The hero shows the filed line (`RvUneCard state="filed"`). The chip disappears | 1/3 |
| **`/revue`** | Immersive (no tab bar, like the journey session). Its states are `choose` → `arrive` → `facts` → `pursue` → `make` → `close` → `ended` | 1 |
| **`/revue?story=<dossier_id>`** | Enters straight at `arrive` on that story (`chosen_by: learner`) | 1 |
| **Le Relevé** (`/notebook?mode=releve#revue-<week>`) | Section «La Revue» after Le Registre, one `RvReleveEntry` per week | 3 (stub in 1) |

**Navigation.**
- **In.**
  - From the hero press: the recommended story, at `arrive`.
  - From «Autre sujet ?»: a `BottomSheet` on La Une. Picking a row opens `/revue?story=…`. A free request answered by a
    match opens the same URL; a miss gets Romy's line in the sheet (01 `#ask-miss`).
  - From the chip: `/revue` at `choose`. This is §5.1's full card: recommendation, two alternatives and «Autre chose ?».
- **Out, mid-encounter.**
  - The × in `RvSessionHead`, the OS back and swipe-back all do the same: back to La Une. Nothing is
    lost, because the state is append-only (§3.3).
  - There is no confirm dialog. The aria-label says so: «Quitter la Revue — Romy garde tes notes».
- **Back between beats: none.** The conversation is the record. The learner scrolls up to reread, and folded
  claims reopen on tap.
- **Source links** open in a new tab or the in-app browser (`rel="noopener"`). Returning keeps the scroll and the
  state.
- **Out, after the close.**
  - The ink press «Classer la Revue» goes to La Une.
  - The quiet «Voir dans le Relevé» goes to the anchor.
  - Opening `/revue` again this week shows `ended`: read-only, with a back arrow instead of ×.
- **Inside the journey player** (phase 3): for `DayShape.REVUE` the player mounts the same `RvEncounter`.
  There must be one implementation of the encounter, not a second one built from step views.

## 3. Screens (annotated; the numbers are the mockup files)

### 3.1 La Une card — `01-la-une-card.html`
- `#hero`: the recommended layout.
  - Art: the plate at 16:9 with Romy's bust (the `TodayEnvelope.headline.stage` path from WP-116 §7.1).
  - Folio row: the blue label «La Revue» on the left, «Semaine 40» on the right.
  - The title in Garamond, then one meta line with the place and the topic.
  - «Autre sujet ?» as a quiet underlined button.
  - Under the card, «Rejoindre Romy →» in the red 3D press.
- **Budget.** It fits WP-81's ≤ 5 elements and ≤ 25 words, at the limit: masthead, hero and press make 3
  elements and about 25 words. `home.test.js` gets a Revue fixture.
- **§5.1 as written does not fit.** One recommendation, two alternatives and «Autre chose ?» on the card come to
  about 40 words, so the full set lives in the sheet (`#sheet`) and on `/revue` (`#full`, the `choose` state). See Q1.
- `#chip`: the phase-1 and other-day entry. The circle (story) shape is the token.
- `#before`: there is no dossier yet. The evergreen is labelled in two places, the kicker «La Revue · hors actualité»
  and the topic «un classique de saison». One plain line says when the week's stories come.
- `#filed`: the done square, «Revue bouclée · semaine 40», the made headline with the learner's part
  marked, and «La suite la semaine prochaine.» No press. If words are due, the one post-day chip shows.

### 3.2 `arrive` — `02-arrive.html`
- **Stage.** The plate is full-bleed at 4:3, the reader's frame, which never changes size.
  - Romy is in front with `hold: notebook` (single-slot geometry: centre 50 %, 92 % high).
  - Toi is from behind, bottom right, in the dress.
  - **Finding:** at PanelStage's Toi crop (bust, 46 % high, bottom −8 %) the apron's bow and waistband fall outside the
    frame, so the outfit is invisible. On the Revue stage, Toi uses a waist crop: `youCrop="half"`, 58 % high, bottom −6 %.
- **Text under the plate**, never on it:
  - two narrator sentences (sans, `--av2-ink-2`, no face);
  - in phase 1, Romy's honest fallback line («On n'est pas en Bourgogne, hein…»);
  - her purpose, as the screen's one headline in her bubble.
- **Summary.** `HeardLine`, where the face is the play button, shows «Écouter le résumé · Romy · 20 s». While it plays
  (`#listen`), the summary text is shown and the sentence being heard is underlined in story blue. The summary is never a gate.
- **The press is the learner's French.** «D'accord, je t'aide.» posts that line into the thread. «Répondre autrement» opens
  the composer.
- **A1** (`#arrive-a1`):
  - shorter French;
  - the target word's gloss printed under it;
  - the translation open one tap away;
  - «lentement» on the audio.
- **After the press**, the plate folds into the **band** (390 × 168, `object-position: 50% 62%`) and stays pinned
  while the thread scrolls under it. The fold is a single 240 ms height change, and instant under Reduce Motion.

### 3.3 `facts` — `03-facts-a1-b1.html`
- **Layout.**
  - Header: × · five beat segments (pursue is double width, as the open part) · `RvColumn`.
  - Under the header: band · thread · composer foot.
- **Claim cards.** Claims come in one or two at a time, as `RvClaim` cards, each with three parts:
  - **The kind**, carried three ways, never by colour alone:
    - `fact`: ink square, solid ink rule, «Fait»;
    - `interpretation`: blue circle, dashed blue rule, «Interprétation», plus the attribution line «d'après plusieurs
      vignerons cités» before the source;
    - `forecast`: same as interpretation, labelled «Prévision» with «selon …».
  - **The French** in Garamond, at 20 px for A1/A2 and 19 px from B1.
  - **The source line.** «D'après {source}, {date} ↗» is a link, and «La citation» unfolds the verbatim anchor quote in
    guillemets.
- **Support by band** (§6):
  - A1 (`#facts-a1`): target words carry a printed gloss under the word (ruby, German, sans 11 px), on the first
    occurrence only. The translation sits behind the «Traduire» chip on every Romy line and claim.
  - B1 (`#facts-b1`): no printed glosses. Every word is tap-to-gloss (dotted underline, the `fr-word` style). No translate
    chip on claims.
- **Tap-gloss** (`#tap`): the tapped word lights in reward yellow and opens the Feuilleton reader's `WordHelpSheet`
  unchanged. «Garder» files the word with the claim sentence as its example.
- **«Plus»** (`#plus`): the chip posts «Dis-m'en plus.» as the learner's own line, and Romy adds the next layer (a
  forecast, the procedure, the actors). The support level does not change.
- **Simplify on breakdown** (`#simplify`), after two failed comprehension turns:
  - an `RvShift` hairline marker «Plus simple · gloses affichées» (`role="status"`);
  - Romy says «Pardon, je vais trop vite.»;
  - her next lines are shorter and glossed, and the translate chip returns;
  - the quick replies switch to comprehension checks («Ah, d'accord», «Encore plus simple»);
  - a pressed chip «Gloses ✕» lets the learner turn the glosses off again.
  - There is no modal, no toast and no tint. The dossier and the claims already shown do not change.

### 3.4 `pursue` — `04-pursue-guest.html`
- **The acceptance test** (`#pursue`).
  - Once the learner speaks, the claims fold into one quiet line, «2 faits sur la table · d'après Le Monde, RFI», which
    reopens on tap.
  - The learner asks about prices. Romy says «Et là, je n'ai rien.», then an `RvUncertainty` shows: a dashed outline (the av2
    «absence» surface), a blue ring, «Les sources ne le disent pas», and the dossier's sentence.
  - Then she offers to phrase the question together, and the quick replies lead with that offer.
  - An uncertainty card appears only when `uncertainties[]` holds one. Otherwise Romy says she doesn't know, with no card.
- **Waiting** (`#typing`): `CharacterTyping` with the line «Romy cherche dans ses notes». Never «Envoi…».
- **Voice** (`#voice`): the mic is the red icon while the field is empty, the send arrow is red once text is typed, and
  recording turns the icon ink with a stop square. The transcript lands in the thread in grey Garamond (`data-pending`).
- **A guest** (`#guest`).
  - Margaux joins the band in the two-slot geometry (31 % / 69 %), with the speaker in front.
  - An `RvGuestEntrance` pill appears, tinted 12 % from her `--char-margaux` on card: «**Margaux arrive.** Elle achète son
    vin chez un cousin, en Bourgogne.»
  - A guest's lines are speech bubbles, never claim cards. Romy names the difference: «un témoignage, pas une source».
  - The entrance is a 260 ms slide; under Reduce Motion the guest simply appears.

### 3.5 `make` — `05-make.html`
- **The chooser** (`#choose`).
  - At 80 % Romy steers here herself. `RvMakePicker` is a `ChoiceList` with a sub-line per option.
  - The option the conversation fits is pre-selected and marked «Ce que propose Romy» (blue circle).
  - Phase 1 shows only `headline_choice` and `reader_question`. Phase-2 options are absent, never shown greyed.
- **Headline choice** (`#headline`, A1/A2).
  - Three headlines. Exactly one is supported by the claims shown, which the Distinguishable check enforces.
  - The standard `ChoiceList` + `FeedbackBand` cites the anchor quote and source.
  - A wrong pick books no SRS lapse.
- **The reader question** (`#question`, any band).
  - The learner writes it their own way, in German if they want.
  - Romy proposes the French in an `RvQuestionDraft` with two panes: «Ta version» (outlined) and «La question pour les
    lecteurs».
  - The learner's own words are marked with `RvContribution`: a yellow underline plus a small «toi».
  - One line of why, in the learner's language («va être = „wird … sein“ …»).
  - Primary: «On l'envoie à la rédaction». Secondary: «Je change un mot».
  - At A1 the same pane uses `WordTiles` for the word order.

### 3.6 `close` and the Relevé — `06-close-releve.html`
- **The close** (`#close`).
  - Romy says what she did, then an `RvDispatch` clipping: a double rule, the kicker «La Revue de Romy · semaine 40», a
    30 px Garamond headline with the learner's part marked, a three-line dispatch, and the byline «Romy Tremblay, avec
    toi · d'après Le Monde et RFI».
  - Then «Pour ton Relevé»: the five words as `WordToken` rows with their gloss, and the claims.
  - Then the colophon «La suite la semaine prochaine.».
  - The terminal press is **ink** («Classer la Revue»), because nothing is left to do. «Voir dans le Relevé» is quiet.
- **Headline variant** (`#close-headline`): Romy keeps the learner's headline and makes one named revision («j'ajoute juste
  le mois»).
- **The Relevé** (`#releve`).
  - Section «La Revue», counted as «2 coupures».
  - An entry, `RvReleveEntry`, holds: a double hairline; «Semaine 40 · 2 oct.» in blue with the outlets on the right; the
    title; what was made, quoted; the claims with a kind rule and their source line (links); the words as chips (token,
    French, gloss).
  - Older weeks collapse to their title and «Ton titre · 4 mots · 2 faits».
  - **Distinct from a story day's entry** (the Carnet seal row) by its double rule, its source line, and the absence of a
    seal and of a face. The typography is the same: `nb-*` lines, Garamond for French.

### 3.7 States — `07-states.html`
- `#loading`: the plan is being built.
  - The 4:3 frame holds its size with the `av2-art__fallback` stripes.
  - Romy's face reads «Romy rassemble ses notes ···».
  - Skeleton lines, and only after 400 ms.
- `#plate-pending` (phase 4): **the reader's «sous presse» duotone, reused**.
  - The nearest plate in greyscale with story blue screened over it (`.fr-art[data-pending]` + `.fr-ink`), plus the folio
    pill «Un vignoble en Bourgogne · sous presse».
  - The painted plate cross-fades in when it arrives.
  - With the flag off this state does not exist.
- `#evergreen`: the label «Hors actualité · un classique de saison» over the thread, and Romy's own line «Cette semaine,
  rien de solide à la rédaction…». Her purpose stays editorial: her readers in Montréal.
- `#model-down`:
  - A quiet notice (dashed border, triangle): «La conversation ne répond pas pour le moment. Les faits et le titre restent
    là ; tes notes sont gardées.»
  - Romy's authored line follows.
  - The route collapses to what needs no generation: the facts already shown, then the headline choice, then an authored
    close. The open question is kept for next week.
- `#resume-une` / `#resume-page`:
  - The card carries one clause from the state («Commencée hier · tu en étais à la question des prix.») and the press reads
    «Reprendre avec Romy».
  - The page replays the thread, puts an `RvShift` «Hier · tu reprends ici» where today begins, and Romy's next turn
    picks the thread up. The authored fallback is «Te revoilà. On reprend où on en était.»

### 3.8 Budget and ending — `08-budget-ending.html`
- **`RvColumn`** is seven short lines of type, alternating full and 78 % width, 16 px wide, inked as the room is used.
  - Mapping: one line is about 2 plan turns or 1/7 of the plan minutes, whichever runs out first.
  - No number and no clock ever shows. The word appears only at **80 %**, «Bouclage» (the last inked line turns red, the
    one place red marks a state, because it is the action Romy takes next), and at **100 %**, «Bouclé».
  - Tapping it shows one line for 3 s: «De la place pour environ quatre échanges.»
  - Screen readers get that sentence, never «6/7».
- `#steer` (80 %): Romy declines an off-dossier detour honestly («mes sources parlent de la Bourgogne») and proposes the
  make. The learner can still ask one more question.
- `#final` (100 %): «La colonne est pleine ! On boucle avec ce qu'on a…». A new question is kept for next week. The press
  «Voir le papier» goes to the close.
- `#ended`: `/revue` after the close, this week, is read-only:
  - «Revue bouclée le 2 oct.»;
  - the dispatch;
  - «Relire la conversation»;
  - the colophon.
  - A Revue left unfinished on Sunday night is filed by an authored close with whatever exists.

## 4. Component inventory

Names are for the implementers. New components live in `web-frontend/components/revue/`, with styles
in a `RevueStyles` mounted by the components themselves (the Courrier pattern, WP-65). Every rule is
written `.av2 .rv-…` with `--av2-*` tokens only. All copy comes from `revue-copy.ts` (fr/en/de).

### 4.1 Exists, reuse as is
- `AtelierV2Root`
- `Action`: `primary` for the one red press, `done` for «Classer la Revue», `secondary`, `quiet`
- `Chip`
- `IconAction`
- `Surface`
- `Notice` (`tone="quiet"` for model-down)
- `StateBlock`
- `Skeleton`
- `BottomSheet` (the «Autre sujet ?» sheet)
- `ChoiceList` (headline choice)
- `FeedbackBand`
- `TextAnswer` / `textAnswerField`
- `WordTiles` (A1 question order)
- `WordToken`
- `ShapeToken`
- `CastPortrait` (xs/sm faces in lines, the byline)
- `ScreenFoot`
- `MatchPairs` (only for target words not yet used correctly, §5.3)
- `CharacterTyping` / `TypedReply` (`ReplyStage.tsx`)
- `SpeakingPortrait`
- `HeardLine` (the read-aloud summary)
- `WordHelpSheet` (`feuilleton/reader/WordHelpSheet.tsx`, tap-gloss)
- `NbSectionHead` (Relevé section head)
- `CastRig` (with WP-119 §8.2 `outfit`)
- HomeScreen's `chips` and `hero` slots, as data: no change to `HomeScreen.tsx`

### 4.2 Exists, needs a variant
| Component | Variant |
|---|---|
| `PanelStage` | `surface?: 'reader' \| 'revue'` (passes `outfit` only for `revue`, §8.2); `you?: boolean \| { outfit?: Outfit; crop?: 'bust' \| 'half' }`; `crop: 'half'` = 58 % high, bottom −6 %, aspect 180:260; `entering?: string` (rig id that slides in, 260 ms, none under Reduce Motion); `StageMember.hold?: string` passed to `CastRig` |
| `StepProgress` | `StepSegment.weight?: number` (flex-grow; `pursue` = 2) so the beat bar shows the open part wider |
| `ChoiceOption` / `ChoiceList` | `detail?: string` (sans sub-line under the serif option) and `badge?: ReactNode` (the «Ce que propose Romy» mark) |
| Reply composer in `RespondStepView` (`JourneySteps.tsx`, text field + mic/stop/send) | extract as `ReplyComposer { value, onChange, onSend, voice: VoiceState, placeholder, disabled }` so the respond step and the Revue share it; the red icon is the mic when empty, send when typed |
| Reader «sous presse» duotone (`reader-styles.tsx` `.fr-plate .fr-art[data-pending]`, `.fr-ink`, `.fr-folio`) | lift to shared `.av2 .av2-plate`, `[data-pending]`, `.av2-plate__ink`, `.av2-plate__folio` so `RvStage` and the reader use one rule set |
| `Releve.tsx` | one section slot after Le Registre: `<RvReleveSection />`, which renders nothing when there are no entries |
| `home.test.js` | a Revue hero fixture: ≤ 5 elements, ≤ 25 words, one primary, in en/de/fr |

### 4.3 New
| Name | Props | Notes |
|---|---|---|
| `RvUneCard` | `{ story: RvStoryCard; week: RvWeek; state: 'offer' \| 'evergreen' \| 'resume' \| 'filed'; resumeLine?: string; filed?: { headlineFr: string; contribution: RvSpan[] }; onOpen(): void; onOtherSubject(): void }` | La Une hero. `RvStoryCard = { dossierId, titleFr, placeFr, topic, plateUrl, stage }`, `RvWeek = { iso: '2026-W40', label: 'Semaine 40', range: 'du 28 sept. au 4 oct.' }` |
| `RvSubjectSheet` | `{ open; week: RvWeek; alternatives: RvStoryCard[]; onPick(id): void; onAsk(text): Promise<RvAskResult>; onClose }` | `RvAskResult = { match: string \| null; romyLineFr?: string }` |
| `RvChooser` | `{ recommended: RvStoryCard; alternatives: RvStoryCard[]; week; onPick; onAsk }` | `/revue` `choose` state (§5.1 in full) |
| `RvEncounter` | `{ revueId: string; initial?: RvState }` | owns the beats, the replay and the steer; mounted by `/revue` and the journey player |
| `RvSessionHead` | `{ beat: RvBeat \| null; room: RvRoom; onExit(): void; ended?: boolean }` | `RvBeat = 'arrive' \| 'facts' \| 'pursue' \| 'make' \| 'close'` |
| `RvColumn` | `{ room: RvRoom }`, `RvRoom = { used: 0..7; phase: 'open' \| 'bouclage' \| 'boucle'; srLabel: string }` | computed from `budget` and the state, never a clock |
| `RvStage` | `{ plateUrl: string; size: 'full' \| 'band' \| 'une'; cast: StageMember[]; you?: { outfit?: Outfit }; entering?: string; pending?: { folio: string } }` | wraps `PanelStage surface="revue"`; full = 4:3, band = 390:168, une = 16:9 |
| `RvThread` | `{ items: RvThreadItem[]; support: RvSupport; onWord(w): void }` | `RvThreadItem` = `narration \| line \| mine \| claims \| claimsFolded \| uncertainty \| shift \| guest \| typing`; reuses `.av2-thread*` CSS |
| `RvNarration` | `{ textFr: string }` | sans, ink-2, no face |
| `RvLine` | `{ speaker: CastId; textFr: string; past: boolean; mood?; translation?: string; support: RvSupport; glosses: RvGloss[] }` | speaker name in `--char-*`; translate chip by band |
| `RvGlossText` | `{ text: string; glosses: RvGloss[]; mode: 'shown' \| 'tap' \| 'none'; onWord(fr): void }` | `RvGloss = { fr, gloss, claimId? }`; `shown` prints a ruby under the first occurrence only |
| `RvClaim` | `{ claim: { id; kind: 'fact' \| 'interpretation' \| 'forecast'; fr; quote; attributedTo?; source: RvSource }; support; translation?: string }` | `RvSource = { name, url, publishedAt }` |
| `RvSourceLine` | `{ source: RvSource; quote?: string; attributedTo?: string }` | «D'après …, 29 sept. ↗» + «La citation» disclosure |
| `RvUncertainty` | `{ textFr: string }` | dashed outline, «Les sources ne le disent pas» |
| `RvShift` | `{ label: string }` | hairline marker, `role="status"` |
| `RvGuestEntrance` | `{ castId: string; name: string; reasonFr: string }` | 12 % accent tint on card |
| `RvQuickReplies` | `{ replies: { label: string; sendFr: string }[]; onSend(fr): void }` | label may differ from the sent French («Plus» → «Dis-m'en plus.») |
| `RvMakePicker` | `{ options: { id: RvMakeKind; titleFr; detail }[]; recommended: RvMakeKind; value; onChange }` | `ChoiceList` variant inside |
| `RvHeadlineChoice` | `{ options: ChoiceOption[]; answerId; evidence: { quote; source: RvSource }; onDone }` | `ChoiceList` + `FeedbackBand` |
| `RvQuestionDraft` | `{ learnerFr: string; proposalFr: string; contribution: RvSpan[]; whyNative?: string; onSend(); onEdit() }` | `RvSpan = [start, end]` into `proposalFr` |
| `RvContribution` | `{ children; label?: string }` (default «toi») | yellow underline + sup word, never colour alone |
| `RvDispatch` | `{ week: RvWeek; headlineFr; bodyFr?; contribution: RvSpan[]; sources: RvSource[]; readOnly?: boolean }` | the clipping |
| `RvKept` | `{ words: { fr; article?; gender?; state; gloss }[]; claims: RvClaim['claim'][] }` | «Pour ton Relevé» |
| `RvReleveSection` / `RvReleveEntry` | `{ entries: RvReleveEntryData[] }` / `{ entry; collapsed: boolean; onToggle }` | `RvReleveEntryData = { week; date; titleFr; made: { kind: RvMakeKind; textFr }; claims; words; sources }` |

## 5. Copy: Romy's voice vs the chrome

- **Chrome** is the labels, buttons, kickers and notices. It is short, sentence case, and has no exclamation marks
  and no personality. The publication words stay French in every language: «La Revue», «Semaine 40», «Fait»,
  «Interprétation», «Bouclage», «La suite la semaine prochaine.».
- **Tool chips and notices follow the chrome language** of the WP-82 tables («Traduire» / «Übersetzen»), the way
  the reader does. The mockups show the French table. Instructional explanations, such as the one-line why under a
  proposal, are in the learner's language.
- **Romy speaks French only**, *tu*, in the Québécoise journalist's register: short sentences, concrete, a little
  wry («hein»), professional about sources. She:
  - asks for help as a peer, with a need, a deadline and «tu m'aides ?»;
  - never praises like a teacher («Bravo !», «Excellent travail»): she uses what the learner said («J'ai mis ta question
    dans le titre»);
  - says what she does not know in plain words («Et là, je n'ai rien.»);
  - names the kind of statement («un témoignage, pas une source», «d'après plusieurs vignerons»);
  - never promises what the system will not do: «je la garde pour la rédaction», never «je te dirai la réponse».
- **The narrator** has no voice of its own: two sentences, present tense, a place and a gesture.
- **No line is set on the plate.** A claim never appears in a speech bubble without its card. A guest's line
  never appears as a card.
- **Banned words:** «actu», «breaking», «à la une» for the Revue (La Une is the front page itself), «quiz», «score»,
  «niveau» shown to the learner, and any relative date in claims («jeudi», «demain»), which the Temporal check enforces.

## 6. Accessibility

- **Tap targets.** Every control is ≥ 44 px (`--av2-tap`): chips that act, source-link rows, «La citation», the
  column button, and tap-gloss words. Inline words are smaller than 44 px, so the word sheet is also reachable from
  the line's «…» tool (WordHelpSheet keyboard path), and adjacent words keep ≥ 4 px spacing.
- **Plates.**
  - Text never sits on a plate. The only overlay is the folio pill on `--av2-paper`, and the × on a paper disc with a
    1 px line ring.
  - Plates are decorative (`alt=""`, stage `aria-hidden`). The narration carries the place in text.
  - In dark mode plates stay as painted, and the band gets a 1 px `--av2-line` bottom edge.
- **Contrast.** All text pairs are existing av2 pairs that already clear 4.5:1 in both themes. The ruby gloss uses
  `--av2-muted` at 11 px 600 weight: check this pair in CI (`atelier-v2-ui.test.js` contrast helper) and lift it to
  `--av2-ink-2` if it fails in dark.
- **Meaning never by colour alone.**
  - claim kind = label + shape + rule style;
  - contribution = underline + «toi»;
  - bouclage = word + red line;
  - selected make option = dot + label + mark.
- **Reduced motion** (`prefers-reduced-motion` and the rig's `still` prop):
  - no rig idle, blink or guest slide;
  - the arrive→band fold is instant;
  - typing dots are static;
  - the summary underline does not travel;
  - the duotone cross-fade is a cut.
  - One mover at a time (WP-116 phase 4) holds on the band.
- **Screen readers.**
  - The thread is an `<ol>` with «Romy : / Toi : / Margaux : » speaker prefixes.
  - `RvShift` and the guest entrance are `role="status"` and announced once.
  - The column has a sentence label.
  - `lang="fr"` on all French and `lang="de"` on glosses and translations.
  - Source links say «D'après Le Monde, 29 septembre, s'ouvre dans un nouvel onglet».
- **Text size.** Everything is in rem, so the Apparence setting moves it. At 320 px and 200 % the beat bar shrinks
  before the column, and the column never wraps.

## 7. Open design questions for the owner (recommendation first)

1. **Where the full choice lives.** *Recommend:* La Une shows the one recommended story with «Autre sujet ?» opening
   a sheet with the two alternatives and «Autre chose ?» (01 `#hero`/`#sheet`). The full three-story card (01 `#full`) is
   `/revue`'s first state when the learner comes from the chip. The alternative, all three on La Une, breaks WP-81's
   25-word Home.
2. **Toi's crop on the Revue stage.** *Recommend:* the waist crop (`half`) on `arrive` and the band, so the dress
   reads, while season panels keep the bust. The alternative is a bigger bust that still hides the apron's bow.
3. **The budget sign.** *Recommend:* the seven-line column with the word only at 80 % («Bouclage») and 100 %
   («Bouclé»). The alternatives are no indicator at all (Romy's steer alone), or a line count «encore 2 échanges», which
   reads as a timer.
4. **The terminal press.** *Recommend:* ink «Classer la Revue» (done tone), since the Revue is filed, not continued.
   The alternative is red «Continuer» back to La Une, which spends the one red on an exit.
5. **The Relevé home for Revues.** *Recommend:* a «La Revue» section in Le Relevé after Le Registre, as clippings.
   The alternative is the Carnet, but the Carnet records can-dos with seals, and a Revue is a record of facts and words
   with sources.
6. **The name in the chrome.** *Recommend:* «La Revue» in labels and «La Revue de Romy» only in the dispatch kicker
   and `/revue`'s choose state. It saves two words on La Une. This depends on package §12.1. If the owner picks
   «Le Papier», the clipping metaphor still holds and only the copy table changes.

## 8. Not verified

- The mockups are static HTML. The cast figures are placeholders in the rigs' palettes and placed by PanelStage's slot
  table; they are not `CastRig`.
- The word counts against `home.test.js` were counted by hand, not run.
- The ruby gloss contrast in dark was judged by eye only.
- Plate fallbacks (`PLACE_FALLBACKS`) are assumed, not read from code: `app/services/revue/` is being written in parallel.
