# Week 2026-W40 (Monday 28 September – Sunday 4 October 2026)

Six live editorial dossiers in the §3.1 schema, loaded by `app/services/revue/weekly.py`
and checked offline by `tests/test_revue_weekly.py`. The layout and the quote rule are
the evergreens' (`../../evergreen/README.md`): one `<id>.json` per dossier, one
`sources/<source_id>.txt` excerpt per source (header `# <url> — fetched 2026-10-02`,
verbatim passages joined by ` […] `, at most 120 words). Source ids carry the `w40_`
prefix so they never clash with the evergreens' when the two are merged.

| id | topic | `happening` | sources (published) |
|---|---|---|---|
| `2026-w40-goncourt-roman-retire` | culture | 09-25 → 10-06 | franceinfo.fr, actualitte.com (both 09-25) |
| `2026-w40-prix-produits-frais` | food | 09-30 → 10-15 | abcbourse.com, insee.fr (both 09-30) |
| `2026-w40-paris-plan-canicules` | city | 09-29 → 10-11 | ici.fr (09-29) |
| `2026-w40-ce-qui-change-1er-octobre` | city | 10-01 → 10-31 | franceinfo.fr (09-30) |
| `2026-w40-prix-de-l-arc-de-triomphe` | sport | 10-01 → 10-04 | equidia.fr (10-01), AFP on actu.orange.fr (10-02) |
| `2026-w40-budget-2027` | politics | 10-01 → 12-20 | lafinancepourtous.com, franceinfo.fr (both 10-02) |

Every quote was checked against the live page on 2026-10-02 (`fold()`-ed substring of
the fetched HTML text). `published_at` is the page's `article:published_time` /
`datePublished` (Insee: the "Informations rapides" date). All claims fall inside the
Temporal window: 21 days before Sunday 4 October, and not after it.

Notes:

- france24.com refused the fetch (403); the Insee figures come from insee.fr and ABC
  Bourse instead. The AFP story on the Arc is read on actu.orange.fr.
- The AFP spells the trainer "Francis-Henry Graffard" (kept verbatim in the quote);
  `attributed_to` and the entity use "Francis-Henri", as Equidia does.
- The Paris plan also exists as a press kit (cdn.paris.fr, PDF, 29 September); the
  dossier quotes only the ICI article.
- Stories left out: the 2026 vendanges (Agreste's estimate is from 7 September, too old
  for the window; the next one is 7 October), Nuit Blanche (held on 6 June in 2026), the
  métro line 18 opening (now December), the lycée blockades (damage and police).
