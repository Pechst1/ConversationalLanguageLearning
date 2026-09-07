"""Versioned, inspectable lesson contracts and concrete challenges for the core catalog.

The marked span is the exact teaching target; the second form is an authored foil.
Examples in unrelated task text must never select a different grammar lesson.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def curriculum() -> dict[str, dict[str, Any]]:
    with (ROOT / 'templates/french_core_grammar_v1.tsv').open(encoding='utf-8') as source:
        lessons = {row['external_id']: dict(row) for row in csv.DictReader(source, delimiter='\t')}
    for line in (ROOT / 'app/data/seance_challenges.txt').read_text(encoding='utf-8').splitlines():
        external_id, marked, scene = line.split('|')
        match = re.search(r'\[([^/]+)/([^\]]+)\]', marked)
        if not match:
            raise ValueError(f'Missing focus in {external_id}')
        focus, foil = match.groups()
        lessons[external_id].update(
            focus=focus, foil=foil, scene=scene,
            sentence=marked[:match.start()] + focus + marked[match.end():],
            source=marked[:match.start()] + foil + marked[match.end():],
            blank=marked[:match.start()] + '___' + marked[match.end():],
        )
    for key in ('FR_A2_PRON_002', 'FR_B1_PRON_002'):
        lessons[key]['core_rule'] += (
            " Put y or en before the conjugated verb (or before the infinitive it belongs to)."
            " For quantities, en replaces the noun but the number stays:"
            " Tu veux des pommes ? J'en veux deux."
            " For a place: Tu vas au marché ? J'y vais."
            " For a de-complement: Tu parles de ce projet ? J'en parle."
        )
    # Alternate authored correct/incorrect examples by catalog position.
    # Teaching-order values are not a probability or a sampling interval.
    for index, key in enumerate(sorted(
        lessons, key=lambda key: (int(lessons[key]['teaching_order']), key)
    )):
        lessons[key]['classify_show_correct'] = index % 2 == 0
    return lessons


def lesson_for(concept: Any) -> dict[str, Any] | None:
    return curriculum().get(str(getattr(concept, 'external_id', '') or ''))


def lesson_panel(concept: Any) -> dict[str, Any] | None:
    lesson = lesson_for(concept)
    if not lesson:
        return None
    return {
        'title': concept.name,
        'rule': lesson['core_rule'],
        'when': lesson['when_to_use'],
        'pattern': lesson['pattern'],
        'check': 'Avoid: ' + lesson['main_traps'].split(' | ')[0],
        'examples': [lesson['sentence'], *lesson['anchor_examples'].split(' | ')[:2]],
        'traps': lesson['main_traps'].split(' | '),
    }
