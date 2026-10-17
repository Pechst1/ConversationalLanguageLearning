export const meta = {
  name: 'night-shift',
  description: 'Work the walk-finding queue: plan clusters, fix each in its own worktree and open a PR, verify each PR (its tests must fail without the fix), write the morning digest. Merges only with autoMerge.',
  whenToUse: 'Nightly after the walks (docs/ops/improvement-loop.md). args: {date: "YYYY-MM-DD", maxFixes?: 15, maxStory?: 3, maxRootCauses?: 3, wave?: 5, backlog?: 30, autoMerge?: false, maxMerges?: 4, queue?: "python /path/loop_queue.py"}',
  phases: [
    { title: 'Plan', detail: 'read the queue, group issues that touch the same files' },
    { title: 'Fix', detail: 'one agent per cluster in its own worktree, one wave at a time' },
    { title: 'Verify', detail: 'an independent reviewer checks each PR against the issue\'s done-when' },
    { title: 'Digest', detail: 'list (or, with autoMerge, merge) the PRs that are ready and write the morning digest' },
  ],
}

const date = (args && args.date) || 'unknown-date'
const MAX_FIXES = (args && args.maxFixes) || 15
const MAX_STORY = (args && args.maxStory) || 3
const MAX_ROOT = (args && args.maxRootCauses) || 3
const WAVE = (args && args.wave) || 5
const BACKLOG = (args && args.backlog) || 30
// Owner switch. Off: the digest lists the ready code fixes and the owner merges. On: the digest
// merges them (at most maxMerges, only onto a green main), CI runs on main and Render deploys.
const AUTO_MERGE = !!(args && args.autoMerge)
const MAX_MERGES = (args && args.maxMerges) || 4
// Until the loop tooling is on main, the routine passes a copy's path in args.queue.
const Q = (args && args.queue) || 'python scripts/loop/loop_queue.py'
// Night shift 17 Oct: the fixer for #197 only loosened the walk driver, and its PR passed as a
// fix. A fix is proven by scripts/loop/red_green.py: the PR's tests fail with every non-test
// change put back to main and pass with it. The fixer runs it before opening a PR and the
// verifier runs it again; nothing without a proven (or read-and-accepted weak) result is ready.
const RED_GREEN = 'python scripts/loop/red_green.py --base origin/main'
// Cloud sessions block GitHub GraphQL, so `gh issue …` and `gh pr …` fail there. Every
// GitHub read and write goes through ${Q} (REST via `gh api`) or the GitHub MCP tools.
const NO_GH = `Never use \`gh issue\` or \`gh pr\` (GraphQL is blocked here). Use ${Q}: \`show N\` (issue or PR with comments), \`comment N --body-file F\`, \`pr-create\`, \`pr-diff N\`, \`pr-reject N --body-file F\`, or the GitHub MCP tools.`

const PLAN = {
  type: 'object',
  properties: {
    openLoopPrs: { type: 'integer' },
    clusters: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          issues: { type: 'array', items: { type: 'integer' } },
          lane: { type: 'string', enum: ['code', 'story'] },
          size: { type: 'string', enum: ['S', 'M'] },
          title: { type: 'string' },
          rootCause: { type: 'boolean' },
          files: { type: 'array', items: { type: 'string' } },
        },
        required: ['issues', 'lane', 'size', 'title', 'files'],
      },
    },
    skipped: {
      type: 'array',
      items: {
        type: 'object',
        properties: { issue: { type: 'integer' }, reason: { type: 'string' } },
        required: ['issue', 'reason'],
      },
    },
  },
  required: ['openLoopPrs', 'clusters', 'skipped'],
}

const FIX = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['pr', 'released', 'already-fixed'] },
    pr: { type: 'integer' },
    branch: { type: 'string' },
    mergeReadyLabel: { type: 'boolean' },
    summary: { type: 'string' },
    checks: { type: 'string' },
  },
  required: ['status', 'summary'],
}

const VERDICT = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    problems: { type: 'array', items: { type: 'string' } },
  },
  required: ['ok', 'problems'],
}

phase('Plan')
const plan = await agent(
  `You plan tonight's night shift for L'Atelier (repo Pechst1/ConversationalLanguageLearning, date ${date}).
Rules: docs/ops/improvement-loop.md, sections "The queue" and "The night shift". Never push to main, never merge, never deploy.

${NO_GH}

1. Count open PRs from night-shift branches: \`${Q} open-night-prs\`. If there are ${BACKLOG} or more, plan NO new fixes: return empty clusters and list every ready issue in skipped with reason "PR backlog is full: the owner merges or closes first". Otherwise plan at most ${BACKLOG} minus that count clusters.
2. Run \`${Q} ready\` and read each issue (body and the latest "Done when" triage comment): \`${Q} show N\`.
3. Root causes first: issues labelled \`root-cause\` each describe one structural flaw with child findings. Make each of the top ${MAX_ROOT} (severity order) its own cluster with rootCause true, holding the root-cause issue first and then its children that are queue:ready. Its children are not planned anywhere else.
4. For each other issue find the files a fix will most likely touch (grep the repo; the issue often names them).
5. Group issues whose likely files overlap into one cluster, so no two clusters edit the same file tonight (root-cause clusters included). A cluster is one lane (code or story). Keep clusters small: at most 3 issues, except root-cause clusters.
6. Order clusters: root causes, then severity (sev:blocker, high, medium, low), then size S before M. Keep at most ${MAX_FIXES} clusters, of which at most ${MAX_STORY} are lane story. Put everything you leave out in skipped with the reason (cap, overlap, unclear, needs a device or the owner).
Return the plan.`,
  { label: 'plan', phase: 'Plan', schema: PLAN },
)

if (!plan) {
  log('Planning failed; nothing fixed tonight.')
  return { date, plan: null }
}
log(`Open night-shift PRs: ${plan.openLoopPrs}. Clusters: ${plan.clusters.length}; skipped: ${plan.skipped.length}.`)
for (const s of plan.skipped) log(`skipped #${s.issue}: ${s.reason}`)

function fixPrompt(c) {
  const nums = c.issues.map(n => '#' + n).join(', ')
  const branch = `claude/night-${date}-${c.issues[0]}`
  const story = c.lane === 'story'
  return `You are a night-shift fixer for L'Atelier (repo Pechst1/ConversationalLanguageLearning). Fix ${nums} ("${c.title}"). Likely files: ${c.files.join(', ')}.
You are in your own git worktree. Never push to main, never merge, never deploy, never touch another cluster's issues.
${NO_GH}
Vincent's rule: fix the flaw at the structural level, not just the plumbing. Before patching, name why the code allowed the bug; if the cause is shared with other places, fix it there too or add it to the matching \`root-cause\` issue. The PR body has a «Root cause:» line.${c.rootCause ? `
This cluster is ROOT CAUSE ${'#' + c.issues[0]}: confirm the mechanism in the code, change it so the whole class of bug cannot happen, add the guard test its Done when names, and check every child against the change. When the whole mechanism is larger than one reviewable PR, ship the first self-contained stage and post the remaining stages as a checklist comment on ${'#' + c.issues[0]}. Use "Fixes #N" only for children that are fully fixed and "Part of #N" for the rest.` : ''}

1. Start from the latest main: \`git fetch -q origin && git checkout -B ${branch} origin/main\`. Then \`bash scripts/loop/setup_env.sh && source $HOME/.venvs/atelier/bin/activate\` (on a main without that script, copy it the way ${Q} was copied). Run pytest as \`python -m pytest\` from the worktree root.
2. Claim each issue: \`${Q} claim N --run night-${date}\`. If a claim fails, drop that issue.
3. Read each issue and its "Done when" triage comment (\`${Q} show N\`). The done-when is your acceptance test. If a comment says «Night shift: attempt N … failed review», an earlier PR was rejected: read the reviewer's notes there and the earlier branch (\`git fetch origin <branch>\`), keep what the reviewer accepted and fix what it rejected.
4. Test first. Write the test that shows the bug (step 5 says which kind) and run it on the unfixed code. It must FAIL by an assertion that describes the bug, not by an import error or a missing name. Keep that output: it goes in the PR body under «Fails without the fix:». If you cannot make a test fail, you have not reproduced the bug: do not fix by guesswork, release the issue with what you tried. A bug only the browser walk shows still gets a unit or API test of the mechanism you found; loosening the walk driver (longer timeouts, swallowed errors) is never a fix. If an issue's bug is already gone on main, comment the evidence on it, run \`${Q} release N --reason "already fixed on main: <how you checked>"\`, and go on with the cluster's other issues. Return status already-fixed only when every issue in the cluster was already fixed; never leave a claimed issue in queue:working.
5. Fix it the way the surrounding code is written. ${story
    ? 'Story lane: do not rewrite prompts wholesale. Prefer a deterministic guard or validator next to the existing ones (app/services/season/canon_guards.py and friends) plus the smallest prompt change. Add a test that feeds the EXACT text quoted in the issue and asserts the guard catches or repairs it. No paid model calls in tests.'
    : 'Code lane: add the test or walk assertion (web-frontend/e2e/lib/learner-walk.mjs, node tests, or pytest) that would have caught it.'}
6. Prove it: commit, then run `${RED_GREEN}` from the worktree root. It reverts your non-test changes to main, runs your changed tests (they must fail), restores them (they must pass). Continue only on PROVEN; on WEAK, make the test assert the behaviour rather than a new name; on RED-PASSES or NO-TEST your test does not test the bug, go back to 4. List an issue under "Fixes #N" only when a test proven here covers that issue; otherwise "Part of #N".
7. Run the focused checks for what you touched: backend \`ruff check\` + the touched pytest files (the suite runs in random order; run focused files only); frontend \`npx tsc --noEmit\`, \`npm run lint\` and the touched node tests in web-frontend. CI runs the full suite.
8. Commit with a message that says what changed for the learner. Push the branch.
9. Write the PR body to a file and open the PR with \`${Q} pr-create --branch ${branch} --title "<plain words>" --body-file <file> --label lane:${c.lane}${story ? ' --label needs-owner-review --draft' : ''}\`. The body's first two lines are \`<!-- claude-projects-attribution: {"github_login":"Pechst1"} -->\` and \`_Requested by **Vincent** · night shift ${date}_\`; then what was wrong (quote the issue), «Root cause:», what changed, «Fails without the fix:» with the failing output from step 4, the red/green result line from step 6, how else it was checked, and the "Fixes #N" / "Part of #N" lines.${story ? '' : ` Do not add loop:merge-ready yourself: report mergeReadyLabel true only if the cluster is size S, the diff is under 400 lines and touches none of the owner-only paths in scripts/loop/loop_queue.py (MERGE_DENY_PREFIXES). The verifier adds the label once it agrees; nobody merges but the owner.`}
10. For each issue: \`${Q} mark-pr N --pr <PR>\`.
If you cannot finish (cannot reproduce, too large, checks fail and you cannot fix them), push nothing half-done, run \`${Q} release N --reason "<one line>"\` for each claimed issue, and return status released.
Return status, pr, branch, whether the PR qualifies for loop:merge-ready, a two-line summary and the checks you ran.`
}

function verifyPrompt(c, fix) {
  return `Review night-shift PR #${fix.pr} (branch ${fix.branch}) for issues ${c.issues.map(n => '#' + n).join(', ')} in Pechst1/ConversationalLanguageLearning. Be a skeptic: you did not write it.
${NO_GH}
Read the issues and their "Done when" comments (\`${Q} show N\`) and the diff (\`${Q} pr-diff ${fix.pr}\`).
Run the tests yourself: \`git fetch -q origin ${fix.branch} && git worktree add -q --detach /tmp/verify-${fix.pr} FETCH_HEAD && cd /tmp/verify-${fix.pr} && bash scripts/loop/setup_env.sh && source $HOME/.venvs/atelier/bin/activate\`, then \`python -m pytest\` from that worktree's root on the touched and new test files. If setup_env.sh fails, say so in your verdict; never report "could not run pytest" as a code finding.
Prove the fix yourself, do not trust the PR body: in that worktree run `${RED_GREEN}`. PROVEN is required for ok. WEAK is ok only if you read the test and it asserts the bug's behaviour, not just that a new name exists. RED-PASSES, NO-TEST or GREEN-FAILS is not ok. Check that each issue listed under "Fixes #N" has its own failing-then-passing test in that output; an issue fixed only by a walk-driver change or without a test is not fixed.${c.lane === 'story' ? ' Story lane: also run `python -m pytest tests/test_prompt_regression.py`; a changed prompt snapshot must be explained in the PR body.' : ''}
Check: does the diff meet every done-when? Does it change behaviour beyond the issue (other screens, other languages, story canon)? Any bug introduced?
If it is not ok: write the problems to a file, each with the exact input that fails and what the fix must do instead, and run \`${Q} pr-reject ${fix.pr} --body-file <file>\`. It closes the PR, labels it loop:failed-verify, and gives its issues back to the queue with your notes so the next night starts from them (after two failed attempts the issue goes to the owner). If it is ok, \`${Q} comment ${fix.pr} --body "<the red/green result line, then one line: what else you checked>"\`${fix.mergeReadyLabel && c.lane === 'code' ? `, then \`${Q} add-label ${fix.pr} loop:merge-ready\` (only when ok; the label is what puts it on the owner's ready-to-merge list)` : ''}. Do not change the code.
Return ok and the problems you found (empty when ok).`
}

const waves = []
for (let i = 0; i < plan.clusters.length; i += WAVE) waves.push(plan.clusters.slice(i, i + WAVE))

const results = []
for (let w = 0; w < waves.length; w++) {
  log(`Wave ${w + 1} of ${waves.length}: ${waves[w].map(c => c.issues.map(n => '#' + n).join('+')).join(', ')}`)
  const wave = await pipeline(
    waves[w],
    c => agent(fixPrompt(c), {
      label: `fix ${c.issues.map(n => '#' + n).join('+')}`,
      phase: 'Fix',
      schema: FIX,
      isolation: 'worktree',
      // Reproducing first and proving red/green is the careful part; the verifier already ran at high.
      effort: 'high',
    }),
    (fix, c) => {
      if (!fix || fix.status !== 'pr' || !fix.pr) return { cluster: c, fix, verdict: null }
      return agent(verifyPrompt(c, fix), { label: `verify #${fix.pr}`, phase: 'Verify', schema: VERDICT, effort: 'high' })
        .then(verdict => ({ cluster: c, fix, verdict }))
    },
  )
  results.push(...wave.filter(Boolean))
}

phase('Digest')
const digest = await agent(
  AUTO_MERGE
    ? `In Pechst1/ConversationalLanguageLearning run \`${Q} merge-ready --merge --max ${MAX_MERGES}\` (it merges only verified, small, green code fixes outside the owner-only paths, and nothing while main's CI is red) and then \`${Q} digest --date ${date}\`. Return both outputs verbatim, the digest first, then a section "Merged tonight" with the merge lines and the reasons the others wait.`
    : `In Pechst1/ConversationalLanguageLearning run \`${Q} merge-ready\` (it only lists; it never merges) and then \`${Q} digest --date ${date}\`. Return both outputs verbatim, the digest first, then a section "Ready to merge once CI is green" with the merge-ready lines.`,
  { label: 'digest', phase: 'Digest', effort: 'low' },
)

return {
  date,
  skipped: plan.skipped,
  results: results.map(r => ({
    issues: r.cluster.issues,
    lane: r.cluster.lane,
    status: r.fix ? r.fix.status : 'agent-died',
    pr: r.fix ? r.fix.pr : null,
    mergeReady: !!(r.fix && r.fix.mergeReadyLabel && r.verdict && r.verdict.ok),
    verified: r.verdict ? r.verdict.ok : null,
    problems: r.verdict ? r.verdict.problems : [],
    summary: r.fix ? r.fix.summary : '',
  })),
  digest,
}
