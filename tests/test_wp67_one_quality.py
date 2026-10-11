"""WP-67 — one quality: the whole app in the learner's language, no phantoms.

Three things are pinned here.

1. **The correction speaks the learner's language.** WP-56 moved the generic
   recognize feedback into `learner_copy` and left the three hand-written
   grammar families — si type 1, the article after negation, imparfait vs passé
   composé — as English literals, which is the worst place to leave English: the
   learner reading it is the one who just got the item wrong.

2. **A shared exercise set is read in the learner's language.** An exercise set
   is generated once and reused by every learner, so its instruction cannot be
   written in one learner's language when it is stored. It carries the copy key
   instead and the endpoint resolves it on the way out — the same discipline
   `_with_fr_titles` already uses for the French concept title — and nothing the
   corrector grades against is touched.

3. **F-30: the ladder starts at the placement estimate.** An A2-placed learner
   opened on the first A1 foundation rule in the catalogue, because the ceiling
   was read and the floor never was.
"""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from app.api.v1.endpoints.atelier import _with_learner_instructions
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.atelier import (
    AtelierCorrectionService,
    AtelierScheduler,
    _cefr_levels_at_or_below,
    placement_band,
)
from app.services.learner_copy import LEARNER_COPY, key_for_english, learner_text_for_english

ROOT = Path(__file__).resolve().parents[1]

#: Words that only an English sentence carries. A German erratum containing one
#: of these is an English erratum wearing a German label.
ENGLISH_TELLS = ("You used", "You chose", "You classified", "the result clause", "needs")


def _german_user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="test",
        target_language="fr",
        native_language="de",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _concept(db_session, external_id: str) -> GrammarConcept:
    AtelierScheduler(db_session).ensure_catalog()
    return db_session.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one()


def _service(db_session, language: str) -> AtelierCorrectionService:
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    return service


# ---------------------------------------------------------------------------
# 1. The correction speaks the learner's language
# ---------------------------------------------------------------------------


def test_si_fill_erratum_is_written_in_the_learners_language(db_session) -> None:
    concept = _concept(db_session, "FR_B1_COND_001")
    item = {"id": "si-fill-1", "prompt": "Si elle appelle, je ____ tout de suite."}

    german = _service(db_session, "de")._fill_erratum(concept, item, "appelle", "appellerai")
    english = _service(db_session, "en")._fill_erratum(concept, item, "appelle", "appellerai")
    french = _service(db_session, "fr")._fill_erratum(concept, item, "appelle", "appellerai")

    assert german["display_label"] == "Verlangte Form"
    assert "Futur simple" in german["why_wrong"]
    assert not any(tell in german["why_wrong"] for tell in ENGLISH_TELLS)
    # The English column is unchanged, so the pins written before WP-67 hold.
    assert english["display_label"] == "Target form needed"
    assert "future simple" in english["why_wrong"]
    assert french["display_label"] == "Forme attendue"
    assert "futur simple" in french["why_wrong"]


def test_negation_and_tense_errata_follow_the_learner_too(db_session) -> None:
    negation = _concept(db_session, "FR_A2_NEG_001")
    item = {"id": "neg-fill-1", "prompt": "Je ne bois pas ____ café."}

    german = _service(db_session, "de")._fill_erratum(negation, item, "du", "de")
    assert german["display_label"] == "Artikel nach der Verneinung"
    assert "du" in german["why_wrong"]
    assert not any(tell in german["why_wrong"] for tell in ENGLISH_TELLS)

    classified = _service(db_session, "fr")._classify_erratum(
        negation, {"id": "neg-classify-1", "prompt": "pas de café"}, "être exception", "article changes"
    )
    assert classified["display_label"] == "Schéma de négation"
    assert "classé" in classified["why_wrong"]


def test_a_word_bank_mis_ordering_is_still_recognised_in_german(db_session) -> None:
    """The relabelling used to compare the label against the English literal.

    With the label translated, «Wortbank» never matched "Word bank", so a German
    learner who had all the right chips in the wrong order was told the sentence
    itself was wrong.
    """
    concept = _concept(db_session, "FR_A2_NEG_001")
    item = {"id": "wb-1", "prompt": "Reconstruisez la phrase."}

    errata = _service(db_session, "de")._word_bank_errata(
        concept, item, "café de pas bois ne Je", "Je ne bois pas de café"
    )

    assert len(errata) == 1
    assert errata[0]["display_label"] == "Wortstellung"
    assert "Reihenfolge" in errata[0]["why_wrong"]


def test_the_no_concept_floors_are_translated(db_session) -> None:
    service = _service(db_session, "de")

    assert service._label_for(None, {}) == "Grammatikziel"
    assert service._why_for(None) == LEARNER_COPY["atelier.generic.why"]["de"]
    assert service._repair_for(None) == LEARNER_COPY["atelier.generic.repair"]["de"]


# ---------------------------------------------------------------------------
# 2. Shared exercise sets are read in the learner's language
# ---------------------------------------------------------------------------


def test_a_fallback_transform_instruction_carries_its_copy_key(db_session) -> None:
    from app.services.atelier import AtelierExerciseGenerator

    concept = _concept(db_session, "FR_B1_COND_001")
    items = AtelierExerciseGenerator(db_session)._fallback_transform_items(
        concept, [], prefix="si"
    )

    assert len(items) == 3
    for item in items:
        assert item["instruction_key"] in LEARNER_COPY
        assert item["instruction"] == LEARNER_COPY[item["instruction_key"]]["en"]
        # The no-spoil rule: an instruction never hands over the answer whole.
        assert item["expected_answer"] not in item["instruction"]
        assert item["source"] != item["expected_answer"]


def test_the_endpoint_reads_a_stored_instruction_in_the_learners_language() -> None:
    payload = {
        "transform": {
            "items": [
                {
                    "id": "si-fallback-transform-1",
                    "instruction": LEARNER_COPY["atelier.transform.si.1"]["en"],
                    "instruction_key": "atelier.transform.si.1",
                    "source": "Quand il arrivera, on commencera.",
                    "expected_answer": "S'il arrive, on commencera.",
                }
            ]
        }
    }

    german = _with_learner_instructions(payload, native_language="de")

    assert german["transform"]["items"][0]["instruction"] == LEARNER_COPY["atelier.transform.si.1"]["de"]
    # Nothing the corrector grades against moved.
    assert german["transform"]["items"][0]["expected_answer"] == "S'il arrive, on commencera."
    assert german["transform"]["items"][0]["source"] == "Quand il arrivera, on commencera."
    # An English reader gets the payload back untouched, object for object.
    assert _with_learner_instructions(payload, native_language="en") == payload


def test_a_payload_cached_before_wp67_still_localizes() -> None:
    """The rows already in `atelier_exercise_sets` carry no key, only the text.

    They are looked up in the copy table's own English column rather than
    regenerated, so no cache had to be retired to fix the language.
    """
    stored = {
        "output_ladder": {
            "writing": {
                "items": [
                    {"instruction": "Use the target grammar visibly in your answer.", "prompt": "Écrivez."}
                ]
            }
        }
    }

    french = _with_learner_instructions(stored, native_language="fr")

    assert french["output_ladder"]["writing"]["items"][0]["instruction"] == (
        LEARNER_COPY["atelier.fallback.output_instruction"]["fr"]
    )


def test_an_instruction_nobody_authored_is_left_alone() -> None:
    """The localizer re-reads rows the table holds; it never invents a sentence."""
    written_by_the_model = {"items": [{"instruction": "Réécrivez la phrase au passé."}]}

    assert key_for_english("Réécrivez la phrase au passé.") is None
    assert learner_text_for_english("Réécrivez la phrase au passé.", "de") == "Réécrivez la phrase au passé."
    assert _with_learner_instructions(written_by_the_model, native_language="de") == written_by_the_model


def test_every_copy_key_atelier_asks_for_is_a_real_row() -> None:
    source = (ROOT / "app" / "services" / "atelier.py").read_text(encoding="utf-8")
    keys = set(re.findall(r'"(atelier\.[a-z_0-9]+\.[a-z_0-9.]+)"', source))

    assert len(keys) > 60
    missing = sorted(key for key in keys if key not in LEARNER_COPY)
    assert missing == []


def test_the_two_french_only_errata_now_follow_the_learner(db_session) -> None:
    """The mirror defect: French prose shown to a learner who cannot read it.

    The short-paragraph gate and the lexical-gap note were written in French (the
    second one half in English), for everyone, whatever the account says.
    """
    service = _service(db_session, "de")

    gated = service._apply_produce_length_gate(
        {"verdict": "correct", "errata": []},
        prompt_payload={"min_words": 40},
        answer_payload={"text": "Zu kurz."},
    )
    assert gated["errata"][0]["display_label"] == "Absatz zu kurz"
    assert "verlangt" in gated["errata"][0]["why_wrong"]

    why = service._lexical_gap_why(
        {"learner_fragment": "Fahrrad", "french": "vélo", "source_language": "de", "gloss": "bicycle"}
    )
    assert why.startswith("Du hast")
    assert "auf Deutsch" in why
    assert "(bicycle)" in why
    # And the French reader still reads the French the screen was designed with.
    assert _service(db_session, "fr")._apply_produce_length_gate(
        {"verdict": "correct", "errata": []},
        prompt_payload={"min_words": 40},
        answer_payload={"text": "Trop court."},
    )["errata"][0]["display_label"] == "Paragraphe trop court"


# ---------------------------------------------------------------------------
# 3. F-30 — the ladder starts at the placement estimate
# ---------------------------------------------------------------------------


def test_a_placement_raises_the_ceiling_even_before_a_recompute(db_session) -> None:
    user = _german_user(db_session)
    user.cefr_estimate = "A1.1"

    assert _cefr_levels_at_or_below(user) == ["A1"]
    assert _cefr_levels_at_or_below(user, placement="A2") == ["A1", "A2"]
    # A measurement can only ever raise it: a low placement never demotes a
    # learner whose own estimate is higher.
    user.cefr_estimate = "B1.2"
    assert _cefr_levels_at_or_below(user, placement="A1") == ["A1", "A2", "B1"]


def test_an_unmeasured_learner_has_no_placement_band(db_session) -> None:
    assert placement_band(db_session, _german_user(db_session)) is None


def test_the_cold_start_opens_at_the_learners_own_band(db_session, monkeypatch) -> None:
    user = _german_user(db_session)
    user.cefr_estimate = "A2.2"
    db_session.add(user)
    db_session.commit()

    scheduler = AtelierScheduler(db_session)
    monkeypatch.setattr("app.services.atelier.placement_band", lambda db, user: "A2")
    selections = scheduler.select_today(user)

    assert selections
    opened_on = selections[0].concept
    assert opened_on.level.startswith("A2"), opened_on.name
    # And without the measurement the same learner starts where they always did.
    monkeypatch.setattr("app.services.atelier.placement_band", lambda db, user: None)
    user.cefr_estimate = "A1.1"
    db_session.add(user)
    db_session.commit()
    assert AtelierScheduler(db_session).select_today(user)[0].concept.level.startswith("A1")


# ---------------------------------------------------------------------------
# The phantom that was removed rather than mounted
# ---------------------------------------------------------------------------


def test_reglages_no_longer_promises_a_distinction_notice() -> None:
    """`achievement_notifications` is stored and read by no sender.

    The distinctions themselves are real and already printed with their dates in
    La Collection (Cahier › Le Relevé); the note that was promised never
    existed, so the row went rather than the section being built twice.
    """
    settings_page = (ROOT / "web-frontend" / "pages" / "settings.tsx").read_text(encoding="utf-8")
    settings_copy = (ROOT / "web-frontend" / "lib" / "settings-copy.ts").read_text(encoding="utf-8")

    assert "copy.notif_achievements" not in settings_page
    assert "notif_achievements" not in settings_copy
    # The stored preference is not destroyed: this page still round-trips it.
    assert "achievement_notifications: settings.achievementNotifications" in settings_page

    # And nothing in the backend sends such a note, which is why the row went.
    senders = list((ROOT / "app").rglob("*.py"))
    readers = [
        path
        for path in senders
        if "achievement_notifications" in path.read_text(encoding="utf-8")
        and path.parts[-2:] not in [("db", "models"), ("app", "schemas")]
        and path.name not in {"user.py", "auth.py"}
    ]
    assert readers == [], f"a sender appeared: {[str(p) for p in readers]}"


def test_the_dead_grammar_achievements_component_is_gone() -> None:
    assert not (ROOT / "web-frontend" / "components" / "learning" / "GrammarAchievements.tsx").exists()
