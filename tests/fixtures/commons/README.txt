Commons API answers for tests/test_revue_photos.py (no network in tests).

Shaped exactly like a `action=query&generator=search&prop=imageinfo&formatversion=2` answer of
https://commons.wikimedia.org/w/api.php (iiprop=url|extmetadata|size|mime, iiurlwidth=1280):
pages with `index` (search rank), `imageinfo[0]` with size, mime, thumburl, descriptionurl and the
extmetadata entries the filter keeps. The files, authors and URLs are made up for the tests (each
page exercises one rule of app/services/revue/photos.py); they were written by hand in the API's
format, not recorded from the live API.

live_2026-11-22_budget.json is different: RECORDED from the live API on the first real Papier run
(2026-11-22, HTTP/2), trimmed to the first 4 pages of each search and the extmetadata keys the filter
reads, with the run's own dossier. It shows two faults the hand-written answers never had: a stage
landmark the story never names (the Arc de Triomphe for the budget) and an infographic saved as JPEG.
live_2026-11-22_goncourt.json, recorded the same way: «roman» found a Roman theatre in Orange and
«sélection» found the Auschwitz-Birkenau ramp (1944), which only the person rule refused.
