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

# One opener per cast member, in their own voice; `tu`/`vous` where it matters. #822: the
# «À suivre…» prints the hook as a caption, in nobody's bubble, so an opener is said only
# when :func:`lead_problem` lets it through (no «je» nobody said, no «ne» dropped):
# Margaux's «J'ai rien entendu», Marin's «j'y repense» and Lila's «tu me caches» never are.
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


#: #822: what may stand before a hook's question. The hook is printed as a caption, the
#: last words of the page, so it may not speak as somebody («je», «me», «moi») unless a
#: character said that very line in the scene, and it never drops the «ne» of a negation.
_NEGATIVE = re.compile(r"\b(?:rien|jamais|personne)\b", re.IGNORECASE)
_NE = re.compile(r"\bn(?:e\b|['’])", re.IGNORECASE)
#: Uses of the words that are no negation: «de rien», «pour rien», «une personne».
_NOT_A_NEGATION = re.compile(
    r"\b(?:de|pour)\s+rien\b|\b(?:une|la|les|des|cette|chaque|en)\s+personnes?\b", re.IGNORECASE
)
#: A negation needs its «ne» only on a verb: «Rien de grave.», «Jamais !» need none.
_HAS_SUBJECT = re.compile(
    r"(?:^|[\s,;:…(])(?:(?:je|tu|il|elle|on|nous|vous|ils|elles|ça|cela)\b|[jc]['’])"
    r"|^(?:personne|rien)\s+(?!de\b|d['’])\w",
    re.IGNORECASE,
)
_FIRST_PERSON = re.compile(r"(?:^|[\s,;:…(])(?:(?:je|me|moi)\b|[jm]['’])", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def drops_ne(sentence: Any) -> bool:
    """Whether a sentence says «rien», «jamais» or «personne» on a verb without its «ne»
    («J'ai rien entendu.»): spoken French an A1 page does not teach (#822)."""

    line = _NOT_A_NEGATION.sub(" ", " ".join(str(sentence or "").split())).strip()
    return bool(_NEGATIVE.search(line) and _HAS_SUBJECT.search(line) and not _NE.search(line))


def lead_problem(lead: Any, *, spoken: Iterable[str] = ()) -> str | None:
    """Why a line cannot stand before a hook's question, as a code, or ``None`` (#822).

    ``hook_dropped_ne``: a sentence drops the «ne» of its negation. ``hook_unsaid_speech_act``:
    a sentence speaks in the first person and is not a line a character said in this scene
    (``spoken``): the hook is printed in nobody's bubble, so «Je n'ai rien entendu» there is
    a speech act no character made. Guillemets are the learner's words, checked by
    :func:`teaser_quotes_only_said`."""

    said = {_folded(line).strip(" .!?…") for line in spoken or [] if str(line or "").strip()}
    text = _TEASER_QUOTE.sub(" ", " ".join(str(lead or "").split()))
    for sentence in _SENTENCE_END.split(text):
        if not sentence.strip():
            continue
        if drops_ne(sentence):
            return "hook_dropped_ne"
        if _FIRST_PERSON.search(sentence) and _folded(sentence).strip(" .!?…") not in said:
            return "hook_unsaid_speech_act"
    return None


def hook_problem(text: Any, *, open_fr: Any = None, spoken: Iterable[str] = ()) -> str | None:
    """Why a finished hook cannot be filed, as a code, or ``None`` (#822).

    What stays open (``open_fr``, else the hook's last sentence) is checked where it is
    written (:func:`question_problem`, :func:`open_line`); this checks what comes before it
    (:func:`lead_problem`). A question alone always holds."""

    line = " ".join(str(text or "").split())
    question = " ".join(str(open_fr or "").split())
    if not question or not line.endswith(question):
        question = _SENTENCE_END.split(line)[-1] if line else ""
    return lead_problem(line[: len(line) - len(question)], spoken=spoken)


def held_hook(leads: Iterable[str], open_fr: str, *, spoken: Iterable[str] = ()) -> str:
    """The hook as filed: each lead in front of ``open_fr`` that :func:`lead_problem` lets
    through, in order. A lead that fails goes whole («J'ai rien entendu. Mais quand même…»
    is one voice: no stray «Mais quand même…» is left behind) and is never repaired."""

    kept = [part for part in leads if str(part or "").strip() and lead_problem(part, spoken=spoken) is None]
    return " ".join([*kept, open_fr])


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
    return held_hook((voice[key], lead), open_line(candidate, register=register, variant=variant))


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


def question_problem(
    text: Any, *, known: str, ledger: dict | None = None, asked: Iterable[str] = ()
) -> str | None:
    """Why a written question cannot be tomorrow's line, as a code, or ``None``.

    Compared against what the scene holds, never against what the question means: it is
    one sentence that ends on its question, at most :data:`TOMORROW_WORDS` words, quotes
    nobody, brings in no number or name the scene does not hold, touches something the
    scene holds, does not ask again what the learner has answered, and is not a hook an
    earlier day already left open (``asked``: :func:`hooks_asked`, #850). A failed check
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
    if drops_ne(line):
        return "tomorrow_dropped_ne"
    if scene_ledger.brings_in_new(line, known):
        return "tomorrow_brings_in_new_fact"
    if not _words(line) & _words(known):
        return "tomorrow_off_the_scene"
    if lane_guards.reasked_question(line, ledger):
        return "tomorrow_already_answered"
    if asked_before(line, asked):
        return "tomorrow_asked_before"
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


def _recent_hooks(live: dict, today: str) -> list[dict]:
    """The teaser ledger's rows of the last :data:`TEASER_WINDOW_DAYS` days, oldest first."""

    rows = []
    for row in live.get(TEASERS_KEY) or []:
        days = _days_between(row.get("date"), today) if isinstance(row, dict) else None
        if days is not None and 0 <= days < TEASER_WINDOW_DAYS:
            rows.append(row)
    return rows


def _left_open(row: dict) -> str:
    """What a filed hook left the reader with: its ``open_fr``, else the question its line
    ends on (a plan's or a page's own hook has no ``open_fr``), else nothing."""

    line = " ".join(str(row.get("open_fr") or "").split())
    if line:
        return line
    last = (_SENTENCE_END.split(" ".join(str(row.get("text_fr") or "").split())) or [""])[-1]
    return last if last.endswith("?") else ""


def hooks_asked(live: dict | None, *, date: str | None) -> list[str]:
    """#850: the questions the hooks of the last :data:`TEASER_WINDOW_DAYS` days left open,
    oldest first. A question in this list was printed on Home, Done and the last panel
    already: whether the learner answered it or not, asking it again is the story standing
    still (:func:`asked_before`)."""

    engine = _engine()
    today = engine._date_of(date) or engine._today().isoformat()
    asked: list[str] = []
    for row in _recent_hooks(live or {}, today):
        line = _left_open(row)
        if line and line not in asked:
            asked.append(line)
    return asked


def same_question(left: Any, right: Any) -> bool:
    """#850: whether two hook questions ask the same thing, in whatever words or tense.

    What a question is about is its words of meaning by lemma and stem
    (:func:`learner_facts.content_of`): «Margaux lira-t-elle la lettre avec toi ?» and
    «Margaux va-t-elle lire la lettre ?» are both {margaux, lire, lettre}. The same when one
    is about nothing the other is not (two words of meaning at least, so «Et Lila ?» is not
    every question about Lila); a question that adds a topic («Qui a écrit cette lettre ?»)
    is a new one, and so is one with another number. A question with no word of meaning is
    the same only word for word. A row of the story (a promise, a detail, a season question)
    is told again only under another ``ref``: that is a new row, not this check's."""

    from app.services.learner_facts import content_of, fold, numbers_of

    # «Lila part-elle le 3 ?» and «Lila part-elle le 5 ?» are two questions.
    if numbers_of(left) != numbers_of(right):
        return False
    a, b = content_of(left), content_of(right)
    if not a or not b:
        bare = [fold(text).strip(" ?!.…") for text in (left, right)]
        return bool(bare[0]) and bare[0] == bare[1]
    small, large = sorted((a, b), key=len)
    return small == large or (len(small) >= 2 and small <= large)


def asked_before(question: Any, asked: Iterable[str]) -> str | None:
    """The earlier hook question ``question`` asks again (:func:`same_question`), or None."""

    return next((line for line in asked or [] if same_question(question, line)), None)


# ---------------------------------------------------------------------------
# P8 · one hook, and a hook that moves (real-model check of 17 Nov)
# ---------------------------------------------------------------------------

#: What a learner's line says when it puts a question off: «demain», «pas encore»…
_PUT_OFF = re.compile(
    r"\b(?:demain|plus\s+tard|pas\s+encore|pas\s+maintenant|pas\s+ce\s+soir|je\s+ne\s+sais\s+pas"
    r"|je\s+sais\s+pas|on\s+verra|je\s+(?:vais\s+)?r[ée]fl[ée]chi\w*|attend\w*|la\s+semaine\s+prochaine)\b",
    re.IGNORECASE,
)
#: The day's ending names tomorrow: the sentence that does is the day's step forward.
_TOMORROW = re.compile(r"\bdemain\b", re.IGNORECASE)
_STEP_OPENER = re.compile(r"^(?:et|alors|bon|donc|mais)\s*,?\s+", re.IGNORECASE)


def subject_of(text: Any) -> set[str]:
    """What a hook line is about: its words of meaning as five-letter stems, the question's
    frame left out (``living_story._hook_stems``): «Tu gardes ton vol de mercredi ?» is
    {garde, vol, mercr}."""

    return _engine()._hook_stems({"text_fr": str(text or "")})


def same_subject(left: Any, right: Any) -> bool:
    """P8: whether two hook lines ask the same thing of the same subject. The same question
    in other words (:func:`same_question`), or two words of meaning in common with no new
    number (A1 walk: «Que fais-tu de ton vol de mercredi ?» on day 3, «Tu gardes ton vol de
    mercredi ?» on day 4). A date that moved («le 2 décembre») is a new question."""

    from app.services.learner_facts import numbers_of

    if numbers_of(left) != numbers_of(right):
        return False
    if same_question(left, right):
        return True
    return len(subject_of(left) & subject_of(right)) >= 2


def _put_off(hook_line: str, said: Iterable[str]) -> bool:
    """Whether one of the learner's replies today put ``hook_line`` off in so many words: it
    speaks of what the hook is about and says «demain», «pas encore», «je ne sais pas»…"""

    subject = subject_of(hook_line)
    for line in said or ():
        if _PUT_OFF.search(str(line or "")) and subject & subject_of(line):
            return True
    return False


def hook_again(line: Any, live: dict | None, *, said: Iterable[str] = ()) -> str:
    """P8 (A1 walk, days 2–4: three days ended on the Wednesday flight): whether ``line``
    may be tomorrow's hook after today's page took up the stored one.

    ``"new"``: it asks something else. ``"again"``: the same question, once more, because
    the learner's reply put it off (:func:`_put_off`). ``"refused"``: the same question
    without that, or a second time after it. Taking a hook up moves it: it is settled or
    it changes."""

    stored = (live or {}).get(TEASER_KEY)
    if not isinstance(stored, dict):
        return "new"
    previous = _left_open(stored) or " ".join(str(stored.get("text_fr") or "").split())
    if not previous or not same_subject(line, previous):
        return "new"
    if stored.get("renewed"):
        return "refused"
    return "again" if _put_off(previous, said) else "refused"


#: A clause break inside a sentence: «… l'appartement ; demain, vous pourrez …». Round 4
#: (B1 walk of 19 Nov, day 3): a colon before a space is one too — «Parle à Gus demain :
#: il connaissait une autre facette d'elle, et …» said the learner's plan back in 18
#: words, no clause was found, and the hook fell to tomorrow's beat (Marin's soup) while
#: the last panel promised Gus. Not a clock's colon («19:00»).
_CLAUSE_BREAK = re.compile(r"\s*(?:;|:(?=\s)|\s[—–]\s)\s*")


def _tomorrow_clauses(text: Any) -> list[str]:
    """The sentences and clauses of ``text`` that name tomorrow and can stand alone as the
    day's hook (3 to :data:`TOMORROW_TOLD_WORDS` words, nobody quoted, no dropped «ne»),
    last first, as they would be printed («Et demain, vous parlerez à Gus.» → «Demain, vous
    parlerez à Gus.»)."""

    found: list[str] = []
    line = " ".join(str(text or "").split())
    for sentence in reversed(_SENTENCE_END.split(line)):
        if _TEASER_QUOTE.search(sentence):
            continue
        parts = [sentence] if _word_count(sentence) <= TOMORROW_TOLD_WORDS else _CLAUSE_BREAK.split(sentence)
        for part in parts:
            if not _TOMORROW.search(part) or drops_ne(part):
                continue
            step = _STEP_OPENER.sub("", part.strip()).strip()
            step = step[:1].upper() + step[1:]
            if step and step[-1] not in ".!?…":
                step += "."
            if 3 <= _word_count(step) <= TOMORROW_TOLD_WORDS:
                found.append(step)
    return found


def ending_step(ending_fr: Any) -> str | None:
    """P8 (B1 walk, day 4): the sentence (or clause) of the day's ending that says what
    happens tomorrow («Et demain, vous parlerez à Gus de la clé.»), as it can stand alone
    as the day's hook, or None. The end card prints the ending; this is the promise in it."""

    found = _tomorrow_clauses(ending_fr)
    return found[0] if found else None


def learner_plan_line(said: Iterable[str]) -> str | None:
    """The learner's own last sentence that names tomorrow («Demain, je veux parler à Gus
    de la clé.»), verbatim, or None. P8 (fourth commit): tomorrow's brief opens on it."""

    plans = [
        sentence
        for line in said or ()
        for sentence in _SENTENCE_END.split(" ".join(str(line or "").split()))
        if _TOMORROW.search(sentence)
    ]
    return plans[-1].strip() if plans else None


def plan_step(said: Iterable[str], told: Iterable[str]) -> str | None:
    """P8 (third commit): the learner's own plan for tomorrow, as the scene said it back.

    The learner's last line that names tomorrow («Demain, je veux parler à Gus de la clé.»),
    matched to a sentence of ``told`` (the ending, then the character's replies, newest
    first) that names tomorrow and shares a word of meaning with it («… demain, vous
    pourrez parler de la clé avec Gus.»). The learner's words are never turned into a hook
    themselves: the hook is said to the learner, so it is the character's sentence."""

    plan = learner_plan_line(said)
    if not plan:
        return None
    subject = subject_of(plan)
    for text in told or ():
        for step in _tomorrow_clauses(text):
            if subject & subject_of(step):
                return step
    return None


def answered_in_scene(question: Any, asked: Iterable[str]) -> bool:
    """P8 (A1 walk, day 4: «Qu'est-ce qui te ferait rester à Paris ?» filed as the hook
    right after the learner answered «Qu'est-ce qui te ferait rester ?»): whether
    ``question`` asks again a question the learner has already answered in this scene
    (``asked``: the opening question and every reply but the last). The same question
    (:func:`same_question`), or one about everything an answered one was about."""

    line = " ".join(str(question or "").split())
    if not line:
        return False
    wanted = subject_of(line)
    for text in asked or ():
        for sentence in _SENTENCE_END.split(" ".join(str(text or "").split())):
            if not sentence.endswith("?"):
                continue
            about = subject_of(sentence)
            if same_question(line, sentence) or (about and about <= wanted):
                return True
    return False


def ending_hook(
    ending_fr: Any,
    live: dict | None,
    *,
    character_id: str | None,
    date: str | None,
    name: str | None = None,
    said: Iterable[str] = (),
    replies: Iterable[str] = (),
) -> dict | None:
    """P8: the day's step forward as its ONE hook, or None: first the learner's own plan
    for tomorrow as the ending or a reply said it back (:func:`plan_step`), else the
    ending's own sentence about tomorrow (:func:`ending_step`). The end card shows the
    ending, and Home, the push and tomorrow's page then read the same promise — not a
    loose end drawn at random beside it (B1 walk, day 4: the ending promised Gus and the
    key, Home said «L'avenir du Mistral…», and day 5 followed Home)."""

    steps = (("plan", plan_step(said, [ending_fr, *reversed(list(replies or ()))])), ("scene", ending_step(ending_fr)))
    for source, step in steps:
        if not step:
            continue
        again = hook_again(step, live, said=said)
        if again == "refused":
            continue
        engine = _engine()
        today = engine._date_of(date) or engine._today().isoformat()
        return {
            "text_fr": step,
            "open_fr": step,
            "character_id": character_id,
            **({"character_name": name} if name else {}),
            "date": today,
            "ref": f"ending:{today}",
            "kind": "promise",
            # P8 (fourth commit): the learner's own plan, or the ending's own step.
            "source": source,
            **({"renewed": 1} if again == "again" else {}),
        }
    return None


#: P8 (third commit): the one line every surface prints is at most this long.
HOOK_LINE_WORDS = TOMORROW_TOLD_WORDS
_A_SUIVRE_TAIL = re.compile(r"\s*À suivre\s*(?:…|\.\.\.)?\s*$", re.IGNORECASE)


def hook_line(teaser: dict | None) -> str:
    """P8 (third commit): the ONE line of a hook, as the end card, Home, «Done» and the push
    all print it. What it leaves open (``open_fr``) when it names it, else its line; never
    the «À suivre…» label (each surface prints its own). A line longer than
    :data:`HOOK_LINE_WORDS` keeps its first whole sentences that fit (at least one), here,
    once, so no surface can shorten it differently (walk of 17 Nov: the end card had two
    sentences, Home and «Done» one; the end card had «Au fait…», Home did not)."""

    row = teaser or {}
    line = " ".join(str(row.get("open_fr") or row.get("text_fr") or "").split())
    line = _A_SUIVRE_TAIL.sub("", line).strip()
    if _word_count(line) <= HOOK_LINE_WORDS:
        return line
    sentences = _SENTENCE_END.split(line)
    kept = sentences[0]
    for sentence in sentences[1:]:
        if _word_count(f"{kept} {sentence}") > HOOK_LINE_WORDS:
            break
        kept = f"{kept} {sentence}"
    return kept


#: P8 (fourth commit): where a filed hook came from, stored with it and logged with the
#: next page's ``hook_observation``, so a walk can count which sources get taken up.
#: ``plan``: the learner's own «demain …» said back; ``beat``: composed from tomorrow's
#: planned beat; ``contract``: the day contract's authored hook; ``tentpole``: an
#: authored tentpole's own line; ``pick``: the learner's «Demain» pick; ``scene``: what
#: today's scene left (its ending's step, the writer's question, a promise or a plant);
#: ``generic``: one of the season's long questions.
HOOK_SOURCES = ("plan", "beat", "contract", "tentpole", "pick", "scene", "generic")


def hook_source(teaser: dict | None) -> str:
    """The source of a hook row (:data:`HOOK_SOURCES`); a row that does not say is read
    from its ``ref`` and ``kind`` (rows filed before the fourth commit)."""

    row = teaser or {}
    if row.get("source") in HOOK_SOURCES:
        return str(row["source"])
    ref = str(row.get("ref") or "")
    for prefix, source in (("contract:", "contract"), ("season:", "tentpole"), ("tomorrow:", "pick"), ("beat:", "beat")):
        if ref.startswith(prefix):
            return source
    return "generic" if row.get("kind") == "thread" else "scene"


def one_hook(teaser: dict | None) -> dict | None:
    """The hook as it is filed: ``text_fr`` and ``open_fr`` are both :func:`hook_line`, so
    every reader of the stored row prints the same words; ``source`` says where it came
    from (:func:`hook_source`)."""

    if not teaser:
        return teaser
    line = hook_line(teaser)
    sourced = {**teaser, "source": hook_source(teaser)}
    return {**sourced, "text_fr": line, "open_fr": line} if line else sourced


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
    (:func:`question_problem`), or the scene's own (:func:`question_left_open`). It leads,
    unless an earlier hook asked it (:func:`asked_before`, #850). Otherwise this prefers a
    row the addressed character witnessed, then any open row, in a seeded order; skips any
    row or wording already used as a teaser in the last ``TEASER_WINDOW_DAYS`` days; and
    validates the composed line against the row it names
    before it is kept. ``said`` and ``clean`` are this scene's replies, and those that
    needed no correction: a hook quotes only the second, whatever row wrote it.
    """

    engine = _engine()
    today = engine._date_of(date) or engine._today().isoformat()
    recent = _recent_hooks(live, today)
    used_refs = {str(row.get("ref")) for row in recent}
    last_kind = str((recent[-1] if recent else {}).get("kind") or "")
    used_texts = {str(row.get("text_fr")) for row in recent}
    # #850: what earlier hooks asked, compared by what it asks, not by its words: the
    # walk's «Margaux lira-t-elle la lettre avec toi ?» came back as «Margaux va-t-elle
    # lire la lettre ?», a new string, for a third day.
    asked = hooks_asked(live, date=today)
    # P8: a hook today's page took up is settled or changed, not asked again (unless the
    # learner put it off, and then once).
    again = hook_again(question, live, said=said) if question else "refused"
    if question and not asked_before(question, asked) and again != "refused":
        voice = TEASER_VOICES.get(str(character_id or ""), DEFAULT_TEASER_VOICE)["tu" if register == "tu" else "vous"]
        return {
            "text_fr": held_hook((voice,), question),
            "open_fr": question,
            "character_id": character_id,
            **({"character_name": name} if name else {}),
            "date": today,
            "ref": f"scene:{today}",
            "kind": "question",
            **({"renewed": 1} if again == "again" else {}),
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
        # P8: an open row that is today's hook again is no step forward either.
        if hook_again(opened, live, said=said) == "refused":
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
            {
                **{key: teaser.get(key) for key in ("ref", "kind", "text_fr", "open_fr", "date", "character_id", "source")},
                **({"renewed": teaser["renewed"]} if teaser.get("renewed") else {}),
            }
        )
    return rows[-TEASER_LEDGER_LIMIT:]


# ---------------------------------------------------------------------------
# P8 (fifth commit): a hook composed from tomorrow's beat is a line the learner can read
# ---------------------------------------------------------------------------

#: The second real-model walk of 17 Nov filed a beat's bare title as the hook: «Le
#: billet» (two words), «Romy enquête» (a name the learner had not met), «La même
#: chose ?» (a question with no referent). A hook from a beat is now a whole line, built
#: from the beat's premise: who, and what is about to happen (its title).
BEAT_HOOK_MIN_WORDS = 4
_DE_ARTICLE = (
    (re.compile(r"^le\s+", re.IGNORECASE), "du "),
    (re.compile(r"^les\s+", re.IGNORECASE), "des "),
    (re.compile(r"^la\s+", re.IGNORECASE), "de la "),
    (re.compile(r"^l['’]\s*", re.IGNORECASE), "de l'"),
    (re.compile(r"^(une?)\s+", re.IGNORECASE), r"d'\1 "),
)


def _with_de(title: str) -> str:
    """«Le billet» → «du billet», «La soupe de Marin» → «de la soupe de Marin»."""

    lowered = title[:1].lower() + title[1:]
    for pattern, replacement in _DE_ARTICLE:
        if pattern.match(lowered):
            return pattern.sub(replacement, lowered, count=1)
    return f"de {lowered}"


def readable_hook(line: Any) -> bool:
    """A hook the learner can read on its own: at least four words, not a bare question
    that only makes sense inside its scene («La même chose ?»)."""

    text = " ".join(str(line or "").split())
    if _word_count(text) < BEAT_HOOK_MIN_WORDS:
        return False
    return not (text.endswith("?") and _word_count(text) <= BEAT_HOOK_MIN_WORDS)


def compose_beat_hook(
    title_fr: Any,
    *,
    who_fr: str = "",
    who_native: dict[str, str] | None = None,
    subject_rest: str = "",
    pronoun: str = "",
) -> dict | None:
    """``{text_fr, text_native?}`` for tomorrow's beat, or None when no readable line can
    be built. Deterministic, no model call.

    - the title is somebody doing something («Romy enquête»): ``subject_rest`` is what
      follows the name, and ``who_fr`` says who (a description when the learner has not
      met them: «Demain, une journaliste québécoise est là et elle enquête.»). No native line: the verb
      is the season's French and has no translation in its data.
    - the title is a question («La même chose ?»): «Demain, Margaux te demande : « La même
      chose ? »», natively «Morgen fragt dich Margaux: „La même chose ?“» (the quoted line
      is fiction and stays French).
    - the title names a thing («Le billet»): «Demain, Lila te parle du billet.» («Morgen
      spricht Lila mit dir über „Le billet“.»); when the person is in the title already,
      «Demain, Marin est là : la soupe de Marin.»
    """

    title = " ".join(str(title_fr or "").split()).strip()
    who = " ".join(str(who_fr or "").split())
    native = {lang: " ".join(str(text or "").split()) for lang, text in (who_native or {}).items() if text}
    if not title or not who:
        return None
    text_native: dict[str, str] = {}
    if subject_rest:
        text = f"Demain, {who} est là et {pronoun or 'on'} {subject_rest.strip().rstrip('.')}."
    elif title.endswith("?"):
        text = f"Demain, {who} te demande : « {title} »"
        text_native = {
            lang: template.format(who=native[lang], title=title)
            for lang, template in (("de", "Morgen fragt dich {who}: „{title}“"), ("en", "Tomorrow {who} asks you: “{title}”"))
            if lang in native
        }
    else:
        bare = title.rstrip(" .")
        if _folded(who) and _folded(who) in _folded(bare):
            text = f"Demain, {who} est là : {bare[:1].lower()}{bare[1:]}."
            templates = (("de", "Morgen ist {who} da: „{title}“."), ("en", "Tomorrow {who} is there: “{title}”."))
        else:
            text = f"Demain, {who} te parle {_with_de(bare)}."
            templates = (
                ("de", "Morgen spricht {who} mit dir über „{title}“."),
                ("en", "Tomorrow {who} talks to you about “{title}”."),
            )
        text_native = {lang: template.format(who=native[lang], title=bare) for lang, template in templates if lang in native}
    if not readable_hook(text):
        return None
    return {"text_fr": text, **({"text_native": text_native} if text_native else {})}
