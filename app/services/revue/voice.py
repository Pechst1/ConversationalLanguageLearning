"""La voix de Romy (WP-119 §10e, phase 6): deterministic checks on what the learner reads.

The real-model sample of 2026-10-03 failed natural French in 10/10 sessions for mechanical
reasons: dossier ids spoken to the learner («d'après c2»), telegraphic symbols at A1–A2
(«100→140 €»), orders to the learner («Dis-lui…»), guests offering services («Voulez-vous
que je…»), app words in the close («l'artefact»). Each is a pure function here; the
encounter decides what a hit leads to (regenerate once, then repair or fall back) and
logs the reason code:

=====================  ==========================================  =========================
reason code            check                                       repair after the retry
=====================  ==========================================  =========================
``id_leak``            :func:`id_leaks`                            :func:`strip_ids`, log ``revue_id_leak``
``symbols``            :func:`symbols` (A1–A2 only)                :func:`replace_symbols`
``imperative``         :func:`imperatives`                         :func:`drop_imperatives`
``service_offer``      :func:`is_service_offer` (guests)           the authored guest line
``app_words``          :func:`app_words` (close)                   the authored close template
=====================  ==========================================  =========================

:func:`french_typography` puts the space French wants before ``? ! : ;`` (cosmetic, no retry).
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Ids (claims c1, angles a1, uncertainties u1, «incert. 1», «incertitude 2»)
# ---------------------------------------------------------------------------

_ID = r"[cau]\d{1,2}"
#: One id or a list of them («c1», «c1,c2,c3», «c1 et c2», «c1/c2»).
_ID_LIST = rf"{_ID}(?:\s*(?:,|/|&|\bet\b|\band\b|\bund\b)\s*{_ID})*"
_UNCERTAINTY_TAG = r"incert(?:itude|\.)?\s*(?:n[°o]\s*)?\d+|incert\."
_LEAK = re.compile(rf"(?<![\w-])(?:{_ID})(?![\w-])|{_UNCERTAINTY_TAG}", re.IGNORECASE)
#: «(c1)», «(a1)», «(c1, c2)», «(incert. 1)», «[c2]», «(interprétation c3)» — the whole bracket.
_BRACKETED = re.compile(
    rf"\s*[(\[]\s*(?:[^()\[\]]{{0,20}}?\s)?(?:{_ID_LIST}|{_UNCERTAINTY_TAG})\s*[)\]]", re.IGNORECASE
)
#: «d'après c1,c2», «selon c3», «laut c2», «according to c2», «see c1» — the attribution goes with the id.
_ATTRIBUTED = re.compile(
    rf"(?:\b(?:d['’]apr[eè]s|selon|voir|cf\.?|laut|gemäß|according\s+to|see|per)\s+)(?:{_ID_LIST})(?![\w-])\s*,?\s*",
    re.IGNORECASE,
)
_BARE_LIST = re.compile(rf"(?<![\w-]){_ID_LIST}(?![\w-])", re.IGNORECASE)
_UPPER_ID = re.compile(r"[CAU]\d{1,2}")


def id_leaks(text: str | None) -> list[str]:
    """Every dossier id or uncertainty tag in ``text`` («c2», «a1», «u1», «incert. 1»,
    «incertitude 2»). Bare ids in upper case are not leaks (a CEFR «A1» or «B1»)."""

    return [m.group(0) for m in _LEAK.finditer(str(text or "")) if not _UPPER_ID.fullmatch(m.group(0))]


def strip_ids(text: str | None) -> str:
    """``text`` without ids: brackets holding only ids go, «d'après c1,c2, …» loses its
    attribution, bare ids and id lists go; spacing, punctuation and the sentence's first
    capital are repaired."""

    value = str(text or "")
    if not id_leaks(value):
        return value
    value = _BRACKETED.sub("", value)
    value = _ATTRIBUTED.sub("", value)
    value = re.sub(rf"(?<![\w-])(?:{_UNCERTAINTY_TAG})", "", value, flags=re.IGNORECASE)
    value = _BARE_LIST.sub(lambda m: m.group(0) if _UPPER_ID.fullmatch(m.group(0)) else "", value)
    return _tidy(value)


def _tidy(value: str) -> str:
    value = re.sub(r"[(\[]\s*[)\]]", "", value)
    value = re.sub(r"\s+([,.…])", r"\1", value)
    value = re.sub(r"([,;:])\s*([,.;:!?])", r"\2", value)
    value = re.sub(r"(^|[.!?…]\s+)[,;:]\s*", r"\1", value)
    value = re.sub(r"\s{2,}", " ", value).strip(" ,;")
    # A sentence that now starts with a lower-case letter gets its capital back.
    value = re.sub(r"(^|[.!?…]\s+)([a-zàâçéèêëîïôûùüÿœ])", lambda m: m.group(1) + m.group(2).upper(), value)
    return value


# ---------------------------------------------------------------------------
# Symbols (A1–A2): → ≈ ~ > < / ×
# ---------------------------------------------------------------------------

SYMBOLS: tuple[str, ...] = ("→", "≈", "~", ">", "<", "/", "×")
_SYMBOL = re.compile(r"[→≈~><×]|(?<!:)/(?!/)")
_URL = re.compile(r"https?://\S+")


def symbols(text: str | None) -> list[str]:
    """The telegraphic symbols in ``text`` (URLs ignored)."""

    return _SYMBOL.findall(_URL.sub(" ", str(text or "")))


def replace_symbols(text: str | None) -> str:
    """Words for the symbols: «100→140 €» → «de 100 à 140 €», «≈0,40 €» → «environ 0,40 €»,
    «>60 km/h» → «plus de 60 km par heure»."""

    parts = _URL.split(str(text or ""))
    urls = _URL.findall(str(text or ""))
    out = [_words_for_symbols(part) for part in parts]
    value = "".join(chunk + (urls[i] if i < len(urls) else "") for i, chunk in enumerate(out))
    return re.sub(r"\s{2,}", " ", value).strip()


def _words_for_symbols(value: str) -> str:
    value = re.sub(r"(\d[\d\s,.]*?)\s*→\s*(\d)", r"de \1 à \2", value)
    value = re.sub(r"\s*→\s*", " puis ", value)
    value = re.sub(r"[≈~]\s*", "environ ", value)
    value = re.sub(r">\s*", "plus de ", value)
    value = re.sub(r"<\s*", "moins de ", value)
    value = re.sub(r"\s*×\s*", " fois ", value)
    value = re.sub(r"\bkm/h\b", "km par heure", value)
    return re.sub(r"\s*/\s*", " par ", value)


# ---------------------------------------------------------------------------
# Orders to the learner
# ---------------------------------------------------------------------------

#: Sentence-initial imperatives addressed to the learner, as the sample found them («Dis-lui :»,
#: «Écris…», «Note…», «Répète…», «Propose la question…», «Précise que…», «Donne deux voix»).
#: «Dis-moi» is a question to the learner, not an order, and stays.
IMPERATIVES: tuple[str, ...] = ("dis", "ecris", "note", "repete", "propose", "precise", "donne", "explique")
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*[»”\"]?\s*")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).replace("’", "'").lower()


def _sentences(text: str) -> list[str]:
    return [chunk.strip() for chunk in _SENTENCE.findall(text or "") if chunk.strip()]


def _imperative(sentence: str) -> str | None:
    folded = _fold(sentence).lstrip(" «\"'(-—")
    match = re.match(r"([a-z]+)(-[a-z']+)?", folded)
    if not match or match.group(1) not in IMPERATIVES:
        return None
    if match.group(1) == "dis" and (match.group(2) or "").startswith("-moi"):
        return None
    rest = folded[match.end():]
    # «Note» / «Précise» as nouns or third-person verbs («Note bien que…» stays an order).
    if match.group(1) in {"note", "precise", "propose", "donne", "explique"} and rest[:1] not in {" ", ":", ","}:
        return None
    return sentence.split(" ", 1)[0]


def imperatives(text: str | None) -> list[str]:
    """Sentence-initial orders to the learner in ``text`` (the first word of each)."""

    return [hit for hit in (_imperative(s) for s in _sentences(str(text or ""))) if hit]


def drop_imperatives(text: str | None) -> str:
    return " ".join(s for s in _sentences(str(text or "")) if not _imperative(s))


# ---------------------------------------------------------------------------
# Guests: offers of service
# ---------------------------------------------------------------------------

_SERVICE = re.compile(
    r"\b(?:"
    r"(?:voulez|veux)[- ](?:vous|tu) que je"
    r"|(?:vous voulez|tu veux) que je"
    r"|souhait(?:ez|es)[- ](?:vous|tu)"
    r"|(?:vous|tu) souhait(?:ez|es)"
    r"|je (?:peux|pourrais|vais) (?:vous |te |t'|lui |leur )?(?:demander|chercher|verifier|montrer|aider|"
    r"trouver|appeler|envoyer|regarder|expliquer|rediger|preparer|noter|ecrire)"
    r"|(?:est-ce que )?je (?:vous|t')aide"
    r")",
)


def is_service_offer(text: str | None) -> bool:
    """A guest line that offers to do something for the learner or Romy («Voulez-vous que
    je…», «Tu veux que je cherche…», «Je peux demander…», «Souhaitez-vous…»)."""

    return bool(_SERVICE.search(_fold(str(text or "")).replace("’", "'")))


# ---------------------------------------------------------------------------
# The close: app words
# ---------------------------------------------------------------------------

#: Words of the app, not of the world. «état» only in lower case: «l'État» is a word of the news.
APP_WORDS: tuple[str, ...] = ("artefact", "artéfact", "session", "dossier", "état", "événement", "evenement")
_APP_WORD = re.compile(r"(?<![\w-])(" + "|".join(APP_WORDS) + r")s?(?![\w-])", re.IGNORECASE)


def app_words(text: str | None) -> list[str]:
    """App words in a line of the world («artefact», «session», «dossier», «état»,
    «événement»). «État» with its capital is the State, a word of the news, and stays."""

    hits = [m.group(1).lower() for m in _APP_WORD.finditer(str(text or "")) if not m.group(1).startswith(("É", "E"))
            or m.group(1).lower() not in {"état", "etat"}]
    return list(dict.fromkeys(hits))


#: Romy's replies: the app's machinery named in a line of the world («d'après le dossier», «tu l'as
#: sur l'écran», «ce qu'on a sur la table», «les éléments fournis»).
_META = re.compile(
    r"(?<![\w-])(dossiers?|artefacts?|sessions?|(?:sur |à )l'(?:é|e)cran|sur la table|les (?:é|e)l(?:é|e)ments"
    r"(?: fournis| sur la table)?|les infos sur la table)(?![\w-])",
    re.IGNORECASE,
)


def meta_words(text: str | None) -> list[str]:
    """The app's machinery in one of Romy's replies (a superset of :func:`app_words` without «état»)."""

    return [m.group(1).lower() for m in _META.finditer(str(text or "").replace("’", "'"))]


# ---------------------------------------------------------------------------
# Echo: Romy repeating the learner's line before answering
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def strip_echo(reply: str | None, learner: str | None) -> str:
    """``reply`` without a leading copy of the learner's line («Les fruits sont plus chers ?
    Oui. …» → «Oui. …»); unchanged when the learner's line has fewer than two words."""

    value = str(reply or "")
    said = [_fold(t) for t in _TOKEN.findall(str(learner or ""))]
    if len(said) < 2:
        return value
    tokens = list(_TOKEN.finditer(value))
    if len(tokens) <= len(said) or [_fold(t.group(0)) for t in tokens[: len(said)]] != said:
        return value
    rest = value[tokens[len(said) - 1].end():].lstrip(" ?!.,;:…»\"'")
    return _tidy(rest) if rest else value


# ---------------------------------------------------------------------------
# French typography
# ---------------------------------------------------------------------------


def french_typography(text: str | None) -> str:
    """A space before ``? ! ; :`` after a letter or a closing quote («en novembre?» → «en
    novembre ?», «Dis-lui:» → «Dis-lui :»). Digits, times and URLs are left alone."""

    value = str(text or "")
    if _URL.search(value):
        return value
    return re.sub(r"(?<=[^\W\d_]|[»)])([?!;:])", r" \1", value)


__all__ = [
    "APP_WORDS",
    "IMPERATIVES",
    "SYMBOLS",
    "app_words",
    "drop_imperatives",
    "french_typography",
    "id_leaks",
    "imperatives",
    "is_service_offer",
    "meta_words",
    "replace_symbols",
    "strip_echo",
    "strip_ids",
    "symbols",
]
