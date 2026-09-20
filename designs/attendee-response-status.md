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

**Drafting** — 2026-09-20, revised 2026-09-21 (Home page scope added, storage shape reconciled with
the now-shipped [`dynamodb-storage-compaction.md`](archive/dynamodb-storage-compaction.md), UI
prototype added, and all blocking open questions resolved: naming/colour/icon, card ordering, and
organiser default status - see below). No blocking open questions remain; awaiting Geoff's move to
Ready.

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

Non-blocking:

- Whether a response change should re-publish `daysInvalidated` for that date (see Technical
  considerations) — likely yes, listed here rather than assumed.
- Migration strategy for existing `test`/`production` data — see "Rollout & migration"; this doc
  recommends read-path tolerance over a backfill Lambda, not yet confirmed.

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
  the organiser's status to `Going` and every other new attendee's to `NoResponse` (see "Open
  questions"). New `RespondToMeetingHandler` — finds
  the caller's index in `attendeeIds`, writes the same index in `attendeeStatuses`, inside the same
  whole-day conditional rewrite every other write already uses. `deleteMyAccount`'s existing "removes
  them from every upcoming meeting they only attend" logic needs re-verifying against the new shape:
  removing a person now means removing the same index from *both* lists together, not just one.
- **mootmaker-android**: not yet implemented (checked 2026-09-21 - the repo is still a placeholder,
  no source code). Nothing to change today; noted so this feature isn't forgotten once that app's
  own work starts, and so its own design doc (whenever written) accounts for status from day one
  rather than bolting it on afterward.
- **mootmaker-demo-data**: `DemoData.java`'s meeting-generation attendee assignment — assign a
  realistic status mix instead of leaving every attendee unset; its own inline GraphQL query string
  (currently `attendees { id }`) needs the same shape update as the webapp.
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
- `docs/reference/use-cases.md`: new use cases for setting/changing a response (likely a new
  sub-case under section H, Meeting Detail, currently H.68-73) and for the Home page's "Needs your
  response" section and card-based agenda (extending section D, currently D.21-25). Next free use-
  case id across the whole document is **107** (checked 2026-09-21 - the highest id in use today is
  N.106).

## Rollout & migration

Existing meetings in `test`/`production` have `attendeeIds: List<String>` with no status. Since a
day item is rewritten whole on every write, no existing item will spontaneously gain the new shape.
Two paths:

1. A `database-repair`-style backfill Lambda (this project's existing `*Repair` pattern) that
   rewrites every existing day item to the new shape, defaulting every existing attendee to
   `NotResponded` (organiser to `Going`, per "Open questions"), before the new schema ships.
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

N/A at Drafting — no blocking open questions remain (see "Open questions"); to be filled in once
this moves to Ready.
