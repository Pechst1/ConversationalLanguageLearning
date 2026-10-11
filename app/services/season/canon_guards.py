"""WP-149 «Rien de refusé à l'écran» — what a generated page must get right.

The WP-136 read served nine pages the story critic had refused twice. Most were
refused for *storytelling* (no visible change, the open obstacle off the page),
which stays a soft judgement: the page is served and the override logged. Two
named a *correctness* defect the learner would notice — Gus saying «tu» before
T3, Margaux holding the letter the learner gave Marin. This module holds:

* the two deterministic checks those defects call for (``flag_holder_hits``; the
  register check lives next to its sibling ``_check_season_register`` in
  ``living_story``), and
* the classifier that sorts a critic refusal into correctness or storytelling, so
  a correctness refusal is never served (``living_story._approved``).

Pure functions: no model call, no database.
"""

from __future__ import annotations

import re
from typing import Any

#: The two classes of a story-critic refusal (WP-149 §B.2).
CORRECTNESS = "correctness"
STORYTELLING = "storytelling"

# A critic issue that names a correctness defect: the register canon (a quoted
# «tu»/«vous», tutoiement, «register»), a contradiction of the flags or of what the
# learner chose, knowledge a character was never given, a spoiler. The French hints
# use «tu» and «vous» as ordinary words («si tu keep the airline beat»), so only a
# *quoted* pronoun or a register word counts. Storytelling words («change», «obstacle»,
# «tournant», «révèle une information») never match.
_CORRECTNESS_ISSUE = re.compile(
    r"['‘’«\"]\s?(?:tu|vous)\s?['‘’»\"]"
    r"|\b(?:tutoi\w*|vouvoi\w*|register|registre)\b"
    r"|\bcontradict\w*|\bcontredi\w*|\bincoh[ée]ren\w*"
    r"|\bflags?\b"
    r"|\btrusted\b|\bconfi[ée]e?s?\s+(?:à|a)\b"
    r"|\bnever (?:told|knew|saw|given)\b|\bn['’](?:a|ont|avait) jamais (?:su|vu|appris)\b"
    r"|\bspoil\w*|\bmust_not\b|\bdivulg\w*"
    r"|\bdeparted\b|\bn['’]est plus là\b",
    re.IGNORECASE,
)


def issue_class(issue: str) -> str:
    """``correctness`` or ``storytelling`` for one critic issue sentence."""

    return CORRECTNESS if _CORRECTNESS_ISSUE.search(str(issue or "")) else STORYTELLING


def review_class(review: Any | None, issues: list[str] | None = None) -> str:
    """The class of a refusal: correctness when the rubric says the page contradicts
    the choices or spoils a tentpole, or when any issue names a correctness defect;
    storytelling otherwise (no change, the obstacle off the page, weak stakes).

    ``review`` is a :class:`~app.services.season.director.StoryReview` or ``None``
    (the offline replay has only the recorded issue sentences)."""

    if review is not None and (
        getattr(review, "spoils_next_tentpole", False) or not getattr(review, "honours_choices", True)
    ):
        return CORRECTNESS
    texts = list(issues if issues is not None else getattr(review, "issues", None) or [])
    return CORRECTNESS if any(issue_class(text) == CORRECTNESS for text in texts) else STORYTELLING


# ---------------------------------------------------------------------------
# flag_contradiction: who holds what, against the flags
# ---------------------------------------------------------------------------

#: An object whose holder a flag decides. ``holders`` maps a flag value to the cast
#: member it names (the value is that member's first name or nickname, lower case);
#: values in ``skip`` say nothing about who has it (Gus read the letter aloud: the
#: whole café knows), and ``nobody`` means the learner kept it — no cast member
#: holds it. ``gaps``: the generated days that read the flag (season.json
#: ``read_where``); after them the object is no longer the one the flag is about.
HOLDER_RULES: tuple[dict[str, Any], ...] = (
    {
        "flag": "s1.letter_trusted_to",
        "object": r"lettre|enveloppe|letter|envelope",
        "what": "the notary's letter",
        "gaps": ("g1",),
        "skip": ("gus",),
    },
)

_HOLD_VERBS = (
    r"tient|tenait|garde|gardait|range|glisse|lit|relit|lisait|ouvre|déplie|deplie|cache|"
    r"pose|sort|serre|brandit|agite|montre|plie|froisse|rend|a reçu|a lu|"
    r"holds?|holding|held|has|keeps?|kept|reads?|reading|opens?|opening|unfolds?|hides?|"
    r"pockets?|tucks?|slides?|clutch(?:es)?|clutching|waves?|shows?|folds?"
)
#: Determiners that make the object THE letter of the flag, not «une lettre».
_DEFINITE = r"la|sa|ta|votre|cette|l['’]|the|her|his|your|this"
_ELSEWHERE = re.compile(r"\bd['’]\s?odile\b|\bodile['’]s\b|\bde l['’]agence\b", re.IGNORECASE)
_SENTENCES = re.compile(r"(?<=[.!?;…])\s+")


def cast_aliases(cast: list[Any]) -> dict[str, list[str]]:
    """``{member id: [names a page calls them by]}``: the nickname in «», else the
    first name (the last word after a title: «M. Marchand» → Marchand)."""

    titles = {"m.", "mme", "maître", "maitre", "le", "la", "l'", "un", "une", "monsieur", "madame"}
    out: dict[str, list[str]] = {}
    for member in cast:
        name = str(getattr(member, "name", None) or (member.get("name") if isinstance(member, dict) else "") or "")
        member_id = str(getattr(member, "id", None) or (member.get("id") if isinstance(member, dict) else "") or "")
        if not name or not member_id:
            continue
        nick = re.search(r"«\s*([^»]+?)\s*»", name)
        words = [word for word in re.findall(r"[^\W\d_][\w'’-]*\.?", name) if word.casefold() not in titles]
        aliases = [nick.group(1)] if nick else []
        if words:
            aliases.append(words[0])
        out[member_id] = list(dict.fromkeys(alias for alias in aliases if alias))
    return out


def _holds(sentence: str, alias: str, obj: str) -> bool:
    name = re.escape(alias)
    active = re.compile(
        rf"\b{name}\b[^.!?;]{{0,40}}?\b(?:{_HOLD_VERBS})\b[^.!?;]{{0,24}}?"
        rf"(?:\b(?:{_DEFINITE})\s?)(?:{obj})\b",
        re.IGNORECASE,
    )
    passive = re.compile(
        rf"(?:\b(?:{_DEFINITE})\s?)(?:{obj})\b[^.!?;]{{0,40}}?"
        rf"(?:\b(?:dans|entre) les mains de|\bchez|\bin) {name}\b",
        re.IGNORECASE,
    )
    possessive = re.compile(rf"\b{name}['’]s hands?\b[^.!?;]{{0,24}}\b(?:{obj})\b", re.IGNORECASE)
    return bool(active.search(sentence) or passive.search(sentence) or possessive.search(sentence))


def flag_holder_hits(
    texts: list[str],
    *,
    flags: dict[str, Any],
    gap_id: str,
    cast: list[Any],
    learner_letter_day: bool = False,
) -> list[dict[str, str]]:
    """Every sentence in ``texts`` that puts a flagged object in the wrong hands:
    ``[{flag, value, holder, allowed, what, sentence}]``. Empty when the flag is unset,
    when it says nothing about a holder, or off the gaps that read it.

    ``learner_letter_day``: a letter-shaped day, where «ta lettre» is the one the
    learner is writing today, not the flag's."""

    aliases = cast_aliases(cast)
    hits: list[dict[str, str]] = []
    for rule in HOLDER_RULES:
        if gap_id not in rule["gaps"]:
            continue
        value = str(flags.get(rule["flag"]) or "").strip().casefold()
        if not value or value in rule["skip"]:
            continue
        allowed = None
        if value != "nobody":
            allowed = next(
                (member_id for member_id, names in aliases.items() if value in {n.casefold() for n in names}),
                None,
            )
            if allowed is None:
                continue
        for text in texts:
            for sentence in _SENTENCES.split(str(text or "")):
                if not sentence.strip() or _ELSEWHERE.search(sentence):
                    continue
                if learner_letter_day and re.search(r"\b(?:ta|votre|your)\s+(?:lettre|letter)\b", sentence, re.I):
                    continue
                for member_id, names in aliases.items():
                    if member_id == allowed:
                        continue
                    if any(_holds(sentence, name, rule["object"]) for name in names):
                        hits.append(
                            {
                                "flag": rule["flag"],
                                "value": value,
                                "holder": names[0],
                                "allowed": (aliases.get(allowed) or [allowed])[0] if allowed else "",
                                "what": rule["what"],
                                "sentence": sentence.strip()[:160],
                            }
                        )
                        break
    return hits


def flag_holder_hint(hits: list[dict[str, str]]) -> str:
    """The retry hint for a page that puts a flagged object in the wrong hands."""

    hit = hits[0]
    if hit["allowed"]:
        owner = (
            f"The learner trusted {hit['what']} to {hit['allowed']} ({hit['flag']}): only "
            f"{hit['allowed']} has seen it."
        )
    else:
        owner = f"The learner kept {hit['what']} and showed it to nobody ({hit['flag']})."
    return (
        f"«{hit['sentence']}» puts {hit['what']} in {hit['holder']}'s hands. {owner} "
        f"Rewrite the page so {hit['holder']} does not hold, read or keep it; they may "
        "only know what the learner's choices told them."
    )
