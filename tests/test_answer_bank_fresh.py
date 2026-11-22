"""#174: the answer bank is regenerated whenever an item's prompt or key changes.

The bank (``app/data/answer_bank``) was written for each authored item's prompt and key at
the time (``answer_bank.item_hash``). Edit a ✗/✓ pair, a séance challenge, a scenario
phrase or a season word without rerunning ``scripts/build_answer_bank.py`` and this fails,
naming the item. A source the bank has not been written for yet is not checked here.
"""

from __future__ import annotations

from dataclasses import replace

from app.services import answer_bank


def test_every_banked_item_is_fresh():
    problems = answer_bank.freshness_problems()
    assert not problems, "Regenerate the answer bank (scripts/build_answer_bank.py):\n" + "\n".join(problems[:40])


def test_a_changed_prompt_or_key_is_caught():
    items = [item for item in answer_bank.authored_items() if item.id in (answer_bank.load_bank(item.source).get("entries") or {})]
    assert items, "the bank covers no item"
    item = items[0]
    changed_prompt = replace(item, prompt={**item.prompt, "wrong_sentence": "Autre phrase."})
    changed_key = replace(item, key=item.key + " Autre.")
    assert answer_bank.freshness_problems([changed_prompt])
    assert answer_bank.freshness_problems([changed_key])
    assert not answer_bank.freshness_problems([item])
