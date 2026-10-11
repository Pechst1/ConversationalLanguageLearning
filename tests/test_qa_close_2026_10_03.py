"""QA-CLOSE 2026-10-03 — the open items of EXERCISE-QA-2026-10-03, closed.

One regression test (or more) per item:

1. «Convaincre» objections name the speaker, so the walk carries no known defect;
2. a story reply in German or English is never routed: the scene asks for French;
3. the story's French task line says «vous», like the rest of the French chrome;
4. a test-out's free use needs acceptable French, not only a detector hit;
5. the Forge's keyed graders use the acceptance contract (no accent fold, no
   «pas de» shortcut);
6. owner decisions: (a) drill and conjugation graded on the server, (b) three
   explicit ✗ → ✓ pairs per B1 unit, (c) strict accents where the accent is the
   rule, (d) a forgiven slip named on a hit, (e) gender labels in the learner's
   language;
7. CI runs the long walk.
"""
# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
from __future__ import annotations

import csv
import json
import re
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_season_story_qa import _page, _say, _scenario, offline  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


# -- 1. «Convaincre» names its speaker; the walk filters nothing ---------------------


def test_the_walk_has_no_known_defect_left():
    from tests import walk_checks

    assert walk_checks.KNOWN_DEFECTS == ()
    problem = "T3 [respond]: machine key shown: augustin_de_roncourt : Marchand ?"
    assert walk_checks.run_all([], include_known=False) == []
    assert not walk_checks._known(problem), "a cast id in a reply is a problem again"


def test_a_convince_objection_is_said_by_a_name_never_a_cast_id():
    from app.services.season.page import convince_as_turn

    turn = convince_as_turn(
        {
            "id": "b.convaincre",
            "to": "augustin_de_roncourt",
            "to_name": "Gus",
            "objections": [{"text_fr": "Marchand ? Il veut fermer le café !"}],
            "prompt": {"text_fr": "Convaincre Gus."},
        }
    )
    spoken = [line for line in turn["panel"]["lines"] if line.get("who") == "augustin_de_roncourt"]
    assert spoken and all(line["name"] == "Gus" for line in spoken)


# -- 2. a reply in German or English is asked again, in French -----------------------


@pytest.mark.parametrize(
    "text",
    ["Ich weiß nicht.", "Ich bin hier wegen Odile.", "I don't know.", "I am her grandson.", "Nein", "Yes"],
)
def test_a_reply_in_another_language_is_detected(text):
    from app.services.season.turns import reply_is_not_french

    assert reply_is_not_french(text)


@pytest.mark.parametrize(
    "text",
    [
        "Je ne sais pas.",
        "je sais pas",
        "Odile est ma grand-mère.",
        "Je m'appelle Vincent.",
        "hier je suis allé au café",
        "Je suis Vincent, ich wohne hier",  # mixed, still French enough to read
        "Oui",
        "Vincent",
        "merci",
    ],
)
def test_clumsy_or_mixed_french_is_still_french(text):
    from app.services.season.turns import reply_is_not_french

    assert not reply_is_not_french(text)


def test_a_german_reply_is_never_routed_and_is_asked_for_in_french(offline):
    from app.services.season.runtime import ASK_AGAIN

    scenario = _scenario(_page(band="A1", language="de"))
    evaluation = _say(scenario, "Ich weiß nicht.", [], 0)
    assert evaluation.route == {"turn": "a.turn1", "reply": ASK_AGAIN}, "no story branch"
    assert evaluation.turn_consumed is False and evaluation.needs_repair is True
    assert "en français" in evaluation.character_reply_fr
    assert [line["speaker_id"] for line in evaluation.reply_lines] == ["augustin_de_roncourt"]
    # Asked again every time: a second German reply is not routed either.
    history = [{"learner": "Ich weiß nicht.", "character": "…", "free": True, "route": dict(evaluation.route)}]
    again = _say(scenario, "Ich weiß es nicht.", history, 0)
    assert again.route["reply"] == ASK_AGAIN
    # The same learner in clumsy French is routed.
    routed = _say(scenario, "Odile est ma grand-mère.", history, 0)
    assert routed.route["reply"] != ASK_AGAIN and routed.turn_consumed is True


def test_the_french_please_line_is_in_french_with_a_translation_only_below_b1():
    from app.services.season.turns import FRENCH_PLEASE, french_please_panel

    turn = {"id": "a.turn1", "to": "lila_bonnet", "to_name": "Lila"}
    a1 = french_please_panel(turn, native="de")["lines"][0]
    assert a1["text_fr"] == FRENCH_PLEASE["fr"] and a1["text_native"] == FRENCH_PLEASE["de"]
    assert a1["name"] == "Lila"
    assert french_please_panel(turn, native=None)["lines"][0]["text_native"] is None
    # Every character can say it: neither «tu» nor «vous».
    assert not re.search(r"\b(tu|vous|te|toi)\b", FRENCH_PLEASE["fr"], re.IGNORECASE)


# -- 3. the French task line says «vous» ---------------------------------------------

_TU = re.compile(r"\b(tu|te|toi|ton|ta|tes|t')\b|^(Dis|Choisis|Décide|Lis|Touche|Montre|Convaincs|Ajoute|Réponds|Demande)\b")


def test_every_french_task_line_says_vous_like_the_chrome():
    tasks = json.loads((ROOT / "app/data/season/s1/tasks.json").read_text(encoding="utf-8"))["tasks"]
    tu = {key: row["fr"] for key, row in tasks.items() if _TU.search(row.get("fr") or "")}
    assert not tu, tu


def test_the_c1_objective_reads_vous():
    page = _page(band="C1", language="fr")
    first = next(m for m in page["movements"] if m.get("kind") == "turn")
    assert first["task_native"] == "Dites qui vous êtes et pourquoi vous êtes là."


# -- 4. a test-out's free use must be acceptable French ------------------------------


def test_free_use_with_the_rules_trap_is_not_acceptable(db_session):
    from app.services.forge_grading import detector_check, free_use_acceptable
    from tests.test_atelier import _concept

    concept = _concept(db_session, "FR_A2_NEG_001")
    wrong = "Je n'ai pas une maison."
    assert detector_check(concept, wrong)["status"] == "hit", "the detector alone would pass it"
    verdict = free_use_acceptable(concept, wrong)
    assert verdict["acceptable"] is False and verdict["right"] == "n'ai pas de"
    assert free_use_acceptable(concept, "Je n'ai pas de maison.")["acceptable"] is True


def test_a_test_out_free_use_with_an_error_in_the_rule_fails(db_session, monkeypatch):
    from app.config import settings
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService, forge_state_of
    from tests.test_atelier import _concept, _user
    from tests.test_forge_integration import _right

    monkeypatch.setattr(settings, "ATELIER_CORRECTION_LLM_ENABLED", False)
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: False)
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    forge = ForgeService(db_session)
    session = forge.start_test_out(user=user, concept_id=concept.id)
    service = AtelierCorrectionService(db_session)
    free_verdicts = []
    while (nxt := forge.next_item(user=user, session=session)) is not None:
        free = nxt["round"] not in {"recognize", "transform"}
        answer = {"text": "Je n'ai pas une voiture le soir."} if free else _right(nxt["item"], nxt["round"], nxt["mode"])
        attempt = service.submit_attempt(
            session=session,
            user=user,
            concept=concept,
            round_name=nxt["round"],
            mode="rewrite" if nxt["round"] == "transform" else nxt["mode"],
            exercise_id=f"forge:{concept.id}:{nxt['round']}:{nxt['item_id']}",
            answer_payload=answer,
        )
        if free:
            free_verdicts.append(attempt.correction_payload["verdict"])
            assert attempt.correction_payload["local_check"]["detector"] == "hit"
            assert attempt.correction_payload["local_check"]["trap"]["right"] == "n'ai pas de"
        forge.observe_attempt(user=user, session=session, attempt=attempt)
    assert free_verdicts and set(free_verdicts) == {"incorrect"}
    result = forge_state_of(session).result
    assert result["passed"] is False and result["production_correct"] is False


# -- 5. the Forge's keyed graders use the acceptance contract -------------------------


def _transform(learner: str, expected: str, source: str) -> dict[str, Any]:
    from app.services.atelier import AtelierCorrectionService

    item = {"id": "t1", "type": "directed_rewrite", "source": source, "expected_answer": expected, "instruction": "x"}
    return AtelierCorrectionService(None)._correct_transform_rule_based(
        None, {"items": [item]}, {"answers": {"t1": learner}}
    )


def test_a_rewrite_accent_slip_is_forgiven_and_named():
    correction = _transform("C'est tres bien.", "C'est très bien.", "C'est bien.")
    assert correction["verdict"] == "correct"
    assert correction["accent_notes"][0]["corrected_target"] == "C'est très bien."


def test_a_rewrite_accent_that_is_grammar_is_refused():
    assert _transform("Il à mangé.", "Il a mangé.", "Il mange.")["verdict"] == "incorrect"


def test_a_rewrite_whose_source_differs_only_by_the_accent_is_strict():
    """The item's rule is the accent (owner decision c): the cedilla is the answer."""

    assert _transform("Nous commencons.", "Nous commençons.", "Nous commencons.")["verdict"] == "incorrect"
    assert _transform("Nous commençons.", "Nous commençons.", "Nous commencons.")["verdict"] == "correct"


def test_the_pas_de_shortcut_is_gone():
    from app.services.atelier import AtelierCorrectionService

    service = AtelierCorrectionService(None)
    concept = SimpleNamespace(external_id="FR_A2_NEG_001", name="ne...pas de", id=1)
    assert not service._close_enough_transform(concept, "Je ne pas de café bois.", "Je ne bois pas de café.")
    source = (ROOT / "app/services/atelier.py").read_text(encoding="utf-8")
    assert '"pas de" in learner_norm' not in source


def test_a_fill_option_that_differs_from_the_key_by_its_accent_is_graded_strictly():
    from app.services.atelier import AtelierCorrectionService

    item = {"id": "f1", "prompt": "Il ___ mangé.", "choices": ["a", "à", "as"], "correct_answer": "a"}
    service = AtelierCorrectionService(None)
    wrong = service._correct_recognize(None, "fill", {"items": [item]}, {"answers": {"f1": "à"}})
    right = service._correct_recognize(None, "fill", {"items": [item]}, {"answers": {"f1": "a"}})
    assert wrong["verdict"] == "incorrect" and right["verdict"] == "correct"


# -- 6a. the drill and the conjugation are graded on the server -----------------------


def _login(client, db_session):
    from app.core.security import decode_token
    from app.db.models.user import User

    email = f"qa-close-{uuid.uuid4().hex}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "qa-close-pass-1", "target_language": "fr", "native_language": "de"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "qa-close-pass-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, db_session.get(User, uuid.UUID(str(decode_token(token)["sub"])))


def test_the_drill_never_trusts_the_clients_correct_flag(client, db_session):
    from app.db.models.progress import ReviewLog, UserVocabularyProgress
    from tests.test_wp115a_vocabulary_memory import _make_due_word

    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "la clé", rank=84)
    db_session.commit()
    wrong = client.post(
        "/api/v1/anki/review",
        headers=headers,
        json={"word_id": word.id, "rating": 3, "format": "typed", "correct": True, "answer_text": "la porte"},
    )
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["correct"] is False and wrong.json()["expected"] == "la clé"
    db_session.expire_all()
    progress = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word.id).one()
    log = db_session.query(ReviewLog).filter(ReviewLog.progress_id == progress.id).order_by(ReviewLog.created_at.desc()).first()
    assert log.rating == 0, "the server's verdict, not the client's «correct: true»"

    slip = client.post(
        "/api/v1/anki/review",
        headers=headers,
        json={"word_id": word.id, "rating": 0, "format": "typed", "answer_text": "cle"},
    ).json()
    assert slip["correct"] is True
    assert slip["note_native"] and "Akzent" in slip["note_native"], "a forgiven slip is named"


def test_a_review_without_text_is_a_self_rated_flashcard(client, db_session):
    from app.db.models.progress import ReviewLog, UserVocabularyProgress
    from tests.test_wp115a_vocabulary_memory import _make_due_word

    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "le seau", rank=85)
    db_session.commit()
    old_client = client.post(
        "/api/v1/anki/review",
        headers=headers,
        json={"word_id": word.id, "rating": 1, "format": "typed", "correct": True},
    )
    assert old_client.status_code == 200 and old_client.json()["correct"] is None
    db_session.expire_all()
    progress = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word.id).one()
    log = db_session.query(ReviewLog).filter(ReviewLog.progress_id == progress.id).order_by(ReviewLog.created_at.desc()).first()
    assert (log.rating, log.format) == (1, "flashcard")


def test_the_conjugation_is_graded_on_the_server(client, db_session):
    from app.db.models.vocabulary import UserConjugationProgress
    from app.services.conjugation import build_conjugation_rows, upsert_conjugation_rows

    headers, user = _login(client, db_session)
    upsert_conjugation_rows(db_session, build_conjugation_rows("venir", cefr_band="A2"))
    db_session.commit()
    item = client.get("/api/v1/vocabulary/conjugation/review", headers=headers).json()["items"][0]
    wrong = client.post(
        "/api/v1/vocabulary/conjugation/review",
        headers=headers,
        json={"lemma": item["lemma"], "tense": item["tense"], "rating": 3, "person": item["person"], "answer_text": "venu"},
    )
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["correct"] is False and wrong.json()["expected"]
    progress = (
        db_session.query(UserConjugationProgress)
        .filter(UserConjugationProgress.user_id == user.id, UserConjugationProgress.normalized_lemma == "venir")
        .one()
    )
    assert progress.lapses == 1, "a miss is «Again», whatever was pressed"
    right = client.post(
        "/api/v1/vocabulary/conjugation/review",
        headers=headers,
        json={"lemma": item["lemma"], "tense": item["tense"], "rating": 0, "person": item["person"], "answer_text": item["answer"]},
    ).json()
    assert right["correct"] is True
    rated = client.post(
        "/api/v1/vocabulary/conjugation/review",
        headers=headers,
        json={"lemma": item["lemma"], "tense": item["tense"], "rating": 2},
    ).json()
    assert rated["correct"] is None, "a rating alone is a self-rating"


def test_the_frontend_sends_the_text_not_a_verdict():
    review = (ROOT / "web-frontend/pages/vocabulary/review.tsx").read_text(encoding="utf-8")
    assert "correct: typedMatches" not in review and "answer_text: typedAnswer" in review
    conjugation = (ROOT / "web-frontend/pages/vocabulary/conjugation.tsx").read_text(encoding="utf-8")
    assert "answer_text: typed" in conjugation


# -- 6b. three explicit ✗ → ✓ pairs per B1 unit --------------------------------------


def test_every_b1_unit_carries_three_explicit_trap_pairs():
    pair = re.compile(r"^✗ .+ → ✓ .+$")
    with (ROOT / "templates/french_core_grammar_v2.tsv").open(encoding="utf-8") as handle:
        b1 = [row for row in csv.DictReader(handle, delimiter="\t") if row["cefr_level"] == "B1"]
    assert len(b1) >= 40
    for row in b1:
        traps = [part.strip() for part in row["main_traps"].split(" | ")]
        assert len(traps) == 3 and all(pair.match(trap) for trap in traps), (row["external_id"], traps)
    shard = json.loads((ROOT / "app/data/grammar_review/units_B1.json").read_text(encoding="utf-8"))
    assert {u["external_id"]: u["main_traps"] for u in shard["units"]} == {r["external_id"]: r["main_traps"] for r in b1}


# -- 6c. accents strict where the accent is the rule ---------------------------------


def test_the_spelling_unit_is_accent_strict():
    from app.services.answer_acceptance import accent_policy, judge

    assert accent_policy(unit="FR2_A12_ER_SPELLING") == "strict"
    assert accent_policy(unit=SimpleNamespace(external_id="FR2_A12_ER_SPELLING")) == "strict"
    assert accent_policy(unit="FR2_A11_ETRE") == "lenient"
    assert not judge("nous commencons", ["nous commençons"], accents=accent_policy(unit="FR2_A12_ER_SPELLING")).correct
    assert judge("il achete", ["il achète"]).correct, "elsewhere an accent slip is forgiven"


def test_a_journey_item_of_the_spelling_unit_is_graded_strictly():
    from app.services.journey_contracts import (
        AssistanceLevel,
        AttemptAnswer,
        InputMode,
        RecallTask,
        TargetKind,
        TargetRef,
        TaskOutcome,
    )
    from app.services.journey_learning import evaluate_recall

    target = TargetRef(kind=TargetKind.GRAMMAR, id="7", label_fr="-cer / -ger", concept_title=True)
    task = RecallTask(
        task_type="short_answer", instruction_native="Ergänze.", prompt_fr="Nous ___ à huit heures.", options=[],
        target=target, optional=True, accepted_answers=["commençons"], solution_fr="commençons",
    )
    db = SimpleNamespace(get=lambda model, key: SimpleNamespace(external_id="FR2_A12_ER_SPELLING"))
    user = SimpleNamespace(native_language="de", cefr_estimate="A1.1", proficiency_level="A1", id=uuid.uuid4())
    answer = AttemptAnswer(mode=InputMode.TEXT, text="commencons")
    strict = evaluate_recall(db, user=user, task=task, answer=answer, assistance=AssistanceLevel.NONE)
    assert strict.outcome is TaskOutcome.NOT_YET
    lenient = evaluate_recall(None, user=user, task=task, answer=answer, assistance=AssistanceLevel.NONE)
    assert lenient.outcome is TaskOutcome.MET


# -- 6d. a forgiven slip is named on a hit -------------------------------------------


def test_a_forgiven_slip_is_named_in_one_line_without_a_correction():
    from app.services.journey_contracts import (
        AssistanceLevel,
        AttemptAnswer,
        InputMode,
        RecallTask,
        TargetKind,
        TargetRef,
        TaskOutcome,
    )
    from app.services.journey_learning import evaluate_recall

    def task(accepted: str) -> RecallTask:
        target = TargetRef(kind=TargetKind.VOCABULARY, id="9", label_fr=accepted, label_native="x")
        return RecallTask(
            task_type="short_answer", instruction_native="Wie sagt man es?", prompt_fr=None, options=[],
            target=target, optional=True, accepted_answers=[accepted], solution_fr=accepted,
        )

    user = SimpleNamespace(native_language="de", cefr_estimate="A1.1", proficiency_level="A1", id=uuid.uuid4())
    accent = evaluate_recall(
        None, user=user, task=task("très bien"),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="tres bien"), assistance=AssistanceLevel.NONE,
    )
    assert accent.outcome is TaskOutcome.MET and accent.correction is None
    assert accent.slip_note_native == "Richtig — achte auf den Akzent: «très»."
    typo = evaluate_recall(
        None, user=user, task=task("appartement"),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="appartemnet"), assistance=AssistanceLevel.NONE,
    )
    assert typo.outcome is TaskOutcome.MET and typo.correction is None
    assert typo.slip_note_native == "Richtig — kleiner Tippfehler: «appartement»."
    exact = evaluate_recall(
        None, user=user, task=task("très bien"),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Très bien !"), assistance=AssistanceLevel.NONE,
    )
    assert exact.slip_note_native is None


def test_the_slip_note_reaches_the_wire_and_the_band():
    from app.schemas.daily_journey import AttemptResult

    assert "slip_note_native" in AttemptResult.model_fields
    steps = (ROOT / "web-frontend/components/atelier-v2/journey/JourneySteps.tsx").read_text(encoding="utf-8")
    assert "result.slip_note_native" in steps


# -- 6e. gender labels in the learner's language --------------------------------------


@pytest.mark.parametrize(
    ("language", "labels", "side"),
    [("de", ["männlich", "weiblich"], "native"), ("en", ["masculine", "feminine"], "native"), ("fr", ["masculin", "féminin"], None)],
)
def test_the_gender_classify_labels_are_in_the_learners_language(language, labels, side):
    from app.services.journey_contracts import TargetKind, TargetRef
    from app.services.journey_planner import build_classify_task

    target = TargetRef(kind=TargetKind.VOCABULARY, id="12", label_fr="la terrasse", label_native="die Terrasse")
    task = build_classify_task(target=target, optional=False, control_language=language)
    assert [option["text_fr"] for option in task.options] == labels
    assert all(option.get("side") == side for option in task.options)
    correct = next(option for option in task.options if option["id"] == task.correct_option_id)
    assert correct["text_fr"] == labels[1]


# -- 7. CI runs the long walk --------------------------------------------------------


def test_ci_runs_the_long_learner_walk():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "-m walk tests/test_learner_walk.py" in workflow
