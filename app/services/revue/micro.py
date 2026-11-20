"""«Le micro»: the interview desk (WP-119 «les rubriques», owner 2026-11-21).

The learner, Romy's trainee, interviews a regular who was there (the comptoir's topic guest,
``comptoir.comptoir_guests``: «who was there», in character per the world bible) and fills
the holes in Romy's notes from what the witness says (the loop is ``micro_loop.py``; the
dealer is ``assignments.py``). This module writes what every learner shares:
:class:`~app.services.revue.dossier.MicroDesk`, one JSON call per story (:func:`write_micro`,
through ``rubriques.ask_desk``: one retry, then refused), and the deterministic matcher
(:func:`match`) that tells which stored fact a learner's question asks for.

- Five or six ``facts``, each grounded in ONE claim (``claim_id``), with the question word
  that unlocks it (qui / quoi / où / quand / combien / pourquoi / comment), the claim's words
  a question about it uses (``keywords``, each in the claim), Romy's note («Combien ? ___»),
  an A1 question tile (correct by construction: it is a question, it carries no vocative and
  the matcher sends it to its own fact and to no other), an A2 opening, the witness's answer at
  A1 (≤ 14 words), A2 (≤ 22) and B1 (≤ 32), fr + en + de, and the value that fills the hole
  (in the claim and in the answer at every band).
- A witness never states anything the claims lack: an answer carries no number and no name
  its own claim does not carry (the comptoir's checks for the rest: no relative date, no id,
  no app word, nothing about a private life).
- ``shrug``: the witness's line for a question the story cannot answer, at each band: no
  number, no name.
- A story the comptoir would not argue about gets none (``fit: "skip"``, and a row whose takes
  were skipped is never asked, ``rubriques.ensure_desk``).
"""

from __future__ import annotations

import re
from typing import Any

from app.services.revue import comptoir, rubriques
from app.services.revue.comptoir import _Checker, address_problem, ci, contains, numbers, word_count
from app.services.revue.dossier import (
    MICRO_ASKS,
    BandTexts,
    ComptoirPhrase,
    ComptoirText,
    EditorialDossier,
    MicroDesk,
    MicroFact,
)
from app.services.revue.fil import new_names
from app.services.revue.intox import grounded

MICRO_PROMPT_VERSION = "micro-desk-v1"

ANSWER_MAX_WORDS: dict[str, int] = {"a1": 14, "a2": 22, "b1": 32}
TILE_MAX_WORDS = 10
FRAME_MAX_WORDS = 5
HOLE_MAX_WORDS = 6
VALUE_MAX_WORDS = 8
PHRASE_MAX_WORDS = 10
FACTS_MIN, FACTS_MAX = 5, 6


def _t(fr: str, en: str, de: str) -> ComptoirText:
    return ComptoirText(fr=fr, en=en, de=de)


AUTHORED_PHRASE = ComptoirPhrase(
    a1=_t("Quand… ? · Combien… ?", "When…? · How many…?", "Wann…? · Wie viele…?"),
    a2=_t("Pourquoi est-ce que… ?", "Why…?", "Warum…?"),
    b1=_t("Est-ce que vous pourriez me dire… ?", "Could you tell me…?", "Könnten Sie mir sagen, …?"),
    b2=_t("J'aimerais savoir pourquoi…", "I'd like to know why…", "Ich würde gern wissen, warum …"),
)

# ---------------------------------------------------------------------------
# The matcher: which stored fact a question asks for (deterministic)
# ---------------------------------------------------------------------------

#: Words that only make a question a question (never content).
_QUESTION_TOKENS = frozenset("""
    qui que quoi quand combien pourquoi comment quel quelle quels quelles est-ce est ce c'est qu'est-ce
    vous tu pouvez peux pourriez dire savoir sais
""".split())
_PRONOUNS = frozenset("je tu il elle on nous vous ils elles".split())
_WORD = re.compile(r"[0-9]+(?:[.,][0-9]+)?|[^\W\d_]+(?:['’-][^\W\d_]+)*")


def _fold(text: str | None) -> str:
    return ci(text).replace("’", "'")


def stem(word: str) -> str:
    """Lemma-light: case and accents folded, an elided article dropped, a final -s / -x
    dropped, the first five letters («musiciens» → «music», «gratuite» → «gratu»)."""

    folded = _fold(word)
    folded = re.sub(r"^(?:l|d|qu|j|n|s|c|m|t)'", "", folded)
    if folded[:1].isdigit():
        return folded.replace(",", ".")
    if len(folded) > 4 and folded[-1] in "sx":
        folded = folded[:-1]
    return folded[:5]


def content_stems(text: str | None) -> set[str]:
    """The content words of ``text``, lemma-light: numbers, and words of four letters or more
    that are not grammar or question words."""

    from app.services.revue.fil import _STOP  # noqa: PLC0415 - the wire desk's stop list

    out: set[str] = set()
    for token in _WORD.findall(text or ""):
        folded = _fold(token)
        bare = re.sub(r"^(?:l|d|qu|j|n|s|c|m|t)'", "", folded)
        if bare[:1].isdigit():
            out.add(stem(bare))
            continue
        if len(bare) < 4 or bare in _STOP or bare in _QUESTION_TOKENS or folded in _QUESTION_TOKENS:
            continue
        out.add(stem(bare))
    return out


def question_word(text: str | None) -> str | None:
    """The question word of ``text`` as a fact's ``ask`` («où» → ``ou``), ``quel`` for
    «quel / quelle…» (it may ask for anything but a reason or a manner), else ``None``."""

    raw = str(text or "").lower().replace("’", "'")
    tokens = re.findall(r"[a-zà-ÿœ']+", raw)
    for index, token in enumerate(tokens):
        if token in {"où", "d'où"}:
            return "ou"
        folded = _fold(token)
        if folded.startswith("qu'est") or (folded.startswith("qu'") and index == 0):
            return "quoi"
        if folded in {"combien", "pourquoi", "comment", "quand", "quoi"}:
            return folded
        if folded in {"quel", "quelle", "quels", "quelles"}:
            return "quel"
        if folded == "qui" and (index <= 1 or re.search(r"\bqui\s*\?\s*$", raw)):
            return "qui"
        if folded == "que" and index == 0:
            return "quoi"
    return None


def is_question(text: str | None) -> bool:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return bool(value) and (value.endswith("?") or question_word(value) is not None
                            or _fold(value).startswith("est-ce que") or _fold(value).startswith("est-ce qu'"))


def _asks(qword: str | None, ask: str) -> bool:
    if qword == "quel":
        return ask not in {"pourquoi", "comment"}
    return qword == ask


def match(text: str, facts: list[MicroFact], *, chosen: list[int] | None = None,
          generic: set[str] | None = None) -> dict[str, Any]:
    """Which of ``facts`` ``text`` asks for: ``{"kind": "match", "index"}``, ``{"kind":
    "none"}`` (the shrug) or ``{"kind": "ambiguous", "candidates"}`` (two or more fit equally;
    only then may a model pick among them). ``qword`` is the question word found.

    A fact is hit by the content words its ``keywords`` share with the question (five
    letters, lemma-light), or, when its question word is the question's, by four («se
    plaignent» / «plaintes»). Without a hit, the question word alone picks the facts it asks
    for, and only when the question says nothing beyond the story's own name (``generic``:
    the title's words), so «Combien de musiciens ?» is not «Combien ça coûte ?». ``chosen``
    (the learner's three holes) breaks a tie before anything else does."""

    qword = question_word(text)
    words = content_stems(text)
    weak = {w[:4] for w in words}
    hits: list[int] = []
    for fact in facts:
        own = content_stems(" ".join(fact.keywords))
        strong = len(words & own)
        loose = len(weak & {w[:4] for w in own}) if qword and _asks(qword, fact.ask) else 0
        hits.append(strong or loose)
    with_hits = [i for i, n in enumerate(hits) if n > 0]
    if with_hits:
        asked = [i for i in with_hits if qword and _asks(qword, facts[i].ask)]
        pool = asked or with_hits
        best = max(hits[i] for i in pool)
        candidates = [i for i in pool if hits[i] == best]
    elif qword and qword != "quel" and words <= (generic or set()):
        candidates = [i for i, fact in enumerate(facts) if fact.ask == qword]
    else:
        candidates = []
    if len(candidates) > 1 and chosen:
        mine = [i for i in candidates if i in chosen]
        candidates = mine or candidates
    if not candidates:
        return {"kind": "none", "qword": qword}
    if len(candidates) == 1:
        return {"kind": "match", "index": candidates[0], "qword": qword}
    return {"kind": "ambiguous", "candidates": candidates, "qword": qword}


def generic_words(dossier: EditorialDossier) -> set[str]:
    """The story's own name, which every question may carry («la fête», «le bac»)."""

    return content_stems(dossier.title_fr)


def formation_slips(text: str, fact: MicroFact | None, qword: str | None) -> list[str]:
    """What a question gets wrong in its form, collected for «Relis tes questions» and never
    shown during the interview: ``inversion`` (a question word first, then a subject pronoun,
    without «est-ce que» or an inversion: «Pourquoi elle est gratuite ?»), ``question_word``
    (it asks «quand» for a «combien» hole). When in doubt, nothing."""

    slips: list[str] = []
    tokens = re.findall(r"[a-zà-ÿœ'-]+", str(text or "").lower().replace("’", "'"))
    folded = " ".join(_fold(t) for t in tokens)
    if (len(tokens) >= 3 and qword not in {None, "qui", "quel"} and _fold(tokens[0]).strip("'") in
            {"combien", "pourquoi", "comment", "quand", "ou", "où"} and "est-ce" not in folded
            and tokens[1] in _PRONOUNS and "-" not in tokens[2]):
        slips.append("inversion")
    if fact is not None and qword not in {None, "quel"} and qword != fact.ask:
        slips.append("question_word")
    return slips


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

MICRO_SPEC = """{"fit": "interview" | "skip",
 "witness": str,
 "facts": [{"claim_id": str, "ask": "qui" | "quoi" | "ou" | "quand" | "combien" | "pourquoi" | "comment",
   "keywords": [str], "hole": T, "tile": T, "frame": T, "answer": {"a1": T, "a2": T, "b1": T}, "value_fr": str}, ×5 or 6],
 "shrug": {"a1": T, "a2": T, "b1": T},
 "phrase": {"a1": T, "a2": T, "b1": T, "b2": T}}
where T = {"fr": str, "en": str, "de": str} (en and de translate the French faithfully, every time)"""

MICRO_RULES = """RULES
- fit: "skip" when the story is a death, a war, a crime with victims, an election or a party's politics, or
  anything where playing an interview would be cruel; also when the claims hold fewer than five things to ask.
  Otherwise "interview".
- witness: copy INPUT.witness.id. The learner interviews this regular, who was there; every answer is in their
  voice (INPUT.witness.sheet), friendly, never rude, and never about anyone's private life.
- facts: five or six things the witness can tell, each from ONE claim (claim_id), each with the question word that
  asks for it (ask; "ou" is «où»). No two facts with the same claim AND the same ask.
  - keywords: two to five words a question about this fact would use (a noun, a verb, a number), copied from the
    claim, or from your hole or tile («coûte» for «gratuite»); at least one from the claim; never the words every
    fact shares (the story's name).
  - hole: Romy's note for it, 6 words at most, a question word and what it asks («Combien d'élèves ?», «Pourquoi
    gratuit ?»).
  - tile: the beginner's whole question for it, 10 words at most, with «est-ce que» or an inversion, ending with
    « ?», using the ask word and at least one keyword; never a name in the vocative, never «tu» or «vous» with an
    adjective.
  - frame: the A2 opening the learner completes, 5 words at most, starting with the question word («Combien de»,
    «Pourquoi est-ce que»).
  - answer: what the witness says when asked: a1 14 words at most, a2 22, b1 32; it states the fact, in
    character, and NOTHING its claim does not say: no number, name, place or date the claim lacks.
  - value_fr: the words that fill the hole, copied exactly from the claim AND said in the answer at every band
    (8 words at most: «le 21 juin 1982», «gratuite», «8 %»).
- shrug: what the witness says to a question the story cannot answer («Ça, je ne sais pas. L'article ne le dit pas.»),
  per band, no number, no name.
- phrase: how to ask, per band (a1 «Quand… ? · Combien… ?», a2 «Pourquoi est-ce que… ?», b1 «Est-ce que vous
  pourriez me dire… ?», b2 «J'aimerais savoir pourquoi…»).
- Facts: only what the claims say. Numbers in digits, copied exactly from the claims. Never a relative date
  (demain, hier, aujourd'hui, ce soir, cette semaine) nor a weekday the claims do not name. Never about the app:
  never «dossier», «session», «application». Our French only: never copy the outlet's sentences.
- French typography: a space before ? ! : ;
EXAMPLE (story: the covered market Beauvau closes for works; claims c1 «Le 3 mars, la mairie du 12e
arrondissement annonce des travaux au marché Beauvau.», c2 «Le 10 mars, les commerçants quittent le marché couvert
et s'installent sur la place d'Aligre.», c3 «Après le départ des commerçants, les ouvriers changent le toit du
marché.», c4 «Une fois les travaux finis, le marché Beauvau rouvre le 14 novembre.»; witness Margaux):
{"fit": "interview", "witness": "margaux_barman",
 "facts": [
  {"claim_id": "c2", "ask": "ou", "keywords": ["commerçants", "installent", "place"],
   "hole": {"fr": "Où vont les commerçants ?", "en": "Where do the traders go?", "de": "Wohin gehen die Händler?"},
   "tile": {"fr": "Où est-ce que les commerçants s'installent ?", "en": "Where do the traders set up?", "de": "Wo lassen sich die Händler nieder?"},
   "frame": {"fr": "Où est-ce que", "en": "Where", "de": "Wo"},
   "answer": {"a1": {"fr": "Ils vont sur la place d'Aligre, juste à côté.", "en": "They go to the Place d'Aligre, right next door.", "de": "Sie gehen auf die Place d'Aligre, gleich nebenan."},
     "a2": {"fr": "Les commerçants quittent le marché couvert et s'installent sur la place d'Aligre.", "en": "The traders leave the covered market and set up on the Place d'Aligre.", "de": "Die Händler verlassen die Markthalle und ziehen auf die Place d'Aligre."},
     "b1": {"fr": "Le 10 mars, tout le monde déménage : les commerçants quittent le marché couvert et s'installent sur la place d'Aligre.", "en": "On 10 March everyone moves: the traders leave the covered market and set up on the Place d'Aligre.", "de": "Am 10. März ziehen alle um: Die Händler verlassen die Markthalle und ziehen auf die Place d'Aligre."}},
   "value_fr": "la place d'Aligre"}, …],
 "shrug": {"a1": {"fr": "Ça, je ne sais pas, mon chou.", "en": "That, I don't know, sweetie.", "de": "Das weiß ich nicht, Schätzchen."}, …},
 "phrase": {…}}
Do not reuse the example's lines: write for THIS story."""

MICRO_DESK_INSTRUCTIONS = (
    """You write «Le micro» for «Le Papier de Romy», a French-learning app. The learner is the trainee of Romy, a
Québécoise journalist; after reading a news story they interview a regular of the café who was there, asking one
question at a time, and fill the holes in Romy's notes from the answers. From INPUT (the story's French facts, the
claims' quotes and the witness) answer with ONE JSON object:
"""
    + MICRO_SPEC
    + "\n"
    + MICRO_RULES
)

# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def witness_of(dossier: EditorialDossier) -> str:
    """Who was there: the comptoir's topic guest (``policy.GUEST_AFFINITY``, Margaux else)."""

    return comptoir.comptoir_guests(dossier)[1]


def answer_problem(fr: str, claim_fr: str) -> str | None:
    """Why an answer line states something its claim lacks: a number, a name."""

    if numbers(fr) - numbers(claim_fr):
        return "number_not_in_claim"
    if new_names(fr, claim_fr):
        return "name_not_in_claim"
    return None


def _band_texts(check: _Checker, row: Any, limits: dict[str, int], tag: str) -> tuple[dict[str, ComptoirText], list[str]]:
    texts: dict[str, ComptoirText] = {}
    refusals: list[str] = []
    if not isinstance(row, dict):
        return texts, [f"{tag}:missing"]
    for band, limit in limits.items():
        line, why = rubriques.text(check, row.get(band), limit)
        if line is None:
            refusals.append(f"{tag}:{band}:{why}")
        else:
            texts[band] = line
    return texts, refusals


def _fact(index: int, row: Any, dossier: EditorialDossier, check: _Checker, witness: str) -> tuple[MicroFact | None, list[str]]:
    tag = f"micro:{index}"
    if not isinstance(row, dict):
        return None, [f"{tag}:missing"]
    claim = dossier.claims_by_id().get(str(row.get("claim_id") or "").strip())
    if claim is None:
        return None, [f"{tag}:claim_unknown"]
    ask = str(row.get("ask") or "").strip().lower().replace("où", "ou")
    if ask not in MICRO_ASKS:
        return None, [f"{tag}:ask_unknown"]
    refusals: list[str] = []
    keywords = [re.sub(r"\s+", " ", str(k or "")).strip() for k in list(row.get("keywords") or [])[:6]]
    keywords = [k for k in keywords if k]
    asked_fr = " ".join(str((row.get(f) or {}).get("fr") or "") if isinstance(row.get(f), dict) else str(row.get(f) or "")
                        for f in ("hole", "tile"))
    if (not keywords or not any(contains(claim.fr, k) for k in keywords)
            or any(not (contains(claim.fr, k) or contains(asked_fr, k)) for k in keywords)
            or not content_stems(" ".join(keywords))):
        refusals.append(f"{tag}:keywords_not_in_claim")
    value = re.sub(r"\s+", " ", str(row.get("value_fr") or "")).strip().strip(" .,«»")
    if not value or word_count(value) > VALUE_MAX_WORDS or not contains(claim.fr, value):
        refusals.append(f"{tag}:value_not_in_claim")
    answers, why = _band_texts(check, row.get("answer"), ANSWER_MAX_WORDS, f"{tag}:answer")
    refusals += why
    for band, line in answers.items():
        problem = answer_problem(line.fr, claim.fr)
        if problem:
            refusals.append(f"{tag}:answer:{band}:{problem}")
        elif value and not contains(line.fr, value):
            refusals.append(f"{tag}:answer:{band}:value_not_said")
        elif not grounded(line.fr, claim.fr):
            refusals.append(f"{tag}:answer:{band}:ungrounded")
    hole, why_hole = rubriques.text(check, row.get("hole"), HOLE_MAX_WORDS)
    if hole is None:
        refusals.append(f"{tag}:hole:{why_hole}")
    tile, why_tile = rubriques.text(check, row.get("tile"), TILE_MAX_WORDS)
    if tile is None:
        refusals.append(f"{tag}:tile:{why_tile}")
    elif address_problem(tile.fr, witness) or "!" in tile.fr or not tile.fr.rstrip().endswith("?"):
        refusals.append(f"{tag}:tile:not_a_plain_question")
    elif not (question_word(tile.fr) and (question_word(tile.fr) == ask or question_word(tile.fr) == "quel")):
        refusals.append(f"{tag}:tile:question_word")
    elif numbers(tile.fr) - numbers(claim.fr):
        refusals.append(f"{tag}:tile:number_not_in_claim")
    frame, why_frame = rubriques.text(check, row.get("frame"), FRAME_MAX_WORDS)
    if frame is None:
        refusals.append(f"{tag}:frame:{why_frame}")
    elif question_word(frame.fr) is None:
        refusals.append(f"{tag}:frame:no_question_word")
    if refusals or len(answers) < 3:
        return None, refusals or [f"{tag}:incomplete"]
    return MicroFact(claim_id=claim.id, ask=ask, keywords=keywords, hole=hole, tile=tile, frame=frame,  # type: ignore[arg-type]
                     answer=BandTexts(**answers), value_fr=value), []


def repair_micro(raw: Any, dossier: EditorialDossier) -> tuple[MicroDesk | None, list[str]]:
    """What the interview desk wrote, checked against ``dossier``. ``(None, ["skip"])`` for
    an unfit story; ``(None, problems)`` when it is refused (one fact fails, the witness is not
    who was there, a tile the matcher would not send to its own fact); else the desk's work
    and what fell back to authored lines."""

    if not isinstance(raw, dict):
        return None, ["micro:missing"]
    if str(raw.get("fit") or "").strip().lower() == "skip":
        return None, ["skip"]
    witness = witness_of(dossier)
    if str(raw.get("witness") or "").strip() != witness:
        return None, ["micro:witness"]
    rows = raw.get("facts")
    if not isinstance(rows, list) or not FACTS_MIN <= len(rows) <= FACTS_MAX:
        return None, ["micro:facts:count"]
    check = _Checker(dossier)
    facts: list[MicroFact] = []
    refusals: list[str] = []
    for index, row in enumerate(rows, start=1):
        fact, refused = _fact(index, row, dossier, check, witness)
        refusals += refused
        if fact is not None:
            facts.append(fact)
    if refusals:
        return None, refusals
    if len({(f.claim_id, f.ask) for f in facts}) < len(facts):
        return None, ["micro:facts:duplicate"]
    for index, fact in enumerate(facts):
        found = match(fact.tile.fr, facts, generic=generic_words(dossier))
        if found.get("kind") != "match" or found.get("index") != index:
            refusals.append(f"micro:{index + 1}:tile:not_its_fact")
    if refusals:
        return None, refusals
    shrug, why = _band_texts(check, raw.get("shrug"), ANSWER_MAX_WORDS, "micro:shrug")
    if why or len(shrug) < 3:
        return None, why or ["micro:shrug:incomplete"]
    for band, line in shrug.items():
        if numbers(line.fr) or new_names(line.fr, ""):
            return None, [f"micro:shrug:{band}:states_something"]
    problems: list[str] = []
    phrase: dict[str, ComptoirText] = {}
    raw_phrase = raw.get("phrase") if isinstance(raw.get("phrase"), dict) else {}
    for band in ("a1", "a2", "b1", "b2"):
        line, why_phrase = check.text(raw_phrase.get(band), PHRASE_MAX_WORDS)
        if line is None:
            problems.append(f"micro:phrase:{band}:{why_phrase}")
        phrase[band] = line or getattr(AUTHORED_PHRASE, band)
    return MicroDesk(witness=witness, facts=facts, shrug=BandTexts(**shrug), phrase=ComptoirPhrase(**phrase)), problems


def as_desk_answer(desk: MicroDesk) -> dict[str, Any]:
    """``desk`` in the desk's answer shape, so :func:`audit` runs the same checks."""

    data = desk.model_dump(mode="json")
    return {"fit": "interview", "witness": data["witness"], "facts": data["facts"], "shrug": data["shrug"],
            "phrase": data["phrase"]}


def audit(desk: MicroDesk, dossier: EditorialDossier) -> list[str]:
    """Every check :func:`repair_micro` would make on ``desk``: ``[]`` when nothing would change."""

    repaired, problems = repair_micro(as_desk_answer(desk), dossier)
    return problems if repaired is not None else problems or ["micro:refused"]


# ---------------------------------------------------------------------------
# The desk
# ---------------------------------------------------------------------------


def desk_payload(dossier: EditorialDossier) -> dict[str, Any]:
    witness = witness_of(dossier)
    return {**rubriques.desk_payload(dossier),
            "witness": {"id": witness, "name": comptoir.name_fr(witness),
                        "sheet": comptoir.character_sheets().get(witness, {})}}


class _WithWitness:
    """The provider, asked with the witness in its INPUT (``rubriques.ask_desk`` sends the
    story's own payload)."""

    def __init__(self, provider: Any, dossier: EditorialDossier) -> None:
        self.provider = provider
        self.dossier = dossier
        self.model = getattr(provider, "model", "")

    def ask_json(self, instructions: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        return self.provider.ask_json(instructions, {**payload, **{"witness": desk_payload(self.dossier)["witness"]}},
                                      **kwargs)


def write_micro(dossier: EditorialDossier, provider: Any = None) -> tuple[MicroDesk | None, list[str]]:
    """The interview desk: one JSON call (a second with the problems), checked by :func:`repair_micro`."""

    provider = provider if provider is not None else rubriques.desk_provider("openai-revue-micro-desk")
    return rubriques.ask_desk(dossier, _WithWitness(provider, dossier), key="micro",
                              instructions=MICRO_DESK_INSTRUCTIONS, repair=repair_micro,
                              prompt_version=MICRO_PROMPT_VERSION)


def _evergreen(dossier_id: str) -> MicroDesk | None:
    from app.services.revue.evergreen import evergreen_micro  # noqa: PLC0415

    return evergreen_micro(dossier_id)


def ensure_micro(db: Any, period: str, *, provider: Any = None) -> list[str]:
    """Each morning, once per kiosk row (``rubriques.ensure_desk``)."""

    return rubriques.ensure_desk(db, period, key="micro", write=write_micro, evergreen=_evergreen, provider=provider)


def micro_of(dossier: EditorialDossier) -> MicroDesk | None:
    """The interview a session on ``dossier`` plays: the dossier's own, else the evergreen's."""

    return rubriques.material_of(dossier, "micro", _evergreen)


__all__ = [
    "MICRO_DESK_INSTRUCTIONS",
    "MICRO_PROMPT_VERSION",
    "answer_problem",
    "audit",
    "content_stems",
    "ensure_micro",
    "formation_slips",
    "generic_words",
    "is_question",
    "match",
    "micro_of",
    "question_word",
    "repair_micro",
    "witness_of",
    "write_micro",
]
