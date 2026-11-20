"""Pilot P9 (check 2, day 1, A1): two retries of one Courrier reply were both refused —
first «Too hard to read: no subjonctif…», then «asks again a question the learner has
already answered». The second draft was told what was wrong, not how to say it instead.

The second draft's request now carries the first draft's refusal with its plain way out:
a refused tense → «aller + infinitif» or the present; a question asked again → do not
ask it again. No model is called: a fake records every request.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.services.missions as missions_module
from app.services.missions import REASK_WAY_OUT, second_draft_hint
from tests.test_courrier_held_reply import VETOED, _setup


class _Recording:
    """First draft in a futur simple (A1 refuses it), second draft fine."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_chat_completion(self, **kwargs):  # type: ignore[no-untyped-def]
        self.prompts.append(str(kwargs.get("system_prompt") or ""))
        content = VETOED if len(self.prompts) == 1 else "D'accord. Tu vas venir au café demain ?"
        return SimpleNamespace(content=content)


def test_the_second_draft_is_asked_for_aller_plus_infinitive(client: TestClient, monkeypatch) -> None:
    headers, mission_id, _old = _setup(client, monkeypatch)
    llm = _Recording()
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: llm)

    response = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Je mange une soupe avec Marin ce soir.", "mode": "chat"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    first, second = llm.prompts[0], llm.prompts[1]
    assert "Rewrite your reply" not in first
    assert "futur simple" in second, "the first refusal's reason"
    assert "aller + infinitif" in second and "the present" in second, "and its plain way out"


def test_the_hint_names_the_way_out_for_each_refusal() -> None:
    tense = second_draft_hint(["Too hard to read: no futur simple."], tenses=["futur simple"])
    assert "Too hard to read: no futur simple." in tense
    assert "«aller + infinitif»" in tense
    subj = second_draft_hint(["Too hard to read: no subjonctif."], tenses=["subjonctif"])
    assert "the present or an infinitive" in subj
    reask = second_draft_hint(
        ["The reply asks again a question the learner has already answered («À quelle heure on se retrouve ?»)."],
        codes=["reply_reasks_answered_question"],
    )
    assert "À quelle heure on se retrouve ?" in reask and REASK_WAY_OUT in reask
    assert REASK_WAY_OUT not in tense and "aller + infinitif" not in reask
