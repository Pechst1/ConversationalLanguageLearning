"""WP-119 phase 3: the dossier builder's repairs and refusals (§4.2), and the article fetch
rules (§4.1, §12.3: robots.txt, one attempt, six seconds, quotes and a hash only)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from app.services.revue import checks
from app.services.revue.builder import (
    FakeDossierProvider,
    SourceItem,
    StoryInput,
    build_dossier,
    provider_context,
    trim_quote,
)
from app.services.revue.dossier import quote_word_count
from app.services.revue.sources import (
    FETCH_BUDGET_SECONDS,
    RobotsCache,
    extract_text,
    fetch_article,
    text_hash,
)

WEEK = "2026-W40"
FIXTURES = Path(__file__).parent / "fixtures" / "revue_rss"

S1 = (
    "Les vendanges ont commencé fin août dans plusieurs domaines de la Côte-d'Or, deux semaines plus tôt "
    "que la moyenne des trente dernières années."
)
S2 = (
    "Selon la chambre d'agriculture, la récolte de 2026 représente environ 1,4 million d'hectolitres pour "
    "toute la Bourgogne, un volume comparable à celui des cinq dernières années selon les vignerons."
)
S3 = "Les vignerons de Beaune ont embauché plus de saisonniers que l'an dernier pour couper le raisin à la main."
ARTICLE = "\n".join([S1, S2, S3])


def story(text: str = ARTICLE) -> StoryInput:
    return StoryInput(
        key="vendanges",
        topic="food",
        week=WEEK,
        period=WEEK,
        today=date(2026, 10, 2),
        items=(
            SourceItem(
                source_id="kiosque_gastronomie",
                name="Le Kiosque",
                url="https://kiosque.test/gastronomie/vendanges-bourgogne.html",
                title="Les vendanges se terminent en Bourgogne",
                summary="Dans la Côte-d'Or, les vignerons rentrent les derniers raisins.",
                published_at=date(2026, 9, 29),
                article_text=text,
                fetch_status="fetched",
            ),
        ),
    )


def raw(claims: list[dict], **extra) -> dict:
    data = {
        "title_fr": "Des vendanges précoces en Bourgogne",
        "summary_fr": "En Bourgogne, les vendanges ont commencé plus tôt que d'habitude.",
        "topic": "food",
        "claims": claims,
        "entities": [{"name": "Bourgogne", "kind": "place"}],
        "uncertainties": ["Les sources ne disent pas si les prix vont changer."],
        "angles": [
            {"id": "a1", "fr": "Ce que ça change pour qui achète du vin", "purpose": "understand_change",
             "participation": "none", "guest_fit": "margaux_barman"},
            {"id": "a2", "fr": "Aider au tri du raisin", "purpose": "prepare_dispatch", "participation": "helps"},
        ],
        "places": [{"id": "vignoble_beaune", "name_fr": "Un vignoble à Beaune",
                    "brief": "Un vignoble à Beaune: rows of vines on the Côte, a stone cabotte, the Hospices roofs, late light"}],
        "time_scope": {"happening": "2026-08-25/2026-10-05", "relevant_until": "2026-10-20"},
        "vignette_object_fr": "une grappe de raisin",
    }
    data.update(extra)
    return data


def claim(cid: str, quote: str, fr: str | None = None, kind: str = "fact", **extra) -> dict:
    return {"id": cid, "kind": kind, "fr": fr or quote, "quote": quote, "source_id": "kiosque_gastronomie", **extra}


def build(data: dict, text: str = ARTICLE):
    return build_dossier(story(text), FakeDossierProvider(script={"*": data}), geocode=lambda d: d)


# ---------------------------------------------------------------------------
# Repairs and refusals
# ---------------------------------------------------------------------------


def test_a_41_word_quote_is_trimmed_to_its_sentence() -> None:
    long_quote = f"{S1} {S2}"
    assert quote_word_count(long_quote) >= 41
    result = build(raw([claim("c1", long_quote, fr="Les vendanges ont commencé fin août, deux semaines plus tôt."),
                        claim("c2", S3)]))
    assert result.ok, result.rejected
    first = result.dossier.claims_by_id()["c1"]
    assert first.quote == S1
    assert any(repair.startswith("trim:c1:") for repair in result.repairs)
    assert trim_quote(long_quote, ARTICLE) == S1


def test_an_unanchored_claim_is_dropped_and_two_left_still_make_a_dossier() -> None:
    result = build(raw([claim("c1", S1), claim("c2", S3),
                        claim("c3", "Le prix du vin va doubler en Bourgogne dès cet hiver.")]))
    assert result.ok
    assert [c.id for c in result.dossier.claims] == ["c1", "c2"]
    assert "drop:c3:quote_not_in_source" in result.repairs


def test_a_dossier_left_with_one_anchored_claim_is_rejected() -> None:
    result = build(raw([claim("c1", S1), claim("c2", "Une phrase qui n'est dans aucun article publié.")]))
    assert not result.ok
    assert "too_few_claims_anchored" in result.rejected


def test_a_claim_not_entailed_by_its_quote_is_dropped() -> None:
    result = build(raw([claim("c1", S1), claim("c2", S3),
                        claim("c4", S3, fr="Le gouvernement vote un budget.")]))
    assert result.ok
    assert "c4" not in result.dossier.claims_by_id()


def test_a_fact_that_reads_as_an_opinion_is_retyped_with_attribution() -> None:
    result = build(raw([claim("c1", S1, fr="Heureusement, les vendanges ont commencé fin août."), claim("c2", S3)]))
    assert result.ok
    c1 = result.dossier.claims_by_id()["c1"]
    assert c1.kind == "interpretation" and c1.attributed_to == "Le Kiosque"
    assert "retype:c1" in result.repairs


def test_an_interpretation_without_attribution_gets_its_outlet() -> None:
    result = build(raw([claim("c1", S1, kind="interpretation"), claim("c2", S3)]))
    assert result.ok
    assert result.dossier.claims_by_id()["c1"].attributed_to == "Le Kiosque"


def test_relative_dates_drop_a_claim_and_reject_a_summary() -> None:
    dropped = build(raw([claim("c1", S1), claim("c2", S3), claim("c3", S3, fr="Demain, les vignerons embauchent.")]))
    assert dropped.ok and "c3" not in dropped.dossier.claims_by_id()
    rejected = build(raw([claim("c1", S1), claim("c2", S3)], summary_fr="Demain, les vendanges finissent."))
    assert not rejected.ok and "relative_date" in rejected.rejected


def test_a_story_outside_the_week_is_rejected() -> None:
    result = build(raw([claim("c1", S1), claim("c2", S3)],
                       time_scope={"happening": "2026-06-01/2026-06-10", "relevant_until": "2026-06-30"}))
    assert not result.ok
    assert {"not_this_week", "expired"} & set(result.rejected)


def test_a_place_brief_names_its_place() -> None:
    data = raw([claim("c1", S1), claim("c2", S3)])
    data["places"] = [{"id": "vignoble", "name_fr": "Le vignoble de Beaune", "brief": "rows of vines, a stone hut, light"}]
    result = build(data)
    assert result.ok
    assert result.dossier.places[0].brief.startswith("Le vignoble de Beaune")


def test_ids_urls_dates_and_sources_come_from_the_feed_not_the_model() -> None:
    result = build(raw([claim("c1", S1, url="https://invented.example"), claim("c2", S3)]))
    assert result.ok
    dossier = result.dossier
    assert dossier.id.startswith("2026-w40-")
    assert {c.url for c in dossier.claims} == {"https://kiosque.test/gastronomie/vendanges-bourgogne.html"}
    assert dossier.sources[0].name == "Le Kiosque" and str(dossier.sources[0].published_at) == "2026-09-29"
    assert result.source_hashes == {"kiosque_gastronomie": text_hash(ARTICLE)}
    assert checks.passed(checks.run_dossier_checks(dossier, source_texts={"kiosque_gastronomie": ARTICLE}, week=WEEK))


def test_a_provider_failure_rejects_the_story_only() -> None:
    class Down(FakeDossierProvider):
        def build_dossier(self, context):  # noqa: ANN001, ANN201
            raise RuntimeError("down")

    result = build_dossier(story(), Down(), geocode=lambda d: d)
    assert not result.ok and result.rejected == ["provider_failed"]


def test_without_an_article_the_teaser_is_the_source() -> None:
    teaser_only = StoryInput(**{**story().__dict__, "items": (SourceItem(**{**story().items[0].__dict__, "article_text": "", "fetch_status": "robots_refused"}),)})
    context = provider_context(teaser_only)
    assert context["items"][0]["is_teaser_only"] is True
    assert "Les vendanges se terminent en Bourgogne" in context["items"][0]["text"]
    assert len(provider_context(story("x" * 20000))["items"][0]["text"]) == 6000


# ---------------------------------------------------------------------------
# The article fetch (§12.3)
# ---------------------------------------------------------------------------


class Host:
    def __init__(self, robots: str | None = "User-agent: *\nDisallow: /prive/\n", *, fail=None) -> None:
        self.robots = robots
        self.fail = fail or {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path in self.fail:
            raise self.fail[path]
        if path == "/robots.txt":
            return httpx.Response(200, text=self.robots) if self.robots is not None else httpx.Response(404)
        page = FIXTURES / "articles" / path.rsplit("/", 1)[-1]
        return httpx.Response(200, text=page.read_text(encoding="utf-8")) if page.exists() else httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


URL = "https://kiosque.test/gastronomie/vendanges-bourgogne.html"


def test_an_article_is_fetched_once_and_read_without_the_page_furniture() -> None:
    host = Host()
    article = fetch_article(URL, client=host.client(), enabled=True)
    assert article.ok
    assert host.paths() == ["/robots.txt", "/gastronomie/vendanges-bourgogne.html"]
    assert "deux semaines plus tôt" in article.text
    for furniture in ("Abonnez-vous", "Accueil", "mentions légales", "À lire aussi", "tracking", "Photo d'illustration"):
        assert furniture not in article.text
    assert article.sha256 == text_hash(article.text)
    # Every request carries the intake's user agent and a timeout inside the budget.
    for request in host.requests:
        assert "ConversationalLanguageLearningBot" in request.headers["user-agent"]
        timeout = request.extensions["timeout"]
        assert 0 < timeout["read"] <= FETCH_BUDGET_SECONDS


def test_robots_txt_is_respected_and_read_once_per_host() -> None:
    host = Host()
    cache = RobotsCache()
    client = host.client()
    refused = fetch_article("https://kiosque.test/prive/sport/rugby-prive.html", client=client, robots=cache, enabled=True)
    assert refused.status == "robots_refused" and not refused.text
    fetched = fetch_article(URL, client=client, robots=cache, enabled=True)
    assert fetched.ok
    assert host.paths() == ["/robots.txt", "/gastronomie/vendanges-bourgogne.html"], "no page under /prive/, one robots.txt"


def test_a_refusing_source_and_the_flag_cost_no_request() -> None:
    host = Host()
    assert fetch_article(URL, fetch_policy="refuses", client=host.client(), enabled=True).status == "policy_refused"
    assert fetch_article(URL, client=host.client(), enabled=False).status == "disabled"
    assert host.requests == []


def test_one_attempt_no_retry_on_a_timeout() -> None:
    host = Host(fail={"/gastronomie/vendanges-bourgogne.html": httpx.ReadTimeout("slow")})
    article = fetch_article(URL, client=host.client(), enabled=True)
    assert article.status == "failed" and article.reason == "ReadTimeout"
    assert host.paths().count("/gastronomie/vendanges-bourgogne.html") == 1


def test_the_six_second_budget_covers_robots_and_the_page() -> None:
    ticks = iter([0.0, 0.1, 6.5])  # start, robots.txt, then the page: the budget is spent
    host = Host()
    article = fetch_article(URL, client=host.client(), enabled=True, clock=lambda: next(ticks))
    assert article.status == "failed" and article.reason == "budget_spent"
    assert host.paths() == ["/robots.txt"]


def test_an_unreachable_robots_txt_means_no_fetch_and_a_403_means_disallow() -> None:
    host = Host(fail={"/robots.txt": httpx.ConnectError("down")})
    assert fetch_article(URL, client=host.client(), enabled=True).status == "robots_unverified"
    assert host.paths() == ["/robots.txt"]

    class Forbidden(Host):
        def __call__(self, request):  # noqa: ANN001, ANN204
            self.requests.append(request)
            return httpx.Response(403) if request.url.path == "/robots.txt" else httpx.Response(200, text="<p>x</p>")

    forbidden = Forbidden()
    assert fetch_article(URL, client=forbidden.client(), enabled=True).status == "robots_refused"
    missing = Host(robots=None)
    assert fetch_article(URL, client=missing.client(), enabled=True).ok, "no robots.txt allows everything"


@pytest.mark.parametrize("html", ["", "<html><body><nav>Menu</nav></body></html>"])
def test_an_empty_page_is_empty(html: str) -> None:
    assert extract_text(html) == ""
