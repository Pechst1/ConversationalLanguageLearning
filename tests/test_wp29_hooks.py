"""WP-29 §5 — the coverage hooks, applied to the story engine.

WP-29 shipped the arithmetic (``lexical_coverage.py``, 57 tests) and could not
register it: ``living_story.py`` was leased to WP-28. This pins the registration
itself, and the three ways it could have been got wrong:

1. **The guard runs, and names the words.** A scene carrying words this learner
   has never met is a scene they decode rather than read; the retry is told
   which words to replace and which to keep.
2. **It never costs a learner their day.** No lexicon, or a scene too short to
   measure, is *no verdict* — never a rejection. And it is measure-only until
   the 821-lemma core list has been calibrated (``COVERAGE_ENFORCED``).
3. **Nothing about the learner's vocabulary reaches a prompt.** ``KnownWordSet``
   is a frozen dataclass that ``json.dumps`` cannot serialise — the trap WP-29
   §5.1 flagged — and the actor must never be told which words the learner
   cannot read, for the same reason WP-28 kept the errata away from it.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.user import User
from app.services import living_story as engine
from app.services.journey_contracts import InputMode
from app.services.lexical_coverage import (
    SUPPORTED_COVERAGE_FLOOR,
    KnownWordSet,
    load_lexicon,
    text_coverage,
)
from tests import test_living_story as story_support
from tests.test_wp28_integration import make_user, record_erratum

Driver = story_support.Driver
assembled_client = story_support.assembled_client
clock = story_support.clock
journey_enabled = story_support.journey_enabled
provider = story_support.provider


# ---------------------------------------------------------------------------
# Fixtures: a known-word set a test fully controls
# ---------------------------------------------------------------------------

# Ordinary A1 French. Everything in it is granted to the learner below, so a
# test's unknown words are only ever the ones the test puts there.
PLAIN_A1 = (
    "Le matin je prends un café avec mon ami dans la petite ville. "
    "Nous parlons de la maison et du travail. "
    "Je demande l'heure et il donne une réponse simple. "
    "Après nous allons au parc et nous marchons un peu."
)

# Three words an A1 learner has not met, and that the core list does not grant.
# Everything else in the sentence is the carrier, and is granted below, so the
# sentence contributes exactly three unknown words and no more.
ACCIDENTAL = "Aussitôt il y a un vacarme dans la démarche."
ACCIDENTAL_CARRIER = "il y a un dans la"
ACCIDENTAL_SURFACES = ("Aussitôt", "vacarme", "démarche")
# The lemmas those surfaces resolve to. A target is matched as a lemma, which is
# the form both target sources produce: an erratum's correction and a vocabulary
# card's headword are dictionary forms, not inflections.
ACCIDENTAL_LEMMAS = frozenset({"aussitôt", "vacarme", "démarche"})


def known_for(text: str, *, band: str = "A1") -> KnownWordSet:
    """Every word of ``text`` known, plus the band's core list, and nothing else.

    Built by measuring ``text`` against the bare core list and granting whatever
    came back unknown, so the fixture cannot drift when the vendored lexicon
    grows: a test's unknown words stay exactly the ones it wrote.
    """

    core = load_lexicon().core_lemmas(band)
    seed = KnownWordSet(
        lemmas=frozenset(core),
        band=band,
        estimate_level=band,
        estimate_source="placement",
        nailed_count=0,
        core_count=len(core),
    )
    lemmas = set(core) | {word.lemma for word in text_coverage(text, seed).unknown}
    return KnownWordSet(
        lemmas=frozenset(lemmas),
        band=band,
        estimate_level=band,
        estimate_source="placement",
        nailed_count=0,
        core_count=len(core),
    )


def record_erratum_with(db: Session, user: User, *, correction: str) -> None:
    """WP-28's ``record_erratum``, with a correction this test picks.

    Its fixture corrects to «un homme», and "homme" is on the A1 core list — so a
    target the learner already knows can never show the target/accident split.
    """

    from app.db.models.error import UserError
    from app.services.error_memory import ERROR_STATE_OPEN, ErrorMemoryService

    ErrorMemoryService(db).record_erratum(
        user=user,
        erratum={
            "display_label": "Le nom masculin",
            "learner_text": correction.replace("un ", "une "),
            "corrected_target": correction,
            "why_wrong": "this noun is masculine",
            "repair_hint": correction,
            "task_error_type": "gender",
            "severity": 2,
        },
        source_type="daily_journey",
    )
    db.commit()
    error = (
        db.query(UserError)
        .filter(UserError.user_id == user.id)
        .order_by(UserError.created_at.desc())
        .first()
    )
    assert error is not None
    error.state = ERROR_STATE_OPEN
    error.next_review_date = datetime.now(UTC) - timedelta(days=1)
    db.commit()


def context_with(known: KnownWordSet, *, targets: frozenset[str] = frozenset()) -> dict:
    return {
        engine.LEXICON_KEY: {
            "known": known,
            "targets": targets,
            "proper_nouns": frozenset({"Romy"}),
        }
    }


@pytest.fixture()
def enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard as it will behave once the core list has been calibrated."""

    monkeypatch.setattr(engine, "COVERAGE_ENFORCED", True)


# ---------------------------------------------------------------------------
# 1. §5.1 — the guard rejects, and says what to do about it
# ---------------------------------------------------------------------------


def test_a_scene_carrying_three_unplanned_b1_words_is_rejected_by_name(enforced: None) -> None:
    """The A1 budget is one accidental unknown; three is a scene to rewrite.

    And the hint has to name them. Every rejecting guard in this engine owes the
    retry an instruction rather than a bare token (STATUS 2026-09-07, defect 1):
    the paid A2 run lost five days to a retry that only ever saw
    ``repeated_premise_triple``.
    """

    known = known_for(f"{PLAIN_A1} {ACCIDENTAL_CARRIER}")
    with pytest.raises(engine.StoryUnavailable) as raised:
        engine._check_coverage([PLAIN_A1, ACCIDENTAL], context_with(known))

    assert str(raised.value) in {"lexical_coverage_low", "too_many_new_words"}
    hint = raised.value.hint or ""
    for surface in ACCIDENTAL_SURFACES:
        assert surface in hint, hint
    # An instruction, not a verdict: it says what to do with them.
    assert "everyday equivalents" in hint or "words this" in hint


def test_the_same_words_pass_when_they_are_what_today_is_teaching() -> None:
    """Targets are the difference between "three new words" and "today's lesson".

    Identical text, identical known set: the only change is that the day's plan
    chose these words. They still count against coverage — they *are* unknown
    running words — but they no longer spend the accidental budget, which is what
    the budget is for.
    """

    known = known_for(f"{PLAIN_A1} {ACCIDENTAL_CARRIER}")
    lexicon = context_with(known, targets=ACCIDENTAL_LEMMAS)

    # Long enough that three target unknowns stay above the 95 % floor.
    text = [PLAIN_A1, PLAIN_A1, PLAIN_A1, ACCIDENTAL]
    context = dict(lexicon)
    engine._check_coverage(text, context)  # no raise

    metadata = context[engine.COVERAGE_KEY]
    assert metadata["coverage"] >= SUPPORTED_COVERAGE_FLOOR
    assert metadata["target_count"] == 3
    assert metadata["accidental_count"] == 0
    assert metadata["verdict"] == "accepted"


def test_a_day_one_learner_is_never_rejected_for_having_no_lexicon() -> None:
    """Fails open, in both of its shapes.

    No lexicon on the context at all (the guard is simply not registered for this
    caller — every pre-existing ``_validate_scene`` test looks like this), and a
    scene too short to measure. Neither is a bad scene, and a guard that failed
    closed here would empty the product on a bad data day.
    """

    bare: dict = {}
    engine._check_coverage([PLAIN_A1, ACCIDENTAL], bare)
    assert engine.COVERAGE_KEY not in bare

    short = context_with(known_for(f"{PLAIN_A1} {ACCIDENTAL_CARRIER}"))
    engine._check_coverage(["Bonjour Romy."], short)
    # "Not measured" is neither 0 % nor 100 %.
    assert short[engine.COVERAGE_KEY] is None


def test_coverage_is_measured_even_when_it_may_not_reject() -> None:
    """The distribution is recorded from the first scene, not from the first flip.

    ``COVERAGE_ENFORCED`` is False while the 821-lemma core list is uncalibrated
    (7 of 7 A1 fixture scenes reject against it). A guard that rejected first and
    measured afterwards could never produce the numbers that would calibrate it.
    """

    assert engine.COVERAGE_ENFORCED is False

    context = context_with(known_for(f"{PLAIN_A1} {ACCIDENTAL_CARRIER}"))
    engine._check_coverage([PLAIN_A1, ACCIDENTAL], context)  # no raise

    metadata = context[engine.COVERAGE_KEY]
    assert metadata["verdict"] == "rejected"
    assert metadata["enforced"] is False
    assert metadata["accidental_count"] == 3
    assert metadata["estimate_source"] == "placement"
    assert [word["surface"] for word in metadata["accidental_unknowns"]]


# ---------------------------------------------------------------------------
# 2. §5.3 — the targets are the ones the day was planned from
# ---------------------------------------------------------------------------


def test_the_targets_are_the_errata_the_plan_actually_chose(db_session: Session) -> None:
    """WP-28 wired one errata read into the director and the prefetch key.

    The coverage guard reuses that same target set rather than reading the queue
    a second time, so it can never excuse a word the plan never chose. The
    erratum's *correction* is the French; its label names the rule, and
    whitelisting "accord" or "participe" would excuse words no scene is teaching.
    """

    user = make_user(db_session, "wp29-targets@example.com")
    assert engine.coverage_targets(db_session, user, errata=[]) == frozenset()

    record_erratum(db_session, user)
    errata = engine.due_errata(db_session, user)
    assert errata, "the erratum this test recorded should be due"

    targets = engine.coverage_targets(db_session, user, errata=errata)
    assert "un homme" in targets
    # The rule's name is not vocabulary the scene is teaching.
    assert not any("participe" in token.casefold() for token in targets)


def test_a_target_word_is_excused_from_the_budget_and_an_unplanned_one_is_not(
    db_session: Session,
) -> None:
    """The end of the chain the previous test starts.

    A correction the plan chose reaches the verdict as a *target* — still an
    unknown running word, but not one spending the accidental budget — while the
    same scene's unplanned words still do. Phrases are folded to lookup keys by
    the coverage module, not by the engine, so the erratum's «un vacarme» matches
    the scene's "vacarme".
    """

    user = make_user(db_session, "wp29-target-verdict@example.com")
    record_erratum_with(db_session, user, correction="un vacarme")
    targets = engine.coverage_targets(db_session, user, errata=engine.due_errata(db_session, user))
    assert "un vacarme" in targets

    known = known_for(f"{PLAIN_A1} {ACCIDENTAL_CARRIER}")
    context = context_with(known, targets=targets)
    engine._check_coverage([PLAIN_A1, ACCIDENTAL], context)
    metadata = context[engine.COVERAGE_KEY]

    assert "vacarme" in {word["lemma"] for word in metadata["target_unknowns"]}
    assert "vacarme" not in {word["lemma"] for word in metadata["accidental_unknowns"]}
    # The two words nobody planned are still accidents.
    assert metadata["accidental_count"] == 2


def test_an_unreadable_queue_makes_the_guard_stricter_never_wronger(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A target is a lenience, so every read behind it fails open to nothing."""

    user = make_user(db_session, "wp29-targets-broken@example.com")

    def explode(*args, **kwargs):
        raise RuntimeError("queue is down")

    monkeypatch.setattr(engine, "due_errata", explode)
    import app.services.unified_srs as unified_srs

    monkeypatch.setattr(unified_srs.UnifiedSRSService, "get_journey_candidate_pool", explode)

    assert engine.coverage_targets(db_session, user, errata=[]) == frozenset()
    # And the lexicon as a whole: no known set means no verdict, never a refusal.
    assert engine.scene_lexicon(db_session, user, {"world": {}}, errata=[])["known"] is not None


# ---------------------------------------------------------------------------
# 3. §5.1's trap and §5.2 — serialisation, storage, and the prompts
# ---------------------------------------------------------------------------


def test_the_brief_still_serialises_with_a_lexicon_on_the_context(
    db_session: Session, provider, clock
) -> None:
    """The one part of the hook that breaks loudly if it is skipped.

    ``context`` is stored verbatim on ``brief.story_context["source"]`` and that
    dict is JSON-dumped into the prefetch cache and the stored scene.
    ``KnownWordSet`` is a frozen dataclass, so the lexicon has to be swapped for
    its provenance on the way out — the counts and the authority, not the eight
    hundred lemmas.
    """

    user = make_user(db_session, "wp29-serialise@example.com")
    brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    assert getattr(brief, "story_context", None), brief

    json.dumps(brief.story_context)  # the trap: would raise TypeError unhandled

    stored = brief.story_context["source"][engine.LEXICON_KEY]
    assert stored["known"]["band"] == "A1"
    assert stored["known"]["estimate_source"]
    assert stored["known"]["known_lemmas"] > 0
    assert "lemmas" not in stored["known"], "the word list itself is not worth storing"

    # §5.2: the measurement rides out on the brief without being threaded through.
    metadata = brief.story_context[engine.COVERAGE_KEY]
    assert metadata is None or metadata["version"] == "lexical-coverage-v1"


def test_the_stored_scene_carries_what_the_learner_was_actually_served(
    assembled_client, db_session, journey_enabled, clock, provider
) -> None:
    """§5.2's second half: ``script_payload``, so the report reads it back.

    Recomputing coverage later measures the scene against the learner's *current*
    vocabulary, which is a different number from the one they were served.
    """

    d = story_support.driver(assembled_client, db_session)
    d.create()

    scene = db_session.scalars(
        select(GraphicNovelScene)
        .where(GraphicNovelScene.user_id == d.user_id)
        .order_by(GraphicNovelScene.created_at.desc())
    ).first()
    assert scene is not None
    assert engine.COVERAGE_KEY in (scene.script_payload or {})

    from app.services.lexical_coverage import stored_scene_coverage

    stored = stored_scene_coverage(scene)
    if stored is not None:
        assert stored["coverage"] > 0
        assert stored["band"]


def test_no_prompt_is_ever_told_what_this_learner_cannot_read(
    assembled_client, db_session, journey_enabled, clock, provider
) -> None:
    """Pinned the way WP-28 pinned the errata's absence from the actor.

    The director has no use for eight hundred lemmas, and the actor must not have
    them at all: it grades what was actually said, and a grader primed with the
    words the learner cannot read is not a grader.
    """

    d = story_support.driver(assembled_client, db_session)
    d.create()
    d.play(answer="Je peux apporter les affiches samedi.")

    seen = [(schema, payload) for schema, payload in provider.calls]
    assert any(schema == "SceneDraft" for schema, _ in seen)
    assert any(schema == "SemanticTurn" for schema, _ in seen)

    for schema, payload in seen:
        blob = json.dumps(payload, ensure_ascii=False, default=str)
        assert engine.LEXICON_KEY not in payload, schema
        assert engine.COVERAGE_KEY not in payload, schema
        assert "accidental_unknowns" not in blob, schema
        assert "known_lemmas" not in blob, schema

    actor = next(payload for schema, payload in seen if schema == "SemanticTurn")
    assert engine.LEXICON_KEY not in actor["story"]
    assert engine.COVERAGE_KEY not in actor["story"]
