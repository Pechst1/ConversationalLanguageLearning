"""WP-S1 (La Forge): grade locally, never block on the model.

Everything the séance can check against an answer key is checked here, in
microseconds, on the request path:

* the comparison folds what is typography, not French — apostrophe and quote
  variants (``journey_contracts.normalize_answer_text``), case, exotic spaces and
  the final punctuation mark — and keeps the accents, so an accent slip is
  *reported* even where the grader forgives it;
* a token-level diff says *what* is wrong in a rewrite or a word-bank line: the
  ending of one word, a missing word, a stray one, or only the order;
* a unit's regex detectors (WP-L2 v2 catalogue) or, for v1 units, the profile
  matcher tell whether a free sentence uses the rule at all.

Free production (a sentence, the paragraph, a spoken transcript, a
conversation turn) still gets the model's verdict, but asynchronously: the
request returns :func:`production_local_check` at once and the relecture amends
the stored correction when it lands (``AtelierCorrectionService``).
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from app.services.journey_contracts import normalize_answer_text
from app.services.learner_copy import learner_text as _copy

#: Rungs graded by the model — asynchronously — after an instant local verdict.
FREE_PRODUCTION_ROUNDS: frozenset[str] = frozenset({"sentence", "speak", "conversation", "produce"})

#: Rungs graded by an answer key; the model never decides these verdicts.
KEYED_ROUNDS: frozenset[str] = frozenset({"recognize", "transform"})

_FINAL_PUNCTUATION = " .!?;:,…"
#: An elided particle («l'», «j'», «qu'») is its own token; «aujourd'hui» stays whole.
_TOKEN = re.compile(
    r"\b(?:jusqu|lorsqu|puisqu|quoiqu|qu|[cdjlmnst])'|\w+(?:['-]\w+)*|[^\s\w]",
    re.UNICODE | re.IGNORECASE,
)


def fold_typography(value: Any) -> str:
    """Quotes, case, spacing and the final punctuation folded; accents kept."""

    text = normalize_answer_text("" if value is None else str(value))
    text = unicodedata.normalize("NFC", text).casefold()
    text = re.sub(r"[«»\"]", " ", text)
    text = re.sub(r"'\s+", "'", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return " ".join(text.split()).strip(_FINAL_PUNCTUATION)


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokens(value: Any) -> list[str]:
    """Words (an elided «l'», «j'» stays one token) — punctuation is dropped."""

    return [token for token in _TOKEN.findall(fold_typography(value)) if token[0].isalnum()]


def same_answer(learner: Any, target: Any) -> tuple[bool, bool]:
    """``(matches, accent_slip)``: does it match, and only once accents are folded?"""

    left, right = fold_typography(learner), fold_typography(target)
    if not right:
        return False, False
    if left == right:
        return True, False
    folded_match = strip_accents(left) == strip_accents(right)
    return folded_match, folded_match


def _ending(learner: str, target: str) -> tuple[str, str] | None:
    """Same stem, different ending: ``("arrive", "arrivera")`` -> the two words."""

    prefix = 0
    for left, right in zip(strip_accents(learner), strip_accents(target), strict=False):
        if left != right:
            break
        prefix += 1
    stem = min(len(learner), len(target))
    if prefix >= 3 or (stem and prefix >= stem - 1 and prefix >= 2):
        return learner, target
    return None


def token_diff(learner: Any, target: Any) -> list[dict[str, str]]:
    """What separates the learner's line from the key, one operation per difference.

    Kinds: ``ending`` (same stem), ``accent``, ``word`` (a different word),
    ``missing``, ``extra`` and ``order`` (same words, other order — reported alone).
    """

    left, right = tokens(learner), tokens(target)
    if left == right:
        return []
    if sorted(strip_accents(token) for token in left) == sorted(strip_accents(token) for token in right) and [
        strip_accents(token) for token in left
    ] != [strip_accents(token) for token in right]:
        return [{"kind": "order", "learner": " ".join(left), "target": " ".join(right)}]
    ops: list[dict[str, str]] = []
    matcher = SequenceMatcher(a=[strip_accents(token) for token in left], b=[strip_accents(token) for token in right], autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                if left[i1 + offset] != right[j1 + offset]:
                    ops.append({"kind": "accent", "learner": left[i1 + offset], "target": right[j1 + offset]})
            continue
        if tag == "delete":
            ops.extend({"kind": "extra", "learner": token, "target": ""} for token in left[i1:i2])
            continue
        if tag == "insert":
            ops.extend({"kind": "missing", "learner": "", "target": token} for token in right[j1:j2])
            continue
        # replace: pair the words up in order; any surplus is missing / extra.
        pairs = list(zip(left[i1:i2], right[j1:j2], strict=False))
        for learner_word, target_word in pairs:
            kind = "ending" if _ending(learner_word, target_word) else "word"
            ops.append({"kind": kind, "learner": learner_word, "target": target_word})
        ops.extend({"kind": "extra", "learner": token, "target": ""} for token in left[i1 + len(pairs):i2])
        ops.extend({"kind": "missing", "learner": "", "target": token} for token in right[j1 + len(pairs):j2])
    return ops


def describe_diff(ops: list[dict[str, str]], language: Any) -> str:
    """One or two short sentences, in the learner's language, naming the difference."""

    sentences: list[str] = []
    for op in ops:
        kind = op.get("kind")
        if kind == "accent":
            continue
        if kind == "order":
            sentences.append(_copy("forge.diff.order", language))
        elif kind == "ending":
            sentences.append(_copy("forge.diff.ending", language, learner=op["learner"], target=op["target"]))
        elif kind == "word":
            sentences.append(_copy("forge.diff.word", language, learner=op["learner"], target=op["target"]))
        elif kind == "missing":
            sentences.append(_copy("forge.diff.missing", language, target=op["target"]))
        elif kind == "extra":
            sentences.append(_copy("forge.diff.extra", language, learner=op["learner"]))
        if len(sentences) == 2:
            break
    return " ".join(sentences)


def similarity(learner: Any, target: Any) -> float:
    """0–1 token similarity to a model answer (accent-insensitive)."""

    left = [strip_accents(token) for token in tokens(learner)]
    right = [strip_accents(token) for token in tokens(target)]
    if not left or not right:
        return 0.0
    return round(SequenceMatcher(a=left, b=right, autojunk=False).ratio(), 3)


def detector_check(concept: Any, text: str) -> dict[str, Any]:
    """Does ``text`` use the unit? ``{"status": hit|miss|unknown, "span", "source"}``.

    The v2 unit's own regex detectors decide when it has them (fixed expressions
    such as «un peu» never count); v1 units fall back to the profile matcher.
    """

    if concept is None or not str(text or "").strip():
        return {"status": "unknown", "span": None, "source": None}
    try:
        from app.services.grammar_items import detector_span
        from app.services.grammar_units import regex_patterns, unit_detectors

        patterns = regex_patterns(unit_detectors(concept))
    except Exception:  # pragma: no cover - a catalogue read must never fail a grade
        patterns = []
    if patterns:
        span = detector_span(patterns, text)
        return {"status": "hit" if span else "miss", "span": span, "source": "detector"}
    from app.services.grammar_feedback import count_concept_hits

    hits = count_concept_hits(concept, text)
    return {"status": "hit" if hits else "miss", "span": None, "source": "profile"}


#: WP-103 T9. The only two things the séance may say before the model has read a
#: free answer: «right» (it IS an accepted answer) or «checking» («Je relis…»).
LOCAL_RIGHT = "right"
LOCAL_CHECKING = "checking"


def matches_accepted(text: Any, accepted: Any) -> bool:
    """Is ``text`` one of the accepted answers, up to typography?

    Case, punctuation, apostrophe and quote variants (’ ‘ « » "), and spacing are
    folded; accents are not — «a» for «à» is a slip, not a match.
    """

    said = tokens(text)
    if not said:
        return False
    return any(tokens(answer) == said for answer in accepted or [] if str(answer or "").strip())


def production_local_check(
    concept: Any, text: str, model_answer: Any = None, accepted: Any = None
) -> dict[str, Any]:
    """The instant verdict for free production: the rule's detector, closeness to a
    model answer, and — WP-103 T9 — ``local_status``: ``right`` only when the answer
    is an accepted answer (:func:`matches_accepted`), otherwise ``checking`` until
    the model's verdict lands. A detector hit is a hint, never a «Right»."""

    check = detector_check(concept, text)
    result: dict[str, Any] = {"detector": check["status"], "span": check["span"], "source": check["source"]}
    if model_answer:
        result["model_similarity"] = similarity(text, model_answer)
    keys = [*(accepted or []), *([model_answer] if model_answer else [])]
    result["local_status"] = LOCAL_RIGHT if matches_accepted(text, keys) else LOCAL_CHECKING
    return result


# ---------------------------------------------------------------------------
# WP-103 T10 — one explanation per issue, and French is not English
# ---------------------------------------------------------------------------

#: Established French words that look English. The owner's test: the corrector
#: called «poster» English and replaced it with «affiche». These are French.
FRENCH_LOANWORDS: frozenset[str] = frozenset(
    {
        "poster", "posters", "week-end", "week-ends", "weekend", "parking", "sandwich",
        "sandwichs", "email", "e-mail", "mail", "mails", "film", "films", "sport", "sports",
        "taxi", "taxis", "bus", "jean", "jeans", "basket", "baskets", "shopping", "smartphone",
        "podcast", "match", "matchs", "pull", "t-shirt", "tee-shirt", "sweat", "football",
        "foot", "tennis", "hockey", "rugby", "golf", "jogging", "camping", "pressing",
        "brunch", "cocktail", "whisky", "hamburger", "ketchup", "chips", "cookie", "cookies",
        "muffin", "pizza", "blog", "site", "web", "wifi", "wi-fi", "internet", "selfie",
        "stop", "ok", "cool", "job", "business", "manager", "marketing", "stress", "look",
        "star", "fan", "fans", "rock", "jazz", "show", "club", "bar", "hall", "loft",
        "studio", "toast", "bacon", "snack", "leader", "planning", "budget", "badge",
        "flash", "scanner", "zoom", "rap", "clip", "sms", "bug", "stand", "spot", "short",
        "bowling", "skate", "surf", "yoga", "fitness", "coach", "score", "ticket",
        "tickets", "garage", "baby-sitter", "babysitter", "bodyguard", "jingle", "live",
    }
)

_ENGLISH_CLAIM = re.compile(
    r"\b(?:is|an?|in|the)\s+english\b|\benglish\s+(?:word|term|noun|loanword)|\banglicism"
    r"|\b(?:mot|terme|nom)\s+anglais\b|\ben\s+anglais\b|\best\s+anglais\b|\banglicisme"
    r"|\benglisch(?:es|e|er)?\s+(?:wort|begriff|nomen)|\bauf\s+englisch\b|\bist\s+englisch\b"
    r"|\banglizism|\bnot\s+(?:a\s+)?french\b|\bpas\s+(?:un\s+mot\s+)?français\b"
    r"|\bkein\s+französisch",
    re.IGNORECASE,
)


def _fold_word(word: Any) -> str:
    return normalize_answer_text(str(word or "")).casefold().strip(" .,;:!?«»\"()[]")


@lru_cache(maxsize=1)
def _bank_french_words() -> frozenset[str]:
    """Every French form the item bank's lexicon writes (nouns, their alternatives,
    adjectives) — the words La Forge itself asks for are French by definition."""

    try:
        import json

        from app.services.item_bank import TEMPLATE_DIR

        lexicon = json.loads((TEMPLATE_DIR / "lexicon.json").read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - a missing lexicon only weakens the guard
        return frozenset()
    words: set[str] = set()
    for entry in [*(lexicon.get("nouns") or []), *(lexicon.get("adjectives") or [])]:
        for key in ("fr", "m", "f", "mp", "fp", "pl"):
            value = entry.get(key)
            if isinstance(value, str):
                words.update(_fold_word(part) for part in value.split())
        for alternative in entry.get("alt_fr") or []:
            value = alternative.get("fr") if isinstance(alternative, dict) else alternative
            if isinstance(value, str):
                words.update(_fold_word(part) for part in value.split())
    return frozenset(word for word in words if word)


def is_french_word(word: Any) -> bool:
    """Is ``word`` French — in the core lexicon, the bank's lexicon, or an established
    loanword? Plural -s/-x is tried too. Unknown words are not claimed either way."""

    folded = _fold_word(word)
    if not folded:
        return False
    candidates = {folded}
    if len(folded) > 3 and folded[-1] in "sx":
        candidates.add(folded[:-1])
    if candidates & FRENCH_LOANWORDS or candidates & _bank_french_words():
        return True
    try:
        from app.services.lexical_coverage import fold as lexical_fold
        from app.services.lexical_coverage import load_lexicon

        lexicon = load_lexicon()
        return any(
            lexical_fold(candidate) in lexicon.lemmas or lexical_fold(candidate) in lexicon.forms
            for candidate in candidates
        )
    except Exception:  # pragma: no cover - a lexicon read never fails a grade
        return False


def _all_french(fragment: Any) -> bool:
    words = [word for word in re.findall(r"[^\W\d_][\w'’-]*", str(fragment or "")) if word]
    return bool(words) and all(is_french_word(word) for word in words)


def _claims_english(erratum: dict[str, Any]) -> bool:
    text = " ".join(
        str(erratum.get(key) or "") for key in ("why_wrong", "repair_hint", "display_label")
    )
    return bool(_ENGLISH_CLAIM.search(text)) or str(erratum.get("task_error_type") or "") == "lexical_gap"


def drop_false_english(
    errata: list[dict[str, Any]] | None, lexical_gaps: list[dict[str, Any]] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """``(errata, lexical_gaps, dropped)`` without the corrections that call a French
    word English (WP-103 T10: «poster» is French). An erratum is dropped when it says
    the word is English (or is a lexical gap) and every word it flags is French; a
    lexical gap likewise when its fragment is French."""

    kept_gaps = [
        gap
        for gap in lexical_gaps or []
        if not (isinstance(gap, dict) and _all_french(gap.get("learner_fragment")))
    ]
    dropped_fragments = {
        _fold_word(gap.get("learner_fragment"))
        for gap in lexical_gaps or []
        if isinstance(gap, dict) and gap not in kept_gaps
    }
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for erratum in errata or []:
        if not isinstance(erratum, dict):
            continue
        learner = erratum.get("learner_text")
        if (_claims_english(erratum) and _all_french(learner)) or (
            str(erratum.get("task_error_type") or "") == "lexical_gap"
            and _fold_word(learner) in dropped_fragments
        ):
            dropped.append(erratum)
            continue
        kept.append(erratum)
    return kept, kept_gaps, dropped


_NOTE_SENTENCE = re.compile(r"(?<=[.!?…])\s+")
_NOTE_SENTENCES = 2


def _fold_note(text: Any) -> str:
    folded = strip_accents(normalize_answer_text(str(text or "")).casefold())
    return " ".join(re.sub(r"[^\w\s]", " ", folded).split())


def clip_note(text: Any, sentences: int = _NOTE_SENTENCES) -> str:
    """One note: at most two sentences, none of them said twice."""

    parts: list[str] = []
    seen: set[str] = set()
    for part in _NOTE_SENTENCE.split(" ".join(str(text or "").split())):
        key = _fold_note(part)
        if not key or key in seen:
            continue
        seen.add(key)
        parts.append(part.strip())
        if len(parts) == sentences:
            break
    return " ".join(parts)


def notes_native(errata: list[dict[str, Any]] | None, *, extra: Any = ()) -> list[str]:
    """WP-103 contract: one note per issue, deduplicated, at most two sentences each,
    in the learner's language — never the rule's note, the model's note and a second
    check glued into one blob. A note already said (or contained in one already said)
    is not said again."""

    notes: list[str] = []
    keys: list[str] = []
    candidates = [
        (item.get("why_wrong") or item.get("repair_hint")) if isinstance(item, dict) else item
        for item in [*(errata or []), *(extra or [])]
    ]
    for candidate in candidates:
        note = clip_note(candidate)
        key = _fold_note(note)
        if not key:
            continue
        if any(
            key == other
            or (len(key) >= 12 and f" {key} " in f" {other} ")
            or (len(other) >= 12 and f" {other} " in f" {key} ")
            for other in keys
        ):
            continue
        notes.append(note)
        keys.append(key)
    return notes


#: Adjectives French puts before the noun (petit, grand, bon, beau…), every form.
PRE_NOMINAL_ADJECTIVES: frozenset[str] = frozenset(
    {
        "petit", "petite", "petits", "petites", "grand", "grande", "grands", "grandes",
        "joli", "jolie", "jolis", "jolies", "jeune", "jeunes", "nouveau", "nouvel",
        "nouvelle", "nouveaux", "nouvelles", "vieux", "vieil", "vieille", "vieilles",
        "beau", "bel", "belle", "beaux", "belles", "bon", "bonne", "bons", "bonnes", "gros",
        "grosse", "grosses", "mauvais", "mauvaise", "mauvaises", "long", "longue", "longs",
        "longues", "haut", "haute", "hauts", "hautes", "premier", "première", "premiers",
        "premières", "dernier", "dernière", "derniers", "dernières",
    }
)
_DETERMINERS: frozenset[str] = frozenset(
    {
        "un", "une", "des", "le", "la", "les", "l'", "du", "au", "aux", "mon", "ma", "mes",
        "ton", "ta", "tes", "son", "sa", "ses", "notre", "nos", "votre", "vos", "leur",
        "leurs", "ce", "cet", "cette", "ces",
    }
)
_ORDER_NOTES: dict[str, dict[str, str]] = {
    "adjective": {
        "en": "«{adjective}» goes before the noun: «{target}».",
        "de": "«{adjective}» steht vor dem Nomen: «{target}».",
        "fr": "«{adjective}» se place avant le nom : «{target}».",
    },
    "label": {"en": "Word order", "de": "Wortstellung", "fr": "Ordre des mots"},
}


def _language(value: Any) -> str:
    language = str(value or "en").strip().lower()[:2]
    return language if language in {"en", "de", "fr"} else "en"


def reordering_correction(
    learner: Any, accepted: Any, language: Any = "en"
) -> tuple[str, dict[str, Any]] | None:
    """``(accepted answer, erratum)`` when ``learner`` is an accepted answer with its
    words in another order — then that is the one issue, whatever else a model said.
    The erratum names the smallest span that moved («un poster grand» → «un grand
    poster») and, for an adjective French puts first, says so."""

    said = tokens(learner)
    if len(said) < 2:
        return None
    for answer in accepted or []:
        target = tokens(answer)
        if len(target) != len(said) or target == said:
            continue
        if sorted(strip_accents(token) for token in target) != sorted(strip_accents(token) for token in said):
            continue
        start = 0
        while start < len(said) and strip_accents(said[start]) == strip_accents(target[start]):
            start += 1
        end = 0
        while end < len(said) - start and strip_accents(said[-1 - end]) == strip_accents(target[-1 - end]):
            end += 1
        if start and said[start - 1] in _DETERMINERS:
            start -= 1
        learner_span = said[start: len(said) - end]
        target_span = target[start: len(target) - end]
        joined_target = " ".join(target_span).replace("' ", "'")
        joined_learner = " ".join(learner_span).replace("' ", "'")
        language_key = _language(language)
        moved = next((token for token in target_span if token in PRE_NOMINAL_ADJECTIVES), None)
        if moved and target_span.index(moved) < learner_span.index(moved):
            why = _ORDER_NOTES["adjective"][language_key].format(adjective=moved, target=joined_target)
        else:
            why = _copy("forge.diff.order", language_key)
        erratum = {
            "item_id": "",
            "display_label": _ORDER_NOTES["label"][language_key],
            "learner_text": joined_learner,
            "corrected_target": joined_target,
            "why_wrong": why,
            "repair_hint": "",
            "severity": 2,
            "recurring": True,
            "task_error_type": "word_order",
        }
        return str(answer), erratum
    return None


def refine_production_correction(
    correction: dict[str, Any], *, learner_text: Any, accepted: Any, language: Any = "en"
) -> dict[str, Any]:
    """The model's reading of a free answer, held to what the key knows (WP-103 T10).

    * a correction that calls a French word English is dropped;
    * an answer that is an accepted answer in another order has one issue — the
      order — and its correction is that accepted answer;
    * ``notes_native``: one note per issue, deduplicated.
    """

    refined = dict(correction)
    errata, gaps, dropped = drop_false_english(
        list(refined.get("errata") or []), list(refined.get("lexical_gaps") or [])
    )
    if dropped:
        refined["errata"], refined["lexical_gaps"] = errata, gaps
        refined["dropped_errata"] = [
            {"learner_text": item.get("learner_text"), "reason": "french_word_called_english"}
            for item in dropped
        ]
    reordered = reordering_correction(learner_text, accepted, language)
    if reordered is not None:
        answer, erratum = reordered
        concept = next((item for item in refined.get("errata") or [] if isinstance(item, dict)), {})
        erratum["concept_id"] = concept.get("concept_id")
        erratum["external_id"] = concept.get("external_id")
        refined["errata"] = [erratum]
        refined["lexical_gaps"] = []
        refined["corrected_answer"] = answer
        refined["verdict"] = "partial"
        refined["score_0_4"] = min(max(float(refined.get("score_0_4") or 0), 2.0), 2.5)
    elif dropped and not refined.get("errata") and not refined.get("lexical_gaps"):
        # Nothing was left but the false «English» note: the answer stands as written.
        refined["corrected_answer"] = str(learner_text or refined.get("corrected_answer") or "")
    refined["notes_native"] = notes_native(refined.get("errata"))
    return refined


# ---------------------------------------------------------------------------
# WP-103 T8 — «À corriger» leads somewhere
# ---------------------------------------------------------------------------

#: The judgement label that means «this sentence is wrong».
TO_CORRECT_LABEL = "À corriger"
#: Bands that correct with tiles rather than a field.
TILE_BANDS = frozenset({"A1"})


def _scrambled(values: list[str], key: str) -> list[str]:
    import hashlib

    order = sorted(values, key=lambda value: hashlib.sha256(f"{key}:{value}".encode()).hexdigest())
    return order


def classify_follow_up(
    item: dict[str, Any], learner_answer: Any, *, band: Any = None, language: Any = None
) -> dict[str, Any] | None:
    """What a judgement item adds once it is answered (WP-103 T8).

    A wrong sentence always shows its right form (``corrected_fr``). Sorted
    «À corriger» *correctly*, it also opens the correction itself: a ``follow_up``
    ``{kind: "correct_it", source_fr, goal_native, accepted_fr}`` graded like a
    transform (a typography-folded match against ``accepted_fr``), with ``options``
    (tiles: the right sentence's words and the wrong one's word as a spare) at A1.
    ``None`` for a right sentence or an item without the key.
    """

    key = item.get("follow_up_key") if isinstance(item, dict) else None
    if not isinstance(key, dict) or not str(key.get("corrected_fr") or "").strip():
        return None
    if fold_typography(item.get("correct_label")) != fold_typography(TO_CORRECT_LABEL):
        return None
    corrected = str(key["corrected_fr"])
    result: dict[str, Any] = {"corrected_fr": corrected}
    if fold_typography(learner_answer) != fold_typography(TO_CORRECT_LABEL):
        return result
    from app.services.item_bank import _tokens as sentence_tokens
    from app.services.item_bank import goal_l10n

    code = _language(language)
    meaning = str(key.get("meaning") or "").strip()
    goal = (goal_l10n("repair", meaning) if meaning else {
        "en": "Correct the sentence.", "de": "Korrigiere den Satz.", "fr": "Corrigez la phrase.",
    })
    source = str(item.get("source_fr") or item.get("prompt") or "").strip()
    accepted = [corrected, *[str(value) for value in key.get("accepted_fr") or [] if str(value).strip()]]
    follow_up: dict[str, Any] = {
        "kind": "correct_it",
        "id": f"{item.get('id') or 'classify'}:correct-it",
        "source_fr": source,
        "goal_native": goal.get(code) or goal["en"],
        "accepted_fr": list(dict.fromkeys(accepted)),
    }
    if str(band or "").strip().upper()[:2] in TILE_BANDS:
        words = sentence_tokens(corrected)
        spare = [
            token
            for token in sentence_tokens(str(key.get("wrong_span") or ""))
            if fold_typography(token) not in {fold_typography(word) for word in words}
        ]
        words = [word for word in words if word[:1].isalnum()]
        options = _scrambled([*words, *spare[:1]], str(item.get("id") or corrected))
        if options[: len(words)] == words and len(options) > 1:
            options = options[1:] + options[:1]
        follow_up["options"] = options
    result["follow_up"] = follow_up
    return result


__all__ = [
    "TO_CORRECT_LABEL",
    "classify_follow_up",
    "FREE_PRODUCTION_ROUNDS",
    "FRENCH_LOANWORDS",
    "KEYED_ROUNDS",
    "LOCAL_CHECKING",
    "LOCAL_RIGHT",
    "clip_note",
    "describe_diff",
    "detector_check",
    "drop_false_english",
    "fold_typography",
    "is_french_word",
    "matches_accepted",
    "notes_native",
    "production_local_check",
    "refine_production_correction",
    "reordering_correction",
    "same_answer",
    "similarity",
    "strip_accents",
    "token_diff",
    "tokens",
]
