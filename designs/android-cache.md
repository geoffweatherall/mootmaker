# Android: a client-side cache of seen days, kept honest by the live channel

## Summary

The Android app fetches every screen from the network on every visit and on every return to the
foreground, so going back into a meeting shows the full spinner, and closing a share sheet flashes
the progress bar. This design adds one in-memory store of the data the app has already seen —
days, reference data and meetings — that every read screen draws from, and that the existing
`daysInvalidated` channel keeps honest exactly as the webapp's Apollo cache is kept honest. It
fixes [mootmaker-android#22](https://github.com/geoffweatherall/mootmaker-android/issues/22) and,
with it, [#23](https://github.com/geoffweatherall/mootmaker-android/issues/23),
[#24](https://github.com/geoffweatherall/mootmaker-android/issues/24) and
[#25](https://github.com/geoffweatherall/mootmaker-android/issues/25).

## Status

**Building** — 2026-10-08. Drafted by Claude after a discussion with Geoff, who asked for the work
to start straight after the draft. Not yet moved to Ready by Geoff; the "Choices you had me make"
below are the ones to review.

## Scope / non-goals

**In scope:** the four screens that read meetings — Home, Person Calendar, Room Availability and
Meeting Details — and the reference data they share (who you are, people, rooms, the bookable
window). How they load, when they refetch, what the live channel does to them, and what this
device's own writes do to them.

**Not in scope:**

- **Persisting the cache to disk.** Memory only. When Android kills the process, the next open is
  a cold start with one spinner, as today. Disk persistence is a possible follow-up; it would need
  wiping on sign-out, account deletion and environment switch, and a migration story for the
  stored shape.
- **Settings, Admin (rooms and people) and the meeting form.** They keep fetching for themselves.
  Their *writes* do invalidate the store (Decision 9), because they change data the store holds.
- **Apollo Kotlin's normalized cache** (Decision 1).
- **The API.** No schema or resolver changes. The broadcast stays `{ dates }`; the planned origin
  ids and reference-data flags
  ([live-update-origin-and-reference-data.md](live-update-origin-and-reference-data.md)) slot in
  later without reshaping this (see Technical considerations).
- **Optimistic responses (#26)** are made easier by this but are their own change.

## Trade-offs and decisions

1. **An app-specific store of plain Kotlin data, not Apollo Kotlin's normalized cache.** Most of
   the webapp's cache code exists to work around its general-purpose cache, and was found bug by
   bug: a read policy rebuilding `days` from arguments (mootmaker-webapp#66), merge warnings (#67),
   an evicted day reading back *complete, minus that day* so nothing refilled it (#136), refetches
   overwriting other queries' data (#164), and cancelled meetings surviving `gc()` while watched.
   Apollo Kotlin's cache has its own version of each question, and its classic form cannot answer a
   five-day query with four cached days at all (a missing field is a whole-query miss); the newer
   one that can is still incubating. A store that holds exactly what these screens need, in the
   shape the existing pure functions (`buildAgenda`, `buildWeek`, `buildRoomCards`,
   `buildMeetingDetail`) already take, has no hidden behaviour to discover, and is testable
   exhaustively without a network or a UI.
2. **The webapp's invalidation rules are ported; its Apollo workarounds are not.** Ported, because
   they are about AppSync and the API, not about Apollo:
   - the broadcast carries dates, never data: a named date is marked stale, never patched;
   - a date that is being watched is refetched; one that isn't stays stale until it is watched again;
   - after a gap in the connection (`LiveEvent.Subscribed`) everything held is suspect, reference
     data included, because rooms and people are never broadcast;
   - a response that was in flight when its date was invalidated cannot be trusted and is fetched
     again (the webapp's `reconcileAfterFetch`).
3. **Stale data stays on screen while it is refreshed.** Each date is one of *unknown*, *loaded* or
   *loaded and stale*. A screen shows the full spinner only when something it needs is *unknown*,
   the slim bar while anything it shows is being refreshed, and "no meetings" only for a date that
   is *loaded* and empty. That is use case M.92's rule, and it is what tells "not loaded yet" from
   "really no meetings" (#25).
4. **No own-write grace window.** The webapp ignores broadcasts for its own writes for 5 seconds
   because its eviction blanks the day until the refetch lands, so the person who just booked would
   watch their own day flicker. Here an invalidated day keeps showing its last content under the
   bar, so the device's own broadcast can simply be obeyed: it costs one extra fetch, invisibly,
   and removes a timing rule that also swallows other people's changes for 5 seconds.
5. **Generation counters, not timestamps, for the in-flight race.** Each key carries a generation
   that every invalidation bumps. A fetch records the generations it was issued under; when it
   lands, data for a key whose generation has moved on is stored (it is still newer than what was
   held) but stays stale, and is refetched if watched. Deterministic, and testable without a clock.
6. **Refresh on reconnect, not on every resume.** The live socket is collected while the activity
   is STARTED (`MootmakerApp.kt`), so the lock screen and the app switcher drop it and the return
   reconnects, which emits `Subscribed`, which refreshes everything: the same as the webapp's tab
   return. A share sheet, permission dialog or picker only pauses the activity (the system
   chooser is translucent, so the app stays STARTED beneath it), keeps the socket, and now
   refreshes nothing (#23). That the chooser only pauses is an assumption no automated layer here
   can prove; Geoff's phone check (checklist step 7) is what confirms it. As a safety net for reference data and for a socket that looks
   up but is silent, a resume also refreshes what is on screen if it was last fetched more than
   **5 minutes** ago.
7. **Meeting Details reads the meeting from its day.** The day query selects everything the
   details screen shows (attendee statuses, `version`, and room, organiser and attendee ids, with
   names and avatars from the shared people and rooms), so a meeting opened from Home, Calendar or
   Availability renders at once. `meeting(id)` is still used when the meeting is not in any loaded
   day (a shared link, or a day aged out of what is held), and when a refetched day no longer holds
   it, to tell *moved* from *cancelled* (use cases H.73, O.121, O.123).
8. **One app-wide store, cleared on every identity change.** It lives in `AppContainer`, beside the
   live channel, and is emptied on sign-out, account deletion and environment switch. Any response
   still in flight from before the clear is dropped (an epoch counter, the same idea as Decision 5),
   so one account's data can never land in the next account's store.
9. **This device's own writes invalidate what they touch.** Respond, cancel, create and update
   invalidate the dates involved (both dates for a meeting moved to another day); admin room and
   person changes, and changes to your own name, preferences and avatar, invalidate the reference
   data. The broadcast would do most of this anyway; doing it directly means the device's own
   change never depends on the socket.
10. **Bounded.** Days more than 60 days from today that no screen is watching are dropped, so at
    most 121 unwatched days are ever held; watched days are bounded by what the screens show.
    Meetings looked up by id are held for at most 50 ids, least recently used first.

## Choices you had me make

- **Building started while this is Drafting.** You asked for work to start immediately after the
  draft; the status says Building, not Ready, so the doc doesn't claim a review it hasn't had.
- **5 minutes** as the resume safety net (Decision 6), and the bounds in Decision 10.
- **Selecting more on the day query** (Decision 7): attendee statuses and `version` for every
  meeting, and people with avatars in the reference data. The schema notes that selection is what
  the server charges for; the extra fields are a few bytes per meeting and remove a request per
  meeting opened.
- **New use cases 144 to 149** (Documentation impacts), tagged [All frontends] because the webapp
  already behaves this way, with the webapp's slot marked "not yet a webapp test case" rather than
  inventing webapp work in this design.

## Open questions

**Blocking:** none.

**Non-blocking:**

- Whether Admin's room and people lists should read from the store too. They are only ever open
  for an admin who is editing them, and refetching them is cheap.
- When the origin ids land, whether the device should skip refetching after its own broadcast
  (Decision 4 makes it harmless either way).

## Impacts on components

All in `mootmaker-android`:

- **New `data/.../cache/`:**
  - `WorkspaceStore`: the entries, the watch counts, the generation and epoch counters, fetch
    coalescing and batching, invalidation, bounds and clear. Pure Kotlin over coroutines; no Android
    or Apollo types.
  - `WorkspaceApi`: the three fetches the store makes (`reference()`, `days(dates)`,
    `meeting(id)`), with an Apollo implementation and a fake for tests.
  - Snapshot types the screens read: per-date `Unknown`/`Loaded(day, refreshing)`, the reference
    data, and errors.
- **New queries** in `data/src/main/graphql/`: `Reference` (me, people with avatars, rooms with
  capacity and colour, boundaries), `Days($dates)` (every field any of the four screens shows) and
  `MeetingById($id)`. `Home`, `PersonCalendar`, `Availability` and `MeetingDetails` queries go.
- **Repositories** `HomeRepository`, `CalendarRepository`, `AvailabilityRepository` and
  `MeetingRepository`'s load path become thin builders over store snapshots, returning a `Flow`
  rather than one `suspend` result. Their writes stay, and invalidate the store afterwards.
- **ViewModels** of the four screens collect the store's flow instead of calling `refresh()`. They
  keep their error and action state. A date, week or person change switches what they watch; the
  old data never shows under the new header (#24, #25).
- **`MootmakerApp.kt`:** the four `LifecycleResumeEffect { refresh() }` calls become the 5-minute
  safety net; the per-screen `liveEvents.collect { refresh() }` calls go, because the store, not
  the screen, now listens to the channel.
- **`AppContainer`:** owns the store, feeds it the live events, and clears it on identity changes.
- **Settings, Admin and meeting-form writes** call the store's invalidation after a successful
  write.

## Changes to the domain data model and data storage models

N/A. Nothing persisted changes; the store is in memory and holds data the API already returns.

## Technical considerations

- **Times stay naive.** The store keys days by `LocalDate` and keeps meeting times as the API's
  naive local date-time strings; nothing is converted through `Instant`.
- **At most 42 dates per request** (the API's limit on `workspace(dates)`). The store batches the
  missing and stale dates of a watch into requests of at most 42.
- **Coalescing.** A key already being fetched is not requested again; if it is invalidated while in
  flight, it is refetched once the current fetch lands (Decision 5).
- **Errors.** A failed fetch leaves any data held on screen with the error beside it, as today's
  reload does; with no data held, the screen shows the error and Try again. `SessionExpired` goes
  through the existing sign-out path, which clears the store.
- **A meeting that leaves its day.** When a refetched day no longer holds a meeting a details
  screen is showing, the store fetches `meeting(id)`: null is the cancelled state (O.123), a
  different date means it moved (O.121), and the details screen follows it there.
- **Ready for the planned broadcast fields.** When `Invalidation` gains `rooms`/`people` flags,
  they map onto the store's existing `invalidateReference()`; origin ids only decide whether to
  skip a refetch. Neither changes the store's shape.
- **What this leaves behind:** nothing on disk. Memory is bounded by Decision 10 and released when
  the process ends.

## Testing impacts

By layer, as [testing-strategy.md](https://github.com/geoffweatherall/mootmaker-android/blob/main/testing-strategy.md)
lays them out.

**Unit (`data`, JVM) — the store itself.** Most of the risk is here, and here it can be covered
exhaustively, with a fake `WorkspaceApi` whose every response the test releases by hand:

- a first watch fetches; a second watch of the same dates is served from the store with no request;
- a watch of five dates with three held fetches only the two missing ones, in one request; 50
  missing dates go as two requests;
- the same key watched twice while in flight makes one request;
- a watched date invalidated is refetched, and its old data is readable throughout with
  `refreshing = true`; an unwatched one is not refetched until it is next watched, and then shows
  its stale data at once with `refreshing = true`;
- **the in-flight race:** a date invalidated after its fetch was issued and before it landed ends
  stale and is fetched again, in both orders of landing;
- `Subscribed` marks every day, every meeting and the reference data stale, and refetches only the
  watched ones;
- a failed fetch keeps held data and reports the error; with no data it reports the error alone; a
  retry after a failure fetches again;
- `clear()` empties everything and drops a response that lands after it (the epoch);
- bounds: unwatched days far from today are dropped, watched ones never;
- meetings: found from a loaded day; fetched by id when no loaded day holds them; a meeting gone
  from its refetched day triggers the by-id fetch, and null reads as cancelled, another date as
  moved;
- the webapp's `daysInvalidated.test.ts` scenarios, each translated, so both clients are held to
  the same rules.

**Unit (`app`, JVM) — ViewModels.** Existing ViewModel tests move from fake `*Source`s to a store
over a fake `WorkspaceApi`. New: changing week, person or date never exposes the previous key's
data under the new one.

**Flow (Robolectric with `FakeBackend` and `FakeLiveUpdates`) — the screens over the real store.**
This is the right layer for "no spinner, no request" assertions: `FakeBackend` counts requests
exactly and can hold one open (`holdGraphql`), which a real environment cannot.

- Opening a meeting, going back and opening it again makes no second request and never shows the
  spinner (#22).
- A meeting opened from Home renders without a request.
- Calendar: next week shows the spinner, not the old week's meetings, the first time; back and
  forth again shows each week at once (#24). The same for changing person.
- Availability: a new date shows the spinner, never "no meetings", until it has loaded; a date seen
  before shows at once (#25).
- Pausing and resuming the activity (the share sheet's path) makes no request; stopping and
  starting it with a `Subscribed` refetches what is shown (#23).
- A `DaysChanged` for a shown date refetches it and shows the change, with the old content up
  meanwhile; one for a held but unshown date makes no request until that date is shown again.
- Signing out and in as another account shows nothing of the first account's data.
- The existing `LiveUpdatesFlowTest` and `CrossCuttingFlowTest` (M.92, M.93, M.94) keep passing,
  adapted where they asserted a refetch on resume.

**Acceptance (emulator against a fresh `and-acc` environment) — another client changes what this
one is viewing.** "User A on the web" is played as it is today: a second fixture account calling
the same API mutations the webapp sends, through the acceptance `Api` helper, while user B uses the
app. This layer is the only one that proves the real AppSync path end to end — subscription,
publish, broadcast and refetch — so each case waits on screen for the change with no action from
B. New cases, in a new `CacheAcceptanceTest` and in `LiveUpdatesAcceptanceTest`:

- **Calendar (uc-144):** B has their week open; A books a meeting with B as attendee in it, then
  renames it, then cancels it. Each shows on B's open calendar.
- **Room availability (uc-145):** B has a date open; A books a room on it, then cancels it. The
  booking appears in, then leaves, that room's card.
- **Moved meeting (uc-146):** B has Home open showing a meeting today; A moves it to tomorrow. It
  leaves today's section and appears under tomorrow.
- **Cached but off screen (uc-147):** B views week 1, then week 2. A renames a meeting in week 1.
  B goes back to week 1 and sees it at once (from the store, no spinner), then the new name.
- **Back from the background (uc-148):** B has a meeting open and puts the app in the background
  (the activity is stopped, so the socket drops). A renames the meeting and an admin renames its
  room. B returns: both names update, the room's through the reconnect refresh, since room changes
  are not broadcast.
- **One change, every screen (uc-149):** B opens a meeting from Home; A renames it. The details
  screen updates, and going back, Home already shows the new name with no spinner.
- The existing cases — a booking appearing on Home, M.111, O.122, O.123 and M.98 — keep passing
  unchanged; they now run against the store.

**Not affected:** the instrumented (non-acceptance) tests, which touch Keystore and sign-in only;
the Roborazzi screenshots, since what is drawn does not change; the Maestro smokes and
mootmaker-release's smoke suite, which sign in, book and read without depending on when a screen
refetches; and the webapp and API, which do not change.

## Documentation impacts

- **`use-cases.md`:** new cases 144 to 149 under M (above), [All frontends], each with its android
  link, and the webapp's slot as "not yet a webapp test case".
- **`mootmaker-android` README and `testing-strategy.md`:** a short "Caching and live updates"
  section, replacing `HomeRepository`'s "no cache" note.
- **`docs/development/architecture.md`:** the Android client's data flow — store, live channel,
  invalidation — beside the webapp's.
- **`android-app.md`:** nothing; this follows it.

## Rollout & migration

Ships in an ordinary release. Nothing persists, so there is no migration and no transition state:
the first launch of the new version starts with an empty store, as every cold start does.

## Risks

- **A subtle staleness bug** — a date that should have been refetched and wasn't — shows the user
  old data with no error. Mitigated by Decisions 5 and 6, the exhaustive store tests, and the
  5-minute safety net, which bounds how long any such miss can last on screen.
- **A store shared across screens** means a bug in it shows everywhere at once. That is also what
  makes it testable once instead of four times.
- **Reversing it** is an ordinary revert: no data or API depends on it.

## Implementation checklist

1. [Claude] The store, `WorkspaceApi` and the three queries, with the unit tests above.
   mootmaker-android#32, merged.
2. [Claude] All four read screens on the store, the writes' invalidation (Decision 9), the old
   queries removed, the flow tests and the new acceptance cases. Stages 2 and 3 of the first draft,
   done as one PR to save an acceptance cycle: mootmaker-android#34, merged after a green
   acceptance run (and-acc-261008-d0qz, torn down).
3. [Claude] Use cases 144 to 149 (this PR) and the documentation above (README and
   testing-strategy in #34, architecture.md here).
4. [Claude] A release: v5.10.9 (mootmaker-release run 94, 2026-10-08), every stage green, the n-1
   check passing with v5.10.8's APK.
5. [Geoff] Try it on the phone: in and out of a meeting, week and date changes, the share sheet.

## Definition of done

The new unit, flow and acceptance cases are green; the whole acceptance suite is green on a fresh
environment and in the release that ships it; #22 to #25 are closed by it; the documentation above
is done; and Geoff has seen it on the phone.
