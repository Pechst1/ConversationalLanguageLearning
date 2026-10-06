# Fixture RSS corpus for WP-119 phase 3 «Le kiosque»

Authored for the tests (`tests/test_revue_intake.py`, `test_revue_builder.py`,
`test_revue_kiosk.py`): five French feeds of a fictitious outlet group on the host
`https://kiosque.test`, served through `httpx.MockTransport`.

- `registry.json` — the fixture source registry (same shape as
  `NewsService.FRANCE_SOURCE_REGISTRY`, with `fetch_policy`).
- `<feed>.xml` — RSS 2.0, ISO week 2026-W40 (28 Sept – 4 Oct 2026). Seven usable stories
  (two culture, one food, two city, one sport, one politics), plus a sensitive item (filtered
  at intake), an English item (filtered by the language check) and a story under `/prive/`
  (refused by `robots.txt`, so built from its teaser).
- `articles/<slug>.html` — the article pages, with navigation, scripts, an aside and a
  footer around the `<article>` the extractor keeps.
- `robots.txt` — `Disallow: /prive/`.

The facts are invented for the tests; nothing here is real reporting.
