# WP-117 · La troupe qui bouge: interactive characters (proposal)

*Status: proposal of 2026-10-01, written by a design agent for the owner; it starts after WP-116 phase 3. The owner decides the shortlist in §5. The rig sources it refers to are the variant-C canvas rigs (claude.ai/artifact/6Lr278xt6RDmRhYHDwt8WS), to be ported by WP-116.*


*Design proposal, 2026-10-01. Input: the ten variant-C rig sources (`scratchpad/cast-svg/project/*.dc.html`), the season-1 bible (§4 cast, `10-lieux-et-images.md` motifs, `11-pedagogie.md`), T1 «Le mauvais accueil», WP-109/110/115, and `web-frontend/components/atelier-v2/journey/`. Nothing here changes the plot, a line or a choice. Every move below comes from something already in the bible.*

## 0. What the rigs can do today (read from source)

| Capability | State in the sources |
|---|---|
| Moods | `neutre · ravie · surprise · fachee · emue` on every face rig. Each mood sets a head tilt, an eye state (`wry/happy/wide/cross/sad/level/heavy`), the brows and a default mouth. |
| Mouth | `rest · a · o · e · m · f`, plus mood mouths (`smirk/smile/grin/frown/soft`). In `Main.dc`, a fixed **115 ms setInterval** steps a hand-written viseme array. That timing is not tied to the audio. |
| Blink | a boolean prop. The parent toggles it on a timer (3.3 s / 4.3 s). |
| Gaze | **already half there**: each eye takes `dx/dy` pupil offsets, but they are constants per character (Lila `dx:4`, Marin `dx:-2`, Gus `dy:2`). Exposing them as a prop costs almost nothing. |
| Idle | one SMIL `<animateTransform repeatCount="indefinite">` per rig: Margaux bob 4.2 s, Marin 4.8 s, Lila 2.8 s (the liveliest), Gus a −2.5° theatrical sway at 3.6 s, Marchand a +3° sway at 5.2 s, Romy 5 s, Camille 4.6 s, Odile 3.2 s, Toi a 4 s breath. Romy's camera tally light also blinks forever (SMIL opacity, 1.6 s). |
| Props | only Margaux has a `hold` prop (`verre · tasse · cle`; the key has its cicada). Every other prop is baked in: Gus's cards and red pocket square, Marchand's ring, Romy's camera, Camille's helmet, Odile's camera. |
| Crops | `full · bust · head` (Toi: `full · bust`). Camille has a `variant: f/m`. |

**Two problems to fix before any of this ships.**

1. **SMIL ignores `prefers-reduced-motion`.** A CSS media query cannot stop `<animateTransform>`. Today every idle loop, and Romy's blinking light, would keep running for a learner with Reduce Motion on. That breaks WCAG 2.2.2 (Pause, Stop, Hide: anything moving for more than 5 s) and the house rule that the journey already follows for the typing reveal and the Seal (`prefersReducedMotion()` in `lib/journey-reply-reveal.ts`).
2. **Visemes on a fixed clock drift from the voice.** Any voice longer than about two seconds, or any clip at 0.75×, drifts out of sync.

---

## 1. Principles: when the cast moves, and when it stays still

1. **Every move has a job.** A move must signal who is speaking, show where to look, give feedback, or mark a story beat. The research is blunt here. In a meta-analysis of 20 experiments, agent gestures helped retention (g ≈ 0.28) and transfer (g ≈ 0.39) ([Davis 2018](https://www.sciencedirect.com/science/article/abs/pii/S1747938X18302343)). But facial expression, gesture and gaze with no meaningful link to the material had no effect, and only pointing with a clear target helped ([review](https://www.researchgate.net/publication/362879152_Effects_of_Gesture_by_Pedagogical_Agents_in_Multimedia_Learning)). Instructor gaze that guides attention helps too ([meta-analysis, 2023](https://link.springer.com/article/10.1007/s10648-023-09820-7)). So a decorative wave is out, and a glance at the cup Margaux is naming is in.
2. **The cast is still while you read, type or decide.** While a field has focus, a caption is being read, or an option is waiting to be picked, faces drop to blink plus breath, with an amplitude of 1 px or less. Mouths move only while audio plays. Nothing loops in peripheral vision next to a text field.
3. **One mover at a time.** On ensemble screens (La Une, the reader's group panels, the recap), only the speaker or the reactor animates, and everyone else holds a pose. This is the motion version of "one primary button per screen".
4. **Never telegraph the answer** (the Atelier no-spoil rule, extended to bodies). No mood change, gaze or lean before the verdict. In a by-voice «Qui parle ?», every mouth stays at `rest` while the clip plays. Live reactions while typing show *attention*, never *evaluation*.
5. **Feedback is in character, and the character carries the mistake.** A wrong answer never gets a face turned cross *at the learner*. Today's `WhoSaid` does exactly that: it sets `moodFor('wrong') = 'cross'`, and that has to change. Every wrong-answer reaction below either takes the blame (Gus's cards fall), forgives (Margaux «J'ai rien entendu»), or hands over the right form (Lila's napkin, Marchand's right key). Reactions last 1.2 s or less and never block «Continuer».
6. **Reduced motion is a designed state, not a missing one.** Under Reduce Motion:
   - moods swap instantly (a pose change, not a tween);
   - mouths stay at `rest` and the speaking face keeps the still accent ring that `SpeakingPortrait` already uses;
   - idle loops are paused;
   - signature moves become a single end-pose (Gus's cards are already on the floor; Romy's light is simply off).
   The meaning has to survive with no motion at all.
7. **Canon over cute.** Every signature move is a bible gag or small moment, rationed so it keeps working: a signature move plays at most once per session per character, and correct-answer reactions rotate through 3 variants. Toi is never face-on and never reacts to their own errors. Odile appears only inside a Polaroid or a faded-ink 2023 frame, never "live" in the present. Camille's agreement-free rule extends to exercises: no adjective-agreement item is ever built on Camille.

---

## 2. Signature-move sheet

Durations: an idle loop is 3–5 s at ≤ 2 px / ≤ 3°, and blink-only while the learner is busy. A signature move is about 0.8–1.5 s. Reactions are 1.2 s or less.

| Character | Idle loop | Signature move (bible source) | Correct answer | Wrong answer (never punishing) |
|---|---|---|---|---|
| **Margaux** | Slow 4.2 s bob. Every third cycle the cloth makes one turn inside the glass. | **Dries a glass that is already dry** (§4 running gag). Variant: the hand **stops on the cicada** (T1 P3), used only when the key word or `la clé` is in play. | Sets the glass down, gives a short nod, and **slides a café crème forward** (`hold: tasse`): «Bois.» The cup is a reward without a point, the way she rewards in the story. | Keeps drying, one brow up: **«J'ai rien entendu.»** Then the field clears for a second try. Her gag ("she heard everything") becomes forgiveness: the mistake didn't happen. |
| **Lila** | The fastest bob (2.8 s), plus a pencil that **draws on a napkin** when she is a bystander in a group frame. | **Grades a decision: «Sept sur vingt. Peut mieux faire.»** She lifts the napkin with the grade in red. This is reserved for *other characters'* choices (Gus's plans), never for the learner's answers. | «Vingt sur vingt. Je le dis à ma classe.» A tick on the napkin and a quick ochre-thumb point at you. | **«Presque.»** She writes the right form on the napkin and turns it toward you, so the correction sits in the margin (11-pedagogie: grammar is corrected in the margin). Under surprise she slips into Marseille: «Oh, fan de chichourle !», used only on a near-miss and never on a blank. |
| **Gus** | A theatrical sway (−2.5°, 3.6 s), one hand on the lapel. | **The index cards fall.** He fans them for a speech and they slide out of the breast pocket behind the red pocket square (T3, T4, gap 3). | **Superlatives that grow** within a session: «Magnifique.» → «Non : sublime.» → «Historique.» He resets the next day. | **His cards fall, not you:** «Règle numéro un de La Méthode : on recommence.» He gathers them while the right answer shows. When he is upset in a story scene, he straightens the salt cellars; that move belongs to the story, never to feedback. |
| **Marin** | A 4.8 s bob, with a spoon stirring a bowl when `hold: bol`. | **Wipes a tear** (cries at adverts). Kept for sincere moments: the Seal of a tentpole day, or a reply where the learner says something true (T5 can-do). | «C'est un signe, ça.» A small fist, eyes `happy`. | **«Ma grand-mère disait toujours…»** plus an absurd proverb from a rotating set, then «Bon. Qui veut une soupe ?» as the bowl is pushed forward. Comfort, then the right form. |
| **Romy** | A 5 s bob. The camera on its strap has its **red tally light ON, steady**. The current endless blink goes: it moves forever and would read as a recording indicator nagging the learner. | **Switches the camera off so you can see her do it** (§4 small moment). Her thumb finds the button and the red light dies with a small click haptic. | **«C'est pas pire !»** It is Québec understatement for "great". The first time, a one-line gloss explains it, which makes it a cultural word in itself. | **She switches the camera off: «On recommence. C'est off.»** The mistake isn't on the record. Her signature move *is* her wrong-answer reaction, which makes her the safest face for hard formats (audio rung, rescue). |
| **M. Marchand** | A slow 5.2 s sway. The **key ring** at his hip catches the light. | **Finds one key on the heavy ring**: he lifts it, sorts, and holds up the one. Small moment: **reading glasses pushed down his nose** to read a Polaroid or a form. | The key turns in the air (a 90° rotate) and he says «La succession Ferrand est à jour.» It is the opposite of his running «…est en retard», so it reads as dry praise. | Glasses down, he re-reads, tries **the wrong key, then the next one**: «Non. Celle-ci.» The right form appears on the key's tag. It is procedure, not judgement. |
| **Camille (f/m)** | A 4.6 s bob, helmet under one arm. Every few loops, one rain-drip falls off the helmet rim. | **Corrects a number** («Pas cent. Quatre-vingt-dix-sept.»): a pen tap on the folder of figures. In the story this is aimed at Gus's superlatives. | «Exact.» A level nod and a pen tick. Camille never gushes, so the nod is worth more. | **«Pas tout à fait.»** A precise correction of the number or word, with the folder turned toward you. Dry, never contemptuous (§4). |
| **Odile** | **None in the present.** She exists only as a **Polaroid** (white border, flash colours) or a faded-ink 2023 frame. Inside a Polaroid, a 3.2 s breath at most, and only while the Polaroid is in focus. | **The Polaroid flash**: a white flash, then the image **develops** over 1.5 s into her laughing at something out of frame. Her caption in blue ballpoint handwriting fades in after it. | The Polaroid develops fully. Used for milestones only, never per answer: a word *retrieved at 21+ days* (WP-115 §4.4), or a level move. | No wrong-answer reaction. Odile never judges, and she never appears on an error. |
| **Toi (from behind)** | A 4 s breath. The coat's shoulder lifts. | **Clips the cicada back onto the key ring** (§4 small moment). It plays when a word is **kept** («Garder» in the reader): the word joins *your* ring. | Toi has no face reaction. The only cue is the **balloon** popping from behind the shoulder when a reply is sent. | Never. Toi is the learner, and a self-shaming avatar is out. |

The **ensemble** reaction, at the Seal and on a streak milestone, is not cheering. **Margaux pours a café crème in front of Odile's stool** (motif: a coffee nobody ordered), the day's character gives a one-line nod, and everyone else holds still. Calm, as `JourneyRecap` already promises ("the cast's face is the reward"). Do **not** tie the streak to Toi's return ticket: `user.return_ticket` is a story flag the learner chooses, and the app must never move it.

---

## 3. Interaction patterns, mapped to surfaces and to the recall ladder

Effort is **S** (≤ 2 days with today's rigs), **M** (one new rig capability) or **L** (several capabilities or server work). The ladder rungs are from WP-115b: first meeting → scene → recognition → production → audio → cloze, plus rescue.

| # | Pattern | Surface / rung | Learning value | Effort | Rig needs |
|---|---|---|---|---|---|
| P1 | **Tap-to-hear with lip sync.** The face is the play button (today's `SpeakingPortrait`), and the mouth now moves in time with the clip. | Reader captions, `RespondThread`, `HeardLine`, Courrier. All rungs with a voice. | Binds voice to face, so speakers become recognisable by ear (the WP-91 aim). Visible onsets and pauses help segment a sentence. | **M** | A viseme track synced to `audio.currentTime`; a mouth swap with no React re-render per frame. |
| P2 | **«Qui parle ?» by voice.** One line plays, three rigs listen with mouths shut, and you tap the speaker. Afterwards the speaker says it again *with* lip sync. | `WhoSaid` upgraded to the **audio rung**. | Real listening: register and idiolect. Romy's «Voyons donc», Margaux's two words, Gus's «Mesdames, messieurs !», Marchand's procedure. | **S** | A `listening` pose (gaze toward the learner, slight lean). The wrong pick **shrugs and glances at the true speaker**, replacing today's `cross`. |
| P3 | **L'objet tendu.** The character who said the word holds the object out: «Qu'est-ce que Margaux pose devant toi ?» (the `Exercise.dc` board). | **First meeting** (guess before the reveal), **recognition** (pick), **production** (type or say it, cued by the object rather than an L1 gloss), **scene** rung (her recorded line blanked). | Concept→French with no translation step, plus episodic memory (who, where). The WP-115 panel-and-voice cue made physical. | **M** | A prop library for every rig plus an `offer` arm pose (hand toward the camera, where Toi is). |
| P4 | **Le mot qu'on te demande.** The WP-115 §4.2 "need": Gus can't remember a word, **mimes turning a key**, and asks «Comment on dit déjà, ce truc… ?». You answer in the reply. | The respond step on a generated day, for the hardest due words. Graded as production. | Retrieval from a gesture: the meaning without L1, inside a real exchange. It is the different encounter that leeches need. | **M** | A gesture library (`mime`: turn-key, drink, write, photograph, carry) plus `ask` (open palm). The gesture name travels with `turn_plan`. |
| P5 | **«Tiens, tu l'as retenu !»** When a due word is used unprompted (WP-115d `noticed_word`), the character does their *correct* reaction plus one glance at the word in your balloon. | Respond thread, Courrier reply. Transfer. | Rewards free use (the top rung) socially, with no points. | **S** | Gaze toward a target (your balloon, lower right). |
| P6 | **Lis le visage.** A face plus a short question: «Comment est Margaux ?» → *fatiguée* (T7 B lexicon). Also the reverse: hear a line with its prosody, pick the face. | Recognition (pick the face), production (type the adjective, with the face as the cue). Practice after the ending. | Emotion adjectives *with agreement* (Lila *contente*, Marin *content*). Pragmatics: «J'ai rien entendu» said `wry` means she heard everything. Never built on Camille. | **S** (5 moods) / **M** (adds `fatiguee`, `inquiet·e`) | More moods per character. |
| P7 | **Au ralenti, la bouche.** Replay at 0.75× with visemes kept, for dictation. | `Dictation` / `HeardLine` replay, audio rung. | Segmentation and rounding cues. Visual speech helps L2 sound perception ([Navarra & Soto-Faraco 2005](https://link.springer.com/article/10.1007/s00426-005-0031-5); [lip movements and gesture in L2 listening](https://www.degruyterbrill.com/document/doi/10.1515/9783111568645-008/html)). **The honest limit:** six cartoon mouths carry rhythm and lip rounding, not phoneme identity. Pitch it as "see where the words break", never as pronunciation teaching (WP-27 rules out pronunciation). | **M** | 0.75× playback with a scaled viseme track; two added visemes (`u` rounded-small, `i` spread) so French rounding is visible. |
| P8 | **Live attention while you type a reply.** The character turns to you when the field gets focus, blinks, and gives one small nod when you type a full stop. When you send, Toi's balloon pops and the existing «Marin écrit…» shows a `thinking` pose. | `RespondThread` / `ReplyStage`. | Social presence: you write *to someone*, which lengthens replies. **Constraint:** attention only, never evaluation (principle 4), and nothing loops. | **S** | `look-at-learner` gaze, a nod. |
| P9 | **Tu ou vous ?** Two-character interplay. You address Marchand and Lila in turn. Saying *vous* to Lila earns «Tu me vouvoies ? Je le dis à ma classe.» with a grin. Gus's weaponised *vous* is shown as a cold bow. | A warm-up or practice item on T1–T3 days. | Register, the main pragmatic error for A1–A2 learners, taught by the cast's own gags. | **S** | A `bow` pose (Gus), a mood swap. |
| P10 | **Les chiffres de Camille.** Gus claims a figure; Camille taps the folder and gives the real one. You hear the number and type it, or pick the right figure. | Audio rung and cloze, for numbers (soixante-dix, quatre-vingt-dix-sept: a classic French trap). | Gives the hardest closed vocabulary set a speaker and a reason. | **S** | Camille's pen-tap gesture; two characters in frame. |
| P11 | **«Gus a une astuce».** Leech rescue (≥ 5 lapses, «un mot têtu»). Gus pulls a card from the fan: the mnemonic or image is written on it, and the first letter and length are on the back. | Rescue rung (WP-115b). | A changed method for stubborn words, given by the character whose gag is index cards. | **S** | A card prop that can be drawn out of the pocket. |
| P12 | **Le Polaroid se développe.** A word retrieved at 21+ days develops a Polaroid in «Les mots de Margaux» (the per-character collection). Its caption in Odile's hand uses the word. | The Cahier collection; milestone only. | Motivation tied to *retention*, not activity. The caption is a short authentic handwritten read. | **M** | A Polaroid render mode (frame, flash, develop) and a faded-ink mode. |
| P13 | **La Une reflects yesterday.** The four-face header (`Une.dc`) takes moods from yesterday's flags. If you gave the letter to Romy, she leads the group and the camera light is off. If you said «Je vends», Marin is `emue`. The «Précédemment» line is the caption. | The Home / La Une headline (`JourneyTodayCard`), outside the day. | Mainly motivation (consequences are visible). Light narrative recall before the day's warm-ups. | **M** | Flag→pose map (server: `headline.cast[].mood`); ensemble layout; one mover. |
| P14 | **Le courrier signé d'un geste.** The letter's closing formula comes with a small signing vignette: Marchand stamps a *recommandé* («Je vous prie d'agréer…»), Lila leaves an ochre thumbprint («Bises»), Gus a flourish on a card («Votre dévoué»), Romy «À plus !». | Courrier (WP-115d's weekly letter). | Makes the register of a sign-off noticeable; motivation. | **S** | The `sign` gesture plus props (stamp, thumbprint, card). |
| P15 | **Le regard qui montre.** In the reader, when a caption names an object, the speaker glances at it in the plate (deictic gaze). The word is underlined at the same moment. | Reader panels, first meeting. | Maps the referent for new words. The one kind of gaze the research credits. | **M** | Gaze targets in plate coordinates, so plates need hotspot data. |

---

## 4. Rig capabilities to add, in priority order

| Priority | Capability | Why | Notes |
|---|---|---|---|
| **P0** | **Motion contract**: a `still` prop, idle moved from SMIL to CSS keyframes (or `svg.pauseAnimations()`), Reduce Motion honoured, idle paused off-screen (IntersectionObserver), only the latest face animated in a thread. | Principles 2 and 6. Fixes WCAG 2.2.2 and battery drain on threads with many faces. | Reuse `prefersReducedMotion()`. iOS Reduce Motion reaches WKWebView through the same media query. |
| **P0** | **`RigPortrait` adapter** behind `CastPortrait`. It maps `PortraitMood` (`neutral/happy/cross/moved`) to `neutre/ravie/fachee/emue` and keeps the image fallback for anyone without a rig (the notaire, Mme Diallo). | Every existing surface (WhoSaid, recap, thread, CastIntro) gets the rigs in one swap. | Keep the `data-*` and ARIA contracts the tests pin. |
| **P0** | **Audio-synced visemes.** A track of `[t_ms, viseme]` is read from `audio.currentTime` in requestAnimationFrame, and the mouth `d` is set via a ref. | P1, P2, P7. Removes the 115 ms clock drift. | Track sources, cheapest first: (a) a **French grapheme→viseme heuristic** stretched to the clip's duration, with pauses at punctuation (deterministic, free, testable in node); (b) a **Web Audio amplitude gate** that closes the mouth in silences and corrects drift (server clips only: `speechSynthesis` output can't be analysed); (c) later, **offline forced alignment** of each *cached* clip, run once at clip-cache time with a free local aligner. No paid call is needed, since OpenAI TTS returns no timings. The `speechSynthesis` fallback uses `onboundary` word events where WebKit sends them, and (a) otherwise. |
| **P0** | **Gaze and look-at-learner.** Expose the existing `dx/dy` as `gaze: 'learner' \| 'left' \| 'right' \| 'down' \| {x,y}`, plus a ±4° head turn. | P2, P5, P8, P15. Nearly free. | The pupil can't cross the lid; clamp to ~0.4 × rx. |
| **P1** | **Generalised `hold` (prop swap) on every rig**, drawn from the scene lexicon: tasse, verre, clé + cigale, chocolat, bol, Polaroid, carte(s), trousseau, casque, pinceau, carnet noir, calendrier, deux croissants, lettre recommandée. | P3, P11, P14. Props *are* the 11-pedagogie word floors. | One shared prop set, anchored to each rig's hand point. Margaux's anchors are the template. |
| **P1** | **Gesture library**: `offer`, `ask` (open palm), `point` (L/R/target), `shrug`, `nod`, `bow`, `sign`, `mime:{turn-key, drink, write, photograph, carry}`, plus each character's signature. | P3, P4, P9, P14 and section 2. | Two-segment arm paths with 4–6 fixed poses per character. No IK. Tween between poses with a CSS transform on the forearm group. |
| **P1** | **Two more visemes**: `u` (small rounded, for tu / vu / dessus) and `i` (spread, for oui / dix). | P7: rounding is the visible French contrast. | Draw the mood mouths per character; the 6 → 8 swap is backward compatible. |
| **P2** | **Extra moods**, shared: `ecoute` (listening) and `fatiguee` (T7 B). Per character: Margaux `oracle` (lid-heavy smirk), Lila `deduction` (one brow), Gus `theatre`, Romy `curieuse`, Marchand `lunettes` (glasses down), Camille `pas-d'accord` (level). | P6, and story beats. | Each one is an eye state + brows + mouth: data, not drawing. |
| **P2** | **Render modes**: `polaroid` (white border, flash palette, develop) and `flashback` (paper + cobalt at half strength, one warm accent, per 10-lieux rule 4). | Odile (P12) and 2023 scenes. | An SVG filter or a palette swap at the component level. |
| **P3** | **Enter/exit** (slide in from a frame edge with a step bob; the door bell in T1 P2/P8) and **two-rig interplay**: a hand-off between rigs (Margaux→Toi the key), mutual gaze. | La Une, the reader's act panels. | Only after the rest proves useful. Toi's hand-only crop (`crop: 'hand'`) for the key on the zinc. |

### Runtime: stay on React inline SVG (CSS + WAAPI); don't move to Rive now

**Why Rive is tempting.** Duolingo runs its cast on Rive state machines: separate pose and mouth states, about 20 visemes per character, phoneme timing from their own speech models, and idle/success/failure states blended at runtime ([Duolingo blog](https://blog.duolingo.com/world-character-visemes); [Rive × Duolingo, Lily video call](https://rive.app/blog/duolingo-s-ai-powered-video-call-brings-lily-to-life)). Its transitions are smoother, a designer authors behaviour as data, and bones and meshes allow body deformation.

**Why it's wrong for this project now.**

- **Authoring.** The owner chose rigs *drawn in code*, they are parametric (mood geometry computed, Camille f/m as a prop), and nobody on the team animates in the Rive editor. Moving would mean redrawing all ten characters as `.riv` files, and every later prop or mood would wait on an animator.
- **Weight.** `@rive-app/canvas-lite`, the smallest web build, is ~222 KB brotli of JS plus a WASM fetch (~260 KB as of v2) ([npm](https://www.npmjs.com/package/@rive-app/canvas-lite); [runtime sizes](https://rive.app/docs/runtimes/runtime-sizes); [preloading WASM](https://rive.app/docs/runtimes/web/preloading-wasm)). A variant-C rig is ~11 KB of source, ~3 KB gzipped, with no runtime at all.
- **Web and iOS.** Rive runs in WKWebView, but every face becomes a canvas: no SSR, no DOM for ARIA or tests, memory multiplied across a thread of faces or a four-rig La Une, and audio-unlock rules to respect. Inline SVG renders server-side, prints in the archive's finished page, and is tested by the existing node `*.test.js` harness.
- **Reduced motion.** It is not automatic in either option. In SVG it is one media query plus `pauseAnimations()`. In Rive it is an input wired per state machine.

**What to do instead.**

- Pose changes are prop swaps.
- Transitions are CSS transforms on groups: head, arm, prop.
- Mouth `d` swaps are instant, as Duolingo's are, set via a ref so React doesn't re-render per frame. Don't rely on CSS `d` interpolation: WebKit support is unreliable.
- Signature moves are short WAAPI timelines with a reduced-motion end-pose.

**Revisit Rive** if the season needs walk cycles, cloth or limb deformation, or the owner hires an animator. The rig contract (props in, events out) would carry over unchanged.

---

## 5. Ranked shortlist: the first six to ship

**1. Le visage qui parle (P1 + the P0 contract).** `RigPortrait` replaces the static portrait behind `CastPortrait` and `SpeakingPortrait` everywhere.
- Tapping a face plays its clip: the server clip first, otherwise the device voice (as `useLineVoice` does today). The mouth follows a viseme track built from the line's French text and stretched to the clip's measured duration, with the amplitude gate closing it in silences.
- Idle runs only on the newest face in view, is paused while any field has focus, and is gone under Reduce Motion. In that case the still accent ring marks the speaker, as today.
- Done when: the speaking face's mouth moves only while `audio.currentTime` advances; a 0.75× replay stays in sync; a test pins "no SMIL idle under reduced motion".
- Everything else in this list builds on it.

**2. Les réactions en personnage.** Replace the verdict faces (`moodFor` in `WhoSaid`, the respond step's closing verdict, `MatchPairs` flashes) with the section 2 table:
- Margaux «J'ai rien entendu» + a second try;
- Romy turns the camera off;
- Gus's cards fall;
- Marin's proverb and soup;
- Marchand's wrong key, then the right one;
- Lila's napkin with the right form;
- Camille's «Pas tout à fait».

Rules:
- The reacting character is the day's speaker (`journeySpeaker`).
- Reactions are 1.2 s or less and never delay «Continuer».
- Correct reactions rotate 3 variants; each signature plays once per session per character.
- The right form is always shown in text at the same moment, so the reaction never carries the correction alone.
- Haptics come from `useJourneyFeel`.
- **No face ever turns `fachee` at the learner.**

**3. L'objet tendu (P3).** A practice format bound to WP-115's ladder. The character who gave the learner the word (card metadata: speaker, panel) stands on the word's place plate and holds the object out (`hold` prop, `offer` gesture).
- **First meeting:** «Qu'est-ce que c'est ?» Guess, then the reveal with her recorded line.
- **Recognition:** three French options.
- **Production:** type or say the word, cued by the object only, with no L1 gloss.
- **Scene rung:** her own line plays with the word blanked and her mouth moving.
- A correct answer triggers her correct reaction (the café crème is pushed forward).
- Starter set: the 15–20 concrete nouns of the T1–T4 word floors (la clé, la tasse, le calendrier, la boîte, la photo, le manteau…). Abstract words stay on the text rungs.

**4. «Qui parle ?» à l'oreille (P2).** An upgrade of `WhoSaid` to the audio rung.
- The line plays with no text; three rigs listen in the `ecoute` pose with mouths at `rest` (no-spoil); the learner taps a face.
- On the verdict, the true speaker says the line again with lip sync and the caption appears.
- A wrong pick shrugs and glances at the true speaker: it shows the learner where to look and doesn't scold.
- Distractors are chosen for distinct voices first (the seven fixed `cast_voices`), so the item is about the ear, then about idiolect at B1.
- Romy's lines teach that a Québec accent is French too.

**5. Le mot qu'on te demande (P4 + P5).** The WP-115 §4.2 flagship, staged.
- On a generated day carrying a hard due word, the asking character performs a **mime** for it (Gus turns an invisible key; Marin mimes a spoon; Romy a photo) with the `ask` palm, and the line «Comment on dit déjà… ?».
- The learner answers in the reply; the tutor lane grades it as production, as today.
- When a due word appears unprompted (`turn_plan.noticed_word`), the character glances at the word in Toi's balloon and does their correct reaction: «Tiens, "la clé" ! Tu l'as retenu.»
- Server: a `gesture` field next to the need in the director brief, chosen from a closed list of the mimes the rigs can do, so the generator can't ask for a move the rig can't draw.

**6. Lis le visage (P6).** A cheap, high-value practice item built on the five moods that already exist.
- A rig shows a mood on its place plate, with the question «Comment est Lila ?»
  - A1: three adjectives;
  - A2: typed, with agreement checked: *contente / content, fâchée, émue, surprise / surpris*;
  - B1: «Pourquoi ?», answered from the day's scene.
- The reverse form: hear a line said with intent («J'ai rien entendu») and pick the face that matches its meaning.
- Never built on Camille (agreement-free rule), and never on Odile.
- Adds `fatiguee` before T7 B, whose word floor needs it.

**Next, once these are in:** P13 La Une (needs `headline.cast[].mood` from flags), P11 «Gus a une astuce» (rescue), P10 Camille's numbers, P14 signed letters, P12 Odile's Polaroids for 21-day retrievals, P15 deictic gaze (needs plate hotspots).

---

### Sources
- Duolingo, *World character visemes*: https://blog.duolingo.com/world-character-visemes
- Rive, *Duolingo's AI-powered Video Call brings Lily to life*: https://rive.app/blog/duolingo-s-ai-powered-video-call-brings-lily-to-life
- Rive runtime sizes: https://rive.app/docs/runtimes/runtime-sizes · canvas-lite: https://www.npmjs.com/package/@rive-app/canvas-lite · Canvas vs WebGL2: https://rive.app/docs/runtimes/web/canvas-vs-webgl · Preloading WASM: https://rive.app/docs/runtimes/web/preloading-wasm
- Davis (2018), *The impact of pedagogical agent gesturing in multimedia learning environments: a meta-analysis*: https://www.sciencedirect.com/science/article/abs/pii/S1747938X18302343
- *Effects of Gesture by Pedagogical Agents in Multimedia Learning* (review): https://www.researchgate.net/publication/362879152_Effects_of_Gesture_by_Pedagogical_Agents_in_Multimedia_Learning
- *Effect of the Instructor's Eye Gaze on Student Learning from Video Lectures* (2023 meta-analyses): https://link.springer.com/article/10.1007/s10648-023-09820-7
- Navarra & Soto-Faraco (2005), *Hearing lips in a second language*: https://link.springer.com/article/10.1007/s00426-005-0031-5
- *Visibility of lip movements and gestures equally facilitates L2 listening comprehension*: https://www.degruyterbrill.com/document/doi/10.1515/9783111568645-008/html
- Florence (Mountains): the interaction's shape carries the relationship state: https://gamesbeat.com/florence-uses-clever-interactions-to-create-a-relatable-mobile-game-about-romance/ (an inspiration for P8/P13: the mechanic expresses the relationship, not decoration)
- WCAG 2.2 SC 2.2.2 Pause, Stop, Hide: https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html · SC 2.3.3 Animation from Interactions: https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html
