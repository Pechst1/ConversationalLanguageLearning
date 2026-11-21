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
differ only by case («J'ai» and «j'ai»), or that are the same word twice («le»),
are interchangeable. The grader reads :func:`tiles_spell_an_answer` (the text the
build spells, no list to run out of); the device key holds every id order that
spells it (:func:`accepted_tile_orders`), or no key at all when there are too many
to list, so the colour on the device can never contradict the server.
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
#: The most id orders a device key lists. An item with more right orders (many
#: repeated words) gets no key: the device waits for the server, never guesses.
MAX_KEY_ORDERS = 64


def _tile_tokens(text: Any) -> list[str]:
    """What a tile or a sentence says, word by word: case and apostrophes folded,
    punctuation kept (a «!» moved into the middle is not the same sentence)."""

    folded = normalize_answer_text(str(text or "")).casefold()
    return _TILE_PUNCTUATION.sub(r" \1 ", folded).split()


def _field(task: Any, name: str) -> Any:
    return task.get(name) if isinstance(task, Mapping) else getattr(task, name, None)


def _tile_build(task: Any) -> tuple[list[str], dict[str, list[str]], list[list[str]]] | None:
    """The stored order, each of its tiles' tokens, and the token sequences that are
    right: the stored order's own, and each accepted sentence (read with the stored
    final punctuation when it is given without one, the «!» being a tile of the build).
    ``None`` when a tile of the order has no text to read (ids are all there is)."""

    order = [str(tile) for tile in (_field(task, "correct_tile_order") or [])]
    if not order:
        return None
    texts = {
        str(option.get("id")): option.get("text_fr")
        for option in (_field(task, "options") or [])
        if isinstance(option, Mapping)
    }
    tokens = {tile: _tile_tokens(texts.get(tile)) for tile in order}
    if any(not tokens[tile] for tile in order):
        return None
    stored = [token for tile in order for token in tokens[tile]]
    tail: list[str] = []
    while len(tail) < len(stored) and stored[-1 - len(tail)] in _FINAL_PUNCTUATION:
        tail.insert(0, stored[-1 - len(tail)])
    targets = [stored]
    for sentence in [*(_field(task, "accepted_answers") or []), _field(task, "solution_fr")]:
        said = _tile_tokens(sentence)
        while said and said[-1] in _FINAL_PUNCTUATION:
            said.pop()
        said += tail
        if said and said not in targets:
            targets.append(said)
    return order, tokens, targets


def tiles_spell_an_answer(task: Any, tile_ids: Iterable[Any]) -> bool:
    """Is this build right (#174, #781)? It uses the answer's own tiles, each once (a
    word bank's spare chips stay spare), and spells one of the item's right
    sentences, case and apostrophes folded. Read off the text, so two «le» tiles or
    «J'ai» / «j'ai» swapped are the same build."""

    submitted = [str(tile) for tile in tile_ids]
    order = [str(tile) for tile in (_field(task, "correct_tile_order") or [])]
    if not submitted or sorted(submitted) != sorted(order):
        return False
    if submitted == order:
        return True
    build = _tile_build(task)
    if build is None:
        return False
    _order, tokens, targets = build
    return [token for tile in submitted for token in tokens[tile]] in targets


def accepted_tile_orders(task: Any, *, limit: int = MAX_KEY_ORDERS) -> list[list[str]] | None:
    """Every id order :func:`tiles_spell_an_answer` takes, stored order first, or
    ``None`` when there are more than ``limit`` (the device key is then left out:
    a key missing a right order would colour a right build red, #781).

    ``task`` is a ``RecallTask`` or its stored JSON."""

    order = [str(tile) for tile in (_field(task, "correct_tile_order") or [])]
    if not order:
        return []
    build = _tile_build(task)
    if build is None:
        return [order]
    _order, tokens, targets = build
    out: list[list[str]] = [order]
    overflow = False

    def spell(target: list[str], at: int, left: list[str], placed: list[str]) -> None:
        nonlocal overflow
        if overflow:
            return
        if not left:
            if at == len(target) and placed not in out:
                out.append(list(placed))
                overflow = len(out) > limit
            return
        for index, tile in enumerate(left):
            if tile in left[:index] or target[at : at + len(tokens[tile])] != tokens[tile]:
                continue
            placed.append(tile)
            spell(target, at + len(tokens[tile]), left[:index] + left[index + 1 :], placed)
            placed.pop()

    for target in targets:
        spell(target, 0, order, [])
    return None if overflow else out


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
        # #781: every order the grader takes (``tiles_spell_an_answer``), or no key.
        orders = accepted_tile_orders(recall_task)
        materials = [answer_material(task_type, tile_ids=order) for order in orders or []]
        if not materials or not all(materials):
            return None
        salt = answer_key_salt(str(step_id), secret=secret)
        return {
            "version": ANSWER_KEY_VERSION,
            "salt": salt,
            # Sorted, so the first digest does not name the stored order.
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
