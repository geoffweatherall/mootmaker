# Meeting form pickers — sort + filter — to-do

Status: **not started, not scheduled** — captured per Geoff's request on 2026-08-28, explicitly not
to be worked on now. No dependency on the delete-my-account or Google sign-in work.

## What's there today

[AddMeetingPage.tsx](../mootmaker-webapp/webapp/src/pages/AddMeetingPage.tsx) has three pickers, all
plain MUI `Select`/`MenuItem` (not `Autocomplete`):
- Organiser (single-select, ~line 284)
- Attendees (multi-select with checkboxes, ~line 300)
- Room (single-select, ~line 346)

Organiser/attendee options already run through
[addMeetingLogic.ts](../mootmaker-webapp/webapp/src/pages/addMeetingLogic.ts)'s
`filterOrganiserOptions`/`filterAttendeeOptions` — but that's mutual-exclusivity filtering only (the
same person can't be picked as both), not sorting or text search. None of the three lists are sorted
today; they render in whatever order the API returns (`Query.people`/`Query.rooms`, both a plain
DynamoDB Scan — see `ListPeopleHandler`/`ListRoomsHandler` — so effectively arbitrary order). Note
`SettingsPage.tsx` already works around this same gap for its own people/rooms lists by sorting
client-side (`[...(data?.people ?? [])].sort((a, b) => a.name.localeCompare(b.name))`) — the same
approach would fix ordering here.

## The ask

- Sort all three dropdowns (organiser, attendee, room) — alphabetically by name seems the obvious
  default, matching `SettingsPage.tsx`'s existing pattern.
- Add a filter/search box at the top of each dropdown's open list.

## Worth knowing before picking this up

- Plain MUI `Select` has no built-in search-while-open behaviour — getting a filter box "at the top"
  properly likely means switching to MUI `Autocomplete` instead (single-select for organiser/room,
  `multiple` with checkboxes for attendees, which `Autocomplete` also supports). That's a bigger
  change than it sounds: it touches the value/onChange shape for all three fields, not just an
  additive tweak to the existing `Select`s.
- Explicitly check the room dropdown gets the same treatment, not just organiser/attendee - Geoff
  called this out separately, easy to forget since it's visually the least prominent of the three.
- Explicitly verify narrow mobile widths once changed - `Autocomplete`'s open dropdown and (for
  attendees) selected-chips rendering are the parts most likely to misbehave on a small screen; this
  needs actual manual checking in a narrow viewport, not just an assumption that MUI handles it for
  free.
