# Implementation review and next steps — 2026-09-06

Reviewed commit `b0f3602` (`feat: Atelier V2 daily journey — functional milestone`). The worktree was clean at inspection. This is a focused independent review, not a repeat of all WP-12 checks. No production code, account data, flags, or deployment was changed.

**Recommendation:** complete a focused correctness and continuity pass, then integrate the Claude UI. Design access and state mapping can proceed alongside the fixes. Do not enable a pilot based on the existing conditional-GO label alone.

## Independently verified

| Check | Current result |
|---|---|
| `pytest` on `test_journey_end_to_end.py`, `test_journey_capabilities.py`, `test_provider_cost_guard.py` | 89 collected: 88 passed, 1 expected failure (D-1b) |
| Frontend `test:journey`, `test:recovery`, `type-check` | Passed |
| Two additional conversation regression probes | Both failed; new findings R-1/R-2 below |
| `ruff check . --output-format concise` | 12 findings; 11 documented baseline findings plus a new unused `day1_scene` in `tests/test_journey_end_to_end.py:674` |
| Capability recap implementation | Uses the shared rubric in `DailyJourneyService._journey_capability_evidence`; objective-level evidence exists in `journey_learning` |

All review probes used pytest's isolated SQLite fixtures and fake providers. No paid model calls were made. The temporary probe module was removed from the repository after execution. Existing reported PostgreSQL, full-suite, web-build, and browser results were read but not independently rerun in this review.

## R-1 — P1: negated intent earns a successful outcome

Location: `app/services/journey_conversation.py`, `_signals`, `_INTENT_TESTS`, and `evaluate_response`.

Reproduction: resolve the authored A1 `order_at_cafe` brief and evaluate this unassisted text on turn zero with providers disabled:

> Je ne veux pas de café. Je ne veux pas rester en terrasse.

Actual result:

```text
outcome: met
reply: Un café en terrasse, très bien. Je vous apporte ça, la terrasse est couverte.
consequence: served_at_terrace
callback: un café en terrasse
```

The grader treats mentions of a drink/place as positive intent. It therefore contradicts the learner and supplies a false successful result to downstream evidence logic. This is present in the authored path; enabling a model does not fix it because the deterministic grader decides success first.

**Required fix:** handle negation, refusal, correction of a previous choice, and ambiguous alternatives across turns. Preserve acceptance of legitimate short beginner answers and paraphrases. Clarify when uncertain. Add regressions for all three scenario families and an API-level check that rejected/ambiguous choices cannot mint successful capability evidence or completion rewards. Do not solve this with one special-case string or by rejecting all sentences containing `pas`.

## R-2 — P1 before model enablement: an allowed model outcome can reverse the learner's choice

Location: `app/services/journey_conversation.py:1647`, after `_model_reply`; parser at `_parse_model_reply` checks schema/allowed-key membership but not consistency with the grounded decision.

Reproduction: A1 learner says:

> Un thé en terrasse, s'il vous plaît.

Mock `_conversation_llm()` with a client returning this valid response (no network call):

```json
{"reply_fr":"Très bien, je vous le prépare à emporter.","outcome_key":"takeaway"}
```

Actual result: `met`, `takeaway`, callback `un thé à emporter`. The model's allowed key replaces the grounded `served_at_terrace` choice.

**Required fix:** the model must not override an established learner choice merely because another key is allowed. Reject conflicting output and use a coherent bounded retry/fallback. Validate reply and consequence together; keeping the correct key while displaying the conflicting takeaway reply is still wrong. Add tests for conflicting allowed keys, unsupported keys, multi-turn choices, and the final recap/ledger. Retain existing schema and arbitrary-memory-field protections.

## R-3 — incomplete requirement: next-day continuity (existing D-1b)

The existing strict `xfail` reproduced. A callback is produced at completion but is not used in a later scene. Some authored side scenes have no serial-thread binding and return `applied=False`, so implementation must handle that case deliberately too.

This is central to the accepted personal-world concept. Scenario rotation alone does not satisfy it.

**Required fix:** retrieve learner-owned, eligible prior consequences through the existing records/state; use them in a coherent later interaction. Respect character knowledge, current scene, superseded state, and content version. Avoid advancing unrelated serial episodes or adding another memory store. Test a two-day journey with a controllable clock, another learner's isolation, an unbound authored scene, and a case where no callback is appropriate. Assert semantic grounding and provenance rather than only verbatim insertion of a stored phrase. Remove the expected-failure marker only when the requirement works.

## Follow-up sequence and ownership

1. **Conversation correctness owner (WP-05/06):** fix R-1 and R-2, including evidence and API regressions. Both touch the same conversation module; keep one implementation owner.
2. **Continuity owner (WP-03/06):** implement R-3 after acquiring any shared conversation/serial leases. Content-side preparation can happen independently. Integrate after corrected consequences are available.
3. **Integration/QA owner:** reconcile STATUS/QA evidence against the actual committed revision, repair CI failures, and fix test tooling. The old capability “in progress” section is stale; do not implement a second fix. The 12th Ruff finding is new, so do not label all lint failures pre-existing. Revalidate affected functional checks after integration.
4. **UI owner:** obtain an accessible export/authenticated view of the selected Claude artifact and map real application states. Then implement WP-01 → WP-07 visual → WP-08/WP-09 visual, retaining the working controllers and APIs. The older `docs/design-reference/` files are not automatically the selected design.

Use one integration lead with up to three bounded subagents if supported, and exclusive file leases. Do not dispatch overlapping conversation/serial edits simultaneously. Correctness fixes and design mapping may run together; final visual polish is not a substitute for closing the functional gaps.

## Verification work before pilot readiness

- **Green assembled CI:** fix the baseline grammar-notebook denominator, duplicate legacy migration downgrade, and lint findings. Baseline status explains origin; it does not make a red release gate pass. Run migration tests only on disposable databases with representative legacy rows.
- **Safe capture tooling:** `capture-mobile-states.mjs` still defaults to port 8000 and its seeder can target a different database from the API. Require explicit authenticated-capture targets and verify API/seeder alignment; preserve CI's public, no-auth static capture mode.
- **Auth hydration gap:** the sign-in form still has no native-safe submit behavior; the prior QA report reproduced credentials entering a GET URL before hydration. Fix and test this before external use.
- **Bounded real-provider review:** model reply/content quality and real voice transcription have not been validated. Use explicit provider settings, throwaway accounts, recorded model/prompt versions, and a bounded cost budget. Keep pytest isolated from live keys. The prior provider-cost incident needs its separate owner follow-up; this review made no billable calls.
- **Native/build/browser checks:** run build validation using the existing documented CI or simulator configuration; a production API host is not required merely to compile (CI already uses its explicit placeholder override). Real voice, device lifecycle, keyboard, safe-area, and permission checks still require an appropriate runnable environment. Walk the full recap, keepsake, and capability UI in the browser.
- **Final design and learner checks:** after Claude integration, run responsive/theme/accessibility/native verification and the prepared five-learner study. Keep unperformed human/device checks pending.

The feature remains default-off. A successful stabilization pass should produce a tested foundation ready for final UI integration, not an automatic deployment or pilot enablement.
