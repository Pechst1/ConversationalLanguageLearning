"""Night shift #378 (child of #145), rework of #703: how a scene closes, and where the
margin's correction sits in the learner's sentence.

1. #378, live walk 30 Oct: Lila answered the one reply the scene took with «« Deux », oui,
   je le note dans ma tête. Et ce restaurant te fait peur ?», and the scene closed under
   that question. The learner could never answer it.
2. Review of #703: a margin correction names the learner's words by their text alone. Every
   surface that shows or applies it finds them by their first match (the thread's
   strike-through ``markSpan``, the drill's saved sentence, the settle check in
   ``verify_edit``). The common A1 fix «a» → «à» was accepted with the span «a» while the
   reply also had the verb «a» earlier («Il a peur et il va a Paris.»), so the verb was
   the word marked and made «à», and the real slip stayed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.verdict import span_pattern
from app.services import correction_contract, spoken_reply
from app.services.season import runtime
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import resolve_day
from app.services.season.runtime import (
    SEASON_CONTEXT_KEY,
    evaluate_tentpole_turn,
    page_tail,
    projected_turns,
)

FIRST = "Non, je ne suis pas en colère. Je comprends."
LAST_REPLY = (
    "Oui, un peu. Tu as menti pendant trois ans a ma grand-mere. Mais je veux comprendre pourquoi tu as fait ca."
)


@pytest.fixture
def offline(monkeypatch):
    real = runtime.classify

    def classify(db, user, **kwargs):
        kwargs["use_model"] = False
        return real(db, user, **kwargs)

    monkeypatch.setattr(runtime, "classify", classify)
    import app.services.living_story as engine
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    monkeypatch.setattr(spoken_reply.settings, "ATELIER_SPOKEN_REPLY_ENABLED", True)
    runtime._ROUTE_CACHE.clear()
    yield


def _le_mistral():
    """T4 day B as the walk of 6 Nov had it: the letter trusted to Margaux, at A1."""

    season = load_season("s1")
    flags = effective_flags(season, {"s1.letter_trusted_to": "margaux"}, seed="x")
    page = resolve_day(season, "t4", "b", flags=flags, band="A1", language="en")
    turns = projected_turns(page)
    scenario = SimpleNamespace(
        story_context={
            "scene_id": "walk-378",
            SEASON_CONTEXT_KEY: {
                "id": "s1",
                "kind": "tentpole",
                "page": page,
                "turns": turns,
                "tail": page_tail(page),
                "ending": {},
                "position": {"key": "t4:b"},
            },
        },
        character_id="augustin_de_roncourt",
        title_fr=page["title_fr"],
    )
    return scenario, turns


def _say(scenario, text, history, turn_index, planned):
    evaluation = evaluate_tentpole_turn(
        None,
        user=None,
        scenario=scenario,
        task=SimpleNamespace(max_turns=planned),
        answer=SimpleNamespace(text=text, is_blank=False),
        turn_index=turn_index,
        assistance="none",
        history=history,
    )
    history.append(
        {
            "learner": text,
            "character": evaluation.character_reply_fr,
            "free": bool(evaluation.needs_repair and not evaluation.turn_consumed),
            **({"route": dict(evaluation.route)} if evaluation.route else {}),
        }
    )
    return evaluation


WALK_ACK = "« Deux », oui, je le note dans ma tête. Et ce restaurant te fait peur ?"


def _with_ack(monkeypatch, ack):
    offline_classify = runtime.classify

    def classify(db, user, **kwargs):
        return offline_classify(db, user, **kwargs).model_copy(update={"ack_fr": ack})

    monkeypatch.setattr(runtime, "classify", classify)


def test_the_closing_reaction_never_ends_on_a_question_the_scene_cannot_take(offline, monkeypatch):
    """#378: on the exchange the conversation closes on, the reaction keeps what it says and
    drops what it asks. Mid-scene the question stays: the next exchange takes the answer."""

    _with_ack(monkeypatch, WALK_ACK)
    scenario, _turns = _le_mistral()
    history: list[dict] = []
    first = _say(scenario, FIRST, history, 0, planned=2)
    assert "te fait peur ?" in first.character_reply_fr
    closing = _say(scenario, LAST_REPLY, history, 1, planned=2)
    assert closing.needs_repair is False
    said = closing.character_reply_fr
    assert "te fait peur" not in said, f"the scene closes under a question it cannot take: {said!r}"
    assert "je le note dans ma tête" in said, said
    asked = [line["text_fr"] for line in closing.reply_lines if line["text_fr"].rstrip(" »\"").endswith("?")]
    assert not asked, asked


def test_a_closing_reaction_that_only_asks_is_not_said(offline, monkeypatch):
    _with_ack(monkeypatch, "Et ce restaurant te fait peur ?")
    scenario, _turns = _le_mistral()
    history: list[dict] = []
    _say(scenario, FIRST, history, 0, planned=2)
    closing = _say(scenario, LAST_REPLY, history, 1, planned=2)
    assert "restaurant" not in closing.character_reply_fr, closing.character_reply_fr
    assert closing.character_reply_fr.strip(), "the page's own reaction still plays"


# ---------------------------------------------------------------------------
# The margin's correction sits where it corrects
# ---------------------------------------------------------------------------


def _made_right_where_marked(said: str, span: str | None, fixed: str | None) -> str:
    """The learner's sentence with the margin's fix put where the surfaces put it: a
    correction keeps no offsets, so its span is found by the first place its words stand
    (``span_pattern``: the thread's strike-through, the drill's saved sentence). A span
    whose words also stand earlier is marked and fixed at the wrong word."""

    if not span or not fixed:
        return said
    found = span_pattern(span).search(said)
    assert found is not None, f"the span {span!r} is not in {said!r}"
    return said[: found.start()] + fixed + said[found.end() :]


@pytest.mark.parametrize(
    ("said", "span", "fixed", "expected"),
    [
        # Review of #673: a span found inside another word («reste», «pars»).
        ("Je reste ici, tu est gentil.", "est", "es", "Je reste ici, tu es gentil."),
        ("Je pars a Paris demain.", "a", "à", "Je pars à Paris demain."),
        ("Je vais a la gare.", "a", "à", "Je vais à la gare."),
        ("Elle mange une pomme et il parle a sa mere.", "a", "à", "Elle mange une pomme et il parle à sa mere."),
        # Review of #703: the verb «a» of a subject before the slip.
        ("Il a peur et il va a Paris.", "a", "à", "Il a peur et il va à Paris."),
        ("Elle a une soeur qui va a Lyon.", "a", "à", "Elle a une soeur qui va à Lyon."),
        ("Marin a un chat et il va a la gare.", "a", "à", "Marin a un chat et il va à la gare."),
        ("Lila a raison, je vais a Lyon.", "a", "à", "Lila a raison, je vais à Lyon."),
    ],
)
def test_a_margin_correction_is_applied_only_at_the_occurrence_it_corrects(said, span, fixed, expected):
    shown_span, shown_fix, _note = correction_contract.first_valid_edit(said, span, fixed, None, language="en")
    assert _made_right_where_marked(said, shown_span, shown_fix) == expected, (shown_span, shown_fix)


@pytest.mark.parametrize(
    "said",
    ["Il a peur.", "Marin a un chat.", "Lila a raison.", "Ce restaurant est loin et il est fermé."],
)
def test_the_verb_of_a_subject_before_it_is_never_corrected_into_a_preposition(said):
    """«a»/«est» right after its subject is the verb: «à»/«et» there is no fix."""

    word = "a" if " a " in said else "est"
    fixed = "à" if word == "a" else "et"
    verdict = correction_contract.verify_edit(said, word, fixed)
    assert not verdict.ok, verdict


def test_when_no_occurrence_can_be_singled_out_the_span_is_not_applied():
    """Both «a» could be the slip; neither is the verb of a subject. The model's span is not
    shown; the model-free pass decides, and names its own words once."""

    said = "Je pense a toi et a elle."
    span, fixed, _note = correction_contract.first_valid_edit(said, "a", "à", None, language="en")
    if span is not None:
        assert span_pattern(span).search(said).start() == said.find(span), span


def test_a_journal_erratum_names_its_words_once():
    """``verify_erratum`` (the Journal, the Courrier) shows the span the check settled."""

    said = "Il a peur et il va a Paris."
    item = correction_contract.verify_erratum(said, {"learner_text": "a", "corrected_target": "à", "why_wrong": ""})
    assert item is not None
    assert _made_right_where_marked(said, item["learner_text"], item["corrected_target"]) == "Il a peur et il va à Paris."
