"""«La photo»: the photo desk (WP-119 «les rubriques», owner 2026-11-21).

The learner, Romy's trainee, works the story's pictures: which one goes with the headline,
what it shows, which of three captions carries a wrong fact, and finally their own caption
(the loop is ``photo_loop.py``; the dealer is ``assignments.py``). This module reads the story's
gallery (:func:`story_pictures`: the painted illustration(s) and the Commons photos of
``photos.gallery_for``, each with a ``ref`` and what we know of it, ``basis_fr``) and writes
what every learner shares: :class:`~app.services.revue.dossier.PhotoDesk`, one JSON call per
story (:func:`write_photo`, through ``rubriques.ask_desk``: one retry, then refused).

- ``seen``: concrete things a picture shows, a noun with its article («le port», «des
  bateaux»), fr + en + de. For a Commons photo ONLY what its stored subject and caption state
  (never a guess at what a photo shows): every word of a ``seen`` line must be a word of that
  basis; for an illustration, of its French brief (its caption, Romy's look, its words), or in
  English of the painter's brief. The lead picture (the one for the headline) has at least two.
- Three ``captions`` of the lead picture at A1 (≤ 10 words), A2 (≤ 14), B1 (≤ 20): ``right``
  (it names a thing the picture shows and says the news from its claim), ``wrong`` (ONE fact
  changed, checked as the intox: ``wrong_fr`` in no claim, ``right_fr`` in its claim, a
  ``distractor_fr`` of the same kind, ``fixed`` as it should read), ``other`` (it describes
  another picture of the story: one of that picture's things, none of the lead's).
- «À toi»'s material: fact tiles (A1: «Sur la photo, on voit {a thing}.» then a fact: correct by
  construction, no vocative) and the A2 frame; the phrase of the day per band.
- The comptoir's checks everywhere (no number the claims lack, no relative date, no id, no
  app word, nothing about a private life), names from the claims or the pictures' basis only.
- The desk needs two pictures: with fewer it is asked again the next morning (the story's
  picture is painted after the desks); a story the comptoir would not argue about gets none.
- :func:`bind`: a session plays the desk only while the story's gallery still holds each
  picture with the same basis; their links and credits are copied in then.
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
    in_story,
    numbers,
    numeric,
    word_count,
)
from app.services.revue.dossier import (
    PHOTO_CAPTION_ROLES,
    BandTexts,
    ComptoirPhrase,
    ComptoirText,
    EditorialDossier,
    PhotoBuild,
    PhotoCaption,
    PhotoDesk,
    PhotoPicture,
)
from app.services.revue.intox import grounded

PHOTO_PROMPT_VERSION = "photo-desk-v1"

CAPTION_MAX_WORDS: dict[str, int] = {"a1": 10, "a2": 14, "b1": 20}
FIXED_EXTRA_WORDS = 4
SEEN_MAX_WORDS = 5
SEEN_MAX = 6
LEAD_SEEN_MIN = 2
WHY_MAX_WORDS = 20
VALUE_MAX_WORDS = 6
FACT_MAX_WORDS = 9
FRAME_MAX_WORDS = 6
PHRASE_MAX_WORDS = 10
MIN_PICTURES = 2
MAX_PICTURES = 4


def _t(fr: str, en: str, de: str) -> ComptoirText:
    return ComptoirText(fr=fr, en=en, de=de)


AUTHORED_PHRASE = ComptoirPhrase(
    a1=_t("Sur la photo, on voit…", "In the photo, you can see…", "Auf dem Foto sieht man…"),
    a2=_t("Au premier plan, …", "In the foreground, …", "Im Vordergrund …"),
    b1=_t("À l'arrière-plan, …", "In the background, …", "Im Hintergrund …"),
    b2=_t("On aperçoit…", "You can make out…", "Man erkennt…"),
)

# ---------------------------------------------------------------------------
# The story's pictures
# ---------------------------------------------------------------------------


def _illustration_basis(dossier: EditorialDossier) -> tuple[str, str]:
    visual = dossier.visual
    if visual is None:
        return "", ""
    french = " ".join(part for part in (visual.caption_fr, visual.look_fr or "", *(w.fr for w in visual.words)) if part)
    english = " ".join(part for part in (visual.moment, visual.symbol or "", *(w.shows for w in visual.words)) if part)
    return french, english


def story_pictures(db: Any, dossier: EditorialDossier) -> list[dict[str, Any]]:
    """The story's gallery (``photos.gallery_for``) as the photo desk reads it: per picture its
    ``ref`` (kind and position, ``illustration-1``, ``photo-1``…), its link and credit, and
    ``basis_fr`` (and ``basis_en``): a photo's stored subject and caption, an illustration's
    brief. Never raises: no gallery is no pictures."""

    from app.services.revue import photos

    try:
        gallery = photos.gallery_for(db, dossier)
    except Exception:  # noqa: BLE001 - no gallery, no «La photo»
        return []
    rows = {row.image_url: row for row in photos._media_rows(db, dossier.id)} if db is not None else {}  # noqa: SLF001
    french, english = _illustration_basis(dossier)
    counts: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for picture in gallery:
        counts[picture.kind] = counts.get(picture.kind, 0) + 1
        if picture.kind == "photo":
            row = rows.get(picture.url)
            subject = str(getattr(row, "subject", "") or "")
            basis_fr = " · ".join(part for part in (subject, picture.caption_fr or "") if part)
            basis_en = ""
        else:
            basis_fr, basis_en = french, english
        out.append({"ref": f"{picture.kind}-{counts[picture.kind]}", "kind": picture.kind, "url": picture.url,
                    "credit_fr": picture.credit_fr, "licence": picture.licence, "licence_url": picture.licence_url,
                    "source_url": picture.source_url, "width": picture.width, "height": picture.height,
                    "basis_fr": basis_fr, "basis_en": basis_en})
    return out


def bind(desk: PhotoDesk, pictures: list[dict[str, Any]]) -> PhotoDesk | None:
    """``desk`` with its pictures' links and credits from the story's gallery as it stands,
    or ``None`` when the gallery no longer holds one of them (or holds it with another
    basis), or holds fewer than two: the desk then is not dealt."""

    by_ref = {str(p.get("ref")): p for p in pictures}
    bound: list[PhotoPicture] = []
    for picture in desk.pictures:
        found = by_ref.get(picture.ref)
        if found is None or found.get("kind") != picture.kind or ci(found.get("basis_fr")) != ci(picture.basis_fr):
            return None
        if not found.get("url") or not found.get("credit_fr"):
            return None
        bound.append(picture.model_copy(update={key: found.get(key) for key in (
            "url", "credit_fr", "licence", "licence_url", "source_url", "width", "height")}))
    if len(bound) < MIN_PICTURES:
        return None
    return desk.model_copy(update={"pictures": bound})


# ---------------------------------------------------------------------------
# What a picture shows
# ---------------------------------------------------------------------------

_ARTICLES = frozenset("le la les l un une des du de d au aux a the an of some".split())
_GRAMMAR = frozenset("et ou en sur sous dans avec pour par and with in on at".split())


def nouns(text: str | None) -> set[str]:
    """The words of ``text`` that carry meaning, lemma-light (folded, a final -s / -x off, five
    letters): articles and grammar words aside, three letters and more («bac» counts)."""

    out: set[str] = set()
    for token in re.findall(r"[^\W\d_]+|\d+", ci(text).replace("’", "'")):
        token = re.sub(r"^(?:l|d)'", "", token)
        if token in _ARTICLES or token in _GRAMMAR or (len(token) < 3 and not token.isdigit()):
            continue
        if len(token) > 4 and token[-1] in "sx":
            token = token[:-1]
        out.add(token[:5])
    return out


def seen_problem(line: ComptoirText, picture: dict[str, Any]) -> str | None:
    """Why ``line`` is not a thing ``picture`` plainly shows: for a Commons photo, a word
    outside its stored subject and caption; for an illustration, outside its French brief
    (or, in English, the painter's)."""

    words = nouns(line.fr)
    if not words:
        return "seen_empty"
    if words <= nouns(picture.get("basis_fr")):
        return None
    if picture.get("kind") == "illustration" and line.en and nouns(line.en) and nouns(line.en) <= nouns(picture.get("basis_en")):
        return None
    return "seen_not_in_basis"


def mentions(text: str, seen: list[ComptoirText]) -> bool:
    """``text`` names one of ``seen``'s things."""

    return any(nouns(item.fr) and nouns(item.fr) <= nouns(text) for item in seen)


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

PHOTO_SPEC = """{"fit": "photo" | "skip",
 "pictures": [{"ref": str, "seen": [T]}],
 "lead": str,
 "captions": [{"role": "right" | "wrong" | "other", "claim_id": str, "picture": str, "a1": T, "a2": T, "b1": T,
   "why": T, "wrong_fr": str, "right_fr": str, "distractor_fr": str, "fixed": {"a1": T, "a2": T, "b1": T}}, ×3],
 "build": {"facts": [T, T, T], "frame": T},
 "phrase": {"a1": T, "a2": T, "b1": T, "b2": T}}
where T = {"fr": str, "en": str, "de": str} (en and de translate the French faithfully, every time); "picture" only
on the other caption, "why" on the wrong and the other one, wrong_fr / right_fr / distractor_fr / fixed only on the
wrong one"""

PHOTO_RULES = """RULES
- fit: "skip" when the story is a death, a war, a crime with victims, an election or a party's politics, or
  anything where a photo game would be cruel. Otherwise "photo".
- pictures: one row per picture of INPUT.pictures (same ref). seen: 1 to 6 concrete things the picture shows, each
  a noun with its article («le port», «des bateaux», «une guitare»), 5 words at most. ONLY what its basis_fr says
  (for kind "photo", its stored subject and caption: never guess what a photo shows; a photo of «Paris» shows
  «Paris», nothing more); for kind "illustration", what its basis_fr or basis_en says. Use the basis's own words.
- lead: the ref of the picture that goes best with INPUT.title_fr; it has at least two things in seen, and none of
  them is also in another picture's seen.
- captions: three captions of the LEAD picture, newspaper style: a1 10 words at most, a2 14, b1 20.
  - right: names one thing the lead picture shows (from its seen) and says the news from its claim (claim_id).
  - wrong: the right caption with exactly ONE fact changed (a number, a day, a place, who): wrong_fr the changed
    words as they stand in a1, a2 AND b1 (6 words at most, in NO claim); right_fr the true words copied from the
    claim; distractor_fr ANOTHER value of the same kind copied from the claims; fixed the caption with right_fr.
  - other: describes ANOTHER picture (picture: its ref): names one of that picture's seen things and none of the
    lead's; true to the claims (claim_id).
  - why (wrong and other): 20 words at most, what is wrong with it («La fête a lieu le 21 juin, pas le 14 juillet.»,
    «Cette légende parle de l'autre photo : on n'y voit pas de guitare.»).
- build: facts: 2 to 4 short true sentences of the news (9 words at most, ending with a full stop, «La fête est
  gratuite.») that follow «Sur la photo, on voit {a thing}.» in a beginner's caption; never a vocative, never an
  exclamation. frame: the A2 caption's opening, 6 words at most («Au premier plan, on voit»).
- phrase: per band (a1 «Sur la photo, on voit…», a2 «Au premier plan, …», b1 «À l'arrière-plan, …», b2 «On
  aperçoit…»).
- Facts: only what the claims say. Numbers in digits, copied exactly from the claims (the wrong value excepted);
  no name the claims or the pictures' basis do not carry. Never a relative date (demain, hier, aujourd'hui, ce soir,
  cette semaine). Never about the app. Never about a person's private life. Our French only.
- French typography: a space before ? ! : ;
Write for THIS story and THESE pictures."""

PHOTO_DESK_INSTRUCTIONS = (
    """You write «La photo» for «Le Papier de Romy», a French-learning app. The learner is the trainee of Romy, a
Québécoise journalist; with the story's pictures side by side they pick the one for the headline, say what it shows,
find the caption with a wrong fact, then write their own caption. From INPUT (the story's French facts, the claims'
quotes and the pictures with what we know of each) answer with ONE JSON object:
"""
    + PHOTO_SPEC
    + "\n"
    + PHOTO_RULES
)

# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def _allow(pictures: list[dict[str, Any]], *extra: str | None) -> str:
    return " ".join([*(str(p.get("basis_fr") or "") for p in pictures), *(e or "" for e in extra)])


def _bands(check: _Checker, row: Any, limits: dict[str, int], *, allow: str, extra: int = 0) -> tuple[dict[str, ComptoirText], list[str]]:
    texts: dict[str, ComptoirText] = {}
    whys: list[str] = []
    if not isinstance(row, dict):
        return texts, ["missing"]
    for band, limit in limits.items():
        line, why = rubriques.text(check, row.get(band), limit + extra, allow=allow)
        if line is None:
            whys.append(f"{band}:{why}")
        else:
            texts[band] = line
    return texts, whys


def _pictures(raw: Any, given: list[dict[str, Any]], check: _Checker) -> tuple[list[PhotoPicture], list[str]]:
    rows = {str(r.get("ref")): r for r in raw if isinstance(r, dict)} if isinstance(raw, list) else {}
    out: list[PhotoPicture] = []
    refusals: list[str] = []
    for picture in given[:MAX_PICTURES]:
        ref = str(picture.get("ref"))
        row = rows.get(ref)
        tag = f"photo:{ref}"
        if row is None:
            refusals.append(f"{tag}:missing")
            continue
        seen: list[ComptoirText] = []
        for index, item in enumerate(list(row.get("seen") or [])[:SEEN_MAX]):
            line, why = rubriques.text(check, item, SEEN_MAX_WORDS, allow=str(picture.get("basis_fr") or ""))
            why = why or (seen_problem(line, picture) if line is not None else None)
            if why:
                refusals.append(f"{tag}:seen:{index}:{why}")
                continue
            if line is not None and not any(nouns(s.fr) == nouns(line.fr) for s in seen):
                seen.append(line)
        if not seen:
            refusals.append(f"{tag}:seen:none")
            continue
        out.append(PhotoPicture(ref=ref, kind=picture["kind"], basis_fr=str(picture.get("basis_fr")), seen=seen))
    return out, refusals


def _caption(row: Any, role: str, dossier: EditorialDossier, check: _Checker, pictures: list[PhotoPicture],
             lead: PhotoPicture, allow: str) -> tuple[PhotoCaption | None, list[str]]:
    tag = f"photo:caption:{role}"
    claim = dossier.claims_by_id().get(str(row.get("claim_id") or "").strip())
    if claim is None:
        return None, [f"{tag}:claim_unknown"]
    refusals: list[str] = []
    wrong = right = distractor = None
    other_ref = None
    if role == "wrong":
        wrong, right, distractor = _value(row.get("wrong_fr")), _value(row.get("right_fr")), _value(row.get("distractor_fr"))
        if not 1 <= word_count(wrong) <= VALUE_MAX_WORDS:
            return None, [f"{tag}:wrong_length"]
        if contains(check.story, wrong) or any(contains(c.fr, wrong) for c in dossier.claims):
            return None, [f"{tag}:not_false"]
        if not right or not contains(claim.fr, right):
            return None, [f"{tag}:right_not_in_claim"]
        if ci(right) == ci(wrong) or contains(right, wrong) or contains(wrong, right):
            return None, [f"{tag}:right_is_wrong"]
        if (not distractor or not in_story(check.story, distractor) or ci(distractor) in {ci(right), ci(wrong)}
                or numeric(right) != numeric(distractor) or numeric(right) != numeric(wrong)):
            return None, [f"{tag}:distractor"]
    if role == "other":
        other_ref = str(row.get("picture") or "")
        if other_ref == lead.ref or other_ref not in {p.ref for p in pictures}:
            return None, [f"{tag}:picture"]
    texts, whys = _bands(check, row, CAPTION_MAX_WORDS, allow=_allow([], allow, wrong))
    refusals += [f"{tag}:{why}" for why in whys]
    claim_numbers = numbers(claim.fr)
    other = next((p for p in pictures if p.ref == other_ref), None)
    lead_only = [s for s in lead.seen if not (other and any(nouns(s.fr) == nouns(o.fr) for o in other.seen))]
    for band, line in texts.items():
        if role == "right" and not mentions(line.fr, lead.seen):
            refusals.append(f"{tag}:{band}:shows_nothing")
        elif role == "right" and (numbers(line.fr) - claim_numbers or not grounded(line.fr, claim.fr)):
            refusals.append(f"{tag}:{band}:not_the_claim")
        elif role == "wrong" and (not contains(line.fr, wrong) or contains(line.fr, right)):
            refusals.append(f"{tag}:{band}:wrong_not_in_caption")
        elif role == "wrong" and numbers(line.fr) - claim_numbers - numbers(wrong):
            refusals.append(f"{tag}:{band}:two_changes")
        elif role == "other" and (other is None or not mentions(line.fr, other.seen) or mentions(line.fr, lead_only)):
            refusals.append(f"{tag}:{band}:not_the_other_picture")
        elif role == "other" and numbers(line.fr) - numbers(check.story):
            refusals.append(f"{tag}:{band}:number_not_in_claims")
    fixed = None
    if role == "wrong":
        fixed_texts, whys = _bands(check, row.get("fixed"), CAPTION_MAX_WORDS, allow=allow, extra=FIXED_EXTRA_WORDS)
        refusals += [f"{tag}:fixed:{why}" for why in whys]
        for band, line in fixed_texts.items():
            if not contains(line.fr, right) or contains(line.fr, wrong) or numbers(line.fr) - claim_numbers:
                refusals.append(f"{tag}:fixed:{band}:not_true")
        if len(fixed_texts) == 3:
            fixed = BandTexts(**fixed_texts)
    why_line = None
    if role != "right":
        why_line, why = rubriques.text(check, row.get("why"), WHY_MAX_WORDS, allow=_allow([], allow, wrong))
        if why_line is None:
            refusals.append(f"{tag}:why:{why}")
    if refusals or len(texts) < 3:
        return None, refusals or [f"{tag}:incomplete"]
    return PhotoCaption(role=role, claim_id=claim.id, picture=other_ref, why=why_line, wrong_fr=wrong,  # type: ignore[arg-type]
                        right_fr=right, distractor_fr=distractor, fixed=fixed, **texts), []


def _build(raw: Any, dossier: EditorialDossier, check: _Checker, wrong: str | None) -> tuple[PhotoBuild | None, list[str], list[str]]:
    if not isinstance(raw, dict):
        return None, ["photo:build:missing"], []
    refusals: list[str] = []
    problems: list[str] = []
    facts: list[ComptoirText] = []
    for index, row in enumerate(list(raw.get("facts") or [])[:4]):
        line, why = rubriques.text(check, row, FACT_MAX_WORDS)
        if line is not None:
            if address_problem(line.fr, ROMY_ID) or "!" in line.fr or "?" in line.fr:
                why = "vocative"
            elif wrong and contains(line.fr, wrong):
                why = "wrong_fact"
            elif not any(grounded(line.fr, c.fr) for c in dossier.claims):
                why = "ungrounded"
        if why:
            refusals.append(f"photo:build:fact:{index}:{why}")
            continue
        fr = line.fr.rstrip(" .") + "."  # type: ignore[union-attr]
        facts.append(line.model_copy(update={"fr": fr}))  # type: ignore[union-attr]
    if len(facts) < 2:
        refusals.append("photo:build:count")
    if refusals:
        return None, refusals, []
    frame, why = rubriques.text(check, raw.get("frame"), FRAME_MAX_WORDS)
    if frame is None:
        problems.append(f"photo:build:frame:{why}")
        frame = _t("Au premier plan, on voit", "In the foreground, you can see", "Im Vordergrund sieht man")
    frame = frame.model_copy(update={"fr": frame.fr.rstrip(" .…")})
    return PhotoBuild(facts=facts, frame=frame), [], problems


def repair_photo(raw: Any, dossier: EditorialDossier, pictures: list[dict[str, Any]] | None = None
                 ) -> tuple[PhotoDesk | None, list[str]]:
    """What the photo desk wrote about ``pictures`` (``story_pictures``), checked against
    ``dossier``. ``(None, ["skip"])`` for an unfit story; ``(None, problems)`` when it is
    refused; else the desk's work and what fell back to authored lines."""

    if not isinstance(raw, dict):
        return None, ["photo:missing"]
    if str(raw.get("fit") or "").strip().lower() == "skip":
        return None, ["skip"]
    given = list(pictures or [])
    if len(given) < MIN_PICTURES:
        return None, ["photo:pictures:too_few"]
    check = _Checker(dossier)
    shown, refusals = _pictures(raw.get("pictures"), given, check)
    if refusals:
        return None, refusals
    lead = next((p for p in shown if p.ref == str(raw.get("lead") or "")), None)
    if lead is None:
        return None, ["photo:lead:unknown"]
    if len(lead.seen) < LEAD_SEEN_MIN:
        return None, ["photo:lead:shows_too_little"]
    for other in shown:
        if other.ref != lead.ref and any(nouns(s.fr) == nouns(o.fr) for s in lead.seen for o in other.seen):
            return None, ["photo:lead:shared_thing"]
    rows = raw.get("captions")
    if not isinstance(rows, list) or len(rows) != 3 or not all(isinstance(r, dict) for r in rows):
        return None, ["photo:captions:count"]
    if sorted(str(r.get("role") or "") for r in rows) != sorted(PHOTO_CAPTION_ROLES):
        return None, ["photo:captions:roles"]
    allow = _allow(given)
    captions: list[PhotoCaption] = []
    for row in rows:
        caption, refused = _caption(row, str(row.get("role")), dossier, check, shown, lead, allow)
        refusals += refused
        if caption is not None:
            captions.append(caption)
    wrong = next((c.wrong_fr for c in captions if c.role == "wrong"), None)
    build, refused, problems = _build(raw.get("build"), dossier, check, wrong)
    refusals += refused
    if refusals:
        return None, [*refusals, *problems]
    for band in CAPTION_MAX_WORDS:
        if len({ci(c.for_band(band).fr) for c in captions}) < 3:
            return None, ["photo:captions:duplicate", *problems]
    phrase: dict[str, ComptoirText] = {}
    raw_phrase = raw.get("phrase") if isinstance(raw.get("phrase"), dict) else {}
    for band in ("a1", "a2", "b1", "b2"):
        line, why = check.text(raw_phrase.get(band), PHRASE_MAX_WORDS)
        if line is None:
            problems.append(f"photo:phrase:{band}:{why}")
        phrase[band] = line or getattr(AUTHORED_PHRASE, band)
    order = {role: i for i, role in enumerate(PHOTO_CAPTION_ROLES)}
    captions.sort(key=lambda c: order[c.role])
    return PhotoDesk(pictures=shown, lead=lead.ref, captions=captions, build=build,  # type: ignore[arg-type]
                     phrase=ComptoirPhrase(**phrase)), problems


def as_desk_answer(desk: PhotoDesk) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """``desk`` in the desk's answer shape and the pictures it was given, so :func:`audit`
    runs the same checks on stored or hand-written work."""

    data = desk.model_dump(mode="json")
    pictures = [{"ref": p["ref"], "kind": p["kind"], "basis_fr": p["basis_fr"], "basis_en": ""} for p in data["pictures"]]
    answer = {"fit": "photo", "lead": data["lead"], "build": data["build"], "phrase": data["phrase"],
              "pictures": [{"ref": p["ref"], "seen": p["seen"]} for p in data["pictures"]],
              "captions": [{k: v for k, v in row.items() if v is not None} for row in data["captions"]]}
    return answer, pictures


def audit(desk: PhotoDesk, dossier: EditorialDossier, pictures: list[dict[str, Any]] | None = None) -> list[str]:
    """Every check :func:`repair_photo` would make on ``desk`` (``pictures``: the gallery it was
    written against; by default its own pictures' basis): ``[]`` when nothing would change."""

    answer, own = as_desk_answer(desk)
    repaired, problems = repair_photo(answer, dossier, pictures if pictures is not None else own)
    return problems if repaired is not None else problems or ["photo:refused"]


# ---------------------------------------------------------------------------
# The desk
# ---------------------------------------------------------------------------


class _WithPictures:
    """The provider, asked with the story's pictures in its INPUT."""

    def __init__(self, provider: Any, pictures: list[dict[str, Any]]) -> None:
        self.provider = provider
        self.pictures = [{k: p.get(k) for k in ("ref", "kind", "basis_fr", "basis_en")} for p in pictures]
        self.model = getattr(provider, "model", "")

    def ask_json(self, instructions: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        return self.provider.ask_json(instructions, {**payload, "pictures": self.pictures}, **kwargs)


def write_photo(dossier: EditorialDossier, provider: Any = None, *, pictures: list[dict[str, Any]] | None = None
                ) -> tuple[PhotoDesk | None, list[str]]:
    """The photo desk: one JSON call (a second with the problems), checked by
    :func:`repair_photo`. Fewer than two pictures: no call, asked again tomorrow."""

    given = list(pictures or [])[:MAX_PICTURES]
    if len(given) < MIN_PICTURES:
        return None, ["photo:desk_failed"]
    provider = provider if provider is not None else rubriques.desk_provider("openai-revue-photo-desk")
    return rubriques.ask_desk(dossier, _WithPictures(provider, given), key="photo",
                              instructions=PHOTO_DESK_INSTRUCTIONS,
                              repair=lambda raw, d: repair_photo(raw, d, given),
                              prompt_version=PHOTO_PROMPT_VERSION)


def _evergreen(dossier_id: str) -> PhotoDesk | None:
    from app.services.revue.evergreen import evergreen_photo  # noqa: PLC0415

    return evergreen_photo(dossier_id)


def ensure_photo(db: Any, period: str, *, provider: Any = None) -> list[str]:
    """Each morning, once per kiosk row with two pictures (``rubriques.ensure_desk``)."""

    return rubriques.ensure_desk(db, period, key="photo",
                                 write=lambda dossier, given: write_photo(dossier, given,
                                                                          pictures=story_pictures(db, dossier)),
                                 evergreen=_evergreen, provider=provider)


def photo_of(dossier: EditorialDossier) -> PhotoDesk | None:
    """The photo desk a session on ``dossier`` plays: the dossier's own, else the evergreen's
    (unbound: :func:`bind` ties it to the gallery)."""

    return rubriques.material_of(dossier, "photo", _evergreen)


__all__ = [
    "PHOTO_DESK_INSTRUCTIONS",
    "PHOTO_PROMPT_VERSION",
    "audit",
    "bind",
    "ensure_photo",
    "mentions",
    "nouns",
    "photo_of",
    "repair_photo",
    "seen_problem",
    "story_pictures",
    "write_photo",
]
