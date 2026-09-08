# Overhaul — Missions (`/missions`)

Part of the journal-system overhaul; method and contract in `docs/JOURNAL_SYSTEM_OVERHAUL.md`.
Audited 2026-07-06 against `web-frontend/pages/missions.tsx` (1,246 lines),
`app/api/v1/endpoints/missions.py`, `app/services/missions.py`, `app/services/serial.py`,
`app/services/serial_arc_planner.py`.

## Purpose

A Mission is a short (~2–4 min) real-world French moment: a character contacts you, you
handle it in French, the world reacts in character, and it resolves when the real-life
problem is solved. It doubles as the serial's "act" beat (`isSerialAct`). Functional
north star (kept from `docs/MISSIONS_OVERHAUL_PLAN.md`): FUN / REAL / CREATIVE, mint-not-
score. Its *visual* direction from that plan is superseded — see §5 of the procedure doc.

## 1. Works today (code-grounded)

- **Load & deep-link seeding.** Today's mission via `GET /missions/today`
  (`active_mission || weekly_mission || post_session_recommendation`, missions.tsx:138);
  direct open via `?mission=<id>`; auto-creation from seeds — `serial_thread_id` +
  `episode_index`, `atelier_session_id`, `concept_id[]`, `vocabulary_id[]`,
  `erratum_id[]` (querySeed :201, shouldCreateFromSeed :215, loadMission :371). This is
  how the Atelier path, errata, and the serial hand context in.
- **Chat play loop.** Character opening message, learner replies (`POST /{id}/turns`,
  mode `'chat'`), in-character world reply; turns ordered by `turn_index` (:157, :417).
  Backend dedup guards for repeated attempts/turns (endpoints/missions.py:101–155).
- **Quiet inline repair.** `TurnRepair` (:164) under the learner's own bubbles only —
  real grammar fixes only (filters `task_compliance` and vocabulary nudges), max 2,
  "Saved to your repairs"; errata are persisted to the SRS repair queue server-side.
  The character never breaks role to correct. This is a strength — keep it.
- **Vocabulary integration.** Target-word ribbon (≤3, `word – translation`, :145, :526);
  completion credits produced words (`recap.vocabulary_credit.produced_correct`, :240).
- **Translate assists** for the frame and every character message (`TranslateButton` :250).
- **Finish gating & payoff.** "Finish" disabled until ≥1 interaction ("Send first", :610);
  `POST /{id}/complete` mints a logo token (`recap.minted_collectibles`), flips the local
  day-progress flag (:442), serial acts auto-route to the next beat (:445).
- **Serial-act variant.** Header/kicker swaps to "Feuilleton act"; "Next act" link on
  completion; `mission.serial_thread_id` drives it (:331, :630).
- **States.** Loading (`LoadingState` :298), error with Retry (:501), completed with
  resolution note + reward strip + quiet links (Coverage map / New moment).
- **Bottom nav** present (`PhoneProductNav active="missions"` :307/:650).

## 2. Missing / should add (prioritised)

> **Visual pass shipped (2026-07-07):** the "Le Courrier" newspaper reskin in §5 is
> now implemented. `web-frontend/components/courrier/Courrier.tsx` ports the design
> package (`courrier-parts.jsx` / `courrier.css`) into the `--app-*` token system —
> theme-aware light/dark for free — and reuses LaUne's stamp / press-notice /
> skeleton primitives so the two surfaces are one publication. `pages/missions.tsx`
> renders through it: desk header (`CrDesk`), situation standfirst + translate glyph
> (`CrSituation`), P.S. twist (`CrPS`), word ribbon (`CrRibbon`), dépêche slips
> (`CrSlip`) with graphite repair (`CrRepair`), phone memo (`CrMemo`) + mic composer
> (`CourrierMic`) for voicemail/phone, per-format composer (`CrComposer`), and the
> resolved-dossier stamp + minted `LogoToken`. All fiction copy is French; every
> string still maps to a named payload field. Verified: tsc/lint/`npm run build`
> green; static mission tests updated + green (`test_core_mobile_edge_flows`,
> `test_core_mobile_user_flows`, `test_frontend_serial_surfaces`,
> `test_frontend_thread_destinations`, `test_frontend_red_ink_repair_slip`).
>
> **Functional-layer status (2026-07-07):** items 1–6 below were IMPLEMENTED first in
> `web-frontend/pages/missions.tsx` (functional wiring), then reskinned by the pass
> above. Summary:
> 1. **Format support** — `missionFormat()`/`missionFormatPayload()`/`missionWriting()`
>    drive a format-aware composer: email/admin_form get the `writing_*` scaffold
>    (label, instruction, multi-line placeholder, taller box) + format submit labels
>    ("Envoyer l’email" / "Déposer"); voicemail/phone get the voice recorder; chat
>    unchanged. Verified live against a real `email_formal` weekly mission.
> 2. **Voice** — `MissionVoiceRecorder` (record → `apiService.transcribeMissionAudio`
>    → transcript into composer) with idle/recording/transcribing + mic-denied/no-mic/
>    transcribe-fail messages; shown for voicemail/phone formats.
> 3. **Archive** — surfaces `today.recent_completed` (already served) as a re-openable
>    "Courrier passé" list. No new backend endpoint needed.
> 4. **Cadence** — `missionCadenceLabel()` shows "Courrier de la semaine" / "Après la
>    séance" in the scene kicker (verified: weekly mission → shown).
> 5. **Reward moment** — completion shows the minted `LogoToken` (from `components/ui/Seal`)
>    when `recap.minted_collectibles` has a `logo_token`, else the check.
> 6. **Twist** — `messenger.twist` renders as a "Coup de théâtre" line (verified live).
> 7. (Minor) quick-reply append behaviour and a "world is typing" indicator: DEFERRED.
> Verified: tsc/lint/`npm run build` green; static mission tests updated + green
> (`test_core_mobile_edge_flows`, `test_core_mobile_user_flows`, `test_frontend_serial_surfaces`).


1. **The five mission formats are invisible (headline gap).** The backend rotates
   `MISSION_FORMAT_ROTATION = ("chat_message", "email_formal", "admin_form",
   "voicemail_reply", "phone_call")` (serial_arc_planner.py:12) and writes format
   payloads — `email_formal` gets `writing_title/instruction/placeholder`
   ("Objet : …\n\nMadame, Monsieur, …"), `admin_form` gets form-field framing
   ("Nom :\nAdresse :\nDemande :") (serial.py:376–384) — but missions.tsx has **zero**
   references to `mission_format` and renders every format as the same chat thread.
   Frontend creation even hardcodes `mission_type: 'message'` (:351). WP-Y1 ("format
   variety must return") is unfulfilled at the UI layer. → Each format needs its own
   *document form* (see brief).
2. **No voice.** `POST /missions/audio/transcribe` exists (endpoints/missions.py:196) and
   the API client supports `mode: 'voice'` + `transcript_metadata`, but there is no mic
   capture UI. `voicemail_reply`/`phone_call` cannot feel real without it.
3. **No archive.** Completed missions vanish; no list/history endpoint is consumed.
   Nothing to reread, no accumulation. (Backend list endpoint would be a small addition;
   design should include the archive surface now so it doesn't get bolted on.)
4. **Cadence is flattened.** `pickMission` (:138) silently merges weekly / post-session /
   ad-hoc; the learner never sees "this is your weekly mission".
5. **Reward moment is flat.** Completion = check icon + text strip. The minted logo-token
   art exists (`components/ui/Seal.tsx`) and the home page celebrates it; missions should
   use the same reward moment.
6. **Twist never surfaces.** `messenger.twist` is extracted (:120) but never rendered —
   a variety-engine feature with no stage.
7. Minor: quick replies append into the textarea rather than acting as one-tap starters;
   no "the world is typing…" indicator while the reply generates (only a button spinner).

## 3. Design drift vs. the journal contract

- **Own palette, hardcoded light.** `:root { --mission-* }` (missions.tsx:659–669)
  ignores the `--app-*` tokens → the page is blind to dark mode (the La Une home honours
  it). Fonts hardcode Inter; **no serif voice at all** — the one page with real
  characters and stakes has no story typography.
- **Messenger-app metaphor.** Avatar circle + presence dot + bubbles reads as a WhatsApp
  clone, visually unrelated to the newspaper the user just left.
- **Desktop-ish two-column grid** (1180px, scene-column + phone-column :728) vs the
  phone-first single-column shell everywhere else.
- **Own sticky header** (`mission-nav`, backdrop blur :690) instead of edition furniture.
- English UI copy mixed into the scene ("Your reply in French", "Send first",
  "Mission resolved") — violates the language rule.

## 4. Weave-in vision — "Le Courrier" (the correspondence desk)

The front page (La Une) is *read*; Missions is where the reader **writes back**. In the
journal metaphor a mission is a piece of correspondence crossing the reader's desk, and
each backend format already maps to a natural printed artefact:

| `mission_format` | Artefact on the desk |
|---|---|
| `chat_message`   | **Petit bleu / dépêche** — a telegram-style message slip; the thread is a stack of slips, not bubbles |
| `email_formal`   | **Lettre** — letterhead sheet with Objet/greeting/body/closing structure (payload already provides it) |
| `admin_form`     | **Formulaire** — a printed administrative form with labelled fields |
| `voicemail_reply`| **Message téléphonique** — a "while you were out" phone-memo slip + mic to speak the reply |
| `phone_call`     | Live call variant of the memo slip |

The learner's sent reply gets a small postal stamp; completion strikes the whole dossier
with the same rubber-stamp language as the home page ("RÉSOLU") and mints the logo token
with the existing Seal art. The archive is a bundle of past correspondence. Same paper,
same ink, same stamps as La Une — one publication.

---

## 5. Claude Design brief — "Le Courrier"

> Copy from here down into Claude Design.

# Design brief: "Le Courrier" — Missions as the journal's correspondence desk

## Context
You are redesigning the Missions surface (`/missions`) of a French-learning app whose
home screen is already a newspaper front page ("La Une"). Study these first — the new
surface must be the same publication, not a sibling app:
- `web-frontend/components/laune/LaUne.tsx` — the shipped front page: masthead, kickers,
  hairline rules, rubber stamps (`LuStamp`), press notices (`LuNotice`), skeletons, the
  ink "press bar" CTA, and the grayscale→color "print-in" done-state mechanic.
- `web-frontend/styles/globals.css` — the `--app-*` tokens (paper/sheet/ink ×3, red,
  blue, yellow, `--app-serif` = EB Garamond) + phone-shell vars. Tokens only; the design
  must survive light AND dark theme.
- `docs/design-reference/press.css` and `serial-world-design-package.md` — the wider
  press vocabulary and the serial cast (Monsieur Marchand, Romy Tremblay, …) whose
  members author these missions.

## The concept
The front page is read; **Le Courrier is where the reader writes back**. A mission is a
piece of correspondence that crossed the reader's desk this morning. The play loop stays
exactly what it is today (character opens → learner replies in French → world reacts in
character → resolve), but staged as documents on paper rather than a chat app.

## The five formats (each is its own artefact — this is the core of the brief)
The backend supplies `prompt_payload.mission_format` and format payloads. Design one
artefact per format, sharing the same paper/ink/stamp system:
1. `chat_message` → **La Dépêche**: telegram/pneumatique slips. The conversation is a
   stack of message slips (sender name + time rule + text), NOT rounded bubbles. The
   learner's slips align right with a small postal stamp once sent.
2. `email_formal` → **La Lettre**: a letterhead sheet. The composer IS the letter —
   fields for Objet, greeting, body, closing (payload provides `writing_title`,
   `writing_instruction`, `writing_placeholder`). The character's reply arrives as a
   return letter.
3. `admin_form` → **Le Formulaire**: a printed administrative form with labelled boxes
   (Nom / Adresse / Demande …), stamped "REÇU" when submitted.
4. `voicemail_reply` → **Le Message téléphonique**: a "pendant votre absence" phone-memo
   slip showing the transcribed voicemail; the reply composer offers a microphone
   (speak) AND a written fallback. Design record/recording/transcribing states.
5. `phone_call` → live-call variant of 4: the memo slip plus a call strip
   (answer → speak → hang up), same mic states.

## Page anatomy (mobile-first 375–430px, single column, safe-area aware, ≥44px targets)
1. **Desk header** — edition furniture, not an app bar: kicker "LE COURRIER" (or
   "LE FEUILLETON · ACTE N" when `serial_thread_id` is set), the mission title as a serif
   italic headline, a cadence tag when relevant ("Courrier de la semaine" for weekly),
   and a discreet ← back to La Une. Status shown as printed marginalia, not a pill.
6. **The situation** — the frame + ask (payload `slim_payload.frame` / `.ask`) set like a
   short editorial standfirst above the artefact; translate assist as a small marginal
   glyph. Surface `twist` (payload) as a one-line "P.S." tucked into the artefact when
   present.
3. **The artefact** — one of the five formats above, carrying the correspondence so far
   (turns). The learner's own slips carry the quiet repair note underneath (existing
   `TurnRepair` content: corrected form + why, "Saved to your repairs") — keep it small,
   graphite-pencil tone, never in the character's voice.
4. **Word ribbon** — ≤3 target words as typeset marginal vocabulary ("à placer :").
5. **Composer** — per-format (slip / letter / form / mic). Quick replies are one-tap
   starter slips. Primary action = the ink press-bar from La Une ("Envoyer" /
   "Déposer" / "Parler"). Secondary "Terminer" gated by "Send first" logic — French:
   "Envoie d'abord".
6. **Resolution** — on completion the dossier is struck with a rubber stamp ("RÉSOLU",
   serial acts: "ACTE BOUCLÉ"), the minted logo token appears (reuse the existing Seal
   art direction), vocabulary credit line, then: next act (serial) / "Nouveau courrier" /
   back to La Une.
7. **Bottom nav** (`PhoneProductNav`) untouched.

## States to design (all of them)
1. Chat/dépêche mid-conversation (2 turns + one repaired learner slip).
2. Lettre (email_formal) empty composer + its completed/reply state.
3. Formulaire mid-fill.
4. Voicemail with mic: idle / recording / transcribing / sent.
5. Resolution/stamped state with minted token.
6. Weekly-cadence variant of the desk header.
7. Loading skeleton (press style, no spinners), error press-notice (label + message +
   Retry, like `LuNotice`), empty state ("Aucun courrier — la Une vous attend").
8. Every state in **light and dark** (tokens make this nearly free — verify contrast).

## Copy rules
French for everything in the publication world (kickers, stamps, field labels, buttons
that belong to the fiction: "Envoyer", "Terminer", "Nouveau courrier"). English only for
out-of-fiction chrome ("Retry"). Never mix languages in one line. Write ALL copy for all
states — real strings, no lorem ipsum.

## Hard constraints
- `--app-*` tokens only; derived values documented. No page-local palette.
- EB Garamond (`--app-serif`) for headlines/character voice; grotesk for chrome.
- Animations: transform/opacity/filter only; respect `prefers-reduced-motion` (stamps
  appear without animation).
- Honest data: every string maps to a named payload field (`mission_format`,
  `messenger.*`, `slim_payload.frame/ask`, `writing_*`, `target_vocabulary`,
  `recap.minted_collectibles`, `recap.vocabulary_credit`, `twist`, `serial_thread_id`,
  `cadence`). Design the empty variant of anything optional.
- Do not redesign the bottom nav or the home page.

## Deliverables
1. High-fidelity mobile frames (390px) for states 1–7, light + dark for at least the
   dépêche and lettre formats.
2. A component spec: the shared "correspondence" primitives (slip, letterhead, form
   field, phone memo, stamp variants, composer bar) with props and their payload
   mapping, spacing scale, and the stamp/print-in transition spec.
3. Full French copy deck for all states.
4. A short migration note mapping each new component onto what it replaces in
   `pages/missions.tsx` (mission-nav, scene-frame, phone-column thread, composer,
   reward-strip).
