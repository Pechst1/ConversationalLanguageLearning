"""F-1 (content program 2026-10-03): the grammar unit page's payload.

The unit page shows the full rule card, the x-ray sentence with its marks and
the «Compare with» partners by title. The payload changes are additive:

1. ``unit_xray`` reads the catalogue's x-ray (discontinuous tokens kept as-is);
2. ``card_with_partner_titles`` titles every known partner, leaves the rest;
3. the notebook detail carries ``rule_card``, ``xray`` and ``sub_band`` for a
   v2 unit, and the concept serializer carries ``xray``.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.models.grammar import GrammarConcept
from app.services.atelier import serialize_concept
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.grammar_map import card_with_partner_titles, unit_titles, unit_xray
from app.services.rule_cards import rule_card_for


def _concept(xray: object) -> SimpleNamespace:
    return SimpleNamespace(source_refs={"blueprint_seed": {"sentence_xray": xray}})


def test_unit_xray_reads_the_marks_and_keeps_discontinuous_tokens() -> None:
    xray = unit_xray(
        _concept(
            {
                "sentence": "Je ne bois que du thé le matin.",
                "explanation": "ignored",
                "marks": [
                    {"token": "ne...que", "role": "restriction", "explanation": "ne…que = only", "color": "ink"},
                    {"token": "du thé", "role": "article_kept", "explanation": "article stays"},
                    {"token": "", "role": "empty", "explanation": "dropped"},
                    "not a mark",
                ],
            }
        )
    )
    assert xray == {
        "sentence": "Je ne bois que du thé le matin.",
        "marks": [
            {"token": "ne...que", "role": "restriction", "explanation": "ne…que = only"},
            {"token": "du thé", "role": "article_kept", "explanation": "article stays"},
        ],
    }


@pytest.mark.parametrize(
    "refs",
    [None, {}, {"blueprint_seed": {}}, {"blueprint_seed": {"sentence_xray": {"sentence": "Bonjour.", "marks": []}}}],
)
def test_unit_xray_is_none_without_a_sentence_and_a_mark(refs) -> None:
    assert unit_xray(SimpleNamespace(source_refs=refs)) is None


def test_partners_get_their_titles_and_unknown_ones_stay_untitled() -> None:
    card = rule_card_for("FR2_A21_PC_ETRE")
    assert card and card.get("contrast_with"), "the authored A2 card has partners"
    titles = unit_titles()
    assert "FR2_A21_PC_AVOIR" in titles and titles["FR2_A21_PC_AVOIR"].get("fr")

    enriched = card_with_partner_titles(
        {**card, "contrast_with": [*card["contrast_with"], {"id": "FR2_NOPE"}, {"note": {}}]}
    )
    partners = {partner["id"]: partner for partner in enriched["contrast_with"]}
    assert partners["FR2_A21_PC_AVOIR"]["title"] == titles["FR2_A21_PC_AVOIR"]
    assert partners["FR2_A21_PC_AVOIR"]["note"]["en"], "the authored note is kept"
    assert "title" not in partners["FR2_NOPE"]
    assert len(enriched["contrast_with"]) == len(card["contrast_with"]) + 1, "an id-less entry is dropped"
    # The authored card itself is never mutated.
    assert all("title" not in partner for partner in rule_card_for("FR2_A21_PC_ETRE")["contrast_with"])
    # A card with no partners (v1) comes back as it was.
    v1 = {"example": {"fr": "x"}, "rule": {"en": "y"}}
    assert card_with_partner_titles(v1) is v1
    assert card_with_partner_titles(None) is None


@pytest.fixture()
def v2(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    yield
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v1")
    FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()


def _token(client: TestClient) -> str:
    email = f"f1-{uuid4().hex}@example.com"
    password = "f1-unit-page-secure"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "de"},
    )
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]


def test_notebook_detail_carries_card_xray_and_sub_band_for_a_v2_unit(client: TestClient, db_session, v2) -> None:
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_A21_PC_ETRE").one()
    headers = {"Authorization": f"Bearer {_token(client)}"}

    detail = client.get(f"/api/v1/grammar/notebook/{concept.id}", headers=headers, params={"locale": "de"})
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["sub_band"] == "A2.1"
    card = body["rule_card"]
    assert card["example"]["fr"] and card["rule"]["de"] and card["how"]["de"]
    assert any(partner.get("title", {}).get("fr") for partner in card["contrast_with"])
    xray = body["xray"]
    assert xray["sentence"]
    assert xray["marks"] and set(xray["marks"][0]) == {"token", "role", "explanation"}

    rows = client.get("/api/v1/grammar/notebook", headers=headers, params={"limit": 500}).json()
    bands = {row["external_id"]: row["sub_band"] for row in rows}
    assert bands["FR2_A21_PC_ETRE"] == "A2.1"
    assert all(band for band in bands.values()), "every v2 row names its sub-band"

    payload = serialize_concept(concept)
    assert payload["xray"] == xray
    assert payload["rule_card"]["contrast_with"][0].get("title")


def test_a_v1_notebook_row_has_no_sub_band_and_the_detail_still_validates(client: TestClient, db_session) -> None:
    FrenchCoreGrammarCatalog(db_session).ensure_catalog(archive_legacy=True)
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_B1_COND_001").one()
    headers = {"Authorization": f"Bearer {_token(client)}"}
    body = client.get(f"/api/v1/grammar/notebook/{concept.id}", headers=headers).json()
    assert body["sub_band"] is None
    assert "rule_card" in body and "xray" in body
