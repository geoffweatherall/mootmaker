# Room Availability and Person Calendar: a mobile-first redesign

## Summary

Room Availability and Person Calendar both break down on narrow screens — Room Availability's grid
forces horizontal scrolling and has a real rendering defect (scrolled content bleeding under its
sticky room-name column, mootmaker-webapp#11); Person Calendar's six-week grid crams full text
lines into a fifth of a phone's width, with no tracked issue yet. This design replaces both with
Material-inspired, mobile-first layouts that are equally usable with touch and a mouse, and
introduces two small shared UI ideas along the way — a person-initials avatar, and a floating
action button (FAB) for each page's primary "add a meeting" action — used consistently across both.

## Status

**Drafting** — 2026-09-19.

## Scope / non-goals

**In scope:**

- Room Availability's mobile layout: replace the fixed-column timeline grid with a scrollable list
  of Material "room status" cards (free/busy status, capacity, an expandable list of the day's
  meetings), closing mootmaker-webapp#11.
- Person Calendar's mobile layout: replace the six-week grid with a single scrollable weekly agenda
  (day sections, each listing that day's meetings), with tap/click-to-detail.
- Meeting detail on tap: a bottom sheet on narrow viewports, a right-docked side sheet at wider
  ones, showing subject, time, room, organiser, and attendees.
- A shared initials-avatar for a person (e.g. "Priya Chaudhary" → a colored circle showing "PC"),
  used in the new detail views.
- A FAB for "Add Meeting" on both redesigned pages, anchored to the content column rather than the
  raw viewport edge.

**Non-goals, decided explicitly:**

- **Uploadable avatars.** Initials only, for both people, for now. Uploadable photos are a known
  upcoming feature; this design deliberately does not build toward it beyond not doing anything that
  would make it harder later (see "Choices you had me make").
- **Renaming Person Calendar.** Considered calling it "Agenda" to match the new visual pattern;
  decided against — "Agenda" collides with this app's existing "meeting agenda" vocabulary and risks
  a first-time user reading it as "the topics for one meeting" rather than "my schedule." Every
  mainstream calendar app keeps the product/page named "Calendar" and uses "Agenda"/"Schedule" only
  as an internal *view* name — which doesn't apply here, since there is only one view. The page
  keeps its current title, route, and nav label unchanged.
- **Room avatars.** Rooms keep their existing small colored dot (`theme/roomColor.ts`), not an
  initials-avatar. See "Trade-offs and decisions."
- **Converting Settings' "Add room"/"Add person" or HomePage's "Add Meeting" buttons to FABs.**
  Decided against for both. See "Trade-offs and decisions."
- **A grid/month view alternative for Person Calendar.** Not being reintroduced in any form.
- Carrying the avatar and structured attendee-list treatment to `MeetingDetailsPage.tsx`,
  `AddMeetingPage.tsx`'s pickers, Settings' People list, or `AccountBox.tsx`'s icon. All four are
  genuinely good follow-ons (see "Choices you had me make") but are not bundled into this design's
  build scope.
- Extending the room-color-dot to Settings' Rooms list or `AddMeetingPage.tsx`'s room picker (both
  currently show rooms as plain text with no color at all — a real, pre-existing inconsistency,
  just not one this design bundles in).

## Trade-offs and decisions

**Room Availability: room-status cards, not a per-room agenda or a refined grid.** Three directions
were prototyped: a vertical per-room agenda (switch rooms via chips, see one room's day as a
timeline), a refined version of the existing grid (compact avatar rail, bottom-sheet detail), and
the chosen direction — a card per room with a glanceable "Free now" / "Busy until…" status pill,
capacity, and an expandable list of that day's meetings. Chosen because it needs no per-room
selection step to answer "what's free right now," matches the room-status-dashboard pattern used by
Robin, Teem, and Google Workspace's own room-booking UI, and reads well to a first-time user without
any grid literacy.

**Day-relative framing on the cards.** "Today" and "Tomorrow" for the two near days, then the plain
weekday name beyond that (Google Calendar / Fantastical convention) — avoids clunky phrasing like
"in 4 days." A future day has no "now," so its status pill shows a simple summary ("Free all day" /
"3 meetings, first at 09:00") instead of the live "Free now" / "Busy until…" pill a today-view
shows.

**Person Calendar: a weekly agenda, not a week-strip-with-detail or a horizontally-scrolling week
grid.** Same three-direction exploration, same governing reasoning as Room Availability above — a
plain scrollable list of day sections needs no day-selection step and keeps both redesigned pages
philosophically consistent with each other.

**Meeting detail: bottom sheet (narrow) → right-docked non-modal side sheet (≥900px), not an
anchored popover.** A popover-per-row alternative was prototyped too. The side sheet won because it
has room to grow (this design already needs organiser + attendees, more than a popover comfortably
holds) and doesn't fight for space with a dark modal scrim on a screen that's plenty wide enough not
to need one; the popover also had a real, unsolved edge-of-screen clipping risk for a meeting near
the bottom or side of the list.

**Breakpoint: a plain CSS width media query at 900px, not a pointer/hover-capability query.** Matches
this codebase's own existing convention (e.g. `RoomAvailabilityPage.tsx`'s `sx={{ display: { xs:
'none', sm: 'inline-flex' } }}` pattern) rather than introducing a second responsive mechanism.
`@media (pointer: coarse)` would more precisely catch a touchscreen laptop on a wide monitor, but
that's a real edge case worth solving only if it's ever an actual complaint.

**The FAB hides while a meeting's detail is open, on both mobile and desktop, rather than shifting
position.** On many desktop widths, a fixed-position FAB anchored to the content column's right edge
sits exactly where the 340px side sheet's left edge begins. Hiding the FAB while detail is open
avoids that collision outright, and reads reasonably as "attention is on this meeting right now."

**The FAB must anchor to the content column, not the raw viewport edge.** A first attempt used a
plain `position: fixed; right: 20px`, which drifts away from a centered content column on wide
screens. The fix is a fixed-position overlay layer whose own `max-width` matches the content
column's, so both stay aligned at every width. This bit the design once already (caught while
reviewing the prototype) and is recorded here so an implementer doesn't repeat it.

**No room-equivalent for the new person avatar.** Two reasons, not one. First, rooms already have a
working, deliberately validated identity system — the 8-color categorical palette in
`theme/roomColor.ts`, checked for contrast and colorblind-safety — that's consistent across Room
Availability and Person Calendar today; there's no problem it needs solving. Second, and more
important: keeping "round avatar = person" and "small colored dot = room" as a deliberate shape
distinction is useful on its own, independent of the first reason — it lets a glance tell the two
apart. Making rooms round too would blur that for no gain.

**FAB adoption stops at these two pages.** Settings' "Add room" / "Add person" already open in-place
dialogs, not a page navigation — a different, already-fine pattern that never had the
narrow-screen duplicated-button problem the FAB was invented to solve (mootmaker-webapp#65).
HomePage's two "Add Meeting" buttons sit alongside 2-3 other equally-weighted actions (Calendar, Room
availability today); a FAB visually claims to be *the* primary action on a screen, which would
misrepresent a hub page with several equal entry points. Both are left as regular buttons.

**Prototypes use real data, not placeholders** — the app's actual room names, capacities, and
categorical palette (`theme/roomColor.ts`, `theme/tokens.ts`), and the demo-data generator's own
curated name/subject vocabulary (`mootmaker-demo-data`'s `SampleData.java`) — so review happens
against something that reads as this app, not a generic mockup.

Interactive prototypes (private, Geoff's Claude account):
- Room Availability — <https://claude.ai/artifact/1Z3gT9MmFGRzRq5jpvS4Xr>
- Person Calendar — <https://claude.ai/artifact/DB1xu9GWzDbrgCp3xLwtxo>

## Choices you had me make

- **Attendee-list truncation at 4 visible, then "+N more."** An arbitrary threshold — not discussed
  as a specific number, just picked to keep the sheet/side-sheet from growing unbounded for a
  large meeting (the prototype's All-Hands example has 18 attendees).
- **The avatar's tint color** (a light lavender background with the brand primary as text) — a new
  neutral tonal pairing, not pulled from an existing token. Kept deliberately distinct from both the
  three brand semantic hues and the room categorical palette so it doesn't compete with either.
- **Not bundling the avatar/attendee-list carryover** to `MeetingDetailsPage.tsx` (which today
  renders attendees as one comma-joined string with a bare "None" fallback — arguably a pre-existing
  gap independent of this redesign), `AddMeetingPage.tsx`'s organiser/attendee pickers, Settings'
  People list, or `AccountBox.tsx`'s generic person-icon avatar. All four are genuine, low-risk wins
  once a shared avatar component exists, but I left them out of this design's build scope rather than
  deciding unilaterally to grow it — see "Open questions."
- **Not bundling the room-color-dot fix** for Settings' Rooms list and `AddMeetingPage.tsx`'s room
  picker (both show rooms with no color today, inconsistent with Room Availability/Person Calendar),
  for the same reason.
- **Person Calendar's new FAB does not yet pre-fill anything.** I built its visual presence and its
  hide-while-detail-open behavior, but not what happens when it's tapped — that's a real product
  decision (see "Open questions"), not just a visual one, and this is a genuinely new affordance for
  this page, not a replacement of an existing control.

## Open questions

**Blocking:**

1. Should Person Calendar's new "Add Meeting" FAB pre-fill the person being viewed as an attendee
   when it opens `AddMeetingPage`? It's a net-new feature on this page (Person Calendar has never
   had an "add a meeting" affordance before this design), so this needs a real answer, not an
   assumption.
2. Should the four follow-ons named in "Choices you had me make" (room-color-dot consistency in
   Settings/AddMeetingPage; avatar carryover to MeetingDetailsPage, AddMeetingPage's pickers,
   Settings' People list, and AccountBox) be folded into this design's build scope now, or tracked
   as separate design(s)/issue(s)?

**Non-blocking:**

3. The attendee-overflow threshold (currently 4) and the avatar's exact tint color/token name are
   both fine to settle during implementation or review.

## Impacts on components

Single repository: **`mootmaker-webapp`**. No API, data model, or demo-data change (see below).

- `webapp/src/pages/RoomAvailabilityPage.tsx` — replace the grid+tooltip layout with the room-status
  card list, day-relative framing, and FAB.
- `webapp/src/pages/PersonCalendarPage.tsx` — replace the six-week grid with the weekly agenda list,
  tap-to-detail (bottom sheet / side sheet), and FAB.
- `webapp/src/pages/AddMeetingPage.tsx` — needs to accept the Person Calendar FAB's navigation state
  once Open question 1 is answered; no visual change otherwise in this design's scope.
- A new shared avatar component (name TBD, e.g. `PersonAvatar`) computing initials from a person's
  `name`, used by both redesigned pages' detail views.
- `webapp/src/theme/` — likely a token or two for the avatar tint and/or naming the 900px breakpoint,
  an implementation-time detail rather than a decision this doc needs to pin down.

Explicitly **not** touched by this design (see "Non-goals"): `MeetingDetailsPage.tsx`,
`SettingsPage.tsx`, `AccountBox.tsx`, `mootmaker-api`, `mootmaker-demo-data`.

## Changes to the domain data model and data storage models

N/A. Avatars use the existing `Person.name`; nothing new is stored server-side. Organiser/attendees
are already served by `LIST_MEETINGS` (`organiser { id name }`, `attendees { id name }`) — this
design only changes how that existing data is rendered.

## Technical considerations

- **The FAB's accessible name must exactly match whatever accessible name the current "Add Meeting"
  button carries** (case-sensitive) — this project locates elements by role and accessible name in
  its tests, and a mismatch (even just capitalization) silently breaks every existing test that
  locates it. If the wording is deliberately changed instead of preserved, that's a coordinated
  test-suite update in the *same* PR, not a follow-up.
- **The FAB must anchor to the content column via a max-width-matched fixed overlay, never a bare
  `right: 20px` against the viewport** — see "Trade-offs and decisions."
- The old grid's sticky-column background-bleed defect (reported against #11) is fixed by
  construction in the new card layout, which has no sticky column at all — not patched separately in
  the old grid.
- Nothing new accumulates. This is display logic over data that already exists and is already
  bounded elsewhere (meetings, people, rooms) — no new logs, objects, or queued state to bound.

## Testing impacts

Per `mootmaker-webapp/testing-strategy.md`'s four layers:

- **Unit** (`webapp/src/**/*.test.ts`): attendee-list truncation (>4 attendees shows exactly 4 plus a
  correct overflow count; ≤4 shows all with none); initials computation from a name, including a
  single-word name (Settings' Add Person form takes free text, so this is reachable, not
  hypothetical) degrading gracefully rather than crashing.
- **Integration** (`webapp/tests/`, Playwright + MSW): the FAB is hidden while a meeting's detail is
  open and reappears on close; at a narrow viewport, tapping a meeting opens the bottom sheet (dark
  scrim, Close button); at ≥900px, the same tap opens the side sheet instead (no scrim, list stays
  interactive) — two viewport-emulated cases of one behavior; clicking a second meeting while the
  side sheet is already open swaps its content without requiring a close first.
- **Existing test impact**: any current test locating "Add Meeting" by accessible name needs to
  keep matching post-FAB — see "Technical considerations."
- **e2e / acceptance**: no new coverage needed. Nothing here is an infrastructure-wiring or new-use-
  case question the integration layer doesn't already answer more cheaply.

## Documentation impacts

- `mootmaker-webapp` README/testing-strategy.md, if the new shared component or test files change
  its described structure meaningfully.
- `docs/reference/use-cases.md` and `docs/reference/business-functionality.md` (this repo) likely
  need their Room Availability / Person Calendar descriptions refreshed once shipped.
- This design doc itself moves to `designs/archive/` once Shipped, per the lifecycle.

## Rollout & migration

No data migration, no feature flag. Pure UI replacement with no transition state — deploys cleanly
through the normal release pipeline (ephemeral → `test` → `production`).

## Risks

- The FAB accessible-name mismatch (see "Technical considerations") is the single most likely thing
  to silently break existing coverage if missed.
- Scope creep: several genuine, low-risk follow-ons surfaced while designing this (room-dot
  consistency, avatar carryover) — the risk is one of them getting folded in mid-implementation
  without first being added to this doc's "Scope" deliberately (Open question 2 exists precisely to
  settle this before Building starts).
- Nothing here is harder to reverse than a normal deploy — no data model change means a rollback is
  a plain revert-and-redeploy.

## Implementation checklist

Not filled in yet — per the design-doc lifecycle, this stays sparse while Drafting. Blocking open
questions 1 and 2 need answers before Status can move to Ready, at which point this gets a real,
ordered, `[Geoff]`/`[Claude]`-tagged checklist.

## Definition of done

- This design's new/changed test coverage (see "Testing impacts") is green.
- The existing `mootmaker-webapp` test suite (all four layers) is still green.
- A clean acceptance run against a real deployed environment.
- Everything listed under "Documentation impacts" is actually done.
- This PR is merged and the doc's Status is moved to Shipped, then the doc moves to
  `designs/archive/`.
