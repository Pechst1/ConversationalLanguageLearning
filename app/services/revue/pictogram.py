"""The vignette's pictogram: an SVG in the house grammar, drawn once per dossier (WP-120 §4.2).

The model is asked for one object («une urne», «une grappe de raisin») as a small SVG;
:func:`validate_pictogram` decides whether it may be shown. The grammar (:data:`GRAMMAR`):

- ``viewBox="0 0 100 100"``; 3 to 12 shape elements, each one of ``path``, ``circle``,
  ``rect``, ``ellipse``, directly under ``<svg>`` (no groups, no transforms);
- fills from the seven av2 inks only (:data:`INKS`); an off-palette colour within
  :data:`SNAP_TOLERANCE` (RGB distance) of an ink is snapped to it, once, and logged;
  anything further is rejected;
- no stroke except ink (``#14110D``) at width 0 to 6;
- no text, gradients, images, scripts, styles, xlink, filters, ids, event handlers;
- at most 2 KB once normalised;
- every point of the drawing (path control points, circle and ellipse rims, rect
  corners, each widened by half the stroke) inside the circle of radius 40 around (50, 50);
- "round construction": every path is absolute ``M L C Q Z`` only and every subpath is
  closed with ``Z``.

The XML is parsed with ``defusedxml`` (no DTD, no entities) and the output is rebuilt
from the whitelist, never echoed: the normalised SVG holds only the attributes listed
here, with numbers re-printed.

:func:`pictogram_for` is the cached entry point: one row per dossier in
``revue_pictograms``; on a miss it asks the provider, regenerates once with the errors
named, then falls back to the authored topic pictogram in ``evergreen/pictograms/``. The
fallback is stored too, so a story costs at most two small text calls, ever.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from xml.etree.ElementTree import Element

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.revue_vignette import RevuePictogram

PROMPT_VERSION = "pictogram-v1"
FALLBACK_VERSION = "fallback-v1"
PICTOGRAM_DIR = Path(__file__).with_name("evergreen") / "pictograms"

SVG_NS = "http://www.w3.org/2000/svg"

#: The seven av2 inks (``scripts/art/atelier_art.py`` ``PALETTE_WORDS``), name → hex.
INKS: dict[str, str] = {
    "paper": "#F1ECE1",
    "ink": "#14110D",
    "blue": "#1D3A8A",
    "red": "#D8321A",
    "yellow": "#F3C318",
    "green": "#2C6A5D",
    "ochre": "#C2890F",
}
STROKE_INK = INKS["ink"]
#: The one tolerance pass: an off-palette colour this close (Euclidean RGB) snaps to the nearest ink.
SNAP_TOLERANCE = 60.0

GRAMMAR: dict[str, Any] = {
    "viewbox": "0 0 100 100",
    "min_elements": 3,
    "max_elements": 12,
    "shapes": ("path", "circle", "rect", "ellipse"),
    "inks": tuple(INKS.values()),
    "stroke": STROKE_INK,
    "max_stroke_width": 6.0,
    "max_bytes": 2048,
    "centre": (50.0, 50.0),
    "radius": 40.0,
    "path_commands": "MLCQZ",
}

#: Raw input larger than this is not even parsed.
MAX_RAW_BYTES = 16384
_EPSILON = 0.5  # rounding slack on the radius check

_PAINT = ("fill", "stroke", "stroke-width", "stroke-linejoin", "stroke-linecap", "fill-rule")
_GEOMETRY: dict[str, tuple[str, ...]] = {
    "path": ("d",),
    "circle": ("cx", "cy", "r"),
    "rect": ("x", "y", "width", "height", "rx", "ry"),
    "ellipse": ("cx", "cy", "rx", "ry"),
}
_REQUIRED: dict[str, tuple[str, ...]] = {
    "path": ("d",),
    "circle": ("r",),
    "rect": ("width", "height"),
    "ellipse": ("rx", "ry"),
}
_ROOT_ATTRS = {"viewBox", "width", "height", "version"}
_ENUMS = {
    "stroke-linejoin": {"round", "miter", "bevel"},
    "stroke-linecap": {"round", "butt", "square"},
    "fill-rule": {"nonzero", "evenodd"},
}
_NAMED = {"black": "#000000", "white": "#FFFFFF", "red": "#FF0000", "blue": "#0000FF", "yellow": "#FFFF00",
          "green": "#008000", "orange": "#FFA500", "brown": "#A52A2A", "gold": "#FFD700"}
_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_PATH_TOKEN = re.compile(r"[A-Za-z]|[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_ARITY = {"M": 2, "L": 2, "C": 6, "Q": 4, "Z": 0}


@dataclass(frozen=True)
class PictogramResult:
    ok: bool
    svg_normalised: str | None
    errors: list[str] = field(default_factory=list)
    #: ``"#000000→#14110D"`` per colour the tolerance pass moved.
    snapped_colours: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _fmt(value: float) -> str:
    text = f"{round(value, 2):.2f}".rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    value = hex_colour.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def nearest_ink(hex_colour: str) -> tuple[str, float]:
    """The closest of the seven inks and its RGB distance."""

    rgb = _rgb(hex_colour)
    best = min(INKS.values(), key=lambda ink: math.dist(rgb, _rgb(ink)))
    return best, math.dist(rgb, _rgb(best))


class _Checker:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.snapped: list[str] = []

    def fail(self, code: str, detail: str = "") -> None:
        message = f"{code}: {detail}" if detail else code
        if message not in self.errors:
            self.errors.append(message)

    def colour(self, raw: str, attr: str) -> str | None:
        value = raw.strip()
        lowered = value.lower()
        if lowered == "none":
            return "none"
        hex_value = _NAMED.get(lowered, value)
        if not _HEX.match(hex_value):
            self.fail("bad_colour", f"{attr}={value}")
            return None
        canonical = "#" + "".join(f"{c:02X}" for c in _rgb(hex_value))
        if canonical in INKS.values():
            return canonical
        ink, distance = nearest_ink(canonical)
        if distance <= SNAP_TOLERANCE:
            self.snapped.append(f"{canonical}→{ink}")
            return ink
        self.fail("off_palette", f"{attr}={value}")
        return None

    def number(self, raw: str | None, attr: str) -> float | None:
        if raw is None:
            return None
        value = raw.strip()
        if value.endswith("px"):
            value = value[:-2]
        if not _NUMBER.match(value):
            self.fail("bad_number", f"{attr}={raw}")
            return None
        return float(value)


def _local(tag: str, checker: _Checker) -> str | None:
    if tag.startswith("{"):
        ns, _, name = tag[1:].partition("}")
        if ns != SVG_NS:
            checker.fail("forbidden_namespace", ns)
            return None
        return name
    return tag


def _parse_path(d: str, checker: _Checker) -> tuple[list[tuple[str, list[float]]], list[tuple[float, float]]] | None:
    stripped = d.replace(",", " ")
    tokens = _PATH_TOKEN.findall(stripped)
    if "".join(tokens).replace(" ", "") != re.sub(r"\s+", "", stripped):
        checker.fail("path_syntax", "unreadable characters in d")
        return None
    commands: list[tuple[str, list[float]]] = []
    points: list[tuple[float, float]] = []
    index = 0
    current: str | None = None
    closed = True
    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            if token not in _ARITY:
                checker.fail("path_command", token)
                return None
            current = token
            index += 1
            if current == "Z":
                commands.append(("Z", []))
                closed = True
                continue
            if current == "M":
                if not closed:
                    checker.fail("open_path", "a subpath ends without Z")
                    return None
                closed = False
        elif current is None:
            checker.fail("path_syntax", "d must start with M")
            return None
        elif current == "Z":
            checker.fail("path_syntax", "numbers after Z")
            return None
        if not commands and current != "M":
            checker.fail("path_syntax", "d must start with M")
            return None
        arity = _ARITY[current]
        args = tokens[index:index + arity]
        if len(args) < arity or any(arg.isalpha() for arg in args):
            checker.fail("path_syntax", f"{current} needs {arity} numbers")
            return None
        values = [float(arg) for arg in args]
        commands.append((current, values))
        points.extend(zip(values[0::2], values[1::2], strict=True))
        index += arity
        if current == "M":
            current = "L"  # implicit lineto after a moveto pair
    if not commands or commands[0][0] != "M":
        checker.fail("path_syntax", "d must start with M")
        return None
    if not closed:
        checker.fail("open_path", "a subpath ends without Z")
        return None
    return commands, points


def _path_d(commands: list[tuple[str, list[float]]]) -> str:
    return "".join(command + " ".join(_fmt(v) for v in values) for command, values in commands)


def _inside(points: list[tuple[float, float]], extra: float = 0.0) -> bool:
    cx, cy = GRAMMAR["centre"]
    limit = GRAMMAR["radius"] + _EPSILON
    return all(math.dist((x, y), (cx, cy)) + extra <= limit for x, y in points)


def _viewbox(raw: str | None) -> str:
    return " ".join(re.split(r"[\s,]+", (raw or "").strip()))


def validate_pictogram(svg: str) -> PictogramResult:
    """Check ``svg`` against :data:`GRAMMAR`; on success return it rebuilt from the whitelist."""

    checker = _Checker()
    text = (svg or "").strip()
    if not text:
        return PictogramResult(False, None, ["empty"])
    if len(text.encode("utf-8")) > MAX_RAW_BYTES:
        return PictogramResult(False, None, [f"too_large: {len(text.encode('utf-8'))} bytes raw"])
    if "xlink" in text.lower():
        checker.fail("forbidden_namespace", "xlink")
    try:
        root = fromstring(text)
    except DefusedXmlException as exc:
        return PictogramResult(False, None, [f"forbidden_xml: {type(exc).__name__}"])
    except (ParseError, ValueError) as exc:
        return PictogramResult(False, None, [f"parse_error: {exc}"])

    if _local(root.tag, checker) != "svg":
        checker.fail("not_svg", str(root.tag))
        return PictogramResult(False, None, checker.errors)
    for attr in root.attrib:
        name = _local(attr, checker)
        if name is None:
            continue
        if name.lower().startswith("on") or name not in _ROOT_ATTRS:
            checker.fail("forbidden_attribute", f"svg {name}")
    if _viewbox(root.attrib.get("viewBox")) != GRAMMAR["viewbox"]:
        checker.fail("bad_viewbox", root.attrib.get("viewBox") or "missing")
    if (root.text or "").strip():
        checker.fail("stray_text", (root.text or "").strip()[:24])

    shapes: list[str] = []
    for child in list(root):
        if (child.tail or "").strip():
            checker.fail("stray_text", (child.tail or "").strip()[:24])
        rendered = _shape(child, checker)
        if rendered is not None:
            shapes.append(rendered)

    count = len(list(root))
    if count < GRAMMAR["min_elements"]:
        checker.fail("too_few_elements", f"{count} < {GRAMMAR['min_elements']}")
    if count > GRAMMAR["max_elements"]:
        checker.fail("too_many_elements", f"{count} > {GRAMMAR['max_elements']}")

    if checker.errors:
        return PictogramResult(False, None, checker.errors, checker.snapped)
    normalised = f'<svg xmlns="{SVG_NS}" viewBox="{GRAMMAR["viewbox"]}">' + "".join(shapes) + "</svg>"
    size = len(normalised.encode("utf-8"))
    if size > GRAMMAR["max_bytes"]:
        return PictogramResult(False, None, [f"too_large: {size} bytes > {GRAMMAR['max_bytes']}"], checker.snapped)
    if checker.snapped:
        logger.info("revue pictogram: snapped off-palette colours {}", ", ".join(checker.snapped))
    return PictogramResult(True, normalised, [], checker.snapped)


def _shape(element: Element, checker: _Checker) -> str | None:
    tag = _local(element.tag, checker)
    if tag is None:
        return None
    if tag not in GRAMMAR["shapes"]:
        checker.fail("forbidden_element", tag)
        return None
    if len(list(element)):
        checker.fail("nested_element", f"inside {tag}")
        return None
    if (element.text or "").strip():
        checker.fail("stray_text", (element.text or "").strip()[:24])
    allowed = set(_GEOMETRY[tag]) | set(_PAINT)
    attrs: dict[str, str] = {}
    for attr, value in element.attrib.items():
        name = _local(attr, checker)
        if name is None:
            continue
        if name not in allowed:
            checker.fail("forbidden_attribute", f"{tag} {name}")
            continue
        attrs[name] = value
    for name in _REQUIRED[tag]:
        if name not in attrs:
            checker.fail("missing_attribute", f"{tag} {name}")
            return None

    out: list[tuple[str, str]] = []
    fill = attrs.get("fill")
    if fill is None:
        checker.fail("missing_fill", tag)
        fill_value = None
    else:
        fill_value = checker.colour(fill, "fill")
    stroke_width = 0.0
    stroke_value: str | None = None
    if "stroke" in attrs:
        stroke_value = checker.colour(attrs["stroke"], "stroke")
        if stroke_value not in {None, "none", STROKE_INK}:
            checker.fail("stroke_not_ink", attrs["stroke"])
    if "stroke-width" in attrs:
        width = checker.number(attrs["stroke-width"], "stroke-width")
        if width is not None:
            if not 0 <= width <= GRAMMAR["max_stroke_width"]:
                checker.fail("stroke_width", _fmt(width))
            stroke_width = width
    if stroke_value in {None, "none"}:
        stroke_width = 0.0
    if fill_value == "none" and stroke_width <= 0:
        checker.fail("invisible_shape", tag)

    if tag == "path":
        parsed = _parse_path(attrs["d"], checker)
        if parsed is None:
            return None
        commands, points = parsed
        if not _inside(points, stroke_width / 2):
            checker.fail("out_of_circle", "path")
        out.append(("d", _path_d(commands)))
    else:
        numbers: dict[str, float] = {}
        for name in _GEOMETRY[tag]:
            if name in attrs:
                value = checker.number(attrs[name], name)
                if value is None:
                    return None
                if name in {"r", "rx", "ry", "width", "height"} and value < 0:
                    checker.fail("bad_number", f"{name}={attrs[name]}")
                    return None
                numbers[name] = value
        half = stroke_width / 2
        if tag == "circle":
            cx, cy, r = numbers.get("cx", 0.0), numbers.get("cy", 0.0), numbers["r"]
            if not _inside([(cx, cy)], r + half):
                checker.fail("out_of_circle", "circle")
        elif tag == "ellipse":
            cx, cy = numbers.get("cx", 0.0), numbers.get("cy", 0.0)
            rx, ry = numbers["rx"] + half, numbers["ry"] + half
            rim = [(cx + rx * math.cos(k * math.pi / 36), cy + ry * math.sin(k * math.pi / 36)) for k in range(72)]
            if not _inside(rim):
                checker.fail("out_of_circle", "ellipse")
        else:
            x, y, w, h = numbers.get("x", 0.0), numbers.get("y", 0.0), numbers["width"], numbers["height"]
            if not _inside([(x, y), (x + w, y), (x, y + h), (x + w, y + h)], half):
                checker.fail("out_of_circle", "rect")
        out.extend((name, _fmt(value)) for name, value in numbers.items())

    if fill_value:
        out.append(("fill", fill_value))
    if stroke_value and stroke_value != "none" and stroke_width > 0:
        out.append(("stroke", stroke_value))
        out.append(("stroke-width", _fmt(stroke_width)))
        for name in ("stroke-linejoin", "stroke-linecap"):
            if name in attrs:
                if attrs[name] not in _ENUMS[name]:
                    checker.fail("bad_value", f"{name}={attrs[name]}")
                else:
                    out.append((name, attrs[name]))
    if "fill-rule" in attrs:
        if attrs["fill-rule"] not in _ENUMS["fill-rule"]:
            checker.fail("bad_value", f"fill-rule={attrs['fill-rule']}")
        else:
            out.append(("fill-rule", attrs["fill-rule"]))
    return f"<{tag} " + " ".join(f'{name}="{value}"' for name, value in out) + "/>"


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class PictogramProviderError(RuntimeError):
    """The provider could not answer at all (network, empty content)."""


class PictogramProvider(Protocol):
    name: str

    def draw(self, *, object_fr: str, topic: str, errors: list[str] | None = None) -> str:
        """An SVG for ``object_fr``; ``errors`` names what was wrong with the previous try."""
        ...


INK_LINES = "\n".join(f"  {hex_value} ({name})" for name, hex_value in INKS.items())

PICTOGRAM_SYSTEM = (
    "You draw one small pictogram as SVG for a French newspaper's stamp, in a Bauhaus screen-print style: "
    "flat colour shapes, round construction, no outlines, no shading, no text. You answer with the SVG "
    "markup only, nothing before or after it."
)

PICTOGRAM_RULES = f"""Draw this one object: «{{object_fr}}» (the story's topic: {{topic}}).

Rules (a validator rejects anything else):
- Root exactly: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">.
- 3 to 12 shapes, each a direct child of <svg>: <path>, <circle>, <rect> or <ellipse>. No <g>, no transform.
- Every shape has a fill attribute, using only these seven colours:
{INK_LINES}
- No stroke, except stroke="#14110D" with stroke-width between 1 and 6, used sparingly.
- Paths use only absolute commands M, L, C, Q and Z (upper case); every subpath ends with Z. No arcs (A), no H/V/S/T, no relative commands.
- Everything (all coordinates, control points, circle and ellipse edges, rect corners) stays inside the circle of radius 40 centred on (50,50); keep a margin, aim for radius 36.
- No text, no <style>, no style attribute, no id, no class, no gradients, no filters, no images, no xlink, no comments.
- Keep it under 1500 characters; round coordinates to whole numbers.
- One clear, recognisable silhouette built from a few simple geometric forms; generous, calm, centred."""


def _extract_svg(content: str) -> str:
    match = re.search(r"<svg\b.*?</svg>", content or "", flags=re.S | re.I)
    return match.group(0) if match else (content or "").strip()


@dataclass
class OpenAIPictogramProvider:
    """The app's LLM service (``LLMService``), one small text call per drawing."""

    name: str = "openai-pictogram"
    max_tokens: int = 6000  # reasoning models starve on low budgets ([[gpt5-empty-content-token-starvation]])
    model: str | None = None
    spent_usd: float = 0.0
    _service: Any = None

    def _llm(self) -> Any:
        if self._service is None:
            from app.services.llm_service import LLMService

            self._service = LLMService()
        return self._service

    def draw(self, *, object_fr: str, topic: str, errors: list[str] | None = None) -> str:
        prompt = PICTOGRAM_RULES.format(object_fr=object_fr, topic=topic)
        if errors:
            prompt += (
                "\n\nYour previous drawing was rejected by the validator for: "
                + "; ".join(errors)
                + ". Draw it again and fix exactly these problems."
            )
        try:
            result = self._llm().generate_chat_completion(
                [{"role": "user", "content": prompt}],
                system_prompt=PICTOGRAM_SYSTEM,
                temperature=0.6,
                max_tokens=self.max_tokens,
                model=self.model,
                reasoning_effort="low",
            )
        except Exception as exc:  # noqa: BLE001 - pictogram_for falls back
            raise PictogramProviderError(str(exc)) from exc
        self.spent_usd += float(getattr(result, "cost", 0.0) or 0.0)
        content = _extract_svg(getattr(result, "content", "") or "")
        if not content:
            raise PictogramProviderError("empty content")
        return content


_FAKE_COLOURS = ("#1D3A8A", "#D8321A", "#F3C318", "#2C6A5D", "#C2890F")


@dataclass
class FakePictogramProvider:
    """Deterministic, valid drawings from the object's hash (tests, the walk, no key)."""

    name: str = "fake-pictogram"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def draw(self, *, object_fr: str, topic: str, errors: list[str] | None = None) -> str:
        self.calls.append({"object_fr": object_fr, "topic": topic, "errors": list(errors or [])})
        digest = hashlib.sha256(object_fr.encode("utf-8")).digest()
        a, b, c = (_FAKE_COLOURS[digest[i] % len(_FAKE_COLOURS)] for i in range(3))
        r = 18 + digest[3] % 10
        w = 10 + digest[4] % 14
        h = 8 + digest[5] % 10
        lift = digest[6] % 8
        return (
            f'<svg xmlns="{SVG_NS}" viewBox="0 0 100 100">'
            f'<circle cx="50" cy="{46 - lift}" r="{r}" fill="{a}"/>'
            f'<rect x="{50 - w}" y="{62 - lift}" width="{2 * w}" height="{h}" rx="3" fill="{b}"/>'
            f'<path d="M50 {28 - lift}L{60} {44 - lift}L{40} {44 - lift}Z" fill="{c}"/>'
            f'<ellipse cx="50" cy="{76 - lift // 2}" rx="20" ry="4" fill="#14110D"/>'
            f'<circle cx="{44 + digest[7] % 12}" cy="{40 - lift}" r="3" fill="#F1ECE1"/>'
            "</svg>"
        )


def default_pictogram_provider() -> PictogramProvider:
    from app.config import settings

    if getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "ANTHROPIC_API_KEY", None):
        return OpenAIPictogramProvider()
    return FakePictogramProvider()


# ---------------------------------------------------------------------------
# Fallbacks and the cache
# ---------------------------------------------------------------------------

FALLBACK_TOPICS: tuple[str, ...] = ("food", "culture", "city", "sport", "nature", "work", "politics")


def fallback_svg(topic: str | None) -> str:
    """The authored pictogram for ``topic`` (``culture`` when the topic is unknown), normalised."""

    name = topic if topic in FALLBACK_TOPICS else "culture"
    raw = (PICTOGRAM_DIR / f"{name}.svg").read_text(encoding="utf-8")
    result = validate_pictogram(raw)
    if not result.ok or result.svg_normalised is None:  # pragma: no cover - a test holds the files valid
        raise RuntimeError(f"authored pictogram {name}.svg breaks the grammar: {result.errors}")
    return result.svg_normalised


def _store(db: Session, *, dossier_id: str, object_fr: str, svg: str, version: str) -> str:
    row = RevuePictogram(
        dossier_id=dossier_id, object_fr=object_fr[:200], svg=svg, prompt_version=version, validated_at=datetime.now(UTC)
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        # Another learner's close drew it first: theirs is the shared one.
        existing = db.get(RevuePictogram, dossier_id)
        if existing is not None:
            return existing.svg
    return svg


def pictogram_for(db: Session, dossier: Any, provider: PictogramProvider | None) -> str:
    """The dossier's pictogram: cached, else drawn (one regeneration), else the topic fallback.

    ``dossier`` is an ``EditorialDossier`` (``id``, ``topic``, ``vignette_object_fr``). A
    dossier without an object gets the topic fallback and is not cached, so a later build
    that names an object still gets drawn.
    """

    dossier_id = str(dossier.id)
    topic = str(getattr(dossier, "topic", "") or "")
    object_fr = re.sub(r"\s+", " ", str(getattr(dossier, "vignette_object_fr", None) or "")).strip()
    cached = db.get(RevuePictogram, dossier_id)
    if cached is not None:
        return cached.svg
    if not object_fr or provider is None:
        return fallback_svg(topic)

    errors: list[str] | None = None
    for attempt in (1, 2):
        try:
            raw = provider.draw(object_fr=object_fr, topic=topic, errors=errors)
        except Exception as exc:  # noqa: BLE001 - a provider failure counts as a failed try
            errors = [f"provider_error: {exc}"]
            logger.bind(dossier_id=dossier_id).warning("revue pictogram: provider failed on try {} ({})", attempt, exc)
            continue
        result = validate_pictogram(raw)
        if result.ok and result.svg_normalised:
            return _store(db, dossier_id=dossier_id, object_fr=object_fr, svg=result.svg_normalised,
                          version=PROMPT_VERSION)
        errors = result.errors
        logger.bind(dossier_id=dossier_id).info("revue pictogram: try {} rejected ({})", attempt, "; ".join(errors))
    logger.bind(dossier_id=dossier_id).warning("revue pictogram: falling back to the {} pictogram", topic or "culture")
    return _store(db, dossier_id=dossier_id, object_fr=object_fr, svg=fallback_svg(topic),
                  version=f"{FALLBACK_VERSION}:{topic or 'culture'}")
