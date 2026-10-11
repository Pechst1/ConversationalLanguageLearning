"""WP-119 §10c / WP-120 §4.2 — redraw weak Revue pictograms and lay them out for the owner.

    .venv/bin/python scripts/art/revue_pictograms.py                 # the four weak evergreens (paid, ~1 cent)
    .venv/bin/python scripts/art/revue_pictograms.py --sheet-only    # rebuild the contact sheet from the files
    .venv/bin/python scripts/art/revue_pictograms.py --fake          # dry run with the fake provider (free)

Each pictogram goes through the app's own path, ``pictogram_for(..., refresh=True)``, against a
throwaway in-memory ``revue_pictograms`` table seeded with the current drawing, so the redraw
exercises the same validator, the same single regeneration and the same overwrite the app uses.
Nothing touches the real database.

Outputs, in ``docs/design-reference/revue/vignettes/``:
- ``<dossier>.v2.svg`` (the normalised new drawing) and ``<dossier>.v2.tryN.raw.svg`` (what the
  model answered on each try);
- ``generation-log-2.json`` (objects old and new, outcome per try, spend);
- ``contact-sheet-2.webp``: the old drawing beside the new one, one row per story, for the owner
  to pick. The evergreen JSON is not changed here; the owner's pick decides.

Needs OPENAI_API_KEY in `.env` (read with python-dotenv, never printed). The sheet is rendered by
the frontend's Playwright Chromium (``web-frontend/node_modules/playwright``) and saved as WebP.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from html import escape
from pathlib import Path
from types import SimpleNamespace

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/design-reference/revue/vignettes"
EVERGREEN = REPO / "app/services/revue/evergreen"
FRONTEND = REPO / "web-frontend"

#: dossier id → the tighter object description: one flat object, front view, no scene.
REDRAW: dict[str, str] = {
    "evergreen-bac": "un stylo-plume posé sur une feuille",
    "evergreen-fete-de-la-musique": "une guitare acoustique vue de face",
    "evergreen-tour-de-france": "un maillot à manches courtes, jaune, vu de face",
    "evergreen-quatorze-juillet": "trois fusées de feu d'artifice en éventail",
}

sys.path.insert(0, str(REPO))


def _key_from_dotenv() -> None:
    """The app's settings read `.env` themselves; this only fills a missing environment."""

    env = dotenv_values(REPO / ".env")
    for name in ("OPENAI_API_KEY", "OPENAI_API_BASE"):
        if env.get(name) and not os.environ.get(name):
            os.environ[name] = str(env[name])


class Recording:
    """Wraps a provider and keeps each raw answer (or error) per try."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.name = getattr(inner, "name", "provider")
        self.tries: list[dict] = []

    def draw(self, *, object_fr: str, topic: str, errors: list[str] | None = None) -> str:
        try:
            raw = self.inner.draw(object_fr=object_fr, topic=topic, errors=errors)
        except Exception as exc:
            self.tries.append({"raw": None, "provider_error": str(exc)[:200], "told": list(errors or [])})
            raise
        self.tries.append({"raw": raw, "told": list(errors or [])})
        return raw


def redraw(*, fake: bool) -> dict:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models.revue_vignette import RevuePictogram
    from app.services.revue import pictogram as pg

    engine = create_engine("sqlite://")
    RevuePictogram.__table__.create(bind=engine)
    db = sessionmaker(bind=engine)()
    inner = pg.FakePictogramProvider() if fake else pg.OpenAIPictogramProvider()
    log: dict = {"prompt_version": pg.PROMPT_VERSION, "provider": inner.name, "results": []}
    for dossier_id, new_object in REDRAW.items():
        data = json.loads((EVERGREEN / f"{dossier_id}.json").read_text(encoding="utf-8"))
        old_svg = (OUT / f"{dossier_id}.svg").read_text(encoding="utf-8")
        db.add(RevuePictogram(dossier_id=dossier_id, object_fr=data["vignette_object_fr"], svg=old_svg,
                              prompt_version=pg.PROMPT_VERSION))
        db.flush()
        provider = Recording(inner)
        dossier = SimpleNamespace(id=dossier_id, topic=data["topic"], vignette_object_fr=new_object)
        out = pg.pictogram_for(db, dossier, provider, refresh=True)
        row = db.get(RevuePictogram, dossier_id)
        redrawn = out != old_svg
        tries = []
        for number, attempt in enumerate(provider.tries, start=1):
            entry = {"told": attempt["told"]}
            if attempt["raw"] is None:
                entry.update(ok=False, errors=[f"provider_error: {attempt['provider_error']}"], snapped=[])
            else:
                if not fake:
                    (OUT / f"{dossier_id}.v2.try{number}.raw.svg").write_text(attempt["raw"], encoding="utf-8")
                result = pg.validate_pictogram(attempt["raw"])
                entry.update(ok=result.ok, errors=result.errors, snapped=list(result.snapped_colours))
            tries.append(entry)
        if redrawn and not fake:
            (OUT / f"{dossier_id}.v2.svg").write_text(out, encoding="utf-8")
        log["results"].append({
            "dossier_id": dossier_id,
            "topic": data["topic"],
            "object_fr_old": data["vignette_object_fr"],
            "object_fr_new": new_object,
            "outcome": ("first" if len(tries) == 1 else "regenerated") if redrawn else "kept_old",
            "row_object_fr": row.object_fr,
            "bytes": len(out.encode("utf-8")) if redrawn else None,
            "tries": tries,
        })
    log["spent_usd"] = round(float(getattr(inner, "spent_usd", 0.0) or 0.0), 4)
    if not fake:
        (OUT / "generation-log-2.json").write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")
    return log


PAPER, INK, CREAM = "#F1ECE1", "#14110D", "#E6DFD0"


def _face(svg_text: str | None, caption: str) -> str:
    inner = svg_text or '<svg viewBox="0 0 100 100"></svg>'
    inner = inner.replace("<svg ", '<svg width="132" height="132" x="14" y="14" ', 1)
    return (
        '<figure><svg viewBox="0 0 160 160" width="200" height="200" xmlns="http://www.w3.org/2000/svg">'
        f'<circle cx="80" cy="80" r="78" fill="{INK}"/><circle cx="80" cy="80" r="70" fill="{PAPER}"/>'
        f"{inner}</svg><figcaption>{escape(caption)}</figcaption></figure>"
    )


def sheet() -> Path:
    log_path = OUT / "generation-log-2.json"
    results = {row["dossier_id"]: row for row in json.loads(log_path.read_text())["results"]} if log_path.exists() else {}
    rows = []
    for dossier_id, new_object in REDRAW.items():
        data = json.loads((EVERGREEN / f"{dossier_id}.json").read_text(encoding="utf-8"))
        old = (OUT / f"{dossier_id}.svg").read_text(encoding="utf-8")
        new_path = OUT / f"{dossier_id}.v2.svg"
        new = new_path.read_text(encoding="utf-8") if new_path.exists() else None
        outcome = results.get(dossier_id, {}).get("outcome", "not drawn")
        rows.append(
            f'<section><h2>{escape(dossier_id.removeprefix("evergreen-"))}</h2><div class="pair">'
            f'{_face(old, "avant · " + data["vignette_object_fr"])}'
            f'{_face(new, "après · " + new_object + ("" if new else " (pas de nouveau dessin)"))}'
            f'</div><p class="note">{escape(outcome)}</p></section>'
        )
    html = (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        f"body{{margin:0;background:{CREAM};color:{INK};font-family:'Instrument Sans',Helvetica,Arial,sans-serif}}"
        ".wrap{padding:32px 40px;width:920px}"
        "h1{font-family:'EB Garamond',Garamond,Georgia,serif;font-style:italic;font-weight:500;font-size:34px;margin:0 0 4px}"
        ".lede{margin:0 0 24px;font-size:14px}"
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}"
        f"section{{background:{PAPER};border-radius:20px;padding:16px 18px}}"
        "h2{font-size:15px;margin:0 0 8px;font-weight:600}"
        ".pair{display:flex;gap:12px}figure{margin:0;width:200px}"
        "figcaption{font-size:12px;line-height:1.35;margin-top:6px}"
        ".note{font-size:11px;opacity:.6;margin:6px 0 0}"
        '</style></head><body><div class="wrap">'
        "<h1>Vignettes · planche 2</h1>"
        '<p class="lede">WP-119 §10c — les quatre pictogrammes faibles, avant et après (un objet, vu de face, sans décor). '
        "Le propriétaire choisit ; le JSON evergreen ne change qu'après ce choix.</p>"
        f'<div class="grid">{"".join(rows)}</div></div></body></html>'
    )
    html_path = OUT / "contact-sheet-2.tmp.html"
    png_path = OUT / "contact-sheet-2.tmp.png"
    html_path.write_text(html, encoding="utf-8")
    script = (
        "const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
        "const p=await b.newPage({viewport:{width:1000,height:800},deviceScaleFactor:2});"
        f"await p.goto('file://{html_path}');"
        f"await p.locator('.wrap').screenshot({{path:'{png_path}'}});await b.close();}})()"
        ".catch(e=>{console.error(e);process.exit(1)});"
    )
    subprocess.run(["node", "-e", script], cwd=FRONTEND, check=True)  # noqa: S603, S607 - our own script, local node
    from PIL import Image

    target = OUT / "contact-sheet-2.webp"
    with Image.open(png_path) as image:
        image.convert("RGB").save(target, "WEBP", quality=88, method=6)
    png_path.unlink()
    html_path.unlink()
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sheet-only", action="store_true")
    parser.add_argument("--fake", action="store_true", help="the fake provider; writes nothing but prints the log")
    args = parser.parse_args()
    if not args.sheet_only:
        _key_from_dotenv()
        log = redraw(fake=args.fake)
        for row in log["results"]:
            print(f"{row['dossier_id']}: {row['outcome']} ({len(row['tries'])} tr{'y' if len(row['tries']) == 1 else 'ies'})")
        print(f"spent ${log['spent_usd']:.4f}")
        if args.fake:
            return
    print(sheet().relative_to(REPO))


if __name__ == "__main__":
    main()
