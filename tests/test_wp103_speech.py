# ruff: noqa: F811 - the fixtures are imported by name and requested as arguments
"""WP-103 T1 «l'accent anglais» — the voices speak native French, at the band's pace.

The owner's first test: «everywhere the horrible English accent» and the radio
«too fast». The speech model is now steerable (``gpt-4o-mini-tts``) and every
line is spoken with its character's *instructions* and the pace of the
learner's band. What is pinned here is everything a test *can* pin:

* the instructions per character (native French, no English accent; Romy's
  light Montréal accent is the one exception) and the pace per band;
* what reaches the wire: ``instructions`` only to a model that takes them,
  ``speed`` only where it is known to work;
* the cache key — model, instructions version, pace and the instructions
  themselves — so audio spoken under any other spec is never served;
* the fallback to ``tts-1-hd`` when the steerable model errors (logged, and the
  clip records what really spoke it).

Whether it *sounds* French is not a test: it is the owner's listening sheet
(``docs/implementation/atelier-v2/listening-sheet-2026-09-29``).

**No paid call is made anywhere in this file.** Every synthesis goes to a fake
provider, and an autouse fixture puts a recorder in place of the HTTP client so
that even a path that reached the real provider could only record a request.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.episode_audio import EpisodeAudioClip
from app.db.models.line_audio import LineAudioClip
from app.db.models.pilot_event import PilotEvent
from app.services import cast_voices, episode_audio, line_audio
from app.services import llm_service as llm_module
from app.services.cast_voices import (
    CAST_VOICES,
    FALLBACK_SPEECH_MODEL,
    NARRATOR_ID,
    SPEECH_INSTRUCTIONS_VERSION,
    STEERABLE_SPEECH_MODEL,
    cache_key_is_current,
    pace_for_band,
    parse_cache_key,
    speech_instructions,
    speech_spec,
)
from tests.test_episode_audio import (  # noqa: F401 - fixtures
    FakeSynthesizer,
    audio_on,
    cost_rows,
    learner,
    make_scene,
)

MODEL = STEERABLE_SPEECH_MODEL
CAST = tuple(CAST_VOICES)


class _Recorder:
    """Stands in for ``httpx.Client``: records the request, returns fake audio."""

    posts: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> _Recorder:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def post(self, url: str, **kwargs: Any) -> Any:
        _Recorder.posts.append({"url": url, **kwargs})

        class Response:
            status_code = 200
            content = b"mp3:recorded"
            text = ""

        return Response()


@pytest.fixture(autouse=True)
def no_paid_call(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """The HTTP client is a recorder for every test here; the speech model is
    the default the deployment ships; the speed opt-in is unset."""

    _Recorder.posts = []
    monkeypatch.setattr(llm_module.httpx, "Client", _Recorder)
    monkeypatch.setattr(settings, "FEUILLETON_AUDIO_TTS_MODEL", MODEL)
    monkeypatch.setattr(settings, "FEUILLETON_AUDIO_STEERABLE_A1_SPEED", None)
    return _Recorder.posts


# ---------------------------------------------------------------------------
# 1. The deployment's default and the instructions per character
# ---------------------------------------------------------------------------


def test_the_shipped_default_is_the_steerable_model() -> None:
    field = type(settings).model_fields["FEUILLETON_AUDIO_TTS_MODEL"]
    assert field.default == "gpt-4o-mini-tts" == STEERABLE_SPEECH_MODEL
    assert FALLBACK_SPEECH_MODEL == "tts-1-hd"
    assert type(settings).model_fields["FEUILLETON_AUDIO_STEERABLE_A1_SPEED"].default is None


@pytest.mark.parametrize("person", [*CAST, NARRATOR_ID])
def test_every_person_is_told_to_speak_native_french_with_no_english_accent(person: str) -> None:
    text = speech_instructions(person, "B1")
    assert "français" in text and "locut" in text
    assert "accent anglais" in text, "the owner's complaint, named in every set of instructions"
    if person == "romy_tremblay":
        assert "Montréal" in text and "québécois" in text
        assert "accent parisien" not in text, "a Québécoise is not asked to fake a Paris accent"
    else:
        assert "accent parisien neutre" in text
        assert "sans aucun accent anglais" in text
        assert "québécois" not in text


def test_each_person_has_their_own_persona() -> None:
    texts = {person: speech_instructions(person, "B1") for person in [*CAST, NARRATOR_ID]}
    assert len(set(texts.values())) == len(texts), "two people were given the same instructions"
    # Age, warmth and register — the persona line names who is speaking.
    assert "Romy" in texts["romy_tremblay"] and "32 ans" in texts["romy_tremblay"]
    assert "Marin" in texts["marin_leveque"] and "douce" in texts["marin_leveque"]
    assert "Lila" in texts["lila_bonnet"]
    assert "Gus" in texts["augustin_de_roncourt"] and "théâtrale" in texts["augustin_de_roncourt"]
    assert "Margaux" in texts["margaux_barman"] and "sèche" in texts["margaux_barman"]
    assert "Marchand" in texts["landlord_marchand"] and "vouvoie" in texts["landlord_marchand"]
    assert "voix off" in texts[NARRATOR_ID]


def test_a_nickname_or_a_voice_only_id_is_the_same_person() -> None:
    assert speech_instructions("gus", "A2") == speech_instructions("augustin_de_roncourt", "A2")
    assert speech_instructions("marchand", "A2") == speech_instructions("landlord_marchand", "A2")
    assert speech_instructions(None, "A2") == speech_instructions("narrator", "A2")
    # A planned listening clip knows only its voice; the voice's owner speaks it.
    assert speech_instructions("voice:nova", "A1") == speech_instructions("romy_tremblay", "A1")
    assert speech_instructions("voice:sage", "A1") == speech_instructions(NARRATOR_ID, "A1")


def test_anyone_else_speaks_plain_native_french_not_a_cast_members_persona() -> None:
    stranger = speech_instructions("henriette_dubois", "B1")
    assert "accent parisien neutre" in stranger and "sans aucun accent anglais" in stranger
    assert all(stranger != speech_instructions(person, "B1") for person in [*CAST, NARRATOR_ID])
    assert stranger == speech_instructions("toi", "B1"), "the learner's own line is plain too"
    assert stranger == speech_instructions("voice:coral", "B1")


# ---------------------------------------------------------------------------
# 2. The pace per band
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "band,pace",
    [
        ("A1", "a1"), ("A1.1", "a1"), ("a1.2", "a1"),
        ("A2", "a2"), ("A2.2", "a2"),
        ("B1", "b1"), ("B1.2", "b1"), ("B2", "b1"), ("C1", "b1"), ("C2.1", "b1"),
        (None, "a1"), ("", "a1"), ("beginner", "a1"),
    ],
)
def test_the_band_names_the_pace(band: str | None, pace: str) -> None:
    assert pace_for_band(band) == pace


def test_the_instructions_carry_the_pace_of_the_band() -> None:
    a1 = speech_instructions("marin_leveque", "A1.2")
    a2 = speech_instructions("marin_leveque", "A2.1")
    b1 = speech_instructions("marin_leveque", "B1.1")
    assert "posé, articulé, sans traîner" in a1
    assert "naturel, un peu lent" in a2
    assert "naturel, celui d'une conversation courante" in b1
    assert len({a1, a2, b1}) == 3
    assert speech_instructions("marin_leveque", "B2") == b1 == speech_instructions("marin_leveque", "C1")
    # The persona does not change with the pace.
    persona = [line for line in a1.splitlines() if line.startswith("Personnage")]
    assert persona == [line for line in b1.splitlines() if line.startswith("Personnage")]


def test_only_a_steerable_model_is_sent_instructions() -> None:
    steerable = speech_spec("romy_tremblay", "A1", model=MODEL)
    dated = speech_spec("romy_tremblay", "A1", model="gpt-4o-mini-tts-2025-12-15")
    plain = speech_spec("romy_tremblay", "A1", model="tts-1-hd")
    assert steerable.instructions == speech_instructions("romy_tremblay", "A1")
    assert dated.instructions == steerable.instructions
    assert plain.instructions is None
    assert cast_voices.is_steerable_model(MODEL) and not cast_voices.is_steerable_model("tts-1")


def test_speed_is_sent_where_it_works_and_only_at_a1() -> None:
    # tts-1 / tts-1-hd honour `speed` (documented): A1 gets 0.9, the rest 1.0 (not sent).
    assert [speech_spec("marin", band, model="tts-1-hd").speed for band in ("A1", "A2", "B1")] == [0.9, None, None]
    assert speech_spec("marin", "A1", model="tts-1").speed == 0.9
    # gpt-4o-mini-tts: OpenAI says unsupported — not sent unless the deployment opts in.
    assert [speech_spec("marin", band, model=MODEL).speed for band in ("A1", "A2", "B1")] == [None] * 3
    opted = [
        speech_spec("marin", band, model=MODEL, steerable_a1_speed=0.9).speed for band in ("A1", "A2", "B1")
    ]
    assert opted == [0.9, None, None]


def test_the_deployments_speed_opt_in_reaches_the_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    assert episode_audio.spec_for("marin", "A1", model=MODEL).speed is None
    monkeypatch.setattr(settings, "FEUILLETON_AUDIO_STEERABLE_A1_SPEED", 0.9)
    assert episode_audio.spec_for("marin", "A1", model=MODEL).speed == 0.9
    assert episode_audio.spec_for("marin", "B1", model=MODEL).speed is None


# ---------------------------------------------------------------------------
# 3. What reaches the wire
# ---------------------------------------------------------------------------


def _speak_through_the_real_provider(model: str, **kwargs: Any) -> dict[str, Any]:
    provider = llm_module.OpenAIProvider(api_key="test-key-not-real", model="unused")
    assert provider.text_to_speech("Bonjour !", voice="nova", model=model, **kwargs) == b"mp3:recorded"
    return _Recorder.posts[-1]


def test_a_steerable_model_receives_instructions_and_speed_on_the_speech_endpoint() -> None:
    sent = _speak_through_the_real_provider(MODEL, instructions="Accent : parisien.", speed=0.9)
    assert sent["url"] == "/audio/speech"
    assert sent["json"] == {
        "model": MODEL,
        "input": "Bonjour !",
        "voice": "nova",
        "response_format": "mp3",
        "instructions": "Accent : parisien.",
        "speed": 0.9,
    }


def test_tts_1_hd_is_never_sent_instructions() -> None:
    sent = _speak_through_the_real_provider(
        "tts-1-hd", instructions="Accent : parisien.", speed=0.9
    )
    assert "instructions" not in sent["json"], "OpenAI: instructions do not work with tts-1 / tts-1-hd"
    assert sent["json"]["speed"] == 0.9


def test_nothing_extra_is_sent_when_there_is_nothing_to_say() -> None:
    sent = _speak_through_the_real_provider("tts-1-hd")
    assert set(sent["json"]) == {"model", "input", "voice", "response_format"}


def test_the_service_passes_instructions_and_speed_to_openai() -> None:
    service = llm_module.LLMService()
    service._providers = [llm_module.OpenAIProvider(api_key="test-key-not-real", model="unused")]
    audio = service.text_to_speech(
        "Bonjour !", voice="onyx", model=MODEL, provider="openai", instructions="Ton : doux.", speed=0.9
    )
    assert audio == b"mp3:recorded"
    assert _Recorder.posts[-1]["json"]["instructions"] == "Ton : doux."
    assert _Recorder.posts[-1]["json"]["voice"] == "onyx"


def test_the_price_table_knows_the_new_model() -> None:
    assert llm_module.estimate_tts_cost_usd(MODEL, 1000) == pytest.approx(0.02)
    assert llm_module.estimate_tts_cost_usd("tts-1-hd", 1000) == pytest.approx(0.03)


# ---------------------------------------------------------------------------
# 4. The cache key: model, instructions version, pace, instructions
# ---------------------------------------------------------------------------


def _key(person: str = "romy_tremblay", band: str = "A1", model: str = MODEL) -> str:
    return speech_spec(person, band, model=model).cache_key


def test_the_key_changes_with_the_model() -> None:
    assert _key(model=MODEL) != _key(model="tts-1-hd")
    assert _key(model=MODEL) != _key(model="gpt-4o-mini-tts-2025-12-15")
    assert _key() == _key(), "and is stable for the same spec"


def test_the_key_changes_with_the_pace_and_not_with_the_sublevel() -> None:
    assert len({_key(band="A1"), _key(band="A2"), _key(band="B1")}) == 3
    assert _key(band="A1.1") == _key(band="A1.2") == _key(band="A1")
    assert _key(band="B1") == _key(band="B2") == _key(band="C1")


def test_the_key_changes_with_the_speaker_because_the_instructions_differ() -> None:
    keys = {_key(person) for person in [*CAST, NARRATOR_ID]}
    assert len(keys) == len(CAST) + 1
    assert _key("gus") == _key("augustin_de_roncourt")


def test_the_key_changes_with_the_instructions_version(monkeypatch: pytest.MonkeyPatch) -> None:
    before = _key()
    monkeypatch.setattr(cast_voices, "SPEECH_INSTRUCTIONS_VERSION", "2099-01-01.1")
    after = _key()
    assert before != after
    assert SPEECH_INSTRUCTIONS_VERSION in before and "2099-01-01.1" in after


def test_the_key_changes_when_the_wording_changes_even_if_the_version_was_not_bumped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _key("marin_leveque")
    monkeypatch.setitem(
        cast_voices._PERSONA,
        "marin_leveque",
        (cast_voices._ACCENT_PARIS, "Personnage : Marin, mais pressé."),
    )
    assert _key("marin_leveque") != before


def test_the_key_changes_when_the_speed_sent_changes() -> None:
    assert (
        speech_spec("marin", "A1", model=MODEL).cache_key
        != speech_spec("marin", "A1", model=MODEL, steerable_a1_speed=0.9).cache_key
    )


def test_the_key_is_the_shape_the_cache_column_holds() -> None:
    parsed = parse_cache_key(_key())
    assert parsed is not None and parsed[:3] == (MODEL, SPEECH_INSTRUCTIONS_VERSION, "a1")
    longest = _key(model="gpt-4o-mini-tts-2025-12-15")
    assert len(longest) <= 60, "LineAudioClip.model is a String(60)"
    # A clip made before WP-103 is stored under a bare model name: never current.
    for legacy in ("tts-1-hd", "tts-1", "", None):
        assert parse_cache_key(legacy) is None
        assert not cache_key_is_current(legacy, models=(MODEL, FALLBACK_SPEECH_MODEL))
    assert cache_key_is_current(_key(), models=(MODEL, FALLBACK_SPEECH_MODEL))
    assert cache_key_is_current(_key(model="tts-1-hd"), models=(MODEL, FALLBACK_SPEECH_MODEL))
    assert not cache_key_is_current(_key(model="tts-1"), models=(MODEL, FALLBACK_SPEECH_MODEL))
    assert cast_voices.model_of_cache_key(_key()) == MODEL
    assert cast_voices.model_of_cache_key("tts-1-hd") == "tts-1-hd"


def test_the_radio_revision_changes_with_model_instructions_and_pace(
    db_session: Session, learner, monkeypatch: pytest.MonkeyPatch
) -> None:
    lines = episode_audio.episode_lines(make_scene(db_session, learner))
    base = episode_audio.scene_revision(lines, model=MODEL, band="A1")
    assert base == episode_audio.scene_revision(lines, model=MODEL, band="A1.2"), "same pace, same audio"
    assert base != episode_audio.scene_revision(lines, model=MODEL, band="A2")
    assert base != episode_audio.scene_revision(lines, model=MODEL, band="B1")
    assert episode_audio.scene_revision(lines, model=MODEL, band="B1") == episode_audio.scene_revision(
        lines, model=MODEL, band="B2"
    )
    assert base != episode_audio.scene_revision(lines, model="tts-1-hd", band="A1")
    monkeypatch.setattr(cast_voices, "SPEECH_INSTRUCTIONS_VERSION", "2099-01-01.1")
    assert base != episode_audio.scene_revision(lines, model=MODEL, band="A1")


# ---------------------------------------------------------------------------
# 5. The call and its fallback
# ---------------------------------------------------------------------------


def _speak(fake: FakeSynthesizer, *, band: str = "A1", model: str = MODEL, person: str = "romy_tremblay"):
    return episode_audio.speak_text(
        fake,
        text="Bonjour !",
        voice=cast_voices.voice_for_character(person),
        character_id=person,
        band=band,
        model=model,
    )


def test_the_steerable_call_carries_the_characters_instructions() -> None:
    fake = FakeSynthesizer()
    spoken = _speak(fake, band="A2", person="lila_bonnet")
    assert len(fake.specs) == 1
    call = fake.specs[0]
    assert call["model"] == MODEL and call["voice"] == "shimmer"
    assert call["instructions"] == speech_instructions("lila_bonnet", "A2")
    assert call["speed"] is None
    assert spoken.model == MODEL and spoken.fell_back is False
    assert spoken.spec.cache_key == _key("lila_bonnet", "A2")


def test_a_failing_steerable_model_falls_back_to_tts_1_hd_once_and_says_so() -> None:
    from loguru import logger

    records: list[dict[str, Any]] = []
    sink = logger.add(lambda message: records.append(message.record), level="WARNING")
    try:
        fake = FakeSynthesizer(fail_models=(MODEL,))
        spoken = _speak(fake, band="A1")
    finally:
        logger.remove(sink)
    assert [call["model"] for call in fake.specs] == [MODEL, FALLBACK_SPEECH_MODEL]
    fallback_call = fake.specs[1]
    assert fallback_call["instructions"] is None, "tts-1-hd cannot be steered"
    assert fallback_call["speed"] == 0.9, "but it honours speed, so A1 keeps its pace"
    assert spoken.fell_back is True and spoken.model == FALLBACK_SPEECH_MODEL
    assert spoken.audio.startswith(b"mp3:")
    assert spoken.spec.cache_key == _key(band="A1", model=FALLBACK_SPEECH_MODEL)
    warned = [record for record in records if "falling back" in record["message"]]
    assert len(warned) == 1, "logged once, at warning level"
    assert warned[0]["extra"]["model"] == MODEL and warned[0]["extra"]["fallback"] == FALLBACK_SPEECH_MODEL
    assert "said no" in warned[0]["extra"]["error"]


def test_a_steerable_model_that_returns_nothing_also_falls_back() -> None:
    class Silent(FakeSynthesizer):
        def text_to_speech(self, text, voice="nova", model=None, provider=None, **kwargs):  # type: ignore[override]
            audio = super().text_to_speech(text, voice, model, provider, **kwargs)
            return b"" if model == MODEL else audio

    fake = Silent()
    spoken = _speak(fake)
    assert spoken.fell_back is True and spoken.audio.startswith(b"mp3:")
    assert [call["model"] for call in fake.specs] == [MODEL, FALLBACK_SPEECH_MODEL]


def test_a_fallback_that_fails_too_is_an_error_and_a_configured_fallback_is_not_retried() -> None:
    both = FakeSynthesizer(fail_models=(MODEL, FALLBACK_SPEECH_MODEL))
    with pytest.raises(RuntimeError):
        _speak(both)
    assert len(both.specs) == 2

    only = FakeSynthesizer(fail_models=(FALLBACK_SPEECH_MODEL,))
    with pytest.raises(RuntimeError):
        _speak(only, model=FALLBACK_SPEECH_MODEL)
    assert len(only.specs) == 1, "tts-1-hd configured: there is nothing to fall back to"


# ---------------------------------------------------------------------------
# 6. The radio episode
# ---------------------------------------------------------------------------


def test_the_radio_speaks_each_line_as_its_character_at_the_learners_pace(
    db_session: Session, learner, audio_on
) -> None:
    learner.cefr_estimate = "A1.1"
    scene = make_scene(db_session, learner)
    fake = FakeSynthesizer()
    result = episode_audio.synthesize_episode_audio(db_session, scene=scene, synthesizer=fake)

    assert result.status == "ready" and len(fake.specs) == 3
    by_text = {call["text"]: call for call in fake.specs}
    narrator = by_text["Le marché est presque vide."]
    landlord = by_text["Bien sûr, elles sont d’aujourd’hui."]
    assert narrator["instructions"] == speech_instructions(NARRATOR_ID, "A1.1")
    assert landlord["instructions"] == speech_instructions("landlord_marchand", "A1.1")
    assert narrator["instructions"] != landlord["instructions"]
    assert all(call["model"] == MODEL for call in fake.specs)
    rows = cost_rows(db_session, learner)
    assert rows[0].payload["instructions_version"] == SPEECH_INSTRUCTIONS_VERSION
    assert rows[0].payload["pace"] == "a1" and rows[0].payload["fallback_lines"] == 0
    assert rows[0].payload["model"] == MODEL


def test_a_learner_who_reaches_a_new_pace_hears_a_new_episode_not_the_old_recording(
    db_session: Session, learner, audio_on
) -> None:
    learner.cefr_estimate = "A1.2"
    scene = make_scene(db_session, learner)
    first = FakeSynthesizer()
    episode_audio.synthesize_episode_audio(db_session, scene=scene, synthesizer=first)
    a1_revision = episode_audio.episode_audio_manifest(db_session, scene=scene).revision

    same_pace = FakeSynthesizer()
    learner.cefr_estimate = "A1.1"
    episode_audio.synthesize_episode_audio(db_session, scene=scene, synthesizer=same_pace)
    assert same_pace.calls == [], "A1.1 and A1.2 share a pace: a replay is free"

    learner.cefr_estimate = "B1.1"
    assert episode_audio.episode_audio_manifest(db_session, scene=scene).status == "absent"
    second = FakeSynthesizer()
    result = episode_audio.synthesize_episode_audio(db_session, scene=scene, synthesizer=second)
    assert result.status == "ready" and result.revision != a1_revision
    assert len(second.calls) == 3
    assert all("naturel, celui d'une conversation courante" in call["instructions"] for call in second.specs)


def test_a_reworded_instruction_never_serves_the_old_recording(
    db_session: Session, learner, audio_on, monkeypatch: pytest.MonkeyPatch
) -> None:
    scene = make_scene(db_session, learner)
    episode_audio.synthesize_episode_audio(db_session, scene=scene, synthesizer=FakeSynthesizer())
    monkeypatch.setattr(cast_voices, "SPEECH_INSTRUCTIONS_VERSION", "2099-01-01.1")
    assert episode_audio.episode_audio_manifest(db_session, scene=scene).status == "absent"
    again = FakeSynthesizer()
    episode_audio.synthesize_episode_audio(db_session, scene=scene, synthesizer=again)
    assert len(again.calls) == 3


def test_a_radio_line_that_fell_back_is_stored_and_billed_as_what_spoke_it(
    db_session: Session, learner, audio_on
) -> None:
    scene = make_scene(db_session, learner)
    fake = FakeSynthesizer(fail_models=(MODEL,))
    result = episode_audio.synthesize_episode_audio(db_session, scene=scene, synthesizer=fake)

    assert result.status == "ready" and len(result.clips) == 3
    stored = list(
        db_session.scalars(select(EpisodeAudioClip).where(EpisodeAudioClip.scene_id == scene.id))
    )
    assert {clip.model for clip in stored} == {FALLBACK_SPEECH_MODEL}
    payload = cost_rows(db_session, learner)[0].payload
    assert payload["fallback_lines"] == 3 and payload["model"] == MODEL

    # …and the replay is free: the fallback clips are this revision's clips.
    replay = FakeSynthesizer(fail_models=(MODEL,))
    episode_audio.synthesize_episode_audio(db_session, scene=scene, synthesizer=replay)
    assert replay.calls == []


# ---------------------------------------------------------------------------
# 7. The line-audio cache
# ---------------------------------------------------------------------------

LINE = "Salut ! Tu veux t'asseoir avec nous ?"


def _line(person: str = "romy_tremblay") -> line_audio.StepLine:
    return line_audio.StepLine(person, LINE)


def _speak_line(db: Session, user, fake, *, person: str = "romy_tremblay", band: str | None = None):
    return line_audio.speak_line(
        db, user=user, line=_line(person), surface="test", synthesizer=fake, respect_cap=False, band=band
    )


def _clips(db: Session, user) -> list[LineAudioClip]:
    db.flush()
    return list(db.scalars(select(LineAudioClip).where(LineAudioClip.user_id == user.id)))


def test_a_spoken_line_is_stored_under_its_speech_spec(db_session: Session, learner, audio_on) -> None:
    learner.cefr_estimate = "A1.1"
    fake = FakeSynthesizer()
    outcome = _speak_line(db_session, learner, fake)
    assert outcome.status == "ready" and outcome.cached is False
    (clip,) = _clips(db_session, learner)
    assert clip.model == _key("romy_tremblay", "A1", MODEL)
    assert clip.clip_id == cast_voices.clip_id_for("nova", LINE), "the id itself is unchanged"
    call = fake.specs[0]
    assert call["instructions"] == speech_instructions("romy_tremblay", "A1.1") and call["model"] == MODEL

    # A replay at the same pace is free; smart quotes are the same line.
    replay = FakeSynthesizer()
    again = _speak_line(db_session, learner, replay)
    assert again.cached is True and replay.calls == []
    assert len(_clips(db_session, learner)) == 1


def test_a_learner_at_another_pace_is_spoken_to_again(db_session: Session, learner, audio_on) -> None:
    learner.cefr_estimate = "A1.1"
    _speak_line(db_session, learner, FakeSynthesizer())
    learner.cefr_estimate = "B1.1"
    fake = FakeSynthesizer()
    outcome = _speak_line(db_session, learner, fake)
    assert outcome.cached is False and len(fake.calls) == 1
    assert "naturel, celui d'une conversation courante" in fake.specs[0]["instructions"]
    keys = {clip.model for clip in _clips(db_session, learner)}
    assert keys == {_key(band="A1"), _key(band="B1")}
    # The explicit band wins over the estimate.
    third = FakeSynthesizer()
    assert _speak_line(db_session, learner, third, band="A2").cached is False
    assert "naturel, un peu lent" in third.specs[0]["instructions"]


def test_a_clip_made_before_wp103_is_never_served_or_reused(
    db_session: Session, learner, audio_on
) -> None:
    clip_id = cast_voices.clip_id_for("nova", LINE)
    db_session.add(
        LineAudioClip(
            user_id=learner.id, clip_id=clip_id, voice="nova", model="tts-1-hd",
            character_id="romy_tremblay", text_fr=LINE, char_count=len(LINE), audio=b"old-english-accent",
        )
    )
    db_session.flush()
    # The route that serves bytes does not find it…
    assert line_audio.owned_clip(db_session, user_id=learner.id, clip_id=clip_id) is None
    # …and a request to speak the line makes a new call rather than reusing it.
    fake = FakeSynthesizer()
    outcome = _speak_line(db_session, learner, fake)
    assert outcome.cached is False and len(fake.calls) == 1
    assert outcome.clip is not None and not outcome.clip.audio.startswith(b"old")
    served = line_audio.owned_clip(db_session, user_id=learner.id, clip_id=clip_id)
    assert served is not None and served.audio == outcome.clip.audio


def test_a_clip_from_an_older_instructions_version_is_not_served(
    db_session: Session, learner, audio_on, monkeypatch: pytest.MonkeyPatch
) -> None:
    _speak_line(db_session, learner, FakeSynthesizer())
    clip_id = cast_voices.clip_id_for("nova", LINE)
    assert line_audio.owned_clip(db_session, user_id=learner.id, clip_id=clip_id) is not None
    monkeypatch.setattr(cast_voices, "SPEECH_INSTRUCTIONS_VERSION", "2099-01-01.1")
    assert line_audio.owned_clip(db_session, user_id=learner.id, clip_id=clip_id) is None
    fake = FakeSynthesizer()
    assert _speak_line(db_session, learner, fake).cached is False and len(fake.calls) == 1


def test_a_change_of_model_finds_no_clip_of_the_old_one(
    db_session: Session, learner, audio_on, monkeypatch: pytest.MonkeyPatch
) -> None:
    _speak_line(db_session, learner, FakeSynthesizer())
    monkeypatch.setattr(settings, "FEUILLETON_AUDIO_TTS_MODEL", "gpt-4o-mini-tts-2025-12-15")
    fake = FakeSynthesizer()
    assert _speak_line(db_session, learner, fake).cached is False
    assert fake.specs[0]["model"] == "gpt-4o-mini-tts-2025-12-15"


def test_two_speakers_of_one_voice_do_not_share_a_clip(db_session: Session, learner, audio_on) -> None:
    """A generated character can hash into Romy's voice, but not into her instructions."""

    _speak_line(db_session, learner, FakeSynthesizer(), person="romy_tremblay")
    stranger = "henriette_dubois"
    if cast_voices.voice_for_character(stranger) != "nova":
        stranger = next(
            candidate for candidate in (f"guest_{n}" for n in range(200))
            if cast_voices.voice_for_character(candidate) == "nova"
        )
    fake = FakeSynthesizer()
    outcome = _speak_line(db_session, learner, fake, person=stranger)
    assert outcome.cached is False and len(fake.calls) == 1
    assert "accent parisien neutre" in fake.specs[0]["instructions"]
    # The route that serves bytes still finds a clip the learner was told is ready.
    served = line_audio.owned_clip(db_session, user_id=learner.id, clip_id=outcome.clip.clip_id)
    assert served is not None


def test_a_second_learner_copies_a_clip_spoken_the_same_way_and_only_that(
    db_session: Session, learner, audio_on
) -> None:
    other = type(learner)(
        email=f"radio-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
        target_language="fr", native_language="en",
    )
    db_session.add(other)
    db_session.flush()
    learner.cefr_estimate = "A1.1"
    other.cefr_estimate = "A1.2"
    _speak_line(db_session, learner, FakeSynthesizer())
    fake = FakeSynthesizer()
    copied = _speak_line(db_session, other, fake)
    assert copied.cached is True and fake.calls == [], "same pace, same instructions: bytes are copied"
    assert copied.clip.model == _key(band="A1")

    third = type(learner)(
        email=f"radio-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
        target_language="fr", native_language="en",
    )
    db_session.add(third)
    db_session.flush()
    third.cefr_estimate = "B1.1"
    fresh = FakeSynthesizer()
    assert _speak_line(db_session, third, fresh).cached is False and len(fresh.calls) == 1


def test_a_line_that_fell_back_is_cached_priced_and_flagged(db_session: Session, learner, audio_on) -> None:
    learner.cefr_estimate = "A1.1"
    fake = FakeSynthesizer(fail_models=(MODEL,))
    outcome = _speak_line(db_session, learner, fake)
    assert outcome.status == "ready" and outcome.cached is False
    assert [call["model"] for call in fake.specs] == [MODEL, FALLBACK_SPEECH_MODEL]
    (clip,) = _clips(db_session, learner)
    assert clip.model == _key(band="A1", model=FALLBACK_SPEECH_MODEL)

    db_session.flush()
    (row,) = db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.user_id == learner.id, PilotEvent.event_type == line_audio.LINE_AUDIO_EVENT_TYPE
        )
    )
    assert row.payload["model"] == FALLBACK_SPEECH_MODEL and row.payload["fell_back"] is True
    assert row.payload["estimated"] is True and row.payload["pace"] == "a1"
    assert row.cost_usd == pytest.approx(len(LINE) / 1000 * 0.03), "priced at the model that spoke it"

    # An outage must not mean a paid call for the same line on every replay.
    replay = FakeSynthesizer(fail_models=(MODEL,))
    assert _speak_line(db_session, learner, replay).cached is True and replay.calls == []
    assert line_audio.owned_clip(db_session, user_id=learner.id, clip_id=clip.clip_id) is not None


def test_a_line_priced_at_the_steerable_model_carries_the_spec_on_the_ledger(
    db_session: Session, learner, audio_on
) -> None:
    learner.cefr_estimate = "B1.1"
    _speak_line(db_session, learner, FakeSynthesizer())
    db_session.flush()
    (row,) = db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.user_id == learner.id, PilotEvent.event_type == line_audio.LINE_AUDIO_EVENT_TYPE
        )
    )
    payload = row.payload
    assert payload["model"] == MODEL and payload["fell_back"] is False
    assert payload["instructions_version"] == SPEECH_INSTRUCTIONS_VERSION and payload["pace"] == "b1"
    assert payload["cache_key"] == _key(band="B1")
    assert payload["estimated"] is True and row.cost_usd == pytest.approx(len(LINE) / 1000 * 0.02)


def test_a_planned_listening_clip_is_spoken_by_its_voices_owner(
    db_session: Session, learner, audio_on
) -> None:
    """The planner names a clip by voice only; that voice's owner speaks it."""

    learner.cefr_estimate = "A2.1"
    fake = FakeSynthesizer()
    outcome = line_audio.speak_line(
        db_session,
        user=learner,
        line=line_audio._VoicedLine("voice:nova", LINE, "nova"),
        surface="journey_listening_item",
        respect_cap=False,
        synthesizer=fake,
    )
    assert outcome.status == "ready"
    assert fake.specs[0]["instructions"] == speech_instructions("romy_tremblay", "A2")
    served = line_audio.owned_clip(db_session, user_id=learner.id, clip_id=outcome.clip.clip_id)
    assert served is not None and served.id == outcome.clip.id


def test_no_call_in_this_file_reached_the_network(no_paid_call: list[dict[str, Any]]) -> None:
    """The recorder saw only the requests the provider tests above made on purpose;
    this test makes none and finds the list as the fixture left it."""

    assert no_paid_call == []
    assert json.dumps(_Recorder.posts) == "[]"
