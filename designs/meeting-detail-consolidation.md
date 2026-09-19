# Meeting detail consolidation

## Summary

Consolidate every place a meeting's details can be viewed into one shared mechanism — a mobile-first
slide-up bottom sheet / desktop slide-out side panel, extracted from `PersonCalendarPage.tsx`'s
existing `MeetingDetail` so the Home page and Room Availability can open it too, instead of
navigating to the separate full-page `/meetings/:id` route. That full page is **retained**, but only
as the landing target for a shared/bookmarked/direct URL — nothing in the app links to it any more —
and its own layout, which has visibly drifted from the sheet/panel, is brought back into parity with
it. Converts [mootmaker-webapp#74](https://github.com/geoffweatherall/mootmaker-webapp/issues/74)'s
inventory into a concrete decision on all five entry points it listed.

## Status

**Drafting** — 2026-09-20.

## Scope / non-goals

In scope, mapped onto #74's five entry points:

1. **Home page agenda lists** (`HomePage.tsx:63`) — opens the shared sheet/panel in place instead of
   navigating to the full page.
2. **Room Availability's per-room meeting list** (`RoomAvailabilityPage.tsx:250`) — same.
3. **Calendar view** (`PersonCalendarPage.tsx`) — already does this; becomes the reference
   implementation the shared piece is extracted from.
4. **The sheet/panel's own "View full details" button** — removal already decided independently in
   [#73](https://github.com/geoffweatherall/mootmaker-webapp/issues/73); this doc doesn't re-litigate
   it, just notes the overlap so the two pieces of work aren't done in conflicting order.
5. **Direct/bookmarked/shared URL** to `/meetings/:id` — the one case that keeps the full page.
   `MeetingDetailsPage` is retained, not deleted, and is brought to visual/structural parity with the
   shared sheet/panel content (same field set, order, room colour, avatar alignment).

Also in scope: the full page's "Back" link's correctness — gated on genuine in-app origin, not on
browser history depth (see Trade-offs).

Non-goals:

- Extending this pattern to any location that doesn't show meetings today.
- Re-deciding whether to remove "View full details" — #73 already covers that.
- Any change to what data a meeting response carries — this is purely presentational/routing.

## Trade-offs and decisions

- **Split `MeetingDetail` into content and chrome, share only the content.** Pure content — subject,
  room + colour dot, date, time, organiser row, attendee rows, no dismiss/backdrop behaviour —
  becomes a component reusable by both the sheet/panel and the full page. The existing responsive
  wrapper (the `isWide` branch between a MUI `Drawer anchor="bottom"` and the hand-rolled fixed side
  panel — see that code's own comment on why the wide-screen panel deliberately has no backdrop, so
  clicking a different meeting row doesn't need the panel closed first) stays specific to the
  sheet/panel; `MeetingDetailsPage` renders the shared content directly inside its own `Paper` card,
  not the overlay wrapper.
- **Where the shared open/close state lives: a custom hook**, confirmed with Geoff —
  `useMeetingDetailOverlay()` returning `{ open(meeting), overlay: <ReactNode> }`. Each page calls
  `open()` from its own row's `onClick` and renders the returned node once, near the top of its JSX.
  Chosen over a wrapping component (more component-tree structure for no real benefit here) or a
  root-mounted context (furthest-reaching option, and nothing outside these three pages needs it) —
  plain React, no new dependency, keeps the responsive Drawer/panel markup co-located with the state
  that drives it. Owns `openMeeting`/`setOpenMeeting` and the existing `isWide` branching logic
  internally, so `HomePage`, `RoomAvailabilityPage` and `PersonCalendarPage` each mount it once
  rather than duplicating that branch three times.
- **The full page keeps fetching its own data, not a warm cache.** Its existing comment already
  explains why it selects names itself rather than resolving ids against cached rooms/people: "a
  details page reached cold from a shared or bookmarked link has no cached rooms or people to resolve
  ids against." Bringing it to visual parity means it now also needs `REFERENCE_DATA` (rooms +
  people) — room colour in particular needs a room's **position in the full sorted room list**
  (`roomColorAt(index, mode)`), not just the room object `MEETING_BY_ID` already returns embedded on
  the meeting. Fetched independently, the same self-sufficient way, because for the one path this
  page now serves — a cold direct link — there is no caller to pass that context in.
- **Field set and order unified across both surfaces**, closing the "not in a logical order"
  complaint by construction rather than by separately re-ordering the full page's own rows.
  Confirmed order: Subject (heading) → Room (with colour dot) → Date → Time → Organiser →
  Attendees. This adds Date to the shared content — today's sheet/panel omits it, since it's always
  opened from an already-dated context — harmless there, and required standalone on the full page.
- **"Back" gated on an explicit navigation flag, not `history.length`/`navigate(-1)`.** The reported
  failure mode: paste a mootmaker meeting URL into an existing browser tab that already had unrelated
  browsing history, and `navigate(-1)` — or any check based on whether history is merely non-empty —
  takes you to that unrelated page, not back into mootmaker. Once points 1–2 above remove every
  current in-app entry point into `/meetings/:id`, there is no first-party path left that would
  legitimately set such a flag — so in practice "Back" will not render at all after this change. This
  is documented as the mechanism to use if a future internal link into this route is ever added, not
  as something exercised today.

## Choices you had me make

None — the two decisions originally left open here (field order, and the shared-overlay extraction
shape) were put to Geoff directly and are recorded as confirmed in "Trade-offs and decisions" above.

## Open questions

Blocking: none identified — the request's four points resolve every open question #74 itself raised
(which of the five entry points to keep, and whether `MeetingDetailsPage` survives at all).

Non-blocking:

- Whether the "Back" gating flag should ever cover a future case (none exists today) where the app
  wants to deep-link into the full page for some other reason — deferred until such a case exists.

## Impacts on components

- **mootmaker-webapp**:
  - `PersonCalendarPage.tsx` — `MeetingDetail` split into shared content + the existing responsive
    wrapper; `openMeeting` state moves into, or is driven through, the new shared piece.
  - `HomePage.tsx` (`AgendaList`, line 63) — replace `Link to={`/meetings/${id}`}` with opening the
    shared overlay; needs a `peopleById` built from `REFERENCE_DATA` alongside its existing
    `roomsById` (rooms already fetched here — confirm at implementation time whether people are too).
  - `RoomAvailabilityPage.tsx` (line 250) — same replacement; already fetches `REFERENCE_DATA` for
    rooms, needs `peopleById` added the same way `PersonCalendarPage` already does it.
  - `MeetingDetailsPage.tsx` — rewritten to render the shared content component inside its own
    `Paper`/Back-link chrome, additionally fetching `REFERENCE_DATA` so it can compute room colour
    and stay self-sufficient for the cold-link case.
  - **A code comment recording the parity invariant this request explicitly asks for** — placed on
    the shared content component (and cross-referenced from `MeetingDetailsPage`), so a future
    redesign of one surface is a visible prompt to check the other, rather than the silent drift that
    produced this issue in the first place.
- **mootmaker-release**: `smoke/tests/test-stage.spec.ts`'s "a meeting can be created" test currently
  reads back a just-created meeting via Room Availability's list, which today is a `Link` to the full
  page. Once that row opens the sheet instead, this smoke test's assertions need updating to match —
  open the sheet, assert inside it, rather than asserting on a navigated-to page. Same class of
  cross-repo drift as this session's earlier smoke-suite fixes (#46, #50) — worth fixing in the same
  PR that changes the behaviour, not discovered at the next release.

## Changes to the domain data model and data storage models

N/A — no persisted-state changes, purely UI/routing.

## Technical considerations

- Room colour depends on a room's **index** in the full, sorted-by-name room list, not on the room's
  own id — `MeetingDetailsPage` needs the same `roomIndexById` computation `RoomAvailabilityPage`/
  `PersonCalendarPage` already do, not just the single room object embedded on the meeting.
- `MEETING_BY_ID`'s existing selection already carries room name/capacity/organiser/attendee names
  (it was deliberately built not to depend on a warm cache) — adding `REFERENCE_DATA` alongside it is
  purely to get the room's position in the full list for colour, not to re-fetch anything already
  fetched.
- Both `mootmaker-release`'s smoke suite and mootmaker-webapp's own `acceptance/` suite have existing
  locator assumptions tied to today's navigate-to-full-page behaviour (see Impacts on components) —
  update both, following the same role/name-based, exact-matched locator discipline this session's
  earlier fixes (mootmaker-release#46, #50, mootmaker-webapp#71) already established, rather than
  reintroducing a fragile substring match.

## Testing impacts

- New/updated unit and mocked-integration tests in `webapp/` for: the shared overlay opening from
  each of the three surfaces, `MeetingDetailsPage`'s Back-link visibility (present only after a
  genuine in-app-flagged navigation, absent on a cold load), and the unified field set/order.
- `mootmaker-webapp/acceptance/` and `mootmaker-release/smoke/tests/test-stage.spec.ts` both need
  their meeting-detail assertions updated from "navigate to `/meetings/:id`" to "open the sheet/panel
  in place" — see Impacts on components.

## Documentation impacts

- The parity-invariant comment requested above is itself a documentation change, in-code rather than
  in a `docs/` file — see Impacts on components.
- `mootmaker-webapp/README.md`, if it currently describes `/meetings/:id` as a click-reachable page
  rather than a deep-link-only route.

## Rollout & migration

N/A — no persisted state; existing bookmarked/shared `/meetings/:id` links keep working unchanged,
which is the point of retaining the route.

## Risks

- Cross-repo test coupling (mootmaker-release's smoke suite), same shape as this session's earlier
  release failures — flagged explicitly so it's fixed as part of this change's own PR(s), not
  discovered at the next release.
- If the shared overlay extraction is done carelessly, `PersonCalendarPage`'s existing "click another
  meeting while the panel is open, no need to close first" behaviour (named in its own current
  comment) could regress silently. Worth an explicit test for it in the new shared implementation,
  not just inherited by assumption.

## Definition of done

N/A at Drafting — to be filled in once Geoff reviews and moves this to Ready.
