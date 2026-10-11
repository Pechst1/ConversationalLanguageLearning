"""WP-111 «La bible de saison»: the owner-approved season, runnable.

The season bible in ``docs/story/season-1/`` is prose for people. This package is
the same season as data the engine can play:

* :mod:`.format` — the typed season format (tentpoles as authored two-day pages,
  the gaps between them, the flag table) and its loader;
* :mod:`.clock` — the learner's own day count, the segments of the season, and
  the weekend flex that lands a tentpole's Day A on a Saturday or Sunday (S-12);
* :mod:`.flags` — the world flags a season sets and reads, and Lila's path;
* :mod:`.page` — one tentpole day resolved for a band, a language and the flags,
  and its projection onto today's scene / reply / ending steps;
* :mod:`.director` — what the director is told on a generated day, the gap's
  forbidden reveals, and the story critic (WP-114).

Nothing here calls a model on a tentpole day: an authored page is instant.
"""
