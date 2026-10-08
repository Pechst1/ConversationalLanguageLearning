#!/usr/bin/env python3
"""WP-103 T1 — the owner's listening sheet: do the voices sound native French?

No test can decide this; an ear can. This makes the sheet the owner listens to:
each of the six characters and the narrator says one short line at the A1 pace
and at the B1 pace (14 clips), spoken exactly as production speaks them
(:func:`app.services.episode_audio.speak_text` — the steerable model, the
character's instructions, the fallback), plus two probes that answer «does the
model honour what we send?»:

* **speed probe** — Romy at the A1 pace, with the instructions and with
  ``speed=0.9`` forced. Beside her ordinary A1 clip (same words, same voice,
  same instructions, no ``speed``) the durations say whether the field does
  anything on this model.
* **plain probe** — Romy's voice with *no* instructions at all: what the model
  does by default, so the ear can hear what the instructions change.

It is a **paid** script (about US$0.02 for the whole sheet) with hard limits:
at most 16 clips and US$0.10, checked before the first call and again after
every one. Every synthesis is written on the pilot ledger like the app's own
(``line_audio_synthesis``, ``estimated: true``, with its basis) when the
database is reachable; ``--no-ledger`` skips that.

Usage::

    venv/bin/python scripts/listening_sheet.py --dry-run      # the plan, no calls
    venv/bin/python scripts/listening_sheet.py                # speak it (paid)
    venv/bin/python scripts/listening_sheet.py --reindex      # rewrite index.md from the mp3s (free)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.services import cast_voices  # noqa: E402
from app.services.episode_audio import (  # noqa: E402
    TTS_PROVIDER,
    estimate_synthesis_cost_usd,
    speak_text,
    spec_for,
)

OUT_DIR = ROOT / "docs/implementation/atelier-v2/listening-sheet-2026-09-29"
MAX_CLIPS = 16
MAX_USD = 0.10
#: The doc's own estimate of the model: US$0.015 a minute of speech.
USD_PER_MINUTE = 0.015

#: (character id, name shown on the sheet, the line). One line per person, said
#: at both paces, so the ear compares pace and not words.
SHEET: tuple[tuple[str, str, str], ...] = (
    ("romy_tremblay", "Romy", "Salut ! Tu veux t'asseoir avec nous ? On t'a gardé une place."),
    ("marin_leveque", "Marin", "Bonjour ! Moi, c'est Marin. Tu prends un café avec nous ?"),
    ("lila_bonnet", "Lila", "Alors, tu viens ? Assieds-toi là, à côté de moi !"),
    ("augustin_de_roncourt", "Gus", "Bonsoir ! Je m'appelle Augustin, mais tout le monde dit Gus."),
    ("margaux_barman", "Margaux", "Qu'est-ce que je vous sers ? Un café, un verre d'eau ?"),
    ("landlord_marchand", "M. Marchand", "Bonjour, madame. Le loyer est à payer avant le cinq du mois."),
    ("narrator", "La narratrice", "Il est huit heures. Au Mistral, la journée commence."),
)


@dataclass
class Item:
    number: int
    kind: str  # "sheet" | "probe-speed" | "probe-plain"
    character_id: str
    name: str
    text: str
    band: str
    model: str
    instructions: str | None
    speed: float | None
    file: str = ""
    seconds: float = 0.0
    size: int = 0
    fell_back: bool = False

    @property
    def pace(self) -> str:
        return cast_voices.pace_for_band(self.band)

    @property
    def voice(self) -> str:
        return cast_voices.voice_for_character(self.character_id)


def plan() -> list[Item]:
    model = str(settings.FEUILLETON_AUDIO_TTS_MODEL)
    items: list[Item] = []
    for character_id, name, text in SHEET:
        for band in ("A1", "B1"):
            spec = spec_for(character_id, band, model=model)
            items.append(
                Item(len(items) + 1, "sheet", character_id, name, text, band, model,
                     spec.instructions, spec.speed)
            )
    romy_id, romy, romy_line = SHEET[0]
    a1 = spec_for(romy_id, "A1", model=model)
    items.append(
        Item(len(items) + 1, "probe-speed", romy_id, romy, romy_line, "A1", model, a1.instructions, 0.9)
    )
    items.append(
        Item(len(items) + 1, "probe-plain", romy_id, romy, romy_line, "B1", model, None, None)
    )
    return items


def worst_case_usd(items: list[Item]) -> float:
    """A ceiling before any call: the configured per-character rate, doubled."""

    return round(2 * sum(estimate_synthesis_cost_usd(len(item.text)) for item in items), 6)


def duration_seconds(path: Path) -> float:
    """``afinfo`` ships with macOS; the number is the clip's real length."""

    result = subprocess.run(  # noqa: S603
        ["afinfo", str(path)], capture_output=True, text=True, check=False  # noqa: S607
    )
    match = re.search(r"estimated duration:\s*([0-9.]+)", result.stdout)
    return float(match.group(1)) if match else 0.0


def slug(item: Item) -> str:
    who = re.sub(r"[^a-z]+", "-", item.name.lower()).strip("-")
    tag = {"sheet": item.pace, "probe-speed": "a1-speed-0.9", "probe-plain": "sans-instructions"}[item.kind]
    return f"{item.number:02d}-{who}-{tag}"


def speak(items: list[Item], *, ledger: bool) -> float:
    from app.services.llm_service import LLMService

    provider = LLMService()
    db = None
    if ledger:
        try:
            from app.db.session import SessionLocal

            db = SessionLocal()
        except Exception as exc:  # noqa: BLE001
            print(f"ledger unavailable ({exc}); costs are only in index.md")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    for item in items:
        if spent >= MAX_USD:
            raise SystemExit(f"stopped: measured estimate {spent:.4f} reached the cap")
        if item.kind == "sheet":
            spoken = speak_text(
                provider, text=item.text, voice=item.voice, character_id=item.character_id,
                band=item.band, model=item.model,
            )
            audio, item.fell_back = spoken.audio, spoken.fell_back
            if item.fell_back:
                # The sheet judges the steerable model; a fallback clip says
                # nothing about it. Stop before spending more (the warning above
                # carries the provider's error).
                raise SystemExit(f"stopped: clip {item.number} fell back to {spoken.model}")
        else:
            extra = {}
            if item.instructions:
                extra["instructions"] = item.instructions
            if item.speed is not None:
                extra["speed"] = item.speed
            audio = provider.text_to_speech(
                text=item.text, voice=item.voice, model=item.model, provider=TTS_PROVIDER, **extra
            )
        path = OUT_DIR / f"{slug(item)}.mp3"
        path.write_bytes(audio)
        item.file, item.size = path.name, len(audio)
        item.seconds = duration_seconds(path)
        cost = round(item.seconds / 60.0 * USD_PER_MINUTE, 6)
        spent += cost
        print(f"{item.number:2d} {path.name}  {item.seconds:5.2f}s  {item.size / 1024:5.1f} kB  ~${cost:.5f}")
        if db is not None:
            try:
                from app.services.line_audio import LINE_AUDIO_EVENT_TYPE
                from app.services.pilot_events import PilotEventService

                PilotEventService(db).record(
                    LINE_AUDIO_EVENT_TYPE,
                    user_id=None,
                    entity_type="listening_sheet",
                    payload={
                        "surface": "listening_sheet_2026-09-29",
                        "provider": TTS_PROVIDER,
                        "model": item.model,
                        "voice": item.voice,
                        "character_id": item.character_id,
                        "pace": item.pace,
                        "kind": item.kind,
                        "instructions_version": cast_voices.SPEECH_INSTRUCTIONS_VERSION,
                        "lines": 1,
                        "chars": len(item.text),
                        "seconds": item.seconds,
                        "estimated": True,
                        "cost_basis": f"{USD_PER_MINUTE}/min of speech (measured duration)",
                    },
                    cost_usd=cost,
                )
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                print(f"  ledger row not written ({exc})")
                db = None
    return spent


def write_index(items: list[Item], spent: float) -> None:
    def instructions_of(item: Item) -> str:
        return (item.instructions or "(none: the model's defaults)").replace("\n", "<br>")

    lines = [
        "# Listening sheet — 2026-09-29 (WP-103 T1, decision R-5)",
        "",
        "**Question for the owner's ear:** does each voice sound like a native French speaker",
        "(no English accent), at a pace a learner can follow? Tick the box per clip.",
        "Romy is a Québécoise: a *light Montréal accent* is intended for her, an English one is not.",
        "",
        f"Model `{items[0].model}` · instructions version `{cast_voices.SPEECH_INSTRUCTIONS_VERSION}` · "
        f"{len(items)} clips · measured length {sum(i.seconds for i in items):.1f} s · "
        f"size {sum(i.size for i in items) / 1024:.0f} kB · "
        f"**estimated cost US${spent:.4f}** (US$0.015 a minute of speech, from the clips' real duration; "
        "the speech endpoint returns no usage, so this is an estimate and each ledger row says so).",
        "",
        "Regenerate with `venv/bin/python scripts/listening_sheet.py` (paid, capped at 16 clips / US$0.10).",
        "",
        "| # | Clip | Who | Pace | Speed sent | Length | Sonne français natif ? |",
        "|---|------|-----|------|-----------|--------|------------------------|",
    ]
    for item in items:
        pace = {"a1": "A1 posé", "a2": "A2", "b1": "B1 naturel"}[item.pace]
        if item.kind == "probe-plain":
            pace = "sans instructions"
        speed = f"{item.speed}" if item.speed is not None else "—"
        lines.append(
            f"| {item.number} | [{item.file}]({item.file}) | {item.name} (`{item.voice}`) | {pace} | "
            f"{speed} | {item.seconds:.2f} s | [ ] oui · [ ] à peine · [ ] non |"
        )
    lines += ["", "## The lines", ""]
    seen: set[tuple[str, str]] = set()
    for item in items:
        if (item.name, item.text) in seen:
            continue
        seen.add((item.name, item.text))
        lines.append(f"- **{item.name}** — « {item.text} »")
    lines += ["", "## What each clip was told", ""]
    for item in items:
        lines += [
            f"### {item.number}. {item.name} — {item.kind} — {item.band} pace",
            "",
            f"- model: `{item.model}`" + (" (**fell back**)" if item.fell_back else ""),
            f"- voice: `{item.voice}` · speed sent: `{item.speed}`",
            f"- instructions: {instructions_of(item)}",
            "",
        ]
    by_pair: dict[str, dict[str, float]] = {}
    for item in items:
        if item.kind == "sheet":
            by_pair.setdefault(item.name, {})[item.pace] = item.seconds
    lines += [
        "## Evidence: do `instructions` and `speed` do anything on this model?",
        "",
        "**Instructions.** They are accepted (HTTP 200, no error; `tts-1` is not sent them). Whether they are",
        "*obeyed* — no English accent, the persona, the Montréal accent for Romy — is exactly what your ear",
        "decides; clip 16 is the same voice with no instructions at all, to hear what they change.",
        "For the pace: same words, same voice, same instructions, only the pace sentence differs",
        "(A1 «posé, articulé, sans traîner», B1 «naturel»), no `speed` sent:",
        "",
        "| Who | A1 | B1 | A1 ÷ B1 |",
        "|-----|----|----|---------|",
    ]
    ratios = []
    for name, pair in by_pair.items():
        a1, b1 = pair.get("a1", 0.0), pair.get("b1", 0.0)
        if b1:
            ratios.append(a1 / b1)
            lines.append(f"| {name} | {a1:.2f} s | {b1:.2f} s | {a1 / b1:.2f}× |")
    if ratios:
        slower = sum(1 for ratio in ratios if ratio > 1.0)
        lines += [
            "",
            f"A1 came out slower than B1 for {slower} of {len(ratios)} voices "
            f"(mean {sum(ratios) / len(ratios):.2f}×). The pace sentence *steers* the pace but is not a",
            "guarantee: a single take is noisy, so judge pace by ear, not by this table.",
        ]
    plain = next((i for i in items if i.kind == "probe-plain"), None)
    a1_romy = next((i for i in items if i.kind == "sheet" and i.name == "Romy" and i.pace == "a1"), None)
    probe = next((i for i in items if i.kind == "probe-speed"), None)
    if probe and a1_romy and a1_romy.seconds and probe.seconds:
        lines += [
            "",
            "**Speed.** OpenAI's API reference lists `speed` (0.25–4.0) for the endpoint, but its team said in",
            "May 2025 that `gpt-4o-mini-tts` does not support it (a later forum reply says it works again).",
            f"Probe (Romy, A1 instructions): clip 01 without `speed` {a1_romy.seconds:.2f} s, clip 15 with "
            f"`speed=0.9` {probe.seconds:.2f} s → {probe.seconds / a1_romy.seconds:.2f}× "
            "(honoured would be ≈ 1.11×; 1.00× would mean ignored). The field is *accepted* and the clip is "
            "longer, but this is one pair against a noisy baseline: suggestive, not proof. So production does "
            "**not** send it to this model by default; `tts-1`/`tts-1-hd` (the fallback) do get 0.9 at A1. "
            "**Your call:** listen to 01 then 15; if 15 is the pace you want and sounds natural, set "
            "`FEUILLETON_AUDIO_STEERABLE_A1_SPEED=0.9` on the API (no code change).",
            "",
            "Note: the A1 clips on this sheet were spoken exactly as production speaks them, i.e. without `speed`.",
        ]
    if plain:
        lines += ["", f"No-instructions probe (Romy voice, B1 line): {plain.seconds:.2f} s."]
    (OUT_DIR / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def reindex(items: list[Item]) -> float:
    """Rebuild ``index.md`` from the mp3s already on disk. Free: no call is made."""

    spent = 0.0
    for item in items:
        path = OUT_DIR / f"{slug(item)}.mp3"
        if not path.exists():
            raise SystemExit(f"missing {path.name}: nothing to index")
        item.file, item.size = path.name, path.stat().st_size
        item.seconds = duration_seconds(path)
        spent += item.seconds / 60.0 * USD_PER_MINUTE
    return spent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="print the plan and the ceiling; no calls")
    parser.add_argument("--no-ledger", action="store_true", help="do not write pilot-ledger rows")
    parser.add_argument("--reindex", action="store_true", help="rewrite index.md from the mp3s on disk; no calls")
    args = parser.parse_args()

    items = plan()
    ceiling = worst_case_usd(items)
    print(f"{len(items)} clips, {sum(len(i.text) for i in items)} characters, ceiling US${ceiling:.4f}")
    if len(items) > MAX_CLIPS or ceiling > MAX_USD:
        raise SystemExit("refusing: over the clip or cost limit")
    if args.dry_run:
        for item in items:
            print(f"{item.number:2d} {slug(item)}  {item.voice:8s} speed={item.speed}  {item.text}")
        return
    if args.reindex:
        write_index(items, reindex(items))
        print("index.md rewritten from the mp3s on disk (no calls)")
        return
    if not settings.OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY is not set")
    spent = speak(items, ledger=not args.no_ledger)
    write_index(items, spent)
    print(f"done: {OUT_DIR}  estimated cost US${spent:.4f}")


if __name__ == "__main__":
    main()
