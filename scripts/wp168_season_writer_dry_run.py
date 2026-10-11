"""WP-168 dry run: three lives that finished season 1 roll over into a written season.

Each life ends season 1 differently (garder / partager / laisser_partir, the flags of
``app/data/season/s1/``), is carried into the continuation exactly as the engine does
(``epilogue.carry_into_live``), and holds a few rows of material a ~66-day life would
have left open (synthetic, listed in the README). ``living_story.roll_over_season`` is
then called with the writer on and allowed to move; the draft, the critic's verdict and
the merged world are saved per life. Optionally the first new place of each accepted
season is painted through the shared plate interface (``season.plates.paint_plate``).

    venv/bin/python scripts/wp168_season_writer_dry_run.py --out docs/implementation/atelier-v2/evidence/wp168-season-writer [--paint] [--max-usd 0.8]

Uses the real provider from .env (PAID). No database: the roll-over runs on an
in-memory thread; plates are recorded in a throwaway SQLite table.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.services import living_story as engine  # noqa: E402
from app.services import season_writer  # noqa: E402
from app.services.season.clock import SEASON_KEY, nominal_calendar  # noqa: E402
from app.services.season.epilogue import carry_into_live  # noqa: E402
from app.services.season.format import load_season  # noqa: E402
from app.services.season.world import season_world_bible  # noqa: E402

ENDING_FLAGS = {
    "garder": {"s1.flat_decision": "keep", "s1.evidence_shared": "marchand_only", "s1.margaux_persuaded": True,
               "marchand.sundays": True, "romy.footage": "kept"},
    "partager": {"s1.flat_decision": "coop", "s1.evidence_shared": "public", "s1.gus_persuaded": True,
                 "s1.lila_has_key": True},
    "laisser_partir": {"s1.flat_decision": "sell"},
}

#: What a ~66-day life left open besides its ending (synthetic; see the README).
LIFE_ROWS: dict[str, dict[str, list[dict]]] = {
    "garder": {
        "planted": [
            {"id": "p:polaroid_port", "text_fr": "Dans le tiroir d'Odile, un Polaroid : un port, des bateaux, et « 1971 » au dos.", "status": "planted", "character_id": "romy_tremblay"},
            {"id": "p:lettre_gus", "text_fr": "Gus a reçu une lettre d'un notaire, avec un timbre étranger, et il ne l'ouvre pas.", "status": "planted", "character_id": "augustin_de_roncourt"},
        ],
        "consequences": [
            {"id": "b:peintre_l", "kind": "branch", "text_fr": "Vous avez promis à M. Marchand de retrouver le peintre « L. » avant son anniversaire.", "weight": 3, "day": 58, "last_referenced": None, "character_id": "landlord_marchand"},
            {"id": "b:documentaire", "kind": "branch", "text_fr": "Romy vous a demandé d'être la voix française de son documentaire radio.", "weight": 2, "day": 52, "last_referenced": None, "character_id": "romy_tremblay"},
        ],
        "commitments": [
            {"id": "c:carte_mistral", "text_fr": "Aider Margaux à refaire la carte du Mistral avant le printemps.", "status": "open", "witnesses": ["margaux_barman"]},
        ],
    },
    "partager": {
        "planted": [
            {"id": "p:lettres_grand_mere", "text_fr": "Dans le loft de Gus, une caisse de lettres de sa grand-mère, écrites d'une ville où il n'est jamais allé.", "status": "planted", "character_id": "augustin_de_roncourt"},
            {"id": "p:dessin_enfant", "text_fr": "À l'atelier, un enfant dessine toujours la même maison au bord de l'eau.", "status": "planted", "character_id": None},
        ],
        "consequences": [
            {"id": "b:mariage_camille", "kind": "branch", "text_fr": "Camille vous a demandé de l'accompagner à un mariage de famille, loin de Paris.", "weight": 3, "day": 61, "last_referenced": None, "character_id": "camille_marchand"},
            {"id": "b:roman_marin", "kind": "branch", "text_fr": "Marin vous a confié son roman et vous a demandé où il devrait se passer.", "weight": 2, "day": 47, "last_referenced": None, "character_id": "marin_leveque"},
        ],
        "commitments": [
            {"id": "c:interviews_romy", "text_fr": "Traduire les interviews de Romy pour son nouveau contrat.", "status": "open", "witnesses": ["romy_tremblay"]},
        ],
    },
    "laisser_partir": {
        "planted": [
            {"id": "p:carte_phare", "text_fr": "La carte postale de Margaux : un phare, et « Il y a du travail ici, si tu veux. »", "status": "planted", "character_id": "margaux_barman"},
            {"id": "p:neon", "text_fr": "Romy a gardé le dernier néon du Mistral dans sa cave.", "status": "planted", "character_id": "romy_tremblay"},
        ],
        "consequences": [
            {"id": "b:bateau_pere", "kind": "branch", "text_fr": "Marin vous a dit que son père cherche quelqu'un pour l'été, sur son bateau.", "weight": 3, "day": 60, "last_referenced": None, "character_id": "marin_leveque"},
            {"id": "b:camion_tableau", "kind": "branch", "text_fr": "Un voisin a vu le camion du brocanteur partir vers le sud avec le tableau.", "weight": 2, "day": 59, "last_referenced": None, "character_id": "augustin_de_roncourt"},
        ],
        "commitments": [
            {"id": "c:photos_lila", "text_fr": "Envoyer à Lila les photos du canal, chaque dimanche.", "status": "open", "witnesses": ["lila_bonnet"]},
        ],
    },
}


def finished_life(ending: str) -> dict:
    season = load_season("s1")
    played = []
    # The whole calendar: the eight tentpoles, the gaps and the epilogue week (65 days).
    for row in nominal_calendar(season):
        played.append({**row, "flex": 0, "date": None, "event_id": f"dry:{row['key']}"})
    live = {
        SEASON_KEY: {"id": "s1", "played": played, "flags": dict(ENDING_FLAGS[ending]), "signals": []},
        "season_index": 1,
        **LIFE_ROWS[ending],
    }
    return carry_into_live(live, season=season)


def spend(records: dict) -> float:
    return round(sum(float(u.get("cost_usd") or 0) for rec in records.values() for u in rec.get("usage") or []), 6)


def summary(world: dict) -> dict:
    setting = world.get("setting") or {}
    return {
        "season_number": world.get("season_number"),
        "season_source": world.get("season_source"),
        "world_bible_version": world.get("world_bible_version"),
        "title_fr": world.get("season_title_fr"),
        "logline": world.get("logline"),
        "season_logline_fr": world.get("season_logline_fr"),
        "setting": {key: setting.get(key) for key in ("city", "previous_city", "region", "neighborhood", "genre", "tone", "situation")},
        "places": [
            {key: place.get(key) for key in ("id", "name_fr", "type", "description", "brief", "plate_id", "stand_in")}
            for place in setting.get("recurring_locations") or []
            if isinstance(place, dict) and place.get("plate_id")
        ],
        "kept_places": [
            place.get("id") for place in setting.get("recurring_locations") or [] if isinstance(place, dict) and not place.get("plate_id")
        ],
        "new_characters": [member for member in world.get("cast") or [] if isinstance(member, dict) and member.get("written_season")],
        "away": {member["id"]: member["away"] for member in world.get("cast") or [] if isinstance(member, dict) and member.get("away")},
        "arcs": [
            {"id": arc.get("id"), "title_fr": arc.get("title_fr"), "characters": arc.get("characters"),
             "grounded_in": arc.get("grounded_in"), "stages": [stage.get("summary") for stage in arc.get("stages") or []]}
            for arc in world.get("season_arcs") or []
        ],
        "situation": engine.season_situation(world),
    }


def paint_first_places(results: dict, out: Path, max_usd: float, spent: float) -> dict:
    """Paint the first new place of each written season (throwaway SQLite, local storage)."""

    import tempfile

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.models.revue_place import RevuePlace
    from app.services.season import plates

    tmp = Path(tempfile.mkdtemp(prefix="wp168-plates-"))
    settings.GRAPHIC_NOVEL_IMAGE_STORAGE = "local"
    settings.GRAPHIC_NOVEL_LOCAL_IMAGE_DIR = tmp
    db_engine = create_engine(f"sqlite:///{tmp / 'plates.db'}")
    RevuePlace.__table__.create(bind=db_engine)
    painted: dict[str, dict] = {}
    with Session(db_engine) as db:
        for ending, result in results.items():
            places = result.get("world", {}).get("places") or []
            if not places:
                continue
            if spent + 0.07 > max_usd:
                print(f"  budget: not painting {ending}", flush=True)
                break
            place = places[0]
            started = time.monotonic()
            try:
                url = plates.paint_plate(db, plates.plate_key(place["plate_id"]), place["brief"], name_fr=place["name_fr"])
            except Exception as exc:  # noqa: BLE001
                print(f"  {ending}: plate failed: {exc}", flush=True)
                painted[ending] = {"place": place["id"], "error": str(exc)[:300]}
                continue
            spent += 0.06
            stored = next(tmp.rglob(f"*{plates.plate_key(place['plate_id']).replace(':', '-')}*"), None)
            target = out / f"plate-{ending}-{place['id']}.webp"
            if stored:
                shutil.copyfile(stored, target)
            painted[ending] = {"place": place["id"], "url": url, "file": target.name, "seconds": round(time.monotonic() - started, 1)}
            print(f"  {ending}: painted {place['id']} in {painted[ending]['seconds']} s", flush=True)
    return {"plates": painted, "estimated_image_usd": round(0.06 * sum(1 for row in painted.values() if row.get("file")), 2)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs/implementation/atelier-v2/evidence/wp168-season-writer")
    parser.add_argument("--paint", action="store_true")
    parser.add_argument("--max-usd", type=float, default=0.8)
    parser.add_argument("--only", nargs="*", default=list(ENDING_FLAGS))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    settings.ATELIER_LLM_ENABLED = True
    settings.ATELIER_SEASON_WRITER_ENABLED = True
    settings.ATELIER_SEASON_WRITER_MAY_MOVE = True

    records: dict[str, dict] = {}
    current: dict[str, str] = {}
    original = season_writer.draft_next_season

    def recording(**kwargs):
        return original(**kwargs, record=records[current["ending"]])

    season_writer.draft_next_season = recording
    results: dict[str, dict] = {}
    for ending in args.only:
        if spend(records) > args.max_usd - 0.1:
            print(f"budget reached before {ending}", flush=True)
            break
        current["ending"] = ending
        records[ending] = {}
        thread = SimpleNamespace(id=f"wp168-{ending}", world_bible=season_world_bible("s1"))
        live = finished_life(ending)
        started = time.monotonic()
        rolled = engine.roll_over_season(None, thread, live, day=66, today="2026-12-20")
        record = records[ending]
        seconds = round(time.monotonic() - started, 1)
        result = {
            "ending": ending,
            "rolled": rolled,
            "seconds": seconds,
            "material": record.get("material"),
            "canon": record.get("canon"),
            "draft": record.get("draft"),
            "review": record.get("review"),
            "refused": record.get("refused"),
            "details": record.get("details"),
            "usage": record.get("usage"),
            "world": summary(thread.world_bible) if rolled else None,
            "interlude": live.get("interlude"),
        }
        results[ending] = result
        (args.out / f"life-{ending}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        verdict = result["review"] or {}
        print(
            f"{ending}: rolled={rolled} refused={result['refused']} city={(result['world'] or {}).get('setting', {}).get('city')} "
            f"grows={verdict.get('grows_from_material')} fresh={verdict.get('fresh')} "
            f"usd={spend({ending: record}):.4f} in {seconds}s",
            flush=True,
        )
    total = spend(records)
    report = {"llm_usd": total, "lives": {k: {"rolled": v["rolled"], "refused": v["refused"]} for k, v in results.items()}}
    if args.paint:
        report.update(paint_first_places({k: v for k, v in results.items() if v["rolled"]}, args.out, args.max_usd, total))
    (args.out / "spend.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
