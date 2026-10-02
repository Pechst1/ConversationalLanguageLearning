"""WP-120 phase B: the vignette's pictogram — the house grammar, its validator, the cache.

The validator is the gate between a model's SVG and a learner's screen: the seven
authored fallbacks and the fake provider pass it; a hostile SVG (script, external
image, off-palette fill, text, too many shapes, an open path, a shape outside the
stamp's circle) is rejected with a named code; a near-ink colour is snapped once and
logged. ``pictogram_for`` draws once per dossier, regenerates once with the errors
named, then falls back to the topic pictogram — and caches either way.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from loguru import logger
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.db.models.revue_vignette import RevuePictogram
from app.services.revue import pictogram as pg
from app.services.revue.pictogram import (
    FALLBACK_TOPICS,
    GRAMMAR,
    INKS,
    PICTOGRAM_DIR,
    FakePictogramProvider,
    fallback_svg,
    pictogram_for,
    validate_pictogram,
)

HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
BASE = (
    '<circle cx="50" cy="50" r="20" fill="#1D3A8A"/>'
    '<rect x="40" y="60" width="20" height="8" fill="#D8321A"/>'
    '<path d="M50 30 L60 45 L40 45 Z" fill="#F3C318"/>'
)


def svg(body: str = BASE, head: str = HEAD) -> str:
    return f"{head}{body}</svg>"


def codes(result) -> set[str]:
    return {error.split(":", 1)[0] for error in result.errors}


# -- the grammar --------------------------------------------------------------


def test_grammar_constants_follow_the_spec() -> None:
    assert GRAMMAR["viewbox"] == "0 0 100 100"
    assert (GRAMMAR["min_elements"], GRAMMAR["max_elements"]) == (3, 12)
    assert set(GRAMMAR["shapes"]) == {"path", "circle", "rect", "ellipse"}
    assert GRAMMAR["max_bytes"] == 2048 and GRAMMAR["radius"] == 40 and GRAMMAR["centre"] == (50, 50)
    assert GRAMMAR["path_commands"] == "MLCQZ" and GRAMMAR["max_stroke_width"] == 6
    assert set(INKS.values()) == {"#F1ECE1", "#14110D", "#1D3A8A", "#D8321A", "#F3C318", "#2C6A5D", "#C2890F"}


@pytest.mark.parametrize("topic", FALLBACK_TOPICS)
def test_the_seven_authored_fallbacks_pass_the_validator(topic: str) -> None:
    raw = (PICTOGRAM_DIR / f"{topic}.svg").read_text(encoding="utf-8")
    result = validate_pictogram(raw)
    assert result.ok, result.errors
    assert result.snapped_colours == []
    assert result.svg_normalised and len(result.svg_normalised.encode()) <= 2048
    assert fallback_svg(topic) == result.svg_normalised


def test_exactly_seven_fallbacks_one_per_topic() -> None:
    assert sorted(path.stem for path in Path(PICTOGRAM_DIR).glob("*.svg")) == sorted(FALLBACK_TOPICS)
    assert fallback_svg("not-a-topic") == fallback_svg("culture")


@pytest.mark.parametrize("obj", ["une grappe de raisin", "une urne", "une galette avec sa fève", "un vélo", "x"])
def test_the_fake_provider_draws_valid_deterministic_svg(obj: str) -> None:
    provider = FakePictogramProvider()
    first = provider.draw(object_fr=obj, topic="food")
    assert first == provider.draw(object_fr=obj, topic="food")
    assert validate_pictogram(first).ok, validate_pictogram(first).errors


def test_valid_svg_is_rebuilt_from_the_whitelist() -> None:
    raw = svg(
        '<circle cx="50.000" cy="50" r="20px" fill="#1d3a8a" />\n'
        '<rect x="40" y="60" width="20" height="8" rx="2" fill="#D8321A" stroke="#14110D" stroke-width="2" '
        'stroke-linejoin="round"/>\n<path d="M50,30 L60,45 L40,45 Z M50 50 Q55 55 50 60 Z" fill="#F3C318" fill-rule="evenodd"/>',
        head='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0,0,100,100" width="100" height="100">',
    )
    result = validate_pictogram(raw)
    assert result.ok, result.errors
    assert result.svg_normalised == (
        HEAD + '<circle cx="50" cy="50" r="20" fill="#1D3A8A"/>'
        '<rect x="40" y="60" width="20" height="8" rx="2" fill="#D8321A" stroke="#14110D" stroke-width="2" stroke-linejoin="round"/>'
        '<path d="M50 30L60 45L40 45ZM50 50Q55 55 50 60Z" fill="#F3C318" fill-rule="evenodd"/>'
        "</svg>"
    )


# -- hostile and off-grammar input ----------------------------------------------


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (svg(BASE + "<script>alert(1)</script>"), "forbidden_element"),
        (svg(BASE + '<image href="https://evil.example/x.png" x="0" y="0" width="10" height="10"/>'), "forbidden_element"),
        (
            svg(BASE + '<image xlink:href="https://evil.example/x.png"/>',
                head='<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 100">'),
            "forbidden_namespace",
        ),
        (svg(BASE + '<text x="40" y="50" fill="#14110D">Vote</text>'), "forbidden_element"),
        (svg(BASE + "<style>circle{fill:red}</style>"), "forbidden_element"),
        (svg(BASE + '<linearGradient><stop offset="0"/></linearGradient>'), "forbidden_element"),
        (svg(BASE + '<g><circle cx="50" cy="50" r="3" fill="#14110D"/></g>'), "forbidden_element"),
        (svg(BASE.replace('r="20"', 'r="20" onclick="alert(1)"')), "forbidden_attribute"),
        (svg(BASE.replace('r="20"', 'r="20" id="sun"')), "forbidden_attribute"),
        (svg(BASE.replace('r="20"', 'r="20" style="fill:red"')), "forbidden_attribute"),
        (svg(BASE.replace('r="20"', 'r="20" transform="scale(3)"')), "forbidden_attribute"),
        (svg(BASE.replace("#1D3A8A", "#FF00FF")), "off_palette"),
        (svg(BASE.replace("#1D3A8A", "url(#g)")), "bad_colour"),
        (svg(BASE.replace('fill="#1D3A8A"', 'fill="#1D3A8A" stroke="#D8321A" stroke-width="2"')), "stroke_not_ink"),
        (svg(BASE.replace('fill="#1D3A8A"', 'fill="#1D3A8A" stroke="#14110D" stroke-width="9"')), "stroke_width"),
        (svg(BASE.replace(' fill="#1D3A8A"', "")), "missing_fill"),
        (svg("".join(f'<circle cx="50" cy="50" r="{i + 1}" fill="#1D3A8A"/>' for i in range(13))), "too_many_elements"),
        (svg('<circle cx="50" cy="50" r="20" fill="#1D3A8A"/><circle cx="50" cy="50" r="2" fill="#14110D"/>'), "too_few_elements"),
        (svg(BASE.replace("L40 45 Z", "L40 45")), "open_path"),
        (svg(BASE.replace("M50 30 L60 45 L40 45 Z", "M50 30 L60 45 Z M40 45 L45 50")), "open_path"),
        (svg(BASE.replace("M50 30 L60 45 L40 45 Z", "M50 30 l10 15 L40 45 Z")), "path_command"),
        (svg(BASE.replace("M50 30 L60 45 L40 45 Z", "M50 30 A5 5 0 0 1 60 45 Z")), "path_command"),
        (svg(BASE.replace('r="20"', 'r="45"')), "out_of_circle"),
        (svg(BASE.replace('x="40" y="60"', 'x="70" y="80"')), "out_of_circle"),
        (svg(BASE.replace("M50 30", "M50 2")), "out_of_circle"),
        (svg(BASE, head='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'), "bad_viewbox"),
        (svg(BASE + "Vote !"), "stray_text"),
        ('<!DOCTYPE svg [<!ENTITY x "boom">]>' + svg(BASE), "forbidden_xml"),
        ("<svg", "parse_error"),
        ('<html xmlns="http://www.w3.org/1999/xhtml"/>', "forbidden_namespace"),
        (svg(BASE + "<!--" + "x" * 20000 + "-->"), "too_large"),
    ],
)
def test_hostile_or_off_grammar_svg_is_rejected(raw: str, code: str) -> None:
    result = validate_pictogram(raw)
    assert not result.ok and result.svg_normalised is None
    assert code in codes(result), result.errors


def test_more_than_two_kilobytes_normalised_is_rejected() -> None:
    long_path = "M50 20 " + " ".join(f"L{50 + (i % 7) * 1.37:.2f} {30 + (i % 11) * 1.91:.2f}" for i in range(250)) + " Z"
    result = validate_pictogram(svg(BASE + f'<path d="{long_path}" fill="#2C6A5D"/>'))
    assert not result.ok and "too_large" in codes(result)


def test_near_ink_colours_are_snapped_once_and_logged() -> None:
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)), level="INFO")
    try:
        result = validate_pictogram(svg(BASE.replace("#1D3A8A", "#203c90").replace("#D8321A", "black")))
    finally:
        logger.remove(sink)
    assert result.ok, result.errors
    assert result.snapped_colours == ["#203C90→#1D3A8A", "#000000→#14110D"]
    assert "#203C90" not in (result.svg_normalised or "") and 'fill="#1D3A8A"' in (result.svg_normalised or "")
    assert any("snapped off-palette colours" in message for message in messages)


def test_pure_black_snaps_to_ink_but_magenta_does_not() -> None:
    assert pg.nearest_ink("#000000")[0] == "#14110D"
    assert pg.nearest_ink("#FF00FF")[1] > pg.SNAP_TOLERANCE


# -- pictogram_for: cache, one regeneration, fallback ------------------------------


@pytest.fixture(scope="module")
def pictogram_table(db_engine) -> Generator[None, None, None]:
    created = not inspect(db_engine).has_table(RevuePictogram.__tablename__)
    if created:
        RevuePictogram.__table__.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        if created:
            RevuePictogram.__table__.drop(bind=db_engine, checkfirst=True)


def dossier(topic: str = "food", obj: str | None = "une grappe de raisin") -> SimpleNamespace:
    return SimpleNamespace(id=f"test-{uuid.uuid4().hex[:10]}", topic=topic, vignette_object_fr=obj)


class Scripted:
    """Answers each draw from a list; records what it was told."""

    name = "scripted"

    def __init__(self, answers: list[str | Exception]) -> None:
        self.answers = list(answers)
        self.calls: list[dict] = []

    def draw(self, *, object_fr: str, topic: str, errors: list[str] | None = None) -> str:
        self.calls.append({"object_fr": object_fr, "errors": list(errors or [])})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_pictogram_for_draws_once_then_serves_the_cache(db_session: Session, pictogram_table) -> None:
    d = dossier()
    provider = FakePictogramProvider()
    first = pictogram_for(db_session, d, provider)
    assert validate_pictogram(first).ok and len(provider.calls) == 1
    second = pictogram_for(db_session, d, provider)
    assert second == first and len(provider.calls) == 1
    row = db_session.get(RevuePictogram, d.id)
    assert row.object_fr == "une grappe de raisin" and row.prompt_version == pg.PROMPT_VERSION
    assert row.validated_at is not None
    # Every learner shares it, even through another provider.
    assert pictogram_for(db_session, d, Scripted([])) == first


def test_pictogram_for_regenerates_once_with_the_errors_named(db_session: Session, pictogram_table) -> None:
    d = dossier()
    good = FakePictogramProvider().draw(object_fr="une urne", topic="politics")
    provider = Scripted([svg(BASE + "<script>x</script>"), good])
    out = pictogram_for(db_session, d, provider)
    assert out == validate_pictogram(good).svg_normalised
    assert provider.calls[0]["errors"] == []
    assert provider.calls[1]["errors"] == ["forbidden_element: script"]


def test_pictogram_for_falls_back_after_two_failures_and_caches_it(db_session: Session, pictogram_table) -> None:
    d = dossier(topic="sport", obj="un maillot jaune")
    provider = Scripted([svg(BASE.replace("#1D3A8A", "#FF00FF")), RuntimeError("timeout")])
    out = pictogram_for(db_session, d, provider)
    assert out == fallback_svg("sport") and len(provider.calls) == 2
    assert provider.calls[1]["errors"] == ["off_palette: fill=#FF00FF"]
    assert db_session.get(RevuePictogram, d.id).prompt_version == "fallback-v1:sport"
    again = Scripted([])
    assert pictogram_for(db_session, d, again) == out and again.calls == []


def test_a_dossier_without_an_object_gets_its_topic_fallback_uncached(db_session: Session, pictogram_table) -> None:
    d = dossier(topic="nature", obj=None)
    provider = Scripted([])
    assert pictogram_for(db_session, d, provider) == fallback_svg("nature")
    assert provider.calls == [] and db_session.get(RevuePictogram, d.id) is None
