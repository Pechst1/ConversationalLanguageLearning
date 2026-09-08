"""Les Mots du jour — the day's coordinated vocabulary slate.

Every surface of the edition teaches the same handful of words each day.
The slate picks up to four focus words (due first, then fragile, at most one
new), preferring words that already appear in today's feuilleton episode so
the reading encounter comes for free. Each word then collects up to three
stamps in three different memory modes:

- ``lu``       — met in context (feuilleton scene completed with the word)
- ``retrouve`` — retrieved from memory (review-deck grade submitted)
- ``place``    — produced (mission credits the word as produced correctly)

The stamps are recorded server-side from the existing flows; a word that
earns all three in one day is marked ``triple`` — the visible payoff on
La Une. Selection persists per (user, day) so all surfaces agree all day.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.mission import RealWorldMission
from app.db.models.user import User
from app.db.models.vocabulary import UserDailyWordSlate
from app.services.glosses import gloss_from_map
from app.services.progress import ProgressService

SLATE_SIZE = 4
MAX_NEW_WORDS = 1
STAMP_KINDS = ("lu", "retrouve", "place")


def _today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).date()


class DailyWordSlateService:
    """Select, persist, and stamp the day's vocabulary slate."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ read

    def get_or_create(self, *, user: User, now: datetime | None = None) -> dict[str, Any]:
        """Return today's slate payload, selecting it on first call of the day."""
        slate = self._row(user=user, now=now)
        if slate is not None:
            return dict(slate.payload or {})
        payload = self._select(user=user, now=now)
        slate = UserDailyWordSlate(user_id=user.id, slate_date=_today(now), payload=payload)
        try:
            # Isolate the uniqueness race in a savepoint. Rolling back the
            # whole request here would discard unrelated mission/scene work
            # already staged by callers that create the slate incidentally.
            with self.db.begin_nested():
                self.db.add(slate)
                self.db.flush([slate])
        except IntegrityError:
            # Two surfaces raced on the day's first call; keep the winner's row.
            slate = self._row(user=user, now=now)
            if slate is not None:
                return dict(slate.payload or {})
            raise
        return dict(payload)

    def slate_word_ids(self, *, user: User, now: datetime | None = None) -> list[int]:
        """Word ids on today's slate, creating the slate if needed.

        Used by mission / feuilleton vocabulary selection so every surface
        converges on the same words. Never raises: surfaces must not break
        because the slate could not be built.
        """
        try:
            payload = self.get_or_create(user=user, now=now)
        except Exception:
            return []
        ids: list[int] = []
        for entry in payload.get("words") or []:
            try:
                ids.append(int(entry["word_id"]))
            except (KeyError, TypeError, ValueError):
                continue
        return ids

    def focus_word_ids(self, *, user: User, now: datetime | None = None) -> list[int]:
        """Slate words with real retrieval value (due/fragile — never brand-new).

        Missions produce these; producing a word met for the first time today
        would be premature, so the "new" slot is excluded here (the feuilleton
        read is where a new word gets its first contextual encounter).
        """
        try:
            payload = self.get_or_create(user=user, now=now)
        except Exception:
            return []
        ids: list[int] = []
        for entry in payload.get("words") or []:
            if (entry.get("bucket") or "due") == "new":
                continue
            try:
                ids.append(int(entry["word_id"]))
            except (KeyError, TypeError, ValueError):
                continue
        return ids

    # ----------------------------------------------------------------- write

    def record_encounter(
        self,
        *,
        user: User,
        word_id: int,
        kind: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Stamp one encounter (lu / retrouve / place) on today's slate.

        Idempotent per day; silently does nothing when the word is not on the
        slate or the slate does not exist yet (encounters never create one —
        selection stays a deliberate morning act). Returns the updated word
        entry, or ``None`` when nothing changed.
        """
        if kind not in STAMP_KINDS:
            return None
        # Stamp updates are read-modify-write operations on one JSON payload.
        # Lock the row so simultaneous review/mission completions cannot erase
        # one another's stamps on PostgreSQL.
        slate = self._row(user=user, now=now, for_update=True)
        if slate is None:
            return None
        payload = dict(slate.payload or {})
        words = [dict(entry) for entry in (payload.get("words") or [])]
        updated: dict[str, Any] | None = None
        for entry in words:
            if int(entry.get("word_id") or 0) != int(word_id):
                continue
            stamps = dict(entry.get("stamps") or {})
            if stamps.get(kind):
                return None
            stamps[kind] = (now or datetime.now(UTC)).isoformat()
            entry["stamps"] = stamps
            entry["triple"] = all(stamps.get(k) for k in STAMP_KINDS)
            updated = entry
            break
        if updated is None:
            return None
        payload["words"] = words
        payload["triples"] = sum(1 for entry in words if entry.get("triple"))
        slate.payload = payload
        self.db.add(slate)
        if updated.get("triple"):
            from app.services.pilot_events import PilotEventService

            PilotEventService(self.db).record(
                "slate_triple",
                user_id=user.id,
                entity_type="vocabulary_word",
                entity_id=word_id,
                payload={"word": updated.get("word"), "slate_date": slate.slate_date.isoformat()},
            )
        self.db.flush([slate])
        return updated

    def record_encounters(
        self,
        *,
        user: User,
        word_ids: list[int],
        kind: str,
        now: datetime | None = None,
    ) -> int:
        """Stamp several words at once; returns how many stamps landed."""
        count = 0
        for word_id in word_ids:
            try:
                if self.record_encounter(user=user, word_id=int(word_id), kind=kind, now=now):
                    count += 1
            except (TypeError, ValueError):
                continue
        return count

    # ------------------------------------------------------------- selection

    def _row(
        self,
        *,
        user: User,
        now: datetime | None = None,
        for_update: bool = False,
    ) -> UserDailyWordSlate | None:
        query = (
            self.db.query(UserDailyWordSlate)
            .filter(
                UserDailyWordSlate.user_id == user.id,
                UserDailyWordSlate.slate_date == _today(now),
            )
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def _select(self, *, user: User, now: datetime | None = None) -> dict[str, Any]:
        context = ProgressService(self.db).get_vocabulary_due_context(
            user=user,
            limit=24,
            due_limit=12,
            fragile_limit=8,
            new_limit=4,
            topic_limit=0,
            linked_limit=0,
            now=now,
        )
        due = list(context.get("due_words") or [])
        fragile = list(context.get("fragile_words") or [])
        new = list(context.get("new_words") or [])[:MAX_NEW_WORDS]

        # Never re-drill a nailed word: a mastered word with no scheduled
        # review can surface in the "due" bucket, but the slate exists for
        # shaky memory, not victory laps.
        nailed_ids = self._nailed_ids(
            user=user,
            candidate_ids=[int(item.get("word_id") or 0) for item in due + fragile],
            now=now,
        )
        due = [item for item in due if int(item.get("word_id") or 0) not in nailed_ids]
        fragile = [item for item in fragile if int(item.get("word_id") or 0) not in nailed_ids]

        scene = self._todays_scene(user=user, now=now)
        scene_word_ids = {
            int(word_id)
            for word_id in ((scene.target_vocabulary_ids or []) if scene else [])
            if isinstance(word_id, (int, str)) and str(word_id).isdigit()
        }

        # Words already printed in today's episode come first: the "lu"
        # encounter is then free, and the reader meets the word in story
        # context before ever being tested on it.
        in_scene = [item for item in due + fragile if int(item.get("word_id") or 0) in scene_word_ids]
        rest = [item for item in due + fragile if int(item.get("word_id") or 0) not in scene_word_ids]

        picked: list[dict[str, Any]] = []
        seen: set[int] = set()
        for item in in_scene + rest + new:
            word_id = int(item.get("word_id") or 0)
            if not word_id or word_id in seen:
                continue
            picked.append(item)
            seen.add(word_id)
            if len(picked) >= SLATE_SIZE:
                break

        words = [self._entry(user=user, item=item, scene=scene, scene_word_ids=scene_word_ids) for item in picked]
        return {
            "date": _today(now).isoformat(),
            "words": words,
            "triples": 0,
            "version": "mots-du-jour-v1",
        }

    def _entry(
        self,
        *,
        user: User,
        item: dict[str, Any],
        scene: GraphicNovelScene | None,
        scene_word_ids: set[int],
    ) -> dict[str, Any]:
        word_id = int(item.get("word_id") or 0)
        translations = item.get("translations") if isinstance(item.get("translations"), dict) else {}
        return {
            "word_id": word_id,
            "word": item.get("word") or "",
            # Upstream payloads already resolve `translation` for this learner;
            # the raw map is only a fallback, and it must not default to German.
            "translation": item.get("translation") or gloss_from_map(translations, user.native_language),
            "bucket": item.get("bucket") or "due",
            "example_sentence": item.get("example_sentence") or None,
            "example_translation": item.get("example_translation") or None,
            "anchor": self._anchor(user=user, word_id=word_id, scene=scene, scene_word_ids=scene_word_ids),
            "stamps": {},
            "triple": False,
        }

    def _nailed_ids(
        self,
        *,
        user: User,
        candidate_ids: list[int],
        now: datetime | None = None,
    ) -> set[int]:
        from app.db.models.progress import UserVocabularyProgress
        from app.services.vocabulary_coverage import is_vocab_nailed

        ids = [word_id for word_id in candidate_ids if word_id]
        if not ids:
            return set()
        rows = (
            self.db.query(UserVocabularyProgress)
            .filter(
                UserVocabularyProgress.user_id == user.id,
                UserVocabularyProgress.word_id.in_(ids),
            )
            .all()
        )
        return {
            int(row.word_id)
            for row in rows
            if is_vocab_nailed(row, now=now or datetime.now(UTC))
        }

    def _todays_scene(self, *, user: User, now: datetime | None = None) -> GraphicNovelScene | None:
        scene = (
            self.db.query(GraphicNovelScene)
            .filter(GraphicNovelScene.user_id == user.id)
            .order_by(GraphicNovelScene.created_at.desc())
            .first()
        )
        if scene is None:
            return None
        created = scene.created_at
        if created is not None:
            created_date = (
                created.astimezone(UTC).date()
                if created.tzinfo
                else created.date()
            )
            if created_date != _today(now):
                return None
        return scene

    def _anchor(
        self,
        *,
        user: User,
        word_id: int,
        scene: GraphicNovelScene | None,
        scene_word_ids: set[int],
    ) -> str | None:
        """One episodic line tying the word to the learner's own story.

        Retrieval cues that point at a self-experienced moment ("you read
        this in Episode IV") anchor far better than a bare dictionary line.
        Shown after the answer in the review deck, never before.
        """
        if scene is not None and word_id in scene_word_ids:
            if scene.episode_index is not None:
                return f"Dans l’épisode {int(scene.episode_index) + 1} · {scene.title}"
            return f"Dans « {scene.title} »"
        past_scene = (
            self.db.query(GraphicNovelScene)
            .filter(
                GraphicNovelScene.user_id == user.id,
                GraphicNovelScene.completed_at.isnot(None),
            )
            .order_by(GraphicNovelScene.completed_at.desc())
            .limit(12)
            .all()
        )
        for candidate in past_scene:
            ids = {int(v) for v in (candidate.target_vocabulary_ids or []) if str(v).isdigit()}
            if word_id in ids:
                if candidate.episode_index is not None:
                    return f"Lu dans l’épisode {int(candidate.episode_index) + 1} · {candidate.title}"
                return f"Lu dans « {candidate.title} »"
        past_mission = (
            self.db.query(RealWorldMission)
            .filter(RealWorldMission.user_id == user.id)
            .order_by(RealWorldMission.created_at.desc())
            .limit(12)
            .all()
        )
        for candidate in past_mission:
            ids = {int(v) for v in (candidate.target_vocabulary_ids or []) if str(v).isdigit()}
            if word_id in ids:
                return f"Courrier · « {candidate.title} »"
        return None
