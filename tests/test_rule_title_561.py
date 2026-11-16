"""#561 / #522 stage 2 and 5: La Forge and the Cahier name a rule as the rule card does.

Walk 6 Nov 2026 (`a1-de-fresh`, German chrome): the rule card said «Ich bin, du bist:
Subjektpronomen und être», La Forge's header and end sheet and every Cahier row said
«Je suis, tu es : les pronoms et être». Both surfaces were handed `title_fr` only, so
the page had nothing in the learner's language to show. The payloads now carry
`title_native` (`concept_title(concept, chrome language)`) next to `title_fr`.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models.grammar import GrammarConcept, GrammarConceptLocalization
from app.db.models.user import User
from app.services.atelier import AtelierScheduler
from app.services.chrome_language import user_chrome_language
from app.services.concept_titles import concept_title
from tests.test_rule_title_522 import _concept


def _learner(client: TestClient, db_session, language: str) -> dict[str, str]:
    email = f"{uuid4()}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "atelier-secure", "target_language": "fr", "native_language": language},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "atelier-secure"}).json()[
        "access_token"
    ]
    user = db_session.query(User).filter(User.email == email).one()
    assert user_chrome_language(user) == language, "the test learner must read the chrome of their language"
    return {"Authorization": f"Bearer {token}"}


def _etre(db_session) -> GrammarConcept:
    """A rule whose English, German and French titles all differ (as FR2_A11_ETRE's do)."""

    AtelierScheduler(db_session).ensure_catalog()
    return _concept(db_session)


@pytest.mark.parametrize("language", ["de", "fr"])
def test_cahier_rule_title_in_chrome(client: TestClient, db_session, language) -> None:
    concept = _etre(db_session)
    headers = _learner(client, db_session, language)

    body = client.get("/api/v1/atelier/forge/map", headers=headers).json()
    rules = {rule["concept_id"]: rule for band in body["bands"] for rule in band["rules"]}
    rule = rules[concept.id]

    expected = concept_title(concept, language)
    assert rule.get("title_native") == expected, (
        f"the Cahier row names the rule {rule.get('title_fr')!r} for a {language} learner, "
        f"not {expected!r}: {rule}"
    )
    assert rule["title_fr"] == concept_title(concept, "fr")


@pytest.mark.parametrize("language", ["de", "fr"])
def test_forge_header_rule_title_in_chrome(client: TestClient, db_session, language) -> None:
    """La Forge's header and end sheet read the session's concept: it carries the chrome title."""

    AtelierScheduler(db_session).ensure_catalog()
    headers = _learner(client, db_session, language)

    first = client.get("/api/v1/atelier/today", headers=headers).json()
    assert first["concepts"], "the learner's day has no rule"
    shown_concept = db_session.get(GrammarConcept, first["concepts"][0]["id"])
    # The day's rule has a German and a French title that differ from each other.
    for locale, title in (("de", "Ich bin, du bist"), ("fr", "Je suis, tu es")):
        row = (
            db_session.query(GrammarConceptLocalization)
            .filter_by(concept_id=shown_concept.id, locale=locale)
            .one_or_none()
        )
        if row is None:
            db_session.add(GrammarConceptLocalization(concept_id=shown_concept.id, locale=locale, title=title))
        else:
            row.title = title
    db_session.commit()
    db_session.refresh(shown_concept)

    today = client.get("/api/v1/atelier/today", headers=headers).json()
    shown = next(item for item in today["concepts"] if item["id"] == shown_concept.id)
    expected = concept_title(shown_concept, language)
    assert shown.get("title_native") == expected, (
        f"La Forge's header names the rule {shown.get('title_fr')!r} for a {language} learner, "
        f"not {expected!r}"
    )
    assert shown["title_fr"] == concept_title(shown_concept, "fr")


@pytest.mark.parametrize("language", ["de", "fr"])
def test_forge_state_title_in_chrome(db_session, language) -> None:
    """The forge's per-rule state (the Cahier's source) is titled for the learner, not by `concept.name`."""

    from app.db.models.grammar import UserGrammarProgress
    from app.services.forge import ForgeService
    from tests.test_rule_title_522 import _learner as make_learner

    concept = _concept(db_session)
    user = make_learner(db_session, language)
    db_session.add(UserGrammarProgress(user_id=user.id, concept_id=concept.id, reps=1))
    db_session.flush()

    rows = ForgeService(db_session).state_for_user(user=user)
    title = next(row["title"] for row in rows if row["concept_id"] == concept.id)

    assert title == concept_title(concept, language), title
    assert title != concept.name, "the English catalogue name reached the learner"


# ---------------------------------------------------------------------------
# Re-test 10 Nov: the Cahier's rule list and the Éclair pair label
# ---------------------------------------------------------------------------
#
# #566 moved the map's rule sheet to `title_native`, but the Cahier's list rows and
# the rule page are drawn from `/grammar/notebook`, which only carried `title_fr`
# (and a `display_title` for the page's `?locale=`, «en» by default), and Éclair's
# pairs only carried `title_fr`. Each of these payloads now names the rule with
# `concept_title(concept, chrome language)` as `title_native`, like the map does.


def _first_notebook_rule(client: TestClient, db_session, headers: dict[str, str]) -> tuple[dict, GrammarConcept]:
    rows = client.get("/api/v1/grammar/notebook", headers=headers, params={"limit": 500}).json()
    assert rows, "the Cahier lists no rule"
    row = rows[0]
    concept = db_session.get(GrammarConcept, row["id"])
    db_session.refresh(concept)
    return row, concept


@pytest.mark.parametrize("language", ["de", "en", "fr"])
def test_cahier_rule_list_title_in_chrome(client: TestClient, db_session, language) -> None:
    headers = _learner(client, db_session, language)
    row, concept = _first_notebook_rule(client, db_session, headers)

    expected = concept_title(concept, language)
    if language != "fr":
        assert expected != concept_title(concept, "fr"), "the test rule needs a title that differs from the French"
    assert row.get("title_native") == expected, (
        f"the Cahier list names the rule {row.get('title_fr')!r} for a {language} learner, "
        f"while the rule card says {expected!r}"
    )
    assert row["title_fr"] == concept_title(concept, "fr")

    page = client.get(f"/api/v1/grammar/notebook/{concept.id}", headers=headers).json()
    assert page.get("title_native") == expected, (
        f"the Cahier's rule page names the rule {page.get('title_fr')!r} for a {language} learner, not {expected!r}"
    )


@pytest.mark.parametrize("language", ["de", "en"])
def test_eclair_pair_rules_title_in_chrome(db_session, language) -> None:
    """The Éclair pair label (map, recap, round) reads the pair's rules: they carry the chrome title."""

    from app.services.eclair import eclair_pairs
    from tests.test_rule_title_522 import _learner as make_learner
    from tests.test_wp_s7_momentum import _contrasting_pair, _introduce

    with _contrasting_pair(db_session) as (first, second):
        user = make_learner(db_session, language)
        _introduce(db_session, user, first, second)
        pairs = eclair_pairs(db_session, user)
        assert pairs, "the two introduced partners opened no Éclair pair"
        for rule in pairs[0]["rules"]:
            concept = db_session.get(GrammarConcept, rule["concept_id"])
            expected = concept_title(concept, language)
            assert rule.get("title_native") == expected, (
                f"Éclair names the rule {rule.get('title_fr')!r} for a {language} learner, not {expected!r}"
            )
            assert rule["title_fr"] == concept_title(concept, "fr")
