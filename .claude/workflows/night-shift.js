export const meta = {
  name: 'night-shift',
  description: 'Work the walk-finding queue: plan clusters, fix each in its own worktree and open a PR, verify each PR, write the morning digest. Never merges.',
  whenToUse: 'Nightly after the walks (docs/ops/improvement-loop.md). args: {date: "YYYY-MM-DD", maxFixes?: 15, maxStory?: 3, maxRootCauses?: 3, wave?: 5, backlog?: 30, queue?: "python /path/loop_queue.py"}',
  phases: [
    { title: 'Plan', detail: 'read the queue, group issues that touch the same files' },
    { title: 'Fix', detail: 'one agent per cluster in its own worktree, one wave at a time' },
    { title: 'Verify', detail: 'an independent reviewer checks each PR against the issue\'s done-when' },
    { title: 'Digest', detail: 'list the PRs that are ready to merge and write the morning digest' },
  ],
}

const date = (args && args.date) || 'unknown-date'
const MAX_FIXES = (args && args.maxFixes) || 15
const MAX_STORY = (args && args.maxStory) || 3
const MAX_ROOT = (args && args.maxRootCauses) || 3
const WAVE = (args && args.wave) || 5
const BACKLOG = (args && args.backlog) || 30
// Until the loop tooling is on main, the routine passes a copy's path in args.queue.
const Q = (args && args.queue) || 'python scripts/loop/loop_queue.py'
// Cloud sessions block GitHub GraphQL, so `gh issue …` and `gh pr …` fail there. Every
// GitHub read and write goes through ${Q} (REST via `gh api`) or the GitHub MCP tools.
const NO_GH = `Never use \`gh issue\` or \`gh pr\` (GraphQL is blocked here). Use ${Q}: \`show N\` (issue or PR with comments), \`comment N --body-file F\`, \`pr-create\`, \`pr-diff N\`, \`pr-unready N --body-file F\`, or the GitHub MCP tools.`

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
3. Read each issue and its "Done when" triage comment (\`${Q} show N\`). The done-when is your acceptance test.
4. Reproduce the bug in code or a test before fixing it. If an issue's bug is already gone on main, comment the evidence on it, run \`${Q} release N --reason "already fixed on main: <how you checked>"\`, and go on with the cluster's other issues. Return status already-fixed only when every issue in the cluster was already fixed; never leave a claimed issue in queue:working.
5. Fix it the way the surrounding code is written. ${story
    ? 'Story lane: do not rewrite prompts wholesale. Prefer a deterministic guard or validator next to the existing ones (app/services/season/canon_guards.py and friends) plus the smallest prompt change. Add a test that feeds the EXACT text quoted in the issue and asserts the guard catches or repairs it. No paid model calls in tests.'
    : 'Code lane: add the test or walk assertion (web-frontend/e2e/lib/learner-walk.mjs, node tests, or pytest) that would have caught it.'}
6. Run the focused checks for what you touched: backend \`ruff check\` + the touched pytest files (the suite runs in random order; run focused files only); frontend \`npx tsc --noEmit\`, \`npm run lint\` and the touched node tests in web-frontend. CI runs the full suite.
7. Commit with a message that says what changed for the learner. Push the branch.
8. Write the PR body to a file and open the PR with \`${Q} pr-create --branch ${branch} --title "<plain words>" --body-file <file> --label lane:${c.lane}${story ? ' --label needs-owner-review --draft' : ''}\`. The body's first two lines are \`<!-- claude-projects-attribution: {"github_login":"Pechst1"} -->\` and \`_Requested by **Vincent** · night shift ${date}_\`; then what was wrong (quote the issue), «Root cause:», what changed, how it was checked, and "Fixes ${nums}" lines.${story ? '' : ` Do not add loop:merge-ready yourself: report mergeReadyLabel true only if the cluster is size S, the diff is under 400 lines and touches none of the owner-only paths in scripts/loop/loop_queue.py (MERGE_DENY_PREFIXES). The verifier adds the label once it agrees; nobody merges but the owner.`}
9. For each issue: \`${Q} mark-pr N --pr <PR>\`.
If you cannot finish (cannot reproduce, too large, checks fail and you cannot fix them), push nothing half-done, run \`${Q} release N --reason "<one line>"\` for each claimed issue, and return status released.
Return status, pr, branch, whether the PR qualifies for loop:merge-ready, a two-line summary and the checks you ran.`
}

function verifyPrompt(c, fix) {
  return `Review night-shift PR #${fix.pr} (branch ${fix.branch}) for issues ${c.issues.map(n => '#' + n).join(', ')} in Pechst1/ConversationalLanguageLearning. Be a skeptic: you did not write it.
${NO_GH}
Read the issues and their "Done when" comments (\`${Q} show N\`) and the diff (\`${Q} pr-diff ${fix.pr}\`).
Run the tests yourself: \`git fetch -q origin ${fix.branch} && git worktree add -q --detach /tmp/verify-${fix.pr} FETCH_HEAD && cd /tmp/verify-${fix.pr} && bash scripts/loop/setup_env.sh && source $HOME/.venvs/atelier/bin/activate\`, then \`python -m pytest\` from that worktree's root on the touched and new test files. If setup_env.sh fails, say so in your verdict; never report "could not run pytest" as a code finding.
Check: does the diff meet every done-when? Is there a test that fails without the fix? Does it change behaviour beyond the issue (other screens, other languages, story canon)? Any bug introduced?
If it is not ok: write the problems to a file and run \`${Q} pr-unready ${fix.pr} --body-file <file>\` (drops loop:merge-ready, makes it a draft, comments). If it is ok, \`${Q} comment ${fix.pr} --body "<one line: what you checked>"\`${fix.mergeReadyLabel && c.lane === 'code' ? `, then \`${Q} add-label ${fix.pr} loop:merge-ready\` (only when ok; the label is what puts it on the owner's ready-to-merge list)` : ''}. Do not change the code.
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
  `In Pechst1/ConversationalLanguageLearning run \`${Q} merge-ready\` (it only lists; it never merges) and then \`${Q} digest --date ${date}\`. Return both outputs verbatim, the digest first, then a section "Ready to merge once CI is green" with the merge-ready lines.`,
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
