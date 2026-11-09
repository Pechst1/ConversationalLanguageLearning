"""ROOT CAUSE #147 — the cast is one registry.

Before this module a character's name, gender, face, voice and first day were
written out again in the teaser (``serial_notifications``), the cast intro
(``intro.json``), the story content (``t*.json``), the voices (``cast_voices``)
and the prompts, and they drifted: Romy greeted in a teaser before she was in the
story, Camille was missing from the cast intro, M. Marchand was called «Elle».
Nothing made a second copy fail when the first changed.

Now there is one row per person, :class:`CastMember` (id, name, gender, face,
voice, first day), and every surface reads it **by id**:

* ``name`` and ``gender`` come from the season's world bible
  (``app/data/season/s1/world.json`` ``cast``), so a pronoun follows the canon;
* ``voice`` comes from :mod:`app.services.cast_voices`;
* ``face`` is the drawn portrait directory, found on disk, never typed twice;
* the card line (:func:`card_line`) is the one sentence a cast card shows about a
  person, written for the learner per interface language in ``cast_cards.json``;
  never the world bible's ``role`` / ``dynamic_with_user``, which are briefs for the
  writers (#298);
* ``first_day`` is ``(tentpole, day letter)`` of the person's first authored page;
* the role the learner reads (:func:`role`, #265) lives in :mod:`app.services.cast_roles`
  and is printed by the Courrier, both cast intros, the director's cast rows and the
  voice persona alike;
* the pronoun the story uses for a person (:func:`pronoun_for`) comes from the same
  row, and for the one person whose gender the learner picks (Camille) from that
  life's own choice — every story prompt reads it here (#147, Phase 3);
* ``address`` is how the person opens with the learner (the season's cast row), and
  ``relation_to_learner`` / ``relations`` what they are to the learner and to each
  other (``cast_relations.json``, from the season bible);
* :func:`person` is the one read of all of it for a surface: name, role, relation, the
  address **now** and whether this learner has met them.

The address rule, as the code already behaves (#594, #147)
----------------------------------------------------------
During a scripted season **the season decides** the register: ``living_story`` never
asks «On se tutoie ?» while a season runs, and ``season.runtime._apply_registers`` writes
the season's value back onto the relationship map at every settle. Once no season runs,
**the relationship decides**: that is where an accepted «On se tutoie ?» is kept.
:func:`address_now` wraps ``address.known_register`` and reads no register of its own.

Someone outside this registry is not a person of the cast: :func:`person` answers
``None``. A letter from outside the cast (a shop, a clerk) is a one-letter extra, with
the one tu/vous stored on the letter, no face and no claim to know the learner.

``tests/test_cast_registry_147.py`` is the guard: every id the authored season,
the cast intro and the teasers name must be here, speakers need a face, the
first day must match the authored season, and the intro may not name someone
before their day. ``tests/test_one_cast_table_147.py`` forbids a literal table of the
cast's names anywhere else.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services import address
from app.services.cast_aliases import ALIASES
from app.services.cast_roles import role_of
from app.services.cast_voices import CAST_VOICES

_REPO = Path(__file__).resolve().parents[2]
SEASON_PATH = _REPO / "app" / "data" / "season" / "s1" / "season.json"
WORLD_PATH = _REPO / "app" / "data" / "season" / "s1" / "world.json"
CARDS_PATH = _REPO / "app" / "data" / "season" / "s1" / "cast_cards.json"
RELATIONS_PATH = _REPO / "app" / "data" / "season" / "s1" / "cast_relations.json"
COACHES_PATH = _REPO / "app" / "data" / "forge_coaches.json"
DRAWN_FACES_DIR = _REPO / "web-frontend" / "public" / "assets" / "serial" / "drawn"

#: What the learner reads for each person.
_SHORT_NAMES: dict[str, str] = {
    "margaux_barman": "Margaux",
    "augustin_de_roncourt": "Gus",
    "marin_leveque": "Marin",
    "lila_bonnet": "Lila",
    "camille_marchand": "Camille",
    "romy_tremblay": "Romy",
    "landlord_marchand": "M. Marchand",
    "mme_diallo": "Mme Diallo",
    "maitre_vasseur": "Maître Vasseur",
    "bastien_roux": "Bastien Roux",
    "odile_ferrand": "Odile",
}
#: What a person says when they name themselves («Bonjour, c'est …», a voicemail): the
#: label without its written abbreviations, and the first name where the label is a full
#: name. Anyone not listed says their label (#217).
_SPOKEN_NAMES: dict[str, str] = {
    "landlord_marchand": "Monsieur Marchand",
    "mme_diallo": "Madame Diallo",
    "bastien_roux": "Bastien",
}
#: The spelling an English cue uses where it is not the label («…, Mr Marchand.»).
_ENGLISH_NAMES: dict[str, str] = {"landlord_marchand": "Mr Marchand"}
#: When the story first puts each person on a page: ``(tentpole, day letter)``.
#: The guard test re-derives it from ``t*.json`` and fails if this drifts.
_FIRST_APPEARANCE: dict[str, tuple[int, str]] = {
    "margaux_barman": (1, "a"),
    "augustin_de_roncourt": (1, "a"),
    "marin_leveque": (1, "a"),
    "lila_bonnet": (1, "a"),
    "camille_marchand": (1, "b"),
    "bastien_roux": (2, "b"),
    "romy_tremblay": (4, "a"),
    "mme_diallo": (4, "a"),
    "landlord_marchand": (4, "a"),
    "odile_ferrand": (4, "b"),
    "maitre_vasseur": (6, "b"),
}
#: Ids a scene uses for the same person: ``cast_aliases``, which ``cast_voices`` reads too.
_ALIASES: dict[str, str] = ALIASES
#: A person whose gender the learner picks: the season flag that holds the choice.
GENDER_FLAGS: dict[str, str] = {"camille_marchand": "s1.camille_gender"}
#: Ids in a scene that are not a person with a face: the learner, the narration
#: and things that «speak» (a letter, an SMS, everyone at once).
NON_PEOPLE: frozenset[str] = frozenset({"toi", "caption", "letter", "all", "sms"})
#: Unnamed one-scene extras (a clerk, a child): a role, not a recurring person.
EXTRAS: frozenset[str] = frozenset({"clerk", "clerk_2", "child", "builder", "dealer"})


@dataclass(frozen=True)
class LearnerRelation:
    """What a person is to the learner: ``kind`` to test, ``labels`` to print, per language."""

    kind: str  # one of cast_relations.json ``kinds``: "family", "friend", "other_side"…
    labels: Mapping[str, str]

    def label(self, language: str | None = "fr") -> str:
        code = str(language or "fr").strip().lower().replace("_", "-").split("-")[0]
        return str(self.labels.get(code) or self.labels.get("en") or "")

    @property
    def is_friend(self) -> bool:
        """May a surface call this person the learner's friend? Camille: no, ever, in season 1."""

        return self.kind == "friend"


@dataclass(frozen=True)
class Relation:
    """One person's tie to another person of the cast, and the page that first shows it."""

    kind: str  # "grandchild_of", "grandparent_of"…
    other: str  # registry id
    known_from: tuple[int, str]  # (tentpole, day letter)


@dataclass(frozen=True)
class CastMember:
    id: str
    name: str  # the world bible's full name
    short_name: str  # what the learner reads
    spoken_name: str  # what the person says when naming themselves
    gender: str  # "f", "m", or "x" (the learner picks: Camille)
    voice: str | None
    face: str | None  # drawn portrait directory name; None when no art exists yet
    first_day: tuple[int, str]  # (tentpole number, day letter)
    # How the person opens with the learner (the season's cast row), before any flag moves
    # it. What they say today is :func:`address_now`, never this.
    address: str | None = None
    relation_to_learner: LearnerRelation | None = None
    relations: tuple[Relation, ...] = ()

    @property
    def pronoun_fr(self) -> str:
        """«Il» or «Elle»; the neutral «Iel» for a person whose gender the learner picks."""

        return {"f": "Elle", "m": "Il"}.get(self.gender, "Iel")


def _face_for(cast_id: str) -> str | None:
    return cast_id if (DRAWN_FACES_DIR / cast_id / "portrait-neutre.png").is_file() else None


def _opening_addresses() -> dict[str, str]:
    """``cast[].address`` of the season file, by registry id (the file says «odile»)."""

    season = json.loads(SEASON_PATH.read_text(encoding="utf-8"))
    return {
        _ALIASES.get(str(row["id"]), str(row["id"])): str(row["address"])
        for row in season.get("cast", [])
        if row.get("id") and row.get("address")
    }


def _relations_data() -> tuple[dict[str, LearnerRelation], dict[str, tuple[Relation, ...]]]:
    data = json.loads(RELATIONS_PATH.read_text(encoding="utf-8"))
    to_learner = {
        str(cast_id): LearnerRelation(
            kind=str(row["kind"]),
            labels={code: str(row[code]) for code in ("fr", "en", "de") if row.get(code)},
        )
        for cast_id, row in (data.get("to_learner") or {}).items()
    }
    between: dict[str, list[Relation]] = {}
    for row in data.get("between") or []:
        tentpole, day = row["known_from"]
        known_from = (int(tentpole), str(day))
        person, other = str(row["person"]), str(row["other"])
        between.setdefault(person, []).append(Relation(str(row["kind"]), other, known_from))
        between.setdefault(other, []).append(Relation(str(row["inverse"]), person, known_from))
    return to_learner, {cast_id: tuple(rows) for cast_id, rows in between.items()}


@lru_cache(maxsize=1)
def _registry() -> dict[str, CastMember]:
    world = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    rows = {str(row["id"]): row for row in world.get("cast", []) if row.get("id")}
    rows.setdefault("odile_ferrand", {"id": "odile_ferrand", "gender": "f", "name": "Odile Ferrand"})
    addresses = _opening_addresses()
    to_learner, between = _relations_data()
    members: dict[str, CastMember] = {}
    for cast_id, row in rows.items():
        gender = str(row.get("gender") or "x")
        members[cast_id] = CastMember(
            id=cast_id,
            name=str(row.get("name") or cast_id),
            short_name=_SHORT_NAMES.get(cast_id, str(row.get("name") or cast_id)),
            spoken_name=_SPOKEN_NAMES.get(
                cast_id, _SHORT_NAMES.get(cast_id, str(row.get("name") or cast_id))
            ),
            gender=gender if gender in ("f", "m", "x") else "x",
            voice=CAST_VOICES.get(cast_id),
            face=_face_for(cast_id),
            first_day=_FIRST_APPEARANCE.get(cast_id, (1, "a")),
            address=addresses.get(cast_id),
            relation_to_learner=to_learner.get(cast_id),
            relations=between.get(cast_id, ()),
        )
    return members


@lru_cache(maxsize=1)
def _cards() -> dict[str, dict[str, str]]:
    data = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    return {str(cid): dict(row) for cid, row in (data.get("cards") or {}).items()}


def card_line(character_id: str | None, language: str | None = "en") -> str:
    """What a cast card says about this person, in the learner's interface language.

    ``""`` when nobody wrote a line: a card then shows the name only. It never falls
    back to the world bible's text, which is the author's (#298).
    """

    cast_id = resolve_id(character_id)
    row = _cards().get(cast_id or "") or {}
    code = str(language or "en").strip().lower().replace("_", "-").split("-")[0]
    return str(row.get(code) or row.get("en") or "")


def all_members() -> dict[str, CastMember]:
    return dict(_registry())


def resolve_id(character_id: str | None) -> str | None:
    """The registry id for any id, alias or first-name token, or ``None``."""

    raw = str(character_id or "").strip().lower()
    if not raw:
        return None
    registry = _registry()
    if raw in registry:
        return raw
    if raw in _ALIASES:
        return _ALIASES[raw]
    return _ALIASES.get(raw.split("_", 1)[0])


def aliases() -> dict[str, str]:
    """``{alias: registry id}``: the short ids scenes use («gus», «marchand», «landlord»)."""

    return dict(_ALIASES)


def member(character_id: str | None) -> CastMember | None:
    cast_id = resolve_id(character_id)
    return _registry().get(cast_id) if cast_id else None


def display_name(character_id: str | None, default: str = "") -> str:
    found = member(character_id)
    return found.short_name if found else default


def spoken_name(character_id: str | None, default: str = "") -> str:
    """What a person says when naming themselves: «Bonjour, c'est Gus.», «… c'est Monsieur
    Marchand.» — never the world bible's «Augustin « Gus » de Roncourt» (#217)."""

    found = member(character_id)
    return found.spoken_name if found else default


_VOWELS = frozenset("aeiouàâäéèêëîïôöùûüœæ")


def with_de(name: str) -> str:
    """«de» in front of a name, elided before a vowel: «d'Odile», «d'Augustin», «de Gus»."""

    text = str(name or "").strip()
    return f"d'{text}" if text[:1].casefold() in _VOWELS else f"de {text}"


def display_names(cast: Any) -> dict[str, str]:
    """``{id: what the learner reads}`` for a season's cast rows (anything with ``id`` and
    ``name``). A person the registry holds is named by the registry; anyone else keeps the
    name the season gave them.

    Every surface that names a speaker to the learner (the page's lines, the reply thread,
    the re-read day) builds its ``{id: name}`` map here, never from ``member.name`` — that
    is the world bible's full name («Augustin « Gus » de Roncourt»), and a thread that took
    it from there printed one person under two names (#217).
    """

    return {row.id: display_name(row.id, row.name) for row in cast}


def role(character_id: str | None, language: str = "fr") -> str:
    """The role the learner reads for a person («institutrice et peintre»), by id or
    alias, in ``fr``, ``en`` or ``de``; ``""`` when nobody has written one (#265)."""

    cast_id = resolve_id(character_id)
    return role_of(cast_id, language) if cast_id else ""


def pronoun_for(
    character_id: str | None,
    *,
    gender: str | None = None,
    flags: Mapping[str, Any] | None = None,
) -> str | None:
    """«il» or «elle» for a person, as this life's story says it — or ``None`` when
    nobody has decided (a prompt then uses the name, never a guess).

    The registry's gender; for Camille, the learner's own choice (``flags``, seeded
    until T1 B poses it); ``gender`` is the world bible's value for a person the
    registry does not hold (a later season's cast)."""

    found = member(character_id)
    cast_id = found.id if found else str(character_id or "")
    value = (flags or {}).get(GENDER_FLAGS[cast_id]) if cast_id in GENDER_FLAGS else None
    if not value:
        value = found.gender if found else gender
    return {"f": "elle", "m": "il"}.get(str(value or "").strip().lower()[:1])


def introduced_by(character_id: str | None, tentpole: int, day: str = "z") -> bool:
    """Has the story put this person on a page by ``(tentpole, day)``?

    Unknown ids are not introduced: a surface must not name someone the registry
    does not hold.
    """

    found = member(character_id)
    return found is not None and found.first_day <= (int(tentpole), str(day))


# --------------------------------------------------------------------------- #
# Who this learner has met (#147, re-test 31 Oct: unmet people were listed)
# --------------------------------------------------------------------------- #

_SEGMENT = re.compile(r"^([tg])(\d+)$")


def season_reach(state: Mapping[str, Any] | None) -> tuple[int, str] | None:
    """How far this life's season has gone, as ``(tentpole, day letter)``, or ``None``.

    Read from the season's played log (``living_story.season_script.played``): a
    tentpole day is ``(n, "a")`` / ``(n, "b")``; a gap day after tentpole *n* is
    ``(n, "z")`` (everyone that tentpole put on a page is met). ``None`` when the
    thread plays no season yet.
    """

    live = (state or {}).get("living_story") if isinstance(state, Mapping) else None
    script = live.get("season_script") if isinstance(live, Mapping) else None
    played = script.get("played") if isinstance(script, Mapping) else None
    best: tuple[int, str] | None = None
    for row in played if isinstance(played, list) else []:
        if not isinstance(row, Mapping):
            continue
        found = _SEGMENT.match(str(row.get("segment") or "").strip().lower())
        if not found:
            continue
        number = int(found.group(2))
        if found.group(1) == "g":
            point = (number, "z")
        else:
            point = (number, "a" if int(row.get("day_in_segment") or 1) <= 1 else "b")
        best = point if best is None or point > best else best
    return best


def _met_in_story(state: Mapping[str, Any] | None) -> set[str]:
    """Ids the story has actually put in front of the learner: a relationship with
    something in it (closeness, a callback, a summary) or a mood the engine keeps."""

    found: set[str] = set()
    relationships = (state or {}).get("relationships") if isinstance(state, Mapping) else None
    for key, entry in (relationships or {}).items() if isinstance(relationships, Mapping) else []:
        if isinstance(entry, Mapping) and (
            int(entry.get("closeness") or 0) > 0 or entry.get("callbacks") or entry.get("last_summary")
        ):
            found.add(resolve_id(str(key)) or str(key))
    live = (state or {}).get("living_story") if isinstance(state, Mapping) else None
    moods = live.get("moods") if isinstance(live, Mapping) else None
    for key in (moods or {}) if isinstance(moods, Mapping) else []:
        found.add(resolve_id(str(key)) or str(key))
    return found


def met_ids(state: Mapping[str, Any] | None) -> frozenset[str] | None:
    """Everyone this learner has met: the registry's people the season has reached
    (:func:`introduced_by`), plus anyone the story has spoken with. ``None`` when the
    thread plays no season (an older story has no canon of who comes when): the caller
    then does not filter.

    Ids are registry ids where the registry holds the person, the stored id otherwise.
    """

    reach = season_reach(state)
    if reach is None:
        return None
    found = _met_in_story(state)
    found.update(cid for cid in _registry() if introduced_by(cid, *reach))
    return frozenset(found)


def has_met(state: Mapping[str, Any] | None, character_id: str | None) -> bool:
    """Has this learner met this person? ``True`` when nothing can tell (no season)."""

    known = met_ids(state)
    if known is None:
        return True
    raw = str(character_id or "").strip()
    return bool(raw) and (resolve_id(raw) or raw) in known


# --------------------------------------------------------------------------- #
# The one read of a person (#147)
# --------------------------------------------------------------------------- #


def address_now(
    character_id: Any,
    state: Mapping[str, Any] | None = None,
    *,
    registers: Mapping[str, Any] | None = None,
) -> address.Register | None:
    """How this person addresses the learner now, or ``None`` when nothing says.

    ``address.known_register`` and nothing else (the module docstring has the rule):
    the relationship map where the story has one, the day's own snapshot ``registers``
    (``address.season_registers``), then the season the thread plays. ``None`` is not
    «vous»: a caller whose own text can decide (a letter that keeps one stored tu/vous)
    must not mistake a default for knowledge (#506).
    """

    return address.known_register(state, character_id, registers=registers)


@dataclass(frozen=True)
class Person:
    """A person of the cast as this learner stands with them today."""

    id: str
    name: str  # what the learner reads
    role: str  # "" when nobody has written one
    relation: LearnerRelation | None
    address_now: address.Register | None
    met: bool


def person(
    character_id: Any,
    state: Mapping[str, Any] | None = None,
    *,
    registers: Mapping[str, Any] | None = None,
    language: str = "fr",
) -> Person | None:
    """The one read of a person: name, role, relation, address now, met.

    ``None`` for anyone the registry does not hold: a one-letter extra or a clerk is not
    a person of the cast, so no surface may give them a relation or a claim to know the
    learner. ``state`` may be ``None`` (a first letter before any scene): ``met`` is then
    :func:`has_met`'s «nothing can tell»; ask :func:`introduced_by` for a day instead.
    """

    found = member(character_id)
    if found is None:
        return None
    return Person(
        id=found.id,
        name=found.short_name,
        role=role(found.id, language),
        relation=found.relation_to_learner,
        address_now=address_now(found.id, state, registers=registers),
        met=has_met(state, found.id),
    )


# --------------------------------------------------------------------------- #
# Names: every spelling of a person, for a surface that reads text
# --------------------------------------------------------------------------- #


def _spellings(row: CastMember) -> set[str]:
    """What a line may call this person: their label, what they call themselves, their
    nickname and their first name."""

    spellings = {row.short_name, row.spoken_name}
    nickname = re.search(r"«\s*([^»]+?)\s*»", row.name)
    if nickname:
        spellings.add(nickname.group(1))
    first = re.sub(r"«[^»]*»", " ", row.name).split()
    if first and len(first[0]) >= 3 and first[0][:1].isupper() and first[0] not in {"Mme", "Maître"}:
        spellings.add(first[0])
    return {spelling for spelling in spellings if spelling}


def name_words() -> set[str]:
    """Every capitalised word a line may use to call someone of the cast: what must never
    be taken for the learner's own name («Je suis Lila»)."""

    return {
        word
        for row in _registry().values()
        for spelling in _spellings(row)
        for word in spelling.split()
        if word[:1].isupper()
    }


@lru_cache(maxsize=1)
def _bank_ids() -> dict[str, str]:
    """``{registry id: the id La Forge's item bank knows them by}``, from the coaches file."""

    data = json.loads(COACHES_PATH.read_text(encoding="utf-8"))
    return {str(cid): str(row["lexicon"]) for cid, row in (data.get("cast") or {}).items() if row.get("lexicon")}


def bank_ids() -> dict[str, str]:
    """The item bank's people: ``{registry id: lexicon id}`` («marin_leveque» → «marin»)."""

    return dict(_bank_ids())


def bank_tokens() -> dict[str, str]:
    """``{lowercase word in a sentence: lexicon id}`` for the bank's people, nicknames and
    first names included («augustin» → «gus», «marchand» → «marchand»)."""

    tokens: dict[str, str] = {}
    for cid, lexicon in _bank_ids().items():
        row = _registry()[cid]
        words = {word.casefold() for spelling in (row.name, *_spellings(row)) for word in re.findall(r"\w+", spelling)}
        tokens[lexicon] = lexicon
        tokens.update((alias, lexicon) for alias, target in _ALIASES.items() if target == cid and alias in words)
    return tokens


def bank_first_names() -> list[str]:
    """The labels of the bank's people who go by one word («Marin», «Gus», not «M. Marchand»)."""

    labels = (_registry()[cid].short_name for cid in _bank_ids())
    return [label for label in labels if " " not in label]


def vocative_names() -> list[str]:
    """How a sentence of the bank calls its people to their face, in French and in an
    English cue: «…, Gus.», «…, Monsieur Marchand.», «…, Mr Marchand.»."""

    names: list[str] = []
    for cid in _bank_ids():
        row = _registry()[cid]
        for name in (row.short_name, row.spoken_name, _ENGLISH_NAMES.get(cid)):
            if name and name not in names:
                names.append(name)
    return names


#: Names a line may call a person by, longest first: «Monsieur Marchand» before «Marchand».
def _name_patterns() -> list[tuple[re.Pattern[str], str]]:
    rows: list[tuple[str, str]] = []
    for row in _registry().values():
        rows.extend((spelling, row.id) for spelling in _spellings(row))
    rows.sort(key=lambda pair: -len(pair[0]))
    return [(re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])"), cid) for name, cid in rows]


def people_named(text: Any) -> list[str]:
    """Registry ids of the people a text names, in order of first mention, once each.

    «Elle est à l'église, Gus.» → ``["augustin_de_roncourt"]``. A La Forge item or a
    prompt carries its cast in its words; this is how a surface reads it back, so the
    badge over a line is the person the line is said to (#147, 31 Oct)."""

    content = str(text or "")
    hits: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    for pattern, cid in _name_patterns():
        for match in pattern.finditer(content):
            span = match.span()
            if any(start < span[1] and span[0] < end for start, end in taken):
                continue
            taken.append(span)
            hits.append((span[0], cid))
    out: list[str] = []
    for _pos, cid in sorted(hits):
        if cid not in out:
            out.append(cid)
    return out


def people_addressed(text: Any) -> list[str]:
    """Registry ids of the people a text speaks *to* (a vocative): «…, Gus.», «Lila, tu…».

    :func:`people_named` minus the people the text only talks *about*."""

    content = str(text or "")
    out: list[str] = []
    for pattern, cid in _name_patterns():
        for match in pattern.finditer(content):
            before = content[: match.start()].rstrip(" \u00a0")
            after = content[match.end():].lstrip(" \u00a0")
            vocative_after = before.endswith(",") and (not after or after[:1] in ".?!…»\"”)")
            vocative_before = (not before or before[-1:] in ".?!:«\"“") and after[:1] == ","
            if (vocative_after or vocative_before) and cid not in out:
                out.append(cid)
    return out
