# Release status: the iOS app

Where the native release stands. The procedure is in
[testflight-production-flip-checklist.md](../testflight-production-flip-checklist.md);
this file says what is done.

Rules:

- A state the repository cannot prove is «unknown». Settings typed into the Render or
  App Store Connect dashboards are not in the repository, so they stay «unknown» until
  someone who can see them writes the state and the date here.
- «As of» is the date the state was last checked or became true.
- `bundle exec fastlane ios beta` adds one row to «TestFlight builds» below after each
  upload. Update «Last TestFlight build» by hand from that row.

## Status

| Item | State | As of | Who can change it | Source |
|---|---|---|---|---|
| Apple Developer enrolment | unknown: no record in the repository. The checklist (7 Oct) still lists it as an owner action. | — | Owner (Apple account holder) | `docs/testflight-production-flip-checklist.md` |
| App Store Connect record | unknown: no record. The app id it needs is `com.pixellab.feuilleton`. | — | Owner (App Store Connect) | `web-frontend/fastlane/Appfile` |
| APNs environment on Render | unknown on the live services. The blueprint sets `APNS_USE_SANDBOX=false` (production) on the API and the worker since 2026-09-06; the status note of 2026-10-06 said the dashboard then had sandbox on both. | — | Owner (Render dashboard) | `render.yaml`, `docs/status-and-pilot-plan-2026-10-06.md` |
| Sentry DSNs | unknown: `SENTRY_DSN` (API, worker) is `sync: false` in the blueprint, so its value lives only in the Render dashboard; `NEXT_PUBLIC_SENTRY_DSN` (client) is build configuration. Sentry is a no-op while unset. | — | Owner (Render dashboard, build environment) | `render.yaml` |
| Legal text | draft: version 2026-09-22, `contact_email` is still the placeholder `[contact e-mail]`. The archive lane refuses to build without `NEXT_PUBLIC_LEGAL_CONTACT_EMAIL`. | 2026-11-10 | Owner (review), then anyone (edit `app/data/legal/legal_content.json` and sync) | `app/data/legal/legal_content.json` |
| Last archive | unknown: archives are built on a Mac and not recorded. | — | Whoever runs `fastlane ios archive` | none |
| Last TestFlight build | unknown: none recorded. The next `fastlane ios beta` adds a row below. | — | Whoever runs `fastlane ios beta` | «TestFlight builds» below |

## TestFlight builds

Appended by the `beta` lane (`web-frontend/fastlane/release_status.rb`). Newest last.

| Uploaded | Version | Build | Commit |
|---|---|---|---|
