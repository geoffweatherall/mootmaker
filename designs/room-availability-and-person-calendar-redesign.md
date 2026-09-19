# Room Availability and Person Calendar: a mobile-first redesign

## Summary

Room Availability and Person Calendar both break down on narrow screens — Room Availability's grid
forces horizontal scrolling and has a real rendering defect (scrolled content bleeding under its
sticky room-name column, mootmaker-webapp#11); Person Calendar's six-week grid crams full text
lines into a fifth of a phone's width, with no tracked issue yet. This design replaces both with
Material-inspired, mobile-first layouts that are equally usable with touch and a mouse, and
introduces two small shared UI ideas along the way — a person-initials avatar, and a floating
action button (FAB) for each page's primary "add a meeting" action. Both ideas are carried through
consistently to the rest of the app's person/room touchpoints: meeting detail, the add-meeting
pickers, Settings' People/Rooms lists, and the account menu.

## Status

**Building** — 2026-09-19. Implementation started on `mootmaker-webapp`'s
`feature/room-availability-and-person-calendar-redesign`, per the Implementation checklist below.

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
  raw viewport edge. Person Calendar's FAB pre-fills the person being viewed as an attendee when it
  opens `AddMeetingPage`.
- Carrying the avatar and structured attendee-list treatment to `MeetingDetailsPage.tsx` (replacing
  its comma-joined attendee string), `AddMeetingPage.tsx`'s organiser/attendee pickers, Settings'
  People list, and `AccountBox.tsx`'s generic person-icon.
- Extending the existing room-color-dot to Settings' Rooms list and `AddMeetingPage.tsx`'s room
  picker, so a room's color is consistent everywhere it appears.

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
- **An attendee-count cap in the detail view.** Considered truncating at 4 with a "+N more" line;
  decided against — the detail surfaces (bottom sheet, side sheet) already scroll internally, so
  showing everyone is simpler and loses nothing, including for the 18-attendee All-Hands case in
  the prototype.

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

**Person Calendar's FAB pre-fills the viewed person as an attendee, not organiser, and not left
blank.** Opening Add Meeting from someone's calendar reads as "schedule a meeting with them," which
matches what the page is already for (viewing that person's schedule) — pre-filling as organiser
would assume you're scheduling on their behalf, which is a less common case, and leaving it blank
would waste the one piece of context the FAB actually has.

**Attendee/avatar carryover, and the room-color-dot fix, are in scope after all.** Originally left as
follow-ons so as not to unilaterally grow the design (see the doc's earlier drafting history in this
PR). On review, folded in: `MeetingDetailsPage.tsx`'s attendees today are one comma-joined string
with a bare `"None"` fallback — worse than the detail view this design already builds for Person
Calendar — and the room-color gap in Settings/`AddMeetingPage.tsx` is a real, visible inconsistency
once the redesigned pages are showing colored dots consistently elsewhere. Both are small,
low-risk, and share the same building blocks (the new avatar component, the existing
`roomColorAt`) already being built for the two redesigned pages, so doing them together costs little
extra and leaves less inconsistency behind.

**No attendee-count cap.** Considered, and dropped — see "Non-goals."

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

- **The avatar's tint color** (a light lavender background with the brand primary as text) — a new
  neutral tonal pairing, not pulled from an existing token. Kept deliberately distinct from both the
  three brand semantic hues and the room categorical palette so it doesn't compete with either.
  Reviewed and kept as-is.

## Open questions

None outstanding. Both blocking questions from the previous draft (the FAB's pre-fill behavior, and
whether to fold the avatar/room-color follow-ons into scope) are resolved above; both non-blocking
ones (the attendee cap, the avatar tint) are resolved too.

## Impacts on components

Single repository: **`mootmaker-webapp`**. No API, data model, or demo-data change (see below).

- `webapp/src/pages/RoomAvailabilityPage.tsx` — replace the grid+tooltip layout with the room-status
  card list, day-relative framing, and FAB.
- `webapp/src/pages/PersonCalendarPage.tsx` — replace the six-week grid with the weekly agenda list,
  tap-to-detail (bottom sheet / side sheet), and FAB.
- `webapp/src/pages/AddMeetingPage.tsx` — accepts the Person Calendar FAB's navigation state and
  pre-fills the viewed person as an attendee; organiser and attendee `Autocomplete`s gain an avatar
  per option (the attendee one already has a custom `renderOption` with a checkbox — the avatar
  slots in there; the organiser one needs its own `renderOption` added, since it uses the default
  today).
- `webapp/src/pages/MeetingDetailsPage.tsx` — organiser and attendees move from `DetailRow` plain
  text (attendees currently a single comma-joined string, falling back to the bare word `"None"`)
  to the same avatar + structured list treatment as the new Person Calendar detail view.
- `webapp/src/pages/SettingsPage.tsx` — People list (`PeopleSection`) gains a leading avatar per row;
  Rooms list (`RoomsSection`) gains the existing colored dot per row, matching Room
  Availability/Person Calendar.
- `webapp/src/components/AccountBox.tsx` — its existing 32px `Avatar` swaps its generic
  `PersonRoundedIcon` for the signed-in user's own initials.
- A new shared avatar component (name TBD, e.g. `PersonAvatar`) computing initials from a person's
  `name`, used everywhere above.
- `webapp/src/theme/` — likely a token or two for the avatar tint and/or naming the 900px breakpoint,
  an implementation-time detail rather than a decision this doc needs to pin down.

Still a single repository (`mootmaker-webapp`) and still no API, data model, or demo-data change —
see below.

## Changes to the domain data model and data storage models

N/A. Avatars use the existing `Person.name`; nothing new is stored server-side.

**Correction found during implementation:** this section originally assumed organiser/attendees
were already served with names attached wherever a `Meeting` appears (`organiser { id name }`,
`attendees { id name }`). That's true of `MeetingByIdQuery` (`MeetingDetails`, used by
`MeetingDetailsPage`), but not of the `Meeting` type nested inside a `Day` (`PAGE_LOAD`/`DAYS`,
what `RoomAvailabilityPage` and `PersonCalendarPage` actually query) — that shape deliberately
carries organiser/attendee **ids only**, resolved against the workspace's already-fetched people
list where a name is needed (see `webapp/src/graphql/types.ts`'s own comment on `Meeting` vs.
`MeetingDetails`). Person Calendar's new meeting-detail panel reads from the `Day`-nested shape, so
it needed the same id-to-name lookup `RoomAvailabilityPage`/`PersonCalendarPage` already use for
rooms (`roomsById`) - added as a `peopleById` map built from the same reference-data query already
in scope. This shipped as a real `tsc -b` build failure caught only once it reached CI (the
session's own `tsc --noEmit` check doesn't follow this repo's project references and silently
checked nothing - see the Implementation checklist), not as a design-time catch.

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

- **Unit** (`webapp/src/**/*.test.ts`): initials computation from a name, including a single-word
  name (Settings' Add Person form takes free text, so this is reachable, not hypothetical)
  degrading gracefully rather than crashing.
- **Integration** (`webapp/tests/`, Playwright + MSW):
  - the FAB is hidden while a meeting's detail is open and reappears on close;
  - at a narrow viewport, tapping a meeting opens the bottom sheet (dark scrim, Close button); at
    ≥900px, the same tap opens the side sheet instead (no scrim, list stays interactive) — two
    viewport-emulated cases of one behavior;
  - clicking a second meeting while the side sheet is already open swaps its content without
    requiring a close first;
  - a meeting with many attendees (the All-Hands case) renders all of them in the detail view and
    scrolls, rather than truncating;
  - opening Add Meeting via Person Calendar's FAB pre-fills the viewed person as an attendee;
  - `MeetingDetailsPage` renders organiser and every attendee with an avatar, replacing the old
    comma-joined string (including the previously-bare `"None"` case, now an empty-state row
    instead);
  - `AddMeetingPage`'s organiser and attendee `Autocomplete` options each show an avatar;
  - Settings' People list shows an avatar per row and Rooms list shows the colored dot per row;
  - `AccountBox`'s avatar shows the signed-in user's initials, not the generic icon.
- **Existing test impact**: any current test locating "Add Meeting" by accessible name needs to
  keep matching post-FAB — see "Technical considerations." Any existing test asserting on
  `MeetingDetailsPage`'s old comma-joined attendee string, or on `AccountBox`'s generic icon, needs
  updating to match the new structure — not just new tests, existing ones will need editing.
- **e2e / acceptance**: this prediction turned out to be wrong once implementation actually reached
  this layer. No *new* use cases needed covering, but the existing acceptance suite - which locates
  real elements in a real deployed environment, not a mock - broke wherever it depended on the old
  grid's DOM: the fixed-hour timeline, tooltips, `<a>`-per-meeting-block, the six-week grid's outlined
  `Paper` cells, and direct click-to-navigate on Person Calendar all changed shape. That affected far
  more than `room-availability.spec.ts`/`person-calendar.spec.ts` themselves - `add-meeting.spec.ts`,
  `cross-cutting.spec.ts`, `cross-client-updates.spec.ts`, `settings-rooms.spec.ts`,
  `settings-people.spec.ts`, `meeting-details.spec.ts`, `sign-up.spec.ts`,
  `settings-date-time-format.spec.ts` and `non-default-format-reruns.spec.ts` all had at least one
  case asserting on a meeting's visibility or click-through on one of these two pages. Every one of
  those needed fixing, verified against a real deployed ephemeral environment rather than guessed
  from source alone - see the Implementation checklist for the full account. Lesson for next time:
  "the integration layer already covers this" isn't the same claim as "the acceptance layer doesn't
  also assert on this same UI," and a redesign this structural should assume the latter needs
  checking too.

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
- Larger surface area than a first read of "redesign two pages" suggests: folding in the avatar and
  room-color follow-ons means this design now also touches `MeetingDetailsPage.tsx`,
  `SettingsPage.tsx`, and `AccountBox.tsx`. Each change is individually small, but four extra files
  is four extra places for a regression, and `MeetingDetailsPage.tsx`'s attendee-rendering change in
  particular has existing test assertions that need updating, not just new ones added — see
  "Testing impacts."
- Nothing here is harder to reverse than a normal deploy — no data model change means a rollback is
  a plain revert-and-redeploy.

## Implementation checklist

All in `mootmaker-webapp`, one `feature/room-availability-and-person-calendar-redesign` branch,
one PR at the end. Progress as of 2026-09-19 (see that branch's own commits for full detail):

1. `[Claude]` ✅ Shared avatar component (`components/PersonAvatar.tsx`,
   `theme/avatarInitials.ts`) plus its unit test.
2. `[Claude]` ✅ `AccountBox.tsx` uses it.
3. `[Claude]` ✅ `SettingsPage.tsx`: avatar per person row, colored dot per room row.
4. `[Claude]` ✅ `RoomAvailabilityPage.tsx` rewritten: room-status cards, day-relative framing, FAB.
5. `[Claude]` ✅ `PersonCalendarPage.tsx` rewritten: weekly agenda (one week shown, not six — see
   "Trade-offs" for why), tap-to-detail (bottom sheet/side panel), FAB with attendee pre-fill.
6. `[Claude]` ✅ `MeetingDetailsPage.tsx`: organiser/attendees now use the avatar + structured list.
7. `[Claude]` ✅ `AddMeetingPage.tsx`: avatar per picker option; accepts the FAB's pre-fill.
8. `[Claude]` ✅ Done, including the acceptance layer. New unit tests (initials, room status,
   day-relative label). The full mocked-integration suite (`webapp/tests/`, no AWS needed) runs
   clean, including two real bugs this work caught and fixed: the avatar's initials text was
   leaking into option accessible names (`aria-hidden` fixed it), and `meeting-details.spec.ts`
   navigated through Person Calendar in a way that no longer holds. New integration coverage added
   for FAB visibility and the bottom-sheet/side-panel surface swap.

   A real, AWS-deployed ephemeral environment (`claude-260919-hbrf`) was then used to rewrite the
   acceptance suite against reality rather than guesswork - which turned out to need far more than
   the cases flagged above: the redesign's DOM changes broke every case anywhere in the suite that
   asserted on a meeting's visibility or click-through on either page, not just
   `room-availability.spec.ts`/`person-calendar.spec.ts` themselves. Nine other files needed at
   least one fix (`add-meeting`, `cross-cutting`, `cross-client-updates`, `settings-rooms`,
   `settings-people`, `meeting-details`, `sign-up`, `settings-date-time-format`,
   `non-default-format-reruns`). A real, previously-unfixed `tsc -b` build failure was also caught
   and fixed along the way (`PersonCalendarPage.tsx` assumed organiser/attendee names were already
   present on the `Day`-nested `Meeting` shape; they aren't - see "Changes to the domain data model"
   above) - this session's own `tsc --noEmit` check had been silently checking nothing the whole
   time, which is how it got past local verification undetected. Every touched acceptance file has
   since been re-run individually against the same reused environment and passes. See that
   environment's own commits for the full account.
9. `[Claude]` ✅ Done — `docs/reference/use-cases.md` and `docs/reference/business-functionality.md`
   updated to describe the card/agenda design (including closing G.62's previously-documented
   "no week navigation" gap).
10. `[Geoff]` Review the PR diff; merge when satisfied.
11. `[Geoff]` Run `gh workflow run release.yml` in `mootmaker-release` to reach `production` — see
    "Definition of done."
12. `[Claude]` Once production is confirmed, move Status to Shipped and move this doc to
    `designs/archive/`.

## Definition of done

- This design's new/changed test coverage (see "Testing impacts") is green.
- The existing `mootmaker-webapp` test suite (all four layers) is still green.
- A clean acceptance run against a real deployed environment.
- Everything listed under "Documentation impacts" is actually done.
- **A real production release** — `gh workflow run release.yml` in `mootmaker-release`, reaching
  `production` with its smoke test passing — not just a merge to `main`. `main` being green is
  necessary but not sufficient: per `docs/process/environments.md`, a merge changes nothing in
  `test`/`production` by itself, and this is a live public demo, so "Shipped" means an actual
  visitor can see it, not that the code exists on `main`.
- This PR is merged and the doc's Status is moved to Shipped, then the doc moves to
  `designs/archive/`.
