"""WP-167: the paid read of news days (owner-approved, capped). Never part of the suite.

For each band in ``WP167_BANDS`` a learner is put on a gap day of season 1 with a news
day due, and the real director writes it from today's real headlines (the real pick,
the real critic); then the day's own plate is painted. Everything lands in
``WP167_OUT``: the day as text, the headline and the picker's notes, the plate.

    WP167_OUT=docs/implementation/atelier-v2/evidence/wp167-news-day \
    SEASON_REPORT_LIVE=1 SEASON_REPORT_MAX_USD=0.9 WP167_BANDS=A2.1:4,B1.1:12,C1.1:20 \
    python -m pytest tests/test_wp167_live_news_day.py -q -s -p no:randomly
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.user import User
from app.services import living_story as engine
from app.services import news_day
from app.services.journey_contracts import ContentUnavailable, InputMode
from app.services.revue import plates as revue_plates
from app.services.season import plates
from app.services.season.admin import jump_to_day
from tests import test_season_one as season_suite

assembled_client = season_suite.assembled_client
clock = season_suite.clock
journey_enabled = season_suite.journey_enabled
season_on = season_suite.season_on
support = season_suite.support


def _page_md(band: str, day: int, draft: dict, marker: dict, pick: dict, refusals: list[dict]) -> str:
    news = marker.get("news") or {}
    lines = [
        f"# {band} · season day {day} · «{draft.get('title_fr')}»",
        "",
        f"**Headline** — {news.get('title')} ({news.get('source')}, {news.get('published_on')})  ",
        f"{news.get('url')}",
        "",
        f"**Picked by** {pick.get('picked_by')} out of {news.get('offered')} — mechanic: «{pick.get('mechanic_fr')}» — why: {pick.get('why')}",
        "",
        f"**Director's notes** — mechanic: «{news.get('mechanic_fr')}»; enters by: «{news.get('entry_fr')}»",
        "",
        f"**Credit** — {news.get('credit_fr')}",
        "",
        f"**Premise** — {draft.get('premise_fr')}",
        "",
        f"**Objective** ({draft.get('character_id')} @ {draft.get('location_id')}) — {draft.get('objective_native')}",
        "",
    ]
    for index, panel in enumerate(draft.get("panels") or [], start=1):
        lines.append(f"**Panel {index}.** {panel.get('narration_fr') or ''}".rstrip())
        for line in panel.get("dialogue") or []:
            lines.append(f"- *{line.get('character_id')}* — «{line.get('text_fr')}»")
        lines.append("")
    lines += [
        f"**Opening line** — «{draft.get('opening_line_fr')}»",
        "",
        f"**Hook** — {((draft.get('season_checklist') or {}).get('hook_fr'))}",
        "",
        f"**Plate brief** — {(news.get('plate') or {}).get('brief')}",
        "",
    ]
    if refusals:
        lines += ["**Refused drafts on the way**", ""]
        lines += [f"- {row.get('reason')}: {str(row.get('hint') or '')[:240]}" for row in refusals]
        lines.append("")
    return "\n".join(lines)


@pytest.mark.skipif(not os.environ.get("WP167_OUT"), reason="paid read; set WP167_OUT=<dir> with the owner's approval")
def test_wp167_live_news_days(assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch):
    out = Path(os.environ["WP167_OUT"])
    out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SEASON_REPORT_SPEND", str(out / "spend.json"))
    # Without SEASON_REPORT_LIVE: a free plumbing run (real headlines, fake director, no plate).
    live_run = bool(os.environ.get("SEASON_REPORT_LIVE"))
    spend = season_suite._live_model(monkeypatch) if live_run else {"usd": 0.0, "calls": 0}
    season_on.spoil_once = False
    season_on.critic_refusals_left = 0
    monkeypatch.setattr(settings, "ATELIER_NEWS_DAY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_NEWS_DAY_EVERY", 2)
    monkeypatch.setattr(settings, "ATELIER_SEASON_PLATES_ENABLED", True)
    from app.db.models.revue_place import RevuePlace

    # The suite's schema lists its tables; the plate store's is not among them.
    RevuePlace.__table__.create(bind=db_session.get_bind(), checkfirst=True)
    headlines = news_day.fetch_headlines(refresh=True)
    (out / "headlines.json").write_text(json.dumps(headlines, ensure_ascii=False, indent=1), encoding="utf-8")
    assert headlines, "no fresh headline could be read"
    picks: list[dict] = []
    real_pick = news_day.pick

    def recorded_pick(*args, **kwargs):
        chosen, notes = real_pick(*args, **kwargs)
        picks.append(notes)
        return chosen, notes

    monkeypatch.setattr(news_day, "pick", recorded_pick)
    refusals: list[dict] = []
    monkeypatch.setattr(engine, "REFUSAL_OBSERVERS", [refusals.append])
    stored: list[bytes] = []
    real_store = revue_plates._store  # noqa: SLF001

    def keep(place_id, content):
        stored.append(content)
        return real_store(place_id, content)

    monkeypatch.setattr(revue_plates, "_store", keep)
    plates_painted = 0
    summary = []
    for spec in os.environ.get("WP167_BANDS", "A2.1:4,B1.1:12,C1.1:20").split(","):
        band, day = spec.split(":")
        email = f"wp167-{band.lower()}-{uuid.uuid4()}@example.com"
        support.register(assembled_client, email, cefr=band)
        user = db_session.scalar(select(User).where(User.email == email))
        jump_to_day(db_session, user, day=int(day))
        # WP167_FREE_DAY=1: move on to the first gap day without a scheduled moment (the
        # A2 reads of g1 had «La même chose ?» scheduled, and the director dropped the news).
        # A jump into a gap's middle leaves its moments owed, so only a gap's first day is tried.
        if os.environ.get("WP167_FREE_DAY"):
            from app.services.season.clock import nominal_calendar
            from app.services.season.format import load_season

            firsts = [row["season_day"] for row in nominal_calendar(load_season("s1")) if row["kind"] == "gap" and row["day_in_segment"] == 1]
            for first in [d for d in firsts if d >= int(day)]:
                jump_to_day(db_session, user, day=first)
                day = str(first)
                brief = ((engine.story_context(db_session, user).get("season_script") or {}).get("brief")) or {}
                if brief and not (brief.get("today") or {}).get("required_premise"):
                    break
        thread = season_suite._thread(db_session, user.id)
        state = dict(thread.state or {})
        live = dict(state.get(engine.STATE_KEY) or {})
        live[news_day.LEDGER_KEY] = {"generated": 1, "since_news": 1}
        state[engine.STATE_KEY] = live
        thread.state = state
        db_session.commit()
        refusals.clear()
        before = len(picks)
        result = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
        db_session.commit()
        if isinstance(result, ContentUnavailable):
            summary.append({"band": band, "day": int(day), "lost": result.reason, "refusals": list(refusals)})
            continue
        marker = result.story_context.get(news_day.BRIEF_KEY) or {}
        draft = result.story_context.get("draft") or {}
        pick = picks[-1] if len(picks) > before else {}
        tag = band.replace(".", "") + f"-d{int(day)}"
        (out / f"{tag}-day.json").write_text(
            json.dumps({"marker": marker, "pick": pick, "draft": draft, "refusals": refusals}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        (out / f"{tag}-day.md").write_text(_page_md(band, int(day), draft, marker, pick, refusals), encoding="utf-8")
        row = {"band": band, "day": int(day), "title": draft.get("title_fr"), "news": bool(marker.get("news")), "skipped": marker.get("skipped")}
        plate = (marker.get("news") or {}).get("plate") or {}
        if live_run and plate.get("key") and plate.get("brief"):
            stored.clear()
            url = plates.paint_plate(db_session, plate["key"], plate["brief"], name_fr=plate.get("name_fr"))
            plates_painted += 1
            if stored:
                (out / f"{tag}-plate.webp").write_bytes(stored[-1])
            row["plate_url"] = url
            (out / f"{tag}-plate-prompt.txt").write_text(plates.prompt_for(plate["brief"]), encoding="utf-8")
        summary.append(row)
    plate_usd = plates_painted * float(settings.ATELIER_PANEL_ART_COST_USD_PER_PANEL)
    (out / "summary.json").write_text(
        json.dumps(
            {"days": summary, "text_usd": round(spend["usd"], 4), "calls": spend["calls"], "plates": plates_painted,
             "plate_usd_estimated": round(plate_usd, 4), "total_usd": round(spend["usd"] + plate_usd, 4)},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    shutil.rmtree(out / "__pycache__", ignore_errors=True)
