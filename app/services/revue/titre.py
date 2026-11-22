"""«Le titre»: the headline desk (WP-119 «les rubriques», owner 2026-11-20).

Gus, who exaggerates by character, proposes three headlines for the story; the learner,
Romy's trainee, picks the honest one, names what makes the exaggerated one false and writes a
better headline (the loop is ``titre_loop.py``; the dealer is ``assignments.py``). This module
writes what every learner shares: :class:`~app.services.revue.dossier.TitreDesk`, one JSON
call per story (:func:`write_titre`), modelled on the wire desk (``fil.py``).

- Three headlines at A1 (≤ 7 words), A2 (≤ 9) and B1 (≤ 12; B2 reads B1), with English and
  German: exactly one ``honest`` (says what the claims say), one ``exaggerated`` (says MORE: a
  wider place, «always / everyone», a bigger number, a certainty the story lacks) and one
  ``off`` (true-sounding but about a detail, missing the news). Headlines are OURS: never an
  outlet's words (a headline inside a claim's quote is refused).
- The honest headline carries no number and no name the claims do not carry (the claims
  alone, not the summary); it is grounded in its claim and never says the exaggerated words.
- The exaggerated one differs from the claims in exactly the stated way (``stretch``): its
  wrong words (``wrong_fr``) are in its text at every band and in no claim (nor the title or
  summary), case- and accent-folded; ``number`` needs a number, ``always`` a word such as
  «toujours», «tout le monde», ``certainty`` a word such as «c'est sûr», ``place`` no number.
- Each wrong one says why (≤ 20 words, fr + en + de) and the claim that settles it.
- «À toi»'s material: A1 tiles (two or three subjects, two to four facts: every pair a true
  headline, correct by construction, never the exaggerated words, never a vocative) and the A2
  frame; the phrase of the day per band.
- One check that fails refuses the whole desk (after one retry, ``rubriques.ask_desk``).
"""

from __future__ import annotations

import re
from typing import Any

from app.services.revue import rubriques
from app.services.revue.comptoir import (
    ROMY_ID,
    _Checker,
    _value,
    address_problem,
    ci,
    contains,
    numbers,
    numeric,
    word_count,
)
from app.services.revue.dossier import (
    TITRE_ROLES,
    ComptoirPhrase,
    ComptoirText,
    EditorialDossier,
    TitreBuild,
    TitreDesk,
    TitreHeadline,
)
from app.services.revue.fil import new_names
from app.services.revue.intox import grounded

TITRE_PROMPT_VERSION = "titre-desk-v3"

HEADLINE_MAX_WORDS: dict[str, int] = {"a1": 7, "a2": 9, "b1": 12}
WHY_MAX_WORDS = 20
WRONG_MAX_WORDS = 6
SUBJECT_MAX_WORDS = 5
FACT_MAX_WORDS = 6
FRAME_MAX_WORDS = 5
PHRASE_MAX_WORDS = 10
STRETCHES: tuple[str, ...] = ("place", "always", "number", "certainty")

#: The words that say «always / everyone / never»: an ``always`` stretch carries one.
ALWAYS_WORDS: tuple[str, ...] = (
    "toujours", "jamais", "tout le monde", "tous", "toutes", "chaque", "personne", "aucun", "aucune",
    "sans exception", "a chaque fois", "tout le temps", "plus jamais", "pour toujours", "partout",
)
#: The words that claim a certainty: a ``certainty`` stretch carries one.
CERTAINTY_WORDS: tuple[str, ...] = (
    "c'est sur", "c'est certain", "c'est officiel", "officiel", "officiellement", "definitivement", "definitif",
    "prouve", "sans aucun doute", "sans doute", "a coup sur", "confirme", "garanti", "garantie", "assurement",
    "forcement", "certainement", "enfin", "pour de bon", "c'est fini", "c'est fait",
)


def _t(fr: str, en: str, de: str) -> ComptoirText:
    return ComptoirText(fr=fr, en=en, de=de)


AUTHORED_PHRASE = ComptoirPhrase(
    a1=_t("La fête est…", "The festival is…", "Das Fest ist…"),
    a2=_t("… et …", "… and …", "… und …"),
    b1=_t("… : … mais …", "… : … but …", "… : … aber …"),
    b2=_t("Selon…, …", "According to…, …", "Laut…, …"),
)

# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

TITRE_SPEC = """{"fit": "titles" | "skip",
 "headlines": [{"role": "honest" | "exaggerated" | "off", "claim_id": str, "a1": T, "a2": T, "b1": T, "why": T}, ×3],
 "stretch": "place" | "always" | "number" | "certainty",
 "wrong_fr": str,
 "build": {"subjects": [T, T], "facts": [T, T, T], "frame": T},
 "phrase": {"a1": T, "a2": T, "b1": T, "b2": T}}
where T = {"fr": str, "en": str, "de": str} (en and de translate the French faithfully, every time); "why" only on
the exaggerated and the off headline"""

TITRE_RULES = """RULES
- fit: "skip" when the story is a death, a war, a crime with victims, an election or a party's politics, or
  anything where a headline game would be cruel. Otherwise "titles".
- headlines: three headlines for the story, newspaper style (no final full stop), written by YOU, never an outlet's
  headline or words. a1: 7 words at most, the most common words; a2: 9 words at most; b1: 12 words at most.
  - honest: says what the claims say, nothing more. No number and no name the claims do not carry. claim_id: the
    claim it rests on.
  - exaggerated: the honest news said with MORE than the claims say, in exactly one way (stretch): a wider place
    («partout en France» for one city), «always / everyone» («toujours», «tout le monde», «tous»), a bigger number
    in digits («30 chevaux» for sixteen), or a certainty the story lacks with one of «c'est officiel», «c'est
    sûr», «c'est certain», «c'est prouvé», «définitivement», «sans aucun doute», «confirmé». Never «sûrement» or
    «probablement»: in French they mean "probably", not a certainty. A changed verb («sont installés» for «doivent
    être installés») is not a stretch. wrong_fr is ONLY the words that say too much, never a word the
    honest headline says too: for a bigger number the number alone («200», not «200 nouveaux voiles»). wrong_fr: the words that say too much, exactly
    as they stand in its a1, a2 AND b1 (6 words at most); they must appear in NO claim. claim_id: the claim that
    shows it says too much.
  - off: sounds true and is true, but is about a detail of the story and misses the news. claim_id: the claim the
    detail comes from.
  - why (exaggerated and off only): what the headline claims that the article does not say, 20 words at most.
- build: what a beginner builds a headline from: subjects (2 or 3, 5 words at most each, «La Fête de la musique»)
  and facts (2 to 4, 6 words at most each, «est gratuite»): EVERY subject followed by EVERY fact must make a true
  headline; never the exaggerated words; never a vocative or an exclamation. Each fact uses its claim's own verb
  and words («augmentent de 9,9 %» when the claim says «augmentent», never a synonym such as «progressent»). frame: an A2 headline's opening (5
  words at most) that the learner completes.
- phrase: a headline pattern of each band (a1 «La fête est…», a2 «… et …», b1 «… : … mais …», b2 «Selon…, …»).
- Facts: only what the claims say. Numbers in digits, copied exactly from the claims (the exaggerated number
  excepted). Never a relative date (demain, hier, aujourd'hui, ce soir, cette semaine) nor a weekday the claims do
  not name. Never about the app: never «dossier», «session», «application». Never about a person's private life.
- French typography: a space before ? ! : ;
EXAMPLE (story: the covered market Beauvau closes for works; claims c1 «Le 3 mars, la mairie du 12e
arrondissement annonce des travaux au marché Beauvau.», c2 «Le 10 mars, les commerçants quittent le marché couvert
et s'installent sur la place d'Aligre.», c3 «Après le départ des commerçants, les ouvriers changent le toit du
marché.», c4 «Une fois les travaux finis, le marché Beauvau rouvre le 14 novembre.»):
{"fit": "titles",
 "headlines": [
  {"role": "honest", "claim_id": "c4",
   "a1": {"fr": "Le marché Beauvau rouvre le 14 novembre", "en": "The Beauvau market reopens on 14 November", "de": "Der Markt Beauvau öffnet am 14. November wieder"},
   "a2": {"fr": "Le marché Beauvau rouvre ses portes le 14 novembre", "en": "The Beauvau market opens its doors again on 14 November", "de": "Der Markt Beauvau öffnet am 14. November wieder seine Türen"},
   "b1": {"fr": "Toit neuf et travaux finis : le marché Beauvau rouvre le 14 novembre", "en": "New roof, works finished: the Beauvau market reopens on 14 November", "de": "Neues Dach, Arbeiten fertig: Der Markt Beauvau öffnet am 14. November wieder"}},
  {"role": "exaggerated", "claim_id": "c4",
   "a1": {"fr": "Tous les marchés de Paris rouvrent", "en": "All the markets in Paris reopen", "de": "Alle Märkte von Paris öffnen wieder"},
   "a2": {"fr": "Après les travaux, tous les marchés de Paris rouvrent", "en": "After the works, all the markets in Paris reopen", "de": "Nach den Arbeiten öffnen alle Märkte von Paris wieder"},
   "b1": {"fr": "Travaux finis : tous les marchés de Paris rouvrent le 14 novembre", "en": "Works finished: all the markets in Paris reopen on 14 November", "de": "Arbeiten fertig: Alle Märkte von Paris öffnen am 14. November wieder"},
   "why": {"fr": "L'article parle d'un seul marché, le marché Beauvau, pas de tous les marchés.", "en": "The article is about one market, the Beauvau market, not all markets.", "de": "Der Artikel spricht von einem Markt, dem Markt Beauvau, nicht von allen Märkten."}},
  {"role": "off", "claim_id": "c3",
   "a1": {"fr": "Les ouvriers changent un toit", "en": "The workers change a roof", "de": "Die Arbeiter erneuern ein Dach"},
   "a2": {"fr": "Dans le 12e, des ouvriers changent un toit", "en": "In the 12th, workers change a roof", "de": "Im 12. Bezirk erneuern Arbeiter ein Dach"},
   "b1": {"fr": "Dans le 12e arrondissement, des ouvriers changent le toit d'un marché", "en": "In the 12th arrondissement, workers change the roof of a market", "de": "Im 12. Arrondissement erneuern Arbeiter das Dach eines Marktes"},
   "why": {"fr": "C'est vrai, mais la nouvelle, c'est la réouverture du marché le 14 novembre.", "en": "True, but the news is that the market reopens on 14 November.", "de": "Stimmt, aber die Nachricht ist, dass der Markt am 14. November wieder öffnet."}}],
 "stretch": "place",
 "wrong_fr": "tous les marchés de Paris",
 "build": {"subjects": [{"fr": "Le marché Beauvau", "en": "The Beauvau market", "de": "Der Markt Beauvau"},
   {"fr": "Le marché couvert", "en": "The covered market", "de": "Die Markthalle"}],
  "facts": [{"fr": "rouvre le 14 novembre", "en": "reopens on 14 November", "de": "öffnet am 14. November wieder"},
   {"fr": "ferme pour des travaux", "en": "closes for works", "de": "schließt wegen Arbeiten"},
   {"fr": "a un toit neuf", "en": "has a new roof", "de": "hat ein neues Dach"}],
  "frame": {"fr": "Le marché Beauvau", "en": "The Beauvau market", "de": "Der Markt Beauvau"}},
 "phrase": {"a1": {"fr": "Le marché rouvre…", "en": "The market reopens…", "de": "Der Markt öffnet wieder…"},
  "a2": {"fr": "… et …", "en": "… and …", "de": "… und …"},
  "b1": {"fr": "… : … mais …", "en": "… : … but …", "de": "… : … aber …"},
  "b2": {"fr": "Selon…, …", "en": "According to…, …", "de": "Laut…, …"}}}
Do not reuse the example's lines: write for THIS story."""

TITRE_DESK_INSTRUCTIONS = (
    """You write «Le titre» for «Le Papier de Romy», a French-learning app. The learner is the trainee of Romy, a
Québécoise journalist; Gus, a regular of the café who always exaggerates, proposes three headlines for a news story
and the learner must find the honest one, say what makes the exaggerated one false, then write a better one. From
INPUT (the story's French facts) answer with ONE JSON object:
"""
    + TITRE_SPEC
    + "\n"
    + TITRE_RULES
)

# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    folded = f" {ci(text)} "
    return any(re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", folded) for word in words)


def stretch_problem(stretch: str, wrong: str) -> str | None:
    """Why ``wrong`` does not say too much in the way ``stretch`` says, or ``None``."""

    if stretch not in STRETCHES:
        return "stretch_unknown"
    if stretch == "number":
        return None if numeric(wrong) else "stretch_kind"
    if stretch == "always":
        return None if _has_word(wrong, ALWAYS_WORDS) else "stretch_kind"
    if stretch == "certainty":
        return None if _has_word(wrong, CERTAINTY_WORDS) else "stretch_kind"
    return None if not numeric(wrong) else "stretch_kind"


def too_wide(wrong: str, honest: TitreHeadline) -> bool:
    """``wrong_fr`` carries a word the honest headline says too, at every band: the trap would
    strike true words (first real run: «200 nouveaux voiles» struck «nouveaux» and «voiles»,
    which the honest «100 nouveaux voiles» says; only «200» says too much)."""

    words = re.findall(r"[a-z]{4,}", ci(wrong))
    return any(all(re.search(rf"(?<![a-z]){w}(?![a-z])", ci(honest.for_band(b).fr)) for b in HEADLINE_MAX_WORDS)
               for w in words)


def headline_text(fr: str) -> str:
    """A headline as the page prints it: no final full stop."""

    return re.sub(r"\s+", " ", str(fr or "")).strip().rstrip(" .")


def _claims_text(dossier: EditorialDossier) -> str:
    return " ".join(c.fr for c in dossier.claims)


def outlet_words(fr: str, dossier: EditorialDossier) -> bool:
    """``fr`` is an outlet's words: inside a claim's verbatim quote."""

    return any(contains(c.quote, fr) for c in dossier.claims)


def _line(check: _Checker, row: Any, limit: int, *, allow: str | None = None) -> tuple[ComptoirText | None, str | None]:
    if isinstance(row, dict):
        row = {**row, "fr": headline_text(row.get("fr") or "")}
    return rubriques.text(check, row, limit, allow=allow)


def _headline(row: Any, role: str, wrong: str, dossier: EditorialDossier, check: _Checker
              ) -> tuple[TitreHeadline | None, list[str]]:
    tag = f"titre:{role}"
    claims = dossier.claims_by_id()
    claim = claims.get(str(row.get("claim_id") or "").strip())
    if claim is None:
        return None, [f"{tag}:claim_unknown"]
    claims_text = _claims_text(dossier)
    refusals: list[str] = []
    texts: dict[str, ComptoirText] = {}
    for band, limit in HEADLINE_MAX_WORDS.items():
        raw_fr = row.get(band).get("fr") if isinstance(row.get(band), dict) else row.get(band)
        if role != "exaggerated" and contains(str(raw_fr or ""), wrong):
            refusals.append(f"{tag}:{band}:says_too_much")
            continue
        line, why = _line(check, row.get(band), limit, allow=wrong if role == "exaggerated" else None)
        if line is not None:
            if outlet_words(line.fr, dossier):
                why = "outlet_words"
            elif role == "exaggerated":
                if not contains(line.fr, wrong):
                    why = "wrong_not_in_headline"
                elif not any(grounded(line.fr, c.fr) for c in dossier.claims):
                    why = "ungrounded"
            else:
                if not grounded(line.fr, claim.fr):
                    why = "ungrounded"
                elif numbers(line.fr) - numbers(claims_text):
                    why = "number_not_in_claims"
                elif role == "honest" and new_names(line.fr, claims_text):
                    why = "name_not_in_claims"
        if why:
            refusals.append(f"{tag}:{band}:{why}")
            continue
        texts[band] = line  # type: ignore[assignment]
    why_line = None
    if role != "honest":
        why_line, why = rubriques.text(check, row.get("why"), WHY_MAX_WORDS, allow=wrong)
        if why_line is None:
            refusals.append(f"{tag}:why:{why}")
    if refusals or len(texts) < 3:
        return None, refusals or [f"{tag}:incomplete"]
    return TitreHeadline(role=role, claim_id=claim.id, why=why_line, **texts), []  # type: ignore[arg-type]


def _build(raw: Any, wrong: str, dossier: EditorialDossier, check: _Checker) -> tuple[TitreBuild | None, list[str], list[str]]:
    """A1 tiles and the A2 frame: ``(build, refusals, problems)``."""

    if not isinstance(raw, dict):
        return None, ["titre:build:missing"], []
    claims_text = _claims_text(dossier)
    refusals: list[str] = []
    problems: list[str] = []

    def tile(row: Any, limit: int, tag: str) -> ComptoirText | None:
        if isinstance(row, dict):
            row = {**row, "fr": headline_text(row.get("fr") or "")}
            if contains(row["fr"], wrong):
                refusals.append(f"titre:build:{tag}:says_too_much")
                return None
        line, why = rubriques.text(check, row, limit)
        if line is not None:
            if address_problem(line.fr, ROMY_ID) or "!" in line.fr or "?" in line.fr:
                why = "vocative"
            elif numbers(line.fr) - numbers(claims_text):
                why = "number_not_in_claims"
        if why:
            refusals.append(f"titre:build:{tag}:{why}")
            return None
        return line

    subjects = [tile(r, SUBJECT_MAX_WORDS, f"subject:{i}") for i, r in enumerate(list(raw.get("subjects") or [])[:3])]
    facts = [tile(r, FACT_MAX_WORDS, f"fact:{i}") for i, r in enumerate(list(raw.get("facts") or [])[:4])]
    for index, fact in enumerate(facts):
        if fact is not None and not any(grounded(fact.fr, c.fr) for c in dossier.claims):
            refusals.append(f"titre:build:fact:{index}:ungrounded")
    if len(subjects) < 2 or len(facts) < 2:
        refusals.append("titre:build:count")
    if refusals:
        return None, refusals, []
    frame_row = raw.get("frame")
    if isinstance(frame_row, dict):
        frame_row = {**frame_row, "fr": headline_text(frame_row.get("fr") or "").rstrip(" …")}
    if isinstance(frame_row, dict) and contains(frame_row["fr"], wrong):
        frame, why = None, "says_too_much"
    else:
        frame, why = rubriques.text(check, frame_row, FRAME_MAX_WORDS)
    if frame is None:
        problems.append(f"titre:build:frame:{why}")
        frame = subjects[0]
    return TitreBuild(subjects=subjects, facts=facts, frame=frame), [], problems  # type: ignore[arg-type]


def repair_titre(raw: Any, dossier: EditorialDossier) -> tuple[TitreDesk | None, list[str]]:
    """What the headline desk wrote, checked against ``dossier``. ``(None, ["skip"])`` for an
    unfit story; ``(None, problems)`` when it is refused; else the desk's work and what fell
    back to authored lines."""

    if not isinstance(raw, dict):
        return None, ["titre:missing"]
    if str(raw.get("fit") or "").strip().lower() == "skip":
        return None, ["skip"]
    rows = raw.get("headlines")
    if not isinstance(rows, list) or len(rows) != 3 or not all(isinstance(r, dict) for r in rows):
        return None, ["titre:headlines:count"]
    if sorted(str(r.get("role") or "") for r in rows) != sorted(TITRE_ROLES):
        return None, ["titre:headlines:roles"]
    check = _Checker(dossier)
    stretch = str(raw.get("stretch") or "").strip().lower()
    wrong = _value(raw.get("wrong_fr"))
    if not 1 <= word_count(wrong) <= WRONG_MAX_WORDS:
        return None, ["titre:wrong_length"]
    if contains(check.story, wrong) or any(contains(c.fr, wrong) for c in dossier.claims):
        return None, ["titre:wrong_in_claims"]
    why = stretch_problem(stretch, wrong)
    if why:
        return None, [f"titre:{why}"]
    headlines: list[TitreHeadline] = []
    refusals: list[str] = []
    for row in rows:
        headline, refused = _headline(row, str(row.get("role")), wrong, dossier, check)
        refusals += refused
        if headline is not None:
            headlines.append(headline)
    build, refused, problems = _build(raw.get("build"), wrong, dossier, check)
    refusals += refused
    if refusals:
        return None, [*refusals, *problems]
    for band in HEADLINE_MAX_WORDS:
        if len({ci(h.for_band(band).fr) for h in headlines}) < 3:
            return None, ["titre:headlines:duplicate", *problems]
    if too_wide(wrong, next(h for h in headlines if h.role == "honest")):
        return None, ["titre:wrong_too_wide", *problems]
    phrase: dict[str, ComptoirText] = {}
    raw_phrase = raw.get("phrase") if isinstance(raw.get("phrase"), dict) else {}
    for band in ("a1", "a2", "b1", "b2"):
        line, why = check.text(raw_phrase.get(band), PHRASE_MAX_WORDS)
        if line is None:
            problems.append(f"titre:phrase:{band}:{why}")
        phrase[band] = line or getattr(AUTHORED_PHRASE, band)
    order = {role: i for i, role in enumerate(TITRE_ROLES)}
    headlines.sort(key=lambda h: order[h.role])
    return TitreDesk(headlines=headlines, stretch=stretch, wrong_fr=wrong, build=build,  # type: ignore[arg-type]
                     phrase=ComptoirPhrase(**phrase)), problems


def as_desk_answer(desk: TitreDesk) -> dict[str, Any]:
    """``desk`` in the desk's answer shape, so :func:`audit` runs the same checks."""

    data = desk.model_dump(mode="json")
    return {"fit": "titles", "stretch": data["stretch"], "wrong_fr": data["wrong_fr"], "build": data["build"],
            "phrase": data["phrase"],
            "headlines": [{k: v for k, v in row.items() if v is not None} for row in data["headlines"]]}


def audit(desk: TitreDesk, dossier: EditorialDossier) -> list[str]:
    """Every check :func:`repair_titre` would make on ``desk``: ``[]`` when nothing would change."""

    repaired, problems = repair_titre(as_desk_answer(desk), dossier)
    return problems if repaired is not None else problems or ["titre:refused"]


# ---------------------------------------------------------------------------
# The desk
# ---------------------------------------------------------------------------


def write_titre(dossier: EditorialDossier, provider: Any = None) -> tuple[TitreDesk | None, list[str]]:
    """The headline desk: one JSON call (a second with the problems), checked by :func:`repair_titre`."""

    return rubriques.ask_desk(dossier, provider, key="titre", instructions=TITRE_DESK_INSTRUCTIONS,
                              repair=repair_titre, prompt_version=TITRE_PROMPT_VERSION)


def _evergreen(dossier_id: str) -> TitreDesk | None:
    from app.services.revue.evergreen import evergreen_titre  # noqa: PLC0415

    return evergreen_titre(dossier_id)


def ensure_titre(db: Any, period: str, *, provider: Any = None) -> list[str]:
    """Each morning, once per kiosk row (``rubriques.ensure_desk``)."""

    return rubriques.ensure_desk(db, period, key="titre", write=write_titre, evergreen=_evergreen, provider=provider)


def titre_of(dossier: EditorialDossier) -> TitreDesk | None:
    """The headlines a session on ``dossier`` plays: the dossier's own, else the evergreen's."""

    return rubriques.material_of(dossier, "titre", _evergreen)


__all__ = [
    "ALWAYS_WORDS",
    "CERTAINTY_WORDS",
    "TITRE_DESK_INSTRUCTIONS",
    "TITRE_PROMPT_VERSION",
    "audit",
    "ensure_titre",
    "headline_text",
    "repair_titre",
    "stretch_problem",
    "titre_of",
    "write_titre",
]
