"""2026-09-24 — the one-language rule reaches the document intake, the letter
headline fallback and the placement's evidence notes.

Up to A2 the app's own words are in the learner's language; from B1 French.
The document's reading, a correspondent's words and the learner's French stay
French at every level.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.api.v1.endpoints.intake import _refused
from app.services import story_correspondence as courrier
from app.services.chrome_language import user_chrome_language
from app.services.intake import IntakeRefused, parse_reading, public_view, read_prompt
from app.services.missions import artefact_mission_payload, success_signal_i18n
from app.services.placement import PlacementService, normalize_grading
from tests.test_intake import (  # noqa: F401 - `enabled_intake` is a fixture
    CAFE_MENU,
    _FakeLLM,
    _menu_reading,
    _service,
    _user,
    enabled_intake,
)
from tests.test_placement import _user as _placement_user


def _reading_with(native: dict[str, str] | None = None, **task_overrides) -> dict:
    reading = _menu_reading()
    reading["task"] = {**reading["task"], **(native or {}), **task_overrides}
    return reading


# ---------------------------------------------------------------------------
# (2) the document intake
# ---------------------------------------------------------------------------


def test_intake_a1_english_serves_its_chrome_in_english(db_session, enabled_intake):
    user = _user(db_session, native="en", level="A1")
    provider = _FakeLLM(
        _reading_with(
            {
                "instruction_native": "Order your lunch menu from the waiter.",
                "success_native": "The waiter knows what you are having and paying.",
            }
        )
    )
    artefact = _service(db_session, provider).submit_text(user, text=CAFE_MENU)

    # The model is asked for the learner's-language task only below B1.
    prompt = provider.calls[0]["messages"][0]["content"]
    assert '"instruction_native"' in prompt and "English" in prompt

    view = public_view(artefact, language=user_chrome_language(user))
    task, payload = view["task"], view["artefact"]
    assert task["kind_label"] == "Choose"
    assert task["instruction"] == "Order your lunch menu from the waiter."
    assert task["success"] == "The waiter knows what you are having and paying."
    assert task["instruction_by_language"]["fr"].startswith("Commandez")
    assert payload["type_label"] == "A menu"
    assert set(payload["type_label_by_language"]) == {"fr", "en", "de"}
    # Document content stays French.
    assert payload["title_fr"] == "Formule du midi"
    assert task["counterpart_fr"] == "le serveur"
    assert "counterpart_by_language" not in task

    mission = artefact_mission_payload(
        db_session,
        user=user,
        artefact_payload=artefact.artefact,
        task=artefact.task,
        source_text=artefact.source_text,
    )
    prompt_payload = mission["prompt_payload"]
    messenger = prompt_payload["messenger"]
    # The corrector keeps the French opening; the page says the English one.
    assert messenger["opening_message"].startswith("Commandez")
    assert messenger["opening_message_by_language"]["en"] == "Order your lunch menu from the waiter."
    assert messenger["opening_is_chrome"] is True
    assert success_signal_i18n(messenger)["en"].startswith("The waiter knows")
    assert prompt_payload["slim_payload"]["ask_by_language"]["en"].startswith("The waiter knows")
    assert prompt_payload["title_by_language"]["en"] == "Choose from the document"


def test_intake_a2_german_serves_its_chrome_in_german(db_session, enabled_intake):
    user = _user(db_session, native="de", level="A2")
    provider = _FakeLLM(
        _reading_with(
            {"instruction_native": "Bestell dein Mittagsmenü beim Kellner."},
            counterpart_fr="",
        )
    )
    artefact = _service(db_session, provider).submit_text(user, text=CAFE_MENU)
    assert "German" in provider.calls[0]["messages"][0]["content"]

    view = public_view(artefact, language=user_chrome_language(user))
    task = view["task"]
    assert task["kind_label"] == "Auswählen"
    assert task["instruction"] == "Bestell dein Mittagsmenü beim Kellner."
    # No German success line was written: its French stays, labelled by the table.
    assert task["success_by_language"] == {"fr": task["success_fr"]}
    assert view["artefact"]["type_label"] == "Eine Speisekarte"
    # The document named nobody: the fallback counterpart is chrome.
    assert task["counterpart_fr"] == "votre correspondant"
    assert task["counterpart_by_language"]["de"] == "dein Gegenüber"

    detail = _refused(IntakeRefused("image_empty"), user_chrome_language(user)).detail
    assert detail["message"].startswith("Das Foto ist leer")
    assert detail["message_fr"].startswith("La photo est vide")
    assert set(detail["message_by_language"]) == {"fr", "en", "de"}


def test_intake_b1_reads_french_chrome_and_asks_for_no_translation(db_session, enabled_intake):
    user = _user(db_session, native="en", level="B1")
    provider = _FakeLLM(_menu_reading())
    artefact = _service(db_session, provider).submit_text(user, text=CAFE_MENU)
    assert '"instruction_native"' not in provider.calls[0]["messages"][0]["content"]

    view = public_view(artefact, language=user_chrome_language(user))
    assert view["task"]["kind_label"] == "Choisir"
    assert view["task"]["instruction"].startswith("Commandez")
    assert view["artefact"]["type_label"] == "Un menu"
    assert _refused(IntakeRefused("image_empty"), "fr").detail["message"].startswith("La photo")


def test_an_older_artefact_row_still_gets_its_chrome_tables():
    reading = parse_reading(json.dumps(_menu_reading()), band="A2")
    assert reading is not None
    legacy_task = {k: v for k, v in reading.task.items() if not k.endswith("_by_language")}
    row = SimpleNamespace(
        id="a1",
        version="v",
        status="read",
        source_kind="text",
        source_text="",
        artefact=reading.as_artefact(),
        task=legacy_task,
        mission_id=None,
        queued_word_ids=[],
        created_at=None,
    )
    view = public_view(row, language="en")
    assert view["task"]["kind_label"] == "Choose"
    # No English instruction was ever written: the French one, under `fr` only.
    assert view["task"]["instruction_by_language"] == {"fr": legacy_task["instruction_fr"]}
    assert read_prompt(band="A2", native_language="de", has_image=False, chrome="fr").count("_native") == 0


# ---------------------------------------------------------------------------
# (3) the letter headline fallback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", "A letter from Le Courrier."),
        ("de", "Ein Brief aus Le Courrier."),
        ("fr", "Une lettre du Courrier."),
    ],
)
def test_the_letter_headline_fallback_is_chrome(language, expected):
    untitled = SimpleNamespace(prompt_payload={}, title=None)
    summary = courrier.summarise_letter(untitled)
    # The French line still feeds French prompts and recaps unchanged.
    assert summary == "Une lettre du Courrier."
    view = courrier.letter_headline_view(summary, language)
    assert view["summary"] == expected
    assert view["summary_fr"] == summary
    assert view["summary_is_fallback"] is True


def test_a_real_letter_headline_stays_french():
    titled = SimpleNamespace(prompt_payload={"messenger": {"thread_title": "Le radiateur"}}, title="x")
    assert courrier.letter_headline_view(courrier.summarise_letter(titled), "en") == {
        "summary_fr": "Le radiateur"
    }


def test_thread_history_resolves_the_fallback_for_the_learner():
    # Level rule by user: A1 English, A2 German, B1 French.
    for native, level, expected in (
        ("en", "A1", "A letter from Le Courrier."),
        ("de", "A2", "Ein Brief aus Le Courrier."),
        ("en", "B1", "Une lettre du Courrier."),
    ):
        user = SimpleNamespace(native_language=native, cefr_estimate=level)
        view = courrier.letter_headline_view(
            courrier.LETTER_HEADLINE_FALLBACK["fr"], user_chrome_language(user)
        )
        assert view["summary"] == expected


# ---------------------------------------------------------------------------
# (4) the placement's evidence notes
# ---------------------------------------------------------------------------

_GRADING = {
    "score_0_4": 3,
    "demonstrated_band": "A2.1",
    "dimensions": {"range": 3, "accuracy": 3, "coherence": 3, "task": 3},
    "evidence_fr": "phrase complète : « je voudrais un café »",
    "off_task": False,
}


def test_placement_note_in_english_keeps_the_learners_french_quote():
    graded = normalize_grading(
        {**_GRADING, "evidence_native": "A complete sentence: « je voudrais un café »"},
        language="en",
    )
    assert graded["evidence_native"].startswith("A complete sentence")
    assert "« je voudrais un café »" in graded["evidence_native"]
    assert graded["evidence_language"] == "en"
    assert graded["evidence_fr"].startswith("phrase complète")


def test_placement_note_in_german_and_the_french_fallback():
    graded = normalize_grading(
        {**_GRADING, "evidence_native": "Ein vollständiger Satz: « je voudrais un café »"},
        language="de",
    )
    assert graded["evidence_language"] == "de"
    # A grader that wrote no note in the learner's language: the French one, labelled.
    older = normalize_grading(dict(_GRADING), language="de")
    assert older["evidence_native"] == _GRADING["evidence_fr"]
    assert older["evidence_language"] == "fr"


def test_placement_note_for_a_french_reader_is_the_french_note():
    graded = normalize_grading({**_GRADING, "evidence_native": "ignored"}, language="fr")
    assert graded["evidence_native"] == _GRADING["evidence_fr"]
    assert graded["evidence_language"] == "fr"


class _NoteGrader:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def generate_error_detection(self, messages, **kwargs):
        self.payloads.append(json.loads(messages[0]["content"]))
        assert "evidence_native" in kwargs["response_format"]["json_schema"]["schema"]["required"]
        return SimpleNamespace(
            content=json.dumps({**_GRADING, "evidence_native": "A complete sentence."}),
            model="test-model",
            provider="test",
            prompt_tokens=100,
            completion_tokens=40,
            total_tokens=140,
            cost=0.0004,
        )


def test_the_grader_is_told_the_learners_language_and_the_estimate_carries_the_note(db_session):
    user = _placement_user(db_session)
    grader = _NoteGrader()
    service = PlacementService(db_session, llm_service=grader)
    session = service.start(user)
    session = service.respond(
        session, answer="Je voudrais un café, s’il vous plaît.", turn_index=0, language="en"
    )
    assert grader.payloads[0]["evidence_language"] == "en"
    turn = session.turns[0]["grading"]
    assert turn["evidence_native"] == "A complete sentence."
    assert turn["evidence_language"] == "en"
    evidence = (session.estimate or {}).get("evidence") or []
    assert evidence and evidence[0]["evidence_native"] == "A complete sentence."
