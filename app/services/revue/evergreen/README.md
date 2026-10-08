# Evergreen dossiers (WP-119 §4.3)

Twelve authored editorial dossiers in the §3.1 schema (`app/services/revue/dossier.py`),
loaded by `app/services/revue/evergreen.py`. They fill a thin week, and they are the only
content of the test and walk harnesses. `tests/test_revue_evergreen.py` checks that they
pass the Anchor, Attribution and Temporal checks offline.

| id | topic | `happening` | sources |
|---|---|---|---|
| `evergreen-rentree` | culture | 2026-08-24 → 2026-09-13 | service-public.gouv.fr (2), fr.wikipedia.org |
| `evergreen-beaujolais-nouveau` | food | 2026-11-19 → 2026-11-29 | beaujolais.com (Inter Beaujolais), fr.wikipedia.org |
| `evergreen-galette-des-rois` | culture | 2026-01-01 → 2026-01-31 | fr.wikipedia.org |
| `evergreen-soldes-d-hiver` | city | 2026-01-07 → 2026-02-03 | service-public.gouv.fr (2) |
| `evergreen-fete-de-la-musique` | culture | 2026-06-15 → 2026-06-28 | fetedelamusique.culture.gouv.fr, fr.wikipedia.org |
| `evergreen-tour-de-france` | sport | 2026-07-04 → 2026-07-26 | fr.wikipedia.org (2) |
| `evergreen-toussaint` | culture | 2026-10-26 → 2026-11-08 | fr.wikipedia.org (2) |
| `evergreen-marche-du-dimanche` | food | all of 2026 | paris.fr, fr.wikipedia.org |
| `evergreen-greve-transports` | work | all of 2026 | ecologie.gouv.fr, fr.wikipedia.org |
| `evergreen-bac` | culture | 2026-06-08 → 2026-07-12 | fr.wikipedia.org |
| `evergreen-quatorze-juillet` | culture | 2026-07-06 → 2026-07-19 | fr.wikipedia.org (2) |
| `evergreen-noel-au-marche` | culture | 2026-11-27 → 2026-12-24 | noel.strasbourg.eu, fr.wikipedia.org |

## Layout

- `<id>.json`: one dossier. The file name is the dossier id. `evergreen` is `true`.
- `sources/<source_id>.txt`: the excerpt for one source. The first line is
  `# <url> — fetched <YYYY-MM-DD>`. After it come the passages that contain the quotes,
  copied verbatim and joined by ` […] `, at most 120 words. `evergreen_source_texts()`
  returns them with the header line removed, and the Anchor check compares against them.
  Source ids are global across all dossiers, so each dossier prefixes its own
  (`beaujolais_…`, `greve_…`).

## The quote rule

Every claim's `quote` must be a **verbatim** substring of a real public page, at most 40
words after `fold()`. Keep accents. Apostrophes and quotation marks may differ (’ vs ',
« » vs "), because `fold()` makes them the same. The quote must appear in that source's
excerpt file, and the claim's `url` and `published_at` must be the source's.

- Wikipedia sources link to a **permanent revision** (`index.php?title=…&oldid=…`), so
  the quoted text cannot drift. Their `published_at` is that revision's date.
- Official pages use their own date: "Publié le", or "Vérifié le", or "Mise à jour le"
  when that is the only date the page shows. `noel.strasbourg.eu/notre-histoire` shows
  no date, so its `published_at` is the day it was read (2026-10-02).
- One quote comes from a table: in `rentree_sp_calendrier`, the row "Rentrée des élèves …"
  of the service-public.gouv.fr calendar. In the excerpt, its cells are joined with
  single spaces.

## What the checks expect (and how the text is written for them)

- **Temporal.** A claim's `fr` or the `summary_fr` must not contain a weekday or a
  relative date ("jeudi", "dimanche", "demain", "aujourd'hui"). The only exception is a
  weekday followed by a day number ("le jeudi 19 novembre"). So the Beaujolais claim says
  "le jeudi 19 novembre" instead of "le troisième jeudi de novembre". The marché claim
  says "six jours sur sept" instead of "sauf le lundi". Titles, quotes and uncertainties
  are not scanned.
- **Attribution.** A `fact` must not contain a word of judgement (`checks.OPINION_LEXICON`).
  Every dossier has at least one `interpretation` with `attributed_to`.
- **Anchor (phase 0).** A claim's `fr` must share a content word with its quote.
- **Policy.** Titles, summaries, claims and quotes must pass `policy.is_sensitive`. A
  place `brief` describes a place with nobody in it, so `policy.plate_forbidden_hits` must
  return nothing.

## Weeks and time scopes

`EditorialDossier.week` is required. Each JSON stores the ISO week in which its
`happening` window **starts** (for example, `2026-W47` for Beaujolais). The stored week is
only there to satisfy the schema. `evergreens_for_week(week)` ignores it and uses
`time_scope` alone: a dossier matches when its window overlaps that week's Monday to
Sunday. Matches are sorted most specific first (shortest window, then id). This way
`evergreen_for(week)` returns a seasonal dossier before the two year-round ones (the
market and the strike). The year-round dossiers mean that every week of 2026
(W01 to W53) has at least one match. `relevant_until` is at least two weeks after each
window ends.

The windows are 2026 dates. For 2027, every yearly dossier needs a new window and new
date claims (for example, the rentrée date, the soldes dates and the Tour dates).

## Adding a dossier

1. Find a stable public French page. Prefer official sites (service-public.gouv.fr, a
   ministry, a city) or a Wikipedia permanent revision.
2. Copy the passages that hold your quotes into `sources/<dossier>_<source>.txt`, under
   the header line. Stay within 120 words.
3. Write `<id>.json`:
   - 3–4 claims, mostly `fact`, with at least one `interpretation` that has `attributed_to`;
   - 1–3 entities (a person only if needed, and always with a `role`);
   - 1–2 uncertainties (real gaps a learner could ask about);
   - 2 angles with different `purpose`s;
   - 1 place whose `brief` shows no people;
   - `time_scope`, with `week` set to the ISO week of the window's start;
   - `"evergreen": true`.
4. Add the id to `EXPECTED_IDS` in `tests/test_revue_evergreen.py`, then run
   `.venv/bin/python -m pytest tests/test_revue_evergreen.py -q`.

## À vérifier

Every quote was checked against the live page on 2026-10-02, and nothing is unverified.
Some page dates are worth a second look:

- `noel_strasbourg`: the page shows no date (see above).
- `noel_strasbourg` says the market moved to place Broglie in 1870, and the same site's
  "Christkindelsmärik" magazine page says 1871. No claim uses that date.
- Several Wikipedia revisions and official pages are dated **after** the 2026 window they
  describe. Temporal skips its source-age rule for evergreens, so the checks accept this.
