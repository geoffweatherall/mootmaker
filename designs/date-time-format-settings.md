# Date/time format account settings

## Summary

Two new per-account settings — **time format** (24-hour or AM/PM) and **date format** (USA
`MM/DD/YYYY`, British `DD/MM/YYYY`, or ISO/Japanese `YYYY-MM-DD`) — editable in the webapp's
Settings page, affecting every date/time display and input across the app. This is the
properly-scoped, per-user-configurable version of an AM/PM time-picker tweak Geoff asked for and
then deferred earlier in the same session this doc was first drafted in.

## Status

**Drafting** — as of 2026-08-28. The one blocking open question is now resolved (see Trade-offs and
decisions) — no known blockers remain, but Status only moves to Ready on Geoff's explicit say-so
per this folder's own rule, not automatically.

## Scope / non-goals

In scope: the two settings themselves, and making every existing date/time display/input in the
webapp respect the signed-in viewer's own choice. Out of scope: per-meeting or per-room time zones
(this app has none today — see Technical considerations); localized weekday/month *names* (e.g.
translating "Monday"/"January") — this is a numeric-format setting, not an i18n/translation
feature; Android — `mootmaker-android` doesn't exist as a checked-out project yet, so this design
covers webapp + API only, though the resolved decisions below (especially "whose preference wins")
are written to be client-agnostic so Android can follow the same rules later.

## Trade-offs and decisions

Resolved directly with Geoff via upfront questions before drafting:

- **Storage: server-side, per-account** — new fields on the `Person` record, not browser
  `localStorage`. Syncs across devices, matches the existing "Your name" pattern rather than
  resetting per browser.
- **Default** (new sign-ups, and every account that hasn't set a preference yet): **24-hour + ISO
  `YYYY-MM-DD`**. Matches the API's own internal date-time format already (see Technical
  considerations), so it's the least surprising default and needs no locale-detection logic.
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
  behalf. Also keeps `createPerson`/guest-Person flows completely untouched (guest Persons never
  sign in, so they never need this). Confirmed directly with Geoff on 2026-08-28, resolving what
  was this doc's one blocking open question.

## Choices you had me make

None — every substantive decision in this doc, including the API-shape question above, was made
together via direct questions rather than decided unilaterally.

## Open questions

No blocking open questions remain.

**Non-blocking** (fine to resolve during implementation):

- `RoomAvailabilityPage`'s day-navigation `DatePicker` (`format="dddd D MMM YYYY"`, e.g. "Monday 5
  Jan 2026") doesn't map cleanly onto "USA/British/ISO" the way a plain numeric field does. Decide
  during implementation whether this picker's weekday/month-name display stays fixed regardless of
  the setting (arguably fine — it's a navigation aid, not "the record of when the meeting is"), or
  whether ISO specifically collapses it to a fully numeric `YYYY-MM-DD` while USA/British keep
  word-based month names but reorder (`"Monday, January 5, 2026"` vs `"Monday, 5 January 2026"`).
- Similarly, Person Calendar's Monday–Friday weekday column headers are plain weekday labels, not
  full dates — almost certainly unaffected by this setting either way, but worth a one-line
  confirmation during implementation rather than a silent assumption.

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
  `TimePicker`s (Start/End), currently hardcoded to MUI's defaults (no explicit `format`/`ampm`
  props today). This is the one place format drives *input parsing*, not just display.
- **`webapp/src/pages/SettingsPage.tsx`** — new section for the two settings themselves, mirroring
  `NameSection` (lines 56-129): local field state seeded from `useAuth()`, a mutation, an
  `ErrorBanner`, a `SubmitButton`, a `SuccessToast`. Always renders (not admin-gated).
  `useAuth()`/`AuthProvider.tsx` likely needs to expose the two preferences the same way it
  exposes `displayName`/`personId` today, rather than every consumer re-deriving them.
- **`mootmaker-api`** — a new GraphQL mutation (`updateMyPreferences` or similar — see Trade-offs
  and decisions) and its resolver, a new `PreferencesInput`/result type, and a `TimeFormat`/
  `DateFormat` enum pair on `Person`'s GraphQL type, plus the matching Java model changes (mirroring
  the `RoomError`/`PersonError`/`MeetingError` enum pattern — see Technical considerations). Likely
  still a full-item `PutItem` under the hood (same pattern `UpdatePersonHandler` already uses), just
  behind a new, narrower resolver rather than `UpdatePersonHandler` itself.
- **`mootmaker-tools/sample-data-generator`** — creates people via `createPerson`, which is
  untouched by this design (guest Persons never sign in, so never need a preferences mutation) — no
  changes needed here.

## Changes to the domain data model and data storage models

See [`data-model.md`](../docs/reference/data-model.md) for the current state. This design adds two new fields to the
`Person` domain concept — `timeFormat` (enum: `TWENTY_FOUR_HOUR` | `AM_PM`) and `dateFormat` (enum:
`USA` | `BRITISH` | `ISO`) — defaulting to `TWENTY_FOUR_HOUR`/`ISO` for any Person that's never set
them, surfaced via a new self-only mutation rather than folded into `PersonInput`/`updatePerson`
(see Trade-offs and decisions). DynamoDB-specific note: whatever handler backs the new mutation
still needs to do a full item replace carefully — `UpdatePersonHandler` already has to carry
`cognitoSub` forward explicitly since `PersonInput` doesn't include it (see Technical
considerations), and the new preferences handler will need the equivalent care in the other
direction: a preferences-only update must not touch `name`/`cognitoSub`. Cognito is untouched by
this design — no new custom attributes, no Lambda trigger changes.

## Technical considerations

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

Every one of the 90+ existing acceptance tests already exercises *some* date/time rendering, under
whatever format the account they sign in as currently has. Since the recommended default is
unchanged from today's actual (hardcoded) behaviour — 24-hour, ISO — the existing suite as-is
already covers "default format renders correctly" for free, with zero changes needed. The
interesting gap is coverage for the *non-default* formats. Two things worth doing, at different
scales:

1. **A new, dedicated acceptance-test section** (next available letter is `N`, case numbers
   starting at 100, per `mootmaker-webapp/acceptance/test-cases/README.md`'s numbering convention)
   covering the setting itself thoroughly — change time format, change date format, the section's
   own save/toast/persistence behaviour (mirroring I.74-76's shape: happy path, a validation-
   adjacent edge case if one exists, a degraded-state case for an account with no linked Person) —
   plus a small number of cases that change the setting and assert a *rendered* value elsewhere
   updates to match (Meeting Details' Date/Time rows are a good pick, since they exercise both
   `formatLocalDate` and `formatLocalTime` in one place).
2. **Don't touch the shared demo user's default.** Flipping it to a non-default format would turn
   the *entire* existing suite into incidental non-default-format coverage for free — appealing in
   theory, but means updating every existing hardcoded date/time assertion across dozens of files
   (e.g. `add-meeting.spec.ts`'s `toHaveValue('10:15 AM')`, `meeting-details.spec.ts`'s
   `\d{4}-\d{2}-\d{2}` regex) to compute the expected string from the demo user's *configured*
   format instead of a literal — real migration work, not a free lunch. **Recommendation instead**:
   pick 2-3 existing, already-passing scenarios (one each from Room Availability, Person Calendar,
   Meeting Details for spread) and add a *second, parameterized run* of just those specific cases
   under a fresh account deliberately set to a non-default format (e.g. AM/PM + British), asserting
   the same business outcome but computing the expected string from that format rather than a
   hardcoded literal.

## Documentation impacts

- `mootmaker/use-cases.md` — add the two new settings as use cases, plus "a rendered date/time
  reflects the *viewer's* own format preference regardless of whose data it is" as an explicit
  cross-cutting use case (the kind of rule `m-cross-cutting.md` already exists to hold) — this is
  the resolved "whose preference wins" decision above and deserves its own catalogued case rather
  than being implicit in each page's scenario.
- `mootmaker-webapp/README.md` — the `formatDateTime.ts` / date-time-rendering description, and the
  Settings page section list.
- `mootmaker-api/README.md` — a new section documenting the `updateMyPreferences` mutation
  alongside the existing `updatePerson`/`createPerson` documentation.
- `designs/data-model.md` — update once shipped, per this folder's own process.

## Rollout & migration

Purely additive — existing `Person` records simply lack these attributes until the owner sets them,
and the API's `fromItem()`-equivalent treats a missing attribute as the default
(`TWENTY_FOUR_HOUR`/`ISO`), the same way `cognitoSub` is already treated as `null` when absent
today. No backfill needed, no migration script, no feature flag — this can deploy cleanly to an
environment with existing data with no transition state to reason about.

## Risks

Low. The main risk is under-scoping the frontend change (missing one of the five files above, or
a display path not yet found) rather than anything hard to reverse — this is a pure UI/display
feature with an additive, defaultable data model change, not a migration or a breaking change to
anything existing.

## Implementation checklist

Legend: **[Geoff]** = manual/review step. **[Claude]** = implementation step. Ordered by
dependency.

**API (`mootmaker-api`):**
1. [Claude] Add `TimeFormat`/`DateFormat` enums to the GraphQL schema, plus `PreferencesInput` and
   an `UpdateMyPreferencesResult` (mirroring `UpdatePersonResult`'s `{ person, errors }` shape).
2. [Claude] Add the matching Java enums (mirroring the `RoomError`/`PersonError`/`MeetingError`
   pattern — see Technical considerations), and the two new fields on the `Person` record/DynamoDB
   item mapping, defaulting to `TWENTY_FOUR_HOUR`/`ISO` when absent.
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
10. [Claude] New `N` acceptance-test section (`n-date-time-format-settings.md` +
    `n-date-time-format-settings.spec.ts`) — see Testing impacts.
11. [Claude] The 2-3 parameterized non-default-format reruns of existing scenarios — see Testing
    impacts.
12. [Claude] Full acceptance suite green on a real deployed environment (this project's usual done
    condition).

**Review:**
13. [Geoff] Sign off on the deployed behaviour before this moves to Shipped.

## Definition of done

- New/changed acceptance-test coverage (the `N` section, plus the parameterized non-default-format
  reruns) is green.
- The full existing acceptance suite is still green on a real deployed environment.
- Both settings are editable in Settings, persist across sessions, and every one of the five
  component files above correctly reflects the signed-in viewer's own choice.
- Documentation impacts above are actually done, not just planned.
