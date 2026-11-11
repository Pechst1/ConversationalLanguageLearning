"""``STORY_SCENE_RECORD``: the one switch for the story-truth work (#145, #147).

With it on, a scene keeps a record of what each learner turn did (``scene_ledger``),
the reply lanes are written from it, the reply check vetoes a reply that goes against
it, and the day contract reads «answered» from it. With it off, everything runs as it
did before the stack landed. Every place that changes behaviour asks :func:`enabled`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, model_serializer

from app.config import settings


def enabled() -> bool:
    return bool(getattr(settings, "STORY_SCENE_RECORD", False))



#: The output fields the stack added to the models a story call is answered in, by the
#: model's name (a nested model is matched in ``$defs`` by its title). With the flag off
#: the model is sent the schema without them, exactly what it was sent before; the answer
#: still parses into the full class, where they keep their defaults.
STACK_FIELDS: dict[str, frozenset[str]] = {
    "ReplyChoice": frozenset({"learner_intent", "listen_fr"}),
    "VoiceReply": frozenset({"learner_intent", "learned"}),
    "StoryTurn": frozenset({"tomorrow_question_fr"}),
    "SemanticTurn": frozenset({"tomorrow_question_fr"}),
    "SceneDraft": frozenset({"scene_cast"}),
    "Panel": frozenset({"location_id", "time_jump"}),
}


def _strip(node: dict[str, Any]) -> None:
    dropped = STACK_FIELDS.get(str(node.get("title") or ""))
    if not dropped or not isinstance(node.get("properties"), dict):
        return
    node["properties"] = {key: value for key, value in node["properties"].items() if key not in dropped}
    if isinstance(node.get("required"), list):
        node["required"] = [key for key in node["required"] if key not in dropped]


def json_schema(model: type) -> dict[str, Any]:
    """The JSON schema a story call sends for ``model``: the stack's fields only with the
    flag on (:data:`STACK_FIELDS`)."""

    schema = model.model_json_schema()
    if enabled():
        return schema
    _strip(schema)
    defs = schema.get("$defs") or {}
    for node in defs.values():
        if isinstance(node, dict):
            _strip(node)
    if defs:
        # A model only a dropped field used (``LearnerFact`` under ``learned``) goes too.
        used: set[str] = set()
        todo = [{key: value for key, value in schema.items() if key != "$defs"}]
        while todo:
            text = json.dumps(todo.pop())
            for name in re.findall(r'"#/\$defs/([^"]+)"', text):
                if name not in used and name in defs:
                    used.add(name)
                    todo.append(defs[name])
        schema["$defs"] = {name: node for name, node in defs.items() if name in used}
        if not schema["$defs"]:
            schema.pop("$defs")
    return schema


def main_dump(model: Any, handler: Any) -> Any:
    """A model's dump without the stack's fields when the flag is off, so what is stored,
    shown or sent on to the next model is what main stored, showed and sent. Wired as each
    model's ``model_serializer(mode="wrap")``."""

    data = handler(model)
    if enabled() or not isinstance(data, dict):
        return data
    dropped = STACK_FIELDS.get(type(model).__name__)
    if not dropped:
        return data
    return {key: value for key, value in data.items() if key not in dropped}


class MainDump(BaseModel):
    """Mixed into a story model the stack added fields to (:data:`STACK_FIELDS`): with the
    flag off its dump is main's (:func:`main_dump`)."""

    @model_serializer(mode="wrap")
    def _scene_record_dump(self, handler: Any) -> Any:
        return main_dump(self, handler)
