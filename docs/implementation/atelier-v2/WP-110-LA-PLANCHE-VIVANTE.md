# WP-110 · La planche vivante — a finished day reads as one page

*2026-09-30. Brief: `HANDOVER-FEUILLETON-REBUILD-2026-09-30.md` §2. Built on WP-111.*

## 1. What a learner sees

Once the day's ending is written, the episode is one page. The reader pages through it,
one panel per screen:

| Movement | Row | What it draws |
|---|---|---|
| 1 · the characters acting | `act` | the scene's panels |
| 2 · the turn to *you* | `turn` | the panel the question is asked in; **your line is the balloon on its art** (red press, bottom right), the characters keep their captions (S-2/F-2) |
| 3 · the reaction | `reaction` | what your line set off: on a tentpole, the bible's beats for the reply it routed to; on a generated day, the character's answer (and your next line, as the next balloon) |
| 4 · the solve | `solve` | the moment and the card the story took (WP-112 will pose it) |
| 5 · the ending | `ending` + the reader's last stage | a tentpole's hook panel; the day's ending line |
| 6 · «À suivre…» | on the last stage | tomorrow's line (`next_teaser_fr`) |

Where the page shows:

- **At the day's ending.** The ending step re-reads the episode once, so the finale closes
  the whole page, not only the scene read before it. A learner on the ending stays on it
  when the page arrives.
- **In the Feuilleton archive.** Re-reading a day opens the page on its first panel. The
  separate «Your reply / How it ended» box is gone for a day with a page: the page is the
  record. The last panel's button goes back to the archive.

Before the day is finished, nothing changes: the scene is its panels, and the conversation
is the WP-89 thread.

## 2. The contract

- **Server.** `app/services/story_page.py` builds the page, only for a completed scene.
  - *Tentpole days:* from the stored `season_page` and the routed replies
    (`season_routing`). Each panel stands on its place's plate.
  - *Generated days:* from the scene's panels and the conversation stored at settle
    (`script_payload.page_thread`: who, the opening question, each reply and its answer).
- **DTO.** `StoryEpisodeRead.page: StoryPageRead | null` (`rows[]`, `a_suivre_fr`). Each
  row is panel-shaped (`narration_fr`, `dialogue`, `image_url`, `image_status`) plus
  `movement`; a line carries `you`. `StoryDialogueRead` now documents `mood` and
  `text_native`, which the server already sent.
- **Frontend.**
  - `buildStoryStages` reads `page.rows` when present.
  - `panelReaderVariant` draws a panel holding your line as the balloon, whatever the
    variant switch says (the owner's variant B still governs every character line).
  - `FeuilletonReader` puts the `you` line in the balloon (`data-you`) and closes on
    «À suivre…».

## 3. Evidence

- **Backend.** `tests/test_season_one.py::test_a_finished_day_reads_as_one_page_with_the_learners_lines_in_it`
  covers a tentpole day and a generated day.
- **Frontend.**
  - `story-episode-model.test.js`: 3 WP-110 tests.
  - `reader-render.test.js`: your line in the balloon, the character in a caption;
    «À suivre…».
  - `archive.test.js`: the page is the record.
- **Walk.** `readThePage()` re-reads the day from the Feuilleton for the season learner
  every day, and for the other learners on day 1 and their last day. It shoots every
  panel and checks:
  - `page-draws-your-line`
  - `page-has-the-six-movements`
  - `page-ends-a-suivre`

## 4. Not in this package

- **Per-panel art.** Tentpole pages stand on the location plates. Drawing them is the
  art run (WP-88/108), which is the owner's decision.
- **Solves posed in the page** (WP-112). Today a solve row shows the card the story took.
- **The day's steps are unchanged.** The page is how the day reads once it is finished.
  Playing the turns inside the page is WP-112/113 territory.
