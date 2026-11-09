#!/usr/bin/env python
"""Play one learner over the season-end walk's real API (``season_end_walk_server.py``).

A person writes the answers: this only opens the day, prints what the learner would
read and sends what it is told to say. One JSON state file per persona.

    season_end_play.py --api URL --state a1.json new --email ... --native de --cefr A1.1
    season_end_play.py --api URL --state a1.json jump 58 --flag s1.ending=garder
    season_end_play.py --api URL --state a1.json open [--prefetch]    # the day, as text
    season_end_play.py --api URL --state a1.json say "Bonjour Margaux."
    season_end_play.py --api URL --state a1.json next                 # scene, rule, ending…
    season_end_play.py --api URL --state a1.json drills               # recall steps, right
    season_end_play.py --api URL --state a1.json finish
    season_end_play.py --api URL --state a1.json clock 1
    season_end_play.py --api URL --state a1.json live

``say`` measures: the POST's own time, then how long ``story_pending`` lasts while it
polls once a second as the app does, and the slowest poll. Every printed day also goes
to ``<state>.transcript.md``. Recall answers come from the database (a throwaway one),
as in ``tests/test_journey_end_to_end.py``. Nothing here can spend except through the
server, whose cap is hard.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

TZ = "Europe/Paris"


def mutation() -> str:
    return uuid.uuid4().hex


class Player:
    def __init__(self, api: str, state_path: Path) -> None:
        self.api = api.rstrip("/")
        self.state_path = state_path
        self.state: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        self.http = httpx.Client(base_url=self.api, timeout=400)
        self.journey: dict[str, Any] = {}
        self.last_body: dict[str, Any] | None = None

    def save(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=1, ensure_ascii=False), encoding="utf-8")

    def emit(self, text: str = "") -> None:
        print(text)
        with self.state_path.with_suffix(".transcript.md").open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")

    @property
    def headers(self) -> dict[str, str]:
        token = self.http.post("/__walk/token", json={"email": self.state["email"]}).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def load(self) -> None:
        response = self.http.get(f"/api/v1/daily-journeys/{self.state['journey_id']}", headers=self.headers)
        response.raise_for_status()
        self.journey = response.json()

    def current(self) -> dict[str, Any] | None:
        step_id = self.journey.get("current_step_id")
        return next((row for row in self.journey.get("steps") or [] if row["id"] == step_id), None)

    # --- what the learner reads ------------------------------------------------

    def print_page(self) -> None:
        journey = self.journey
        scenario = journey.get("scenario") or {}
        self.emit(f"\n## {journey.get('local_date')} · {scenario.get('title_fr') or scenario.get('title')}")
        self.emit(f"steps: {' '.join(row['kind'] for row in journey.get('steps') or [])} · status {journey.get('status')}")
        for row in journey.get("steps") or []:
            prompt = row.get("prompt") or {}
            if row["kind"] == "scene":
                stage = prompt.get("stage") or {}
                season = prompt.get("season_part") or {}
                self.emit(f"season_part: {season} · stage: {stage.get('key')} {stage.get('title_fr') or ''} {stage.get('story_date_fr') or ''} band {stage.get('band')}")
                for key in ("setup_fr", "setup_native", "premise_fr", "premise_native", "objective_native", "previously_fr", "reread_native", "character_line_fr"):
                    if prompt.get(key):
                        self.emit(f"{key}: {prompt[key]}")
                for extra in ("season_premiere", "interlude", "greeting", "meanwhile", "season_interlude", "absence"):
                    if prompt.get(extra):
                        self.emit(f"{extra}: {json.dumps(prompt[extra], ensure_ascii=False)}")
                if stage.get("movements"):
                    for line in render_movements(stage["movements"]):
                        self.emit(line)
                for panel in prompt.get("panels") or []:
                    self.emit(f"  [panel] {str(panel.get('caption_fr') or panel.get('narration_fr') or panel.get('visual') or '')[:220]}")
                    for line in panel.get("lines") or panel.get("dialogue") or []:
                        self.emit(line_of(line) if isinstance(line, dict) else f"- {line}")
            elif row["kind"] == "respond":
                self.emit(f"\n[respond] {json.dumps({k: v for k, v in prompt.items() if k in ('task_native', 'objective_native', 'instruction_native', 'examples', 'choices', 'character_line_fr', 'min_turns', 'max_turns', 'hint_native')}, ensure_ascii=False)[:900]}")
            elif row["kind"] == "rule":
                self.emit(f"\n[rule] {json.dumps(prompt, ensure_ascii=False)[:500]}")
            elif row["kind"] == "resolution":
                self.emit(f"\n[resolution] {json.dumps({k: v for k, v in prompt.items() if k in ('character_line_fr', 'summary_native', 'outcome_key', 'story_pending', 'teaser_fr', 'next_teaser_fr', 'hook_fr')}, ensure_ascii=False)[:700]}")

    def print_story(self) -> None:
        """The reader's own page (``/story-engine/episodes``), the newest one."""

        response = self.http.get("/api/v1/story-engine/episodes", headers=self.headers)
        if response.status_code != 200:
            self.emit(f"(no episode list: {response.status_code})")
            return
        items = response.json().get("items") or response.json().get("episodes") or []
        self.emit(f"(episodes: {len(items)})")
        if items:
            self.emit(json.dumps(items[0], ensure_ascii=False)[:6000])

    # --- commands --------------------------------------------------------------

    def cmd_new(self, args) -> None:
        self.state.update({"email": args.email, "native": args.native, "cefr": args.cefr})
        self.save()
        print(self.http.post("/__walk/level", json={"email": args.email, "cefr": args.cefr}).json())

    def cmd_jump(self, args) -> None:
        flags = {}
        for raw in args.flag or []:
            key, _, value = raw.partition("=")
            lowered = value.casefold()
            flags[key] = True if lowered == "true" else False if lowered == "false" else value
        print(json.dumps(self.http.post("/__walk/jump", json={"email": self.state["email"], "day": args.day, "flags": flags}).json(), ensure_ascii=False)[:1200])

    def cmd_open(self, args) -> None:
        if args.prefetch:
            answer = self.http.post("/__walk/prefetch", json={"email": self.state["email"]})
            self.emit(f"(night: prefetch {answer.status_code} {answer.text[:300]})")
        started = time.monotonic()
        response = self.http.post(
            "/api/v1/daily-journeys",
            headers=self.headers,
            json={"mutation_id": mutation(), "timezone": TZ, "budget_seconds": 300, "preferred_input_mode": "text"},
        )
        seconds = time.monotonic() - started
        if response.status_code >= 300:
            self.emit(f"(open failed {response.status_code}: {response.text[:400]})")
            return
        self.journey = response.json()
        self.state["journey_id"] = self.journey["id"]
        self.save()
        self.emit(f"\n(open: {seconds:.1f} s)")
        self.print_page()

    def cmd_show(self, args) -> None:
        self.load()
        self.print_page()

    def cmd_step(self, args) -> None:
        self.load()
        print(json.dumps(self.current(), ensure_ascii=False, indent=1)[:args.limit])

    def cmd_next(self, args) -> None:
        self.load()
        for _ in range(args.count):
            step = self.current()
            if step is None:
                print("(no current step)")
                return
            response = self.http.post(
                f"/api/v1/daily-journeys/{self.journey['id']}/advance",
                headers=self.headers,
                json={"mutation_id": mutation(), "expected_revision": self.journey["revision"], "current_step_id": step["id"]},
            )
            if response.status_code != 200:
                print(f"(advance {response.status_code}: {response.text[:300]})")
                return
            self.journey = response.json()
        step = self.current()
        print(f"(current: {step['kind'] if step else None})")

    def cmd_say(self, args) -> None:
        self.load()
        step = self.current()
        while step is not None and step["kind"] in ("scene",):
            # The learner has read the page: «Continuer» leads to the answer box.
            self.cmd_next(argparse.Namespace(count=1))
            step = self.current()
        if step is None:
            print("(no current step)")
            return
        if args.card is not None:
            payload = {"mode": "text", "text": args.text, "choice_id": args.card}
        else:
            payload = {"mode": "text", "text": args.text}
        self.emit(f"\n**Moi** : {args.text}")
        self.last_body = None
        started = time.monotonic()
        response = self.http.post(
            f"/api/v1/daily-journeys/{self.journey['id']}/steps/{step['id']}/attempts",
            headers=self.headers,
            json={"mutation_id": mutation(), "expected_revision": self.journey["revision"], "input": payload},
        )
        post_seconds = time.monotonic() - started
        if response.status_code != 200:
            self.emit(f"(attempt {response.status_code}: {response.text[:500]})")
            return
        body = response.json()
        self.last_body = body
        self.journey = body["journey"]
        self.emit(f"(reply in {post_seconds:.1f} s · {body.get('task_outcome')} · source {body.get('reply_source')})")
        with self.state_path.with_suffix(".raw.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({key: value for key, value in body.items() if key != "journey"}, ensure_ascii=False) + "\n")
        correction = body.get("correction") or {}
        if correction:
            self.emit(f"  correction [{correction.get('kind')}]: «{correction.get('span_fr')}» → «{correction.get('corrected_fr')}» · {correction.get('note_native')}")
        for row in body.get("character_lines") or []:
            self.emit(f"- {row.get('speaker_name')}: {row.get('text_fr')}")
        if not body.get("character_lines"):
            self.emit(f"- (reply): {body.get('character_reply_fr')}")
        next_prompt = (body.get("next_turn") or {}).get("prompt") or {}
        if next_prompt:
            self.emit(f"> next: {next_prompt.get('objective_native')} (turn {next_prompt.get('turn_index')}/{next_prompt.get('max_turns')})")
        self.wait_for_ending(post_seconds)
        self.print_ending()

    def wait_for_ending(self, post_seconds: float = 0.0) -> None:
        pending = [row for row in self.journey.get("steps") or [] if row["kind"] == "resolution" and (row.get("prompt") or {}).get("story_pending")]
        if not pending:
            return
        started = time.monotonic()
        polls: list[float] = []
        while time.monotonic() - started < 400:
            time.sleep(1.0)
            before = time.monotonic()
            response = self.http.get(f"/api/v1/daily-journeys/{self.journey['id']}", headers=self.headers)
            polls.append(time.monotonic() - before)
            if response.status_code != 200:
                self.emit(f"(poll {response.status_code})")
                continue
            self.journey = response.json()
            if not any(
                row["kind"] == "resolution" and (row.get("prompt") or {}).get("story_pending")
                for row in self.journey.get("steps") or []
            ):
                break
        waited = time.monotonic() - started
        self.emit(
            f"(ending ready after {waited:.1f} s of story_pending · {len(polls)} polls · slowest poll "
            f"{max(polls or [0]):.1f} s · total from my answer {waited + post_seconds:.1f} s)"
        )

    def print_ending(self) -> None:
        """The day's written ending, once: what «Weiter» opens after the last answer."""

        rows = [row for row in self.journey.get("steps") or [] if row["kind"] == "resolution"]
        for row in rows:
            prompt = row.get("prompt") or {}
            if prompt.get("story_pending") or row["id"] in self.state.setdefault("endings_shown", []):
                continue
            pages = prompt.get("panels") or prompt.get("resolution_panels") or []
            line = prompt.get("character_line_fr") or ""
            summary = prompt.get("summary_native") or ""
            if not (pages or line or summary):
                continue
            self.state["endings_shown"].append(row["id"])
            self.save()
            self.emit(f"\n[ending] outcome {prompt.get('outcome_key')} · {prompt.get('title_fr') or ''}")
            for key in ("summary_native", "character_line_fr", "teaser_fr", "next_teaser_fr", "hook_fr", "feedback_native", "reason_native"):
                if prompt.get(key):
                    self.emit(f"{key}: {prompt[key]}")
            for panel in pages:
                if not isinstance(panel, dict):
                    continue
                visual = panel.get("caption_fr") or panel.get("narration_fr") or panel.get("visual") or ""
                if visual:
                    self.emit(f"  ({str(visual)[:300]})")
                for spoken in panel.get("lines") or panel.get("dialogue") or []:
                    if isinstance(spoken, dict):
                        self.emit(line_of(spoken))

    def cmd_drills(self, args) -> None:
        """Advance through the day, answering recall steps from the stored key."""

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from sqlalchemy import select

        from app.db.models.daily_journey import DailyJourneyStep
        from app.db.session import SessionLocal

        self.load()
        for _ in range(60):
            step = self.current()
            if step is None:
                print("(day has no current step)")
                return
            kind = step["kind"]
            if kind == "respond" or (kind == "scene" and getattr(args, "to_scene", False)):
                print(f"(stopped at {kind})")
                return
            if kind != "recall":
                self.cmd_next(argparse.Namespace(count=1))
                self.load()
                continue
            with SessionLocal() as db:
                row = db.scalar(select(DailyJourneyStep).where(DailyJourneyStep.id == uuid.UUID(step["id"])))
                private = dict(row.private_task or {})
            payload = recall_payload(step, private)
            response = self.http.post(
                f"/api/v1/daily-journeys/{self.journey['id']}/steps/{step['id']}/attempts",
                headers=self.headers,
                json={"mutation_id": mutation(), "expected_revision": self.journey["revision"], "input": payload},
            )
            if response.status_code != 200:
                print(f"(recall {response.status_code}: {response.text[:300]}) {json.dumps(step.get('prompt'), ensure_ascii=False)[:400]}")
                return
            self.journey = response.json()["journey"]
            if self.journey.get("current_step_id") == step["id"]:
                self.cmd_next(argparse.Namespace(count=1))
                self.load()

    def cmd_fastday(self, args) -> None:
        """The whole day on one line of learner, for fake rehearsals and for days nobody reads."""

        self.cmd_open(argparse.Namespace(prefetch=args.prefetch))
        if not self.journey:
            return
        for _ in range(80):
            self.load()
            step = self.current()
            if step is None:
                break
            if step["kind"] == "respond":
                self.cmd_say(argparse.Namespace(text=args.answer, card=None))
                if self.last_body is None:
                    print("(the answer was refused: stopping this day)")
                    return
                if not self.last_body.get("next_turn") and self.journey.get("current_step_id") == step["id"]:
                    self.cmd_next(argparse.Namespace(count=1))
                continue
            if step["kind"] == "recall":
                self.cmd_drills(argparse.Namespace())
                continue
            self.cmd_next(argparse.Namespace(count=1))
        self.cmd_finish(argparse.Namespace(kind="complete"))
        self.cmd_clock(argparse.Namespace(days=1, absolute=None))
        body = self.http.get("/__walk/live", params={"email": self.state["email"]}).json()
        chapter = body.get("chapter") or {}
        print(
            f"=> season {body.get('season_index')} stage {body.get('season_stage')} shape {chapter.get('shape')} "
            f"interlude-ch {chapter.get('interlude')} interlude {(body.get('interlude') or {}).get('returns_on')} "
            f"premiere {(body.get('season_premiere') or {}).get('title_fr')}"
        )

    def cmd_finish(self, args) -> None:
        self.load()
        response = self.http.post(
            f"/api/v1/daily-journeys/{self.state['journey_id']}/finish",
            headers=self.headers,
            json={"mutation_id": mutation(), "expected_revision": self.journey["revision"], "finish_kind": args.kind},
        )
        print(response.status_code, response.text[:300] if response.status_code != 200 else "(finished)")

    def cmd_clock(self, args) -> None:
        # One clock per server, shared by every learner on it.
        shared = self.state_path.parent / "clock_offset"
        current = int(shared.read_text()) if shared.is_file() else 0
        offset = args.absolute if args.absolute is not None else current + args.days
        response = self.http.post("/api/v1/dev/test-clock", json={"offset_days": offset})
        shared.write_text(str(offset))
        print(response.status_code, response.text[:200])

    def cmd_live(self, args) -> None:
        body = self.http.get("/__walk/live", params={"email": self.state["email"]}).json()
        print(json.dumps(body, ensure_ascii=False, indent=args.indent)[:args.limit])

    def cmd_today(self, args) -> None:
        response = self.http.get("/api/v1/daily-journeys/today", headers=self.headers, params={"timezone": TZ})
        print(response.status_code, json.dumps(response.json(), ensure_ascii=False, indent=0)[:args.limit])

    def cmd_spend(self, args) -> None:
        print(json.dumps(self.http.get("/__walk/spend").json(), indent=0))

    def cmd_control(self, args) -> None:
        print(self.http.post("/__walk/control", json=json.loads(args.values)).json())

    def cmd_episodes(self, args) -> None:
        self.print_story()


def recall_payload(step: dict, private: dict) -> dict:
    """The right answer for each recall format, from the stored key (the suite's Driver)."""

    task = dict(private.get("recall_task") or {})
    kind = task.get("task_type")
    if kind in {"match_pairs", "tiles", "word_bank", "unscramble"}:
        return {"mode": "tiles", "tile_ids": list(task.get("correct_tile_order") or [])}
    if kind in {"choice", "classify", "listen_tap"}:
        return {"mode": "choice", "option_id": task.get("correct_option_id")}
    accepted = list(task.get("accepted_answers") or [])
    return {"mode": "text", "text": accepted[0] if accepted else "Je ne sais pas."}


def line_of(line: dict) -> str:
    who = line.get("name") or line.get("who") or ""
    kind = line.get("kind")
    native = f"  [{line.get('text_native')}]" if line.get("text_native") else ""
    label = f"{who}" + (f" ({kind})" if kind and kind != "speech" else "")
    return f"- {label}: {line.get('text_fr')}{native}"


def render_movements(movements: list[dict]) -> list[str]:
    out: list[str] = []
    for row in movements or []:
        kind = row.get("kind")
        if kind == "turn":
            panel = row.get("panel") or {}
            if panel:
                out.extend(render_movements([panel]))
            out.append(f"> TURN to {row.get('to_name') or row.get('to')}: {row.get('task_native')}" + (" (choice)" if row.get("choice") else ""))
            for option in row.get("choices") or []:
                out.append(f"    · {option.get('text_fr') or option}")
        elif kind == "hook":
            out.append(f"HOOK: {json.dumps({k: v for k, v in row.items() if k not in ('kind', 'id')}, ensure_ascii=False)[:500]}")
        else:
            visual = str(row.get("visual") or "")
            if visual:
                out.append(f"  ({visual[:170]})")
            for line in row.get("lines") or []:
                out.append(line_of(line))
            for line in row.get("diegetic") or []:
                out.append(f"  «{line}»")
            if kind not in (None, "panel"):
                out.append(f"[{kind}] {json.dumps({k: v for k, v in row.items() if k not in ('kind', 'id', 'lines', 'visual')}, ensure_ascii=False)[:300]}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default=os.environ.get("SEASON_END_API", ""))
    parser.add_argument("--state", default=os.environ.get("SEASON_END_STATE", ""))
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new")
    new.add_argument("--email", required=True)
    new.add_argument("--native", required=True)
    new.add_argument("--cefr", required=True)
    jump = sub.add_parser("jump")
    jump.add_argument("day", type=int)
    jump.add_argument("--flag", action="append")
    opened = sub.add_parser("open")
    opened.add_argument("--prefetch", action="store_true")
    sub.add_parser("show")
    step = sub.add_parser("step")
    step.add_argument("--limit", type=int, default=6000)
    advance = sub.add_parser("next")
    advance.add_argument("--count", type=int, default=1)
    say = sub.add_parser("say")
    say.add_argument("text")
    say.add_argument("--card")
    drills = sub.add_parser("drills")
    drills.add_argument("--to-scene", action="store_true")
    fast = sub.add_parser("fastday")
    fast.add_argument("--answer", default="Je ne sais pas.")
    fast.add_argument("--prefetch", action="store_true")
    finish = sub.add_parser("finish")
    finish.add_argument("--kind", default="complete")
    clock = sub.add_parser("clock")
    clock.add_argument("days", type=int, nargs="?", default=1)
    clock.add_argument("--absolute", type=int)
    live = sub.add_parser("live")
    live.add_argument("--limit", type=int, default=8000)
    live.add_argument("--indent", type=int, default=0)
    today = sub.add_parser("today")
    today.add_argument("--limit", type=int, default=4000)
    sub.add_parser("spend")
    control = sub.add_parser("control")
    control.add_argument("values")
    sub.add_parser("episodes")
    args = parser.parse_args()
    if not args.api or not args.state:
        sys.exit("--api and --state are required")
    player = Player(args.api, Path(args.state))
    getattr(player, f"cmd_{args.command}")(args)


if __name__ == "__main__":
    main()
