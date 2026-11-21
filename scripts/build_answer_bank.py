#!/usr/bin/env python3
"""Write the answer bank (#174): every answer a teacher accepts, and the wrong ones that stay wrong.

Offline, run by a person, never by CI. Four steps, each resumable from the work directory:

    python scripts/build_answer_bank.py export  --work W [--source repair_pairs ...]
    python scripts/build_answer_bank.py propose --work W [--pilot 2] [--wait]
    python scripts/build_answer_bank.py judge   --work W [--pilot 2] [--wait]
    python scripts/build_answer_bank.py write   --work W

``export`` lists the authored items (:func:`app.services.answer_bank.authored_items`).
``propose`` asks Claude Sonnet 5.5, a dozen items per request through the Message Batches
API, for every answer a French teacher accepts for each item's exact prompt and the common
wrong answers that must stay wrong, each with a one-line reason. ``judge`` asks a second,
independent call: the same model with another prompt sees the key, the proposed variants and
the proposed wrong answers shuffled and unlabelled, and marks each right or wrong. ``write``
keeps a variant only when both calls accept it, a wrong form only when both refuse it, and
records an item whose own key the judge refuses as ``key_rejected`` (a finding to read, the
key is never changed).

Spend is read from every response's ``usage`` and priced at the batch rate. Before each
submission the worst case (every request using its whole ``max_tokens``) must fit under the
cap (``--budget``, default US$20 for the whole run); a step that would cross it submits only
the groups that fit and says what is left.

``ANTHROPIC_API_KEY`` must be in the environment; the ``anthropic`` package is needed only by
``propose`` and ``judge`` (``pip install anthropic``), not by the app.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL = "claude-sonnet-5-5"
#: US$ per million tokens, Claude Sonnet 5.5, before the 50% batch discount.
PRICE = {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.10}
BATCH_DISCOUNT = 0.5
GROUP = 12
MAX_TOKENS = 12000

PROPOSE_SYSTEM = """You are an experienced teacher of French as a foreign language. You review the answer keys of a French course for adult learners (CEFR A1 to C1). A key that only accepts one string fails learners who write another correct answer; a key that is too lenient lets real mistakes through. Your job is to write both lists for each item.

Each item gives: its id, the kind of exercise, the CEFR level, what the learner is shown or told, and the stored key.

Kinds:
- fix_the_mistake: the learner sees a sentence with a mistake (wrong_sentence) and writes the corrected sentence. The item practises the grammar_point.
- recall_word / recall_phrase: the learner sees the meaning (in English or German) or the scene and writes the French word or phrase. The item practises that word or phrase.
- cloze_word: the learner sees a line of the story with one blank (line_with_blank) and a hint (the word's meaning and dictionary form) and writes the word that fills the blank, in the form the line needs. A form that does not fit the line (the bare infinitive where the line needs a conjugated verb) is wrong.

For every item return:

1. accepted: every OTHER complete answer you would mark right for this exact prompt at this level. Do not repeat the key. Same shape as the key: a whole sentence for a sentence, a word or phrase for a word or phrase; if the key has no article, give none. Think of:
   - two correct spellings of one word (clé / clef, 1990 rectified spellings such as évènement, connaitre, paie / paye);
   - tu / vous, il / elle, masculine / feminine or singular / plural where the prompt leaves it open (English "you", "I" or "we" names no gender; a fix_the_mistake sentence only leaves open what its own wrong sentence leaves open);
   - on / nous when "we" is open and the grammar point is not on itself;
   - correct contractions and elisions, and another correct word order (inversion / est-ce que / intonation) when the grammar point is not that order.
   For cloze_word, accept only other forms of the same word that fit the blank equally well (a spelling variant, a gender or number the line leaves open); never a synonym.
   For fix_the_mistake, accept another correction only when it fixes the mistake, keeps the meaning and the other words, and is correct standard French that still uses the grammar point; a rewrite beyond the mistake is not accepted. For recall_word, synonyms are NOT accepted (the item practises that word), but spelling variants are.
   Do not list forms that differ from the key only by capitals, punctuation, apostrophe style or spacing: those are already folded. An empty list is a normal answer.

2. wrong: up to five wrong answers learners at this level really write for this prompt and that must stay wrong: for fix_the_mistake the wrong sentence left unchanged, a half fix, the classic trap of the grammar point, an accent that makes another word (a / à, ou / où); for recall the wrong gender or number, a near word, a false friend. Each wrong answer needs why_en and why_de: one short sentence that names what is wrong WITHOUT writing the right form or the key (the learner tries again before any solution is shown). Never list a form you would also accept.

3. key_ok: false when the stored key itself is not correct French or not a right answer to the prompt, and key_problem: one line saying why (else an empty string).

Answer for every item, in the order given, with its id."""

JUDGE_SYSTEM = """You are a strict, fair teacher of French as a foreign language grading learners' answers in a French course for adults (CEFR A1 to C1).

Each item gives: its id, the kind of exercise, the CEFR level, what the learner is shown or told, and a numbered list of answers different learners wrote.

Kinds:
- fix_the_mistake: the learner sees a sentence with a mistake (wrong_sentence) and must write it corrected. Right means: correct standard French, the mistake is fixed, the meaning and the other words are kept, and the grammar point is still used. A rewrite beyond the mistake is wrong. Something the wrong sentence leaves open (tu or vous, a gender the sentence does not fix) may be either.
- recall_word / recall_phrase: the learner sees the meaning or the scene and must write that French word or phrase. Right means: that word or phrase, in a correct spelling (two accepted spellings are both right, for example clé and clef). A synonym is wrong.
- cloze_word: the learner sees a line with one blank and a hint (meaning and dictionary form) and must write the word that fills the blank. Right means: the hinted word, in a form that makes the whole line correct French (capital letters never matter). A synonym or a form that does not fit the line is wrong.

Capitals, final punctuation, apostrophe style and spaces never matter. Judge every answer on its own, against the prompt, not against the other answers. For each answer return accept (true or false) and, when false, a short reason."""


def _schema_propose() -> dict[str, Any]:
    wrong = {
        "type": "object",
        "properties": {"form": {"type": "string"}, "why_en": {"type": "string"}, "why_de": {"type": "string"}},
        "required": ["form", "why_en", "why_de"],
        "additionalProperties": False,
    }
    item = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "accepted": {"type": "array", "items": {"type": "string"}},
            "wrong": {"type": "array", "items": wrong},
            "key_ok": {"type": "boolean"},
            "key_problem": {"type": "string"},
        },
        "required": ["id", "accepted", "wrong", "key_ok", "key_problem"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"items": {"type": "array", "items": item}},
        "required": ["items"],
        "additionalProperties": False,
    }


def _schema_judge() -> dict[str, Any]:
    verdict = {
        "type": "object",
        "properties": {"n": {"type": "integer"}, "accept": {"type": "boolean"}, "reason": {"type": "string"}},
        "required": ["n", "accept", "reason"],
        "additionalProperties": False,
    }
    item = {
        "type": "object",
        "properties": {"id": {"type": "string"}, "verdicts": {"type": "array", "items": verdict}},
        "required": ["id", "verdicts"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"items": {"type": "array", "items": item}},
        "required": ["items"],
        "additionalProperties": False,
    }


# ---------------------------------------------------------------------------
# Work directory
# ---------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _uid(item: dict[str, Any]) -> str:
    return f"{item['source']}/{item['id']}"


def _spend(work: Path) -> dict[str, Any]:
    path = work / "spend.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"usd": 0.0, "calls": 0, "tokens": {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}}


def _save_spend(work: Path, spend: dict[str, Any]) -> None:
    (work / "spend.json").write_text(json.dumps(spend, indent=1))


def _price(usage: Any, *, batch: bool) -> tuple[float, dict[str, int]]:
    tokens = {
        "input": int(getattr(usage, "input_tokens", 0) or 0),
        "output": int(getattr(usage, "output_tokens", 0) or 0),
        "cache_write": int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        "cache_read": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
    }
    usd = sum(tokens[name] * PRICE[name] for name in tokens) / 1_000_000
    return usd * (BATCH_DISCOUNT if batch else 1.0), tokens


def _book(work: Path, usage: Any, *, batch: bool) -> float:
    spend = _spend(work)
    usd, tokens = _price(usage, batch=batch)
    spend["usd"] = round(spend["usd"] + usd, 6)
    spend["calls"] += 1
    for name, value in tokens.items():
        spend["tokens"][name] += value
    _save_spend(work, spend)
    return usd


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


def _item_text(item: dict[str, Any], *, with_key: bool) -> dict[str, Any]:
    shown = {"id": _uid(item), "kind": item["kind"], "cefr": item["cefr"], "prompt": item["prompt"]}
    if with_key:
        shown["stored_key"] = item["key"]
    return shown


def _params(system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
    }


def _worst_case(n_requests: int) -> float:
    per_request = (6000 * PRICE["input"] + MAX_TOKENS * PRICE["output"]) / 1_000_000
    return n_requests * per_request * BATCH_DISCOUNT


def _fits(work: Path, groups: list[list[dict[str, Any]]], budget: float) -> list[list[dict[str, Any]]]:
    spent = _spend(work)["usd"]
    allowed = []
    for group in groups:
        if spent + _worst_case(len(allowed) + 1) > budget:
            break
        allowed.append(group)
    if len(allowed) < len(groups):
        print(f"budget: only {len(allowed)} of {len(groups)} requests fit under ${budget:.2f} (spent ${spent:.2f})")
    return allowed


def _client():
    import anthropic

    return anthropic.Anthropic()


def _text(message: Any) -> str:
    return next((block.text for block in message.content if block.type == "text"), "")


def _run(work: Path, step: str, requests: dict[str, dict[str, Any]], *, pilot: bool, wait: bool) -> dict[str, Any]:
    """Pilot: synchronous calls. Otherwise one batch, polled when ``wait``. Returns parsed JSON by custom id."""

    client = _client()
    out: dict[str, Any] = {}
    if pilot:
        for custom_id, params in requests.items():
            message = client.messages.create(**params)
            usd = _book(work, message.usage, batch=False)
            print(f"{step} {custom_id}: stop={message.stop_reason} usage={message.usage.input_tokens}/"
                  f"{message.usage.output_tokens} cache_r={message.usage.cache_read_input_tokens} ${usd:.4f}")
            if message.stop_reason == "end_turn":
                out[custom_id] = json.loads(_text(message))
        return out
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    batch = client.messages.batches.create(
        requests=[Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**params)) for cid, params in requests.items()]
    )
    (work / f"{step}_batch_{batch.id}.txt").write_text(json.dumps(sorted(requests)))
    print(f"{step}: batch {batch.id} with {len(requests)} requests")
    if not wait:
        return out
    return collect(work, step, batch.id)


def collect(work: Path, step: str, batch_id: str) -> dict[str, Any]:
    client = _client()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        counts = batch.request_counts
        print(f"{step}: {batch.processing_status} processing={counts.processing} succeeded={counts.succeeded}", flush=True)
        time.sleep(60)
    out: dict[str, Any] = {}
    for result in client.messages.batches.results(batch_id):
        if result.result.type != "succeeded":
            print(f"{step} {result.custom_id}: {result.result.type}")
            continue
        message = result.result.message
        _book(work, message.usage, batch=True)
        if message.stop_reason != "end_turn":
            print(f"{step} {result.custom_id}: stop_reason={message.stop_reason}")
            continue
        try:
            out[result.custom_id] = json.loads(_text(message))
        except ValueError:
            print(f"{step} {result.custom_id}: unreadable JSON")
    return out


def _groups(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    return [items[i : i + GROUP] for i in range(0, len(items), GROUP)]


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def export(work: Path, sources: list[str]) -> None:
    sys.path.insert(0, str(ROOT))
    from app.services.answer_bank import SOURCES, authored_items

    rows = [item.to_dict() for name in (sources or SOURCES) for item in authored_items(name)]
    (work / "items.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    counts: dict[str, int] = {}
    for row in rows:
        counts[f"{row['source']}:{row['kind']}"] = counts.get(f"{row['source']}:{row['kind']}", 0) + 1
    print(json.dumps({"items": len(rows), "by_source_and_kind": counts}, indent=1))


def propose(work: Path, *, pilot: int, wait: bool, budget: float) -> None:
    items = _read_jsonl(work / "items.jsonl")
    done = {row["uid"] for row in _read_jsonl(work / "proposals.jsonl")}
    todo = [item for item in items if _uid(item) not in done]
    groups = _groups(todo)[: pilot or None]
    groups = _fits(work, groups, budget)
    if not groups:
        print("propose: nothing to do")
        return
    requests = {}
    for n, group in enumerate(groups):
        user = "Items:\n" + json.dumps([_item_text(item, with_key=True) for item in group], ensure_ascii=False, indent=1)
        requests[f"p{n:04d}-{len(done)}"] = _params(PROPOSE_SYSTEM, user, _schema_propose())
    by_group = dict(zip(requests, groups, strict=True))
    results = _run(work, "propose", requests, pilot=bool(pilot), wait=wait)
    _store_proposals(work, results, by_group)


def _store_proposals(work: Path, results: dict[str, Any], by_group: dict[str, list[dict[str, Any]]]) -> None:
    rows = []
    for cid, parsed in results.items():
        wanted = {_uid(item) for item in by_group[cid]}
        for row in parsed.get("items") or []:
            if row.get("id") in wanted:
                rows.append({"uid": row["id"], **{k: v for k, v in row.items() if k != "id"}})
    _append_jsonl(work / "proposals.jsonl", rows)
    print(f"propose: stored {len(rows)} items, spend ${_spend(work)['usd']:.4f}")


def _candidates(item: dict[str, Any], proposal: dict[str, Any]) -> list[str]:
    forms = [item["key"], *proposal.get("accepted", []), *(row["form"] for row in proposal.get("wrong", []))]
    seen: dict[str, str] = {}
    for form in forms:
        folded = " ".join(str(form).casefold().replace("’", "'").split()).strip(" .!?")
        if folded and folded not in seen:
            seen[folded] = str(form).strip()
    out = list(seen.values())
    random.Random(_uid(item)).shuffle(out)  # noqa: S311 - a stable order, not a secret
    return out


def judge(work: Path, *, pilot: int, wait: bool, budget: float) -> None:
    items = {_uid(item): item for item in _read_jsonl(work / "items.jsonl")}
    proposals = {row["uid"]: row for row in _read_jsonl(work / "proposals.jsonl")}
    done = {row["uid"] for row in _read_jsonl(work / "judgements.jsonl")}
    todo = [items[uid] for uid in proposals if uid not in done and uid in items]
    groups = _groups(todo)[: pilot or None]
    groups = _fits(work, groups, budget)
    if not groups:
        print("judge: nothing to do")
        return
    requests, by_group, shown = {}, {}, {}
    for n, group in enumerate(groups):
        payload = []
        for item in group:
            forms = _candidates(item, proposals[_uid(item)])
            shown[_uid(item)] = forms
            payload.append({**_item_text(item, with_key=False), "answers": [{"n": i + 1, "answer": f} for i, f in enumerate(forms)]})
        cid = f"j{n:04d}-{len(done)}"
        requests[cid] = _params(JUDGE_SYSTEM, "Items:\n" + json.dumps(payload, ensure_ascii=False, indent=1), _schema_judge())
        by_group[cid] = group
    results = _run(work, "judge", requests, pilot=bool(pilot), wait=wait)
    _store_judgements(work, results, by_group, shown)


def _store_judgements(work: Path, results: dict[str, Any], by_group: dict[str, Any], shown: dict[str, list[str]]) -> None:
    rows = []
    for cid, parsed in results.items():
        wanted = {_uid(item) for item in by_group[cid]}
        for row in parsed.get("items") or []:
            uid = row.get("id")
            if uid not in wanted:
                continue
            forms = shown[uid]
            verdicts = {}
            for verdict in row.get("verdicts") or []:
                n = int(verdict.get("n") or 0)
                if 1 <= n <= len(forms):
                    verdicts[forms[n - 1]] = {"accept": bool(verdict.get("accept")), "reason": verdict.get("reason") or ""}
            if len(verdicts) == len(forms):
                rows.append({"uid": uid, "verdicts": verdicts})
    _append_jsonl(work / "judgements.jsonl", rows)
    print(f"judge: stored {len(rows)} items, spend ${_spend(work)['usd']:.4f}")


def _fold(value: str) -> str:
    sys.path.insert(0, str(ROOT))
    from app.services.answer_acceptance import fold_typography

    return fold_typography(value)


def write(work: Path) -> None:
    items = {_uid(item): item for item in _read_jsonl(work / "items.jsonl")}
    proposals = {row["uid"]: row for row in _read_jsonl(work / "proposals.jsonl")}
    judgements = {row["uid"]: row for row in _read_jsonl(work / "judgements.jsonl")}
    spend = _spend(work)
    banks: dict[str, dict[str, Any]] = {}
    for uid, item in items.items():
        if uid not in proposals or uid not in judgements:
            continue
        proposal, verdicts = proposals[uid], judgements[uid]["verdicts"]
        key_fold = _fold(item["key"])

        def verdict_of(form: str, verdicts: dict[str, Any] = verdicts) -> dict[str, Any] | None:
            for shown, verdict in verdicts.items():
                if _fold(shown) == _fold(form):
                    return verdict
            return None

        key_verdict = verdict_of(item["key"]) or {"accept": False, "reason": "not judged"}
        accepted: list[str] = []
        for form in proposal.get("accepted") or []:
            folded = _fold(form)
            verdict = verdict_of(form)
            if folded and folded != key_fold and verdict and verdict["accept"] and folded not in {_fold(f) for f in accepted}:
                accepted.append(str(form).strip())
        accepted_folds = {key_fold, *(_fold(f) for f in accepted)}
        wrong: list[dict[str, str]] = []
        for row in proposal.get("wrong") or []:
            folded = _fold(row["form"])
            verdict = verdict_of(row["form"])
            reasons_given = str(row.get("why_en") or "").strip() and str(row.get("why_de") or "").strip()
            if folded and folded not in accepted_folds and verdict and not verdict["accept"] and reasons_given:
                if folded not in {_fold(w["form"]) for w in wrong}:
                    wrong.append({"form": row["form"].strip(), "why_en": row["why_en"].strip(), "why_de": row["why_de"].strip()})
        entry: dict[str, Any] = {
            "hash": item["hash"],
            "kind": item["kind"],
            "key": item["key"],
            "accepted": accepted,
            "wrong": wrong,
        }
        if not key_verdict["accept"]:
            entry["key_rejected"] = True
            entry["key_judge_reason"] = key_verdict["reason"]
        if not proposal.get("key_ok", True):
            entry["key_proposer_problem"] = proposal.get("key_problem") or ""
        bank = banks.setdefault(item["source"], {"entries": {}})
        bank["entries"][item["id"]] = entry
    out_dir = ROOT / "app" / "data" / "answer_bank"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).date().isoformat()
    for source, bank in sorted(banks.items()):
        total = sum(1 for item in items.values() if item["source"] == source)
        document = {
            "_about": "Answer bank (#174), written by scripts/build_answer_bank.py. Do not edit by hand: regenerate.",
            "source": source,
            "model": MODEL,
            "generated": stamp,
            "items": total,
            "covered": len(bank["entries"]),
            "entries": dict(sorted(bank["entries"].items())),
        }
        (out_dir / f"{source}.json").write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        rejected = sum(1 for e in bank["entries"].values() if e.get("key_rejected"))
        variants = sum(len(e["accepted"]) for e in bank["entries"].values())
        wrongs = sum(len(e["wrong"]) for e in bank["entries"].values())
        print(f"{source}: {len(bank['entries'])}/{total} items, {variants} variants, {wrongs} wrong forms, {rejected} keys rejected")
    print(f"spend: ${spend['usd']:.4f} over {spend['calls']} calls, tokens {spend['tokens']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["export", "propose", "judge", "write"])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--pilot", type=int, default=0, help="only this many groups, synchronously")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--budget", type=float, default=20.0)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    if args.step == "export":
        export(args.work, args.source)
    elif args.step == "propose":
        propose(args.work, pilot=args.pilot, wait=args.wait, budget=args.budget)
    elif args.step == "judge":
        judge(args.work, pilot=args.pilot, wait=args.wait, budget=args.budget)
    else:
        write(args.work)


if __name__ == "__main__":
    main()
