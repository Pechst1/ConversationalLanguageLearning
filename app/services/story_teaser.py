"""Tomorrow's line: the one forward hook a finished scene leaves (WP-99, #466).

The hook names a real open row of the story or says nothing: never an invented plot.
It is written here and stored on the living story as ``next_teaser``, and the closing
panel's «À suivre…», Home, Done and the morning push all read that one row.

A hook has two parts. ``text_fr`` is the whole line, in the character's voice, for the
closing panel and the push. ``open_fr`` is what stays open, as a whole sentence that
ends on its question: that is what «Tomorrow» prints on Home and Done, so no surface has
to cut a line that opens on a voice («Au fait…» was the walks' Tomorrow for a week).

Guillemets hold only what the learner wrote in this scene, in a sentence that needed no
correction. Anything else the learner said is told, or not said at all (#445, #620).

``living_story`` re-exports these names.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date as _date
from typing import Any

TEASER_WINDOW_DAYS = 14
TEASER_LEDGER_LIMIT = 30
TEASER_QUOTE_CHARS = 110
TEASER_KEY = "next_teaser"
TEASERS_KEY = "teasers"

# One opener per cast member, in their own voice; `tu`/`vous` where it matters.
TEASER_VOICES: dict[str, dict[str, str]] = {
    "marin_leveque": {"tu": "Dis, j'y repense… C'est peut-être un signe.", "vous": "Dites, j'y repense… C'est peut-être un signe."},
    "lila_bonnet": {"tu": "Toi, tu me caches quelque chose…", "vous": "Vous, vous me cachez quelque chose…"},
    "augustin_de_roncourt": {"tu": "Règle numéro un de La Méthode : on n'oublie rien.", "vous": "Règle numéro un de La Méthode : on n'oublie rien."},
    "romy_tremblay": {"tu": "Bon, c'est quoi la vraie histoire ?", "vous": "Bon, c'est quoi la vraie histoire ?"},
    "margaux_barman": {"tu": "J'ai rien entendu. Mais quand même…", "vous": "Je n'ai rien entendu. Mais quand même…"},
    "tiago_moreira": {"tu": "Pardon, une question…", "vous": "Pardon, une question…"},
}
DEFAULT_TEASER_VOICE = {"tu": "Au fait…", "vous": "Au fait…"}
#: What a hook says before what stays open: per kind, per variant, per register.
_TEASER_LEADS: dict[str, tuple[dict[str, str], dict[str, str]]] = {
    # #378: guillemets hold only words somebody said.
    "commitment": (
        {"tu": "Tu n'as pas oublié :", "vous": "Vous n'avez pas oublié :"},
        {"tu": "Tu as promis, hein :", "vous": "Vous avez promis, hein :"},
    ),
    # #445: the same promise in plain words, when the learner's own needed correcting.
    "told": (
        {"tu": "Tu n'as pas oublié.", "vous": "Vous n'avez pas oublié."},
        {"tu": "Tu as promis, hein.", "vous": "Vous avez promis, hein."},
    ),
    # A planted detail and a season question are the story's, not a line of dialogue.
    "plant": (
        {"tu": "Je repense à ce détail.", "vous": "Je repense à ce détail."},
        {"tu": "", "vous": ""},
    ),
    "thread": (
        {"tu": "Il faudra qu'on en parle.", "vous": "Il faudra qu'on en parle."},
        {"tu": "Demain, peut-être, on saura.", "vous": "Demain, peut-être, on saura."},
    ),
}
#: A question a writer wrote for «Tomorrow» is at most this long (owner, 2026-11-01, #450).
TOMORROW_WORDS = 9
#: A row told with its question runs longer, whole; a longer one is not the day's hook.
TOMORROW_TOLD_WORDS = 14
_TEASER_QUOTE = re.compile(r"«\s*([^«»]+?)\s*»")
_INFINITIVE = re.compile(r"^[a-zàâäçéèêëîïôöûùüÿœ]{2,}(?:er|ir|re|oir)$")
#: Words that end like an infinitive but open a noun phrase.
_NOT_AN_INFINITIVE = {"notre", "votre", "autre", "autres", "chaque", "quelque", "premier", "dernier", "hier", "cher"}
_PERSON = re.compile(r"\b(?:je|j|tu|vous|nous|moi|toi|me|m|te|t|mon|ma|mes|ton|ta|tes|notre|votre)\b", re.IGNORECASE)
_NUMBER_WORDS = {
    "un", "une", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze",
    "treize", "quatorze", "quinze", "seize", "vingt", "trente", "quarante", "cinquante", "soixante", "cent", "mille",
}


def _engine() -> Any:
    """``living_story``, read at call time: it imports this module at load."""

    from app.services import living_story

    return living_story


def _words(text: Any) -> set[str]:
    return {word for word in re.findall(r"\w+", str(text or "").casefold()) if len(word) > 3}


def _clip_quote(text: Any, limit: int = TEASER_QUOTE_CHARS) -> str:
    line = " ".join(str(text or "").split()).strip().strip("«»\"").strip()
    if len(line) <= limit:
        return line
    return line[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _word_count(text: str) -> int:
    """Words as a reader counts them: anything with a letter or a digit."""

    return sum(1 for token in text.split() if re.search(r"\w", token))


def _folded(text: Any) -> str:
    from app.services.scene_ledger import _folded as folded

    return folded(str(text or ""))


def told_promise(text_fr: Any, source_quote: Any) -> str | None:
    """#445: a promise in plain words, or ``None`` when it cannot be told safely.

    The row's ``text_fr`` is the model's «what the learner will do» («Apporter du pain
    dimanche.»). It goes in a character's mouth, so it must be a bare infinitive phrase
    that names nobody, must share a word with what the learner wrote (it is theirs, not
    an invention) and may hold no number they never wrote («quatorze heures» for «deux
    heures», #378; «14h» for «2h»)."""

    line = " ".join(str(text_fr or "").split()).strip(" .!?…»«\"")
    quote = str(source_quote or "").strip()
    if not line or not quote:
        return None
    first = line.split(" ", 1)[0].casefold()
    if not _INFINITIVE.match(first) or first in _NOT_AN_INFINITIVE:
        return None
    if _PERSON.search(line.replace("'", " ").replace("’", " ")):
        return None
    if not _words(line) & _words(quote):
        return None
    said = set(re.findall(r"\w+", quote.casefold()))
    for token in re.findall(r"\w+", line.casefold()):
        if (any(char.isdigit() for char in token) or token in _NUMBER_WORDS) and token not in said:
            return None
    return f"{line[:1].upper()}{line[1:]}."


def teaser_candidates(live: dict, world: dict, *, clean: Iterable[str] = ()) -> list[dict]:
    """The open rows a teaser may name: promises, unpaid plants, open season questions.

    ``clean``: the learner's replies in this scene that needed no correction. A promise
    in one of them is quoted; any other is told (:func:`told_promise`) or left out. The
    model's restatement is never quoted (the walk of 30 Oct read «Tu n'as pas oublié ?
    « Je serai chez moi après quatorze heures. »», a sentence nobody said)."""

    rows: list[dict] = []
    clean_lines = [_folded(line) for line in clean if str(line or "").strip()]
    for row in live.get("commitments") or []:
        if not isinstance(row, dict) or row.get("status") != "open" or not row.get("id"):
            continue
        quote = str(row.get("source_quote") or "").strip()
        if not quote:
            continue
        said_clean = any(_folded(quote) in line for line in clean_lines)
        told = None if said_clean else told_promise(row.get("text_fr"), quote)
        if not said_clean and told is None:
            continue
        rows.append({
            "ref": str(row["id"]), "kind": "commitment", "text_fr": quote if said_clean else told,
            "characters": [str(who) for who in row.get("witnesses") or []],
            **({} if said_clean else {"told": True}),
        })
    for row in live.get("planted") or []:
        if isinstance(row, dict) and row.get("status") != "paid" and row.get("id") and row.get("text_fr"):
            rows.append({
                "ref": str(row["id"]), "kind": "plant", "text_fr": str(row["text_fr"]),
                "characters": [str(row.get("character_id") or "")],
            })
    # Season questions are season-wide: any cast member may raise one.
    for row in _engine().threads_projection(world, live):
        if row["state"] != "closed" and row.get("text_fr"):
            rows.append({"ref": row["key"], "kind": "thread", "text_fr": row["text_fr"], "characters": []})
    return rows


def teaser_grounded(text: str, ref: str | None, candidates: list[dict]) -> bool:
    """True only when the teaser names a real open row: its id, and its words."""

    row = next((item for item in candidates if item["ref"] == ref), None) if ref else None
    if row is None:
        return False
    needed = _words(_clip_quote(row["text_fr"]))
    if not needed:
        return False
    return len(needed & _words(text)) >= min(2, len(needed))


def _finished(text: str) -> str:
    """``text`` as a sentence: a detail may end on no mark at all."""

    line = text.rstrip()
    return line if line.endswith((".", "!", "?", "…")) else f"{line}."


def open_line(candidate: dict, *, register: str, variant: int = 0) -> str:
    """What stays open, as the reader can carry it: the row's words, ending on a question."""

    text = _clip_quote(candidate["text_fr"])
    key = "tu" if register == "tu" else "vous"
    index = int(variant) % 2
    kind = candidate["kind"]
    if kind == "commitment":
        if candidate.get("told"):
            return f"{text.rstrip(' .')} : c'est toujours d'accord ?"
        return f"« {_finished(text)} » C'est toujours d'accord ?"
    if kind == "plant":
        ask = ("Pourquoi ?", {"tu": "Tu as remarqué ?", "vous": "Vous avez remarqué ?"}[key])[index]
        return f"{_finished(text)} {ask}"
    if text.endswith("?"):
        return text
    return f"{_finished(text)} {'Qu’en penses-tu ?' if key == 'tu' else 'Qu’en pensez-vous ?'}"


def compose_teaser(
    candidate: dict, *, character_id: str | None, register: str, variant: int = 0
) -> str:
    """The hook: the voice, what leads in, and what stays open."""

    voice = TEASER_VOICES.get(str(character_id or ""), DEFAULT_TEASER_VOICE)
    key = "tu" if register == "tu" else "vous"
    kind = "told" if candidate.get("told") else candidate["kind"]
    lead = _TEASER_LEADS[kind][int(variant) % 2][key]
    return " ".join(part for part in (voice[key], lead, open_line(candidate, register=register, variant=variant)) if part)


def teaser_quotes_only_said(text: str, said: Iterable[str]) -> bool:
    """#620: True when every quotation in a finished hook is a line of ``said``.

    Guillemets hold only words the learner wrote in the scene being closed. The check
    runs on the composed line, whatever row wrote it, so no hook can put a stale or
    restated sentence in the learner's mouth (live walks of 30 Oct, 1 Nov and 9 Nov all
    read «Tu as promis : « … »» over words nobody said). With ``said=()`` a hook quotes
    nothing. A quote the hook clipped with «…» is still the learner's."""

    lines = [_folded(line) for line in said or [] if str(line or "").strip()]
    for span in _TEASER_QUOTE.findall(str(text or "")):
        quote = _folded(span.rstrip("…").rstrip())
        if quote and not any(quote in line for line in lines):
            return False
    return True


def question_problem(text: Any, *, known: str, ledger: dict | None = None) -> str | None:
    """Why a written question cannot be tomorrow's line, as a code, or ``None``.

    Compared against what the scene holds, never against what the question means: it is
    one sentence that ends on its question, at most :data:`TOMORROW_WORDS` words, quotes
    nobody, brings in no number or name the scene does not hold, touches something the
    scene holds, and does not ask again what the learner has answered. A failed check
    drops the question and the hook falls back to the story's open rows: it costs no
    retry and no turn, and the writer stays free to write any question that holds."""

    from app.services import lane_guards, scene_ledger

    line = " ".join(str(text or "").split())
    if not line.endswith("?"):
        return "tomorrow_not_a_question"
    # «M. Marchand» is one word; any other full stop, «!» or «?» makes it two sentences.
    if re.search(r"[.!?…]", re.sub(r"\bM\.\s", "M ", line[:-1])):
        return "tomorrow_not_one_sentence"
    if not 3 < _word_count(line) <= TOMORROW_WORDS:
        return "tomorrow_length"
    if any(mark in line for mark in "«»\"“”"):
        return "tomorrow_quotes"
    if scene_ledger.brings_in_new(line, known):
        return "tomorrow_brings_in_new_fact"
    if not _words(line) & _words(known):
        return "tomorrow_off_the_scene"
    if lane_guards.reasked_question(line, ledger):
        return "tomorrow_already_answered"
    return None


def question_left_open(ledger: dict | None) -> str | None:
    """The scene's own open question, when no writer wrote one: the last thing a character
    asked and nobody answered, if it can stand alone as tomorrow's line."""

    rows = [row for row in (ledger or {}).get("still_open") or [] if isinstance(row, dict)]
    for row in reversed(rows):
        line = " ".join(str(row.get("text_fr") or "").split())
        if row.get("kind") == "question" and row.get("by") == "character" and line.endswith("?"):
            if 3 < _word_count(line) <= TOMORROW_WORDS and not re.search(r"[«»]", line):
                return line
    return None


def _days_between(earlier: str | None, later: str | None) -> int | None:
    a, b = _engine()._date_of(earlier), _engine()._date_of(later)
    if not a or not b:
        return None
    return (_date.fromisoformat(b) - _date.fromisoformat(a)).days


def next_teaser(
    live: dict,
    world: dict,
    *,
    character_id: str | None,
    register: str,
    date: str | None,
    seed: str,
    name: str | None = None,
    said: Iterable[str] = (),
    clean: Iterable[str] = (),
    question: str | None = None,
) -> dict | None:
    """One forward line per resolution, or None — never an invented plot.

    ``question``: what a writer left open in this scene, already checked
    (:func:`question_problem`), or the scene's own (:func:`question_left_open`). It leads.
    Otherwise this prefers a row the addressed character witnessed, then any open row, in
    a seeded order; skips any row or wording already used as a teaser in the last
    ``TEASER_WINDOW_DAYS`` days; and validates the composed line against the row it names
    before it is kept. ``said`` and ``clean`` are this scene's replies, and those that
    needed no correction: a hook quotes only the second, whatever row wrote it.
    """

    engine = _engine()
    today = engine._date_of(date) or engine._today().isoformat()
    recent = [
        row for row in live.get(TEASERS_KEY) or []
        if isinstance(row, dict)
        and (_days_between(row.get("date"), today) is not None)
        and 0 <= _days_between(row.get("date"), today) < TEASER_WINDOW_DAYS
    ]
    used_refs = {str(row.get("ref")) for row in recent}
    last_kind = str((recent[-1] if recent else {}).get("kind") or "")
    used_texts = {str(row.get("text_fr")) for row in recent}
    used_open = {str(row.get("open_fr")) for row in recent if row.get("open_fr")}
    if question and question not in used_open:
        voice = TEASER_VOICES.get(str(character_id or ""), DEFAULT_TEASER_VOICE)["tu" if register == "tu" else "vous"]
        return {
            "text_fr": f"{voice} {question}",
            "open_fr": question,
            "character_id": character_id,
            **({"character_name": name} if name else {}),
            "date": today,
            "ref": f"scene:{today}",
            "kind": "question",
        }
    candidates = teaser_candidates(live, world, clean=clean)
    fresh = [row for row in candidates if row["ref"] not in used_refs]
    varied = len({row["kind"] for row in fresh}) > 1
    first_name = str(name or "").split(" ")[0].casefold()
    # Variety first (not the same kind of line as yesterday's), then the rows this
    # character was there for, then the learner's own dice.
    fresh.sort(
        key=lambda row: (
            1 if varied and row["kind"] == last_kind else 0,
            # A question about the speaker, quoted in the third person, sounds wrong
            # in their own mouth: someone else raises it first.
            1 if first_name and row["kind"] == "thread" and first_name in _words(row["text_fr"]) else 0,
            0 if character_id and character_id in row["characters"] else 1,
            engine._die(seed, "teaser", today, row["ref"]),
        )
    )
    variant = engine._die(seed, "teaser-frame", today)
    for row in fresh:
        text = compose_teaser(row, character_id=character_id, register=register, variant=variant)
        if text in used_texts or not teaser_grounded(text, row["ref"], candidates):
            continue
        # #620: a promise from an earlier day is not this scene's to quote.
        if not teaser_quotes_only_said(text, said):
            continue
        # #466: «Tomorrow» prints this whole. A row too long to say whole is not the hook.
        opened = open_line(row, register=register, variant=variant)
        if _clip_quote(row["text_fr"], 10_000) != _clip_quote(row["text_fr"]) or _word_count(opened) > TOMORROW_TOLD_WORDS:
            continue
        return {
            "text_fr": text,
            "open_fr": opened,
            "character_id": character_id,
            **({"character_name": name} if name else {}),
            "date": today,
            "ref": row["ref"],
            "kind": row["kind"],
        }
    return None


def teasers_after(live: dict, teaser: dict | None) -> list[dict]:
    rows = [row for row in live.get(TEASERS_KEY) or [] if isinstance(row, dict)]
    if teaser:
        rows.append(
            {key: teaser.get(key) for key in ("ref", "kind", "text_fr", "open_fr", "date", "character_id")}
        )
    return rows[-TEASER_LEDGER_LIMIT:]
