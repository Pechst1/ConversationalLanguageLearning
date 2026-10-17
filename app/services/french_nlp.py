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
    from loguru import logger

    from app.config import settings
    from app.services import compact_lemmas

    # #134: the lemmatizer's own tables are ~150 MB as spaCy loads them; the
    # compact copy the Docker build writes next to the model answers the same
    # lemmas in ~6 MB. Without it (a dev checkout) the plain load stands.
    try:
        return compact_lemmas.load(settings.FRENCH_NLP_MODEL)
    except FileNotFoundError:
        logger.info(
            "French pipeline: no compact lemma tables, loading the full ones "
            "(python -m app.services.compact_lemmas builds them)"
        )
    except Exception as exc:  # noqa: BLE001 - a broken compact copy must not cost the pipeline
        logger.warning("French pipeline: compact lemma tables unusable ({}); loading the full ones", exc)
    return spacy.load(settings.FRENCH_NLP_MODEL)


__all__ = ["french_nlp"]
