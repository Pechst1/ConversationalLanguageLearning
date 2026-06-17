"""Server-side Atelier reward economy helpers."""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierAttempt, AtelierCollectible, AtelierSession
from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.serial import SerialEpisode, SerialThread


LOGO_TOKEN = "logo_token"
GILT_SEAL = "gilt_seal"
STORY_SEAL = "story_seal"
PLATE_SEMAINE = "plate_semaine"
PLATE_CHAPTER = "plate_chapter"
COLOPHON = "colophon"

GILT_VARIANTS = ("row", "stack", "nested", "quad")
PLATE_KINDS = {PLATE_SEMAINE, PLATE_CHAPTER, COLOPHON}
COLLECTIBLE_KINDS = (LOGO_TOKEN, GILT_SEAL, STORY_SEAL, PLATE_SEMAINE, PLATE_CHAPTER, COLOPHON)
WORKSHOP_RULES: dict[str, dict[str, Any]] = {
    PLATE_SEMAINE: {"member_kind": LOGO_TOKEN, "required": 7, "label": "Semaine gilt plate"},
    PLATE_CHAPTER: {"member_kind": STORY_SEAL, "required": 3, "label": "Bound chapter plate"},
    COLOPHON: {"member_kind": GILT_SEAL, "required": 4, "label": "Annual colophon"},
}


@dataclass
class AtelierWorkshopShortfall(Exception):
    target: str
    member_kind: str
    required: int
    available: int

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "code": "atelier_workshop_shortfall",
            "target": self.target,
            "member_kind": self.member_kind,
            "required": self.required,
            "available": self.available,
            "shortfall": max(0, self.required - self.available),
        }


def serialize_collectible(item: AtelierCollectible, *, members: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = {
        "id": str(item.id),
        "kind": item.kind,
        "minted_at": item.minted_at.isoformat() if item.minted_at else None,
        "source_kind": item.source_kind,
        "source_ref": item.source_ref,
        "metadata": item.metadata_payload or {},
        "composed": bool(item.composed),
        "composed_into_id": str(item.composed_into_id) if item.composed_into_id else None,
    }
    if members is not None:
        payload["members"] = members
    return payload


class AtelierRewardService:
    """Mint, query, and compose Atelier collectibles."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def mint_logo_token_for_attempt(self, attempt: AtelierAttempt, *, first_submission: bool) -> list[dict[str, Any]]:
        if not first_submission or not self._is_flawless_recognize_screen(attempt):
            return []
        item, created = self._mint(
            user_id=attempt.user_id,
            kind=LOGO_TOKEN,
            source_kind="screen",
            source_ref=self._screen_source_ref(attempt),
            metadata={
                "name": "Logo token",
                "date": self._date_for(attempt.created_at),
                "screen": {
                    "session_id": str(attempt.atelier_session_id),
                    "concept_id": attempt.concept_id,
                    "round": attempt.round,
                    "mode": attempt.mode,
                    "exercise_id": attempt.exercise_id,
                },
            },
        )
        return [serialize_collectible(item)] if created else []

    def mint_gilt_seal_for_session(self, session: AtelierSession) -> list[dict[str, Any]]:
        attempts = list(
            self.db.query(AtelierAttempt)
            .filter(AtelierAttempt.atelier_session_id == session.id)
            .order_by(AtelierAttempt.created_at.asc(), AtelierAttempt.id.asc())
            .all()
        )
        if not self._is_flawless_session(session, attempts):
            return []
        completed_at = session.completed_at or datetime.now(timezone.utc)
        variant = self._gilt_variant(completed_at, str(session.id))
        item, created = self._mint(
            user_id=session.user_id,
            kind=GILT_SEAL,
            source_kind="session",
            source_ref=str(session.id),
            metadata={
                "name": "Gilt seal",
                "date": self._date_for(completed_at),
                "seal_variant": variant,
                "session_id": str(session.id),
                "attempts": len(attempts),
            },
        )
        return [serialize_collectible(item)] if created else []

    def mint_story_seal_for_serial_episode(
        self,
        *,
        user_id: UUID,
        thread: SerialThread,
        episode: SerialEpisode,
        scene: GraphicNovelScene | None = None,
    ) -> list[dict[str, Any]]:
        if episode.kind != "feuilleton":
            return []
        scene = scene or (self.db.get(GraphicNovelScene, episode.scene_id) if episode.scene_id else None)
        crop = self._story_seal_crop(scene)
        item, created = self._mint(
            user_id=user_id,
            kind=STORY_SEAL,
            source_kind="serial_beat",
            source_ref=f"{thread.id}:{episode.episode_index}",
            metadata={
                "name": "Story seal",
                "date": self._date_for(episode.completed_at),
                "thread_id": str(thread.id),
                "episode_id": str(episode.id),
                "episode_index": episode.episode_index,
                "episode_label": f"Episode {episode.episode_index + 1}",
                "scene_id": str(episode.scene_id) if episode.scene_id else None,
                "scene_title": scene.title if scene else None,
                "seal_crop": crop,
            },
        )
        return [serialize_collectible(item)] if created else []

    def almanac(self, *, user_id: UUID) -> dict[str, Any]:
        rows = self._collectibles_for_user(user_id)
        grouped: dict[str, list[dict[str, Any]]] = {kind: [] for kind in COLLECTIBLE_KINDS}
        for row in rows:
            grouped.setdefault(row.kind, []).append(serialize_collectible(row))

        members_by_plate: dict[UUID, list[AtelierCollectible]] = defaultdict(list)
        for row in rows:
            if row.composed_into_id:
                members_by_plate[row.composed_into_id].append(row)
        plates = [
            serialize_collectible(
                row,
                members=[serialize_collectible(member) for member in members_by_plate.get(row.id, [])],
            )
            for row in rows
            if row.kind in PLATE_KINDS
        ]
        return {
            "collectibles": grouped,
            "progress": self.workshop_progress(user_id=user_id),
            "plates": plates,
            "totals": dict(Counter(row.kind for row in rows)),
        }

    def compose(self, *, user_id: UUID, target: str) -> dict[str, Any]:
        if target not in WORKSHOP_RULES:
            raise ValueError(f"Unsupported Atelier workshop target: {target}")
        rule = WORKSHOP_RULES[target]
        member_kind = str(rule["member_kind"])
        required = int(rule["required"])
        members = (
            self.db.query(AtelierCollectible)
            .filter(
                AtelierCollectible.user_id == user_id,
                AtelierCollectible.kind == member_kind,
                AtelierCollectible.composed.is_(False),
            )
            .order_by(AtelierCollectible.minted_at.asc(), AtelierCollectible.id.asc())
            .limit(required)
            .all()
        )
        if len(members) < required:
            raise AtelierWorkshopShortfall(
                target=target,
                member_kind=member_kind,
                required=required,
                available=len(members),
            )

        member_ids = [str(member.id) for member in members]
        source_ref = self._compose_source_ref(target, member_ids)
        existing = self._existing(
            user_id=user_id,
            kind=target,
            source_kind="compose",
            source_ref=source_ref,
        )
        created = existing is None
        if existing:
            plate = existing
            members = (
                self.db.query(AtelierCollectible)
                .filter(AtelierCollectible.composed_into_id == plate.id)
                .order_by(AtelierCollectible.minted_at.asc(), AtelierCollectible.id.asc())
                .all()
            )
        else:
            plate = AtelierCollectible(
                user_id=user_id,
                kind=target,
                source_kind="compose",
                source_ref=source_ref,
                metadata_payload={
                    "name": str(rule["label"]),
                    "target": target,
                    "member_kind": member_kind,
                    "required": required,
                    "member_ids": member_ids,
                    "date": self._date_for(None),
                },
            )
            self.db.add(plate)
            self.db.flush([plate])
            for member in members:
                member.composed = True
                member.composed_into_id = plate.id
                self.db.add(member)
            self.db.commit()
            self.db.refresh(plate)
            for member in members:
                self.db.refresh(member)

        return {
            "plate": serialize_collectible(plate),
            "members": [serialize_collectible(member) for member in members],
            "progress": self.workshop_progress(user_id=user_id),
            "minted_collectibles": [serialize_collectible(plate)] if created else [],
        }

    def workshop_progress(self, *, user_id: UUID) -> dict[str, dict[str, Any]]:
        progress: dict[str, dict[str, Any]] = {}
        for target, rule in WORKSHOP_RULES.items():
            member_kind = str(rule["member_kind"])
            required = int(rule["required"])
            available = (
                self.db.query(AtelierCollectible)
                .filter(
                    AtelierCollectible.user_id == user_id,
                    AtelierCollectible.kind == member_kind,
                    AtelierCollectible.composed.is_(False),
                )
                .count()
            )
            progress[target] = {
                "target": target,
                "member_kind": member_kind,
                "required": required,
                "available": int(available),
                "progress": min(int(available), required),
                "shortfall": max(0, required - int(available)),
            }
        return progress

    def _mint(
        self,
        *,
        user_id: UUID,
        kind: str,
        source_kind: str,
        source_ref: str,
        metadata: dict[str, Any],
    ) -> tuple[AtelierCollectible, bool]:
        existing = self._existing(user_id=user_id, kind=kind, source_kind=source_kind, source_ref=source_ref)
        if existing:
            return existing, False
        item = AtelierCollectible(
            user_id=user_id,
            kind=kind,
            source_kind=source_kind,
            source_ref=source_ref,
            metadata_payload=metadata,
        )
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self._existing(user_id=user_id, kind=kind, source_kind=source_kind, source_ref=source_ref)
            if existing:
                return existing, False
            raise
        self.db.refresh(item)
        return item, True

    def _existing(self, *, user_id: UUID, kind: str, source_kind: str, source_ref: str) -> AtelierCollectible | None:
        return (
            self.db.query(AtelierCollectible)
            .filter(
                AtelierCollectible.user_id == user_id,
                AtelierCollectible.kind == kind,
                AtelierCollectible.source_kind == source_kind,
                AtelierCollectible.source_ref == source_ref,
            )
            .first()
        )

    def _collectibles_for_user(self, user_id: UUID) -> list[AtelierCollectible]:
        return list(
            self.db.query(AtelierCollectible)
            .filter(AtelierCollectible.user_id == user_id)
            .order_by(AtelierCollectible.minted_at.asc(), AtelierCollectible.id.asc())
            .all()
        )

    @staticmethod
    def _is_flawless_recognize_screen(attempt: AtelierAttempt) -> bool:
        if attempt.round != "recognize" or attempt.verdict != "correct" or float(attempt.score_0_4 or 0) < 4:
            return False
        correction = attempt.correction_payload or {}
        if correction.get("errata") or correction.get("missing_targets"):
            return False
        items = (attempt.prompt_payload or {}).get("items") or []
        corrected = correction.get("corrected_answer") if isinstance(correction, dict) else {}
        return len(items) == 3 and isinstance(corrected, dict) and len(corrected) == 3

    @classmethod
    def _is_flawless_session(cls, session: AtelierSession, attempts: list[AtelierAttempt]) -> bool:
        if not attempts:
            return False
        if any(not cls._is_flawless_attempt(attempt) for attempt in attempts):
            return False
        expected = cls._expected_session_keys(session)
        if not expected:
            return False
        submitted = {cls._session_attempt_key(attempt) for attempt in attempts}
        return expected.issubset(submitted)

    @staticmethod
    def _is_flawless_attempt(attempt: AtelierAttempt) -> bool:
        if attempt.verdict not in {"correct", "accepted"} or float(attempt.score_0_4 or 0) < 4:
            return False
        correction = attempt.correction_payload or {}
        return not correction.get("errata") and not correction.get("missing_targets")

    @staticmethod
    def _expected_session_keys(session: AtelierSession) -> set[tuple[Any, ...]]:
        concept_ids = [int(item) for item in (session.selected_concept_ids or [])]
        expected: set[tuple[Any, ...]] = {("produce", None)}
        for concept_id in concept_ids:
            expected.update(
                {
                    ("recognize", "fill", concept_id),
                    ("recognize", "classify", concept_id),
                    ("recognize", "word_bank", concept_id),
                    ("transform", concept_id),
                    ("sentence", concept_id),
                    ("speak", concept_id),
                    ("conversation", concept_id),
                }
            )
        return expected

    @staticmethod
    def _session_attempt_key(attempt: AtelierAttempt) -> tuple[Any, ...]:
        if attempt.round == "recognize":
            return ("recognize", attempt.mode, attempt.concept_id)
        if attempt.round == "produce":
            return ("produce", None)
        if attempt.round == "transform":
            return ("transform", attempt.concept_id)
        return (attempt.round, attempt.concept_id)

    @staticmethod
    def _screen_source_ref(attempt: AtelierAttempt) -> str:
        concept_ref = str(attempt.concept_id) if attempt.concept_id is not None else "session"
        raw = f"{attempt.atelier_session_id}:{concept_ref}:{attempt.round}:{attempt.mode}:{attempt.exercise_id}"
        return raw[:180]

    @staticmethod
    def _compose_source_ref(target: str, member_ids: list[str]) -> str:
        digest = hashlib.sha256("|".join(member_ids).encode("utf-8")).hexdigest()[:24]
        return f"{target}:{digest}"

    @staticmethod
    def _gilt_variant(completed_at: datetime, source_ref: str) -> str:
        basis = f"{completed_at.date().isoformat()}:{source_ref}"
        index = int(hashlib.sha256(basis.encode("utf-8")).hexdigest(), 16) % len(GILT_VARIANTS)
        return GILT_VARIANTS[index]

    @staticmethod
    def _date_for(value: datetime | None) -> str:
        moment = value or datetime.now(timezone.utc)
        return moment.date().isoformat()

    @staticmethod
    def _story_seal_crop(scene: GraphicNovelScene | None) -> dict[str, Any]:
        if not scene:
            return {"kind": "house_mark", "fallback": True}
        panel = AtelierRewardService._story_seal_panel(scene)
        if not panel:
            return {"kind": "house_mark", "scene_id": str(scene.id), "fallback": True}
        metadata = panel.generation_metadata or {}
        image_payload = panel.image_payload or {}
        crop = metadata.get("seal_crop") if isinstance(metadata.get("seal_crop"), dict) else None
        crop = crop or (image_payload.get("seal_crop") if isinstance(image_payload.get("seal_crop"), dict) else None)
        image_url = panel.image_url or image_payload.get("url") or (crop or {}).get("image_url")
        if crop:
            return {
                **crop,
                "kind": crop.get("kind") or "panel_crop",
                "scene_id": str(scene.id),
                "panel_id": str(panel.id),
                "panel_index": panel.panel_index,
                "image_url": image_url,
                "fallback": False,
            }
        return {
            "kind": "panel_crop",
            "scene_id": str(scene.id),
            "panel_id": str(panel.id),
            "panel_index": panel.panel_index,
            "image_url": image_url,
            "focal_point": {"x": 0.5, "y": 0.5},
            "region": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "fallback": not bool(image_url),
        }

    @staticmethod
    def _story_seal_panel(scene: GraphicNovelScene) -> GraphicNovelPanel | None:
        panels = sorted(scene.panels or [], key=lambda item: item.panel_index)
        if not panels:
            return None
        for panel in panels:
            metadata = panel.generation_metadata or {}
            if isinstance(metadata.get("seal_crop"), dict):
                return panel
        return panels[0]
