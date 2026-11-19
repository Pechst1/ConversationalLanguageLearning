# Round 4 (owner go-ahead 19 Nov 2026)

Read `/private/tmp/claude-501/-Users-vincentpechstein--claude-spares-spare-8BRKzU/24979350-c568-4d32-a313-976ff75f7f81/scratchpad/PACKAGE-RULES.md` fully first; its rules apply, except where this file differs.

## What is different in round 4
- **Base and PR target:** cut your branch from `origin/claude/pilot-train-6-switches-courrier` (it holds every pilot package; its tree equals the integration branch) and open your **draft** PR against that branch, not `main`. Worktree: `git -C /Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning worktree add .claude/worktrees/<your-branch-short-name> -b <your branch> origin/claude/pilot-train-6-switches-courrier`.
- **Never alter a gate** (the gold-transcript gate and `gate.json`, `tests/gold_transcripts/*`, the walk's known-failures list, CI workflows). If a gate objects, report it. «Backend · ruff + pytest (1/4)» stops at the gold gate on this base already («STALE scene/forge/correction»): that is the owner's paid run, not yours. If your change alters a model prompt, say so plainly at the top of the PR body.
- Never merge, never mark ready, never enable auto-merge. No paid model calls. No dev servers.
- Other round-4 agents work at the same time; stay inside the files your task names as yours. If you must touch a file outside them, keep the edit minimal and name it in your final message.
- After pushing, check CI once (`gh pr checks N` about 12 minutes later), fix failures that are yours, then stop. Do not keep a monitor; send ONE final message.

## Evidence
A third real-model walk of that tree on 19 Nov, two learners, four days each:
- Result: `/Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning/.claude/worktrees/experience-review-1117/docs/implementation/pilot-2026-11-17/WALK3-2026-11-19.md` (read it; item numbers below refer to its «Found in this walk» list).
- Verbatim play logs: `…/experience-review-1117/docs/ops/walks/2026-11-17-experience-review/logs/walk3-integration-a1.md` (A1, German) and `walk3-integration-b1.md` (B1, English). Grep them for your items.
- Screenshots: `/private/tmp/claude-501/-Users-vincentpechstein--claude-spares-spare-8BRKzU/24979350-c568-4d32-a313-976ff75f7f81/scratchpad/i7/a1/` and `…/i7/b1/` (view with Read). Server logs: `…/i7/a1/logs/api.log`, `…/i7/b1/logs/api.log`.
- The walk databases still exist on local PostgreSQL (`psql -h localhost postgres -Atc "select datname from pg_database where datname like 'atelier_walk_179509%'"`); learners' emails: `explore-de-1795093873339-8300@example.com` (A1) and `explore-en-1795093898817-818@example.com` (B1). You may READ them (read-only queries) to see what was stored; never write to them.
- Reproduce from stored data or a fixture where you can. A fix for something you have not reproduced must say so.

## Final message (under 250 words, once)
PR URL, branch, files changed, per item: reproduced? guard failing on base / passing after; what you chose not to do; what is unverified; whether a model prompt changed.
