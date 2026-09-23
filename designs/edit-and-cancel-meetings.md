# Edit and cancel meetings

## Summary

Let a meeting's organiser edit or cancel that meeting, and let an admin edit or cancel any meeting.
Adds two new GraphQL mutations (`updateMeeting`, `cancelMeeting`), a new `/meetings/:meetingId/edit`
route reusing `AddMeetingPage`'s form, and Edit/Cancel icon buttons on the shared meeting detail
sheet/panel (`MeetingDetailContent`), gated by `canEdit = isAdmin || meeting.organiser.id ===
personId`. Cancelling is a hard delete — there is no "cancelled" status to show later — behind a
destructive-confirmation dialog matching `DeleteAccountSection`'s existing pattern.

**UI prototype**: https://claude.ai/artifact/7wfP7C39nUiQW7p5fEu789 — both edit-surface options
(Option A: full-page navigation; Option B: dialog-over-sheet) at narrow and wide viewports, plus the
cancel confirmation dialog. Option A is the one this doc builds — see "Trade-offs and decisions".

## Status

**Drafting** — 2026-09-24.

## Scope / non-goals

- **In scope**: editing every field a meeting has (subject, room, organiser, attendees, date, start
  and end time) and cancelling (hard-deleting) a meeting, for the organiser or an admin.
- **Out of scope**: notifying attendees when a meeting they're on is edited or cancelled — no
  notification mechanism exists anywhere in this app today; this is a deliberate follow-up, not an
  oversight (Geoff confirmed explicitly during design).
- **Out of scope**: recurring/series meetings — mootmaker has no concept of a meeting series, so
  there is no "edit this one / edit all" distinction to design.
- **Out of scope**: an attendee removing themselves from a meeting via this feature — that's
  `respondToMeeting`'s job already (setting status), unaffected by this design.
- **Out of scope**: Android. `mootmaker-android` isn't touched — see "Impacts on components".

## Trade-offs and decisions

1. **Edit opens a full page (`/meetings/:meetingId/edit`), not a dialog.** The UI prototype linked
   above showed both: a dialog looked plausible in isolation, but `AddMeetingPage` is already a full
   route navigation from three separate entry points (`HomePage.tsx:397,426`,
   `PersonCalendarPage.tsx:352`, `RoomAvailabilityPage.tsx:360`), including a deliberate FAB
   pre-fill mechanism via `location.state`. Making Edit a dialog while Add stays a page navigation
   would be the one inconsistent outcome between two flows that should feel identical. Geoff chose
   Option A explicitly for this reason.
2. **One shared form component for both Add and Edit**, not two separate ones. `SettingsPage.tsx`'s
   `RoomDialog`/`PersonDialog` already establish this codebase's precedent for a single form
   component handling both create and edit (`room ? 'Edit room' : 'Add room'`). `AddMeetingPage.tsx`
   becomes (or is wrapped by) a component that both `/meetings/add` and
   `/meetings/:meetingId/edit` render, switching on whether a `meetingId` route param is present:
   heading ("Add Meeting" vs "Edit Meeting"), mutation (`CREATE_MEETING` vs `UPDATE_MEETING`), and
   post-submit navigation differ; the field set, `addMeetingLogic.ts`'s pure logic (organiser/
   attendee mutual-exclusion filtering, suggestion-cache, time defaults), validation display, and
   `MEETING_ERROR_MESSAGES` all stay identical and unduplicated.
3. **Edit always fetches the meeting fresh by id, never trusts `location.state` or an in-memory
   snapshot.** This makes a bookmarked/shared `/meetings/:meetingId/edit` link work (consistent
   with why the full page `/meetings/:meetingId` route was kept alive in
   `meeting-detail-consolidation.md`) and avoids editing stale data if the sheet's snapshot has
   drifted from the server. Reuses the same query `MeetingDetailsPage.tsx` already runs for the
   full-page detail view (names pre-resolved server-side, matching `MeetingDetails`'s shape).
4. **Cancel is a hard delete, not a soft "Cancelled" status.** Geoff chose this explicitly, aware of
   the trade-off: nothing will show "this meeting was cancelled" later, to an attendee or anyone
   else — it simply stops existing, the same outcome `deleteMyAccount`'s existing
   `cancelUpcomingMeetings` cascade already produces for a deleted user's meetings
   (`DeleteMyAccountHandler.java:38,114,155`). `cancelMeeting` is the same operation, exposed as its
   own explicit, organiser/admin-gated mutation instead of only ever happening as an account-deletion
   side effect.
5. **The cancel confirmation dialog must not hide the meeting being cancelled.** Caught during UI
   prototyping: an early version of the mockup made the meeting detail sheet/panel disappear the
   instant the confirmation dialog opened, which was a mockup-only bug (its states were built as
   mutually exclusive) rather than an intended behaviour — but it's exactly the kind of thing worth
   nailing down explicitly here so a real implementation doesn't reproduce it by, say, conditionally
   rendering the sheet and the dialog as alternatives. **Requirement**: the sheet/panel stays
   mounted and visible (dimmed by the dialog's own backdrop, not unmounted) behind the confirmation
   dialog, so the person confirming can still see which meeting — subject, time, room, attendees —
   they're about to permanently delete. This is a natural consequence of using a real MUI `Dialog`
   (a portal that overlays without unmounting what's behind it) rather than anything requiring new
   engineering — the risk is purely in *how* it gets built. Stated explicitly here, and turned into
   an acceptance assertion (see F.new below under "Testing impacts"), specifically so it doesn't
   regress silently.
6. **`updateMeeting` is a full field replacement, exactly like `updateRoom`/`updatePerson`.** Both
   existing update mutations take `(id: ID!, <Entity>Input!)` and replace every field
   (`mootmaker.graphql:65,69`) — there is no partial-patch convention anywhere in this API to
   deviate toward. `updateMeeting(id: ID!, meeting: MeetingInput!): UpdateMeetingResult!` reuses the
   existing `MeetingInput` unchanged.
7. **Reassigning the organiser via Edit is allowed**, for both the organiser and an admin, with no
   special-casing — full parity with `createMeeting`, which already allows picking any organiser.
   The consequence (the meeting's new organiser, not the person who made the edit, is who can edit
   it *next* time, since `canEdit` is computed live from the meeting's current organiser on every
   view) falls out naturally from `canEdit`'s definition rather than needing its own rule.
8. **Authorization failures are a thrown exception, not a typed `MeetingError`**, mirroring
   `UpdatePersonHandler.java:91-97` exactly (`IllegalStateException("Forbidden: ...")`, surfaced by
   AppSync as a top-level GraphQL error). Neither `RoomError` nor `PersonError` has a `Forbidden`
   case for the same reason (`mootmaker.graphql:131-136,206-210`) — this codebase already treats
   "not allowed to do this at all" and "allowed, but the input was invalid" as two different
   channels, and there's no reason to invent a third shape for meetings.
9. **`MeetingNotFound` is added to the existing `MeetingError` enum**, not a new enum. Precedent:
   `RoomError`/`PersonError` each gained exactly one `*NotFound` case when their `update` mutation
   was added (`mootmaker.graphql:134-135,208-209`) — "update-only: id did not match any existing
   X." `respondToMeeting`'s separate `RespondToMeetingError` enum (`mootmaker.graphql:247-254`) is
   not the precedent to follow here; that mutation's error set is genuinely disjoint from
   `createMeeting`'s, where `updateMeeting`/`cancelMeeting` share nearly all of theirs with it.
10. **An already-open meeting detail sheet/panel must reflect another client's edit or cancellation
    live, with no reload** — this app already promises exactly that for attendee responses
    (`designs/archive/attendee-response-status.md`, proven by acceptance case M.111, "A response
    made by another client is reflected live"), and there is no principled reason edit/cancel
    should be held to a weaker bar than RSVP was. This is **not automatic** from the existing
    `daysInvalidated` broadcast alone — see "Technical considerations" for why, and what has to
    change. I did not address this in the first draft of this doc; Geoff caught the gap.
11. **When a meeting a viewer has open gets cancelled by someone else, the sheet stays open showing
    "This meeting was cancelled" rather than auto-closing** — Geoff confirmed. Auto-closing a panel
    out from under someone reading it would be its own kind of surprising; `EmptyState` already
    establishes the visual language for this without needing a timed dismissal anywhere else in the
    app.
12. **No restriction based on whether the meeting has already happened or is in progress** — Geoff
    chose this explicitly over `deleteMyAccount`'s "past meetings untouched" precedent, which is
    narrower and account-deletion-specific, not a general precedent this feature has to follow.
    `updateMeeting`/`cancelMeeting` apply the same field-level validation `create` already does to
    the *requested* new time (15-minute boundary, `OutsideBookableRange` against the submitted
    start/end, capacity, room availability) but add no check of the *existing* meeting's own
    start/end against the current time at all — a meeting that ended yesterday, or one happening
    right now, can be edited or cancelled exactly like one next week.
13. **A hidden Edit/Cancel button shows nothing — no disabled state, no tooltip.** Matches
    `AttendeeStatusControl`'s existing precedent (shown only to an attendee, absent otherwise) —
    Geoff confirmed keeping this consistent rather than introducing a new disabled-with-tooltip
    pattern for just this one control.
14. **The cancel confirmation dialog uses the same generic copy regardless of who's cancelling** —
    "This permanently deletes '\<subject\>' for every attendee..." whether it's the organiser
    cancelling their own meeting or an admin cancelling someone else's. Geoff confirmed; one string,
    no admin-specific variant naming the organiser.
15. **`suggestRoom` must also ignore the meeting being edited, and gets a new optional
    `excludingMeetingId: ID` argument for it.** Caught during review: editing a meeting's time
    within its own current room (e.g. 10:00–11:00 → 10:30–11:30 in Room A) must not make Room A
    look unavailable because of the meeting's own prior 10:00–11:00 record, either when
    `updateMeeting` saves (Decision/"Choices" below) **or** when the Edit form's "Suggest a room"
    button is pressed — `SuggestRoomHandler.java:83-88` filters candidate rooms through the same
    `RoomAvailability.isFree` with no exclusion at all today, so it has the identical bug, in a
    second place I hadn't originally covered. `excludingMeetingId` is optional and only ever sent by
    the webapp in edit mode; create's call to `suggestRoom` is unaffected (the argument is simply
    absent, same as today). Schema: `suggestRoom(startTime: String!, endTime: String!,
    requiredCapacity: Int!, excludingMeetingId: ID): [Room!]!`.
16. **"Suggest a room" prioritizes the meeting's current room when editing, done client-side, not
    as new backend ranking logic.** Geoff asked for this "if not too complex" — it isn't: the
    backend keeps returning its existing ranked list (smallest surplus capacity first,
    `SuggestRoomHandler.java:18-19`) unchanged; `addMeetingLogic.ts` (already pure, already
    unit-tested, already the sole owner of `advanceSuggestion`'s cycling behaviour) gets one added
    step in edit mode only: before applying the existing cache/cycling logic, if the meeting's
    current room appears anywhere in the (correctness-fixed) returned candidates, move it to the
    front. No new backend ranking rule, no new schema field beyond Decision 15's
    `excludingMeetingId` (which this reuses), and it's a pure-function change to test the same way
    `addMeetingLogic.test.ts` already tests the rest of this file.

## Choices you had me make

- The `location.state` FAB pre-fill mechanism (Decision 3) is deliberately *not* reused for Edit —
  Edit always queries fresh. I made this call unilaterally; it's cheap to revisit if a future
  entry point wants to pre-seed an edit form with something not on the meeting record itself.
- Field validation on Edit reuses every rule Create already enforces (15-minute boundary,
  organiser/attendee mutual exclusion, capacity, room availability, subject length) with one
  necessary change: the room-availability/double-booking check must exclude the meeting's own
  existing slot when checking room availability for an update, or every edit would spuriously
  conflict with itself — e.g. moving a 10:00–11:00 meeting in Room A to 10:30–11:30, still in Room
  A, must not reject against its own old 10:00–11:00 record. I've treated this as an obvious
  technical necessity rather than a design decision, but flagging it here since it turns out the
  fix already half-exists: `RoomAvailability.java` has an `isFreeIgnoring(meetingsThatDay, roomId,
  startTime, endTime, ignoredMeetingId)` method today, with **zero callers anywhere in the
  codebase** and no test file of its own — `MeetingValidator.dayStateErrors` calls the plain
  `isFree` and needs to switch to `isFreeIgnoring`, passing the meeting's own id on update (`null`/
  absent on create, unchanged). The same swap is needed a second time in `SuggestRoomHandler.java`
  — see Decision 15.
- **`dayStateErrors`'s `DayIsFull` check also needs adjusting for update**, a related gap I found
  while reading that method: `meetingsThatDay.size() >= Limits.MAX_MEETINGS_PER_DAY`
  (`MeetingValidator.java:80-81`) counts the meeting being edited as part of the day's total, so
  editing a meeting on a day that's already exactly at the cap would spuriously reject as
  `DayIsFull` even though editing never changes the day's meeting count. `dayStateErrors` needs to
  exclude the meeting-being-edited from that count too when an `excludingMeetingId` is present
  (effectively comparing against `meetingsThatDay.size() - 1`), not just from the room-availability
  check.

## Open questions

None outstanding. All three raised during drafting (past/in-progress meetings; hidden vs.
disabled-with-tooltip buttons; admin-specific cancel copy) were resolved directly with Geoff — see
Decisions 12–14.

## Impacts on components

- **`mootmaker-api`** (schema + handlers): new `updateMeeting`/`cancelMeeting` mutations,
  `UpdateMeetingResult`/`CancelMeetingResult` types, `MeetingNotFound` added to `MeetingError`,
  `UpdateMeetingHandler.java`/`CancelMeetingHandler.java`, a shared authorization helper (organiser
  `cognitoSubs` contains caller sub, or `Identity.isAdmin`); `MeetingValidator.dayStateErrors`
  switched to the already-existing-but-unused `RoomAvailability.isFreeIgnoring` plus a `DayIsFull`
  count fix (Decisions 15-16, "Choices you had me make"); `Query.suggestRoom` gains the optional
  `excludingMeetingId: ID` argument and the same `isFreeIgnoring` swap in `SuggestRoomHandler.java`;
  a new `RoomAvailabilityTest.java` (doesn't exist today) covering `isFreeIgnoring` directly.
- **`mootmaker-webapp`**: new `/meetings/:meetingId/edit` route in `App.tsx`; `AddMeetingPage.tsx`
  generalized to handle both add and edit (Decision 2), including passing `excludingMeetingId` on
  its `SUGGEST_ROOM` call and reordering results to prioritize the meeting's current room (Decision
  16, in `addMeetingLogic.ts`); `MeetingDetailContent.tsx` gains Edit and Cancel icon buttons, the
  cancel confirmation dialog (a new `CancelMeetingDialog.tsx`, following `DeleteAccountSection`'s
  pattern), and the `useFragment` live-binding moved in from `useMeetingDetailOverlay.tsx`
  (Decision 10) plus the "meeting no longer exists" `EmptyState`; `graphql/queries.ts`'s
  `MEETING_ATTENDEES_FRAGMENT` broadened to cover every editable field, not just `attendees`, and
  `SUGGEST_ROOM` gains the `excludingMeetingId` variable; `graphql/mutations.ts` gains
  `UPDATE_MEETING`/`CANCEL_MEETING`; `graphql/validationMessages.ts`'s `MEETING_ERROR_MESSAGES`
  gains `MeetingNotFound` (required — the map is typed `Record<MeetingError, string>`, so this
  won't compile until it's added); new acceptance test-case file plus two new cases in
  `m-cross-cutting.md` (see "Testing impacts").
- **`mootmaker`** (hub): this design doc; `docs/reference/use-cases.md` gains a new Section O; no
  change needed to `docs/reference/data-model.md` — no storage shape changes (see "Changes to the
  domain data model").
- **Not touched**: `mootmaker-android`, `mootmaker-demo-data`, `mootmaker-ephemeral-envs`,
  `mootmaker-release`, `mootmaker-bootstrap-terraform`, `mootmaker-bootstrap-aws-accounts`,
  `mootmaker-email-testing`, `mootmaker-sensitive-designs`.

## Changes to the domain data model and data storage models

N/A for storage shape — no new DynamoDB attributes, tables, or indexes. `updateMeeting` and
`cancelMeeting` both go through the existing `DayRepository.mutate` read-modify-write path
(`DayRepository.java:140-171`), the same one `createMeeting` already uses: read the `DAY#<date>`
item with `ConsistentRead`, rebuild the whole `meetings` List (`MeetingRecord.java:67-98` — it's a
List, not a map keyed by id, so both update and cancel filter/replace by matching `id` in
application code), and `Put` it back conditional on `version`, retrying up to
`DayRepository.MAX_WRITE_ATTEMPTS` (5) on a version conflict. `cancelMeeting` removing an entry from
`meetings` means `writeItems`'s existing before/after id-set diff (`DayRepository.java:184-187`)
deletes that meeting's `PTR#<meetingId>` pointer automatically, in the same transaction, with no new
code — this is exactly the mechanism it already exists for. The only schema-level addition is the
`MeetingNotFound` case on the existing `MeetingError` enum (mirrored in both
`MeetingError.java` and `mootmaker.graphql`, per this repo's error-enum convention).

## Technical considerations

- **Why the existing `daysInvalidated` broadcast alone is not enough for an open sheet.** Cancelling
  or creating a meeting already broadcasts `publishDaysInvalidated` → `Subscription.daysInvalidated`
  → every other client evicts its `Day:<date>` cache entry and (via `cache.gc()`,
  `daysInvalidated.ts:66`) garbage-collects any now-unreachable normalized entity — this is real and
  correct, and it's exactly why the underlying page (Home, Room Availability, Person Calendar) behind
  an open sheet already updates its list/grid live today. The gap is narrower and more specific: the
  **open sheet itself** does not read from that refetched Day query. `useMeetingDetailOverlay.tsx`'s
  `openMeeting` is `useState` set once, from whichever `Meeting` object the caller passed to `open()`
  at click time — a frozen snapshot, deliberately, per `resolveMeetingDetails`'s own doc comment
  (`useMeetingDetailOverlay.tsx:9-13`). The one thing that currently escapes that freeze is attendee
  status, via `MEETING_ATTENDEES_FRAGMENT` and `useFragment` (`queries.ts:184-203`) — Apollo's
  mechanism for reading one normalized entity's *current* cached fields regardless of which query
  populated them, independent of the frozen snapshot around it. Its own doc comment is explicit that
  the snapshot was considered "correct for fields that never change after creation (subject, times,
  room, organiser)" — true when that comment was written, false as soon as `updateMeeting` exists.
- **The fix: broaden the existing fragment, and move it to where both surfaces share it.**
  `MEETING_ATTENDEES_FRAGMENT` becomes a fragment covering every field `updateMeeting` can change
  (`subject`, `room { id name }`, `organiser { id name }`, `startTime`, `endTime`, `attendees` as
  today) — the same `useFragment` mechanism, just no longer artificially narrowed to the one field
  that used to be the only mutable one. The `useFragment` call itself should move from
  `useMeetingDetailOverlay.tsx` into `MeetingDetailContent.tsx`, the single shared render surface
  ("PARITY INVARIANT", `MeetingDetailContent.tsx:34-41`) — not just for symmetry, but because
  `MeetingDetailsPage.tsx` (the full-page bookmarked-link view) currently has **no live binding of
  any kind**, not even for attendee status (`MeetingDetailsPage.tsx` runs a plain one-shot
  `useQuery(MEETING_BY_ID)`); moving the fragment into the shared component fixes that pre-existing
  gap for free, consistent with the whole reason that component exists. As long as something is
  still watching the underlying Day query (true whenever the sheet/panel is open, since opening it
  requires the hosting page to be mounted; also true for `MeetingDetailsPage` itself, which runs its
  own `MEETING_BY_ID` query), the ordinary gap-refetch after eviction writes fresh field values into
  the normalized `Meeting:<id>` entity, and the broadened fragment picks them up with no new
  plumbing beyond the fragment's field list.
- **Detecting "this meeting no longer exists" needs the fragment's `complete` flag, tracked across
  renders.** When `cancelMeeting` removes a meeting from its Day and `cache.gc()` collects the
  now-unreachable `Meeting:<id>` entity, `useFragment`'s `complete` flips to `false` — but `complete`
  is also `false` for an instant before the *first* read resolves, so the sheet needs to distinguish
  "hasn't loaded yet" from "existed, and now doesn't" (e.g. a ref/state tracking whether `complete`
  was ever `true` for this meeting id). Once detected, `MeetingDetailContent` should show something
  in place of the (now-stale) frozen content — reusing the existing `EmptyState` component
  (`components/EmptyState.tsx`) with copy like "This meeting was cancelled," never silently
  continuing to show frozen data and never crashing on now-missing fields. The sheet stays open
  showing that message rather than auto-closing (Decision 11).
- **`MeetingValidator.dayStateErrors` needs to call `RoomAvailability.isFreeIgnoring`, not
  `isFree`.** Today it checks `RoomAvailability.isFree(meetingsThatDay, roomId, startTime,
  endTime)` (`MeetingValidator.java:85-90`) against every meeting already in the day. For an
  update, the meeting being edited is itself in `meetingsThatDay` and must be excluded before that
  check runs, or editing a meeting's own unchanged (or merely overlapping) time/room would fail as
  a self-conflict — e.g. 10:00–11:00 → 10:30–11:30 in the same room, which genuinely overlaps its
  own prior slot by design, must still succeed. `RoomAvailability.isFreeIgnoring(meetingsThatDay,
  roomId, startTime, endTime, ignoredMeetingId)` already exists for exactly this (`ignoredMeetingId`
  filtered out before the overlap check runs) but has no callers and no tests today — `create`
  keeps calling plain `isFree`; `update` switches to `isFreeIgnoring` with its own id.
  `dayStateErrors`'s `DayIsFull` count needs the same exclusion (see "Choices you had me make").
  `SuggestRoomHandler.java:83-88` needs the identical swap, gated on the new
  `excludingMeetingId` GraphQL argument (Decision 15) — it has the same bug today, since "Suggest a
  room" pressed while editing would otherwise also see the meeting's own current room as occupied
  by its own prior slot and wrongly drop it from the candidate list.
- **The optimistic-locking retry loop is what makes concurrent edit/cancel safe, not new code.**
  Two admins cancelling the same meeting at once, or an organiser editing while an admin cancels,
  both resolve via `DayRepository`'s existing version-conditional retry
  (`DayRepository.java:140-171`): the loser's retry re-reads the day, finds the meeting already gone
  from `meetings`, and its mutation function should return `MeetingNotFound` rather than silently
  no-op-ing or throwing an unrelated error — this needs the read-modify-write callback itself (not
  just the up-front `validateRequest` pass) to check the target id still exists, the same way
  `dayStateErrors` is already re-run inside the retry loop for create (per
  `CreateMeetingHandler.java:117-181`'s existing shape).
- **Real-time**: after a successful write, both new handlers call `broadcaster.publish(List.of(date))`
  (`DaysInvalidatedPublisher`), exactly as `CreateMeetingHandler.java:109` and `respondToMeeting`
  already do, so other open clients' `Day:<date>` cache entries get evicted and refetched. On the
  webapp side, the mutating client calls `dayInvalidations.noteOwnWrite([date])` after success
  (matching `AddMeetingPage.tsx:248`'s existing call), so the person who just edited or cancelled
  doesn't see their own screen flicker from the invalidation they themselves triggered. If an edit
  changes the meeting's date, both the old and new date need broadcasting — this can't happen today
  purely from the form, since the date and time pickers always combine into a single-day
  `startTime`/`endTime`, so this is really "cancel's old date" only for a delete, and update's one
  date (same as create).
- **Byte-size check applies to updates too.** `DayRepository.mutate`'s `ItemSizer.sizeOf` check
  (`DayRepository.java:146-150`) already guards every write; an edit that adds many attendees or a
  much longer subject to an otherwise-full day could in principle trip `DayItemTooLargeException`,
  surfaced the same way create already surfaces it (as `DayIsFull`) — no new handling needed, just
  worth knowing it applies here too.
- **Top-level (Forbidden) errors need the app's existing generic error handling, not new UI.** A
  rejected `updateMeeting`/`cancelMeeting` due to authorization surfaces as a top-level GraphQL
  error (Decision 8), not inside `errors: [MeetingError!]!`. `mootmaker-webapp/README.md` documents
  how the app already handles errors generically; confirm during implementation that this path
  (rather than `ErrorBanner`, which only reads the typed `errors` array) is what actually surfaces
  a Forbidden rejection to the user, since in practice it should be unreachable from the UI (the
  Edit/Cancel buttons are already hidden for anyone `canEdit` would reject) and only reachable via a
  direct GraphQL call bypassing the UI, same as `OrganiserIsAttendee` is tested today (F.45's
  technique).

## Testing impacts

- **Unit (`mootmaker-api`)**:
  - New `RoomAvailabilityTest.java` (none exists today) testing `isFreeIgnoring` directly: the
    excluded meeting's own overlapping slot does not block its own room (the user's exact
    10:00–11:00 → 10:30–11:30-in-Room-A example, as a named case); a genuine conflict from a
    *different* meeting in that room still blocks it even when a (different) id is excluded;
    excluding an id that doesn't appear in `meetingsThatDay` behaves identically to plain `isFree`.
  - `MeetingValidatorTest` gains: the same overlap-with-self case exercised through
    `dayStateErrors` end to end (not just the `RoomAvailability` unit); a day already at
    `MAX_MEETINGS_PER_DAY` does *not* reject an edit to one of the meetings already counted in it
    ("Choices you had me make"'s `DayIsFull` fix).
  - New `SuggestRoomHandlerTest` cases: a room currently occupied only by the meeting named in
    `excludingMeetingId` is returned as a candidate for a new, overlapping time range; a room with a
    genuine conflict from a *different* meeting is still correctly excluded even when
    `excludingMeetingId` is set (proves the exclusion is scoped to the one named meeting, not a
    blanket bypass); `excludingMeetingId` absent (create's call shape) behaves exactly as today.
  - New handler unit tests for `UpdateMeetingHandler`/`CancelMeetingHandler` covering
    organiser-allowed, admin-allowed, neither-rejected (`Forbidden`), and `MeetingNotFound` (an id
    that doesn't resolve to any meeting, and the concurrent-retry case where it stops existing
    mid-retry).
- **Unit/mocked-integration (`mootmaker-webapp`)**: the generalized add/edit form component gets
  tests for prefilling from a fetched meeting, submitting `UPDATE_MEETING` instead of
  `CREATE_MEETING`, and the new `MeetingNotFound` error message rendering. A new `addMeetingLogic.ts`
  test covers Decision 16's reordering: the meeting's current room, if present anywhere in
  `suggestRoom`'s returned candidates, is moved to the front before `advanceSuggestion`'s existing
  cycling logic runs; absent from the candidates (e.g. genuinely unavailable or under capacity for
  the new attendee count), the existing ranked-list behaviour is untouched. `MeetingDetailContent`
  gets tests for the Edit/Cancel buttons' visibility under `canEdit` (organiser, admin,
  neither) — mocked, since this is pure permission-flag logic with no need for a real deployed
  environment. `CancelMeetingDialog` gets a test asserting the underlying sheet/panel content is
  still present in the DOM (not unmounted) while the dialog is open, directly covering Decision 5.
- **Acceptance** (real deployed environment, per this project's usual definition of done): a new
  `o-edit-and-cancel-meetings.md` test-case file (to be created under `acceptance/test-cases/` in
  `mootmaker-webapp`, following this doc's own naming convention) and a matching new
  `## O. Edit and Cancel Meetings` section in `mootmaker/docs/reference/use-cases.md` (appended
  after N, following the precedent `n-date-time-format-settings.md` already set for a section added
  after the original A–M set rather than relettering everything to keep thematic ordering — see
  that file's own history). At minimum:
  - Organiser edits their own meeting (happy path): change subject and time, save, see the change
    reflected on the grid/detail sheet.
  - **Edit a meeting's time within its own current room, where the new range overlaps the old
    one** (e.g. 10:00–11:00 → 10:30–11:30, same Room A): saving succeeds, with no
    `TimeRangeUnavailable` error, and the meeting shows the new time on the grid. Then, still
    editing (or re-opening edit), pressing **Suggest a room** for that same new time also succeeds
    and offers Room A — not skipped, not passed over — as the top suggestion (Decisions 15-16).
    This is the specific case that motivated `RoomAvailability.isFreeIgnoring` actually being wired
    up, so it's covered end to end here, not just at the unit layer.
  - Admin edits a meeting they don't organise.
  - A signed-in user who is neither the organiser nor an admin does not see Edit/Cancel buttons on
    that meeting's detail sheet.
  - Forced server-side authorization check via a raw authenticated GraphQL call bypassing the UI
    (mirroring F.45's technique) — confirms the "not authorized" case is enforced by the API, not
    just hidden in the UI.
  - Organiser cancels their own meeting: confirms the meeting's own details (subject, time, room)
    remain visible, dimmed, behind the confirmation dialog (Decision 5's explicit assertion — not
    just "a dialog appears"), and that confirming removes the meeting from the grid.
  - Admin cancels a meeting they don't organise.
  - `MeetingNotFound`: two admins both try to cancel the same meeting; the second gets a graceful
    error, not a crash or a silent no-op.
  - A past meeting (already ended) and a currently-in-progress meeting can both still be edited and
    cancelled by their organiser or an admin, same as an upcoming one (Decision 12) — one case per
    state is enough to prove no time-based restriction was accidentally introduced.
  - Not planned as a new e2e (mocked-integration) case beyond what's listed under unit/mocked
    integration above — this feature is a straightforward CRUD extension of an existing,
    already-well-covered mutation family, and the acceptance layer against a real environment is
    the right place to prove the authorization boundary specifically, matching how
    `l-authorization-boundaries.md` already does this for `updatePerson`.
  - `mootmaker-release`'s smoke suite is **not** touched — editing/cancelling a meeting isn't part
    of the deliberately minimal five-minute smoke pass, and doesn't change any copy or structure
    the existing smoke suite asserts on.
- **Acceptance — cross-client live update**: two new cases in the existing
  `m-cross-cutting.md`/`## M. Cross-cutting` (not the new O section — this is where the project
  already houses cross-client real-time-sync proofs, per M.109–M.111 covering the same mechanism
  for `respondToMeeting`), directly answering Decision 10 and this doc's own earlier gap:
  - **An edit made by another client is reflected on an already-open meeting detail sheet.** Mirrors
    M.111's exact shape: observer opens a meeting's detail sheet (organiser or an unrelated admin
    session); a second session calls `updateMeeting` directly over the API, changing subject and
    time; the observer's already-open sheet — untouched, no reload or navigation — is asserted again
    and shows the new subject and time within the same window M.111 uses (30s).
  - **A cancellation made by another client is reflected on an already-open meeting detail sheet.**
    Same shape, but the second session calls `cancelMeeting`; the observer's sheet is asserted to
    stay open and show the "This meeting was cancelled" `EmptyState` (Decisions 10-11), not the
    stale frozen content, and not an error or a blank crash.
  - Both reuse `tests/attendee-response-status.spec.ts`'s existing two-browser-context technique
    (M.111's own Steps/Preconditions shape) rather than inventing a new one.

## Documentation impacts

- `mootmaker-webapp/README.md` gains a short section on Edit/Cancel, alongside the existing "Meeting
  details: one shared surface" section, cross-referencing `MeetingDetailContent.tsx`'s new buttons
  and the generalized add/edit form.
- `mootmaker-api/README.md`'s data-model section gains the two new mutations and the
  `MeetingNotFound` error case, matching how `respondToMeeting` is already documented there.
- `mootmaker/docs/reference/use-cases.md` gains Section O (see "Testing impacts").
- `docs/reference/data-model.md`: no change (see "Changes to the domain data model").

## Rollout & migration

No data migration or backfill — purely additive API surface (two new mutations, one new enum case)
and new webapp routes/buttons over existing, unchanged storage. No feature flag: both mutations are
authorization-gated at the API layer regardless of whether the webapp UI exposing them has deployed
yet, so there's no unsafe intermediate state to gate against — deploying the API first and the
webapp second (or the reverse) is both fine. Deploys cleanly through the normal
ephemeral → `production` path via `mootmaker-release`, same as every other feature.

## Risks

- **Hard delete is irreversible by design** (Decision 4, made explicitly, not overlooked). The
  confirmation dialog (Decision 5) is the whole mitigation — same accepted trade-off as
  `delete-my-account.md`'s own "friction, no re-authentication" precedent. There is no undo, no
  trash/recovery window, and no audit trail of who cancelled what.
- **Enum addition compatibility**: adding `MeetingNotFound` to the shared `MeetingError` GraphQL
  enum is additive and should be backward compatible for any existing client selecting on it
  (unknown-enum-value handling is typically graceful in generated GraphQL clients), but
  `mootmaker-android` was not researched as part of this design — worth a quick check during
  implementation that its GraphQL client tolerates an enum gaining a case it doesn't recognise,
  even though Android has no UI work in this feature.
- **Reassigning the organiser (Decision 7)** means a meeting's edit/cancel permissions can change
  out from under the person currently looking at it (they edit themselves out as organiser, then
  immediately lose their own Edit/Cancel buttons on next render/refetch) — intentional, not a bug,
  but worth knowing it's a real, reachable interaction rather than a theoretical one.

## Implementation checklist

Deliberately sparse while Drafting — filled in properly once Status moves to Ready (this doc's own
convention, see `designs/README.md`).

## Definition of done

Per this project's standard bar: the feature's own new acceptance coverage (Section O, plus the two
new cross-client cases in `m-cross-cutting.md`) is green, the full existing acceptance suite is
still green on a real deployed environment, each touched repo's own unit tests pass, and
`mootmaker-webapp/README.md`, `mootmaker-api/README.md`, and `docs/reference/use-cases.md` are
updated.
