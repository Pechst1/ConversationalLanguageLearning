# WP-46 — Réglages in the learner's language — 2026-09-17

## The decision

The app's chrome is French on every **product** screen. That is WP-43's rule
(`CHROME_KEYS` in `journey-copy.ts`): the learner came to read a French
publication, and the words on its furniture — «Séance», «Lexique», «Continuer»
— are part of what they came for.

Réglages is the exception the owner carved out on 2026-09-17, and the reason is
that it is not a product screen. It is the **administrative surface**: where a
learner changes the address they sign in with, decides whether the story
addresses them in the feminine, reads what «suppression définitive» removes,
and finds out why a save was refused. None of that teaches French, and all of
it has to be understood *before* the learner acts. A learner who cannot yet
read «Les modifications n’ont pas pu être classées» must still be able to run
their own account.

So Réglages follows the account's `native_language`: English for the current
learner, German for a German native, French for a French native.

## What was built

| File | What it holds |
|---|---|
| `web-frontend/lib/settings-copy.ts` | `settingsCopy(language)` — the whole screen in `en` / `de` / `fr`, 122 keys. Section titles, row labels and hints, button labels, segmented-control options, field labels, placeholders, toasts, validation messages, both confirmations, the page `<title>`, the WP-43 «Signaler un problème» row, and the WP-25 / WP-31 / WP-35 Bilan / Répétition / Dossier rows. Also `resolveSettingsLanguage(native, control?)`. |
| `web-frontend/lib/settings-copy.test.js` | 11 node tests: identical keys across the three tables, no empty strings, unknown language → English (never French), locale tags (`de-DE`, `fr_CA`, `  fr  `) resolve to their base, French kept verbatim from the artboard, and no key left untranslated between French and German. Wired as `npm run test:settings-copy` and into the CI node block. |
| `web-frontend/pages/settings.tsx` | Renders through the table. |
| `tests/test_settings_language.py` | 7 source-scan tests: the table exists and is complete, the page renders through it, the language choice cannot flicker, and **no French sentence is left in the page**. |

## The language choice, and why it cannot flicker

```ts
const [nativeLanguageKnown, setNativeLanguageKnown] = useState(false);
const copyLanguage = resolveSettingsLanguage(
    nativeLanguageKnown ? settings.nativeLanguage : null,
);
const copy = settingsCopy(copyLanguage);
```

`defaultSettings.nativeLanguage` is `'de'` — a *payload* default, not a claim
about this learner. Seeding the copy language from it would render German (or,
worse, any French default) before the account answered and swap it afterwards.
So the screen holds the honest value until `api.getSettings()` returns:
`nativeLanguageKnown` is false, `resolveSettingsLanguage(null)` answers `'en'`,
and the skeleton reads English. French is rendered **only** when the learner's
own language is French.

`resolveSettingsLanguage` falls through native → control → English. A Spanish
native gets English, not the French they cannot yet read — English is the floor,
never a half-translated screen. The design-system root takes the same
`copyLanguage`, so the shared chrome around the copy cannot disagree with it.
When the learner changes «Langue d'appui» in the dropdown, the screen follows
immediately.

## What stayed as it was

Values are not copy:

- **CEFR codes** — `A1`, `B2.1`. `proficiencyLevels(copy)` interpolates the code
  and translates only the word beside it: `A1 · Beginner` / `A1 · Anfang` /
  `A1 · Début`.
- **The learner's name, their email address, the reminder time, the XP number,
  the TTS speed** — printed exactly as the account holds them.
- **`default_vocab_direction` values** (`fr_to_de`, `en_to_fr`, `mixed`) — the
  schema's values. `vocabDirectionValues()` is now separate from
  `vocabDirectionOptions(native, copy)` so the labels could be translated
  without touching what the save payload carries. The 422-for-English-natives
  fix from 2026-09-04 is unchanged.
- **The interest topic presets** (`technologie`, `travail`, …) — these are the
  *values* stored in `interests` and sent to the server, which uses them to
  select French articles. Translating the chip would change what is stored. See
  open items.

## The re-pinned tests

Six suites pinned French strings on the settings page. None was weakened; each
was re-pinned in two halves — the page is pinned on the **resolver key** it
renders, and the sentence is pinned in **all three languages** where it now
lives.

| Suite | Was | Now |
|---|---|---|
| `test_core_mobile_edge_flows.py` | Eight French sentences inline, incl. `confirm('Supprimer définitivement ce compte` | The `confirm(copy.confirm_delete_account, …)` / `confirm(copy.confirm_signout_all)` call sites, plus the three wordings of each safety sentence in the copy table |
| `test_placement_onboarding_surface.py` | `"Bilan de niveau" in page` | `copy.row_placement` + `Level check` / `Einstufung` / `Bilan de niveau` |
| `test_dossier_surface.py` | `"Votre dossier" in page` | `copy.row_dossier` + `Your file` / `Ihre Akte` / `Votre dossier` |
| `test_frontend_pilot_experience.py` | `"Recevoir l’édition sur cet appareil"` | `copy.card_device_title` + the three titles |
| `test_pilot_work_packages.py` | `"L’administration"`; the duplicate-label counts | `{copy.page_title}` + the artboard title in the table; the counts moved onto the four distinct keys |
| `test_wp37_hooks.py` | `"Écouter d’abord" in settings` | `copy.row_listen_first` + `Listen first` / `Zuerst hören` / `Écouter d’abord` |

The safety guard's requirement that the two irreversible actions go through a
literal `confirm('…')` call site is kept: the call sites are still there, and
the test now reads them by their key.

## The leftover scan

`test_no_french_sentence_is_left_in_the_page` strips comments and fails on any
line carrying a French letter or guillemet that is not an allowed topic value or
the product's own name. Two narrower scans back it up: no
`label|hint|desc|placeholder|aria-label|pendingLabel="…French…"` literal, and no
French sentence inside `toast.*(…)`, `confirm(…)` or `setSaveMessage(…)`.

This exists because a leftover French sentence is *invisible* to a reviewer who
reads French — the page still looks right. Mutation-checked: injecting
`hint="Votre dossier est à jour."` fails two of the three scans.

## Verification

- `npm run type-check`, `npm run lint`, `next build` — all clean.
- `npm run test:settings-copy` — 11/11. All 19 frontend node suites green.
- `pytest` on the seven touched/related source-scan suites — 98 passed.

**Not walked in the browser.** The backend fake-provider harness was up on
8010 and the frontend started on 3000, but `/settings` is auth-gated and the
recorded harness recipe reaches it by signing in with a password, which this
session does not do. This matches the standing note that the preview auth gate
blocks authed routes and such changes are verified by `tsc` / lint / build and
static tests instead. A human QA pass on the three languages — the German QA
account, and a fresh `native_language=en` one — is still owed.

## Open items

1. **The interest topic presets are French values.** An English learner sees
   `économie`, `santé`, `cuisine` as chips because those strings are what the
   server stores and reasons over. Fixing this properly means a value/label
   split on the backend's `interests` field, which is outside this lease.
2. **No browser walk.** See above.
3. **`FeedbackWidget` still speaks French** when opened from the Réglages row.
   The row that opens it is translated; the panel behind it is another owner's
   surface and was left alone.
4. **The `<Dialog>` furniture** (close affordance, etc.) comes from
   `atelier-v2-copy.ts` and now follows `copyLanguage` — correct here, but worth
   confirming it does not surprise anyone who expected the design-system chrome
   to be French everywhere.
5. **`normalizeControlLanguage` is restated** as `normalizeSettingsLanguage` in
   `settings-copy.ts`, because importing `atelier-v2-copy.ts` would pull the
   whole journey copy table into a file that has to stay requirable on its own
   by the node test. If the normalization ever changes, both must change.
