"""#174, second round: what a banked variant may differ from its key by, and nothing else.

A variant is another way to write *the key's* answer, never another answer. Subject, tense,
mood, polarity and lexical content are the key's; for a fix-the-mistake item the variant is
the shown wrong sentence with its error fixed, not another sentence. The differences that
are allowed are the classes in :data:`VARIANT_CLASSES`; each stored variant names one.

:func:`prefilter` is the cheap deterministic half: it refuses a variant whose subject
pronouns, finite-verb tenses and moods, negation or content lemmas differ from the key's
(read with the repo's one spaCy pipeline, :func:`app.services.french_nlp.french_nlp`). What
it lets through goes to a strict model check (``scripts/build_answer_bank.py verify``)
that must name the class or refuse. Only variants with a class are used at answer time.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

__all__ = ["VARIANT_CLASSES", "prefilter"]

#: The only differences a variant may have from its key. The same text goes into the
#: strict check's prompt, so the code and the model read one definition.
VARIANT_CLASSES: dict[str, str] = {
    "spelling": "a recognised second spelling of the same word (clé/clef, 1990 rectified spellings such as "
    "évènement or connaitre, paie/paye), or the feminine job noun for the same feminine subject "
    "(professeur/professeure)",
    "open_person": "tu instead of vous (or the reverse), only when the prompt the learner sees does not fix "
    "which one (an English 'you' with no other cue); never when the shown sentence already uses one",
    "open_gender": "a masculine/feminine agreement only when the prompt the learner sees does not fix the "
    "gender (English 'I', 'you', 'we' with no other cue); never when the shown sentence fixes it",
    "on_nous": "on for nous or nous for on, with the verb agreeing, when the meaning is 'we' and the item does "
    "not practise on itself",
    "question_form": "the same yes/no or wh- question as intonation, est-ce que or inversion, when the item "
    "does not practise the question form",
    "elision": "a correct elision or contraction (que il -> qu'il is not optional; this is for genuine "
    "alternatives such as the spoken-written pairs a teacher accepts)",
    "punctuation": "an optional comma or other punctuation the key has or lacks",
}

_SUBJECTS = ("je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles")
_SWAPS = ({"tu", "vous"}, {"on", "nous"})
_NEGATION = frozenset({"ne", "n", "pas", "jamais", "rien", "personne", "aucun", "aucune", "guère", "nullement", "ni"})
_ESTCEQUE = re.compile(r"\best-ce\s+qu(?:e\s+|')", re.IGNORECASE)
_WORD = re.compile(r"[a-zàâäçéèêëîïôöùûüÿœæ]+", re.IGNORECASE)


def _words(text: str) -> list[str]:
    from app.services.answer_acceptance import fold_typography

    return _WORD.findall(fold_typography(text).replace("'", " "))


def _subjects(text: str) -> Counter[str]:
    # «j'» is «je» elided: the same subject.
    return Counter("je" if word == "j" else word for word in _words(text) if word in _SUBJECTS)


def _negation(text: str) -> Counter[str]:
    words = _words(text)
    # «ne … plus» only: «plus» alone is a comparison.
    out = Counter(word for word in words if word in _NEGATION and word not in {"ne", "n"})
    if "ne" in words or "n" in words:
        out["ne"] += 1
        if "plus" in words:
            out["plus"] += 1
    return out


_LINKS = {"du": "de", "des": "de", "d": "de", "au": "à", "aux": "à", "qu": "que", "puisqu": "puisque", "lorsqu": "lorsque"}


@lru_cache(maxsize=4096)
def _parse(text: str) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """(finite tenses/moods, verb lemmas, noun/adjective/proper-noun lemmas, linking words) of ``text``."""

    from app.services.answer_acceptance import fold_all
    from app.services.french_nlp import french_nlp

    doc = french_nlp()(_ESTCEQUE.sub("", text))
    tenses: list[tuple[str, str]] = []
    verbs: list[str] = []
    content: list[str] = []
    links: list[str] = []
    for token in doc:
        if token.pos_ in {"SCONJ", "CCONJ", "ADP"}:
            word = fold_all(token.text).strip("'")
            links.append(_LINKS.get(word, word))
        morph = token.morph
        if token.pos_ in {"VERB", "AUX"} and "Fin" in morph.get("VerbForm"):
            tenses.append(("|".join(morph.get("Mood")), "|".join(morph.get("Tense"))))
        if token.pos_ == "VERB":
            verbs.append(_lemma(token.lemma_))
        elif token.pos_ in {"NOUN", "ADJ", "PROPN"}:
            content.append(_lemma(token.lemma_))
    return tuple(sorted(tenses)), tuple(sorted(verbs)), tuple(sorted(content)), tuple(sorted(links))


def _lemma(value: str) -> str:
    """A lemma with gender and number folded (professeure -> professeur, prête -> prêt)."""

    from app.services.answer_acceptance import fold_all

    word = fold_all(value)
    for ending in ("eures", "eure", "es", "e", "s"):
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[: len(word) - len(ending)] + ("eur" if ending.startswith("eure") else "")
    return word


def _same_lemmas(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    from app.services.spelling_variants import same_word_variant

    if left == right:
        return True
    if len(left) != len(right):
        return False
    rest = list(right)
    for word in left:
        match = next((other for other in rest if other == word or same_word_variant(word, other)), None)
        if match is None:
            return False
        rest.remove(match)
    return True


def _subjects_allowed(key: Counter[str], variant: Counter[str], shown: Counter[str] | None) -> str | None:
    """Only tu/vous (when the shown sentence does not say it) and on/nous may swap; il/elle and
    ils/elles are another subject («Elle est professeur.» is not «Il est professeur.»)."""

    if key == variant:
        return None
    removed, added = key - variant, variant - key
    if sum(removed.values()) != sum(added.values()):
        return "the subject changed"
    pairs = list(zip(sorted(removed.elements()), sorted(added.elements()), strict=True))
    for gone, new in pairs:
        pair = {gone, new}
        if pair in _SWAPS:
            if shown is not None and gone in shown and pair == {"tu", "vous"}:
                return f"the shown sentence already says «{gone}»"
            continue
        return f"the subject changed from «{gone}» to «{new}»"
    return None


def prefilter(item: Mapping[str, Any], variant: str) -> str | None:
    """Why ``variant`` is not a variant of ``item``'s key, or ``None`` when it may be one.

    Deterministic and conservative: it refuses only what the parse shows plainly (another
    subject, tense, mood, polarity or content word). What passes still needs the strict check.
    """

    key = str(item["key"])
    prompt = item.get("prompt") or {}
    shown_text = str(prompt.get("wrong_sentence") or prompt.get("line_with_blank") or "")
    shown = _subjects(shown_text) if shown_text else None
    reason = _subjects_allowed(_subjects(key), _subjects(variant), shown)
    if reason:
        return reason
    if _negation(key) != _negation(variant):
        return "the polarity changed (a negation was added or removed)"
    if " " not in key.strip() and " " not in variant.strip():
        from app.services.spelling_variants import same_word_variant

        if same_word_variant(key.casefold(), variant.casefold()) or _lemma(key) == _lemma(variant):
            return None
        return "another word"
    key, variant = _plain(key), _plain(_toward_key(key, variant))
    key_tenses, key_verbs, key_content, key_links = _parse(key)
    var_tenses, var_verbs, var_content, var_links = _parse(variant)
    if "?" in key or "?" in variant:
        # The parser misreads «est-ce que tu viens» and «viens-tu»: compare the words themselves.
        if not _same_lemmas(_question_words(key), _question_words(variant)):
            return "another word"
        return None
    if key_tenses and var_tenses and key_tenses != var_tenses:
        return "the tense or mood changed"
    if not _same_lemmas(key_verbs, var_verbs):
        return "another verb"
    if not _same_lemmas(key_content, var_content):
        return "another content word"
    if key_links != var_links:
        return "another linking word or preposition"
    return None


def _plain(text: str) -> str:
    """Commas and dashes out (optional punctuation), so they cannot change the parse."""

    return " ".join(re.sub(r"[,;:–—]", " ", text).split())


def _toward_key(key: str, variant: str) -> str:
    """The variant with each word spelled as the key spells it, when the two are one word in
    two accepted spellings («plait» -> «plaît»), so a spelling cannot change the parse."""

    from app.services.spelling_variants import same_word_variant

    key_words = key.split()
    out = []
    for word in variant.split():
        core = word.strip(".,;:!?«»\"()")
        match = next(
            (k.strip(".,;:!?«»\"()") for k in key_words if k.strip(".,;:!?«»\"()").casefold() != core.casefold()
             and core and same_word_variant(core.casefold(), k.strip(".,;:!?«»\"()").casefold())),
            None,
        )
        out.append(word.replace(core, match) if match else word)
    return " ".join(out)


_QUESTION_FRAME = frozenset({"est", "ce", "que", "qu", "t", *_SUBJECTS})


def _question_words(text: str) -> tuple[str, ...]:
    from app.services.answer_acceptance import fold_all

    return tuple(sorted(fold_all(word) for word in _words(text) if word not in _QUESTION_FRAME))
