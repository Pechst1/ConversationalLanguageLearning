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

#174 / #781: a tile build is right when it spells one of the item's right
sentences, not when it repeats the one id order that was stored. Two tiles that
differ only by case («J'ai» and «j'ai») are the same word, so swapping them is
the same sentence. :func:`accepted_tile_orders` is the one list of right orders;
the grader (``journey_learning.evaluate_recall``) and this key both read it, so
the colour on the device and the server's verdict cannot disagree on a build.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterable, Mapping
from typing import Any

from app.services.journey_contracts import normalize_answer_text

ANSWER_KEY_VERSION = 1

#: Formats graded by option id (a single pick) or by tile-id order.
PICK_FORMATS = frozenset({"choice", "classify", "listen_tap", "who_said"})
ORDER_FORMATS = frozenset({"tiles", "word_bank", "unscramble"})
#: WP-78. A matching item carries one digest *per pair* (material: the French
#: card's id and the meaning card's id, joined like tiles), so the device can
#: colour each pair the moment it is made — the whole point of the format.
PAIR_FORMATS = frozenset({"match_pairs"})

#: Joins tile ids. A unit separator can never appear in an id the planner mints.
TILE_JOINER = "\u001f"


def _secret() -> bytes:
    from app.config import settings

    return str(getattr(settings, "SECRET_KEY", "") or "atelier-answer-key").encode("utf-8")


def answer_key_salt(step_id: str, *, secret: bytes | None = None) -> str:
    """The per-step salt: public, but unpredictable without the server secret."""

    message = f"atelier-answer-key:v{ANSWER_KEY_VERSION}:{step_id}".encode()
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
    if task_type in ORDER_FORMATS or task_type in PAIR_FORMATS:
        parts = [normalize_key_part(tile) for tile in tile_ids]
        if not parts or not all(parts):
            return None
        if task_type in PAIR_FORMATS and len(parts) != 2:
            return None
        return TILE_JOINER.join(parts)
    return None


#: Sentence punctuation is a token of its own: «faim !» and «faim» + «!» spell the same.
_TILE_PUNCTUATION = re.compile(r"\s*([.,;:!?…])\s*")
_FINAL_PUNCTUATION = frozenset(".!?…")
#: An item has a handful of right orders; a cap keeps a pathological item cheap.
MAX_TILE_ORDERS = 24


def _tile_tokens(text: Any) -> list[str]:
    """What a tile or a sentence says, word by word: case and apostrophes folded,
    punctuation kept (a «!» moved into the middle is not the same sentence)."""

    folded = normalize_answer_text(str(text or "")).casefold()
    return _TILE_PUNCTUATION.sub(r" \1 ", folded).split()


def _field(task: Any, name: str) -> Any:
    return task.get(name) if isinstance(task, Mapping) else getattr(task, name, None)


def accepted_tile_orders(task: Any, *, limit: int = MAX_TILE_ORDERS) -> list[list[str]]:
    """Every id order of a tile build that is right (#174, #781): the stored order,
    and each order of the same tiles that spells the stored sentence or one of the
    item's accepted sentences, with case and apostrophes folded.

    ``task`` is a ``RecallTask`` or its stored JSON. The tiles used are the stored
    order's own (a word bank's spare chips stay spare). A sentence given without its
    final punctuation is read with the stored one, which is a tile of the build."""

    order = [str(tile) for tile in (_field(task, "correct_tile_order") or [])]
    if not order:
        return []
    texts = {
        str(option.get("id")): str(option.get("text_fr") or "")
        for option in (_field(task, "options") or [])
        if isinstance(option, Mapping)
    }
    tiles = [(tile, _tile_tokens(texts.get(tile))) for tile in order]
    if any(not tokens for _, tokens in tiles):
        return [order]
    stored = [token for _, tokens in tiles for token in tokens]
    tail: list[str] = []
    while len(tail) < len(stored) and stored[-1 - len(tail)] in _FINAL_PUNCTUATION:
        tail.insert(0, stored[-1 - len(tail)])
    targets = [stored]
    sentences = [*(_field(task, "accepted_answers") or []), _field(task, "solution_fr")]
    for sentence in sentences:
        tokens = _tile_tokens(sentence)
        while tokens and tokens[-1] in _FINAL_PUNCTUATION:
            tokens.pop()
        tokens += tail
        if tokens and tokens not in targets:
            targets.append(tokens)

    out: list[list[str]] = [order]

    def spell(target: list[str], at: int, used: list[bool], placed: list[str]) -> None:
        if len(out) >= limit:
            return
        if at == len(target):
            if len(placed) == len(tiles) and placed not in out:
                out.append(list(placed))
            return
        for index, (tile, tokens) in enumerate(tiles):
            if not used[index] and target[at : at + len(tokens)] == tokens:
                used[index] = True
                placed.append(tile)
                spell(target, at + len(tokens), used, placed)
                placed.pop()
                used[index] = False

    for target in targets:
        spell(target, 0, [False] * len(tiles), [])
    return out


def _pairs(order: Any) -> list[list[str]]:
    """``[fr, native, fr, native, …]`` read as pairs; ``[]`` when malformed."""

    if not isinstance(order, list) or not order or len(order) % 2:
        return []
    return [[str(order[index]), str(order[index + 1])] for index in range(0, len(order), 2)]


def answer_digest(salt: str, material: str) -> str:
    return hashlib.sha256(f"{salt}:{material}".encode()).hexdigest()


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
        # #781: every right order, not only the stored one (the grader reads the same list).
        materials = [answer_material(task_type, tile_ids=order) for order in accepted_tile_orders(recall_task)]
        if not materials or not all(materials):
            return None
        salt = answer_key_salt(str(step_id), secret=secret)
        return {
            "version": ANSWER_KEY_VERSION,
            "salt": salt,
            "digests": sorted(answer_digest(salt, str(item)) for item in materials),
        }
    elif task_type in PAIR_FORMATS:
        pairs = _pairs(recall_task.get("correct_tile_order"))
        materials = [answer_material(task_type, tile_ids=pair) for pair in pairs]
        if not materials or not all(materials):
            return None
        salt = answer_key_salt(str(step_id), secret=secret)
        # Sorted, so the digest order says nothing about which pair is the
        # day's target (the first pair of the stored order).
        return {
            "version": ANSWER_KEY_VERSION,
            "salt": salt,
            "digests": sorted(answer_digest(salt, str(item)) for item in materials),
        }
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
    if task_type in PAIR_FORMATS:
        pairs = _pairs(list(tile_ids))
        digests = set(key.get("digests") or [])
        salt = str(key.get("salt") or "")
        return bool(pairs) and all(
            answer_digest(salt, str(answer_material(task_type, tile_ids=pair))) in digests
            for pair in pairs
        )
    material = answer_material(task_type, option_id=option_id, tile_ids=tile_ids)
    if material is None:
        return False
    return answer_digest(str(key.get("salt") or ""), material) in set(key.get("digests") or [])
