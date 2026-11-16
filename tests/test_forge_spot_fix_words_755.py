"""#755 «Trouve l'erreur» says how many words to touch, read from the item.

Walk 13 Nov: the B1 séance «Deux pronoms ensemble» posed «Je lui le donne.»,
«Je leur les donne.» and «Il me en a parlé.» as spot drills under «Touche le mot
faux et corrige-le.» (one word), though each fix touches two words. The count
(``fix_words``, #300) was set only by the two builders that make a repair item
(the bank's ``transform_item`` and the learner's own sentence); the fallback set's
repair items reach the spot drill without it. The drill's hint now comes from
the item it poses, wherever the item was built.
"""

from __future__ import annotations

from app.config import settings
from app.core.forge import Rung
from app.db.models.grammar import GrammarConcept
from app.services import forge_drills as drills
from app.services.forge import ForgeService, _store_state, forge_state_of
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from tests.test_wp_s2_item_bank import _session, _user

DOUBLE_PRONOUNS = "FR2_B11_DOUBLE_PRONOUNS"


def _spot_items(db_session, monkeypatch) -> list[dict]:
    """Every item the B1 «Deux pronoms ensemble» séance poses as a spot drill."""

    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    monkeypatch.setattr(drills, "rank_drills", lambda **_kw: [drills.DRILL_SPOT])
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == DOUBLE_PRONOUNS).one()
    user = _user(db_session, cefr="B1.1")
    session = _session(db_session, user, [concept])
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(Rung.TRANSFORM)
    state.tracks[0].needs_spaced = False
    _store_state(session, state)
    db_session.commit()

    posed: list[dict] = []
    for _ in range(12):
        nxt = forge.next_item(user=user, session=session)
        if nxt is None or nxt.get("drill") != drills.DRILL_SPOT or int(nxt.get("rung", -1)) != Rung.TRANSFORM:
            break
        posed.append(nxt["item"])
        # The next item of the same slot: this one counts as served, none pending.
        state = forge_state_of(session)
        state.served_fingerprints.append(str(nxt["fingerprint"]))
        state.pending = None
        _store_state(session, state)
        db_session.commit()
    return posed


def test_spot_counts_words(db_session, monkeypatch) -> None:
    """Every spot of the B1 «Deux pronoms ensemble» séance says how many words to fix."""

    try:
        posed = _spot_items(db_session, monkeypatch)
    finally:
        FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()
    sources = {str(item.get("source_fr") or item.get("source")) for item in posed}
    assert {"Je lui le donne.", "Je leur les donne.", "Il me en a parlé."} <= sources, sources
    for item in posed:
        source = item.get("source_fr") or item.get("source")
        words = drills.fix_words(source, item.get("expected_answer"))
        if words > 1:
            assert item.get("fix_words") == words, (
                f"«{source}» → «{item.get('expected_answer')}» touches {words} words, "
                f"but the card says to touch {item.get('fix_words') or 1}"
            )
        else:
            assert "fix_words" not in item, source

