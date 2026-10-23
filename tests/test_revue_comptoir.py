"""«Au comptoir» (WP-119, owner 2026-10-19): the takes desk (``app/services/revue/comptoir.py``).

The checks one by one on the prompt's own example (the Céline story): the case-folded
intox, a stray number, a skip, a stance that contradicts its words, a band whose take lost
the false detail, the seat order, a false detail nobody corrects; who sits at the counter;
the one retry; the morning's ``ensure_comptoir`` once per row; the evergreens' shipped takes.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Generator

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.db.models.revue_session import RevueDossier
from app.services.revue import comptoir
from app.services.revue.dossier import EditorialDossier
from app.services.revue.evergreen import COMPTOIR_DIR, evergreen_takes, load_evergreens

WEEK = "2026-W43"


def celine(*, topic: str = "food", **update: object) -> EditorialDossier:
    """The prompt example's story (Céline Dion's last Paris concert), on an evergreen's sources."""

    base = next(d for d in load_evergreens() if d.id == "evergreen-fete-de-la-musique").model_dump(mode="json")
    base.update({
        "id": "2026-10-19-celine-dion-termine-sa-serie-de-concerts-a-paris",
        "week": WEEK,
        "title_fr": "Céline Dion termine sa série de concerts à Paris",
        "summary_fr": "Céline Dion a donné le dernier concert de sa première série à Paris le 17 octobre. Seize "
                      "concerts ont attiré des spectateurs venus de France et d’autres pays. La chanteuse doit "
                      "revenir à Paris en mai 2027.",
        "topic": topic,
        "evergreen": False,
        "comptoir": None,
        "leads": None,
        "time_scope": {"happening": "2026-10-17/2026-10-19", "relevant_until": "2026-10-26"},
    })
    claims = base["claims"][:3]
    for claim, text in zip(claims, [
        "Céline Dion a terminé sa première série de concerts à Paris le 17 octobre.",
        "Plus de 500 000 personnes sont venues voir Céline Dion à Paris.",
        "Céline Dion doit revenir à Paris en mai 2027.",
    ], strict=True):
        claim.update({"fr": text, "kind": "fact", "attributed_to": None})
    base["claims"] = claims
    base.update(update)
    return EditorialDossier.model_validate(base)


def gold() -> dict:
    """The full answer the prompt shows the desk (guests Romy, Margaux, Gus: a food story)."""

    text = comptoir.COMPTOIR_RULES.split("augustin_de_roncourt):\n", 1)[1].rsplit("\nDo not reuse", 1)[0]
    return json.loads(text)


def guest(raw: dict, cast_id: str) -> dict:
    return next(row for row in raw["guests"] if row["id"] == cast_id)


class _Desk:
    def __init__(self, answers: list) -> None:
        self.answers = list(answers)
        self.calls: list[dict] = []
        self.spent_usd = 0.0
        self.model = "fake-desk"

    def ask_json(self, instructions: str, payload: dict, **_: object) -> dict:
        self.calls.append(payload)
        self.spent_usd += 0.004
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return copy.deepcopy(answer)


# ---------------------------------------------------------------------------
# Who sits at the counter
# ---------------------------------------------------------------------------


def test_romy_the_topic_guest_and_gus_sit_at_the_counter() -> None:
    assert comptoir.comptoir_guests(celine(topic="food")) == ["romy_tremblay", "margaux_barman", "augustin_de_roncourt"]
    assert comptoir.comptoir_guests(celine(topic="culture"))[1] == "lila_bonnet"
    assert comptoir.comptoir_guests(celine(topic="work"))[1] == "marin_leveque"
    # city's first guest is Camille (no portrait): the next one with a portrait sits instead.
    assert comptoir.comptoir_guests(celine(topic="city"))[1] == "landlord_marchand"
    # sport's guest is Gus himself: Margaux takes the middle seat.
    assert comptoir.comptoir_guests(celine(topic="sport")) == ["romy_tremblay", "margaux_barman", "augustin_de_roncourt"]
    assert all("camille_marchand" not in comptoir.comptoir_guests(celine(topic=t))
               for t in ("food", "culture", "city", "sport", "nature", "work", "politics"))
    assert comptoir.role_fr("augustin_de_roncourt") == "consultant" and comptoir.name_fr("landlord_marchand") == "M. Marchand"


def test_the_desk_reads_the_storys_french_and_the_guests_sheets() -> None:
    payload = comptoir.desk_payload(celine(topic="culture"))
    assert [g["id"] for g in payload["guests"]] == ["romy_tremblay", "lila_bonnet", "augustin_de_roncourt"]
    assert "quote" not in payload["claims"][0]
    lila = payload["guests"][1]
    assert "putain" not in json.dumps(lila, ensure_ascii=False).lower(), "the counter never swears"
    assert "at_the_counter" in payload["guests"][0]


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def test_every_honest_take_at_an_intox_band_carries_a_checkable_detail() -> None:
    """2026-10-23: when only the liar's take holds a fact, «who lied?» is found by elimination."""

    story = celine()
    facts = comptoir._Checker(story).story
    question = "Céline revient en 2027. Bonne nouvelle ?"
    assert comptoir.details("Seize concerts, et j'ai pleuré.", facts, question) == ["seize"]
    assert comptoir.details("J'ai pleuré au concert du 17 octobre.", facts, question) == ["17", "octobre"]
    assert comptoir.details("Moi, j'adore Paris.", facts, question) == ["paris"]
    assert comptoir.details("Céline revient en 2027 !", facts, question) == [], "the question's own words: no detail"
    assert comptoir.details("Les fans, c'est bon pour la caisse.", facts, question) == []

    raw = gold()
    guest(raw, "margaux_barman")["a1"]["fr"] = "Ça dépend. Les fans, c'est bon pour la caisse. Pas pour mes oreilles."
    takes, problems = comptoir.repair_comptoir(raw, story)
    # Refused, not repaired by dropping the band: Gus's A1 take would still say «un million»
    # with nothing to correct it (the desk retries once with the problems).
    assert takes is None and "comptoir:margaux_barman:a1:no_detail" in problems
    assert "comptoir:augustin_de_roncourt" not in " ".join(problems), "the liar's take needs no other detail"


def test_the_prompts_own_example_passes_every_check() -> None:
    takes, problems = comptoir.repair_comptoir(gold(), celine())
    assert takes is not None and problems == []
    assert takes.intox is not None and takes.intox.bands == ["a1", "a2", "b1"]
    assert takes.intox.right_fr == "plus de 500 000 personnes" and takes.intox.claim_id == "c2"
    assert takes.question.fr == "Céline revient en 2027. Bonne nouvelle ?"
    assert takes.by_stance("contre").id == "augustin_de_roncourt"
    assert takes.reasons["contre"][1].fr == "la foule me fatigue"
    assert takes.frames["pour"].fr.endswith("parce que")


def test_a_skip_leaves_the_story_a_chat() -> None:
    assert comptoir.repair_comptoir({"fit": "skip"}, celine()) == (None, ["skip"])


def test_the_intox_is_found_case_folded() -> None:
    raw = gold()
    raw["intox"]["wrong_fr"] = "Un million de personnes"  # capital, the takes say «un million…»
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is not None and takes.intox is not None, problems
    assert takes.intox.wrong_fr == "un million de personnes"


def test_a_number_the_claims_do_not_carry_refuses_the_take() -> None:
    raw = gold()
    guest(raw, "romy_tremblay")["a2"]["fr"] = "Céline, c'est le Québec ! J'ai vu 3 concerts. Ne le dis à personne."
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is None and "comptoir:romy_tremblay:a2:number_not_in_claims" in problems


def test_the_liar_may_say_the_numbers_of_his_own_lie() -> None:
    raw = gold()
    raw["intox"]["caught"]["fr"] = "Le 17, le 18… Un artiste ne compte pas, mon cher."
    raw["intox"].update({"wrong_fr": "le 18 octobre", "right_fr": "le 17 octobre", "claim_id": "c1",
                         "distractor_fr": "en mai 2027"})
    for band in ("a1", "a2", "b1"):
        row = guest(raw, "augustin_de_roncourt")[band]
        row["fr"] = row["fr"].replace("un million de personnes", "le 18 octobre").replace(
            "Un million de personnes", "Le 18 octobre")
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is not None and takes.intox is not None, problems
    assert takes.intox.caught.fr.startswith("Le 17, le 18")


def test_a_take_whose_words_contradict_its_side_is_refused() -> None:
    raw = gold()
    guest(raw, "margaux_barman")["a1"]["fr"] = "Je suis pour. Les fans, c'est bon pour la caisse."
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is None and "comptoir:margaux_barman:a1:stance" in problems


def test_a_band_whose_take_lost_the_false_detail_has_no_intox_step() -> None:
    raw = gold()
    guest(raw, "augustin_de_roncourt")["b1"]["fr"] = (
        "Mon cher, tant de monde pour les mêmes chansons, c'est une foule, pas un public. Je préfère le silence.")
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is not None and problems == []
    assert takes.intox is not None and takes.intox.bands == ["a1", "a2"]
    assert takes.intox_for("B1") is None and takes.intox_for("B2") is None and takes.intox_for("A1") is not None


def test_a_false_detail_nobody_corrects_refuses_the_comptoir() -> None:
    raw = gold()
    guest(raw, "romy_tremblay")["a1"]["fr"] = "Je suis pour ! Un million de personnes, c'est le Québec."
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is None and "comptoir:romy_tremblay:a1:uncorrected_intox" in problems

    raw = gold()
    raw["intox"]["distractor_fr"] = "à Paris"  # a place for a number: the intox is dropped
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is None and "comptoir:intox:distractor" in problems
    assert "comptoir:augustin_de_roncourt:a1:uncorrected_intox" in problems


def test_an_intox_that_is_true_or_off_the_claims_is_dropped() -> None:
    for change, why in [
        ({"wrong_fr": "plus de 500 000 personnes"}, "comptoir:intox:not_false"),
        ({"right_fr": "deux millions de personnes"}, "comptoir:intox:right_not_in_claim"),
        ({"by": "lila_bonnet"}, "comptoir:intox:by"),
    ]:
        raw = gold()
        raw["intox"].update(change)
        _, problems = comptoir.repair_comptoir(raw, celine())
        assert why in problems, (change, problems)


def test_the_right_three_in_another_order_are_seated_and_a_stranger_is_refused() -> None:
    raw = gold()
    raw["guests"] = raw["guests"][::-1]
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is not None and [g.id for g in takes.guests] == ["romy_tremblay", "margaux_barman", "augustin_de_roncourt"]

    raw = gold()
    raw["guests"][1]["id"] = "camille_marchand"
    assert comptoir.repair_comptoir(raw, celine()) == (None, ["comptoir:guests:order"])

    raw = gold()
    guest(raw, "margaux_barman")["stance"] = "pour"
    assert comptoir.repair_comptoir(raw, celine()) == (None, ["comptoir:guests:stances"])


def test_small_pieces_are_dropped_and_fall_back_to_authored_lines() -> None:
    raw = gold()
    raw["reasons"]["pour"] = [{"fr": "parce que sa voix est très très très belle et forte"}]
    raw["replies"]["contre"]["by"] = "augustin_de_roncourt"  # Gus is «contre» himself
    raw["question"]["fr"] = "Céline revient en 2027 : est-ce que c'est une très bonne nouvelle ?"
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is None and problems == ["comptoir:question:too_long"], "a long question refuses"

    raw["question"]["fr"] = "Céline revient. Bonne nouvelle ?"
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is not None
    assert "comptoir:reason:pour:0:too_long" in problems and "comptoir:reply:contre:by" in problems
    assert takes.reasons["pour"] == comptoir.AUTHORED_REASONS["pour"]
    assert "contre" not in takes.replies
    fallback = comptoir.reply_for(takes, "contre")
    assert fallback.by == "romy_tremblay" and fallback.line == comptoir.AUTHORED_REPLIES["romy_tremblay"]


def test_a_reply_speaks_to_the_learner_and_never_guesses_who_they_are() -> None:
    assert comptoir.address_problem("Toi aussi ? Mon cher, les mêmes chansons ?", "augustin_de_roncourt") == "gendered_address"
    assert comptoir.address_problem("Voyons donc ! Tu es sérieuse ?", "romy_tremblay") == "gendered_address"
    assert comptoir.address_problem("Voyons donc, Gus ! La brioche ?", "romy_tremblay") == "addresses_other"
    assert comptoir.address_problem("Gus, tu exagères !", "romy_tremblay") == "addresses_other"
    for fine in ("Tu te plains comme Gus ?", "Voyons donc ! Pour vrai ?", "Tu es contre Céline ?", "Mon chou, tu restes chez toi ?"):
        assert comptoir.address_problem(fine, "romy_tremblay") is None, fine

    raw = gold()
    raw["replies"]["pour"]["line"]["fr"] = "Toi aussi ? Mon cher, les mêmes chansons ? Tu n'en as pas marre ?"
    raw["replies"]["contre"]["line"]["fr"] = "Voyons donc, Gus ! Tu as déjà écouté sa voix ?"
    takes, problems = comptoir.repair_comptoir(raw, celine())
    assert takes is not None
    assert {"comptoir:reply:pour:line:gendered_address", "comptoir:reply:contre:line:addresses_other"} <= set(problems)
    assert comptoir.reply_for(takes, "pour").line == comptoir.AUTHORED_REPLIES["augustin_de_roncourt"]
    for line in comptoir.AUTHORED_REPLIES.values():
        assert comptoir.address_problem(line.fr, "") is None, line.fr


def test_app_words_and_relative_dates_never_reach_the_counter() -> None:
    raw = gold()
    guest(raw, "margaux_barman")["a2"]["fr"] = "Ça dépend. Ce dossier est bon pour la caisse."
    _, problems = comptoir.repair_comptoir(raw, celine())
    assert "comptoir:margaux_barman:a2:app_words" in problems

    raw = gold()
    guest(raw, "margaux_barman")["a2"]["fr"] = "Ça dépend. Demain, les fans reviennent au comptoir."
    _, problems = comptoir.repair_comptoir(raw, celine())
    assert "comptoir:margaux_barman:a2:relative_date" in problems


# ---------------------------------------------------------------------------
# The desk: one retry, then the morning
# ---------------------------------------------------------------------------


def test_the_desk_retries_once_with_the_problems() -> None:
    bad = gold()
    guest(bad, "romy_tremblay")["a1"]["fr"] = "Je suis pour ! J'ai vu 9 concerts."
    desk = _Desk([bad, gold()])
    takes, problems = comptoir.write_comptoir(celine(), desk)
    assert takes is not None and problems == []
    assert len(desk.calls) == 2 and "romy_tremblay:a1:number_not_in_claims" in json.dumps(desk.calls[1]["retry_feedback"])
    assert takes.model == "fake-desk" and takes.prompt_version == comptoir.COMPTOIR_PROMPT_VERSION
    assert takes.written_at is not None


def test_the_desk_retries_when_only_the_intox_was_lost() -> None:
    no_intox = gold()
    no_intox["intox"] = None
    for band in ("a1", "a2", "b1"):
        row = guest(no_intox, "augustin_de_roncourt")[band]
        row["fr"] = row["fr"].replace("Un million de personnes", "Tant de monde").replace("un million de personnes", "tant de monde")
    desk = _Desk([no_intox, gold()])
    takes, _ = comptoir.write_comptoir(celine(), desk)
    assert takes is not None and takes.intox is not None and len(desk.calls) == 2

    desk = _Desk([no_intox, no_intox])
    takes, problems = comptoir.write_comptoir(celine(), desk)
    assert takes is not None and takes.intox is None, "takes without an intox still play (four dots)"


def test_a_failing_desk_writes_nothing() -> None:
    takes, problems = comptoir.write_comptoir(celine(), _Desk([RuntimeError("down")]))
    assert takes is None and problems == ["comptoir:desk_failed"]


REVUE_TABLES = (RevueDossier.__table__,)


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


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:
    return db_session


def _row(db: Session, dossier: EditorialDossier, period: str) -> RevueDossier:
    row = RevueDossier(id=f"{period}-{dossier.id}"[:120], week=WEEK, period=period, topic=dossier.topic,
                       payload=dossier.model_dump(mode="json"), source_hashes={}, checks={},
                       builder_version="revue-builder-v3")
    db.add(row)
    db.commit()
    return row


def test_each_morning_writes_the_takes_once_per_row(db: Session) -> None:
    today = "2026-10-19"
    fresh = _row(db, celine(id="2026-10-19-a"), today)
    skipped = _row(db, celine(id="2026-10-19-b"), today)
    evergreen = next(d for d in load_evergreens() if d.id == "evergreen-marche-du-dimanche")
    shipped = _row(db, evergreen.model_copy(update={"comptoir": None}), today)
    desk = _Desk([gold(), {"fit": "skip"}])
    written = comptoir.ensure_comptoir(db, today, provider=desk)
    assert sorted(written) == ["2026-10-19-a", "evergreen-marche-du-dimanche"]
    assert len(desk.calls) == 2, "an evergreen reads its shipped takes; no call"
    db.refresh(fresh), db.refresh(skipped), db.refresh(shipped)
    assert EditorialDossier.model_validate(fresh.payload).comptoir is not None
    assert skipped.checks["comptoir"] == "skip" and skipped.payload.get("comptoir") is None
    assert shipped.payload["comptoir"]["question"]["fr"] == evergreen_takes(evergreen.id).question.fr

    assert comptoir.ensure_comptoir(db, today, provider=_Desk([])) == [], "a skipped row is not asked again"


def test_each_morning_writes_the_takes_after_the_leads_while_the_switch_is_on(monkeypatch) -> None:
    from app.config import settings
    from app.tasks import revue as task

    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    order: list[str] = []
    monkeypatch.setattr(task, "intake_now", lambda refresh=False: {"status": "kept", "period": "2026-10-19"})
    monkeypatch.setattr(task, "leads_now", lambda period=None, now=None: order.append("leads") or {"status": "ok"})
    monkeypatch.setattr(task, "comptoir_now", lambda period=None, now=None: order.append("comptoir") or {"status": "ok"})
    monkeypatch.setattr(task, "_queue_painting", lambda period: order.append("paint") or {"status": "enqueued"})
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", False)
    report = task.weekly_intake()
    assert order == ["leads", "paint"] and "comptoir" not in report, "off: no morning call"
    order.clear()
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    report = task.weekly_intake()
    assert order == ["leads", "comptoir", "paint"] and report["comptoir"] == {"status": "ok"}


# ---------------------------------------------------------------------------
# The evergreens' takes
# ---------------------------------------------------------------------------


def test_the_shipped_evergreen_takes_load_and_pass_every_check() -> None:
    files = sorted(path.stem for path in COMPTOIR_DIR.glob("*.json"))
    assert len(files) == 10
    by_id = {d.id: d for d in load_evergreens()}
    for dossier_id in files:
        dossier = by_id[dossier_id]
        assert dossier.comptoir is not None, dossier_id
        bare = dossier.model_copy(update={"comptoir": None})
        assert comptoir.audit(dossier.comptoir, bare) == [], dossier_id
        assert [g.id for g in dossier.comptoir.guests] == comptoir.comptoir_guests(dossier)
        assert dossier.comptoir.model == "claude-haiku-5-5"
        assert dossier.comptoir.intox is not None, dossier_id
        for g in dossier.comptoir.guests:
            for band in ("a1", "a2", "b1"):
                text = g.take.for_band(band)
                assert text.en and text.de, (dossier_id, g.id, band)
    skipped = {"evergreen-greve-transports", "evergreen-toussaint"}
    assert all(by_id[d].comptoir is None for d in skipped), "the desk's skips stay chats"
