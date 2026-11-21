"""«La photo»: the learner's loop (WP-119 «les rubriques», owner 2026-11-21).

Five screens — read, «La planche», «La légende», «À toi», the page — played from the photo
desk's work (``photo.py``), bound to the story's gallery and snapshotted on the session's
first ``choice`` event (``mode="photo"``). As «Le titre» (``titre_loop.py``): the server owns
the state, every act is one ``photo`` event in the append-only log, the step is derived by
replay (:func:`step_of`), an act out of order is a 409, and an act that repeats one already
recorded records nothing.

Acts, in order (``POST /revue/sessions/{id}/rubrique``):

- ``open``: the learner read the story.
- ``choose {key}``: «Laquelle va avec ce titre ?» — the story's pictures side by side; pick
  the one for the day's headline. A miss says, in the learner's language, what the picked
  picture shows; the second miss shows the answer. Two tries.
- ``seen {words}``: «Qu'est-ce qu'on voit ?» — tap the things THIS picture shows, among
  things the other pictures show (deterministic). A miss names the tapped things another
  picture shows and says how many are still missing, never which; the second shows them.
- ``caption {key}``: three captions of the picture; find the one with a wrong fact (a miss
  says what is right or wrong with the one picked). Two tries.
- ``caption_fix {value | text}``: what is wrong — a pick at A1–A2, a rewrite at B1+, graded as
  the intox's correction. Two tries; the true value only after the second miss.
- ``build {key, parts | text}`` then ``build_fix {text | value: "romy"}``: the learner's own
  caption for a picture of their choice. A1 builds «Sur la photo, on voit {a thing}.» and a
  fact (correct by construction, no model call); A2 completes the frame; B1+ write two
  sentences, one that says what the picture shows, one that gives the news. A deterministic
  check first, then Romy's edit (``rubrique_proof``), the learner fixes before anything prints.

The close (:func:`close`) makes no model call: «La page» (the picture large, the learner's
caption under it, its credit, signed with the sources), the dispatch, the ``photo``
artifact, the vignette, the kept words, Romy's memory.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.schemas.revue import (
    RvClosing,
    RvDispatch,
    RvKept,
    RvPhotoBuild,
    RvPhotoCaption,
    RvPhotoChoice,
    RvPhotoFix,
    RvPhotoLegende,
    RvPhotoPage,
    RvPhotoPicture,
    RvPhotoPlanche,
    RvPhotoSeen,
    RvPhotoView,
    RvPhotoWord,
    RvRubriqueError,
    RvRubriqueRequest,
)
from app.services.revue import comptoir, comptoir_loop, photo, rubrique_proof, voice
from app.services.revue.dossier import ComptoirText, PhotoDesk, PhotoPicture, comptoir_band
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
    rv_claim,
    session_view,
)
from app.services.revue.fil_loop import _rng
from app.services.revue.intox_loop import _ct, _place, read_of
from app.services.revue.intox_loop import grade_fix as intox_grade_fix

if TYPE_CHECKING:  # pragma: no cover
    from app.services.revue.encounter import RevueEncounter

KIND = "photo"
STEPS: tuple[str, ...] = ("read", "planche", "legende", "build", "page")
KEYS: tuple[str, ...] = ("a", "b", "c", "d")
MAX_TRIES = 2
SEEN_SHOWN = 4
DISTRACTORS = 3
MIN_WORDS = 3
MAX_WORDS = {"frame": 20, "free": 30}
FIX_MAX_CHARS = 300

ROMY_CLOSE_LINE = "Belle légende ! Ta photo est dans le journal."
KICKER = "La photo de Romy"


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class Acts:
    """The learner's acts so far, replayed from the ``photo`` events."""

    def __init__(self, state: Any) -> None:
        self.opened = False
        self.chooses: list[dict[str, Any]] = []
        self.seens: list[dict[str, Any]] = []
        self.captions: list[dict[str, Any]] = []
        self.fixes_caption: list[dict[str, Any]] = []
        self.build: dict[str, Any] | None = None
        self.build_fixes: list[dict[str, Any]] = []
        for event in state.events:
            if event.kind != KIND:
                continue
            payload = event.payload
            act = payload.get("act")
            if act == "open":
                self.opened = True
            elif act == "choose" and not self.choose_resolved:
                self.chooses.append(dict(payload))
            elif act == "seen" and not self.seen_resolved:
                self.seens.append(dict(payload))
            elif act == "caption" and not self.caption_resolved:
                self.captions.append(dict(payload))
            elif act == "caption_fix" and not self.fix_resolved:
                self.fixes_caption.append(dict(payload))
            elif act == "build" and self.build is None:
                self.build = dict(payload)
            elif act == "build_fix" and self.build is not None:
                self.build_fixes.append(dict(payload))

    @staticmethod
    def _resolved(rows: list[dict[str, Any]]) -> bool:
        return any(row.get("correct") for row in rows) or len(rows) >= MAX_TRIES

    @staticmethod
    def _correct(rows: list[dict[str, Any]]) -> bool:
        return any(row.get("correct") for row in rows)

    choose_resolved = property(lambda self: self._resolved(self.chooses))
    choose_correct = property(lambda self: self._correct(self.chooses))
    seen_resolved = property(lambda self: self._resolved(self.seens))
    seen_correct = property(lambda self: self._correct(self.seens))
    caption_resolved = property(lambda self: self._resolved(self.captions))
    caption_correct = property(lambda self: self._correct(self.captions))
    fix_resolved = property(lambda self: self._resolved(self.fixes_caption))
    fix_correct = property(lambda self: self._correct(self.fixes_caption))

    @property
    def trail(self) -> rubrique_proof.Trail:
        return rubrique_proof.Trail(self.build, self.build_fixes)


def desk_of(loaded: Loaded) -> PhotoDesk:
    desk = loaded.dossier.photo
    if desk is None:  # a photo session always snapshots its desk; keep the view total anyway
        raise RevueError(409, "revue_not_photo")
    return desk


def band_of(loaded: Loaded) -> str:
    return str(loaded.plan.learner.band)


def step_of(acts: Acts, *, closed: bool) -> str:
    if closed:
        return "page"
    if not acts.opened:
        return "read"
    if not (acts.choose_resolved and acts.seen_resolved):
        return "planche"
    if not (acts.caption_resolved and acts.fix_resolved):
        return "legende"
    if not acts.trail.settled:
        return "build"
    return "page"


def picture_keys(desk: PhotoDesk, seed: str) -> dict[str, str]:
    """ref → the key the session shows it under (shuffled per session)."""

    refs = [p.ref for p in desk.pictures]
    _rng(seed, "photo-pictures").shuffle(refs)
    return {ref: KEYS[i] for i, ref in enumerate(refs)}


def ref_of(desk: PhotoDesk, seed: str, key: str) -> str | None:
    return next((ref for ref, k in picture_keys(desk, seed).items() if k == key), None)


def seen_words(desk: PhotoDesk, seed: str) -> list[tuple[ComptoirText, bool]]:
    """«Qu'est-ce qu'on voit ?»: the lead picture's things (up to four) and the other pictures'
    (up to three, none that the lead shows too), in a per-session order; ``True`` for the
    lead's."""

    lead = desk.picture(desk.lead)
    own = list(lead.seen)[:SEEN_SHOWN]
    others: list[ComptoirText] = []
    for picture in desk.pictures:
        if picture.ref == desk.lead:
            continue
        for item in picture.seen:
            if not any(photo.nouns(item.fr) == photo.nouns(o.fr) for o in [*own, *others]):
                others.append(item)
    _rng(seed, "photo-distractors").shuffle(others)
    rows = [(item, True) for item in own] + [(item, False) for item in others[:DISTRACTORS]]
    _rng(seed, "photo-seen").shuffle(rows)
    return rows


def caption_keys(seed: str) -> list[int]:
    order = [0, 1, 2]
    _rng(seed, "photo-captions").shuffle(order)
    return order


def caption_key_of(seed: str) -> dict[int, str]:
    return {index: "abc"[position] for position, index in enumerate(caption_keys(seed))}


def fix_input(band: str) -> str:
    return "pick" if comptoir_band(band) in {"a1", "a2"} else "write"


def build_input(band: str) -> str:
    return "tiles" if band == "A1" else "frame" if band == "A2" else "free"


def fix_options(desk: PhotoDesk, seed: str) -> list[str]:
    wrong = desk.caption("wrong")
    options = [str(wrong.right_fr), str(wrong.distractor_fr)]
    _rng(seed, "photo-fix-options").shuffle(options)
    return options


def opener(picture: PhotoPicture) -> str:
    """A1's caption opens on the picture: «Sur la photo» (a photo) / «Sur l'image» (ours)."""

    return "Sur la photo, on voit" if picture.kind == "photo" else "Sur l'image, on voit"


def a1_caption(picture: PhotoPicture, seen: str, fact: str) -> str:
    thing = seen.strip().rstrip(" .")
    return voice.french_typography(f"{opener(picture)} {thing}. {fact.strip().rstrip(' .')}.")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s.strip()]


def caption_problem(desk: PhotoDesk, picture: PhotoPicture, dossier: Any, text: str, kind: str) -> RvRubriqueError | None:
    """The deterministic check before Romy reads it: length, what the picture shows, the news
    (B1+: a second sentence grounded in the claims), no number the claims lack."""

    count = comptoir.word_count(text)
    if count < MIN_WORDS:
        return RvRubriqueError(code="too_short", count=MIN_WORDS)
    if count > MAX_WORDS[kind]:
        return RvRubriqueError(code="too_long", count=MAX_WORDS[kind])
    story = " ".join([dossier.title_fr, dossier.summary_fr, *(c.fr for c in dossier.claims)])
    if comptoir.numbers(text) - comptoir.numbers(story):
        return RvRubriqueError(code="number_not_in_claims")
    sentences = _sentences(text)
    if kind == "free" and len(sentences) < 2:
        return RvRubriqueError(code="two_sentences", count=2)
    describing = sentences[0] if kind == "free" else text
    if not photo.mentions(describing, picture.seen):
        return RvRubriqueError(code="name_what_you_see")
    if kind == "free":
        from app.services.revue.intox import grounded  # noqa: PLC0415

        if not any(grounded(" ".join(sentences[1:]), c.fr) for c in dossier.claims):
            return RvRubriqueError(code="say_the_news")
    if desk.caption("wrong").wrong_fr and comptoir.contains(text, str(desk.caption("wrong").wrong_fr)):
        return RvRubriqueError(code="wrong_fact")
    return None


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------


def picture_view(picture: PhotoPicture, key: str) -> RvPhotoPicture:
    return RvPhotoPicture(key=key, kind=picture.kind, url=str(picture.url or ""), credit_fr=str(picture.credit_fr or ""),
                          licence=picture.licence, licence_url=picture.licence_url, source_url=picture.source_url,
                          width=picture.width, height=picture.height)


def photo_view(loaded: Loaded) -> RvPhotoView:
    """What the player shows: the current step and only what that step may know."""

    dossier, plan, state, row = loaded.dossier, loaded.plan, loaded.state, loaded.row
    desk = desk_of(loaded)
    band = band_of(loaded)
    language = _gloss_language_of(plan)
    seed = str(row.id)
    acts = Acts(state)
    step = step_of(acts, closed=state.closed)
    at = STEPS.index(step)
    keys = picture_keys(desk, seed)
    ordered = sorted(desk.pictures, key=lambda p: keys[p.ref])

    planche = None
    if at >= STEPS.index("planche"):
        resolved = acts.choose_resolved
        last = acts.chooses[-1] if acts.chooses and not acts.choose_correct else None
        shows: list[Any] = []
        if last is not None:
            picked_ref = ref_of(desk, seed, str(last.get("key")))
            if picked_ref:
                shows = [_ct(item, language) for item in desk.picture(picked_ref).seen]
        seen = None
        if resolved:
            words = seen_words(desk, seed)
            lead_idx = [i for i, (_, own) in enumerate(words) if own]
            srow = acts.seens[-1] if acts.seens else None
            sres = acts.seen_resolved
            picked = list(srow.get("words") or []) if srow else []
            seen = RvPhotoSeen(
                words=[RvPhotoWord(index=i, text=_ct(item, language)) for i, (item, _) in enumerate(words)],
                tries=len(acts.seens), picked=picked,
                elsewhere=[i for i in picked if i not in lead_idx] if srow and not acts.seen_correct else [],
                missing=len(set(lead_idx) - set(picked)) if srow and not acts.seen_correct else 0,
                resolved=sres, correct=acts.seen_correct if sres else None, solution=lead_idx if sres else [],
            )
        planche = RvPhotoPlanche(
            headline_fr=dossier.title_fr, pictures=[picture_view(p, keys[p.ref]) for p in ordered],
            tries=len(acts.chooses), picked=[str(c.get("key")) for c in acts.chooses], shows=shows,
            resolved=resolved, correct=acts.choose_correct if resolved else None,
            solution=keys[desk.lead] if resolved else None, seen=seen,
        )

    legende = None
    if at >= STEPS.index("legende"):
        ckeys = caption_key_of(seed)
        resolved = acts.caption_resolved
        picked = [str(c.get("key")) for c in acts.captions]
        captions = []
        for index in caption_keys(seed):
            caption, key = desk.captions[index], ckeys[index]
            option = RvPhotoCaption(key=key, text=_ct(caption.for_band(band), language))
            if resolved or (key in picked):
                option.role = caption.role
                option.why = _ct(caption.why, language) if caption.why is not None else None
            captions.append(option)
        fix = None
        if resolved:
            wrong = desk.caption("wrong")
            kind = fix_input(band)
            fres = acts.fix_resolved
            fix = RvPhotoFix(
                input=kind, text=_ct(wrong.for_band(band), language), wrong_fr=str(wrong.wrong_fr),  # type: ignore[arg-type]
                options=fix_options(desk, seed) if kind == "pick" else [], tries=len(acts.fixes_caption),
                attempts=[str(r.get("value") or r.get("text") or "") for r in acts.fixes_caption],
                resolved=fres, correct=acts.fix_correct if fres else None,
                right_fr=wrong.right_fr if fres else None,
                fixed=_ct(wrong.fixed.for_band(band), language) if fres and wrong.fixed else None,
            )
        legende = RvPhotoLegende(
            picture=picture_view(desk.picture(desk.lead), keys[desk.lead]), captions=captions,
            tries=len(acts.captions), picked=picked, resolved=resolved,
            correct=acts.caption_correct if resolved else None,
            solution=ckeys[[c.role for c in desk.captions].index("wrong")] if resolved else None, fix=fix,
        )

    build = None
    if at >= STEPS.index("build"):
        kind = build_input(band)
        trail = acts.trail
        proof = trail.proof
        build = RvPhotoBuild(
            input=kind,  # type: ignore[arg-type]
            phrase=_ct(desk.phrase.for_band(band), language),
            choices=[RvPhotoChoice(picture=picture_view(p, keys[p.ref]), seen=[_ct(s, language) for s in p.seen])
                     for p in ordered],
            facts=[_ct(t, language) for t in desk.build.facts] if kind == "tiles" else [],
            frame=_ct(desk.build.frame, language) if kind == "frame" else None,
            max_words=MAX_WORDS.get(kind, 20),
            picture=str(acts.build.get("key")) if acts.build else None,
            learner_fr=str(acts.build.get("learner_fr")) if acts.build else None,
            draft_fr=proof["draft"] if proof else None,
            proof=proof["proof"] if proof else None,  # type: ignore[arg-type]
            marks=rubrique_proof.marks_view(proof),
            tries=proof["tries"] if proof else 0,
            max_tries=rubrique_proof.FIX_TRIES,
            printed_fr=proof["printed"] if proof else None,
            notes=rubrique_proof.notes_view(trail) if proof else [],
        )

    return RvPhotoView(step=step, steps=list(STEPS), band=comptoir_band(band), title_fr=dossier.title_fr,  # type: ignore[arg-type]
                       read=read_of(loaded, language), planche=planche, legende=legende, build=build)


view = photo_view


# ---------------------------------------------------------------------------
# The acts
# ---------------------------------------------------------------------------


def _out_of_order(step: str, act: str) -> RevueError:
    return RevueError(409, "revue_photo_out_of_order", step=step, act=act)


def _bad(act: str) -> RevueError:
    return RevueError(422, "revue_photo_bad_act", act=act)


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

    if act == "choose":
        key = str(body.key or "")
        ref = ref_of(desk, seed, key)
        if ref is None:
            raise _bad(act)
        if acts.choose_resolved or any(c.get("key") == key for c in acts.chooses):
            return None
        if not acts.opened:
            raise _out_of_order(step, act)
        state.append(KIND, act="choose", key=key, correct=ref == desk.lead, attempt=len(acts.chooses) + 1)
        return None

    if act == "seen":
        words = seen_words(desk, seed)
        picked = sorted({int(i) for i in body.words or []})
        if not picked:
            return RvRubriqueError(code="pick_words")
        if any(i < 0 or i >= len(words) for i in picked):
            raise _bad(act)
        if acts.seen_resolved or (acts.seens and acts.seens[-1].get("words") == picked):
            return None
        if not acts.choose_resolved:
            raise _out_of_order(step, act)
        lead = sorted(i for i, (_, own) in enumerate(words) if own)
        state.append(KIND, act="seen", words=picked, correct=picked == lead, attempt=len(acts.seens) + 1)
        return None

    if act == "caption":
        key = str(body.key or "")
        by_key = {k: i for i, k in caption_key_of(seed).items()}
        if key not in by_key:
            raise _bad(act)
        if acts.caption_resolved or any(c.get("key") == key for c in acts.captions):
            return None
        if step != "legende":
            raise _out_of_order(step, act)
        role = desk.captions[by_key[key]].role
        state.append(KIND, act="caption", key=key, role=role, correct=role == "wrong", attempt=len(acts.captions) + 1)
        return None

    if act == "caption_fix":
        if step != "legende" or not acts.caption_resolved:
            if acts.fix_resolved and step in {"build", "page"}:
                return None
            raise _out_of_order(step, act)
        if acts.fix_resolved:
            return None
        wrong = desk.caption("wrong")
        rows = acts.fixes_caption
        if fix_input(band) == "pick":
            value = re.sub(r"\s+", " ", body.value or "").strip()
            if value not in fix_options(desk, seed):
                raise _bad(act)
            if rows and rows[-1].get("value") == value:
                return None
            state.append(KIND, act="caption_fix", value=value, correct=intox_grade_fix(wrong, value=value),  # type: ignore[arg-type]
                         attempt=len(rows) + 1)
            return None
        text = re.sub(r"\s+", " ", body.text or "").strip()[:FIX_MAX_CHARS]
        if comptoir.word_count(text) < comptoir_loop.FIX_MIN_WORDS:
            return RvRubriqueError(code="too_short", count=comptoir_loop.FIX_MIN_WORDS)
        if rows and comptoir.ci(rows[-1].get("text")) == comptoir.ci(text):
            return None
        state.append("turn_learner", text_fr=text, mode=body.mode, photo="caption_fix")
        state.append(KIND, act="caption_fix", text=text, correct=intox_grade_fix(wrong, text=text),  # type: ignore[arg-type]
                     attempt=len(rows) + 1)
        return None

    if act == "build":
        if acts.build is not None:
            return None
        if step != "build":
            raise _out_of_order(step, act)
        return _build(encounter, loaded, desk, band=band, body=body)

    if act == "build_fix":
        if acts.build is None:
            raise _out_of_order(step, act)
        return _build_fix(encounter, loaded, desk, acts, band=band, body=body)

    raise _bad(act)


def _picture_of(desk: PhotoDesk, seed: str, key: str | None) -> PhotoPicture | None:
    ref = ref_of(desk, seed, str(key or ""))
    return desk.picture(ref) if ref else None


def _build(encounter: RevueEncounter, loaded: Loaded, desk: PhotoDesk, *, band: str,
           body: RvRubriqueRequest) -> RvRubriqueError | None:
    seed = str(loaded.row.id)
    picture = _picture_of(desk, seed, body.key)
    if picture is None:
        return RvRubriqueError(code="pick_picture")
    kind = build_input(band)
    typed = ""
    check: dict[str, Any] = {"proof": "clean", "target": "", "marks": [], "cost": 0.0, "refused": None, "source": "tiles"}
    if kind == "tiles":
        parts = list(body.parts or [])
        if len(parts) != 2 or not 0 <= parts[0] < len(picture.seen) or not 0 <= parts[1] < len(desk.build.facts):
            return RvRubriqueError(code="pick_tiles")
        learner = a1_caption(picture, picture.seen[parts[0]].fr, desk.build.facts[parts[1]].fr)
        check["target"] = learner
    else:
        typed = re.sub(r"\s+", " ", body.text or "").strip()
        learner = _shape(desk, typed, kind)
        why = caption_problem(desk, picture, loaded.dossier, learner, kind)
        if why is not None:
            return why
        check = rubrique_proof.proofread(encounter, loaded, kind=KIND, band=band, learner_fr=learner,
                                         refuse=rubrique_proof.no_new_number(loaded.dossier))
    loaded.state.append("turn_learner", text_fr=learner, mode=body.mode, photo="build")
    loaded.state.append(KIND, act="build", key=str(body.key), learner_fr=learner, typed_fr=typed,
                        parts=list(body.parts or []), proof=check["proof"], target_fr=check["target"],
                        marks=check["marks"], source=check["source"], cost_usd=check["cost"], refused=check["refused"],
                        prompt_version=rubrique_proof.prompt_version() if kind != "tiles" else None)
    return None


def _shape(desk: PhotoDesk, typed: str, kind: str) -> str:
    """The caption as written: A2's frame and the learner's end; a final stop."""

    text = typed
    if kind == "frame":
        head = desk.build.frame.fr.rstrip(" .…")
        text = typed if comptoir.ci(typed).startswith(comptoir.ci(head)) else f"{head} {typed}"
    text = text.strip()
    if text and not re.search(r"[.!?…]$", text):
        text += "."
    return voice.french_typography(text[:1].upper() + text[1:])


def _build_fix(encounter: RevueEncounter, loaded: Loaded, desk: PhotoDesk, acts: Acts, *, band: str,
               body: RvRubriqueRequest) -> RvRubriqueError | None:
    seed = str(loaded.row.id)
    picture = _picture_of(desk, seed, (acts.build or {}).get("key"))
    kind = build_input(band)
    if picture is None:
        raise _bad("build_fix")
    trail = acts.trail

    def check(text: str) -> RvRubriqueError | None:
        return caption_problem(desk, picture, loaded.dossier, text, "free" if kind == "free" else "frame")

    try:
        row, error = rubrique_proof.fix_row(encounter, loaded, trail, kind=KIND, band=band, text=body.text,
                                            value=body.value, check=check, prepare=lambda t: _shape(desk, t, "free"),
                                            refuse=rubrique_proof.no_new_number(loaded.dossier))
    except LookupError as exc:
        raise _out_of_order("build", "build_fix") from exc
    if row is None:
        return error
    if row.get("text_fr"):
        loaded.state.append("turn_learner", text_fr=row["text_fr"], mode=body.mode, photo="build_fix")
    loaded.state.append(KIND, act="build_fix", **row)
    rubrique_proof.settle(encounter, loaded, trail, str(row.get("proof")))
    return None


# ---------------------------------------------------------------------------
# The close: «La page»
# ---------------------------------------------------------------------------


def close(encounter: RevueEncounter, loaded: Loaded) -> tuple[Any, RvClosing]:
    """«La page»: no model call. The learner's caption must be settled first."""

    from app.services.revue.carte import keep_papier_words

    row, dossier, plan, state = loaded.row, loaded.dossier, loaded.plan, loaded.state
    existing = _closing_of(state)
    if existing is not None:
        return session_view(loaded), existing
    desk = desk_of(loaded)
    band = band_of(loaded)
    seed = str(row.id)
    acts = Acts(state)
    trail = acts.trail
    proof = trail.proof
    if proof is None or not trail.settled:
        raise RevueError(409, "revue_photo_out_of_order", step=step_of(acts, closed=False), act="close")
    key = str((acts.build or {}).get("key"))
    picture = _picture_of(desk, seed, key) or desk.picture(desk.lead)
    printed = str(proof["printed"] or "")
    own = trail.own_words()
    page = RvPhotoPage(title_fr=dossier.title_fr, dateline_fr=dateline(dossier, _place(loaded)).rstrip(". "),
                       picture=picture_view(picture, key), caption_fr=printed, proof=proof["proof"],
                       phrase_fr=desk.phrase.for_band(band).fr, words=[])
    contribution = contribution_spans(own, printed) if own else []
    state.append("artifact", kind=KIND, text_fr=printed, learner_fr=own, contribution=contribution,
                 proof=proof["proof"], picture=picture.ref)
    claims = dossier.claims_by_id()
    shown = [claims[cid] for cid in dict.fromkeys(c.claim_id for c in desk.captions) if cid in claims]
    sources = [_source(dossier, sid) for sid in dict.fromkeys(c.source_id for c in shown)]
    names = list(dict.fromkeys(source.name for source in sources))
    byline = "Romy Tremblay, avec toi"
    dispatch = RvDispatch(
        kicker_fr=KICKER,
        headline_fr=dossier.title_fr,
        body_fr=[printed, str(picture.credit_fr or "")],
        contribution=[],
        byline_fr=f"{byline} · d'après " + " et ".join(names) if names else byline,
        sources=sources,
    )
    met = [dossier.lead_for(band).fr, *(c.for_band(band).fr for c in desk.captions), *(c.fr for c in shown)]
    kept = RvKept(words=kept_words(plan, state, met=met, used=[own] if own else []),
                  claims=[rv_claim(dossier, c) for c in shown])
    page.words = [word.fr for word in kept.words]
    closing = RvClosing(romy_line_fr=ROMY_CLOSE_LINE, dispatch=dispatch, kept=kept, question_kept_fr=None,
                        colophon_fr=colophon_for(row.week), photo_page=page)  # type: ignore[arg-type]
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
    "a1_caption",
    "apply_act",
    "caption_problem",
    "close",
    "photo_view",
    "seen_words",
    "step_of",
    "view",
]
