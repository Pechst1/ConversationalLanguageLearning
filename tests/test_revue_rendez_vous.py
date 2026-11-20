"""«Papier · les rendez-vous» (owner 2026-11-21): reasons to come back tomorrow.

Guards: «Trois mots» (selection, grading in two tries, no solution before the retry, the gap
sentence only from the story's own text, no double keep), the regulars' memory (lines only from
stored facts, never invented, never twice in a row, none without memory), «La une de la semaine»
(the editorial rule, printed text only, never another learner's, the empty week), «La carte de
presse», and every switch off = today's payloads byte for byte.
"""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_db
from app.api.v1.endpoints.revue import get_revue_provider
from app.config import settings
from app.db.models.npc import NPC, NPCMemory
from app.db.models.pilot_event import PilotEvent
from app.db.models.revue_session import RevueDossier, RevueSession
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.story import Story
from app.db.models.user import User
from app.main import create_app
from app.schemas.revue import RvRubriqueRequest
from app.schemas.revue_rendez_vous import RvTroisMotsRequest
from app.services.revue import comptoir, souvenirs, titre_loop, trois_mots, une
from app.services.revue import encounter as enc
from app.services.revue.encounter import FakeRevueProvider, RevueEncounter
from app.services.revue.evergreen import evergreen_titre, evergreens_for_week
from app.services.revue.pictogram import FakePictogramProvider
from app.services.revue.state import ConversationState

WEEK = "2026-W25"
FETE = "evergreen-fete-de-la-musique"
REVUE_TABLES = (Story.__table__, NPC.__table__, NPCMemory.__table__, RevueSession.__table__, RevueDossier.__table__,
                RevuePictogram.__table__, RevueVignette.__table__, PilotEvent.__table__)


@pytest.fixture(scope="module")
def revue_tables(db_engine) -> Generator[None, None, None]:
    created = [table for table in REVUE_TABLES if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def switches(monkeypatch) -> None:
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", True)
    comptoir.forget_cache()


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:
    return db_session


def Revue(db: Session) -> RevueEncounter:  # noqa: N802
    revue = RevueEncounter(db, FakeRevueProvider())
    revue.pictogram_provider = FakePictogramProvider()
    return revue


def make_user(db: Session, *, level: str = "A1.1", native: str = "en", played: tuple[str, ...] = ()) -> User:
    user = User(id=uuid.uuid4(), email=f"rdv-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
                cefr_estimate=level, native_language=native, interests="")
    db.add(user)
    db.commit()
    now = datetime.now(UTC)
    for index, mode in enumerate(played):
        payload = {"kind": "dossier", "dossier_id": "old", "mode": mode}
        db.add(RevueSession(id=uuid.uuid4(), user_id=user.id, week=f"2026-W{20 - index}", dossier_id="old", plan={},
                            state={"events": [{"seq": 1, "at": now.isoformat(), "kind": "choice", "payload": payload}]},
                            status="closed", started_at=now - timedelta(days=60 + index),
                            closed_at=now - timedelta(days=60 + index)))
    db.commit()
    return user


def act(revue: RevueEncounter, row: RevueSession, **body):
    return revue.rubrique(row, RvRubriqueRequest(**body))


def closed_titre(db: Session, user: User | None = None) -> tuple[RevueEncounter, RevueSession]:
    """A «Le titre» session played at A1 (tiles, no model call) and closed."""

    revue = Revue(db)
    user = user or make_user(db, played=("comptoir", "intox"))
    row = revue.start(user, week=WEEK, dossier_id=FETE)
    assert revue.view(row).mode == "titre"
    desk = evergreen_titre(FETE)
    keys = titre_loop.key_of(str(row.id))
    act(revue, row, act="open")
    act(revue, row, act="pick", key=keys[titre_loop.role_index(desk, "honest")])
    text = desk.headline("exaggerated").for_band("A1").fr
    act(revue, row, act="trap", words=titre_loop.wrong_span(text, desk.wrong_fr))
    act(revue, row, act="build", parts=[0, 0])
    revue.close(row)
    return revue, row


def set_kept(db: Session, row: RevueSession, change) -> list[dict]:
    """Rewrite the stored close's kept words (a copy: the JSON column sees the change)."""

    state = copy.deepcopy(row.state)
    closed = next(e for e in state["events"] if e["kind"] == "closed")
    words = change(closed["payload"]["closing"]["kept"]["words"])
    closed["payload"]["closing"]["kept"]["words"] = words
    row.state = state
    flag_modified(row, "state")
    db.commit()
    return words


def state_of(row: RevueSession) -> ConversationState:
    return ConversationState.from_json(row.state)


# ---------------------------------------------------------------------------
# 3 · «Trois mots»
# ---------------------------------------------------------------------------


def test_no_round_before_the_close(db: Session) -> None:
    revue = Revue(db)
    row = revue.start(make_user(db, played=("comptoir", "intox")), week=WEEK, dossier_id=FETE)
    assert trois_mots.build(enc.load(row)) is None


def test_the_three_words_are_the_kept_ones_first_and_nothing_says_the_answer_before_it_is_resolved(db: Session) -> None:
    _, row = closed_titre(db)
    loaded = enc.load(row)
    closing = enc._closing_of(loaded.state)  # noqa: SLF001
    round_ = trois_mots.build(loaded)
    assert round_ is not None
    kept = [w.fr for w in sorted(closing.kept.words, key=lambda w: not w.used)]
    assert [w.fr for w in round_.words] == kept[:3] and all(w.kept for w in round_.words)
    view = trois_mots.view(loaded, round_)
    assert view.step == "match" and view.match.solution is None and all(w.gloss is None for w in view.words)
    assert {c.text for c in view.cues} == {w.gloss for w in round_.words}, "a gloss in the mother tongue for each"
    assert [c.text for c in view.cues] != [w.gloss for w in round_.words], "cue 1 is never word a's"
    text = json.dumps(view.model_dump(mode="json"), ensure_ascii=False)
    assert "answer" not in text and "solution\": {" not in text


def test_the_match_takes_two_tries_says_which_pairs_were_wrong_and_shows_the_solution_only_after(db: Session, monkeypatch) -> None:
    revue, row = closed_titre(db)
    calls: list[list[str]] = []  # from here on: the close has kept its words
    monkeypatch.setattr("app.services.revue.carte.keep_papier_words",
                        lambda db, row, **kw: calls.append([w.fr for w in kw["kept"].words]) or 0)
    loaded = enc.load(row)
    round_ = trois_mots.build(loaded)
    right = {trois_mots.WORD_KEYS[i]: key for i, key in round_.answer.items()}
    wrong = dict(right)
    wrong["a"], wrong["b"] = right["b"], right["a"]
    assert trois_mots.act(revue, loaded, RvTroisMotsRequest(act="match", pairs={"a": "1"})).error == "pair_all"
    result = trois_mots.act(revue, enc.load(row), RvTroisMotsRequest(act="match", pairs=wrong))
    view = result.round
    assert view.match.tries == 1 and not view.match.resolved and view.match.solution is None
    assert {m.word_key for m in view.match.misses} == {"a", "b"} and all(w.gloss is None for w in view.words)
    view = trois_mots.act(revue, enc.load(row), RvTroisMotsRequest(act="match", pairs=wrong)).round
    assert view.match.resolved and view.match.correct is False and view.match.solution == right
    assert all(w.gloss for w in view.words), "the glosses once resolved"
    again = trois_mots.act(revue, enc.load(row), RvTroisMotsRequest(act="match", pairs=right))
    assert again.error == "out_of_order" and again.round.match.tries == 2, "never a third try"
    assert calls == [], "the three were kept at the close: never kept twice"


def test_a_right_match_first_time(db: Session) -> None:
    revue, row = closed_titre(db)
    round_ = trois_mots.build(enc.load(row))
    right = {trois_mots.WORD_KEYS[i]: key for i, key in round_.answer.items()}
    view = trois_mots.act(revue, enc.load(row), RvTroisMotsRequest(act="match", pairs=right)).round
    assert view.match.resolved and view.match.correct is True and view.match.misses == []
    assert view.step == ("gap" if view.gap is not None else "done")


def test_words_the_close_did_not_keep_are_kept_once_through_the_close_path(db: Session, monkeypatch) -> None:
    revue, row = closed_titre(db)
    calls: list[list[str]] = []  # from here on: the close has kept its words
    monkeypatch.setattr("app.services.revue.carte.keep_papier_words",
                        lambda db, row, **kw: calls.append([w.fr for w in kw["kept"].words]) or 0)
    # The close kept one word only: the round takes two of the plan's target words.
    first = set_kept(db, row, lambda words: words[:1])[0]
    round_ = trois_mots.build(enc.load(row))
    assert round_.words[0].fr == first["fr"] and round_.words[0].kept and not round_.words[1].kept
    right = {trois_mots.WORD_KEYS[i]: key for i, key in round_.answer.items()}
    view = trois_mots.act(revue, enc.load(row), RvTroisMotsRequest(act="match", pairs=right)).round
    assert calls == [[round_.words[1].fr, round_.words[2].fr]] and view.kept_now == 2
    plan_words = {v.fr for v in enc.load(row).plan.vocabulary}
    assert set(calls[0]) <= plan_words, "the dossier's target words at the learner's band"


def test_the_gap_sentence_is_the_story_s_own_text_with_the_word_taken_out(db: Session) -> None:
    dossier = next(d for d in evergreens_for_week(WEEK) if d.id == FETE)
    words = [trois_mots.Word(fr=fr, bare=trois_mots.bare(fr), gloss=g, claim_id="c1", kept=True)
             for fr, g in (("les voisins", "neighbours"), ("la fête", "party"), ("le bruit", "noise"))]
    gap = trois_mots.gap_for(words, dossier, "A1")
    lead = dossier.lead_for("A1").fr
    assert gap is not None and gap.sentence in lead, "a sentence of the lead, never invented"
    assert gap.before + words[gap.index].bare + gap.after == gap.sentence or \
        (gap.before + gap.sentence[len(gap.before):len(gap.sentence) - len(gap.after)] + gap.after) == gap.sentence
    removed = gap.sentence[len(gap.before):len(gap.sentence) - len(gap.after)]
    assert trois_mots._fold(removed) == trois_mots._fold(words[gap.index].bare)  # noqa: SLF001
    others = [w for i, w in enumerate(words) if i != gap.index]
    assert all(trois_mots.find_word(gap.sentence, w.bare) is None for w in others), "only one word fits"
    none = [trois_mots.Word(fr=f, bare=f, gloss="x", claim_id="c1", kept=True) for f in ("zèbre", "girafe", "okapi")]
    assert trois_mots.gap_for(none, dossier, "A1") is None, "no sentence: no gap (never invented)"


def test_the_gap_round_two_tries_explains_a_miss_with_the_picked_word_s_meaning(db: Session) -> None:
    revue, row = closed_titre(db)
    set_kept(db, row, lambda _: [
        {"fr": "la fête", "gloss": "party", "claim_id": "c1", "used": False},
        {"fr": "le bruit", "gloss": "noise", "claim_id": "c3", "used": False},
        {"fr": "les rues", "gloss": "streets", "claim_id": "c1", "used": False},
    ])
    round_ = trois_mots.build(enc.load(row))
    assert round_.gap is not None and round_.gap.source == "lead"
    right = {trois_mots.WORD_KEYS[i]: key for i, key in round_.answer.items()}
    early = trois_mots.act(revue, enc.load(row), RvTroisMotsRequest(act="gap", word="a"))
    assert early.error == "out_of_order", "the gap waits for the match"
    view = trois_mots.act(revue, enc.load(row), RvTroisMotsRequest(act="match", pairs=right)).round
    assert view.step == "gap" and view.gap.solution is None and view.gap.sentence_fr is None
    answer = trois_mots.WORD_KEYS[round_.gap.index]
    wrong = next(k for k in trois_mots.WORD_KEYS if k != answer)
    view = trois_mots.act(revue, enc.load(row), RvTroisMotsRequest(act="gap", word=wrong)).round
    assert not view.gap.resolved and view.gap.solution is None and view.gap.sentence_fr is None
    assert view.gap.miss.word_key == wrong and view.gap.miss.gloss == round_.words[trois_mots.WORD_KEYS.index(wrong)].gloss
    view = trois_mots.act(revue, enc.load(row), RvTroisMotsRequest(act="gap", word=answer)).round
    assert view.gap.resolved and view.gap.correct and view.gap.solution == answer and view.step == "done"
    assert view.gap.sentence_fr in enc.load(row).dossier.lead_for("A1").fr


def test_a_picture_is_the_cue_when_it_names_the_word() -> None:
    from types import SimpleNamespace

    from app.schemas.revue import RvPicture

    words = [trois_mots.Word(fr=f, bare=trois_mots.bare(f), gloss="g", claim_id="c1", kept=True)
             for f in ("la scène", "le kiosque", "les voisins")]
    photo = RvPicture(kind="photo", url="p.jpg", caption_fr="Le kiosque à musique du jardin", credit_fr="Photo · X")
    painted = RvPicture(kind="illustration", url="i.png", credit_fr="Illustration · Le Papier")
    dossier = SimpleNamespace(visual=SimpleNamespace(words=[SimpleNamespace(fr="la scène")]))
    cues = trois_mots.picture_cues(words, dossier, [painted, photo])
    assert cues == {0: painted, 1: photo}, "the painted picture shows its brief's words; a caption names one"


# ---------------------------------------------------------------------------
# 2 · The regulars remember
# ---------------------------------------------------------------------------


def _row(db: Session, user: User, *, mode: str, days_ago: float, band: str = "A2", topic: str = "culture",
         artifact: dict | None = None, closing: dict | None = None, status: str | None = None) -> RevueSession:
    when = datetime.now(UTC) - timedelta(days=days_ago)
    events = [{"seq": 1, "at": when.isoformat(), "kind": "choice",
               "payload": {"kind": "dossier", "dossier_id": "old", "mode": mode, "snapshot": {"topic": topic, "title_fr": "Une histoire"}}}]
    if artifact is not None:
        events.append({"seq": 2, "at": when.isoformat(), "kind": "artifact", "payload": artifact})
        events.append({"seq": 3, "at": when.isoformat(), "kind": "closed", "payload": {"closing": closing or {}}})
    row = RevueSession(id=uuid.uuid4(), user_id=user.id, week="2026-W47", dossier_id="old",
                       plan={"learner": {"band": band}}, state={"events": events},
                       status=status or ("closed" if artifact is not None else "active"),
                       started_at=when - timedelta(minutes=8), closed_at=when if artifact is not None else None)
    db.add(row)
    db.commit()
    return row


def _counter(stance: str, sides: dict[str, str]) -> tuple[dict, dict]:
    artifact = {"kind": "opinion", "text_fr": "C'est une bonne idée.", "learner_fr": "c une bone idee", "stance": stance,
                "proof": "corrected"}
    closing = {"comptoir_page": {"quotes": [{"cast_id": c, "stance": s} for c, s in sides.items()]}}
    return artifact, closing


def test_no_line_without_memory(db: Session) -> None:
    user = make_user(db)
    row = _row(db, user, mode="comptoir", days_ago=0)
    assert souvenirs.line_for(db, row) is None, "a first Papier: nothing to remember"
    _row(db, user, mode="titre", days_ago=3, status="abandoned")
    assert souvenirs.line_for(db, row) is None, "an abandoned Papier filed nothing"


def test_gus_remembers_the_learner_was_against_him(db: Session) -> None:
    user = make_user(db)
    gus, romy = comptoir.GUS_ID, comptoir.ROMY_ID
    artifact, closing = _counter("contre", {romy: "nuance", "lila_bonnet": "contre", gus: "pour"})
    past = _row(db, user, mode="comptoir", days_ago=2, artifact=artifact, closing=closing, band="A1")
    lines = set()
    for _ in range(12):  # every session draws its own template: look at several
        row = _row(db, user, mode="comptoir", days_ago=0, band="A1")
        line = souvenirs.line_for(db, row)
        db.delete(row)
        db.commit()
        assert line is not None and line.about_session_id == str(past.id)
        lines.add((line.template_id, line.speaker_id, line.fr))
        if line.template_id.startswith("opinion.contre_moi"):
            assert line.speaker_id == gus and line.fr == "La dernière fois, tu étais contre moi. Et aujourd'hui ?"
        if line.template_id.startswith("opinion.avec_moi"):
            assert line.speaker_id == "lila_bonnet" or line.speaker_id not in (gus, romy), "an ally sat on the same side"
    assert any(t.startswith("opinion.contre_moi") for t, _, _ in lines)


def _claims_hold(line, facts: dict) -> None:
    """The pilot's rule: every slot of the line is a stored fact of this learner."""

    if line.fact == "stance":
        stance = facts["stance"]
        if "contre moi" in line.fr or "pas d'accord avec moi" in line.fr or "tenu tête" in line.fr:
            assert facts["sides"][line.speaker_id] == {"pour": "contre", "contre": "pour"}[stance]
        if "d'accord avec moi" in line.fr and "pas d'accord" not in line.fr or "de mon côté" in line.fr:
            assert facts["sides"][line.speaker_id] == stance
        if "ça dépend" in line.fr or "aucun camp" in line.fr or "trancher" in line.fr:
            assert stance == "nuance"
    if line.fact == "headline":
        assert facts["headline_proof"] in souvenirs.QUOTABLE_PROOFS
        if "«" in line.fr:
            assert facts["headline"] in line.fr
    if line.fact == "intox_score":
        assert f"{facts['score']} sur 5" in line.fr and facts["score"] >= 3
    if line.fact == "count":
        assert str(facts["count"]) in line.fr


def test_every_line_says_only_what_the_learner_did(db: Session) -> None:
    gus, romy = comptoir.GUS_ID, comptoir.ROMY_ID
    for band in ("A1", "A2", "B1"):
        for mode in ("comptoir", "titre", "intox", "fil"):
            for stance in ("pour", "contre", "nuance"):
                user = make_user(db)
                sides = {romy: "pour", "lila_bonnet": "nuance", gus: "contre"}
                artifact, closing = _counter(stance, sides)
                _row(db, user, mode="comptoir", days_ago=5, artifact=artifact, closing=closing)
                _row(db, user, mode="titre", days_ago=4, artifact={"kind": "titre", "text_fr": "La fête est gratuite",
                                                                     "learner_fr": "", "proof": "clean"})
                _row(db, user, mode="intox", days_ago=3, artifact={"kind": "intox", "text_fr": "4 sur 5", "score": 4},
                     closing={"intox_page": {"total": 5}})
                _row(db, user, mode="fil", days_ago=1, artifact={"kind": "fil", "text_fr": "D'abord…", "proof": "fixed"})
                row = _row(db, user, mode=mode, days_ago=0, band=band)
                line = souvenirs.line_for(db, row)
                assert line is not None and line.template_id.endswith(band.lower())
                _claims_hold(line, {"stance": stance, "sides": sides, "headline": "La fête est gratuite",
                                    "headline_proof": "clean", "score": 4, "count": 4})
                assert line.en and line.de and "{" not in line.fr + line.en + line.de


def test_a_headline_printed_unchecked_and_a_low_score_are_not_spoken_of(db: Session) -> None:
    user = make_user(db)
    _row(db, user, mode="titre", days_ago=2, artifact={"kind": "titre", "text_fr": "Tout le monde adore", "proof": "as_written"})
    _row(db, user, mode="intox", days_ago=1, artifact={"kind": "intox", "text_fr": "1 sur 5", "score": 1})
    row = _row(db, user, mode="titre", days_ago=0)
    line = souvenirs.line_for(db, row)
    assert line is None or line.fact not in {"headline", "intox_score"}, line
    memory = souvenirs.souvenirs_from([souvenirs.filed_of(r) for r in souvenirs.history(db, user.id) if souvenirs.filed_of(r)])
    assert memory.headline is None, "as_written: never quoted, never called honest"


def test_the_weekday_is_the_day_the_learner_filed(db: Session) -> None:
    when = datetime(2026, 11, 17, 10, 0, tzinfo=UTC)  # a Tuesday
    slot = souvenirs.quand(when, datetime(2026, 11, 20, 9, 0, tzinfo=UTC))
    assert slot == {"fr": "Mardi", "en": "On Tuesday", "de": "Am Dienstag"}
    assert souvenirs.quand(when, datetime(2026, 11, 18, 9, 0, tzinfo=UTC))["fr"] == "Hier"
    assert souvenirs.quand(when, datetime(2027, 1, 20, tzinfo=UTC)) is None, "too old to speak of"


def test_the_same_line_never_twice_in_a_row(db: Session) -> None:
    user = make_user(db)
    _row(db, user, mode="titre", days_ago=20, artifact={"kind": "titre", "text_fr": "La fête est gratuite", "proof": "clean"})
    _row(db, user, mode="intox", days_ago=19, artifact={"kind": "intox", "text_fr": "5 sur 5", "score": 5})
    rows = [_row(db, user, mode="titre", days_ago=18 - i, artifact={"kind": "titre", "text_fr": "Un titre juste", "proof": "fixed"})
            for i in range(10)]
    said = [souvenirs.line_for(db, row) for row in rows]
    ids = [line.template_id for line in said if line is not None]
    assert len(ids) >= 8
    assert all(a != b for a, b in zip(ids, ids[1:], strict=False)), ids
    assert said == [souvenirs.line_for(db, row) for row in rows], "recomputed, the same lines (a reload says the same)"


def test_the_templates_are_authored_for_every_assignment_and_band() -> None:
    table = souvenirs.lines()["templates"]
    for kind in ("opinion", "fil", "titre", "intox"):
        for band in ("a1", "a2", "b1"):
            rows = [t for t in table if t["mode"] == kind and t["band"] == band]
            assert 4 <= len(rows) <= 6, (kind, band)
            for t in rows:
                assert t["fr"] and t["en"] and t["de"]
                for slot in ("{Quand}", "{titre}", "{score}", "{total}", "{n}"):
                    assert (slot in t["fr"]) == (slot in t["en"]) == (slot in t["de"]), (t["id"], slot)
                for text in (t["fr"], t["en"], t["de"]):
                    assert "{Quand}" not in text or text.startswith("{Quand}"), "sentence-initial"


# ---------------------------------------------------------------------------
# 4 · «La une de la semaine», 5 · «La carte de presse»
# ---------------------------------------------------------------------------


def _filed(db: Session, user: User, *, at: datetime, artifact: dict, closing: dict | None = None,
           title: str = "Une histoire") -> RevueSession:
    events = [{"seq": 1, "at": at.isoformat(), "kind": "choice",
               "payload": {"kind": "dossier", "dossier_id": "x", "snapshot": {"title_fr": title}}},
              {"seq": 2, "at": at.isoformat(), "kind": "artifact", "payload": artifact},
              {"seq": 3, "at": at.isoformat(), "kind": "closed", "payload": {"closing": closing or {}}}]
    row = RevueSession(id=uuid.uuid4(), user_id=user.id, week="2026-W47", dossier_id="x", plan={},
                       state={"events": events}, status="closed", started_at=at, closed_at=at)
    db.add(row)
    db.commit()
    return row


def _week(db: Session, user: User) -> None:
    monday = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
    kept = lambda *w: {"kept": {"words": [{"fr": x, "gloss": "g", "claim_id": "c1", "used": False} for x in w]}}  # noqa: E731
    _filed(db, user, at=monday, artifact={"kind": "opinion", "text_fr": "À mon avis, c'est une très bonne nouvelle pour les musiciens.",
                                          "learner_fr": "a mon avi c une tres bone nouvel", "stance": "pour", "proof": "corrected"},
           closing=kept("la fête", "le bruit"), title="La Fête de la musique")
    _filed(db, user, at=monday + timedelta(days=1), artifact={"kind": "titre", "text_fr": "Le bac commence lundi",
                                                              "learner_fr": "le bac comence lundi", "proof": "fixed"},
           closing=kept("le bac"), title="Le bac 2026")
    _filed(db, user, at=monday + timedelta(days=2), artifact={"kind": "fil", "text_fr": "Raw draft never printed checked",
                                                              "learner_fr": "Raw draft never printed checked", "proof": "as_written"},
           closing=kept("la grève"))
    _filed(db, user, at=monday + timedelta(days=3), artifact={"kind": "intox", "text_fr": "4 sur 5, 1 intox corrigée", "score": 4},
           closing={"intox_page": {"total": 5, "lines": [{"learner_fr": "La fête a lieu le 21 juin.", "fixed_right": True},
                                                         {"learner_fr": None, "fixed_right": None}]}, **kept("la fête")})
    _filed(db, user, at=monday - timedelta(days=1), artifact={"kind": "titre", "text_fr": "Last week", "proof": "clean"})


def test_la_une_is_composed_only_from_the_learner_s_printed_pieces_of_the_week(db: Session) -> None:
    user, other = make_user(db), make_user(db)
    _week(db, user)
    _filed(db, other, at=datetime(2026, 11, 17, 9, tzinfo=UTC), artifact={"kind": "titre", "text_fr": "Someone else's", "proof": "clean"})
    page = une.une_semaine(db, user.id, "2026-W47", now=datetime(2026, 11, 22, 18, tzinfo=UTC))
    assert [i.rubrique for i in page.items] == ["titre", "opinion", "intox"], "a titre leads, then the longest text"
    assert page.items[0].role == "headline" and page.items[0].text_fr == "Le bac commence lundi"
    assert page.items[0].story_title_fr == "Le bac 2026" and page.items[0].filed_weekday_fr == "mardi"
    assert page.items[1].role == "vox" and page.items[1].stance == "pour"
    assert page.items[2].role == "rectificatif" and page.items[2].score == 4 and page.items[2].total == 5
    assert page.items[2].corrections_fr == ["La fête a lieu le 21 juin."]
    text = json.dumps(page.model_dump(mode="json"), ensure_ascii=False)
    assert "comence" not in text and "a mon avi" not in text and "Raw draft" not in text, "printed text only"
    assert "Someone else" not in text and "Last week" not in text
    assert page.lexique == ["la fête", "le bruit", "le bac", "la grève"]
    assert (page.rubriques_filed, page.rubriques_total, page.pieces) == (4, 6, 4)
    assert page.due_today is True, "Sunday of the current week, two pieces or more"
    assert une.une_semaine(db, user.id, "2026-W47", now=datetime(2026, 11, 21, 18, tzinfo=UTC)).due_today is False


def test_an_empty_week(db: Session) -> None:
    user = make_user(db)
    page = une.une_semaine(db, user.id, "2026-W40", now=datetime(2026, 11, 22, tzinfo=UTC))
    assert page.items == [] and page.lexique == [] and page.pieces == 0 and page.rubriques_filed == 0 and not page.due_today
    assert page.dateline_fr.startswith("Semaine 40 · ")


def test_the_editorial_rule_without_a_titre_leads_with_the_longest_text() -> None:
    from app.schemas.revue_rendez_vous import RvUneItem

    item = lambda k, t, d: RvUneItem(session_id=t, rubrique=k, role=une.ROLES[k], story_title_fr="s", text_fr=t,  # noqa: E731
                                     filed_on=d, filed_weekday_fr="lundi")
    ordered = une.editorial_order([item("fil", "court", "2026-11-16"), item("opinion", "beaucoup plus long", "2026-11-17")])
    assert [i.text_fr for i in ordered] == ["beaucoup plus long", "court"]


def test_la_carte_de_presse(db: Session) -> None:
    user = make_user(db)
    assert une.carte_de_presse(db, user.id).since is None
    _week(db, user)
    card = une.carte_de_presse(db, user.id)
    by = {r.rubrique: r for r in card.rubriques}
    assert [r.rubrique for r in card.rubriques] == ["opinion", "fil", "titre", "intox", "photo", "micro"]
    assert by["titre"].pieces == 2 and by["photo"].pieces == 0 and by["photo"].first_on is None
    assert card.pieces == 5 and card.since == "2026-11-15"


# ---------------------------------------------------------------------------
# The routes, and every switch off = today's payloads byte for byte
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(db_session: Session, revue_tables) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_revue_provider] = lambda: FakeRevueProvider()
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> dict[str, str]:
    email = f"rdv-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "securepass123", "target_language": "fr",
                                               "native_language": "en"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "securepass123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_with_the_switches_off_nothing_answers_and_nothing_changes(api: TestClient, db_session: Session, monkeypatch) -> None:
    for name in ("REVUE_MEMORY_ENABLED", "REVUE_TROIS_MOTS_ENABLED", "REVUE_UNE_ENABLED"):
        assert getattr(settings, name) is False, "default = today's behaviour"
    headers = login(api)
    session = api.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK, "dossier_id": FETE}).json()
    sid = session["id"]
    for path in (f"/sessions/{sid}/souvenir", f"/sessions/{sid}/trois-mots", "/une", "/carte-de-presse"):
        assert api.get(f"/api/v1/revue{path}").status_code == 404, "404 before auth"
        assert api.get(f"/api/v1/revue{path}", headers=headers).status_code == 404
    assert api.post(f"/api/v1/revue/sessions/{sid}/trois-mots", headers=headers, json={"act": "gap", "word": "a"}).status_code == 404
    before = api.get(f"/api/v1/revue/sessions/{sid}", headers=headers).content
    week_before = api.get("/api/v1/revue/week", headers=headers, params={"week": WEEK}).content
    monkeypatch.setattr(settings, "REVUE_MEMORY_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_TROIS_MOTS_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_UNE_ENABLED", True)
    assert api.get(f"/api/v1/revue/sessions/{sid}/souvenir", headers=headers).json() == {"line": None}
    assert api.get(f"/api/v1/revue/sessions/{sid}/trois-mots", headers=headers).json() == {"round": None, "error": None}
    assert api.get(f"/api/v1/revue/sessions/{sid}", headers=headers).content == before, "the session payload is untouched"
    assert api.get("/api/v1/revue/week", headers=headers, params={"week": WEEK}).content == week_before
    assert api.get("/api/v1/revue/une", headers=headers).status_code == 200
    assert api.get("/api/v1/revue/une", headers=headers, params={"week": "2026-11-20"}).status_code == 422
    assert api.get("/api/v1/revue/carte-de-presse", headers=headers).json()["pieces"] == 0
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert api.get("/api/v1/revue/une", headers=headers).status_code == 404


def test_the_round_leaves_the_session_s_payload_as_it_was(db: Session) -> None:
    revue, row = closed_titre(db)
    before = revue.view(row).model_dump_json()
    round_ = trois_mots.build(enc.load(row))
    right = {trois_mots.WORD_KEYS[i]: key for i, key in round_.answer.items()}
    trois_mots.act(revue, enc.load(row), RvTroisMotsRequest(act="match", pairs=right))
    assert any(e.kind == "trois_mots" for e in state_of(row).events)
    assert revue.view(row).model_dump_json() == before


def test_another_learner_cannot_read_a_round_or_a_line(api: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_MEMORY_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_TROIS_MOTS_ENABLED", True)
    mine, theirs = login(api), login(api)
    sid = api.post("/api/v1/revue/sessions", headers=mine, json={"week": WEEK, "dossier_id": FETE}).json()["id"]
    assert api.get(f"/api/v1/revue/sessions/{sid}/trois-mots", headers=theirs).status_code == 404
    assert api.get(f"/api/v1/revue/sessions/{sid}/souvenir", headers=theirs).status_code == 404
