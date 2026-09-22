"""Notification helpers for serial editions and the V2 daily journey."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.serial import SerialEpisode
from app.db.models.user import User

#: WP-19's title for the morning push. WP-80 replaced it with the speaking
#: character's name; kept so nothing that imports it breaks, and so a test can
#: assert that it is no longer sent.
DAILY_JOURNEY_MORNING_TITLE = "Votre scène du jour est prête"


def _compact(value: Any, max_length: int = 140) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max(0, max_length - 1)].rstrip()}…"


def enqueue_serial_edition_notification(db: Session, episode: SerialEpisode, *, user: User | None = None) -> bool:
    """Queue exactly one push notification when a serial beat becomes available."""
    if episode.status != "available" or int(episode.episode_index or 0) <= 0:
        return False
    learner = user or (episode.thread.user if episode.thread else None)
    if not learner or not getattr(learner, "notifications_enabled", True):
        return False
    if not getattr(learner, "serial_edition_notifications", True):
        return False

    notification_key = (
        f"serial-edition:{episode.thread_id}:{episode.episode_index}:{episode.kind}:"
        f"{episode.scene_id or episode.mission_id or 'planned'}"
    )
    hook = dict(episode.hook or {})
    if hook.get("notification_queued_key") == notification_key:
        return False

    teaser = _compact(hook.get("teaser") or hook.get("text") or hook.get("unresolved_question"))
    if episode.kind == "feuilleton":
        title = f"Épisode {int(episode.episode_index) + 1} disponible"
        message = teaser or "Votre nouvelle édition du Feuilleton est prête."
    else:
        title = f"Épisode {int(episode.episode_index) + 1} · à vous"
        message = teaser or "Romy attend votre réponse dans le prochain acte."

    hook["notification_queued_key"] = notification_key
    hook["notification_queued_at"] = datetime.now(UTC).isoformat()
    episode.hook = hook
    db.add(episode)
    db.commit()

    try:
        from app.tasks.notifications import send_serial_edition_notification

        send_serial_edition_notification.delay(
            str(learner.id),
            int(episode.episode_index),
            title,
            message,
            notification_key,
        )
    except Exception as exc:  # pragma: no cover - local broker-less fallback
        logger.info(
            "Serial edition notification queued for worker/lazy retry",
            user_id=str(learner.id),
            episode_id=str(episode.id),
            error=str(exc),
        )
    return True


# ---------------------------------------------------------------------------
# WP-80: the cast is the face of every push
# ---------------------------------------------------------------------------

#: Where a push opens: straight into today's scene (WP-75's entry).
JOURNEY_DEEP_LINK = "/atelier?start=today"

#: The character directories under ``web-frontend/public/assets/serial/characters``.
#: A scenario may name a character by a short id («marin») or the full one; the
#: first token decides, as in ``episode_audio.PINNED_VOICES``.
PORTRAIT_CHARACTERS: dict[str, str] = {
    "marin": "marin_leveque",
    "romy": "romy_tremblay",
    "lila": "lila_bonnet",
    "margaux": "margaux_barman",
    "augustin": "augustin_de_roncourt",
    "gus": "augustin_de_roncourt",
    "landlord": "landlord_marchand",
    "marchand": "landlord_marchand",
}

#: The display name when nothing else names the character.
CHARACTER_NAMES: dict[str, str] = {
    "marin_leveque": "Marin",
    "romy_tremblay": "Romy",
    "lila_bonnet": "Lila",
    "margaux_barman": "Margaux",
    "augustin_de_roncourt": "Augustin",
    "landlord_marchand": "M. Marchand",
}

#: Who speaks when the learner has no scene yet (WP-80's pre-prompt names him).
DEFAULT_CHARACTER_ID = "marin_leveque"

#: Authored, character-voiced lines, used only when the story has not written a
#: forward teaser (``living_story`` state ``next_teaser`` or a recap
#: ``teaser_fr``). French — it is the character speaking — «vous», no emoji, and
#: never a claim about what happens next: a line that promises a plot point the
#: engine did not write would be a lie. ``A`` is A1/A2, ``B`` is B1 and up.
MORNING_LINES: dict[str, dict[str, str]] = {
    "marin_leveque": {
        "A": "Je vous garde une place au Mistral. Vous venez ?",
        "B": "Je vous garde une place au Mistral. Passez quand vous pouvez, la suite vous attend.",
    },
    "romy_tremblay": {
        "A": "J’ai une question pour vous. Vous passez ?",
        "B": "J’ai une question pour vous, et je crois que vous avez la réponse.",
    },
    "lila_bonnet": {
        "A": "Bonjour ! J’ai besoin de vous aujourd’hui.",
        "B": "J’ai une idée, et elle a besoin de vous. Vous venez ?",
    },
    "margaux_barman": {
        "A": "Le café est prêt. Et vous ?",
        "B": "Votre table est libre. Venez voir ce qui se passe ici.",
    },
    "augustin_de_roncourt": {
        "A": "Bonjour. Vous avez un moment pour moi ?",
        "B": "J’aurais besoin de votre avis, si vous avez un instant.",
    },
    "landlord_marchand": {
        "A": "Bonjour. Passez me voir aujourd’hui.",
        "B": "Passez me voir aujourd’hui, nous avons à parler.",
    },
}
DEFAULT_MORNING_LINE = {"A": "La suite vous attend.", "B": "La suite vous attend. Vous venez ?"}

#: A scene started and left: the character picks it up where it stopped.
RESUME_LINES: dict[str, str] = {
    "A": "On s’est arrêtés au milieu. On continue ?",
    "B": "Nous nous sommes arrêtés au milieu. On reprend ?",
}

#: The evening streak-at-risk push. ``{days}`` is the honest, checked streak.
STREAK_LINES: dict[str, dict[str, str]] = {
    "marin_leveque": {
        "A": "Vous venez ce soir ? {days} jours de suite, déjà !",
        "B": "Vous passez ce soir ? {days} jours de suite, ce serait dommage d’arrêter là.",
    },
    "romy_tremblay": {
        "A": "{days} jours de suite ! On se voit ce soir ?",
        "B": "{days} jours de suite. Je note tout, alors ne me faites pas faux bond ce soir.",
    },
    "lila_bonnet": {
        "A": "{days} jours de suite. Bravo ! Et ce soir ?",
        "B": "{days} jours de suite : je suis fière de vous. Une scène ce soir ?",
    },
    "margaux_barman": {
        "A": "Votre table vous attend ce soir. {days} jours de suite !",
        "B": "Votre table vous attend ce soir. {days} jours de suite, on ne s’arrête pas maintenant.",
    },
    "augustin_de_roncourt": {
        "A": "{days} jours de suite. Vous venez ce soir ?",
        "B": "{days} jours de suite. Ce soir encore, si vous le voulez bien.",
    },
    "landlord_marchand": {
        "A": "{days} jours de suite. Ce soir aussi ?",
        "B": "{days} jours de suite. J’espère vous voir ce soir.",
    },
}
DEFAULT_STREAK_LINE = {
    "A": "{days} jours de suite. Une scène ce soir ?",
    "B": "{days} jours de suite. Une scène ce soir, et la série continue.",
}


@dataclass(frozen=True, slots=True)
class CharacterPush:
    """One push in a character's voice (WP-80)."""

    title: str
    message: str
    character_id: str | None
    #: A path under the web app's public root, or ``None``.
    image: str | None
    #: ``engine`` when the story wrote the line, ``authored`` otherwise.
    source: str
    route: str = JOURNEY_DEEP_LINK

    def data(self, kind: str, notification_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "route": self.route,
            "kind": kind,
            "notification_id": notification_id,
            "teaser_source": self.source,
        }
        if self.character_id:
            payload["character_id"] = self.character_id
        if self.image:
            payload["image"] = self.image
        return payload


def band_group(user: User) -> str:
    """``A`` for A1/A2 learners, ``B`` from B1: the register of an authored line."""

    band = str(getattr(user, "cefr_estimate", None) or "A1").strip().upper()[:2]
    return "A" if band in {"", "A0", "A1", "A2"} or not band.startswith(("B", "C")) else "B"


def portrait_character(character_id: Any) -> str | None:
    """The portrait directory for a scenario's character id, if one exists."""

    raw = str(character_id or "").strip().lower()
    if not raw:
        return None
    if raw in CHARACTER_NAMES:
        return raw
    return PORTRAIT_CHARACTERS.get(raw.split("_", 1)[0])


def portrait_path(character_id: Any) -> str | None:
    key = portrait_character(character_id)
    return f"/assets/serial/characters/{key}/portrait-neutral.webp" if key else None


def _latest_journey(db: Session, user: User) -> DailyJourney | None:
    return db.scalar(
        select(DailyJourney)
        .where(DailyJourney.user_id == user.id)
        .order_by(DailyJourney.local_date.desc(), DailyJourney.created_at.desc())
        .limit(1)
    )


def _speaker(db: Session, user: User) -> tuple[str, str]:
    """(character id, display name) of the learner's latest scene, else Marin."""

    journey = _latest_journey(db, user)
    scenario = dict(getattr(journey, "scenario_snapshot", None) or {}) if journey else {}
    raw_id = str(scenario.get("character_id") or "").strip()
    name = str(scenario.get("character_name") or "").strip()
    key = portrait_character(raw_id)
    if raw_id and name:
        return (key or raw_id), name
    if key:
        return key, CHARACTER_NAMES.get(key, name or key)
    return DEFAULT_CHARACTER_ID, CHARACTER_NAMES[DEFAULT_CHARACTER_ID]


def engine_teaser(db: Session, user: User) -> dict[str, str] | None:
    """The story's own forward line, when it wrote one. Read-only.

    Two places, both optional and read with ``.get``: the living-story state's
    ``next_teaser`` (``{"text_fr", "character_id"}``) and the latest recap's
    ``teaser_fr`` (WP-79). Neither exists in the engine yet; when one does, the
    push uses it without another change here.
    """

    from app.db.models.serial import SerialThread

    thread = db.scalar(
        select(SerialThread)
        .where(SerialThread.user_id == user.id, SerialThread.status == "active")
        .order_by(SerialThread.created_at.desc())
        .limit(1)
    )
    live = dict((getattr(thread, "state", None) or {}).get("living_story") or {}) if thread else {}
    teaser = live.get("next_teaser")
    if isinstance(teaser, dict) and _compact(teaser.get("text_fr")):
        return {
            "text_fr": _compact(teaser.get("text_fr"), 160),
            "character_id": str(teaser.get("character_id") or ""),
            "character_name": str(teaser.get("character_name") or ""),
        }
    journey = _latest_journey(db, user)
    recap = dict(getattr(journey, "recap_snapshot", None) or {}) if journey else {}
    text = _compact(recap.get("teaser_fr"), 160)
    if text:
        scenario = dict(getattr(journey, "scenario_snapshot", None) or {})
        return {
            "text_fr": text,
            "character_id": str(scenario.get("character_id") or ""),
            "character_name": str(scenario.get("character_name") or ""),
        }
    return None


def _journey_today(db: Session, user: User, today: date, statuses: tuple[str, ...]) -> DailyJourney | None:
    return db.scalar(
        select(DailyJourney)
        .where(
            DailyJourney.user_id == user.id,
            DailyJourney.local_date == today,
            DailyJourney.status.in_(statuses),
        )
        .order_by(DailyJourney.created_at.desc())
        .limit(1)
    )


def scene_done_today(db: Session, user: User, *, today: date) -> bool:
    from app.services.journey_contracts import TERMINAL_JOURNEY_STATUSES

    terminal = tuple(str(value) for value in TERMINAL_JOURNEY_STATUSES)
    return _journey_today(db, user, today, terminal) is not None


def daily_journey_morning_push(
    db: Session,
    user: User,
    *,
    today: date,
) -> CharacterPush | None:
    """WP-80's morning push, or ``None`` when it does not apply.

    ``None`` outside the journey cohort (the caller keeps the legacy edition)
    and once today's scene is finished: a "the story goes on" push after the
    fact would be a lie. Title: the character's name. Body: the story's own
    teaser when it wrote one, else an authored line in that character's voice.
    """

    from app.services.daily_journey import journey_enabled_for

    if not journey_enabled_for(user) or scene_done_today(db, user, today=today):
        return None

    group = band_group(user)
    resumable = _journey_today(db, user, today, ("preparing", "active", "paused"))
    teaser = None if resumable is not None else engine_teaser(db, user)
    if teaser is not None:
        key = portrait_character(teaser["character_id"])
        fallback_id, fallback_name = _speaker(db, user)
        character_id = key or fallback_id
        name = teaser["character_name"] or CHARACTER_NAMES.get(character_id) or fallback_name
        return CharacterPush(
            title=name,
            message=teaser["text_fr"],
            character_id=character_id,
            image=portrait_path(character_id),
            source="engine",
        )
    character_id, name = _speaker(db, user)
    if resumable is not None:
        message = RESUME_LINES[group]
    else:
        message = MORNING_LINES.get(character_id, DEFAULT_MORNING_LINE)[group]
    return CharacterPush(
        title=name,
        message=message,
        character_id=character_id,
        image=portrait_path(character_id),
        source="authored",
    )


def daily_journey_morning_copy(
    db: Session,
    user: User,
    *,
    today: date,
) -> tuple[str, str] | None:
    """(title, message) of :func:`daily_journey_morning_push`, for older callers."""

    push = daily_journey_morning_push(db, user, today=today)
    return (push.title, push.message) if push else None


def streak_at_risk_push(db: Session, user: User, *, days: int) -> CharacterPush:
    """The evening push for a live streak (≥ 2) whose day is not yet practised."""

    character_id, name = _speaker(db, user)
    line = STREAK_LINES.get(character_id, DEFAULT_STREAK_LINE)[band_group(user)]
    return CharacterPush(
        title=name,
        message=line.format(days=int(days)),
        character_id=character_id,
        image=portrait_path(character_id),
        source="authored",
    )


#: Title for the WP-31 day-before push of a rehearsal whose real event is tomorrow.
REHEARSAL_READY_TITLE = "Votre répétition est prête"


def rehearsal_reminder_copy(
    db: Session,
    user: User,
    *,
    today: date,
) -> tuple[str, str] | None:
    """The day before the real thing, or ``None`` when there is nothing to say.

    WP-31 §7.2, applied by WP-37. Two properties hold it honest:

    * **Only an unplayed rehearsal.** ``ready`` and ``rehearsing`` are the two
      states with turns still to spend. A learner who has already rehearsed —
      ``rehearsed``, ``debriefed`` — does not need reminding, and a rehearsal
      that was never prepared (``declared``, ``not_prepared``) has nothing to
      open. Nudging either would be a push about work that is done or a push to
      a screen with no scene on it.
    * **The learner's own goal, never a story character.** A rehearsal is
      biography, not canon (WP-31 §2): the message repeats what *they* said they
      were going to do. When the structurer resolved no goal the copy falls back
      to a line that claims nothing about the situation.

    A rehearsal with no ``event_date`` is never reminded about: the date was not
    resolvable, and guessing one is how a push arrives on the wrong day.
    """

    from app.db.models.rehearsal import Rehearsal

    row = db.scalar(
        select(Rehearsal).where(
            Rehearsal.user_id == user.id,
            Rehearsal.status.in_(("ready", "rehearsing")),
            Rehearsal.event_date == today + timedelta(days=1),
        )
    )
    if row is None:
        return None
    goal = _compact((row.brief or {}).get("goal_fr") or "")
    return REHEARSAL_READY_TITLE, goal or "C’est demain. Répétez-la une fois."


__all__ = [
    "DAILY_JOURNEY_MORNING_TITLE",
    "JOURNEY_DEEP_LINK",
    "REHEARSAL_READY_TITLE",
    "CharacterPush",
    "daily_journey_morning_copy",
    "daily_journey_morning_push",
    "engine_teaser",
    "portrait_path",
    "scene_done_today",
    "streak_at_risk_push",
    "enqueue_serial_edition_notification",
    "rehearsal_reminder_copy",
]
