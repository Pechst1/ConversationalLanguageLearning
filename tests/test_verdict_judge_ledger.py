"""Package V stage 2: one judge, one ledger.

* Every ``app.core.verdict.Verdict`` is built by :func:`app.services.judge.judge`. The
  surfaces' stored-row readers (``app/services/verdicts.py``) hand it a reading; they no
  longer build a verdict themselves, so a change to a reader cannot silently re-judge.
* What was decided is stored: ``verdict_records``, append-only, one live record per
  subject, a later check superseding the earlier one.
* After the ledger cut-over, levels, gold and tokens read the record, not the row.
* A record pays what it is due exactly once along its chain.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
#: The only modules that may build a verdict: the shape itself and the judge.
BUILDERS = {APP / "core" / "verdict.py", APP / "services" / "judge.py"}


def _verdict_builds(path: Path) -> list[str]:
    """Calls of ``make_verdict`` or of the core ``Verdict`` class in one module."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.core.verdict":
            imported |= {alias.asname or alias.name for alias in node.names if alias.name in {"Verdict", "make_verdict"}}
        if isinstance(node, ast.ImportFrom) and node.module == "app.core":
            modules |= {alias.asname or alias.name for alias in node.names if alias.name == "verdict"}
        if isinstance(node, ast.Import):
            modules |= {alias.asname or alias.name for alias in node.names if alias.name == "app.core.verdict"}
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in imported:
            found.append(f"{path.relative_to(APP.parent)}:{node.lineno} {func.id}(")
        elif isinstance(func, ast.Attribute) and func.attr in {"Verdict", "make_verdict"}:
            base = func.value
            if isinstance(base, ast.Name) and base.id in modules or ast.unparse(base) == "app.core.verdict":
                found.append(f"{path.relative_to(APP.parent)}:{node.lineno} {ast.unparse(func)}(")
    return found


def test_no_verdict_is_built_outside_the_judge():
    builds = [hit for path in sorted(APP.rglob("*.py")) if path not in BUILDERS for hit in _verdict_builds(path)]
    assert builds == [], "a verdict built outside judge():\n" + "\n".join(builds)


def test_the_guard_sees_a_build():
    sample = APP.parent / "tests" / "verdict_corpus" / "_guard_sample.py"
    sample.write_text("from app.core.verdict import make_verdict\nmake_verdict(outcome=1)\n", encoding="utf-8")
    try:
        assert len(_verdict_builds(sample)) == 1
    finally:
        sample.unlink()


# --- the judge ---------------------------------------------------------------------------------

import re  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.verdict import Call, CheckedBy, Failure, Outcome  # noqa: E402
from app.db.models.gold import GoldLedgerEntry  # noqa: E402
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt  # noqa: E402
from app.db.models.verdict_cutover import VerdictCutover  # noqa: E402
from app.db.models.verdict_record import VerdictRecord  # noqa: E402
from app.services import gold_ledger, verdict_ledger, verdicts  # noqa: E402
from app.services.cefr_progress import CEFRProgressService  # noqa: E402
from app.services.judge import Reading, Task, judge, judge_version, settled_by  # noqa: E402

TEXT = "Je cherche la colis depuis hier."
SLIP = {"span": "la colis", "replacement": "le colis", "note": "«colis» est masculin.", "by": "model"}
MODEL_PARTLY = Reading(outcome=Outcome.PARTLY, by=CheckedBy.MODEL, call=Call.OK, proposed=(SLIP,))
MODEL_RIGHT = Reading(outcome=Outcome.RIGHT, by=CheckedBy.MODEL, call=Call.OK)
FAILED = Reading(
    outcome=Outcome.NOT_CHECKED, by=CheckedBy.NONE, call=Call.FAILED, failure=Failure.TIMEOUT, retryable=True,
    proposed=({**SLIP, "by": "rules"},),
)


def test_the_key_settles_before_any_reading():
    verdict = judge(Task("drill", accepted=("le colis",)), "Le colis", reading=FAILED)
    assert (verdict.outcome, verdict.checked_by, verdict.counts) == (Outcome.RIGHT, CheckedBy.KEY, True)
    assert settled_by(Task("drill", accepted=("le colis",)), "le colis", None) == "key"


def test_rules_add_edits_never_a_verdict():
    verdict = judge(Task("courrier"), TEXT, reading=FAILED)
    assert (verdict.outcome, verdict.checked_by, verdict.counts) == (Outcome.NOT_CHECKED, CheckedBy.RULES, False)
    assert verdict.corrected == "Je cherche le colis depuis hier."


def test_the_variant_gate_drops_an_edit_between_two_right_spellings():
    reading = Reading(
        outcome=Outcome.PARTLY, by=CheckedBy.MODEL, call=Call.OK,
        proposed=({"span": "ognon", "replacement": "oignon", "by": "model"}, SLIP),
    )
    verdict = judge(Task("courrier"), "J'achète un ognon et la colis.", reading=reading)
    assert [edit.replacement for edit in verdict.edits] == ["le colis"]


def test_the_judge_version_names_the_rules_and_the_models(monkeypatch):
    version = judge_version()
    assert re.fullmatch(r"[0-9a-f]{16}", version)
    judge_version.cache_clear()
    monkeypatch.setattr(settings, "ATELIER_CORRECTION_LLM_MODEL", "another-model")
    try:
        assert judge_version() != version
    finally:
        judge_version.cache_clear()


def test_a_reading_survives_the_round_trip_through_a_record():
    assert Reading.from_dict(FAILED.to_dict()) == FAILED


# --- the ledger: pay once ----------------------------------------------------------------------


@pytest.fixture()
def gold_on(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "shadow")


def _supersede(db, user, reading, payer):
    return verdict_ledger.supersede(
        db, user_id=user.id, surface="courrier", subject_type="courrier_attempt", subject_id="letter-1",
        answer=TEXT, reading=reading, payer=payer,
    )


def _standing_gold(db, user) -> list[GoldLedgerEntry]:
    db.flush()
    return [
        entry
        for entry in db.scalars(select(GoldLedgerEntry).where(GoldLedgerEntry.user_id == user.id))
        if entry.state != "void"
    ]


def test_superseding_a_record_twice_pays_its_gold_once(db_session, gold_on):
    from tests.test_atelier import _user

    user = _user(db_session)

    def payer(key):
        return gold_ledger.pay_verdict(db_session, user=user, source_key=key)

    unread = _supersede(db_session, user, FAILED, payer)  # the corrector timed out
    assert unread.counts is False and _standing_gold(db_session, user) == []

    read = _supersede(db_session, user, MODEL_PARTLY, payer)  # «Check again»: read, it counts
    paid = _standing_gold(db_session, user)
    assert read.supersedes_id == unread.id and len(paid) == 1 and paid[0].amount > 0
    assert read.paid["gold"] == paid[0].amount

    reread = _supersede(db_session, user, MODEL_RIGHT, payer)  # a second check, a better verdict
    assert reread.supersedes_id == read.id
    assert _standing_gold(db_session, user) == paid, "a superseding record paid the same answer twice"
    assert reread.paid["gold"] == 0

    assert _supersede(db_session, user, MODEL_RIGHT, payer) is None, "the same verdict is not recorded again"
    live = verdict_ledger.live_record(db_session, "courrier_attempt", "letter-1")
    assert live.id == reread.id
    chain = db_session.scalars(select(VerdictRecord).where(VerdictRecord.subject_id == "letter-1")).all()
    assert len(chain) == 3 and sum(1 for record in chain if record.superseded_by_id is None) == 1


def test_a_record_that_stops_counting_takes_its_gold_back_and_a_later_one_pays_once_more(db_session, gold_on):
    from tests.test_atelier import _user

    user = _user(db_session)

    def payer(key):
        return gold_ledger.pay_verdict(db_session, user=user, source_key=key)

    _supersede(db_session, user, MODEL_PARTLY, payer)
    [first] = _standing_gold(db_session, user)
    revoked = _supersede(db_session, user, FAILED, payer)
    assert _standing_gold(db_session, user) == [] and revoked.paid["gold"] == -first.amount
    _supersede(db_session, user, MODEL_RIGHT, payer)
    again = _standing_gold(db_session, user)
    assert len(again) == 1 and again[0].source_key != first.source_key


# --- the ledger: written on every flush, read after the cut-over -------------------------------


def _letter(db, user) -> RealWorldMission:
    mission = RealWorldMission(
        user_id=user.id, status="in_progress", cadence="ad_hoc", mission_type="message", title="Lettre",
        brief="Réponds.", selected_concept_ids=[], target_errata_ids=[], target_vocabulary_ids=[],
        source_snapshot={}, objectives=[], prompt_payload={}, recap_payload={},
    )
    db.add(mission)
    db.commit()
    return mission


UNREAD_PAYLOAD = {"verdict": "unassessed", "score_0_4": 0, "correction_debug": {"fallback_used": True, "failure": "timeout"}}
READ_PAYLOAD = {"verdict": "partial", "score_0_4": 3, "errata": [], "correction_debug": {"model": "m"}}


def _records(db, attempt) -> list[VerdictRecord]:
    return list(
        db.scalars(
            select(VerdictRecord)
            .where(VerdictRecord.subject_type == "courrier_attempt", VerdictRecord.subject_id == str(attempt.id))
            .order_by(VerdictRecord.created_at)
        )
    )


def test_every_stored_answer_is_recorded_and_a_recheck_supersedes_it(db_session):
    from tests.test_atelier import _user

    user = _user(db_session)
    mission = _letter(db_session, user)
    attempt = RealWorldMissionAttempt(
        mission_id=mission.id, user_id=user.id, mode="writing", verdict="unassessed", score_0_4=0.0,
        answer_payload={"text": TEXT}, correction_payload=UNREAD_PAYLOAD,
    )
    db_session.add(attempt)
    db_session.commit()
    [unread] = _records(db_session, attempt)
    assert unread.counts is False and unread.verdict["shown"]["outcome"] == "not_checked"
    assert unread.judge_version == judge_version() and unread.answer_text == TEXT
    assert unread.verdict["reading"]["call"] == "failed"

    attempt.answer_payload = {"text": TEXT, "note": "seen"}  # a change the verdict does not read
    db_session.commit()
    assert len(_records(db_session, attempt)) == 1

    attempt.correction_payload, attempt.verdict, attempt.score_0_4 = READ_PAYLOAD, "partial", 3.0  # «Check again»
    db_session.commit()
    unread_again, read = _records(db_session, attempt)
    assert read.supersedes_id == unread.id and unread_again.superseded_by_id == read.id
    assert read.counts is True


def _deploy_ledger(db) -> None:
    before = datetime.now(UTC) - timedelta(days=30)
    db.add(VerdictCutover(id=1, at=before, note="stage 1"))
    db.add(VerdictCutover(id=2, at=before + timedelta(days=1), note="ledger"))
    db.commit()


def test_after_the_cutover_a_level_reads_the_record_not_todays_judge(db_session, monkeypatch):
    """A judge change (here: the Courrier reader now calls every read «not checked») moves nothing."""

    from tests.test_atelier import _user

    _deploy_ledger(db_session)
    user = _user(db_session)
    mission = _letter(db_session, user)
    attempt = RealWorldMissionAttempt(
        mission_id=mission.id, user_id=user.id, mode="writing", verdict="partial", score_0_4=3.0,
        answer_payload={"text": TEXT}, correction_payload=READ_PAYLOAD,
    )
    db_session.add(attempt)
    db_session.commit()

    def scores():
        return CEFRProgressService(db_session)._recent_scores(user=user, start=datetime.now(UTC) - timedelta(days=1))

    assert scores() == [3.0]
    monkeypatch.setattr(
        verdicts, "read_courrier",
        lambda *_a, **_k: verdicts.Read(Reading(outcome=Outcome.NOT_CHECKED, call=Call.FAILED), TEXT),
    )
    assert scores() == [3.0], "a judge change re-judged a recorded answer"
    counting = verdict_ledger.counting(db_session, [attempt])
    assert counting.counts(attempt) is True


def test_a_row_after_the_cutover_with_no_record_is_judged_and_named(db_session, monkeypatch):
    from loguru import logger

    from tests.test_atelier import _user

    _deploy_ledger(db_session)
    user = _user(db_session)
    mission = _letter(db_session, user)
    monkeypatch.setattr(settings, "VERDICT_LEDGER_ENABLED", False)
    attempt = RealWorldMissionAttempt(
        mission_id=mission.id, user_id=user.id, mode="writing", verdict="partial", score_0_4=3.0,
        answer_payload={"text": TEXT}, correction_payload=READ_PAYLOAD,
    )
    db_session.add(attempt)
    db_session.commit()
    monkeypatch.setattr(settings, "VERDICT_LEDGER_ENABLED", True)
    assert _records(db_session, attempt) == []

    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    try:
        assert verdict_ledger.counting(db_session, [attempt]).counts(attempt) is True
    finally:
        logger.remove(sink)
    assert any("verdict_ledger_missing" in line for line in seen)
