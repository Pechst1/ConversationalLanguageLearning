# Episode 1 — "Le radiateur" · Golden Reference

**Purpose:** a fully worked first episode the WP-2 (mission world-reply), WP-4 (feuilleton serial gen), and WP-5 (choice forks) agents build against. It demonstrates the full loop end-to-end: **act → world replies → state delta → see (dramatized) → cliffhanger → next act.** Treat the structures here as the target output of the generators, not as hardcoded content (except where noted as the fixed season opener).

World bible: `app/prompts/serial/world_bible_paris_v1.json`. This episode is the **season opener** and is the one episode that is allowed to be authored/fixed rather than fully generated, because it establishes the cast.

---

## Beat A — THE ACT (Mission) · "Reach the landlord"

`mission_type: "message"` · `stakes_level: 1` · register: **vous** (stranger / official)

**Brief (shown to learner):**
> Your first night in Paris. The radiator in your new studio is dead and the flat is freezing. Write a short message to your landlord, **M. Marchand**, to report the problem and get it fixed.

**Messenger (the world that replies):** `landlord_marchand` — gruff but fair, formal, busy. Replies in-fiction (this is WP-2's NPC reply).

**Objectives** (drive `objective_progress[].met`; flag namespace from world bible `initial_state`):
| id | label | maps to grammar/vocab |
|----|-------|----------------------|
| `intro_self` | Say who you are and that you just moved in | present tense, `emménager`, `l'appartement` |
| `describe_problem` | Describe the problem concretely (heating doesn't work) | `ne…pas`, `le radiateur`, `le chauffage`, `en panne` |
| `make_request` | Ask clearly when/if he can fix it | `pouvoir` + infinitive, `réparer` |
| `formal_register` | Address him correctly (vous, polite framing) | tu/vous, `pourriez-vous`, `je vous remercie` |

**Target vocabulary:** le radiateur · le chauffage · en panne · emménager · l'appartement · réparer · le propriétaire.

**World-reply branches (WP-2 — the reply is the payoff, score is under the hood):**
| Condition (objective_progress / branch_state) | M. Marchand's in-fiction reply | `state_delta.set` |
|---|---|---|
| All met, clear, formal (`score_0_4` ≥ 3) | "Bien reçu. J'envoie un plombier demain matin entre 8h et 10h. Bonne installation." | `{ "heating_fixed": "pending_tomorrow", "marchand_trust": "ok" }` |
| Vague / missing detail (`needs_detail`) | "Quel appartement ? Et c'est quoi exactement, le problème ? Soyez précis." | `{ "heating_fixed": false }` (no progress; re-prompt) |
| Tone mismatch (used `tu`) | "…On ne se connaît pas. Reformulez correctement, s'il vous plaît." | `{ "heating_fixed": false, "marchand_trust": "cold" }` |

**Hook emitted on completion (`resolve_hook`, WP-2):**
```json
{
  "text": "Tu raccroches. L'appartement est glacé, le silence total. Six étages plus bas, il y a de la lumière, du bruit, des rires — un café, encore ouvert.",
  "unresolved_question": "Who's down there, and what happens if you go in?",
  "next_beat_kind": "feuilleton",
  "teaser": "Tu n'as pas envie de rester seul ce soir."
}
```

---

## Beat B — THE SEE (Feuilleton episode) · "Le Mistral, minuit"

6 panels. **Reads `thread.state` from Beat A** (was the heating fixed? did Marchand go cold?). Ends on a **cliffhanger, not a recap.** Setting: the user's apartment → the café (this is the one episode that establishes Le Mistral; future episodes rotate per `location_rotation`). News device: Romy.

> **Panel 1 — The cold flat.** You in your coat, breath visible, phone glowing.
> *State-aware:* if `heating_fixed = "pending_tomorrow"`, Marchand's reply sits on screen ("plombier demain 8h"); if `false`, the screen shows only an unanswered message.
> **Caption (fr/en):** "Première nuit à Paris. Zéro chauffage, zéro contact." / "First night in Paris. No heat, no one."
> **Embedded task —** `cloze`: "Le radiateur est ______ (panne)." → `en panne`.

> **Panel 2 — Down into the rain → the café door.** You hesitate at the threshold of Le Mistral, warm light spilling out.
> **Embedded task —** `choice` **(WP-5 FORK):** How do you walk in?
> - A) "Bonsoir… vous auriez une table ?" *(timid vous)* → `branch_target.A`: `state_delta { "user.first_impression": "shy", "user.default_register": "vous" }`; next panel = the group gently teases the formality.
> - B) "Salut — c'est encore ouvert ?" *(warm tu)* → `branch_target.B`: `state_delta { "user.first_impression": "game", "user.knows_tu_switch": "learning" }`; next panel = Lila grins, "Enfin quelqu'un de normal."

> **Panel 3 — The booth.** Marin waves you over ("Eh, viens, mon grand, tu vas geler !"). Lila sizes you up; Gus mid-monologue; Margaux behind the zinc.
> **Embedded task —** `short_sentence`: Introduce yourself to the group (who you are, where you're from, that you just arrived). `expected_features: ["present tense", "emménager / arriver", "self-introduction"]`.

> **Panel 4 — The news on the TV.** Romy at the bar, half-watching her own segment on the screen — **the daily news seed enters here, through her report** (`news_integration`). She turns: "Voyons donc, ils comprennent rien à cette histoire."
> **Embedded task —** `cloze` or vocab, seeded from the day's `news_seed` topic.

> **Panel 5 — The warmth beat (the bond).** Margaux sets a hot drink in front of you without being asked: "La même chose que les autres." You have a booth now. The group has, without discussing it, absorbed you.
> **Caption:** "Tu ne sais pas leurs noms. Mais tu es déjà à leur table." / "You don't know their names yet. But you're already at their table."

> **Panel 6 — CLIFFHANGER (not recap).** Closing time. Coats on. Romy, last out the door, turns back to you with that journalist's look: **"Bon. C'est quoi la vraie histoire, toi ?"**
> **Final hook (written to the episode):**
> ```json
> {
>   "text": "La porte se referme. Demain le plombier viendra réparer le radiateur. Mais ce soir tu as une question plus urgente : comment revoir ces gens ?",
>   "unresolved_question": "How do you turn one accidental night into actual friends — and what was that look from Romy?",
>   "next_beat_kind": "mission",
>   "teaser": "Il te faut un prétexte. Et leurs numéros."
> }
> ```
> The vocabulary recap still renders, but **below** this card — it is no longer the last emotional beat.

---

## Beat C — THE NEXT ACT (seeded from the hook)

The hook's `next_beat_kind: "mission"` seeds Episode 2's Mission: **write a group message proposing to meet again** (`mission_type: "message"`, register **tu**, `stakes_level: 1→2`) — the inverse register lesson from Beat A. How warm/clear it lands sets `state.group_bond` and the next will-they-won't-they beat with Romy.

---

## What this golden sample proves (checklist for the agents)
- [x] **WP-2:** the Mission's payoff is an in-fiction **reply that branches on objectives**, not a bare score; it emits a `state_delta` + `hook`.
- [x] **WP-4:** the Feuilleton **reads prior state** (Panel 1 reflects the landlord outcome), routes **news through Romy** (Panel 4), and **ends on a cliffhanger** (Panel 6), recap demoted.
- [x] **WP-5:** Panel 2 is a real **choice fork** that writes state and changes the next panel.
- [x] **Loop closure:** the hook seeds the next act (Beat C), so the learner is pulled to "what happens next."
- [x] **Register as content:** Beat A teaches `vous` (landlord); Beat C teaches `tu` (friends) — the same skill from both sides.
