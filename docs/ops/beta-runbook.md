# Beta runbook: the first ten, then 25 learners

The plan (proposal of 14 November 2026, Bet 2): ten people Vincent can reach in person,
then 25, German or English speakers at A1 to A2 who want French. Free, and what they
report is fixed overnight. Done when 15 of 25 finish day 7 and each has been spoken to once.

## 1. What only Vincent can do

| # | Step | Where | Unblocks |
|---|---|---|---|
| 1 | Apple Developer enrolment (individual or organisation), then the App Store Connect record for `com.pixellab.feuilleton` | developer.apple.com, appstoreconnect.apple.com | Every TestFlight build |
| 2 | The real contact address (and, if it is not Pixel Lab, the operator name) for the privacy policy and the terms | Render dashboard: `LEGAL_CONTACT_EMAIL` on `atelier-api`; build env: `NEXT_PUBLIC_LEGAL_CONTACT_EMAIL`; optionally `operator` in `app/data/legal/legal_content.json` | The API refuses to start in production without it; the archive lane refuses to build |
| 3 | The list of the first ten people: name, e-mail, the language they want the app in (de/en), level guess | Keep it private. Their e-mails go into `REGISTRATION_ALLOWED_EMAILS` (Render dashboard, comma-separated) and into App Store Connect → TestFlight → testers | The invitations |

Everything else below is ready or can be done by a thread.

## 2. Getting them in (TestFlight)

1. After step 1: `bundle exec fastlane ios beta` (see
   [testflight-production-flip-checklist.md](../testflight-production-flip-checklist.md)).
   The lane appends the build to [release-status.md](release-status.md).
2. App Store Connect → TestFlight: add the ten as **external testers** in one group
   («Beta 1»). External testing needs a one-time Beta App Review (usually a day); the
   privacy URL is `https://<api-host>/privacy`. Internal testers (up to 100, no review)
   must be members of the App Store Connect team, so they only fit people you add as users.
3. Add the same ten e-mails to `REGISTRATION_ALLOWED_EMAILS`. Sign-up stays closed to
   everyone else (`REGISTRATION_OPEN=false`). An address not on the list sees «Sign-up is by
   invitation only during the pilot».
4. Send the invitation (template below). TestFlight sends its own e-mail with the code.

### A web beta, only if Apple takes longer than a week

Decision 5 of the proposal. Not built yet, on purpose: the web app runs a Next.js server
(sign-in goes through NextAuth's server routes), and `npm audit --omit=dev` on 14 November
2026 reports a **critical** advisory for every Next.js release up to 16.3 preview. A public
Next.js server should wait for the fix. The safer shape, if it is needed: serve the static
export (the same bundle as the phone) as a Render static site, let the browser use the
phone's token sign-in instead of NextAuth, and add the site's origin to
`BACKEND_CORS_ORIGINS` (today only `capacitor://localhost` and `ionic://localhost`). About a
day of work; ask a thread for it.

## 3. The invitation (to send yourself)

German:

> Hallo [Name], ich baue eine App, mit der man Französisch über eine Fortsetzungsgeschichte
> lernt, jeden Tag etwa 15 bis 30 Minuten. Ich suche zehn Leute, die sie sechs Wochen lang
> ausprobieren. Sie ist kostenlos. Wenn dir etwas falsch vorkommt, tippe unter der Korrektur
> auf «Hier stimmt etwas nicht»: ich lese jede Meldung und behebe es meist über Nacht. Nach
> der ersten Woche würde ich gern 5 Minuten mit dir sprechen. Du bekommst gleich eine
> TestFlight-Einladung von Apple; melde dich dann in der App mit dieser E-Mail-Adresse an.

English:

> Hi [name], I am building an app that teaches French through a serial story, about 15 to
> 30 minutes a day. I am looking for ten people to try it for six weeks. It is free. When
> something looks wrong, tap «Something here looks wrong» under the correction: I read
> every report and usually fix it overnight. After the first week I would like to talk to
> you for 5 minutes. You will get a TestFlight invitation from Apple; then sign up in the
> app with this e-mail address.

## 4. What to look at

**Every morning, `/pilot-ops`** (owner account):

- **Who came back?** per sign-up week: finished first day, back on day 1, 3, 7, 14, 30,
  days done of started, median minutes, median story words (French in) and own words
  (French out) per active day, and after which step unfinished days stopped. Open a week
  for one row per learner. Under five learners a cell shows counts, not a percentage.
  Walk and test accounts (`users.is_synthetic`) are left out; mark yours with
  `scripts/mark_synthetic_accounts.py` so they never count.
- **What looked wrong?** every «Something here looks wrong» tap with what the screen showed.

**The queue.** `python scripts/loop/learner_reports.py --file` (with `ATELIER_API_URL`,
`ATELIER_ADMIN_EMAIL`, `ATELIER_ADMIN_PASSWORD`) files one `walk-finding` issue per new tap
in `queue:owner`. The issue names the report only, because the repository is public. Read
the text on `/pilot-ops`, then triage it like any finding (lane, size, **Done when:**,
`queue:ready`). Add this command to the live walk's nightly run on the Mac, which already
signs in to production.

**The digest.** `python scripts/pilot_digest.py --day YYYY-MM-DD` prints the same return
table (cohort rows only) with the day's cost and failures.

## 5. The bar

| Measure | Bar | Source |
|---|---|---|
| Back on day 7, of those who finished day 1 | half | `/pilot-ops` → Day 7 |
| Back on day 30 | 30 percent | `/pilot-ops` → Day 30 |
| Finished day 7 | 15 of 25 | per-learner rows |
| Spoken to once | all 25 | your notes |
| Wrong verdicts | fewer than 1 in 200 answers | appeals and «looks wrong» taps against judged answers |
