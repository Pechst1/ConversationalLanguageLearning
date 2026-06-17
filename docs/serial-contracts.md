# Serial Contracts

These contracts are the frozen JSON boundary for the Serial World spine.

## `world_bible` (stable, author-seeded)

```json
{
  "logline": "A newcomer settles into the fictional town of Saint-Renan.",
  "setting": { "town": "Saint-Renan", "era": "present day", "tone": "warm, wry" },
  "protagonist": { "name": "Toi", "situation": "just arrived, renting an apartment" },
  "cast": [
    {
      "id": "landlord_marchand",
      "name": "M. Marchand",
      "role": "landlord",
      "register": "formal (vous)",
      "personality": "gruff but fair",
      "speech_pattern": "short, businesslike"
    }
  ],
  "register_map": { "landlord_marchand": "vous", "neighbor_lea": "tu" }
}
```

## `state` (mutable flags, the memory of the world)

Flat dict of namespaced booleans/short strings. Vocabulary is open but namespaced by topic; episodes read it, missions write deltas to it.

```json
{ "heating_fixed": false, "marchand_trust": "neutral", "has_met_neighbor": false }
```

## `state_delta` (what a completed Mission / choice-task emits)

```json
{
  "set": { "heating_fixed": true, "marchand_trust": "warmer" },
  "reason": "Learner's message was clear and hit all objectives.",
  "source": { "type": "mission", "id": "<uuid>", "score_0_4": 3.5 }
}
```

## `hook` (cliffhanger an episode ends on; lifted from `Chapter.cliffhanger`)

```json
{
  "text": "On rentre, et il y a une enveloppe glissée sous la porte.",
  "unresolved_question": "Who left the envelope, and what does it want?",
  "next_beat_kind": "mission",
  "teaser": "Demain : il faut répondre."
}
```

## `episode` envelope (what `GET /serial/today` returns for the current installment)

```json
{
  "thread_id": "<uuid>",
  "episode_index": 3,
  "kind": "mission",
  "mission_id": "<uuid|null>",
  "scene_id": "<uuid|null>",
  "hook_from_previous": {},
  "status": "available"
}
```
