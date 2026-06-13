"""Deterministic season planner for the Serial World spine."""
from __future__ import annotations

from typing import Any

from app.config import settings
from app.db.models.serial import SerialThread
from app.schemas.serial import EpisodeBrief


STRUCTURE_ROTATION = ("ensemble", "two_hander", "bottle", "callback_open", "news_edition")
MISSION_FORMAT_ROTATION = ("chat_message", "email_formal", "admin_form", "voicemail_reply", "phone_call")
SEASON_FINALE_ARC_ID = "__season_finale__"

CEFR_RAMP: dict[str, dict[str, Any]] = {
    "A1": {
        "caption_complexity": "very short A1 captions; mostly present tense, concrete vocabulary",
        "mission_objective_count": 2,
        "min_words": 25,
    },
    "A2": {
        "caption_complexity": "short A2 captions; present, near future, clear connectors",
        "mission_objective_count": 3,
        "min_words": 35,
    },
    "B1": {
        "caption_complexity": "natural B1 captions; past/present contrast and simple nuance",
        "mission_objective_count": 4,
        "min_words": 60,
    },
    "B2": {
        "caption_complexity": "richer B2 captions; subtext, concession, and idiomatic turns",
        "mission_objective_count": 5,
        "min_words": 90,
    },
    "C1": {
        "caption_complexity": "dense C1 captions; implied motives and register play",
        "mission_objective_count": 5,
        "min_words": 100,
    },
    "C2": {
        "caption_complexity": "native-like C2 captions; irony, rhythm, and layered implication",
        "mission_objective_count": 5,
        "min_words": 110,
    },
}


def cefr_generation_profile(level: Any) -> dict[str, Any]:
    normalized = str(level or "B1").strip().upper().replace("-", "_")
    aliases = {
        "BEGINNER": "A1",
        "ELEMENTARY": "A2",
        "INTERMEDIATE": "B1",
        "UPPER_INTERMEDIATE": "B2",
        "ADVANCED": "C1",
    }
    return dict(CEFR_RAMP.get(aliases.get(normalized, normalized), CEFR_RAMP["B1"]))


def _state_value(state: dict[str, Any], key: str) -> Any:
    if key in state:
        return state.get(key)
    cursor: Any = state
    for part in key.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _int_or(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class SerialArcPlanner:
    """Plan the next episode from durable state rather than from a model."""

    def __init__(self, thread: SerialThread) -> None:
        self.thread = thread
        self.world = thread.world_bible if isinstance(thread.world_bible, dict) else {}
        self.state = thread.state if isinstance(thread.state, dict) else {}

    def plan_next_episode(self, beat: str) -> EpisodeBrief:
        normalized_beat = "see" if beat in {"see", "feuilleton"} else "act"
        episode_index = _int_or(self.thread.current_episode_index, 0)
        if self.season_complete():
            return self._season_finale_brief(beat=normalized_beat, episode_index=episode_index)
        arc, stage, stage_index, advance_on_completion = self._select_arc_stage(episode_index)
        required_cast = self._required_cast(
            arc_characters=[str(item) for item in (arc or {}).get("characters") or []],
            episode_index=episode_index,
        )
        location = self._location_for(episode_index=episode_index, required_cast=required_cast)
        structure = self._structure_for(episode_index=episode_index, beat=normalized_beat, required_cast=required_cast)
        completed = int(self.state.get("episodes_completed") or len([ep for ep in self.thread.episodes or [] if ep.status == "completed"]))
        include_news_panel = structure == "news_edition" or (completed > 0 and completed % 7 == 0)
        include_choice_fork = normalized_beat == "see" and self._last_see_choice_episode() != episode_index - 2
        tentpole = bool((stage or {}).get("tentpole"))
        next_beat_kind = "mission" if normalized_beat == "see" else "feuilleton"
        mission_format = self._mission_format_for(episode_index=episode_index, beat=normalized_beat)
        hook_guidance = self._hook_guidance(required_cast=required_cast, stage=stage, next_beat_kind=next_beat_kind)
        tentpole_reference = f"docs/serial-episode-tentpole-{(arc or {}).get('id')}.md" if tentpole and arc else None
        profile = cefr_generation_profile(getattr(self.thread.user, "proficiency_level", None))

        return EpisodeBrief(
            episode_index=episode_index,
            beat=normalized_beat,
            mission_format=mission_format,
            a_plot={
                "arc_id": (arc or {}).get("id"),
                "stage_id": (stage or {}).get("id"),
                "stage_index": stage_index,
                "stage_summary": (stage or {}).get("summary") or "",
                "characters": [str(item) for item in (arc or {}).get("characters") or []],
                "advance_on_completion": advance_on_completion,
                "sets": (stage or {}).get("sets") or {},
                "tentpole": tentpole,
            },
            b_plot=self._b_plot(episode_index=episode_index, structure=structure, required_cast=required_cast),
            required_cast=required_cast,
            location_id=str(location.get("id") or "le_mistral"),
            structure=structure,
            include_news_panel=include_news_panel,
            include_choice_fork=include_choice_fork,
            stakes_level=min(3, self._stakes_level() + (1 if tentpole else 0)),
            hook_guidance=hook_guidance,
            tentpole_reference=tentpole_reference,
            next_beat_kind=next_beat_kind,
            location=location,
            cefr_profile=profile,
            relationship_context=self._relationships_for(required_cast),
        )

    def season_complete(self) -> bool:
        arcs = [arc for arc in self.world.get("season_arcs") or [] if isinstance(arc, dict) and arc.get("id")]
        if not arcs:
            return False
        arc_state = self.state.get("arcs") if isinstance(self.state.get("arcs"), dict) else {}
        for arc in arcs:
            stages = [stage for stage in arc.get("stages") or [] if isinstance(stage, dict) and stage.get("id")]
            if not stages:
                return False
            entry = arc_state.get(str(arc.get("id"))) if isinstance(arc_state, dict) else {}
            try:
                stage_index = int((entry or {}).get("stage_index"))
            except (TypeError, ValueError):
                return False
            if stage_index < len(stages) - 1:
                return False
        return True

    def _season_finale_brief(self, *, beat: str, episode_index: int) -> EpisodeBrief:
        required_cast = self._main_cast_ids() or ["margaux_barman"]
        setting = self.world.get("setting") if isinstance(self.world.get("setting"), dict) else {}
        locations = [item for item in setting.get("recurring_locations") or [] if isinstance(item, dict) and item.get("id")]
        by_id = {str(item.get("id")): item for item in locations}
        location = by_id.get("le_mistral") or (locations[0] if locations else {"id": "le_mistral", "name": "Le Mistral"})
        season_number = _int_or(self.state.get("season_number") or self.world.get("season_number"), 1)
        return EpisodeBrief(
            episode_index=episode_index,
            beat=beat,
            mission_format=self._mission_format_for(episode_index=episode_index, beat=beat),
            a_plot={
                "arc_id": SEASON_FINALE_ARC_ID,
                "stage_id": f"season_{season_number}_finale",
                "stage_index": 0,
                "stage_summary": "The season's open threads converge at Le Mistral before a new set of problems begins.",
                "characters": required_cast,
                "advance_on_completion": False,
                "season_finale": True,
            },
            b_plot={"kind": "finale", "seed": "Every private secret becomes public enough to change the next season."},
            required_cast=required_cast,
            location_id=str(location.get("id") or "le_mistral"),
            structure="ensemble",
            include_news_panel=False,
            include_choice_fork=False,
            stakes_level=3,
            hook_guidance="Pay off the season's promises, then leave one clean doorway into season 2.",
            tentpole_reference="docs/serial-season-finale.md",
            next_beat_kind="mission" if beat == "see" else "feuilleton",
            location=location,
            cefr_profile=cefr_generation_profile(getattr(self.thread.user, "proficiency_level", None)),
            relationship_context=self._relationships_for(required_cast),
            season_finale=True,
            season_number=season_number,
        )

    def _select_arc_stage(self, episode_index: int) -> tuple[dict[str, Any] | None, dict[str, Any] | None, int, bool]:
        arcs = [arc for arc in self.world.get("season_arcs") or [] if isinstance(arc, dict) and arc.get("id")]
        if not arcs:
            return None, None, -1, False
        arc_state = self.state.get("arcs") if isinstance(self.state.get("arcs"), dict) else {}
        eligible: list[tuple[int, int, dict[str, Any], dict[str, Any], int]] = []
        fallback: list[tuple[int, int, dict[str, Any], dict[str, Any], int]] = []
        for order, arc in enumerate(arcs):
            stages = [stage for stage in arc.get("stages") or [] if isinstance(stage, dict) and stage.get("id")]
            if not stages:
                continue
            entry = arc_state.get(str(arc.get("id"))) if isinstance(arc_state, dict) else {}
            current_index = int((entry or {}).get("stage_index") if (entry or {}).get("stage_index") is not None else -1)
            advanced_at = int((entry or {}).get("advanced_at_episode") if (entry or {}).get("advanced_at_episode") is not None else -1)
            next_index = current_index + 1
            if next_index >= len(stages):
                fallback.append((advanced_at, order, arc, stages[-1], current_index))
                continue
            next_stage = stages[next_index]
            min_gap = max(0, int(arc.get("min_episodes_between_stages") or 0))
            gap_ok = current_index < 0 or episode_index - advanced_at >= min_gap
            entry_ok = self._entry_requirements_met(next_stage)
            if gap_ok and entry_ok:
                eligible.append((advanced_at, order, arc, next_stage, next_index))
            else:
                fallback.append((advanced_at, order, arc, stages[max(0, current_index)], current_index))
        if eligible:
            _, _, arc, stage, next_index = min(eligible, key=lambda item: (item[0], item[1]))
            return arc, stage, next_index, True
        if fallback:
            _, _, arc, stage, current_index = min(fallback, key=lambda item: (item[0], item[1]))
            return arc, stage, current_index, False
        return arcs[0], None, -1, False

    def _entry_requirements_met(self, stage: dict[str, Any]) -> bool:
        requirements = stage.get("entry_requires") if isinstance(stage.get("entry_requires"), dict) else {}
        for key, expected in requirements.items():
            if _state_value(self.state, str(key)) != expected:
                return False
        return True

    def _required_cast(self, *, arc_characters: list[str], episode_index: int) -> list[str]:
        main_cast = self._main_cast_ids()
        cast_last_seen = self.state.get("cast_last_seen") if isinstance(self.state.get("cast_last_seen"), dict) else {}
        selected = [item for item in arc_characters if item != "user"]
        stale = sorted(
            main_cast,
            key=lambda character_id: (
                int(cast_last_seen.get(character_id) if cast_last_seen.get(character_id) is not None else -999),
                main_cast.index(character_id),
            ),
        )
        for character_id in stale:
            last_seen = int(cast_last_seen.get(character_id) if cast_last_seen.get(character_id) is not None else -999)
            if character_id not in selected and (episode_index - last_seen >= 3 or len(selected) < 2):
                selected.append(character_id)
            if len(selected) >= 3:
                break
        return _dedupe(selected or main_cast[:2] or ["margaux_barman"])

    def _main_cast_ids(self) -> list[str]:
        cast = self.world.get("cast") if isinstance(self.world.get("cast"), list) else []
        ids = [str(item.get("id")) for item in cast if isinstance(item, dict) and item.get("id")]
        return [item for item in ids if item not in {"user", "landlord_marchand"}]

    def _location_for(self, *, episode_index: int, required_cast: list[str]) -> dict[str, Any]:
        setting = self.world.get("setting") if isinstance(self.world.get("setting"), dict) else {}
        locations = [item for item in setting.get("recurring_locations") or [] if isinstance(item, dict) and item.get("id")]
        if not locations:
            return {"id": "le_mistral", "name": "Le Mistral", "description": "A warm corner cafe in Paris."}
        by_id = {str(item.get("id")): item for item in locations}
        if "landlord_marchand" in required_cast and "office_admin" in by_id:
            return by_id["office_admin"]
        if required_cast == ["romy_tremblay"] and "newsroom" in by_id:
            return by_id["newsroom"]
        if "augustin_de_roncourt" in required_cast and episode_index % 3 == 0 and "brocante" in by_id:
            return by_id["brocante"]
        previous_locations = [
            str(episode.location_id)
            for episode in sorted(self.thread.episodes or [], key=lambda item: item.episode_index)
            if episode.location_id
        ]
        last_location = previous_locations[-1] if previous_locations else ""
        location_ids = [str(item.get("id")) for item in locations]
        usage = {location_id: previous_locations.count(location_id) for location_id in location_ids}
        candidates = [item for item in locations if str(item.get("id")) != last_location]
        if not candidates:
            return locations[0]
        return min(candidates, key=lambda item: (usage.get(str(item.get("id")), 0), location_ids.index(str(item.get("id")))))

    def _structure_for(self, *, episode_index: int, beat: str, required_cast: list[str]) -> str:
        previous = [
            (episode.brief_payload or {}).get("structure")
            for episode in sorted(self.thread.episodes or [], key=lambda item: item.episode_index)
            if isinstance(episode.brief_payload, dict)
        ]
        last = previous[-1] if previous else None
        if beat == "see" and len(required_cast) <= 2:
            preferred = "two_hander"
        elif beat == "act":
            preferred = "bottle"
        else:
            preferred = STRUCTURE_ROTATION[episode_index % len(STRUCTURE_ROTATION)]
        if preferred != last:
            return preferred
        for structure in STRUCTURE_ROTATION:
            if structure != last:
                return structure
        return "ensemble"

    def _mission_format_for(self, *, episode_index: int, beat: str) -> str:
        if beat != "act":
            return "chat_message"
        candidates = ["chat_message", "email_formal", "admin_form"]
        if settings.FEUILLETON_AUDIO_ENABLED:
            candidates.append("voicemail_reply")
        if settings.SERIAL_PHONE_CALL_MISSIONS_ENABLED:
            candidates.append("phone_call")
        previous = [
            str((episode.brief_payload or {}).get("mission_format") or "")
            for episode in sorted(self.thread.episodes or [], key=lambda item: item.episode_index)
            if isinstance(episode.brief_payload, dict) and episode.kind == "mission"
        ]
        last = previous[-1] if previous else None
        offset = len(previous) + max(0, episode_index - len(previous))
        preferred = candidates[offset % len(candidates)]
        if preferred != last:
            return preferred
        for candidate in candidates:
            if candidate != last:
                return candidate
        return "chat_message"

    def _last_see_choice_episode(self) -> int | None:
        for episode in sorted(self.thread.episodes or [], key=lambda item: item.episode_index, reverse=True):
            brief = episode.brief_payload if isinstance(episode.brief_payload, dict) else {}
            if brief.get("beat") == "see" and brief.get("include_choice_fork"):
                return int(brief.get("episode_index") or episode.episode_index)
        return None

    def _stakes_level(self) -> int:
        completed_missions = [episode for episode in self.thread.episodes or [] if episode.kind == "mission" and episode.status == "completed"]
        return max(1, min(3, 1 + len(completed_missions) // 2))

    def _hook_guidance(self, *, required_cast: list[str], stage: dict[str, Any] | None, next_beat_kind: str) -> str:
        pending = self.state.get("pending_register_switch")
        if isinstance(pending, dict) and pending.get("character_id") in required_cast:
            return f"{pending.get('name') or pending.get('character_id')} offers the tu; make the register switch an authored story beat."
        if stage and stage.get("tentpole"):
            return f"End on the emotional consequence of the tentpole, then seed the next {next_beat_kind} beat."
        if next_beat_kind == "mission":
            return "End with a concrete unanswered question that requires the learner's next message."
        return "End with a visual hook that asks to be seen in the next Feuilleton."

    def _b_plot(self, *, episode_index: int, structure: str, required_cast: list[str]) -> dict[str, str]:
        seeds = [
            "Margaux notices the group's rituals changing around the newcomer.",
            "Gus's La Méthode creates a practical problem no one requested.",
            "A small Paris errand turns the correct register into the actual plot.",
            "Romy's newsroom timing interrupts private honesty.",
            "Lila tries to help and accidentally reveals what she is avoiding.",
        ]
        if structure == "news_edition":
            return {"kind": "news", "seed": "Romy has to turn the week's news into a question for the group."}
        if "augustin_de_roncourt" in required_cast:
            return {"kind": "everyday", "seed": "Gus's La Méthode fails publicly at exactly the wrong scale."}
        return {"kind": "everyday", "seed": seeds[episode_index % len(seeds)]}

    def _relationships_for(self, required_cast: list[str]) -> dict[str, Any]:
        relationships = self.state.get("relationships") if isinstance(self.state.get("relationships"), dict) else {}
        return {
            character_id: relationships.get(character_id, {"closeness": 0, "register": "vous", "callbacks": []})
            for character_id in required_cast
        }
