# Atelier design preview — archived proposal

**Superseded 2026-09-05:** the owner rejected this visual direction and selected Claude Design. Do not implement its styling, typography, buttons, or navigation composition. The accepted functional concepts are maintained in the [revised work packages](../implementation/atelier-v2/README.md).

An isolated historical design proposal. No production screen, application route, auth gate, or backend has been changed.

From the repository root:

```sh
python3 -m http.server 4173 --bind 127.0.0.1
```

Open [the interactive preview](http://127.0.0.1:4173/docs/atelier-redesign/index.html). Use Desktop / Mobile to inspect both layouts. The **Design notes** link contains the audit, visual system, screen decisions, and implementation sequence.

The preview also opens directly from `index.html` on disk; artwork paths intentionally reference the existing `web-frontend/public/assets/serial` directory. Keep it in its repository location. Fonts are bundled locally, with their license in `assets/OFL.txt`. No package installation or build step is required.

## Interactive coverage

- Home navigation and sample profile.
- Three-step lesson: choose an answer, get help, correct a mistake, order words, respond to Romy, earn a postcard.
- Six-word self-review; finishing updates the local due count.
- Three sample story chapters, word details, and translations.
- Two-turn scripted conversation with branching replies and restart.
- Notebook search, due filter, grammar explanations, keepsakes.
- Responsive desktop/mobile layouts, keyboard-operable controls, native modal dialogs, reduced-motion preference.

All learner data, duration estimates, and dialogue are examples. In-memory progress resets on reload. No microphone, API, account write, analytics, storage, or production integration. This proposal uses English controls and French content; production controls should follow the learner’s language preference.

## Source inspection

- `web-frontend/styles/globals.css`: paper/ink palette, serif/sans/mono stacks, overlapping global and phone type scales.
- `web-frontend/components/laune/LaUne.tsx`: current Manchette and En Bref home composition.
- `web-frontend/components/epreuve/Epreuve.tsx`: lesson furniture, grouped progress, rule, prompt, confidence, feedback.
- `web-frontend/components/cahiers/Cahiers.tsx`: notebook tabs and list primitives.
- `web-frontend/components/courrier/Courrier.tsx`: mission typography and translation controls.
- `web-frontend/components/layout/*` and `web-frontend/lib/product-shell.ts`: four current product destinations and own-shell routes.
- `docs/design-overhaul-2026-08-31.md`: recent simplification and soft-button decisions.
- Running `/mobile-visual-qa`: current component compositions, not an authenticated account walkthrough.

Any production implementation should follow the revised work packages and Claude UI reference while preserving existing learning behavior and real metadata. The current extensive worktree changes were not reverted or edited.

## Verification — 5 September 2026

Manually exercised the preview in the Codex browser: lesson entry, incorrect answer and retry, help with Escape dismissal, all three lesson steps, postcard completion, home progress update, notebook search and due filtering, word and grammar dialogs, story reading and translation, branching conversation, repeated recall, all six word reviews, and the cleared review queue.

Visually inspected desktop and phone compositions. Measured home, conversation, notebook, and lesson at an actual 320 CSS-pixel viewport with no horizontal overflow. Checked the corrected character crop and legibility of answered choices. JavaScript syntax and all local HTML references pass. Measured text contrast: body on paper 11.68:1, secondary on paper 4.51:1, primary action 5.04:1, and success feedback 5.80:1. These are targeted checks, not a full accessibility audit or native-device certification.

The browser host logged two MutationObserver errors on page loading; the preview does not use MutationObserver. No corresponding failure was observed in the exercised interactions.
