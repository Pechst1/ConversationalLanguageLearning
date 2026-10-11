#!/usr/bin/env python3
"""WP-72 — render the app icon, the launch-screen mark and the web icons.

Source: ``web-frontend/ios/branding/atelier-mark.svg`` — the masthead's four
shapes (ink square, blue circle, yellow square, red triangle). This script reads
that SVG (the small subset it uses: ``rect`` with ``rx``, ``circle``, and ``path``
made of absolute M/L/H/V/Z) and draws it with Pillow, supersampled 4x and
downscaled, so no SVG renderer is needed.

Writes:

* ``ios/App/App/Assets.xcassets/AppIcon.appiconset`` — iPhone sizes + the
  1024 px App Store icon, opaque (no alpha channel: App Store Connect rejects
  an icon with one), paper ground, mark centred; ``Contents.json`` rewritten.
* ``ios/App/App/Assets.xcassets/Splash.imageset`` — the mark alone on
  transparency at 1x/2x/3x of 104 pt; ``LaunchScreen.storyboard`` centres it on
  the paper colour.
* ``public/apple-touch-icon.png``, ``public/favicon.ico`` and
  ``public/icons/icon-{192,512}.png`` for the web manifest.

Run from anywhere:  venv/bin/python web-frontend/scripts/generate-app-icons.py
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw

WEB_ROOT = Path(__file__).resolve().parent.parent
SOURCE_SVG = WEB_ROOT / "ios" / "branding" / "atelier-mark.svg"
ASSETS = WEB_ROOT / "ios" / "App" / "App" / "Assets.xcassets"
APPICON_DIR = ASSETS / "AppIcon.appiconset"
SPLASH_DIR = ASSETS / "Splash.imageset"
PUBLIC = WEB_ROOT / "public"

PAPER = "#f1ece1"
#: Share of the icon's width the mark spans. Apple's grid keeps the subject
#: well inside the corner mask; 0.56 leaves ~22% paper on each side.
ICON_MARK_SHARE = 0.56
#: The launch image is 104 pt square with the mark at 90% of it, so the
#: antialiased edges are never clipped by the image bounds.
SPLASH_POINTS = 104
SPLASH_MARK_SHARE = 0.9
SUPERSAMPLE = 4

#: (points, scale, idiom) — the iPhone set plus the marketing icon.
ICON_SPECS: list[tuple[float, int, str]] = [
    (20, 2, "iphone"),
    (20, 3, "iphone"),
    (29, 2, "iphone"),
    (29, 3, "iphone"),
    (40, 2, "iphone"),
    (40, 3, "iphone"),
    (60, 2, "iphone"),
    (60, 3, "iphone"),
    (1024, 1, "ios-marketing"),
]

SVG_NS = "{http://www.w3.org/2000/svg}"


def _hex(color: str) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), 255)


def load_shapes(svg_path: Path = SOURCE_SVG) -> tuple[float, list[dict]]:
    """Return (viewBox size, shapes) from the source SVG."""

    root = ET.parse(svg_path).getroot()  # noqa: S314 - the repository's own mark, not untrusted input
    view = [float(v) for v in root.attrib["viewBox"].split()]
    if view[0] != 0 or view[1] != 0 or view[2] != view[3]:
        raise ValueError("The mark's viewBox must be square and start at 0 0.")
    shapes: list[dict] = []
    for node in root:
        tag = node.tag.replace(SVG_NS, "")
        a = node.attrib
        if tag == "rect":
            shapes.append({
                "kind": "rect",
                "box": (float(a["x"]), float(a["y"]), float(a["x"]) + float(a["width"]), float(a["y"]) + float(a["height"])),
                "rx": float(a.get("rx", 0)),
                "fill": a["fill"],
            })
        elif tag == "circle":
            cx, cy, r = float(a["cx"]), float(a["cy"]), float(a["r"])
            shapes.append({"kind": "circle", "box": (cx - r, cy - r, cx + r, cy + r), "fill": a["fill"]})
        elif tag == "path":
            shapes.append({"kind": "polygon", "points": _path_points(a["d"]), "fill": a["fill"]})
    if len(shapes) != 4:
        raise ValueError(f"Expected the four-shape mark, found {len(shapes)} shapes.")
    return view[2], shapes


def _path_points(d: str) -> list[tuple[float, float]]:
    tokens = re.findall(r"[MLHVZmlhvz]|-?\d*\.?\d+", d)
    points: list[tuple[float, float]] = []
    x = y = 0.0
    command = ""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            if token.islower():
                raise ValueError("Only absolute path commands are supported.")
            command = token
            i += 1
            if command == "Z":
                continue
            token = tokens[i]
        if command in ("M", "L"):
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
        elif command == "H":
            x = float(tokens[i])
            i += 1
        elif command == "V":
            y = float(tokens[i])
            i += 1
        else:
            raise ValueError(f"Unsupported path command {command!r}.")
        points.append((x, y))
    return points


def draw_mark(size_px: int, *, mark_px: float, background: str | None) -> Image.Image:
    """Draw the mark `mark_px` wide, centred on a `size_px` square."""

    view, shapes = load_shapes()
    big = size_px * SUPERSAMPLE
    ground = _hex(background) if background else (0, 0, 0, 0)
    image = Image.new("RGBA", (big, big), ground)
    draw = ImageDraw.Draw(image)
    scale = mark_px * SUPERSAMPLE / view
    offset = (big - view * scale) / 2

    def tx(px: float, py: float) -> tuple[float, float]:
        return (offset + px * scale, offset + py * scale)

    for shape in shapes:
        fill = _hex(shape["fill"])
        if shape["kind"] == "rect":
            x0, y0, x1, y1 = shape["box"]
            draw.rounded_rectangle([tx(x0, y0), tx(x1, y1)], radius=shape["rx"] * scale, fill=fill)
        elif shape["kind"] == "circle":
            x0, y0, x1, y1 = shape["box"]
            draw.ellipse([tx(x0, y0), tx(x1, y1)], fill=fill)
        else:
            draw.polygon([tx(px, py) for px, py in shape["points"]], fill=fill)
    return image.resize((size_px, size_px), Image.LANCZOS)


def icon(size_px: int) -> Image.Image:
    # Opaque RGB: an App Store icon must not carry an alpha channel.
    return draw_mark(size_px, mark_px=size_px * ICON_MARK_SHARE, background=PAPER).convert("RGB")


def _points_label(points: float) -> str:
    return str(int(points)) if float(points).is_integer() else str(points)


def write_app_icons() -> None:
    for stale in APPICON_DIR.glob("*.png"):
        stale.unlink()
    images = []
    for points, scale, idiom in ICON_SPECS:
        pixels = int(round(points * scale))
        name = f"AppIcon-{_points_label(points)}@{scale}x.png" if idiom != "ios-marketing" else "AppIcon-1024.png"
        icon(pixels).save(APPICON_DIR / name, optimize=True)
        images.append({
            "filename": name,
            "idiom": idiom,
            "scale": f"{scale}x",
            "size": f"{_points_label(points)}x{_points_label(points)}",
        })
    (APPICON_DIR / "Contents.json").write_text(
        json.dumps({"images": images, "info": {"author": "xcode", "version": 1}}, indent=2) + "\n",
        encoding="utf-8",
    )


def write_splash() -> None:
    for stale in SPLASH_DIR.glob("*.png"):
        stale.unlink()
    images = []
    for scale in (1, 2, 3):
        pixels = SPLASH_POINTS * scale
        name = f"splash-mark@{scale}x.png"
        draw_mark(pixels, mark_px=pixels * SPLASH_MARK_SHARE, background=None).save(SPLASH_DIR / name, optimize=True)
        images.append({"idiom": "universal", "filename": name, "scale": f"{scale}x"})
    (SPLASH_DIR / "Contents.json").write_text(
        json.dumps({"images": images, "info": {"author": "xcode", "version": 1}}, indent=2) + "\n",
        encoding="utf-8",
    )


def write_web_icons() -> None:
    (PUBLIC / "icons").mkdir(parents=True, exist_ok=True)
    icon(180).save(PUBLIC / "apple-touch-icon.png", optimize=True)
    for size in (192, 512):
        icon(size).save(PUBLIC / "icons" / f"icon-{size}.png", optimize=True)
    # pages/_document.tsx links /favicon.ico; it had never existed.
    icon(256).save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])


def main() -> None:
    write_app_icons()
    write_splash()
    write_web_icons()
    print(f"Icons written to {APPICON_DIR.relative_to(WEB_ROOT)}, {SPLASH_DIR.relative_to(WEB_ROOT)} and public/.")


if __name__ == "__main__":
    main()
