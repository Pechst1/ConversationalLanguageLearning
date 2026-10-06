"""EXERCISE-QA 2026-10-03 — one regression test per defect the learner walk found.

Each test names the walk finding it pins (see
``docs/implementation/atelier-v2/EXERCISE-QA-2026-10-03.md``).
"""
from __future__ import annotations

import csv
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import grammar_items
from app.services.journey_contracts import LearningCandidate, RecallTask, TargetKind, TargetRef
from app.services.journey_planner import PracticeItem, SelectedTarget, _repeats_the_day
from app.services.learner_copy import learner_text, word_count
from app.services.scene_items import SceneLine, build_cloze_task, build_line_unscramble_task

ROOT = Path(__file__).resolve().parents[1]


# -- F1: a B1 learner never met a Règle step ------------------------------------


def _v2_units() -> dict[str, dict[str, str]]:
    with (ROOT / "templates/french_core_grammar_v2.tsv").open(encoding="utf-8") as handle:
        return {row["external_id"]: row for row in csv.DictReader(handle, delimiter="\t")}


def test_every_b1_unit_has_two_contrast_pairs_for_its_essai():
    """The B1 ``main_traps`` carry one ✗ → ✓ each; the reviewed card's traps are
    the others. Without them a B1 Essai had one repair and was refused daily."""

    from app.services.grammar_units import contrast_pairs

    b1 = [unit for unit in _v2_units().values() if unit["cefr_level"] == "B1"]
    assert len(b1) >= 40
    short = []
    for unit in b1:
        concept = SimpleNamespace(external_id=unit["external_id"], main_traps=unit["main_traps"], source_refs={})
        if len(contrast_pairs(concept)) < 2:
            short.append(unit["external_id"])
    assert not short, short


def test_an_unintroducible_unit_does_not_hold_the_grammar_track(db_session, monkeypatch):
    """F1b: the first unit in line that cannot be introduced is passed over."""

    from app.db.models.user import User
    from app.services import concept_life
    from app.services.grammar_catalog import FrenchCoreGrammarCatalog

    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    try:
        user = User(
            id=uuid.uuid4(), email=f"qa-b1-{uuid.uuid4().hex}@example.com", hashed_password="x",
            native_language="en", target_language="fr", proficiency_level="B1", cefr_estimate="B1.1",
            daily_goal_minutes=10,
        )
        db_session.add(user)
        db_session.commit()
        brief = concept_life.introduction_for_today(db_session, user)
        assert brief is not None and str(brief["level"]).startswith("B1")
        assert concept_life.introducible(brief)

        real = concept_life.concept_brief
        first = {}

        def thin_first(db, concept, **kwargs):
            out = real(db, concept, **kwargs)
            if not first:
                first["id"] = out["concept_id"]
                return {**out, "contrast_pairs": out["contrast_pairs"][:1]}
            return out

        monkeypatch.setattr(concept_life, "concept_brief", thin_first)
        skipped = concept_life.introduction_for_today(db_session, user)
        assert skipped is not None and skipped["concept_id"] != first["id"]
    finally:
        monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v1")
        FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()


# -- F2: the B2/C1 Essai asked to rewrite the sentence it had just printed --------


def test_the_essai_never_asks_to_rewrite_what_the_card_or_warm_up_printed():
    pairs = [
        {"wrong": "Je suis content que tu es là.", "right": "Je suis content que tu sois là."},
        {"wrong": "C'est dommage qu'il ne peut pas rester.", "right": "C'est dommage qu'il ne puisse pas rester."},
        {"wrong": "J'ai peur qu'on est en retard.", "right": "J'ai peur qu'on soit en retard."},
    ]
    brief = {
        "concept_id": 116,
        "external_id": "FR2_B21_SUBJ_EMOTION",
        "level": "B2",
        "title_native": "Emotion + subjunctive",
        "contrast_pairs": pairs,
        "recognition_pair": None,
        "rule_card": {"contrast": {"wrong": pairs[0]["wrong"], "right": "Je suis content que tu [sois] là."}},
        "detectors": [],
    }
    items = grammar_items.guided_items(brief, sentences=[], language="en")
    shown = {grammar_items._fold("Je suis content que tu sois là.")}
    warm = [item for item in items if item.task_type == "choice"]
    shown |= {grammar_items._fold(str(item.solution_fr)) for item in warm}
    repairs = [item for item in items if item.task_type == "transform"]
    assert len(items) >= 2
    assert repairs and all(grammar_items._fold(str(item.solution_fr)) not in shown for item in repairs)


# -- F3: «Bring den Satz von clerk_2 …» and gaps with no sentence ------------------


TARGET = TargetRef(kind=TargetKind.VOCABULARY, id="7", label_fr="le propriétaire", label_native="Eigentümer")


def test_an_unnamed_speaker_is_never_printed_as_an_id():
    line = SceneLine(character_id="clerk_2", text_fr="Il faut un vrai propriétaire.", line_ref="p1:l0")
    task = build_line_unscramble_task(
        target=TARGET, line=line, speaker_name=None, optional=True, control_language="de",
        meaning="Es braucht einen echten Eigentümer.",
    )
    assert task is not None
    assert "clerk" not in task.instruction_native and "clerk" not in str(task.goal_native)
    assert "Eigentümer" in str(task.goal_native)
    assert build_line_unscramble_task(
        target=TARGET, line=line, speaker_name="clerk_2", optional=True, control_language="de",
    ) is None


@pytest.mark.parametrize("sentence", ["Propriétaire.", "Le propriétaire.", "Propriétaire chacune."])
def test_a_gap_needs_a_sentence_around_it(sentence):
    surface = "propriétaire" if sentence.startswith("Le") else "Propriétaire"
    assert build_cloze_task(
        target=TARGET, surface=surface, sentence=sentence, distractors=["voisin", "chat"],
        optional=True, control_language="de",
    ) is None


def test_a_gap_in_a_real_sentence_is_still_posed():
    task = build_cloze_task(
        target=TARGET, surface="propriétaire", sentence="Il faut un vrai propriétaire.",
        distractors=["voisin", "chat"], optional=True, control_language="de",
    )
    assert task is not None and "___" in str(task.prompt_fr)


# -- F4: the same item twice; producing a word the previous item printed ----------


def _entry(target: TargetRef) -> SelectedTarget:
    return SelectedTarget(
        candidate=LearningCandidate(target=target, priority_score=1.0, due_since_days=0, estimated_seconds=10),
        fit=1.0,
        demonstrated=False,
    )


def _task(task_type: str, target: TargetRef, cards: list[str], prompt: str | None = None) -> RecallTask:
    return RecallTask(
        task_type=task_type, instruction_native="Tippe die Paare an.", prompt_fr=prompt,
        options=[{"id": f"c{i}", "text_fr": text} for i, text in enumerate(cards)], target=target,
        optional=True, accepted_answers=[target.label_fr],
    )


def test_two_match_grids_over_the_same_words_are_one_item():
    other = TargetRef(kind=TargetKind.VOCABULARY, id="8", label_fr="le chat", label_native="Katze")
    cards = ["propriétaire", "chat", "Eigentümer", "Katze"]
    placed = [PracticeItem(slot="warmup", position=0, entry=_entry(TARGET), task=_task("match_pairs", TARGET, cards), cost=10)]
    assert _repeats_the_day(_task("match_pairs", other, list(reversed(cards))), _entry(other), placed, slot="warmup")


def test_no_production_of_a_word_in_the_block_that_printed_it():
    placed = [PracticeItem(slot="mid", position=0, entry=_entry(TARGET), task=_task("listen_tap", TARGET, ["Eigentümer", "Katze"], "le propriétaire"), cost=10)]
    asks = _task("short_answer", TARGET, [])
    assert _repeats_the_day(asks, _entry(TARGET), placed, slot="post")
    # The scene between the warm-ups and the after-block is the spacing that makes it recall.
    warm = [PracticeItem(slot="warmup", position=0, entry=_entry(TARGET), task=placed[0].task, cost=10)]
    assert not _repeats_the_day(asks, _entry(TARGET), warm, slot="post")


# -- F5: «Wort/Wörter» -------------------------------------------------------------


def test_word_counts_are_pluralised_in_each_language():
    assert word_count(1, "de") == "1 Wort" and word_count(3, "de") == "3 Wörter"
    assert word_count(0, "fr") == "0 mot" and word_count(2, "fr") == "2 mots"
    assert word_count(1, "en") == "1 word" and word_count(0, "en") == "0 words"
    line = learner_text("atelier.writing.too_short_why", "de", written_words=word_count(1, "de"), required=40)
    assert line == "1 Wort geschrieben; diese Aufgabe verlangt 40."


def test_the_journal_word_count_is_not_a_slash_plural():
    copy = (ROOT / "web-frontend/components/cahiers/cahier-copy.ts").read_text(encoding="utf-8")
    assert "Wort/Wörter" not in copy and "word(s)" not in copy and "mot(s)" not in copy
    tab = (ROOT / "web-frontend/components/cahiers/JournalTab.tsx").read_text(encoding="utf-8")
    assert "word_count_one" in tab


# -- F6: a forgiven slip is said, a refused one says why ----------------------------


def _recall(task_type: str, accepted: str, label_native: str = "sehr gut") -> RecallTask:
    target = TargetRef(kind=TargetKind.VOCABULARY, id="9", label_fr=accepted, label_native=label_native)
    return RecallTask(
        task_type=task_type, instruction_native="Wie sagt man es?", prompt_fr=None, options=[],
        target=target, optional=True, accepted_answers=[accepted], solution_fr=accepted,
    )


def test_a_forgiven_accent_is_met_without_a_correction():
    """The journey's correction policy: a met answer carries no correction
    (``test_journey_correction_policy``). The named slip («achte auf den Akzent»)
    is ready in ``answer_acceptance.feedback_note``; showing it is an owner call."""

    from app.services.journey_contracts import (
        AssistanceLevel,
        AttemptAnswer,
        InputMode,
        TaskOutcome,
    )
    from app.services.journey_learning import evaluate_recall

    user = SimpleNamespace(native_language="de", cefr_estimate="A1.1", proficiency_level="A1", id=uuid.uuid4())
    result = evaluate_recall(
        None, user=user, task=_recall("short_answer", "très bien"),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="tres bien"), assistance=AssistanceLevel.NONE,
    )
    assert result.outcome is TaskOutcome.MET
    assert result.correction is None


def test_a_refused_form_says_why():
    from app.services.journey_contracts import (
        AssistanceLevel,
        AttemptAnswer,
        InputMode,
        TaskOutcome,
    )
    from app.services.journey_learning import evaluate_recall

    user = SimpleNamespace(native_language="de", cefr_estimate="A1.1", proficiency_level="A1", id=uuid.uuid4())
    result = evaluate_recall(
        None, user=user, task=_recall("transform", "Il a mangé."),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Il à mangé."), assistance=AssistanceLevel.NONE,
    )
    assert result.outcome is TaskOutcome.NOT_YET
    assert result.correction is not None and result.correction.corrected_fr == "Il a mangé."
    assert "Akzent" in result.correction.note_native


# -- F7: «l'haricot» in the band check ------------------------------------------------


def test_the_band_check_never_elides_before_an_aspirated_h():
    from app.services.band_check import _shown

    assert _shown("haricot", {"pos": "noun", "gender": "m"}) == "le haricot"
    assert _shown("honte", {"pos": "noun", "gender": "f"}) == "la honte"
    assert _shown("homme", {"pos": "noun", "gender": "m"}) == "l'homme"
    assert _shown("heure", {"pos": "noun", "gender": "f"}) == "l'heure"
