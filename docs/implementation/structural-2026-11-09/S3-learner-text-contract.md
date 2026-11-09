# S3 · A contract for learner-facing text: one language resolver, text by key, instruction by task kind

Written 9 Nov 2026 from `origin/main` at `ec60ae44`. Root causes #522 and #542, with #451, #196, #523, #519, #520 as children.
Implementation: Opus 5.5, medium effort, own worktree cut from `origin/main`, draft PR, nothing merges without the owner.

## The structural flaw

There is a rule for the interface language (`app/services/chrome_language.py`, mirrored in `web-frontend/lib/language-rule.ts`), but nothing forces text through it.

1. **Many resolvers.** Besides `user_chrome_language`, the server has `normalize_control_language` (`journey_contracts.py:322`), `glosses.normalize_language` (`glosses.py:42`), `learner_copy.copy_language` (`learner_copy.py:1433`), six private `_localized` helpers, three private `_language` helpers and about 22 inline `native_language[:2]` slices. They disagree on unknown codes and on the B1 switch to French. One screen guesses from the phone (`QuartierScreen.tsx:123`).
2. **Stored display text has no language.** 59 reads of the English `GrammarConcept.name` remain in 22 files (`tests/test_rule_title_522.py::_BASELINE`), and the ratchet cannot see `c.name`, `display_title` or `title_fr`. Glosses fall back en, de, fr (`glosses.py:24`; client `lib/glosses.ts` in a fixed order), so French chrome gets English. Raw gloss columns are read in `session_moment_planner.py:87`, `session_service.py:974-2368`, `progress.py:1226` and others. Achievements are French only (`achievement.py:99-200`). Bank items have English and German meanings and no French one.
3. **Text is keyed by its English rendering.** `item_bank._with_fallback_task` (`:2952`) and `learner_copy.key_for_english` look a stored English string up to find its translations.
4. **The instruction follows the item's shape.** `TASK_GOAL_KINDS` covers three transform kinds. Everything else goes through `_goal_kind`'s shape tests (`item_bank.py:2784-2817`), `grammar_items.transform_instruction` (`:630`, word count and digits) and `RECALL_GOALS` keyed by widget format (`journey_contracts.py:850-856`).
5. **Guards cover lists of files.** The register test, the copy-language test and the chrome test each scan a named set of modules; text outside the list is unguarded (for example `rehearsal.py:45`, `vocabulary.py:400`, `notifications.py:72`, `achievement.py:190`, all «vous»).

## Target structure

**A. One resolver.** `chrome_language.user_chrome_language(user)` on the server and `useChromeLanguage()` on the client are the only ways to get the interface language. The other normalisers and helpers call it or are deleted. A source guard forbids `native_language` reads outside the resolver, the settings code and the prompt builders that need the mother tongue (an explicit allowlist that may only shrink).

**B. Display text is a typed value, not a string.** Introduce `LearnerText` on the server: `{key, fields}` or `{by_language: {en, de, fr}}`, rendered at the response boundary by one function with the resolved language. Rules:
- Stored catalogue text is read only through an accessor that takes a language: `concept_title` (exists), `gloss(word, language)`, `achievement_text`, `mission_text`, `item_meaning`. Each declares its fallback. For French chrome the fallback of a gloss is the French definition, never English (owner decision 2 below).
- No accessor returns English to a `de` or `fr` learner without marking it (`language` on the payload), so the client can label it.
- `key_for_english` and `fallback_prompt_table` are removed; items store the key.
- The pydantic response models mark display fields with a `Display` annotation. One test walks every response schema and fails if a display field is filled from a raw column.

**C. The instruction is a function of the declared task kind.** Every drill item carries `task_kind` from one enum (build, fill, pick, judge, rewrite, contrast_rewrite, repair, repair_own, number_write, form_write, free_sentence, …). One table maps `task_kind` × language to the goal line. `_goal_kind`'s shape tests, `transform_instruction` and the format-keyed `RECALL_GOALS` are replaced by it. An item without a kind is not served; the generator's schema requires the field.

**D. Guards cover everything by default.** The register, three-language and no-English guards scan all of `app/` and all of `web-frontend/{pages,components,lib}`, with an explicit exemption list (dev pages, character dialogue, prompts) that may only shrink. On the client, one `defineCopy<T>()` helper replaces the per-file `Record<ControlLanguage, …>` and the `FR as …` casts; a single test checks key parity for every table, and an ESLint rule forbids literal text in JSX and in `aria-label`, `title`, `placeholder` outside copy tables.

## Stages (each its own PR)

1. One resolver and its guard (A). No learner-visible change except the screens that guessed.
2. Accessors for glosses, achievements, missions and item meanings; the 59 `name` reads to zero; schema walk test (B). Closes #451, #523.
3. `task_kind` on every item and the one goal table (C). Closes the rest of #542, #519.
4. Whole-tree guards, `defineCopy`, the ESLint rule, and the «vous» literals they find (D). Closes #196.

## Done when

- A payload test builds Home, the rule card, a recall drill, a Forge item, a word card, a Courrier objective, the Cahier row and an achievement for a `de` A1 learner, a `fr`-chrome B1 learner and an `en` learner, and asserts no English catalogue name or English gloss appears for `de` or `fr`, and every rule title equals `concept_title(concept, language)`. It fails on `ec60ae44`.
- `_BASELINE` in `tests/test_rule_title_522.py` is empty and its regex also covers `display_title` and `title_fr` reads.
- A guard builds one item of every `task_kind` in en, de and fr: only kinds whose source holds an error carry an «error» instruction, and every kind has a row in the goal table.
- The register guard finds no «vous» addressed to the learner anywhere outside the exemption list.
- `tsc` fails when a copy table lacks a language; the ESLint rule passes on the whole tree.

## Not in this package

- Translating the fiction: it stays French.
- The tu/vous of characters: that is the cast registry (#147, story-truth stack).

## Owner decisions needed

1. Bank items have no French meaning. For French chrome (B1 and above): show the task with no meaning cue, or author French cues?
2. A word with no French gloss, for a French-chrome learner: French definition, or the mother-tongue gloss with a label?
3. Achievements in en and de: translate the catalogue, or retire achievements (they are not reachable from the daily path today)?
