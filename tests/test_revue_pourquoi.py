"""«Papier · Le pourquoi» (owner 2026-11-20): Romy's marks explain themselves and come back.

With ``REVUE_POURQUOI_ENABLED`` each mark on «Ton avis» carries the rule in the learner's
mother tongue — a hint without the answer while they fix it, the full rule and the story's own
example once settled — and the slips go to the learner's error memory (source «revue»). Off,
the ``comptoir_edit`` prompt, its payload, the stored events and the view are today's.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.error import UserError
from app.services.revue import comptoir, comptoir_loop
from app.services.revue import encounter as enc
from app.services.revue.encounter import FakeRevueProvider
from app.services.revue.evergreen import evergreens_for_week
from tests.test_revue_comptoir_loop import (
    GUS,
    MARCHE,
    MARGAUX,
    ROMY,
    WEEK,
    Revue,
    act,
    make_user,
    revue_tables,  # noqa: F401 - the fixture
    state_of,
    wire,
)

#: The v3 prompt as it shipped (comptoir-edit-v3): «off» must send exactly this.
V3_SHA256 = "905f20018fc0fe2e34da28be1bf3417bc9ce865b9ea719856a8cbe9a3a02c26f"
A2_REASON = "le gens sont content au supermarché"


class _Pourquoi:
    """``app.services.revue.pourquoi``, imported when a test reads it (so each guard fails on its own line on the base)."""

    def __getattr__(self, name: str) -> Any:
        return getattr(importlib.import_module("app.services.revue.pourquoi"), name)


pourquoi = _Pourquoi()
A2_DRAFT = "À mon avis, ce n'est pas une bonne idée, parce que le gens sont content au supermarché."


@pytest.fixture(autouse=True)
def switches(monkeypatch) -> None:
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_POURQUOI_ENABLED", True, raising=False)
    comptoir.forget_cache()


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:  # noqa: F811 - the imported fixture
    return db_session


def to_opinion(revue, row, band: str) -> None:
    act(revue, row, act="vote", value="contre")
    for guest in (ROMY, MARGAUX, GUS):
        act(revue, row, act="react", guest_id=guest, value="agree")
    act(revue, row, act="intox_who", guest_id=GUS)
    if band == "A2":
        act(revue, row, act="intox_fix", value="six jours sur sept")
    else:
        act(revue, row, act="intox_fix", text="C'est faux, Gus ! C'est six jours sur sept, pas sept.")


def session(db: Session, provider: FakeRevueProvider, *, level: str, native: str):
    revue = Revue(db, provider)
    user = make_user(db, level=level, native=native)
    row = revue.start(user, week=WEEK, dossier_id=MARCHE)
    to_opinion(revue, row, "A2" if level.startswith("A2") else "B1")
    return revue, user, row


def faults(db: Session, user) -> list[UserError]:
    return list(db.scalars(select(UserError).where(UserError.user_id == user.id)).all())


# ---------------------------------------------------------------------------
# The why reaches the view, in the mother tongue, without the answer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("level", "native", "words"), [
    ("A2.1", "de", ("Artikel", "Nomen")),
    ("A2.1", "en", ("article", "noun")),
    ("B1.1", "de", ("Akzent",)),
    ("B1.1", "en", ("accent",)),
])
def test_the_why_reaches_the_view_in_the_mother_tongue(db: Session, level: str, native: str, words) -> None:
    fake = FakeRevueProvider()
    revue, _, row = session(db, fake, level=level, native=native)
    text = A2_REASON if level.startswith("A2") else "ça depend, le marché est tres bien mais il y a trop de monde"
    view = act(revue, row, act="opinion", value="contre", text=text).session.comptoir
    assert view.opinion.proof == "marked"
    edit = [c for c in fake.calls if c[0] == "comptoir_edit"][-1][1]
    assert edit["explain_language"] == native, "the explanation language is passed as data"
    whys = [m.why for m in view.opinion.marks]
    assert whys and all(whys), whys
    assert all(word in " ".join(whys) for word in words)
    event = next(e for e in state_of(row).events if e.payload.get("act") == "opinion")
    assert event.payload["prompt_version"] == "comptoir-edit-v4"


def test_the_hint_never_carries_the_answer_and_the_full_why_waits_for_the_fix(db: Session) -> None:
    revue, _, row = session(db, FakeRevueProvider(), level="A2.1", native="en")
    view = act(revue, row, act="opinion", value="contre", text=A2_REASON).session.comptoir
    shown = wire(view)
    assert [(m.span_fr, m.kind) for m in view.opinion.marks] == [("le", "accord"), ("content", "accord")]
    assert "les gens" not in shown and "contents" not in shown, "no solution before a retry"
    assert "notes" not in json.loads(shown)["opinion"], "the full why is absent until settled"
    assert "why_full" not in shown and "fix_fr" not in shown and "example_fr" not in shown
    for mark in view.opinion.marks:
        assert not pourquoi.gives_away(mark.why, mark.span_fr, {"le": "les", "content": "contents"}[mark.span_fr])

    view = act(revue, row, act="opinion_fix", text="les gens sont contents au supermarché").session.comptoir
    assert view.opinion.proof == "fixed"
    notes = view.opinion.notes
    assert [(n.span_fr, n.kind, n.rule_id) for n in notes] == [("le", "accord", "plural_s"), ("content", "accord", "plural_s")]
    assert "«les gens»" in notes[0].why and "«sont contents»" in notes[1].why, "the full why may show the fix now"


def test_a_failing_check_drops_the_why_and_keeps_the_mark(db: Session) -> None:
    class Leaky(FakeRevueProvider):
        def comptoir_edit(self, context):
            out = super().comptoir_edit(context)
            whys = [
                {"why_hint": "Write «les gens»: the article agrees with the plural noun.",  # the answer
                 "why_full": "The article agrees with the plural noun: «les gens»."},
                {"why_hint": "L'adjectif s'accorde avec le nom, comme toujours en français.",  # not English
                 "why_full": "L'adjectif s'accorde avec le nom : «sont contents»."},
            ]
            out["marks"] = [{**mark, **why} for mark, why in zip(out["marks"], whys, strict=False)]
            return out

    revue, _, row = session(db, Leaky(), level="A2.1", native="en")
    view = act(revue, row, act="opinion", value="contre", text=A2_REASON).session.comptoir
    assert [(m.span_fr, m.kind, m.why) for m in view.opinion.marks] == [("le", "accord", None), ("content", "accord", None)]
    event = next(e for e in state_of(row).events if e.payload.get("act") == "opinion")
    assert [m.get("why_refused") for m in event.payload["marks"]] == ["why_hint:gives_away", "why_hint:language"]
    view = act(revue, row, act="opinion_fix", text="les gens sont contents au supermarché").session.comptoir
    assert all(note.why is None for note in view.opinion.notes), "never a wrong or leaking explanation"


def test_the_checks_one_by_one() -> None:
    ok = {"span": "le", "fix": "les", "learner_fr": A2_DRAFT, "language": "en"}
    hint = "In French the article agrees with its noun in number."
    full = "In French the article agrees with its noun in number: «les gens»."
    assert pourquoi.check_why(hint, full, **ok) == ({"why_hint": hint, "why_full": full}, None)
    assert pourquoi.check_why(hint, full, **{**ok, "language": "de"})[1] == "why_hint:language"
    long = "In French the article always agrees with its noun in number and in gender, " * 2
    assert pourquoi.check_why(long, full, **ok)[1] == "why_hint:too_long"
    assert pourquoi.check_why("Wrong word.", full, **ok)[1] in {"why_hint:language", "why_hint:no_rule"}
    assert pourquoi.check_why("The kind accord_number applies to the article here.", full, **ok)[1] == "why_hint:app_words"
    assert pourquoi.check_why("Use les with a plural noun, as the article agrees.", full, **ok)[1] == "why_hint:gives_away"
    assert pourquoi.check_why(hint, "The article agrees with its noun: «des chats».", **ok)[1] == "why_full:quotes"
    assert pourquoi.gives_away("Put the words «gens les» in order.", "gens les", "les gens") is False
    assert pourquoi.gives_away("Write «les gens» in this order.", "gens les", "les gens") is True


# ---------------------------------------------------------------------------
# «Dans l'article» : only the story's own words
# ---------------------------------------------------------------------------


def test_the_example_is_found_only_in_the_storys_own_text() -> None:
    dossier = next(d for d in evergreens_for_week(WEEK) if d.id == MARCHE)
    takes = dossier.comptoir
    # Romy's A2 take carries «légumes»: the pattern, in today's story.
    assert pourquoi.story_example(dossier, takes, "A2", fix="légumes", before="les", after="sont") == (
        "Des vrais légumes, des vrais rires.")
    assert pourquoi.story_example(dossier, takes, "B1", fix="très", before="est", after="bien") is None, "not in the story"
    assert pourquoi.story_example(dossier, takes, "A2", fix="les", before="que", after="gens") is None, (
        "a small word alone is no pattern")
    # «paniers» is only in Gus's take, and Gus told the lie: never an example.
    assert pourquoi.story_example(dossier, takes, "A2", fix="paniers", before="les", after="sont") is None
    assert pourquoi.story_example(dossier, takes, "A2", fix="marché couvert", after="et") == (
        "Il y a un marché couvert et un marché en plein air.")


def test_the_example_shows_after_the_fix_in_a_session(db: Session) -> None:
    class Legumes(FakeRevueProvider):
        def comptoir_edit(self, context):
            self.calls.append(("comptoir_edit", context))
            learner = context["learner_fr"]
            return {"edited_fr": learner.replace("legumes", "légumes"),
                    "marks": [{"span_fr": "legumes", "kind": "orthographe",
                               "why_hint": "Im Französischen trägt dieses Wort einen Akzent auf dem ersten e.",
                               "why_full": "Im Französischen trägt dieses Wort einen Akzent auf dem ersten e: «légumes»."}],
                    "reply_fr": context["example_reply_fr"], "reply_en": context["example_reply_en"],
                    "reply_de": context["example_reply_de"]}

    revue, _, row = session(db, Legumes(), level="A2.1", native="de")
    view = act(revue, row, act="opinion", value="contre", text="les legumes sont chers et la rue est pleine").session.comptoir
    assert view.opinion.marks[0].why and "Des vrais légumes, des vrais rires." not in json.dumps(
        json.loads(wire(view))["opinion"], ensure_ascii=False), "the example waits too: it shows the fix"
    view = act(revue, row, act="opinion_fix", text="les légumes sont chers et la rue est pleine").session.comptoir
    note = view.opinion.notes[0]
    assert note.example_fr == "Des vrais légumes, des vrais rires." and note.rule_id == "accent"


# ---------------------------------------------------------------------------
# The mark comes back: the error memory
# ---------------------------------------------------------------------------


def test_the_slips_are_kept_once_with_the_papier_as_source(db: Session) -> None:
    revue, user, row = session(db, FakeRevueProvider(), level="A2.1", native="de")
    act(revue, row, act="opinion", value="contre", text=A2_REASON)
    assert faults(db, user) == [], "nothing is kept while the learner is still fixing"
    act(revue, row, act="opinion_fix", text="les gens sont content au supermarché")
    act(revue, row, act="opinion_fix", value="romy")
    kept = faults(db, user)
    # «le gens» (repaired) and «sont content» (missed) are one pattern for the error memory
    # (``plural_s``): one row, seen twice, as any surface's repeated slip.
    assert [(e.original_text, e.correction, e.source_type, e.occurrences) for e in kept] == [
        ("content", "contents", "revue", 2)]
    fault = kept[0]
    payload = fault.error_metadata["source_payload"]
    assert payload["surface"] == "papier" and payload["outcome"] == "missed" and payload["rule_id"] == "plural_s"
    assert fault.why_wrong and "Nomen" in fault.why_wrong, "the why is kept in the mother tongue"
    assert fault.next_review_date is not None and fault.task_error_type == "plural_s"
    assert fault.error_metadata["context_fr"] == A2_DRAFT.replace("le gens", "les gens"), "the sentence it sat in"
    act(revue, row, act="opinion_fix", text="autre chose")  # settled: a repeat
    act(revue, row, act="comeback", index=0)
    revue.close(row)
    again = faults(db, user)
    assert len(again) == 1 and again[0].occurrences == 2, "kept once"


def test_a_half_edited_sentence_is_never_kept(db: Session) -> None:
    revue, user, row = session(db, FakeRevueProvider(), level="B1.1", native="en")
    text = "je je pense que le gens sont content parce que le marché ouvre aussi le mardi"
    view = act(revue, row, act="opinion", value="contre", text=text).session.comptoir
    assert view.opinion.proof == "marked"
    view = act(revue, row, act="opinion_fix", text=text.replace("le gens sont content", "les gens sont contents")).session.comptoir
    assert view.opinion.proof == "fixed"
    assert faults(db, user) == [], "a sentence with a doubled word is an editing artefact"


# ---------------------------------------------------------------------------
# Off: today's prompt, payload, events and view
# ---------------------------------------------------------------------------


def test_off_is_todays_prompt_and_payload(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_POURQUOI_ENABLED", False, raising=False)
    assert hashlib.sha256(comptoir_loop.COMPTOIR_EDIT_INSTRUCTIONS.encode()).hexdigest() == V3_SHA256
    fake = FakeRevueProvider()
    revue, user, row = session(db, fake, level="A2.1", native="de")
    view = act(revue, row, act="opinion", value="contre", text=A2_REASON).session.comptoir
    context = [c for c in fake.calls if c[0] == "comptoir_edit"][-1][1]
    dossier = next(d for d in evergreens_for_week(WEEK) if d.id == MARCHE)
    assert context == comptoir_loop.edit_context(dossier, dossier.comptoir, band="A2", stance="contre", learner_fr=A2_DRAFT)

    sent: dict[str, Any] = {}

    class Stub:
        def ask_json(self, instructions, context, **kwargs):
            sent.update(instructions=instructions, context=context, **kwargs)
            return {}

    enc.OpenAIRevueProvider.comptoir_edit(Stub(), context)  # type: ignore[arg-type]
    assert sent["instructions"] == comptoir_loop.COMPTOIR_EDIT_INSTRUCTIONS, "byte for byte"
    assert sent["label"] == "comptoir_edit" and sent["temperature"] == 0.5
    on = pourquoi.edit_instructions({**context, pourquoi.EXPLAIN_KEY: "de"})
    assert on != sent["instructions"] and "why_hint" in on and "why_hint" not in sent["instructions"]

    event = next(e for e in state_of(row).events if e.payload.get("act") == "opinion")
    assert event.payload["prompt_version"] == "comptoir-edit-v3"
    assert [sorted(m) for m in event.payload["marks"]] == [["kind", "span_fr", "start"]] * 2
    shown = json.loads(wire(view))["opinion"]
    assert all(sorted(m) == ["kind", "span_fr", "start"] for m in shown["marks"])
    view = act(revue, row, act="opinion_fix", text="les gens sont contents au supermarché").session.comptoir
    assert "notes" not in json.loads(wire(view))["opinion"]
    assert faults(db, user) == [], "off: nothing is kept"
