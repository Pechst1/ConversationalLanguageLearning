"""«La photo» and «Le micro» (owner 2026-11-21): their desks (``photo.py``, ``micro.py``) and the
interview's deterministic matcher.

«La photo»: a ``seen`` word for a Commons photo outside its stored subject and caption is
refused; a caption whose «wrong» fact is in a claim is refused; the «other» caption describes
another picture; the desk needs two pictures (no call with fewer, asked again tomorrow) and is
asked with them; a gallery that changed unbinds it. «Le micro»: an answer line with a number
(or a name) its own claim lacks is refused; the witness is the comptoir's topic guest; a tile
the matcher would send to another fact is refused; the shrug states nothing. The matcher:
every question word, paraphrases, the shrug, ambiguity. One retry; a sensitive story never
asked; the morning writes each once; the shipped evergreens pass.
"""

from __future__ import annotations

import copy
from collections.abc import Generator

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.models.revue_session import RevueDossier
from app.services.revue import micro, photo
from app.services.revue.dossier import EditorialDossier
from app.services.revue.evergreen import evergreen_micro, evergreen_photo, load_evergreens

FETE = "evergreen-fete-de-la-musique"
BAC = "evergreen-bac"
WEEK = "2026-W25"


def dossier(dossier_id: str = FETE, **update: object) -> EditorialDossier:
    base = next(d for d in load_evergreens() if d.id == dossier_id).model_dump(mode="json")
    base.update({"evergreen": False, "comptoir": None, **update})
    return EditorialDossier.model_validate(base)


def gallery(dossier_id: str = FETE) -> list[dict]:
    """The pictures the evergreen's photo desk was written against, as ``story_pictures`` gives them."""

    desk = evergreen_photo(dossier_id)
    return [{"ref": p.ref, "kind": p.kind, "basis_fr": p.basis_fr, "basis_en": "", "url": f"https://example.org/{p.ref}.jpg",
             "credit_fr": "Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons", "licence": "CC BY-SA 4.0",
             "licence_url": "https://creativecommons.org/licenses/by-sa/4.0/", "source_url": None, "width": 1280,
             "height": 853} for p in desk.pictures]


def photo_answer(dossier_id: str = FETE) -> dict:
    answer, _ = photo.as_desk_answer(evergreen_photo(dossier_id))
    return answer


def micro_answer(dossier_id: str = FETE) -> dict:
    return micro.as_desk_answer(evergreen_micro(dossier_id))


class _Desk:
    def __init__(self, answers: list) -> None:
        self.answers = list(answers)
        self.calls: list[dict] = []
        self.model = "fake-desk"

    def ask_json(self, instructions: str, payload: dict, **_: object) -> dict:
        self.calls.append(payload)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return copy.deepcopy(answer)


# ---------------------------------------------------------------------------
# «La photo»
# ---------------------------------------------------------------------------


def test_the_shipped_photo_desks_pass_and_bind_only_to_their_gallery() -> None:
    for dossier_id in (FETE, BAC):
        made, problems = photo.repair_photo(photo_answer(dossier_id), dossier(dossier_id), gallery(dossier_id))
        assert made is not None and problems == [], (dossier_id, problems)
        bound = photo.bind(made, gallery(dossier_id))
        assert bound is not None and all(p.url and p.credit_fr for p in bound.pictures)
    desk = evergreen_photo(FETE)
    changed = [dict(p, basis_fr="Lyon · Lyon") if p["ref"] == "photo-1" else p for p in gallery()]
    assert photo.bind(desk, changed) is None, "a gallery whose photo changed unbinds the desk"
    assert photo.bind(desk, gallery()[:1]) is None, "one picture is not «La photo»"
    assert photo.bind(desk, []) is None


def test_a_seen_word_for_a_commons_photo_outside_its_subject_and_caption_is_refused() -> None:
    raw = photo_answer()
    guitar = next(p for p in raw["pictures"] if p["ref"] == "photo-2")
    guitar["seen"].append({"fr": "une scène", "en": "a stage", "de": "eine Bühne"})  # plausible, never stated
    made, problems = photo.repair_photo(raw, dossier(), gallery())
    assert made is None and "photo:photo-2:seen:2:seen_not_in_basis" in problems
    raw = photo_answer()
    next(p for p in raw["pictures"] if p["ref"] == "photo-1")["seen"] = [{"fr": "la tour Eiffel", "en": "the Eiffel Tower",
                                                                         "de": "der Eiffelturm"}]
    made, problems = photo.repair_photo(raw, dossier(), gallery())
    assert made is None and any(p.startswith("photo:photo-1:seen:0:") for p in problems), "a photo of «Paris» is Paris"
    line = photo.ComptoirText(fr="une guitare", en="a guitar", de="eine Gitarre")
    assert photo.seen_problem(line, {"kind": "photo", "basis_fr": "guitare acoustique vue de face"}) is None
    assert photo.seen_problem(line, {"kind": "photo", "basis_fr": "Paris · Paris"}) == "seen_not_in_basis"
    # an illustration may be read from the painter's English brief
    drum = photo.ComptoirText(fr="une batterie", en="a drum kit", de="ein Schlagzeug")
    assert photo.seen_problem(drum, {"kind": "illustration", "basis_fr": "", "basis_en": "an empty stage with a drum kit"}) is None
    assert photo.seen_problem(drum, {"kind": "photo", "basis_fr": "", "basis_en": "an empty stage with a drum kit"})


def test_a_caption_whose_wrong_fact_is_in_a_claim_is_refused() -> None:
    raw = photo_answer()
    wrong = next(c for c in raw["captions"] if c["role"] == "wrong")
    wrong["wrong_fr"] = "en 1982"  # true: c1 says it
    for band in ("a1", "a2", "b1"):
        wrong[band]["fr"] = wrong[band]["fr"].replace("le 14 juillet", "en 1982")
    made, problems = photo.repair_photo(raw, dossier(), gallery())
    assert made is None and "photo:caption:wrong:not_false" in problems
    raw = photo_answer()
    wrong = next(c for c in raw["captions"] if c["role"] == "wrong")
    wrong["right_fr"] = "le 22 juin"
    made, problems = photo.repair_photo(raw, dossier(), gallery())
    assert made is None and "photo:caption:wrong:right_not_in_claim" in problems


def test_the_other_caption_describes_another_picture_and_the_right_one_shows_the_lead() -> None:
    raw = photo_answer()
    other = next(c for c in raw["captions"] if c["role"] == "other")
    other["a1"]["fr"] = "Une guitare et la Fête de la musique."  # the lead's thing: not the other picture
    made, problems = photo.repair_photo(raw, dossier(), gallery())
    assert made is None and "photo:caption:other:a1:not_the_other_picture" in problems
    raw = photo_answer()
    right = next(c for c in raw["captions"] if c["role"] == "right")
    right["a1"]["fr"] = "La fête est gratuite."  # names nothing the picture shows
    made, problems = photo.repair_photo(raw, dossier(), gallery())
    assert made is None and "photo:caption:right:a1:shows_nothing" in problems
    raw = photo_answer()
    raw["lead"] = "photo-1"  # «Paris» shows one thing only
    made, problems = photo.repair_photo(raw, dossier(), gallery())
    assert made is None and problems == ["photo:lead:shows_too_little"]


def test_the_tiles_carry_no_vocative_and_no_number_the_claims_lack() -> None:
    raw = photo_answer()
    raw["build"]["facts"][0]["fr"] = "Viens vite, la fête est gratuite !"
    made, problems = photo.repair_photo(raw, dossier(), gallery())
    assert made is None and "photo:build:fact:0:vocative" in problems
    raw = photo_answer()
    raw["build"]["facts"][1]["fr"] = "La fête a 50 scènes."
    made, problems = photo.repair_photo(raw, dossier(), gallery())
    assert made is None and "photo:build:fact:1:number_not_in_claims" in problems


def test_the_photo_desk_needs_two_pictures_is_asked_with_them_and_retries_once() -> None:
    desk = _Desk([photo_answer()])
    assert photo.write_photo(dossier(), desk, pictures=gallery()[:1]) == (None, ["photo:desk_failed"])
    assert desk.calls == [], "no call with one picture: asked again tomorrow"
    broken = photo_answer()
    broken["lead"] = "photo-9"
    desk = _Desk([broken, photo_answer()])
    made, problems = photo.write_photo(dossier(), desk, pictures=gallery())
    assert made is not None and problems == []
    assert [p["ref"] for p in desk.calls[0]["pictures"]] == ["photo-1", "photo-2"]
    assert set(desk.calls[0]["pictures"][0]) == {"ref", "kind", "basis_fr", "basis_en"}, "never a link or a credit"
    assert desk.calls[1]["retry_feedback"]["problems"] == ["photo:lead:unknown"]
    assert made.prompt_version == photo.PHOTO_PROMPT_VERSION and made.pictures[0].url is None, "bound at the deal"
    assert photo.write_photo(dossier(), _Desk([{"fit": "skip"}]), pictures=gallery()) == (None, ["skip"])


# ---------------------------------------------------------------------------
# «Le micro»
# ---------------------------------------------------------------------------


def test_the_shipped_interviews_pass_every_check() -> None:
    for dossier_id in (FETE, BAC):
        assert micro.audit(evergreen_micro(dossier_id), dossier(dossier_id)) == [], dossier_id
        assert evergreen_micro(dossier_id).witness == micro.witness_of(dossier(dossier_id))
    dumped = next(d for d in load_evergreens() if d.id == FETE).model_dump(mode="json")
    assert "micro" not in dumped and "photo" not in dumped, "never attached to the loaded evergreen"


def test_an_answer_line_with_a_number_its_claim_lacks_is_refused() -> None:
    raw = micro_answer()
    fact = raw["facts"][2]  # c2: the festival is free
    fact["answer"]["b1"]["fr"] = "Rien du tout : depuis 1982, la fête est gratuite."  # 1982 is c1's, not c2's
    made, problems = micro.repair_micro(raw, dossier())
    assert made is None and "micro:3:answer:b1:number_not_in_claim" in problems
    raw = micro_answer()
    raw["facts"][0]["answer"]["a2"]["fr"] = "Le 21 juin 1982, avec Jack Lang, mon chou !"  # a name no claim gives
    made, problems = micro.repair_micro(raw, dossier())
    assert made is None and any(p.startswith("micro:1:answer:a2:name_not_in_claim") for p in problems)
    raw = micro_answer()
    raw["facts"][0]["answer"]["a1"]["fr"] = "C'est en été, mon chou !"  # does not say the value
    made, problems = micro.repair_micro(raw, dossier())
    assert made is None and "micro:1:answer:a1:value_not_said" in problems


def test_the_witness_tiles_and_shrug_are_checked() -> None:
    raw = micro_answer()
    raw["witness"] = "augustin_de_roncourt"
    assert micro.repair_micro(raw, dossier()) == (None, ["micro:witness"])
    raw = micro_answer()
    raw["facts"][1]["tile"]["fr"] = "Pourquoi est-ce qu'il y a des plaintes ?"  # another fact's question
    made, problems = micro.repair_micro(raw, dossier())
    assert made is None and "micro:2:tile:not_its_fact" in problems
    raw = micro_answer()
    raw["facts"][0]["tile"]["fr"] = "Lila, dis-moi la date !"
    made, problems = micro.repair_micro(raw, dossier())
    assert made is None and "micro:1:tile:not_a_plain_question" in problems
    raw = micro_answer()
    raw["shrug"]["a2"]["fr"] = "Ça, je ne sais pas. Il y avait 10 groupes, je crois."
    made, problems = micro.repair_micro(raw, dossier())
    assert made is None and problems and problems[0].startswith("micro:shrug:a2:")
    raw = micro_answer()
    raw["facts"][3]["keywords"] = ["jazz"]
    made, problems = micro.repair_micro(raw, dossier())
    assert made is None and "micro:4:keywords_not_in_claim" in problems


def test_the_interview_desk_is_asked_with_its_witness_and_retries_once() -> None:
    broken = micro_answer()
    broken["facts"] = broken["facts"][:3]
    desk = _Desk([broken, micro_answer()])
    made, problems = micro.write_micro(dossier(), desk)
    assert made is not None and problems == []
    assert desk.calls[0]["witness"]["id"] == "lila_bonnet" and desk.calls[0]["witness"]["sheet"]["speech_pattern"]
    assert desk.calls[1]["retry_feedback"]["problems"] == ["micro:facts:count"]
    assert micro.write_micro(dossier(), _Desk([{"fit": "skip"}])) == (None, ["skip"])
    assert micro.write_micro(dossier(), _Desk([RuntimeError("down")])) == (None, ["micro:desk_failed"])


# ---------------------------------------------------------------------------
# The matcher
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("question", "ask"), [
    ("Quand est-ce que la première fête a eu lieu ?", "quand"),
    ("C'est quand, la première fête ?", "quand"),
    ("Pourquoi est-ce qu'il y a des plaintes ?", "pourquoi"),
    ("Pourquoi les voisins se plaignent-ils ?", "pourquoi"),  # «se plaignent» / «plaintes»
    ("Combien coûte la fête ?", "combien"),
    ("Ça coûte combien ?", "combien"),
    ("Est-ce que la fête est gratuite ?", "combien"),  # no question word: the content words
    ("Quelles musiques est-ce qu'on peut écouter ?", "quoi"),
    ("Qu'est-ce qu'on écoute comme musiques ?", "quoi"),
    ("Comment est-ce que la première édition s'est passée ?", "comment"),
    ("Pourquoi est-ce que la fête a lieu le 21 juin ?", "pourquoi"),
])
def test_each_question_word_and_its_paraphrases_reach_their_fact(question: str, ask: str) -> None:
    facts = evergreen_micro(FETE).facts
    found = micro.match(question, facts, generic=micro.generic_words(dossier()))
    assert found["kind"] == "match", (question, found)
    assert facts[found["index"]].ask == ask


def test_the_matcher_shrugs_and_says_when_it_is_ambiguous() -> None:
    facts = evergreen_micro(FETE).facts
    generic = micro.generic_words(dossier())
    for question in ("Qui organise la fête ?", "Combien de musiciens jouent ?", "Où est la grande scène ?"):
        assert micro.match(question, facts, generic=generic)["kind"] == "none", question
    found = micro.match("Pourquoi la fête ?", facts, generic=generic)
    assert found["kind"] == "ambiguous" and sorted(facts[i].ask for i in found["candidates"]) == ["pourquoi", "pourquoi"]
    chosen = [found["candidates"][1]]
    assert micro.match("Pourquoi la fête ?", facts, chosen=chosen, generic=generic) == {
        "kind": "match", "index": chosen[0], "qword": "pourquoi"}, "the learner's own holes break the tie"
    bac = evergreen_micro(BAC).facts
    found = micro.match("Quand est le bac ?", bac, generic=micro.generic_words(dossier(BAC)))
    assert found["kind"] == "ambiguous" and {bac[i].ask for i in found["candidates"]} == {"quand"}


def test_formation_slips_are_collected_only_when_sure() -> None:
    facts = evergreen_micro(FETE).facts
    cost = next(f for f in facts if f.ask == "combien")
    assert micro.formation_slips("Pourquoi elle est gratuite ?", cost, "pourquoi") == ["inversion", "question_word"]
    assert micro.formation_slips("Combien coûte la fête ?", cost, "combien") == []
    assert micro.formation_slips("Combien est-ce qu'elle coûte ?", cost, "combien") == []
    assert micro.formation_slips("Combien coûte-t-elle ?", cost, "combien") == []
    assert micro.formation_slips("Est-ce que la fête est gratuite ?", cost, None) == [], "no question word: no slip"
    assert micro.is_question("La fête est gratuite ?") and not micro.is_question("La fête est gratuite.")


# ---------------------------------------------------------------------------
# The morning
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def revue_tables(db_engine) -> Generator[None, None, None]:
    created = not inspect(db_engine).has_table(RevueDossier.__table__.name)
    if created:
        RevueDossier.__table__.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        if created:
            RevueDossier.__table__.drop(bind=db_engine, checkfirst=True)


def _row(db: Session, story: EditorialDossier, period: str, **checks: str) -> RevueDossier:
    row = RevueDossier(id=f"{period}-{story.id}"[:120], week=WEEK, period=period, topic=story.topic,
                       payload=story.model_dump(mode="json"), source_hashes={}, checks=dict(checks),
                       builder_version="revue-builder-v3")
    db.add(row)
    db.commit()
    return row


def test_each_morning_writes_each_once_and_waits_for_two_pictures(db_session: Session, revue_tables, monkeypatch) -> None:
    db = db_session
    period = "2026-06-20"
    story = dossier(id="2026-06-20-la-fete-de-la-musique")
    sensitive = dossier(id="2026-06-20-un-drame")
    _row(db, story, period)
    _row(db, sensitive, period, comptoir="skip")
    desk = _Desk([micro_answer()])
    assert micro.ensure_micro(db, period, provider=desk) == [story.id]
    assert len(desk.calls) == 1, "the sensitive story is never asked"
    monkeypatch.setattr(photo, "story_pictures", lambda db, d: [])
    desk = _Desk([photo_answer()])
    assert photo.ensure_photo(db, period, provider=desk) == [] and desk.calls == []
    rows = {r.payload["id"]: r for r in db.scalars(select(RevueDossier).where(RevueDossier.period == period))}
    assert "photo" not in (rows[story.id].checks or {}), "no pictures yet: asked again tomorrow"
    monkeypatch.setattr(photo, "story_pictures", lambda db, d: gallery())
    assert photo.ensure_photo(db, period, provider=desk) == [story.id]
    rows = {r.payload["id"]: r for r in db.scalars(select(RevueDossier).where(RevueDossier.period == period))}
    assert rows[story.id].payload["micro"]["witness"] == "lila_bonnet"
    assert rows[story.id].payload["photo"]["lead"] == "photo-2"
    assert rows[sensitive.id].checks["micro"] == "skip" and rows[sensitive.id].checks["photo"] == "skip"
    assert micro.ensure_micro(db, period, provider=_Desk([])) == [], "once per row"
    assert photo.ensure_photo(db, period, provider=_Desk([])) == []
    stored = EditorialDossier.model_validate(rows[story.id].payload)
    assert micro.micro_of(stored) is not None and photo.photo_of(stored) is not None
