# WP-149 «Rien de refusé à l'écran»: what a learner sees has passed its checks

*Defined 2026-10-07 from the WP-136 read (`evidence/loss-rate-2026-10-07/`). The owner asked to define it and start it.*

## Why

WP-136 brought the loss rate to 0 of 19 generated days. Two paths now show the learner material a checker refused. These are the ones a learner would notice.

1. **Released replies that the critic flagged after the fact.**
   - Under lanes (WP-87), the tutor's grade and the voice's line are shown first. The story-lane critic reads the turn afterwards, and its refusal is only *logged* (`story_lanes.py:1284`, `reply_refused_after_release`).
   - The read logged 9 such events. Five were `false_successful_grading`: the task was marked «met» although the learner had not given what it asked for, e.g. no reason for staying. The others:
     - 1 × `reply_vs_resolution_contradiction` (shown «met», but the resolution says the letter was not answered);
     - 1 × `incompatible_demonstrated_targets` (credit for a target the learner text does not support);
     - 1 × `attributing_a_learner_choice_to_the_character`;
     - 1 × `unsupported_commitment_resolution`.
   - A false «met» is a **trust and learning-record** defect: the learner is told they did it, and the evidence ledger credits it.
2. **Pages the story critic refused twice and then served** (`living_story.py:1712`, `:1756`, `:7844`).
   - Every served page passed all the deterministic guards. The gendered drafts, for example, were blocked and never shown.
   - The critic's 10 issues fall into three groups:
     - **Storytelling (7):** «no visible change by the end of the page» or «the open obstacle is not on the page». Several pages end on the learner's task, so the change comes *after* the learner's reply. The critic may be judging the page without the turn.
     - **Register canon (1):** «Gus uses vous until T3». This is checkable deterministically.
     - **Continuity (1):** Margaux holds the letter, but the flag says `letter_trusted_to` = Marin. This is checkable deterministically against the flags.
   - Day 66 also invented «la nuit du 14 mars». The critic did not catch it.

## Principle

A day is never lost (WP-136 stays), but **a correctness defect is never served**:
- **Correctness** must be fixed before the learner sees anything: grading, credit, canon register, flag contradictions, departed cast, gendered agreement.
- **Storytelling** can be served with a logged override: whether the page is dramatically weak.

## Scope

**A. Grading before release (reply lanes)**
1. A deterministic **met-gate** in the tutor lane, before the response is returned.
   - «met» requires the tutor's evidence quotes to occur in the learner's text, after quote folding (`ios-smart-quote-normalization`).
   - It also requires that every required slot of the objective is evidenced. Slots come from the task's own contract (e.g. «dites pourquoi» needs a reason clause), via `answer_acceptance` / `journey_contracts` where those exist.
   - Otherwise the gate downgrades to `partial`, with the existing partial feedback.
   - `demonstrated_target_ids` keeps only targets supported by the learner text.
2. **After release:** when the story-lane critic still flags `false_successful_grading` or `incompatible_demonstrated_targets`, the shown line stays (never retracted), but the **learning record is corrected**:
   - the outcome is stored as partial;
   - credit is withdrawn from the evidence ledger / SRS;
   - the story lane writes an ending consistent with a partial.
   - Record it as an event.
3. **Coherence:** the resolution the story lane writes must agree with the outcome that was shown (`reply_vs_resolution_contradiction`). The lane is given the released outcome as fixed input.

**B. Pages: correctness becomes hard, storytelling stays soft**
1. Two new deterministic guards in the guard chain (no new art, no model calls):
   - `canon_register`: the season's per-character tu/vous canon by tentpole, e.g. Gus vous until T3;
   - `flag_contradiction`: objects and holders against the flags, e.g. `s1.letter_trusted_to`.

   Like the existing guards, they block a draft and give retry feedback.
2. **Classify critic issues** as correctness or storytelling. A critic refusal that is only storytelling keeps today's behaviour (served with a logged override). A refusal that names a correctness issue is not served: the day falls to the existing re-read or bridge path (WP-124b).
3. **Critic calibration:** give the critic the page *with* its learner-turn structure, so a page that ends on the learner's task is judged with the planned resolution.
   - The target is fewer false «no visible change» refusals. Measure it on the recorded WP-136 drafts offline: the refusals' `draft` digests are stored.
4. **Invented canon dates** (out of scope to solve; record only): add «la nuit du 14 mars» as a negative example in the director's `_must_not` list. A full date-canon check is a later package.

**C. Measurement**
- `scripts/pilot_digest.py`: the share of served overrides by class, and the count of after-release grading corrections.
- Offline replay: a test that feeds the stored WP-136 refusal records through the new guards and gate, with no paid calls.

## Acceptance

- **Fake-provider tests:**
  - a «met» without evidence is downgraded before release;
  - a post-release `false_successful_grading` corrects the ledger and the ending;
  - a Gus-tu draft before T3 and a Margaux-holds-the-letter draft are blocked;
  - a storytelling-only critic refusal is still served and logged;
  - a correctness critic refusal falls to the re-read.
- Full suites green, with no regression in the walk checks.
- **Paid confirmation (owner OK, about US$0.30):** re-run A1 1–10 and B1 25–32. Pass: 0 after-release `false_successful_grading`, 0 correctness overrides served, loss rate still ≤ 2 of about 8 first days.

## Not in scope

- Retracting text the learner already saw.
- New UI.
- A full date-canon checker.
