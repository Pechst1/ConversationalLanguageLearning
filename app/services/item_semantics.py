"""WP-S5 — naturalness of La Forge's templated sentences.

The item bank (:mod:`app.services.item_bank`) fills template slots from a small
lexicon. Grammar alone lets it write «Il y a une carotte au théâtre» or «Hier,
vous avez nagé le dimanche»: correct French nobody says. This module holds the
*semantic* side of the bank, used twice:

* **at the source** — :func:`compatible` filters slot candidates against what
  is already bound (a carrot belongs to the market or the kitchen, a price
  fits the thing, «tard» cannot go with «ce matin»), so bad combinations are
  not generated in the first place;
* **as a checker** — :func:`violations` reads a finished item (its bindings and
  its sentences) and names every broken constraint. The bank rejects such an
  item as a last line of defence, and a test proves that a seeded sample of
  every A1–A2 unit is clean and that the source constraints, not the rejection,
  do the work.

The annotations live in the lexicon (``lexicon.json``): noun domains (``dom``),
what a place holds (``holds``) and what happens there (``use``: ``at_*``),
prices, capacities, adjective domains (``kinds``), verb aspect tags (stative,
mishap, oneoff, habit), where a verb happens (``at``), how long (``dur``) and
its part of day (``daypart``). Time expressions are classified from their text
(:func:`time_marks`), the same way for a lexicon entry, a frame's literal words
and a finished sentence.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# --------------------------------------------------------------------------- #
# Time expressions
# --------------------------------------------------------------------------- #

_WEEKDAYS = r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)"
_HOURS = r"(?:une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze)"

#: (category, pattern). A category may match several times in one text.
_TIME_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("now", re.compile(r"\ben train d[e']|\bv(?:ien|en)\w* d(?:e |')(?:\w+(?:er|ir|re)|s'|se |me |m'|te |t'|nous |vous )")),
    ("clock", re.compile(rf"\b(?:à|vers|jusqu'à|est)\s+(?:{_HOURS}\s+heures?|midi|minuit)\b")),
    ("span", re.compile(
        r"\b(?:depuis|pendant|dans|il y a)\s+(?:\w+(?:-\w+)?\s+)?(?:minutes?|heures?|jours?|semaines?|mois|ans?)\b"
        r"|\btout(?:e)? (?:la nuit|la journée|la soirée|le week-end)\b"
        rf"|(?<!à )(?<!vers )(?<!est )\b{_HOURS} heures\b(?! (?:et|moins))"
    )),
    ("day", re.compile(
        r"\b(?:demain|hier|avant-hier|aujourd'hui|cette semaine|ce week-end|cet été|l'été dernier"
        r"|la semaine (?:prochaine|dernière))\b"
        rf"|(?<!le )(?<!les )(?<!tous les )\b{_WEEKDAYS}\b(?! soir\b)(?:\s+(?:prochain|dernier))?"
    )),
    ("part", re.compile(r"\b(?:ce soir|ce matin|hier soir|demain matin|cette nuit|après le travail)\b")),
    ("freq", re.compile(
        rf"\b(?:le|les|tous les|toutes les)\s+(?:{_WEEKDAYS}s?(?: soirs?)?|soirs?|matins?|week-ends?|jours|semaines|étés|mois)\b"
        r"|\b(?:une|deux|trois) fois par\b"
    )),
    ("habit", re.compile(r"(?:^|[.!?]\s*)(?:avant|autrefois|à l'époque|enfant|à vingt ans|d'habitude|tous les étés)\s*,")),
    ("rel", re.compile(r"\b(?:tôt|tard|en retard)\b")),
)
_MORNING = re.compile(r"\bmatins?\b")
_EVENING = re.compile(r"\b(?:soirs?|soirée|nuit|minuit)\b")

#: Two marks of these categories never share one sentence.
TIME_CONFLICTS: frozenset[frozenset[str]] = frozenset(
    frozenset(pair)
    for pair in (
        ("day", "day"), ("part", "part"), ("clock", "clock"), ("freq", "freq"), ("span", "span"),
        ("habit", "habit"), ("rel", "rel"), ("now", "now"),
        ("freq", "day"), ("freq", "part"), ("part", "clock"), ("habit", "day"), ("habit", "part"),
        ("span", "clock"), ("span", "day"), ("span", "part"), ("span", "rel"),
        ("now", "day"), ("now", "part"), ("now", "clock"), ("now", "freq"), ("now", "span"),
        ("now", "rel"), ("now", "habit"),
    )
)


def fold(text: Any) -> str:
    value = re.sub(r"[‘’‚‛′`´ʹʻʼ]", "'", str(text or "")).lower()
    return re.sub(r"\s+", " ", value).strip()


def time_marks(text: Any) -> list[str]:
    """The time categories a French text carries, one entry per mark.

    «Hier soir» is a day and a part of the day; «le samedi» a frequency;
    «à huit heures» a clock time; «pendant deux ans» a span; «tard» a
    relative time; «en train de» / «vient de partir» the now of the action.
    """

    value = fold(text)
    if not value:
        return []
    marks: list[str] = []
    for category, pattern in _TIME_PATTERNS:
        # The same words said twice («… ce soir ? Oui, … ce soir») are one time.
        seen = {match.group(0).strip(" ,.") for match in pattern.finditer(value)}
        marks.extend(category for _ in seen)
    return marks


def dayparts(text: Any) -> set[str]:
    value = fold(text)
    found: set[str] = set()
    if _MORNING.search(value):
        found.add("morning")
    if _EVENING.search(value):
        found.add("evening")
    return found


def time_conflict(first: Iterable[str], second: Iterable[str]) -> tuple[str, str] | None:
    """The first clashing pair between two sets of marks, if any."""

    for a in first:
        for b in second:
            if frozenset((a, b)) in TIME_CONFLICTS:
                return a, b
    return None


def own_time_conflict(marks: list[str]) -> tuple[str, str] | None:
    for index, a in enumerate(marks):
        for b in marks[index + 1:]:
            if frozenset((a, b)) in TIME_CONFLICTS:
                return a, b
    return None


# --------------------------------------------------------------------------- #
# Entries
# --------------------------------------------------------------------------- #

_CAST_NAMES = {
    "margaux": "margaux", "marin": "marin", "romy": "romy", "lila": "lila", "gus": "gus",
    "augustin": "gus", "marchand": "marchand",
}
_CAST_RE = re.compile(r"\b(margaux|marin|romy|lila|gus|augustin|marchand)\b", re.IGNORECASE)
#: The world bible's recurring places, as a sentence names them.
BIBLE_PLACE_RE = re.compile(
    r"\b(?:mistral|marché du canal|canal|rédaction|brocante|bureau de l'ong|ong|buttes-chaumont|montmartre)\b",
    re.IGNORECASE,
)


def members(entry: dict[str, Any]) -> set[str]:
    """The cast members an entry names (a cast subject, a pair, «avec Lila»)."""

    found = set(entry.get("members") or [])
    if entry.get("kind") == "person" and entry.get("bible"):
        found.add(str(entry.get("id")))
    for match in _CAST_RE.finditer(str(entry.get("fr") or "")):
        found.add(_CAST_NAMES[match.group(1).lower()])
    return found


def _is_place(entry: dict[str, Any]) -> bool:
    return entry.get("kind") == "place" and "holds" in entry


def _is_thing(entry: dict[str, Any]) -> bool:
    """A noun that sits somewhere: an object, a food, a person noun (not a cast subject)."""

    return entry.get("kind") in {"obj", "food", "person"} and bool(entry.get("dom"))


def _is_verb(entry: dict[str, Any]) -> bool:
    return "inf" in entry


def _entry_marks(entry: dict[str, Any]) -> list[str]:
    cached = entry.get("_time")
    if cached is None:
        cached = time_marks(entry.get("fr"))
        if "span" in (entry.get("tags") or []) and "span" not in cached:
            cached = [*cached, "span"]
        entry["_time"] = cached
    return cached


entry_marks = _entry_marks


def _number(entry: dict[str, Any]) -> int | None:
    value = entry.get("value")
    return int(value) if isinstance(value, (int, float)) and "digits" in entry else None


@dataclass(frozen=True)
class Clash:
    kind: str
    detail: str


def pair_clash(a: dict[str, Any], b: dict[str, Any]) -> Clash | None:
    """Why two bound entries cannot share a sentence (``None``: they can)."""

    for first, second in ((a, b), (b, a)):
        # A thing at a place: the place must hold that kind of thing.
        if _is_thing(first) and _is_place(second) and not second.get("tags", []).count("area"):
            if not set(first["dom"]) & set(second.get("holds") or []):
                return Clash("location", f"{first.get('fr')} at {second.get('fr')}")
        # A price or a head count.
        number = _number(first)
        if number is not None:
            if second.get("kind") in {"obj", "food", "topic"}:
                price = second.get("price")
                if not price or not (price[0] <= number <= price[1]):
                    return Clash("price", f"{number} euros for {second.get('fr')}")
            if _is_place(second) and second.get("cap") and number > int(second["cap"]):
                return Clash("capacity", f"{number} people at {second.get('fr')}")
        # Where a verb happens.
        if _is_verb(first) and _is_place(second) and first.get("at"):
            if not set(first["at"]) & set(second.get("use") or []):
                return Clash("verb_place", f"{first.get('inf')} at {second.get('fr')}")
        # How long it lasts.
        if _is_verb(first) and second.get("scale") and first.get("dur"):
            if second["scale"] not in first["dur"]:
                return Clash("verb_duration", f"{first.get('inf')} for {second.get('fr')}")
        # A verb that must not meet a time expression («travailler après le travail»).
        if _is_verb(first) and first.get("id") in (second.get("not_with") or []):
            return Clash("verb_time", f"{first.get('inf')} with {second.get('fr')}")
        # The cast keep the jobs the world bible gave them.
        if first.get("jobs") and str(second.get("id") or "").startswith("job_"):
            if second["id"] not in first["jobs"]:
                return Clash("cast_fact", f"{first.get('fr')} as {second.get('m')}")
        # A cup of coffee, never a cup of wine.
        if first.get("fits") is not None and second.get("kind") in {"food", "obj"}:
            if second.get("id") not in first["fits"]:
                return Clash("container", f"{first.get('fr')} de {second.get('fr')}")
        # Part of the day: getting up is a morning thing.
        if _is_verb(first) and first.get("daypart"):
            parts = dayparts(second.get("fr"))
            if parts and first["daypart"] not in parts:
                return Clash("daypart", f"{first.get('inf')} with {second.get('fr')}")
    # One person never does a thing with themself.
    shared = members(a) & members(b)
    if shared:
        return Clash("identity", f"{', '.join(sorted(shared))} twice")
    conflict = time_conflict(_entry_marks(a), _entry_marks(b))
    if conflict:
        return Clash("time", f"{a.get('fr')} + {b.get('fr')} ({conflict[0]}/{conflict[1]})")
    return None


def adjective_fits(adjective: dict[str, Any], head: dict[str, Any]) -> bool:
    kinds = adjective.get("kinds")
    if not kinds:
        return True
    features = {head.get("kind") or "person", *(head.get("tags") or [])}
    return bool(features & set(kinds))


def contains(area: dict[str, Any], inner: dict[str, Any]) -> bool:
    """«le meilleur café du quartier»: a place sits in an area, never in a place."""

    return "area" in (area.get("tags") or []) and "area" not in (inner.get("tags") or [])


def link_clash(head: dict[str, Any], dependent: dict[str, Any]) -> Clash | None:
    """A declared dependency (``X@HEAD``) that does not hold."""

    if "m" in dependent and "kinds" in dependent and not adjective_fits(dependent, head):
        return Clash("adjective", f"{dependent.get('m')} for {head.get('fr')}")
    if _is_place(head) and _is_place(dependent) and not contains(dependent, head):
        return Clash("containment", f"{head.get('fr')} in {dependent.get('fr')}")
    if dependent.get("verbs") is not None and _is_verb(head) and head.get("id") not in dependent["verbs"]:
        return Clash("adverb", f"{dependent.get('fr')} with {head.get('inf')}")
    if head.get("p") == 1 and dependent.get("members") and dependent.get("g") and head.get("g") != dependent["g"]:
        # «Tu es contente, Marin»: said to Marin, «tu» is Marin.
        return Clash("address", f"{head.get('fr')} ({head.get('g')}) to {dependent.get('fr')}")
    number = _number(dependent)
    if number is not None and head.get("age") and not (head["age"][0] <= number <= head["age"][1]):
        return Clash("cast_fact", f"{head.get('fr')} is not {number}")
    if head.get("dom") and dependent.get("dom") and not set(head["dom"]) & set(dependent["dom"]):
        # «La table est aussi jolie que le stylo»: compare like with like.
        return Clash("comparison", f"{head.get('fr')} vs {dependent.get('fr')}")
    return None


# --------------------------------------------------------------------------- #
# Sentence-level rules (independent of how the item was bound)
# --------------------------------------------------------------------------- #

_FORM_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("elision", re.compile(r"\b(?:je|me|te|se|ne|de|que)\s+(?=[aeiouyéèêàâîôû])", re.IGNORECASE)),
    ("elision", re.compile(r"\bde (?:elle|elles|eux|il|ils)\b", re.IGNORECASE)),
    ("contraction", re.compile(r"(?<![\w'])(?:à le|à les|de le|de les)\s", re.IGNORECASE)),
    ("adverb_position", re.compile(
        r"\b(?:ai|as|a|avons|avez|ont|suis|es|est|sommes|êtes|sont)\s+\w+(?:é|ée|és|ées|i|ie|is|it|u|ue)\s+(?:bien|beaucoup)\b"
    )),
    ("adverb_position", re.compile(r"\b\w+(?:er|ir|re)\s+bien\b")),
)
#: «Marin et Lila part»: a verb right after a pair of names is plural.
_PAIR_VERB = re.compile(
    r"\b(?:margaux|marin|romy|lila|gus) et (?:margaux|marin|romy|lila|gus)\s+(?:(?:ne|se|nous|vous)\s+|[ns]')*(\w+)",
    re.IGNORECASE,
)
_PLURAL_VERB = re.compile(r"(?:ent|ont|aient)$|^(?:sont|ont|font|vont)$")
#: Grammatical but odd: verbs that cannot be wanted, planned, ordered or
#: be «in progress», and a few known collocation slips.
_ODD_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aspect", re.compile(
        r"\b(?:veux|veut|voulons|voulez|veulent|voudrais|voudrait|voudriez|aimerais|pourriez|pourrais"
        r"|dois|doit|devons|devez|doivent|devrais|devriez|faut|peux|peut|pouvons|pouvez|peuvent)\s+"
        r"(?:préférer|perdre|oublier|tomber|connaître|savoir|avoir)\b"
    )),
    ("aspect", re.compile(r"\ben train d[e'] ?(?:préférer|connaître|savoir|oublier|perdre|aimer|habiter|avoir|tomber)\b")),
    ("aspect", re.compile(r"\bv(?:ien|en)\w* d[e'] ?(?:préférer|connaître|savoir|avoir|habiter|aimer)\b")),
    ("collocation", re.compile(r"\b(?:va|vais|vas|allons|allez|vont) (?:au quartier|à l'immeuble|à la rue)\b")),
    ("collocation", re.compile(r"\b(?:parce qu|mais)\w*\s+\w+\s+(?:est|es|suis|sommes|êtes|sont)\s+(?:prêt|prête|prêts|prêtes)\b")),
)
_EN_FUTURE = re.compile(
    r"\b(?:tomorrow|tonight|next (?:week|monday|month|year)|this (?:weekend|summer))\b",
    re.IGNORECASE,
)
_EN_FUTURE_OK = re.compile(
    r"\b(?:will|won't|going to|'ll|shall|would|could|should|can|have to|has to|want|wants|need|needs)\b"
    r"|\b(?:exam|meeting|appointment|train to catch)\b"
    r"|\b\w+ed\b|\b(?:did|was|were|went|ate|drank|took|saw|had|made|came|left|slept|wrote|read|got|gave|found)\b"
    r"|\b(?:am|is|are|'m|'re|'s)\b|\b(?:starts?|begins?|opens?|leaves?|arrives?)\b",
    re.IGNORECASE,
)
_EN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("english_quantity", re.compile(r"\btoo much \w+s\b(?<!ss)", re.IGNORECASE)),
    ("english_agreement", re.compile(
        r"\b(?:Margaux|Marin|Romy|Lila|Gus) and (?:Margaux|Marin|Romy|Lila|Gus) (?:is|has|goes|does|was)\b"
    )),
)


def sentence_violations(sentence: str, english: str = "") -> list[Clash]:
    """Rules read off the finished French sentence and its English cue."""

    found: list[Clash] = []
    text = fold(sentence)
    marks = time_marks(text)
    conflict = own_time_conflict(marks)
    if conflict:
        found.append(Clash("time", f"{conflict[0]}/{conflict[1]}: {sentence}"))
    parts = dayparts(text)
    if re.search(r"\b(?:lève|lèves|lèvent|levé|levée|levés|levées|lever|réveill\w*)\b", text) and "evening" in parts:
        found.append(Clash("daypart", sentence))
    if re.search(r"\b(?:couche|couches|couchent|couché|couchée|couchés|couchées|coucher)\b", text) and "morning" in parts:
        found.append(Clash("daypart", sentence))
    for kind, pattern in (*_FORM_RULES, *_ODD_RULES):
        if kind == "elision":
            # h aspiré and «je/que» before a name are fine.
            for match in pattern.finditer(sentence):
                following = sentence[match.end(): match.end() + 12].lower()
                if following.startswith(("huit", "haut", "hauteur")):
                    continue
                found.append(Clash(kind, sentence))
                break
            continue
        if pattern.search(text):
            found.append(Clash(kind, sentence))
    for match in _PAIR_VERB.finditer(sentence):
        word = match.group(1).lower()
        if word in {"aussi", "moins", "plus", "au", "à", "en", "chez", "dans"}:
            continue
        if not _PLURAL_VERB.search(word):
            found.append(Clash("pair_agreement", sentence))
    names = [m.group(1).lower() for m in _CAST_RE.finditer(sentence)]
    if len(names) != len({_CAST_NAMES[name] for name in names}):
        found.append(Clash("identity", sentence))
    if english:
        if _EN_FUTURE.search(english) and not _EN_FUTURE_OK.search(english):
            found.append(Clash("english_tense", english))
        for kind, pattern in _EN_RULES:
            if pattern.search(english):
                found.append(Clash(kind, english))
    return found


def violations(item: Any) -> list[Clash]:
    """Every broken constraint of one bank item (empty: natural)."""

    found: list[Clash] = []
    bound = [entry for _slot, entry in getattr(item, "bindings", ()) or ()]
    for index, a in enumerate(bound):
        for b in bound[index + 1:]:
            clash = pair_clash(a, b)
            if clash:
                found.append(clash)
    frame_marks = list(getattr(item, "frame_times", ()) or ())
    for entry in bound:
        conflict = time_conflict(frame_marks, _entry_marks(entry))
        if conflict:
            found.append(Clash("time", f"frame + {entry.get('fr')} ({conflict[0]}/{conflict[1]})"))
    slots = dict(getattr(item, "bindings", ()) or ())
    for slot, head in getattr(item, "links", ()) or ():
        if slot in slots and head in slots:
            clash = link_clash(slots[head], slots[slot])
            if clash:
                found.append(clash)
    found.extend(sentence_violations(getattr(item, "sentence", ""), getattr(item, "en", "")))
    return found


# --------------------------------------------------------------------------- #
# Story links
# --------------------------------------------------------------------------- #

#: The world bible's recurring objects (as the lexicon marks them ``story``).
STORY_OBJECT_RE = re.compile(
    r"\b(?:bague|carnet|radiateur|tasse|tableau|roman|affiche|téléphone|micro|carton|plante|clé|valise|guitare)s?\b",
    re.IGNORECASE,
)


def story_links(sentence: str) -> dict[str, list[str]]:
    """What in a sentence belongs to the learner's story: cast, places, objects."""

    text = unicodedata.normalize("NFC", str(sentence or ""))
    return {
        "cast": sorted({_CAST_NAMES[m.group(1).lower()] for m in _CAST_RE.finditer(text)}),
        "places": sorted({m.group(0).lower() for m in BIBLE_PLACE_RE.finditer(text)}),
        "objects": sorted({m.group(0).lower() for m in STORY_OBJECT_RE.finditer(text)}),
    }


def is_story_linked(sentence: str) -> bool:
    return any(story_links(sentence).values())


def is_story_entry(entry: dict[str, Any]) -> bool:
    """A lexicon entry that brings the story in: a cast member, a bible place, a story object."""

    if members(entry):
        return True
    if entry.get("story"):
        return True
    text = str(entry.get("fr") or "")
    return bool(BIBLE_PLACE_RE.search(text) or STORY_OBJECT_RE.search(text))


__all__ = [
    "Clash",
    "TIME_CONFLICTS",
    "adjective_fits",
    "dayparts",
    "is_story_entry",
    "is_story_linked",
    "link_clash",
    "members",
    "pair_clash",
    "sentence_violations",
    "story_links",
    "time_conflict",
    "time_marks",
    "violations",
]
