"""Package V stage 1: the deploy moves no level, no gold and no token.

The verdict stack asks of each stored row whether it ``counts`` (#333). Main never asked:
every stored attempt fed the level average, a finished letter paid its gold on the stored
word («partial»), and its logo token whatever its gaps. A row main stored after a model
failure (the rules lowered it to «partial», ``fallback_used``) does not count under the
stack, so reading old rows the new way would re-judge history on deploy.

Here the same Courrier letter is stored the way main's code stored it, then finished and
read three ways:

* ``main``: this branch with the four stack reads put back as main had them (no ``counts``
  filter on the level scores, no unread or unanswered message holding back the token, gold
  on the stored word). That is main's arithmetic, read through this branch's routes.
* ``as_counted``: the branch as it ships, the rows older than the cut-over row.
* ``rejudge``: ``VERDICT_LEGACY_ROWS=rejudge``, what the stack alone would do.

``as_counted`` must equal ``main``. ``rejudge`` must not: it shows the test sees a move.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select

import app.services.cefr_progress as cefr_module
import app.services.gold_ledger as gold_module
import app.services.missions as missions_module
from app.config import settings
from app.db.models.gold import GoldLedgerEntry
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt, RealWorldMissionTurn
from app.db.models.user import User
from app.db.models.verdict_cutover import VerdictCutover
from app.services import verdict_cutover
from app.services.atelier_rewards import AtelierRewardService
from app.services.cefr_progress import CEFRProgressService
from app.services.news_service import NewsService
from tests.test_missions import _fake_france_context, _token

#: What main stored after the corrector failed and the rules found a slip (WP-74, before #333).
RULES_ONLY_PARTIAL = {
    "verdict": "partial",
    "score_0_4": 3,
    "corrected_answer": "Je cherche le colis depuis hier.",
    "correction_debug": {"fallback_used": True},
    "errata": [
        {"learner_text": "la colis", "corrected_target": "le colis", "why_wrong": "«colis» est masculin.", "severity": 1}
    ],
}
#: A message the model read: it counts both before and after the stack.
MODEL_READ = {"verdict": "accepted", "score_0_4": 4, "corrected_answer": "", "errata": [], "correction_debug": {}}


@pytest.fixture(autouse=True)
def gold_on(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "shadow")


@pytest.fixture()
def tokens(monkeypatch):
    minted: list = []
    monkeypatch.setattr(
        AtelierRewardService, "mint_logo_token_for_mission", lambda self, mission: minted.append(mission.id) or []
    )
    return minted


def _as_main_read_them(monkeypatch) -> None:
    """Main's four reads: every stored row counts, no stored message holds a letter back."""

    monkeypatch.setattr(settings, "VERDICT_LEDGER_ENABLED", False)  # main had no ledger (package V stage 2)
    counted = SimpleNamespace(counts=True)
    monkeypatch.setattr(
        cefr_module,
        "verdicts",
        SimpleNamespace(from_forge=lambda *a, **k: counted, from_courrier=lambda *a, **k: counted,
                        from_feuilleton=lambda *a, **k: counted),
    )
    monkeypatch.setattr(gold_module, "verdicts", SimpleNamespace(from_courrier=lambda *a, **k: counted))
    monkeypatch.setattr(missions_module, "unchecked_messages", lambda *a, **k: [])
    monkeypatch.setattr(missions_module, "unanswered_user_turns", lambda *a, **k: [])


def _letter_stored_by_main(client, db, monkeypatch) -> tuple[dict[str, str], str, User]:
    """A letter written before the deploy: one rules-only attempt, a read turn, an unanswered one."""

    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    headers = {"Authorization": f"Bearer {_token(client)}"}
    created = client.post(
        "/api/v1/missions/", json={"mission_type": "message", "cadence": "ad_hoc", "use_news": False}, headers=headers
    )
    assert created.status_code == 200, created.text
    mission_id = created.json()["mission"]["id"]
    mission = db.get(RealWorldMission, UUID(mission_id))
    user = db.get(User, mission.user_id)
    before = datetime.now(UTC) - timedelta(days=2)
    db.add(
        RealWorldMissionAttempt(
            mission_id=mission.id, user_id=user.id, mode="writing", verdict="partial", score_0_4=3,
            answer_payload={"text": "Je cherche la colis depuis hier."}, correction_payload=RULES_ONLY_PARTIAL,
            created_at=before,
        )
    )
    rows = [
        ("user", "Bonjour Camille, je cherche la colis.", RULES_ONLY_PARTIAL),
        ("assistant", "Ah d'accord ! Donnez-moi le numéro.", None),
        ("user", "Le numéro est 12345.", MODEL_READ),  # main stored no stock reply (#397): unanswered
    ]
    for index, (role, text, correction) in enumerate(rows):
        db.add(
            RealWorldMissionTurn(
                mission_id=mission.id, user_id=user.id, turn_index=index, role=role, mode="chat", text=text,
                correction_payload=correction, created_at=before + timedelta(minutes=index),
            )
        )
    db.commit()
    return headers, mission_id, user


def _deploy(db, *, at: datetime | None = None) -> None:
    db.add(VerdictCutover(id=1, at=at or datetime.now(UTC) - timedelta(hours=1), note="test deploy"))
    db.commit()


def _what_the_learner_has(client, db, headers, mission_id, user, tokens) -> dict:
    scores = sorted(
        CEFRProgressService(db)._recent_scores(user=user, start=datetime.now(UTC) - timedelta(days=14))
    )
    response = client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers)
    assert response.status_code == 200, response.text
    recap = response.json()["recap"]
    db.expire_all()
    gold = sum(
        int(entry.amount or 0)
        for entry in db.scalars(select(GoldLedgerEntry).where(GoldLedgerEntry.user_id == user.id))
    )
    return {
        "level_scores": scores,
        "gold": gold,
        "token": UUID(mission_id) in tokens,
        "outcome": recap.get("courrier_outcome"),
    }


def _read(client, db, monkeypatch, tokens, mode: str) -> dict:
    with monkeypatch.context() as patch:
        headers, mission_id, user = _letter_stored_by_main(client, db, patch)
        if mode == "main":
            _as_main_read_them(patch)
        else:
            if db.get(VerdictCutover, 1) is None:
                _deploy(db)
            patch.setattr(settings, "VERDICT_LEGACY_ROWS", mode)
        return _what_the_learner_has(client, db, headers, mission_id, user, tokens)


def test_rows_stored_by_main_keep_what_they_counted_for(client, db_session, monkeypatch, tokens):
    main = _read(client, db_session, monkeypatch, tokens, "main")
    shipped = _read(client, db_session, monkeypatch, tokens, "as_counted")
    rejudged = _read(client, db_session, monkeypatch, tokens, "rejudge")

    # Main's arithmetic: the rules-only «partial» fed the level, and the letter paid gold and a token.
    assert main["level_scores"] == [3.0] and main["token"] is True and main["gold"] > 0, main
    assert shipped == main, f"the deploy moved something: main {main}, branch {shipped}"
    # The stack alone would have moved all three: the test sees a move when there is one.
    assert rejudged["level_scores"] == [] and rejudged["token"] is False and rejudged["gold"] == 0, rejudged


def test_legacy_rows_are_only_rows_older_than_the_cutover(monkeypatch):
    at = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
    cut = verdict_cutover.Cutover(at, verdict_cutover.AS_COUNTED)
    assert cut.keeps(SimpleNamespace(created_at=at - timedelta(seconds=1)))
    assert cut.keeps(SimpleNamespace(created_at=(at - timedelta(days=1)).replace(tzinfo=None)))  # naive = UTC
    assert not cut.keeps(SimpleNamespace(created_at=at))
    assert not cut.keeps(SimpleNamespace(created_at=None))
    assert not verdict_cutover.Cutover(None, verdict_cutover.AS_COUNTED).keeps(SimpleNamespace(created_at=at))
    assert not verdict_cutover.Cutover(at, verdict_cutover.REJUDGE).keeps(SimpleNamespace(created_at=at - timedelta(days=1)))


def test_a_database_without_a_cutover_row_has_no_legacy_rows(db_session):
    assert verdict_cutover.cutover(db_session).at is None


def test_the_level_report_says_what_a_rejudge_would_move_and_writes_nothing(client, db_session, monkeypatch):
    """scripts/verdict_level_report.py: per learner, the old rows a re-judge would stop counting."""

    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "verdict_level_report", Path(__file__).resolve().parents[1] / "scripts" / "verdict_level_report.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    _headers, mission_id, user = _letter_stored_by_main(client, db_session, monkeypatch)
    mission = db_session.get(RealWorldMission, UUID(mission_id))
    mission.status = "completed"
    db_session.commit()
    assert module.report(db_session) == [], "no cut-over row: nothing is old yet"
    _deploy(db_session)
    db_session.expire_all()

    [learner] = module.report(db_session, user_ids={user.id})
    assert learner["level"]["courrier"] == {"rows": 1, "rejudged_not_counting": 1}
    assert learner["attempts_14d"] == {"as_counted": 1, "rejudged": 0}
    assert learner["letters"]["held_back"] == 1
    assert not db_session.new and not db_session.dirty
