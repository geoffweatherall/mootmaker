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

**Shipped** — 2026-09-24. Implemented across `mootmaker-api` (#66, #67, #68, #69) and
`mootmaker-webapp` (#118, #120, #121), including a real IAM gap (`dynamodb:UpdateItem`) and two
unrelated pre-existing acceptance-suite bugs caught while chasing a clean full run; released as
`v4.4.0` via `mootmaker-release`, deployed to `test` then `production`, both smoke tests green, no
rollback triggered.

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
17. **Editing a meeting's date to a different calendar day is supported**, not blocked. Caught
    mid-implementation: a meeting lives inside one calendar day's DynamoDB item, and moving it
    means removing it from one day's item and adding it to a different one - genuinely two
    separate writes, not something `DayRepository.mutate`'s existing single-day transaction can do
    (it manages exactly one day item plus that day's own pointer diff). Geoff chose to support
    this properly (write-to-new-day-first, then remove-from-old-day) over the simpler
    same-day-only restriction, accepting the added complexity documented in "Technical
    considerations" below - a new `DayRepository.moveMeeting` method, ordered so a failure between
    the two writes leaves the meeting briefly on *both* days (an overcount, harmless, recoverable)
    rather than on neither (unrecoverable data loss). A same-day edit never calls this at all - it
    stays on the existing, unchanged `DayRepository.mutate` path (Decision 6 and "Choices you had
    me make", untouched by this decision).

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
  won't compile until it's added); `realtime/daysInvalidated.ts`'s `evict()` now also evicts every
  `Meeting` a day referenced before evicting the day itself (see "Technical considerations" — a
  fix to shared real-time infrastructure every meeting feature uses, found and made while building
  this one); new acceptance test-case file plus two new cases in `m-cross-cutting.md` (see "Testing
  impacts").
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
  renders — and `cache.gc()` alone turned out not to be enough.** The original plan here was:
  `cancelMeeting` removes a meeting from its Day, `cache.gc()` collects the now-unreachable
  `Meeting:<id>` entity, and `useFragment`'s `complete` flips to `false`. Built and tested against
  the real running app (Integration layer, not just reasoned about), that didn't hold up:
  `daysInvalidated.ts`'s existing `evict()` only ever evicted the `Day:<date>` entity itself,
  leaving each `Meeting`'s own cached fields completely untouched — and Apollo's automatic
  `cache.gc()` does not reliably collect an entity that still has an *active watcher*, which an
  open `MeetingDetailContent`'s own `useFragment` on that exact id always is. Measured directly:
  `complete` sometimes flipped to `false` eventually, sometimes didn't within any reasonable wait,
  never inside a UI-relevant timeframe. Geoff chose the architecturally correct fix over a
  same-tab workaround: `daysInvalidated.ts`'s `evict()` now reads a day's current `meetings` list
  *before* evicting the day, and explicitly `cache.evict()`s every one of those `Meeting:<id>`
  entities too — safe for a meeting that's still valid (the refetch this triggers writes it fresh
  a moment later regardless, same brief-incomplete window every day-level eviction here already
  accepts), and now reliably, quickly incomplete for one that's genuinely gone. This is a fix to
  shared real-time infrastructure every meeting feature uses, not something scoped to edit/cancel
  alone — it was always a latent gap, just one attendee-response-status never needed to expose,
  since RSVP changes a field on a meeting that keeps existing rather than making the meeting itself
  disappear.

  With that fixed, the rest of the original plan holds: `complete` is also `false` for an instant
  before the *first* read resolves, so the sheet needs to distinguish "hasn't loaded yet" from
  "existed, and now doesn't" (a ref/state tracking whether `complete` was ever `true` for this
  meeting id). Once detected, `MeetingDetailContent` shows something in place of the (now-stale)
  frozen content — reusing the existing `EmptyState` component (`components/EmptyState.tsx`) with
  copy like "This meeting was cancelled," never silently continuing to show frozen data and never
  crashing on now-missing fields. The sheet stays open showing that message rather than
  auto-closing (Decision 11).
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
- **A new `DayRepository.moveMeeting` method, for a cross-day edit (Decision 17).** The existing
  pointer write (`pointerPut`, `DayRepository.java:224-233`) is conditional on
  `attribute_not_exists(pk)` — collision-safety for a freshly allocated id, but it means re-adding
  an *existing* id to a different day's `meetings` list via the ordinary `mutate`/`writeItems`
  path would collide with that same id's own still-live pointer at the old date and fail every
  retry identically, not just once. `mutate` is refactored into a shared internal retry/size-check
  loop (`mutateInternal`, parameterised over how pointer-related transaction items are built from
  before/after state) plus two callers: `mutate` itself (unchanged external behaviour — always
  diffs and manages pointers automatically, exactly as today) and the new `moveMeeting`, which
  supplies its own pointer handling instead of the automatic diff:
  1. **Add** the updated record to `toDate`'s day, in the same transaction as an `Update` (not
     `Put`) on the pointer item — `SET date = :toDate` conditional on the pointer's *current* value
     still being `:fromDate`, so two concurrent moves of the same meeting cannot both "win" and
     leave the pointer in an inconsistent state.
  2. **Remove** the record from `fromDate`'s day — a write that must touch *no* pointer at all
     (it was already repointed in step 1), unlike an ordinary loss through `mutate`, which always
     deletes a lost id's pointer as part of its normal diff.

  Add-then-remove is deliberate, not incidental: a failure (a thrown exception, a Lambda timeout,
  the process dying) between the two steps leaves the meeting visible on *both* days — an
  overcount, harmless, and safe for a retry to finish cleaning up — never gone from *both*, which
  nothing could recover. Idempotent by construction: `moveMeeting` starts by reading the pointer
  itself; already at `toDate` means step 1 already committed (this is a retry of a call whose
  first write actually succeeded) and only step 2 runs; still at `fromDate` means neither step has
  run and both do. `UpdateMeetingHandler` calls this only when the requested new date differs from
  the meeting's current one (itself resolved via the existing `findDateOfMeeting`, which already
  backs `Query.meeting(id:)`); a same-day edit never touches any of this and stays on the ordinary,
  completely unchanged `mutate` path.
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
  - New `DayRepositoryTest` cases for `moveMeeting` (Decision 17): a normal move (the record
    appears on `toDate`, is gone from `fromDate`, and the pointer resolves to `toDate` afterward);
    idempotent resume (calling it again after the pointer already points to `toDate` only performs
    the removal, never attempts step 1 twice); a version conflict on either day during either step
    still converges within `MAX_WRITE_ATTEMPTS`; `UpdateMeetingHandler` picks `moveMeeting` only
    when the requested date differs from the meeting's current one, plain `mutate` otherwise
    (asserted at the handler level, not just the repository's).
- **Unit (`mootmaker-webapp`, `webapp/src/**/*.test.ts`, Vitest)**: this layer is pure-logic only
  in this repo — `addMeetingLogic.ts`'s own tests already exist "so they're testable without
  rendering the component or mocking Apollo" (its own doc comment; see `testing-strategy.md`'s
  "Unit tests" section). Nothing here renders `MeetingDetailContent`/`AddMeetingPage` directly, and
  this design doesn't introduce that pattern. A new `addMeetingLogic.test.ts` case covers Decision
  16's reordering directly: the meeting's current room, if present anywhere in `suggestRoom`'s
  returned candidates, is moved to the front before `advanceSuggestion`'s existing cycling logic
  runs; absent from the candidates (e.g. genuinely unavailable or under capacity for the new
  attendee count), the existing ranked-list behaviour is untouched. `daysInvalidated.test.ts`
  (already exists, already exercises `DayInvalidations` directly against a real `InMemoryCache`)
  gains a case for the eviction fix above: invalidating a day also evicts the `Meeting` entities
  it referenced, and leaves an unrelated day's own meeting alone.
- **Integration (`mootmaker-webapp`, `webapp/tests/`, Playwright + MSW)** — this is the layer that
  actually renders and drives the real UI against a mocked API (`vite --mode mock`, no real AWS at
  all); an earlier draft of this doc called this layer "mocked-integration" and proposed jsdom
  component tests with an Apollo `MockedProvider`, a pattern that **doesn't exist anywhere in this
  codebase today** — every existing component-level proof already lives here instead (see
  `attendee-response-status.spec.ts`, `meeting-detail-survives-refetch.spec.ts`). Corrected once
  this was checked against the actual repo rather than assumed. `src/testSupport/mocks/handlers.ts`
  needs new `UpdateMeeting`/`CancelMeeting` cases (mirroring `CreateMeeting`/`RespondToMeeting`'s
  existing shape) before any of this can run at all — without them, an edit or cancel from the UI
  under `vite --mode mock` just hits the handler's "no handler for this operation" fallback. New
  specs cover: the edit form fetching and prefilling from an existing meeting (`meeting-form.spec.ts`
  already covers create; a new `meeting-edit.spec.ts` or an extension of it covers edit reusing the
  same field assertions); Edit/Cancel button visibility under `canEdit` (organiser, admin, neither —
  driven through real sign-ins via `cognito.mock.ts`'s `DEMO_USER`/`ADMIN_USER`, not a synthetic
  prop); the cancel confirmation dialog leaving the meeting's own details visible behind it
  (Decision 5, queryable in the real rendered DOM without unmounting anything); and, mirroring
  `meeting-detail-survives-refetch.spec.ts`'s own established technique (a visibility-triggered
  refetch stands in for a real subscription push, which needs a real AppSync endpoint this layer
  doesn't have) — an open meeting detail sheet reflecting a same-session edit or cancel once that
  same refetch fires, proving `MeetingDetailContent`'s broadened live-fragment binding and its
  "This meeting was cancelled" `EmptyState` actually render correctly, not just that the mechanism
  is plausible in the abstract.
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
  - **Edit a meeting's date to a different day** (Decision 17): the meeting disappears from its
    original date's grid and appears on the new date's, its id is unchanged (the same meeting, not
    a new one — checked via a direct `meeting(id:)` lookup resolving to the new date), and a second
    edit of the same meeting immediately afterward still works (proves the pointer genuinely moved,
    not just the day's own meetings list).
  - Not planned as a new e2e (`e2e/`) case beyond what's listed under Integration above — this
    feature is a straightforward CRUD extension of an existing, already-well-covered mutation
    family, and the acceptance layer against a real environment is the right place to prove the
    authorization boundary specifically, matching how `l-authorization-boundaries.md` already does
    this for `updatePerson`.
  - `mootmaker-release`'s smoke suite is **not** touched — editing/cancelling a meeting isn't part
    of the deliberately minimal five-minute smoke pass, and doesn't change any copy or structure
    the existing smoke suite asserts on.
- **Cross-client live update is proven at two layers, deliberately, not one** — this was under-
  specified in an earlier draft of this doc (only the acceptance layer was there) until Geoff asked
  which layer actually covers it, and the *name* of the other layer was wrong in the draft after
  that (called "mocked-integration" with an Apollo `MockedProvider`, a pattern this codebase
  doesn't use anywhere — corrected above once actually checked against `testing-strategy.md` and
  the existing specs, rather than assumed). The two that actually exist here prove genuinely
  different things and neither substitutes for the other:
  - **Integration (`webapp/tests/`, Playwright + MSW, one browser, no real deployed
    environment)** proves `MeetingDetailContent`'s own rendering logic against the real running
    app, fast and deterministic, using the same visibility-triggered-refetch technique
    `meeting-detail-survives-refetch.spec.ts` already established for exactly this limitation (no
    real AppSync subscription under `vite --mode mock`): open a meeting's detail sheet, mutate the
    MSW fixture directly (an edit or a cancel, via the new `UpdateMeeting`/`CancelMeeting` handler
    cases), fire the same simulated `visibilitychange` refetch, and assert the open sheet now shows
    the new subject/time/room/organiser/attendee-status values, or - for a cancel - the "This
    meeting was cancelled" `EmptyState`, never a crash or stale content.

    Asserting attendee status here too isn't backfilling coverage for unrelated old code for its
    own sake — Decision 10 *relocates* the `useFragment` call itself from
    `useMeetingDetailOverlay.tsx` into `MeetingDetailContent.tsx`, so it stops being untouched,
    pre-existing behaviour and becomes code this design moves and modifies. Today that relocation
    would have **zero** fast-running regression coverage of its own: the only thing that currently
    proves the underlying mechanism works at all is the acceptance-layer M.111, which is slow, runs
    against a real environment, and on a failure wouldn't distinguish "the relocated attendee-status
    binding broke" from "the new subject/time/room logic broke." Covering all fields in the same
    integration spec the new fields already need costs little extra and closes that gap directly,
    for the first time.
  - **Acceptance (`m-cross-cutting.md`/`## M. Cross-cutting`, real deployed environment, two real
    browser contexts)** proves the actual wire mechanism the Integration-layer test above stands in
    for: that a genuine `updateMeeting`/`cancelMeeting` call from one real, independent session
    triggers AppSync's real `daysInvalidated` broadcast, which a second real session actually
    receives, evicts, and refetches — infrastructure neither a mock nor a same-tab visibility
    trigger can exercise at all, since there is
    no real AppSync subscription or Lambda broadcast involved. This is where the project already
    houses cross-client real-time-sync proofs (M.109–M.111, the same mechanism, for
    `respondToMeeting`); two new cases here, directly answering Decision 10:
    - **An edit made by another client is reflected on an already-open meeting detail sheet.**
      Mirrors M.111's exact shape: observer opens a meeting's detail sheet (organiser or an
      unrelated admin session); a second session calls `updateMeeting` directly over the API,
      changing subject and time; the observer's already-open sheet — untouched, no reload or
      navigation — is asserted again and shows the new subject and time within the same window
      M.111 uses (30s).
    - **A cancellation made by another client is reflected on an already-open meeting detail
      sheet.** Same shape, but the second session calls `cancelMeeting`; the observer's sheet is
      asserted to stay open and show the "This meeting was cancelled" `EmptyState`
      (Decisions 10-11), not the stale frozen content, and not an error or a blank crash.
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

Ordered by dependency — `mootmaker-api` first (webapp can't be wired up without the schema it
targets), then `mootmaker-webapp`, then `mootmaker` (hub docs/use-cases), then deploy and verify.
Each repo gets its own `feature/edit-and-cancel-meetings` branch and PR (a PR cannot span repos —
`docs/process/branching-and-prs.md`).

**`mootmaker-api`** (all `[Claude]` unless noted):
1. Add `MeetingNotFound` to `MeetingError` (both `MeetingError.java` and `mootmaker.graphql`,
   mirrored per this repo's convention).
2. Schema: `UpdateMeetingResult`/`CancelMeetingResult` types; `updateMeeting`/`cancelMeeting`
   mutations; `excludingMeetingId: ID` added to `Query.suggestRoom`.
3. New `RoomAvailabilityTest.java`; switch `MeetingValidator.dayStateErrors` from `isFree` to
   `isFreeIgnoring`, threading an `excludingMeetingId` parameter through (`null` from `create`); fix
   `DayIsFull`'s count to exclude that same id when present; new `MeetingValidatorTest` cases
   (self-overlap, day-at-cap-during-edit).
4. Same `isFree` → `isFreeIgnoring` swap in `SuggestRoomHandler.java`, gated on the new
   `excludingMeetingId` argument; new `SuggestRoomHandlerTest` cases.
5. New `DayRepository.moveMeeting` (Decision 17) plus its `mutateInternal` refactor of `mutate` -
   land and unit-test this first, since `UpdateMeetingHandler` depends on it for a cross-day edit.
6. `UpdateMeetingHandler.java`: resolves the meeting's current date via `findDateOfMeeting`
   (`MeetingNotFound` if absent); authorization against the *current* record's organiser
   (`cognitoSubs` contains caller `sub`, or `Identity.isAdmin`) before applying anything, `Forbidden`
   `IllegalStateException` on failure; same-date edit uses the existing `DayRepository.mutate`
   (mirroring `CreateMeetingHandler`'s read-modify-write/retry shape exactly, with
   `excludingMeetingId` threaded through `dayStateErrors`); different-date edit uses the new
   `moveMeeting` instead; `broadcaster.publish` for the date(s) actually written (both, on a move) on
   success. Unit tests: organiser-allowed, admin-allowed, forbidden, not-found,
   concurrent-retry-finds-it-gone, same-date-uses-mutate vs different-date-uses-moveMeeting.
7. `CancelMeetingHandler.java`: same shape, removing the meeting from `meetings` instead of
   replacing a field-set; relies on `DayRepository.writeItems`'s existing pointer diff to delete the
   `PTR#<meetingId>` row. Same unit test set as step 6 (minus the move-vs-mutate case, which has
   no cancel equivalent).
8. Terraform: register both new Lambda handlers the same way `CreateMeetingHandler`'s is wired
   (`deploy/terraform/`), and their AppSync resolvers.
9. `mvn -f impl/pom.xml spotless:apply` and `mvn -f impl/pom.xml test` green.
10. Update `mootmaker-api/README.md`'s data-model section.

**`mootmaker-webapp`**:
11. `graphql/queries.ts`: broaden `MEETING_ATTENDEES_FRAGMENT` to every editable field (subject,
    room, organiser, startTime, endTime, attendees); add `excludingMeetingId` variable to
    `SUGGEST_ROOM`.
12. `graphql/mutations.ts`: `UPDATE_MEETING`/`CANCEL_MEETING`. `graphql/validationMessages.ts`:
    `MeetingNotFound` added to `MEETING_ERROR_MESSAGES` (required for the `Record<MeetingError,
    string>` type to compile once step 1's schema change lands).
13. `npm run codegen` (against the updated `mootmaker-api` schema) and `npm run codegen:check`.
14. Generalize `AddMeetingPage.tsx` for add+edit (Decision 2): a `meetingId` route param switches
    heading/mutation/post-submit navigation; edit mode fetches fresh via the existing `MEETING_BY_ID`
    query (Decision 3), never `location.state`.
15. `addMeetingLogic.ts`: same-room-priority reordering (Decision 16) when editing, plus its unit
    tests.
16. New route `/meetings/:meetingId/edit` in `App.tsx`.
17. `MeetingDetailContent.tsx`: Edit/Cancel icon buttons gated by `canEdit`; the `useFragment`
    live-binding moved in from `useMeetingDetailOverlay.tsx` (now covering every broadened field);
    the "This meeting was cancelled" `EmptyState` on the fragment going incomplete.
    `useMeetingDetailOverlay.tsx` loses the binding it no longer owns.
18. New `CancelMeetingDialog.tsx`, following `DeleteAccountSection`'s confirm-dialog pattern,
    mounted so the sheet/panel stays visible (dimmed) behind it (Decision 5) — never conditionally
    rendered as an alternative to it.
19. Tests: form prefill/submit/`MeetingNotFound` rendering; `addMeetingLogic.ts` reorder test;
    `MeetingDetailContent` button-visibility under `canEdit`; `CancelMeetingDialog` DOM-presence
    test; mocked live-binding tests (all fields including attendee status, plus the
    complete-flips-false → `EmptyState` case) — see "Testing impacts" for the full list.
20. Update `mootmaker-webapp/README.md`.

**`mootmaker`** (hub):
21. `docs/reference/use-cases.md`: new `## O. Edit and Cancel Meetings` section (appended after N).
22. New `acceptance/test-cases/o-edit-and-cancel-meetings.md` in `mootmaker-webapp` (lives in that
    repo, tracked here since it's driven by this doc's own use-case numbering) with every case
    listed under "Testing impacts", plus the two new `m-cross-cutting.md` cases.
23. Corresponding Playwright specs in `mootmaker-webapp/acceptance/tests/`.

**Deploy and verify**:
24. `[Claude]` Create (or reuse this session's) ephemeral environment; deploy `mootmaker-api` then
    `mootmaker-webapp` to it, in that order (webapp reads the API's Terraform outputs).
25. `[Claude]` Fix any bugs surfaced along the way; re-confirm each touched repo's own unit tests.
26. `[Claude]` Full acceptance suite green against that environment — not just the new Section O/M
    cases, the whole existing suite, per this project's actual definition of working.
27. `[Geoff]` Review and merge each repo's PR — no separate approval step beyond reading the diff,
    per `docs/process/branching-and-prs.md`.
28. `[Claude]` Tear down the ephemeral environment once Geoff confirms, as part of finishing.

## Definition of done

Per this project's standard bar: the feature's own new acceptance coverage (Section O, plus the two
new cross-client cases in `m-cross-cutting.md`) is green, the full existing acceptance suite is
still green on a real deployed environment, each touched repo's own unit tests pass, and
`mootmaker-webapp/README.md`, `mootmaker-api/README.md`, and `docs/reference/use-cases.md` are
updated.
