# S4 · The frame: one register of places, one error path, one mail outbox

Written 9 Nov 2026 from `origin/main` at `ec60ae44`.
Implementation: Opus 5.5, medium effort, own worktree cut from `origin/main`, draft PR, nothing merges without the owner.

## The structural flaw

The daily lesson has contracts. What surrounds it does not, so each surface solved the same three problems alone.

1. **Places are not declared anywhere.** The four tabs are one table (`web-frontend/lib/product-shell.ts:24-74`). Everything else is reached by a link written into some component, and gated in a different way each time:
   - `/audio-session` only from `pages/atelier.tsx:1901`, `/mur` only from `MurEntry.tsx:16`, `/bibliotheque` only from `pages/notebook.tsx:562`, `/eclair` from two Forge links;
   - gates live in four systems: `launch-flags.json`, backend settings (`REVUE_ENABLED`, `ATELIER_CALLS_ENABLED`, …), `next.config.js` redirects, and `getStaticProps` returning `notFound`;
   - three gallery pages are not in the native export's prune list (`native-export-policy.mjs:29`);
   - `/pilot-ops` ships with no client guard and an English title;
   - `/serial/episode/[index]` still renders as a page beside the Feuilleton that replaced it.
   Nobody can answer «what can a learner open today, and from where» without reading the code.
2. **Errors have no single path.**
   - There is no `404.tsx`, `500.tsx`, `_error.tsx` and no error boundary in `_app.tsx`. A crash or a wrong URL shows Next's English default page. The crash is reported silently (`_app.tsx:168-201`).
   - A failed API call raises an English toast from the axios interceptor (`services/api.ts:2150-2205`), while 429 is French and says «vous».
   - Home has its own error kinds in three languages (`lib/atelier-errors.ts`); other pages roll their own notices. `StateBlock` exists and is used in 29 files, but nothing requires it.
   - `public/sw.js` handles push only. The TestFlight checklist expects a cached edition offline; nothing provides it.
3. **Mail is one hard-wired message.**
   - The only mail is the password-reset code, built inline (`app/services/auth.py:363-409`) and sent through an outbox that only knows that message (`password_reset_delivery.py`).
   - The address is never verified: `User.is_verified` exists and no flow sets it. `PATCH /users/me/email` takes effect at once.
   - `weekly_email_summary` is a stored preference that nothing sends.
   - Feedback is one-way (`FeedbackWidget`); there is no help or contact surface except the address on the legal pages, and the legal text is still a draft with a placeholder operator.

## Target structure

**A. A register of places.** One table, `web-frontend/lib/places.ts`, lists every route with: learner name per language, kind (tab, child of a tab, day step, account, legal, dev), parent, the one gate that shows it, and its entry points. From it:
- the tab bar, the masthead, `OWN_SHELL_ROUTES`, `RouteAuthGate`'s public list, the redirects in `next.config.js` and the native prune list are generated or checked;
- a test fails when a file in `pages/` is not in the register, when a non-dev place has no entry point, or when a dev place can be built into a release;
- one gate function, `placeVisible(place, flags, serverCapabilities)`, replaces the four gate systems on the client. The server sends its switches once in the today envelope's capabilities;
- every place renders inside one of three shells (tab, child with a back link to its parent, full-screen step), so «where am I» has the same answer everywhere.
The register is also the list the owner uses to decide what stays. It does not remove any place by itself.

**B. One error path.**
- An error boundary in `_app.tsx` and `404.tsx`, `500.tsx` pages drawn with `StateBlock`, in the learner's language, each with one way back (Home).
- One mapping `errorToState(error) -> {kind, title, body, action}` in `lib/app-errors.ts`, grown from `lib/atelier-errors.ts`. The axios interceptor stops writing English toasts and uses it; pages use it for their inline state. Kinds: offline, slow, down, not_found, forbidden, rate_limited, session_expired, unknown.
- What the boundary shows, the silent reporter sends: one event id on the screen and in the report.
- Offline: the service worker caches the app shell and the last today envelope, read-only, with the revalidation note the checklist already describes.

**C. One mail outbox and a verified address.**
- Generalise the reset outbox to `MailDelivery {kind, user_id, payload, attempts}` with templates per kind and language in `app/mail/`. Kinds now: `password_reset`, `verify_email`, `email_changed`. The weekly summary gets a kind only if the owner wants the mail; otherwise delete the preference.
- Sign-up sends `verify_email`. Unverified accounts can use the app; password reset by mail and email change need a verified address, and an email change is confirmed at the new address and announced at the old one.
- A «Help» place in Réglages: a short FAQ from a copy table, the feedback sheet (already built), and the contact address. A feedback report stores whether the learner wants a reply; the reply goes through the outbox.

## Stages (each its own PR)

1. `places.ts`, the register test, generated nav and prune lists. No visible change except dev pages leaving the release build.
2. Error boundary, 404 and 500 pages, `errorToState`, interceptor on it.
3. Mail outbox with kinds and templates; verification on sign-up and on email change.
4. Help place and feedback reply.
5. Offline shell and cached edition.

## Done when

- The register test fails on `ec60ae44` (three unlisted gallery pages, places with one hard-coded entry) and passes after stage 1.
- The browser walk opens an unknown URL and a page forced to throw, in `de` and `fr`: each shows a `StateBlock` in that language with a working way back, and no English.
- A guard finds no English literal in `services/api.ts` error handling and no `toast.error` with a literal string outside `errorToState`.
- A test registers, receives `verify_email` from the outbox, verifies, changes the address, and sees the change take effect only after confirmation.
- Airplane-mode cold start shows the cached edition.

## Not in this package

- Which places to hide or merge. The register makes that a one-line decision per place; the decision is the owner's.
- Payment. Nothing here assumes it.
- Final legal text and the operator's name.

## Owner decisions needed

1. May an unverified account play, with verification required only for reset and email change (proposal: yes)?
2. Weekly summary mail: build it or delete the preference?
3. Who answers feedback, and from which address?
