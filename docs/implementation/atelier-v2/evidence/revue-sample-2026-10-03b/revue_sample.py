# ruff: noqa  -- an evidence script, kept as it ran
"""WP-119 §10e acceptance rerun («La voix de Romy»): the same ten Papier sessions and scripted learner as the
§10d sample of 2026-10-03, real provider + real critic, throwaway SQLite."""
from __future__ import annotations

import json, os, sys, time, uuid
from pathlib import Path

SCRATCH = Path(__file__).parent
DBFILE = SCRATCH / "revue_sample.sqlite3"
if DBFILE.exists():
    DBFILE.unlink()
# Throwaway DB: an env var outranks the .env file's DATABASE_URL (the owner's database is never opened).
os.environ["DATABASE_URL"] = f"sqlite:///{DBFILE}"
os.environ.setdefault("SECRET_KEY", "sample-secret")
REPO = Path("/Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning")
sys.path.insert(0, str(REPO))
os.chdir(REPO)
OUT = Path(os.environ.get("REVUE_SAMPLE_OUT") or REPO / "docs/implementation/atelier-v2/evidence/revue-sample-2026-10-03b")
(OUT / "sessions").mkdir(parents=True, exist_ok=True)
BUDGET = 3.0

from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker


@compiles(PG_UUID, "sqlite")
def _uuid(type_, compiler, **kw):
    return "CHAR(32)"


@compiles(JSONB, "sqlite")
def _jsonb(type_, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array(type_, compiler, **kw):
    return "JSON"


from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models.user import User
from app.db.models.revue_session import RevueSession
from app.services.revue import encounter as enc
from app.services.revue import grading
from app.services.revue.weekly import available_for_week
from app.services.revue.evergreen import load_evergreens
from app.services.revue.pictogram import FakePictogramProvider
from app.config import settings

assert str(settings.DATABASE_URL).startswith("sqlite"), "refusing to run against a non-throwaway DB"

engine = create_engine(f"sqlite:///{DBFILE}", connect_args={"check_same_thread": False})
skipped = []
for table in Base.metadata.sorted_tables:
    try:
        table.create(bind=engine, checkfirst=True)
    except Exception as exc:  # noqa: BLE001
        skipped.append((table.name, str(exc)[:120]))
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

WEEK = "2026-W40"
LIVE = {d.id: d for d in available_for_week(WEEK)}
EVER = {d.id: d for d in load_evergreens()}
ALL = {**LIVE, **EVER}


def kiosk(week, db=None):
    return list(LIVE.values()) + [EVER[i] for i in EVERGREEN_IDS]


EVERGREEN_IDS = ["evergreen-marche-du-dimanche", "evergreen-greve-transports",
                 "evergreen-beaujolais-nouveau", "evergreen-rentree"]
enc.available_dossiers = kiosk  # the six live dossiers plus the four evergreens, as one kiosk


class Recording(enc.OpenAIRevueProvider):
    calls: list

    def __init__(self):
        super().__init__(name="openai-revue")
        self.calls = []

    def ask_json(self, instructions, payload, *, system=enc._SYSTEM, temperature=0.4, label="task"):
        if system is grading._CRITIC_SYSTEM:
            label = "critic"
        before = self.thread_spent()  # per thread: reply, guest and critic may overlap (§10e.8)
        t0 = time.perf_counter()
        err = None
        out = None
        try:
            out = super().ask_json(instructions, payload, system=system, temperature=temperature, label=label)
            return out
        except Exception as exc:
            err = str(exc)[:300]
            raise
        finally:
            self.calls.append({"label": label, "seconds": round(time.perf_counter() - t0, 3),
                               "started": round(t0 - T0, 3), "cost_usd": round(self.thread_spent() - before, 6),
                               "error": err,
                               "payload": payload, "response": out})
            if GLOBAL["spent"] + self.spent_usd > BUDGET:
                raise SystemExit(f"budget passed: {GLOBAL['spent'] + self.spent_usd:.4f}")


GLOBAL = {"spent": 0.0}
T0 = time.perf_counter()

# (dossier, band, native, answerable question, unanswerable question, opinion lead, article error?, headline for B1)
PLAN = [
    ("2026-w40-budget-2027", "B1.1", "en", "Qu'est-ce que le budget change pour les retraités ?",
     "Est-ce que l'Assemblée nationale va modifier le texte ?", "À mon avis, c'est dur pour les retraités.", False,
     "Budget 2027 : les petites pensions protégées, les autres moins"),
    ("2026-w40-ce-qui-change-1er-octobre", "A2.1", "de", "Le gaz coûte combien maintenant ?",
     "Le prix du gaz va encore monter en novembre ?", "Je trouve ça cher.", True, None),
    ("2026-w40-goncourt-roman-retire", "B1.1", "de", "Pourquoi l'Académie a retiré le roman ?",
     "Est-ce que le Renaudot va aussi retirer le roman ?", "Je pense que l'auteur a le droit de se défendre.", False,
     "Le Goncourt écarte un roman soupçonné d'être écrit par une IA"),
    ("2026-w40-paris-plan-canicules", "A1.1", "en", "Il y a combien de voiles ?",
     "Le plan coûte combien ?", "C'est bien pour les enfants.", False, None),
    ("2026-w40-prix-de-l-arc-de-triomphe", "A2.1", "en", "La course est longue ?",
     "Qui va gagner ?", "J'aime les chevaux, c'est beau.", True, None),
    ("2026-w40-prix-produits-frais", "A1.1", "de", "Les fruits sont plus chers ?",
     "Quels légumes sont plus chers ?", "C'est difficile pour moi.", False, None),
    ("evergreen-marche-du-dimanche", "A2.1", "en", "Le marché d'Aligre est ouvert quand ?",
     "C'est moins cher qu'au supermarché ?", "J'adore les marchés, c'est vivant.", False, None),
    ("evergreen-greve-transports", "B1.1", "en", "Combien de jours avant faut-il déposer un préavis ?",
     "Quand est la prochaine grève, et quelles lignes seront touchées ?",
     "Personnellement, je comprends les grévistes, même si c'est pénible pour les voyageurs.", True,
     "Grève : cinq jours de préavis, mais pas de vrai service minimum"),
    ("evergreen-beaujolais-nouveau", "A1.1", "en", "C'est quel raisin ?",
     "La bouteille coûte combien en 2026 ?", "J'aime le vin rouge.", False, None),
    ("evergreen-rentree", "A2.1", "de", "L'allocation, c'est combien ?",
     "Combien coûte une rentrée pour une famille en 2026 ?", "Pour moi, l'école coûte trop cher.", False, None),
]

SWAP = {"le": "la", "la": "le"}


def target_sentence(vocab, wrong: bool):
    """A short use of the first le/la noun of the plan's vocabulary; ``wrong`` swaps the article."""
    for item in vocab:
        head, _, rest = item.fr.partition(" ")
        if head.lower() in SWAP and rest:
            art = SWAP[head.lower()] if wrong else head.lower()
            return f"Pour moi, {art} {rest}, c'est important.", item.fr, art
    for item in vocab:  # no le/la noun: use whatever comes first, correctly
        return f"Pour moi, {item.fr}, c'est important.", item.fr, None
    return "", None, None


def dump(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, (list, tuple)):
        return [dump(o) for o in obj]
    return obj


def timed(timings, name, fn, *a, **k):
    t0 = time.perf_counter()
    out = fn(*a, **k)
    timings.append({"step": name, "seconds": round(time.perf_counter() - t0, 3)})
    return out


def run(n, spec):
    did, level, native, q_ok, q_gap, opinion, wrong, headline = spec
    db = Session()
    user = User(id=uuid.uuid4(), email=f"sample-{n}-{uuid.uuid4().hex[:6]}@example.com", hashed_password="x",
                cefr_estimate=level, native_language=native, interests="")
    db.add(user)
    db.commit()
    provider = Recording()
    revue = enc.RevueEncounter(db, provider)
    revue.pictogram_provider = FakePictogramProvider()  # the stamp is out of §10d's scope
    timings = []
    record = {"n": n, "dossier_id": did, "level": level, "native_language": native,
              "dossier": ALL[did].model_dump(mode="json")}
    row = timed(timings, "start", revue.start, user, WEEK, dossier_id=did)
    loaded = enc.load(row)
    vocab = loaded.plan.vocabulary
    record["band"] = loaded.plan.learner.band
    record["vocabulary"] = [v.model_dump(mode="json") for v in vocab]
    sent, word, art = target_sentence(vocab, wrong)
    record["target_use"] = {"word": word, "article_said": art, "intended": "incorrect" if wrong else "correct",
                            "sentence": sent}
    lines = ["D'accord, je t'aide.", q_ok, q_gap, f"{opinion} {sent}".strip()]
    turns = []
    for i, text in enumerate(lines):
        res = timed(timings, f"turn{i+1}", revue.turn, row, text)
        turns.append({"learner": text, "result": dump(res)})
    record["turns"] = turns
    offer = timed(timings, "make_options", revue.make_options, row)
    record["make_offer"] = dump(offer)
    rec = offer.recommended
    if rec == "reader_question":
        prop = timed(timings, "make_propose", revue.make, row, "reader_question", {"action": "propose"})
        sendres = timed(timings, "make_send", revue.make, row, "reader_question",
                        {"action": "send", "text_fr": prop.draft.proposal_fr})
        record["make"] = {"option": rec, "propose": dump(prop), "send": dump(sendres)}
    elif rec == "headline_write":
        res = timed(timings, "make_write", revue.make, row, "headline_write",
                    {"action": "write", "text_fr": headline or ALL[did].title_fr})
        record["make"] = {"option": rec, "write": dump(res)}
    elif rec == "headline_choice":
        ex = enc._choices(enc.load(row).state, "headline_exercise")[-1].payload["exercise"]
        res = timed(timings, "make_pick", revue.make, row, "headline_choice",
                    {"action": "pick", "option_id": ex["answer"]})
        record["make"] = {"option": rec, "pick": dump(res)}
    else:
        record["make"] = {"option": rec, "skipped": True}
    view, closing = timed(timings, "close", revue.close, row)
    record["closing"] = dump(closing)
    db.refresh(row)
    final = enc.load(row)
    record["thread"] = dump(enc.session_view(final).thread)
    record["events"] = [{"seq": e.seq, "kind": e.kind, "payload": e.payload} for e in final.state.events]
    record["evidence"] = [e.payload for e in final.state.events if e.kind == "evidence"]
    record["guest"] = [{"kind": e.kind, **e.payload} for e in final.state.events
                       if e.kind in ("guest_enter", "turn_guest", "guest_position")]
    record["cost_usd_state"] = final.state.cost_usd
    record["cost_usd_provider"] = round(provider.spent_usd, 6)
    record["calls"] = provider.calls
    record["timings"] = timings
    record["prompt_versions"] = {"rubric": grading.RUBRIC_ID, "provider": provider.name,
                                 "model": settings.OPENAI_MODEL, **enc.PROMPT_VERSIONS}
    GLOBAL["spent"] += provider.spent_usd
    db.close()
    (OUT / "sessions" / f"{n:02d}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str))
    print(f"[{n}] {did} {level} cost={provider.spent_usd:.4f} state={final.state.cost_usd} calls={len(provider.calls)} "
          f"make={rec} total={GLOBAL['spent']:.4f}", flush=True)


if __name__ == "__main__":
    only = [int(a) for a in sys.argv[1:]] or list(range(1, 11))
    print("skipped tables:", [s[0] for s in skipped])
    for n in only:
        try:
            run(n, PLAN[n - 1])
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            print(f"[{n}] FAILED: {exc}")
    print(f"TOTAL ${GLOBAL['spent']:.4f}")
