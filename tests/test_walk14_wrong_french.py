"""Walk 14 (two-week real-model walk, 21 Nov 2026): wrong French taught, wrong answers
credited, a right answer refused, an item back against its own schedule.

Each case uses the walk's exact strings; the rows are those stored in the walk databases.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.fault_quality import drillable_errors, learner_own_fault

# ---------------------------------------------------------------------------
# A. «je vends» «corrected» to «je vende» (B, days 3–13)
# ---------------------------------------------------------------------------


def _row(original: str, correction: str, *, source_type: str = "mission") -> SimpleNamespace:
    return SimpleNamespace(
        original_text=original,
        correction=correction,
        source_type=source_type,
        source_attempt_id=None,
        error_metadata={},
    )


def test_a_letter_s_subjunctive_fix_without_its_clause_is_not_a_review_item() -> None:
    # The Courrier's correction was right in «il faut que je vends …»; stored bare,
    # it «corrects» right French into wrong French.
    assert not learner_own_fault(wrong="je vends", correct="je vende")
    # The learner's answer to that card became a second fault: same verdict.
    assert not learner_own_fault(wrong="je avais vendu", correct="je vende")
    rows = [_row("je vends", "je vende"), _row("je avais vendu", "je vende", source_type="atelier")]
    assert drillable_errors(None, rows) == []


def test_the_same_fix_inside_its_clause_stays() -> None:
    assert learner_own_fault(wrong="il faut que je vends", correct="il faut que je vende")
    assert learner_own_fault(
        wrong="je vends",
        correct="je vende",
        submitted="Il faut que je vends son appartement.",
        item=None,
    )
    # A fix that changes no tense is untouched by the check.
    assert learner_own_fault(wrong="un valise", correct="une valise")


def test_due_error_records_never_hands_out_the_bare_subjunctive(db_session) -> None:
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from app.db.models.error import UserError
    from app.db.models.user import User
    from app.services.error_memory import ErrorMemoryService

    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="x", target_language="fr", native_language="en")
    db_session.add(user)
    db_session.flush()
    past = datetime.now(UTC) - timedelta(days=1)
    bad = UserError(
        id=uuid4(), user_id=user.id, error_category="grammar", original_text="je vends", correction="je vende",
        occurrences=1, state="repairing", next_review_date=past, source_type="mission",
    )
    good = UserError(
        id=uuid4(), user_id=user.id, error_category="grammar", original_text="un valise", correction="une valise",
        occurrences=1, state="repairing", next_review_date=past, source_type="atelier",
    )
    db_session.add_all([bad, good])
    db_session.flush()
    ids = {row.id for row in ErrorMemoryService(db_session).due_error_records(user)}
    assert good.id in ids
    assert bad.id not in ids
