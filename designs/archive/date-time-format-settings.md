# Date/time format account settings

## Summary

Two new per-account settings — **time format** (24-hour or AM/PM) and **date format** (USA
`MM/DD/YYYY`, British `DD/MM/YYYY`, or ISO/Japanese `YYYY-MM-DD`) — editable in the webapp's
Settings page, affecting every date/time display and input across the app. Both settings are
**mandatory** — every Person always has a concrete pair, defaulting to ISO + 24-hour — and both are
**presentation-only**: the GraphQL API goes on speaking ISO-8601 everywhere it already does, and
these settings change nothing but how a client renders date/times to a human and parses what that
human types back in. This is the properly-scoped, per-user-configurable version of an AM/PM
time-picker tweak Geoff asked for and then deferred earlier in the same session this doc was first
drafted in.

## Status

**Shipped** — as of 2026-09-01. Merged across `mootmaker`, `mootmaker-api` and
`mootmaker-webapp`, and deployed to production. The full acceptance suite ran green on a freshly
deployed environment (107 passed, 0 failed), and Geoff signed off after a manual pass on an
ephemeral environment seeded with demo data and a second account preset to British + AM/PM.

Two things were found after the design was written and are recorded above rather than quietly
fixed: the Add Meeting pickers had always disagreed with the rest of the app (US-locale defaults
against ISO displays), and the component list missed Room Availability's hour axis and
business-hours caption because it was built by grepping for existing call sites.

## Scope / non-goals

In scope: the two settings themselves, and making every existing date/time display/input in the
webapp respect the signed-in viewer's own choice. Out of scope: per-meeting or per-room time zones
(this app has none today — see Technical considerations); **any change to how date/times travel
over the API** — the wire format stays ISO-8601 in both directions, unconditionally (see "The API
is ISO-only" under Technical considerations); localized weekday/month *names* (e.g.
translating "Monday"/"January") — this is a numeric-format setting, not an i18n/translation
feature; Android — `mootmaker-android` exists as a repo but holds no app code yet (just its
`README`/`AGENTS`/`CLAUDE` docs), so this design covers webapp + API only, though the resolved
decisions below (especially "whose preference wins") are written to be client-agnostic so Android
can follow the same rules later.

## Trade-offs and decisions

Resolved directly with Geoff via upfront questions before drafting:

- **Storage: server-side, per-account** — new fields on the `Person` record, not browser
  `localStorage`. Syncs across devices, matches the existing "Your name" pattern rather than
  resetting per browser.
- **Default** (new sign-ups, and every account that hasn't set a preference yet): **ISO
  `YYYY-MM-DD` + 24-hour**. Matches the format the API itself speaks on the wire (see "The API is
  ISO-only" under Technical considerations), so it's the least surprising default, needs no
  locale-detection logic, and means a brand-new account renders exactly what the API returned.
  Nothing detects or infers the browser's locale, now or later — a user who wants a different
  format sets it explicitly in Settings.
- **Both preferences are mandatory — non-null everywhere, with no "unset" state.** `Person`
  exposes `dateFormat: DateFormat!` and `timeFormat: TimeFormat!`, and `PreferencesInput` requires
  both. Consequences, all deliberate: clients never write `?? 'Iso'` fallbacks at call sites, since
  a preference pair is always present; the mutation always sets *both* formats together rather than
  patching one (the Settings form seeds both fields from the viewer's current values, so it always
  has both to submit); and "never set it" is indistinguishable from "explicitly chose the default",
  which is fine — nothing in this feature needs to tell those apart. The default is materialised by
  the API when reading a record that predates the fields (see Rollout & migration), so non-null is
  safe from day one with no backfill.
- **Scope: every date/time display and input, app-wide** — not just the Add Meeting form.
- **Whose preference renders a shared view: always the signed-in viewer's own** — e.g. viewing a
  meeting someone else organised still renders in the viewer's own chosen format, never the
  organiser's. This is a real design decision (the alternative — rendering in whichever format the
  *data's owner* chose — would mean the same meeting displays differently depending on who's
  looking, which is confusing) and is written here explicitly so it doesn't get silently
  reinvented differently on Android later.
- **API shape: a new, self-only mutation** — `updateMyPreferences(preferences: PreferencesInput!)`
  (exact name TBD during implementation), separate from `PersonInput`/`updatePerson` entirely.
  Requires the caller to have a linked Person; no admin bypass, ever — unlike `updatePerson`
  (usable by an admin on someone else's Person, which is how admin-renames-a-person works), a
  personal display preference isn't "profile data" an admin should be able to set on someone else's
  behalf. Also keeps `createPerson`/`PersonInput`/guest-Person flows completely untouched (guest
  Persons never sign in, so they never need this — they get the defaults like anyone else).
  Confirmed directly with Geoff on 2026-08-28, resolving what was this doc's one blocking open
  question. The proposed schema addition, in full:

  ```graphql
  enum DateFormat { Usa British Iso }
  enum TimeFormat { TwentyFourHour AmPm }

  type Person {
      id: ID!
      name: String!
      "How this person prefers dates rendered and parsed by clients. Never null; defaults to Iso."
      dateFormat: DateFormat!
      "How this person prefers times rendered and parsed by clients. Never null; defaults to TwentyFourHour."
      timeFormat: TimeFormat!
  }

  "Both formats are required - this replaces the caller's whole preference pair, it does not patch one of them."
  input PreferencesInput {
      dateFormat: DateFormat!
      timeFormat: TimeFormat!
  }

  type UpdateMyPreferencesResult {
      "Populated when the update was applied."
      person: Person
      "Non-empty when the update was rejected; one entry per validation rule broken."
      errors: [PreferencesError!]!
  }

  enum PreferencesError {
      "The caller has no linked Person, so there is nothing to store a preference against."
      NoLinkedPerson
  }

  type Mutation {
      "Sets the signed-in caller's own display preferences. Self-only - requires a linked Person, and there is no admin override. Purely presentational: does not change the ISO-8601 format this API uses for every date/time it accepts and returns."
      updateMyPreferences(preferences: PreferencesInput!): UpdateMyPreferencesResult!
  }
  ```

  Making both input fields non-null means the schema itself enforces "both or neither": a missing
  or null format is rejected by AppSync before the resolver runs, so there is no
  `PreferencesRequired`-style validation error to write. That leaves exactly one runtime failure —
  the caller has no linked Person — and it gets **its own `PreferencesError` enum** rather than
  reusing `PersonError`. Reuse was considered and rejected: `PersonError.PersonNotFound` is
  documented as "id did not match any existing person", which is not what happens here (there is no
  id — the caller simply has no Person), and its sibling `NameRequired` would be permanently
  unreachable in this result. A one-value enum that says exactly what it means beats a two-value one
  where half is a lie.

- **Enum values use PascalCase**, matching every existing enum in `mootmaker.graphql`
  (`NameRequired`, `PersonNotFound`, `StartMissaligned`, `TimeRangeUnavailable`) rather than the
  SCREAMING_SNAKE this doc originally drafted. The Java constants must match
  character-for-character, since AppSync serializes enums by literal name.

- **The preference fields live on the shared `Person` type**, not behind a self-only
  `myPreferences` query. This does mean any signed-in caller could select another person's
  `dateFormat` via `people` or a meeting's `organiser`/`attendees`. Considered and accepted: a
  numeric-date-format choice is not sensitive, no client has any reason to select it outside
  `myPerson`, and the alternative costs a second query and resolver in `AuthProvider` to protect
  something that does not need protecting. Revisit only if `Person` later grows a field that *is*
  sensitive.

- **Rendered strings are zero-padded, matching what the pickers already produce today:**

  | Setting | Renders | dayjs format |
  |---|---|---|
  | `Iso` | `2026-08-24` | `YYYY-MM-DD` |
  | `British` | `24/08/2026` | `DD/MM/YYYY` |
  | `Usa` | `08/24/2026` | `MM/DD/YYYY` |
  | `TwentyFourHour` | `10:15`, `14:30` | `HH:mm` |
  | `AmPm` | `10:15 AM`, `02:30 PM` | `hh:mm A` |

  Zero-padding keeps display and input agreeing: MUI's pickers already render `08/24/2026` and
  `10:15 AM`, so this table is a formalisation of existing behaviour rather than a new convention,
  and picker round-trips stay known-good.

## Choices you had me make

None — every substantive decision in this doc, including the API-shape question above, was made
together via direct questions rather than decided unilaterally.

## Open questions

**None.** Everything below was resolved with Geoff on 2026-08-31, in one round before
implementation started, precisely because implementation would then run unattended.

- **`RoomAvailabilityPage`'s day-navigation `DatePicker`** (`format="dddd D MMM YYYY"`, e.g.
  "Monday 5 Jan 2026") **stays fixed**, ignoring the date-format setting entirely. It is a
  navigation aid, not the record of when a meeting is, and the weekday name is the useful part of
  it. No new formatting path, no risk.
- **Person Calendar's Monday–Friday weekday column headers are unaffected** — they are plain
  weekday labels, not dates. Confirmed rather than assumed.
- **Enum value naming, error enum shape, `Person`-type exposure, and the exact rendered strings**
  are all settled under Trade-offs and decisions above.
- **The Add Meeting pickers change for existing accounts** — see Testing impacts, where this doc's
  original assumption turned out to be wrong.

## Impacts on components

All in `mootmaker-webapp` unless noted. Exactly five page files touch a date/time today (confirmed
by grepping for `formatLocalTime`/`formatLocalDate`/`DatePicker`/`TimePicker`/
`toLocaleDateString`/`Intl.DateTimeFormat`/raw `new Date(...)` across `pages/*.tsx` and
`components/*.tsx` — nothing else does):

- **`webapp/src/graphql/formatDateTime.ts`** — the only date/time formatting logic in the app
  today. `formatLocalTime`/`formatLocalDate` need a second argument (the relevant format enum) and
  a lookup table mapping enum values to dayjs format strings.
- **`webapp/src/pages/HomePage.tsx`** — `formatLocalTime` for each agenda row's start–end range.
- **`webapp/src/pages/RoomAvailabilityPage.tsx`** — the day-navigation `DatePicker` (see open
  question above) and `formatLocalTime` for each meeting block's tooltip range.
- **`webapp/src/pages/PersonCalendarPage.tsx`** — `formatLocalTime` for each meeting row's range.
- **`webapp/src/pages/MeetingDetailsPage.tsx`** — `formatLocalDate` for the "Date" row,
  `formatLocalTime` for the "Time" row's range.
- **`webapp/src/pages/AddMeetingPage.tsx`** — the actual input controls: one `DatePicker`, two
  `TimePicker`s (Start/End), with no explicit `format`/`ampm` props today, so they silently inherit
  MUI's US-locale defaults (`08/24/2026`, `10:15 AM`). This is the one place format drives *input
  parsing*, not just display — and the one place existing behaviour visibly changes under the new
  default. See the correction in Testing impacts.
- **`webapp/src/pages/SettingsPage.tsx`** — new section for the two settings themselves, mirroring
  `NameSection` (lines 56-129): local field state seeded from `useAuth()`, a mutation, an
  `ErrorBanner`, a `SubmitButton`, a `SuccessToast`. Always renders (not admin-gated).
  `useAuth()`/`AuthProvider.tsx` likely needs to expose the two preferences the same way it
  exposes `displayName`/`personId` today, rather than every consumer re-deriving them.
- **`mootmaker-api`** — a new GraphQL mutation (`updateMyPreferences` or similar — see Trade-offs
  and decisions) and its resolver, a new `PreferencesInput`/result type with both fields required,
  and a non-null `TimeFormat`/`DateFormat` enum pair on `Person`'s GraphQL type, plus the matching
  Java model changes (mirroring the `RoomError`/`PersonError`/`MeetingError` enum pattern — see
  Technical considerations). Likely
  still a full-item `PutItem` under the hood (same pattern `UpdatePersonHandler` already uses), just
  behind a new, narrower resolver rather than `UpdatePersonHandler` itself.
- **`mootmaker-demo-data/sample-data-generator`** — creates people via `createPerson`, which is
  untouched by this design (guest Persons never sign in, so never need a preferences mutation) — no
  changes needed here.

## Changes to the domain data model and data storage models

See [`data-model.md`](../../docs/reference/data-model.md) for the current state. This design adds two new fields to the
`Person` domain concept — `timeFormat` (enum: `TwentyFourHour` | `AmPm`) and `dateFormat` (enum:
`Usa` | `British` | `Iso`) — both **mandatory** at the domain level: a Person always has exactly one
of each, and the pair defaults to `Iso`/`TwentyFourHour` for any Person that has never set them
(including every guest Person, which never signs in to set one). They are surfaced via a new
self-only mutation rather than folded into `PersonInput`/`updatePerson` (see Trade-offs and
decisions). Both are display metadata about the *person*, not about any meeting — no Meeting,
Room, or stored timestamp changes shape, and stored date/times remain ISO-8601 exactly as today.
DynamoDB-specific note: whatever handler backs the new mutation still needs to do a full item
replace carefully — `UpdatePersonHandler` already has to carry
`cognitoSub` forward explicitly since `PersonInput` doesn't include it (see Technical
considerations), and the new preferences handler will need the equivalent care in the other
direction: a preferences-only update must not touch `name`/`cognitoSub`. Cognito is untouched by
this design — no new custom attributes, no Lambda trigger changes.

## Technical considerations

- **The API is ISO-only, and stays that way.** Every date/time crossing the GraphQL boundary is an
  ISO-8601 *local* date-time string with no time-zone offset (`java.time.LocalDateTime` semantics,
  e.g. `"2026-07-01T14:30:00"`) — `Meeting.startTime`/`endTime`, `MeetingInput.startTime`/
  `endTime`, `suggestRoom`'s `startTime`/`endTime` arguments, and the `fromStartTime`/`toEndTime`
  meeting filters, all already documented as such in `mootmaker.graphql`. **This design does not
  touch any of that.** `dateFormat`/`timeFormat` are *client display preferences carried as data*,
  not a content-negotiation mechanism: the API never renders a date, never parses a localized one,
  and never varies its own wire format based on who is asking. Concretely, this means:
  - The webapp formats ISO → display string on the way out of the GraphQL layer, and parses
    display string → ISO on the way in (`AddMeetingPage`'s pickers), so the format setting is
    applied at the presentation edge only. Android will do the same later, using the same
    preference off the same `Person` — that is the whole reason this lives server-side rather than
    in `localStorage`.
  - Nothing downstream of the API (DynamoDB items, handler validation like the 15-minute-boundary
    and same-calendar-date rules, acceptance-test fixtures, `mootmaker-demo-data`) is affected by,
    or should ever consult, a preference value.
  - A preference is therefore never a correctness concern for stored data — the worst a wrong
    `dateFormat` can do is show a human the right instant written the wrong way round.
- `formatDateTime.ts` is deliberately locale-agnostic today: it does raw string-slicing on the
  backend's naive local ISO string (`"2026-07-01T14:30:00"`, no offset), specifically to avoid the
  browser silently applying its own time zone to a value that was never meant to carry one. Any
  dayjs-based reformatting must preserve that invariant — parse the naive string as local
  wall-clock time, never as UTC. This app has no time-zone concept at all today (rooms/meetings are
  implicitly "wherever the office is"); this design doesn't change that.
- No existing precedent in `mootmaker-api` for a **data-carrying** enum field on a DynamoDB-backed
  type. The only enum pattern that exists is the *error-code* enum (`RoomError`/`PersonError`/
  `MeetingError`) — a GraphQL `enum` plus a same-named Java `enum` whose constant names match the
  schema's enum value names exactly (AppSync serializes by literal string name). Worth mirroring
  that shape for `TimeFormat`/`DateFormat`, but double-check nothing in the error-mapping helpers
  gets awkwardly reused for it — it's a different *use* (a data value, not an error code).

## Testing impacts

**Correction — this section originally got the blast radius wrong.** It claimed the default is
"unchanged from today's actual (hardcoded) behaviour — 24-hour, ISO", so the existing suite would
need zero changes. That is true only of *read-only displays*. The **input pickers disagree with
them today**: `AddMeetingPage`'s `DatePicker`/`TimePicker` pass no `format`/`ampm` prop
(`AddMeetingPage.tsx` lines ~315-334), so they inherit MUI's US-locale defaults and render
`08/24/2026` and `10:15 AM`, while `formatDateTime.ts` renders `2026-08-24` and `10:15` by string
slicing. The app is already internally inconsistent, and nobody noticed because no test compares
the two.

Consequence: shipping `Iso`/`TwentyFourHour` as the default **changes the pickers** for every
existing account, breaking roughly 40 hardcoded picker lines across `add-meeting.spec.ts`,
`home-page.spec.ts` and `room-availability.spec.ts` — the `meridiem` typing helpers, and literal
assertions like `toHaveValue('10:15 AM')` and `toHaveValue('08/24/2026')`.

**Decision (2026-08-31): ship `Iso`/`TwentyFourHour` as the default and update those tests.** The
alternative — setting the shared demo account to `Usa`/`AmPm` so the picker tests keep passing —
only moves the breakage onto the display assertions, and leaves the project's stated default as the
one path the main test account never exercises. Fixing the tests makes input and display agree for
the first time, which is a genuine improvement this feature happens to force. The churn is
mechanical but real, and it is the single largest piece of unattended work here.

Beyond that correction, the *non-default* formats still need coverage. Two things, at different
scales:

1. **A new, dedicated acceptance-test section** (next available letter is `N`, case numbers
   starting at 100, per `mootmaker-webapp/acceptance/test-cases/README.md`'s numbering convention)
   covering the setting itself thoroughly — change time format, change date format, the section's
   own save/toast/persistence behaviour (mirroring I.74-76's shape: happy path, a validation-
   adjacent edge case if one exists, a degraded-state case for an account with no linked Person) —
   plus a small number of cases that change the setting and assert a *rendered* value elsewhere
   updates to match (Meeting Details' Date/Time rows are a good pick, since they exercise both
   `formatLocalDate` and `formatLocalTime` in one place).
2. **The shared demo user keeps the default** (`Iso`/`TwentyFourHour`) — confirmed, not merely
   recommended. Flipping it to a non-default format would turn the entire existing suite into
   incidental non-default coverage for free, but at the cost of rewriting every date/time assertion
   across dozens of files to compute expectations from a configured format rather than a literal.
   **Instead**: pick 2-3 existing, already-passing scenarios (one each from Room Availability,
   Person Calendar and Meeting Details, for spread) and add a *second, parameterized run* of just
   those cases under a fresh account deliberately set to `AmPm` + `British`, asserting the same
   business outcome but computing the expected string from that format rather than a hardcoded
   literal. Confirmed in scope on 2026-08-31 — it is the only thing that proves a non-default
   format renders end to end on a real deployment.

## Documentation impacts

- [`docs/reference/use-cases.md`](../../docs/reference/use-cases.md) — add the two new settings as
  use cases, plus "a rendered date/time reflects the *viewer's* own format preference regardless
  of whose data it is" as an explicit cross-cutting use case (the kind of rule
  `m-cross-cutting.md` already exists to hold) — this is the resolved "whose preference wins"
  decision above and deserves its own catalogued case rather than being implicit in each page's
  scenario.
- `mootmaker-webapp/README.md` — the `formatDateTime.ts` / date-time-rendering description, and the
  Settings page section list.
- `mootmaker-api/README.md` — a new section documenting the `updateMyPreferences` mutation
  alongside the existing `updatePerson`/`createPerson` documentation.
- [`docs/reference/data-model.md`](../../docs/reference/data-model.md) — update once shipped, per this
  folder's own process.

## Rollout & migration

Purely additive — existing `Person` records simply lack these attributes until the owner sets them,
and the API's `fromItem()`-equivalent substitutes the default (`Iso`/`TwentyFourHour`) for a
missing attribute, the same place `cognitoSub` is already treated as `null` when absent today. That
substitution is what makes the non-null GraphQL fields safe to ship on day one against a table full
of records written before the fields existed: the *item* attribute is optional, the *API* field
never is. Worth an explicit unit test on the mapper, since it is the single point holding that
guarantee up. No backfill needed, no migration script, no feature flag — this can deploy cleanly
to an environment with existing data with no transition state to reason about.

## Risks

**Low-to-moderate** — revised upward from "Low" once the picker-default finding landed (see Testing
impacts).

- **Acceptance-test churn is the real risk**, not the feature. Roughly 40 hardcoded picker lines
  across three spec files change meaning at once. A careless edit there produces a suite that passes
  while asserting the wrong thing — worse than one that fails. Update the typing helpers first, then
  the literals, and treat any test that needed *no* change as suspicious.
- Under-scoping the frontend change (missing one of the five files above, or a display path not yet
  found) remains a risk, though the file list was verified by grep.
- Nothing here is hard to reverse: an additive, defaultable data-model change and a pure
  display/input feature — no migration, no breaking API change.

## Implementation checklist

Legend: **[Geoff]** = manual/review step. **[Claude]** = implementation step. Ordered by
dependency.

Logistics for the unattended run, agreed 2026-08-31: a `feature/date-time-format-settings` branch
cut fresh from `main` in each of `mootmaker`, `mootmaker-api` and `mootmaker-webapp`, one PR each,
merged API-before-webapp. One ephemeral environment, reused throughout and **left running** at the
end so Geoff can review the deployed behaviour before sign-off. On hitting a blocker: use judgement
and keep going on anything reversible, recording each such call here rather than stopping.

**API (`mootmaker-api`):**
1. [Claude] Add `TimeFormat`/`DateFormat` enums to the GraphQL schema, plus `PreferencesInput`
   (both fields non-null) and an `UpdateMyPreferencesResult` (mirroring `UpdatePersonResult`'s
   `{ person, errors }` shape), and the two non-null fields on `Person` — see the schema block
   under Trade-offs and decisions. Leave every existing date/time field exactly as it is: this step
   adds preference fields, it does not touch the API's ISO-8601 wire format.
2. [Claude] Add the matching Java enums (mirroring the `RoomError`/`PersonError`/`MeetingError`
   pattern — see Technical considerations), and the two new fields on the `Person` record/DynamoDB
   item mapping, substituting `Iso`/`TwentyFourHour` when the attribute is absent so the non-null
   GraphQL fields hold against pre-existing records. Unit-test that absent-attribute path directly.
3. [Claude] Write `UpdateMyPreferencesHandler` — self-only (caller's `cognitoSub` must match; no
   admin bypass), full-item `PutItem` carrying `name`/`cognitoSub` forward unchanged. Depends on:
   1, 2.
4. [Claude] Wire the resolver into AppSync/Terraform, deploy to an ephemeral environment for a
   first pass. Depends on: 3.

**Webapp (`mootmaker-webapp`):**
5. [Claude] Extend `formatDateTime.ts`: `formatLocalTime`/`formatLocalDate` take a format-enum
   argument and a dayjs-format lookup table, preserving the naive-local-time parsing invariant (see
   Technical considerations).
6. [Claude] Expose the two preferences from `useAuth()`/`AuthProvider.tsx`, the same way
   `displayName`/`personId` are exposed today.
7. [Claude] New Settings section (mirroring `NameSection`) calling the new mutation. Depends on:
   4, 6.
8. [Claude] Update all five display/input call sites (`HomePage`, `RoomAvailabilityPage`,
   `PersonCalendarPage`, `MeetingDetailsPage`, `AddMeetingPage`) to pass the viewer's preferences
   through. Depends on: 5, 6. Resolve the two non-blocking open questions (RoomAvailabilityPage's
   day-picker format, Person Calendar's weekday headers) while doing this.
9. [Claude] Deploy webapp to the same ephemeral environment as step 4 for an end-to-end manual
   check.

**Testing:**
10. [Claude] Update the ~40 existing hardcoded picker lines in `add-meeting.spec.ts`,
    `home-page.spec.ts` and `room-availability.spec.ts` for the pickers' new default rendering
    (`2026-08-24` / `10:15` rather than `08/24/2026` / `10:15 AM`), including the `meridiem` typing
    helpers. Depends on: 8. See the correction in Testing impacts.
11. [Claude] New `N` acceptance-test section (`n-date-time-format-settings.md` +
    `n-date-time-format-settings.spec.ts`) — see Testing impacts.
12. [Claude] The 2-3 parameterized non-default-format reruns of existing scenarios, under an
    account set to `AmPm` + `British` — see Testing impacts.
13. [Claude] Full acceptance suite green on a real deployed environment (this project's usual done
    condition).

**Review:**
14. [Geoff] Sign off on the deployed behaviour before this moves to Shipped.

## Definition of done

- New/changed acceptance-test coverage (the `N` section, plus the parameterized non-default-format
  reruns) is green.
- The full existing acceptance suite is still green on a real deployed environment.
- Both settings are editable in Settings, persist across sessions, and every one of the five
  component files above correctly reflects the signed-in viewer's own choice.
- A Person created before this feature (or via `createPerson`) reads back as ISO + 24-hour rather
  than erroring on the non-null fields.
- The API's own request/response date/times are still ISO-8601 regardless of the caller's
  preference — worth one explicit assertion so a future change can't quietly turn these settings
  into a wire-format switch.
- Documentation impacts above are actually done, not just planned.
