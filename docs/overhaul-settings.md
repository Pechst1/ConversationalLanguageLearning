# Overhaul — Settings (`/settings`)

Part of the journal-system overhaul; method and contract in
`docs/JOURNAL_SYSTEM_OVERHAUL.md`. Audited 2026-07-18 against
`web-frontend/pages/settings.tsx`, the user/settings API client, and the live signed-in
route. This completes the required audit and design brief. The visual implementation waits
for the owner-provided Claude Design package.

## Purpose

Settings is the journal's administration layer: account identity, learning preferences,
practice goals, notifications, appearance, audio, privacy, and sign-out. It should feel
deliberately quieter and more utilitarian than La Une without dropping out of the same
publication system.

## 1. Works today (code-grounded)

- The page loads saved settings, maps API fields into a local typed model, applies the saved
  visual theme/font size, and refuses to overwrite preferences after a failed load
  (`pages/settings.tsx:141-228`).
- One save path persists profile, language, goals, vocabulary direction, notifications,
  theme/font, audio, and correction preferences (`:230-284`).
- Email and password changes use separate credential-confirmed forms (`:289-378`).
- Browser notification permission and server-side notification preferences are coordinated
  with clear denial/error handling (`:389-428`).
- Seven sections cover profile, learning, practice goals, notifications, appearance, audio,
  and privacy (`:139`, `:488-1130`), with a responsive horizontal/vertical section switch
  (`:498-520`).
- Loading and retryable load-error states exist (`:463-486`); unsaved changes and save
  status are surfaced before the active section (`:523-540`).
- The root page background, type, and newer shell furniture already consume `--app-*`
  tokens (`:463-493`, `:1149-1188`), and live verification confirms saved light/dark themes
  persist across `/atelier`, `/serial`, `/graphic-novel`, and `/missions`.

## 2. Missing / should add

1. A shared administration-page visual hierarchy. Each section currently retains legacy
   Bauhaus cards, colors, shadows, and rounded toggles inside a token-aware outer shell.
2. A deliberate save model on phones. The save banner appears above the active section and
   can scroll out of view; the design package should specify a safe, non-obstructive sticky
   save/settled treatment.
3. Complete destructive-action states. Privacy/data actions need clear confirm, pending,
   success, and failure treatments without making ordinary preference changes feel risky.
4. Publication-world copy. "Administration Layer" is the right concept but the page mixes
   it with generic English card language. Supply French section furniture while leaving
   instructional/account language in English.
5. Accessibility specification for the section switch, toggle states, range controls,
   permission denial, validation, and save announcements.

No backend expansion is required for the reskin.

## 3. Design drift vs. the journal contract

- The page has no literal color values in CSS declarations, but legacy utility classes
  still encode a light-only palette and hard shadows: `border-black`, `bg-white`,
  `bg-gray-*`, `text-white`, `bg-green-500`, `bg-purple-600`, and 26 `#000` shadow
  fragments (`pages/settings.tsx:540-1130`).
- Rounded pill toggles and brightly colored card headers belong to the old Bauhaus settings
  UI, not the hairline-rule/stamp/paper language of La Une.
- Desktop card stacks determine the hierarchy; the phone layout adapts them rather than
  starting with a compact administration form.
- Loading/error states use tokens, while populated sections fall back to the old palette,
  so theme fidelity is uneven despite the theme switch itself working.

## 4. Weave-in vision — "Le Bureau"

Treat Settings as **Le Bureau**, the publication office behind the edition. It is a ledger
of account and production preferences: ruled forms, section tabs, small status stamps, clear
permission notices, and one unambiguous "file changes" action. Keep it restrained. No fake
newspaper story, no ornamental dashboard, and no metaphor that obscures email/password or
privacy consequences.

## 5. Claude Design brief — "Le Bureau"

> Owner: copy from here into Claude Design and return the package before implementation.

# Design brief: "Le Bureau" — administration inside the journal system

Design `/settings` for a phone-first French-learning journal. Its other surfaces are La Une
(front page), L'Épreuve (practice print shop), Le Courrier (Missions), Le Feuilleton
(serial), and Les Cahiers (Notebook). Study their shared primitives and
`web-frontend/styles/globals.css`.

## Real capabilities to preserve

- Profile display name and email; separate authenticated email/password change forms.
- Native/target language, proficiency, CEFR target, interests, correction level, grammar
  explanations.
- Daily minutes/XP, new words/day, vocabulary direction, preferred session length.
- Practice, streak, weekly, achievement, and serial-edition notifications plus reminder time.
- Light/dark/system theme and small/medium/large font size.
- Voice input, TTS, speed, and pronunciation autoplay.
- Privacy/data controls and sign-out.
- Loading, retryable load error, validation, unsaved, saving, saved, and save-failed states.

## Required 390px frames

1. Bureau landing/profile with compact section navigation.
2. Learning and practice forms.
3. Notifications with browser permission denied and granted variants.
4. Appearance in light and dark.
5. Audio/voice.
6. Privacy/data with confirmation state.
7. Email/password security forms.
8. Loading, load error, unsaved, saving, saved, and save-failed.

## Copy and hierarchy

Use **LE BUREAU** for publication furniture and French labels such as **Compte**,
**Apprentissage**, **Objectifs**, **Avis**, **Apparence**, **Voix**, **Données**,
**Modifications à classer**, and **Classé**. Keep security explanations, validation, and
high-consequence actions in plain instructional English. Never mix languages within a line.

## Components requested

`StShell`, `StMasthead`, `StSectionTabs`, `StSection`, `StField`, `StChoice`,
`StToggle`, `StRange`, `StSaveBar`, `StStatusStamp`, `StNotice`, `StConfirm`,
`StSkeleton`.

Provide token-only component source/spec, every state, exact strings, keyboard/focus and
screen-reader behavior, and a migration map from current markup.

## Hard constraints

- Only global `--app-*` tokens; derived values via documented `color-mix`.
- Light/dark/system; no encoded Tailwind color palette, hardcoded hex, or local theme.
- Phone-first, safe-area aware, 44px targets; desktop is a secondary enhancement.
- Preserve all current data fields, validation, APIs, and security boundaries.
- Do not redesign bottom navigation.
- Confirm high-consequence account/data actions; ordinary preference save remains fast.
- Motion uses transform/opacity/filter and respects reduced motion.

