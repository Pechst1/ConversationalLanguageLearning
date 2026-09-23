"""WP-29 — coverage-controlled generation.

The acceptance list of the spec, in order: coverage math, lemma folding
(accents, elision ``l'``/``qu'``/``d'``/``j'``/``n'``), the target/accidental
split, the per-band guard thresholds, an A1 learner rejecting a scene with three
accidental B1 words *by name*, and a scene whose only unknowns are today's
targets passing.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.lexical_coverage import (
    ACCIDENTAL_UNKNOWN_BUDGET,
    COVERAGE_VERSION,
    MIN_ASSESSED_TOKENS,
    REJECT_LOW_COVERAGE,
    REJECT_UNKNOWN_BUDGET,
    SCENE_METADATA_KEY,
    SUPPORTED_COVERAGE_FLOOR,
    CoverageResult,
    CuratedResolver,
    KnownWordSet,
    LearnerLexicon,
    SceneText,
    SpacyResolver,
    accidental_budget,
    band_of,
    check_scene_coverage,
    coverage_distribution,
    fold,
    format_coverage_line,
    known_word_set,
    load_lexicon,
    nailed_lemmas,
    recent_scene_coverage,
    scene_text_from_draft,
    stored_scene_coverage,
    text_coverage,
    tokenize,
    world_proper_nouns,
)

RESOLVER = CuratedResolver()


def _known(*extra: str, band: str = "A1", source: str = "placement") -> KnownWordSet:
    """A learner who has the core list for ``band`` and nothing else."""

    core = load_lexicon().core_lemmas(band)
    return KnownWordSet(
        lemmas=frozenset(core | {fold(word) for word in extra}),
        band=band,
        estimate_level=f"{band}.1",
        estimate_source=source,
        nailed_count=len(extra),
        core_count=len(core),
    )


def _lexicon_only(*lemmas: str, band: str = "A1") -> KnownWordSet:
    """A hand-built known set, for coverage arithmetic with no core list noise."""

    return KnownWordSet(
        lemmas=frozenset(fold(lemma) for lemma in lemmas),
        band=band,
        estimate_level=f"{band}.1",
        estimate_source="measured",
        nailed_count=len(lemmas),
        core_count=0,
    )


def _user(db_session, *, email: str, level: str = "A1", estimate: str = "A1.1") -> User:
    user = User(
        id=uuid4(),
        email=email,
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level=level,
        cefr_estimate=estimate,
        cefr_target_level="A2.1",
        daily_goal_minutes=20,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# 1. The vendored lexicon
# ---------------------------------------------------------------------------


def test_lexicon_declares_its_provenance_and_is_not_empty():
    lexicon = load_lexicon()

    # WP-L2 extended the list to ~2,500 lemmas through B1 and added sub_band.
    assert lexicon.version == "fr-core-lexicon-v2"
    assert len(lexicon.lemmas) > 500
    # A word list with no stated origin is a word list nobody can audit.
    assert lexicon.provenance["function_words"].startswith("Seeded from spaCy")
    assert "licence" in lexicon.provenance
    # `rank` is list order, not a corpus count, and the file has to say so.
    assert "frequency proxy" in lexicon.provenance["summary"]


def test_core_lemmas_accumulate_upward_through_the_bands():
    lexicon = load_lexicon()

    a1 = lexicon.core_lemmas("A1")
    b1 = lexicon.core_lemmas("B1")

    assert a1 < b1
    assert "café" in a1
    assert "démarche" in b1 and "démarche" not in a1
    # A band above the list's top still gets everything, never nothing.
    assert lexicon.core_lemmas("C1") == lexicon.core_lemmas("B1")


@pytest.mark.parametrize(
    ("level", "expected"),
    [("A1.1", "A1"), ("a2", "A2"), ("B1.2", "B1"), ("", "A1"), (None, "A1"), ("junk", "A1")],
)
def test_band_of_reads_the_half_step_scale_and_clamps(level, expected):
    assert band_of(level) == expected


# ---------------------------------------------------------------------------
# 2. Lemma folding: accents, elision, clitics
# ---------------------------------------------------------------------------


def test_elision_resolves_to_the_underlying_function_word():
    keys = [token.key for token in tokenize("L'addition, j'ai d'argent, n'est-ce qu'un rêve ?")]

    assert keys[:2] == ["le", "addition"]
    assert "je" in keys and "de" in keys and "ne" in keys and "que" in keys
    # The apostrophe never survives as part of a content word.
    assert not any(key.startswith("l'") for key in keys)


def test_hyphenated_clitics_split_but_real_compounds_do_not():
    keys = [token.key for token in tokenize("Qu'est-ce qu'on fait ? Va-t-il au rendez-vous ?")]

    assert "est" in keys and "ce" in keys
    # The euphonic -t- of "va-t-il" is grammar, not a word.
    assert "t" not in keys
    assert "rendez-vous" in keys
    assert "rendre" not in keys


def test_words_that_merely_contain_an_apostrophe_stay_whole():
    keys = [token.key for token in tokenize("Aujourd'hui, quelqu'un attend d'abord.")]

    assert "aujourd'hui" in keys
    assert "quelqu'un" in keys
    assert "d'abord" in keys


def test_typographic_and_ascii_apostrophes_fold_together():
    assert [t.key for t in tokenize("L’addition")] == [t.key for t in tokenize("L'addition")]


def test_accents_are_kept_and_only_fold_as_a_last_resort_for_longer_words():
    known = _lexicon_only("etudier", "sur", "ou")

    # A long word matches its unaccented twin: "étudier" is not a different word.
    long_word = text_coverage("étudier étudier étudier", known, resolver=RESOLVER)
    assert long_word.coverage == 1.0

    # Short minimal pairs do not vouch for one another: "sûr" is not "sur",
    # and "où" is not "ou".
    short = text_coverage("sûr où", known, resolver=RESOLVER)
    assert short.known_words == 0
    assert {word.lemma for word in short.unknown} == {"sûr", "où"}


def test_inflected_forms_resolve_to_the_lemma_the_learner_knows():
    known = _lexicon_only("aller", "manger", "beau", "journal", "finir")
    text = "allé mangé belle journaux finissons"

    result = text_coverage(text, known, resolver=RESOLVER)

    assert result.coverage == 1.0
    assert result.unknown == ()


# ---------------------------------------------------------------------------
# 3. Coverage math
# ---------------------------------------------------------------------------


def test_coverage_is_the_share_of_running_words_the_learner_knows():
    known = _lexicon_only("le", "chat", "être", "noir")

    result = text_coverage("Le chat est noir. Le chien est brun.", known, resolver=RESOLVER)

    assert result.running_words == 8
    assert result.known_words == 6
    assert result.unknown_words == 2
    assert result.coverage == pytest.approx(0.75)


def test_coverage_counts_tokens_while_the_unknown_list_counts_types():
    known = _lexicon_only("le", "être")

    result = text_coverage("Le chat est le chat. Le chat est le chat.", known, resolver=RESOLVER)

    assert result.running_words == 10
    assert len(result.unknown) == 1  # one type
    assert result.unknown[0].count == 4  # four tokens
    assert result.unknown_words == 4


def test_proper_nouns_count_as_known_and_are_reported_separately():
    known = _lexicon_only("être", "le", "café", "au")

    result = text_coverage(
        "Romy est au café.", known, proper_nouns=["Romy"], resolver=RESOLVER
    )

    assert result.coverage == 1.0
    assert result.proper_noun_words == 1
    assert result.unknown == ()


def test_empty_text_is_zero_coverage_and_is_never_assessable():
    result = text_coverage("", _known(), resolver=RESOLVER)

    assert result.running_words == 0
    assert result.coverage == 0.0
    assert result.is_assessable is False


def test_unknown_words_are_ranked_by_frequency_with_off_list_words_last():
    known = _lexicon_only("le")

    result = text_coverage("Le zorglub le démarche le café", known, resolver=RESOLVER)

    lemmas = [word.lemma for word in result.unknown]
    # "café" is A1 core, "démarche" is B1 core, "zorglub" is on no list at all.
    assert lemmas.index("café") < lemmas.index("démarche") < lemmas.index("zorglub")
    assert result.unknown[-1].rank is None


# ---------------------------------------------------------------------------
# 4. Target vs accidental
# ---------------------------------------------------------------------------


def test_unknown_words_split_into_targets_and_accidents():
    known = _lexicon_only("le", "être")

    result = text_coverage(
        "Le chauffage est cassé.", known, targets=["chauffage"], resolver=RESOLVER
    )

    assert [word.lemma for word in result.targets] == ["chauffage"]
    assert {word.lemma for word in result.accidental} == {"cassé"}


def test_a_target_still_counts_against_coverage():
    """The 95 % figure is about running words; a target is still an unknown word."""

    known = _lexicon_only("le", "être")

    result = text_coverage("Le chauffage est le chauffage est", known, targets=["chauffage"])

    assert result.coverage == pytest.approx(4 / 6)
    assert result.targets[0].count == 2


def test_a_target_matches_the_inflected_form_in_the_scene():
    known = _lexicon_only("le", "être")

    result = text_coverage("Les factures sont", known, targets=["facture"], resolver=RESOLVER)

    assert [word.lemma for word in result.targets] == ["facture"]
    assert result.accidental == ()


# ---------------------------------------------------------------------------
# 5. The guard
# ---------------------------------------------------------------------------

# An A1 scene in this world's own register: café, a character, a small request.
A1_SCENE = (
    "Romy est au café. Elle regarde la carte et elle sourit. "
    "« Bonjour ! Vous voulez quelque chose à boire ? » "
    "Tu as soif. Tu veux un café et un verre d'eau. "
    "« Un café, s'il vous plaît. Et l'addition, aussi. » "
    "Romy apporte le café. Elle demande si tout va bien."
)


def test_an_a1_scene_written_in_a1_words_is_accepted():
    verdict = check_scene_coverage(
        SceneText(text=A1_SCENE, proper_nouns=frozenset({"romy"})),
        LearnerLexicon(known=_known(), resolver=RESOLVER),
    )

    assert verdict.accepted is True
    assert verdict.reason is None
    assert verdict.result.coverage >= SUPPORTED_COVERAGE_FLOOR


def test_three_accidental_b1_words_are_rejected_and_the_hint_names_them():
    """The acceptance case of the spec, verbatim."""

    scene = (
        "Romy est au café. Elle est bouleversée par la démarche du propriétaire. "
        "« Bonjour ! Vous voulez quelque chose à boire ? » "
        "Aussitôt, tu penses à l'addition. Tu veux un café et un verre d'eau. "
        "« Un café, s'il vous plaît. » Romy apporte le café et demande si tout va bien."
    )

    verdict = check_scene_coverage(
        SceneText(text=scene, proper_nouns=frozenset({"romy"})),
        LearnerLexicon(known=_known(), targets=frozenset({"propriétaire"}), resolver=RESOLVER),
    )

    assert verdict.rejected is True
    assert verdict.reason in {REJECT_LOW_COVERAGE, REJECT_UNKNOWN_BUDGET}
    # Every rejecting guard in this codebase owes the retry an instruction
    # (STATUS 2026-09-07, defect 1), and this one has to name the words.
    assert verdict.hint
    for word in ("bouleversée", "démarche", "Aussitôt"):
        assert word in verdict.hint
    # ...and tell the retry what to keep.
    assert "propriétaire" in verdict.hint
    assert "target" in verdict.hint


def test_a_scene_whose_only_unknowns_are_todays_targets_passes():
    """The other half of the acceptance case: targets are a budget, not a fault."""

    scene = (
        "Romy est au café. Elle regarde la carte. "
        "« Bonjour ! Vous voulez quelque chose ? » "
        "Tu veux un café. Le chauffage est cassé et Romy demande si tu as froid. "
        "« Un café, s'il vous plaît. » Elle apporte le café et tout va bien."
    )
    learner = LearnerLexicon(
        known=_known(),
        targets=frozenset({"chauffage", "cassé"}),
        resolver=RESOLVER,
    )

    verdict = check_scene_coverage(
        SceneText(text=scene, proper_nouns=frozenset({"romy"})), learner
    )

    assert verdict.accepted is True
    assert {word.lemma for word in verdict.result.targets} == {"chauffage", "cassé"}
    assert verdict.result.accidental == ()


def test_the_guard_rejects_on_the_budget_even_when_coverage_clears_the_floor():
    """Two independent axes: a long scene can be ≥95 % and still teach too much."""

    filler = "Le chat est là et le chien est là et la femme est là et l'homme est là. " * 4
    scene = filler + "Le zorglub et le brindok sont sur la table."
    learner = LearnerLexicon(known=_known(), resolver=RESOLVER)

    verdict = check_scene_coverage(SceneText(text=scene), learner)

    assert verdict.result.coverage >= SUPPORTED_COVERAGE_FLOOR
    assert verdict.rejected is True
    assert verdict.reason == REJECT_UNKNOWN_BUDGET
    assert "zorglub" in verdict.hint and "brindok" in verdict.hint


@pytest.mark.parametrize(("band", "budget"), sorted(ACCIDENTAL_UNKNOWN_BUDGET.items()))
def test_the_accidental_budget_scales_with_the_band(band, budget):
    assert accidental_budget(band) == budget
    assert accidental_budget(f"{band}.2") == budget
    # Monotonic: a higher band never gets a smaller allowance.
    assert budget >= accidental_budget("A1")


def test_the_same_scene_passes_at_b1_and_fails_at_a1():
    """The threshold is per band, not global."""

    scene = (
        "Romy est au café. Elle est bouleversée par la démarche du propriétaire. "
        "« Bonjour ! Vous voulez quelque chose à boire ? » "
        "Aussitôt, tu penses à l'addition. Tu veux un café et un verre d'eau. "
        "« Un café, s'il vous plaît. » Romy apporte le café et demande si tout va bien."
    )
    scene_text = SceneText(text=scene, proper_nouns=frozenset({"romy"}))

    at_a1 = check_scene_coverage(scene_text, LearnerLexicon(known=_known(), resolver=RESOLVER))
    at_b1 = check_scene_coverage(
        scene_text, LearnerLexicon(known=_known(band="B1"), resolver=RESOLVER)
    )

    assert at_a1.rejected is True
    assert at_b1.accepted is True


def test_text_below_the_measurement_floor_is_not_assessed_and_never_rejected():
    short = "Bonjour. Ça va ?"
    assert len(tokenize(short)) < MIN_ASSESSED_TOKENS

    verdict = check_scene_coverage(SceneText(text=short), LearnerLexicon(known=_known()))

    assert verdict.status == "not_assessed"
    assert verdict.reason == "text_too_short"
    assert verdict.rejected is False


def test_an_unusable_known_set_abstains_rather_than_rejecting_everything():
    """A missing lexicon must not turn into "the learner knows nothing"."""

    empty = KnownWordSet(
        lemmas=frozenset(),
        band="A1",
        estimate_level="A1.1",
        estimate_source="declared",
        nailed_count=0,
        core_count=0,
    )

    verdict = check_scene_coverage(SceneText(text=A1_SCENE), LearnerLexicon(known=empty))

    assert verdict.status == "not_assessed"
    assert verdict.reason == "known_set_unavailable"
    assert verdict.rejected is False


# ---------------------------------------------------------------------------
# 6. Scene metadata (spec §3.4)
# ---------------------------------------------------------------------------


class _Line:
    def __init__(self, text_fr: str) -> None:
        self.text_fr = text_fr


class _Panel:
    def __init__(self, narration_fr: str, dialogue: list[str]) -> None:
        self.narration_fr = narration_fr
        self.dialogue = [_Line(text) for text in dialogue]


class _Draft:
    """Structurally a living_story.SceneDraft, without importing the leased file."""

    premise_fr = "Romy est au café."
    opening_line_fr = "Bonjour !"
    suggested_response_fr = "Un café, s'il vous plaît."
    panels = [_Panel("Elle regarde la carte.", ["Vous voulez quelque chose ?"])]


def test_scene_text_is_collected_from_the_draft_without_importing_living_story():
    scene = scene_text_from_draft(_Draft(), proper_nouns=["Romy"])

    for fragment in ("Romy est au café", "Bonjour", "Vous voulez", "Elle regarde"):
        assert fragment in scene.text
    assert "romy" in scene.proper_nouns


def test_world_proper_nouns_reads_cast_and_locations_off_a_story_context():
    context = {
        "world": {
            "cast": [{"id": "romy", "name": "Romy"}],
            "locations": [{"id": "cafe_des_arts", "name": "Café des Arts"}],
        }
    }

    names = world_proper_nouns(context)

    assert {"romy", "café", "arts"} <= names
    assert world_proper_nouns(None) == frozenset()


def test_scene_metadata_carries_coverage_unknown_count_and_the_target_list():
    result = text_coverage(
        "Le chauffage est cassé dans la chambre et le zorglub est là aussi.",
        _known(),
        targets=["chauffage"],
        resolver=RESOLVER,
    )

    metadata = result.as_metadata()

    assert metadata["version"] == COVERAGE_VERSION
    assert 0.0 <= metadata["coverage"] <= 1.0
    assert metadata["unknown_words"] == result.unknown_words
    assert [item["lemma"] for item in metadata["target_unknowns"]] == ["chauffage"]
    assert "zorglub" in {item["lemma"] for item in metadata["accidental_unknowns"]}
    assert metadata["band"] == "A1"
    assert metadata["estimate_source"] == "placement"
    assert metadata["floor"] == SUPPORTED_COVERAGE_FLOOR
    assert metadata["budget"] == ACCIDENTAL_UNKNOWN_BUDGET["A1"]


def test_scene_metadata_is_json_small_even_when_a_scene_is_full_of_new_words():
    known = _lexicon_only("le")
    invented = " ".join(f"zorglub{'x' * index}" for index in range(40))
    result = text_coverage(f"le {invented}", known)

    metadata = result.as_metadata()

    assert metadata["accidental_count"] == 40
    assert len(metadata["accidental_unknowns"]) <= 6
    assert metadata["unknown_lemmas"] == 40


# ---------------------------------------------------------------------------
# 7. The known-word set, from the learner's own rows
# ---------------------------------------------------------------------------


def _word(db_session, surface: str, word_id: int) -> VocabularyWord:
    word = VocabularyWord(
        id=word_id,
        language="fr",
        word=surface,
        normalized_word=surface,
        direction="fr_to_de",
        german_translation="x",
        difficulty_level=1,
    )
    db_session.add(word)
    db_session.commit()
    return word


def test_a_nailed_fsrs_row_puts_its_word_in_the_known_set(db_session):
    user = _user(db_session, email="cov-nailed@example.com")
    _word(db_session, "chauffage", 900_101)
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=900_101,
            # Retrievability well above NAILED_RETRIEVABILITY: reviewed
            # yesterday with a 30-day stability, never lapsed.
            stability=30.0,
            reps=4,
            lapses=0,
            state="review",
            last_review_date=datetime.now(UTC) - timedelta(days=1),
        )
    )
    db_session.commit()

    assert "chauffage" in nailed_lemmas(db_session, user=user)


def test_a_word_the_learner_has_not_nailed_stays_out_of_the_known_set(db_session):
    user = _user(db_session, email="cov-not-nailed@example.com")
    _word(db_session, "brindok", 900_102)
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=900_102,
            stability=0.5,
            reps=1,
            lapses=2,
            state="relearning",
            last_review_date=datetime.now(UTC) - timedelta(days=10),
        )
    )
    db_session.commit()

    assert "brindok" not in nailed_lemmas(db_session, user=user)


def test_the_known_set_names_the_authority_behind_the_band(db_session):
    """A declaration is not evidence, and the payload has to keep saying so."""

    user = _user(db_session, email="cov-source@example.com", level="B1", estimate="")
    user.cefr_estimate_payload = None
    db_session.commit()

    known = known_word_set(db_session, user=user)

    assert known.estimate_source in {"declared", "measured", "placement", "lazy"}
    assert known.as_dict()["estimate_source"] == known.estimate_source
    assert known.as_dict()["nailed_rule"]["retrievability"] == 0.9


def test_a_day_one_learner_still_has_an_assessable_known_set(db_session):
    """No FSRS history must not mean 0 % coverage on every scene forever."""

    user = _user(db_session, email="cov-day-one@example.com")

    known = known_word_set(db_session, user=user)

    assert known.nailed_count == 0
    assert known.is_assessable is True
    verdict = check_scene_coverage(
        SceneText(text=A1_SCENE, proper_nouns=frozenset({"romy"})),
        LearnerLexicon(known=known, resolver=RESOLVER),
    )
    assert verdict.rejected is False


def test_an_explicit_level_override_is_labelled_as_an_override(db_session):
    user = _user(db_session, email="cov-override@example.com")

    known = known_word_set(db_session, user=user, level="B1.1")

    assert known.band == "B1"
    assert known.estimate_source == "override"


# ---------------------------------------------------------------------------
# 8. Reporting: stored scenes, the distribution, the digest line
# ---------------------------------------------------------------------------


def _scene(db_session, user, *, title: str, coverage_metadata: dict | None = None):
    scene = GraphicNovelScene(
        id=uuid4(),
        user_id=user.id,
        title=title,
        brief="Romy est au café et elle regarde la carte du jour avec attention.",
        status="available",
        cadence="daily",
        cache_key=str(uuid4()),
        prompt_version="test",
        image_model="none",
        image_quality="none",
        created_at=datetime.now(UTC),
        script_payload=({SCENE_METADATA_KEY: coverage_metadata} if coverage_metadata else {}),
        source_snapshot={},
    )
    db_session.add(scene)
    db_session.flush()
    db_session.add(
        GraphicNovelPanel(
            scene_id=scene.id,
            panel_index=0,
            title="1",
            beat="Elle regarde la carte et elle sourit vers la table du fond.",
            image_prompt="x",
            overlay_payload={
                "narration_fr": "Elle regarde la carte et elle sourit vers la table du fond.",
                "dialogue": [
                    {"text_fr": "Bonjour ! Vous voulez quelque chose à boire ce matin ?"},
                    {"text_fr": "Un café et un verre d'eau, s'il vous plaît."},
                ],
            },
        )
    )
    db_session.commit()
    return scene


def test_stored_scene_coverage_is_none_when_the_hook_has_not_landed(db_session):
    user = _user(db_session, email="cov-stored-none@example.com")
    scene = _scene(db_session, user, title="Sans mesure")

    assert stored_scene_coverage(scene) is None


def test_the_report_labels_recomputed_rows_as_recomputed(db_session):
    user = _user(db_session, email="cov-report-recompute@example.com")
    _scene(db_session, user, title="Au café")

    rows = recent_scene_coverage(db_session, user=user, limit=5)

    assert [row.origin for row in rows] == ["recomputed"]
    assert 0.0 <= rows[0].coverage <= 1.0


def test_the_report_prefers_what_the_generator_measured(db_session):
    user = _user(db_session, email="cov-report-stored@example.com")
    _scene(
        db_session,
        user,
        title="Mesurée",
        coverage_metadata={
            "version": COVERAGE_VERSION,
            "coverage": 0.91,
            "accidental_count": 3,
            "target_count": 1,
            "accidental_unknowns": [{"surface": "démarche", "lemma": "démarche"}],
        },
    )

    rows = recent_scene_coverage(db_session, user=user, limit=5)

    assert [row.origin for row in rows] == ["stored"]
    assert rows[0].coverage == pytest.approx(0.91)
    assert rows[0].accidental == ("démarche",)


def test_stored_only_never_invents_a_number_for_an_unmeasured_scene(db_session):
    user = _user(db_session, email="cov-report-stored-only@example.com")
    _scene(db_session, user, title="Sans mesure")

    assert recent_scene_coverage(db_session, user=user, limit=5, recompute=False) == []


def test_a_distribution_over_no_scenes_is_insufficient_data_not_zero():
    assert coverage_distribution([])["status"] == "insufficient_data"
    assert "median" not in coverage_distribution([])


def test_the_digest_line_says_unmeasured_rather_than_printing_a_zero(db_session):
    user = _user(db_session, email="cov-digest-unmeasured@example.com")
    _scene(db_session, user, title="Sans mesure")

    line = format_coverage_line(db_session, datetime.now(UTC).date(), str(user.id))

    assert "none measured" in line
    assert "WP-29 hook not applied" in line
    assert "0.0%" not in line


def test_the_digest_line_reports_the_distribution_once_scenes_are_measured(db_session):
    user = _user(db_session, email="cov-digest-measured@example.com")
    _scene(
        db_session,
        user,
        title="Mesurée",
        coverage_metadata={"coverage": 0.96, "accidental_count": 1, "target_count": 2},
    )

    line = format_coverage_line(db_session, datetime.now(UTC).date(), str(user.id))

    assert "median 96.0%" in line
    assert "1/1 at the 95% floor" in line
    assert "1 accidental unknown(s)" in line


def test_the_digest_line_on_a_day_with_no_scenes_says_so(db_session):
    user = _user(db_session, email="cov-digest-empty@example.com")

    assert format_coverage_line(
        db_session, (datetime.now(UTC) - timedelta(days=400)).date(), str(user.id)
    ) == "Lexical coverage: no scenes"


# ---------------------------------------------------------------------------
# 9. Resolvers
# ---------------------------------------------------------------------------


def test_a_spacy_resolver_offers_its_lemma_first_and_still_falls_back():
    class _Token:
        def __init__(self, lemma: str) -> None:
            self.lemma_ = lemma

    class _NLP:
        def __call__(self, text):
            return [_Token("aller")] if text == "allâmes" else []

    resolver = SpacyResolver(nlp=_NLP())

    assert resolver.candidates("allâmes")[1] == "aller"
    # An empty spaCy answer degrades to the curated candidates, never to nothing.
    assert "manger" in resolver.candidates("mangé")


def test_a_broken_spacy_pipeline_never_costs_a_learner_their_scene():
    class _Broken:
        def __call__(self, text):
            raise RuntimeError("model gone")

    resolver = SpacyResolver(nlp=_Broken())

    assert "manger" in resolver.candidates("mangé")


def test_the_curated_resolver_needs_no_spacy_and_is_the_declared_fallback():
    assert CuratedResolver().name == "curated"
    assert isinstance(text_coverage("Le chat", _known(), resolver=CuratedResolver()), CoverageResult)


# ---------------------------------------------------------------------------
# 10. The report script
# ---------------------------------------------------------------------------


def test_the_report_refuses_to_run_without_a_learner(db_session):
    """Coverage is a property of a text *and a reader*; there is no global number."""

    from scripts.coverage_report import resolve_user

    with pytest.raises(SystemExit) as excinfo:
        resolve_user(db_session, user_id=None, email=None)

    assert "per learner" in str(excinfo.value)


def test_the_report_finds_the_learner_by_email(db_session):
    from scripts.coverage_report import resolve_user

    user = _user(db_session, email="cov-report-lookup@example.com")

    assert resolve_user(db_session, user_id=None, email=user.email).id == user.id
    assert resolve_user(db_session, user_id=str(user.id), email=None).id == user.id


def test_a_phrase_card_contributes_its_words_not_the_whole_phrase(db_session):
    """A card can hold "avoir soif"; a scene says "soif"."""

    user = _user(db_session, email="cov-phrase@example.com")
    _word(db_session, "avoir soif", 900_103)
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=900_103,
            stability=40.0,
            reps=3,
            lapses=0,
            state="review",
            last_review_date=datetime.now(UTC) - timedelta(days=2),
        )
    )
    db_session.commit()

    lemmas = nailed_lemmas(db_session, user=user)

    assert {"avoir", "soif"} <= lemmas
    assert "avoir soif" not in lemmas
