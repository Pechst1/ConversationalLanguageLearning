"""Bounded paid calibration of the 2026-09-10 packages (owner-approved 2026-09-17).

Runs the judgement half of four packages against the real providers, on a
throwaway database, with a hard call cap and a cost ledger, and writes one JSON
report. Nothing here changes application code; it measures.

  placement  — three scripted personas (A1.1 / A2 / B1) answer the ladder
  register   — six turns where the deterministic detector abstains, judged by the model
  radio      — three French lines spoken by the TTS voice, saved as mp3 for the owner to hear
  intake     — the landlord letter as text, and the café menu rendered to a PNG for the vision path

Coverage (WP-29) is exercised by the living-story engine itself:
``scripts/longitudinal_story_review.py --live`` now carries the guard; run it
separately for that half.

Usage (never against the live database — the DATABASE_URL guard refuses it):

    DATABASE_URL=postgresql://localhost/<throwaway> venv/bin/python \
        scripts/calibrate_new_packages.py --live --max-calls 40 --max-cost-usd 1.00
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "var" / "reviews"


class Budget:
    def __init__(self, max_calls: int, max_cost: float) -> None:
        self.max_calls = max_calls
        self.max_cost = max_cost
        self.calls = 0
        self.cost = 0.0

    def check(self, what: str) -> None:
        if self.calls >= self.max_calls:
            raise RuntimeError(f"call cap {self.max_calls} reached before {what}")
        if self.cost >= self.max_cost:
            raise RuntimeError(f"cost cap US${self.max_cost:.2f} reached before {what}")

    def charge(self, cost: float | None, n: int = 1) -> None:
        self.calls += n
        self.cost += float(cost or 0.0)


PERSONAS = {
    "A1.1": {
        "A1.1": "Je m'appelle Anna. Je suis de Berlin.",
        "A1.2": "Un café s'il vous plaît. Combien?",
        "A2.1": "Samedi je suis au parc. Je mange pizza. Dimanche je dors.",
        "A2.2": "Désolé je suis en retard. 15h ok?",
        "B1.1": "Je pense c'est bien. Je ne sais pas.",
        "B1.2": "Oui. Non. Je ne comprends pas.",
        "B2.1": "Je ne sais pas.",
    },
    "A2": {
        "A1.1": "Bonjour, je m'appelle Anna et je viens de Berlin, en Allemagne.",
        "A1.2": "Bonjour, je voudrais un café crème, s'il vous plaît. Ça fait combien ?",
        "A2.1": "Le week-end dernier, je suis allée au marché avec une amie. Nous avons acheté des fruits et après nous avons mangé au restaurant.",
        "A2.2": "Bonjour Madame, je suis désolée, je vais arriver en retard à cause du métro. Est-ce que 15 h 30 vous convient ?",
        "B1.1": "Je pense que c'est une bonne idée parce que on peut rencontrer des gens. Mais c'est un peu cher.",
        "B1.2": "Si j'avais le temps, je voyagerais plus. Mais je travaille beaucoup.",
        "B2.1": "C'est difficile à dire. Il y a des avantages et des inconvénients.",
    },
    "B1": {
        "A1.1": "Bonjour ! Je m'appelle Anna, je viens de Berlin et j'habite à Lyon depuis six mois.",
        "A1.2": "Bonjour, je prendrais un café allongé, s'il vous plaît. Vous pourriez me dire combien je vous dois ?",
        "A2.1": "Le week-end dernier, j'ai rendu visite à mes grands-parents à la campagne. On a jardiné le samedi, puis le dimanche on a fait une longue promenade avant de rentrer.",
        "A2.2": "Bonjour Madame Roux, je suis vraiment désolée : mon train a été annulé et j'aurai une demi-heure de retard. Serait-il possible de décaler notre rendez-vous à 15 h 30 ?",
        "B1.1": "À mon avis, cela vaut la peine d'essayer, même si ce n'est pas donné : on y rencontre des gens qu'on ne croiserait jamais autrement.",
        "B1.2": "Si j'avais davantage de temps libre, je reprendrais la musique ; j'ai arrêté le piano quand j'ai commencé à travailler et ça me manque.",
        "B2.1": "Je dirais que la question mérite d'être nuancée : ce qui semble une contrainte au premier abord devient souvent un avantage à long terme.",
    },
}

REGISTER_TURNS = [
    # (counterpart, expected register, learner text)
    ("le propriétaire", "vous", "Salut, tu peux venir réparer le chauffage demain ?"),
    ("le propriétaire", "vous", "Bonjour, pourriez-vous passer demain pour le chauffage ?"),
    ("Romy, une amie", "tu", "Bonjour Madame, pourriez-vous me prêter votre vélo ?"),
    ("Romy, une amie", "tu", "Tu peux me prêter ton vélo ce soir ?"),
    ("Margaux, la barmaid", "vous", "Un café."),
    ("Margaux, la barmaid", "vous", "Bonjour, un café s'il vous plaît, et l'addition quand vous pourrez."),
]

RADIO_LINES = [
    ("augustin", "Ma foi — on dirait une scène tragique. Je peux aider."),
    ("lila", "Le plombier ne vient pas sans les vingt euros. Tu fais quoi ?"),
    ("narrator", "Augustin sort quelques billets et tend la main, déjà en train d'imaginer la suite."),
]

LANDLORD_LETTER = """
Monsieur, Madame,

Suite à votre signalement du 3 septembre concernant le chauffage de votre
appartement, un technicien de la société Berthier passera le mardi 16 septembre
entre 8 h et 12 h. Merci de confirmer votre présence avant le 12 septembre.
En cas d'absence, une nouvelle intervention vous sera facturée 65 €.

Veuillez agréer, Monsieur, Madame, mes salutations distinguées.
M. Marchand, gérant
"""

CAFE_MENU = """Café des Trois Ponts — Formule du midi
Entrée du jour : velouté de potiron
Plat : gratin de courgettes ou saucisse de Toulouse, purée
Dessert : tarte aux noix
Formule complète 14,50 €. Plat seul 11 €.
Service de 12 h à 14 h 30. Pas de réservation le samedi."""


def _menu_png() -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 520), (248, 243, 232))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    y = 40
    for line in CAFE_MENU.splitlines():
        draw.text((40, y), line, fill=(20, 17, 13), font=font)
        y += 60
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _make_user(db, *, native: str, declared: str):
    from app.db.models.user import User

    user = User(
        id=uuid4(),
        email=f"calib-{uuid4().hex[:8]}@calibration.local",
        hashed_password="x",  # noqa: S106 - a throwaway calibration account, never a login
        native_language=native,
        target_language="fr",
        proficiency_level=declared,
        cefr_estimate=declared if "." in declared else f"{declared}.1",
        daily_goal_minutes=20,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def run_placement(db, budget: Budget) -> dict:
    from app.services.placement import PlacementService

    out = {}
    for persona, answers in PERSONAS.items():
        budget.check(f"placement {persona}")
        user = _make_user(db, native="en", declared="A1")
        service = PlacementService(db)
        session = service.start(user)
        turns = 0
        while session.status == "in_progress" and turns < 8:
            prompt = service.current_prompt(session)
            answer = answers.get(prompt.band) or answers["B2.1"]
            before = budget.calls
            budget.check(f"placement {persona} turn {turns}")
            t0 = time.perf_counter()
            session = service.respond(session, answer=answer, turn_index=turns)
            elapsed = time.perf_counter() - t0
            last = (session.turns or [])[-1] if session.turns else {}
            grading = last.get("grading") or {}
            budget.charge(grading.get("cost_usd") or grading.get("cost") or 0.0)
            out.setdefault(persona, {"turns": []})["turns"].append(
                {
                    "band": last.get("band"),
                    "score_0_4": grading.get("score_0_4"),
                    "grader_band": grading.get("band") or grading.get("estimated_band"),
                    "seconds": round(elapsed, 1),
                    "graded": bool(grading),
                    "calls": budget.calls - before,
                }
            )
            turns += 1
        if session.status == "in_progress":
            session = service.finish_now(session)
        out[persona].update(
            {
                "status": session.status,
                "estimate_level": session.estimate_level,
                "confidence": round(float(session.confidence or 0.0), 2),
                "estimate": session.estimate,
            }
        )
    return out


def run_register(db, budget: Budget) -> dict:
    from app.services.pragmatics import assess_register, model_register_gap

    rows = []
    for counterpart, expected, text in REGISTER_TURNS:
        det = assess_register(text, expected_register=expected, level_band="A2")
        row = {
            "counterpart": counterpart,
            "expected": expected,
            "text": text,
            "deterministic": str(getattr(det, "verdict", det)),
        }
        if str(getattr(det, "verdict", "")).lower().endswith("not_evaluated"):
            budget.check("register model")
            res = model_register_gap(
                db,
                user_id=None,
                scenario_key="calibration",
                learner_text=text,
                counterpart=counterpart,
                expected_register=expected,
            )
            budget.charge(0.0)
            row["model"] = str(getattr(res, "verdict", res))
        rows.append(row)
    return {"turns": rows}


def run_radio(budget: Budget, out_dir: Path) -> dict:
    from app.config import settings
    from app.services.episode_audio import NARRATOR_VOICE, voice_for_character
    from app.services.llm_service import LLMService

    llm = LLMService()
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    model = settings.FEUILLETON_AUDIO_TTS_MODEL
    for who, text in RADIO_LINES:
        budget.check(f"radio {who}")
        voice = NARRATOR_VOICE if who == "narrator" else voice_for_character(who)
        t0 = time.perf_counter()
        audio = llm.text_to_speech(text, voice=voice, model=model)
        elapsed = time.perf_counter() - t0
        # OpenAI TTS is priced per character; tts-1-hd US$30 / 1M chars.
        rate = 30.0 if "hd" in model else 15.0
        cost = len(text) * rate / 1_000_000
        budget.charge(cost)
        path = out_dir / f"{who}.mp3"
        path.write_bytes(audio)
        rows.append({"who": who, "voice": voice, "model": model, "bytes": len(audio), "seconds": round(elapsed, 1), "file": str(path.relative_to(ROOT)), "cost_usd": round(cost, 5)})
    return {"lines": rows, "listen": "open the mp3s and judge intelligibility at A1 speed — nothing automated can"}


def run_intake(db, budget: Budget) -> dict:
    from app.services.intake import IntakeService, public_view

    user = _make_user(db, native="de", declared="A2")
    service = IntakeService(db)
    out = {}
    budget.check("intake text")
    t0 = time.perf_counter()
    letter = service.submit_text(user, text=LANDLORD_LETTER)
    budget.charge(float(getattr(letter, "cost_usd", 0.0) or 0.0))
    out["letter"] = {"seconds": round(time.perf_counter() - t0, 1), "view": public_view(letter)}
    budget.check("intake image")
    t0 = time.perf_counter()
    menu = service.submit_image(user, data=_menu_png(), content_type="image/png")
    budget.charge(float(getattr(menu, "cost_usd", 0.0) or 0.0))
    out["menu_png"] = {"seconds": round(time.perf_counter() - t0, 1), "view": public_view(menu)}
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="Actually call the providers.")
    parser.add_argument("--max-calls", type=int, default=40)
    parser.add_argument("--max-cost-usd", type=float, default=1.0)
    parser.add_argument("--only", nargs="*", choices=("placement", "register", "radio", "intake"), default=None)
    parser.add_argument("--output", type=Path, default=OUT_DIR / f"calibration-{datetime.now(UTC):%Y-%m-%d}.json")
    args = parser.parse_args()

    if not args.live:
        print("dry run: nothing called. Pass --live with DATABASE_URL pointing at a throwaway database.")
        return 0
    url = os.environ.get("DATABASE_URL", "")
    if not url or "language_learning" in url:
        print("refusing: DATABASE_URL must name a throwaway database, never language_learning", file=sys.stderr)
        return 2

    from app.db.session import SessionLocal

    budget = Budget(args.max_calls, args.max_cost_usd)
    report: dict = {"ran_at": datetime.now(UTC).isoformat(), "caps": {"calls": args.max_calls, "cost_usd": args.max_cost_usd}, "sections": {}}
    wanted = set(args.only or ("placement", "register", "radio", "intake"))
    db = SessionLocal()
    try:
        for name, fn in (
            ("placement", lambda: run_placement(db, budget)),
            ("register", lambda: run_register(db, budget)),
            ("radio", lambda: run_radio(budget, args.output.with_suffix("") / "audio")),
            ("intake", lambda: run_intake(db, budget)),
        ):
            if name not in wanted:
                continue
            try:
                report["sections"][name] = fn()
            except Exception as exc:  # noqa: BLE001 - a calibration run reports, it does not crash
                report["sections"][name] = {"error": f"{exc.__class__.__name__}: {exc}"}
            report["budget"] = {"calls": budget.calls, "cost_usd_known": round(budget.cost, 4)}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(f"{name}: done · calls so far {budget.calls} · known cost US${budget.cost:.4f}", file=sys.stderr)
    finally:
        db.close()
    print(json.dumps(report["budget"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
