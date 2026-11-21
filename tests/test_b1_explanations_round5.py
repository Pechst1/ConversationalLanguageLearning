"""R5 (check walk of 19 Nov, B1.1, English learner): explanations left in French.

* A scene word's gloss: «tremper — être mouillé complètement par la pluie» in the Cahier.
  The scene lexicon glosses in the scene's control language (French from B1); a lemma the
  catalogue lacked was entered with that French gloss in ``english_translation``, so the
  deck, the Cahier and the word sheet all read French. Reproduced from the walk DB
  (``vocabulary_words`` 6857, tag ``scene_lexicon``).
* A Rappel miss ended on «Règle : Deux pronoms ensemble : je le lui donne.» after an
  English note: the repair's rule line was built in the chrome.
* «Je pense que c'est juste» answered «Tu dois placer « lui » avant « en »…»: the appeal's
  reason language was the chrome (``verdict_appeals.reason_language = 'fr'`` in the walk DB).

Below B1 the chrome is the mother tongue, so nothing changes there.
"""

from __future__ import annotations

import inspect
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import journey_planner as planner
from app.services.journey_contracts import TargetKind, TargetRef
from app.services.journey_errata import ErrataTarget
from app.services.kept_words import record_scene_lexicon
from app.services.repair_context import RepairContext, repair_context_of
from tests.test_journey_planner import _brief

FRENCH_GLOSS = "être mouillé complètement par la pluie"


def _learner(db: Session, *, native: str, level: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"r5-explain-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language=native,
        target_language="fr",
        proficiency_level=level[:2],
        cefr_estimate=level,
        daily_goal_minutes=20,
    )
    db.add(user)
    db.commit()
    return user


def _lemma() -> str:
    # A lemma no list or other suite has: the walk's «tremper» case, the catalogue lacks it.
    return f"tremperx{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------- #
# Scene words
# --------------------------------------------------------------------------- #


def test_a_b1_scene_gloss_in_french_never_becomes_the_words_english_gloss(db_session: Session) -> None:
    user = _learner(db_session, native="en", level="B1.1")
    lemma = _lemma()
    words = record_scene_lexicon(
        db_session,
        user=user,
        entries=[{"lemma": lemma, "surface_fr": lemma, "gloss_native": FRENCH_GLOSS, "part_of_speech": "verbe"}],
        sentences={lemma: f"J'ai {lemma} deux fois."},
        level="B1",
        gloss_language="fr",
    )
    assert words == [], "no gloss in the mother tongue: the word is not recorded"
    rows = db_session.scalars(select(VocabularyWord).where(VocabularyWord.normalized_word == lemma)).all()
    assert rows == [], "no shared row is entered with a French «English» gloss"


def test_a_b1_scene_word_the_catalogue_knows_takes_its_english_gloss(db_session: Session) -> None:
    user = _learner(db_session, native="en", level="B1.1")
    lemma = _lemma()
    db_session.add(
        VocabularyWord(language="fr", word=lemma, normalized_word=lemma, english_translation="to soak", difficulty_level=3)
    )
    db_session.flush()
    words = record_scene_lexicon(
        db_session,
        user=user,
        entries=[{"lemma": lemma, "surface_fr": lemma, "gloss_native": FRENCH_GLOSS}],
        sentences={lemma: f"J'ai {lemma} deux fois."},
        level="B1",
        gloss_language="fr",
    )
    assert [word.gloss for word in words] == ["to soak"]


def test_an_a1_scene_gloss_in_the_mother_tongue_is_kept(db_session: Session) -> None:
    user = _learner(db_session, native="de", level="A1.1")
    lemma = _lemma()
    words = record_scene_lexicon(
        db_session,
        user=user,
        entries=[{"lemma": lemma, "surface_fr": lemma, "gloss_native": "durchnässen"}],
        sentences={lemma: f"J'ai {lemma} deux fois."},
        level="A1",
        gloss_language="de",
    )
    assert [word.gloss for word in words] == ["durchnässen"]
    row = db_session.get(VocabularyWord, words[0].word_id)
    assert row.german_translation == "durchnässen"


# --------------------------------------------------------------------------- #
# Rappel: the rule line closing a repair's miss note
# --------------------------------------------------------------------------- #

TITLES = (
    ("en", "Two pronouns together: je le lui donne"),
    ("de", "Zwei Pronomen zusammen: je le lui donne"),
    ("fr", "Deux pronoms ensemble : je le lui donne"),
)


def _repair_task(explain: str | None):
    target = TargetRef(kind=TargetKind.ERROR, id="e1", label_fr="lui en", label_native="Order of pronouns")
    return planner.build_recall_task(
        target=target,
        scenario=_brief(level_band="B1", control_language="fr"),
        affordances=[],
        optional=False,
        learner_text="en lui",
        repair=RepairContext(
            sentence="On en lui parle après le travail ?", rule=TITLES[0][1], rule_titles=TITLES, explain_language=explain
        ),
    )


def test_a_b1_repairs_rule_line_explains_in_the_mother_tongue() -> None:
    task = _repair_task("en")
    assert task is not None
    assert task.rule_native == "Rule: Two pronouns together: je le lui donne"
    # The goal above the card is interface: it stays French.
    assert "Règle : Deux pronoms ensemble" in (task.goal_native or "")
    german = _repair_task("de")
    assert german.rule_native == "Regel: Zwei Pronomen zusammen: je le lui donne"


def test_below_b1_the_rule_line_is_the_goals() -> None:
    task = _repair_task(None)
    assert task.rule_native == "Règle : Deux pronoms ensemble : je le lui donne"


def test_the_errata_carry_the_explanation_language_to_the_repair() -> None:
    target = ErrataTarget(
        error_id="e1", memory_key=None, concept_id=None, example_learner="en lui", example_correct="lui en",
        why=None, label="x", review_mode="grammar", state="learning", occurrences=1, lapses=0,
        overdue_days=0, priority=1.0, rule=TITLES[0][1], rule_titles=dict(TITLES), explain_language="en",
    )
    context = repair_context_of(target.as_candidate().metadata)
    assert context is not None and context.explain_language == "en"
    plain = ErrataTarget(**{**{f: getattr(target, f) for f in target.__slots__}, "explain_language": None})
    assert "erratum_explain_language" not in plain.as_candidate().metadata


# --------------------------------------------------------------------------- #
# «Je pense que c'est juste»: the appeal's reason
# --------------------------------------------------------------------------- #


def test_the_appeal_reason_is_asked_in_the_mother_tongue() -> None:
    from app.api.v1.endpoints import daily_journey as endpoint

    source = inspect.getsource(endpoint.appeal_verdict)
    assert "language=str(user_correction_language(current_user))" in source
    assert "user_chrome_language" not in source
