# WP-122 · La Radio et le Correcteur: the newspaper's other desks

*Defined 2026-10-03. Owner's brief: «anything really missing? be innovative». Open decisions
delegated to the lead. Builds on WP-119 (the week's dossiers, Romy's lines, the guest), the line-voice
pipeline (`episode_audio.speak_text`, `cast_voices.py`, `line_audio.py`, the `DICTATION` format of
WP-91) and the errata (`journey_errata.py`, `error_memory.py`, `grammar_map.py`).*

## 1. Goal

**A. La Radio.** The week's Papier as a 50-second bulletin in the cast's voices: Romy reads the lede
and three claims, a guest gives their one-line reaction, a jingle of nothing (silence and the paper
texture). Listen first, read after, then a dictée of one sentence. A tiny habit surface for the days
between Papiers that answers the listening gap with real French news rhythm.

**B. Le Correcteur.** Romy's draft arrives with mistakes seeded from the learner's own error profile,
and the learner marks them before it goes to print. Noticing is the step most apps skip; the newspaper
metaphor makes it natural; it reuses the errata and the grammar map.

**Non-goals.** No podcast feed, no background audio service, no social sharing. No new voices beyond
`cast_voices.py`. The Correcteur never shows a mistake the learner has never made, except the three
«classiques» of their band (decision 5).

## 2. What exists today
- `episode_audio.speak_text(…)` synthesises a line in a character's voice with cost recording;
  `line_audio_clips` stores clips (WP-91); `useLineVoice`/`HeardLine` play them; `LISTEN_TAP` and
  `DICTATION` recall formats carry a clip and are graded (dictation: typed, case/punctuation folded).
- The week's dossiers: `weekly.available_for_week`; Romy's reply pipeline and the guest line in
  `encounter.py` (phase 2); the guest's authored defaults in `evergreen/guests/guest_lines.json`.
- Errors: `UserError` rows with occurrences and lapses; `journey_errata.rank_errata_targets` picks the
  day's errata; `grammar_map.py` knows the grammar points; `error_memory.erratum_repair_evidence`.
- The daily journey: `DayShape`s and `StepKind`s (WP-66); the planner validates a day's steps.

## 3. A · La Radio

### 3.1 The bulletin (`revue/radio.py`)
`bulletin_for(dossier, band) -> Bulletin{lines: [{speaker, text_fr, clip_url}], seconds, dictee: {line_index}}`:
Romy's lede (from `summary_fr`, trimmed to the band's reading target ÷ 2), three claims as spoken
sentences (facts as reports, interpretations with «d'après…»), one guest reaction (the authored line
for the dossier's topic, or the phase-2 guest line when a session exists), Romy's sign-off («C'était
Le Papier, semaine 41»). Each line through `speak_text` in the speaker's voice, cached per
`(dossier_id, band, line)` in `line_audio_clips` so a bulletin costs once per story per band. Target
45–60 s. The dictée line is the shortest fact.

### 3.2 The surface (`/radio`, own-shell; a chip on La Une «La Radio · 50 s» on non-Papier days)
Plate as the full-bleed stage with Romy (and the guest when they speak) drawn small, a single play
control (the 3D-press primary), a progress hairline. **Listen first**: the text is hidden until the
bulletin ends or the learner taps «Lire». Then the text appears line by line with tap-glosses, and the
dictée poses the chosen sentence with the existing `DICTATION` format. Evidence through the existing
listening policy. Daily cadence: one bulletin per dossier; the chip rotates through the week's
dossiers the learner has not heard; a learner who has heard all six gets the evergreen of the week.

### 3.3 Cost and flags
`REVUE_RADIO_ENABLED` (off). Per story per band: ~6 lines × ~15 words → under US$0.02 of TTS, once.

## 4. B · Le Correcteur

### 4.1 The draft (`revue/correcteur.py`)
`draft_for(user, dossier, band) -> Draft{text_fr, seeded: [{span, error_id, correct_fr, grammar_point}]}`:
Romy's three-line dispatch for the dossier (the phase-1 close builder without a session, or the
bulletin's lines), then **seeded errors**: 3 at A1–A2, 4 at B1+, drawn from the learner's
`rank_errata_targets` (their own recurring errors, applied to the text where the grammar point
occurs) plus up to three «classiques» of the band when the learner has fewer errors on file (agreement
of the past participle, article contraction, accents). Seeding is deterministic from the errata and
the text through `grammar_map` rules; a model call only to rewrite a sentence when a rule cannot apply
cleanly, then the Attribution/Anchor checks run again on the facts (a seeded error must never change a
fact). Private key: the seeded spans.

### 4.2 The surface (`/correcteur`, and a `correcteur` recall step the planner may deal)
The draft on paper, the learner taps a word or span they think is wrong; a tapped span opens a small
field «Corrige» (type or pick from three options at A1–A2). Grading: a tapped seeded span = noticed;
a correct fix = repaired (`erratum_repair_evidence`); an untouched seeded span = missed, shown after
«Bon à tirer»; a tapped correct span = a false alarm, shown kindly («celui-là était bon»). Romy's one
line at the end, authored by outcome. Evidence into the errata memory so the errors the learner now
notices stop being seeded.

### 4.3 Flags
`REVUE_CORRECTEUR_ENABLED` (off). Cost ≈ zero on most drafts.

## 5. Decisions (lead, 2026-10-03)
1. Radio: listen first, text hidden until the end. 2. One bulletin per dossier per band, cached.
3. Dictée on the shortest fact. 4. Correcteur: errors come from the learner's own errata first.
5. Three «classiques» per band fill the gap for new learners. 6. False alarms are shown, never penalised.
7. Both surfaces are own-shell pages plus a La Une chip; neither is a tab.

## 6. Phases and acceptance
| Phase | What lands | Done when |
|---|---|---|
| A | `radio.py`, caching, `/radio`, La Une chip, listen-first, dictée | a bulletin for an evergreen is 45–60 s with a fake TTS; the chip rotates; the dictée grades |
| B | `correcteur.py` seeding from errata + classiques with fact checks, `/correcteur`, grading, errata write-back | a learner with two recurring errors gets a draft seeded with them; a fix repairs; a seeded error never changes a claim (test) |
| Walk | E-3 `radio-then-dictee`, `correcteur-notices` | owner's hands-on |

## 7. Status
| Phase | Commit | What landed |
|---|---|---|
| — | — | defined 2026-10-03 |
