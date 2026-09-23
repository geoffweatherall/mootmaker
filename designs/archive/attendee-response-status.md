# Attendee response status (RSVP)

## Summary

Record each attendee's response to a meeting — Going / Not going / Maybe / No response — and show
it next to every attendee wherever attendees are listed, with a small colour + icon per status and a
control letting a signed-in user set or change only their own response. Also redesigns the Home page
around it: a "Needs your response" section, and the existing Today/Tomorrow agenda lists become
cards with a show-more expander. Touches storage (DynamoDB, per Geoff's own note that this uses more
record space), the GraphQL API, demo-data generation, and the webapp's Home/Calendar/Meeting-Detail
surfaces.

**UI prototype**: https://claude.ai/artifact/NifSs32je8ejXWttFsh95D — icon options, the redesigned
Home page (interactive: try the quick-respond buttons and the "show more" expander), and the
Meeting Detail attendee list with the response control (interactive: try changing "your" response).

## Status

**Shipped** — 2026-09-21. Implemented across `mootmaker-api` (#59, #60), `mootmaker-demo-data`
(#33), `mootmaker-webapp` (#106, #107) and this hub repo's own docs (#99); released as `v4.0.0`
(major bump, per the breaking `Meeting.attendees` schema change) — deployed and smoke-tested clean
on both `test` and `production`, no rollback. See "Definition of done" below for what that bar
actually covered.

Left in `designs/` rather than moved to `designs/archive/` as the lifecycle normally calls for: the
implementation left ~15 bare-text references to this doc's path scattered across code comments in
all three implementation repos (mostly `// see designs/attendee-response-status.md` javadoc-style
notes), and updating every one of them across three more small PRs wasn't judged worth it purely for
path hygiene. `docs/reference/data-model.md` and `use-cases.md` - the two documents that actually
have to stay current - are both already updated to reflect the shipped shape.

## Scope / non-goals

In scope:

- A **fourth, distinct state**: not yet responded — different from Maybe, and the default for every
  attendee until they explicitly respond.
- **Self-only control**: a signed-in user may set/change only their own response on a meeting they
  attend, mirroring `updateMyPreferences`'s existing self-only pattern (no id argument, acts on the
  caller's own linked Person) rather than `updatePerson`'s self-or-admin pattern.
- Shown next to every attendee wherever an attendee list already renders: the shared meeting-detail
  sheet/panel (`MeetingDetailContent.tsx`, per 2026-09-20's meeting-detail-consolidation work — this
  supersedes the original draft's references to `PersonCalendarPage.tsx`'s own `MeetingDetail` and a
  separate `MeetingDetailsPage.tsx`'s `PersonRow`, both since merged into that one shared component).
- **Home page redesign** (added to scope 2026-09-21, per Geoff's own follow-up ask — supersedes the
  original draft's "Room Availability and the Home page... no change needed there" line):
  - A new **"Needs your response"** section: one card per upcoming meeting where the signed-in
    person is an attendee (not organiser, who defaults to Going — see "Open questions") with status
    still "No response," ordered soonest-first, with a quick-respond action directly on the card (no
    need to open the full detail sheet for the common case).
  - The existing Today/Tomorrow agenda lists become **cards** instead of plain list rows, each
    showing the viewer's own response status; a **"Show more" expander** once a day has more than a
    small fixed number of meetings, rather than an ever-growing unbounded list.
  - Room Availability stays out of scope, as the original draft decided — that page is about *room*
    occupancy, not personal attendance, and adding per-attendee status there would answer a question
    the page doesn't ask.
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

- **Status lives per-attendee inside the day item's `meetings` list, as a parallel `attendeeStatuses`
  list next to `attendeeIds`** — not a combined list of `{personId, status}` maps. This reverses this
  doc's own earlier draft (see git history), corrected once `designs/archive/dynamodb-storage-
  compaction.md` shipped (2026-09-20/21, `mootmaker-api` v3.0.0): that design's byte model explicitly
  reserved headroom for exactly this field, sized as **"1 byte code (+1 overhead = 2)" per attendee**,
  under the name `attendeeStatuses`. A combined list of maps is a materially heavier shape — each
  entry becomes a DynamoDB map (its own container overhead) holding a `personId` string plus a
  `status` value that, as an enum *name* (e.g. `"NotResponded"`, 12 bytes), costs roughly 6x the
  reserved 2 bytes — eating back into the margin that work was specifically built to create. The
  parallel-list desync risk the earlier draft worried about (insert/removal drift between two
  independently-maintained lists) doesn't actually apply to this table: per the very next bullet,
  **every write already rewrites the whole day item atomically** under one optimistic lock — there is
  no partial, per-index update anywhere in this model for the two lists to drift apart *between*.
  `attendeeIds`/`attendeeStatuses` are written together, same length, same order, in the same
  transaction, every time — matching how `attendeeIds` itself already has to stay in step with
  `startTime`/`endTime`/`subject` inside the same list entry today.
- **`MeetingRecord.attendeeIds: List<String>` gains a sibling `attendeeStatuses: List<AttendeeStatus>`**,
  same length and order, rather than changing `attendeeIds`'s own element type. The GraphQL-facing
  shape still reads naturally as one list of `{person, status}` pairs (see "Impacts on components")
  — this is purely a storage-layer decision; nothing about the API shape changes from the original
  draft.
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
- **Naming, per Geoff's own explicit invitation to propose it**: enum `AttendeeStatus { GOING,
  NOT_GOING, MAYBE, NO_RESPONSE }`, single-byte storage codes `G`/`N`/`M`/`U`, user-facing labels
  **"Going" / "Not going" / "Maybe" / "No response"**. Plain, everyday words over calendar-invite
  jargon ("Accepted"/"Declined"/"Tentative"/"Needs action") to match this app's existing casual copy
  register throughout ("Free now", "No meetings", "Busy until…") rather than introducing a more
  formal vocabulary found nowhere else in the app. "No response" over the ask's own literal "not yet
  responded" as the *displayed* label — shorter, fits a small badge/chip without wrapping, and reads
  as a state rather than an accusation. The icon prototype (see below) shows this labelling in
  context; flag to override any of it.

## Open questions

Blocking: none remaining — see "Definition of done."

Resolved (confirmed by Geoff; still flag to override):

- Enum names and displayed labels — `Going` / `Not going` / `Maybe` / `No response`.
- Colour mapping — MUI's existing semantic palette (`success`/`error`/`warning`/neutral), not a new
  scheme.
- **Icon treatment — Option A (filled circle + glyph)**. Solid colour fill with a white glyph (check
  / cross / "?" / low-opacity dot for no-response); the status reads from both colour and shape, not
  colour alone. Applies wherever the status badge appears (attendee list, Home cards). See the
  prototype's "Why Option A" panel for the colourblind/greyscale reasoning.
- **Order for the Home page's "Needs your response" cards** — soonest-meeting-first (the most
  actionable ordering: respond to what's coming up soonest), not e.g. most-recently-invited.
- **Organiser gets an implicit default status of Going**, and shows no status control of their own
  (scheduling a meeting *is* confirming attendance) — every other invited attendee starts at
  "no response." Affects both the API's default-on-create behaviour and demo-data's generation
  logic.

Non-blocking, now also confirmed by Geoff:

- **Response changes re-publish `daysInvalidated`** for that date, same as `createMeeting` already
  does (see "Technical considerations").
- **Migration for existing `test`/`production` data: drop and reseed both databases as part of this
  release** (see "Rollout & migration") — not a backfill or a read-tolerant path.

## Impacts on components

- **mootmaker-api**: `api/mootmaker.graphql` — new `AttendeeStatus` enum; `Meeting.attendees` changes
  from `[Person!]!` to a new `Attendee` type wrapping `{ person: Person!, status: AttendeeStatus! }`
  (GraphQL-facing shape unchanged from the original draft — only the DynamoDB storage shape
  underneath it moved to a parallel list, see "Trade-offs and decisions"); new `respondToMeeting`
  mutation, `RespondToMeetingResult`, and its error enum (meeting not found, caller not an attendee
  of that meeting, etc. — mirrors the existing `MeetingError`/`PersonError` pattern of one enum per
  entity). `MeetingRecord` gains `attendeeStatuses: List<AttendeeStatus>` alongside `attendeeIds`;
  its `toAttributeValue`/`fromAttributeValue` read/write both lists together; the resolver layer
  zips them by index into `Attendee` objects for the GraphQL response. `CreateMeetingHandler` sets
  every new attendee's status to `NoResponse` — the organiser's "implicit Going" is a display-time
  default only (see "Open questions"), never a stored value: the organiser is never in
  `attendeeIds`/`attendeeStatuses` at all (`OrganiserIsAttendee` already rejects that), so there is
  no slot to put a status in even if one were wanted. `Meeting.organiser` stays a plain `Person!`,
  unchanged by this design. New `RespondToMeetingHandler` — finds
  the caller's index in `attendeeIds`, writes the same index in `attendeeStatuses`, inside the same
  whole-day conditional rewrite every other write already uses. `deleteMyAccount`'s existing "removes
  them from every upcoming meeting they only attend" logic needs re-verifying against the new shape:
  removing a person now means removing the same index from *both* lists together, not just one.
  Also gained an optional `MeetingInput.attendeeStatuses` override (ignored unless it matches
  `attendeeIds`' length) so `mootmaker-demo-data` can seed a realistic mix without needing
  DynamoDB access or an identity to call the self-only `respondToMeeting` as.
- **mootmaker-android**: not yet implemented (checked 2026-09-21 - the repo is still a placeholder,
  no source code). Nothing to change today; noted so this feature isn't forgotten once that app's
  own work starts, and so its own design doc (whenever written) accounts for status from day one
  rather than bolting it on afterward.
- **mootmaker-demo-data**: `DemoData.java`'s meeting-generation attendee assignment — per Geoff's
  explicit mix, roughly **60% `Going`**, remaining **~40% split randomly across `Not going`/`Maybe`/
  `No response`** (i.e. each of those three roughly ~13.3%, not a fixed round-robin) for every
  non-organiser attendee — organiser is always `Going` per the resolved default above, not part of
  this random mix. Its own inline GraphQL query string (currently `attendees { id }`) needs the same
  shape update as the webapp.
- **mootmaker-webapp**: `webapp/src/graphql/types.ts` hand-maintained mirror + `npm run codegen`;
  `MeetingDetailContent.tsx`'s attendee rows (the one shared component behind both the sheet/panel
  and the full page, per the 2026-09-20 consolidation - superseding this doc's original references
  to `PersonCalendarPage.tsx`'s own `MeetingDetail` and a separate `MeetingDetailsPage.tsx`'s
  `PersonRow`); a new small status icon+colour component (mirrors the existing
  `PersonAvatar`/`roomColorAt` pattern of one small reusable visual unit per concept); a compact
  status-setting control (a select/menu, not a whole form) shown only on the signed-in user's own
  attendee row. `HomePage.tsx`: a new "Needs your response" section/component, and the existing
  `AgendaList` component's List/`ListItemButton` rows becoming Paper cards with a show-more
  expander — see the prototype for the concrete shapes.

## Changes to the domain data model and data storage models

Delta against `docs/reference/data-model.md`'s Meetings table section: `MeetingRecord` gains
`attendeeStatuses: List<AttendeeStatus>`, a new sibling list to the existing `attendeeIds: List<String>`
— same length, same order, index `i` of one corresponds to index `i` of the other. Stored as a
DynamoDB list of single-character/short codes (e.g. `"G"`/`"N"`/`"M"`/`"U"` — see "Open questions" on
final naming), matching the byte budget `designs/archive/dynamodb-storage-compaction.md` already
reserved for this exact field. `data-model.md` needs this section rewritten once implemented, per
this project's "if your change makes a document wrong, fixing it is part of the change" rule —
including correcting its own current note (added during that design's implementation) that
`attendeeStatuses` is "reserved, not built here."

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
- **`publishDaysInvalidated` is called after every successful response change**, confirmed by Geoff,
  same as `createMeeting` already does — so another open tab watching that date sees the updated
  status live via `useDaysInvalidated`'s cache-eviction + `refetchQueries` path, not only on its next
  fetch.
- **Concurrency: `respondToMeeting` writes hit the same single-day-item optimistic lock every other
  write to that date already contends on** — and this design multiplies the ways two writes to the
  *same* day item can race, beyond what `createMeeting` alone sees today. Two cases, both must retry
  on a `version` conflict and both must be covered by real concurrent tests (see "Testing impacts"),
  not just reasoned about:
  1. **Same meeting, different people** — two attendees of the same meeting call `respondToMeeting`
     at the same time. Different index writes into the same `attendeeStatuses` list, but still one
     whole-day rewrite each — the second writer must retry against the first's new `version`, not
     silently overwrite or drop the first response.
  2. **Same person, different meetings, same day** — a person rapidly responds to several meetings
     that happen to fall on the same calendar day. Because storage is one item per *day* (not per
     meeting), these are **not independent writes** the way they'd naively look from the API surface
     — every one of them contends on the exact same day item's lock, so this case is the *more*
     likely one to actually produce conflicts in practice, not a theoretical edge case.
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
- **mootmaker-demo-data**: an invariant that the generated status mix is roughly the confirmed 60%
  `Going`/~13.3% each of the other three, following the pattern of
  `GeneratedDataInvariantsAcceptanceIT`'s existing `guaranteedMeetingsCreated > 0` assertion — but
  see mootmaker-demo-data#32 (filed this session) about that specific assertion's own
  probabilistic-failure shape, and design this new one to avoid the same mistake from the start
  (e.g. assert a generated sample large enough that a deviation from 60/40 outside a wide, explicitly
  chosen tolerance band is what fails, not any single run's natural variance).
- **Concurrency — real integration-layer coverage, per Geoff's explicit ask.** These need to run
  against the real deployed stack (`mootmaker-webapp/acceptance`, this project's real-AWS/real-
  DynamoDB/real-AppSync layer — mocked-integration and e2e can't exercise an actual DynamoDB
  `version`-conditional-write conflict), not just unit-level reasoning about the retry logic. At
  minimum:
  1. **Multiple people responding to the same meeting concurrently** — fire `respondToMeeting` from
     several signed-in clients at the same moment for the same meeting's different attendees, and
     assert every one of their responses is present in the final state (no lost update from the
     day-item `version` race — see "Technical considerations"). Should deliberately try to land the
     requests close enough in time to actually trigger a real conditional-write conflict and exercise
     the retry path, not just each request happening to land sequentially by accident.
  2. **One user rapidly responding to several meetings on the same day** — same client, back-to-back
     (or overlapping) `respondToMeeting` calls for different meetings that share a calendar date.
     Because all of them hit the *same* day item (see "Technical considerations", case 2), this is
     the scenario most likely to actually produce a real `version` conflict — assert all responses
     land correctly and none is silently dropped by a losing writer that failed to retry.
  3. **Apollo cache convergence across clients** — after concurrent writes from (1) and (2), a
     *different* open client watching that date (via the `daysInvalidated` subscription/
     `document.visibilitychange` fallback and `refetchQueries({include:'active'})`, per
     `useDaysInvalidated.ts`) must converge to the true server-side final state for every affected
     attendee, not to a stale value left behind by whichever mutation's optimistic response or cache
     write happened to apply last on that client. Also cover the writer's own tab: `openMeeting`'s
     snapshot state (`useMeetingDetailOverlay.tsx`) must reflect the fresh status after its own
     mutation, not the stale value it was opened with.
  4. Case 2 is also the clearest place to prove the `respondToMeeting` conflict-retry path actually
     retries rather than surfacing a user-visible error on the first `version` clash — this should be
     asserted directly (e.g. success despite deliberately-overlapping concurrent calls), not inferred
     from the absence of a failure.

## Documentation impacts

- `docs/reference/data-model.md` (Meetings table section).
- `mootmaker-api/README.md` and `mootmaker-webapp/README.md`/`testing-strategy.md`, wherever they
  describe the meeting/attendee shape.
- `docs/reference/use-cases.md`: new use cases for setting/changing a response (likely a new
  sub-case under section H, Meeting Detail, currently H.68-73) and for the Home page's "Needs your
  response" section and card-based agenda (extending section D, currently D.21-25). Next free use-
  case id across the whole document is **107** (checked 2026-09-21 - the highest id in use today is
  N.106).

## Rollout & migration

**Geoff's decision: no migration — drop and reseed instead.** `mootmaker-api`'s existing
`database_reset` Lambda (`deploy/terraform/admin-tools.tf`; preserves only Cognito-linked people,
per this project's standing per-environment reset rule) is invoked by hand against `test` and
`production` as part of shipping this release, *before* `release.yml`'s own "Seed \<env\> with demo
data" step runs. Every meeting either database holds after that was created under the new shape
(`attendeeStatuses` present from the start, generated per the 60/40 mix above), so there is no
old-shape data for the read path to tolerate and no backfill Lambda to write. This replaces both
migration paths the original draft considered (backfill Lambda vs. read-path tolerance for a missing
`status`) — neither is needed. Note this is a **manual step outside `release.yml` itself**
(`DemoData.java`'s own doc comment is explicit that seeding "never deletes anything" and reset is "a
separate, deliberate invocation... run by hand before" seeding) — call this out in the release
runbook/PR so it isn't skipped, since `release.yml`'s automatic reseed alone would just add
new-shape meetings on top of old-shape ones still missing `attendeeStatuses`.

## Risks

- **Release coupling** (see Technical considerations): shipping `mootmaker-api` and
  `mootmaker-webapp` out of step breaks the deployed environment until both catch up.
  `release.yml`'s existing all-three-together versioning is the mitigation already in place.
- **Optimistic-lock conflicts, raised from theoretical to a must-test risk per Geoff's ask**: a
  response submitted concurrently with another write to the same day (another meeting created,
  another response set — including two *different* meetings' responses on the same day, since they
  now share the same day item too) can hit the day item's `version` conflict and needs a
  client-side/handler-side retry. `respondToMeeting` must have the same conflict-handling
  `createMeeting` already has — see "Technical considerations" and "Testing impacts" for the two
  concurrency shapes this design specifically needs real acceptance-layer tests for, not just
  reasoning that the existing retry pattern should cover it.

## Implementation checklist

All 20 steps below are complete as of 2026-09-21 (shipped as `v4.0.0`) - kept unedited as a record of
the plan actually followed, with two real divergences worth calling out: step 6's "handler-level
concurrent test coverage" (done, `RespondToMeetingHandlerTest`) still needed step 15's real-DynamoDB
acceptance layer to catch anything, since a fake client can't produce a genuine
`ConditionalCheckFailedException`; and step 12/19 surfaced two gaps this checklist didn't anticipate
- `mootmaker-api`'s separate `verify/` acceptance module (missed until the release build itself
caught it) and `useMeetingDetailOverlay.tsx`'s snapshot staleness for another client's change (missed
until step 15's cache-convergence test ran for real) - both fixed before release. See "Definition of
done" below for the full account.

1. `[Claude]` **mootmaker-api**: `mootmaker.graphql` — `AttendeeStatus` enum, `Attendee` type,
   `Meeting.attendees: [Person!]!` → `[Attendee!]!`, `respondToMeeting` mutation +
   `RespondToMeetingResult`/error enum.
2. `[Claude]` **mootmaker-api**: `MeetingRecord.attendeeStatuses`, `toAttributeValue`/
   `fromAttributeValue`, resolver zip into `Attendee`.
3. `[Claude]` **mootmaker-api**: `CreateMeetingHandler` — organiser `Going`, others `NoResponse`.
4. `[Claude]` **mootmaker-api**: `RespondToMeetingHandler` — self-only, whole-day conditional
   rewrite, conflict retry (same pattern `createMeeting` uses).
5. `[Claude]` **mootmaker-api**: `deleteMyAccount` — remove same index from both lists together.
6. `[Claude]` **mootmaker-api**: unit tests (Testing impacts) + `RespondToMeetingHandler` concurrent
   in-process test covering both race shapes at the handler level (real DynamoDB conflict retry
   still needs the acceptance layer per step 15, but the handler's own retry loop should have unit
   coverage too).
7. `[Claude]` **mootmaker-demo-data**: `DemoData.java` attendee status assignment (60/13.3/13.3/
   13.3), inline GraphQL query string update, mix-invariant test.
8. `[Claude]` **mootmaker-webapp**: `types.ts`/`npm run codegen`, status icon+colour component
   (Option A), self-only status control, `MeetingDetailContent.tsx` attendee rows.
9. `[Claude]` **mootmaker-webapp**: `HomePage.tsx` — "Needs your response" section, Today/Tomorrow
   card redesign with show-more expander (per prototype).
10. `[Claude]` **mootmaker-webapp**: `respondToMeeting` mutation wiring, `daysInvalidated`
    republish confirmed end-to-end, `openMeeting` snapshot refresh after own mutation.
11. `[Claude]` **mootmaker-webapp**: unit/mocked-integration tests (Testing impacts).
12. `[Claude]` **docs**: `data-model.md`, both repos' `README.md`/`testing-strategy.md`,
    `use-cases.md` (starting at id 107).
13. `[Claude]` Deploy all three components to a reused ephemeral env; run the existing acceptance
    suite clean before adding new coverage on top of it.
14. `[Claude]` **mootmaker-webapp/acceptance**: new acceptance tests for the feature itself
    (response control, status display, Home page redesign).
15. `[Claude]` **mootmaker-webapp/acceptance**: the two concurrency scenarios plus Apollo-cache
    convergence, against the ephemeral env (Testing impacts, concurrency bullet) — this is the one
    step of the checklist that specifically needs a real deployed AWS/DynamoDB backend, not a mock.
16. `[Claude]` Full acceptance suite clean on the reused ephemeral env.
17. `[Claude]` Merge implementation PRs to `main` (one per repo, per this project's normal
    branch-and-PR flow).
18. `[Geoff, pre-approved to run autonomously]` Invoke `mootmaker-api`'s `database_reset` Lambda
    against `test`, then `production` (Rollout & migration) — before the release's own seed step.
19. `[Claude]` Dispatch `mootmaker-release`'s Release workflow and watch it to completion
    (deploy-test → smoke-test-test → deploy-production → smoke-test-production).
20. `[Claude]` Move Status to Shipped, move this doc to `designs/archive/`, confirm
    `data-model.md` reflects the shipped shape.

## Definition of done

All met as of 2026-09-21:

- **This feature's own acceptance coverage is green against a real deployed environment**
  (`claude-260920-gzzy`): `acceptance/tests/attendee-response-status.spec.ts`, 4 tests - the feature
  itself (Home page + detail sheet), both concurrency scenarios (proving a real DynamoDB
  `ConditionalCheckFailedException` gets hit and retried, not just reasoned about), and cross-client
  cache convergence. The cache-convergence test failed on its first run and surfaced a real bug -
  `useMeetingDetailOverlay.tsx`'s `openMeeting` snapshot never picked up another client's change -
  fixed with `useFragment` (see `mootmaker-webapp` #107); green after the fix.
- **The full existing acceptance suite is still green on that same environment**: 120/120, run twice
  (once before the fix above, once after, both clean).
- **Each touched repo's own unit tests pass**: `mootmaker-api` (230), `mootmaker-webapp` (99 unit +
  39 mocked-integration), `mootmaker-demo-data` (62).
- **`mootmaker-api` and `mootmaker-webapp` deploy and are smoke-tested clean on both `test` and
  `production`**, via `release.yml` - shipped as `v4.0.0`. First release attempt failed at
  `build-api`'s own `verify/` acceptance module (a separate Java suite this implementation missed
  entirely - see `mootmaker-api` #60); fixed, and the retry deployed clean through to
  `smoke-test-production` with no rollback.
- **`test`/`production` were reset** (`database_reset`, preserving Cognito-linked people in
  production per the standing per-environment rule) **before** the release's own reseed step, so no
  environment ever ran the new API against old-shape data.
- **Documentation**: `data-model.md` and `use-cases.md` (D.107, H.108, M.109-111) are updated;
  `mootmaker-api`/`mootmaker-webapp` READMEs cover the new mutation/type/UI. `designs/` vs
  `designs/archive/` - see "Status" above for why this doc itself stayed put.
