# Home and misc pages redesign

## Summary

Brings the Home page, and every other webapp page except Settings, into the visual language
`PersonCalendarPage`/`RoomAvailabilityPage` already established: Material Design, card-flowing
layout, no marketing-style hero imagery, restrained actions instead of competing CTA buttons.
Follows up on [mootmaker-webapp#111](https://github.com/geoffweatherall/mootmaker-webapp/issues/111)'s
loading-state fix with the deeper visual pass Geoff asked for directly, and revises part of
[`attendee-response-status.md`](attendee-response-status.md)'s Home page design: "Needs your
response" gains an explicit time range and an incremental way to look further ahead, and the
Today/Tomorrow agenda goes from that design's per-list "show more" cards back to one merged
calendar-style list. Also generalizes its empty-state icon treatment into the app's standard empty
state, which is the one place this touches `PersonCalendarPage`/`RoomAvailabilityPage` — their own
empty states (not anything else about those pages) move from the current bespoke SVG illustrations
to the same icon-in-a-tinted-circle pattern.

**UI prototype**: https://claude.ai/artifact/9PWBGRbGKZBU1CTAcZLP54 — 14 artboards: Home page
signed-in/signed-out at both wide (1280, with sidebar) and narrow (390×844, collapsed top app bar)
widths, two of the signed-in ones interactive (try "Search further ahead" — it's a real
incremental fetch simulation, not a static reveal), plus Sign In, Sign Up (both steps), Reset
Password (both steps), About, Add Meeting, and Meeting Details restyled at wide width only.

## Status

**Drafting** — 2026-09-22.

## Scope / non-goals

In scope:

- **Home page** (`HomePage.tsx`) — full visual rework, signed-in and signed-out, wide and narrow.
- **"Needs your response"** — copy that names the time range it's vouching for (both when it has
  items and when it's empty), an explicit empty-state layout, and an incremental **"Search further
  ahead"** control that always stays available and extends the search window by 3 more days per
  click, merging in whatever that turns up.
- **Today/Tomorrow agenda** — merges back into one continuous, calendar-style list (day-sectioned,
  dot + subject + time rows, matching `PersonCalendarPage`'s own day sections) instead of
  `attendee-response-status.md`'s two side-by-side card columns.
- **Sign In, Sign Up (both steps), Reset Password (both steps), About, Add Meeting, Meeting
  Details** — page-chrome-only pass: drop each page's hero SVG, plain page title (no icon beside
  it), form/content in a card matching Home's shadow/radius/spacing, capped to a narrower width
  (~460–560px) rather than stretching to the full content column. Wide viewport (1280) only — see
  the "Mobile scope" decision below. No step indicator/progress UI added to the two two-step flows
  (Sign Up, Reset Password); each screen is restyled in place, the flow itself is unchanged.
- **`EmptyState` generalized to an icon-in-a-tinted-circle pattern**, app-wide — replaces the
  bespoke SVG illustrations currently used by `HomePage`'s own agenda empty state,
  `PersonCalendarPage`'s "No people exist yet.", and `RoomAvailabilityPage`'s "No rooms exist yet.",
  alongside the new Needs-your-response empty state this design already introduces. This is the one
  place `PersonCalendarPage`/`RoomAvailabilityPage` are touched — nothing else about either page
  changes.

Non-goals:

- **Settings page** — explicitly excluded; not touched by this design.
- **Restyling MUI's own input components** (`TextField`/`Autocomplete`/`DatePicker`/`Select`) —
  resolved during prototyping (see "Choices you had me make"): they stay exactly as they render
  today. The prototype's plain bordered-box-with-label-above fields were a flat static
  approximation of those interactive components, not a proposal to reskin them.
- **Sign Up's field set** — stays Name, Email, Password, unchanged. Geoff's explicit note: the real
  implementation keeps those three fields as they are; this design is chrome only, not a form
  redesign.
- **Narrow (390px) mockups for the misc pages** — not built for this doc. They inherit the narrow,
  single-column pattern already proven on the Home page (top app bar replacing the sidebar,
  everything stacked) without separate prototypes, since these are already simple single-column
  forms.
- **`PersonCalendarPage`/`RoomAvailabilityPage`** — already match this visual language and are not
  otherwise touched; their only change is the generalized `EmptyState` icon (see above), not their
  layout, day sections, or anything else.
- **Any GraphQL schema or DynamoDB change** — see Technical considerations for how "Search further
  ahead" is built against the existing API surface.

## Trade-offs and decisions

- **No imagery anywhere.** Every hero SVG (`home-hero.svg`, `home-signed-in.svg`,
  `signin-hero.svg`, `signup-hero.svg`, `forgot-password-hero.svg`, `add-meeting-hero.svg`) is
  dropped, not replaced with a smaller or repositioned image — Geoff's direction was to actually
  remove the imagery, not relocate it. Concept 3 of the original three Home page directions
  explored an "ambient watermark" background treatment instead; Geoff picked Concept 1, which has
  no imagery at all, so that idea isn't carried forward here.
- **Today/Tomorrow: one merged list, not two card columns.** Reverses part of
  `attendee-response-status.md`'s own design (two side-by-side `AgendaList` cards, each with its
  own show-more expander) in favour of a single calendar-style list matching
  `PersonCalendarPage`'s day sections exactly — this was Geoff's stated preference ("Today and
  Tomorrow could look more like the calendar view, which I like better").
- **"Needs your response" names its time range explicitly, in both directions.** The heading now
  always shows the range it covers (e.g. "Tue 22 – Thu 24 Sep"), and the empty-state copy says
  "Nothing waiting on a response between {range}" rather than the previous unqualified "you're all
  caught up" — the bug this design closes: that claim was only ever true within whatever window
  happened to be cached, and said nothing about which window that was.
- **"Search further ahead" always stays available and never collapses.** Each click extends the
  window by exactly 3 more days (matching the existing 3-day `PAGE_LOAD` window size) and appends
  whatever that turns up — including nothing, e.g. a weekend with no meetings. There is no
  "collapse back" control; once a request has been made for a wider window, the UI doesn't offer to
  narrow it again. Confirmed uncapped (see Open questions/decisions below) — it never stops
  offering to search further, by design, for this iteration.
- **Populate via the existing `DAYS` query, one call per additional day, not a new range query.**
  Geoff's direction: reuse the same query `RoomAvailabilityPage` already issues per individual day,
  because `DAYS` reads are day-keyed in the Apollo cache — a "Search further ahead" click and a
  later visit to Room Availability or Person Calendar for one of those same dates then share one
  cache entry instead of two independent fetches. See Technical considerations for the mechanism.
- **Newly-found items are visually distinguished from the originally-loaded ones** (indigo left
  border vs. the existing amber), purely so it's legible that a card appeared because of a widened
  search rather than being part of the initial load. No behavioural difference between the two.
- **Auth/misc pages: chrome only, inputs untouched.** Confirmed with Geoff: the real
  `TextField`/`Autocomplete`/`DatePicker` components on Sign In, Sign Up, Reset Password, and Add
  Meeting keep their current MUI rendering exactly as-is. What changes is everything around
  them — no hero image, plain page title, the surrounding card matching Home's shadow/radius.
- **Add Meeting's "Suggest a room" gradient button is kept unchanged.** It's the app's one
  deliberate non-flat accent (the code's own comment already calls this out as the one "smart"
  feature), and stays that way rather than being flattened to match the plainer chip/icon-button
  treatment used elsewhere — it's a real feature affordance, not a marketing CTA.
- **This ships as one combined issue/PR**, confirmed with Geoff, rather than splitting Home from
  the misc pages or splitting the misc pages from each other — see Risks for how that's kept
  reviewable anyway.
- **Misc-page forms are capped to a narrower width** (~460–560px), not left stretching to the
  content column's full 900px, matching the prototype — confirmed with Geoff rather than left as a
  chrome-only guess, since it's a real layout change beyond "same width, new styling."
- **No step indicator added to the two-step flows.** Sign Up and Reset Password stay a plain screen
  swap (details → verify code; request → reset) with no new "Step 1 of 2" affordance — confirmed
  with Geoff to keep this pass scoped to chrome/imagery, not new UI structure.
- **`EmptyState` generalizes to one icon-in-a-tinted-circle pattern app-wide**, confirmed with
  Geoff over keeping the new check-circle treatment scoped to Needs-your-response alone. The
  colour of the tint carries meaning, not just the icon: green (`secondary`-adjacent success tint)
  is reserved for "you resolved something" (Needs-your-response's "you're caught up"); a neutral
  primary-indigo tint is used for "nothing exists yet" states (Person Calendar's no-people,
  Room Availability's no-rooms, Home's own no-meetings-today) — see "Choices you had me make" for
  the specific icon picked per page, which is a smaller, unilateral call within this resolved
  decision.
- **Meeting Details stays in scope for this combined PR**, confirmed with Geoff over cutting it to
  a follow-up — it's cheap, chrome-only, and rides along with the rest even though the page itself
  is rarely reached.

## Choices you had me make

Made unilaterally while iterating on the prototype; flagged for Geoff to review/override cheaply:

- The exact 3-day increment size for "Search further ahead" — chosen to match the existing
  `PAGE_LOAD` window rather than some other step size.
- The border-color convention (amber = originally loaded, indigo = found via a later search).
- The icon-button toolbar (Add meeting / Rooms today / My calendar) replacing the old three-button
  CTA row on Home, and reused as the page-action pattern generally.
- Fictional prototype content (NZ-native-tree room names Kauri/Rimu/Tōtara, people like "Priya
  Nair", "Jordan Lee") — placeholder data for the mockup only, not a proposal to change demo data.
- The specific icon chosen per generalized empty state: a check-circle for Needs-your-response
  ("caught up"), a person outline for Person Calendar's no-people state, a door/room outline for
  Room Availability's no-rooms state (reusing the same glyph already used for the "Room
  Availability" nav item), and a calendar outline for Home's own no-meetings-today state (matching
  the "Calendar" nav item's glyph). The pattern itself (icon-in-tinted-circle, and green vs.
  primary-indigo tint carrying meaning) was confirmed with Geoff; which literal icon represents
  each specific empty condition was my own call, flagged here for a cheap override if any read
  wrong.

## Open questions

Blocking: none — every call that would have blocked drafting (phasing, input chrome, the search
cap, mobile-mockup scope, form width, step indicators, `EmptyState` generalization, and Meeting
Details' scope) was made directly with Geoff before this doc was written; see the decisions above.

Non-blocking:

- Whether `AddMeetingPage`'s existing `loadingReferenceData` spinner state and other
  unknown/refreshing/settled handling need any adjustment now that the surrounding card changes —
  expected to be untouched, but worth explicit confirmation during implementation given
  mootmaker-webapp#111 was exactly this class of bug.
- Exact icon glyphs for the generalized `EmptyState` pattern (see "Choices you had me make") were
  picked unilaterally and not checked against any existing icon-naming convention beyond reusing
  nav-item glyphs where an obvious match existed — worth a quick visual sanity check during
  implementation, not a design-level blocker.

## Impacts on components

All in `mootmaker-webapp`:

- `webapp/src/pages/HomePage.tsx` — the major change: `AgendaList`'s two-column
  card layout replaced by one merged day-sectioned list; "Needs your response" gains
  time-range-aware copy, an empty-state branch, and the search-further-ahead control/state; the
  three-button CTA row becomes an icon-button toolbar; both hero `<img>`s removed.
- `webapp/src/pages/SignInPage.tsx`, `SignUpPage.tsx`, `ForgotPasswordPage.tsx`,
  `AboutPage.tsx` — drop each page's hero `<img>` and the row layout that positioned it; plain page
  title; existing `Paper`/form content restyled to match (shadow/radius, no structural change to
  the forms themselves).
- `webapp/src/pages/AddMeetingPage.tsx` — drop the hero `<img>`; form fields, `Autocomplete`s,
  pickers, and the "Suggest a room" button are otherwise unchanged.
- `webapp/src/pages/MeetingDetailsPage.tsx` — chrome only; renders the same
  `MeetingDetailContent` it already does.
- `webapp/src/components/EmptyState.tsx` — shape change from an `illustration: string` (image src)
  prop to an icon-based render (icon-in-a-tinted-circle, with a colour/tone input for the
  green-vs-primary distinction in Trade-offs). Every existing caller needs updating to the new
  prop shape, not just the three below.
- `webapp/src/pages/PersonCalendarPage.tsx` — empty-state branch only ("No people exist yet."
  moves to the new icon pattern); day sections, Autocomplete, FAB, everything else untouched.
- `webapp/src/pages/RoomAvailabilityPage.tsx` — empty-state branch only ("No rooms exist yet."
  moves to the new icon pattern); room cards, timeline bars, everything else untouched.
- New: a small hook/utility driving "Search further ahead" — tracks the current window's end
  offset, issues one `DAYS` query per newly-added day (or a batched set), merges newly-found
  unresponded meetings into the existing list. Exact shape (hook vs. inline state, per the
  prototype's own `level`/`searching` state machine) is an implementation-time call, not a design
  decision this doc needs to pin down further.
- Assets to retire once nothing references them: `home-hero.svg`, `home-signed-in.svg`,
  `signin-hero.svg`, `signup-hero.svg`, `forgot-password-hero.svg`, `add-meeting-hero.svg`,
  `empty-meetings.svg`, `empty-people.svg`, `empty-rooms.svg` — check for other referrers before
  deleting each (see Risks).

## Changes to the domain data model and data storage models

N/A — this is pure UI/display and client-side query composition over data the API already serves;
nothing new is persisted.

## Technical considerations

- **"Search further ahead" mechanism**: call the existing `DAYS` query once per additional day
  (or a small batch) rather than widening `PAGE_LOAD`'s own `dates` argument — `PAGE_LOAD` covers
  rooms/people/the fixed 3-day agenda window in one shot and isn't shaped for an open-ended range.
  `DAYS` is already how `RoomAvailabilityPage` reads a single day, and it writes into the same
  day-keyed cache entity, so a search-further-ahead click for, say, 28 September leaves that day
  warm in the cache exactly as if the user had opened Room Availability for that date directly —
  and vice versa.
- **Unbounded by design** (Geoff's explicit call) — nothing currently stops a user clicking "Search
  further ahead" many times in a row, firing many individual day queries. Each is a cheap read, and
  this design deliberately doesn't add a cap or a "give up" state; if repeated clicking ever proves
  to be a real problem, that's a follow-up issue, not something to design around speculatively now
  (per this project's "raise issues for deferred decisions" convention).
- **mootmaker-webapp#111's unknown/refreshing/settled discipline must be preserved, not
  regressed**, through the Home page rework — the merged Today/Tomorrow list and the new
  search-further-ahead state both need their own honest unknown/refreshing/settled handling, not
  just the existing agenda-level one.

## Testing impacts

- `layout-stability.spec.ts` (already the home of #111's regression tests) needs new coverage for:
  the empty "Needs your response" layout, "Search further ahead" actually appending newly-fetched
  meetings rather than revealing hidden DOM (the same non-vacuous-test rigor #111's tests already
  established — prove it by checking the new cards are genuinely absent before the click, not just
  hidden), and the merged Today/Tomorrow list rendering correctly.
- New unit/mocked-integration coverage for whatever hook drives the day-by-day search-forward
  accumulation, including that repeated clicks keep extending rather than resetting.
- The misc pages' changes are chrome-only; existing role/accessible-name-based tests for headings,
  form labels, and button names shouldn't need to change unless a specific test asserted on
  something being removed (e.g. an image's `alt` text, unlikely since these are all `alt=""`
  decorative images already). A full suite run is the actual check, not a prediction here.
- `EmptyState`'s prop-shape change touches Person Calendar's and Room Availability's own existing
  empty-state tests (their "No people/rooms exist yet." coverage) — confirm those still locate the
  message by its text/role, not by anything that assumed an `<img>` was present.

## Documentation impacts

- `mootmaker-webapp/README.md`'s "Home page" section (already updated for #111) needs a further
  pass describing the merged Today/Tomorrow list and the search-further-ahead mechanism in place of
  the current two-column/show-more description.
- Any README material describing the misc pages' current image-led layout (if any exists beyond
  what's already implicit in the code) needs updating to match.

## Rollout & migration

No migration or feature flag needed. Deploys cleanly through the usual `release.yml` pipeline; no
transition state, no data to backfill.

## Risks

- **Combined-PR scope is the main risk** — Geoff's chosen phasing lands Home and every misc page in
  one PR. Mitigated by keeping commits separated per page/section even within that one PR (this
  project's "separate commits per piece of work" convention), so the diff stays reviewable
  piece-by-piece even without separate PRs.
- **Deleting hero SVGs is easy to ship but a small papercut to reverse** if a page still references
  one that looked unused — grep for each asset's actual referrers before removing the file, not
  just deleting because removal was the intent.
- **`EmptyState`'s prop-shape change is a breaking change to a shared component** — every existing
  caller (Home's agenda, Person Calendar, Room Availability, and this design's new
  Needs-your-response empty state) must be updated in the same change, or the build fails outright
  rather than silently regressing. Low risk in practice (TypeScript catches every caller), called
  out because it's the one place this design's blast radius extends past pages explicitly listed in
  Scope.

## Implementation checklist

Sparse while Drafting, per convention — filled in properly once Status moves to Ready.

1. `[Claude]` Build the search-further-ahead hook/query composition, with unit tests.
2. `[Claude]` Rework `HomePage.tsx` to the approved prototype (signed-in + signed-out, wide +
   narrow).
3. `[Claude]` Update `SignInPage`/`SignUpPage`/`ForgotPasswordPage`/`AboutPage`/`AddMeetingPage`/
   `MeetingDetailsPage` chrome.
4. `[Claude]` Remove now-unused hero SVG assets, after confirming no other referrers.
5. `[Claude]` New/updated tests per Testing impacts.
6. `[Claude]` README updates per Documentation impacts.
7. `[Geoff]` Review the PR.
8. `[Claude]` Deploy to a reused ephemeral environment, run acceptance, ship through the normal
   release path.

## Definition of done

New/changed acceptance coverage is green; the existing acceptance suite is still green on a real
deployed environment; the README updates from Documentation impacts are actually made, not just
planned.
