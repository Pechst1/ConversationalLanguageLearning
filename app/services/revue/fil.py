"""«Le fil»: the wire desk (WP-119 «les rubriques», owner 2026-11-20).

The dispatches about one story came in out of order; the learner, Romy's trainee, puts them
back on the wire, gives each its sequence word («d'abord», «par la suite», «en fin de
compte») and tells the story in two sentences (the loop is ``fil_loop.py``; the dealer that
decides which story gets «Le fil» is ``assignments.py``).

This module writes what every learner shares: :class:`~app.services.revue.dossier.FilWire`,
one JSON call per story (:func:`write_fil`), modelled on the takes desk (``comptoir.py``) and
the lead desk (``leads.py``).

- The wire is four events of the story in TRUE chronological order, each told at A1 (≤ 9
  words), A2 (≤ 14) and B1 (≤ 22; B2 reads B1), with English and German, each grounded in a
  claim (``claim_id``). :func:`repair_fil` checks them with the comptoir's checks (no number or
  name the claims do not carry, no relative date, no id, no app word, French typography) and
  refuses the whole wire, never a part of it, when a strip fails: four events or none.
- The order must be justified from the claims: two neighbours are in order when both strips
  carry a date and the dates say so, or when the claims carry the words that say it («après le
  départ des commerçants»). Otherwise the wire is refused (``order:unjustified``).
- The sequence words are authored here (:data:`CONNECTORS`), not written by the model: the
  learner is graded on them, so they are always right.
- A story the comptoir would not argue about (a death, a war, a crime with victims, an
  election or a party's politics) gets no wire: the desk answers ``fit: "skip"`` and a row whose
  takes were skipped is never asked (:func:`ensure_fil`).
- :func:`ensure_fil` runs each morning after the takes (``app/tasks/revue.py``), once per
  kiosk row, only while ``REVUE_ASSIGNMENTS_ENABLED`` is on; an evergreen reads the wire shipped
  with it (``evergreen/fil/``).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from app.services.revue.comptoir import (
    RUDE_WORDS,  # noqa: F401 - the same words are refused here (through _Checker)
    _Checker,
    _lower_start,
    ci,
    contains,
    sentences,
)
from app.services.revue.dossier import (
    FIL_ROLES,
    ComptoirPhrase,
    ComptoirText,
    EditorialDossier,
    FilConnector,
    FilStrip,
    FilTelling,
    FilWire,
)

FIL_PROMPT_VERSION = "fil-wire-v1"

STRIP_MAX_WORDS: dict[str, int] = {"a1": 9, "a2": 14, "b1": 22}
LABEL_MAX_WORDS = 4
TILE_MAX_WORDS = 8
FRAME_MAX_WORDS = 7
PHRASE_MAX_WORDS = 10
TRANSLATION_MAX_CHARS = 400


def _t(fr: str, en: str, de: str) -> ComptoirText:
    return ComptoirText(fr=fr, en=en, de=de)


def _c(fr: str, en: str, de: str, role: str) -> FilConnector:
    return FilConnector(fr=fr, en=en, de=de, role=role)  # type: ignore[arg-type]


#: The sequence words per band, and where each fits (``first`` · ``middle`` · ``last``).
#: Authored, never the model's: the learner is graded on them. «Entre-temps» (meanwhile) is
#: left out: it says two events overlap, and the wire's four never do.
CONNECTORS: dict[str, list[FilConnector]] = {
    "a1": [
        _c("d'abord", "first", "zuerst", "first"),
        _c("ensuite", "next", "danach", "middle"),
        _c("puis", "then", "dann", "middle"),
        _c("enfin", "finally", "schließlich", "last"),
    ],
    "a2": [
        _c("d'abord", "first", "zuerst", "first"),
        _c("au début", "at the start", "am Anfang", "first"),
        _c("ensuite", "next", "danach", "middle"),
        _c("puis", "then", "dann", "middle"),
        _c("après", "after that", "nachher", "middle"),
        _c("enfin", "finally", "schließlich", "last"),
        _c("finalement", "in the end", "am Ende", "last"),
    ],
    "b1": [
        _c("tout d'abord", "first of all", "zunächst", "first"),
        _c("au départ", "at the outset", "anfangs", "first"),
        _c("par la suite", "later on", "in der Folge", "middle"),
        _c("ensuite", "next", "danach", "middle"),
        _c("puis", "then", "dann", "middle"),
        _c("en fin de compte", "in the end", "letzten Endes", "last"),
        _c("pour finir", "to finish", "zum Schluss", "last"),
        _c("finalement", "in the end", "am Ende", "last"),
    ],
}

AUTHORED_PHRASE = ComptoirPhrase(
    a1=_t("D'abord…, ensuite…", "First…, next…", "Zuerst…, danach…"),
    a2=_t("D'abord…, puis…, enfin…", "First…, then…, finally…", "Zuerst…, dann…, schließlich…"),
    b1=_t("Tout d'abord…, par la suite…, en fin de compte…", "First of all…, later on…, in the end…",
          "Zunächst…, in der Folge…, letzten Endes…"),
    b2=_t("Une fois que…, …", "Once…, …", "Sobald…, …"),
)
AUTHORED_FRAMES: list[ComptoirText] = [
    _t("D'abord,", "First,", "Zuerst,"),
    _t("Ensuite,", "Next,", "Danach,"),
]

#: Words that say an order: never inside a strip (the order step would give itself away),
#: and what a claim's own words must carry to justify one.
SEQUENCE_WORDS: tuple[str, ...] = (
    "d'abord", "tout d'abord", "ensuite", "puis", "enfin", "apres", "apres que", "avant", "avant de",
    "finalement", "plus tard", "le lendemain", "la veille", "une fois", "par la suite", "au depart",
    "au debut", "a la fin", "pour finir", "en fin de compte", "entre-temps", "desormais", "deja", "bientot",
    "a la suite", "suite a", "des que", "jusqu'a", "jusqu'en", "depuis", "a partir de", "pour la premiere fois",
    "d'ici", "dans un second temps", "premier", "premiere", "dernier", "derniere",
)
#: The ones a strip may never carry (the others — «depuis 1570», «la première édition» — are facts).
_STRIP_FORBIDDEN: tuple[str, ...] = (
    "d'abord", "ensuite", "puis", "enfin", "apres", "avant", "finalement", "plus tard", "le lendemain",
    "la veille", "une fois", "par la suite", "au depart", "au debut", "a la fin", "pour finir",
    "en fin de compte", "entre-temps", "dans un second temps",
)

# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

FIL_SPEC = """{"fit": "wire" | "skip",
 "strips": [{"claim_id": str, "a1": T, "a2": T, "b1": T, "label": T, "tile": T}, ×4],
 "basis": [str, str, str],
 "frames": [T, T],
 "phrase": {"a1": T, "a2": T, "b1": T, "b2": T}}
where T = {"fr": str, "en": str, "de": str} (en and de translate the French faithfully, every time)"""

FIL_RULES = """RULES
- fit: "skip" when the story is a death, a war, a crime with victims, an election or a party's politics, or
  anything where retelling it as a game would be cruel; also when the claims do not hold FOUR events whose order
  they state. Otherwise "wire".
- strips: exactly four EVENTS of the story (something happened, someone did something), in TRUE chronological
  order, the first first. Each one comes from ONE claim (claim_id) and says only what that claim says.
  a1: one present-tense sentence, 9 words at most, the most common words. a2: 14 words at most. b1: 22 words at
  most. Never a sequence word inside a strip (no «d'abord», «ensuite», «puis», «enfin», «après», «avant»,
  «finalement», «une fois», «plus tard»): the learner adds them. Dates are welcome when the claim gives them.
  label: what the event is called in two or three words with its article («l'annonce», «le vote», «la
  réouverture»), so one can say «le vote vient après l'annonce». tile: the a1 event as it reads after «d'abord,»:
  lower-case start unless a name, no final full stop, 8 words at most.
- basis: for each pair of neighbours (1→2, 2→3, 3→4), why the second comes after the first: "date" when both
  strips carry a date from the claims and the dates say so; otherwise the claims' own words that say it, copied
  word for word from a claim («Après le départ des commerçants», «Une fois les travaux finis»). If a pair has
  neither, the order is a guess: answer "skip".
- Facts: only what the claims say. Numbers in digits, copied exactly from the claims; no other number, no name the
  claims do not carry. Never a relative date (demain, hier, aujourd'hui, ce soir, cette semaine) nor a weekday the
  claims do not name. Never about the app: never «dossier», «session», «application», «événement».
- frames: the A2 retelling's two openings, each a sequence word and the subject of one event («D'abord, la
  mairie», «Enfin, le marché»), 6 words at most; the learner writes the rest of each sentence.
- phrase: the sequence pattern of each band (a1 «D'abord…, ensuite…», a2 «D'abord…, puis…, enfin…», b1 «Tout
  d'abord…, par la suite…, en fin de compte…», b2 «Une fois que…, …»).
- French typography: a space before ? ! : ;
EXAMPLE (story: the covered market Beauvau reopens after works; claims c1 «Le 3 mars, la mairie du 12e
arrondissement annonce des travaux au marché Beauvau.», c2 «Le 10 mars, les commerçants quittent le marché couvert
et s'installent sur la place d'Aligre.», c3 «Après le départ des commerçants, les ouvriers changent le toit du
marché.», c4 «Une fois les travaux finis, le marché Beauvau rouvre le 14 novembre.»):
{"fit": "wire",
 "strips": [
  {"claim_id": "c1",
   "a1": {"fr": "La mairie annonce des travaux au marché Beauvau.", "en": "The town hall announces works at the Beauvau market.", "de": "Das Rathaus kündigt Arbeiten am Markt Beauvau an."},
   "a2": {"fr": "Le 3 mars, la mairie du 12e annonce des travaux au marché Beauvau.", "en": "On 3 March, the 12th district town hall announces works at the Beauvau market.", "de": "Am 3. März kündigt das Rathaus des 12. Bezirks Arbeiten am Markt Beauvau an."},
   "b1": {"fr": "Le 3 mars, la mairie du 12e arrondissement annonce des travaux au marché couvert Beauvau.", "en": "On 3 March, the town hall of the 12th arrondissement announces works at the Beauvau covered market.", "de": "Am 3. März kündigt das Rathaus des 12. Arrondissements Arbeiten an der Markthalle Beauvau an."},
   "label": {"fr": "l'annonce", "en": "the announcement", "de": "die Ankündigung"},
   "tile": {"fr": "la mairie annonce des travaux", "en": "the town hall announces works", "de": "das Rathaus kündigt Arbeiten an"}},
  {"claim_id": "c2",
   "a1": {"fr": "Les commerçants quittent le marché.", "en": "The traders leave the market.", "de": "Die Händler verlassen den Markt."},
   "a2": {"fr": "Le 10 mars, les commerçants quittent le marché couvert.", "en": "On 10 March, the traders leave the covered market.", "de": "Am 10. März verlassen die Händler die Markthalle."},
   "b1": {"fr": "Le 10 mars, les commerçants quittent le marché couvert et s'installent sur la place d'Aligre.", "en": "On 10 March, the traders leave the covered market and set up on the Place d'Aligre.", "de": "Am 10. März verlassen die Händler die Markthalle und ziehen auf die Place d'Aligre."},
   "label": {"fr": "le départ", "en": "the move out", "de": "der Auszug"},
   "tile": {"fr": "les commerçants quittent le marché", "en": "the traders leave the market", "de": "die Händler verlassen den Markt"}},
  {"claim_id": "c3",
   "a1": {"fr": "Les ouvriers changent le toit.", "en": "The workers change the roof.", "de": "Die Arbeiter erneuern das Dach."},
   "a2": {"fr": "Les ouvriers changent le toit du marché couvert.", "en": "The workers change the roof of the covered market.", "de": "Die Arbeiter erneuern das Dach der Markthalle."},
   "b1": {"fr": "Dans le marché vide, les ouvriers changent le toit du bâtiment.", "en": "In the empty market, the workers change the building's roof.", "de": "In der leeren Halle erneuern die Arbeiter das Dach des Gebäudes."},
   "label": {"fr": "le nouveau toit", "en": "the new roof", "de": "das neue Dach"},
   "tile": {"fr": "les ouvriers changent le toit", "en": "the workers change the roof", "de": "die Arbeiter erneuern das Dach"}},
  {"claim_id": "c4",
   "a1": {"fr": "Le marché rouvre le 14 novembre.", "en": "The market reopens on 14 November.", "de": "Der Markt öffnet am 14. November wieder."},
   "a2": {"fr": "Le marché Beauvau rouvre ses portes le 14 novembre.", "en": "The Beauvau market opens its doors again on 14 November.", "de": "Der Markt Beauvau öffnet am 14. November wieder seine Türen."},
   "b1": {"fr": "Le 14 novembre, le marché Beauvau rouvre ses portes aux habitants du quartier.", "en": "On 14 November, the Beauvau market opens its doors again to the people of the neighbourhood.", "de": "Am 14. November öffnet der Markt Beauvau wieder seine Türen für die Leute aus dem Viertel."},
   "label": {"fr": "la réouverture", "en": "the reopening", "de": "die Wiedereröffnung"},
   "tile": {"fr": "le marché rouvre le 14 novembre", "en": "the market reopens on 14 November", "de": "der Markt öffnet am 14. November wieder"}}],
 "basis": ["date", "Après le départ des commerçants", "Une fois les travaux finis"],
 "frames": [{"fr": "D'abord, la mairie", "en": "First, the town hall", "de": "Zuerst das Rathaus"},
  {"fr": "Enfin, le marché", "en": "Finally, the market", "de": "Schließlich der Markt"}],
 "phrase": {"a1": {"fr": "D'abord…, ensuite…", "en": "First…, next…", "de": "Zuerst…, danach…"},
  "a2": {"fr": "D'abord…, puis…, enfin…", "en": "First…, then…, finally…", "de": "Zuerst…, dann…, schließlich…"},
  "b1": {"fr": "Tout d'abord…, par la suite…, en fin de compte…", "en": "First of all…, later on…, in the end…", "de": "Zunächst…, in der Folge…, letzten Endes…"},
  "b2": {"fr": "Une fois que…, …", "en": "Once…, …", "de": "Sobald…, …"}}}
Do not reuse the example's lines: write for THIS story."""

FIL_DESK_INSTRUCTIONS = (
    """You write «Le fil» for «Le Papier de Romy», a French-learning app. The learner is the trainee of Romy, a
Québécoise journalist; the dispatches about one news story came in out of order, and the learner puts them back
on the wire, adds the sequence words and retells the story. From INPUT (the story's French facts) answer with ONE
JSON object:
"""
    + FIL_SPEC
    + "\n"
    + FIL_RULES
)
DESK_SYSTEM = "You write plain, correct, factual French for language learners. Answer with one JSON object only."

# ---------------------------------------------------------------------------
# Dates and order
# ---------------------------------------------------------------------------

_MONTHS = ("janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre",
           "novembre", "decembre")
_MONTH = "|".join(_MONTHS)
_DATE = re.compile(
    rf"(?<![\w-])(?:(?P<day>1er|\d{{1,2}})\s+(?P<dmonth>{_MONTH})(?:\s+(?P<dyear>\d{{4}}))?"
    rf"|(?P<month>{_MONTH})(?:\s+(?P<myear>\d{{4}}))?"
    rf"|(?P<year>1[0-9]\d\d|20\d\d))(?![\w-])"
)


def when(text: str | None) -> tuple[int | None, int | None, int | None] | None:
    """The first date ``text`` names, as ``(year, month, day)`` with ``None`` for what it does
    not say («le 3 mars» → ``(None, 3, 3)``, «en 1982» → ``(1982, None, None)``)."""

    match = _DATE.search(ci(text))
    if match is None:
        return None
    if match.group("dmonth"):
        day = 1 if match.group("day") == "1er" else int(match.group("day"))
        year = int(match.group("dyear")) if match.group("dyear") else None
        return year, _MONTHS.index(match.group("dmonth")) + 1, day
    if match.group("month"):
        year = int(match.group("myear")) if match.group("myear") else None
        return year, _MONTHS.index(match.group("month")) + 1, None
    return int(match.group("year")), None, None


def date_order(a: tuple | None, b: tuple | None) -> int | None:
    """``-1`` when ``a`` is surely before ``b``, ``1`` when surely after, ``0`` when the dates
    say the same day, ``None`` when they cannot be compared (one year against a month with
    no year, a month against the same month…)."""

    if a is None or b is None:
        return None
    (ya, ma, da), (yb, mb, db) = a, b
    if ya is not None and yb is not None and ya != yb:
        return -1 if ya < yb else 1
    if (ya is None) != (yb is None):
        return None
    if ma is None or mb is None:
        return 0 if ma is None and mb is None else None
    if ma != mb:
        return -1 if ma < mb else 1
    if da is None or db is None:
        return 0 if da is None and db is None else None
    return (da > db) - (da < db)


def strip_date(strip: FilStrip) -> tuple | None:
    """The date a strip carries (its most detailed telling first)."""

    for band in ("b1", "a2", "a1"):
        found = when(strip.for_band(band).fr)
        if found is not None:
            return found
    return None


def _has_sequence_word(text: str, words: tuple[str, ...]) -> str | None:
    folded = f" {ci(text)} "
    return next((word for word in words if re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", folded)), None)


def order_problem(strips: list[FilStrip], basis: list[Any], dossier: EditorialDossier) -> str | None:
    """Why the order of ``strips`` cannot be justified from the claims, or ``None``: for each
    pair of neighbours, their dates say the second comes after, or a claim of the pair carries
    the words that say it (``basis``, verbatim, with a sequence word). Dates that disagree
    refuse the pair whatever the words say."""

    claims = dossier.claims_by_id()
    for index in range(3):
        first, second = strips[index], strips[index + 1]
        dated = date_order(strip_date(first), strip_date(second))
        if dated is not None and dated > 0:
            return f"order:dates_disagree:{index + 1}"
        if dated == -1:
            continue
        cue = re.sub(r"\s+", " ", str(basis[index] if index < len(basis) else "")).strip(" .,«»")
        texts = [claims[s.claim_id].fr for s in (first, second) if s.claim_id in claims]
        if (cue and ci(cue) != "date" and any(contains(text, cue) for text in texts)
                and _has_sequence_word(cue, SEQUENCE_WORDS)):
            continue
        return f"order:unjustified:{index + 1}"
    return None


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

_STOP = frozenset("""
    le la les l un une des de du d au aux a en dans sur par pour et ou est sont c ce cette ces qui que qu il elle
    ils elles on se s sa son ses leur leurs avec sans plus moins tres pas ne n y
""".split())


def _content(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", ci(text)) if len(w) >= 4 and w not in _STOP}


def _stems(words: set[str]) -> set[str]:
    return {w[:5] for w in words}


def new_names(fr: str, story: str) -> list[str]:
    """Capitalised words inside a sentence that the story does not carry (a name the claims
    do not give)."""

    known = set(re.findall(r"[a-z0-9]+", ci(story)))
    found = []
    for sentence in sentences(fr):
        for index, token in enumerate(re.findall(r"[^\W\d_]+", sentence)):
            if index > 0 and token[:1].isupper() and ci(token) not in known:
                found.append(token)
    return found


def _text(check: _Checker, row: Any, limit: int, *, need_translations: bool) -> tuple[ComptoirText | None, str | None]:
    if isinstance(row, str):
        row = {"fr": row}
    if not isinstance(row, dict):
        return None, "missing"
    text, why = check.text(row, limit)
    if text is None:
        return None, why
    if new_names(text.fr, check.story):
        return None, "name_not_in_claims"
    if need_translations and not (text.en and text.de):
        return None, "translation_missing"
    return ComptoirText(fr=text.fr, en=(text.en or "")[:TRANSLATION_MAX_CHARS] or None,
                        de=(text.de or "")[:TRANSLATION_MAX_CHARS] or None), None


def _tile_from(strip_fr: str) -> str:
    first = (sentences(strip_fr) or [strip_fr])[0]
    return _lower_start(first.strip().rstrip(" .!…"))


def repair_fil(raw: Any, dossier: EditorialDossier) -> tuple[FilWire | None, list[str]]:
    """What the wire desk wrote, checked against ``dossier``. ``(None, ["skip"])`` for a story
    the desk judged unfit; ``(None, problems)`` when the wire is refused (a strip fails, the
    order cannot be justified); else the wire and what fell back to authored lines."""

    if not isinstance(raw, dict):
        return None, ["fil:missing"]
    if str(raw.get("fit") or "").strip().lower() == "skip":
        return None, ["skip"]
    rows = raw.get("strips")
    if not isinstance(rows, list) or len(rows) != 4:
        return None, ["fil:strips:count"]
    check = _Checker(dossier)
    claims = dossier.claims_by_id()
    refusals: list[str] = []
    problems: list[str] = []
    strips: list[FilStrip] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            refusals.append(f"fil:{index}:missing")
            continue
        claim_id = str(row.get("claim_id") or "").strip()
        claim = claims.get(claim_id)
        if claim is None:
            refusals.append(f"fil:{index}:claim_unknown")
            continue
        texts: dict[str, ComptoirText] = {}
        for band, limit in STRIP_MAX_WORDS.items():
            text, why = _text(check, row.get(band), limit, need_translations=True)
            if text is not None and _has_sequence_word(text.fr, _STRIP_FORBIDDEN):
                why = "sequence_word"
            if text is not None and not (_stems(_content(text.fr)) & _stems(_content(claim.fr))):
                why = "ungrounded"
            if why:
                refusals.append(f"fil:{index}:{band}:{why}")
                continue
            texts[band] = text  # type: ignore[assignment]
        if len(texts) < 3:
            continue
        label, why = _text(check, row.get("label"), LABEL_MAX_WORDS, need_translations=True)
        if label is None:
            problems.append(f"fil:{index}:label:{why}")
        tile_row = row.get("tile")
        if isinstance(tile_row, dict):
            tile_row = {**tile_row, "fr": _tile_from(str(tile_row.get("fr") or ""))}
        tile, why = _text(check, tile_row, TILE_MAX_WORDS, need_translations=True)
        if tile is not None and _has_sequence_word(tile.fr, _STRIP_FORBIDDEN):
            tile, why = None, "sequence_word"
        if tile is None:
            problems.append(f"fil:{index}:tile:{why}")
            a1 = texts["a1"]
            tile = ComptoirText(fr=_tile_from(a1.fr), en=_tile_from(a1.en or "") or None,
                                de=_tile_from(a1.de or "") or None)
        strips.append(FilStrip(claim_id=claim_id, label=label, tile=tile, **texts))
    if refusals:
        return None, [*refusals, *problems]
    if len({ci(s.a1.fr) for s in strips}) < 4 or len({ci(s.b1.fr) for s in strips}) < 4:
        return None, ["fil:strips:duplicate", *problems]
    basis = raw.get("basis") if isinstance(raw.get("basis"), list) else []
    why = order_problem(strips, basis, dossier)
    if why:
        return None, [why, *problems]

    frames: list[ComptoirText] = []
    raw_frames = raw.get("frames") if isinstance(raw.get("frames"), list) else []
    for index, row in enumerate(raw_frames[:2]):
        text, why = _text(check, row, FRAME_MAX_WORDS, need_translations=True)
        if text is not None:
            text = ComptoirText(fr=text.fr.rstrip(" .…"), en=text.en, de=text.de)
            if not any(ci(text.fr).startswith(ci(c.fr)) for c in CONNECTORS["a2"]):
                why = "no_sequence_word"
        if why:
            problems.append(f"fil:frame:{index}:{why}")
            continue
        frames.append(text)  # type: ignore[arg-type]
    if len(frames) != 2:
        problems.append("fil:frames:authored")
        frames = [f.model_copy() for f in AUTHORED_FRAMES]

    phrase: dict[str, ComptoirText] = {}
    raw_phrase = raw.get("phrase") if isinstance(raw.get("phrase"), dict) else {}
    for band in ("a1", "a2", "b1", "b2"):
        text, why = check.text(raw_phrase.get(band), PHRASE_MAX_WORDS)
        if text is None:
            problems.append(f"fil:phrase:{band}:{why}")
        phrase[band] = text or getattr(AUTHORED_PHRASE, band)

    wire = FilWire(
        strips=strips,
        connectors={band: [c.model_copy() for c in rows] for band, rows in CONNECTORS.items()},  # type: ignore[misc]
        telling=FilTelling(frames=frames, phrase=ComptoirPhrase(**phrase)),
        basis=[str(b) for b in basis[:3]],
    )
    return wire, problems


def as_desk_answer(wire: FilWire) -> dict[str, Any]:
    """``wire`` in the desk's answer shape, so :func:`audit` runs the same checks on stored or
    hand-written wires (the evergreens' files, the tests)."""

    data = wire.model_dump(mode="json")
    return {"fit": "wire", "strips": data["strips"], "basis": data["basis"], "frames": data["telling"]["frames"],
            "phrase": data["telling"]["phrase"]}


def audit(wire: FilWire, dossier: EditorialDossier) -> list[str]:
    """Every check :func:`repair_fil` would make on ``wire``: ``[]`` when nothing would change."""

    repaired, problems = repair_fil(as_desk_answer(wire), dossier)
    return problems if repaired is not None else problems or ["fil:refused"]


def role_of(position: int) -> str:
    """Where position ``position`` (0–3) sits on the wire: first, middle or last."""

    return FIL_ROLES[position]


# ---------------------------------------------------------------------------
# The desk
# ---------------------------------------------------------------------------


def desk_payload(dossier: EditorialDossier) -> dict[str, Any]:
    """What the wire desk reads: the story's French (never its sources' text)."""

    return {
        "title_fr": dossier.title_fr,
        "summary_fr": dossier.summary_fr,
        "claims": [{"id": c.id, "kind": c.kind, "fr": c.fr, "attributed_to": c.attributed_to} for c in dossier.claims],
        "topic": dossier.topic,
        "happening": dossier.time_scope.happening,
    }


def desk_provider() -> Any:
    """The Revue's own provider and model, with room for the four strips in three languages."""

    from app.services.revue.encounter import (
        OpenAIRevueProvider,  # noqa: PLC0415 - encounter imports the desks
    )

    return OpenAIRevueProvider(name="openai-revue-fil-desk", max_tokens=4000)


def write_fil(dossier: EditorialDossier, provider: Any = None) -> tuple[FilWire | None, list[str]]:
    """The wire desk: one JSON call (a second with the problems when the first was refused),
    checked by :func:`repair_fil`. ``(None, ["skip"])`` for an unfit story; ``(None,
    problems)`` when nothing passes or the call fails."""

    from app.services.revue import (
        rubriques,  # noqa: PLC0415 - rubriques reads the comptoir like this module
    )

    provider = provider if provider is not None else desk_provider()
    payload = desk_payload(dossier)
    problems: list[str] = []
    raw: Any = None
    for attempt in range(2):
        ask = payload if attempt == 0 else {**payload, "retry_feedback": rubriques.retry_feedback(problems, raw)}
        try:
            raw = provider.ask_json(FIL_DESK_INSTRUCTIONS, ask, system=DESK_SYSTEM, temperature=0.4, label="write_fil")
        except Exception as exc:  # noqa: BLE001 - the story carries another assignment
            logger.bind(dossier=dossier.id).warning("revue fil desk failed ({})", exc)
            return None, ["fil:desk_failed"]
        wire, problems = repair_fil(raw, dossier)
        if problems == ["skip"]:
            return None, problems
        if wire is not None:
            model = getattr(provider, "model", None) or ""
            return wire.model_copy(update={"model": str(model), "written_at": datetime.now(UTC),
                                           "prompt_version": FIL_PROMPT_VERSION}), problems
    return None, problems


def ensure_fil(db: Any, period: str, *, provider: Any = None) -> list[str]:
    """Give every dossier in ``period``'s kiosk without a wire a try at the wire desk, once
    (``checks["fil"]`` records a refusal or ``"skip"``); a row whose takes the comptoir skipped
    (a sensitive story) is skipped too, without a call; an evergreen reads the wire shipped
    with it, or none. Returns the ids that got a wire."""

    from app.services.revue.comptoir import _kiosk_rows  # noqa: PLC0415
    from app.services.revue.evergreen import evergreen_wire  # noqa: PLC0415

    done: list[str] = []
    changed = False
    for row in _kiosk_rows(db, period):
        if (row.payload or {}).get("fil") or (row.checks or {}).get("fil"):
            continue
        try:
            dossier = EditorialDossier.model_validate(row.payload)
        except Exception as exc:  # noqa: BLE001 - an unreadable row is left to the kiosk's own guard
            logger.bind(row=row.id).debug("revue fil: stored dossier unreadable ({})", exc)
            continue
        changed = True
        if (row.checks or {}).get("comptoir") == "skip":
            row.checks = {**(row.checks or {}), "fil": "skip"}
            continue
        if dossier.evergreen:
            wire, problems = evergreen_wire(dossier.id), ["fil:evergreen_without_wire"]
        else:
            wire, problems = write_fil(dossier, provider)
        if wire is None:
            if problems == ["fil:desk_failed"]:
                continue  # asked again tomorrow
            row.checks = {**(row.checks or {}), "fil": "skip" if problems == ["skip"] else ",".join(problems) or "refused"}
            logger.bind(dossier=dossier.id, problems=problems).info("revue fil: no wire")
            continue
        row.payload = {**row.payload, "fil": wire.model_dump(mode="json")}
        done.append(dossier.id)
    if changed:
        db.commit()
    return done


def fil_enabled() -> bool:
    from app.config import settings

    return bool(getattr(settings, "REVUE_ENABLED", False) and getattr(settings, "REVUE_ASSIGNMENTS_ENABLED", False))


def wire_of(dossier: EditorialDossier) -> FilWire | None:
    """The wire a session on ``dossier`` plays: the dossier's own, else the evergreen's shipped one."""

    if dossier.fil is not None:
        return dossier.fil
    if dossier.evergreen:
        from app.services.revue.evergreen import evergreen_wire  # noqa: PLC0415

        return evergreen_wire(dossier.id)
    return None


__all__ = [
    "CONNECTORS",
    "FIL_DESK_INSTRUCTIONS",
    "FIL_PROMPT_VERSION",
    "audit",
    "date_order",
    "ensure_fil",
    "fil_enabled",
    "order_problem",
    "repair_fil",
    "role_of",
    "when",
    "wire_of",
    "write_fil",
]
