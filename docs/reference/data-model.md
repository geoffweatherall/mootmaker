# Domain data model — current state

**Living reference, not a design doc.** This describes what's actually deployed today, across both
Cognito (identity/auth) and DynamoDB (application data) — the two together, since most features
that touch persisted state touch more than "the obvious database." Individual design docs describe
*deltas* against this file under their own "Changes to the domain data model" section and link
back here rather than duplicating it; this file gets updated once a design ships (see
[README.md](../../designs/README.md)'s process). Last verified 2026-08-28, against `mootmaker-api`.

## Cognito

**User pool** (`aws_cognito_user_pool.this`, `${resource_prefix}-users`,
`mootmaker-api/deploy/terraform/cognito.tf`):

- `username_attributes = ["email"]` — users sign in by email; Cognito auto-generates a UUID
  username identical to the user's `sub`, with email as an alias.
- `auto_verified_attributes = ["email"]`; email delivered via SES (`DEVELOPER` sending account,
  `mail.mootmaker.com`), not Cognito's built-in sender.
- Password policy: minimum length 10, lowercase + numbers required; no uppercase/symbol
  requirement. Account recovery via `verified_email`.

**Attributes**:

| Attribute | Kind | Mutable by | Set by | Purpose |
|---|---|---|---|---|
| `email` | standard | self (sign-up), or Terraform (seeded accounts) | sign-up form, or Terraform directly | Username alias, contact address. |
| `email_verified` | standard | — | Cognito verification flow, or Terraform (seeded accounts) | Gates sign-in. |
| `name` | standard | self (webapp client's `write_attributes`) | sign-up form; kept in sync one-way from `Person.name` afterward (see Cross-references) | Cognito's own copy of display name — DynamoDB's `Person.name` is the real source of truth. |
| `sub` | standard | — (Cognito-generated) | Cognito | The identity linking key into DynamoDB — see Cross-references. |
| `custom:class` | custom, String, 1-20 chars | **server-side only** — excluded from the webapp client's `write_attributes` | `PostConfirmationCreatePersonHandler` (`"standard"`, every new sign-up); Terraform directly for the two seeded accounts | `"standard"` or `"admin"`; surfaced in the ID token's `custom:class` claim; drives `Identity.isAdmin`/`Identity.requireAdmin`. |

**User pool clients**:

- **`webapp`** (`${resource_prefix}-webapp`) — public, no secret, for the browser SPA.
  `ALLOW_USER_SRP_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH`. `prevent_user_existence_errors = "ENABLED"`.
  `read_attributes = [email, email_verified, name, custom:class]`; `write_attributes = [name]` —
  `custom:class` is deliberately absent from both accidentally-writable and read-only-by-omission
  concerns since it's read via the JWT claim, not a direct attribute read.
- **`acceptance_tests`** (`${resource_prefix}-acceptance-tests`) — confidential (has a secret),
  OAuth2 `client_credentials` flow only, scoped to two custom resource-server scopes (`execute`,
  `admin` — via `aws_cognito_resource_server.api`). No Cognito user or JWT `sub` involved at all;
  used by `mootmaker-api/verify`'s own acceptance tests and other machine-to-machine tooling
  (`mootmaker-demo-data`). `Identity.hasAdminScope` checks the `admin` scope the same way
  `Identity.isAdmin` checks `custom:class`.
- A hosted domain (`aws_cognito_user_pool_domain.this`) exists only to expose the OAuth2 token
  endpoint the client_credentials flow needs.

**Lambda trigger**: `post_confirmation` → `PostConfirmationCreatePersonHandler`. Fires on
`PostConfirmation_ConfirmSignUp` only (**not** for federated/external-provider sign-in — relevant
if a federated identity provider is ever added, since nothing else creates the linked `Person` for
that path today). On each confirmed sign-up it: (a) creates a `Person` DynamoDB item carrying the new user's `sub`
in `cognitoSubs`, idempotently, (b) writes that Person's id back onto the user as the
`custom:personId` claim, and (c) sets `custom:class = "standard"` — both via
`AdminUpdateUserAttributes`. The `custom:personId` step is what lets every later request resolve
the caller by primary key instead of through an index. Both steps swallow and log their own
failures rather than failing the sign-up itself.

**Seeded accounts** (both created directly by Terraform via `aws_cognito_user`, bypassing sign-up
and therefore bypassing the `post_confirmation` trigger entirely):

- **e2e user** (`e2e-tests@example.com`) — random password, `email_verified=true`,
  `custom:class="standard"` set explicitly in Terraform "for parity with a real signed-up user"
  since the trigger never runs for it. **Has no linked `Person` from Cognito's side** — this is
  deliberate (several acceptance-suite cases specifically need a no-linked-Person account) and gets
  backfilled only by `database-repair`'s "create missing Person" repair if invoked.
- **Demo user** (`demo@mootmaker.com`) — random password, `email_verified=true`,
  `custom:class="admin"` (the app's one always-present admin). **Not gated by environment** — exists
  even in `production`. Unlike the e2e user, its `Person` record **is** created directly by
  Terraform (`aws_dynamodb_table_item.demo_person`, same item shape as `Person.toItem()`, linked
  via `cognitoSub = aws_cognito_user.demo.sub`).
- Both are protected from self-service deletion: `DeleteMyAccountHandler` refuses if the caller's
  email is in a Terraform-populated `RESERVED_ACCOUNT_EMAILS` env var.

## DynamoDB

All tables: `PAY_PER_REQUEST` billing, named `${resource_prefix}-<table>`.

### Rooms — `${resource_prefix}-rooms`

Primary key: `id` (S), no sort key. Primary source of truth.

| Attribute | Type | Purpose |
|---|---|---|
| `id` | S | Primary key. |
| `name` | S | Room name. |
| `capacity` | N | Room capacity. |

No GSIs/LSIs. Referenced by `MeetingRecord.roomId`.

### People — `${resource_prefix}-people`

Primary key: `id` (S), no sort key. Primary source of truth.

| Attribute | Type | Purpose |
|---|---|---|
| `id` | S | Primary key. |
| `name` | S | Display name — the real source of truth (Cognito's `name` attribute is a one-way synced copy). |
| `cognitoSubs` | List\<S\> | Every Cognito account linked to this person — **empty** for guest Persons created directly by an admin (no Cognito account at all); never exposed over GraphQL. |
| `dateFormat`, `timeFormat` | S, optional | The caller's own display preferences, set by `updateMyPreferences`. Presentational only. |

**No GSIs.** There was a `cognitoSub-index` (hash `cognitoSub`, projection `ALL`), used to resolve
the signed-in caller's Person from their JWT `sub`. It is gone: the caller's person id now travels
**forward** on the token as the `custom:personId` claim, so that lookup is a primary-key read. The
`cognitoSubs` list is the **reverse** direction, for the cases that genuinely need it — the
`post_confirmation` trigger checking whether a Person already exists, and `database-repair`'s
`CreateMissingPersonsRepair`.

Relates to Cognito via `cognitoSubs`; relates to Meetings via `MeetingRecord.organiserId`/
`attendeeIds` inside the day item.

### Meetings — `${resource_prefix}-meetings`

Primary key: `pk` (S), no sort key. **One item per calendar day**, not one per meeting. Every
meeting is constrained to span a single calendar day (application-enforced,
`MeetingError.SpansMultipleDays`), which is what makes "a day" a well-defined unit to store at all.

Three kinds of item share this table, distinguished by `pk` prefix:

| `pk` | Item |
|---|---|
| `DAY#2026-09-14` | Every meeting on that date, plus a `version` |
| `PTR#<meetingId>` | Pointer from a meeting id to the date holding it |
| `CONFIG#retention` | The single stored retention boundary |

**Day item** — persisted shape is `Day`, holding a list of `MeetingRecord` (distinct from `Meeting`,
the resolved GraphQL response shape, which is not persisted — room, organiser and attendees are
resolved from their own tables at read time).

| Attribute | Type | Purpose |
|---|---|---|
| `pk` | S | `DAY#` + the ISO date. |
| `version` | N | Optimistic lock. Adding one meeting rewrites the whole item, so concurrent writers must not clobber each other. A day never written has version 0 and no item, so the conditional write for a first write is "must not exist" rather than "version must equal 0" — two racing first-writes would both pass an equality check against zero. |
| `meetings` | List | Each with `id`, `roomId`, `organiserId`, `attendeeIds`, `subject`, `startTime`, `endTime`. Times are canonical fixed-width `yyyy-MM-dd'T'HH:mm:ss` with no zone offset — see [date-time-format-settings.md](../../designs/archive/date-time-format-settings.md) for why the webapp treats these as naive local time, never UTC. |

**Pointer item** — `pk` is `PTR#` + the meeting id; its payload is the date. It exists solely so
`Query.meeting(id:)` can resolve without an index: read the pointer, then read that day. Pointers
are written in the same `TransactWriteItems` as the day they describe, and deleted with it.

**No GSIs.** There were two — `bucket-startTime-index` (hash on a constant `"ALL"`, range
`startTime`) and `roomId-startTime-index` — plus a `bucket` attribute that existed purely to give
the first one a hash key. All three are gone. A day is reachable by primary key, and a primary-key
read can be a `ConsistentRead`, which removes read-after-write staleness as a class rather than
working around it.

**The MeetingParticipants table is gone too.** `${resource_prefix}-meeting-participants` held one
row per (meeting, participant) pair, because `attendeeIds` is a list and DynamoDB keys must be
scalars, so "which meetings is this person in" could not be answered from the meetings table
itself. That question is now answered by reading the days in the window and filtering in memory —
the day is being fetched anyway. Its rebuild repair, `RebuildMeetingParticipantsRepair`, went with
it. **Nothing in this model is stored twice any more.**

## Cross-references between Cognito and DynamoDB

- **The link is one attribute**: `Person.cognitoSub` = the Cognito user's `sub`. Populated at
  Person-creation time — by `PostConfirmationCreatePersonHandler` (reads `sub` from the trigger
  event) for a real sign-up, or directly by Terraform for the seeded accounts. Guest Persons
  (created via the admin-only `createPerson` mutation) have an empty `cognitoSubs` — no Cognito
  account at all.
- **Read side**: the link is followed **forward**, off the token. `custom:personId` names the
  caller's Person, so `workspace { me }` is a primary-key read; `UpdatePersonHandler` compares that
  claim to authorize a self-rename (unless the caller is admin), and `DeleteMyAccountHandler` uses
  it too, plus calls Cognito's `AdminDeleteUser` directly using `sub`. The old direction — JWT
  `sub` → `cognitoSub-index` GSI → Person — is gone along with the index and
  `MyPersonHandler` itself.
- **An account with no linked Person is a real state**, not a defect: `custom:personId` is absent,
  `workspace { me }` returns null, and the webapp degrades deliberately (Calendar disabled rather
  than hidden, the agenda replaced by an explanation). Every non-production environment carries
  `no-person-tests@example.com` to keep that path covered.
- **`Person.name` → Cognito `name` is a one-way sync**, not a shared field: Cognito sets it once at
  sign-up; only `UpdatePersonHandler` updates it thereafter (to mirror a Person rename), via
  `AdminUpdateUserAttributes` using `cognitoSub` as the username (this works because
  username == `sub` in this pool). Best-effort — a failure there doesn't fail the rename mutation
  itself, since `Person.name` (DynamoDB) is the actual source of truth.
- **Stray `Person` records with a dangling `cognitoSub`** (the Cognito user was deleted or recreated
  independently) are closed going forward, in every environment except `production`: `database-reset`
  determines which People survive from Cognito's *actual current* user list (`ListUsers`, matched
  against the two Terraform-managed reserved accounts), not from whether a `Person`'s `cognitoSub`
  attribute happens to be present — so a Person whose Cognito account is gone no longer survives just
  because the attribute wasn't cleared. In `production`, where the Cognito wipe is refused outright,
  the original narrower rule still applies (any non-null `cognitoSub` survives), so a stray Person
  there is unaffected by reset and still has to be deleted directly via DynamoDB. `database-repair`
  has no repair for this case either way — see
  [mootmaker-api's README](https://github.com/geoffweatherall/mootmaker-api#reset-and-real-user-accounts)
  and [designs/admin-tools-into-api.md](../../designs/archive/admin-tools-into-api.md) (archived once shipped).
