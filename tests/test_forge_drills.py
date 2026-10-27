"""La Forge's drills and its recommender (the overhaul, owner 2026-10-18).

The owner: more varied, more fun, more personal, and the learner learns fast;
use the mistakes we track to pick the exercise. A rung says *what* a learner
proves about a rule, a drill *how* the item is posed. These tests pin:

* what kind of slip a saved error is, and the learner's signal from them;
* the recommender's reasons: the learner's own mistakes, easier after a miss,
  harder after a streak, never the same drill twice in a row, «Ta phrase»;
* which items each drill can pose;
* end to end: a burst graded in one attempt, the learner's own sentence as a
  repair, the weak spot in the plan, and the épreuve offered from the recap.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.core import forge as core
from app.core.forge import Rung
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.error import UserError
from app.db.models.grammar import UserGrammarProgress
from app.services import forge_drills as drills
from app.services.forge import (
    TEST_OUT_OFFER_GAP_DAYS,
    ForgeService,
    _meaning_on_screen,
    _store_state,
    burst_selection,
    forge_state_of,
    offer_test_out,
)
from app.services.forge_drills import LearnerSignal, rank_drills

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# What kind of slip a saved error is
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("learner", "corrected", "kind"),
    [
        ("ecole", "école", drills.KIND_ACCENT),
        ("Il a mangé déjà", "Il a déjà mangé", drills.KIND_ORDER),
        ("Je suis allé marché", "Je suis allé au marché", drills.KIND_MISSING),
        ("je mange pas", "je ne mange pas", drills.KIND_MISSING),
        ("Je suis allé au le marché", "Je suis allé au marché", drills.KIND_EXTRA),
        ("Il avait content", "Il était content", drills.KIND_FORM),
        ("Hier j'ai allé au cinéma", "Hier je suis allé au cinéma", drills.KIND_FORM),
        ("Elle est allé", "Elle est allée", drills.KIND_FORM),
        ("Il mange une pomme", "Il mange une poire", drills.KIND_WORD),
        # Four tiles tapped at random is not a slip to learn from.
        ("marché le au suis", "Je suis allé au marché", None),
        ("Je mange.", "je mange", None),
        ("", "je mange", None),
    ],
)
def test_error_kind_reads_what_kind_of_slip_a_saved_error_is(learner, corrected, kind):
    assert drills.error_kind(learner, corrected) == kind


def test_the_signal_weighs_each_mistake_and_trusts_more_evidence_more():
    one = LearnerSignal.from_mistakes([("ecole", "école", 1.0)])
    assert one.kinds == {drills.KIND_ACCENT: 1.0}
    assert one.weight == pytest.approx(1.0 / drills.SIGNAL_FULL_WEIGHT)
    mixed = LearnerSignal.from_mistakes(
        [("ecole", "école", 3.0), ("Il avait content", "Il était content", 1.0), ("x", "x", 5.0)]
    )
    assert mixed.kinds[drills.KIND_ACCENT] == pytest.approx(0.75)
    assert mixed.kinds[drills.KIND_FORM] == pytest.approx(0.25)
    assert mixed.weight == 1.0
    assert LearnerSignal.from_mistakes([]).weight == 0.0


def _error(db: Session, user, *, learner: str, corrected: str, concept_id: int | None = None, **extra) -> UserError:
    row = UserError(
        user_id=user.id,
        concept_id=concept_id,
        error_category="grammar",
        original_text=learner,
        correction=corrected,
        source_type=extra.pop("source_type", "conversation"),
        state=extra.pop("state", "open"),
        occurrences=extra.pop("occurrences", 1),
        error_metadata=extra.pop("error_metadata", {}),
        **extra,
    )
    db.add(row)
    db.commit()
    return row


def test_learner_signal_reads_recent_saved_errors_and_discounts_old_or_mastered_ones(db_session: Session):
    from tests.test_atelier import _user

    user = _user(db_session)
    _error(db_session, user, learner="ecole", corrected="école", occurrences=3)
    _error(db_session, user, learner="Il avait content", corrected="Il était content", state="mastered")
    old = _error(db_session, user, learner="Il mange une pomme", corrected="Il mange une poire")
    old.updated_at = datetime.now(UTC) - timedelta(days=drills.SIGNAL_WINDOW_DAYS + 5)
    db_session.add(old)
    db_session.commit()
    signal = drills.learner_signal(db_session, user)
    assert set(signal.kinds) == {drills.KIND_ACCENT, drills.KIND_FORM}  # the old one is out of the window
    assert signal.kinds[drills.KIND_ACCENT] > 0.9  # three occurrences against a mastered slip


# ---------------------------------------------------------------------------
# The recommender
# ---------------------------------------------------------------------------


def _signal(kind: str) -> LearnerSignal:
    return LearnerSignal(kinds={kind: 1.0}, weight=1.0)


def _entry(concept_id: int, *, outcome: str = core.OUTCOME_CORRECT, drill: str = drills.DRILL_CHOICE) -> dict:
    return {"concept_id": concept_id, "outcome": outcome, "checked": True, "drill": drill}


@pytest.mark.parametrize("rung", list(Rung))
def test_without_a_signal_each_rung_opens_on_its_scaffolded_drill(rung):
    assert rank_drills(rung=int(rung), concept_id=1)[0] == drills.canonical_drill(int(rung))


def test_accent_slips_call_for_typing_and_word_order_slips_for_tiles():
    assert rank_drills(rung=Rung.BUILD, concept_id=1, signal=_signal(drills.KIND_ACCENT))[0] == drills.DRILL_TYPED
    assert rank_drills(rung=Rung.BUILD, concept_id=1, signal=_signal(drills.KIND_ORDER))[0] == drills.DRILL_TILES
    assert rank_drills(rung=Rung.TRANSFORM, concept_id=1, signal=_signal(drills.KIND_MISSING))[0] == drills.DRILL_REWRITE
    assert rank_drills(rung=Rung.DISCRIMINATE, concept_id=1, signal=_signal(drills.KIND_JUDGE))[0] == drills.DRILL_RAFALE


def test_a_miss_brings_the_scaffold_back_and_two_right_in_a_row_a_stretch():
    accent = _signal(drills.KIND_ACCENT)
    missed = [_entry(1, outcome=core.OUTCOME_INCORRECT)]
    assert rank_drills(rung=Rung.BUILD, concept_id=1, signal=accent, history=missed)[0] == drills.DRILL_TILES
    assert rank_drills(rung=Rung.BUILD, concept_id=1, signal=accent, reprise=True)[0] == drills.DRILL_TILES
    streak = [_entry(1), _entry(1, drill=drills.DRILL_JUDGE)]
    assert rank_drills(rung=Rung.BUILD, concept_id=1, history=streak)[0] in {drills.DRILL_TYPED, drills.DRILL_DICTATION}
    # Another rule's streak is not this one's.
    assert rank_drills(rung=Rung.BUILD, concept_id=2, history=streak)[0] == drills.DRILL_TILES


def test_never_the_same_drill_twice_in_a_row():
    after_judge = [_entry(2, drill=drills.DRILL_JUDGE)]
    assert rank_drills(rung=Rung.DISCRIMINATE, concept_id=1, history=after_judge)[0] == drills.DRILL_RAFALE
    after_tiles = [_entry(2, drill=drills.DRILL_TILES)]
    assert rank_drills(rung=Rung.BUILD, concept_id=1, history=after_tiles)[0] != drills.DRILL_TILES


def test_the_seances_own_missed_judgements_call_for_a_burst():
    misses = [_entry(2, outcome=core.OUTCOME_INCORRECT, drill=drills.DRILL_JUDGE), _entry(3, drill=drills.DRILL_TILES)]
    assert rank_drills(rung=Rung.DISCRIMINATE, concept_id=1, history=misses)[0] == drills.DRILL_RAFALE


def test_the_learners_own_sentence_comes_back_at_most_twice_and_never_back_to_back():
    assert rank_drills(rung=Rung.TRANSFORM, concept_id=1, mine_ready=True)[0] == drills.DRILL_MINE
    assert drills.DRILL_MINE not in rank_drills(rung=Rung.TRANSFORM, concept_id=1)
    just_now = [_entry(2, drill=drills.DRILL_MINE)]
    assert drills.DRILL_MINE not in rank_drills(rung=Rung.TRANSFORM, concept_id=1, mine_ready=True, history=just_now)
    twice = [_entry(2, drill=drills.DRILL_MINE), _entry(3, drill=drills.DRILL_TILES), _entry(2, drill=drills.DRILL_MINE),
             _entry(3, drill=drills.DRILL_TILES)]
    assert drills.DRILL_MINE not in rank_drills(rung=Rung.TRANSFORM, concept_id=1, mine_ready=True, history=twice)


def test_the_ranking_is_the_same_for_one_seance_and_slot():
    kwargs = {"rung": int(Rung.BUILD), "concept_id": 4, "signal": _signal(drills.KIND_FORM), "seed": "s:3"}
    assert rank_drills(**kwargs) == rank_drills(**kwargs)
    assert set(rank_drills(**kwargs)) == set(drills.DRILLS_BY_RUNG[Rung.BUILD])


# ---------------------------------------------------------------------------
# Which items a drill can pose
# ---------------------------------------------------------------------------


def test_typed_takes_a_short_form_in_a_blank():
    fill = {"prompt": "Hier, j'___ une pomme.", "correct_answer": "ai mangé", "choices": ["ai mangé", "suis mangé"]}
    assert drills.typed_fits(fill)
    assert not drills.typed_fits({**fill, "correct_answer": "ai mangé une très grande pomme rouge"})
    assert not drills.typed_fits({**fill, "prompt": "Hier, j'ai mangé une pomme."})
    judgement = {"prompt": "Il ___", "correct_answer": "Correct", "classify_kind": "judgement"}
    assert not drills.typed_fits(judgement)


def test_dictation_takes_a_sentence_one_hears_in_one_go():
    bank = {"answer_tokens": ["Je", "ne", "mange", "pas"], "correct_answer": "Je ne mange pas."}
    assert drills.dictation_fits(bank)
    assert not drills.dictation_fits({"answer_tokens": ["Viens"], "correct_answer": "Viens !"})


def test_a_spot_needs_one_short_stretch_to_fix():
    assert drills.spot_window("Hier j'ai allé au cinéma.", "Hier je suis allé au cinéma.") == (1, 2)
    assert drills.spot_window("Elle est allé à Paris", "Elle est allée à Paris") == (2, 3)
    assert drills.spot_window("je mange pas", "je ne mange pas") is None  # nothing to tap: a rewrite
    assert drills.spot_window("Il mange.", "Il mange.") is None
    assert drills.spot_window("Les enfants a joué dans le jardin hier soir", "Hier soir, les enfants ont joué") is None


def test_only_a_sentence_with_a_mistake_in_it_is_a_spot():
    repair = {"type": "rewrite", "source_fr": "Elle est allé à Paris", "source": "Elle est allé à Paris",
              "expected_answer": "Elle est allée à Paris"}
    assert drills.is_repair(repair) and drills.spot_fits(repair)
    assert drills.spot_fits({"type": "repair_rewrite", "source": "Elle n'a pas une idée.", "expected_answer": "Elle n'a pas d'idée."})
    # «Je bois du café.» → «Je ne bois pas de café.» is a right sentence to change: nothing to find.
    directed = {"type": "directed_rewrite", "source": "Je bois du café.", "expected_answer": "Je ne bois pas de café."}
    assert not drills.is_repair(directed)
    assert not drills.spot_fits(directed)
    assert drills.drill_of_item(Rung.TRANSFORM, directed, "transform") == drills.DRILL_REWRITE
    assert not drills.spot_fits({"source": "Il pleut quand je sors.", "expected_answer": "Il pleuvait quand je suis sorti."})


def test_own_sentences_are_real_local_slips_in_a_line():
    assert drills.mine_fits("Hier j'ai allé au cinéma", "Hier je suis allé au cinéma")
    assert not drills.mine_fits("Je mange.", "je mange")  # typography only
    assert not drills.mine_fits("ecole", "école")  # a word, not a line
    assert not drills.mine_fits("marché le au suis", "Je suis allé au marché")  # random tiles


def test_a_learners_own_sentence_is_only_ever_posed_as_itself():
    personal = {"personal": True, "source": "x y", "expected_answer": "x z"}
    assert drills.item_fits(drills.DRILL_MINE, personal)
    assert not drills.item_fits(drills.DRILL_SPOT, personal)
    assert not drills.item_fits(None, personal)
    assert not drills.item_fits(drills.DRILL_MINE, {"source": "x y", "expected_answer": "x z"})


def test_an_item_served_without_the_recommender_keeps_its_rungs_drill():
    assert drills.drill_of_item(Rung.RECOGNISE, {}) == drills.DRILL_CHOICE
    spot = {"source": "Elle est allé à Paris", "source_fr": "Elle est allé à Paris", "expected_answer": "Elle est allée à Paris"}
    assert drills.drill_of_item(Rung.TRANSFORM, spot, "transform") == drills.DRILL_SPOT
    assert drills.drill_of_item(Rung.TRANSFORM, {"source": "je mange pas", "expected_answer": "je ne mange pas"}) == (
        drills.DRILL_REWRITE
    )
    assert drills.drill_of_item(Rung.TRANSFORM, {"personal": True}) == drills.DRILL_MINE


def test_typing_a_form_needs_its_meaning_on_screen():
    assert _meaning_on_screen({"goal_native": 'Complete: "I ate an apple."'})
    assert _meaning_on_screen({"goal_native": "Ergänze den Satz: „Ich habe gegessen.“"})
    assert _meaning_on_screen({"goal_native": "Complète la phrase : « I ate »"})
    assert _meaning_on_screen({"prompt": "Hier, j'___ une pomme. (I ate)"})
    assert not _meaning_on_screen({"goal_native": "Complète la phrase avec la forme qui convient."})
    assert not _meaning_on_screen({"goal_native": 'Complete: ""'})


def test_a_burst_mixes_right_and_wrong_sentences_when_it_can():
    from app.services.forge import ForgeItem

    def judgement(index: int, label: str) -> ForgeItem:
        return ForgeItem(1, 1, "recognize", "classify", f"j{index}", index, f"fp{index}",
                         payload={"correct_label": label, "classify_kind": "judgement"})

    found = [judgement(i, "Correct") for i in range(4)] + [judgement(9, "À corriger")]
    picked = burst_selection(found)
    assert len(picked) == drills.RAFALE_SIZE
    assert {item.payload["correct_label"] for item in picked} == {"Correct", "À corriger"}
    assert burst_selection(found) == picked  # stable


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


def _forge_seance(db_session: Session, *, rung: int):
    from tests.test_forge_integration import _forge_session

    user, concept, session, shared = _forge_session(db_session)
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(rung)
    state.tracks[0].needs_spaced = False
    _store_state(session, state)
    db_session.commit()
    return user, concept, session, forge


def test_a_burst_poses_four_judgements_and_grades_them_in_one_attempt(db_session: Session, monkeypatch):
    from app.services.atelier import AtelierCorrectionService

    monkeypatch.setattr(drills, "rank_drills", lambda **_kw: [drills.DRILL_RAFALE, drills.DRILL_JUDGE])
    user, concept, session, forge = _forge_seance(db_session, rung=Rung.DISCRIMINATE)
    nxt = forge.next_item(user=user, session=session)
    assert nxt["drill"] == drills.DRILL_RAFALE
    items = nxt["items"]
    assert len(items) == drills.RAFALE_SIZE and items[0]["id"] == nxt["item_id"]
    assert len(set(nxt["group_fingerprints"])) == drills.RAFALE_SIZE
    assert all(drills.judgement_fits(item) for item in items)
    assert all("follow_up_key" not in item for item in items), "the burst's keys stay on the server"

    ids = [str(item["id"]) for item in items]
    # The set the learner's client reads holds every one of them (bank top-ups included).
    db_session.refresh(session)
    # Answered in another order than posed: the payload's «burst» keeps the order.
    answers = dict.fromkeys(reversed(ids), "Correct")
    # The exercise id names the lead and the count: four ids overflow its column.
    exercise_id = f"{concept.external_id}:classify:{ids[0]}+{len(ids)}"
    assert len(exercise_id) <= AtelierAttempt.__table__.c.exercise_id.type.length
    attempt = AtelierCorrectionService(db_session).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="recognize",
        mode="classify",
        exercise_id=exercise_id,
        answer_payload={"answers": answers, "burst": ids},
    )
    assert [item["id"] for item in attempt.prompt_payload["items"]] == ids
    burst = attempt.correction_payload["burst"]
    assert [row["item_id"] for row in burst] == ids
    right = [row["correct"] for row in burst]
    assert attempt.verdict == ("correct" if all(right) else "partial" if any(right) else "incorrect")
    assert "follow_up" not in attempt.correction_payload, "no correction step after a burst"
    for row in burst:
        if row["expected"] == "À corriger":
            assert row["corrected_fr"]
        assert row["sentence"]

    forge.observe_attempt(user=user, session=session, attempt=attempt)
    state = forge_state_of(session)
    assert state.history[-1]["drill"] == drills.DRILL_RAFALE
    assert set(nxt["group_fingerprints"]) <= set(state.served_fingerprints)
    assert attempt.correction_payload["forge"]["drill"] == drills.DRILL_RAFALE


def test_the_learners_own_mistake_comes_back_as_a_repair_and_counts_once_fixed(db_session: Session):
    from app.services.atelier import AtelierCorrectionService

    user, concept, session, forge = _forge_seance(db_session, rung=Rung.TRANSFORM)
    error = _error(
        db_session,
        user,
        learner="Je mange pas de viande le soir",
        corrected="Je ne mange pas de viande le soir",
        concept_id=concept.id,
    )
    nxt = forge.next_item(user=user, session=session)
    assert nxt["drill"] == drills.DRILL_MINE and nxt["personal"] is True
    item = nxt["item"]
    assert item["source_fr"] == "Je mange pas de viande le soir"
    assert item["instruction"] == "You wrote this earlier. Fix the mistake."
    assert item["goal_native"] == "You wrote this earlier. Fix the mistake."

    db_session.refresh(session)
    attempt = AtelierCorrectionService(db_session).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id=f"{concept.external_id}:rewrite:{nxt['item_id']}",
        answer_payload={"answers": {nxt["item_id"]: "Je ne mange pas de viande le soir."}},
    )
    assert attempt.verdict == "correct"
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    db_session.refresh(error)
    assert error.mastery_streak == 1 and error.last_correct_date is not None
    assert error.state == "repairing"
    state = forge_state_of(session)
    assert state.history[-1]["drill"] == drills.DRILL_MINE


def test_an_own_sentence_is_read_in_its_whole_line_when_the_answer_is_at_hand(db_session: Session):
    from app.services.forge import _mine_sentence

    user, concept, session, _forge = _forge_seance(db_session, rung=Rung.TRANSFORM)
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=concept.id,
        round="sentence",
        mode="sentence",
        exercise_id="x",
        prompt_payload={},
        answer_payload={"text": "Bonjour Marin. Hier j'ai allé au marché avec ma sœur. C'était bien."},
        correction_payload={},
        verdict="incorrect",
        score_0_4=1.0,
    )
    db_session.add(attempt)
    db_session.commit()
    error = _error(
        db_session, user, learner="j'ai allé", corrected="je suis allé", concept_id=concept.id,
        source_type="atelier", source_attempt_id=attempt.id,
    )
    assert _mine_sentence(db_session, error) == (
        "Hier j'ai allé au marché avec ma sœur.",
        "Hier je suis allé au marché avec ma sœur.",
    )


def test_a_line_with_a_german_word_left_in_it_is_never_posed_as_a_repair(db_session: Session):
    """#348: «war» → «est» left «Im est au Mistral, Marin.» as the key, and the right
    «Je suis au Mistral, Marin.» was refused. The corrected line must be French."""
    from app.services.forge import BankItemProvider

    user, concept, session, _forge = _forge_seance(db_session, rung=Rung.TRANSFORM)
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=concept.id,
        round="sentence",
        mode="sentence",
        exercise_id="x",
        prompt_payload={},
        answer_payload={"text": "Im war au Mistral, Marin."},
        correction_payload={},
        verdict="incorrect",
        score_0_4=1.0,
    )
    db_session.add(attempt)
    db_session.commit()
    _error(
        db_session, user, learner="war", corrected="est", concept_id=concept.id,
        source_type="atelier", source_attempt_id=attempt.id,
    )
    assert not drills.mine_fits(
        "Im war au Mistral, Marin.", "Im est au Mistral, Marin."
    ), "a key with a German word left in it was accepted as a repair"
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    assert provider.mine_candidates(concept.id) == [], "the garbled line was posed as the learner's own repair"
    assert provider.mine_item(concept_id=concept.id, exclude=set()) is None


def test_a_french_line_with_one_slip_is_posed_and_its_right_answer_is_accepted(db_session: Session):
    from app.services.answer_acceptance import judge
    from app.services.forge import BankItemProvider

    user, concept, session, _forge = _forge_seance(db_session, rung=Rung.TRANSFORM)
    _error(db_session, user, learner="Je es au Mistral, Marin.", corrected="Je suis au Mistral, Marin.", concept_id=concept.id)
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    found = provider.mine_candidates(concept.id)
    assert [c["expected"] for c in found] == ["Je suis au Mistral, Marin."]
    assert judge("Je suis au Mistral, Marin.", [found[0]["expected"]]).correct


def test_a_recognise_rounds_mistake_is_never_posed_as_the_learners_own(db_session: Session):
    from app.services.forge import BankItemProvider

    user, concept, session, _forge = _forge_seance(db_session, rung=Rung.TRANSFORM)
    _error(
        db_session, user, learner="Je mange pas de viande le soir", corrected="Je ne mange pas de viande le soir",
        concept_id=concept.id, source_type="atelier", error_metadata={"source_payload": {"round": "recognize"}},
    )
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    assert provider.mine_candidates(concept.id) == []


def _slip_not_yet_due(db_session: Session, user, concept_id: int, learner: str, corrected: str, now: datetime):
    """A fresh mistake whose own review is days away: the review queue does not
    bring its rule today; only the weak spot can."""

    row = _error(db_session, user, learner=learner, corrected=corrected, concept_id=concept_id)
    row.updated_at = now - timedelta(hours=3)
    row.next_review_date = now + timedelta(days=4)
    db_session.add(row)
    db_session.commit()
    return row


def test_the_weak_spot_takes_the_first_due_slot(db_session: Session):
    from app.services.forge_picker import REASON_WEAK_SPOT, forge_plan
    from tests.test_atelier import _concept, _user

    now = datetime.now(UTC)
    user = _user(db_session)
    anchor = _concept(db_session, "FR_A2_NEG_001")
    weak = _concept(db_session, "FR_B1_TENSE_001")
    for concept in (anchor, weak):
        db_session.add(
            UserGrammarProgress(
                user_id=user.id, concept_id=concept.id, introduced_at=now - timedelta(days=4), reps=1,
                stability=5.0, next_review=now + timedelta(days=5),
            )
        )
    db_session.commit()
    _slip_not_yet_due(db_session, user, weak.id, "j'ai allé", "je suis allé", now)
    plan = forge_plan(db_session, user, now, preferred_concept_id=anchor.id)
    assert weak.id not in plan.concept_ids  # one slip, not due: not a weak spot yet

    _slip_not_yet_due(db_session, user, weak.id, "il a venu", "il est venu", now)
    plan = forge_plan(db_session, user, now, preferred_concept_id=anchor.id)
    due = [unit for unit in plan.units if unit.role == "due"]
    assert due and due[0].concept_id == weak.id and due[0].reason == REASON_WEAK_SPOT


def test_a_mistake_never_seats_a_rule_the_learner_has_not_met(db_session: Session):
    from app.services.forge_picker import forge_plan
    from tests.test_atelier import _concept, _user

    now = datetime.now(UTC)
    user = _user(db_session)
    anchor = _concept(db_session, "FR_A2_NEG_001")
    unmet = _concept(db_session, "FR_B1_TENSE_001")
    for _ in range(3):
        _slip_not_yet_due(db_session, user, unmet.id, "j'ai allé", "je suis allé", now)
    plan = forge_plan(db_session, user, now, preferred_concept_id=anchor.id)
    assert unmet.id not in plan.concept_ids


def _ready_rule(db_session: Session, user, concept, **fields) -> UserGrammarProgress:
    progress = UserGrammarProgress(
        user_id=user.id,
        concept_id=concept.id,
        introduced_at=fields.pop("introduced_at", NOW - timedelta(days=2)),
        forge_rung=fields.pop("forge_rung", int(Rung.TRANSFORM)),
        reps=2,
        stability=4.0,
        **fields,
    )
    db_session.add(progress)
    db_session.commit()
    return progress


def test_the_epreuve_is_offered_for_a_ready_rule_every_few_days(db_session: Session):
    from tests.test_atelier import _concept, _user

    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    _ready_rule(db_session, user, concept)
    offer = offer_test_out(db_session, user=user, concept_ids=[concept.id], now=NOW)
    assert offer == {"concept_id": concept.id, "rung": int(Rung.TRANSFORM), "short": True, "items": 3}
    db_session.commit()
    assert offer_test_out(db_session, user=user, concept_ids=[concept.id], now=NOW + timedelta(hours=2)) is None
    tomorrow = NOW + timedelta(days=1)
    assert offer_test_out(db_session, user=user, concept_ids=[concept.id], now=tomorrow) is None
    later = NOW + timedelta(days=TEST_OUT_OFFER_GAP_DAYS, hours=1)
    assert offer_test_out(db_session, user=user, concept_ids=[concept.id], now=later) is not None


@pytest.mark.parametrize(
    "fields",
    [
        {"forge_rung": int(Rung.BUILD)},  # not high enough yet
        {"introduced_at": NOW - timedelta(hours=1)},  # met today: its first day
        {"held_at": NOW - timedelta(days=1)},  # held already
        {"tested_out_at": NOW - timedelta(days=9)},  # tested out already
    ],
)
def test_the_epreuve_is_not_offered_for_a_rule_that_is_not_ready(db_session: Session, fields):
    from tests.test_atelier import _concept, _user

    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    _ready_rule(db_session, user, concept, **fields)
    assert offer_test_out(db_session, user=user, concept_ids=[concept.id], now=NOW) is None


def test_a_recent_epreuve_paces_the_next_offer(db_session: Session):
    from tests.test_atelier import _concept, _user

    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    _ready_rule(db_session, user, concept)
    session = ForgeService(db_session).start_test_out(user=user, concept_id=concept.id, short=True)
    assert session.status == "test_out"
    assert offer_test_out(db_session, user=user, concept_ids=[concept.id], now=datetime.now(UTC)) is None


def test_the_seance_recap_carries_the_epreuve_offer(client, db_session: Session):
    from app.db.models.grammar import GrammarConcept
    from tests.test_atelier import _prime_core_exercise_sets, _token

    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    started = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id})
    assert started.status_code == 201, started.text
    session = db_session.get(AtelierSession, UUID(started.json()["session_id"]))
    progress = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == session.user_id, UserGrammarProgress.concept_id == neg.id)
        .one_or_none()
    )
    if progress is None:
        progress = UserGrammarProgress(user_id=session.user_id, concept_id=neg.id)
    progress.introduced_at = datetime.now(UTC) - timedelta(days=3)
    progress.forge_rung = int(Rung.PRODUCE)
    progress.held_at = None
    db_session.add(progress)
    db_session.commit()
    done = client.post(f"/api/v1/atelier/sessions/{session.id}/complete", headers=headers)
    assert done.status_code == 200, done.text
    offer = done.json()["recap"]["forge"]["test_out_offer"]
    assert offer["concept_id"] == neg.id and offer["short"] is True
    # The recap read again is the same recap: the offer stays on it.
    again = client.post(f"/api/v1/atelier/sessions/{session.id}/complete", headers=headers)
    assert again.json()["recap"]["forge"]["test_out_offer"] == offer


def test_an_unknown_error_id_on_an_own_sentence_is_ignored(db_session: Session):
    user, _concept, _session, forge = _forge_seance(db_session, rung=Rung.TRANSFORM)
    forge._review_own_mistake(user=user, item={"error_id": "not-a-uuid"}, now=NOW)
    forge._review_own_mistake(user=user, item={"error_id": str(uuid4())}, now=NOW)
