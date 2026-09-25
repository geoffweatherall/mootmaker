# Admin management of rooms and people

## Summary

Gives admins full CRUD over Rooms and People from two new dedicated pages (Rooms, Persons), moved
out of Settings, plus the ability to grant or revoke admin access on another person. Settings is
cut down to purely self-service content (name, date/time format, delete account). This is a
backend-heavy feature: creation already existed and was already admin-only, but **deletion of a
Room or a Person, and granting/revoking admin status, do not exist as API operations at all
today** — this design adds them, deliberately reshaping the existing `Person` mutations around them
rather than bolting them on, since backward compatibility carries no weight here (nothing external
depends on this API yet).

## Status

**Building** — 2026-09-25. Approved by Geoff (every open question resolved); implementation started
the same day.

## Scope / non-goals

In scope: `deleteRoom`, `deletePerson`, `setPersonAdmin`, splitting `updatePerson` into
`updateMyName` (self-only) + `renamePerson` (admin-only), and the UI already prototyped (nav
changes, cut-down Settings, Rooms page, Persons page, all with a mobile layout).

Out of scope, deliberately:
- **The sign-up name-collision problem** (a sign-up with a name matching an existing Person creates
  a duplicate rather than linking) — tracked separately as
  [mootmaker-api#70](https://github.com/geoffweatherall/mootmaker-api/issues/70). Not blocking:
  nothing in this design assumes it's fixed.
- **AppSync schema-level authorization directives** (`@aws_cognito_user_pools(cognito_groups:
  [...])`) — considered and rejected, see Trade-offs and decisions. Authorization stays exactly
  where it is today: `Identity.requireAdmin`/`Identity.isAdmin`, re-checked inside each handler.
- **A `mergePersons` operation** for resolving a name-collision duplicate once #70 is picked up —
  that issue names it as an open question for whoever builds it, not decided here.
- **Android** — `mootmaker-android` holds no app code yet, so this covers webapp + API only.
- **`mootmaker-demo-data` gaining `deletePerson`/`deleteRoom` calls of its own** — noted as a real
  future need (see Impacts on components) but not built now; it doesn't currently need to delete
  anything it creates.

## Trade-offs and decisions

Resolved through discussion before drafting:

- **Duplicate `isAdmin`: a real DynamoDB attribute on `Person`, kept in sync with Cognito's
  `custom:class`, rather than resolving it live from Cognito on read.** The alternative — querying
  Cognito per linked account whenever `Person.isAdmin` is selected — avoids any duplication but
  costs a live `AdminGetUser`-shaped call per person just to render the Persons list, with no batch
  API for it. `custom:class` stays the actual authorization source every request checks
  (`Identity.isAdmin`); `Person.isAdmin` is a read-optimised copy, written at the same time.

- **`deleteRoom` rejects outright if the room has any meeting from today onward** (new
  `RoomError.RoomHasUpcomingMeetings`), rather than cascading. A room's upcoming meetings can belong
  to many unrelated organisers — one admin deleting a room shouldn't silently cancel other people's
  meetings across the whole organisation. Forces a deliberate "move these first" step instead.
  `deletePerson` (below) cascades instead, because there the blast radius is naturally scoped to
  just that one person's own meetings.

  This *is* safe to build as a genuine hard delete once past meetings are the only thing that can
  reference a gone room, because `MeetingResponse.resolveRoom`
  ([`impl/src/main/java/com/mootmaker/handler/MeetingResponse.java`](https://github.com/geoffweatherall/mootmaker-api/blob/main/impl/src/main/java/com/mootmaker/handler/MeetingResponse.java))
  already has exactly this fallback in place, unused until now:

  > "Rooms cannot be deleted today, but the same reasoning applies if that ever changes." — falls
  > back to `Room(roomId, "Deleted room", 0)` for an id it can't resolve.

- **`deletePerson` cascades exactly like `deleteMyAccount` already does to the caller's own
  account** — cancel every upcoming meeting they organise, remove them from every upcoming meeting
  they only attend, leave the past untouched — just admin-invoked against someone else. Same
  reasoning `DeleteMyAccountHandler` already documents for the ordering (Cognito user deleted
  first, then DynamoDB cleanup, so a partial failure fails toward "still works" rather than
  "silently broken"), and `MeetingResponse.resolvePerson`'s "Deleted user" placeholder already
  covers what a past meeting sees afterward — this path is proven, not new.

- **`updatePerson` is retired and split by caller, not merged with the new admin fields.** Today one
  mutation serves two different authorization shapes (self-rename, or admin renaming anyone) under
  a name that reveals neither. Replaced by:
  - `updateMyName(name: String!)` — self-only, joining the existing `updateMy*` family
    (`updateMyPreferences`, `deleteMyAccount`): same shape, no id argument, no admin override.
  - `renamePerson(id: ID!, name: String!)` — admin-only.

  `PersonInput` is retired with it. It only ever wrapped one field (`name`); `RoomInput`/
  `MeetingInput` earn their wrapper by grouping several. `createPerson` moves to a bare
  `name: String!` argument for the same reason.

- **`setPersonAdmin(id: ID!, isAdmin: Boolean!)` stays a separate mutation from `renamePerson`, not
  merged into one `editPerson`.** A single merged mutation would give one `PutItem` instead of two —
  looks more "atomic" — but the real risk was never mutation count, it's a handler forgetting a
  field it doesn't own on a full-item `PutItem`. See the very next decision: that risk is exactly
  what already happened.

  Keeping them separate also keeps the name itself meaningful: something that can grant admin
  access should be findable by grepping for exactly that, not buried as an argument on a
  general-purpose "edit" mutation. The Edit Person dialog's single Save click sends both as one
  GraphQL document (`mutation { renamePerson(...) { ... } setPersonAdmin(...) { ... } }`) — one HTTP
  round trip, GraphQL executes mutation root fields serially, no UX cost to keeping them separate
  server-side.

- **Both new/changed Person-writing handlers must explicitly carry forward every field they don't
  own.** Investigating this surfaced a live bug —
  [mootmaker-api#71](https://github.com/geoffweatherall/mootmaker-api/issues/71): today's
  `UpdatePersonHandler` carries `cognitoSubs` forward explicitly but passes `null` for
  `dateFormat`/`timeFormat`, which `Person`'s constructor then normalises to the *defaults* rather
  than leaving unset — so any successful rename today silently resets the target's date/time
  preferences. Filed and fixed independently of this design, but it's the concrete reason
  `renamePerson` and `setPersonAdmin` are specified below as read-then-full-replace, carrying
  `cognitoSubs`, `dateFormat`, `timeFormat`, and whichever of `name`/`isAdmin` they don't own,
  forward from the record they just read — not reconstructed from a partial set of arguments.

- **Write order: DynamoDB first, Cognito second, on both new mutations** — matching
  `UpdatePersonHandler`'s existing order for name propagation, but here the direction is also the
  *secure* one, not just consistent. If the Cognito call fails after the DynamoDB write succeeds,
  the failure mode is "the Persons screen shows them as admin but their token doesn't grant it yet"
  — fail-closed. The reverse order risks a token silently carrying real admin access the DynamoDB
  record (and therefore the admin UI) doesn't yet reflect — fail-open, invisible privilege
  escalation. Same principle either mutation, opposite consequence if got wrong for `setPersonAdmin`
  specifically.

- **`setPersonAdmin` surfaces a Cognito-sync failure; `renamePerson` doesn't.** Both do the same
  two-system write, but the stakes differ: `updatePerson`'s existing swallow-and-log behaviour for a
  name-sync failure is justified by its own comment — Cognito's `name` is "only a display
  convenience for the brief window before `AuthProvider`'s `myPerson` lookup resolves." A stuck
  `custom:class` sync is not cosmetic; it means the person still can't actually do admin things
  despite what the UI now shows. `SetPersonAdminResult` gets a `cognitoSyncFailed: Boolean!` field
  for this — true only alongside a successful DynamoDB write and an empty `errors` list, never
  alongside a rejection. `renamePerson` keeps the existing swallow-and-log precedent rather than
  gaining the same field "for consistency" where it wouldn't carry real meaning.

  **UI handling of `cognitoSyncFailed: true`**: a small dialog on top of the (already-closed) Edit
  Person dialog, mirroring `CancelMeetingDialog`'s "mounts alongside, not replacing, the triggering
  content" pattern — the DynamoDB write already succeeded, so this isn't a rejection, it's a
  follow-up prompt. Title poses it as a question, body names the consequence, actions are
  **Cancel** (dismiss; the grant/revoke stands as already saved, just not yet reflected in the
  person's token) and **Retry** (re-sends `setPersonAdmin` with the same `id`/`isAdmin` — idempotent,
  same call either way). E.g.:

  > **Sync to sign-in failed**
  > {{name}}'s admin access was saved, but couldn't be synced to their sign-in account yet — they
  > won't be able to use it until this succeeds.
  > [Cancel] [Retry]

  Deliberately no persistent "sync pending" indicator on the Person card if Cancel is chosen — that
  would need new stored/queryable state this design doesn't otherwise need, and isn't what was
  asked for. Re-opening Edit and saving again re-sends `setPersonAdmin` the same way Retry does, so
  nothing is unrecoverable, just not proactively surfaced a second time.

- **A Person with no linked Cognito account cannot be made admin.** `custom:class` lives on the
  Cognito account, not the `Person` record — a guest Person (the "Not signed up yet" case in the
  prototype) has nothing for `setPersonAdmin` to actually flip; setting DynamoDB's `isAdmin` alone
  would show an "Admin" badge that grants nothing until they eventually sign up, which is worse than
  just rejecting it. **Enforced in both places, not just one:**
  - **Backend**: `setPersonAdmin(isAdmin: true)` rejects with a new `PersonError.NoLinkedAccount`
    when the target's `cognitoSubs` is empty. This is the actual guarantee — the webapp check below
    is a courtesy, not the enforcement.
  - **Webapp**: explained *upfront*, not just surfaced as an error after the fact — the Edit Person
    dialog's admin switch is disabled with inline copy for a guest Person (e.g. "This person hasn't
    signed in yet — admin access can only be granted once they've signed up."), rather than letting
    someone flip it and only then finding out it can't apply.

- **No one can remove their own admin access, full stop — not just the demo account.**
  `setPersonAdmin(id: <caller's own Person id>, isAdmin: false)` rejects with a new
  `PersonError.CannotRevokeOwnAdminAccess`, regardless of which admin is calling it. This is a
  stronger, simpler rule than the "just protect the reserved demo account" version floated earlier
  in discussion (superseding that question rather than answering it as asked) — mirrors
  `deletePerson`'s existing `CannotDeleteSelf` guard for the same underlying reason: an admin
  shouldn't be able to lock themselves out via this path, whether that's a slip, a compromised
  session, or (in the demo account's specific case) breaking the one admin every fresh environment
  is guaranteed to have. Granting *someone else* admin, or granting/revoking your own on a person
  *other* than yourself, is unaffected.

- **No AppSync schema-level authorization directives.** `@aws_cognito_user_pools(cognito_groups:
  [...])` only checks Cognito User Pool *Group* membership — there's no `scopes:` parameter, and
  this project has no Cognito Group resource at all (admin is a custom attribute,
  `custom:class`). Worse: Cognito Groups are inherently a *user* concept, and the M2M
  `client_credentials` clients (`acceptance_tests`, `demo_data`) that call `createRoom`/
  `createPerson`/etc. today have no user behind them at all — they can never have group membership,
  no matter what Terraform changes are made. Adding a `cognito_groups` directive to any mutation
  those clients need to keep calling would reject them outright at the AppSync layer. So this stays
  Lambda-side `Identity.requireAdmin`/`Identity.isAdmin`, exactly as today, for every mutation this
  design adds.

## Choices you had me make

- **`deletePerson` refuses to delete the caller's own Person** (new `PersonError.CannotDeleteSelf`)
  — an admin deleting themselves through the admin path would skip `deleteMyAccount`'s own
  ordering guarantees (Cognito-first, reserved-account check) entirely. Point them at
  `deleteMyAccount` instead.
- **`deletePerson` refuses to delete a reserved system account's Person** (new
  `PersonError.ReservedAccount`) — reusing the same `RESERVED_ACCOUNT_EMAILS` mechanism
  `DeleteMyAccountHandler` already uses. Concretely protects the demo user's Person
  (`aws_dynamodb_table_item.demo_person`), which is Terraform-managed and not something an app
  mutation should be able to remove out from under a running `production` environment.
- **`renamePerson`/`setPersonAdmin`/`deletePerson` reuse the existing `PersonError` enum** rather
  than each getting their own, matching this project's stated convention (one error enum per
  *entity*, shared across its mutations) — confirmed against `mootmaker-api/CLAUDE.md` rather than
  assumed.

## Open questions

**None remaining.** Blocking (whether a guest Person can be granted admin) and non-blocking (the
`cognitoSyncFailed` UI shape) are both resolved — see "A Person with no linked Cognito account
cannot be made admin" and "`setPersonAdmin` surfaces a Cognito-sync failure" under Trade-offs and
decisions.

## Impacts on components

**`mootmaker-api`:**
- `api/mootmaker.graphql` — remove `updatePerson`, `UpdatePersonResult`, `PersonInput`; add
  `updateMyName`/`UpdateMyNameResult`, `renamePerson`/`RenamePersonResult`,
  `setPersonAdmin`/`SetPersonAdminResult` (with `cognitoSyncFailed`), `deleteRoom`/
  `DeleteRoomResult`, `deletePerson`/`DeletePersonResult`; add `isAdmin: Boolean!` to `Person`;
  change `createPerson(person: PersonInput!)` to `createPerson(name: String!)`; add
  `RoomError.RoomHasUpcomingMeetings`, `PersonError.NoLinkedPerson`/`CannotDeleteSelf`/
  `ReservedAccount`/`NoLinkedAccount`/`CannotRevokeOwnAdminAccess`.
- New handlers: `UpdateMyNameHandler`, `RenamePersonHandler`, `SetPersonAdminHandler`,
  `DeleteRoomHandler`, `DeletePersonHandler`. `UpdatePersonHandler`/`CreatePersonHandler` retired or
  rewritten to match the new signatures.
- `Person.java` — add `isAdmin` (mirroring how `dateFormat`/`timeFormat` are already optional
  DynamoDB attributes defaulting on read), `toItem()`/`fromItem()` updated.
- `deploy/terraform/appsync.tf` — five new resolvers, matching the existing `create_room`/
  `update_room`/`create_person`/`update_person` resolver blocks' shape.
- **Every consumer of the retired `PersonInput`/`updatePerson` shape needs updating** — found by
  grepping the actual call sites, not assumed minimal:
  - `mootmaker-api/verify`: `CreatePersonAcceptanceIT`, `CreateMeetingAcceptanceIT`,
    `CreateMeetingValidationAcceptanceIT`, `CreateRoomAcceptanceIT`, `HistoryRetentionAcceptanceIT`,
    `UpdatePersonAcceptanceIT`, `AuthenticationAcceptanceIT` (its "no Authorization header" fixture
    mutation), `DemoAndE2eUserRolesAcceptanceIT` — plus five new `*AcceptanceIT` classes for the new
    mutations, mirroring `CreateRoomAcceptanceIT`'s shape.
  - `mootmaker-demo-data`: `DemoData.java`'s `createPerson` call (`impl/src/main/java/com/mootmaker/demodata/DemoData.java:213-215`).
  - `mootmaker-webapp/acceptance/tests/authorization-boundaries.spec.ts`: constructs a raw
    `updatePerson` mutation directly against the M2M-fetched token to test the authorization
    boundary — needs to target `renamePerson`/`updateMyName` instead, and its assertions on
    `UpdatePersonHandler`'s specific rejection message need re-checking against whichever new
    handler now owns that check.

**`mootmaker-webapp`:** UI fully prototyped —
[interactive click-through prototype](https://claude.ai/artifact/YQiWH12MsrXquj6grm3MCw), private,
covers desktop and mobile:
- `components/MenuContent.tsx` — Home/Calendar/Room availability unchanged; new "Admin" section
  (Rooms, Persons) between them and Settings; Settings stays last.
- `pages/SettingsPage.tsx` — `AdminSections()` (Rooms/People inline lists + `RoomDialog`/
  `PersonDialog`) removed entirely; page cut to Your name, Date & time format, Delete account, plus
  a banner pointing at the new pages.
- New `pages/RoomsPage.tsx`, `pages/PersonsPage.tsx` — card-grid layout matching
  `RoomAvailabilityPage`'s existing card pattern, Add/Edit/Delete dialogs reusing the existing
  `Dialog`/`ErrorBanner`/`SubmitButton` pattern `RoomDialog`/`PersonDialog` already established.
  Persons cards show the admin badge and linked-email chips; the admin toggle lives as a switch
  inside Edit Person only (not Add, not a separate card action) — this was reworked once during
  prototyping, see the prototype's own history. The switch is **disabled**, with inline explanatory
  copy in place of the usual helper text, in two cases: editing a person with no linked email (the
  "Not signed up yet" card state — see "A Person with no linked Cognito account cannot be made
  admin"), and editing the signed-in admin's own Person (see "No one can remove their own admin
  access"). Neither is yet reflected in the published prototype; do both alongside the matching
  schema changes so the disabled states and the new `PersonError` cases land together.
- Both new pages need a mobile layout (top app bar + slide-in drawer replacing the sidebar, FAB
  replacing the header "Add" button) — already prototyped, not yet built against real MUI
  components.

**`mootmaker-demo-data`:** no code change needed now (see Scope/non-goals), but worth naming: it
gains no way to clean up what it creates via the API until it adopts `deletePerson`/`deleteRoom`
itself — currently relies entirely on the separate `database-reset` Lambda for that.

## Changes to the domain data model and data storage models

See [`data-model.md`](../docs/reference/data-model.md) for the current state. Deltas:

- **DynamoDB, People table**: new `isAdmin` attribute (Boolean, optional — absent means `false`,
  same "optional attribute, non-null GraphQL field with a default" pattern `dateFormat`/
  `timeFormat` already use). Read-optimised copy of admin status; `custom:class` on the linked
  Cognito account(s) stays the actual authorization source.
- **Cognito**: no new attribute — `custom:class` already exists and already takes `"admin"`/
  `"standard"`. What's new is a client-invocable path to *set* it (`setPersonAdmin`, via
  `AdminUpdateUserAttributes`) where today only `PostConfirmationCreatePersonHandler` (always to
  `"standard"`) and manual Terraform/console action can.
- **No new table, no new GSI.** Deletion of a Room/Person is a plain `DeleteItem` on an existing
  table; nothing needs to look them up by anything the primary key doesn't already give.

## Technical considerations

- `Person`'s compact constructor normalises a `null` `dateFormat`/`timeFormat` to the *defaults*,
  not "leave unset" — see mootmaker-api#71. Any new full-item-replace write must pass the current
  record's actual values, not `null`, for every field it isn't changing.
- `MeetingResponse.resolveRoom`/`resolvePerson` already provide the "Deleted room"/"Deleted user"
  placeholder fallback a hard delete needs — confirmed by reading the code, not assumed. No new
  resolver-layer work required for existing meetings to keep rendering after their room or organiser
  is deleted.
- `DeleteMyAccountHandler`'s Cognito-then-DynamoDB ordering (and its reasoning: a transient Cognito
  failure should leave the account "still works" rather than "silently broken") is the direct model
  for `deletePerson`'s own ordering, just admin-invoked. Worth extracting the cascade logic
  (cancel-upcoming-organised, remove-from-upcoming-attended) into something both handlers call,
  rather than duplicating it.
- The M2M `admin` OAuth scope (`Identity.hasAdminScope`) is checked; the sibling `execute` scope is
  granted alongside it on every existing M2M client but not actually inspected by any handler today
  (`Identity.requireAuthenticated` only checks that an identity exists) — noted while investigating
  this design, not something this design changes.

## Testing impacts

**Unit (`mootmaker-api`, `mvn -f impl/pom.xml test`):** new handler tests for
`UpdateMyNameHandler`/`RenamePersonHandler`/`SetPersonAdminHandler`/`DeleteRoomHandler`/
`DeletePersonHandler`, mirroring the existing `UpdatePersonHandlerTest`/`CreateRoomHandlerTest`
shape — each needs an explicit case proving `dateFormat`/`timeFormat`/`cognitoSubs` survive a write
that isn't touching them (the regression case for mootmaker-api#71). `Person`'s `isAdmin`
attribute-mapping needs the same "absent attribute defaults" unit test `dateFormat`/`timeFormat`
already have. This is also the right (only practical) layer for `cognitoSyncFailed` itself: mock
the Cognito client to throw from `SetPersonAdminHandler`'s `AdminUpdateUserAttributes` call, assert
the DynamoDB write still happened, `cognitoSyncFailed: true`, `errors` empty — a real Cognito
failure isn't something an acceptance run can reliably force (see below).

**`/verify` acceptance IT (`mootmaker-api`):** this is the right layer for the authorization
boundary itself — real AppSync, real Cognito tokens (both a real user's and the M2M client's),
which a mocked layer can't exercise. New `*AcceptanceIT` classes per new mutation, each proving:
admin succeeds, non-admin is rejected, the M2M admin-scope token succeeds (since `demo_data`/
`acceptance_tests` both need continued access to whichever of these they call). Every existing
`*AcceptanceIT` class listed under Impacts on components needs its `PersonInput`/`updatePerson`
usage updated to compile at all, not just to keep passing.

**Integration (`mootmaker-webapp/webapp/tests/`, mocked API/auth):** the right layer for the new
pages' own UI logic — dialogs opening/closing, the admin switch, form validation, card
add/edit/remove reflecting live in the mocked cache — same reasoning
`attendee-response-status.spec.ts` already uses for this class of scenario: no real AWS needed,
since what's under test is client-side wiring, not server behaviour. New spec file(s) for
`RoomsPage`/`PersonsPage`, mirroring `settings-rooms.spec.ts`/`settings-people.spec.ts`'s existing
shape but for the new pages rather than Settings' old inline sections. Also the right layer for the
retry/cancel prompt: mock `setPersonAdmin`'s response as `cognitoSyncFailed: true`, assert the
prompt appears with the expected copy; clicking **Retry** re-sends `setPersonAdmin` with the same
variables (assert a second matching request); clicking **Cancel** dismisses with no second call and
the person's card still reflects the (already-successful) admin change. Same reasoning as the rest
of this layer — this is entirely client-reaction-to-a-mocked-response, no real Cognito failure
needed to prove the UI does the right thing with one.

**Acceptance (`mootmaker-webapp/acceptance/`, real deployed environment):** existing sections
**J** (`j-settings-rooms.md`, cases 77-83) and **K** (`k-settings-people.md`, cases 84-88) describe
the Rooms/People sections *inside Settings* — both now describe a page structure this design
removes. They get superseded by two new lettered sections (next available: **P**, starting case
122) — `p-rooms.md` and `q-persons.md` — covering the same functional ground (admin can
create/edit rooms and people, standard user can't reach any of it) against the new top-level pages,
plus the genuinely new cases this design adds: delete room (including the blocked-with-upcoming-
meetings case), delete person (including the cascade), and grant/revoke admin. **L**
(`l-authorization-boundaries.md`) needs two updates, not just new cases: **L.89** ("standard user
cannot reach admin-only UI") currently asserts against Settings' old sections and needs re-pointing
at the new pages/nav items; **L.91** ("self-rename works; renaming someone else does not") is
written against `UpdatePersonHandler`'s specific check and mutation name — both change under this
design, so its assertions need updating to match, not just its prose. The grant/revoke-admin case
in the new **Q** section covers only the `cognitoSyncFailed: false` happy path — deliberately not
the retry/cancel prompt, which needs the Cognito call to actually fail and there's no reliable way
to force that against a real environment on demand; that behaviour is fully covered at the Unit and
Integration layers above instead.

**`mootmaker-release`'s smoke suite:** not affected — it's deliberately minimal and doesn't cover
admin-only Settings/Rooms/People flows today; nothing here changes what it should assert on.

## Documentation impacts

- [`docs/reference/data-model.md`](../docs/reference/data-model.md) — update once shipped, per this
  folder's process (new `isAdmin` attribute, retired `cognitoSub-index`-adjacent notes if any
  reference the old mutation shape).
- [`docs/reference/use-cases.md`](../docs/reference/use-cases.md) — retire/rewrite the Settings §J/K
  use cases to describe the new pages; add cases for delete-room, delete-person, grant/revoke admin.
- `mootmaker-api/README.md` — replace the `updatePerson`/`createPerson`(`PersonInput`) description
  with the new mutation set.
- `mootmaker-webapp/README.md` — Settings page section list, new Rooms/Persons pages.
- [mootmaker-api#70](https://github.com/geoffweatherall/mootmaker-api/issues/70) — worth a comment
  once this ships, since the new Persons admin screen is what makes a sign-up-name collision visible
  and mergeable for the first time; doesn't need to be *fixed* by this design, but the issue's own
  context should note this landed.

## Rollout & migration

Additive on the data side — `isAdmin` absent on every existing `Person` record defaults to `false`
on read, same pattern `dateFormat`/`timeFormat` already prove safe. No backfill needed. The schema
break (`updatePerson`/`PersonInput` removed) is not additive, but nothing external depends on this
API today, which is the whole premise of this design — no deployed client exists that isn't part of
this same rollout (webapp, `/verify`, `demo-data`, all updated together, same reasoning
`graphql-schema-and-caching.md` already documents for why this project can make this kind of change
freely pre-1.0). Deploy order: `mootmaker-api` before `mootmaker-webapp` (webapp reads the API's
Terraform outputs), same as every other cross-repo feature.

## Risks

**Moderate** — the largest risk is the blast radius under Impacts on components: this touches every
existing `/verify` test that creates a Room or Person, `mootmaker-demo-data`'s seeding, and the
webapp's own authorization-boundary test, all at once, because `PersonInput` is being removed
rather than deprecated. Missing one of those breaks a build, not silently — acceptable, but worth
doing that sweep first as its own checklist step before any new mutation logic, the same lesson
`date-time-format-settings.md` recorded about under-scoping a file list built by grep.

Reversibility: nothing here is hard to undo before it ships (additive DynamoDB attribute, no
migration). Once shipped, `deletePerson`/`deleteRoom` are genuinely irreversible for the caller in
the normal sense a delete always is — mitigated by `deleteRoom`'s upcoming-meetings block and
`deletePerson`'s reserved-account/self-delete guards, not by any soft-delete/undo mechanism (none
proposed here).

## Implementation checklist

Legend: **[Geoff]** = manual/review step. **[Claude]** = implementation step. Ordered by
dependency.

Logistics: one `feature/admin-rooms-and-people` branch per repo touched (`mootmaker-api`,
`mootmaker-webapp`, `mootmaker-demo-data` if step 12 needs it), cut fresh from `main`. Given
approval to run unattended: fix bugs found along the way and keep going on anything reversible
rather than stopping, recording each such call in this doc rather than pausing for it. One
ephemeral environment, created once and reused throughout, left running at the end for review.

**API (`mootmaker-api`):**
1. [Claude] **Blast-radius sweep first, before any new logic** — per Risks, this is the step most
   likely to be under-scoped if skipped. Confirm the full list of `PersonInput`/`updatePerson`
   consumers found during design (nine `/verify` IT classes, `DemoData.java`,
   `authorization-boundaries.spec.ts`) is still accurate against current `main`, and note anything
   new.
2. [Claude] Schema: `api/mootmaker.graphql` changes from Trade-offs and decisions / Impacts on
   components — remove `updatePerson`/`UpdatePersonResult`/`PersonInput`; add `updateMyName`,
   `renamePerson`, `setPersonAdmin` (with `cognitoSyncFailed`), `deleteRoom`, `deletePerson`, and
   their result types; add `Person.isAdmin`; `createPerson(name: String!)`; new `RoomError`/
   `PersonError` cases.
3. [Claude] `Person.java` — add `isAdmin`, defaulting like `dateFormat`/`timeFormat` (absent
   attribute → `false`); `toItem()`/`fromItem()` updated; unit test the default path.
4. [Claude] Extract `DeleteMyAccountHandler`'s cascade (cancel-upcoming-organised,
   remove-from-upcoming-attended) into something both it and the new `DeletePersonHandler` call,
   rather than duplicating it.
5. [Claude] New handlers — `UpdateMyNameHandler`, `RenamePersonHandler`, `SetPersonAdminHandler`,
   `DeleteRoomHandler`, `DeletePersonHandler` — each per its own Trade-offs and decisions entry:
   read-then-full-replace carrying every untouched field forward (closing #71's bug, not repeating
   it), DynamoDB-then-Cognito write order, the guard errors (`CannotDeleteSelf`, `ReservedAccount`,
   `NoLinkedAccount`, `CannotRevokeOwnAdminAccess`), `cognitoSyncFailed` on `SetPersonAdminHandler`
   only. Retire `UpdatePersonHandler`; rewrite `CreatePersonHandler` for the new signature. Depends
   on: 2, 3, 4.
6. [Claude] Terraform: five new resolvers in `deploy/terraform/appsync.tf`, matching the existing
   `create_room`/`update_room`/`create_person`/`update_person` blocks' shape. Depends on: 5.
7. [Claude] Unit tests for every new/changed handler — the #71-regression case (untouched fields
   survive), the guard-error cases, and `SetPersonAdminHandler`'s `cognitoSyncFailed` case (mocked
   Cognito client throws) per Testing impacts. Depends on: 5.
8. [Claude] Update the nine existing `/verify` IT classes and add new `*AcceptanceIT` classes per
   new mutation (admin succeeds, non-admin rejected, M2M admin-scope token succeeds), mirroring
   `CreateRoomAcceptanceIT`'s shape. Depends on: 1, 6.
9. [Claude] `mvn -f impl/pom.xml test` green; deploy to the ephemeral environment; `/verify` green
   against it. Depends on: 7, 8.

**Tooling consumers (still `mootmaker-api`'s change, different repo):**
10. [Claude] `mootmaker-demo-data`'s `DemoData.java` `createPerson` call, updated for the new
    signature. Depends on: 9.
11. [Claude] `mootmaker-webapp/acceptance/tests/authorization-boundaries.spec.ts`'s direct
    `updatePerson` mutation, re-targeted at `renamePerson`/`updateMyName`, assertions re-checked
    against whichever new handler now owns that rejection. Depends on: 9.

**Webapp (`mootmaker-webapp`):**
12. [Claude] `webapp/src/graphql/types.ts`'s hand-maintained schema mirror, updated to match step 2.
    Depends on: 9.
13. [Claude] `MenuContent.tsx` — new Admin section (Rooms, Persons) between the existing items and
    Settings. Depends on: 12.
14. [Claude] `SettingsPage.tsx` — remove `AdminSections()` entirely; cut to Your name, Date & time
    format, Delete account, plus the "moved" banner. Depends on: 12.
15. [Claude] New `RoomsPage.tsx` — card grid (matching `RoomAvailabilityPage`'s card pattern),
    Add/Edit dialog with the colour-swatch picker, delete confirmation (including the
    `RoomHasUpcomingMeetings`-rejected case's own messaging). Depends on: 12.
16. [Claude] New `PersonsPage.tsx` — card grid with admin badge and linked-email chips, Add/Edit
    dialog with the admin switch (Edit only), its two disabled states (no linked account; editing
    self) and their inline copy, delete confirmation, and the `cognitoSyncFailed` retry/cancel
    dialog. Depends on: 12.
17. [Claude] Mobile layouts for both new pages (app bar + drawer, FAB), per the prototype. Depends
    on: 15, 16.
18. [Claude] Deploy webapp to the same ephemeral environment as step 9. Depends on: 13-17.

**Testing (`mootmaker-webapp`):**
19. [Claude] Integration coverage (`webapp/tests/`) for both new pages' client-side logic, including
    the `cognitoSyncFailed` retry/cancel behaviour against a mocked response, per Testing impacts.
    Depends on: 15, 16.
20. [Claude] New acceptance sections **P** (`p-rooms.md` + spec) and **Q** (`q-persons.md` + spec),
    case numbers from 122, superseding **J**/**K**'s Settings-scoped cases. Depends on: 18.
21. [Claude] Update **L.89** and **L.91** for the new pages/nav and the new mutation names. Depends
    on: 11, 18.
22. [Claude] Full acceptance suite green on the deployed environment (this project's usual done
    condition). Depends on: 19, 20, 21.

**Review:**
23. [Geoff] Sign off on the deployed behaviour before this moves to Shipped.

## Definition of done

- New/changed acceptance-test coverage (sections **P**, **Q**, and the updated **L** cases) is
  green.
- The full existing acceptance suite is still green on a real deployed environment, including every
  updated `*AcceptanceIT`/`DemoData.java`/`authorization-boundaries.spec.ts` call site.
- An admin can create, edit, and delete a Room and a Person, and grant/revoke admin status, all from
  the new pages; a standard user can reach none of it.
- `deleteRoom` correctly refuses when the room has an upcoming meeting; `deletePerson` correctly
  cascades and correctly refuses for self/reserved accounts.
- A past meeting whose Room or organiser has since been deleted still renders (placeholder name).
- Documentation impacts above are actually done, not just planned.
