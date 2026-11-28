"""«Le titre»: the learner's loop (WP-119 «les rubriques», owner 2026-11-20).

Five screens — read, «Trois titres», «Le piège», «À toi», the page — played from the
headlines the desk wrote (``titre.py``) and snapshotted on the session's first ``choice``
event (``mode="titre"``). As «Le fil» (``fil_loop.py``): the server owns the state, every act
is one ``titre`` event in the append-only log, the step is derived by replay
(:func:`step_of`), an act out of order is a 409 with the same view, and an act that repeats
one already recorded records nothing.

Acts, in order (``POST /revue/sessions/{id}/rubrique``):

- ``open``: the learner read the story.
- ``pick {key}``: Gus proposes three headlines (he exaggerates by character, so the learner
  cannot tell the honest one by who says it); the learner picks the honest one. A wrong pick
  shows that headline's ``why`` in the learner's language with the claim that settles it,
  never the solution; a second wrong pick resolves the step and shows it. Two tries at most.
- ``trap {words}``: the learner taps the word(s) of the exaggerated headline that say too
  much; graded deterministically against the stored ``wrong_fr`` (every tapped word inside
  it, at least one of its content words). A miss says which tapped words the claims do say
  (``fine``), never the answer; the second miss shows it. Two tries at most.
- ``build {parts | text}``: the learner's own headline. A1 builds it from a subject tile and
  a fact tile (correct by construction, no model call). A2 completes the frame, B1+ write
  freely (≤ 12 words); a deterministic check first (never the words that said too much, no
  number the claims lack, length), then one model call (``provider.titre_edit``) for Romy's
  edit, kept back: the learner sees her marks on their own words and fixes them
  (``build_fix {text | value: "romy"}``) before anything prints, as in «Le fil».

The close (:func:`close`) makes no model call: «La page» (the story under the learner's
headline, signed), the dispatch, the ``titre`` artifact, the vignette, the kept words.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.schemas.revue import (
    RvClosing,
    RvComptoirMark,
    RvComptoirNote,
    RvDispatch,
    RvKept,
    RvRubriqueCast,
    RvRubriqueError,
    RvRubriqueRequest,
    RvTitreBuild,
    RvTitreOption,
    RvTitrePage,
    RvTitreThree,
    RvTitreTrap,
    RvTitreView,
    RvTitreWord,
)
from app.services.revue import comptoir, comptoir_loop, fil_loop, pourquoi, regle, voice
from app.services.revue.dossier import EditorialDossier, TitreDesk, comptoir_band
from app.services.revue.encounter import (
    Loaded,
    RevueError,
    _closing_of,
    _gloss_language_of,
    _source,
    colophon_for,
    contribution_spans,
    dateline,
    kept_words,
    meter,
    rv_claim,
    session_view,
)
from app.services.revue.fil_loop import _rng
from app.services.revue.intox_loop import _ct, _place, read_of
from app.services.revue.titre import headline_text, headline_tokens

if TYPE_CHECKING:  # pragma: no cover
    from app.services.revue.encounter import RevueEncounter

KIND = "titre"
TITRE_EDIT_PROMPT_VERSION = "titre-edit-v1"
STEPS: tuple[str, ...] = ("read", "three", "trap", "build", "page")
KEYS: tuple[str, ...] = ("a", "b", "c")
MAX_TRIES = 2
FIX_TRIES = comptoir_loop.FIX_TRIES
MIN_WORDS = 3
MAX_WORDS = 12
#: Words of a stretch that do not, alone, say too much («le» in «tout le monde»).
_TRAP_STOP = frozenset("le la les l de du des d un une a au aux en dans sur et".split())
_WORD = re.compile(r"[\w'’-]+")

ROMY_CLOSE_LINE = "Merci ! Ton titre est en une, et il dit vrai."
KICKER = "Le titre de Romy"


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class Acts:
    """The learner's acts so far, replayed from the ``titre`` events."""

    def __init__(self, state: Any) -> None:
        self.opened = False
        self.picks: list[dict[str, Any]] = []
        self.traps: list[dict[str, Any]] = []
        self.build: dict[str, Any] | None = None
        self.fixes: list[dict[str, Any]] = []
        for event in state.events:
            if event.kind != KIND:
                continue
            payload = event.payload
            act = payload.get("act")
            if act == "open":
                self.opened = True
            elif act == "pick" and not self.three_resolved:
                self.picks.append(dict(payload))
            elif act == "trap" and not self.trap_resolved:
                self.traps.append(dict(payload))
            elif act == "build" and self.build is None:
                self.build = dict(payload)
            elif act == "build_fix" and self.build is not None:
                self.fixes.append(dict(payload))

    @property
    def three_resolved(self) -> bool:
        return any(row.get("correct") for row in self.picks) or len(self.picks) >= MAX_TRIES

    @property
    def three_correct(self) -> bool:
        return any(row.get("correct") for row in self.picks)

    @property
    def trap_resolved(self) -> bool:
        return any(row.get("correct") for row in self.traps) or len(self.traps) >= MAX_TRIES

    @property
    def trap_correct(self) -> bool:
        return any(row.get("correct") for row in self.traps)

    @property
    def proof(self) -> dict[str, Any] | None:
        """Where the learner's headline stands before print (as ``fil_loop.Acts.proof``)."""

        if self.build is None:
            return None
        latest = self.fixes[-1] if self.fixes else self.build
        proof = str(latest.get("proof") or "as_written")
        texts = [str(fix.get("text_fr")) for fix in self.fixes if fix.get("text_fr")]
        draft = texts[-1] if texts else str(self.build.get("learner_fr") or "")
        target = str(latest.get("target_fr") or "")
        printed = None
        if proof in {"clean", "fixed", "corrected"}:
            printed = target or voice.french_typography(draft)
        elif proof == "as_written":
            printed = voice.french_typography(draft)
        return {"proof": proof, "draft": draft, "marks": list(latest.get("marks") or []) if proof == "marked" else [],
                "tries": len(texts), "target": target, "printed": printed}

    @property
    def settled(self) -> bool:
        proof = self.proof
        return proof is not None and proof["proof"] != "marked"

    def own_words(self) -> str:
        texts = [str((self.build or {}).get("typed_fr") or "")]
        texts += [str(fix.get("typed_fr") or "") for fix in self.fixes]
        return " ".join(text for text in texts if text)


def desk_of(loaded: Loaded) -> TitreDesk:
    desk = loaded.dossier.titre
    if desk is None:  # a titre session always snapshots its headlines; keep the view total anyway
        raise RevueError(409, "revue_not_titre")
    return desk


def band_of(loaded: Loaded) -> str:
    return str(loaded.plan.learner.band)


def step_of(acts: Acts, *, closed: bool) -> str:
    if closed:
        return "page"
    if not acts.opened:
        return "read"
    if not acts.three_resolved:
        return "three"
    if not acts.trap_resolved:
        return "trap"
    if not acts.settled:
        return "build"
    return "page"


def shown_order(seed: str) -> list[int]:
    """The headlines' indices (honest, exaggerated, off) in the order the session shows them."""

    order = [0, 1, 2]
    _rng(seed, "titre-order").shuffle(order)
    return order


def key_of(seed: str) -> dict[int, str]:
    return {index: KEYS[position] for position, index in enumerate(shown_order(seed))}


def index_of(seed: str) -> dict[str, int]:
    return {key: index for index, key in key_of(seed).items()}


def role_index(desk: TitreDesk, role: str) -> int:
    return next(i for i, h in enumerate(desk.headlines) if h.role == role)


# ---------------------------------------------------------------------------
# «Le piège»
# ---------------------------------------------------------------------------


def words_of(text: str) -> list[str]:
    return [m.group(0) for m in _WORD.finditer(text or "")]


def wrong_span(headline: str, wrong: str) -> list[int]:
    """The indices of ``headline``'s words that are ``wrong`` (case and accents folded)."""

    words = [comptoir.ci(w).replace("’", "'") for w in words_of(headline)]
    needle = [comptoir.ci(w).replace("’", "'") for w in words_of(wrong)]
    for start in range(len(words) - len(needle) + 1):
        if words[start:start + len(needle)] == needle:
            return list(range(start, start + len(needle)))
    return []


def said_in(word: str, honest: str) -> bool:
    """``word`` (an elided form split, «c'est» → «c'» + «est») stands in the honest headline."""

    said = set(headline_tokens(honest))
    tokens = headline_tokens(word)
    return bool(tokens) and all(token in said for token in tokens)


def grade_trap(headline: str, wrong: str, picked: list[int], honest: str | None = None) -> dict[str, Any]:
    """Right when every tapped word is one of the words that say too much and at least one of
    them carries the meaning (not «le» alone); ``fine``: the tapped words the claims do say.

    ``honest`` (the honest headline of the same band, 2026-11-22): a tapped word outside
    ``wrong`` is ``fine`` («Bleibt stehen: Das sagt der Artikel») only when the honest headline
    says it too. A desk that changed more than ``wrong`` (the Arc story: «gagne» for «essaie de
    gagner») never makes the trap call a word the article does not say true; such a word is
    neither fine nor held against the learner."""

    span = set(wrong_span(headline, wrong))
    words = words_of(headline)
    chosen = set(picked)
    outside = chosen - span
    if honest is not None:
        unsaid = {i for i in outside if not said_in(words[i], honest)}
        outside -= unsaid
        chosen -= unsaid
    fine = sorted(outside)
    meaningful = {i for i in span if comptoir.ci(words[i]) not in _TRAP_STOP}
    return {"correct": bool(chosen) and not fine and bool(chosen & meaningful), "fine": fine}


# ---------------------------------------------------------------------------
# «À toi»
# ---------------------------------------------------------------------------


def build_input(band: str) -> str:
    return "tiles" if band == "A1" else "frame" if band == "A2" else "free"


def a1_headline(subject: str, fact: str) -> str:
    return voice.french_typography(f"{headline_text(subject)} {headline_text(fact)}")


def a2_headline(frame: str, text: str) -> str:
    body = headline_text(text)
    head = headline_text(frame).rstrip(" …")
    if comptoir.ci(body).startswith(comptoir.ci(head)):
        return voice.french_typography(body[:1].upper() + body[1:])
    return voice.french_typography(f"{head} {body}")


def headline_problem(desk: TitreDesk, dossier: EditorialDossier, text: str) -> RvRubriqueError | None:
    """The deterministic check before Romy reads it: length, the words that said too much, a
    number the claims do not carry."""

    count = comptoir.word_count(text)
    if count < MIN_WORDS:
        return RvRubriqueError(code="too_short", count=MIN_WORDS)
    if count > MAX_WORDS:
        return RvRubriqueError(code="too_long", count=MAX_WORDS)
    if comptoir.contains(text, desk.wrong_fr):
        return RvRubriqueError(code="says_too_much")
    if comptoir.numbers(text) - comptoir.numbers(" ".join(c.fr for c in dossier.claims)):
        return RvRubriqueError(code="number_not_in_claims")
    return None


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------


def _cast() -> RvRubriqueCast:
    return RvRubriqueCast(id=comptoir.GUS_ID, name_fr=comptoir.name_fr(comptoir.GUS_ID),
                          role_fr=comptoir.role_fr(comptoir.GUS_ID))


def _claim(dossier: EditorialDossier, claim_id: str) -> Any:
    claim = dossier.claims_by_id().get(claim_id)
    return rv_claim(dossier, claim) if claim is not None else None


def titre_view(loaded: Loaded) -> RvTitreView:
    """What the player shows: the current step and only what that step may know."""

    dossier, plan, state, row = loaded.dossier, loaded.plan, loaded.state, loaded.row
    desk = desk_of(loaded)
    band = band_of(loaded)
    language = _gloss_language_of(plan)
    seed = str(row.id)
    acts = Acts(state)
    step = step_of(acts, closed=state.closed)
    at = STEPS.index(step)
    keys = key_of(seed)

    three = None
    if at >= STEPS.index("three"):
        resolved = acts.three_resolved
        picked = [str(p.get("key")) for p in acts.picks]
        options = []
        for index in shown_order(seed):
            headline, key = desk.headlines[index], keys[index]
            option = RvTitreOption(key=key, text=_ct(headline.for_band(band), language))
            if resolved or (key in picked and headline.role != "honest"):
                option.role = headline.role
                if headline.why is not None:
                    option.why = _ct(headline.why, language)
                    option.claim = _claim(dossier, headline.claim_id)
            options.append(option)
        three = RvTitreThree(by=_cast(), headlines=options, tries=len(acts.picks), picked=picked, resolved=resolved,
                             correct=acts.three_correct if resolved else None,
                             solution=keys[role_index(desk, "honest")] if resolved else None)

    trap = None
    if at >= STEPS.index("trap"):
        exaggerated = desk.headline("exaggerated")
        text = exaggerated.for_band(band)
        resolved = acts.trap_resolved
        last = acts.traps[-1] if acts.traps else None
        trap = RvTitreTrap(
            headline=_ct(text, language),
            words=[RvTitreWord(index=i, fr=w) for i, w in enumerate(words_of(text.fr))],
            tries=len(acts.traps),
            picked=list(last.get("words") or []) if last else [],
            fine=list(last.get("fine") or []) if last and not acts.trap_correct else [],
            resolved=resolved,
            correct=acts.trap_correct if resolved else None,
            solution=wrong_span(text.fr, desk.wrong_fr) if resolved else [],
            why=_ct(exaggerated.why, language) if resolved else None,
            claim=_claim(dossier, exaggerated.claim_id) if resolved else None,
        )

    build = None
    if at >= STEPS.index("build"):
        kind = build_input(band)
        proof = acts.proof
        build = RvTitreBuild(
            input=kind,  # type: ignore[arg-type]
            phrase=_ct(desk.phrase.for_band(band), language),
            subjects=[_ct(t, language) for t in desk.build.subjects] if kind == "tiles" else [],
            facts=[_ct(t, language) for t in desk.build.facts] if kind == "tiles" else [],
            frame=_ct(desk.build.frame, language) if kind == "frame" else None,
            max_words=MAX_WORDS,
            avoid_fr=desk.wrong_fr,
            learner_fr=str(acts.build.get("learner_fr")) if acts.build else None,
            draft_fr=proof["draft"] if proof else None,
            proof=proof["proof"] if proof else None,  # type: ignore[arg-type]
            marks=[RvComptoirMark(span_fr=str(m.get("span_fr")), start=int(m.get("start") or 0), kind=str(m.get("kind")),  # type: ignore[arg-type]
                                  why=pourquoi.hint_of(m), **regle.view_fields(m))
                   for m in (proof["marks"] if proof else []) if isinstance(m, dict) and m.get("kind") in comptoir_loop.MARK_KINDS],
            tries=proof["tries"] if proof else 0,
            max_tries=FIX_TRIES,
            printed_fr=proof["printed"] if proof else None,
            # «Le pourquoi», once settled: the counter's notes, from the same rounds of marks.
            notes=[RvComptoirNote(**note) for note in pourquoi.notes_of(pourquoi.rounds_of(acts.build, acts.fixes),
                                                                         proof["proof"])
                   if note["kind"] in comptoir_loop.MARK_KINDS] if proof else [],
        )

    return RvTitreView(step=step, steps=list(STEPS), band=comptoir_band(band), title_fr=dossier.title_fr,  # type: ignore[arg-type]
                       read=read_of(loaded, language), three=three, trap=trap, build=build)


view = titre_view


# ---------------------------------------------------------------------------
# The acts
# ---------------------------------------------------------------------------


def _out_of_order(step: str, act: str) -> RevueError:
    return RevueError(409, "revue_titre_out_of_order", step=step, act=act)


def _bad(act: str) -> RevueError:
    return RevueError(422, "revue_titre_bad_act", act=act)


def apply_act(encounter: RevueEncounter, loaded: Loaded, body: RvRubriqueRequest) -> RvRubriqueError | None:
    """Record one act (or nothing, when it repeats one already recorded); returns the reason
    for an act the learner can fix on the same screen."""

    state = loaded.state
    desk = desk_of(loaded)
    band = band_of(loaded)
    seed = str(loaded.row.id)
    acts = Acts(state)
    step = step_of(acts, closed=state.closed)
    act = body.act
    if state.closed:
        raise _out_of_order(step, act)

    if act == "open":
        if not acts.opened:
            state.append(KIND, act="open")
        return None

    if act == "pick":
        key = str(body.key or "")
        if key not in KEYS:
            raise _bad(act)
        if acts.three_resolved or any(p.get("key") == key for p in acts.picks):
            return None  # settled, or a repeat
        if not acts.opened:
            raise _out_of_order(step, act)
        headline = desk.headlines[index_of(seed)[key]]
        state.append(KIND, act="pick", key=key, role=headline.role, correct=headline.role == "honest",
                     attempt=len(acts.picks) + 1)
        return None

    if act == "trap":
        picked = sorted({int(i) for i in body.words or []})
        text = desk.headline("exaggerated").for_band(band).fr
        if not picked or any(i < 0 or i >= len(words_of(text)) for i in picked):
            if not picked:
                return RvRubriqueError(code="pick_words")
            raise _bad(act)
        if acts.trap_resolved or (acts.traps and acts.traps[-1].get("words") == picked):
            return None
        if not acts.three_resolved:
            raise _out_of_order(step, act)
        graded = grade_trap(text, desk.wrong_fr, picked, honest=desk.headline("honest").for_band(band).fr)
        state.append(KIND, act="trap", words=picked, correct=graded["correct"], fine=graded["fine"],
                     attempt=len(acts.traps) + 1)
        return None

    if act == "build":
        if acts.build is not None:
            return None  # a double submit returns the stored result
        if not acts.trap_resolved:
            raise _out_of_order(step, act)
        return _build(encounter, loaded, desk, band=band, body=body)

    if act == "build_fix":
        return _build_fix(encounter, loaded, desk, acts, step=step, body=body)

    raise _bad(act)


def _build(encounter: RevueEncounter, loaded: Loaded, desk: TitreDesk, *, band: str,
           body: RvRubriqueRequest) -> RvRubriqueError | None:
    state = loaded.state
    kind = build_input(band)
    typed = ""
    check: dict[str, Any] = {"proof": "clean", "target": "", "marks": [], "cost": 0.0, "refused": None, "source": "tiles"}
    if kind == "tiles":
        parts = list(body.parts or [])
        if (len(parts) != 2 or not 0 <= parts[0] < len(desk.build.subjects)
                or not 0 <= parts[1] < len(desk.build.facts)):
            return RvRubriqueError(code="pick_tiles")
        learner = a1_headline(desk.build.subjects[parts[0]].fr, desk.build.facts[parts[1]].fr)
        check["target"] = learner
    else:
        typed = re.sub(r"\s+", " ", body.text or "").strip()
        learner = a2_headline(desk.build.frame.fr, typed) if kind == "frame" else voice.french_typography(headline_text(typed))
        why = headline_problem(desk, loaded.dossier, learner)
        if why is not None:
            return why
        check = _proofread(encounter, loaded, desk, band=band, learner_fr=learner)
    state.append("turn_learner", text_fr=learner, mode=body.mode, titre="build")
    state.append(KIND, act="build", learner_fr=learner, typed_fr=typed, parts=list(body.parts or []),
                 proof=check["proof"], target_fr=check["target"], marks=check["marks"], source=check["source"],
                 cost_usd=check["cost"], refused=check["refused"],
                 prompt_version=edit_prompt_version() if kind != "tiles" else None)
    return None


def _build_fix(encounter: RevueEncounter, loaded: Loaded, desk: TitreDesk, acts: Acts, *, step: str,
               body: RvRubriqueRequest) -> RvRubriqueError | None:
    """The learner's fix of Romy's marks: as ``fil_loop._tell_fix``."""

    state = loaded.state
    band = band_of(loaded)
    proof = acts.proof
    if proof is None:
        raise _out_of_order(step, "build_fix")
    if proof["proof"] != "marked":
        return None  # settled: a repeat
    if body.value == "romy":
        if proof["tries"] < 1:
            raise _out_of_order(step, "build_fix")
        state.append(KIND, act="build_fix", by="romy", proof="corrected", target_fr=proof["target"])
        _settle(encounter, loaded, acts, "corrected")
        return None
    learner = voice.french_typography(headline_text(re.sub(r"\s+", " ", body.text or "")))
    why = headline_problem(desk, loaded.dossier, learner)
    if why is not None:
        return why
    if comptoir_loop._proof_key(learner) == comptoir_loop._proof_key(proof["draft"]):  # noqa: SLF001
        return RvRubriqueError(code="nothing_changed")
    tries = proof["tries"] + 1
    state.append("turn_learner", text_fr=learner, mode=body.mode, titre="build_fix")
    row: dict[str, Any] = {"text_fr": learner, "typed_fr": learner, "try": tries, "cost_usd": 0.0}
    if comptoir_loop._proof_key(learner) == comptoir_loop._proof_key(proof["target"]):  # noqa: SLF001
        row.update(proof="fixed", target_fr=proof["target"])
    else:
        check = _proofread(encounter, loaded, desk, band=band, learner_fr=learner)
        row.update(cost_usd=check["cost"], refused=check["refused"], prompt_version=edit_prompt_version())
        if check["proof"] == "as_written":
            row.update(proof="as_written", target_fr="")
        elif check["proof"] == "clean":
            row.update(proof="fixed", target_fr=check["target"])
        elif tries >= FIX_TRIES:
            row.update(proof="corrected", target_fr=check["target"])
        else:
            row.update(proof="marked", target_fr=check["target"], marks=check["marks"])
    state.append(KIND, act="build_fix", **row)
    _settle(encounter, loaded, acts, str(row.get("proof")))
    return None


def _settle(encounter: RevueEncounter, loaded: Loaded, acts: Acts, proof: str) -> None:
    """«Le pourquoi», as «Le fil» (``fil_loop._settle``): once the marks are settled the slips
    go to the learner's error memory (``acts`` as they were before this fix)."""

    if pourquoi.enabled() and proof in {"fixed", "corrected"}:
        pourquoi.remember(encounter.db, loaded.row.user_id, pourquoi.rounds_of(acts.build, acts.fixes), proof,
                          session_id=str(loaded.row.id), dossier_id=loaded.dossier.id)


def edit_prompt_version() -> str:
    """The ``titre_edit`` prompt in use: v2 with «Le pourquoi» on (``pourquoi.py``), else v1."""

    return pourquoi.TITRE_PROMPT_VERSION if pourquoi.enabled() else TITRE_EDIT_PROMPT_VERSION


# ---------------------------------------------------------------------------
# Romy's edit (one model call at A2+, one more per fix)
# ---------------------------------------------------------------------------

TITRE_EDIT_INSTRUCTIONS = """You are Romy Tremblay, a Québécoise journalist. Your trainee, a French learner, just
wrote a headline for a news story, one that says no more than the facts. You proofread it like an editor who marks
the copy and gives it back: the learner fixes it. From INPUT answer with ONE JSON object:
{"edited_fr": str, "marks": [{"span_fr": str, "kind": str}]}
RULES
- edited_fr: learner_fr with its mistakes corrected and nothing else: grammar, agreement, conjugation, gender,
  spelling, accents, word order, a missing word. Keep the learner's words and meaning; a headline has no final full
  stop. Never fix style, never swap a correct word for a nicer one, never add a fact, a number, a name or an idea.
  If learner_fr is already correct, copy it unchanged. If it is not French, put the learner's idea into simple
  French.
- marks: one per mistake you corrected, at most three, none when nothing changed. span_fr is the learner's wrong
  words exactly as they appear in learner_fr (for a missing word, the word just before the gap); kind is one of
  accord (agreement), conjugaison (verb form or tense), genre (gender), orthographe (spelling or accents), mot
  (wrong word), ordre (word order), manque (a missing word).
- French typography: a space before ? ! : ;"""

TITRE_EDIT_SYSTEM = ("You proofread learners' French like a kind newspaper editor who marks mistakes for the "
                     "learner to fix. Answer with one JSON object only.")


def edit_context(dossier: EditorialDossier, desk: TitreDesk, *, band: str, learner_fr: str) -> dict[str, Any]:
    return {
        "band": band,
        "learner_fr": learner_fr,
        "honest_fr": desk.headline("honest").for_band(band).fr,
        "facts": [c.fr for c in dossier.claims if c.kind == "fact"],
    }


def _proofread(encounter: RevueEncounter, loaded: Loaded, desk: TitreDesk, *, band: str,
               learner_fr: str) -> dict[str, Any]:
    """One model call (``provider.titre_edit``), checked as «Le fil»'s (``fil_loop.check_edit``)
    and never the words that said too much; ``as_written`` when the call or its checks fail."""

    out: dict[str, Any] = {"proof": "as_written", "target": "", "marks": [], "source": "fallback", "cost": 0.0,
                           "refused": None}
    edit = getattr(encounter.provider, "titre_edit", None)
    if not callable(edit):
        return out
    context = edit_context(loaded.dossier, desk, band=band, learner_fr=learner_fr)
    language = pourquoi.explain_language(encounter, loaded) if pourquoi.enabled() else None
    if language:
        context[pourquoi.EXPLAIN_KEY] = language
    before = meter(encounter.provider)
    try:
        raw = edit(context)
    except Exception as exc:  # noqa: BLE001 - the learner's headline stands
        logger.bind(session_id=str(loaded.row.id)).warning("revue titre: edit failed ({})", exc)
        raw = None
    out["cost"] = round(meter(encounter.provider) - before, 6)
    if not isinstance(raw, dict):
        return out
    checked = fil_loop.check_edit(raw, learner_fr)
    edited = headline_text(checked.get("edited_fr") or "")
    if edited and comptoir.contains(edited, desk.wrong_fr):
        checked = {"_problems": ["edit:says_too_much"]}
        edited = ""
    out["refused"] = checked.get("_problems") or None
    if edited:
        edited = voice.french_typography(edited)
        edited, marks = regle.marked(encounter, loaded, learner_fr=learner_fr, edited=edited,
                                     hints=checked.get("marks") or [], raw_marks=raw.get("marks"), band=band,
                                     language=language, shape=lambda text: voice.french_typography(headline_text(text)))
        out.update(target=edited, marks=marks, proof="marked" if marks else "clean", source="model")
    return out


# ---------------------------------------------------------------------------
# The close: «La page»
# ---------------------------------------------------------------------------


def close(encounter: RevueEncounter, loaded: Loaded) -> tuple[Any, RvClosing]:
    """«La page»: no model call. The learner's headline must be settled first."""

    from app.services.revue.carte import keep_papier_words

    row, dossier, plan, state = loaded.row, loaded.dossier, loaded.plan, loaded.state
    existing = _closing_of(state)
    if existing is not None:
        return session_view(loaded), existing
    desk = desk_of(loaded)
    band = band_of(loaded)
    acts = Acts(state)
    proof = acts.proof
    if proof is None or not acts.settled:
        raise RevueError(409, "revue_titre_out_of_order", step=step_of(acts, closed=False), act="close")
    printed = str(proof["printed"] or "")
    own = acts.own_words()
    lead = dossier.lead_for(band).fr
    honest = desk.headline("honest")
    page = RvTitrePage(headline_fr=printed, proof=proof["proof"],
                       dateline_fr=dateline(dossier, _place(loaded)).rstrip(". "), lead_fr=lead,
                       honest_fr=honest.for_band(band).fr, phrase_fr=desk.phrase.for_band(band).fr, words=[])
    contribution = contribution_spans(own, printed)
    state.append("artifact", kind=KIND, text_fr=printed, learner_fr=own, contribution=contribution,
                 proof=proof["proof"])
    claims = dossier.claims_by_id()
    shown = [claims[cid] for cid in dict.fromkeys(h.claim_id for h in desk.headlines) if cid in claims]
    sources = [_source(dossier, sid) for sid in dict.fromkeys(c.source_id for c in shown)]
    names = list(dict.fromkeys(source.name for source in sources))
    byline = "Romy Tremblay, avec toi"
    dispatch = RvDispatch(
        kicker_fr=KICKER,
        headline_fr=printed,
        body_fr=[lead],
        contribution=[],
        byline_fr=f"{byline} · d'après " + " et ".join(names) if names else byline,
        sources=sources,
    )
    met = [lead, *(h.for_band(band).fr for h in desk.headlines), *(c.fr for c in shown)]
    kept = RvKept(words=kept_words(plan, state, met=met, used=[own]), claims=[rv_claim(dossier, c) for c in shown])
    page.words = [word.fr for word in kept.words]
    closing = RvClosing(romy_line_fr=ROMY_CLOSE_LINE, dispatch=dispatch, kept=kept, question_kept_fr=None,
                        colophon_fr=colophon_for(row.week), titre_page=page)  # type: ignore[arg-type]
    closing.vignette = encounter._mint_vignette(loaded, kind=KIND, kept_contribution=bool(contribution))  # noqa: SLF001
    keep_papier_words(encounter.db, row, dossier=dossier, plan=plan, state=state, kept=kept)

    state.append("turn_romy", beat="close", role="close", text_fr=ROMY_CLOSE_LINE, cost_usd=0.0)
    state.append("closed", closing=closing.model_dump(mode="json"))
    row.status = "closed"
    row.closed_at = datetime.now(UTC)
    encounter._remember(loaded, artifact=state.current_artifact, kind=KIND)  # noqa: SLF001
    encounter._record_cost(loaded)  # noqa: SLF001
    encounter._save(loaded)  # noqa: SLF001
    try:
        from app.services.revue import carte as _carte

        _carte.invalidate(row.user_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("revue: carte invalidate skipped ({})", exc)
    return session_view(loaded), closing


__all__ = [
    "Acts",
    "TITRE_EDIT_INSTRUCTIONS",
    "a1_headline",
    "apply_act",
    "close",
    "grade_trap",
    "step_of",
    "titre_view",
    "view",
    "wrong_span",
]
