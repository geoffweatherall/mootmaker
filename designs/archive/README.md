# Completed designs

Every design here has shipped or been superseded. They are kept as the record of *why* the system
is the way it is, and are not maintained. Each still says what was true when it shipped, so check
anything that matters against the code or the [overview docs](../../docs/overview/).

This index says how far each one still describes the system:

- **Still describes the system.** The design matches what is built. It is the best place to find
  the reasoning behind that part of it.
- **Partly overtaken.** The core still stands, but later work changed parts of it. The note says
  which.
- **Historical only.** Superseded, or describes a structure that no longer exists. Read it only for
  the history.

Designs still being written or built live one level up, in [`designs/`](../). See the
[design process](../README.md) for the lifecycle.

## Still describes the system

| Design | Area | How relevant it is |
|---|---|---|
| [android-app.md](android-app.md) | Android | The plan the Android app was built from, milestone by milestone: toolchain, auth, schema sharing, the cloud-session/CI loop, release and sideloading. Its decisions still describe how the app is built and released. |
| [android-cache.md](android-cache.md) | Android | The Android app's in-memory `WorkspaceStore` and how the `daysInvalidated` channel keeps it honest. The reference for why Android does not use Apollo's normalized cache. |
| [android-error-display.md](android-error-display.md) | Android | The one way the Android app shows errors: a banner pinned under the title bar. The rule itself is restated in the Android README. |
| [quarter-hour-time-dial.md](quarter-hour-time-dial.md) | Android | The custom clock-dial time picker that offers only quarter hours. Matches the code. |
| [graphql-schema-and-caching.md](graphql-schema-and-caching.md) | API, webapp | The day-keyed data model, the composite `workspace` query, selection-aware resolvers and the `daysInvalidated` live channel. The most important design for understanding how data is stored, read and kept fresh. Its supporting [proposal schema](graphql-schema-and-caching-proposal/) is the version that was chosen. |
| [dynamodb-storage-compaction.md](dynamodb-storage-compaction.md) | API | Why ids are 8-character tokens and times are stored as epoch minutes, and what that buys within DynamoDB's 400 KB item limit. |
| [edit-and-cancel-meetings.md](edit-and-cancel-meetings.md) | API, webapp | `updateMeeting`, `cancelMeeting` and moving a meeting to another day. The optimistic-concurrency check (`expectedVersion` / `MeetingChanged`) was added afterwards without a design ([mootmaker-api#96](https://github.com/geoffweatherall/mootmaker-api/issues/96)). |
| [attendee-response-status.md](attendee-response-status.md) | API, webapp | Going / Maybe / Not going and its storage as a parallel list of one-letter codes. Still accurate for the data model and API. Its Home page layout was replaced by home-and-misc-pages-redesign. |
| [admin-rooms-and-people.md](admin-rooms-and-people.md) | API, webapp | Admin CRUD for rooms and people, `setPersonAdmin` and its two-place role storage, and the split of self versus admin mutations. Matches the code. |
| [admin-tools-into-api.md](admin-tools-into-api.md) | API | Why `database-reset` and `database-repair` are Lambdas in mootmaker-api, and the production-safe rules for what a reset may delete. The `MeetingParticipant` repair it mentions went away with the day-keyed model. |
| [date-time-format-settings.md](date-time-format-settings.md) | API, webapp | Per-person date and time formats, and the rule that the API only ever speaks zone-less ISO-8601. The `weekStart` preference was added later without a design. |
| [person-avatar-upload-refactor.md](person-avatar-upload-refactor.md) | API, demo data | The presigned-upload, confirm-and-normalise avatar pipeline, its bucket and CDN, and the move off whole-record `PutItem`. Matches the code. |
| [photorealistic-demo-avatars.md](photorealistic-demo-avatars.md) | Demo data | How the demo avatar pool was generated and reviewed. Matches the image set in mootmaker-demo-data. |
| [demo-data-component.md](demo-data-component.md) | Demo data | demo-data as one Lambda and one deployable with its own M2M client, always on in `production`. Matches the repo's structure. |
| [realistic-demo-meeting-schedule.md](realistic-demo-meeting-schedule.md) | Demo data | The double-hump daily distribution, per-room occupancy tiers and the relaxed attendee-overlap rule the generator uses. |
| [graphql-schema-sharing.md](graphql-schema-sharing.md) | API, webapp | Publishing the schema to npm and GitHub Packages, with webapp and Android generating code from it. demo-data and the API's `verify/` suite still use hand-written query strings, as this design anticipated. |
| [home-and-misc-pages-redesign.md](home-and-misc-pages-redesign.md) | Webapp | The current Home page (Needs your response with Search further ahead, merged Today/Tomorrow agenda) and the shared empty-state component. |
| [meeting-detail-consolidation.md](meeting-detail-consolidation.md) | Webapp | The shared bottom-sheet / side-panel for meeting details, the retained `/meetings/:id` deep link and the Share action. |
| [cloudformation-from-cli-via-sso.md](cloudformation-from-cli-via-sso.md) | AWS accounts | Applying the account CloudFormation from the CLI with SSO: the stack-operator and billing-read-only permission sets and one-hour management credentials. Matches mootmaker-bootstrap-aws-accounts. |

## Partly overtaken

| Design | Area | What changed since |
|---|---|---|
| [ci-cd-pipeline.md](ci-cd-pipeline.md) | Delivery | The pull-request checks and the release pipeline (build once, `test`, smoke, `production`, smoke, automatic rollback) still stand. Since then the pipeline gained the Android APK build, its acceptance and n-1 smoke stages, and fail-fast cancelling of parallel builds; the ephemeral sweep went from report-only to destroying environments idle for 48 hours. Read [delivery](../../docs/overview/delivery.md) for the current shape. |
| [room-availability-and-person-calendar-redesign.md](room-availability-and-person-calendar-redesign.md) | Webapp | The mobile-first layouts for Room availability and Person calendar still stand. Initials avatars became photo avatars, and the People/Rooms lists it restyles moved out of Settings into their own admin pages. |
| [project-reorganisation.md](project-reorganisation.md) | Process | Created the hub, the process docs, issues and the board, per-repo `AGENTS.md` and the workstation manifest, all still in use. Overtaken in several places: the role ("hat") documents and agent definitions have been removed, CI/CD now exists, the `test` environment came back as the release rehearsal stage, and the repository split has changed. |
| [delete-my-account.md](delete-my-account.md) and [its to-do list](delete-my-account-todo.md) | API, webapp | Self-service account deletion, written before the design template existed. The feature still works as described from the user's side, but the implementation notes predate the day-keyed model and avatars; `deleteMyAccount` now also cancels upcoming meetings and deletes the avatar. |

## Historical only

| Design | Area | Why |
|---|---|---|
| [person-avatar-photos.md](person-avatar-photos.md) | Webapp, demo data | A stock photo library bundled into the webapp and pointed at by `Person.photoUrl`. Replaced within days by person-avatar-upload-refactor; none of it remains. |
| [meeting-picker-dropdowns-todo.md](meeting-picker-dropdowns-todo.md) | Webapp | A to-do list for sorting and filtering the meeting form's pickers, from before the design template. Done long ago, and the form has been rebuilt since. |
