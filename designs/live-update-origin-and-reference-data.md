# Live updates: origin ids and reference-data broadcasts

## Summary

Two additive extensions to the `daysInvalidated` broadcast, both anticipated when its payload was
made an object rather than a bare list. **Origin ids** let a tab recognise its own broadcasts
exactly, replacing the 5-second own-write window that also swallows other people's changes.
**Reference-data flags** tell clients when rooms or people changed, so a new room or a renamed
person reaches other screens without a reload. Both come from the
[open-questions answers](../docs/showcase/live-updates-open-questions.md), questions 1 and 3.

## Status

**Drafting** — 2026-10-07. Drafted by Claude, unattended. Not reviewed.

## Scope / non-goals

**In scope:** the `Invalidation` payload and `publishDaysInvalidated` arguments; publishing from
every room- and person-changing path; the webapp's handling of both; removing the time window once
origin ids work.

**Not in scope:**

- `mootmaker-android`'s handling. The schema change is additive, so the Android app keeps working
  unchanged; adopting these fields there is that app's own work.
- Partitioning broadcasts per organisation or user (open question 2: not needed).
- Broadcasting the bookable window (`boundaries`). It moves once a day with retention; a reload or
  tab return is enough.
- Renaming `publishDaysInvalidated` or `daysInvalidated`, which would be a breaking change for a
  name that's only slightly wrong.

## Trade-offs and decisions

1. **Extend the existing message rather than add a second subscription.** One socket and one
   subscription already exist and are resynced correctly on reconnect. A second subscription would
   double that machinery for a rarely-used signal. `Invalidation` was made an object precisely so
   fields could be added.
2. **Flags, not ids.** `rooms: true` means "your room list is stale, refetch it". It doesn't name
   which room. Rooms and people are small lists fetched in one query (`REFERENCE_DATA`), and
   "dates, not data" is the established principle. Flags are idempotent and order-free in the same
   way.
3. **Origin is per tab, not per user.** Two tabs of the same user must behave as two users: row 7
   of the original cross-client table. A random id generated when the app loads gives exactly that.
4. **Origin is advisory, not trusted.** A client could send any origin. The worst it can do is make
   *its own* tab ignore a broadcast, since every other tab has a different id, so it needs no
   validation.
5. **Keep the time window as a fallback, then delete it.** Until the API that echoes `origin` is
   deployed everywhere, a broadcast without `origin` falls back to the window. Once the API has
   shipped, a follow-up removes the window and its trade-off for good.

## Choices you had me make

All of these were made without discussion, and are cheap to change before Ready:

- Field names `origin`, `rooms`, `people`, and the header name `x-mootmaker-origin`.
- `rooms` and `people` as two flags rather than one `referenceData` flag. The webapp would treat
  them identically today, but Android might not.
- Including the person-changing **avatar** mutations (`confirmAvatarUpload`, `removeAvatar`),
  because the people list carries `avatarUrl`.
- Excluding `updateMyPreferences`: preferences aren't in `REFERENCE_DATA`.

## Open questions

**Blocking:**

1. **Does AppSync pass a custom request header through CORS?** The webapp is on a different origin
   from the API, so `x-mootmaker-origin` triggers a CORS preflight. If AppSync doesn't allow
   arbitrary headers, origin has to travel some other way, for example in `extensions` or as a
   mutation argument. Needs a throwaway check, in the same spirit as the original design's
   "Verified" sections.
2. **Does a NONE resolver's `$context.arguments` include argument defaults?** The plan relies on
   `rooms: Boolean = false` reaching the payload as `false` when omitted. If it arrives as absent,
   `Invalidation.rooms` must be nullable, or the publisher must always send it.

**Non-blocking:**

- Whether the post-confirmation trigger (a separate Lambda, `PostConfirmationCreatePersonHandler`)
  gets the same `GRAPHQL_ENDPOINT` and single-field IAM grant, or whether a new sign-up appearing in
  other people's attendee lists can wait for a reload.

## Impacts on components

**`mootmaker-api`**

- `api/mootmaker.graphql`:
  - `publishDaysInvalidated(dates: [String!]!, rooms: Boolean = false, people: Boolean = false, origin: String)`
  - `type Invalidation { dates: [String!]!  rooms: Boolean!  people: Boolean!  origin: String }`
  - Both type-level auth directives stay on `Invalidation`.
  - Minor version bump in `api/package.json`, because it's additive.
- `appsync.tf`: the direct-Lambda request template forwards the `x-mootmaker-origin` header value
  (only that value, not every header) into the payload. The NONE resolver needs no change: it echoes
  arguments.
- `DayBroadcaster` / `DaysInvalidatedPublisher`: `publish` takes an invalidation (dates, flags,
  origin) rather than only dates. It must still never throw. An invalidation with no dates but a flag
  set must not be dropped by the current "empty list returns early" check.
- Handlers: every meeting handler passes the request's origin through. Room handlers (`createRoom`,
  `updateRoom`, `deleteRoom`) set `rooms`. Person handlers (`createPerson`, `updateMyName`,
  `renamePerson`, `setPersonAdmin`, `deletePerson`, `deleteMyAccount`, `confirmAvatarUpload`,
  `removeAvatar`) set `people`. `deletePerson` and `deleteMyAccount` also publish their changed dates
  (already done: mootmaker-api#107).
- Optionally `PostConfirmationCreatePersonHandler` (non-blocking question above).

**`mootmaker-webapp`**

- `apolloClient.ts`: a per-tab origin id generated once, sent as `x-mootmaker-origin` by the auth
  link.
- `useDaysInvalidated.ts`: select `rooms people origin`. Ignore a broadcast whose `origin` is this
  tab's own. If `rooms` or `people` is set, refetch `REFERENCE_DATA` (and anything else that reads
  rooms or people, which `evictAndRefetch` can find by evicting the `workspace.rooms` /
  `workspace.people` fields).
- `daysInvalidated.ts`: `noteOwnWrite` and the window stay only as the fallback (decision 5).
- Codegen against the new `@mootmaker/schema` version.

**Not touched:** `mootmaker-android` (additive change), `mootmaker-demo-data` (calls mutations, never
subscribes), release and infrastructure repos.

## Changes to the domain data model and data storage models

N/A. Nothing is stored; this only changes a broadcast payload.

## Technical considerations

- **The silent-failure catalogue still applies.** A new `Invalidation` field missing either
  type-level directive is the documented "subscribe succeeds, nothing delivered" failure. The
  existing publisher check for `"errors"` in a 200 response covers it, as long as the acceptance
  test asserts delivery.
- **Payload size stays trivial**: two booleans and a short id.
- **Leaves nothing behind.** No storage, no logs beyond the existing WARN on a failed publish.
- **Order of deploy**: API first (extra fields are ignored by old clients), then webapp. Removing
  the window comes last, once the API is in production.

## Testing impacts

- **API unit:** `RecordingBroadcaster` assertions per handler that each publishes the right flag,
  and no dates for a pure room or person change. Meeting handlers pass origin through.
- **API acceptance:** extend `DaysInvalidatedAcceptanceIT`: `createRoom` delivers `rooms: true`, a
  rejected `createRoom` delivers nothing, and a request carrying the header delivers that `origin`.
  This is the only layer that proves the template change and the directives.
- **Webapp unit:** an own-origin broadcast is ignored with no time window involved; another origin
  on the same date is acted on immediately; a `rooms` flag refetches the reference-data query and
  nothing else.
- **Webapp acceptance:** a cross-client case where an admin creates a room over the API and an open
  Room Availability page shows it without reload. The existing own-write case (the booking tab
  doesn't flicker) must stay green.
- **Mocked integration:** not impacted. There's no real subscription there.
- **Release smoke suite:** not impacted. Nothing it asserts on changes.

## Documentation impacts

- mootmaker-api README "Real-time updates": the payload fields and the full trigger list.
- mootmaker-webapp README, near the live-updates description.
- Hub `docs/showcase/` talk, deep dive and open-questions documents: questions 1 and 3 become
  "done", and the 5-second window description changes.

## Rollout & migration

No data migration. API first, webapp second, then the follow-up that removes the window. An old
webapp ignores the new fields. A new webapp against an old API sees `origin`, `rooms` and `people`
absent, and behaves as today.

## Risks

- **CORS** (blocking question 1) could force origin into a different transport.
- **Missing directive on a new field** fails silently. Mitigated by the acceptance test asserting
  delivery.
- **More broadcasts.** Admin changes are rare, so the cost impact is negligible (see the
  open-questions cost model).

## Implementation checklist

Left until Ready.

## Definition of done

The new API acceptance cases and the webapp cross-client room case are green, the full API and
webapp acceptance suites are green on a fresh ephemeral environment, the window-removal follow-up
has shipped, and the documentation impacts above are done.
