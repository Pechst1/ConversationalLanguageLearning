"""A UUID whose hex looks numeric must survive a SQLite round trip.

SQLite gives a column declared ``UUID`` NUMERIC affinity, so a hex string made of
digits (or digits with one ``e``) was stored as a number and read back as a float —
the long-horizon harness mints tens of thousands of ids and hit one every few runs
(«'float' object has no attribute 'replace'», or a user id that no longer matched
its token). Production is PostgreSQL; this pins the test engine.
"""

from __future__ import annotations

import uuid

from app.db.models.user import User


def test_numeric_looking_uuids_round_trip(db_session) -> None:
    ids = [
        uuid.UUID("12345678-1234-1234-1234-123456789012"),  # all digits → INTEGER affinity
        uuid.UUID("12345678-1234-1234-1234-12345678e012"),  # one «e» → REAL affinity
    ]
    for index, user_id in enumerate(ids):
        db_session.add(User(id=user_id, email=f"uuid-affinity-{index}-{uuid.uuid4().hex[:6]}@example.com", hashed_password="x"))
    db_session.commit()
    db_session.expire_all()
    for user_id in ids:
        assert db_session.get(User, user_id).id == user_id
