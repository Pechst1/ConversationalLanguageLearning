"""What a character says when no model could write the reply (#518, root cause #145).

Live walk 4 Nov 2026. The learner wrote «Mon voisin a un dinosaure dans le jardin. Il mange la
lettre !» and got «Attends, on m'appelle — je reviens vers toi très vite, promis.», then
«Margaux doit partir avant de répondre … your words are noted». One failed call ended the
scene, in the same words for everyone.

Fake provider only: nothing is spent.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.models.daily_journey import DailyJourneyStep
from app.services import gold_ledger, lane_guards, scene_exit, scene_ledger
from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services.closing_filler import what_happened
from app.services.daily_journey import previous_outcome_of
from app.services.journal import scene_facts_for
from app.services.season.prose_detector import reply_hits
from tests import test_wp87_lanes as wp87
from tests.test_journal_kept_facts_622 import _journey as kept_facts_journey
from tests.test_living_story import driver
from tests.test_wp87_lanes import ANSWER, _resolution, _respond, _to_respond

assembled_client = wp87.assembled_client
clock = wp87.clock
inline = wp87.inline
journey_enabled = wp87.journey_enabled
provider = wp87.provider

WALK = "Mon voisin a un dinosaure dans le jardin. Il mange la lettre !"
#: What the old exit said, whoever spoke.
OLD_EXIT = ("appelle", "partir", "promis", "reviens")

REPLIES = {
    "no": "Non, je ne veux pas vendre.",
    "yes": "Oui, d'accord.",
    "question": "Pourquoi tu dis ça ?",
    "other": WALK,
}
ALL_LINES = [
    *[line for rows in scene_exit._REACTIONS.values() for lines in rows.values() for line in lines],
    *[line for rows in scene_exit._ENDINGS.values() for line in rows.values()],
]


@pytest.mark.parametrize("register", ["tu", "vous"])
@pytest.mark.parametrize("person", ["margaux", "augustin_de_roncourt", "lila", "camille"])
def test_the_walks_reply_gets_a_reaction_not_the_stock_exit(person, register):
    line = scene_exit.reaction(character_id=person, learner_text=WALK, register=register)
    assert not any(word in line.casefold() for word in OLD_EXIT)
    assert line.split(" ", 1)[1] in scene_exit._REACTIONS["other"][register]


@pytest.mark.parametrize(("intent", "reply"), REPLIES.items())
@pytest.mark.parametrize("register", ["tu", "vous"])
def test_the_reaction_follows_what_kind_of_thing_was_said(intent, reply, register):
    line = scene_exit.reaction(character_id="margaux", learner_text=reply, register=register)
    assert line.split(" ", 1)[1] in scene_exit._REACTIONS[intent][register]
    closing = scene_exit.ending(learner_text=reply, register=register)
    assert closing == scene_exit._ENDINGS[intent][register]


@pytest.mark.parametrize("line", ALL_LINES)
def test_no_line_asks_anything_the_scene_would_then_wait_for(line):
    """The ledger holds a question as the character's own, and the next page is captioned
    with it. «Non ? D'accord.» would have been one."""

    assert "?" not in line
    ledger = scene_ledger.build(opening_line_fr="Tu viens ?", history=[{"learner": "Non.", "character": line}])
    assert [row["text_fr"] for row in ledger["asked"]] == ["Tu viens ?"]
    assert not scene_ledger.keeps_open_for(line, turn_index=0, max_turns=1)


@pytest.mark.parametrize("line", ALL_LINES)
def test_no_line_says_a_gender_or_reads_as_what_a_page_is_refused_for(line):
    lane_guards.check_agreement([line], "neutral", own=frozenset())
    assert reply_hits(line) == []
    assert lane_guards.ending_voice_issue(line, "", "Margaux") is None


@pytest.mark.parametrize(
    ("register", "other"),
    [
        ("tu", {"vous", "votre", "laissez-moi", "attendez", "continuez"}),
        ("vous", {"tu", "ton", "ta", "te", "t'écoute", "t'as", "m'as", "laisse-moi", "attends", "continue"}),
    ],
)
def test_each_line_keeps_to_its_register(register, other):
    lines = [
        *[line for rows in scene_exit._REACTIONS.values() for line in rows[register]],
        *[rows[register] for rows in scene_exit._ENDINGS.values()],
    ]
    for line in lines:
        assert not other & set(line.casefold().replace(",", " ").replace(".", " ").split()), line


def test_a_person_keeps_their_own_opener_and_the_same_reply_reads_the_same():
    first = scene_exit.reaction(character_id="margaux", learner_text=WALK, register="tu")
    assert first == scene_exit.reaction(character_id="margaux", learner_text=WALK, register="tu"), "a retry reads the same"
    openers = {
        scene_exit.reaction(character_id="margaux", learner_text=text, register="tu").split(" ", 1)[0]
        for text in (*REPLIES.values(), "Je reste ici.", "Il pleut.")
    }
    assert len(openers) == 1
    many = {
        scene_exit.reaction(character_id=person, learner_text=WALK, register="tu").split(" ", 1)[0]
        for person in ("margaux", "lila", "camille", "augustin_de_roncourt", "romy", "marin")
    }
    assert len(many) > 1, "not one line for everyone"


@pytest.mark.parametrize(
    ("reply", "clean", "quoted"),
    [
        (WALK, True, True),
        (WALK, False, False),  # the margin corrected something
        ("Je pense a ma grand-mere parce que lappartement est vide.", True, False),  # misspelled
        ("Oui.", True, False),  # nothing to quote
        (" ".join(["Je reste ici avec toi"] * 4) + ".", True, False),  # left out, never cut
    ],
)
def test_the_closing_line_quotes_a_reply_only_whole_and_only_when_it_needed_nothing(reply, clean, quoted):
    line = scene_exit.ending(learner_text=reply, register="tu", clean=clean)
    assert (reply in line) is quoted
    assert ("«" in line) is quoted
    assert line.endswith("On en reparle.")


def test_an_authored_ending_is_not_what_happened():
    written = SimpleNamespace(callback_fr="", resolution_fr="Margaux range la lettre.", authored_ending=False)
    authored = SimpleNamespace(callback_fr="", resolution_fr="Ce que tu m'as dit, je le garde.", authored_ending=True)
    assert what_happened(written) == "Margaux range la lettre."
    assert what_happened(authored) == ""
    assert what_happened(authored, fallback="Une lettre pour Margaux") == "Une lettre pour Margaux"


def test_the_mark_stays_out_of_what_the_model_is_asked_for():
    assert "authored_ending" not in str(engine.SemanticTurn.model_json_schema())
    turn = engine.fallback_turn(character_name="Lila", learner_text=WALK, language="en", reason="x")
    assert turn.authored_ending and "authored_ending" not in turn.model_dump(mode="json"), "nor shown to a critic"


def test_the_person_is_named_by_the_registry_in_the_summary():
    turn = engine.fallback_turn(
        character_name="M. Marchand", character_id="landlord_marchand", learner_text=WALK, language="en", reason="x"
    )
    assert turn.summary_native == "M. Marchand heard what you said. The rest stays open."
    assert not turn.callback_fr and turn.authored_ending


# ---------------------------------------------------------------------------
# Through the real respond route, with the model down
# ---------------------------------------------------------------------------


def _respond_step(db, d) -> DailyJourneyStep:
    db.expire_all()
    return db.scalars(
        select(DailyJourneyStep).where(
            DailyJourneyStep.journey_id == UUID(d.journey["id"]), DailyJourneyStep.kind == "respond"
        )
    ).one()


def _live(db, d) -> dict:
    return engine._active_thread(db, SimpleNamespace(id=d.user_id)).state["living_story"]


def test_a_failed_reply_keeps_the_scene_open_and_the_next_reply_is_written_again(
    assembled_client, db_session, journey_enabled, clock, provider, inline
):
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    provider.fail = {"VoiceReply"}
    first = _respond(assembled_client, d, step, text=WALK)[2].json()
    assert first["reply_source"] == "authored"
    assert not any(word in first["character_reply_fr"].casefold() for word in OLD_EXIT)
    assert first["next_turn"] is not None, "one failed call does not end the scene"
    assert not _resolution(d.journey)["prompt"].get("character_line_fr")

    provider.fail = set()
    second = _respond(assembled_client, d, step, text=ANSWER)[2].json()
    assert second["reply_source"] == "model"
    turns = _respond_step(db_session, d).private_task["turns"]
    assert turns[0]["stock_exit"] is True and "stock_exit" not in turns[1]
    assert turns[0]["learner"] == WALK, "their words are kept"


def test_a_reply_after_a_failed_one_is_no_repair_of_it(
    assembled_client, db_session, journey_enabled, clock, provider, inline, monkeypatch
):
    """Read from the code by the Judgement truth session, 9 Nov. The exit stores an outcome
    nobody judged, and a scene used to end on it. Now that it stays open, the next reply read
    that outcome as a miss and could be paid as its repair."""

    pay = []
    monkeypatch.setattr(gold_ledger, "record_journey_reply", lambda *_args, **kwargs: pay.append(kwargs))
    d = driver(assembled_client, db_session)
    step = _to_respond(d)

    assert _respond(assembled_client, d, step, text=ANSWER)[2].status_code == 200
    provider.fail = {"VoiceReply"}
    assert _respond(assembled_client, d, step, text=WALK)[2].json()["next_turn"] is not None
    provider.fail = set()
    assert _respond(assembled_client, d, step, text=ANSWER)[2].status_code == 200

    assert [call["previous_outcome"] is None for call in pay] == [True, False, True]
    assert _respond_step(db_session, d).private_task["turns"][1]["stock_exit"] is True


@pytest.mark.parametrize("mark", [{"stock_exit": True}, {"check_failure": "TimeoutError: read timed out"}])
def test_an_exchange_nobody_judged_has_no_previous_outcome(mark):
    private = {"result": {"outcome": "partially_met"}}
    assert previous_outcome_of(private, [{"learner": "Bonjour."}]) == "partially_met"
    assert previous_outcome_of(private, [{"learner": "Bonjour."}, {"learner": "Oui.", **mark}]) is None
    assert previous_outcome_of(private, []) is None


def test_a_failed_last_reply_closes_on_the_characters_own_words_and_files_no_event(
    assembled_client, db_session, journey_enabled, clock, provider, inline, monkeypatch
):
    monkeypatch.setattr(engine, "keeps_talking", lambda *a, **k: False)
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    provider.fail = {"TutorVerdict", "VoiceReply"}
    result = _respond(assembled_client, d, step, text=WALK)[2].json()
    assert result["reply_source"] == "authored" and result["next_turn"] is None
    d.advance()
    shown = _resolution(d.journey)["prompt"]
    assert shown["character_line_fr"].endswith("je le garde. On en reparle.")
    assert WALK not in shown["character_line_fr"], "nothing read this reply, so it is not quoted"
    assert not any(word in shown["summary_native"].casefold() for word in ("called away", "weggerufen", "appelé"))

    live = _live(db_session, d)
    stored = [str(event.get("summary_fr") or "") + str(event.get("callback_fr") or "") for event in live["events"]]
    assert stored and not any("je le garde" in row for row in stored), "it is not what happened"


def test_a_failed_story_lane_closes_on_the_characters_own_words_around_the_shown_reply(
    assembled_client, db_session, journey_enabled, clock, provider, inline, monkeypatch
):
    monkeypatch.setattr(engine, "keeps_talking", lambda *a, **k: False)
    provider.story = {"resolution_fr": "", "summary_native": ""}
    d = driver(assembled_client, db_session)
    result = _respond(assembled_client, d, _to_respond(d))[2].json()
    assert result["reply_source"] == "model"
    assert inline == ["fallback"]
    d.advance()
    shown = _resolution(d.journey)["prompt"]
    assert ANSWER in shown["character_line_fr"], "the tutor read it and corrected nothing"
    assert shown["character_line_fr"].endswith("On en reparle.")
    live = _live(db_session, d)
    assert not any("On en reparle" in str(event.get("summary_fr")) for event in live["events"])
    assert not any("On en reparle" in str(row) for row in live.get("chronicle") or [])


def test_a_corrected_reply_is_not_quoted_on_the_closing_line():
    lane = {
        "tutor": lanes.TutorVerdict(
            outcome="partially_met",
            evidence_quotes=[],
            correction_span_fr="la canapé",
            correction_fr="le canapé",
            correction_note_native="le canapé is masculine",
        ).model_dump(mode="json"),
        "voice": lanes.VoiceReply(reply_fr="D'accord.", understood_intent="x", needs_clarification=False).model_dump(mode="json"),
        "learner_text": "Je garde la canapé rouge.",
    }
    turn = lanes.fallback_story(lane, character_name="Marin", language="en", reason="x", register="tu")
    assert "canapé" not in turn.resolution_fr
    assert turn.authored_ending and not turn.callback_fr and turn.reply_fr == "D'accord."


def test_the_journal_does_not_count_a_reply_no_model_wrote():
    line = scene_exit.reaction(character_id="margaux", learner_text=WALK, register="tu")
    turns = [{"learner": WALK, "character": line, "stock_exit": True}]
    facts = scene_facts_for(kept_facts_journey(turns, callback=None), story_context={})
    assert [fact.kind for fact in facts] == ["setup"]
