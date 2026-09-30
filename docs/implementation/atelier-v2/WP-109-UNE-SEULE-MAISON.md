# WP-109 · Une seule maison — one answer to «where is the story?»

*2026-09-30. Brief: `HANDOVER-FEUILLETON-REBUILD-2026-09-30.md` §2 and owner decision F-3.*

## 1. What changed

| | Before | Now |
|---|---|---|
| **Tabs** | Atelier · Courrier · Feuilleton · Cahier | **La Une · Feuilleton · Courrier · Cahier** (F-3). Same routes; the desktop masthead lists the same four, from the same source (`lib/product-shell.ts`) |
| **The day** | warm-ups → scene → reply → *drills* → ending | warm-ups → scene → reply → **ending** → practice. The episode is never interrupted; the planner and the plan validator both say so |
| **Home** | «Votre prochain chapitre · 5 min» until the day was created | **«Nº 7 · La clé d'Odile»**, the title (a tentpole's is known in advance), yesterday's «À suivre…» and the faces of who is in it. A generated day's title does not exist until it is written, and nothing is invented: the teaser leads |
| **Feuilleton tab** | archive and cast only; today's episode was not there | **today's episode first** («Aujourd'hui · Nº 7…», one button «Lire l'épisode du jour»), then the archive and the cast. The card disappears once the day is done: the page is then the archive's newest |
| **Day mark** | — | the practice after the ending counts toward «Bouclé»: the day is never «bouclée» while words remain |

**One way into the story.** Home's primary button and the Feuilleton's card both open the
same day (`/atelier?start=today`: start or resume). The day's scene, reply and ending are
read in the Feuilleton reader. The finished page (WP-110) is filed in the Feuilleton.

## 2. The contract

- **`TodayEnvelope.headline: EpisodeHeadline | null`** (additive):
  `edition_no`, `title_fr`, `teaser_fr`, `season_title_fr`, `cast[{id, name}]`.
  - Built by `app/services/story_headline.py`: read-only, no model call, and it never
    costs Home.
  - `None` when the story engine is off, when the day's episode is over, or when there
    is nothing to headline.
- **`PlannedJourney._validate_practice`:**
  - «nothing may sit between the reply and the ending»;
  - «only practice may follow the ending»;
  - the optional «Lecture» comes last.
  - Plans are validated only when they are built, so journeys already under way keep
    their order.
- **Frontend:**
  - `lib/episode-headline.ts`: kicker, title, teaser; pure and tested.
  - `components/feuilleton/archive/TodayEpisode.tsx`: the Feuilleton's card.
  - `JourneyTodayCard`: the Home headline.

## 3. Evidence

- **Backend:**
  - `tests/test_season_one.py::test_home_headlines_todays_episode`: a tentpole day before
    it starts, gone once finished, then T1 Day B, then a generated day led by its teaser.
  - `test_wp93_day_rebalance.py::test_nothing_sits_between_the_reply_and_the_ending`.
  - The practice-day and rhythm tests are updated to the new order.
- **Frontend:**
  - `lib/episode-headline.test.js`.
  - `archive.test.js` (today's card).
  - `day-mark.test.js` (the practice after the ending counts toward «Bouclé»).
- **Walk checks:**
  - `tabs-la-une-feuilleton-courrier-cahier`
  - `home-headlines-the-episode` (from day 2)
  - `feuilleton-opens-on-today`
  - `feuilleton-today-in-one-tap` (on day 2 each learner enters the day from the
    Feuilleton's card)

## 4. Known cost and open points

- **Latency.** The ending now follows the reply at once. On a generated day the story
  lane writes it off the request path (WP-87); the drills after the reply used to hide
  that time. The learner now sees the ending's «being written» state more often.
  - Measure it in the pilot (`journey_story_lane_settled.seconds`).
  - If it hurts, the fix is to start the story lane on the reply's *last* turn earlier,
    not to move drills back into the episode.
- **Faces.** The headline shows the drawn cast. A speaker without a portrait (Camille,
  the notaire) shows their initial.
- **Words.** «Mots» on Home now points at the warm-ups and the practice after the ending.
  WP-115 proposes where vocabulary review should live.
