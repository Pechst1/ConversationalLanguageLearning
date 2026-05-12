"""Create a small HTML review matrix for curated grammar motifs.

Usage:
    .venv/bin/python scripts/review_grammar_motifs.py --output /tmp/grammar_motifs.html
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.models.grammar import GrammarConcept
from app.db.session import SessionLocal
from app.services.atelier_assets import AtelierAssetService
from app.services.grammar_catalog import FRENCH_CORE_CATALOG_VERSION, FrenchCoreGrammarCatalog

COLOR_MAP = {
    "paper": "#efe8dc",
    "ink": "#11100d",
    "red": "#df2b18",
    "blue": "#21499a",
    "yellow": "#f1c400",
    "muted": "#8c877d",
}


def _value(value: Any) -> str:
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list) and len(value) == 2:
        return f"{value[0]},{value[1]}"
    return html.escape(str(value or ""))


def _color(value: Any) -> str:
    return COLOR_MAP.get(str(value), html.escape(str(value or "none")))


def _svg(motif: dict[str, Any]) -> str:
    canvas = motif.get("canvas") or {"width": 84, "height": 84}
    width = int(canvas.get("width") or 84)
    height = int(canvas.get("height") or 84)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(str(motif.get("accessibility_label") or "grammar motif"))}">'
    ]
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{COLOR_MAP["paper"]}" stroke="{COLOR_MAP["ink"]}" />')
    for primitive in motif.get("primitives") or []:
        if not isinstance(primitive, dict):
            continue
        kind = primitive.get("type")
        stroke = _color(primitive.get("stroke") or "ink")
        fill = _color(primitive.get("fill") or "none")
        if kind == "rect":
            parts.append(
                f'<rect x="{_value(primitive.get("x"))}" y="{_value(primitive.get("y"))}" width="{_value(primitive.get("w"))}" height="{_value(primitive.get("h"))}" fill="{fill}" stroke="{stroke}" stroke-width="2" />'
            )
        elif kind == "circle":
            parts.append(
                f'<circle cx="{_value(primitive.get("cx"))}" cy="{_value(primitive.get("cy"))}" r="{_value(primitive.get("r"))}" fill="{fill}" stroke="{stroke}" stroke-width="2" />'
            )
        elif kind == "line":
            parts.append(
                f'<line x1="{_value(primitive.get("x1"))}" y1="{_value(primitive.get("y1"))}" x2="{_value(primitive.get("x2"))}" y2="{_value(primitive.get("y2"))}" stroke="{stroke}" stroke-width="3" />'
            )
        elif kind == "arrow":
            start = primitive.get("from") or [0, 0]
            end = primitive.get("to") or [0, 0]
            parts.append(
                f'<line x1="{_value(start[0])}" y1="{_value(start[1])}" x2="{_value(end[0])}" y2="{_value(end[1])}" stroke="{stroke}" stroke-width="3" marker-end="url(#arrow)" />'
            )
        elif kind == "path":
            parts.append(f'<path d="{_value(primitive.get("d"))}" fill="none" stroke="{stroke}" stroke-width="3" />')
        if primitive.get("label") or primitive.get("text"):
            label = html.escape(str(primitive.get("label") or primitive.get("text")))
            x = primitive.get("x", primitive.get("cx", 42))
            y = primitive.get("y", primitive.get("cy", 42))
            parts.append(f'<text x="{_value(x)}" y="{_value(y)}" font-size="8" font-family="monospace">{label}</text>')
    parts.insert(
        1,
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#11100d" /></marker></defs>',
    )
    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render curated French grammar motifs for review")
    parser.add_argument("--output", default="/tmp/grammar_motif_review.html")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        FrenchCoreGrammarCatalog(db).ensure_catalog(archive_legacy=True)
        service = AtelierAssetService(db)
        concepts = (
            db.query(GrammarConcept)
            .filter(
                GrammarConcept.language == "fr",
                GrammarConcept.active.is_(True),
                GrammarConcept.catalog_version == FRENCH_CORE_CATALOG_VERSION,
            )
            .order_by(GrammarConcept.level, GrammarConcept.difficulty_order, GrammarConcept.id)
            .all()
        )
        cards: list[str] = []
        signatures: dict[str, list[str]] = {}
        for concept in concepts:
            blueprint = service.ensure_concept_blueprint(concept)
            motif = blueprint.payload.get("visual_motif") or {}
            signature = motif.get("signature") or service.motif_signature(motif) or "missing"
            signatures.setdefault(signature, []).append(concept.external_id or str(concept.id))
            cards.append(
                f'<article><div class="motif">{_svg(motif)}</div><strong>{html.escape(str(blueprint.payload.get("display_title") or concept.name))}</strong><small>{html.escape(str(concept.external_id))} · {html.escape(str(concept.level))}</small><code>{html.escape(signature)}</code></article>'
            )
        collisions = {sig: ids for sig, ids in signatures.items() if len(ids) > 1}
        collision_html = ""
        if collisions:
            collision_html = "<section><h2>Signature collisions</h2>" + "".join(
                f"<p><code>{html.escape(sig)}</code> {html.escape(', '.join(ids))}</p>" for sig, ids in collisions.items()
            ) + "</section>"
        document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8" />
<title>Grammar Motif Review</title>
<style>
body {{ margin: 32px; background: #efe8dc; color: #11100d; font-family: Inter, Arial, sans-serif; }}
h1 {{ font-size: 48px; margin: 0 0 24px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }}
article {{ border: 2px solid #11100d; padding: 12px; min-height: 210px; background: #f7f1e7; }}
.motif {{ width: 112px; height: 112px; margin-bottom: 12px; }}
svg {{ width: 100%; height: 100%; }}
strong, small, code {{ display: block; }}
small {{ margin-top: 8px; color: #5f5b52; }}
code {{ margin-top: 8px; font-size: 11px; }}
</style>
<body>
<h1>Grammar Motif Review</h1>
{collision_html}
<main class="grid">{''.join(cards)}</main>
</body>
</html>"""
        output = Path(args.output)
        output.write_text(document, encoding="utf-8")
        print(f"Wrote {output}")
        print(f"Concepts: {len(concepts)}")
        print(f"Signature collisions: {len(collisions)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
