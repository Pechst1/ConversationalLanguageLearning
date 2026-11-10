# V · The verdict as a stored fact: one judge, one ledger, checks that finish later

Written 10 Nov 2026 from `origin/main` at `762048a7` and the six draft PRs of the verdict stack (#642, #646, #648, #650, #652, #654). Root causes #174, #250, #333.
Implementation: Opus 5.5, medium effort, own worktree cut from `origin/main`, draft PRs, nothing merges without the owner.

## What the stack already does (keep all of it)

- One `check` shape (`app/core/verdict.py`): outcome, who checked, call state, listed edits, `corrected` built from the edits, `counts`.
- A check that did not run counts for nothing; one screen state for it on every surface (`lib/verdict.ts`).
- Every change in a corrected line is listed and verified (`correction_contract.py`).
- A rule pass with a negative corpus (0 false corrections on 4,220 published texts).

## The structural flaw the stack leaves

1. **The verdict is rebuilt on every read.** Nine adapters in `app/services/verdicts.py` (`from_recall`, `from_forge`, `from_courrier`, …) reconstruct it from each surface's own stored payload. Nothing stores what was decided, by which judge, at what time. So a change to an adapter or a rule silently re-judges history: on deploy a learner's level can move without them doing anything.
2. **An unread answer waits for the learner.** `not_checked` is honest, but the only way out is the learner pressing «Check again», on a route with no limit. A provider outage becomes lost work.
3. **Nothing learns.** #174 was «a right answer is judged against one stored string». `answer_acceptance.py` normalises and reads the item's listed variants, but a correct answer outside the list goes to the model every time, costs a call every time, and can be judged differently each time.
4. **No way to say «the judge is wrong».** A wrong verdict can only be found by a walk.
5. **A judge change has no measured effect.** The corpora are tests of single rules. Nothing replays the same answers through the old and the new judge and counts the verdicts that flip. The rule pass already «corrects» valid 1990-reform spellings; nobody saw it until a review.

## Target structure

**A. One judge.** `app/services/judge.py`: `judge(task, answer, *, user) -> Verdict`. Fixed stages, each adding evidence, the first that settles wins:

1. normalise (`answer_acceptance`);
2. key and listed variants;
3. the memo (D below);
4. rules: add edits, never a verdict;
5. model, with every edit verified against the learner's text;
6. variant gate: no edit may turn one accepted spelling into another (1990 rectifications, both apostrophes, «?» spacing).

Every surface calls it. `judge_version` is a hash of the rule set, the prompt and the model id.

**B. A verdict ledger.** Table `verdict_records`: id, user, surface, subject (row type and id), answer text, the verdict as JSON, `judge_version`, `supersedes_id`, `settled_at`, what it paid (level evidence, gold, token). Append-only: a later check writes a new record that supersedes the old one.
- Levels, gold and tokens read only ledger records with `counts`. Payment is tied to the record, so a superseding record pays or takes back the difference exactly once.
- The `from_*` adapters stay only as the reader for rows older than the cut-over. Those rows keep what they counted for (`VERDICT_LEGACY_ROWS = as_counted`), so **nothing moves on deploy**. A script prints, per learner, what a re-judge of the old rows would change, for the owner to decide.

**C. Checks that finish later.** A retryable `not_checked` record enqueues `app.tasks.verdict_settle.settle_verdict` (same pattern as `season_writer`: capped attempts with backoff, a budget cap, broker refusal leaves the record as it is). When it settles, the new record pays what is due, and the surface shows «Checked since» the next time it is opened. The learner's «Ask again» enqueues the same job: idempotent per record, limited per learner and day. An outage becomes a delay.

**D. A memo that learns.** Table `answer_memos`: item fingerprint, normalised answer, outcome, edits, state `candidate | confirmed | revoked`, the records that back it. Only for tasks with a key (drills, Forge, placement).
- A model verdict on a keyed item writes a candidate. It is confirmed by a second, independent check (a second call with a different prompt that agrees, and rules that find nothing for «right»). A confirmed memo settles the same answer next time as `checked_by: key`: instant, free, the same for everyone.
- Confirmed «not yet» memos keep their verified edits, so the same miss gets the same explanation.
- Revoking a memo supersedes the records it settled. `/pilot-ops` lists candidates and confirmed memos.

**E. An appeal.** On a `not_yet` or `partly` verdict, one quiet line: «Je pense que c'est juste». It enqueues a re-judge by the stronger model with the appeal prompt. Upheld: the record is superseded, the memo gains the answer, and the case is written to `tests/verdict_corpus/candidates/` by a script for the night shift to open as a PR. Refused: the learner gets the reason in one sentence. Limited per day. av2 only: no new colour, font or component shape.

**F. A replay gate.** `tests/verdict_corpus/`: the walk and issue sentences, the gold set, the negative corpus, a list of valid 1990-reform spellings and other valid variants. `scripts/verdict_replay.py` runs a corpus, or an export of the ledger, through two judge versions (model answers from the `tests/prompt_regression` cache) and prints every flip. CI fails on a right→wrong flip and on any edit of a valid variant.

## Stages (each its own PR, stacked)

1. **Base.** One branch from `origin/main` that holds both stack tips (`claude/verdict-remaining-surfaces`, `claude/verdict-rule-pass`), conflicts resolved. Plus: the variant gate with the 1990 list, a limit on «Check again», and the cut-over so stored rows keep what they counted for. It replaces the six PRs; say so in the PR, close nothing.
2. **Judge and ledger** (A, B), with the level-report script and the replay gate (F).
3. **Settlement job** (C).
4. **Memo** (D).
5. **Appeal** (E).

## Done when

- Stage 1: a test loads rows written by main's code, switches to the branch's code and asserts no level, gold or token changes. The reform list yields zero edits. The 23 backend guards of the stack pass.
- Stage 2: a source guard finds no `Verdict` built outside `judge()` and the legacy reader. A test supersedes a record twice and sees gold paid once. Replay of the corpus against the base judge shows zero right→wrong flips.
- Stage 3: an end-to-end test through the real routes: provider down, the answer is saved unread, the provider returns, the eager job settles it, gold is paid once, the screen payload says it was checked since. A broker that refuses the task leaves a retryable record.
- Stage 4: the second identical answer to an item makes no model call and gets the same verdict; a revoked memo takes back what it paid.
- Stage 5: the walk appeals a wrong verdict in `de` and `fr` and sees the verdict change; the daily limit holds.
- Before handing over each stage that changes a screen: a full A1 `de` day and a full B1 `en` day, normally and with `WALK_PROVIDER_DOWN=1`.

## Not in this package

- The story-truth stack and the re-ask mechanism.
- S1's `explain_miss`: it will read the ledger record; it is not built here.
- Pronunciation scoring.

## Owner decisions needed (the proposal is built unless the owner says otherwise)

1. Old rows: keep what they counted for (proposal), or re-judge after reading the level report?
2. A check that settles later pays its gold and token then (proposal: yes).
3. Memo confirmation: a second agreeing call (proposal), or owner approval on `/pilot-ops` for each one?
4. Appeal: on, three per day (proposal), or off.
5. Budget for background checks per learner and day (proposal: 20 calls).
