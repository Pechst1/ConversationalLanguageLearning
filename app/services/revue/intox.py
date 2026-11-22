"""«L'intox express»: the express desk (WP-119 «les rubriques», owner 2026-11-20).

Five short statements about the story, three true and two false: the learner, Romy's trainee,
reads the story (the lead stays one tap away: reading practice, not memory), says «vrai» or
«faux» to each, then corrects the two false ones (the loop is ``intox_loop.py``; the dealer
is ``assignments.py``). This module writes what every learner shares:
:class:`~app.services.revue.dossier.IntoxExpress`, one JSON call per story
(:func:`write_intox`), modelled on the wire desk (``fil.py``).

- Each statement is told at A1 (≤ 8 words), A2 (≤ 12) and B1 (≤ 16; B2 reads B1), with
  English and German, tied to one claim (``claim_id``) and grounded in it, with the comptoir's
  checks (no number or name the claims lack, no relative date, no id, no app word) and never a
  word about a person's private life (``rubriques.private``).
- A true statement carries no number its claim does not carry.
- A false one changes exactly ONE element of its claim (``swap``: a number, a day, a place,
  who), as the comptoir's intox: ``wrong_fr`` is in the statement at every band and in no
  claim (nor the title or summary), case- and accent-folded; ``right_fr`` is in its claim;
  ``distractor_fr`` is another value of the same kind from the claims (the A1–A2 pick);
  ``fixed`` the statement as it should read (carries ``right_fr``, never ``wrong_fr``).
- Each statement keeps its claim's verbatim quote (the outlet's words, ≤ 40 words, already
  checked by the dossier) with the outlet's name, and the words in it that settle the
  statement (``settles_fr``, lit by the player; nothing is lit when they are not in it).
- One statement that fails refuses the whole round: five or none.
- A story the comptoir would not argue about (a death, a war, a crime with victims, an
  election) gets none: the desk answers ``fit: "skip"`` and a row whose takes were skipped is
  never asked (``rubriques.ensure_desk``).
"""

from __future__ import annotations

import re
from typing import Any

from app.services.revue import rubriques
from app.services.revue.comptoir import (
    _CALENDAR,
    _Checker,
    _value,
    ci,
    contains,
    in_story,
    numbers,
    numeric,
    value_kind,
    word_count,
)
from app.services.revue.dossier import (
    BandTexts,
    ComptoirPhrase,
    ComptoirText,
    EditorialDossier,
    IntoxExpress,
    IntoxStatement,
)
from app.services.revue.fil import _content, _stems

INTOX_PROMPT_VERSION = "intox-express-v2"

STATEMENT_MAX_WORDS: dict[str, int] = {"a1": 8, "a2": 12, "b1": 16}
#: A fixed statement may be a little longer than the false one (the true value can be).
FIXED_EXTRA_WORDS = 4
WHY_MAX_WORDS = 20
VALUE_MAX_WORDS = 6
PHRASE_MAX_WORDS = 10
SWAPS: tuple[str, ...] = ("number", "day", "place", "who")


def _t(fr: str, en: str, de: str) -> ComptoirText:
    return ComptoirText(fr=fr, en=en, de=de)


AUTHORED_PHRASE = ComptoirPhrase(
    a1=_t("C'est vrai. · C'est faux.", "That's true. · That's false.", "Das stimmt. · Das stimmt nicht."),
    a2=_t("Ce n'est pas…, c'est…", "It isn't…, it's…", "Es ist nicht…, es ist…"),
    b1=_t("En réalité, …", "In reality, …", "In Wirklichkeit …"),
    b2=_t("Contrairement à ce qu'on dit, …", "Contrary to what people say, …", "Anders als behauptet …"),
)

# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

INTOX_SPEC = """{"fit": "express" | "skip",
 "statements": [{"claim_id": str, "true": bool, "a1": T, "a2": T, "b1": T, "why": T, "settles_fr": str,
   "swap": "number" | "day" | "place" | "who", "wrong_fr": str, "right_fr": str, "distractor_fr": str,
   "fixed": {"a1": T, "a2": T, "b1": T}}, ×5],
 "phrase": {"a1": T, "a2": T, "b1": T, "b2": T}}
where T = {"fr": str, "en": str, "de": str} (en and de translate the French faithfully, every time); swap,
wrong_fr, right_fr, distractor_fr and fixed only on a false statement"""

INTOX_RULES = """RULES
- fit: "skip" ONLY when the story is a death, a war, a crime with victims, an election or a party's politics, or
  anything where a true-or-false game would be cruel, or when there are fewer than three claims. Otherwise
  "express": three or four claims are enough, because one claim can carry two statements (one true, one false,
  or two different facts of it) — the EXAMPLE below makes five statements from four claims.
- statements: exactly five short statements about the story, THREE true and TWO false, in any order. Each comes
  from ONE claim (claim_id) and uses its words. a1: one present-tense sentence, 8 words at most, the most common
  words. a2: 12 words at most. b1: 16 words at most. Never about a person's private life (family, love, health,
  home, money, religion).
- A true statement says only what its claim says; no number its claim does not carry.
- A false statement changes exactly ONE element of its claim and nothing else: a number, a day, a place, or who
  (swap). The false value stays plausible, of the claim's own kind and unit, so only a reader of the facts can
  tell («2 500 mètres» for «2 400 mètres», «le 8 octobre» for «le 6 octobre»); never an absurd one («5 millions
  de mètres») nor one borrowed from another claim's unit. wrong_fr: the changed words exactly as they stand in each of a1, a2 and b1 (6 words at most); they must
  appear in NO claim. right_fr: the true words, copied exactly from the claim. distractor_fr: ANOTHER value of the
  same kind copied from the claims (a day for a day, a who for a who), neither the true nor the false one,
  character for character as a claim writes it (never a value from the articles); when the claims hold no
  second value of that kind, change another element instead. fixed:
  the statement at each band as it should read, with right_fr in place of wrong_fr.
- why: one line, 20 words at most, that says what settles the statement («La mairie annonce les travaux le 3
  mars.»; on a false one «…, pas le 20 mars.»).
- settles_fr: the words of the claim's quote (its "quote", the outlet's own words) that settle it, copied
  exactly from that quote, 12 words at most.
- Facts: only what the claims say. Numbers in digits, copied exactly from the claims (the false value excepted);
  no name the claims do not carry. Never a relative date (demain, hier, aujourd'hui, ce soir, cette semaine) nor
  a weekday the claims do not name. Never about the app: never «dossier», «session», «application».
- Our French only: never copy the outlet's sentences into a statement.
- phrase: how to say it when a statement is false, per band (a1 «C'est faux.», a2 «Ce n'est pas…, c'est…», b1
  «En réalité, …», b2 «Contrairement à ce qu'on dit, …»).
- French typography: a space before ? ! : ;
EXAMPLE (story: the covered market Beauvau closes for works; claims c1 «Le 3 mars, la mairie du 12e
arrondissement annonce des travaux au marché Beauvau.», c2 «Le 10 mars, les commerçants quittent le marché couvert
et s'installent sur la place d'Aligre.», c3 «Après le départ des commerçants, les ouvriers changent le toit du
marché.», c4 «Une fois les travaux finis, le marché Beauvau rouvre le 14 novembre.», each with its quote):
{"fit": "express",
 "statements": [
  {"claim_id": "c4", "true": true,
   "a1": {"fr": "Le marché rouvre le 14 novembre.", "en": "The market reopens on 14 November.", "de": "Der Markt öffnet am 14. November wieder."},
   "a2": {"fr": "Une fois les travaux finis, le marché rouvre le 14 novembre.", "en": "Once the works are finished, the market reopens on 14 November.", "de": "Nach den Arbeiten öffnet der Markt am 14. November wieder."},
   "b1": {"fr": "Une fois les travaux finis, le marché Beauvau rouvre ses portes le 14 novembre.", "en": "Once the works are finished, the Beauvau market opens its doors again on 14 November.", "de": "Nach den Arbeiten öffnet der Markt Beauvau am 14. November wieder seine Türen."},
   "why": {"fr": "Le marché rouvre bien le 14 novembre, après les travaux.", "en": "The market does reopen on 14 November, after the works.", "de": "Der Markt öffnet tatsächlich am 14. November wieder, nach den Arbeiten."},
   "settles_fr": "le 14 novembre"},
  {"claim_id": "c2", "true": false, "swap": "day", "wrong_fr": "le 20 mars", "right_fr": "le 10 mars", "distractor_fr": "le 3 mars",
   "a1": {"fr": "Les commerçants partent le 20 mars.", "en": "The traders leave on 20 March.", "de": "Die Händler gehen am 20. März."},
   "a2": {"fr": "Le 20 mars, les commerçants quittent le marché couvert.", "en": "On 20 March, the traders leave the covered market.", "de": "Am 20. März verlassen die Händler die Markthalle."},
   "b1": {"fr": "Le 20 mars, les commerçants quittent le marché couvert pour la place d'Aligre.", "en": "On 20 March, the traders leave the covered market for the Place d'Aligre.", "de": "Am 20. März verlassen die Händler die Markthalle und ziehen auf die Place d'Aligre."},
   "fixed": {"a1": {"fr": "Les commerçants partent le 10 mars.", "en": "The traders leave on 10 March.", "de": "Die Händler gehen am 10. März."},
     "a2": {"fr": "Le 10 mars, les commerçants quittent le marché couvert.", "en": "On 10 March, the traders leave the covered market.", "de": "Am 10. März verlassen die Händler die Markthalle."},
     "b1": {"fr": "Le 10 mars, les commerçants quittent le marché couvert pour la place d'Aligre.", "en": "On 10 March, the traders leave the covered market for the Place d'Aligre.", "de": "Am 10. März verlassen die Händler die Markthalle und ziehen auf die Place d'Aligre."}},
   "why": {"fr": "Les commerçants quittent le marché le 10 mars, pas le 20 mars.", "en": "The traders leave the market on 10 March, not on 20 March.", "de": "Die Händler verlassen den Markt am 10. März, nicht am 20. März."},
   "settles_fr": "Le 10 mars"},
  {"claim_id": "c3", "true": true,
   "a1": {"fr": "Les ouvriers changent le toit du marché.", "en": "The workers change the market's roof.", "de": "Die Arbeiter erneuern das Dach des Marktes."},
   "a2": {"fr": "Après le départ des commerçants, les ouvriers changent le toit.", "en": "After the traders leave, the workers change the roof.", "de": "Nach dem Auszug der Händler erneuern die Arbeiter das Dach."},
   "b1": {"fr": "Après le départ des commerçants, les ouvriers changent le toit du marché couvert.", "en": "After the traders leave, the workers change the roof of the covered market.", "de": "Nach dem Auszug der Händler erneuern die Arbeiter das Dach der Markthalle."},
   "why": {"fr": "Les ouvriers changent bien le toit, après le départ des commerçants.", "en": "The workers do change the roof, after the traders leave.", "de": "Die Arbeiter erneuern tatsächlich das Dach, nach dem Auszug der Händler."},
   "settles_fr": "les ouvriers changeront le toit"},
  {"claim_id": "c1", "true": false, "swap": "who", "wrong_fr": "la région", "right_fr": "la mairie", "distractor_fr": "les commerçants",
   "a1": {"fr": "La région annonce des travaux au marché.", "en": "The region announces works at the market.", "de": "Die Region kündigt Arbeiten am Markt an."},
   "a2": {"fr": "Le 3 mars, la région annonce des travaux au marché Beauvau.", "en": "On 3 March, the region announces works at the Beauvau market.", "de": "Am 3. März kündigt die Region Arbeiten am Markt Beauvau an."},
   "b1": {"fr": "Le 3 mars, la région annonce des travaux au marché couvert Beauvau.", "en": "On 3 March, the region announces works at the Beauvau covered market.", "de": "Am 3. März kündigt die Region Arbeiten an der Markthalle Beauvau an."},
   "fixed": {"a1": {"fr": "La mairie annonce des travaux au marché.", "en": "The town hall announces works at the market.", "de": "Das Rathaus kündigt Arbeiten am Markt an."},
     "a2": {"fr": "Le 3 mars, la mairie annonce des travaux au marché Beauvau.", "en": "On 3 March, the town hall announces works at the Beauvau market.", "de": "Am 3. März kündigt das Rathaus Arbeiten am Markt Beauvau an."},
     "b1": {"fr": "Le 3 mars, la mairie annonce des travaux au marché couvert Beauvau.", "en": "On 3 March, the town hall announces works at the Beauvau covered market.", "de": "Am 3. März kündigt das Rathaus Arbeiten an der Markthalle Beauvau an."}},
   "why": {"fr": "C'est la mairie du 12e arrondissement qui annonce les travaux, pas la région.", "en": "It is the town hall of the 12th arrondissement that announces the works, not the region.", "de": "Das Rathaus des 12. Arrondissements kündigt die Arbeiten an, nicht die Region."},
   "settles_fr": "la mairie du 12e arrondissement"},
  {"claim_id": "c2", "true": true,
   "a1": {"fr": "Les commerçants s'installent place d'Aligre.", "en": "The traders set up on the Place d'Aligre.", "de": "Die Händler ziehen auf die Place d'Aligre."},
   "a2": {"fr": "Les commerçants quittent le marché et s'installent place d'Aligre.", "en": "The traders leave the market and set up on the Place d'Aligre.", "de": "Die Händler verlassen den Markt und ziehen auf die Place d'Aligre."},
   "b1": {"fr": "Le 10 mars, les commerçants s'installent sur la place d'Aligre.", "en": "On 10 March, the traders set up on the Place d'Aligre.", "de": "Am 10. März ziehen die Händler auf die Place d'Aligre."},
   "why": {"fr": "Les commerçants s'installent bien sur la place d'Aligre.", "en": "The traders do set up on the Place d'Aligre.", "de": "Die Händler ziehen tatsächlich auf die Place d'Aligre."},
   "settles_fr": "s'installer place d'Aligre"}],
 "phrase": {"a1": {"fr": "C'est faux.", "en": "That's false.", "de": "Das stimmt nicht."},
  "a2": {"fr": "Ce n'est pas…, c'est…", "en": "It isn't…, it's…", "de": "Es ist nicht…, es ist…"},
  "b1": {"fr": "En réalité, …", "en": "In reality, …", "de": "In Wirklichkeit …"},
  "b2": {"fr": "Contrairement à ce qu'on dit, …", "en": "Contrary to what people say, …", "de": "Anders als behauptet …"}}}
Do not reuse the example's lines: write for THIS story."""

INTOX_DESK_INSTRUCTIONS = (
    """You write «L'intox express» for «Le Papier de Romy», a French-learning app. The learner is the trainee of
Romy, a Québécoise journalist; after reading a news story they say whether five short statements about it are true
or false, then correct the false ones. From INPUT (the story's French facts and the claims' quotes) answer with ONE
JSON object:
"""
    + INTOX_SPEC
    + "\n"
    + INTOX_RULES
)

# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def grounded(fr: str, claim_fr: str) -> bool:
    """``fr`` shares a content word with its claim (fil's check)."""

    return bool(_stems(_content(fr)) & _stems(_content(claim_fr)))


def swap_problem(swap: str, wrong: str, right: str) -> str | None:
    """Why ``wrong`` and ``right`` are not the same kind of element as ``swap`` says."""

    if swap not in SWAPS:
        return "swap_unknown"
    if swap == "number":
        return None if numeric(wrong) and numeric(right) else "swap_kind"
    if swap == "day":
        def dated(value: str) -> bool:
            return bool(set(re.findall(r"[a-z]+", ci(value))) & _CALENDAR) or bool(numbers(value))
        return None if dated(wrong) and dated(right) else "swap_kind"
    return None if not numeric(wrong) and not numeric(right) else "swap_kind"


def quote_slice(quote: str, words: str) -> str:
    """``words`` as they stand in ``quote`` (case and accents of the quote), or ``""``."""

    folded, needle = ci(quote), ci(words).strip(" .,!?…«»\"")
    at = folded.find(needle) if needle else -1
    if at < 0 or len(folded) != len(quote):
        return words.strip() if at >= 0 else ""
    return quote[at:at + len(needle)]


def _bands(check: _Checker, row: Any, limits: dict[str, int], *, allow: str | None = None,
           extra: int = 0) -> tuple[dict[str, ComptoirText], list[str]]:
    texts: dict[str, ComptoirText] = {}
    whys: list[str] = []
    if not isinstance(row, dict):
        return texts, ["missing"]
    for band, limit in limits.items():
        line, why = rubriques.text(check, row.get(band), limit + extra, allow=allow)
        if line is None:
            whys.append(f"{band}:{why}")
            continue
        texts[band] = line
    return texts, whys


def _statement(index: int, row: Any, dossier: EditorialDossier, check: _Checker) -> tuple[IntoxStatement | None, list[str], list[str]]:
    """One statement checked: ``(statement, refusals, problems)``."""

    tag = f"intox:{index}"
    if not isinstance(row, dict):
        return None, [f"{tag}:missing"], []
    claims = dossier.claims_by_id()
    claim = claims.get(str(row.get("claim_id") or "").strip())
    if claim is None:
        return None, [f"{tag}:claim_unknown"], []
    is_true = row.get("true")
    if not isinstance(is_true, bool):
        return None, [f"{tag}:true_missing"], []
    wrong = right = distractor = None
    swap = None
    if not is_true:
        swap = str(row.get("swap") or "").strip().lower()
        wrong, right, distractor = (_value(row.get("wrong_fr")), _value(row.get("right_fr")),
                                    _value(row.get("distractor_fr")))
        if not 1 <= word_count(wrong) <= VALUE_MAX_WORDS:
            return None, [f"{tag}:wrong_length"], []
        if contains(check.story, wrong) or any(contains(c.fr, wrong) for c in dossier.claims):
            return None, [f"{tag}:not_false"], []
        if not right or word_count(right) > VALUE_MAX_WORDS + 2 or not contains(claim.fr, right):
            return None, [f"{tag}:right_not_in_claim"], []
        if ci(right) == ci(wrong) or contains(right, wrong) or contains(wrong, right):
            return None, [f"{tag}:right_is_wrong"], []
        why = swap_problem(swap, wrong, right)
        if why:
            return None, [f"{tag}:{why}"], []
        if numbers(right) - check.known:
            return None, [f"{tag}:right_number"], []
        if (not distractor or word_count(distractor) > VALUE_MAX_WORDS + 2 or not in_story(check.story, distractor)
                or ci(distractor) in {ci(right), ci(wrong)} or contains(right, distractor) or contains(distractor, right)
                or value_kind(right) != value_kind(distractor)):
            return None, [f"{tag}:distractor"], []
    texts, whys = _bands(check, row, STATEMENT_MAX_WORDS, allow=wrong)
    refusals = [f"{tag}:{why}" for why in whys]
    claim_numbers = numbers(claim.fr)
    for band, line in texts.items():
        if not grounded(line.fr, claim.fr):
            refusals.append(f"{tag}:{band}:ungrounded")
        elif is_true and numbers(line.fr) - claim_numbers:
            refusals.append(f"{tag}:{band}:number_not_in_claim")
        elif not is_true and not contains(line.fr, wrong):
            refusals.append(f"{tag}:{band}:wrong_not_in_statement")
        elif not is_true and contains(line.fr, right):
            refusals.append(f"{tag}:{band}:right_in_statement")
        elif not is_true and numbers(line.fr) - claim_numbers - numbers(wrong):
            refusals.append(f"{tag}:{band}:two_changes")
    fixed = None
    if not is_true:
        fixed_texts, whys = _bands(check, row.get("fixed"), STATEMENT_MAX_WORDS, extra=FIXED_EXTRA_WORDS)
        refusals += [f"{tag}:fixed:{why}" for why in whys]
        for band, line in fixed_texts.items():
            if not contains(line.fr, right) or contains(line.fr, wrong) or numbers(line.fr) - claim_numbers:
                refusals.append(f"{tag}:fixed:{band}:not_true")
        if len(fixed_texts) == 3:
            fixed = BandTexts(**fixed_texts)
    why_line, why = rubriques.text(check, row.get("why"), WHY_MAX_WORDS, allow=wrong)
    if why_line is None:
        refusals.append(f"{tag}:why:{why}")
    if refusals or len(texts) < 3:
        return None, refusals or [f"{tag}:incomplete"], []
    problems: list[str] = []
    settles = quote_slice(claim.quote, str(row.get("settles_fr") or ""))
    if not settles and right:
        settles = quote_slice(claim.quote, right)
    if not settles:
        problems.append(f"{tag}:settles_not_in_quote")
    source = next((s.name for s in dossier.sources if s.id == claim.source_id), "")
    statement = IntoxStatement(
        claim_id=claim.id, true=is_true, why=why_line, quote_fr=claim.quote, source_name=source, settles_fr=settles,
        swap=swap, wrong_fr=wrong, right_fr=right, distractor_fr=distractor, fixed=fixed,  # type: ignore[arg-type]
        **texts,
    )
    return statement, [], problems


def repair_intox(raw: Any, dossier: EditorialDossier) -> tuple[IntoxExpress | None, list[str]]:
    """What the express desk wrote, checked against ``dossier``. ``(None, ["skip"])`` for an
    unfit story; ``(None, problems)`` when the round is refused (one statement fails, not three
    true and two false); else the round and what fell back to authored lines."""

    if not isinstance(raw, dict):
        return None, ["intox:missing"]
    if str(raw.get("fit") or "").strip().lower() == "skip":
        return None, ["skip"]
    rows = raw.get("statements")
    if not isinstance(rows, list) or len(rows) != 5:
        return None, ["intox:statements:count"]
    check = _Checker(dossier)
    statements: list[IntoxStatement] = []
    refusals: list[str] = []
    problems: list[str] = []
    for index, row in enumerate(rows, start=1):
        statement, refused, soft = _statement(index, row, dossier, check)
        refusals += refused
        problems += soft
        if statement is not None:
            statements.append(statement)
    if refusals:
        return None, [*refusals, *problems]
    if sum(1 for s in statements if s.true) != 3:
        return None, ["intox:statements:three_true_two_false", *problems]
    for band in STATEMENT_MAX_WORDS:
        if len({ci(s.for_band(band).fr) for s in statements}) < 5:
            return None, ["intox:statements:duplicate", *problems]
    phrase: dict[str, ComptoirText] = {}
    raw_phrase = raw.get("phrase") if isinstance(raw.get("phrase"), dict) else {}
    for band in ("a1", "a2", "b1", "b2"):
        line, why = check.text(raw_phrase.get(band), PHRASE_MAX_WORDS)
        if line is None:
            problems.append(f"intox:phrase:{band}:{why}")
        phrase[band] = line or getattr(AUTHORED_PHRASE, band)
    return IntoxExpress(statements=statements, phrase=ComptoirPhrase(**phrase)), problems


def as_desk_answer(express: IntoxExpress) -> dict[str, Any]:
    """``express`` in the desk's answer shape, so :func:`audit` runs the same checks on stored
    or hand-written rounds (the evergreens' files, the tests)."""

    data = express.model_dump(mode="json")
    keep = ("claim_id", "true", "a1", "a2", "b1", "why", "settles_fr", "swap", "wrong_fr", "right_fr",
            "distractor_fr", "fixed")
    return {"fit": "express", "phrase": data["phrase"],
            "statements": [{k: row[k] for k in keep if row.get(k) is not None} for row in data["statements"]]}


def audit(express: IntoxExpress, dossier: EditorialDossier) -> list[str]:
    """Every check :func:`repair_intox` would make on ``express``: ``[]`` when nothing would change."""

    repaired, problems = repair_intox(as_desk_answer(express), dossier)
    return problems if repaired is not None else problems or ["intox:refused"]


# ---------------------------------------------------------------------------
# The desk
# ---------------------------------------------------------------------------


def write_intox(dossier: EditorialDossier, provider: Any = None) -> tuple[IntoxExpress | None, list[str]]:
    """The express desk: one JSON call (a second with the problems), checked by :func:`repair_intox`."""

    return rubriques.ask_desk(dossier, provider, key="intox", instructions=INTOX_DESK_INSTRUCTIONS,
                              repair=repair_intox, prompt_version=INTOX_PROMPT_VERSION)


def _evergreen(dossier_id: str) -> IntoxExpress | None:
    from app.services.revue.evergreen import evergreen_intox  # noqa: PLC0415

    return evergreen_intox(dossier_id)


def ensure_intox(db: Any, period: str, *, provider: Any = None) -> list[str]:
    """Each morning, once per kiosk row (``rubriques.ensure_desk``)."""

    return rubriques.ensure_desk(db, period, key="intox", write=write_intox, evergreen=_evergreen, provider=provider)


def intox_of(dossier: EditorialDossier) -> IntoxExpress | None:
    """The round a session on ``dossier`` plays: the dossier's own, else the evergreen's."""

    return rubriques.material_of(dossier, "intox", _evergreen)


__all__ = [
    "INTOX_DESK_INSTRUCTIONS",
    "INTOX_PROMPT_VERSION",
    "audit",
    "ensure_intox",
    "intox_of",
    "repair_intox",
    "write_intox",
]
