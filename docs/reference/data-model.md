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
  (`sample-data-generator`). `Identity.hasAdminScope` checks the `admin` scope the same way
  `Identity.isAdmin` checks `custom:class`.
- A hosted domain (`aws_cognito_user_pool_domain.this`) exists only to expose the OAuth2 token
  endpoint the client_credentials flow needs.

**Lambda trigger**: `post_confirmation` → `PostConfirmationCreatePersonHandler`. Fires on
`PostConfirmation_ConfirmSignUp` only (**not** for federated/external-provider sign-in — relevant
if a federated identity provider is ever added, since nothing else creates the linked `Person` for
that path today). On each confirmed sign-up it: (a) creates a `Person` DynamoDB item linked via
`cognitoSub`, idempotently (checks the `cognitoSub-index` GSI first), and (b) sets
`custom:class = "standard"` via `AdminUpdateUserAttributes`. Both steps swallow and log their own
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
| `cognitoSub` | S, optional | Backend-only linking attribute to a Cognito user's `sub`; **absent** for guest Persons created directly by an admin (no Cognito account at all); never exposed over GraphQL. |

**GSI `cognitoSub-index`**: hash key `cognitoSub`, projection `ALL`. Used to (a) let the
`post_confirmation` trigger check for an existing Person before creating one, (b) resolve
`Query.myPerson` for the signed-in caller, (c) resolve `deleteMyAccount`'s own-Person lookup.

Relates to Cognito via `cognitoSub`; relates to Meetings via `MeetingRecord.organiserId`/
`attendeeIds`; relates to MeetingParticipants via `personId`.

### Meetings — `${resource_prefix}-meetings`

Primary key: `id` (S), no sort key. Primary source of truth for meeting data. Every meeting is
constrained to span a single calendar day (application-enforced, `MeetingError.SpansMultipleDays`),
which is what makes the GSI range queries below exact.

Persisted shape is `MeetingRecord` (distinct from `Meeting`, the resolved GraphQL response shape,
which is not itself persisted — attendees/room/organiser are resolved from their own tables at read
time).

| Attribute | Type | Purpose |
|---|---|---|
| `id` | S | Primary key. |
| `bucket` | S | Constant `"ALL"` — exists purely to give the `bucket-startTime-index` GSI a hash key. |
| `roomId` | S | FK → Rooms. |
| `organiserId` | S | FK → People. |
| `attendeeIds` | List\<S\> | FKs → People. |
| `subject` | S | Meeting subject/title. |
| `startTime` | S | Canonical fixed-width `yyyy-MM-dd'T'HH:mm:ss`, no time-zone offset — see [date-time-format-settings.md](../../designs/archive/date-time-format-settings.md)'s Technical considerations for why the webapp treats this as naive local time, never UTC. |
| `endTime` | S | Same format as `startTime`. |

**GSIs**:
- `bucket-startTime-index` — hash `bucket`, range `startTime`, projection `ALL`. Supports
  `Query.meetings`' date-range filter when no `personId` is given.
- `roomId-startTime-index` — hash `roomId`, range `startTime`, projection `ALL`. Supports the
  same-room overlap check at meeting creation, via `begins_with(startTime, datePrefix)`.

### MeetingParticipants — `${resource_prefix}-meeting-participants`

Primary key: `personId` (S, hash) + `sortKey` (S, range). **Fully derived/materialized** — Meetings
is the sole source of truth; this table exists purely as a query-optimized index.

| Attribute | Type | Purpose |
|---|---|---|
| `personId` | S | Hash key, FK → People. |
| `sortKey` | S | Range key, computed as `startTime + "#" + meetingId` — lexicographically sortable since `startTime` is fixed-width. Answers "this person's meetings starting in [from, to)" via the composite key alone, no GSI needed. |
| `meetingId` | S | FK → Meetings. |
| `startTime` | S | Copied from the meeting. |
| `endTime` | S | Copied from the meeting. |

One row per (meeting, organiser-or-attendee) pair. Written in the same `TransactWriteItems` call as
the meeting itself at creation, and kept consistent on deletion/attendee-removal
(`DeleteMyAccountHandler`) — **consistency is maintained purely by application code** (transactional
writes at write/delete time), not a DB-level constraint or event-driven trigger.
`mootmaker-admin-tools/database-repair`'s `RebuildMeetingParticipantsRepair` can fully regenerate this
table from Meetings on demand — used for backfilling pre-existing meetings when the table was
introduced, and as a drift safety net; it's invoked manually (`run.sh`), not event-driven.

## Cross-references between Cognito and DynamoDB

- **The link is one attribute**: `Person.cognitoSub` = the Cognito user's `sub`. Populated at
  Person-creation time — by `PostConfirmationCreatePersonHandler` (reads `sub` from the trigger
  event) for a real sign-up, or directly by Terraform for the demo user. Guest Persons (created via
  the admin-only `createPerson` mutation) have `cognitoSub = null` — no Cognito account at all.
- **Read side**: `MyPersonHandler` resolves `Query.myPerson` by looking up the caller's JWT `sub`
  against the `cognitoSub-index` GSI. `UpdatePersonHandler` does the same to authorize a
  self-rename (caller's `sub` must match the target Person's `cognitoSub`, unless the caller is
  admin). `DeleteMyAccountHandler` uses the same lookup, plus calls Cognito's `AdminDeleteUser`
  directly using `sub`.
- **`Person.name` → Cognito `name` is a one-way sync**, not a shared field: Cognito sets it once at
  sign-up; only `UpdatePersonHandler` updates it thereafter (to mirror a Person rename), via
  `AdminUpdateUserAttributes` using `cognitoSub` as the username (this works because
  username == `sub` in this pool). Best-effort — a failure there doesn't fail the rename mutation
  itself, since `Person.name` (DynamoDB) is the actual source of truth.
- **Known gap**: a stray `Person` record with a dangling `cognitoSub` (the Cognito user was deleted
  or recreated independently) is not detected or cleaned by either `database-repair` or
  `database-reset` today.
