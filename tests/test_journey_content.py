"""WP-03 — bounded scenario briefs and dependable content.

These tests pin the *contract* of ``app.services.journey_content``: schema and
length validation, world-bible integrity, level suitability, media fallback,
bounded generation retries, content-version pinning, and the read-only serial
adapter. They deliberately do not assert real model quality — that is WP-12's
reviewed sample set.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from app.config import settings
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.services import journey_content as jc
from app.services.journey_contracts import (
    CapabilityKey,
    ContentUnavailable,
    InputMode,
    ScenarioBrief,
)
from app.services.llm_service import LLMResult

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "daily_journey_v1" / "public"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_content_cache():
    jc.reset_content_cache()
    yield
    jc.reset_content_cache()


def _user(
    db_session,
    *,
    cefr: str = "A1.1",
    native: str = "en",
    proficiency: str = "beginner",
) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@journey.test",
        hashed_password="x",
        native_language=native,
        target_language="fr",
        proficiency_level=proficiency,
        cefr_estimate=cefr,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / f"{name}.json").read_text(encoding="utf-8"))["response"]


def _cafe_brief(db_session, user) -> ScenarioBrief:
    brief = jc.resolve_scenario_brief(
        db_session, user=user, scenario_key=CapabilityKey.ORDER_AT_CAFE
    )
    assert isinstance(brief, ScenarioBrief)
    return brief


def _copy_content_root(tmp_path: Path) -> Path:
    root = tmp_path / "journey_scenarios"
    shutil.copytree(jc.SCENARIO_DATA_ROOT, root)
    return root


def _patch_spec(root: Path, version: str, scenario_key: str, mutate) -> None:
    path = root / version / f"{scenario_key}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class _FakeLLM:
    """Stand-in provider. Counts calls so bounded retries can be asserted."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def generate_chat_completion(self, messages, **kwargs):
        self.calls += 1
        item = self._responses[min(self.calls - 1, len(self._responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return LLMResult(
            provider="fake",
            model="fake-model",
            content=item,
            prompt_tokens=11,
            completion_tokens=22,
            total_tokens=33,
            cost=0.0012,
            raw_response={},
        )


class _ForbiddenLLM:
    def __init__(self, *args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("the authored path must not construct an LLM client")


_VALID_VARIATION = json.dumps(
    {
        "setup_fr": "Le canal est gris. Tu entres au Mistral. Margaux lève les yeux.",
        "setup_native": "The canal is grey. You step into Le Mistral. Margaux looks up.",
        "opening_line_fr": "Bonsoir ! Vous restez ou c'est à emporter ?",
        "response_opening_line_fr": "Bon, je vous sers quoi ?",
        "resolution_lines": {
            "served_at_counter": "Au comptoir, très bien. Ça arrive.",
            "served_at_terrace": "En terrasse alors. Je vous apporte ça.",
            "takeaway": "À emporter. Deux minutes.",
            "not_ordered": "Pas de souci, prenez votre temps.",
        },
    },
    ensure_ascii=False,
)

_LANDLORD_VARIATION = json.dumps(
    {
        "setup_fr": "Tu entres au Mistral avec ton dossier sous le bras.",
        "setup_native": "You walk into Le Mistral with your file under your arm.",
        "opening_line_fr": "Bonsoir ! Vous avez signé le bail ?",
        "response_opening_line_fr": "Il faut payer la caution avant vendredi.",
        "resolution_lines": {
            "served_at_counter": "Je vous garde la quittance derrière le comptoir.",
            "served_at_terrace": "En terrasse alors.",
            "takeaway": "À emporter. Deux minutes.",
            "not_ordered": "Repassez quand le dossier sera signé.",
        },
    },
    ensure_ascii=False,
)


def _enable_fake_llm(monkeypatch, fake) -> None:
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True)
    monkeypatch.setattr(jc, "LLMService", lambda *args, **kwargs: fake)


# --------------------------------------------------------------------------
# authored content: shape, length, and the three acceptance scenes
# --------------------------------------------------------------------------


def test_three_authored_families_validate_at_a1_and_a2(db_session):
    for scenario_key in jc.SCENARIO_PRIORITY:
        for band in ("A1", "A2"):
            rules = jc.scenario_content_rules(scenario_key, level_band=band)
            assert rules is not None, f"{scenario_key} has no {band} rules"
            user = _user(db_session, cefr=f"{band}.1")
            brief = jc.resolve_scenario_brief(
                db_session, user=user, scenario_key=scenario_key
            )
            assert isinstance(brief, ScenarioBrief), brief
            assert brief.level_band == band
            assert jc.validate_scenario_brief(brief, rules=rules) == []


def test_every_scene_has_a_beginning_a_need_and_an_achievable_ending(db_session):
    user = _user(db_session)
    for brief in jc.list_available_scenarios(db_session, user=user):
        # beginning
        assert brief.setup_fr.strip()
        assert brief.setup_native.strip()
        assert brief.opening_line_fr and brief.opening_line_fr.strip()
        # explicit communicative need
        assert brief.objective_native.strip()
        assert brief.response_task.objective_native.strip()
        assert brief.response_task.required_intents
        # achievable ending, inside the turn limit
        assert brief.response_task.allowed_outcomes
        assert 1 <= brief.response_task.max_turns <= 2
        for outcome in brief.response_task.allowed_outcomes:
            assert brief.resolution_lines[outcome].strip()
            assert brief.resolution_summaries[outcome].strip()


def test_cafe_brief_reproduces_the_frozen_public_payload(db_session):
    user = _user(db_session)
    brief = _cafe_brief(db_session, user)
    fixture = _fixture("cafe_journey_created")

    assert brief.public_descriptor() == fixture["scenario"]
    scene = fixture["steps"][0]["prompt"]
    assert brief.setup_fr == scene["setup_fr"]
    assert brief.setup_native == scene["setup_native"]
    assert brief.opening_line_fr == scene["character_line_fr"]
    respond = fixture["steps"][2]["prompt"]
    assert brief.response_task.opening_line_fr == respond["character_line_fr"]
    assert brief.response_task.objective_native == respond["objective_native"]
    resolution = fixture["steps"][3]["prompt"]
    outcome = resolution["outcome_key"]
    # WP-12 defect D-2: the frozen fixture's ending names a coffee, so it is now
    # the ending of a learner who *ordered* one. The authored template still
    # reproduces the frozen text verbatim for that learner, and only for them;
    # with no drink identified it falls back to wording that names no drink.
    # `cafe_journey_created` is a PRE-ANSWER journey: the learner has ordered
    # nothing yet, so its ending must be the generic form that names no drink.
    # Naming one there was defect D-2.
    assert (
        jc.render_authored_text(brief.resolution_lines[outcome])
        == resolution["character_line_fr"]
    )
    assert (
        jc.render_authored_text(brief.resolution_summaries[outcome])
        == resolution["summary_native"]
    )
    for text in (resolution["character_line_fr"], resolution["summary_native"]):
        assert "café" not in text.lower() and "coffee" not in text.lower(), text

    # And once the learner really orders a coffee, the same template renders the
    # specific text the ANSWERED fixtures record.
    answered = _fixture("completed")
    answered_resolution = next(
        step["prompt"] for step in answered["steps"] if step["kind"] == "resolution"
    )
    ordered_a_coffee = {"drink_cap": "Un café", "drink_native": "coffee"}
    assert (
        jc.render_authored_text(
            brief.resolution_lines[answered_resolution["outcome_key"]], ordered_a_coffee
        )
        == answered_resolution["character_line_fr"]
    )


@pytest.mark.parametrize(
    ("native", "fixture_name"),
    [("de", "controls_de"), ("fr", "controls_fr"), ("en", "first_day")],
)
def test_control_language_resolves_native_strings(db_session, native, fixture_name):
    user = _user(db_session, native=native)
    brief = _cafe_brief(db_session, user)
    assert brief.control_language == native
    assert brief.public_descriptor() == _fixture(fixture_name)["available"]


def test_unsupported_control_language_falls_back_to_english(db_session):
    user = _user(db_session, native="pt-BR")
    brief = _cafe_brief(db_session, user)
    assert brief.control_language == "en"
    assert brief.objective_native == _fixture("first_day")["available"]["objective_native"]


def test_over_long_setup_is_rejected_for_the_level(db_session):
    user = _user(db_session)
    brief = _cafe_brief(db_session, user)
    rules = jc.scenario_content_rules(CapabilityKey.ORDER_AT_CAFE, level_band="A1")
    too_long = replace(brief, setup_fr=" ".join(["mot"] * 60))
    problems = jc.validate_scenario_brief(too_long, rules=rules)
    assert any("setup_fr is 60 words" in problem for problem in problems)


def test_outcome_keys_must_stay_typed_and_complete(db_session):
    user = _user(db_session)
    brief = _cafe_brief(db_session, user)
    rules = jc.scenario_content_rules(CapabilityKey.ORDER_AT_CAFE, level_band="A1")
    missing = replace(
        brief,
        resolution_lines={
            key: value
            for key, value in brief.resolution_lines.items()
            if key != "takeaway"
        },
    )
    problems = jc.validate_scenario_brief(missing, rules=rules)
    assert any("resolution lines do not cover" in problem for problem in problems)


def test_suggested_reply_may_not_leak_into_a_pre_answer_field(db_session):
    user = _user(db_session)
    brief = _cafe_brief(db_session, user)
    rules = jc.scenario_content_rules(CapabilityKey.ORDER_AT_CAFE, level_band="A1")
    assert brief.response_task.suggested_response_fr
    leaked = replace(
        brief,
        response_task=replace(
            brief.response_task,
            opening_line_fr=(
                "Alors, qu'est-ce que je vous sers ? "
                + brief.response_task.suggested_response_fr
            ),
        ),
    )
    problems = jc.validate_scenario_brief(leaked, rules=rules)
    assert any("leaks into a pre-answer field" in problem for problem in problems)


# --------------------------------------------------------------------------
# world-bible integrity
# --------------------------------------------------------------------------


def test_unknown_cast_and_location_are_rejected(db_session):
    user = _user(db_session)
    brief = _cafe_brief(db_session, user)
    rules = jc.scenario_content_rules(CapabilityKey.ORDER_AT_CAFE, level_band="A1")

    invented_cast = replace(
        brief,
        character_id="monsieur_dupont",
        character_name="Monsieur Dupont",
        response_task=replace(brief.response_task, character_id="monsieur_dupont"),
    )
    assert any(
        "unknown world-bible character id" in problem
        for problem in jc.validate_scenario_brief(invented_cast, rules=rules)
    )

    invented_location = replace(brief, location_id="le_petit_zinc")
    assert any(
        "unknown world-bible location id" in problem
        for problem in jc.validate_scenario_brief(invented_location, rules=rules)
    )

    renamed = replace(brief, character_name="Brigitte")
    assert any(
        "is not a form of" in problem
        for problem in jc.validate_scenario_brief(renamed, rules=rules)
    )


def test_authored_file_with_unknown_cast_yields_content_unavailable(
    db_session, tmp_path, monkeypatch
):
    root = _copy_content_root(tmp_path)
    _patch_spec(
        root,
        jc.CURRENT_CONTENT_VERSION,
        "order_at_cafe",
        lambda payload: payload.update(
            {"character_id": "monsieur_dupont", "character_name": "Monsieur Dupont"}
        ),
    )
    monkeypatch.setattr(jc, "SCENARIO_DATA_ROOT", root)
    jc.reset_content_cache()

    user = _user(db_session)
    result = jc.resolve_scenario_brief(
        db_session, user=user, scenario_key=CapabilityKey.ORDER_AT_CAFE
    )
    assert isinstance(result, ContentUnavailable)
    assert result.reason == "authored_content_invalid"
    assert result.retry_allowed is False


def test_cafe_dialogue_cannot_switch_to_landlord_paperwork(db_session):
    user = _user(db_session)
    brief = _cafe_brief(db_session, user)
    rules = jc.scenario_content_rules(CapabilityKey.ORDER_AT_CAFE, level_band="A1")

    paperwork = replace(
        brief,
        response_task=replace(
            brief.response_task,
            opening_line_fr="Il faut signer le bail et payer la caution avant vendredi.",
        ),
    )
    problems = jc.validate_scenario_brief(paperwork, rules=rules)
    assert any("off-topic term" in problem for problem in problems)

    register_break = replace(
        brief,
        response_task=replace(
            brief.response_task, opening_line_fr="Alors, tu prends quoi ?"
        ),
    )
    assert any(
        "register break" in problem
        for problem in jc.validate_scenario_brief(register_break, rules=rules)
    )


def test_tu_scenes_reject_a_vous_slip(db_session):
    user = _user(db_session, cefr="A2.1")
    brief = jc.resolve_scenario_brief(
        db_session, user=user, scenario_key=CapabilityKey.EXPLAIN_DELAY
    )
    assert isinstance(brief, ScenarioBrief)
    rules = jc.scenario_content_rules(CapabilityKey.EXPLAIN_DELAY, level_band="A2")
    assert rules.register == "tu"
    slipped = replace(
        brief,
        response_task=replace(
            brief.response_task, opening_line_fr="Où êtes-vous exactement ?"
        ),
    )
    assert any(
        "register break" in problem
        for problem in jc.validate_scenario_brief(slipped, rules=rules)
    )


# --------------------------------------------------------------------------
# level suitability
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cefr", "proficiency", "expected"),
    [
        ("A1.1", "beginner", "A1"),
        ("A2.3", "intermediate", "A2"),
        ("B1.1", "intermediate", "B1"),
        ("", "advanced", "B2"),
        ("", "", "A1"),
        ("nonsense", "", "A1"),
    ],
)
def test_learner_level_band(db_session, cefr, proficiency, expected):
    user = _user(db_session, cefr=cefr, proficiency=proficiency)
    assert jc.learner_level_band(user) == expected


def test_higher_level_learner_gets_the_a2_scene_with_an_honest_note(db_session):
    user = _user(db_session, cefr="B2.1")
    brief = _cafe_brief(db_session, user)
    # the brief reports the band it was actually written at, never the learner's
    assert brief.level_band == "A2"
    assert "A2" in brief.objective_native

    fit = jc.resolve_level_fit(user=user, brief=brief)
    assert fit.learner_band == "B2"
    assert fit.content_band == "A2"
    assert fit.is_exact is False
    assert fit.note_native and "A2" in fit.note_native


def test_exact_level_match_carries_no_suitability_note(db_session):
    user = _user(db_session, cefr="A1.2")
    brief = _cafe_brief(db_session, user)
    fit = jc.resolve_level_fit(user=user, brief=brief)
    assert fit.is_exact is True
    assert fit.note_native is None
    assert brief.objective_native == _fixture("first_day")["available"]["objective_native"]


def test_german_learner_above_the_authored_ceiling_reads_a_german_note(db_session):
    user = _user(db_session, cefr="C1.1", native="de")
    brief = _cafe_brief(db_session, user)
    assert brief.level_band == "A2"
    assert "Niveau" in brief.objective_native


# --------------------------------------------------------------------------
# media
# --------------------------------------------------------------------------


def test_missing_media_yields_a_null_image_and_a_usable_scene(
    db_session, tmp_path, monkeypatch
):
    monkeypatch.setattr(jc, "MEDIA_PUBLIC_ROOT", tmp_path)
    user = _user(db_session)
    brief = _cafe_brief(db_session, user)

    assert brief.image_url is None
    assert brief.setup_fr
    assert brief.opening_line_fr
    assert brief.response_task.opening_line_fr
    rules = jc.scenario_content_rules(CapabilityKey.ORDER_AT_CAFE, level_band="A1")
    assert jc.validate_scenario_brief(brief, rules=rules) == []
    assert brief.public_descriptor()["image_url"] is None


def test_declared_media_resolves_to_the_existing_serial_convention(db_session):
    user = _user(db_session)
    brief = _cafe_brief(db_session, user)
    assert brief.image_url == "/assets/serial/locations/le_mistral-counter.webp"
    repo_asset = jc.MEDIA_PUBLIC_ROOT / brief.image_url.lstrip("/")
    if jc.MEDIA_PUBLIC_ROOT.is_dir():
        assert repo_asset.is_file()


def test_inline_base64_art_is_rejected(db_session):
    user = _user(db_session)
    brief = _cafe_brief(db_session, user)
    rules = jc.scenario_content_rules(CapabilityKey.ORDER_AT_CAFE, level_band="A1")
    inline = replace(brief, image_url="data:image/webp;base64,AAAA")
    problems = jc.validate_scenario_brief(inline, rules=rules)
    assert any("base64" in problem for problem in problems)
    assert jc.resolve_media_url("data:image/webp;base64,AAAA") is None


# --------------------------------------------------------------------------
# generation: bounded, validated, cached, and never mandatory
# --------------------------------------------------------------------------


def test_authored_fallback_needs_no_model_call(db_session, monkeypatch):
    monkeypatch.setattr(jc, "LLMService", _ForbiddenLLM)
    assert settings.ATELIER_LLM_ENABLED is False
    user = _user(db_session)

    brief = jc.build_scenario_context(db_session, user=user)

    assert isinstance(brief, ScenarioBrief)
    assert brief.scenario_key is CapabilityKey.ORDER_AT_CAFE
    assert brief.content_version == jc.CURRENT_CONTENT_VERSION
    assert brief.setup_fr == _fixture("cafe_journey_created")["steps"][0]["prompt"]["setup_fr"]


def test_rejected_model_output_falls_back_to_the_authored_scene(db_session, monkeypatch):
    fake = _FakeLLM([_LANDLORD_VARIATION])
    _enable_fake_llm(monkeypatch, fake)
    user = _user(db_session)

    brief = jc.build_scenario_context(db_session, user=user)

    assert isinstance(brief, ScenarioBrief)
    assert fake.calls == jc.MAX_GENERATION_ATTEMPTS
    assert "bail" not in brief.setup_fr.lower()
    assert "caution" not in brief.response_task.opening_line_fr.lower()
    assert brief.setup_fr == _fixture("cafe_journey_created")["steps"][0]["prompt"]["setup_fr"]


def test_generation_retries_are_bounded(db_session, monkeypatch):
    fake = _FakeLLM(["not json at all"])
    _enable_fake_llm(monkeypatch, fake)
    user = _user(db_session)

    brief = jc.build_scenario_context(db_session, user=user)

    assert isinstance(brief, ScenarioBrief)
    assert fake.calls == jc.MAX_GENERATION_ATTEMPTS


def test_provider_errors_are_bounded_and_fall_back(db_session, monkeypatch):
    fake = _FakeLLM([RuntimeError("provider down")])
    _enable_fake_llm(monkeypatch, fake)
    user = _user(db_session)

    brief = jc.build_scenario_context(db_session, user=user)

    assert isinstance(brief, ScenarioBrief)
    assert fake.calls == jc.MAX_GENERATION_ATTEMPTS
    assert brief.setup_fr == _fixture("cafe_journey_created")["steps"][0]["prompt"]["setup_fr"]


def test_valid_generation_is_used_validated_and_cached(db_session, monkeypatch):
    fake = _FakeLLM([_VALID_VARIATION])
    _enable_fake_llm(monkeypatch, fake)
    user = _user(db_session)

    first = jc.build_scenario_context(db_session, user=user)
    assert isinstance(first, ScenarioBrief)
    assert fake.calls == 1
    assert first.setup_fr.startswith("Le canal est gris.")
    rules = jc.scenario_content_rules(CapabilityKey.ORDER_AT_CAFE, level_band="A1")
    assert jc.validate_scenario_brief(first, rules=rules) == []
    # the authored, fixed parts survive a re-dress
    assert first.objective_key == "order_at_cafe.counter_drink"
    assert set(first.resolution_lines) == set(rules.allowed_outcomes)

    second = jc.build_scenario_context(db_session, user=user)
    assert isinstance(second, ScenarioBrief)
    assert fake.calls == 1, "a cached variation must not cost a second model call"
    assert second.setup_fr == first.setup_fr


def test_generation_cost_is_recorded_on_the_pilot_ledger(db_session, monkeypatch):
    from app.db.models.pilot_event import PilotEvent

    fake = _FakeLLM([_VALID_VARIATION])
    _enable_fake_llm(monkeypatch, fake)
    user = _user(db_session)

    jc.build_scenario_context(db_session, user=user)
    db_session.flush()

    events = (
        db_session.query(PilotEvent)
        .filter(PilotEvent.user_id == user.id, PilotEvent.event_type == jc.GENERATED_EVENT)
        .all()
    )
    assert len(events) == 1
    assert events[0].cost_usd == pytest.approx(0.0012)
    assert events[0].payload["prompt_version"] == jc.JOURNEY_PROMPT_VERSION


def test_list_available_scenarios_never_calls_a_model(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True)
    monkeypatch.setattr(jc, "LLMService", _ForbiddenLLM)
    user = _user(db_session)

    briefs = jc.list_available_scenarios(db_session, user=user)

    assert [brief.scenario_key for brief in briefs] == list(jc.SCENARIO_PRIORITY)


def test_unknown_scenario_key_is_honestly_unavailable(db_session):
    user = _user(db_session)
    result = jc.resolve_scenario_brief(db_session, user=user, scenario_key="buy_a_train_ticket")
    assert isinstance(result, ContentUnavailable)
    assert result.reason == "scenario_not_authored"
    assert result.retry_allowed is False


# --------------------------------------------------------------------------
# content-version pinning
# --------------------------------------------------------------------------


def test_a_content_version_bump_does_not_strand_a_pinned_brief(
    db_session, tmp_path, monkeypatch
):
    root = _copy_content_root(tmp_path)
    shutil.copytree(root / "journey-content-v1", root / "journey-content-v2")
    for scenario_key in ("order_at_cafe", "arrange_meeting", "explain_delay"):
        _patch_spec(
            root,
            "journey-content-v2",
            scenario_key,
            lambda payload: payload.update({"content_version": "journey-content-v2"}),
        )
    _patch_spec(
        root,
        "journey-content-v2",
        "order_at_cafe",
        lambda payload: payload["variants"][0].update({"title_fr": "Un café, deuxième service"}),
    )
    monkeypatch.setattr(jc, "SCENARIO_DATA_ROOT", root)
    monkeypatch.setattr(jc, "CURRENT_CONTENT_VERSION", "journey-content-v2")
    jc.reset_content_cache()

    user = _user(db_session)
    assert jc.available_content_versions() == ["journey-content-v1", "journey-content-v2"]

    fresh = jc.build_scenario_context(db_session, user=user)
    assert isinstance(fresh, ScenarioBrief)
    assert fresh.content_version == "journey-content-v2"
    assert fresh.title_fr == "Un café, deuxième service"

    pinned = jc.resolve_scenario_brief(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        content_version="journey-content-v1",
        level_band="A1",
    )
    assert isinstance(pinned, ScenarioBrief)
    assert pinned.content_version == "journey-content-v1"
    assert pinned.title_fr == "Un café au Mistral"


def test_a_pinned_level_band_survives_a_learner_level_change(db_session):
    user = _user(db_session, cefr="B1.1")
    pinned = jc.resolve_scenario_brief(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        content_version=jc.CURRENT_CONTENT_VERSION,
        level_band="A1",
    )
    assert isinstance(pinned, ScenarioBrief)
    assert pinned.level_band == "A1"
    assert pinned.title_fr == "Un café au Mistral"


def test_a_retired_content_version_reports_itself_honestly(db_session):
    user = _user(db_session)
    result = jc.resolve_scenario_brief(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        content_version="journey-content-v0",
    )
    assert isinstance(result, ContentUnavailable)
    assert result.reason == "content_version_unavailable"


# --------------------------------------------------------------------------
# serial adapter
# --------------------------------------------------------------------------


def _serial_thread(
    db_session,
    user: User,
    *,
    world_version: str = "paris-v2",
    episode_status: str | None = "available",
    location_id: str | None = "le_mistral",
) -> tuple[SerialThread, SerialEpisode | None]:
    thread = SerialThread(
        id=uuid4(),
        user_id=user.id,
        status="active",
        world_bible={"world_bible_version": world_version},
        state={},
        news_seed={},
        current_episode_index=3,
    )
    db_session.add(thread)
    db_session.flush()
    episode = None
    if episode_status is not None:
        episode = SerialEpisode(
            id=uuid4(),
            thread_id=thread.id,
            episode_index=3,
            kind="feuilleton",
            location_id=location_id,
            hook={"text": "SPOILER: Margaux ferme Le Mistral la semaine prochaine."},
            hook_from_previous={},
            state_delta={},
            brief_payload={"location_id": location_id},
            status=episode_status,
        )
        db_session.add(episode)
    db_session.commit()
    return thread, episode


def test_serial_adapter_binds_a_ready_current_beat(db_session):
    user = _user(db_session)
    thread, episode = _serial_thread(db_session, user)

    scene = jc.derive_serial_side_scene(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        location_id="le_mistral",
    )

    assert scene.reason == "bound_to_current_beat"
    assert scene.is_fallback is False
    assert scene.thread_id == str(thread.id)
    assert scene.episode_id == str(episode.id)

    brief = _cafe_brief(db_session, user)
    assert brief.serial_thread_id == str(thread.id)
    assert brief.serial_episode_id == str(episode.id)
    assert brief.is_authored_fallback is False


@pytest.mark.parametrize(
    ("episode_status", "expected_reason"),
    [
        ("delayed", "serial_episode_delayed"),
        ("generation_failed", "serial_episode_delayed"),
        ("generating", "serial_episode_not_ready"),
        ("completed", "serial_episode_completed"),
    ],
)
def test_delayed_or_unready_serial_source_falls_back(
    db_session, episode_status, expected_reason
):
    user = _user(db_session)
    _serial_thread(db_session, user, episode_status=episode_status)

    scene = jc.derive_serial_side_scene(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        location_id="le_mistral",
    )

    assert scene.reason == expected_reason
    assert scene.is_fallback is True
    assert scene.episode_id is None

    brief = _cafe_brief(db_session, user)
    assert brief.is_authored_fallback is True
    assert brief.serial_thread_id is None
    assert brief.serial_episode_id is None
    # the authored side scene is coherent on its own
    rules = jc.scenario_content_rules(CapabilityKey.ORDER_AT_CAFE, level_band="A1")
    assert jc.validate_scenario_brief(brief, rules=rules) == []


def test_superseded_world_bible_falls_back(db_session):
    user = _user(db_session)
    _serial_thread(db_session, user, world_version="paris-v1")

    scene = jc.derive_serial_side_scene(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        location_id="le_mistral",
    )

    assert scene.reason == "world_bible_superseded"
    assert scene.is_fallback is True
    assert scene.episode_id is None


def test_incompatible_serial_location_falls_back(db_session):
    user = _user(db_session)
    _serial_thread(db_session, user, location_id="office_admin")

    scene = jc.derive_serial_side_scene(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        location_id="le_mistral",
    )

    assert scene.reason == "serial_location_mismatch"
    assert scene.is_fallback is True
    assert scene.episode_id is None


def test_no_serial_thread_falls_back(db_session):
    user = _user(db_session)
    scene = jc.derive_serial_side_scene(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        location_id="le_mistral",
    )
    assert scene.reason == "no_serial_thread"
    assert scene.is_fallback is True


def test_serial_adapter_is_read_only_and_never_advances_the_episode(db_session):
    user = _user(db_session)
    thread, episode = _serial_thread(db_session, user)
    before_index = thread.current_episode_index
    before_status = episode.status
    before_completed = episode.completed_at

    jc.derive_serial_side_scene(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        location_id="le_mistral",
    )
    brief = _cafe_brief(db_session, user)

    assert not db_session.new
    assert not db_session.dirty
    assert not db_session.deleted
    db_session.refresh(thread)
    db_session.refresh(episode)
    assert thread.current_episode_index == before_index
    assert episode.status == before_status
    assert episode.completed_at is before_completed
    # the next-beat teaser must never reach the journey
    spoiler = episode.hook["text"]
    for text in (
        brief.setup_fr,
        brief.setup_native,
        brief.opening_line_fr or "",
        brief.response_task.opening_line_fr,
        *brief.resolution_lines.values(),
    ):
        assert spoiler not in text
        assert "SPOILER" not in text


# --------------------------------------------------------------------------
# affordances / rules lookups used by neighbouring packages
# --------------------------------------------------------------------------


def test_target_affordances_and_required_facts_are_exposed_per_level():
    a1 = jc.scenario_target_affordances(CapabilityKey.ORDER_AT_CAFE, level_band="A1")
    a2 = jc.scenario_target_affordances(CapabilityKey.ORDER_AT_CAFE, level_band="A2")
    assert "un café" in a1
    assert a1 != a2
    facts = jc.scenario_required_facts(CapabilityKey.ORDER_AT_CAFE, level_band="A1")
    assert facts and all(isinstance(item, str) for item in facts)
    assert jc.scenario_target_affordances("buy_a_train_ticket") == []


def test_rules_expose_the_declared_register_and_outcome_keys():
    rules = jc.scenario_content_rules(CapabilityKey.ORDER_AT_CAFE, level_band="A1")
    assert rules.register == "vous"
    assert set(rules.allowed_outcomes) == {
        "served_at_counter",
        "served_at_terrace",
        "takeaway",
        "not_ordered",
    }
    assert "bail" in rules.forbidden_terms
    assert jc.scenario_content_rules("buy_a_train_ticket") is None


def test_voice_input_mode_adds_a_private_transcription_note(db_session):
    user = _user(db_session)
    text_brief = jc.resolve_scenario_brief(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        input_mode=InputMode.TEXT,
    )
    voice_brief = jc.resolve_scenario_brief(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        input_mode=InputMode.VOICE,
    )
    assert isinstance(text_brief, ScenarioBrief)
    assert isinstance(voice_brief, ScenarioBrief)
    assert "transcription" not in text_brief.response_task.rubric_native
    assert "transcription" in voice_brief.response_task.rubric_native
    # the note is private evaluator guidance, never a learner-facing string
    assert "transcription" not in voice_brief.setup_native
    assert "transcription" not in voice_brief.objective_native
    assert text_brief.public_descriptor() == voice_brief.public_descriptor()


def test_serial_adapter_defaults_its_locations_from_the_authored_scenario(db_session):
    """``scenario_key`` alone is enough: the family's own location and its
    declared ``serial_locations`` drive compatibility."""

    user = _user(db_session)
    # Le Mistral is a declared compatible location for arrange_meeting…
    _serial_thread(db_session, user, location_id="le_mistral")
    bound = jc.derive_serial_side_scene(
        db_session, user=user, scenario_key=CapabilityKey.ARRANGE_MEETING
    )
    assert bound.reason == "bound_to_current_beat"
    assert bound.is_fallback is False

    # …and for explain_delay too, which also declares Le Mistral compatible.
    assert (
        jc.derive_serial_side_scene(
            db_session, user=user, scenario_key=CapabilityKey.EXPLAIN_DELAY
        ).reason
        == "bound_to_current_beat"
    )

    # A location no family declares falls back instead of binding.
    other = _user(db_session)
    _serial_thread(db_session, other, location_id="buttes_chaumont")
    assert (
        jc.derive_serial_side_scene(
            db_session, user=other, scenario_key=CapabilityKey.ORDER_AT_CAFE
        ).reason
        == "serial_location_mismatch"
    )
