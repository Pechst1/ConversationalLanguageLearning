"""Tomorrow's line: the one forward hook a finished scene leaves (WP-99, #466).

The hook names a real open row of the story or says nothing: never an invented plot.
It is written here and stored on the living story as ``next_teaser``, and the closing
panel's «À suivre…», Home, Done and the morning push all read that one row.

``STORY_SCENE_RECORD`` off: main's hook, word for word, as it stood in ``living_story``
before the story-truth stack (#466, #445, #620 rewrote it in ``story_teaser``). Nothing
here changes; it goes when the flag does.
"""

from __future__ import annotations

import re
from datetime import date as _date
from typing import Any

TEASER_WINDOW_DAYS = 14
TEASER_LEDGER_LIMIT = 30
TEASER_QUOTE_CHARS = 110
TEASER_KEY = "next_teaser"
TEASERS_KEY = "teasers"

# One opener per cast member, in their own voice; `tu`/`vous` where it matters.
TEASER_VOICES: dict[str, dict[str, str]] = {
    "marin_leveque": {"tu": "Dis, j'y repense… C'est peut-être un signe.", "vous": "Dites, j'y repense… C'est peut-être un signe."},
    "lila_bonnet": {"tu": "Toi, tu me caches quelque chose…", "vous": "Vous, vous me cachez quelque chose…"},
    "augustin_de_roncourt": {"tu": "Règle numéro un de La Méthode : on n'oublie rien.", "vous": "Règle numéro un de La Méthode : on n'oublie rien."},
    "romy_tremblay": {"tu": "Bon, c'est quoi la vraie histoire ?", "vous": "Bon, c'est quoi la vraie histoire ?"},
    "margaux_barman": {"tu": "J'ai rien entendu. Mais quand même…", "vous": "Je n'ai rien entendu. Mais quand même…"},
    "tiago_moreira": {"tu": "Pardon, une question…", "vous": "Pardon, une question…"},
}
DEFAULT_TEASER_VOICE = {"tu": "Au fait…", "vous": "Au fait…"}
_TEASER_FRAMES = {
    "commitment": (
        {"tu": "Tu n'as pas oublié ? « {text} »", "vous": "Vous n'avez pas oublié ? « {text} »"},
        {"tu": "Tu as promis, hein : « {text} »", "vous": "Vous avez promis, hein : « {text} »"},
    ),
    # #378: guillemets hold only words somebody said. A planted detail and a season
    # question are the story's, not a line of dialogue: they are told, not quoted.
    "plant": (
        {"tu": "Je repense à ce détail. {text}", "vous": "Je repense à ce détail. {text}"},
        {"tu": "Tu as remarqué ? {text}", "vous": "Vous avez remarqué ? {text}"},
    ),
    "thread": (
        {"tu": "Il faudra qu'on en parle. {text}", "vous": "Il faudra qu'on en parle. {text}"},
        {"tu": "Demain, peut-être, on saura. {text}", "vous": "Demain, peut-être, on saura. {text}"},
    ),
}



def _engine() -> Any:
    """``living_story``, read at call time: it imports this module at load."""

    from app.services import living_story

    return living_story


def _words(text: Any) -> set[str]:
    return {word for word in re.findall(r"\w+", str(text or "").casefold()) if len(word) > 3}


def _clip_quote(text: Any, limit: int = TEASER_QUOTE_CHARS) -> str:
    line = " ".join(str(text or "").split()).strip().strip("«»\"").strip()
    if len(line) <= limit:
        return line
    return line[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def teaser_candidates(live: dict, world: dict) -> list[dict]:
    """The open rows a teaser may name: promises, unpaid plants, open season questions."""

    rows: list[dict] = []
    for row in live.get("commitments") or []:
        # #378: a promise is quoted in the learner's own words (``source_quote``), never
        # in the model's restatement of it: the walk of 30 Oct read «Tu n'as pas oublié ?
        # « Je serai chez moi après quatorze heures. »», a sentence nobody said. A row
        # with no words of the learner's is not quoted at all.
        quote = str(row.get("source_quote") or "").strip() if isinstance(row, dict) else ""
        if isinstance(row, dict) and row.get("status") == "open" and row.get("id") and quote:
            rows.append({
                "ref": str(row["id"]), "kind": "commitment", "text_fr": quote,
                "characters": [str(who) for who in row.get("witnesses") or []],
            })
    for row in live.get("planted") or []:
        if isinstance(row, dict) and row.get("status") != "paid" and row.get("id") and row.get("text_fr"):
            rows.append({
                "ref": str(row["id"]), "kind": "plant", "text_fr": str(row["text_fr"]),
                "characters": [str(row.get("character_id") or "")],
            })
    # Season questions are season-wide: any cast member may raise one.
    for row in _engine().threads_projection(world, live):
        if row["state"] != "closed" and row.get("text_fr"):
            rows.append({"ref": row["key"], "kind": "thread", "text_fr": row["text_fr"], "characters": []})
    return rows


def teaser_grounded(text: str, ref: str | None, candidates: list[dict]) -> bool:
    """True only when the teaser names a real open row: its id, and its words."""

    row = next((item for item in candidates if item["ref"] == ref), None) if ref else None
    if row is None:
        return False
    needed = _words(_clip_quote(row["text_fr"]))
    if not needed:
        return False
    return len(needed & _words(text)) >= min(2, len(needed))


def compose_teaser(
    candidate: dict, *, character_id: str | None, register: str, variant: int = 0
) -> str:
    voice = TEASER_VOICES.get(str(character_id or ""), DEFAULT_TEASER_VOICE)
    key = "tu" if register == "tu" else "vous"
    frames = _TEASER_FRAMES[candidate["kind"]]
    frame = frames[int(variant) % len(frames)][key]
    return f"{voice[key]} {frame.format(text=_clip_quote(candidate['text_fr']))}"


def _days_between(earlier: str | None, later: str | None) -> int | None:
    a, b = _engine()._date_of(earlier), _engine()._date_of(later)
    if not a or not b:
        return None
    return (_date.fromisoformat(b) - _date.fromisoformat(a)).days


def next_teaser(
    live: dict,
    world: dict,
    *,
    character_id: str | None,
    register: str,
    date: str | None,
    seed: str,
    name: str | None = None,
) -> dict | None:
    """One forward line per resolution, or None — never an invented plot.

    Prefers a row the addressed character witnessed, then any open row, in a seeded
    order; skips any row or wording already used as a teaser in the last
    ``TEASER_WINDOW_DAYS`` days; and validates the composed line against the row it
    names before it is kept.
    """

    engine = _engine()
    today = engine._date_of(date) or engine._today().isoformat()
    recent = [
        row for row in live.get(TEASERS_KEY) or []
        if isinstance(row, dict)
        and (_days_between(row.get("date"), today) is not None)
        and 0 <= _days_between(row.get("date"), today) < TEASER_WINDOW_DAYS
    ]
    used_refs = {str(row.get("ref")) for row in recent}
    last_kind = str((recent[-1] if recent else {}).get("kind") or "")
    used_texts = {str(row.get("text_fr")) for row in recent}
    candidates = teaser_candidates(live, world)
    fresh = [row for row in candidates if row["ref"] not in used_refs]
    varied = len({row["kind"] for row in fresh}) > 1
    first_name = str(name or "").split(" ")[0].casefold()
    # Variety first (not the same kind of line as yesterday's), then the rows this
    # character was there for, then the learner's own dice.
    fresh.sort(
        key=lambda row: (
            1 if varied and row["kind"] == last_kind else 0,
            # A question about the speaker, quoted in the third person, sounds wrong
            # in their own mouth: someone else raises it first.
            1 if first_name and row["kind"] == "thread" and first_name in _words(row["text_fr"]) else 0,
            0 if character_id and character_id in row["characters"] else 1,
            engine._die(seed, "teaser", today, row["ref"]),
        )
    )
    for row in fresh:
        text = compose_teaser(
            row,
            character_id=character_id,
            register=register,
            variant=engine._die(seed, "teaser-frame", today),
        )
        if text in used_texts or not teaser_grounded(text, row["ref"], candidates):
            continue
        return {
            "text_fr": text,
            "character_id": character_id,
            **({"character_name": name} if name else {}),
            "date": today,
            "ref": row["ref"],
            "kind": row["kind"],
        }
    return None


def teasers_after(live: dict, teaser: dict | None) -> list[dict]:
    rows = [row for row in live.get(TEASERS_KEY) or [] if isinstance(row, dict)]
    if teaser:
        rows.append(
            {key: teaser.get(key) for key in ("ref", "kind", "text_fr", "date", "character_id")}
        )
    return rows[-TEASER_LEDGER_LIMIT:]
