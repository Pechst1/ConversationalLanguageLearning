"""The checks on meaning (WP-119 §4.2), phase 0.

Each check answers one question about one generated thing and returns one
:class:`CheckResult` per thing it looked at; a failure names a ``reason`` code (logged
once at debug level as ``revue_check_failed``) the way ``gaps.json`` refusals do. What
a failure leads to (drop the claim, retype it, regenerate the line, skip the exercise,
drop the field, leave the turn unscored) is the caller's business, per the §4.2 table.

A passing result has ``reason=None`` (except ``not_applicable``, see
:func:`check_distinguishable`); every result's ``detail`` names what it looked at
(``claim_id``, ``line_index``, ``option_id``, ``field``…). :func:`failures` and
:func:`passed` read a result list.

Phase 0 is deterministic. Where §4.2 asks a model question (is the ``fr`` entailed by
its quote; is a fact a report or an opinion) the check uses a lexical heuristic, and
the critic judge replaces it in phase 1:

* **content words** (:func:`_content_words`): tokens of ``fold(text).casefold()``
  (accents kept), at least four letters, not a French function word, a final
  plural ``s``/``x`` dropped. Two texts *share* meaning when they share one.

See ``docs/implementation/atelier-v2/WP-119-LA-REVUE-DE-ROMY.md``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.services.revue.dossier import fold, week_bounds
from app.services.revue.policy import OUTFITS

if TYPE_CHECKING:
    from app.services.revue.dossier import Claim, EditorialDossier
    from app.services.revue.session import SessionPlan
    from app.services.season.format import Season

#: Check names, as they appear in :attr:`CheckResult.check`.
CHECK_NAMES: tuple[str, ...] = (
    "anchor",
    "attribution",
    "temporal",
    "knowledge",
    "distinguishable",
    "render",
    "credit",
)


@dataclass(frozen=True)
class CheckResult:
    """One check's verdict on one thing (a claim, a line, an exercise, a stage field)."""

    ok: bool
    check: str
    reason: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

#: A dossier with fewer anchored claims than this is dropped (§4.2 Anchor).
MIN_ANCHORED_CLAIMS = 2
#: A claim's source may be at most this many days older than the week's Sunday.
MAX_SOURCE_AGE_DAYS = 21
#: The learner on stage (``plan_for`` casts ``"user"``); never a ``world.json`` id.
LEARNER_CAST_IDS: frozenset[str] = frozenset({"user"})
CAMILLE_ID = "camille_marchand"
EVIDENCE_OUTCOMES: frozenset[str] = frozenset({"correct", "incorrect", "unscored"})
EVIDENCE_REQUIRED_FIELDS: tuple[str, ...] = ("rubric_version", "capability_id", "outcome")

#: French function words of four letters or more: never evidence that two texts agree.
_STOPWORDS: frozenset[str] = frozenset(
    """
    alors après aussi autre autres avant avec avoir avait avaient bien cela celle celles
    celui ceci ceux cette chez comme comment dans depuis donc dont elle elles encore entre
    était étaient étant être fait faire font leur leurs mais même mêmes moins notre nous
    nos peut peuvent plus pour pourquoi quand quel quelle quelles quels sans selon sera
    seront sont sous suis tous tout toute toutes très vers votre vous ainsi aucun aucune
    lors puis sinon tant tandis voici voilà parce
    """.split()
)
_WORD = re.compile(r"\w+", re.UNICODE)

#: Words of judgement a ``fact`` must not carry (§4.2 Attribution), matched on
#: ``fold(fr).casefold()`` with word boundaries. The critic judge replaces it in phase 1.
OPINION_LEXICON: tuple[str, ...] = (
    "scandaleux",
    "scandaleuse",
    "scandaleusement",
    "formidable",
    "formidables",
    "inacceptable",
    "inacceptables",
    "inadmissible",
    "heureusement",
    "malheureusement",
    "hélas",
    "enfin",
    "évidemment",
    "bien sûr",
    "honteux",
    "honteuse",
    "honteusement",
    "catastrophique",
    "catastrophiques",
    "magnifique",
    "magnifiques",
    "merveilleux",
    "merveilleuse",
    "terrible",
    "terribles",
    "absurde",
    "ridicule",
    "lamentable",
    "admirable",
    "il faut",
    "il faudrait",
    "on doit",
    "devrait",
    "devraient",
)
_OPINION = re.compile(
    r"(?<!\w)("
    + "|".join(re.escape(word) for word in sorted(OPINION_LEXICON, key=len, reverse=True))
    + r")(?!\w)"
)

#: Phrases a session cannot place in time (§4.2 Temporal), longest first.
RELATIVE_DATE_PHRASES: tuple[str, ...] = (
    "la semaine prochaine",
    "la semaine dernière",
    "cette semaine",
    "après-demain",
    "avant-hier",
    "aujourd'hui",
    "ce matin",
    "ce soir",
    "demain",
    "hier",
)
WEEKDAYS: tuple[str, ...] = (
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
)
_RELATIVE = re.compile(
    r"(?<![\w-])(" + "|".join(re.escape(p) for p in RELATIVE_DATE_PHRASES) + r")(?![\w-])"
)
#: A weekday not followed by a day number («jeudi», «jeudi soir»; «jeudi 15 octobre» is absolute).
_WEEKDAY = re.compile(r"(?<!\w)(" + "|".join(WEEKDAYS) + r")(?!\w)(?!\s+(?:\d|1er\b|premier\b))")

#: Formats that pick exactly one option against an answer (any other format with
#: options is read the same way).
PICK_FORMATS: frozenset[str] = frozenset({"choice", "listen_tap", "who_said", "classify"})
#: Formats whose meaning is over vocabulary or a sentence's order, not over claims.
NOT_APPLICABLE_FORMATS: frozenset[str] = frozenset(
    {"match_pairs", "tiles", "word_bank", "unscramble", "dictation", "transform"}
)


def _result(check: str, *, ok: bool, reason: str | None = None, **detail: Any) -> CheckResult:
    result = CheckResult(ok=ok, check=check, reason=reason, detail=detail)
    if not ok:
        logger.bind(check=check, reason=reason, detail=detail).debug(
            "revue_check_failed {} {} {}", check, reason, detail
        )
    return result


def _ok(check: str, **detail: Any) -> CheckResult:
    return _result(check, ok=True, **detail)


def _fail(check: str, reason: str, **detail: Any) -> CheckResult:
    return _result(check, ok=False, reason=reason, **detail)


def _norm(text: str | None) -> str:
    return fold(text).casefold()


def _stem(token: str) -> str:
    return token[:-1] if len(token) > 4 and token[-1] in "sx" else token


def _content_words(text: str | None) -> set[str]:
    """The heuristic's content words: see the module docstring."""

    words: set[str] = set()
    for token in _WORD.findall(_norm(text)):
        if len(token) < 4 or token.isdigit() or token in _STOPWORDS:
            continue
        words.add(_stem(token))
    return words


def _shares_content_word(text: str | None, others: Iterable[str | None]) -> bool:
    mine = _content_words(text)
    return bool(mine) and any(mine & _content_words(other) for other in others)


def failures(results: Iterable[CheckResult]) -> list[CheckResult]:
    """The failed results, in order."""

    return [result for result in results if not result.ok]


def passed(results: Iterable[CheckResult]) -> bool:
    """True when no result failed (an empty list passes)."""

    return not failures(results)


# ---------------------------------------------------------------------------
# Dossier-level checks
# ---------------------------------------------------------------------------


def check_anchor(dossier: EditorialDossier, source_texts: dict[str, str]) -> list[CheckResult]:
    """Anchor: is every ``quote`` a verbatim substring of its source text (both ``fold``-ed),
    and is every claim's ``fr`` entailed by its quote? ``source_texts`` maps source id → full
    text. On failure: drop the claim; fewer than two claims → drop the dossier.

    Reasons, per claim: ``source_text_missing``, ``quote_not_in_source``,
    ``claim_not_grounded_in_quote``; one ok result per anchored claim. Then, for the
    dossier, ``too_few_claims_anchored`` when fewer than two claims passed.

    Entailment is lexical in phase 0: the claim's ``fr`` must share a content word with
    its quote. The critic judge (yes/no) replaces it in phase 1.
    """

    results: list[CheckResult] = []
    anchored = 0
    for claim in dossier.claims:
        source = source_texts.get(claim.source_id)
        if source is None or not fold(source):
            results.append(
                _fail("anchor", "source_text_missing", claim_id=claim.id, source_id=claim.source_id)
            )
        elif fold(claim.quote) not in fold(source):
            results.append(
                _fail("anchor", "quote_not_in_source", claim_id=claim.id, source_id=claim.source_id)
            )
        elif not _shares_content_word(claim.quote, [claim.fr]):
            results.append(_fail("anchor", "claim_not_grounded_in_quote", claim_id=claim.id))
        else:
            anchored += 1
            results.append(_ok("anchor", claim_id=claim.id))
    if anchored < MIN_ANCHORED_CLAIMS:
        results.append(
            _fail(
                "anchor",
                "too_few_claims_anchored",
                dossier_id=dossier.id,
                anchored=anchored,
                required=MIN_ANCHORED_CLAIMS,
            )
        )
    return results


def check_attribution(
    dossier: EditorialDossier, judge: Callable[[str], bool] | None = None
) -> list[CheckResult]:
    """Attribution: does every interpretation and forecast carry ``attributed_to``, and does
    no ``fact`` read as an opinion? ``judge(fr) -> True`` when the sentence reads as an
    opinion, not a report (critic rubric); ``None`` uses the deterministic rules only
    (:data:`OPINION_LEXICON`, whole words on ``fold(fr).casefold()``). On failure: retype
    as ``interpretation`` with attribution, or drop.

    Reasons: ``missing_attribution`` (the model already refuses it; this catches a
    hand-edited JSON), ``fact_reads_as_opinion`` with ``detail["retype_as"] =
    "interpretation"``. One result per claim.
    """

    results: list[CheckResult] = []
    for claim in dossier.claims:
        if claim.kind in {"interpretation", "forecast"}:
            if not (claim.attributed_to or "").strip():
                results.append(
                    _fail("attribution", "missing_attribution", claim_id=claim.id, kind=claim.kind)
                )
            else:
                results.append(_ok("attribution", claim_id=claim.id))
            continue
        if judge is not None:
            if judge(claim.fr):
                results.append(
                    _fail(
                        "attribution",
                        "fact_reads_as_opinion",
                        claim_id=claim.id,
                        retype_as="interpretation",
                        by="judge",
                    )
                )
                continue
        else:
            match = _OPINION.search(_norm(claim.fr))
            if match:
                results.append(
                    _fail(
                        "attribution",
                        "fact_reads_as_opinion",
                        claim_id=claim.id,
                        retype_as="interpretation",
                        word=match.group(1),
                    )
                )
                continue
        results.append(_ok("attribution", claim_id=claim.id))
    return results


def _relative_dates(text: str, *, weekdays_allowed: bool) -> list[str]:
    folded = _norm(text)
    found = [match.group(1) for match in _RELATIVE.finditer(folded)]
    if not weekdays_allowed:
        found.extend(match.group(1) for match in _WEEKDAY.finditer(folded))
    return found


def check_temporal(dossier: EditorialDossier, week: str) -> list[CheckResult]:
    """Temporal: does ``time_scope.happening`` fit ``week`` (ISO, ``"2026-W40"``), is no
    ``fr`` phrased relative to a date the session cannot know ("jeudi", "demain") unless
    ``time_scope`` pins it, and is ``relevant_until`` ≥ the week's Sunday? On failure:
    rewrite with absolute dates; expired → drop.

    Reasons: ``not_this_week`` (happening does not overlap Monday..Sunday), ``expired``,
    ``relative_date`` (per text: ``summary`` or a claim; a weekday followed by a day
    number is absolute, and weekdays are allowed when ``happening`` is a single day),
    ``stale_source`` / ``future_source`` (a claim published more than 21 days before
    the Sunday, or after it; skipped for evergreen dossiers).
    """

    monday, sunday = week_bounds(week)
    scope = dossier.time_scope
    results: list[CheckResult] = []

    if scope.start <= sunday and scope.end >= monday:
        results.append(_ok("temporal", field="happening"))
    else:
        results.append(
            _fail(
                "temporal", "not_this_week", field="happening", happening=scope.happening, week=week
            )
        )

    if scope.relevant_until >= sunday:
        results.append(_ok("temporal", field="relevant_until"))
    else:
        results.append(
            _fail(
                "temporal",
                "expired",
                field="relevant_until",
                relevant_until=scope.relevant_until.isoformat(),
                sunday=sunday.isoformat(),
            )
        )

    weekdays_allowed = scope.start == scope.end
    texts: list[tuple[dict[str, Any], str]] = [({"field": "summary_fr"}, dossier.summary_fr)]
    texts.extend(({"claim_id": claim.id}, claim.fr) for claim in dossier.claims)
    for where, text in texts:
        words = _relative_dates(text, weekdays_allowed=weekdays_allowed)
        if words:
            results.append(_fail("temporal", "relative_date", **where, word=words[0], words=words))
        else:
            results.append(_ok("temporal", **where))

    if not dossier.evergreen:
        oldest = sunday - timedelta(days=MAX_SOURCE_AGE_DAYS)
        for claim in dossier.claims:
            published = claim.published_at.isoformat()
            if claim.published_at > sunday:
                results.append(
                    _fail("temporal", "future_source", claim_id=claim.id, published_at=published)
                )
            elif claim.published_at < oldest:
                results.append(
                    _fail("temporal", "stale_source", claim_id=claim.id, published_at=published)
                )
            else:
                results.append(_ok("temporal", claim_id=claim.id, field="published_at"))
    return results


# ---------------------------------------------------------------------------
# Plan and encounter checks
# ---------------------------------------------------------------------------


def _global_hits(season: Season, line: str, flags: dict) -> list[tuple[str, str]]:
    """``director.forbidden_hits`` for the season's global list alone (no gap at this id)."""

    from app.services.season.flags import holds

    hits: list[tuple[str, str]] = []
    for row in season.global_must_not:
        if row.unless and holds(row.unless, flags):
            continue
        for pattern in row.patterns:
            match = re.compile(pattern, re.IGNORECASE).search(str(line or ""))
            if match:
                hits.append((row.id, match.group(0)))
                break
    return hits


def check_knowledge(
    lines: list[str], *, season: Season, gap_id: str, flags: dict
) -> list[CheckResult]:
    """Knowledge: does the speaker know what they say? Runs the season's reveal guard
    (``director.forbidden_hits`` / ``_must_not``) for the learner's current position on
    every cast line. On failure: regenerate once with a tighter context, then the authored
    default line.

    One result per hit (``forbidden_reveal``, ``detail`` = ``line_index``,
    ``must_not_id``, ``match``) and one ok result per clean line. When ``gap_id`` is not
    a gap of the season (a tentpole, a stale id), the season's global list still applies
    and ``detail["gap_known"]`` is False.
    """

    from app.services.season.director import forbidden_hits

    gap_known = gap_id in season.gaps
    results: list[CheckResult] = []
    for index, line in enumerate(lines):
        if gap_known:
            hits = forbidden_hits(season, gap_id, [line], flags=flags)
        else:
            hits = _global_hits(season, line, flags)
        if not hits:
            results.append(_ok("knowledge", line_index=index, gap_id=gap_id, gap_known=gap_known))
            continue
        for must_not_id, matched in hits:
            results.append(
                _fail(
                    "knowledge",
                    "forbidden_reveal",
                    line_index=index,
                    gap_id=gap_id,
                    gap_known=gap_known,
                    must_not_id=must_not_id,
                    match=matched,
                )
            )
    return results


def _options(exercise: dict) -> list[tuple[str, str]]:
    """``(id, text)`` for each option; a bare string is its own id and text. Real journey
    options are ``{"id", "text_fr"}``; ``text`` and ``label`` are read too."""

    rows: list[tuple[str, str]] = []
    for index, option in enumerate(exercise.get("options") or []):
        if isinstance(option, dict):
            text = str(option.get("text") or option.get("text_fr") or option.get("label") or "")
            rows.append((str(option.get("id") or f"#{index}"), text))
        else:
            rows.append((str(option), str(option)))
    return rows


def check_distinguishable(exercise: dict, claims_shown: list[Claim]) -> list[CheckResult]:
    """Distinguishable: for an exercise with options, is exactly one option supported by the
    claims shown and is every distractor contradicted by at least one of them? For a
    ``SHORT_ANSWER``, does the private rubric name the claims a correct answer must reflect?
    On failure: regenerate, then skip the exercise.

    The exercise dict: ``format`` (or the journey's ``task_type``), ``options`` (``{id,
    text}`` / ``{id, text_fr}`` dicts or strings), ``answer`` (or ``correct_option_id``:
    an option id or its text), ``contradicted_by`` ``{distractor id: claim id}`` and
    optionally ``supported_by`` (a claim id) for the answer; a short answer carries
    ``rubric.claim_ids``.

    Reasons: ``no_single_answer``; ``answer_unsupported`` (the answer shares no content
    word with a shown claim's ``fr`` and names no shown ``supported_by`` claim — options
    in the learner's language, as on a ``listen_tap``, need ``supported_by``);
    ``distractor_not_contradicted`` (one per distractor with no mapping, or a mapping to
    a claim not shown); ``rubric_without_claims``. Formats over vocabulary or word order
    (:data:`NOT_APPLICABLE_FORMATS`) and option-less exercises get one ok
    ``not_applicable`` result. One ok result when everything holds.
    """

    fmt = str(exercise.get("format") or exercise.get("task_type") or "").lower()
    shown = {claim.id: claim for claim in claims_shown}

    if fmt == "short_answer":
        rubric = exercise.get("rubric") if isinstance(exercise.get("rubric"), dict) else {}
        claim_ids = [str(claim_id) for claim_id in (rubric.get("claim_ids") or [])]
        unknown = [claim_id for claim_id in claim_ids if claim_id not in shown]
        if not claim_ids or unknown:
            return [
                _fail(
                    "distinguishable",
                    "rubric_without_claims",
                    format=fmt,
                    claim_ids=claim_ids,
                    unknown=unknown,
                )
            ]
        return [_ok("distinguishable", format=fmt, claim_ids=claim_ids)]

    options = _options(exercise)
    if fmt in NOT_APPLICABLE_FORMATS or not options:
        return [_result("distinguishable", ok=True, reason="not_applicable", format=fmt)]

    answer = exercise.get("answer", exercise.get("correct_option_id"))
    answer_norm = _norm(str(answer)) if answer is not None else ""
    correct = [
        (option_id, text)
        for option_id, text in options
        if answer is not None
        and (option_id == str(answer) or (text and _norm(text) == answer_norm))
    ]
    if len(correct) != 1:
        return [
            _fail(
                "distinguishable",
                "no_single_answer",
                format=fmt,
                answer=answer,
                matching_option_ids=[option_id for option_id, _ in correct],
            )
        ]

    results: list[CheckResult] = []
    answer_id, answer_text = correct[0]
    supported_by = exercise.get("supported_by")
    if not (
        _shares_content_word(answer_text, [claim.fr for claim in claims_shown])
        or (supported_by is not None and str(supported_by) in shown)
    ):
        results.append(
            _fail("distinguishable", "answer_unsupported", format=fmt, option_id=answer_id)
        )

    mapping = (
        exercise.get("contradicted_by") if isinstance(exercise.get("contradicted_by"), dict) else {}
    )
    for option_id, _text in options:
        if option_id == answer_id:
            continue
        claim_id = mapping.get(option_id)
        if claim_id is None or str(claim_id) not in shown:
            results.append(
                _fail(
                    "distinguishable",
                    "distractor_not_contradicted",
                    format=fmt,
                    option_id=option_id,
                    claim_id=claim_id,
                )
            )
    if not results:
        results.append(_ok("distinguishable", format=fmt, option_id=answer_id))
    return results


def check_render(
    plan: SessionPlan,
    *,
    known_places: set[str],
    props: set[str],
    cast_ids: set[str],
    camille_chosen: bool,
) -> list[CheckResult]:
    """Render: is ``dress`` in the catalogue, ``place_id`` registered or paintable, every
    ``hold`` an authored prop, every cast id real, and Camille's look chosen if she is on
    stage? On failure: drop the unknown field; the rig renders what it knows.

    Reasons: ``unknown_outfit``, ``unknown_place`` (neither in ``known_places`` nor
    painted: ``plate_url`` unset), ``unknown_prop``, ``unknown_cast`` (cast or guest;
    the learner's ``"user"`` is always known), ``camille_look_not_chosen``. One ok
    result when all pass. Plate briefs are not on the plan: ``stage.py`` checks them with
    ``policy.plate_forbidden_hits``.
    """

    stage = plan.stage
    known_cast = set(cast_ids) | LEARNER_CAST_IDS
    results: list[CheckResult] = []
    if stage.dress not in OUTFITS:
        results.append(_fail("render", "unknown_outfit", field="dress", value=stage.dress))
    if stage.place_id not in known_places and not stage.plate_url:
        results.append(_fail("render", "unknown_place", field="place_id", value=stage.place_id))
    for member in stage.cast:
        if member.id not in known_cast:
            results.append(_fail("render", "unknown_cast", field="cast", value=member.id))
        if member.hold is not None and member.hold not in props:
            results.append(
                _fail("render", "unknown_prop", field="hold", cast_id=member.id, value=member.hold)
            )
    for guest in stage.guests_available:
        if guest.id not in known_cast:
            results.append(
                _fail("render", "unknown_cast", field="guests_available", value=guest.id)
            )
    on_stage = {member.id for member in stage.cast} | {guest.id for guest in stage.guests_available}
    if CAMILLE_ID in on_stage and not camille_chosen:
        results.append(_fail("render", "camille_look_not_chosen", field="cast", value=CAMILLE_ID))
    return results or [_ok("render", place_id=stage.place_id)]


def check_credit(evidence_write: dict) -> list[CheckResult]:
    """Credit: is the evidence write routed through the existing evidence policy with a
    rubric version? Unknown capability → unknown, never mastery. On failure: the turn is
    unscored and the conversation continues.

    Reasons: ``evidence_missing_fields`` (``rubric_version``, ``capability_id`` or
    ``outcome`` absent or empty; ``detail["missing"]``), ``invalid_outcome`` (not one of
    correct / incorrect / unscored), ``mastery_claimed_for_unknown_capability``
    (``capability_known is False`` and ``outcome == "correct"``). The evidence policy
    adapter sets ``capability_known``; when it is absent the capability is not judged.
    """

    missing = [
        name for name in EVIDENCE_REQUIRED_FIELDS if not str(evidence_write.get(name) or "").strip()
    ]
    if missing:
        return [_fail("credit", "evidence_missing_fields", missing=missing)]
    outcome = str(evidence_write["outcome"])
    capability_id = str(evidence_write["capability_id"])
    if outcome not in EVIDENCE_OUTCOMES:
        return [_fail("credit", "invalid_outcome", outcome=outcome, capability_id=capability_id)]
    if evidence_write.get("capability_known") is False and outcome == "correct":
        return [
            _fail("credit", "mastery_claimed_for_unknown_capability", capability_id=capability_id)
        ]
    return [_ok("credit", capability_id=capability_id, outcome=outcome)]


def run_dossier_checks(
    dossier: EditorialDossier, *, source_texts: dict[str, str], week: str
) -> list[CheckResult]:
    """Anchor, Attribution (deterministic rules, no judge) and Temporal, concatenated."""

    return [
        *check_anchor(dossier, source_texts),
        *check_attribution(dossier),
        *check_temporal(dossier, week),
    ]
