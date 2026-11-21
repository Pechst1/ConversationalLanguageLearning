"""Tomorrow's hook remembers what the learner decided (``STORY_REMEMBERED_HOOK``).

Walks of November (#466, #455, #620): the end of a day said «Tomorrow · On va aider
Lila à l'école.», a flat line that ignored the «non» the learner had just given Lila,
or, worse, quoted the learner's own reply back as a promise, errors and all.

With the flag on, the day's one hook (``living_story._hook_after_day``) is read against
the scene's record. When the learner gave a clear yes or no to something a character put
to them (a proposal, «d'accord ?», or an invitation, «Tu viens ?», «On partage ?»), the
hook says that decision and leaves its consequence open, in the serial's voice:

    «Tu as dit non à Lila. Est-ce qu'elle va accepter ça ?»

Built here, deterministically, from authored templates per decision and level band; no
model call. The line never quotes the learner (only the character's name and the
decision kind come from the scene), never says «oui» once the learner said «non» (a
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
#: The one line every surface prints is at most this long (``story_teaser.HOOK_LINE_WORDS``).
MAX_WORDS = 14
#: A run of this many words shared with a learner reply is a quote, and refused. The line
#: is built from templates and a name, so this only ever costs a coincidence (the learner
#: wrote «je dis non à Lila»): the authored hook then stands.
QUOTE_RUN = 4


def enabled() -> bool:
    return bool(getattr(settings, "STORY_REMEMBERED_HOOK", False))


# ---------------------------------------------------------------------------
# Templates: per decision, per level band, a few variants. {name}: the character's
# spoken name. {who}: «elle» / «il», or the name again when the learner picks the
# person's gender. Every French line is short, at A1 below B1 (present, near future,
# passé composé of «dire»), and opens on what the learner did, never on their words.
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, dict[str, list[dict[str, Any]]]] = {
    "refused": {
        "A": [
            {
                "fr": "Tu as dit non à {name}. Est-ce que {who} va accepter ça ?",
                "native": {
                    "en": "You said no to {name}. Will {who_en} accept that?",
                    "de": "Du hast {name} Nein gesagt. Wird {who_de} das akzeptieren?",
                },
                "push": {
                    "tu": "Tu m'as dit non. J'y pense encore.",
                    "vous": "Vous m'avez dit non. J'y pense encore.",
                },
                "push_native": {
                    "en": "You said no to me. I'm still thinking about it.",
                    "de": "Du hast Nein gesagt. Ich denke noch daran.",
                },
            },
            {
                "fr": "Tu as dit non à {name}. Demain, est-ce que {who} demande encore ?",
                "native": {
                    "en": "You said no to {name}. Tomorrow, will {who_en} ask again?",
                    "de": "Du hast {name} Nein gesagt. Fragt {who_de} morgen noch einmal?",
                },
                "push": {
                    "tu": "Tu m'as dit non. Demain, je demande encore ?",
                    "vous": "Vous m'avez dit non. Demain, je demande encore ?",
                },
                "push_native": {
                    "en": "You said no to me. Shall I ask again tomorrow?",
                    "de": "Du hast Nein gesagt. Frage ich morgen noch einmal?",
                },
            },
        ],
        "B": [
            {
                "fr": "Tu as dit non à {name}. Reste à savoir comment {who} va le prendre.",
                "native": {
                    "en": "You said no to {name}. It remains to be seen how {who_en} will take it.",
                    "de": "Du hast {name} Nein gesagt. Bleibt die Frage, wie {who_de} das aufnimmt.",
                },
                "push": {
                    "tu": "Tu m'as dit non. J'y repense ce soir… on en reparle demain ?",
                    "vous": "Vous m'avez dit non. J'y repense ce soir… on en reparle demain ?",
                },
                "push_native": {
                    "en": "You said no to me. I'm thinking it over tonight… shall we talk tomorrow?",
                    "de": "Du hast Nein gesagt. Ich denke heute Abend darüber nach… reden wir morgen?",
                },
            },
            {
                "fr": "Tu as dit non à {name}. Est-ce que {who} va insister, ou laisser tomber ?",
                "native": {
                    "en": "You said no to {name}. Will {who_en} insist, or let it go?",
                    "de": "Du hast {name} Nein gesagt. Bleibt {who_de} dran, oder lässt es fallen?",
                },
                "push": {
                    "tu": "Ton non, je l'ai bien entendu. Mais je n'ai pas dit mon dernier mot.",
                    "vous": "Votre non, je l'ai bien entendu. Mais je n'ai pas dit mon dernier mot.",
                },
                "push_native": {
                    "en": "I heard your no. But I haven't said my last word.",
                    "de": "Dein Nein habe ich gehört. Aber das letzte Wort ist noch nicht gesprochen.",
                },
            },
        ],
    },
    "agreed": {
        "A": [
            {
                "fr": "Tu as dit oui à {name}. Et demain, qu'est-ce qui va changer ?",
                "native": {
                    "en": "You said yes to {name}. And tomorrow, what will change?",
                    "de": "Du hast {name} Ja gesagt. Und was ändert sich morgen?",
                },
                "push": {
                    "tu": "Tu m'as dit oui. Merci ! On se voit demain ?",
                    "vous": "Vous m'avez dit oui. Merci ! On se voit demain ?",
                },
                "push_native": {
                    "en": "You said yes to me. Thank you! See you tomorrow?",
                    "de": "Du hast Ja gesagt. Danke! Sehen wir uns morgen?",
                },
            },
            {
                "fr": "Tu as dit oui à {name}. Est-ce que tout va bien se passer ?",
                "native": {
                    "en": "You said yes to {name}. Will everything go well?",
                    "de": "Du hast {name} Ja gesagt. Geht alles gut?",
                },
                "push": {
                    "tu": "Tu m'as dit oui. Ça me fait plaisir. À demain ?",
                    "vous": "Vous m'avez dit oui. Ça me fait plaisir. À demain ?",
                },
                "push_native": {
                    "en": "You said yes to me. That makes me happy. See you tomorrow?",
                    "de": "Du hast Ja gesagt. Das freut mich. Bis morgen?",
                },
            },
        ],
        "B": [
            {
                "fr": "Tu as dit oui à {name}. Que va changer ce oui ?",
                "native": {
                    "en": "You said yes to {name}. What will that yes change?",
                    "de": "Du hast {name} Ja gesagt. Was wird dieses Ja verändern?",
                },
                "push": {
                    "tu": "Tu m'as dit oui. Je compte sur toi demain.",
                    "vous": "Vous m'avez dit oui. Je compte sur vous demain.",
                },
                "push_native": {
                    "en": "You said yes to me. I'm counting on you tomorrow.",
                    "de": "Du hast Ja gesagt. Ich zähle morgen auf dich.",
                },
            },
            {
                "fr": "Tu as dit oui à {name}. Demain, on verra si c'était une bonne idée.",
                "native": {
                    "en": "You said yes to {name}. Tomorrow we'll see if it was a good idea.",
                    "de": "Du hast {name} Ja gesagt. Morgen sehen wir, ob das eine gute Idee war.",
                },
                "push": {
                    "tu": "Tu m'as dit oui. Demain, on voit si j'avais raison de demander.",
                    "vous": "Vous m'avez dit oui. Demain, on voit si j'avais raison de demander.",
                },
                "push_native": {
                    "en": "You said yes to me. Tomorrow we'll see if I was right to ask.",
                    "de": "Du hast Ja gesagt. Morgen sehen wir, ob es richtig war zu fragen.",
                },
            },
        ],
    },
}
#: «Précédemment» on the next day: the decision, said once, in the past.
_RECALLED = {"refused": "Tu as dit non à {name}.", "agreed": "Tu as dit oui à {name}."}
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
    """``{"kind": "refused" | "agreed", "at": index}``: the learner's decision in a scene,
    or ``None`` when the record holds none.

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
                found.append({"kind": "refused" if intent == "no" else "agreed", "at": index})
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


def problem(line: Any, *, said: Iterable[str] = ()) -> str | None:
    """Why a composed line may not be shown, or ``None``: empty, a slot left unfilled,
    guillemets (they hold only learner words, and this line holds none), longer than
    :data:`MAX_WORDS`, not ending as a sentence, or sharing a run of :data:`QUOTE_RUN`
    words with something the learner wrote (#620, #949: their raw text is never shown)."""

    text = " ".join(str(line or "").split())
    if not text:
        return "empty"
    if "{" in text or "}" in text:
        return "slot"
    if any(mark in text for mark in '«»"“”'):
        return "quote"
    if len(_words(text)) > MAX_WORDS:
        return "too_long"
    if not text.endswith(("?", ".", "…", "!")):
        return "unfinished"
    own = _folded(text).split()
    runs = {" ".join(own[i : i + QUOTE_RUN]) for i in range(max(0, len(own) - QUOTE_RUN + 1))}
    for reply in said:
        words = _folded(reply).split()
        if any(
            " ".join(words[i : i + QUOTE_RUN]) in runs
            for i in range(max(0, len(words) - QUOTE_RUN + 1))
        ):
            return "learner_quote"
    return None


def _who(character_id: str | None, name: str) -> tuple[str, str, str]:
    from app.services import cast_registry

    found = cast_registry.member(character_id) if character_id else None
    pronouns = _PRONOUNS.get(getattr(found, "gender", "x") or "x")
    return pronouns if pronouns else (name, name, name)


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
    """The hook row for a decision, or ``None`` when no clean line can be said."""

    name = " ".join(str(name or "").split())
    kind = str(found.get("kind") or "")
    if not name or kind not in _TEMPLATES:
        return None
    group = band_group(band)
    variants = _TEMPLATES[kind][group]
    pick = int(hashlib.sha256(f"{seed}:remembered:{date}:{kind}".encode()).hexdigest(), 16) % len(
        variants
    )
    who, who_en, who_de = _who(character_id, name)
    slots = {"name": name, "who": who, "who_en": who_en, "who_de": who_de}
    # The seeded variant, unless a recent hook said it already (two «non» to Lila in a
    # week are two different lines).
    used_lines = {_folded(text) for text in used}
    order = [variants[(pick + step) % len(variants)] for step in range(len(variants))]
    template = next(
        (row for row in order if _folded(_elide(row["fr"].format(**slots))) not in used_lines),
        order[0],
    )
    line = _elide(template["fr"].format(**slots))
    if (issue := problem(line, said=said)) is not None:
        logger.info("remembered_hook: line refused (%s); the authored hook stands", issue)
        return None
    native = {lang: text.format(**slots) for lang, text in template["native"].items()}
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
            "recalled_fr": _RECALLED[kind].format(name=name),
            "native": native,
            "push_fr": dict(template["push"]),
            "push_native": dict(template["push_native"]),
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
    lang = str(language or "en")[:2]
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
    "remember",
]
