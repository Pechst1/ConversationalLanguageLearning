"""WP-119 §10e «La voix de Romy»: the deterministic checks and how the encounter applies them.

The real-model sample of 2026-10-03 failed natural French in 10/10 sessions: ids spoken to the
learner, symbols at A1–A2, orders to the learner, a fact dump at «d'accord», the reader question
pushed every turn, the angle flipping back and forth, guests offering services, app words in the
close, vocabulary the evidence could not use, and an uncertainty index off by one (session 6).
Each failure has a test here, under the fake provider.
"""

from __future__ import annotations

import time

import pytest
from loguru import logger
from sqlalchemy.orm import Session

from app.services.revue import encounter as enc
from app.services.revue import grading, knowledge, voice
from app.services.revue.dossier import EditorialDossier
from app.services.revue.encounter import CLOSE_LINES, FakeRevueProvider, RevueEncounter
from app.services.revue.evergreen import evergreens_for_week
from app.services.revue.weekly import load_week
from tests.test_revue_encounter import (  # noqa: F401 - fixtures
    MARCHE,
    PRICE_QUESTION,
    WEEK,
    _forced,
    _guest,
    evergreens_only,
    items_of,
    make_user,
    revue_tables,
    state_of,
)

AGREE = "D'accord, je t'aide."


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:  # noqa: F811 - the imported fixture
    return db_session


def _reply_calls(fake: FakeRevueProvider) -> list[dict]:
    return [context for name, context in fake.calls if name == "reply"]


def _last_romy(row) -> dict:
    return [e for e in state_of(row).events if e.kind == "turn_romy"][-1].payload


# ---------------------------------------------------------------------------
# The checks themselves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "leaks", "clean"),
    [
        ("Il y en aura cent, d'après c2.", ["c2"], "Il y en aura cent."),
        ("Merci. D'après c1,c2,c3, les prix montent.", ["c1", "c2", "c3"], "Merci. Les prix montent."),
        ("Les sources ne disent pas de combien (incert. 1).", ["incert. 1"], "Les sources ne disent pas de combien."),
        ("On commence par «Ce que la rentrée change» (a1).", ["a1"], "On commence par «Ce que la rentrée change»."),
        ("Quels légumes (incertitude 2) ?", ["incertitude 2"], "Quels légumes ?"),
        ("Au niveau A1, c'est simple.", [], "Au niveau A1, c'est simple."),
    ],
)
def test_id_leaks_are_found_and_stripped(text: str, leaks: list[str], clean: str) -> None:
    assert voice.id_leaks(text) == leaks
    assert voice.strip_ids(text) == clean


def test_symbols_imperatives_offers_and_app_words() -> None:
    assert voice.symbols("Plafond 100→140 €, ≈0,40 €/L, >60 km/h") == ["→", "≈", "/", ">", "/"]
    assert voice.replace_symbols("Plafond 100→140 €, ≈0,40 €/L") == "Plafond de 100 à 140 €, environ 0,40 € par L"
    assert voice.symbols("Voir https://www.insee.fr/fr/statistiques") == []
    assert voice.imperatives("Merci. Dis-lui : Paris a 91 marchés.") == ["Dis-lui"]
    assert voice.imperatives("Écris trois lignes. Note : c'est cher. Répète.") == ["Écris", "Note", "Répète."]
    assert voice.imperatives("Dis-moi, tu aimes les marchés ?") == []
    assert voice.drop_imperatives("Merci. Dis : «Pourquoi ?»") == "Merci."
    assert voice.is_service_offer("Voulez-vous que je demande au maire ?")
    assert voice.is_service_offer("Tu veux que je cherche lesquels ont monté ?")
    assert voice.is_service_offer("Je peux demander à mes élèves.")
    assert voice.is_service_offer("Souhaitez-vous un exemple ?")
    assert not voice.is_service_offer("Moi, je trouve ça cher. Et toi ?")
    assert voice.app_words("Je garde ta question dans l'artefact et je ferme la session.") == ["artefact", "session"]
    assert voice.app_words("L'État paie la moitié.") == []
    assert voice.meta_words("D'après le dossier, c'est cinq jours ; tu l'as sur l'écran.") == ["dossier", "sur l'écran"]
    assert voice.meta_words("Les marchés de Paris sont vivants.") == []
    assert voice.french_typography("Dis-lui: c'est en novembre?") == "Dis-lui : c'est en novembre ?"


def test_uncertainties_are_normalised_to_ids_on_load() -> None:
    dossier = next(d for d in load_week(WEEK) if d.id == "2026-w40-prix-produits-frais")
    assert [u.id for u in dossier.uncertainties] == ["u1", "u2"]  # the stored file holds plain strings
    data = dossier.model_dump(mode="json")
    assert data["uncertainties"][1] == {"id": "u2", "fr": dossier.uncertainties[1].fr}
    again = EditorialDossier.model_validate(data)
    assert again.uncertainty_by_id("u2") == dossier.uncertainties[1]
    mixed = EditorialDossier.model_validate({**data, "uncertainties": ["Un.", {"id": "u7", "fr": "Deux."}]})
    assert [(u.id, u.fr) for u in mixed.uncertainties] == [("u1", "Un."), ("u7", "Deux.")]


# ---------------------------------------------------------------------------
# Romy's reply
# ---------------------------------------------------------------------------


def test_an_id_leak_is_regenerated_once_then_stripped_and_logged(db: Session) -> None:
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(message.record["message"]), level="INFO")
    try:
        leak = _forced("Selon c2 (c2), il ouvre tous les matins.", translation="According to c2, it opens every morning.")
        fake = FakeRevueProvider(script=[_forced("D'après c2, le marché ouvre tôt."), leak])
        revue = RevueEncounter(db, fake)
        row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
        line = items_of(revue.turn(row, "Il ouvre quand ?"), "line")[0]
    finally:
        logger.remove(sink)
    calls = _reply_calls(fake)
    assert len(calls) == 2 and calls[1]["retry_feedback"]["id_leaks"] == ["c2"]
    assert line.text_fr == "Il ouvre tous les matins."
    assert line.translation == "It opens every morning."
    assert not voice.id_leaks(line.text_fr) and not voice.id_leaks(line.translation)
    romy = _last_romy(row)
    assert "id_leak" in romy["refused"] and "id_leak" in romy["repaired"]
    assert "revue_id_leak" in messages


def test_a_symbol_is_regenerated_at_a2_and_replaced_with_words(db: Session) -> None:
    fake = FakeRevueProvider(script=[_forced("Il ouvre 6/7 jours, ~7 h."), _forced("Il ouvre >6 jours.")])
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db, level="A2.1"), WEEK, dossier_id=MARCHE)
    line = items_of(revue.turn(row, "Il ouvre quand ?"), "line")[0]
    assert "symbols" in _reply_calls(fake)[1]["retry_feedback"]["problems"]
    assert line.text_fr == "Il ouvre plus de 6 jours."

    # B1 reads symbols: no regeneration.
    fake_b1 = FakeRevueProvider(script=[_forced("Il ouvre 6/7 jours.")])
    revue_b1 = RevueEncounter(db, fake_b1)
    row_b1 = revue_b1.start(make_user(db, level="B1.1"), WEEK, dossier_id=MARCHE)
    assert items_of(revue_b1.turn(row_b1, "Il ouvre quand ?"), "line")[0].text_fr == "Il ouvre 6/7 jours."
    assert len(_reply_calls(fake_b1)) == 1


def test_an_order_to_the_learner_is_refused(db: Session) -> None:
    fake = FakeRevueProvider(script=[_forced("Dis-lui : Paris a 91 marchés."), _forced("Paris a 91 marchés. Tu le savais ?")])
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    line = items_of(revue.turn(row, "Il y a combien de marchés ?"), "line")[0]
    assert _reply_calls(fake)[1]["retry_feedback"]["imperatives"] == ["Dis-lui"]
    assert line.text_fr == "Paris a 91 marchés. Tu le savais ?"


def test_a_restated_claim_is_dropped_and_shown_claims_leave_the_available_list(db: Session) -> None:
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    revue.turn(row, AGREE)  # the facts beat: c1, c2 on the table
    fake.script = [_forced("Comme on l'a vu, il y en a beaucoup. Le marché Beauvau est couvert.",
                           claims_cited=["c1", "c3"])]
    result = revue.turn(row, "Et il y a un marché couvert ?")
    context = _reply_calls(fake)[-1]
    assert {c["id"] for c in context["claims"]} == {"c3", "c4"}
    assert {c["id"] for c in context["claims_already_said"]} == {"c1", "c2"}
    assert all(c["source"] for c in context["claims"]), "Romy attributes to a source name, never an id"
    romy = _last_romy(row)
    assert (romy["claims_cited"], romy["claims_restated"]) == (["c3"], ["c1"])
    assert [c.id for item in items_of(result, "claims") for c in item.claims] == ["c3"]


def test_more_than_two_new_claims_is_regenerated_then_cut_to_two(db: Session) -> None:
    dump = _forced("Paris a 91 marchés. Aligre ouvre six jours. Beauvau est couvert.", claims_cited=["c1", "c2", "c3"])
    fake = FakeRevueProvider(script=[dump, {**dump, "claims_cited": ["c1", "c2", "c3", "c4"]}])
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    result = revue.turn(row, AGREE)
    assert "too_many_claims" in _reply_calls(fake)[1]["retry_feedback"]["problems"]
    assert _last_romy(row)["claims_cited"] == ["c1", "c2"]
    assert [c.id for item in items_of(result, "claims") for c in item.claims] == ["c1", "c2"]


def test_the_reader_question_is_proposed_once(db: Session) -> None:
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    revue.turn(row, AGREE)
    revue.turn(row, PRICE_QUESTION)
    assert _last_romy(row)["proposes_question"] == PRICE_QUESTION
    fake.script = [_forced("Je n'ai rien. Les sources ne le disent pas. On formule la question ensemble ?",
                           proposes_question="Les horaires changent ?", uncertainty_cited="u2")]
    line = items_of(revue.turn(row, "Est-ce que les horaires changent pendant les fêtes ?"), "line")[0]
    assert _reply_calls(fake)[-1]["question_proposed"] is True
    romy = _last_romy(row)
    assert romy["proposes_question"] is None and "question_repeat" in romy["repaired"]
    assert line.text_fr == "Je n'ai rien. Les sources ne le disent pas."
    assert romy["uncertainty_id"] == "u2"


def test_the_angle_changes_once_and_only_when_the_learner_asks(db: Session) -> None:
    fake = FakeRevueProvider(script=[_forced("Merci !", shift="angle")])
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    assert not items_of(revue.turn(row, AGREE), "shift"), "a quick reply never moves the angle"
    assert _last_romy(row)["shift_refused"] == "learner_did_not_ask"
    fake.script = [_forced("Bonne idée, on compare.", shift="angle")]
    shift = items_of(revue.turn(row, "Moi, je veux comparer avec le supermarché."), "shift")
    assert shift and shift[0].angle.id == "a2"
    fake.script = [_forced("D'accord.", shift="angle")]
    assert not items_of(revue.turn(row, "Et faire ses courses au marché, ça marche comment ?"), "shift")
    assert _last_romy(row)["shift_refused"] == "angle_already_changed"
    assert revue.view(row).plan.angle.id == "a2"
    assert len(enc._choices(state_of(row), "angle")) == 1


def test_session_six_an_out_of_range_uncertainty_index_is_matched_by_content(db: Session, monkeypatch) -> None:
    """2026-10-03 sample, session 6: «Quels légumes sont plus chers ?» is the dossier's second
    uncertainty; the model cited index 2 (out of range) and the question was recorded answerable."""

    kiosk = [*load_week(WEEK), *evergreens_for_week(WEEK)]
    monkeypatch.setattr(enc, "available_dossiers", lambda week, db=None: kiosk)
    gap = _forced("Les sources ne disent pas quels légumes ont le plus augmenté (incertitude 2).", uncertainty_cited=2)
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db, level="A1.1"), WEEK, dossier_id="2026-w40-prix-produits-frais")
    revue.turn(row, AGREE)
    fake.script = [gap, gap]
    result = revue.turn(row, "Quels légumes sont plus chers ?")
    dossier = enc.load(row).dossier
    line = items_of(result, "line")[0]
    assert line.text_fr == "Les sources ne disent pas quels légumes ont le plus augmenté."
    assert [u.text_fr for u in items_of(result, "uncertainty")] == [dossier.uncertainties[1].fr]
    romy = _last_romy(row)
    assert (romy["uncertainty_id"], romy["uncertainty_matched"]) == ("u2", True)
    assert state_of(row).questions[-1]["answerable"] is False
    offer = revue.make_options(row)
    assert offer.recommended == "reader_question"
    draft = revue.make(row, "reader_question", {"action": "propose"}).draft
    revue.make(row, "reader_question", {"action": "send", "text_fr": draft.proposal_fr})
    _, closing = revue.close(row)
    assert closing.question_kept_fr == draft.proposal_fr


# ---------------------------------------------------------------------------
# Guests
# ---------------------------------------------------------------------------


def _margaux_session(db: Session, fake: FakeRevueProvider):
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    revue.turn(row, AGREE)
    return revue, row


def test_a_guest_offer_of_service_is_refused_then_the_authored_line_stands(db: Session) -> None:
    offer = _guest("Tu veux que je cherche les prix ?", "for", "enter")
    fake = FakeRevueProvider(guest_script=[offer, _guest("Voulez-vous que je demande au maire ?", "for", "enter")])
    revue, row = _margaux_session(db, fake)
    guest = items_of(revue.turn(row, PRICE_QUESTION), "guest")[0]
    assert guest.text_fr == knowledge.authored_guest_line("margaux_barman", "food")
    assert len([c for c in fake.calls if c[0] == "guest"]) == 2
    event = [e for e in state_of(row).events if e.kind == "turn_guest"][-1].payload
    assert event["reason"] == "service_offer" and "service_offer" in event["refused"]
    assert guest.position == "for", "an entrance always takes a side"


def test_a_guest_enters_with_a_side_and_moves_only_on_a_statement(db: Session) -> None:
    fake = FakeRevueProvider(guest_script=[
        _guest("Le marché, c'est ma vie.", None, "enter"),
        _guest("Le marché, c'est ma vie, je vois les prix.", "against", "enter"),
        _guest("Bon, je change d'avis.", "moved", "moved"),
    ])
    revue, row = _margaux_session(db, fake)
    entered = items_of(revue.turn(row, PRICE_QUESTION), "guest")[0]
    assert entered.position == "against"
    assert "no_position" in [c for c in fake.calls if c[0] == "guest"][1][1]["retry_feedback"]["problems"]
    follow = items_of(revue.turn(row, "Pourquoi ?"), "guest")[0]
    assert (follow.move, follow.position) == ("disagree", "against"), "a question never changes a mind"
    assert state_of(row).guest_position("margaux_barman") == "against"
    # The guest prompt names the voice and forbids offers.
    context = [c for c in fake.calls if c[0] == "guest"][0][1]
    assert context["voice"]["personality"]
    assert "Voulez-vous que je" in enc._TASKS["guest"] and "MUST take a side" in enc._TASKS["guest"]


def test_a_guest_repeating_their_own_line_is_asked_for_something_new(db: Session) -> None:
    fake = FakeRevueProvider(guest_script=[
        _guest("Je suis contre : je vois les prix monter au comptoir.", "against", "enter"),
        _guest("Je suis contre : je vois les prix monter au comptoir, moi.", "against", "follow_up"),
        _guest("Mes clients, eux, comptent chaque centime.", "against", "follow_up"),
    ])
    revue, row = _margaux_session(db, fake)
    revue.turn(row, PRICE_QUESTION)
    follow = items_of(revue.turn(row, "Je ne sais pas encore."), "guest")[0]
    assert follow.text_fr == "Mes clients, eux, comptent chaque centime."
    assert "repeat" in [c for c in fake.calls if c[0] == "guest"][-1][1]["retry_feedback"]["problems"]


# ---------------------------------------------------------------------------
# The close
# ---------------------------------------------------------------------------


def _closing_script(line: str) -> dict:
    return {"romy_line_fr": line, "headline_fr": "Le marché", "body_lines": ["Un.", "Deux.", "Trois."]}


def test_app_words_in_the_close_are_regenerated_then_the_template_stands(db: Session) -> None:
    jargon = _closing_script("Je garde ta question dans l'artefact de la session.")
    fake = FakeRevueProvider(close_script=[jargon, jargon])
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    revue.turn(row, AGREE)
    _, closing = revue.close(row)
    assert closing.romy_line_fr == CLOSE_LINES["none"]
    close_calls = [c for c in fake.calls if c[0] == "close"]
    assert len(close_calls) == 2 and close_calls[1][1]["retry_feedback"]["app_words"] == ["artefact", "session"]


def test_an_id_in_the_close_is_stripped_after_one_regeneration(db: Session) -> None:
    leak = _closing_script("Je mets les marchés (c1) dans mon papier.")
    fake = FakeRevueProvider(close_script=[leak, leak])
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    revue.turn(row, AGREE)
    _, closing = revue.close(row)
    assert closing.romy_line_fr == "Je mets les marchés dans mon papier."


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class _VocabFake(FakeRevueProvider):
    def vocabulary(self, *, claims, count, language, prefer=()):
        self.calls.append(("vocabulary", {"prefer": list(prefer)}))
        rows = [("Paris", "c1"), ("du", "c4"), ("2026", "c1"), ("91 marchés", "c1"), ("la convivialité", "c4"),
                ("du savoir-faire", "c4"), ("le marché couvert", "c3"), ("les marchés", "c1")]
        return [{"fr": fr, "gloss": f"gloss {fr}", "claim_id": cid} for fr, cid in rows]


def test_vocabulary_excludes_names_contractions_numbers_and_prefers_catalogue_words(db: Session) -> None:
    fake = _VocabFake()
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    words = [item.fr for item in revue.view(row).plan.vocabulary]
    assert len(words) == 5
    assert not {"Paris", "du", "2026", "91 marchés"} & set(words)
    assert "le savoir-faire" in words, "a contraction becomes the article"
    assert grading.capability_for(words[0]) is not None, "catalogue words come first"
    assert words[0] == "les marchés"
    prefer = [call[1]["prefer"] for call in fake.calls if call[0] == "vocabulary"][0]
    assert any("marché" in word for word in prefer)


def test_the_authored_vocabulary_is_filtered_too() -> None:
    claims = [{"id": "c1", "fr": "Selon l'Insee, le prix du pain monte de 3 % en 2026 à Paris."}]
    words = [row["fr"] for row in enc.extract_vocabulary(claims, 5)]
    assert "le pain" in words and "le prix" in words
    assert not any(w[:1].isupper() or any(ch.isdigit() for ch in w) for w in words)
    assert grading.capability_for(words[0]) is not None


# ---------------------------------------------------------------------------
# Prompt versions and latency
# ---------------------------------------------------------------------------


def test_every_cost_event_records_its_prompt_version(db: Session) -> None:
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    revue.turn(row, AGREE)
    revue.turn(row, PRICE_QUESTION)
    word = enc.load(row).plan.vocabulary[0].fr
    revue.turn(row, f"Pour moi, {word}, c'est important.")
    revue.make_options(row)
    draft = revue.make(row, "reader_question", {"action": "propose"}).draft
    revue.make(row, "reader_question", {"action": "send", "text_fr": draft.proposal_fr})
    revue.close(row)
    costed = [e for e in state_of(row).events if "cost_usd" in e.payload]
    assert {e.kind for e in costed} >= {"choice", "turn_romy", "turn_guest", "evidence"}
    versions = set(enc.PROMPT_VERSIONS.values())
    assert all(e.payload.get("prompt_version") in versions for e in costed), [
        (e.kind, e.payload.get("prompt_version")) for e in costed if e.payload.get("prompt_version") not in versions
    ]


class _SlowConcurrent(FakeRevueProvider):
    concurrent = True

    def reply(self, context):
        time.sleep(0.4)
        return super().reply(context)

    def guest(self, context):
        time.sleep(0.4)
        return super().guest(context)


def test_the_guest_line_runs_beside_romys_reply(db: Session) -> None:
    fake = _SlowConcurrent()
    revue, row = _margaux_session(db, fake)
    started = time.perf_counter()
    result = revue.turn(row, PRICE_QUESTION)
    elapsed = time.perf_counter() - started
    assert items_of(result, "guest") and items_of(result, "line")
    assert elapsed < 0.75, f"reply and guest ran in sequence ({elapsed:.2f} s)"
    kinds = [e.kind for e in state_of(row).events if e.seq > state_of(row).events[-8].seq]
    assert kinds.index("turn_romy") < kinds.index("turn_guest"), "the thread order is unchanged"


class _SlowScorer:
    name = "slow-critic"
    spent_usd = 0.0

    def __init__(self, delay: float) -> None:
        self.delay = delay

    def score(self, rubric, text):
        time.sleep(self.delay)
        word = rubric.words[0]["fr"]
        return {"words": [{"fr": word, "outcome": "correct", "quote": word}], "fact_fit": "supported",
                "register": "ok", "band_fit": "at"}


@pytest.mark.parametrize("lose_future", [False, True])
def test_a_late_critic_lands_on_the_next_turn(db: Session, monkeypatch, lose_future: bool) -> None:
    monkeypatch.setattr(enc, "CRITIC_WAIT_SECONDS", 0.05)
    revue = RevueEncounter(db, _SlowConcurrent(), scorer=_SlowScorer(0.9))
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    revue.turn(row, AGREE)
    word = enc.load(row).plan.vocabulary[0].fr
    first = revue.turn(row, f"Pour moi, {word}, c'est important.")
    assert first.evidence.pending is True and first.evidence.outcome == "unscored"
    seq = [e for e in state_of(row).events if e.kind == "turn_learner"][-1].seq
    if lose_future:
        enc._LATE.clear()  # another worker took the next request: the turn is graded again
    revue.turn(row, "Ah, d'accord.")
    late = [e.payload for e in state_of(row).events if e.kind == "evidence" and e.payload.get("late")]
    assert len(late) == 1 and late[0]["turn_seq"] == seq
    assert late[0]["prompt_version"] == grading.CRITIC_PROMPT_VERSION
    assert enc.word_outcomes(state_of(row))[word.casefold()] in {"correct", "unscored"}
    assert late[0]["word_outcomes"][0]["fr"] == word


def test_romy_does_not_read_the_learners_line_back(db: Session) -> None:
    echo = _forced("Il ouvre quand ? Tous les matins, sauf le lundi.", translation="When does it open? Every morning, except Monday.")
    fake = FakeRevueProvider(script=[echo])
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    line = items_of(revue.turn(row, "Il ouvre quand ?"), "line")[0]
    assert (line.text_fr, line.translation) == ("Tous les matins, sauf le lundi.", "Every morning, except Monday.")
    assert "echo" in _last_romy(row)["repaired"] and len(_reply_calls(fake)) == 1


def test_an_infinitive_or_singular_the_claim_inflects_is_kept() -> None:
    assert enc.appears_in("L'Académie a retiré le roman.", "retirer")
    assert enc.appears_in("Seize chevaux courent l'Arc.", "le cheval")
    assert not enc.appears_in("Seize chevaux courent l'Arc.", "la course")
    strict = [row["fr"] for row in enc.extract_vocabulary([{"id": "c1", "fr": "Seize chevaux courent, Paris compte 91 marchés."}], 5, strict=True)]
    assert strict == [], "strict extraction takes only nouns that come with their article"
