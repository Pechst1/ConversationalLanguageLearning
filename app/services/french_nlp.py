"""One spaCy French pipeline per process.

Every ``spacy.load`` of the French model holds its own lemma lookup table
(~217k entries, ~150-200 MB resident). The lemma resolver, the session service
and the error detector each loaded their own copy, the latter two on every
request that built them, which pushed a 512 MB instance out of memory. They
only read the pipeline, so they now share this one.
"""
from __future__ import annotations

import threading
from functools import lru_cache
from typing import Any

_LOCK = threading.Lock()


def french_nlp() -> Any:
    """Return the process-wide French pipeline; raise when it cannot be loaded.

    Callers keep their own fallbacks (a blank pipeline, the curated resolver).
    """

    with _LOCK:
        return _load()


@lru_cache(maxsize=1)
def _load() -> Any:
    import spacy

    from app.config import settings

    return spacy.load(settings.FRENCH_NLP_MODEL)


__all__ = ["french_nlp"]
