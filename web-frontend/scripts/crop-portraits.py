"""Crop the cast's expression portraits out of their model sheets (WP-77).

Every `public/assets/serial/characters/<id>/model-sheet.webp` is a 1448x1086
sheet: three full-body turnarounds on top, three expression busts on the bottom
row. The busts are not in the same order on every sheet, so each character has
its own column map, checked by eye against the sheet:

    neutral  the face the cast intro and plain dialogue use
    happy    the learner got it right
    cross    the learner got it wrong (or the character is annoyed)

The `user` sheet is drawn from behind (the learner is never shown), so it has
no portraits.

Run from `web-frontend/`:

    ../venv/bin/python scripts/crop-portraits.py

Writes `portrait-neutral.webp`, `portrait-happy.webp`, `portrait-cross.webp`
(256x256, face centred) next to each model sheet. Idempotent.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "public" / "assets" / "serial" / "characters"
OUT_SIZE = 256
# Side of the square cut from the 1448x1086 sheet, before resizing.
CROP = 250

# Face centre (x, y) of each bottom-row bust on the sheet, left to right.
# y sits a little below the eyes so the crop keeps hair and a hint of collar.
FACES: dict[str, list[tuple[int, int]]] = {
    "romy_tremblay": [(330, 840), (710, 840), (1070, 835)],
    "marin_leveque": [(290, 875), (700, 870), (1090, 880)],
    "lila_bonnet": [(345, 820), (705, 815), (1060, 825)],
    "margaux_barman": [(355, 790), (715, 785), (1070, 790)],
    "augustin_de_roncourt": [(330, 790), (700, 795), (1100, 795)],
    "landlord_marchand": [(345, 805), (725, 805), (1070, 805)],
}

# mood -> bust column (0 = left). Checked against each sheet by eye.
MOODS: dict[str, dict[str, int]] = {
    # left: warm smile · middle: sly, narrowed eyes · right: calm, earnest
    "romy_tremblay": {"neutral": 2, "happy": 0, "cross": 1},
    # left: warm smile · middle: pensive, looking up · right: downcast
    "marin_leveque": {"neutral": 1, "happy": 0, "cross": 2},
    # left: sly · middle: delighted · right: arms crossed
    "lila_bonnet": {"neutral": 0, "happy": 1, "cross": 2},
    # left: wry, polishing a glass · middle: warm smile · right: wagging finger
    "margaux_barman": {"neutral": 0, "happy": 1, "cross": 2},
    # left: composed · middle: delighted · right: uneasy
    "augustin_de_roncourt": {"neutral": 0, "happy": 1, "cross": 2},
    # left: composed · middle: stern over the glasses · right: slight smile
    "landlord_marchand": {"neutral": 0, "happy": 2, "cross": 1},
}


def crop_face(sheet: Image.Image, centre: tuple[int, int]) -> Image.Image:
    x, y = centre
    half = CROP // 2
    left = max(0, min(sheet.width - CROP, x - half))
    top = max(0, min(sheet.height - CROP, y - half))
    box = (left, top, left + CROP, top + CROP)
    return sheet.crop(box).resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)


def main() -> None:
    for character, faces in FACES.items():
        sheet_path = ROOT / character / "model-sheet.webp"
        sheet = Image.open(sheet_path).convert("RGB")
        for mood, column in MOODS[character].items():
            out = ROOT / character / f"portrait-{mood}.webp"
            crop_face(sheet, faces[column]).save(out, "WEBP", quality=82, method=6)
            print(f"{out.relative_to(ROOT.parent.parent.parent.parent)}")


if __name__ == "__main__":
    main()
