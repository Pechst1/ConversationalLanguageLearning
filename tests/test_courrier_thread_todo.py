"""#1080 / #922: a Courrier letter's verdict follows what the thread established.

The corrector reads one learner message at a time and marks the To do met or not.
Neither the agent's own confirmations (#1080: «Partly · goals met 0/1» after the
agent confirmed tomorrow and the window seat) nor a reply that says the opposite
of the To do (#922: «Promise kept» for «Non, je n’ai pas la serviette») reached
the verdict. These tests drive the debrief, which is where the verdict, the goal
count and the story outcome are decided.
"""
from __future__ import annotations

from uuid import uuid4

from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt, RealWorldMissionTurn
from app.services import story_correspondence as courrier
from app.services.missions import MissionDebriefService

# The live walk of 26 Nov 2026, «Un train pour demain», Agent Moreau.
TRAIN_TODO_EN = "The agent knows you want to leave tomorrow and want a window seat."
TRAIN_TODO_FR = "L'agent sait que tu veux partir demain et que tu veux une place côté fenêtre."
TRAIN_LEARNER = [
    "Non, je ne veux pas mon argent. Je veux partir demain matin, a la fenetre, si possible.",
    "Plus tôt, s il vous plaît. Et est-ce que mon chat Gaston peut voyager avec moi dans le train ?",
    "Oui, c'est parfait, merci.",
]
TRAIN_AGENT = [
    "D'accord, vous voulez partir demain matin. Plutôt tôt ou plus tard ?",
    "Oui, votre chat Gaston peut voyager avec vous. Je vais réserver une place près de la fenêtre "
    "pour un train tôt demain matin.",
    "Parfait, je vous réserve votre place près de la fenêtre pour demain matin.",
]

# The live walk of 19 Nov 2026, Zoé's letter.
NAPKIN_TODO_EN = "Zoé knows you have the napkin for her, and you choose a time."
NAPKIN_TODO_FR = "Zoé sait que tu as la serviette pour elle, et tu choisis une heure."
NAPKIN_REPLY = "Non, je n’ai pas la serviette … On se retrouve à midi quand même ?"

TODO = {"id": "real_world_task", "label": "Régler une situation de voyage ou de travail", "kind": "communication", "required": True}
CONCEPT = {"id": "concept_7", "label": "Placer une fois : un, une, des", "kind": "grammar", "concept_id": 7, "required": False}
RUE = {"id": "vocabulary_42", "label": "Placer « rue » naturellement", "kind": "vocabulary", "word_id": 42, "required": False}


def _mission(*, todo_fr: str, todo_en: str, objectives: list[dict]) -> RealWorldMission:
    return RealWorldMission(
        id=uuid4(),
        user_id=uuid4(),
        cadence="ad_hoc",
        mission_type="travel_work",
        title="Un train pour demain",
        brief="",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=objectives,
        prompt_payload={
            "messenger": {
                "contact_name": "Agent Moreau",
                "success_signal": todo_fr,
                "success_signal_i18n": {"fr": todo_fr, "en": todo_en},
            }
        },
        recap_payload={},
    )


def _progress(**met: bool) -> list[dict]:
    return [{"id": key, "label": key, "met": value, "note": ""} for key, value in met.items()]


def _turns(mission: RealWorldMission, learner: list[str], agent: list[str], progress: list[dict]) -> list[RealWorldMissionTurn]:
    rows: list[RealWorldMissionTurn] = []
    for index, (mine, theirs) in enumerate(zip(learner, agent, strict=True)):
        rows.append(
            RealWorldMissionTurn(
                id=uuid4(), mission_id=mission.id, user_id=mission.user_id, turn_index=2 * index, role="user",
                text=mine, correction_payload={"verdict": "accepted", "objective_progress": progress, "errata": []},
            )
        )
        rows.append(
            RealWorldMissionTurn(
                id=uuid4(), mission_id=mission.id, user_id=mission.user_id, turn_index=2 * index + 1,
                role="assistant", text=theirs, correction_payload={},
            )
        )
    mission.turns = rows
    return rows


def _debrief(mission: RealWorldMission, *, attempts: list | None = None) -> dict:
    users = [turn for turn in (mission.turns or []) if turn.role == "user"]
    return MissionDebriefService().build(
        mission=mission, attempts=attempts or [], turns=users, errata_count=5, srs_result={"saved_count": 0}
    )


# -- #1080 -------------------------------------------------------------------


def test_1080_a_thread_the_agent_confirmed_ends_promise_kept() -> None:
    """The exact 26 Nov thread: the corrector, reading one message at a time, never
    marked the To do met; the agent confirmed both items in its own lines."""

    mission = _mission(todo_fr=TRAIN_TODO_FR, todo_en=TRAIN_TODO_EN, objectives=[TODO, CONCEPT, RUE])
    _turns(mission, TRAIN_LEARNER, TRAIN_AGENT, _progress(real_world_task=False, concept_7=True, vocabulary_42=False))

    recap = _debrief(mission)

    assert recap["outcome"] == "kept", f"the agent confirmed tomorrow and the window seat, yet the letter ends {recap['outcome']!r}"
    assert recap["measured"]["objectives_met"] == recap["measured"]["objectives_total"] == 1
    todo = next(row for row in recap["objective_results"] if row["id"] == "real_world_task")
    assert todo["met"] is True


def test_1080_a_word_target_never_turns_a_met_todo_into_partly() -> None:
    """«rue» is not named in the To do: it is never a goal that counts."""

    outcomes = {}
    for used in (True, False):
        mission = _mission(todo_fr=TRAIN_TODO_FR, todo_en=TRAIN_TODO_EN, objectives=[RUE])
        _turns(mission, TRAIN_LEARNER, TRAIN_AGENT, _progress(vocabulary_42=used))
        recap = _debrief(mission)
        assert recap["measured"]["objectives_total"] == 0, "the word chip «rue» was printed as «goals met 0/1»"
        outcomes[used] = recap["outcome"]
    assert outcomes[True] == outcomes[False], f"the word «rue» decided the verdict: {outcomes}"
    assert outcomes[False] != "missed"


def test_1080_the_agent_saying_no_confirms_nothing() -> None:
    """The lift needs the agent's own confirmation, not the learner's wish alone."""

    mission = _mission(todo_fr=TRAIN_TODO_FR, todo_en=TRAIN_TODO_EN, objectives=[TODO, RUE])
    _turns(
        mission,
        TRAIN_LEARNER[:1],
        ["D'accord pour demain matin, mais il n'y a plus de place près de la fenêtre."],
        _progress(real_world_task=False, vocabulary_42=False),
    )
    recap = _debrief(mission)
    assert recap["outcome"] != "kept"
    assert recap["measured"]["objectives_met"] == 0


# -- #922 --------------------------------------------------------------------


def test_922_a_reply_negating_the_todo_fact_is_not_promise_kept() -> None:
    """The exact 19 Nov reply. The corrector said the To do was met."""

    mission = _mission(todo_fr=NAPKIN_TODO_FR, todo_en=NAPKIN_TODO_EN, objectives=[TODO])
    attempt = RealWorldMissionAttempt(
        id=uuid4(), mission_id=mission.id, user_id=mission.user_id, mode="writing",
        answer_payload={"text": NAPKIN_REPLY},
        correction_payload={"verdict": "accepted", "objective_progress": _progress(real_world_task=True), "errata": []},
        verdict="accepted", score_0_4=4,
    )
    mission.turns = []

    recap = _debrief(mission, attempts=[attempt])

    assert recap["outcome"] != "kept", "«Non, je n’ai pas la serviette» was counted as «Promise kept»"
    assert recap["outcome"] == "partial"
    assert recap["measured"]["objectives_met"] == 0
    # The goal line says which part was missed, in the learner's language and in French.
    assert "napkin" in recap["measured"]["todo_open"]["en"]
    assert "serviette" in recap["measured"]["todo_open"]["fr"]
    todo = next(row for row in recap["objective_results"] if row["id"] == "real_world_task")
    assert todo["met"] is False
    assert "serviette" in todo["note"] or "napkin" in todo["note"]


def test_922_the_same_reply_in_a_chat_thread() -> None:
    mission = _mission(todo_fr=NAPKIN_TODO_FR, todo_en=NAPKIN_TODO_EN, objectives=[TODO, RUE])
    _turns(
        mission,
        [NAPKIN_REPLY],
        ["Ah, dommage. D'accord, à midi alors !"],
        _progress(real_world_task=True, vocabulary_42=False),
    )
    recap = _debrief(mission)
    assert recap["outcome"] == "partial"


# -- the guard itself ----------------------------------------------------------


def test_reading_an_open_question_is_never_contradicted() -> None:
    """«whether you leave on Saturday» is a question: «je ne pars pas samedi» answers it."""

    from app.services.story_correspondence import read_todo_in_thread

    reading = read_todo_in_thread(
        "Hélène sait si tu pars samedi ou si tu veux rester, et de quoi cela dépend.",
        learner_lines=["Je ne pars pas samedi, je reste."],
        correspondent_lines=[],
    )
    assert not reading["contradicted"]


def test_reading_a_later_yes_overrides_an_earlier_no() -> None:
    from app.services.story_correspondence import read_todo_in_thread

    reading = read_todo_in_thread(
        NAPKIN_TODO_FR,
        learner_lines=["Non, je n’ai pas la serviette.", "Ah si, pardon, j'ai la serviette dans mon sac."],
        correspondent_lines=[],
    )
    assert not reading["contradicted"]


def test_reading_an_agent_question_is_not_a_confirmation() -> None:
    from app.services.story_correspondence import read_todo_in_thread

    reading = read_todo_in_thread(
        TRAIN_TODO_FR,
        learner_lines=["Je veux partir demain, a la fenetre."],
        correspondent_lines=["Vous voulez partir demain ? Une place près de la fenêtre ?"],
    )
    assert not reading["established"]


def test_the_outcome_word_ignores_suggested_words_everywhere() -> None:
    """One rule for which objectives count, shared by the verdict and the goal count."""

    objectives = [RUE]
    for used in (True, False):
        progress = {"vocabulary_42": {"met": used}}
        assert courrier.outcome_from_objectives(objectives=objectives, progress_by_id=progress) == "partial"
