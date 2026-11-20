Commons API answers for tests/test_revue_photos.py (no network in tests).

Shaped exactly like a `action=query&generator=search&prop=imageinfo&formatversion=2` answer of
https://commons.wikimedia.org/w/api.php (iiprop=url|extmetadata|size|mime, iiurlwidth=1280):
pages with `index` (search rank), `imageinfo[0]` with size, mime, thumburl, descriptionurl and the
extmetadata entries the filter keeps. The files, authors and URLs are made up for the tests (each
page exercises one rule of app/services/revue/photos.py); they were written by hand in the API's
format, not recorded from the live API.
