export const meta = {
  name: 'night-shift',
  description: 'Work the walk-finding queue: plan clusters, fix each in its own worktree and open a PR, verify each PR, write the morning digest. Never merges.',
  whenToUse: 'Nightly after the walks (docs/ops/improvement-loop.md). args: {date: "YYYY-MM-DD", maxFixes?: 8, maxStory?: 2, wave?: 4, queue?: "python /path/loop_queue.py"}',
  phases: [
    { title: 'Plan', detail: 'read the queue, group issues that touch the same files' },
    { title: 'Fix', detail: 'one agent per cluster in its own worktree, one wave of at most 4 at a time' },
    { title: 'Verify', detail: 'an independent reviewer checks each PR against the issue\'s done-when' },
    { title: 'Digest', detail: 'list the PRs that are ready to merge and write the morning digest' },
  ],
}

const date = (args && args.date) || 'unknown-date'
const MAX_FIXES = (args && args.maxFixes) || 8
const MAX_STORY = (args && args.maxStory) || 2
const WAVE = (args && args.wave) || 4
// Until the loop tooling is on main, the routine passes a copy's path in args.queue.
const Q = (args && args.queue) || 'python scripts/loop/loop_queue.py'

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

1. Count open PRs from night-shift branches: \`gh pr list --search "head:claude/night-" --state open --json number\`. If there are 10 or more, plan NO new fixes: return empty clusters and list every ready issue in skipped with reason "PR backlog is full: the owner merges or closes first".
2. Run \`${Q} ready\` and read each issue (body and the latest "Done when" triage comment): \`gh issue view N --comments\`.
3. For each issue find the files a fix will most likely touch (grep the repo; the issue often names them).
4. Group issues whose likely files overlap into one cluster, so no two clusters edit the same file tonight. A cluster is one lane (code or story). Keep clusters small: at most 3 issues.
5. Order clusters: severity (sev:blocker, high, medium, low), then size S before M. Keep at most ${MAX_FIXES} clusters, of which at most ${MAX_STORY} are lane story. Put everything you leave out in skipped with the reason (cap, overlap, unclear, needs a device or the owner).
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

1. Start from the latest main: \`git fetch -q origin && git checkout -B ${branch} origin/main\`.
2. Claim each issue: \`${Q} claim N --run night-${date}\`. If a claim fails, drop that issue.
3. Read each issue and its "Done when" triage comment (\`gh issue view N --comments\`). The done-when is your acceptance test.
4. Reproduce the bug in code or a test before fixing it. If the bug is already gone on main, comment the evidence on the issue, run \`${Q} release N --reason "already fixed on main: <how you checked>"\`, and return status already-fixed.
5. Fix it the way the surrounding code is written. ${story
    ? 'Story lane: do not rewrite prompts wholesale. Prefer a deterministic guard or validator next to the existing ones (app/services/season/canon_guards.py and friends) plus the smallest prompt change. Add a test that feeds the EXACT text quoted in the issue and asserts the guard catches or repairs it. No paid model calls in tests.'
    : 'Code lane: add the test or walk assertion (web-frontend/e2e/lib/learner-walk.mjs, node tests, or pytest) that would have caught it.'}
6. Run the focused checks for what you touched: backend \`ruff check\` + the touched pytest files (the suite runs in random order; run focused files only); frontend \`npx tsc --noEmit\`, \`npm run lint\` and the touched node tests in web-frontend. CI runs the full suite.
7. Commit with a message that says what changed for the learner. Push the branch.
8. Open the PR with \`gh pr create\`: title in plain words, body = what was wrong (quote the issue), what changed, how it was checked, and "Fixes ${nums}" lines. Labels: lane:${c.lane}${story ? ', needs-owner-review, and open it as --draft' : ''}.${story ? '' : ` Add loop:merge-ready only if the cluster is size S, the diff is under 400 lines and touches none of the owner-only paths in scripts/loop/loop_queue.py (MERGE_DENY_PREFIXES). The label only marks it for the owner's quick review; nobody merges it but the owner.`}
9. For each issue: \`${Q} mark-pr N --pr <PR>\`.
If you cannot finish (cannot reproduce, too large, checks fail and you cannot fix them), push nothing half-done, run \`${Q} release N --reason "<one line>"\` for each claimed issue, and return status released.
Return status, pr, branch, whether you set loop:merge-ready, a two-line summary and the checks you ran.`
}

function verifyPrompt(c, fix) {
  return `Review night-shift PR #${fix.pr} (branch ${fix.branch}) for issues ${c.issues.map(n => '#' + n).join(', ')} in Pechst1/ConversationalLanguageLearning. Be a skeptic: you did not write it.
Read the issues and their "Done when" comments (\`gh issue view N --comments\`) and the diff (\`gh pr diff ${fix.pr}\`).
Check: does the diff meet every done-when? Is there a test that fails without the fix? Does it change behaviour beyond the issue (other screens, other languages, story canon)? Any bug introduced?
If it is not ok: \`gh pr edit ${fix.pr} --remove-label loop:merge-ready\`, \`gh pr ready ${fix.pr} --undo\` (make it a draft), and \`gh pr comment ${fix.pr}\` with the problems. If it is ok, comment one line saying what you checked. Do not change the code.
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
