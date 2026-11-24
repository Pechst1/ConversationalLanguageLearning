"""#1029: La Forge's «je» / «tu» agree in the gender the learner gave, or in none.

The walk of 23 Nov (`a2-en`, day 2, «Passé composé with être, and agreement»): Sam
signed up with no gender (``address_preference`` «neutral»), judged «J'ai parti tôt hier
soir.» and was printed «Correct: **Je suis partie tôt hier soir.**» — a feminine «je»
for a learner who never said she is a woman. The test-out on avoir printed «L'été
dernier, je suis ouverte la valise.» the same way.

The bank drew the «je» of an item at random from ``je_m`` / ``je_f`` and stored the key
that agreement made as one string, with no speaker attached: La Forge never read
``address_preference``. Now the learner is the speaker: «masculine» gets «Je suis
parti», «feminine» «Je suis partie», and «neutral» no item whose key agrees with a
«je» / «tu» (a named person, «Marie est partie», carries the agreement instead).
"""

from __future__ import annotations

import re
from uuid import UUID

import pytest

from app.core.forge import Rung
from app.db.models.atelier import AtelierSession
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services import item_bank as ib
from app.services.atelier import session_exercise_set
from app.services.forge import BankItemProvider
from app.services.grammar_catalog import FrenchCoreGrammarCatalog

ETRE = "FR2_A21_PC_ETRE"
AVOIR = "FR2_A21_PC_AVOIR"
PREFERENCES = ("neutral", "masculine", "feminine")
WALK_WRONG = "J'ai parti tôt hier soir."


def _participles() -> tuple[set[str], set[str]]:
    """The masculine and feminine singular participles of the être verbs (only where
    they differ: «né» / «née», never a participle that reads the same)."""

    lex = ib.lexicon()
    masculine: set[str] = set()
    feminine: set[str] = set()
    for verb in lex.verbs.values():
        try:
            m = lex.morph.participle(verb, "m", False, agree=True).lower()
            f = lex.morph.participle(verb, "f", False, agree=True).lower()
        except (KeyError, ib.RenderError, TypeError):
            continue
        if m != f:
            masculine.add(m)
            feminine.add(f)
    return masculine, feminine


MASCULINE, FEMININE = _participles()
#: «je suis parti», «tu n'es pas encore arrivée», «j'ai ouvert» (no agreement).
_AGREEMENT = re.compile(
    r"\b(?:je|tu)\s+(?:ne\s+|n['’])?(?:suis|es)\s+(?:(?:pas|plus|jamais|déjà|bien|enfin|encore|vite)\s+){0,2}([\wÀ-ÿ]+)",
    re.IGNORECASE,
)


def _speaker_genders(sentence: str) -> set[str]:
    """The genders a «je» / «tu» of ``sentence`` agrees in («m», «f»)."""

    found: set[str] = set()
    for word in _AGREEMENT.findall(sentence):
        word = word.lower()
        if word in FEMININE:
            found.add("f")
        elif word in MASCULINE:
            found.add("m")
    return found


ALLOWED = {"neutral": set(), "masculine": {"m"}, "feminine": {"f"}}


def _seance(db_session, preference: str, unit: str, n: int):
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    user = User(
        id=UUID(f"10290000-0000-4000-8000-{n:012d}"),
        email=f"forge-speaker-{preference}-{unit.lower()}@example.com",
        hashed_password="test",
        target_language="fr",
        address_preference=preference,
    )
    db_session.add(user)
    db_session.commit()
    concept = db_session.query(GrammarConcept).filter_by(external_id=unit).one()
    session = AtelierSession(
        id=UUID(f"10290000-0000-4000-9000-{n:012d}"),
        user_id=user.id,
        selected_concept_ids=[concept.id],
        status="in_progress",
        quote_payload={},
    )
    db_session.add(session)
    db_session.commit()
    return user, concept, session


@pytest.fixture()
def spoken(monkeypatch):
    """Every item the bank hands La Forge, as it comes out of the stream."""

    seen: list[ib.BankItem] = []
    original = ib.ItemBank.sample

    def sample(self, unit, rng, **kwargs):
        for item in original(self, unit, rng, **kwargs):
            seen.append(item)
            yield item

    monkeypatch.setattr(ib.ItemBank, "sample", sample)
    return seen


@pytest.mark.parametrize("unit", [ETRE, AVOIR], ids=["etre", "avoir"])
@pytest.mark.parametrize("preference", PREFERENCES)
def test_keys_follow(db_session, spoken, preference, unit):
    """The séance's set and its top-ups: no key agrees with a «je» / «tu» in a gender
    the learner did not give; on avoir, no ✗ sentence either («je suis ouverte»)."""

    n = PREFERENCES.index(preference) * 10 + (0 if unit == ETRE else 1)
    user, concept, session = _seance(db_session, preference, unit, n)
    session_exercise_set(db_session, user=user, session=session, concept=concept)
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    for drill in ("rafale", "choice", "tiles"):
        provider.top_up_many(concept_id=concept.id, rung=Rung.RECOGNISE, drill=drill, count=12)
    assert spoken, "La Forge drew no item from the bank"
    wrong: list[str] = []
    for item in spoken:
        if _speaker_genders(item.sentence) - ALLOWED[preference]:
            wrong.append(f"key: {item.sentence}")
        if unit == AVOIR:
            wrong.extend(
                f"✗: {sentence}"
                for sentence in item.wrong_sentences
                if _speaker_genders(sentence) - (ALLOWED[preference] or {"m"})
            )
    assert not wrong, f"a learner whose address_preference is «{preference}» is printed: {wrong[:6]}"


def _walk_bindings(monkeypatch):
    """The walk's item: «Hier soir»-at-the-end frame, a feminine «je», partir, tôt."""

    bank = ib.default_bank()
    lex = ib.lexicon()
    frame = next(frame for frame in bank.frames(ETRE) if frame.frame_id == "pc-etre-end")
    je_f = next(entry for entry in lex.pool("pron") if entry["id"] == "je_f")
    partir = next(verb for verb in lex.verbs.values() if verb["inf"] == "partir")
    tot = next(comp for comp in partir["comps"] if comp["fr"] == "tôt")
    hier_soir = next(entry for entry in lex.pool("time_past_end") if entry["fr"] == "hier soir")
    bindings = {"S": je_f, "V": partir, "O": dict(tot, id=tot.get("id") or tot["fr"]), "T": hier_soir}
    monkeypatch.setattr(ib.ItemBank, "frames", lambda self, unit: [frame] if unit == ETRE else [])
    monkeypatch.setattr(ib.ItemBank, "_bind", lambda self, frame, rng, known, story=frozenset(): dict(bindings))


@pytest.mark.parametrize(
    ("preference", "printed"),
    [
        ("masculine", "Je suis parti tôt hier soir."),
        ("feminine", "Je suis partie tôt hier soir."),
        ("neutral", None),
    ],
    ids=["m", "f", "neutral"],
)
def test_walk_item(db_session, monkeypatch, preference, printed):
    """«J'ai parti tôt hier soir.» is corrected into the learner's own «je»; for a
    learner who gave no gender it is not posed with a «je» at all."""

    n = 100 + PREFERENCES.index(preference)
    user, concept, session = _seance(db_session, preference, ETRE, n)
    session_exercise_set(db_session, user=user, session=session, concept=concept)
    _walk_bindings(monkeypatch)
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    made = provider.top_up_many(concept_id=concept.id, rung=Rung.DISCRIMINATE, drill="judge", count=1)
    shown = [item.payload for item in made]
    if printed is None:
        keys = [payload.get("correct_answer") for payload in shown]
        assert not shown, f"a learner with no gender given is printed {keys} as the right sentence"
        return
    assert len(shown) == 1, f"the walk's item was not posed to a «{preference}» learner"
    [payload] = shown
    assert WALK_WRONG in payload.get("labels", []) or payload.get("source_fr") == WALK_WRONG, payload
    key = payload.get("follow_up_key", {}).get("corrected_fr") or payload.get("correct_answer")
    assert key == printed, f"a «{preference}» learner is printed «{key}» as the right sentence"
