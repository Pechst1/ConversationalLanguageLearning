"""QA-FORGE (2026-10-03) — one Forge séance walked as a German A1 learner.

The owner (German, A1) found La Forge confusing: an English judgement label
(«Correct») next to a French one, a drop zone «Hierhin», and a repair whose
instruction quoted an English meaning («…, sodass er sagt: „You are at the NGO
office, Gus.“»). This walk starts a séance on the être rule through the API,
answers every item (alternately wrong and right), and reads every payload the
learner sees: no English ever reaches a German learner.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models.grammar import GrammarConcept
from app.services.atelier import AtelierScheduler

#: Words that only an English sentence has (a German or French cue never does).
#: FORGE-DE: «was» left the list — German cues now quote German («Was für ein Glück!»).
ENGLISH = re.compile(
    r"\b(?:the|you|is|are|were|sentence|correct it|which|says|build|say in french|reply|"
    r"please|would|like|with|this|that|have|has|at the|in the)\b",
    re.IGNORECASE,
)
#: FORGE-DE: the units whose form is chosen by meaning (``gloss``): an item is
#: ambiguous without its meaning, so a German learner must read it in German.
MEANING_UNITS = (
    "FR2_A11_QUESTION_WORDS", "FR2_A11_NUMBERS", "FR2_A12_NUMBERS_BIG", "FR2_A12_TIME",
    "FR2_A12_DAYS_DATES", "FR2_A12_PLACE_PREPOSITIONS", "FR2_A12_CONNECTORS", "FR2_A21_COMPARATIVE",
    "FR2_A21_TIME_PREPOSITIONS", "FR2_A21_CAUSE_CONSEQUENCE", "FR2_A22_ADVICE_CONDITIONAL",
)
#: The keys whose text is chrome or a cue (French sentences live elsewhere).
CUE_KEYS = ("goal_native", "instruction", "meaning_cue", "judge_question")


def _register(client: TestClient, native: str) -> dict[str, str]:
    email = f"{uuid4()}@example.com"
    password = "atelier-secure"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": native},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _item(data: dict[str, Any], nxt: dict[str, Any]) -> dict[str, Any]:
    if isinstance(nxt.get("item"), dict):
        return nxt["item"]
    payload = next(s for s in data["exercise_sets"] if s["concept_id"] == nxt["concept_id"])["payload"]
    if nxt["round"] == "recognize":
        items = payload["recognize"][nxt["mode"]]["items"]
    elif nxt["round"] == "transform":
        items = payload["transform"]["items"]
    else:
        items = payload["output_ladder"][nxt["round"]]["items"]
    return items[nxt["item_index"]]


def _answer(item: dict[str, Any], nxt: dict[str, Any], right: bool) -> dict[str, Any]:
    round_name, mode = nxt["round"], nxt["mode"]
    if round_name == "recognize":
        if mode == "word_bank":
            return {"answers": {item["id"]: list(item.get("answer_tokens") or []) if right else ["zzz"]}}
        if item.get("classify_kind") == "judgement":
            # Always the right judgement on a wrong sentence: that opens the repair.
            return {"answers": {item["id"]: item.get("correct_label")}}
        return {"answers": {item["id"]: (item.get("correct_answer") or item.get("correct_label")) if right else "zzz"}}
    if round_name == "transform":
        return {"answers": {item["id"]: item.get("expected_answer") if right else "zzz"}}
    return {"text": str(item.get("example_answer") or "") if right else "zzz"}


def _walk(client: TestClient, db_session, native: str, external_id: str = "FR_A1_VERB_001") -> list[dict[str, Any]]:
    headers = _register(client, native)
    AtelierScheduler(db_session).ensure_catalog()
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one()
    started = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": concept.id})
    assert started.status_code == 201, started.text
    data = started.json()
    forge = data["forge"]
    screens: list[dict[str, Any]] = []
    nxt = forge["next"]
    for index in range(30):
        if nxt is None:
            break
        item = _item(data, nxt)
        response = client.post(
            f"/api/v1/atelier/sessions/{data['session_id']}/attempts",
            headers=headers,
            json={
                "concept_id": nxt["concept_id"],
                "round": nxt["round"],
                "mode": "rewrite" if nxt["round"] == "transform" else nxt["mode"],
                "exercise_id": f"forge:{nxt['concept_id']}:{nxt['round']}:{nxt['item_id']}",
                "answer_payload": _answer(item, nxt, right=index % 4 != 0),
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        screens.append({"next": {k: nxt.get(k) for k in ("round", "mode", "rung")}, "item": item, "correction": body.get("correction")})
        nxt = body["forge"]["next"]
    out = os.environ.get("FORGE_QA_WALK_OUT")
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(screens, handle, ensure_ascii=False, indent=1)
    return screens


def _cue_texts(screen: dict[str, Any]) -> list[str]:
    item = screen["item"]
    texts = [str(item.get(key) or "") for key in CUE_KEYS]
    if isinstance(item.get("prompt_l10n"), dict):
        texts.append(str(item["prompt_l10n"].get("de") or ""))
    if isinstance(item.get("instruction_l10n"), dict):
        texts.append(str(item["instruction_l10n"].get("de") or ""))
    follow = ((screen.get("correction") or {}).get("forge") or {}).get("follow_up") or (screen.get("correction") or {}).get("follow_up")
    if isinstance(follow, dict):
        texts.append(str(follow.get("goal_native") or ""))
    texts.extend(str(note) for note in (screen.get("correction") or {}).get("notes_native") or [])
    for erratum in (screen.get("correction") or {}).get("errata") or []:
        texts.extend(str(erratum.get(key) or "") for key in ("why_wrong", "repair_hint", "display_label"))
    return [text for text in texts if text]


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [text for value in node.values() for text in _strings(value)]
    if isinstance(node, list):
        return [text for value in node for text in _strings(value)]
    return []


def test_a_german_a1_learner_never_sees_english_in_a_forge_seance(client: TestClient, db_session) -> None:
    screens = _walk(client, db_session, "de")
    assert len(screens) >= 6
    leaks = [(screen["next"], text) for screen in screens for text in _cue_texts(screen) if ENGLISH.search(text)]
    assert leaks == [], leaks
    # Not only the cues: no string of a served item is English.
    served = [(screen["next"], text) for screen in screens for text in _strings(screen["item"]) if " " in text and ENGLISH.search(text)]
    assert served == [], served
    judgements = [screen["item"] for screen in screens if screen["item"].get("classify_kind") == "judgement"]
    for item in judgements:
        # The two answers keep their keys; the learner reads them in German.
        assert item.get("label_l10n", {}).get("de"), item
        assert set(item["label_l10n"]["de"].values()) == {"Stimmt so", "Muss korrigiert werden"}
        assert item["goal_native"] == "Ist der Satz richtig?"


def test_the_meaning_dependent_units_are_marked_gloss():
    from app.services import item_bank as ib

    glossed = {unit for unit, spec in ib.unit_templates().items() if spec.get("gloss")}
    assert glossed == set(MEANING_UNITS)


def test_a_german_walk_on_a_meaning_unit_reads_the_meaning_in_german(client: TestClient, db_session) -> None:
    """FORGE-DE: depuis / pendant / il y a is chosen by meaning — the German learner
    reads that meaning in German on every drill that needs it, never in English."""

    screens = _walk(client, db_session, "de", "FR_A2_PREP_001")
    assert len(screens) >= 6
    leaks = [(screen["next"], text) for screen in screens for text in _cue_texts(screen) if ENGLISH.search(text)]
    assert leaks == [], leaks
    served = [(screen["next"], text) for screen in screens for text in _strings(screen["item"]) if " " in text and ENGLISH.search(text)]
    assert served == [], served
    quoted = [screen for screen in screens if "„" in str(screen["item"].get("goal_native") or "")]
    # fill, build, repair, pick and the translate steps quote the German meaning
    assert len(quoted) >= 4, [screen["item"].get("goal_native") for screen in screens]
    builds = [screen["item"] for screen in screens if "answer_tokens" in screen["item"]]
    for item in builds:
        assert item.get("meaning_cue") and not ENGLISH.search(item["meaning_cue"]), item


@pytest.mark.parametrize("unit", MEANING_UNITS)
def test_every_meaning_unit_serves_a_german_meaning_with_no_english(unit: str) -> None:
    from app.services import item_bank as ib
    bank = ib.default_bank()
    items = bank.generate(unit, 24, seed=f"forge-de-walk:{unit}", detector=ib.unit_detector(unit))
    assert len(items) == 24
    assert sum(1 for item in items if item.de) >= 23, [item.sentence for item in items if not item.de]
    for index, item in enumerate(items):
        if not item.de:
            continue
        assert ib.german_problems(item) == [], (item.sentence, item.de)
        rung = ib.RUNG_TYPES[index % len(ib.RUNG_TYPES)]
        payload = ib.rung_item(rung, item, index=index)
        if payload is None:
            continue
        served = ib.public_item(payload, "de")
        texts = [text for text in _strings(served) if " " in text and text != item.sentence and not text.startswith(item.prefix or "\0")]
        assert not [text for text in texts if ENGLISH.search(text)], (rung, texts)
        cue = " ".join(str(served.get(key) or "") for key in ("goal_native", "meaning_cue", "prompt", "instruction"))
        if rung in {"fill", "word_bank", "transform", "pair", "production"}:
            assert item.de in cue, (rung, cue)
        # French learners keep the gloss-free cue: no English, no German.
        french = ib.public_item(payload, "fr")
        shown = " ".join(str(french.get(key) or "") for key in ("goal_native", "meaning_cue", "prompt", "instruction", "meaning"))
        assert item.de not in shown and item.en not in shown, (rung, shown)
