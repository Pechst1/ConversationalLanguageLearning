"""WP-76 — a hashed answer key, so a pick can be coloured on the device.

A choice, classify, tiles or word-bank recall is graded by the server by
**identity**: the option id that was picked, or the exact sequence of tile ids
(``journey_learning.evaluate_recall`` and the stub adapter both compare ids,
never text). The learner should see green or red within 100 ms of the tap, and
the network round trip is seconds, so the public step carries a key the client
can *check* but cannot *read*:

    salt   = HMAC-SHA256(SECRET_KEY, "atelier-answer-key:v1:" + step_id)[:32]
    digest = SHA-256(salt + ":" + material)

where ``material`` is the normalised answer — the option id, or the tile ids
joined with U+001F. The client hashes its own pick the same way (Web Crypto)
and compares. The salt is per step and derived from a server secret, so two
steps with the same ids never share a digest and a precomputed table is
useless.

What this is not: a secret against a determined learner with devtools. With
three options, hashing each is three digests away. That is fine — the point is
that the answer is never *printed* in the payload a curious learner or a
screenshot reads, and that the server's verdict stays authoritative: the local
colour is a preview the server can overrule.

Only formats graded by identity get a key. A written answer is graded by
folding and synonyms on the server, and a local hash of it would disagree with
the real checker far too often to be worth showing.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Iterable

from app.services.journey_contracts import normalize_answer_text

ANSWER_KEY_VERSION = 1

#: Formats graded by option id (a single pick) or by tile-id order.
PICK_FORMATS = frozenset({"choice", "classify"})
ORDER_FORMATS = frozenset({"tiles", "word_bank"})

#: Joins tile ids. A unit separator can never appear in an id the planner mints.
TILE_JOINER = "\u001f"


def _secret() -> bytes:
    from app.config import settings

    return str(getattr(settings, "SECRET_KEY", "") or "atelier-answer-key").encode("utf-8")


def answer_key_salt(step_id: str, *, secret: bytes | None = None) -> str:
    """The per-step salt: public, but unpredictable without the server secret."""

    message = f"atelier-answer-key:v{ANSWER_KEY_VERSION}:{step_id}".encode("utf-8")
    return hmac.new(secret if secret is not None else _secret(), message, hashlib.sha256).hexdigest()[:32]


def normalize_key_part(value: Any) -> str:
    """One id, normalised exactly as the client does before hashing.

    The server compares ids verbatim; folding smart quotes and collapsing
    whitespace is the same ``normalize_answer_text`` the text checker uses, so
    an id that ever did carry a typed apostrophe hashes identically on both
    sides. For the ids the planner mints this is the identity.
    """

    return normalize_answer_text(str(value if value is not None else ""))


def answer_material(task_type: str, *, option_id: Any = None, tile_ids: Iterable[Any] = ()) -> str | None:
    """The string that is hashed for one answer, or ``None`` when there is none."""

    if task_type in PICK_FORMATS:
        part = normalize_key_part(option_id)
        return part or None
    if task_type in ORDER_FORMATS:
        parts = [normalize_key_part(tile) for tile in tile_ids]
        if not parts or not all(parts):
            return None
        return TILE_JOINER.join(parts)
    return None


def answer_digest(salt: str, material: str) -> str:
    return hashlib.sha256(f"{salt}:{material}".encode("utf-8")).hexdigest()


def answer_key_for(
    step_id: str, recall_task: dict[str, Any] | None, *, secret: bytes | None = None
) -> dict[str, Any] | None:
    """The public ``answer_key`` for one stored recall task, or ``None``.

    ``recall_task`` is the private JSON ``daily_journey`` stores under
    ``private_task["recall_task"]``. Anything malformed yields ``None``: the
    client then simply waits for the server, exactly as before WP-76.
    """

    if not isinstance(recall_task, dict) or not step_id:
        return None
    task_type = str(recall_task.get("task_type") or "")
    if task_type in PICK_FORMATS:
        material = answer_material(task_type, option_id=recall_task.get("correct_option_id"))
    elif task_type in ORDER_FORMATS:
        order = recall_task.get("correct_tile_order")
        material = answer_material(task_type, tile_ids=order if isinstance(order, list) else ())
    else:
        return None
    if not material:
        return None
    salt = answer_key_salt(str(step_id), secret=secret)
    return {
        "version": ANSWER_KEY_VERSION,
        "salt": salt,
        "digests": [answer_digest(salt, material)],
    }


def answer_matches_key(
    key: dict[str, Any] | None,
    task_type: str,
    *,
    option_id: Any = None,
    tile_ids: Iterable[Any] = (),
) -> bool | None:
    """Mirror of the client check, for tests and for parity with the grader."""

    if not key:
        return None
    material = answer_material(task_type, option_id=option_id, tile_ids=tile_ids)
    if material is None:
        return False
    return answer_digest(str(key.get("salt") or ""), material) in set(key.get("digests") or [])
