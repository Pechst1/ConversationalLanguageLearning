"""Tomorrow's hook remembers what the learner decided (``STORY_REMEMBERED_HOOK``).

Walks of November (#466, #455, #620): the end of a day said «Tomorrow · On va aider
Lila à l'école.», a flat line that ignored the «non» the learner had just given Lila,
or, worse, quoted the learner's own reply back as a promise, errors and all.

With the flag on, the day's one hook (``living_story._hook_after_day``) is read against
the scene's record. When the learner gave a clear yes or no to something a character put
to them (a proposal, «d'accord ?», or an invitation, «Tu viens ?», «On partage ?»), the
hook says that decision, naming what it was about when the character's own question can
be quoted as theirs, and leaves its consequence open, in the serial's voice:

    «Lila a demandé : « On partage ? » Tu as dit non. Est-ce qu'elle va accepter ça ?»
    «Tu as dit non à Lila. Est-ce qu'elle va accepter ça ?»  (a longer question)

Built here, deterministically, from authored templates per decision and level band; no
model call. The line never quotes the learner (only the character's name, their short
question and the decision kind come from the scene), never says «oui» once the learner said «non» (a
mixed day falls back), and is checked once more before it is kept (:func:`problem`).
Everything else, and any failure, keeps the authored hook unchanged.

The row is filed as the day's one hook, so the closing panel, Done, Home, the Quartier's
end card and tomorrow's page (``yesterday_hook``) print the same words. It carries
``remembered``: the decision, the authored hook it stands in for, the line «Précédemment»
opens on tomorrow, and the same thought in the character's own voice for the evening push.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

#: Where the decision and its renderings live on the hook row.
REMEMBERED_KEY = "remembered"
#: ``story_teaser.HOOK_SOURCES``: a hook said from the learner's decision.
SOURCE = "remembered"
#: The line without the character's question is at most this long. It is filed after
#: ``story_teaser.one_hook`` (whose cap is 14 words, cut at a sentence), so it is never cut.
MAX_WORDS = 16
#: The line that quotes the character's question runs longer: still two sentences, at
#: most this many words and characters (four short lines at phone width on Done/Home).
MAX_QUOTED_WORDS = 24
MAX_QUOTED_CHARS = 130
#: A character's question is quoted only up to this many words.
QUOTED_QUESTION_WORDS = 7
#: A run of this many words shared with a learner reply is a quote, and refused. The line
#: is built from templates and a name, so this only ever costs a coincidence (the learner
#: wrote «je dis non à Lila»): the authored hook then stands.
QUOTE_RUN = 4


def enabled() -> bool:
    return bool(getattr(settings, "STORY_REMEMBERED_HOOK", False))


# ---------------------------------------------------------------------------
# Templates. A line is two sentences: what the learner decided, then what it leaves
# open. The first names the thing decided when the character's own question is short
# and clean enough to quote as theirs (:func:`quotable`):
#
#     «Lila a demandé : « On partage ? » Tu as dit non.»
#
# and otherwise says the decision with the person's name («Tu as dit non à Lila.»).
# The character's question is on the record and was shown to the learner in the scene;
# the learner's words never are. The second sentence is one of at least four
# consequences per decision and level band, seeded per learner and day, never one a
# recent hook said. {who}: «elle» / «il», or the name again when the learner picks the
# person's gender. Below B1: present, near future, passé composé, no inversion.
# ---------------------------------------------------------------------------

_DECIDED = {
    "plain": {
        "refused": {
            "fr": "Tu as dit non à {name}.",
            "en": "You said no to {name}.",
            "de": "Du hast {name} Nein gesagt.",
        },
        "agreed": {
            "fr": "Tu as dit oui à {name}.",
            "en": "You said yes to {name}.",
            "de": "Du hast {name} Ja gesagt.",
        },
    },
    "quoted": {
        "refused": {
            "fr": "{name} a demandé : « {asked} » Tu as dit non.",
            "en": "{name} asked: “{asked}” You said no.",
            "de": "{name} hat gefragt: „{asked}“ Du hast Nein gesagt.",
        },
        "agreed": {
            "fr": "{name} a demandé : « {asked} » Tu as dit oui.",
            "en": "{name} asked: “{asked}” You said yes.",
            "de": "{name} hat gefragt: „{asked}“ Du hast Ja gesagt.",
        },
    },
}

_CONSEQUENCES: dict[str, dict[str, list[dict[str, str]]]] = {
    "refused": {
        "A": [
            {
                "fr": "Est-ce que {who} va accepter ça ?",
                "en": "Will {who_en} accept that?",
                "de": "Wird {who_de} das akzeptieren?",
            },
            {
                "fr": "Demain, est-ce que {who} demande encore ?",
                "en": "Tomorrow, will {who_en} ask again?",
                "de": "Fragt {who_de} morgen noch einmal?",
            },
            {
                "fr": "Et maintenant, {who} fait quoi ?",
                "en": "And now, what will {who_en} do?",
                "de": "Und was macht {who_de} jetzt?",
            },
            {
                "fr": "Est-ce que {who} a un autre plan ?",
                "en": "Does {who_en} have another plan?",
                "de": "Hat {who_de} einen anderen Plan?",
            },
            {
                "fr": "Demain, on voit la suite.",
                "en": "Tomorrow we'll see what happens next.",
                "de": "Morgen sehen wir, wie es weitergeht.",
            },
        ],
        "B": [
            {
                "fr": "Reste à savoir comment {who} va le prendre.",
                "en": "It remains to be seen how {who_en} will take it.",
                "de": "Bleibt die Frage, wie {who_de} das aufnimmt.",
            },
            {
                "fr": "Est-ce que {who} va insister, ou laisser tomber ?",
                "en": "Will {who_en} insist, or let it go?",
                "de": "Bleibt {who_de} dran, oder lässt es fallen?",
            },
            {
                "fr": "Le dernier mot n'est sans doute pas encore dit.",
                "en": "That is probably not the last word.",
                "de": "Das letzte Wort ist wohl noch nicht gesprochen.",
            },
            {
                "fr": "Ce refus va-t-il changer quelque chose entre vous ?",
                "en": "Will that refusal change something between you?",
                "de": "Ändert diese Absage etwas zwischen euch?",
            },
            {
                "fr": "Reste à voir ce que {who} fera de ce non.",
                "en": "It remains to be seen what {who_en} will make of that no.",
                "de": "Bleibt abzuwarten, was {who_de} aus diesem Nein macht.",
            },
        ],
    },
    "agreed": {
        "A": [
            {
                "fr": "Et demain, qu'est-ce qui va changer ?",
                "en": "And tomorrow, what will change?",
                "de": "Und was ändert sich morgen?",
            },
            {
                "fr": "Est-ce que tout va bien se passer ?",
                "en": "Will everything go well?",
                "de": "Geht alles gut?",
            },
            {
                "fr": "Demain, on voit la suite.",
                "en": "Tomorrow we'll see what happens next.",
                "de": "Morgen sehen wir, wie es weitergeht.",
            },
            {
                "fr": "Maintenant, {who} compte sur toi.",
                "en": "Now {who_en} is counting on you.",
                "de": "Jetzt zählt {who_de} auf dich.",
            },
            {
                "fr": "Mais est-ce que c'est facile ?",
                "en": "But is it easy?",
                "de": "Aber ist das einfach?",
            },
        ],
        "B": [
            {
                "fr": "Que va changer ce oui ?",
                "en": "What will that yes change?",
                "de": "Was wird dieses Ja verändern?",
            },
            {
                "fr": "Demain, on verra si c'était une bonne idée.",
                "en": "Tomorrow we'll see if it was a good idea.",
                "de": "Morgen sehen wir, ob das eine gute Idee war.",
            },
            {
                "fr": "Reste à voir ce que ce oui va coûter.",
                "en": "It remains to be seen what that yes will cost.",
                "de": "Bleibt abzuwarten, was dieses Ja kostet.",
            },
            {
                "fr": "Maintenant, {who} compte sur toi.",
                "en": "Now {who_en} is counting on you.",
                "de": "Jetzt zählt {who_de} auf dich.",
            },
            {
                "fr": "Savais-tu vraiment à quoi tu disais oui ?",
                "en": "Did you really know what you were saying yes to?",
                "de": "Wusstest du wirklich, wozu du Ja gesagt hast?",
            },
        ],
    },
}

#: The evening push, in the character's own voice: their question when it is quotable,
#: what the learner answered them, and one of these tails (by register).
_PUSH_HEAD = {
    "refused": {
        "tu": "Tu m'as dit non.",
        "vous": "Vous m'avez dit non.",
        "en": "You said no to me.",
        "de": "Du hast Nein gesagt.",
    },
    "agreed": {
        "tu": "Tu m'as dit oui.",
        "vous": "Vous m'avez dit oui.",
        "en": "You said yes to me.",
        "de": "Du hast Ja gesagt.",
    },
}
_PUSH_TAILS: dict[str, dict[str, list[dict[str, str]]]] = {
    "refused": {
        "A": [
            {
                "tu": "J'y pense encore.",
                "vous": "J'y pense encore.",
                "en": "I'm still thinking about it.",
                "de": "Ich denke noch daran.",
            },
            {
                "tu": "Demain, je demande encore ?",
                "vous": "Demain, je demande encore ?",
                "en": "Shall I ask again tomorrow?",
                "de": "Frage ich morgen noch einmal?",
            },
        ],
        "B": [
            {
                "tu": "J'y repense ce soir… on en reparle demain ?",
                "vous": "J'y repense ce soir… on en reparle demain ?",
                "en": "I'm thinking it over tonight… shall we talk tomorrow?",
                "de": "Ich denke heute Abend darüber nach… reden wir morgen?",
            },
            {
                "tu": "Mais je n'ai pas dit mon dernier mot.",
                "vous": "Mais je n'ai pas dit mon dernier mot.",
                "en": "But I haven't said my last word.",
                "de": "Aber das letzte Wort ist noch nicht gesprochen.",
            },
        ],
    },
    "agreed": {
        "A": [
            {
                "tu": "Merci ! On se voit demain ?",
                "vous": "Merci ! On se voit demain ?",
                "en": "Thank you! See you tomorrow?",
                "de": "Danke! Sehen wir uns morgen?",
            },
            {
                "tu": "Ça me fait plaisir. À demain ?",
                "vous": "Ça me fait plaisir. À demain ?",
                "en": "That makes me happy. See you tomorrow?",
                "de": "Das freut mich. Bis morgen?",
            },
        ],
        "B": [
            {
                "tu": "Je compte sur toi demain.",
                "vous": "Je compte sur vous demain.",
                "en": "I'm counting on you tomorrow.",
                "de": "Ich zähle morgen auf dich.",
            },
            {
                "tu": "Demain, on voit si j'avais raison de demander.",
                "vous": "Demain, on voit si j'avais raison de demander.",
                "en": "Tomorrow we'll see if I was right to ask.",
                "de": "Morgen sehen wir, ob es richtig war zu fragen.",
            },
        ],
    },
}
_PRONOUNS = {"f": ("elle", "she", "sie"), "m": ("il", "he", "er")}


def band_group(band: Any) -> str:
    """``A`` below B1, ``B`` from B1 to C1 (the level is the learner's, never fixed)."""

    text = str(band or "A1").strip().upper()
    return "B" if text[:1] in {"B", "C"} else "A"


# ---------------------------------------------------------------------------
# The decision, from the scene's record
# ---------------------------------------------------------------------------

#: A yes/no question that asks the learner to do something, by its folded words: «Tu
#: viens ?», «Tu veux goûter ?», «On partage la pizza ?», «Tu m'aides ?». A question about
#: a fact («Tu as faim ?», «Tu connais Paris ?») decides nothing, whatever the answer.
_INVITES = re.compile(
    r"\b(?:tu\s+(?:veux|viens|peux|acceptes|promets|restes|m\s+aides|m\s+accompagnes|es\s+pret|es\s+partant)"
    r"|vous\s+(?:voulez|venez|pouvez|acceptez|promettez|restez|m\s+aidez|m\s+accompagnez|etes\s+pret|etes\s+partant)"
    r"|on\s+(?!(?:est|a|dit|sait|connait)\b)[a-z]+)\b"
    # «Tu lis la lettre avec moi ?»: whatever the verb, doing it together is a choice.
    r"|\b(?:tu|vous)\s+.*\bavec\s+(?:moi|nous)\b"
)


def _folded(text: Any) -> str:
    bare = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^\w\s]", " ", bare.casefold()).split())


def puts_a_choice(line: Any) -> bool:
    """Whether a character's line puts a choice to the learner: a proposal the record
    keeps (``scene_ledger.character_proposal``) or a yes/no invitation."""

    from app.services import scene_ledger

    if scene_ledger.character_proposal(line):
        return True
    question = scene_ledger.character_question(line)
    return (
        bool(question)
        and scene_ledger.asks_yes_or_no(question)
        and bool(_INVITES.search(_folded(question)))
    )


def decision(
    opening_line_fr: Any, exchanges: Iterable[Any], ledger: Any = None
) -> dict[str, Any] | None:
    """``{"kind": "refused" | "agreed", "at": index, "asked_fr"}``: the learner's decision
    in a scene, with the character's question it answered, or ``None`` when the record
    holds none.

    ``exchanges`` are the stored turns (``{"learner", "character", "heard"?}``); a turn's
    reading is the record's (``ledger["turns"]``) where it has one, else
    ``scene_ledger.read_turn``. Only a yes or a no to a choice a character put
    (:func:`puts_a_choice`) is a decision. The last one counts, except that a «oui» never
    stands once the learner said «non» in the scene: that day falls back."""

    from app.services import scene_ledger

    readings = {
        row.get("at"): row.get("intent")
        for row in ((ledger or {}).get("turns") or [] if isinstance(ledger, dict) else [])
        if isinstance(row, dict)
    }
    on_the_table = str(opening_line_fr or "")
    found: list[dict[str, Any]] = []
    for index, row in enumerate(row for row in exchanges or [] if isinstance(row, dict)):
        learner = str(row.get("learner") or "")
        if learner.strip():
            intent = (
                readings.get(index)
                or scene_ledger.read_turn(learner, heard=row.get("heard"))["intent"]
            )
            if intent in ("yes", "no") and puts_a_choice(on_the_table):
                found.append(
                    {
                        "kind": "refused" if intent == "no" else "agreed",
                        "at": index,
                        "asked_fr": scene_ledger.character_question(on_the_table),
                    }
                )
        character = str(row.get("character") or "")
        if character.strip():
            on_the_table = character
    if not found:
        return None
    last = found[-1]
    if last["kind"] == "agreed" and any(row["kind"] == "refused" for row in found):
        return None
    return last


# ---------------------------------------------------------------------------
# The line
# ---------------------------------------------------------------------------


def _elide(text: str) -> str:
    return re.sub(r"\b(que|Que)\s+(elle|il)\b", lambda m: f"{m.group(1)[:-1]}'{m.group(2)}", text)


def _words(text: str) -> list[str]:
    return [word for word in re.split(r"\s+", text.strip()) if re.search(r"\w", word)]


def _runs(text: str, size: int) -> set[str]:
    words = _folded(text).split()
    return {" ".join(words[i : i + size]) for i in range(max(0, len(words) - size + 1))}


def quotable(asked: Any, *, said: Iterable[str] = ()) -> str | None:
    """The character's question as it may be quoted, or ``None``: one sentence ending
    in «?», at most :data:`QUOTED_QUESTION_WORDS` words, no guillemets or slots of its
    own, opening on a capital, and sharing no three words with what the learner wrote
    (a character echoing the learner is not quoted, #620)."""

    text = " ".join(str(asked or "").split()).strip()
    if not text or not text.endswith("?") or not text[:1].isupper():
        return None
    if any(mark in text for mark in '«»"“”{}') or "learner" in text.casefold():
        return None
    if len(_words(text)) > QUOTED_QUESTION_WORDS or len(text) > 60:
        return None
    if re.search(r"[.!?…]", text[:-1]):
        return None
    for reply in said:
        if _runs(text, 3) & _runs(reply, 3):
            return None
    return text


def problem(line: Any, *, said: Iterable[str] = (), quoted: str | None = None) -> str | None:
    """Why a composed line may not be shown, or ``None``: empty, a slot left unfilled,
    guillemets around anything but the character's recorded question (``quoted``), too
    long (:data:`MAX_WORDS`; :data:`MAX_QUOTED_WORDS` / :data:`MAX_QUOTED_CHARS` with the
    question), not ending as a sentence, or, outside the character's question, sharing a
    run of :data:`QUOTE_RUN` words with something the learner wrote (#620, #949: the
    learner's raw text is never shown)."""

    text = " ".join(str(line or "").split())
    if not text:
        return "empty"
    if "{" in text or "}" in text:
        return "slot"
    rest = text
    if quoted:
        span = f"« {quoted} »"
        if text.count(span) != 1:
            return "quote"
        rest = text.replace(span, " ")
    if any(mark in rest for mark in '«»"“”'):
        return "quote"
    if quoted:
        if len(_words(text)) > MAX_QUOTED_WORDS or len(text) > MAX_QUOTED_CHARS:
            return "too_long"
    elif len(_words(text)) > MAX_WORDS:
        return "too_long"
    if not text.endswith(("?", ".", "…", "!")):
        return "unfinished"
    runs = _runs(rest, QUOTE_RUN)
    for reply in said:
        if _runs(reply, QUOTE_RUN) & runs:
            return "learner_quote"
    return None


def _who(character_id: str | None, name: str) -> tuple[str, str, str]:
    from app.services import cast_registry

    found = cast_registry.member(character_id) if character_id else None
    pronouns = _PRONOUNS.get(getattr(found, "gender", "x") or "x")
    return pronouns if pronouns else (name, name, name)


def _die(seed: str, *parts: Any) -> int:
    return int(hashlib.sha256(":".join([seed, *map(str, parts)]).encode()).hexdigest(), 16)


def _consequence(
    kind: str, group: str, slots: dict[str, str], *, seed: str, date: Any, used: list[str]
) -> dict[str, str]:
    """The seeded consequence, unless a recent hook said it (two «non» to Lila in a week
    end on two different questions)."""

    rows = _CONSEQUENCES[kind][group]
    start = _die(seed, "remembered", date, kind) % len(rows)
    said_lately = [_folded(line) for line in used]
    for step in range(len(rows)):
        row = rows[(start + step) % len(rows)]
        if not any(_folded(_elide(row["fr"].format(**slots))) in line for line in said_lately):
            return row
    return rows[start]


def compose(
    found: dict[str, Any],
    *,
    character_id: str | None,
    name: str,
    band: Any,
    seed: str,
    date: str | None,
    said: Iterable[str] = (),
    authored: dict | None = None,
    used: Iterable[str] = (),
) -> dict[str, Any] | None:
    """The hook row for a decision, or ``None`` when no clean line can be said. The
    line quotes the character's question when it can (:func:`quotable`), else names the
    character; either way it never holds a word of the learner's."""

    name = " ".join(str(name or "").split())
    kind = str(found.get("kind") or "")
    if not name or kind not in _CONSEQUENCES:
        return None
    said = list(said)
    group = band_group(band)
    who, who_en, who_de = _who(character_id, name)
    asked = quotable(found.get("asked_fr"), said=said)
    slots = {"name": name, "who": who, "who_en": who_en, "who_de": who_de, "asked": asked or ""}
    consequence = _consequence(kind, group, slots, seed=seed, date=date, used=list(used))
    line = recalled = ""
    for form in ("quoted", "plain") if asked else ("plain",):
        decided = _DECIDED[form][kind]
        recalled = decided["fr"].format(**slots)
        line = _elide(f"{recalled} {consequence['fr'].format(**slots)}")
        quoted = asked if form == "quoted" else None
        if (issue := problem(line, said=said, quoted=quoted)) is None:
            break
        logger.info("remembered_hook: %s line refused (%s)", form, issue)
    else:
        return None
    quoted_form = asked is not None and f"« {asked} »" in line
    if not quoted_form:
        slots["asked"] = ""
    form = "quoted" if quoted_form else "plain"
    native = {
        lang: f"{_DECIDED[form][kind][lang].format(**slots)} {consequence[lang].format(**slots)}"
        for lang in ("en", "de")
    }
    tail = _PUSH_TAILS[kind][group][
        _die(seed, "remembered-push", date, kind) % len(_PUSH_TAILS[kind][group])
    ]
    head = _PUSH_HEAD[kind]
    lead_fr = f"« {asked} » " if quoted_form else ""
    lead_native = {
        "en": f"“{asked}” " if quoted_form else "",
        "de": f"„{asked}“ " if quoted_form else "",
    }
    return {
        "text_fr": line,
        "open_fr": line,
        "character_id": character_id,
        "character_name": name,
        "date": date,
        "ref": f"remembered:{date}:{kind}",
        "kind": "promise" if kind == "agreed" else "question",
        "source": SOURCE,
        REMEMBERED_KEY: {
            "decision": kind,
            "at": found.get("at"),
            "band": group,
            # The character's own question, as quoted (None when it could not be).
            "asked_fr": asked if quoted_form else None,
            "recalled_fr": recalled,
            "native": native,
            "push_fr": {
                register: f"{lead_fr}{head[register]} {tail[register]}"
                for register in ("tu", "vous")
            },
            "push_native": {
                lang: f"{lead_native[lang]}{head[lang]} {tail[lang]}" for lang in ("en", "de")
            },
            # The hook this line stands in for: the pick, the contract or the beat that
            # still steers tomorrow's page.
            "authored": {key: (authored or {}).get(key) for key in ("text_fr", "ref", "source")}
            if authored
            else None,
        },
    }


def remember(
    teaser: dict | None,
    *,
    opening_line_fr: Any,
    exchanges: list[dict[str, Any]],
    ledger: Any,
    character_id: str | None,
    name: str | None,
    band: Any,
    seed: str,
    date: str | None,
    said: Iterable[str] = (),
    used: Iterable[str] = (),
) -> dict | None:
    """The day's hook with the learner's decision remembered, or ``teaser`` unchanged:
    the flag off, a tentpole's own «À suivre…», no decision in the record, a line that
    fails :func:`problem`, or any error."""

    if not enabled():
        return teaser
    try:
        from app.services.story_teaser import hook_source

        if teaser and hook_source(teaser) == "tentpole":
            return teaser
        found = decision(opening_line_fr, exchanges, ledger)
        if found is None:
            return teaser
        row = compose(
            found,
            character_id=character_id,
            name=str(name or ""),
            band=band,
            seed=seed,
            date=date,
            said=list(said),
            authored=teaser,
            used=list(used),
        )
        return row or teaser
    except Exception:  # noqa: BLE001 - the authored hook is never lost to this
        logger.exception("remembered_hook: failed; the authored hook stands")
        return teaser


def of(teaser: Any) -> dict[str, Any] | None:
    """The ``remembered`` block of a hook row, while the flag is on."""

    if not enabled() or not isinstance(teaser, dict):
        return None
    block = teaser.get(REMEMBERED_KEY)
    return block if isinstance(block, dict) and block.get("decision") else None


def previously(live: dict | None, lines: list[str], *, limit: int = 3) -> list[str]:
    """«Précédemment» opens on yesterday's decision, as the hook told it, when the last
    played day ended on a remembered hook: tomorrow's page then delivers what the hook
    teased. Unchanged otherwise."""

    try:
        from app.services.living_story import TEASER_KEY, yesterday_hook

        if not enabled() or yesterday_hook(live or {}) is None:
            return lines
        block = of((live or {}).get(TEASER_KEY))
        recalled = " ".join(str((block or {}).get("recalled_fr") or "").split())
        if not recalled:
            return lines
        rest = [line for line in lines if _folded(recalled) not in _folded(line)]
        return [recalled, *rest][:limit]
    except Exception:  # noqa: BLE001 - the box never costs the page
        logger.exception("remembered_hook: «Précédemment» keeps its own lines")
        return lines


def glossed_push(block: dict[str, Any], *, register: str, language: Any, band: Any) -> str | None:
    """The evening push body: the character's own line in the register they use with the
    learner tonight, with its gloss below B1 (Pilot P9: an A-level push carries its
    translation). ``None`` below B1 in a language the templates do not gloss."""

    lines = block.get("push_fr") if isinstance(block.get("push_fr"), dict) else {}
    line = str(lines.get("tu" if register == "tu" else "vous") or "")
    if not line:
        return None
    from app.services import chrome_language

    lang = chrome_language.mother_tongue(language)
    if band_group(band) == "B" or lang == "fr":
        return line
    native = str((block.get("push_native") or {}).get(lang) or "")
    return f"{line}\n{native}" if native else None


__all__ = [
    "REMEMBERED_KEY",
    "SOURCE",
    "band_group",
    "compose",
    "decision",
    "enabled",
    "glossed_push",
    "of",
    "previously",
    "problem",
    "puts_a_choice",
    "quotable",
    "remember",
]
