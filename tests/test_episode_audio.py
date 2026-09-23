"""WP-32 — «Écouter d'abord»: synthesis, the cache, and the price of a voice.

Behavioural, with a fake synthesizer in place of the paid one. **No live TTS
call is made anywhere in this file**, and the fake counts its calls, which is
how the two properties that decide whether this feature is affordable get
pinned:

* with the flag off nothing is read, nothing is called and nothing is billed;
* the second request for the same scene text calls nobody and bills nobody.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.episode_audio import EpisodeAudioClip
from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services import episode_audio as module
from app.services.episode_audio import (
    EPISODE_AUDIO_EVENT_TYPE,
    PREDICTION_EVENT_TYPE,
    bound_lines,
    episode_audio_manifest,
    episode_lines,
    record_prediction_check,
    scene_revision,
    synthesize_episode_audio,
    voice_for_character,
)
from app.services.living_story import ENGINE_VERSION_PREFIX


class FakeSynthesizer:
    """Counts what it was asked for, and can be told to fail on one line."""

    def __init__(self, *, fail_on: str | None = None, empty_on: str | None = None) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.fail_on = fail_on
        self.empty_on = empty_on

    def text_to_speech(
        self,
        text: str,
        voice: str = "nova",
        model: str | None = None,
        provider: str | None = None,
    ) -> bytes:
        self.calls.append((text, voice, str(provider)))
        if self.fail_on and self.fail_on in text:
            raise RuntimeError("provider said no")
        if self.empty_on and self.empty_on in text:
            return b""
        return f"mp3:{voice}:{text}".encode()


@pytest.fixture()
def learner(db_session: Session) -> User:
    user = User(
        email=f"radio-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
    )
    db_session.add(user)
    db_session.flush()
    return user


def make_scene(db_session: Session, user: User, *, panels: list[dict] | None = None) -> GraphicNovelScene:
    scene = GraphicNovelScene(
        user_id=user.id,
        title="Au marché",
        brief="Vous entrez au marché.",
        status="available",
        cadence="daily",
        cache_key=uuid.uuid4().hex,
        # The engine prefix `story_engine.owned_scene` filters on: a scene the
        # reader cannot open must not be reachable through the audio routes.
        prompt_version=ENGINE_VERSION_PREFIX + "v2",
        image_model="existing-setting-art",
        image_quality="reference",
        source_snapshot={"journey_id": str(uuid.uuid4())},
    )
    db_session.add(scene)
    db_session.flush()
    blocks = panels if panels is not None else [
        {
            "narration_fr": "Le marché est presque vide.",
            "dialogue": [
                {"character_id": "toi", "text_fr": "Bonjour, vous avez des tomates ?"},
                {"character_id": "", "text_fr": ""},
                {"character_id": "marchand", "text_fr": "Bien sûr, elles sont d’aujourd’hui."},
            ],
        }
    ]
    for index, overlay in enumerate(blocks):
        scene.panels.append(
            GraphicNovelPanel(
                panel_index=index,
                title=str(index + 1),
                beat=overlay.get("narration_fr", ""),
                image_prompt="",
                overlay_payload=overlay,
            )
        )
    db_session.flush()
    return scene


@pytest.fixture()
def audio_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module.settings, "ATELIER_EPISODE_AUDIO_ENABLED", True)


def cost_rows(db_session: Session, user: User) -> list[PilotEvent]:
    # The service writes through the caller's transaction and never commits;
    # the rows are visible to a query only once they are flushed. Scoped to this
    # test's learner: the suite shares one database, and a later-alphabet test
    # that commits its own audio rows ran first in a reversed-order run.
    db_session.flush()
    return list(
        db_session.scalars(
            select(PilotEvent).where(
                PilotEvent.event_type == EPISODE_AUDIO_EVENT_TYPE,
                PilotEvent.user_id == user.id,
            )
        )
    )


def clip_rows(db_session: Session, user: User) -> list[EpisodeAudioClip]:
    """This learner's stored clips (see `cost_rows` for why it is scoped)."""

    return list(db_session.scalars(select(EpisodeAudioClip).where(EpisodeAudioClip.user_id == user.id)))


# ---------------------------------------------------------------------------
# Lines and voices
# ---------------------------------------------------------------------------


def test_lines_are_ordered_and_keyed_the_way_the_frontend_derives_them(db_session, learner):
    scene = make_scene(db_session, learner)
    panel_id = scene.panels[0].id
    lines = episode_lines(scene)

    assert [line.key for line in lines] == [
        f"{panel_id}:n",
        f"{panel_id}:l0",
        f"{panel_id}:l2",
    ], "an empty dialogue entry is skipped without shifting the keys after it"
    assert lines[0].character_id == module.NARRATOR_ID
    assert lines[0].voice == module.NARRATOR_VOICE
    assert [line.ordinal for line in lines] == [0, 1, 2]


def test_a_character_keeps_one_voice_and_the_narrator_keeps_their_own():
    assert voice_for_character("romy") == voice_for_character("romy_tremblay")
    assert voice_for_character(None) == module.NARRATOR_VOICE
    assert voice_for_character("narrator") == module.NARRATOR_VOICE
    # A generated cast member is stable across days, not round-robined.
    generated = voice_for_character("henriette_dubois")
    assert generated == voice_for_character("henriette_dubois")
    assert generated in module.CHARACTER_VOICES
    assert module.NARRATOR_VOICE not in module.CHARACTER_VOICES


def test_the_budget_cuts_whole_lines_and_says_that_it_did(db_session, learner):
    scene = make_scene(db_session, learner)
    lines = episode_lines(scene)
    kept, truncated = bound_lines(lines, max_chars=lines[0].char_count)

    assert truncated is True
    assert [line.key for line in kept] == [lines[0].key]
    assert all(line.text_fr in {item.text_fr for item in lines} for line in kept), (
        "a kept line is a whole line, never a clipped one"
    )
    assert bound_lines(lines, max_chars=0) == (lines, False), "0 means no budget, not no audio"


def test_the_revision_changes_when_the_words_or_the_model_change(db_session, learner):
    scene = make_scene(db_session, learner)
    lines = episode_lines(scene)
    base = scene_revision(lines, model="tts-1")

    assert base == scene_revision(lines, model="tts-1")
    assert base != scene_revision(lines, model="tts-1-hd")

    edited = [*lines[:-1], module.EpisodeLine(
        key=lines[-1].key,
        ordinal=lines[-1].ordinal,
        character_id=lines[-1].character_id,
        voice=lines[-1].voice,
        text_fr="Non, il n’y en a plus.",
    )]
    assert base != scene_revision(edited, model="tts-1")


# ---------------------------------------------------------------------------
# The flag
# ---------------------------------------------------------------------------


def test_with_the_flag_off_nothing_is_synthesized_read_or_billed(db_session, learner):
    scene = make_scene(db_session, learner)
    fake = FakeSynthesizer()

    result = synthesize_episode_audio(db_session, scene=scene, synthesizer=fake)

    assert result.status == "disabled"
    assert result.reason == "flag_off"
    assert result.clips == []
    assert fake.calls == []
    assert cost_rows(db_session, learner) == []
    assert clip_rows(db_session, learner) == []
    assert episode_audio_manifest(db_session, scene=scene).status == "disabled"


# ---------------------------------------------------------------------------
# Synthesis, cache, idempotency
# ---------------------------------------------------------------------------


def test_a_first_run_speaks_every_line_and_writes_one_priced_row(
    db_session, learner, audio_on
):
    scene = make_scene(db_session, learner)
    fake = FakeSynthesizer()

    result = synthesize_episode_audio(db_session, scene=scene, synthesizer=fake)

    assert result.status == "ready"
    assert len(result.clips) == 3
    assert [clip["ordinal"] for clip in result.clips] == [0, 1, 2]
    assert all(clip["id"] for clip in result.clips)
    assert "audio" not in result.clips[0], "bytes never travel in the manifest"
    assert len(fake.calls) == 3
    assert {call[2] for call in fake.calls} == {module.TTS_PROVIDER}, (
        "the provider is pinned to the one this path was tested on"
    )

    rows = cost_rows(db_session, learner)
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["estimated"] is True, "the speech endpoint reports no usage"
    assert payload["cost_basis"]
    assert payload["lines"] == 3
    assert payload["status"] == "ready"
    assert payload["surface"] == "journey_episode_radio"
    assert rows[0].cost_usd > 0


def test_a_second_run_of_the_same_scene_calls_nobody_and_bills_nobody(
    db_session, learner, audio_on
):
    scene = make_scene(db_session, learner)
    first = FakeSynthesizer()
    synthesize_episode_audio(db_session, scene=scene, synthesizer=first)

    second = FakeSynthesizer()
    result = synthesize_episode_audio(db_session, scene=scene, synthesizer=second)

    assert result.status == "ready"
    assert len(result.clips) == 3
    assert second.calls == [], "a replayed episode is free"
    assert len(cost_rows(db_session, learner)) == 1, "no zero-cost row that would read as a free call"
    assert result.synthesized_lines == 0


def test_a_rewritten_line_invalidates_the_audio_rather_than_playing_the_old_one(
    db_session, learner, audio_on
):
    scene = make_scene(db_session, learner)
    synthesize_episode_audio(db_session, scene=scene, synthesizer=FakeSynthesizer())
    before = episode_audio_manifest(db_session, scene=scene).revision

    panel = scene.panels[0]
    panel.overlay_payload = {
        **panel.overlay_payload,
        "narration_fr": "Le marché est bondé.",
    }
    db_session.flush()

    fresh = FakeSynthesizer()
    result = synthesize_episode_audio(db_session, scene=scene, synthesizer=fresh)

    assert result.revision != before
    assert result.status == "ready"
    # Only the changed line is new; the two unchanged ones keep the old
    # revision's rows but need their own under the new one.
    assert len(fresh.calls) == 3
    assert len(cost_rows(db_session, learner)) == 2


def test_the_manifest_read_never_starts_a_paid_call(db_session, learner, audio_on):
    scene = make_scene(db_session, learner)

    absent = episode_audio_manifest(db_session, scene=scene)
    assert absent.status == "absent"
    assert absent.clips == []
    assert absent.revision, "the revision is known before anything is spoken"

    synthesize_episode_audio(db_session, scene=scene, synthesizer=FakeSynthesizer())
    assert episode_audio_manifest(db_session, scene=scene).status == "ready"


def test_a_scene_with_nothing_to_say_is_empty_not_failed(db_session, learner, audio_on):
    scene = make_scene(db_session, learner, panels=[{"narration_fr": "", "dialogue": []}])
    fake = FakeSynthesizer()

    result = synthesize_episode_audio(db_session, scene=scene, synthesizer=fake)

    assert result.status == "empty"
    assert fake.calls == []
    assert cost_rows(db_session, learner) == []


# ---------------------------------------------------------------------------
# Failure is a state
# ---------------------------------------------------------------------------


def test_one_failed_line_fails_the_episode_and_keeps_what_was_paid_for(
    db_session, learner, audio_on
):
    scene = make_scene(db_session, learner)
    fake = FakeSynthesizer(fail_on="tomates")

    result = synthesize_episode_audio(db_session, scene=scene, synthesizer=fake)

    assert result.status == "failed"
    assert result.reason == "tts_failed"
    assert result.clips == [], "half a scene played aloud is a test nobody can pass"

    # The narration was synthesized before the failure and is still cached, so
    # the retry is cheaper than the first attempt rather than more expensive.
    stored = clip_rows(db_session, learner)
    assert len(stored) == 1
    rows = cost_rows(db_session, learner)
    assert len(rows) == 1
    assert rows[0].payload["status"] == "failed"
    assert rows[0].payload["lines"] == 1

    retry = FakeSynthesizer()
    healed = synthesize_episode_audio(db_session, scene=scene, synthesizer=retry)
    assert healed.status == "ready"
    assert len(retry.calls) == 2, "the line already paid for is not requested again"


def test_a_provider_that_returns_no_audio_is_a_failure_not_a_silent_clip(
    db_session, learner, audio_on
):
    scene = make_scene(db_session, learner)
    result = synthesize_episode_audio(
        db_session, scene=scene, synthesizer=FakeSynthesizer(empty_on="marché")
    )

    assert result.status == "failed"
    assert result.reason == "tts_empty"
    assert clip_rows(db_session, learner) == []


def test_an_unavailable_provider_is_reported_rather_than_raised(
    db_session, learner, audio_on
):
    def broken() -> module.Synthesizer:
        raise RuntimeError("no OpenAI key")

    result = synthesize_episode_audio(db_session, scene=make_scene(db_session, learner), llm_factory=broken)

    assert result.status == "failed"
    assert result.reason == "tts_unavailable"
    assert cost_rows(db_session, learner) == []


# ---------------------------------------------------------------------------
# The prediction check
# ---------------------------------------------------------------------------


def test_the_prediction_is_stored_beside_the_scene_and_is_never_a_score(
    db_session, learner
):
    scene = make_scene(db_session, learner)

    entry = record_prediction_check(
        db_session, scene=scene, guess="accord", verdict="confirmed", supported="accord"
    )
    db_session.flush()

    assert entry == {"guess": "accord", "verdict": "confirmed", "supported": "accord"}
    assert scene.source_snapshot["radio"]["prediction"] == entry
    assert scene.source_snapshot["journey_id"], "the existing snapshot is preserved"

    rows = list(
        db_session.scalars(
            select(PilotEvent).where(PilotEvent.event_type == PREDICTION_EVENT_TYPE)
        )
    )
    assert len(rows) == 1
    assert rows[0].cost_usd == 0.0
    assert "score" not in rows[0].payload
    assert "correct" not in rows[0].payload


def test_an_unrecognised_verdict_is_stored_as_unresolved_never_as_a_miss(
    db_session, learner
):
    scene = make_scene(db_session, learner)
    entry = record_prediction_check(db_session, scene=scene, guess="accord", verdict="wrong")
    assert entry["verdict"] == "unresolved"
    assert entry["supported"] is None


def test_the_prediction_never_touches_the_capability_rubric():
    """A tapped guess is not production, and must not enter the one rubric.

    Pinned as an AST scan rather than a text scan so the prose above may name
    what it refuses to do. The failure mode this guards is a later edit that
    "helpfully" credits the prediction: two rubrics is how
    ``recap.capability_evidence`` and ``GET /capabilities/progress`` once came to
    disagree about the same journey (CONTRACTS §8).
    """

    import ast

    tree = ast.parse(open(module.__file__, encoding="utf-8").read())
    reached: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            reached.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            reached.add(node.module or "")
            reached.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Attribute):
            reached.add(node.attr)
        elif isinstance(node, ast.Name):
            reached.add(node.id)

    for forbidden in (
        "DailyJourneyStep",
        "app.services.journey_capabilities",
        "build_capability_summary",
        "record_evidence",
        "app.db.models.daily_journey",
    ):
        assert forbidden not in reached, f"episode_audio.py reaches {forbidden}"
