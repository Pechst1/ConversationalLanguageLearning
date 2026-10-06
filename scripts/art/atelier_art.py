"""WP-D8 — the art pipeline: location plates and the cast, in the owner-approved screen-print style.

Everything drawn in the app comes out of this one tool, so the style lives in version control:

    venv/bin/python scripts/art/atelier_art.py plate le_mistral-counter      # redraw one plate
    venv/bin/python scripts/art/atelier_art.py plate all                     # every plate
    venv/bin/python scripts/art/atelier_art.py reference romy_tremblay       # a new approved portrait
    venv/bin/python scripts/art/atelier_art.py moods romy_tremblay           # happy, cross, moved from it
    venv/bin/python scripts/art/atelier_art.py crop romy_tremblay            # the four 256px app portraits
    venv/bin/python scripts/art/atelier_art.py lock in.png out.webp          # palette-lock any image

Rules the owner set (2026-09-22/23), and why they are here rather than in someone's head:
- One style for people and places: flat screen print in the brand inks, no outlines.
- Faces are written out (bone structure, eyes, nose, age, skin); "unique features" alone
  gives every character the same default face.
- Never send the old model sheets as references: they pull results back into the generic
  comic look. A mood is always an edit of that character's own approved reference.
- Location plates hold no people; characters are layered on top of them in the app.
- No character is modelled on a real, identifiable person without their written consent.

Needs OPENAI_API_KEY in `.env`; never prints it. The image API allows 5 input images per minute,
so edits are paced. About US$0.05 per image at 1024 px, medium quality.
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from PIL import Image, ImageFilter

REPO = Path(__file__).resolve().parents[2]
LOCATIONS = REPO / "web-frontend/public/assets/serial/locations"
CHARACTERS = REPO / "web-frontend/public/assets/serial/characters"
REFERENCES = REPO / "docs/design-reference/cast"
SCRATCH = REPO / "var/art"

_ENV = dotenv_values(REPO / ".env")
MODEL = _ENV.get("OPENAI_IMAGE_MODEL") or "gpt-image-2.5-flare"
BASE = (_ENV.get("OPENAI_API_BASE") or "https://api.openai.com/v1").rstrip("/")
EDIT_PACE_SECONDS = 13  # 5 input images per minute

PALETTE_WORDS = (
    "Strict palette: warm paper #F1ECE1, near-black ink #14110D, cobalt blue #1D3A8A, vermilion red "
    "#D8321A, sunflower yellow #F3C318, deep green #2C6A5D, ochre #C2890F"
)

PLATE_STYLE = (
    "Flat screen-printed illustration, like a three-colour risograph poster. " + PALETTE_WORDS + ". "
    "No other hues, no gradients, no photographic lighting, no outlines. Forms simplified into clean "
    "geometric shapes with flat fills, slight print misregistration and paper grain. Calm, generous, "
    "Bauhaus-inspired composition. No people, no animals, no readable text or signage. "
)

CAST_STYLE = (
    "Flat screen-printed poster illustration in the visual language of a vintage travel poster: the "
    "figure is built only from large flat colour shapes, the face modelled with three or four flat planes "
    "of tone, hair as one sculpted mass with a few cut-out waves in brown and ochre, clothes as flat "
    "shapes with one colour reflection. No linework, no hair strands, no skin texture, no glossy "
    "highlights, slight print misregistration and paper grain. Beautiful and elegant, attractive in their "
    "own way, with real warmth, realistic adult proportions. Crucially, this face has its own specific "
    "bone structure, eye shape, nose and mouth exactly as described; it must not look like a generic or "
    "default illustrated face. Chest-up portrait, three-quarter view, head large in the frame. "
    + PALETTE_WORDS + ", and natural skin tones. Transparent background, nothing behind the figure. "
    "No text. "
)

KEEP = (
    "Exactly the same person as the reference image: same face, hair, clothes, colours, framing, flat "
    "screen-printed poster style and transparent background. Change only the facial expression (and head "
    "tilt or a hand if needed), and let the whole face take part so the emotion reads clearly: "
)

# face = (centre x, centre y, crop size), as fractions of the square reference: where the app's
# round 256px portrait is cut from.
CAST: dict[str, dict] = {
    "romy_tremblay": {
        "face": (0.50, 0.29, 0.44),
        "who": "Romy, a Québécoise TV journalist in her early thirties. A soft oval face with high cheekbones "
               "and a gently pointed chin; long straight brown hair with a centre parting falling past her "
               "shoulders, a few caramel strands; light blue-grey eyes, slightly heavy-lidded, glancing "
               "sideways; strong straight dark brows; full lips; a faint dusting of freckles across the nose. "
               "Pensive pose, chin resting lightly on the back of her hand. Black leather jacket over a "
               "deep-blue top, a small clip-on microphone.",
        "moods": {"happy": "a real laugh, head tilted slightly, eyes creased with joy",
                  "cross": "cold anger: brows pulled down, jaw set, lips pressed tight, a hard stare",
                  "moved": "deeply moved: visible tears welling in her eyes, one tear on her cheek, brows "
                           "lifted in the middle, lips trembling in a small smile"},
    },
    "marin_leveque": {
        "face": (0.46, 0.29, 0.44),
        "who": "Marin, a gentle giant in his mid-thirties: a big, broad-shouldered man with a normal adult head "
               "size in natural proportion to his body. A broad round face with full cheeks, small warm brown "
               "eyes with deep laugh lines, a wide flat nose, big ears, thick dark tightly curled hair, a short "
               "full dark beard, warm olive-brown skin. Handsome in a soft, bear-like way. A hand-knitted "
               "deep-green sweater, a small lucky charm on a cord. A shy, hopeful smile.",
        "moods": {"happy": "beaming, a huge warm grin, cheeks lifted, eyes crinkled",
                  "cross": "hurt and upset: brows knitted, a frown, looking away",
                  "moved": "openly crying with emotion: tears running down both cheeks into his beard, brows "
                           "raised in the middle, a trembling grateful smile"},
    },
    "lila_bonnet": {
        "face": (0.52, 0.43, 0.52),
        "who": "Lila, a primary-school teacher and painter in her late twenties, drawn realistically with natural "
               "adult facial anatomy. A heart-shaped face, large wide-set dark eyes of natural size, a small "
               "upturned nose, a wide mouth with a small gap between her front teeth, warm light-brown skin with "
               "freckles, black curly hair piled in a high bun tied with an ochre scarf, gold hoop earrings, a "
               "clean ochre shirt. A mischievous side glance and a half smile.",
        "moods": {"happy": "laughing openly, a wide gap-toothed grin, eyes squeezed",
                  "cross": "exasperated: an eye-roll, mouth twisted to one side",
                  "moved": "touched: one hand on her heart, a soft smile, eyes shining"},
    },
    "augustin_de_roncourt": {
        "face": (0.50, 0.26, 0.48),
        "who": "Augustin « Gus », a dandy in his early thirties. A long narrow face with sharp high cheekbones, a "
               "strong aquiline nose, hooded grey-green eyes, clean-shaven, slicked-back black hair with one "
               "loose curl on the forehead, pale skin with rosy cheeks. An impeccable navy three-piece suit, a "
               "red pocket square. Chin raised, amused, a knowing smile.",
        "moods": {"happy": "triumphant delight: a big confident grin, eyebrows up",
                  "cross": "mock outrage: deeply offended, eyebrows high, mouth open in protest",
                  "moved": "caught being sincere: a rare genuine, soft, slightly embarrassed look"},
    },
    "margaux_barman": {
        "face": (0.47, 0.25, 0.40),
        "who": "Margaux, a café owner-bartender in her late fifties. A square jaw, a strong Roman nose, deep-set "
               "dark eyes with crow's feet, short cropped silver hair, deeply tanned skin with fine lines, a "
               "single small gold hoop. Striking and handsome. A dark apron over a deep-green shirt with rolled "
               "sleeves, drying a wine glass with a cloth. A dry, knowing half-smile.",
        "moods": {"happy": "a rare warm smile that reaches her eyes",
                  "cross": "stern and disapproving, one eyebrow raised, mouth flat",
                  "moved": "unexpectedly moved: eyes glistening with held-back tears, brows lifted, pressing "
                           "her lips together, the glass forgotten in her hand"},
    },
    "landlord_marchand": {
        "face": (0.53, 0.31, 0.50),
        "who": "Monsieur Marchand, a landlord in his early seventies. A long lined face, a long nose, pale blue "
               "eyes behind small round wire glasses, big bushy white eyebrows, thinning white hair with soft "
               "tufts above the ears, fair skin. Dignified and slightly grumpy, but not a caricature. A grey "
               "cardigan, a green wool scarf, a ring of old keys in one hand.",
        "moods": {"happy": "a grudging crooked smile despite himself",
                  "cross": "outraged: bushy eyebrows bristling, mouth open mid-complaint",
                  "moved": "unexpectedly touched: eyes watery behind his glasses, lips pressed together"},
    },
}

# The brand inks plus their tints and deep tones: the palette lock snaps toward these.
LOCK_PALETTE = [
    "#f1ece1", "#f8f3e8", "#e8e0cf", "#d8cdb6", "#14110d", "#4a4538", "#6f6857",
    "#1d3a8a", "#14285f", "#d8321a", "#9c2411", "#f3c318", "#c49a0a",
    "#2c6a5d", "#1f4f45", "#c2890f", "#a85d24",
]


def _key() -> str:
    key = _ENV.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY is missing from .env")
    return key


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _call(prompt: str, *, size: str, reference: Image.Image | None = None, transparent: bool = False) -> Image.Image:
    data: dict = {"model": MODEL, "prompt": prompt, "size": size, "quality": "medium", "n": 1}
    if transparent:
        data.update(background="transparent", output_format="png")
    headers = {"Authorization": f"Bearer {_key()}"}
    for attempt in range(4):
        with httpx.Client(timeout=300) as client:
            if reference is None:
                resp = client.post(f"{BASE}/images/generations", headers=headers, json=data)
            else:
                resp = client.post(f"{BASE}/images/edits", headers=headers,
                                   data={k: str(v) for k, v in data.items()},
                                   files={"image[]": ("ref.png", _png(reference), "image/png")})
        if resp.status_code != 429:
            break
        time.sleep(20 * (attempt + 1))
    if resp.status_code >= 400:
        raise RuntimeError(f"image API {resp.status_code}: {resp.text[:300]}")
    item = resp.json()["data"][0]
    raw = base64.b64decode(item["b64_json"]) if item.get("b64_json") else httpx.get(item["url"]).content
    return Image.open(io.BytesIO(raw))


def palette_lock(image: Image.Image, strength: float = 0.55) -> Image.Image:
    """Snap an image toward the brand inks without posterising it into blotches."""
    rgb = image.convert("RGB")
    pal: list[int] = []
    for hex_ in LOCK_PALETTE:
        pal += [int(hex_[i:i + 2], 16) for i in (1, 3, 5)]
    pal += pal[:3] * (256 - len(LOCK_PALETTE))
    target = Image.new("P", (1, 1))
    target.putpalette(pal)
    snapped = (rgb.filter(ImageFilter.MedianFilter(3))
               .quantize(palette=target, dither=Image.Dither.NONE).convert("RGB")
               .filter(ImageFilter.ModeFilter(7)))
    soft = Image.blend(rgb, snapped, strength)
    grain = Image.effect_noise(soft.size, 20).convert("RGB")
    return Image.blend(soft, grain, 0.04)


def plate(location: str) -> None:
    src = LOCATIONS / f"{location}.webp"
    original = Image.open(src).convert("RGB")
    prompt = (PLATE_STYLE + f"Redraw this exact place ({location.replace('_', ' ')}, Paris) keeping its layout, "
              "viewpoint, light and every key object, as the same flat screen print. Remove any people.")
    raw = _call(prompt, size="1536x1024", reference=original).convert("RGB")
    (SCRATCH / "plates").mkdir(parents=True, exist_ok=True)
    raw.save(SCRATCH / "plates" / f"{location}-raw.webp", quality=88)
    palette_lock(raw).save(src, quality=86)
    print(f"ok {location}")


def reference(character: str) -> None:
    image = _call(CAST_STYLE + CAST[character]["who"], size="1024x1024", transparent=True).convert("RGBA")
    out = REFERENCES / character
    out.mkdir(parents=True, exist_ok=True)
    image.save(out / "reference.webp", quality=88)
    print(f"ok {character} reference — review it before generating moods")


def moods(character: str) -> None:
    ref = Image.open(REFERENCES / character / "reference.webp").convert("RGBA")
    for mood, how in CAST[character]["moods"].items():
        image = _call(KEEP + how + ".", size="1024x1024", reference=ref, transparent=True).convert("RGBA")
        image.save(REFERENCES / character / f"{mood}.webp", quality=88)
        print(f"ok {character} {mood}")
        time.sleep(EDIT_PACE_SECONDS)


def crop(character: str) -> None:
    fx, fy, fs = CAST[character]["face"]
    folder = REFERENCES / character
    for mood in ("neutral", "happy", "cross", "moved"):
        src = folder / ("reference.webp" if mood == "neutral" else f"{mood}.webp")
        image = Image.open(src).convert("RGBA")
        w = image.width
        size = int(fs * w)
        x0 = max(0, min(w - size, int(fx * w - size / 2)))
        y0 = max(0, min(w - size, int(fy * w - size / 2)))
        face = image.crop((x0, y0, x0 + size, y0 + size)).resize((256, 256), Image.LANCZOS)
        paper = Image.new("RGBA", (256, 256), (241, 236, 225, 255))
        paper.alpha_composite(face)
        paper.convert("RGB").save(CHARACTERS / character / f"portrait-{mood}.webp", quality=86)
    print(f"ok {character} portraits")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plate")
    p.add_argument("location", help="a file stem in public/assets/serial/locations, or 'all'")
    for name in ("reference", "moods", "crop"):
        sub.add_parser(name).add_argument("character", choices=sorted(CAST))
    lk = sub.add_parser("lock")
    lk.add_argument("src")
    lk.add_argument("dst")
    args = parser.parse_args()

    if args.cmd == "plate":
        names = sorted(p.stem for p in LOCATIONS.glob("*.webp")) if args.location == "all" else [args.location]
        for i, name in enumerate(names):
            plate(name)
            if i < len(names) - 1:
                time.sleep(EDIT_PACE_SECONDS)
    elif args.cmd == "reference":
        reference(args.character)
    elif args.cmd == "moods":
        moods(args.character)
    elif args.cmd == "crop":
        crop(args.character)
    elif args.cmd == "lock":
        palette_lock(Image.open(args.src)).save(args.dst, quality=86)


if __name__ == "__main__":
    main()
