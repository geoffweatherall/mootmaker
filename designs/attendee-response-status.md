# Attendee response status (RSVP)

## Summary

Record each attendee's response to a meeting — Going / Not going / Maybe / Not yet responded — and
show it next to every attendee wherever attendees are listed, with a small colour + icon per status
and a control letting a signed-in user set or change only their own response. Touches storage
(DynamoDB, per Geoff's own note that this uses more record space), the GraphQL API, demo-data
generation, and the webapp's attendee-list surfaces.

## Status

**Drafting** — 2026-09-20.

## Scope / non-goals

In scope:

- A **fourth, distinct state**: not yet responded — different from Maybe, and the default for every
  attendee until they explicitly respond.
- **Self-only control**: a signed-in user may set/change only their own response on a meeting they
  attend, mirroring `updateMyPreferences`'s existing self-only pattern (no id argument, acts on the
  caller's own linked Person) rather than `updatePerson`'s self-or-admin pattern.
- Shown in every attendee list that exists today: the Calendar view's bottom-sheet/side-panel
  (`PersonCalendarPage.tsx`'s `MeetingDetail`) and the full-page `/meetings/:id`
  (`MeetingDetailsPage.tsx`). Room Availability and the Home page's agenda lists don't show attendee
  lists at all today, so no change is needed there.
- **mootmaker-demo-data**: generate a realistic mix of all four statuses across generated attendees,
  per Geoff's explicit ask, not just leave everyone "not yet responded."

Deliberately deferred, not rejected — see "Open questions":

- Notifying anyone of a status change. Mootmaker has no notification/email-to-user system today;
  this would be its own design.
- Organiser or admin overriding another attendee's response on their behalf. Only the self-only path
  is designed here.
- Any change to `createMeeting`'s attendee **capacity** logic, room-suggestion `requiredCapacity`,
  or the `OrganiserIsAttendee`/`TooManyAttendees` validation rules — RSVP status doesn't change who
  may be invited, only how their response is recorded afterward.
- General meeting editing. There is no `updateMeeting`/`deleteMeeting` mutation in the schema today
  (checked `api/mootmaker.graphql`'s `Mutation` type) — this doc adds one narrow, self-only mutation
  for a person's own response, not a general edit capability.
- Room Availability/Home page ever surfacing attendee status (e.g. an aggregate "3 of 5 confirmed"
  badge) — not requested; noted as a natural future extension.

## Trade-offs and decisions

- **Status lives per-attendee inside the day item's `meetings` list**, not as a parallel list or a
  separate table. The whole storage model already keys everything by day item (one item per calendar
  day, see `docs/reference/data-model.md`'s Meetings table) — a meeting is not its own item, and this
  project already removed a separate `MeetingParticipants` table for exactly this reason ("Nothing in
  this model is stored twice any more"). `MeetingRecord.attendeeIds: List<String>` becomes
  `MeetingRecord.attendees: List<AttendeeRecord>`, `AttendeeRecord(String personId, AttendeeStatus
  status)`, stored as a DynamoDB list of maps instead of a list of strings. A parallel `List<Status>`
  kept in lock-step by index was considered and rejected — any insert/removal desync between two
  independently-maintained lists is a correctness hazard this combined shape avoids by construction.
- **A response is set via a dedicated, narrow mutation** —
  `respondToMeeting(meetingId: ID!, status: AttendeeStatus!): RespondToMeetingResult!` — rather than
  inventing a general `updateMeeting`. No such mutation exists today, and building one just to carry
  this one field would be broader than what was asked for.
- **Whole-day rewrite, same as every other write to this table.** Every write already rewrites the
  whole day item under its optimistic `version` lock (`createMeeting` included). A status change is
  not a new concurrency model, just a smaller change inside the existing one — named explicitly here
  because a naive implementation might reach for a per-attribute DynamoDB update that this table's
  design doesn't use anywhere else.
- **Storage growth is real but small**, called out because Geoff flagged it explicitly. Today's
  `attendeeIds` is a list of plain ~36-byte uuid strings. As `{personId, status}` maps, each entry
  gains roughly the status value's bytes (a short enum name, a handful of bytes) plus DynamoDB's own
  small per-map-attribute overhead. Not expected to move this table into a different pricing tier at
  current data volumes — worth one quantified line in `data-model.md` once implemented, not a
  blocking concern for this doc.

## Choices you had me make

- **Reusing MUI's existing semantic palette** (`success`/`error`/`warning`/a neutral default) for the
  four statuses' colours, rather than inventing a fifth categorical colour scheme alongside the
  existing room-colour palette (`theme/tokens.ts`, `roomColorAt`). Flag to override if a distinct
  scheme is wanted — the room-colour palette exists for a different purpose (distinguishing *rooms*
  from each other) and re-purposing part of it for statuses risks visual confusion between the two.
- **Self-only via `updateMyPreferences`'s no-id-argument pattern**, not `updatePerson`'s
  self-or-admin `cognitoSubs`-comparison pattern. Simpler, and there's no stated need for an admin
  override here — flag if one is actually wanted.

## Open questions

Blocking:

- **Does the organiser get an implicit default status?** E.g. Going, since they scheduled the
  meeting — or do they also start at "not yet responded" like every other attendee? This affects
  both the API's default-on-create behaviour and demo-data's generation logic.
- **Confirm the four values' exact names/labels.** This doc proposes an `AttendeeStatus` enum
  `Going | NotGoing | Maybe | NotResponded`, with user-facing labels to match — confirm wording
  before Ready, especially whether "Not yet responded" (the ask's own phrasing) should be the
  displayed label rather than a terser "No response".
- **Confirm the colour/icon mapping** (this doc's default: Going → success/check, Not going →
  error/cross, Maybe → warning/question, Not responded → neutral/dash) — see "Choices you had me
  make" above.

Non-blocking:

- Whether a response change should re-publish `daysInvalidated` for that date (see Technical
  considerations) — likely yes, listed here rather than assumed.
- Migration strategy for existing `test`/`production` data — see "Rollout & migration"; this doc
  recommends read-path tolerance over a backfill Lambda, not yet confirmed.

## Impacts on components

- **mootmaker-api**: `api/mootmaker.graphql` — new `AttendeeStatus` enum; `Meeting.attendees` changes
  from `[Person!]!` to a new `Attendee` type wrapping `{ person: Person!, status: AttendeeStatus! }`;
  new `respondToMeeting` mutation, `RespondToMeetingResult`, and its error enum (meeting not found,
  caller not an attendee of that meeting, etc. — mirrors the existing `MeetingError`/`PersonError`
  pattern of one enum per entity). `MeetingRecord`/`Meeting` Java records and their
  `toAttributeValue`/`fromAttributeValue`/`toResponseMap` methods. `CreateMeetingHandler` (assign
  initial status per new attendee). New `RespondToMeetingHandler`. `deleteMyAccount`'s existing
  "removes them from every upcoming meeting they only attend" logic needs re-verifying against the
  new record shape (their whole `AttendeeRecord` drops out, status included — should need no logic
  change, but the shape it operates on changes).
- **mootmaker-demo-data**: `DemoData.java`'s meeting-generation attendee assignment — assign a
  realistic status mix instead of leaving every attendee unset; its own inline GraphQL query string
  (currently `attendees { id }`) needs the same shape update as the webapp.
- **mootmaker-webapp**: `webapp/src/graphql/types.ts` hand-maintained mirror + `npm run codegen`;
  `PersonCalendarPage.tsx`'s `MeetingDetail` attendee rows; `MeetingDetailsPage.tsx`'s `PersonRow`; a
  new small status icon+colour component (mirrors the existing `PersonAvatar`/`roomColorAt` pattern
  of one small reusable visual unit per concept); a compact status-setting control (a select/menu,
  not a whole form) shown only on the signed-in user's own attendee row in both of those two
  surfaces.

## Changes to the domain data model and data storage models

Delta against `docs/reference/data-model.md`'s Meetings table section:
`MeetingRecord.attendeeIds: List<String>` → `MeetingRecord.attendees: List<AttendeeRecord>`,
`AttendeeRecord(String personId, AttendeeStatus status)`, stored as a DynamoDB list of maps (each
`{ "personId": {"S": ...}, "status": {"S": ...} }`) instead of a list of plain strings.
`data-model.md` needs this section rewritten once implemented, per this project's "if your change
makes a document wrong, fixing it is part of the change" rule.

## Technical considerations

- **Schema change is breaking, and api+webapp must ship together.** `Meeting.attendees` changing
  shape (`[Person!]!` → `[Attendee!]!`) is exactly the kind of change `mootmaker-api/CLAUDE.md` warns
  about: "nothing enforces that [`mootmaker.graphql` and `webapp/src/graphql/types.ts`] agree, so a
  schema change means changing both in step." `release.yml` already versions and promotes
  `mootmaker-api`, `mootmaker-webapp` and `mootmaker-demo-data` together as one release, which is the
  existing mitigation — but this can't be a partial/staged rollout of just one component, and all
  three need their GraphQL-shaped code (webapp's `types.ts`, demo-data's inline query string) updated
  in the same release.
- **Self-only authorization**: mirrors `updateMyPreferences`'s pattern (no id argument; acts on the
  caller's own `custom:personId`-linked Person), not `UpdatePersonHandler`'s self-or-admin
  `cognitoSubs`-comparison pattern — confirm this is still the right precedent when implementation
  starts, since `updateMyPreferences` is the closer analogue (self-only, no admin override) but
  `UpdatePersonHandler`'s comparison logic is worth a second look regardless.
- **`publishDaysInvalidated`** should likely be called after a successful response change too, same
  as `createMeeting` already does, so another open tab watching that date sees the updated status
  live rather than only on its next fetch.
- Rough storage delta: see "Trade-offs and decisions" — worth one quantified line in `data-model.md`
  once implemented, not a blocking concern here.

## Testing impacts

- **mootmaker-api**: new unit tests for `respondToMeeting` (self-only enforcement, valid/invalid
  status values, meeting-not-found, caller-not-an-attendee-of-that-meeting), and a
  `MeetingRecord`/`AttendeeRecord` (de)serialization round-trip test for the new shape.
- **mootmaker-webapp**: unit/mocked-integration tests for the new status control and status icon
  rendering; the existing acceptance suite's meeting-creation and meeting-detail tests will need
  attendee-status assertions added. Any new attendee-row locator should be written role/name-based
  and exact-matched from the start — this session hit repeated locator-fragility bugs (issues #46,
  #50, mootmaker-webapp#71) from exactly this class of mistake, and a new attendee-status UI element
  is a fresh chance to repeat it if not deliberately avoided.
- **mootmaker-demo-data**: an invariant that a real mix of all four statuses actually appears in
  generated data, following the pattern of `GeneratedDataInvariantsAcceptanceIT`'s existing
  `guaranteedMeetingsCreated > 0` assertion — but see mootmaker-demo-data#32 (filed this session)
  about that specific assertion's own probabilistic-failure shape, and design this new one to avoid
  the same mistake from the start (e.g. assert against a generated sample large enough that
  coincidentally-uniform output is negligible, rather than a small deterministic guarantee that can
  legitimately fail by chance).

## Documentation impacts

- `docs/reference/data-model.md` (Meetings table section).
- `mootmaker-api/README.md` and `mootmaker-webapp/README.md`/`testing-strategy.md`, wherever they
  describe the meeting/attendee shape.

## Rollout & migration

Existing meetings in `test`/`production` have `attendeeIds: List<String>` with no status. Since a
day item is rewritten whole on every write, no existing item will spontaneously gain the new shape.
Two paths:

1. A `database-repair`-style backfill Lambda (this project's existing `*Repair` pattern) that
   rewrites every existing day item to the new shape, defaulting every existing attendee to
   `NotResponded` (organiser to whatever the resolved default from "Open questions" is), before the
   new schema ships.
2. Make the read path tolerant of a missing `status` (treat absent as `NotResponded`) so old data
   keeps working with no migration step, and let it self-heal as meetings naturally age out of the
   retention window.

This doc's default recommendation is (2) — cheaper and lower-risk than a repair Lambda for a change
this narrow — but it is not yet confirmed.

## Risks

- **Release coupling** (see Technical considerations): shipping `mootmaker-api` and
  `mootmaker-webapp` out of step breaks the deployed environment until both catch up.
  `release.yml`'s existing all-three-together versioning is the mitigation already in place.
- **Optimistic-lock conflicts**: a response submitted concurrently with another write to the same
  day (another meeting created, another response set) can hit the day item's `version` conflict and
  need a client-side retry — not a new risk this design introduces, but `respondToMeeting` needs the
  same conflict-handling `createMeeting` already has, and that should be verified rather than
  assumed to already cover a second mutation.

## Definition of done

N/A at Drafting — to be filled in once the blocking open questions above are resolved and this
moves to Ready.
