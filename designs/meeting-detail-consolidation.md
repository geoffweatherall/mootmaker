# Meeting detail consolidation

## Summary

Consolidate every place a meeting's details can be viewed into one shared mechanism — a mobile-first
slide-up bottom sheet / desktop slide-out side panel, extracted from `PersonCalendarPage.tsx`'s
existing `MeetingDetail` so the Home page and Room Availability can open it too, instead of
navigating to the separate full-page `/meetings/:id` route. That full page is **retained**, but only
as the landing target for a shared/bookmarked/direct URL — nothing in the app links to it any more —
and its own layout, which has visibly drifted from the sheet/panel, is brought back into parity with
it. Converts [mootmaker-webapp#74](https://github.com/geoffweatherall/mootmaker-webapp/issues/74)'s
inventory into a concrete decision on all five entry points it listed. Also adds a **Share** action,
shown consistently wherever meeting details are visible, that hands out exactly the `/meetings/:id`
URL this doc already commits to keeping alive as a standalone deep link.

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

6. **A "Share" action**, new to this design (not part of #74's original inventory), placed on the
   shared meeting-detail content itself so it appears identically in the sheet/panel and the full
   page. Hands out the meeting's own `/meetings/:id` URL — see Trade-offs for the mechanism.

Non-goals:

- Extending this pattern to any location that doesn't show meetings today.
- Re-deciding whether to remove "View full details" — #73 already covers that.
- Any change to what data a meeting response carries — this is purely presentational/routing.
- Any sharing mechanism other than handing out the URL (no in-app "invite this person to this
  meeting" flow, no email-sending, no generating a shortened/tokenised link) — Share does exactly
  what pasting the address bar's URL would do, just without making the recipient type or copy it by
  hand themselves.

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
- **Share tries `navigator.share()` first, falls back to clipboard.** On click: if the Web Share API
  is available (`typeof navigator.share === 'function'`), call it with `{ title: meeting.subject,
  url: <absolute /meetings/:id URL> }`, which opens the device's native share sheet (Messages, email,
  Slack, etc. — this is the primary, mobile-first path, consistent with this app's existing
  mobile-first framing). Where it isn't available (most desktop browsers), fall back to
  `navigator.clipboard.writeText(url)` plus a brief "Link copied" snackbar/toast confirmation, since
  the clipboard write itself is otherwise invisible to the user. Both are standard, user-gesture-
  triggered browser APIs — nothing is copied or shared without the user directly clicking Share.
- **One icon for both paths, not one per code path.** `ShareIcon` (MUI's own canonical share glyph —
  confirmed with Geoff over `IosShareIcon`'s borrowed-iOS-styling and `LinkIcon`'s "this is a link"
  reading, which is a different action) is used regardless of whether the click ends up calling
  `navigator.share()` or falling back to clipboard — the user doesn't know or care which fired, so
  swapping icons by device/browser would just look inconsistent for no benefit. Icon-only, with
  `aria-label="Share meeting"`, matching this app's existing pattern for icon-only controls (the
  week-navigation `IconButton`s, the sheet/panel's own Close button).
- **"Back" gated on an explicit navigation flag, not `history.length`/`navigate(-1)`.** The reported
  failure mode: paste a mootmaker meeting URL into an existing browser tab that already had unrelated
  browsing history, and `navigate(-1)` — or any check based on whether history is merely non-empty —
  takes you to that unrelated page, not back into mootmaker. Once points 1–2 above remove every
  current in-app entry point into `/meetings/:id`, there is no first-party path left that would
  legitimately set such a flag — so in practice "Back" will not render at all after this change. This
  is documented as the mechanism to use if a future internal link into this route is ever added, not
  as something exercised today.

## Choices you had me make

None — the three decisions originally left open here (field order, the shared-overlay extraction
shape, and the Share icon) were put to Geoff directly and are recorded as confirmed in "Trade-offs
and decisions" above.

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
  - New `ShareMeetingButton`-style component (`ShareIcon`, `aria-label="Share meeting"`) added to the
    shared content component, so it renders identically in the sheet/panel and the full page.
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
- **Both the Web Share API and the Clipboard API require a secure context (HTTPS)** and a direct user
  gesture — a click handler satisfies the gesture requirement; HTTPS is already satisfied everywhere
  this app runs (production, `test`, and every ephemeral environment all serve over HTTPS via
  CloudFront + ACM — confirmed against this session's own ephemeral-environment `site_url` output,
  e.g. `https://www.claude-260920-6o2p.mootmaker.com`), so no environment-specific gating is needed.
- The shared URL must be **absolute**, not the app's internal relative path — `navigator.share()`'s
  `url` field and a clipboard-pasted link both need a full `https://…/meetings/:id`, built from
  `window.location.origin` plus the route, not just the router's relative path string.
- `navigator.share()`'s availability check (`typeof navigator.share === 'function'`) needs to happen
  at click time, not render time cached into state — some browsers only expose it conditionally (e.g.
  only for same-origin-invoked contexts), and checking once at mount could stale-cache a wrong answer.

## Testing impacts

- New/updated unit and mocked-integration tests in `webapp/` for: the shared overlay opening from
  each of the three surfaces, `MeetingDetailsPage`'s Back-link visibility (present only after a
  genuine in-app-flagged navigation, absent on a cold load), and the unified field set/order.
- `mootmaker-webapp/acceptance/` and `mootmaker-release/smoke/tests/test-stage.spec.ts` both need
  their meeting-detail assertions updated from "navigate to `/meetings/:id`" to "open the sheet/panel
  in place" — see Impacts on components.
- **Two new tests, at two different layers, for the specific scenario this design's "Back" fix
  targets — nothing today covers either.** Checked against the existing suites while drafting this
  doc:
  - `webapp/tests/auth.spec.ts` already parametrically covers "visiting `/meetings/some-id` while
    signed out redirects to `/signin`", but its separate "signing in from a protected page returns
    to that page" test exercises `/meetings/add`, not a meeting-details URL — the sign-in-then-return
    leg is never exercised for this route specifically.
  - `acceptance/tests/meeting-details.spec.ts`'s H.72 ("Back returns to whichever page the user
    actually came from") only exercises Back for navigation that *originated in-app* (clicking
    through from Room Availability or the Home page) — every case in that file signs in first, then
    creates/views a meeting. None of them start signed out and follow a cold link.
  - H.73 covers a bad meeting id, a different failure mode entirely.

  **H.72 itself becomes obsolete under this design, not just superseded.** It reaches the full page
  by clicking through Room Availability's and the Home page's meeting rows — but points 1–2 above
  mean neither of those rows navigates to `/meetings/:id` any more. There is no longer any in-app
  path left for H.72 to exercise as written. It needs rewriting (most likely: removed outright, since
  its premise — Back returning correctly from an in-app-originated navigation to the full page — no
  longer has a first-party scenario to test) rather than left in place asserting behaviour that no
  longer occurs.

  1. **Mocked-integration** (`webapp/tests/`, sits next to `auth.spec.ts`'s existing redirect tests):
     proves the client-routing logic itself. Simulate a browser tab with **unrelated history already
     in it** before the meeting URL loads (e.g. `page.goto('https://example.com')`, or any other
     origin/route, before `page.goto('/meetings/:id')`), signed out, so `RequireAuth` redirects to
     `/signin` and, after the mocked sign-in, returns to the meeting per the existing `from`-state
     mechanism — then assert "Back" either does not render, or definitely does not leave the app. No
     real Cognito round-trip is needed to prove this; mocked auth is what the adjacent tests already
     use for the same reason.
  2. **Acceptance** (`acceptance/tests/meeting-details.spec.ts`, a new `H.74`-style case, real
     deployed environment, real Cognito): proves the realistic end-to-end journey — someone receives
     a meeting link, is not signed in, follows it, goes through a **real** sign-in, and lands on the
     correct meeting with its correct details. This is the scenario as a person would actually
     experience it, and mocked auth can't stand in for it — the real value is proving `RequireAuth`,
     Cognito's hosted sign-in, and AppSync are correctly wired together end-to-end for a cold link,
     not just that the client-side redirect state machine is correct in isolation.

     **The link itself comes from the real Share button, not from the test constructing
     `/meetings/${id}` by hand** — this doubles as real coverage of Share's own URL-construction
     code, at no extra cost, rather than assuming it's correct:
     1. `page.addInitScript(() => { Object.defineProperty(window.navigator, 'share', { value:
        undefined, configurable: true }) })`, registered before navigating anywhere in this test —
        **deterministically forces the clipboard-fallback branch**, rather than relying on whatever
        `navigator.share` happens to be in the CI browser. `navigator.share` is a regular own-callable
        on `Navigator.prototype` in Chromium, so shadowing it with an instance-level `undefined` via
        `Object.defineProperty` reliably makes `typeof navigator.share === 'function'` false for the
        page under test, without touching or mocking anything else the app does.
     2. `context.grantPermissions(['clipboard-read', 'clipboard-write'])` on the Playwright browser
        context — a real Chromium capability, no mocking.
     3. Signed in as demo, create/view the meeting, click Share.
     4. Read back what the app actually wrote: `await page.evaluate(() => navigator.clipboard
        .readText())`.
     5. Sign out, `page.goto()` to the captured URL, then continue as below (`/signin` redirect, real
        sign-in, land on the correct meeting).

     **OS/browser caveat, worth a comment on the test itself**: forcing step 1 removes the dependency
     on `navigator.share`'s real availability, but step 2's clipboard permission grant and the
     clipboard read/write themselves are a genuinely different browser/OS-level mechanism, and this
     suite currently only ever runs on Linux (`release-build.yml`'s `runs-on: ubuntu-latest` — checked,
     no OS branching exists anywhere in `acceptance/run.sh` either). If this suite is ever run on a
     different OS (a Windows or macOS runner, or a developer's own machine outside CI), clipboard
     permission handling and headless-clipboard behaviour is exactly the kind of thing that can differ
     by platform even when the rest of the test is OS-agnostic — so a failure specifically in this
     test on a non-Linux run should be suspected first as a clipboard/OS difference, not necessarily a
     real regression. Leave this as an explicit comment next to the test, not just in this doc, so a
     future debugger sees it immediately rather than re-deriving it from a failure.

  Worth noting explicitly: **today's `MeetingDetailsPage.tsx` renders Back unconditionally**
  (`navigate(-1)` with no origin check at all), so the failure mode both tests above are meant to
  catch already exists in production, untested, right now — not just a theoretical risk this design
  introduces a fix for.
- **Share**: the native-share-sheet branch can only be tested mocked, since an OS share sheet is
  outside anything Playwright can drive — `webapp/tests/`, `navigator.share` mocked as present,
  asserts it's called once with the correct absolute URL and the meeting's subject as `title`. The
  clipboard-fallback branch gets **real** coverage instead, for free, as part of the new `H.74`
  acceptance test above (real `navigator.clipboard.writeText`, real Chromium, real environment) —
  no separate mocked test is needed for that branch, since the acceptance test already exercises the
  real code path.

## Documentation impacts

- The parity-invariant comment requested above is itself a documentation change, in-code rather than
  in a `docs/` file — see Impacts on components.
- `mootmaker-webapp/README.md`, if it currently describes `/meetings/:id` as a click-reachable page
  rather than a deep-link-only route.

## Rollout & migration

N/A — no persisted state; existing bookmarked/shared `/meetings/:id` links keep working unchanged,
which is the point of retaining the route.

## Risks

- **The unsafe-Back scenario this design fixes is a live, untested gap today, not a hypothetical.**
  `MeetingDetailsPage.tsx` currently renders "Back" unconditionally via `navigate(-1)`; a signed-out
  user who pastes a meeting link into a tab with unrelated prior history, signs in via the resulting
  redirect, and clicks Back would leave the app entirely — see Testing impacts for what confirming
  this needs. Worth treating as a real (if likely low-severity/low-frequency) bug fix bundled into
  this design, not purely a nice-to-have alongside the consolidation.
- Cross-repo test coupling (mootmaker-release's smoke suite), same shape as this session's earlier
  release failures — flagged explicitly so it's fixed as part of this change's own PR(s), not
  discovered at the next release.
- If the shared overlay extraction is done carelessly, `PersonCalendarPage`'s existing "click another
  meeting while the panel is open, no need to close first" behaviour (named in its own current
  comment) could regress silently. Worth an explicit test for it in the new shared implementation,
  not just inherited by assumption.

## Definition of done

Per this project's own rule, a green acceptance run against a real deployed environment is what
"working" means here — not a passing unit suite, and not a successful deploy. Every item below
should be confirmed against a real environment, not just read out of the diff:

- [ ] Clicking a meeting row on each of the three surfaces — Home's agenda lists, Room Availability,
  Calendar — opens the shared slide-up/slide-out overlay in place, with no navigation and no change
  to the browser URL. Confirmed on all three, not assumed from one.
- [ ] Nothing left in the app's own source navigates to `/meetings/:id` — confirmed by grepping for
  every remaining `to={`/meetings/${...}`}` / `navigate('/meetings/...')` call site and finding none
  outside `MeetingDetailsPage.tsx`'s own Back-adjacent logic.
- [ ] `/meetings/:id` still renders full details correctly when visited directly (signed in) with a
  real meeting's id — the deep-link path this design exists to preserve.
- [ ] The full page's field order, room colour dot, and organiser/attendee avatar alignment visually
  match the sheet/panel for the same meeting — confirmed by direct comparison (side-by-side or
  before/after screenshots), not just "looks about right."
- [ ] The parity-invariant code comment exists on the shared content component and is
  cross-referenced from `MeetingDetailsPage.tsx`.
- [ ] The mocked unrelated-tab-history Back-safety test (`webapp/tests/`) passes.
- [ ] The real acceptance `H.74`-style test passes: URL captured from the real Share button via the
  clipboard, signed out, that exact URL revisited, redirected to `/signin`, signed in for real, lands
  on the correct meeting.
- [ ] H.72 has been rewritten or removed to match the new reality (see Testing impacts) — not left
  in place asserting a navigation path that no longer exists.
- [ ] Share's native-share-sheet branch has been manually verified at least once on a real mobile
  browser (the OS share sheet itself can't be driven by Playwright — see Testing impacts) — mirrors
  how the dot-alignment fix earlier in this project was verified by eye on a real device rather than
  claimed from a passing test suite alone.
- [ ] The regression named in Risks — clicking a different meeting while the panel is already open,
  with no need to close it first — has an explicit test, and that test passes.
- [ ] `mootmaker-release/smoke/tests/test-stage.spec.ts` is updated to match the sheet-based flow,
  and a real release has gone all the way through `test` and `production` with it green — not just
  updated and unexercised.
- [ ] `mootmaker-webapp/acceptance/`'s full meeting-detail coverage (H.68–H.74) is green against a
  real deployed environment.
