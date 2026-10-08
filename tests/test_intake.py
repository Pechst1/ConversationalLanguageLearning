"""WP-34 — «Apportez votre français»: a real document, read once and used.

What these tests hold down, in the order the package promises it:

1. one model call per artefact, text or photograph, with the payload bounded
   before it is paid for;
2. the reading is *structured or nothing*: a half-answer is «non lu», never a
   plausible summary of a document nobody read;
3. the summary is at the learner's band — a checkable claim, not a prompt wish;
4. glossing goes through the app's own resolver in the learner's own language,
   and a model gloss that stands in for a missing one says so;
5. the derived task is an ordinary Courrier mission, graded by the existing
   corrector at the existing endpoint — this package adds no second grader;
6. unknown words enter the SRS queue as learner-sourced, with provenance, and
   an existing card keeps its schedule;
7. **privacy**: never story canon (an `ast` source scan), deletable together
   with the task derived from it, and never written into any payload but the
   model call's;
8. every call writes a priced pilot row, including the one that failed.

The two fixtures are the ones the package was specified against: a café menu
and a landlord's letter about the heating.

No live model call is made anywhere in this file: the provider is a fake.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config import settings
from app.db.models.intake import LEARNER_SOURCED_PROVENANCE, LearnerArtefact
from app.db.models.mission import RealWorldMission
from app.db.models.pilot_event import PilotEvent
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.intake import (
    INTAKE_EVENT_TYPE,
    MAX_KEY_FACTS,
    MAX_UNKNOWN_WORDS,
    SOURCE_TEXT_MAX_CHARS,
    IntakeRefused,
    IntakeService,
    bound_summary,
    cap_state,
    intake_digest_line,
    learner_sourced_targets,
    normalize_source_text,
    parse_reading,
    public_view,
    read_prompt,
    resolve_glosses,
    summary_word_limit,
    text_messages,
    vision_messages,
)
from app.services.missions import (
    ARTEFACT_CADENCE,
    MissionCorrectionService,
    artefact_mission_payload,
)

# ---------------------------------------------------------------------------
# fixtures — the two documents WP-34 was specified against
# ---------------------------------------------------------------------------

CAFE_MENU = """
Café des Trois Ponts — Formule du midi
Entrée du jour : velouté de potiron
Plat : gratin de courgettes ou saucisse de Toulouse, purée
Dessert : tarte aux noix
Formule complète 14,50 €. Plat seul 11 €.
Service de 12 h à 14 h 30. Pas de réservation le samedi.
"""

LANDLORD_LETTER = """
Monsieur, Madame,

Suite à votre signalement du 3 septembre concernant le chauffage de votre
appartement, un technicien de la société Berthier passera le mardi 16 septembre
entre 8 h et 12 h. Merci de confirmer votre présence avant le 12 septembre.
En cas d'absence, une nouvelle intervention vous sera facturée 65 €.

Veuillez agréer, Monsieur, Madame, mes salutations distinguées.
M. Marchand, gérant
"""


def _menu_reading() -> dict:
    return {
        "readable": True,
        "transcript": " ".join(CAFE_MENU.split()),
        "type": "menu",
        "title_fr": "Formule du midi",
        "summary_fr": (
            "C'est le menu du midi. Il y a un velouté, deux plats et une tarte. "
            "La formule coûte 14,50 euros. Le service est de midi à 14 h 30."
        ),
        "key_facts": [
            {"label_fr": "Formule", "value_fr": "14,50 €"},
            {"label_fr": "Plat seul", "value_fr": "11 €"},
            {"label_fr": "Service", "value_fr": "12 h – 14 h 30"},
        ],
        "unknown_words": [
            {
                "word": "velouté",
                "lemma": "velouté",
                "gloss": "creamy soup",
                "example_fr": "velouté de potiron",
            },
            {
                "word": "gratin",
                "lemma": "gratin",
                "gloss": "baked dish",
                "example_fr": "gratin de courgettes",
            },
        ],
        "task": {
            "kind": "decide",
            "instruction_fr": "Commandez votre formule du midi auprès du serveur.",
            "counterpart_fr": "le serveur",
            "register": "vous",
            "success_fr": "Le serveur sait ce que vous prenez et ce que vous payez.",
        },
    }


def _letter_reading() -> dict:
    return {
        "readable": True,
        "transcript": " ".join(LANDLORD_LETTER.split()),
        "type": "lettre",
        "title_fr": "Rendez-vous pour le chauffage",
        "summary_fr": (
            "Votre gérant répond au sujet du chauffage. Un technicien vient le "
            "mardi 16 septembre, entre 8 h et midi. Vous devez confirmer avant "
            "le 12 septembre."
        ),
        "key_facts": [
            {"label_fr": "Rendez-vous", "value_fr": "mardi 16 septembre, 8 h – 12 h"},
            {"label_fr": "À confirmer avant", "value_fr": "12 septembre"},
            {"label_fr": "Absence", "value_fr": "65 € facturés"},
        ],
        "unknown_words": [
            {
                "word": "signalement",
                "lemma": "signalement",
                "gloss": "report",
                "example_fr": "votre signalement du 3 septembre",
            },
            {
                "word": "facturée",
                "lemma": "facturer",
                "gloss": "to invoice",
                "example_fr": "vous sera facturée 65 €",
            },
        ],
        "task": {
            "kind": "reply",
            "instruction_fr": "Répondez au gérant pour confirmer votre présence mardi.",
            "counterpart_fr": "M. Marchand",
            "register": "vous",
            "success_fr": "Le gérant sait que vous serez là mardi matin.",
        },
    }


class _FakeLLM:
    """One canned reading, and a count of how many times it was asked for."""

    def __init__(self, reading: dict | str | None, *, cost: float = 0.0031) -> None:
        self._reading = reading
        self.calls: list[dict] = []
        self.cost = cost

    def generate_chat_completion(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if self._reading is None:
            raise RuntimeError("provider is down")
        content = (
            self._reading
            if isinstance(self._reading, str)
            else json.dumps(self._reading, ensure_ascii=False)
        )
        return SimpleNamespace(
            content=content,
            model="fake-vision",
            provider="fake",
            prompt_tokens=900,
            completion_tokens=320,
            total_tokens=1220,
            cost=self.cost,
        )


@pytest.fixture()
def enabled_intake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_INTAKE_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_CAP", 5)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_COST_CEILING_USD", 0.5)


def _user(db_session, *, native: str = "en", level: str = "A2") -> User:
    user = User(
        id=uuid4(),
        email=f"intake-{uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language=native,
        target_language="fr",
        proficiency_level=level,
        cefr_estimate=level,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _service(db_session, provider: _FakeLLM | None) -> IntakeService:
    service = IntakeService(db_session)
    service._get_llm_service = lambda: provider  # type: ignore[method-assign]
    return service


# ===========================================================================
# 1. one call per artefact, bounded before it is paid for
# ===========================================================================


def test_a_pasted_document_costs_exactly_one_model_call(db_session, enabled_intake):
    user = _user(db_session)
    provider = _FakeLLM(_letter_reading())
    artefact = _service(db_session, provider).submit_text(user, text=LANDLORD_LETTER)

    assert artefact.status == "read"
    assert len(provider.calls) == 1
    kwargs = provider.calls[0]["kwargs"]
    # A second provider and a retry would each be a second paid read of the
    # same document.
    assert kwargs["max_provider_attempts"] == 1
    assert kwargs["disable_retries"] is True


def test_a_photograph_goes_to_the_vision_model_as_one_image_block(db_session, enabled_intake):
    user = _user(db_session)
    provider = _FakeLLM(_menu_reading())
    artefact = _service(db_session, provider).submit_image(
        user, data=b"\xff\xd8\xff" + b"0" * 400, content_type="image/jpeg"
    )

    assert artefact.status == "read"
    assert artefact.source_kind == "image"
    content = provider.calls[0]["messages"][0]["content"]
    blocks = [block["type"] for block in content]
    assert blocks == ["text", "image_url"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert provider.calls[0]["kwargs"]["model"] == settings.ATELIER_INTAKE_VISION_MODEL


def test_an_oversized_or_unsupported_photo_is_refused_before_the_call(db_session, enabled_intake, monkeypatch):
    user = _user(db_session)
    provider = _FakeLLM(_menu_reading())
    service = _service(db_session, provider)

    monkeypatch.setattr(settings, "ATELIER_INTAKE_MAX_IMAGE_BYTES", 1000)
    with pytest.raises(IntakeRefused) as too_big:
        service.submit_image(user, data=b"0" * 1001, content_type="image/jpeg")
    assert too_big.value.code == "image_too_large"

    with pytest.raises(IntakeRefused) as wrong_type:
        service.submit_image(user, data=b"0" * 10, content_type="application/pdf")
    assert wrong_type.value.code == "image_type_unsupported"

    with pytest.raises(IntakeRefused) as too_short:
        service.submit_text(user, text="bonjour")
    assert too_short.value.code == "document_too_short"

    assert provider.calls == []


def test_a_pasted_book_cannot_size_the_request():
    assert len(normalize_source_text("mot " * 20_000)) == SOURCE_TEXT_MAX_CHARS


def test_the_prompt_never_asks_for_anything_but_a_reading():
    prompt = read_prompt(band="A2", native_language="de", has_image=False)
    lowered = prompt.lower()
    assert "never invent" in lowered
    # The document is the learner's. It is read; it is not mined for a story,
    # nor for the app's own content.
    for forbidden in ("story", "canon", "world bible", "training", "scene"):
        assert forbidden not in lowered


# ===========================================================================
# 2. structured or nothing
# ===========================================================================


@pytest.mark.parametrize(
    "payload",
    [
        {"readable": False},
        {"readable": True, "summary_fr": "trop court"},
        {"readable": True, "summary_fr": "Une phrase assez longue pour passer.", "transcript": ""},
        "not json at all",
        "",
    ],
)
def test_an_unusable_answer_is_non_lu_and_never_a_partial_card(payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    assert parse_reading(raw, band="A2") is None


def test_a_reading_without_a_task_is_non_lu(db_session, enabled_intake):
    payload = _menu_reading()
    payload.pop("task")
    user = _user(db_session)
    artefact = _service(db_session, _FakeLLM(payload)).submit_text(user, text=CAFE_MENU)

    assert artefact.status == "unread"
    assert artefact.artefact == {}
    assert artefact.task == {}
    assert artefact.mission_id is None
    assert artefact.failure_reason == "unreadable"


def test_a_provider_that_never_answers_leaves_non_lu_with_the_document_kept(db_session, enabled_intake):
    user = _user(db_session)
    artefact = _service(db_session, _FakeLLM(None)).submit_text(user, text=LANDLORD_LETTER)

    assert artefact.status == "unread"
    assert artefact.failure_reason == "provider_failed"
    # The learner's own paste survives so the retry does not ask them to paste
    # it again. A photograph has nothing to keep — the bytes were never stored.
    assert "chauffage" in artefact.source_text


def test_a_photograph_that_could_not_be_read_keeps_no_bytes(db_session, enabled_intake):
    user = _user(db_session)
    artefact = _service(db_session, _FakeLLM(None)).submit_image(
        user, data=b"\xff\xd8\xff" + b"1" * 500, content_type="image/png"
    )
    assert artefact.status == "unread"
    assert artefact.source_text == ""


def test_a_word_the_document_does_not_contain_is_dropped():
    payload = _menu_reading()
    payload["unknown_words"].append(
        {"word": "chauffage", "lemma": "chauffage", "gloss": "heating", "example_fr": ""}
    )
    reading = parse_reading(json.dumps(payload), band="A2")
    assert reading is not None
    assert [item["word"] for item in reading.unknown_words] == ["velouté", "gratin"]


def test_facts_and_words_are_bounded():
    payload = _menu_reading()
    payload["key_facts"] = [
        {"label_fr": f"F{index}", "value_fr": str(index)} for index in range(20)
    ]
    payload["unknown_words"] = [
        {"word": word, "lemma": word, "gloss": "x", "example_fr": ""}
        for word in " ".join(CAFE_MENU.split()).split()[:30]
    ]
    reading = parse_reading(json.dumps(payload), band="A2")
    assert reading is not None
    assert len(reading.key_facts) == MAX_KEY_FACTS
    assert len(reading.unknown_words) <= MAX_UNKNOWN_WORDS


# ===========================================================================
# 3. the summary is at the learner's band
# ===========================================================================


def test_the_summary_is_cut_to_the_bands_ceiling_and_says_so():
    long_summary = "mot " * 200
    for band in ("A1", "A2", "B1"):
        text, bounded = bound_summary(long_summary, band=band)
        assert bounded is True
        assert len(text.split()) <= summary_word_limit(band) + 1  # the ellipsis
    assert summary_word_limit("A1") < summary_word_limit("B1")


def test_the_band_reaches_the_prompt_and_the_card(db_session, enabled_intake):
    user = _user(db_session, level="A1")
    provider = _FakeLLM(_menu_reading())
    artefact = _service(db_session, provider).submit_text(user, text=CAFE_MENU)
    assert artefact.artefact["band"] == "A1"
    assert "CEFR A1" in provider.calls[0]["messages"][0]["content"]


# ===========================================================================
# 4. glossing through the app's own resolver
# ===========================================================================


def test_the_apps_own_gloss_wins_and_is_in_the_learners_language(db_session):
    user = _user(db_session, native="de")
    known = f"potiron{uuid4().hex[:6]}"
    unknown = f"courgette{uuid4().hex[:6]}"
    db_session.add(
        VocabularyWord(
            language="fr",
            word=known,
            normalized_word=known,
            german_translation="Kürbis",
            english_translation="pumpkin",
        )
    )
    db_session.commit()

    glossed = resolve_glosses(
        db_session,
        user=user,
        words=(
            {"word": known, "lemma": known, "gloss": "squash-ish", "example_fr": ""},
            {"word": unknown, "lemma": unknown, "gloss": "baked dish", "example_fr": ""},
        ),
    )
    assert glossed[0]["gloss"] == "Kürbis"
    assert glossed[0]["gloss_language"] == "de"
    assert glossed[0]["gloss_source"] == "vocabulary"
    # No entry in the app's vocabulary: the model's gloss stands in, labelled.
    assert glossed[1]["gloss"] == "baked dish"
    assert glossed[1]["gloss_source"] == "model"


def test_the_gloss_language_is_asked_for_in_the_prompt():
    assert '"de"' in read_prompt(band="A2", native_language="de-DE", has_image=False)


# ===========================================================================
# 5. the derived task is an ordinary Courrier mission
# ===========================================================================


def test_the_task_becomes_a_real_courrier_mission(db_session, enabled_intake):
    user = _user(db_session)
    artefact = _service(db_session, _FakeLLM(_letter_reading())).submit_text(
        user, text=LANDLORD_LETTER
    )

    mission = db_session.get(RealWorldMission, artefact.mission_id)
    assert mission is not None
    assert mission.user_id == user.id
    assert mission.cadence == ARTEFACT_CADENCE
    assert mission.status == "available"
    assert mission.prompt_payload["artefact_task_kind"] == "reply"
    assert mission.prompt_payload["messenger"]["contact_name"] == "M. Marchand"
    assert mission.prompt_payload["target_register"].startswith("vous")
    # Everything an existing Courrier surface reads has to be there.
    for key in ("messenger", "slim_payload", "min_words", "max_words", "branching"):
        assert key in mission.prompt_payload


def test_an_artefact_mission_never_hijacks_the_weekly_courrier(db_session, enabled_intake):
    # `MissionScheduler.today` promotes an available *ad_hoc* mission to
    # `active_mission`. An artefact must not displace the day's own Courrier.
    assert ARTEFACT_CADENCE != "ad_hoc"
    user = _user(db_session)
    artefact = _service(db_session, _FakeLLM(_menu_reading())).submit_text(user, text=CAFE_MENU)
    mission = db_session.get(RealWorldMission, artefact.mission_id)
    assert mission.iso_year is None and mission.iso_week is None


def test_the_artefact_mission_is_graded_by_the_existing_corrector(db_session, enabled_intake):
    user = _user(db_session)
    artefact = _service(db_session, _FakeLLM(_letter_reading())).submit_text(
        user, text=LANDLORD_LETTER
    )
    mission = db_session.get(RealWorldMission, artefact.mission_id)

    service = MissionCorrectionService(db_session, llm_service=None)
    correction = service.correct_submission(
        user=user,
        mission=mission,
        text="Bonjour Monsieur, je serai present mardi matin. Merci beaucoup.",
        mode="writing",
    )
    # The same envelope every Courrier correction returns — not a second grader.
    assert "errata" in correction and "corrected_answer" in correction
    assert "correction_debug" in correction
    # 2026-09-05 P0: nothing is presented as a repair unless a repair exists.
    if not service._has_language_repair(correction):
        assert correction["corrected_answer"] == (
            "Bonjour Monsieur, je serai present mardi matin. Merci beaucoup."
        )


def test_only_words_the_ribbon_prints_can_ever_cost_the_learner(db_session, enabled_intake):
    """The 2026-09-05 fix: penalties are limited to the printed slate."""

    user = _user(db_session)
    artefact = _service(db_session, _FakeLLM(_menu_reading())).submit_text(user, text=CAFE_MENU)
    mission = db_session.get(RealWorldMission, artefact.mission_id)
    printed = {
        item["word_id"] for item in mission.prompt_payload["target_vocabulary"]
    }
    assert printed
    assert printed <= set(mission.target_vocabulary_ids)


def test_a_menu_defaults_to_decide_and_a_letter_to_reply():
    for payload, expected in ((_menu_reading(), "decide"), (_letter_reading(), "reply")):
        payload["task"]["kind"] = "nonsense"
        reading = parse_reading(json.dumps(payload), band="A2")
        assert reading is not None
        assert reading.task["kind"] == expected


def test_the_mission_payload_is_built_without_a_model_call(db_session):
    user = _user(db_session)
    reading = parse_reading(json.dumps(_menu_reading()), band="A2")
    assert reading is not None
    payload = reading.as_artefact()
    payload["glossed_words"] = []
    built = artefact_mission_payload(
        db_session,
        user=user,
        artefact_payload=payload,
        task=reading.task,
        source_text=CAFE_MENU,
    )
    assert built["title"]
    assert built["prompt_payload"]["messenger"]["opening_message"]
    assert built["source_snapshot"]["source"] == "learner_artefact"


# ===========================================================================
# 6. learner-sourced vocabulary, with provenance
# ===========================================================================


def test_unknown_words_enter_the_queue_as_learner_sourced(db_session, enabled_intake):
    user = _user(db_session)
    artefact = _service(db_session, _FakeLLM(_letter_reading())).submit_text(
        user, text=LANDLORD_LETTER
    )

    rows = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id)
        .all()
    )
    assert rows
    assert {row.provenance for row in rows} == {LEARNER_SOURCED_PROVENANCE}
    assert {row.provenance_ref for row in rows} == {str(artefact.id)}
    assert artefact.queued_word_ids


def test_wp29_reads_them_as_targets(db_session, enabled_intake):
    user = _user(db_session)
    _service(db_session, _FakeLLM(_letter_reading())).submit_text(user, text=LANDLORD_LETTER)
    targets = learner_sourced_targets(db_session, user)
    assert any("signalement" in target for target in targets)
    # A learner with no artefacts contributes no targets at all.
    assert learner_sourced_targets(db_session, _user(db_session)) == frozenset()


def test_a_second_artefact_never_resets_a_card_the_learner_is_building(db_session, enabled_intake):
    """An artefact must not reset a schedule the learner has been building for weeks."""

    user = _user(db_session)
    service = _service(db_session, _FakeLLM(_letter_reading()))
    first = service.submit_text(user, text=LANDLORD_LETTER)
    word_id = first.queued_word_ids[0]

    row = (
        db_session.query(UserVocabularyProgress)
        .filter(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id == word_id,
        )
        .one()
    )
    row.state = "review"
    row.stability = 42.0
    row.due_at = datetime.now(UTC) + timedelta(days=30)
    db_session.commit()

    second = service.submit_text(user, text=LANDLORD_LETTER + "\nPS : merci.")
    db_session.refresh(row)
    assert row.stability == 42.0
    assert row.state == "review"
    # It is still a target, and it now points at the newest document that
    # brought it back into the learner's life.
    assert row.provenance == LEARNER_SOURCED_PROVENANCE
    assert row.provenance_ref == str(second.id)


# ===========================================================================
# 7. privacy
# ===========================================================================


def test_intake_never_writes_story_canon():
    """An `ast` scan, the same guard WP-31 put on rehearsals.

    A document a learner brought in is biography, not fiction. If this module
    ever imports a serial or living-story writer, this fails the build rather
    than waiting for someone to notice their gas bill in Romy's Paris.
    """

    source = Path("app/services/intake.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = ("serial", "living_story", "story_engine", "daily_journey", "graphic_novel")
    offenders = [
        name
        for name in imported
        if any(part in name for part in forbidden)
    ]
    assert offenders == [], f"intake.py must not import story writers: {offenders}"


def test_the_document_never_reaches_telemetry(db_session, enabled_intake):
    user = _user(db_session)
    _service(db_session, _FakeLLM(_letter_reading())).submit_text(user, text=LANDLORD_LETTER)
    events = db_session.query(PilotEvent).filter(PilotEvent.user_id == user.id).all()
    assert events
    for event in events:
        blob = json.dumps(event.payload or {}, ensure_ascii=False).lower()
        for secret in ("chauffage", "marchand", "berthier", "septembre"):
            assert secret not in blob


def test_deleting_an_artefact_deletes_the_task_derived_from_it(db_session, enabled_intake):
    user = _user(db_session)
    service = _service(db_session, _FakeLLM(_letter_reading()))
    artefact = service.submit_text(user, text=LANDLORD_LETTER)
    mission_id = artefact.mission_id
    artefact_id = artefact.id
    assert mission_id is not None

    assert service.delete(user, artefact_id) is True

    assert db_session.get(LearnerArtefact, artefact_id) is None
    # The mission quotes the document, so it goes too.
    assert db_session.get(RealWorldMission, mission_id) is None
    # The words are the learner's now — kept, but pointing at nothing.
    rows = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id)
        .all()
    )
    assert rows
    assert {row.provenance_ref for row in rows} == {None}
    assert {row.provenance for row in rows} == {LEARNER_SOURCED_PROVENANCE}


def test_one_learner_cannot_read_or_delete_anothers_document(db_session, enabled_intake):
    owner = _user(db_session)
    stranger = _user(db_session)
    service = _service(db_session, _FakeLLM(_menu_reading()))
    artefact = service.submit_text(owner, text=CAFE_MENU)

    assert service.get(stranger, artefact.id) is None
    assert service.delete(stranger, artefact.id) is False
    assert db_session.get(LearnerArtefact, artefact.id) is not None
    assert service.list_for(stranger) == []


def test_public_view_is_the_only_shape_that_leaves(db_session, enabled_intake):
    user = _user(db_session)
    artefact = _service(db_session, _FakeLLM(_menu_reading())).submit_text(user, text=CAFE_MENU)
    view = public_view(artefact)
    assert view is not None
    assert set(view) == {
        "id",
        "version",
        "status",
        "source_kind",
        "source_text",
        "artefact",
        "task",
        "mission_id",
        "queued_word_count",
        "created_at",
    }
    assert "user_id" not in view
    assert public_view(None) is None


# ===========================================================================
# 8. the money
# ===========================================================================


def test_every_call_writes_a_priced_row_including_the_one_that_failed(db_session, enabled_intake):
    user = _user(db_session)
    _service(db_session, _FakeLLM(_menu_reading(), cost=0.004)).submit_text(user, text=CAFE_MENU)
    _service(db_session, _FakeLLM(None)).submit_text(user, text=LANDLORD_LETTER)

    events = (
        db_session.query(PilotEvent)
        .filter(PilotEvent.user_id == user.id, PilotEvent.event_type == INTAKE_EVENT_TYPE)
        .all()
    )
    assert len(events) == 2
    assert sum(float(event.cost_usd or 0.0) for event in events) == pytest.approx(0.004)
    assert {bool(event.payload.get("failed")) for event in events} == {False, True}


def test_the_weekly_cap_and_the_cost_ceiling_refuse_separately(db_session, monkeypatch):
    user = _user(db_session)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_CAP", 1)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_COST_CEILING_USD", 10.0)

    service = _service(db_session, _FakeLLM(_menu_reading()))
    service.submit_text(user, text=CAFE_MENU)
    with pytest.raises(IntakeRefused) as capped:
        service.submit_text(user, text=LANDLORD_LETTER)
    assert capped.value.code == "weekly_cap_reached"

    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_CAP", 20)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_COST_CEILING_USD", 0.001)
    with pytest.raises(IntakeRefused) as broke:
        service.submit_text(user, text=LANDLORD_LETTER)
    assert broke.value.code == "cost_ceiling_reached"

    monkeypatch.setattr(settings, "ATELIER_INTAKE_ENABLED", False)
    with pytest.raises(IntakeRefused) as off:
        service.submit_text(user, text=LANDLORD_LETTER)
    assert off.value.code == "intake_disabled"


def test_an_unread_artefact_still_counts_against_the_cap(db_session, monkeypatch):
    """The call was already paid for. Failure must not be a free retry loop."""

    user = _user(db_session)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_CAP", 1)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_COST_CEILING_USD", 0.0)

    _service(db_session, _FakeLLM(None)).submit_text(user, text=CAFE_MENU)
    assert cap_state(db_session, user).used == 1
    with pytest.raises(IntakeRefused):
        _service(db_session, _FakeLLM(_menu_reading())).submit_text(user, text=CAFE_MENU)


def test_the_digest_line_says_nothing_rather_than_zero_percent(db_session, enabled_intake):
    now = datetime.now(UTC)
    quiet = (now - timedelta(days=400), now - timedelta(days=399))
    assert "nothing to report" in intake_digest_line(db_session, since=quiet[0], until=quiet[1])

    window = (now - timedelta(seconds=2), now + timedelta(days=1))
    user = _user(db_session)
    _service(db_session, _FakeLLM(_menu_reading())).submit_text(user, text=CAFE_MENU)
    line = intake_digest_line(db_session, since=window[0], until=window[1])
    assert "documents read" in line
    assert "US$" in line


def test_messages_builders_are_deterministic_and_carry_the_document():
    messages = text_messages(document=CAFE_MENU, band="A2", native_language="en")
    assert messages[0]["role"] == "user"
    assert "Trois Ponts" in messages[0]["content"]

    photo = vision_messages(
        image_bytes=b"abc", content_type="image/png", band="A2", native_language="en"
    )
    assert photo[0]["content"][1]["image_url"]["url"] == "data:image/png;base64,YWJj"
