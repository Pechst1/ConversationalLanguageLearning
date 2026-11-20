"""P3 walk 2 (B1, day 5): a correction may not change the tense or mood of a clause the
sentence itself does not show to be wrong.

The learner wrote «Alors je lui dirai que Camille …» (a plan, right as written); the
scene's tutor changed it to «je lui ai dit», with a note about a reason «already given
to the agent». ``verify_edit`` settles the pair, because «je lui ai dit» is acceptable
French, and the learner was told her correct future was wrong.

:func:`unsupported_tense_change` reads the verb forms of the span and of the corrected
form. When a verb's tense or mood changes (future → passé composé, present →
subjunctive, passé composé → plus-que-parfait, …) the change stands only on evidence in
the learner's own sentence: an explicit time marker («hier», «demain», «déjà» with a
past beside it), the clause that governs the mood («j'ai peur que», «il faut que»,
«avant que»), «si» for the present of a condition, a past verb beside a present that
should be an imparfait, or the app's own model-free pass making the same fix. Without
it the correction is dropped: when in doubt, show nothing.

A form the module cannot read (no lemma, a table that does not hold it) has no tense,
so a pair it cannot read is never called a change: the check only ever removes a
correction it can prove changes a tense with nothing in the sentence asking for it.
Deterministic, no model, no database.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

PRESENT = "present"
IMPARFAIT = "imparfait"
FUTUR = "futur"
CONDITIONNEL = "conditionnel"
SUBJONCTIF = "subjonctif"
IMPERATIF = "imperatif"
PASSE_COMPOSE = "passe_compose"
PLUS_QUE_PARFAIT = "plus_que_parfait"

_TABLE_LABELS = {
    "present": PRESENT,
    "imparfait": IMPARFAIT,
    "futur_simple": FUTUR,
    "conditionnel_present": CONDITIONNEL,
    "subjonctif_present": SUBJONCTIF,
    "imperatif": IMPERATIF,
}
#: The auxiliary's own tense gives the compound tense its name.
_COMPOUND = {
    PRESENT: PASSE_COMPOSE,
    IMPARFAIT: PLUS_QUE_PARFAIT,
    FUTUR: FUTUR,  # futur antérieur: a future for the evidence it needs
    CONDITIONNEL: CONDITIONNEL,
    SUBJONCTIF: SUBJONCTIF,
}
#: Impersonal verbs the generated tables cannot conjugate.
_IMPERSONAL = {
    "pleut": PRESENT, "pleuvait": IMPARFAIT, "pleuvra": FUTUR, "pleuvrait": CONDITIONNEL, "pleuve": SUBJONCTIF,
    "faut": PRESENT, "fallait": IMPARFAIT, "faudra": FUTUR, "faudrait": CONDITIONNEL, "faille": SUBJONCTIF,
}
_AUX_LEMMAS = ("avoir", "être")
#: Words that may stand between an auxiliary and its participle («a déjà me proposé»).
_BETWEEN = frozenset(
    "ne n pas plus jamais rien déjà encore toujours bien mal vraiment aussi enfin souvent "
    "me m te t se s le la les l lui leur y en nous vous".split()
)
_PARTICIPLE_ENDINGS = (
    "é", "ée", "és", "ées", "i", "ie", "is", "ies", "u", "ue", "us", "ues", "it", "ite", "its", "ites",
    "ert", "erte", "erts", "ertes", "ort", "orte", "eint", "einte", "aint", "ainte",
)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_SENTENCE_END = re.compile(r"[.!?…]+")

#: Explicit past time («hier»), for a change to a past tense.
_PAST_MARKERS = re.compile(
    r"\b(?:hier|avant-hier|la veille|l'autre jour|autrefois|jadis|il y a|derni(?:er|ère|ers|ères)|"
    r"ce jour-là|à ce moment-là|ce matin|ce soir-là|tout à l'heure|la semaine passée|l'an passé)\b",
    re.IGNORECASE,
)
#: Anteriority («déjà», «avant»): the plus-que-parfait's own markers.
_ANTERIOR_MARKERS = re.compile(r"\b(?:déjà|avant|la veille|auparavant|plus tôt|jamais encore)\b", re.IGNORECASE)
_FUTURE_MARKERS = re.compile(
    r"\b(?:demain|après-demain|prochain|prochaine|prochains|prochaines|bientôt|plus tard|un jour|ce soir|"
    r"tout à l'heure|dans (?:un|une|deux|trois|quelques|\d+) \w+)\b",
    re.IGNORECASE,
)
_PRESENT_MARKERS = re.compile(
    r"\b(?:maintenant|aujourd'hui|en ce moment|d'habitude|chaque|tous les|toutes les|actuellement)\b",
    re.IGNORECASE,
)
_CONDITION = re.compile(r"\b(?:si|s'il|s'ils|au cas où|sinon|à ta place|à votre place)\b", re.IGNORECASE)
#: What governs a subjunctive, read in the few words before «que».
_SUBJUNCTIVE_TRIGGERS = frozenset(
    """
    faut faudrait fallait faudra faille veux veut voulons voulez veulent voudrais voudrait voudrions
    voudriez voudraient voulais voulait vouloir souhaite souhaites souhaitons souhaitez souhaitent
    souhaiterais souhaiterait préfère préfères préférons préférez préfèrent préférerais aime aimerais
    aimerait désire désires exige exiges exigent demande demandes ordonne peur crains craint craignons
    content contente contents contentes heureux heureuse triste dommage important importante
    nécessaire possible impossible normal bizarre étonnant étonnée étonné surpris surprise doute doutes
    avant pour afin sans moins pourvu quoique bien condition regrette regrettes attends attend
    jusqu'à ce essentiel urgent temps
    """.split()
)


def _fold(value: object) -> str:
    return unicodedata.normalize("NFC", str(value or "")).replace("’", "'").casefold()


def _words(value: object) -> list[str]:
    return _WORD.findall(_fold(value))


@lru_cache(maxsize=512)
def _table(lemma: str) -> dict[str, frozenset[str]]:
    from app.services.conjugation import fallback_conjugation_table

    try:
        table = fallback_conjugation_table(lemma)
    except Exception:  # pragma: no cover - a table is a hint, never a turn
        return {}
    out: dict[str, set[str]] = {}
    for key, label in _TABLE_LABELS.items():
        for form in (table.get(key) or {}).values():
            out.setdefault(_fold(form), set()).add(label)
    return {form: frozenset(labels) for form, labels in out.items()}


def _lemma(word: str) -> str | None:
    from app.services.correction_contract import _is_verb, _verb_lemma

    found = _verb_lemma(word)
    if found:
        return found
    # The future, the conditional and the imparfait of regular verbs the forms list lacks.
    for ending in ("raient", "rions", "riez", "rais", "rait", "rons", "rez", "ront", "rai", "ras", "ra"):
        if word.endswith(ending) and len(word) > len(ending) + 1:
            stem = word[: -len(ending)]
            for lemma in (_verb_lemma(stem), stem + "r" if _is_verb(stem + "r") else None):
                if lemma:
                    return lemma
    for ending in ("aient", "ais", "ait"):
        if word.endswith(ending) and len(word) > len(ending) + 1:
            stem = word[: -len(ending)]
            for suffix in ("er", "ir", "re"):
                if _is_verb(stem + suffix):
                    return stem + suffix
    return None


def _simple_labels(word: str) -> frozenset[str]:
    if word in _IMPERSONAL:
        return frozenset({_IMPERSONAL[word]})
    lemma = _lemma(word)
    if not lemma:
        return frozenset()
    labels = _table(lemma).get(word)
    if labels:
        return labels
    if word.endswith(("rais", "rait", "raient")):
        return frozenset({CONDITIONNEL})
    if word.endswith(("rai", "ras", "ra", "rons", "rez", "ront")):
        return frozenset({FUTUR})
    if word.endswith(("ais", "ait", "aient")):
        return frozenset({IMPARFAIT})
    return frozenset()


def _aux_labels(word: str) -> frozenset[str]:
    labels: set[str] = set()
    for lemma in _AUX_LEMMAS:
        labels |= _table(lemma).get(word, frozenset())
    return frozenset(labels - {IMPERATIF})


def _is_participle(word: str) -> bool:
    from app.services.conjugation import IRREGULAR_PAST_PARTICIPLES

    if word in {_fold(p) for p in IRREGULAR_PAST_PARTICIPLES.values()} or word in {"plu", "fallu", "été", "eu"}:
        return True
    return word.endswith(_PARTICIPLE_ENDINGS) and _lemma(word) is not None


def verb_units(phrase: object) -> list[tuple[int, int, frozenset[str]]]:
    """The finite verbs of ``phrase`` in order, as ``(first word, last word, tenses)``.

    An auxiliary with its participle is one unit with the compound tense («ai dit»:
    passé composé, «avait réservé»: plus-que-parfait). A word without a tense the
    tables can read is left out."""

    words = _words(phrase)
    units: list[tuple[int, int, frozenset[str]]] = []
    i = 0
    while i < len(words):
        word = words[i]
        aux = _aux_labels(word)
        if aux:
            j = i + 1
            while j < len(words) and words[j] in _BETWEEN and j - i <= 4:
                j += 1
            if j < len(words) and _is_participle(words[j]):
                units.append((i, j, frozenset(_COMPOUND[label] for label in aux if label in _COMPOUND)))
                i = j + 1
                continue
        labels = _simple_labels(word)
        if labels:
            units.append((i, i, labels))
        i += 1
    return units


def changed_tenses(span: object, corrected: object) -> list[tuple[frozenset[str], frozenset[str]]]:
    """Each verb whose tense or mood the correction changes, as ``(was, becomes)``.

    The verbs are paired in order; a pair whose readings share a tense is no change
    («trouve» can be a present or a subjunctive). Different verb counts: the whole
    span against the whole correction."""

    old, new = verb_units(span), verb_units(corrected)
    if not old or not new:
        return []
    if len(old) == len(new):
        pairs = [(a[2], b[2]) for a, b in zip(old, new, strict=True)]
    else:
        pairs = [(frozenset().union(*(u[2] for u in old)), frozenset().union(*(u[2] for u in new)))]
    return [(was, becomes) for was, becomes in pairs if was and becomes and not (was & becomes)]


def _sentence_around(text: str, span: str) -> tuple[str, int, int]:
    """The learner's sentence that holds ``span``, and the span's place in it."""

    at = text.find(span)
    if at < 0:
        folded = _fold(text)
        at = folded.find(_fold(span))
    if at < 0:
        return text, 0, 0
    start = 0
    for match in _SENTENCE_END.finditer(text, 0, at):
        start = match.end()
    end_match = _SENTENCE_END.search(text, at + len(span))
    end = end_match.end() if end_match else len(text)
    return text[start:end], at - start, at - start + len(span)


def _governs_subjunctive(before: str) -> bool:
    """«j'ai peur qu'», «il faut que», «avant que»: the clause in front asks for it."""

    words = _words(before)
    for index in range(len(words) - 1, -1, -1):
        if words[index] in ("que", "qu"):
            ahead = words[max(0, index - 4) : index]
            joined = " ".join(ahead)
            return any(w in _SUBJUNCTIVE_TRIGGERS for w in ahead) or "jusqu'à ce" in joined
    return False


def _has_past_verb(text: str) -> bool:
    return any(
        labels & {PASSE_COMPOSE, PLUS_QUE_PARFAIT, IMPARFAIT} and not labels & {PRESENT, FUTUR}
        for _a, _b, labels in verb_units(text)
    )


def _evidence(becomes: frozenset[str], was: frozenset[str], sentence: str, start: int, end: int) -> bool:
    outside = f"{sentence[:start]} … {sentence[end:]}"
    if SUBJONCTIF in becomes and _governs_subjunctive(sentence[: end]):
        return True
    anterior = {m.group(0).casefold() for m in _ANTERIOR_MARKERS.finditer(sentence)}
    if PLUS_QUE_PARFAIT in becomes and anterior and (
        # «Quand je suis arrivée, il avait déjà …», «Avant son offre, j'avais déjà …»
        _has_past_verb(outside) or _PAST_MARKERS.search(sentence) or len(anterior) > 1
    ):
        return True
    if IMPARFAIT in becomes and (_PAST_MARKERS.search(sentence) or _has_past_verb(outside)):
        return True
    if PASSE_COMPOSE in becomes and (
        _PAST_MARKERS.search(sentence)
        # A narrated present among past verbs; never a future or a conditional made past.
        or (PRESENT in was and _has_past_verb(outside))
    ):
        return True
    if FUTUR in becomes and _FUTURE_MARKERS.search(sentence):
        return True
    if PRESENT in becomes and (
        _CONDITION.search(sentence[:end]) or _PRESENT_MARKERS.search(sentence) or SUBJONCTIF in was
    ):
        return True
    if CONDITIONNEL in becomes and _CONDITION.search(sentence):
        return True
    return False


def _the_rules_make_it(text: str, span: str, corrected: str) -> bool:
    """The app's own model-free pass makes the same fix on these words."""

    from app.services.correction_contract import deterministic_edits

    try:
        edits = deterministic_edits(text)
    except Exception:  # pragma: no cover - a hint, never a turn
        return False
    at = text.find(span)
    if at < 0:
        return False
    fixed = _fold(text[:at] + corrected + text[at + len(span):])
    for edit in edits:
        if edit.start < at + len(span) and at < edit.end:
            if _fold(text[: edit.start] + edit.replacement + text[edit.end :]) == fixed:
                return True
    return False


def unsupported_tense_change(text: object, span: object, corrected: object) -> bool:
    """True when the correction changes a verb's tense or mood and nothing in the
    learner's sentence shows the original to be wrong: such a correction is dropped."""

    text, span, corrected = str(text or ""), str(span or ""), str(corrected or "")
    changes = changed_tenses(span, corrected)
    if not changes:
        return False
    if _the_rules_make_it(text, span, corrected):
        return False
    sentence, start, end = _sentence_around(text, span)
    return not all(_evidence(becomes, was, sentence, start, end) for was, becomes in changes)


__all__ = ["changed_tenses", "unsupported_tense_change", "verb_units"]
