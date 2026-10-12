"""SP2 — can tomorrow honour today? The consequence contract, without a model.

The fixture is the research brief's illustrative scene, not Season 1 canon:
Romy asks to read Odile's letter; the learner may let her, refuse, or let her
with conditions ("but no photo", "keep the address private"). Every test is
deterministic and makes no paid call.
"""
from __future__ import annotations

import random

import pytest

from app.services.season.consequences import (
    Acknowledge,
    Clarify,
    Commit,
    EffectSpec,
    Evidence,
    Intent,
    Storylet,
    TransitionError,
    TurnContract,
    WorldState,
    apply,
    callback_source,
    decide,
    eligible,
    projected_flags,
    select,
)

ROMY = TurnContract(
    turn_id="fixture.romy_letter",
    speaker="romy",
    forbidden_facts=["odile_secret"],
    effects=[
        EffectSpec(
            id="romy_reads_letter",
            actions=["accept", "show"],
            subject="letter",
            allowed_conditions=["no_photo", "no_address"],
            discloses=["letter_contents"],
            alternative="Elle peut la lire ici, maintenant, mais pas l'emporter.",
        ),
        EffectSpec(id="romy_refused_letter", actions=["decline", "withhold"], subject="letter"),
        EffectSpec(
            id="romy_letter_terms_changed",
            actions=["revise"],
            subject="letter",
            allowed_conditions=["no_photo", "no_address"],
        ),
        EffectSpec(id="romy_secret", actions=["tell"], subject="secret", discloses=["odile_secret"]),
        EffectSpec(id="learner_promises_return", actions=["promise"], subject="return_tomorrow"),
    ],
)

MARIN = TurnContract(
    turn_id="fixture.marin_letter",
    speaker="marin",
    effects=[
        EffectSpec(
            id="marin_keeps_letter",
            actions=["accept", "show"],
            subject="letter",
            discloses=["letter_contents"],
        ),
        EffectSpec(id="marin_refused_letter", actions=["decline"], subject="letter"),
    ],
)

GAP = "fixture.gap1"
LIBRARY = [
    Storylet(
        id="romy_checks_notes",
        gap=GAP,
        when={"perm.letter.romy": "granted", "perm.letter.romy.no_photo": True},
        requires_known={"romy": ["letter_contents"]},
        cast=["romy"],
        salience=3,
        pays_off="romy_reads_letter",
    ),
    Storylet(
        id="romy_shows_photo",
        gap=GAP,
        when={"perm.letter.romy": "granted", "perm.letter.romy.no_photo": {"set": False}},
        cast=["romy"],
        salience=2,
    ),
    Storylet(id="marin_private_talk", gap=GAP, when={"perm.letter.romy": "refused"}, cast=["marin"], salience=2),
    Storylet(
        id="margaux_quotes_letter",
        gap=GAP,
        requires_known={"margaux": ["letter_contents"]},
        cast=["margaux"],
        salience=5,
    ),
    Storylet(id="repair_errand", gap=GAP, cast=["gus"]),
    Storylet(id="invitation", gap=GAP, cast=["margaux"]),
    Storylet(id="lila_conversation", gap=GAP, cast=["lila"]),
    Storylet(id="gap_continues", gap=GAP, fallback=True),
]


def _start() -> WorldState:
    return WorldState(known_by={"letter_contents": ["learner"], "odile_address": ["learner"]})


def _span(text: str, part: str) -> Evidence:
    start = text.index(part)
    return Evidence(text=part, start=start, end=start + len(part))


def _intent(text: str, action: str, *parts: str, **fields) -> Intent:  # type: ignore[no-untyped-def]
    return Intent(action=action, evidence=[_span(text, part) for part in parts or (text,)], **fields)


def _commit(
    state: WorldState, contract: TurnContract, text: str, intent: Intent, source: str
) -> WorldState:
    decision = decide(contract, intent, state, learner_text=text, source_turn=source)
    assert isinstance(decision, Commit), decision
    return apply(state, decision.event, expected_version=state.version, learner_text=text)


def _ids(rows: list[Storylet]) -> set[str]:
    return {row.id for row in rows}


# ---------------------------------------------------------------------------
# meaning changes the world; form does not
# ---------------------------------------------------------------------------


def test_opposite_meanings_make_different_worlds() -> None:
    yes_text = "Oui, tu peux lire la lettre."
    no_text = "Non, je préfère pas. Tu peux pas la lire."
    yes = _commit(_start(), ROMY, yes_text, _intent(yes_text, "accept", "tu peux lire la lettre", subject="letter"), "t1")
    no = _commit(_start(), ROMY, no_text, _intent(no_text, "decline", "Tu peux pas la lire", subject="letter"), "t1")

    assert projected_flags(yes)["perm.letter.romy"] == "granted"
    assert projected_flags(no)["perm.letter.romy"] == "refused"
    assert "romy" in yes.known_by["letter_contents"]
    assert "romy" not in no.known_by["letter_contents"]
    assert _ids(eligible(LIBRARY, yes, gap=GAP)) != _ids(eligible(LIBRARY, no, gap=GAP))
    assert "marin_private_talk" in _ids(eligible(LIBRARY, no, gap=GAP))


@pytest.mark.parametrize(
    "text, part",
    [
        ("Oui, tu peux lire la lettre, mais sans photo s'il te plaît.", "mais sans photo"),
        ("oui tu peu lir la letre mais pa de foto", "mais pa de foto"),
        ("D'accord. Pas de photo.", "Pas de photo"),
    ],
)
def test_the_same_meaning_in_any_french_makes_the_same_world(text: str, part: str) -> None:
    state = _commit(
        _start(), ROMY, text, _intent(text, "accept", part, subject="letter", conditions=["no_photo"]), "t1"
    )
    permission = state.permissions["letter>romy"]
    assert permission.granted is True
    assert permission.conditions == ["no_photo"]
    ids = _ids(eligible(LIBRARY, state, gap=GAP))
    assert "romy_checks_notes" in ids
    assert "romy_shows_photo" not in ids


def test_a_condition_the_scene_cannot_keep_is_not_dropped() -> None:
    text = "Oui, si elle me paie cent euros."
    intent = _intent(text, "accept", subject="letter", conditions=["paid"])
    decision = decide(ROMY, intent, _start(), learner_text=text, source_turn="t1")
    assert isinstance(decision, Acknowledge)
    assert decision.reason == "condition_unsupported"
    assert decision.alternative  # the character says what is possible instead


def test_ambiguity_asks_again_and_commits_nothing() -> None:
    text = "Euh… peut-être ?"
    decision = decide(ROMY, _intent(text, "accept", subject="letter", clarity="ambiguous"), _start(), learner_text=text, source_turn="t1")
    assert isinstance(decision, Clarify)
    decision = decide(ROMY, _intent(text, "ask", clarity="unsupported"), _start(), learner_text=text, source_turn="t1")
    assert isinstance(decision, Acknowledge)


def test_evidence_must_be_the_learners_own_words() -> None:
    text = "Oui."
    invented = Intent(action="accept", subject="letter", evidence=[Evidence(text="Oui, bien sûr", start=0, end=13)])
    assert isinstance(decide(ROMY, invented, _start(), learner_text=text, source_turn="t1"), Clarify)

    good = decide(ROMY, _intent(text, "accept", subject="letter"), _start(), learner_text=text, source_turn="t1")
    assert isinstance(good, Commit)
    doctored = good.event.model_copy(update={"evidence": [Evidence(text="Oui, tout", start=0, end=9)]})
    with pytest.raises(TransitionError) as caught:
        apply(_start(), doctored, expected_version=0, learner_text=text)
    assert caught.value.code == "no_evidence"


def test_a_secret_cannot_be_told_from_a_scene_that_forbids_it() -> None:
    text = "Je sais le secret d'Odile."
    decision = decide(ROMY, _intent(text, "tell", subject="secret"), _start(), learner_text=text, source_turn="t1")
    assert isinstance(decision, Acknowledge)
    assert decision.reason == "forbidden_fact"


# ---------------------------------------------------------------------------
# committed is committed
# ---------------------------------------------------------------------------


def test_a_double_submission_settles_once() -> None:
    text = "Oui, lis-la."
    state = _start()
    decision = decide(ROMY, _intent(text, "accept", subject="letter"), state, learner_text=text, source_turn="t1")
    assert isinstance(decision, Commit)
    once = apply(state, decision.event, expected_version=0, learner_text=text)
    twice = apply(once, decision.event, expected_version=0, learner_text=text)  # the retry after a crash
    assert twice == once
    assert len(twice.events) == 1 and twice.version == 1


def test_a_stale_version_and_a_conflicting_replay_are_refused() -> None:
    text = "Oui, lis-la."
    first = decide(ROMY, _intent(text, "accept", subject="letter"), _start(), learner_text=text, source_turn="t1")
    state = apply(_start(), first.event, expected_version=0, learner_text=text)

    late_text = "Non."
    late = decide(ROMY, _intent(late_text, "decline", subject="letter"), _start(), learner_text=late_text, source_turn="t2")
    with pytest.raises(TransitionError) as caught:
        apply(state, late.event, expected_version=0, learner_text=late_text)  # built against version 0
    assert caught.value.code == "stale_version"

    same_turn = decide(ROMY, _intent(late_text, "decline", subject="letter"), _start(), learner_text=late_text, source_turn="t1")
    with pytest.raises(TransitionError) as caught:
        apply(state, same_turn.event, expected_version=1, learner_text=late_text)
    assert caught.value.code == "conflicting_replay"


def test_revising_terms_keeps_what_was_already_seen() -> None:
    text = "Oui, tu peux la lire."
    state = _commit(_start(), ROMY, text, _intent(text, "accept", subject="letter"), "t1")
    assert "romy_shows_photo" in _ids(eligible(LIBRARY, state, gap=GAP))

    later = "Finalement, pas de photo, d'accord ?"
    state = _commit(state, ROMY, later, _intent(later, "revise", "pas de photo", subject="letter", conditions=["no_photo"]), "t2")
    assert state.permissions["letter>romy"].conditions == ["no_photo"]
    assert state.permissions["letter>romy"].granted is True
    assert "romy" in state.known_by["letter_contents"]  # she already read it
    assert "romy_shows_photo" not in _ids(eligible(LIBRARY, state, gap=GAP))


def test_nothing_to_revise_is_not_invented() -> None:
    text = "Pas de photo."
    decision = decide(ROMY, _intent(text, "revise", subject="letter", conditions=["no_photo"]), _start(), learner_text=text, source_turn="t1")
    assert isinstance(decision, Acknowledge)
    assert decision.reason == "nothing_to_revise"


def test_the_learner_cannot_pass_on_what_they_do_not_know() -> None:
    text = "Tiens, lis."
    decision = decide(ROMY, _intent(text, "show", subject="letter"), WorldState(), learner_text=text, source_turn="t1")
    assert isinstance(decision, Commit)
    with pytest.raises(TransitionError) as caught:
        apply(WorldState(), decision.event, expected_version=0, learner_text=text)
    assert caught.value.code == "unknown_fact"


def test_margaux_cannot_quote_a_letter_only_marin_was_given() -> None:
    text = "Garde la lettre, Marin."
    state = _commit(_start(), MARIN, text, _intent(text, "show", subject="letter"), "t1")
    assert "marin" in state.known_by["letter_contents"]
    assert "margaux_quotes_letter" not in _ids(eligible(LIBRARY, state, gap=GAP))


# ---------------------------------------------------------------------------
# dealing the next scene
# ---------------------------------------------------------------------------


def test_a_due_callback_is_dealt_whatever_the_seed_and_cites_its_event() -> None:
    text = "Oui, mais pas de photo."
    state = _commit(_start(), ROMY, text, _intent(text, "accept", "pas de photo", subject="letter", conditions=["no_photo"]), "t1")
    for seed in ("a", "b", "c", "d"):
        chosen, _ = select(LIBRARY, state, gap=GAP, slot="day2", seed=seed)
        assert chosen.id == "romy_checks_notes"
    source = callback_source(chosen, state)
    assert source is not None and source.evidence[0].text == "pas de photo"


def test_a_dealt_slot_is_read_back_not_rerolled() -> None:
    state = _start()
    first, state = select(LIBRARY, state, gap=GAP, slot="day2", seed="s1")
    again, same = select(LIBRARY, state, gap=GAP, slot="day2", seed="another-device")
    assert again.id == first.id
    assert same is state


def test_different_seeds_deal_different_orders() -> None:
    orders = set()
    for run in range(20):
        state = _start()
        order = []
        for day in range(3):
            chosen, state = select(LIBRARY, state, gap=GAP, slot=f"day{day}", seed=f"learner-{run}")
            order.append(chosen.id)
        orders.add(tuple(order))
    assert len(orders) >= 3


def test_with_nothing_eligible_the_fallback_plays() -> None:
    state = _start().model_copy(update={"played": ["repair_errand", "invitation", "lila_conversation"]})
    chosen, _ = select(LIBRARY, state, gap=GAP, slot="day4", seed="x")
    assert chosen.id == "gap_continues"
    with pytest.raises(TransitionError) as caught:
        select([row for row in LIBRARY if not row.fallback], state, gap=GAP, slot="day4", seed="x")
    assert caught.value.code == "dead_end"


# ---------------------------------------------------------------------------
# 1,000 synthetic transitions: no illegal state, ever
# ---------------------------------------------------------------------------

_UTTERANCES = [
    (ROMY, "accept", "Oui, tu peux lire la lettre.", {"subject": "letter"}),
    (ROMY, "accept", "Oui, mais sans photo.", {"subject": "letter", "conditions": ["no_photo"]}),
    (ROMY, "accept", "Oui, sans photo et sans l'adresse.", {"subject": "letter", "conditions": ["no_address", "no_photo"]}),
    (ROMY, "accept", "Oui si tu me paies.", {"subject": "letter", "conditions": ["paid"]}),
    (ROMY, "decline", "Non, pas la lettre.", {"subject": "letter"}),
    (ROMY, "withhold", "Je la garde pour moi.", {"subject": "letter"}),
    (ROMY, "revise", "Finalement, pas de photo.", {"subject": "letter", "conditions": ["no_photo"]}),
    (ROMY, "tell", "Le secret, c'est…", {"subject": "secret"}),
    (ROMY, "promise", "Je reviens demain.", {"subject": "return_tomorrow"}),
    (ROMY, "accept", "Hmm, je sais pas.", {"subject": "letter", "clarity": "ambiguous"}),
    (ROMY, "propose", "On commande un café ?", {"subject": "coffee"}),
    (MARIN, "show", "Garde-la, Marin.", {"subject": "letter"}),
    (MARIN, "decline", "Non Marin.", {"subject": "letter"}),
]


def _check_invariants(state: WorldState, texts: dict[str, str], dealt: dict[str, str]) -> None:
    ids = [row.event_id for row in state.events]
    assert len(ids) == len(set(ids)), "duplicate settlement"
    assert state.version == len(state.events)
    for row in state.events:
        text = texts[row.source_turn]
        assert all(text[e.start : e.end] == e.text for e in row.evidence)
    for key, permission in state.permissions.items():
        source = state.event(permission.event_id)
        assert source is not None
        if permission.granted:
            # Granted only by an accept/show, or a revision of a standing grant.
            assert source.action in {"accept", "show", "revise"}
            if source.action != "revise":
                assert key == f"{source.subject}>{source.recipient}"
        else:
            assert source.action in {"decline", "withhold", "revise"}
        assert "paid" not in permission.conditions
    for fact, knowers in state.known_by.items():
        for who in knowers:
            if who == "learner":
                continue
            assert any(row.recipient == who and fact in row.discloses for row in state.events), (fact, who)
    assert "odile_secret" not in state.known_by
    assert "margaux" not in state.known_by.get("letter_contents", [])
    for slot, storylet_id in dealt.items():
        assert state.selections[slot].storylet_id == storylet_id, "a dealt slot was rerolled"


def test_a_thousand_synthetic_transitions_never_reach_an_illegal_state() -> None:
    rng = random.Random(20261012)
    transitions = 0
    refused = {"clarify": 0, "acknowledge": 0, "stale": 0, "replay": 0}
    while transitions < 1000:
        state = _start()
        texts: dict[str, str] = {}
        dealt: dict[str, str] = {}
        for step in range(rng.randint(3, 12)):
            transitions += 1
            contract, action, text, fields = rng.choice(_UTTERANCES)
            source = f"turn{step}"
            texts[source] = text
            intent = _intent(text, action, **fields)
            decision = decide(contract, intent, state, learner_text=text, source_turn=source)
            if not isinstance(decision, Commit):
                refused[decision.kind] += 1
            else:
                built_at = state.version
                if rng.random() < 0.15:
                    # Another lane commits a different turn at the same version first.
                    o_contract, o_action, o_text, o_fields = rng.choice(_UTTERANCES)
                    o_source = f"lane{step}"
                    texts[o_source] = o_text
                    other = decide(o_contract, _intent(o_text, o_action, **o_fields), state, learner_text=o_text, source_turn=o_source)
                    if isinstance(other, Commit):
                        state = apply(state, other.event, expected_version=built_at, learner_text=o_text)
                try:
                    state = apply(state, decision.event, expected_version=built_at, learner_text=text)
                except TransitionError as exc:
                    assert exc.code == "stale_version"
                    refused["stale"] += 1
                if state.event(decision.event.event_id) and rng.random() < 0.3:
                    # The response was lost after the commit; the client sends it again.
                    assert apply(state, decision.event, expected_version=built_at, learner_text=text) == state
                    refused["replay"] += 1
            if rng.random() < 0.4:
                slot = f"slot{len(dealt)}"
                chosen, state = select(LIBRARY, state, gap=GAP, slot=slot, seed=f"seed{transitions}")
                dealt[slot] = chosen.id
                again, _ = select(LIBRARY, state, gap=GAP, slot=slot, seed="reload")
                assert again.id == chosen.id
                if chosen.id == "romy_checks_notes":
                    assert state.permissions["letter>romy"].granted
                    assert "no_photo" in state.permissions["letter>romy"].conditions
                if chosen.id == "romy_shows_photo":
                    assert "no_photo" not in state.permissions["letter>romy"].conditions
            _check_invariants(state, texts, dealt)
    assert transitions >= 1000
    # The walk exercised every refusal path, not only the happy one.
    assert all(count > 0 for count in refused.values()), refused
