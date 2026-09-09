# GraphQL schema and caching

## Summary

The API's entry points are shaped like REST endpoints: three unrelated top-level list fields that a
client must call separately, with the client supplying its own identity as a filter argument. This
design reshapes them around a single unit — **the day** — so that one key identifies a DynamoDB
item, an AppSync fetch, an Apollo cache entity, and a subscription filter. It also makes resolvers
selection-aware so a query that asks for less does less work, and adds real-time updates so one
user's booking appears on another's screen without a refetch.

## Status

**Ready** — 2026-09-09, promoted by Geoff. Every blocking open question is closed. The items
under "Still to verify" are non-blocking: they are AppSync behaviours to be answered empirically
during slice 5, not decisions still to be made.

## Decisions

Every one is settled. Where a decision constrains implementation the reason is given; where it was
merely argued at length, it is not.

| # | Decision | Why it matters when building |
|---|---|---|
| 1 | **One DynamoDB item per day.** Meetings for a date live in one item, read by primary key | Buys `ConsistentRead`, removing the read-after-write bug class outright. Costs write amplification and read-modify-write contention |
| 2 | **One composite entry point**, `workspace(dates:)` | One request, one Lambda invocation, one SnapStart restore per page load. Written out in full in [`graphql-schema-and-caching-proposal/`](graphql-schema-and-caching-proposal/) |
| 3 | **Selection-aware resolvers** | `attendees { id }` does no Person lookup; `{ id name }` does exactly one. Requires a request-template change *first* |
| 4 | **The server derives "mine" from the JWT**, via a `custom:personId` Cognito claim | Removes the startup waterfall. Zero lookups to know the id; one `ConsistentRead` for the mutable fields |
| 5 | **Day-scoped bulk creation**, `createMeetings(date:, meetings:)` | One item write, one broadcast, one filterable field. Sidesteps `TransactWriteItems`' 100-item cap. Chosen over `setSubscriptionFilter` with a `contains` operator over a `dates` array, which filters *who is woken*, not how much they receive |
| 6 | **Real-time updates via AppSync subscriptions** | Tens of milliseconds. Alternatives cost ~$70/month or a connection registry |
| 7 | **Apollo cache built on day entities**, `Day` keyed by `date` | An empty day and an unfetched day become distinguishable |
| 8 | **No cache persistence across refresh** | A refresh is a guaranteed stateless restart the user can always reach for |
| 9 | **Both meetings GSIs, `meeting-participants`, and `cognitoSub-index` are deleted** | Every user-facing query carries a date range. Nothing is stored twice anywhere after this |
| 10 | **`meeting(id:)` gains a real entry point**, backed by an id → date pointer | Replaces today's full-table scan |
| 11 | **Retention of 30–37 days**, against a stored Monday-aligned boundary, deleted weekly, **no TTL** | The job can broadcast, and delete each day with its pointers in one transaction |
| 12 | **A 180-day booking horizon** | With retention, bounds the table at **217 day items** — a hard cap on row count, not a growth rate |
| 13 | **Enforced size limits**, three layers | No input a user can construct produces an item over 400 KB |
| 14 | **Enforced transport limits** | AppSync's unadjustable 5 MB response and 240 KB subscription caps |
| 15 | **`publishDaysInvalidated` is `@aws_iam`-only** | AppSync refuses the call before a resolver runs — a stronger boundary than any other field has |
| 16 | **Destroy and rebuild both environments.** No migration, Cognito pools included | Removes the largest risk and the longest phase from the rollout |
| 17 | **Reset stays an IAM-invoked Lambda** | `Mutation.reset` was deliberately removed once because any signed-in user could call it |
| 18 | **Repository classes own the write invariants** | Not a portability abstraction — see "Repositories" |

**Two facts about the account that bear on this.** The Lambda concurrency limit was raised from 10 to
**1,000** on 2026-09-07 (#72), which *weakens* rather than strengthens the case for collapsing the root
fields — three parallel invocations no longer approach saturation, so the composite shape is justified
by total compute and SnapStart restores, not by a ceiling. It is a smaller prize than it looked while
the limit was 10. And **#76's RBAC work is not a prerequisite** for this design: reset stays an
IAM-invoked Lambda, so nothing here waits on splitting the flat admin role.

**No decision is carried forward for compatibility's sake.** The finished code and schema should look
as though they were designed this way on day one. This deletes rather than adapts: `MeetingRecord`,
`MeetingParticipant`, the constant `bucket = "ALL"` attribute, both meetings GSIs, `cognitoSub-index`,
`BatchLoader`, the router-state handoff between `AddMeetingPage` and `RoomAvailabilityPage`, and the
resolver payload shape today's handlers read.

## What the client needs, and when

The evidence the entry-point shape was chosen against, and still the checklist of every data need.

| Page or trigger | Data needed |
|---|---|
| Any load or refresh, signed in | The caller's own Person |
| Home (signed in) | My meetings, today → +2 days |
| Home (signed out), About | None — demo credentials come from runtime config |
| Person calendar | All people, all rooms, one person's meetings across a 40-day span (30 weekdays displayed) |
| Room availability | All rooms, all meetings for one date |
| Add meeting | All rooms, all people |
| Meeting details | **One meeting, by id** |
| Settings | The caller's Person; admin sections also need all rooms and all people |
| User actions | `suggestRoom`, `createMeeting`, `updatePerson`, `updateMyPreferences`, `createRoom`/`updateRoom`, `createPerson`, `deleteMyAccount` |
| Caused by someone else | Another user's booking, the 18:00 NZT demo-data run, a database reset |

Three observations fall out. **Rooms and people are wanted by four of seven pages and change rarely** —
fetch once, and Add Meeting becomes a zero-query page. **Meetings are always wanted as a date range**,
and the ranges differ per page (3 days, 1 day, 40 days), which is what day-keyed entities make
composable. And **meeting details is the one lookup that is not a date range at all** — today served by
`ListMeetings` with no filter, fetching every meeting ever stored and filtering client-side.

Everything in the last row currently produces **nothing**: the client stays stale until something
refetches. That is what the subscription strand exists to fix, for the first of the three.

## Scope / non-goals

**In scope:** `Query`'s entry points; selection-aware fetching in the resolver Lambda; day-keyed
storage; the Apollo `InMemoryCache` policy; bulk meeting creation; subscriptions; retention.

**Not in scope:**

- `mootmaker-android` — it does not exist yet and should not constrain this.
- Any change to the privacy model. Every signed-in user can see every meeting, and this design
  assumes that stays true (see Risks — subscriptions make it load-bearing).
- Meeting update and delete. Neither exists today; adding them is a separate design.
- Reference-data invalidation (a new Room or Person appearing on an open page). Deferred
  deliberately; `Invalidation` is shaped so it can be added without a breaking change.
- Pagination beyond day ranges.
- Notifications of any kind. Row 6 of the cross-client table depends on this staying true.

## Storage: the DynamoDB schema

Three tables. After this change **nothing is stored more than once** anywhere — the only secondary
structure is a key, not a copy.

```
mootmaker-<env>-meetings          PK: pk (S).  No sort key. No GSIs.

  DAY#2026-09-14
    pk       S  "DAY#2026-09-14"
    date     S  "2026-09-14"
    version  N  7                      ← conditional write / optimistic lock
    meetings L  [ M{ id, subject, roomId, organiserId,
                     attendeeIds L<S>, startTime, endTime } ]

  PTR#<meetingId>                      ← backs meeting(id:)
    pk       S  "PTR#0f3c…"
    date     S  "2026-09-14"

  CONFIG#retention
    earliestRetainedDate  S  "2026-08-10"   (Monday-aligned, stored, advanced by the job)
    bookingHorizonDays    N  180            (a length, not a date)
```

```
mootmaker-<env>-people            PK: id (S).  cognitoSub-index DELETED.

  { id, name, dateFormat, timeFormat, cognitoSubs L<S> }
```

```
mootmaker-<env>-rooms             PK: id (S).  Unchanged.
```

**Retention is stored; the horizon is computed.** Storing a horizon *date* would need its own daily
job to advance it. Store the **length** and compute `latestBookableDate = serverToday + 180` per
request. One authority — the server — with no second schedule.

**`cognitoSubs` is a list, not an index.** `deleteMyAccount` already holds the Person item when it
needs to delete the linked Cognito users, so the reverse lookup costs nothing. Being a list is what
makes "user(s)" expressible if a second sign-in method is ever added.

**Storing ids as binary** (16 bytes) rather than 36-char strings would raise the per-day ceiling from
~1,000 to ~1,545 meetings; UUIDs are 63% of the payload. Not proposed — recorded as available
headroom.

## Identity: `personId` as a Cognito claim

`PostConfirmationCreatePersonHandler` sets `custom:personId` alongside the `custom:class` it already
sets. `me` then costs **zero lookups to know the id** and one `ConsistentRead` `GetItem` for the
mutable fields. No GSI on the hot path.

Seven consequences, all of which are build steps:

1. **`read_attributes` gains `custom:personId`; `write_attributes` must exclude it.** The list is not
   additive over Cognito's default, so it restates `email`/`name` too. The exclusion is a security
   control, not a formality: self-writing `custom:class` promotes you to admin, but self-writing
   `personId` makes you *become another user* — their preferences, their rename, bookings as them,
   and `deleteMyAccount` on their account.
2. **Terraform sets the claim on directly-created users.** `aws_cognito_user.demo` and
   `aws_cognito_user.e2e` skip PostConfirmation. Terraform already generates
   `random_uuid.demo_person_id` and writes the demo Person item, so it can set the attribute in the
   same place. **The e2e user gains a Person and a claim too** — it has neither today, and it is the
   identity the whole acceptance suite runs as.
3. **`CreateMissingPersonsRepair` must also set the claim**, or it repairs into a state that still
   does not resolve.
4. **A missing claim resolves to `me: null`** — matching today's `myPerson` behaviour. The state is
   reachable because `PostConfirmationCreatePersonHandler` deliberately swallows its own failures.
5. **`cognitoSub-index` is deleted.** The claim serves sub → person; `cognitoSubs` serves the
   reverse. That removes the last `projection_type = "ALL"` duplicate.
6. **M2M tokens carry no claim,** so `me` is null for `mootmaker-demo-data` and the acceptance suite.
   `client_credentials` produces an access token with no user behind it — `Identity.java` already
   documents this and works around it with an OAuth scope. **No mutation may derive the organiser
   from the caller;** `MeetingInput.organiserId` stays explicit.
7. **Custom attributes can never be removed or renamed once added to a pool.** The pool is being
   destroyed and rebuilt anyway, so this is the cheapest moment the decision will ever be available.

## The API: one composite entry point

The full schema and every operation the webapp sends are in
[`graphql-schema-and-caching-proposal/`](graphql-schema-and-caching-proposal/), which also records
what the shape cost. Two consequences to carry into the build:

**Query-level errors are GraphQL errors, not typed results.** `workspace` returns `Workspace!` with
no error channel, so "too many dates" and "response too large" carry a typed `extensions.code`. A
non-null field erroring nulls the whole `Workspace`, so an overflow loses `rooms` and `people` too.
Accepted: the client constructs the request, `maxDates` is a bound it never trips, and
`maxMeetingsPerResponse` should be unreachable against production's 508 meetings in total.

**One timeout for the whole response.** The resolver Lambda moves from 15 s to **25 s** — under
AppSync's unadjustable 30 s so the Lambda fails first with a diagnosable error rather than being
orphaned, but with room for a full-month fetch. `database-reset` and `database-repair` keep 900 s;
the cleanup Lambda gets 300 s.

## Selection-aware resolving

**The template change is a prerequisite.** `info.selectionSetList` is *not* in the resolver payload
today — verified empirically by decoding `$util.toJson($ctx)`, the exact expression in `appsync.tf`'s
shared `direct_lambda_request_template`, from a live response, which gives only
`{"fieldName","parentTypeName","variables"}`. AWS documents that `selectionSetGraphQL` and
`selectionSetList` "are not serialized by default"; they appear only when referenced explicitly.
Nothing selection-aware works until the template changes.

**One selection-aware resolver, not per-field resolvers.** Attaching resolvers to `Person.name` and
`Person.dateFormat` would fire them independently — two invocations and two round trips for two
fields on the same item. One resolver reading nested paths from `selectionSetList` gives one
invocation and one (or zero) `BatchGetItem`, and preserves request-scoped deduplication. A resolver
on `Meeting.attendees` with `max_batch_size` remains the fallback if the projection logic becomes
unwieldy; it costs one extra invocation per batched field and needs `ResolverDispatchHandler` to
handle a `List` event rather than a `Map`.

**Selection tests must fail toward fetching.** Aliased fields appear under the alias *only* —
verified: querying `aliasedName: name` yields `…/aliasedName` and no entry for `name`. A resolver
enumerating known field names would conclude the client did not want the name and return a stub;
because `name: String!` is non-null, GraphQL then nulls the attendee, then the list, then potentially
the meeting. **Non-null propagation turns a stub/selection mismatch into silent data loss, not a
degraded response.** So treat any selection beyond the known-free fields as "fetch".

## Repositories

`DayRepository`, `PersonRepository`, `RoomRepository` — **instances constructed once at init**, held
as handler fields, inside the SnapStart snapshot alongside `DynamoDbClientProvider.client()`.
Standing rule: **nothing in the snapshot may hold state that must differ per restore** — no cached
clock, no seeded random, no per-invocation counters as fields.

This is **not** a portability abstraction; a datastore swap is not anticipated and would not justify
it. It is an *invariant-ownership* abstraction. Five places write a day item — `createMeeting`,
`createMeetings`, `deleteMyAccount`, the cleanup Lambda, and the retention test's seeding — and every
one must do the version-conditional write, the retry-on-conflict, the byte measurement before
`PutItem`, and the pointer in the same transaction. Written inline five times that drifts, and layer
3 of the size guarantee stops being a guarantee and becomes a convention.

`DayRepository` is therefore the **only** code that writes a day item. It owns: `ConsistentRead` day
reads; version-conditional writes with `PTR#` items in the same `TransactWriteItems`; byte
measurement immediately before `PutItem`; retry-on-conflict; transactional day+pointer deletion; a
scan of all days; and the `CONFIG#retention` item.

**`BatchLoader` is absorbed and deleted.** It is a generic "batch-get by id from a named table"
helper, and only people and rooms are ever batch-loaded. Folding it into
`PersonRepository.loadByIds(Set)` and `RoomRepository.loadByIds(Set)` removes the table-name argument
from exactly the call sites where the selection logic is hardest to read.

**Explicitly not:** interfaces with a single implementation, in-memory fakes, or a generic repository
framework.

## Limits, and the two guarantees

Two separate bounds with different consequences: what can be **stored** (400 KB DynamoDB item) and
what can be **moved** (AppSync's quotas). None of the AppSync quotas is adjustable.

| Limit | Value | Bounds |
|---|---|---|
| `maxMeetingsPerDay` | **320** | The day item |
| `maxAttendees` | **20** | Per meeting |
| `maxSubjectBytes` | **280** | NFC-normalised UTF-8 |
| `maxRoomNameBytes` | **100** | Unbounded today |
| `maxPersonNameBytes` | **100** | Unbounded today |
| `maxRooms` | **200** | `rooms`, an unfiltered scan |
| `maxPeople` | **1,000** | `people`, same |
| `maxDates` | **42** | One request |
| `maxMeetingsPerResponse` | **2,000** | The one that makes the response bound unbreakable |
| Request execution time | **30 s** | AppSync, every query and mutation |
| Resolver response size | **5 MB** | AppSync |
| Subscription payload | **240 KB** | AppSync — the tightest limit in the design |

**`maxDates` is 42 because the calendar needs 30.** `WEEKS_SHOWN = 6` × `WORK_DAYS_PER_WEEK = 5` is
30 weekday dates spanning 39 calendar days. 42 covers the whole span with a week to spare, and keeps
working if the UI ever shows weekends — a tighter bound would not.

### The item-size guarantee

**No input a user can construct may produce an item over 400 KB.** The invariant:

```
dayLimit × (perMeetingBase + 37 × attendeeLimit + subjectMaxBytes) + overhead  ≤  safetyFraction × 400 KB

  320       × (212            + 37 × 20            + 280)           + overhead  ≈  394 KB  (96%)
```

Deliberately tight: layer 3 measures the *actual* serialised item, so an error in the byte model
produces a clean "day is full" rejection rather than a DynamoDB failure. Headroom buys nothing layer
3 does not already provide.

**Three layers, because any one alone can be defeated by a later change:**

1. **At deploy.** The handler asserts the invariant during initialisation and refuses to start if the
   limits cannot fit. SnapStart lands this exactly right: publishing a version *executes init*, so an
   inconsistent set of limits fails the **deploy**, not a user's booking. Without this the guarantee
   decays the moment someone raises a limit or adds a field to the persisted shape.
2. **At validation.** Per-request checks on day count, attendee count, subject bytes, and range, each
   returning a `MeetingError`.
3. **At write, in `DayRepository`.** The serialised item is measured immediately before `PutItem`.
   The backstop that holds even if the byte model is wrong — and it will drift, being an estimate of
   DynamoDB's own accounting.

**The day cap can bind before the rooms are full, but only just.** Ten rooms × 36 fifteen-minute
slots is a physical capacity of 360, so 320 refuses a booking with rooms free — at 89% of the
building. Lowering attendees to 16 would make a full 360-meeting day fit at 95% if it ever binds. In
practice `production` holds **508 meetings in total** and demo-data creates ~20 a day.

**The failure must read as such:** `DayIsFull` says the *day*, not the room. A rejection naming the
room is unexplainable when a room stands free.

**No per-organiser limit.** Considered and dropped — the absolute day cap is the only rule that
bounds the item; a per-organiser cap would be a fairness control. One user filling a day is
acceptable on a demo system.

### Subject length: 280 bytes of NFC-normalised UTF-8

- **UTF-8 because DynamoDB itself sizes string attributes in UTF-8 bytes.** Validating in the unit
  the storage bills in makes the limit and the item cost the same quantity rather than two numbers
  that drift.
- **Not `String.length()`.** Java strings are UTF-16, so `length()` counts code *units*: an emoji
  outside the BMP is 2 there and 4 in UTF-8. `subject.getBytes(UTF_8).length` is the only correct
  measure.
- **Normalise to NFC before measuring and storing.** "é" is one code point (2 bytes) or "e" plus a
  combining accent (3 bytes) depending on keyboard and OS. Without normalisation two visually
  identical subjects have different byte counts and one can be rejected — unexplainable to the user.
- **Reject, never truncate.** Cutting at a byte boundary splits characters and produces mojibake. A
  client-side counter must truncate on grapheme boundaries.
- **"How many emoji fit" has no single answer** — a simple emoji is 4 bytes, 👨‍👩‍👧‍👦 is 25, skin-tone
  modifiers add 4 each, so the range is ~70 down to 11. This does not threaten the budget: 280 bytes
  is 280 bytes whatever it holds. The variability lands on the user's character counter, which is the
  right place for it. The counter must count down in the same units it enforces.

Measuring characters instead would mean budgeting 1,120 bytes per meeting on the chance one of them
is emoji — roughly 40% of the day's capacity to buy a promise almost nobody exercises.

### The response bound

```
response  =  maxRooms × roomJson  +  maxPeople × personJson  +  totalMeetings × meetingJson
          ≤  safetyFraction × 5 MB
```

**The static limits alone permit a request that cannot be answered.** `maxDates × maxMeetingsPerDay`
is 42 × 320 = 13,440 meetings, which at 1,931 bytes each is 26 MB. Lowering `maxDates` to make the
product safe would put it around 6, which is useless for a calendar.

So the bound is enforced **dynamically**: the resolver accumulates days in order and fails fast with a
typed error once the running meeting count would exceed **2,000**, before building a response it
cannot send. 2,000 × 1,931 ≈ 3.9 MB, plus 200 rooms (~37 KB) and 1,000 people (~178 KB), against
5 MB. Unreachable in practice, but it turns "the response is probably fine" into a guarantee with a
test behind it.

**JSON is much larger than the stored form.** A worst-case meeting is ~1,232 bytes in DynamoDB and
**~1,931 bytes as JSON** — attribute names repeat per object, and Apollo adds `__typename` to every
selection set. At 20 attendees that is 23 objects per meeting and roughly 480 bytes of `__typename`
alone, a quarter of the payload.

## Retention

`principles.md`'s **"Nothing accumulates without a bound"** requires the bill to be flat under steady
usage. Meeting history is the one place mootmaker breaks it.

**Historic meetings are kept for at least 30 days**, bounded by a **stored** earliest-retained date
rather than one computed from the clock, always aligned to a **Monday**, read with `ConsistentRead`.
Consistency is not incidental: an eventually-consistent read could return a stale, *more permissive*
boundary — exactly the failure the ordering below prevents. Monday alignment makes "is this week
reachable" an exact comparison rather than a straddling judgement, at the cost of retention becoming
a range of **30 to 37 days**, so **the storage bound uses 37 as its worst case**.

**Initialised by Terraform** as a table item, the same way `demo_person` already is, so the boundary
exists the moment the table does. **It needs `lifecycle { ignore_changes = [item] }`**: computing
`Monday(today − 30d)` requires `timestamp()`, which is re-evaluated on every plan, and without the
lifecycle block every `terraform apply` would rewrite the boundary *backwards* — resurrecting the
very "advertised boundary more permissive than reality" failure the ordering exists to prevent, and
doing it silently.

### The cleanup order

Each run, in this order:

1. **Advance the stored date** to the appropriate Monday.
2. **Delete the data before it** — day items and their `id → date` pointers, transactionally.

**The advertised boundary must never be more permissive than reality.** Deleting first opens a window
where the stored date promises data that is already gone, and clients asking for those days get empty
results indistinguishable from "nothing was booked". Advancing first opens the opposite window — data
that still exists but is no longer advertised — which is harmless. **The ordering holds even if the
job dies between steps**, which is the real test of it. It is also catch-up safe: a job that has not
run for weeks advances to the correct Monday and deletes everything before it in one pass.

**It does not notify clients — for now.** Broadcasting would mean routing deletion through a mutation
or a separate broadcast-only call. The consequence is bounded: the ordering protects every reader who
fetches the boundary *after* it advances, which is every new page load. Only a session already in
flight keeps a stale boundary and can navigate to a just-deleted week and see it as empty; a refresh
corrects it completely. Worth revisiting once subscriptions exist — with a dates-only publish mutation
the marginal cost is one more call, needing no new machinery.

### No TTL, not even as a backstop

TTL is the obvious answer and the wrong one, for four reasons:

0. **TTL bakes the policy into the data.** The expiry attribute is written per item, so changing the
   retention window means rewriting every existing item. A scheduled job reads the policy at run
   time. The value is also a function of the *meeting's* date rather than write time — one more thing
   to compute correctly on a path where getting it wrong deletes real data.
1. **TTL cannot tell anyone.** A client holding `Day:2026-08-08` learns nothing when it disappears.
2. **TTL is not atomic across items.** Day items and their pointers would expire independently, so
   `meeting(id:)` could resolve a pointer whose day is gone.
3. **TTL is not even a read boundary.** Deletion is best-effort within ~48 hours, and
   **expired-but-not-yet-deleted items are still returned by reads.** Every read path would need to
   filter on the expiry attribute anyway — strictly more code, for a weaker guarantee.

TTL's real advantage is that deletes cost zero WCU. That matters for millions of rows; here it is
**seven day items and their pointers per week**, so the saving is nil.

**A backstop TTL is worse than none.** It would silently cover for a failed job, so **the failure is
never discovered** — the bill stays flat and nothing surfaces. It would also need a window strictly
longer than 37 days or it would delete data the boundary still advertises.

**The stored boundary is its own dead-man's switch.** If the job has not run, `earliestRetainedDate`
has not advanced, so "is the stored date within 37 days of today?" detects the exact failure using a
value the system already holds and already returns to clients. No metric, no alarm, no new resource,
no cost. A CloudWatch alarm adds only *automatic* notification and is not free — $0.10 per alarm
metric per month, a standing charge that does not scale to zero, against an account running zero
alarms and $0 of CloudWatch spend. The recurring check in #77 is the proportionate answer.

### Cadence and deployment

**Weekly, on an EventBridge scheduled rule** — it pairs with Monday alignment, and the work per run is
bounded by construction. The shape is proven: `mootmaker-demo-data`'s `schedule.tf` is an
`aws_cloudwatch_event_rule` with a cron expression, an `aws_cloudwatch_event_target`, and an
`aws_lambda_permission` scoped to that rule. **It costs nothing** — scheduled rules targeting an AWS
service directly are not billed, and the invocation falls inside Lambda's always-free tier. Confirmed
against the bill: EventBridge does not appear as a line item despite demo-data running daily.

Two details to carry across: set `input = jsonencode({})` explicitly rather than letting EventBridge
send its own envelope, so the handler's payload is a contract rather than an accident; and enable the
rule's `state` in `test` and `production` but **not** in ephemeral environments, which never live
long enough to accumulate anything — and where a schedule firing mid-run would make acceptance tests
nondeterministic.

**Deployed everywhere, scheduled only where it matters.** Acceptance tests invoke it directly, exactly
as `DatabaseReset` already invokes `database-reset` — `LambdaClient` with the test runner's IAM
credentials, function name from an environment variable `verify.sh` computes the same deterministic
way Terraform names it. The Lambda is simpler than demo-data because it talks to DynamoDB rather than
the API: no SSM parameters, no M2M credentials, no Cognito token endpoint.

A `dryRun` payload is worth having, following `database-repair`'s `{"dryRun": true}`, so a test can
assert what *would* be removed before anything is.

**The test seeds history through the API**, using `createMeetings` with past dates inside
`[earliestRetainedDate, earliestRetainedDate + 6]`, then runs the job and asserts those days are gone
and later ones are not. Seeding through the real write path means the seeded items go through
`DayRepository` — there is exactly one implementation of the day-item format, and the test proves it
rather than duplicating it. `verify/` has no DynamoDB SDK and no dependency on `impl`, and this keeps
it that way.

**This is why past bookings stay legal permanently.** It closes what was an open question: adding a
past-booking rule later would break the retention test three files from the symptom. What it costs is
that past days can never be treated as permanently cacheable.

**Writes are therefore bounded in both directions:** `[earliestRetainedDate, today + 180]`. Without
the backward bound a meeting could be created for 1970 and the 217-item storage bound would not be a
bound at all. `OutsideBookableRange` covers both ends, and the same pair of dates bounds viewing —
there is no third concept.

### What the UI must do

**The server publishes both boundaries; the client never computes either.** Having the client work out
"30 days before today" puts **two authorities on one fact**: the deletion job uses the server's date,
the browser uses the user's. A user in UTC+13, or with a skewed clock, then asks for a day the server
already considers expired. Padding by a day would hide the disagreement rather than remove it, and a
test would not catch it because the test would encode the same assumption the code does.

**Both nav directions need a bound.** `PersonCalendarPage` pages backwards *and* forwards without
limit — `subtract(7, 'day')` at line 168 and `add(7, 'day')` at line 177. Disable each against
`earliestRetainedDate` and `latestBookableDate` respectively.

**A client already viewing a week that falls out of retention is not moved.** The control disables
itself where they stand and the empty week says why. Moving a viewport in response to a background
event the user did not cause is the same family of defect as webapp#44, #46 and #50 — the fix for
which was, in every case, to stop things moving underneath the user. In practice this is nearly
unreachable: the boundary advances once a week.

**A link to a meeting older than retention returns not-found** — the same answer as an id that never
existed. One less state for every caller, and it avoids confirming that a given id was once valid.

Retention composes with the horizon: the horizon bounds how far *forward* day items can exist,
retention how far *back*. Together the table holds at most **217 items** — a hard upper bound on row
count, not merely a cap on the growth rate. Cognito is the one component that legitimately grows,
since MAUs track users rather than time.

## Real-time updates

**How `@aws_subscribe` works, since the constraints all follow from it.** A subscription field has no
resolver. It declares "when mutation X succeeds, push me a copy of what it returned". The mutation's
return value *is* the broadcast payload — there is nothing else, and the subscription field's type
must equal the mutation's return type so the subscriber's selection set fits the pushed object.

Three consequences shaped the design:

1. One subscription cannot span mutations with different return types, so it cannot cover both
   `createMeeting` (`CreateMeetingResult`) and `createMeetings` (`CreateMeetingsResult`).
2. A **rejected** `createMeeting` returns successfully with a typed `errors` array — validation is
   data, not a transport error — so subscribing to it directly would broadcast failed bookings.
3. The payload inherits the response's size, and a worst-case `Day` is **~618 KB** of JSON against a
   **240 KB** subscription cap.

**Hence a publish-only mutation, and a payload of invalidated dates rather than data.**
`publishDaysInvalidated(dates:) : Invalidation` exists only to be broadcast, so its return type is
free to be designed as the payload. Beyond fitting the cap this is better on the merits: the payload
is uniform and tiny whatever the day holds; one channel serves every kind of change including future
history deletion; and it is idempotent, where merging the same meeting twice needs deduplication.

| | Payload | Budget | Client work |
|---|---|---|---|
| `createMeeting` response | The whole `Day` | 5 MB | None — `Day` is an entity, Apollo replaces it |
| `daysInvalidated` broadcast | A list of dates | 240 KB, unreachable | Evict; the gap fetch refills |

**`Invalidation` is a wrapper object, not a bare `[String!]!`.** Adding a field to a GraphQL output
type is backward compatible, so deferred reference-data flags (`rooms`, `people`) can be added later
without breaking a deployed client. Typing the subscription as a bare list would have made that a
breaking change. This is the one thing locked in now.

### `publishDaysInvalidated` must be `@aws_iam`

The API is single-mode `AMAZON_COGNITO_USER_POOLS` with `default_action = "ALLOW"` and no `@aws_auth`
anywhere, so **every valid token can reach every field**. The `"Admin only."` docstrings on
`createRoom`/`createPerson` are enforced in the Lambda by `Identity.requireAdmin`, not at the gateway.
A publish mutation left on the default mode would be callable by any signed-in user — reintroducing
exactly the flaw that got `Mutation.reset` removed.

The change is small, because **the default auth mode covers everything unannotated**:

```hcl
authentication_type = "AMAZON_COGNITO_USER_POOLS"   # unchanged
additional_authentication_provider { authentication_type = "AWS_IAM" }
```

```graphql
publishDaysInvalidated(dates: [String!]!): Invalidation @aws_iam
type Invalidation @aws_iam @aws_cognito_user_pools { dates: [String!]! }
```

Every other field, type, input and enum stays bare. `Invalidation` needs both because it is read by
two principals: the Lambda writes it under IAM, Cognito subscribers read the pushed copy.

**Two independent locks.** The schema annotation says "IAM principals only"; the resolver role's
`appsync:GraphQL` grant is scoped to the single field ARN
(`…/types/Mutation/fields/publishDaysInvalidated`). Neither alone is trusted. That is an AWS
permission grant rather than an in-product role — the distinction the reset decision turns on, and
stronger than anything else in the schema currently has.

**The call itself** is a SigV4-signed HTTPS POST from the resolver Lambda back to its own AppSync
endpoint, using its execution role. The role has no `appsync:GraphQL` permission today. `impl` needs
an SigV4 signer (`AwsV4HttpSigner`) and an HTTP client, having neither.

**A failed publish must not fail the mutation.** The write has committed and is correct, and the user
who made the change already has the new state in their own mutation response. Log and move on; other
clients stay stale until they navigate or refresh — the same accepted gap as reset and history
deletion. Failing a successful booking because a notification failed is strictly worse.

### Verified: the transport is AWS's own protocol, not `graphql-ws`

Probed against a deployed API on 2026-09-09, because this decides a client dependency rather than a
detail.

**AppSync refuses the `graphql-transport-ws` subprotocol.** That is the protocol the `graphql-ws` npm
package speaks, and therefore what Apollo's stock `GraphQLWsLink` sends. Requesting it negotiates *no*
subprotocol and the socket closes with code 1006 before a single message is exchanged — with the token
in the `connection_init` payload and with it in the query string alike. Only AWS's own `graphql-ws`
subprotocol connects, and despite the shared name it is a different message format (`ka` rather than
`ping`, `start`/`data` rather than `subscribe`/`next`).

```
requested graphql-ws              → negotiated "graphql-ws", connection_ack, ka
requested graphql-transport-ws    → negotiated "",           close 1006
```

**So `GraphQLWsLink` is ruled out.** The approach *(decided 2026-09-09)* is to **try
`aws-appsync-subscription-link` first and hand-roll if it fights** — least initial effort, with the
protocol now documented well enough above that falling back is a known quantity rather than a
research task. The risk to watch is committing surrounding code to the dependency's shape before
knowing it fits; keep the link behind the smallest possible seam so replacing it stays cheap.

**`connectionTimeoutMs` is 300,000 — five minutes.** Returned in the `connection_ack` payload as
`{"connectionTimeoutMs":300000}`. It is how long the client may wait between messages before treating
the connection as dead, and it bounds how stale a client can be before the reconnect resync in rows 2
and 4 of the cross-client table fires.

**Keep-alive interval: 60 seconds.** Measured over a 150-second connection — gaps of 59,958 ms and
59,836 ms. So the five-minute timeout is five missed keep-alives, not one, which is a comfortable
margin rather than a tight one.

This does not change the conclusion that nothing has to clean up after a disappeared client — that
remains a property of connection-scoped subscriptions. It changes only how the client is built.

### Why AppSync over the alternatives

No new infrastructure, reuses the existing Cognito authoriser, no connection registry. SSE would mean
a Lambda holding an idle connection billed wall-clock: 512 MB × 900 s is ~450 GB-s per connection per
15-minute window, about **$0.03 per connected browser-hour**, or ~$70/month for ten users on an
eight-hour day. The same traffic in AppSync connection-minutes is ~$0.0004. API Gateway WebSockets
avoid the idle billing but rebuild what AppSync already provides.

Rates verified against the bill: August's 27,474 requests cost $0.109896, exactly
`requests × $4/million`. **The free tier is not being applied to this account** — budget without it.

**Nothing has to clean up after a disappeared client.** Subscriptions are scoped to the WebSocket
connection; when it goes, they go. There is no server-side registry to reap — precisely the work API
Gateway WebSockets would have required. A machine switched off mid-session sends no close frame and
no FIN, so the connection is discovered as dead only when AppSync next tries to write to it or the
timeout elapses — tens of seconds to a couple of minutes. Connection-minutes accrue until then; at
$0.08 per million this is not worth engineering around.

**Subscriptions bill per delivery, per subscriber**, so cost scales with `mutations × subscribers`.

## The Apollo cache

`apolloClient.ts` is currently a bare `new InMemoryCache()` with no `typePolicies` — all of this is
new. Full mechanics, including the gap computation and the mutation-payload analysis, are in the
proposal directory's README. Three policies carry the design:

```ts
Day: { keyFields: ['date'] },                // → cache key "Day:2026-09-14"
Workspace: { keyFields: false },             // not an entity; inline under ROOT_QUERY
Query: { fields: { workspace: { keyArgs: false, merge: /* days union, rest replace */ } } }
```

**`keyArgs: false` is easy to miss and expensive to omit.** Without it every distinct `dates` array
gets its own `workspace` slot, caching the same rooms and people again under each. Because the array
changes on every navigation those slots accumulate as junk that is never read. Getting this wrong
produces a cache that silently refetches everything on every navigation — slower, not broken, so
tests still pass. It needs its own test.

**Three hazards that surface as intermittent failures, not reproducible ones:**

- **Cache presence must be the only record of what has been fetched.** A separate "dates I've asked
  for" set in React state would survive an eviction that clears the cache, so the gap check concludes
  the day is still held and that client is stale forever — on one machine, with no error.
- **An in-flight fetch can race an invalidation.** A writes at t0; B's fetch was issued at t−1 and
  lands at t+1 with pre-write data, *after* B evicted at t0. B is stale with nothing left to trigger a
  refetch. A per-date "last invalidated at" marker, re-evicting when a response was requested before
  it, closes it.
- **A client receives its own invalidation.** The tab that just booked is also a subscriber, so it
  evicts the `Day` its own mutation response authoritatively wrote, and refetches — a wasted round
  trip, and a window where `useFragment` reports `complete: false` and the component renders empty.
  **The person who made the booking sees their own screen flicker, on every create.** The client must
  record the dates its own mutations wrote and ignore invalidations for them for a few seconds.

**`days` is a `read` policy, not an accumulating `merge`** *(decided 2026-09-09)*:

```ts
days: { read: (_, { args, toReference }) =>
  args.dates.map((date) => toReference({ __typename: 'Day', date })) }
```

It maps the requested dates onto `Day` references rather than keeping a list. So it never
accumulates across a session, never leaves dangling references after an eviction, and
`workspace.days` means "the days I asked for" rather than "every day this session has seen". The
accumulating `merge` works too — Apollo filters dangling refs from lists on read — but it grows for
the life of the tab and needs a `unionByDate` nobody has to write under this version.

## Still to verify

Facts already established by experiment are stated in the sections above. These are not, and are to
be answered empirically on a throwaway AppSync API before the subscription work is built — enough
constraints have turned up by accident that the rest should be found on purpose.

- **The return-type match.** Confirm a subscription typed to the publish mutation's return type
  delivers, and that a mismatch silently does not.
- **Rejected mutations.** Does a `createMeeting` returning a typed `errors` array broadcast? Can
  `$extensions.setSubscriptionFilter()` exclude it? (Moot if the publish-only mutation is used, but it
  determines whether that is the *only* option.)
- **The `Invalidation` type's directives.** Whether `@aws_iam @aws_cognito_user_pools` on the type is
  required, or whether the field directive suffices. Failure mode is
  `Not Authorized to access dates on type Invalidation` at subscribe or publish time — not at deploy.
- **Whether `default_action` is ignored** once additional authorization modes are configured. If so
  it becomes dead config rather than a live setting, and should not be left looking meaningful.
- **The 240 KB payload cap.** Confirm a dates-only payload cannot approach it.
- **Connection lifetime:** whether AppSync enforces a maximum (24 hours is the figure associated with
  it, without confidence), and whether a subscription can outlive a reconnect. The timeout and
  keep-alive interval are now measured — see "Verified: the transport is AWS's own protocol".

## Changes to the data model

The delta against `docs/reference/data-model.md`:

- **Meetings table re-keyed by day**, with a version attribute for optimistic locking.
- **Both meetings GSIs removed** — `bucket-startTime-index` and `roomId-startTime-index`, along with
  the constant `bucket = "ALL"` attribute that exists solely to give a GSI a partition key.
- **`meeting-participants` deleted**, along with `RebuildMeetingParticipantsRepair`.
- **`cognitoSub-index` deleted**, replaced by the `custom:personId` claim forward and a `cognitoSubs`
  list attribute in reverse.
- **A new id → date pointer** backing `meeting(id:)` — the only secondary lookup structure kept.
- **A `CONFIG#retention` item**, Terraform-initialised.
- **A maximum booking horizon** as a business rule, and a matching floor at the retention boundary.

## Impacts on components

Scope is "everything the new design touches", not the smallest set of files that could work.

**`mootmaker-api`** — `api/mootmaker.graphql` (new `Day`, `Workspace`, `Boundaries`, `Invalidation`;
`createMeetings`; `Subscription`; the `personId` filter argument goes with the client that needed it);
`appsync.tf` (request template, subscription resolvers, `@aws_subscribe`, the IAM auth provider);
`dynamodb.tf` (day-keyed table, GSIs and `bucket` removed, `cognitoSub-index` removed, the retention
config item); `cognito.tf` (the `custom:personId` attribute, read/write attribute lists, claims and
Persons for the demo and e2e users); `iam.tf` (`appsync:GraphQL` scoped to one field). `MeetingRecord`
and `MeetingParticipant` are deleted; `BatchLoader` is absorbed into the repositories;
`ListMeetingsHandler`, `CreateMeetingHandler`, `ResolverDispatchHandler`, `DeleteMyAccountHandler`,
`PostConfirmationCreatePersonHandler`, `CreateMissingPersonsRepair` and `DatabaseReset` are rewritten
against the new shapes rather than adapted. A new history-cleanup Lambda and its EventBridge rule.

**`mootmaker-webapp`** — `apolloClient.ts` (`typePolicies`, the subscription link, designed around the
composite shape from scratch); `graphql/queries.ts` and `mutations.ts` rewritten; `HomePage`,
`RoomAvailabilityPage`, `PersonCalendarPage`, `AddMeetingPage`, `SettingsPage`. The router-state
workaround in `AddMeetingPage` and the paired `createdMeeting` merge in `RoomAvailabilityPage` are
**deleted** — they exist only to work around a read-after-write window that day-keyed reads with
`ConsistentRead` remove entirely. Date navigation gains bounds in both directions.

**`mootmaker-demo-data`** — `DemoData.java`'s `runInParallel(meetings, …createMeeting…)` becomes one
bulk call per seeded day. This is also what resolves its parallel creates colliding on the day item's
version attribute.

**`mootmaker-release`** — no change expected, but the acceptance suite it gates changes materially.

## Testing

**Cross-client visibility — the headline benefit, and the definition of done for it.** No spec under
`webapp/tests/` currently uses `browser.newContext()`; every test runs in the single storage state
from `auth.setup.ts`. This needs two contexts with separate storage states. Both users already exist —
`e2e_user_email` and `demo_user_email` are Terraform outputs — so no new Cognito plumbing.

The trigger for a refetch is **a live `useFragment` watching that `Day`**, not "the user is looking at
it". Cache residency and being watched are independent, which is what rows 3a and 3b distinguish.

| # | Scenario | Requirement |
|---|---|---|
| 1 | B watching that day, tab focused | B's DOM shows the meeting **within 3 s**, no navigation or reload |
| 2 | B watching that day, tab backgrounded | No guarantee while hidden; current **within 3 s** of returning to foreground |
| 3a | Day cached but **not watched** | The entity is evicted and the cached data discarded. **No network request** |
| 3b | Day **not in the cache** | `cache.evict` returns `false`. Complete no-op |
| 4 | B offline when it happens | On reconnect, on-screen days are re-fetched — same mechanism as row 2 |
| 5 | B on the Add Meeting form | **The form does not change under them.** They find out at submit, via `TimeRangeUnavailable` |
| 6 | B is an attendee | **No difference.** Stated as intended, not an oversight — there is no notification concept |
| 7 | Same user, two tabs | Behaves as two users, and the booking tab must not flicker (see the self-invalidation hazard) |
| 8 | The refetch fails | A visible, non-blocking stale indicator with retry — never silently stale |

**Rows 2 and 4 are one requirement.** Both are "the connection was not continuously open", and B never
needs to know *what* it missed — only to distrust what is on screen. On reconnect or on return to
foreground, evict the displayed days and let the gap fetch refill them. No sequence numbers, no
server-side replay. This also settles the socket question honestly: browsers freeze background tabs and
AppSync will drop the connection, so **correctness must not depend on the socket surviving.**

**Row 5 is deliberate restraint.** The server already rejects the overlap at submit, so the failure path
exists and is correct; changing a form under someone is the defect class webapp#44, #46 and #50 were
fixed by *stopping*. The room must not silently vanish from the dropdown, and `suggestRoom` must re-run
only when the user changes the time, never spontaneously.

**Row 3a is the one most likely to be mistaken for a defect later** — the day is evicted, nothing
watches it, no query is made, and it is fetched fresh whenever the user navigates there. That is correct
and costs nothing, but only if it is written down as intended.

**The guarantees need tests that assert the guarantee, not the limits:**

- **A day at every cap simultaneously** — the day limit's worth of meetings, each at the attendee limit
  with a maximum-length subject — serialised, with the real byte size asserted inside budget. That test
  fails if anyone adds a field to the persisted shape without revising the limits, which is the actual
  regression to guard against.
- **A request at every static limit at once** — `maxDates` days each holding `maxMeetingsPerDay`
  meetings, alongside `maxRooms` rooms and `maxPeople` people — asserted **rejected** by the
  `maxMeetingsPerResponse` check rather than producing an oversized response. The mirrored case, one
  meeting under the cap, must succeed.
- **A test that measures the real serialised response**, not the modelled one, so the estimate being
  wrong fails a test rather than a user.
- **A subscription payload test.** 240 KB is the tightest limit in the design and the easiest to breach
  by accident — one change to broadcast a `Day` instead of dates would do it.
- **A test that the deploy-time assertion fires** on a deliberately inconsistent set of limits.
- **Multi-byte subject tests in both directions**: 280 ASCII accepted and 281 rejected; **70 emoji
  accepted and 71 rejected**. A test using only ASCII passes just as happily against a `String.length()`
  implementation, which is the bug this exists to catch.
- **Boundary tests on each rule** — at the limit succeeds, one past it returns the right `MeetingError`
  rather than an exception.
- **An acceptance test that a user hitting a limit sees a rendered message**, not a server error.

**Retention tests:**

- **Assert what survives, not just what goes.** A job that deletes too much passes a test that only
  checks the old data is gone. Seed either side of the boundary; assert everything before it is deleted,
  **everything on or after it is untouched**, the pointers went with their days, and the boundary
  advanced to the expected Monday. The day falling exactly *on* the boundary is the off-by-one worth an
  explicit case.
- **The invariant itself:** after any run, no day item may exist earlier than the stored boundary.
- **Catch-up:** seed several weeks of past days, run once, assert all cleared and the boundary correct.
- **Idempotency:** a second run immediately after the first changes nothing.

**Also:** unit coverage for selection parsing driven by recorded `selectionSetList` payloads including
aliases and fragments; a test that the cache does not refetch reference data on navigation (the
`keyArgs: false` regression); and rewrites of anything depending on `ListMeetings` argument shapes or the
`createdMeeting` router-state handoff.

## Documentation impacts

- `docs/reference/data-model.md` — day-keyed storage, GSI removal, participants table outcome.
- `mootmaker-api/api/` schema documentation strings, which are extensive and load-bearing.
- `mootmaker-api/testing-strategy.md` and `mootmaker-webapp`'s equivalent — the multi-context layer.
- `docs/reference/running-costs.md` — real-time charges are a new line item.
- `designs/README.md` states "there is no longer a long-lived `test` environment", which stopped being
  true on 2026-09-03. Worth fixing, though not part of this design.

## Rollout & migration

**No migration. `test` and `production` are destroyed in full and redeployed.** Every table, every
Cognito user pool, every user. No backfill, no dual-read period, no reverse-migration path. This is a
demo system; `mootmaker-demo-data` repopulates it, and a migration path — plus the reverse path needed
to make it reversible — buys nothing. It also removes the question of what to do about Cognito-linked
Persons by removing both sides of the link at once.

This is a rehearsed operation, not a novel one: both environments were destroyed and rebuilt from
nothing by the pipeline on 2026-09-06 as `v1.0.0`, and Cognito is part of `mootmaker-api`'s Terraform,
so the pools went with them. Tracked as #67.

What comes back is created by Terraform:

- `aws_cognito_user.e2e` and `aws_cognito_user.demo` are recreated with **new passwords** from their
  `random_password` resources, flowing to the webapp through Terraform outputs.
- The acceptance-test M2M client secret rotates. `mootmaker-demo-data` reads its credentials from the
  SSM parameters `mootmaker-api` publishes, so the api deploy must complete before demo-data runs —
  which the pipeline already orders correctly.
- No user pool carries `deletion_protection`, so nothing blocks the destroy.

**Verified 2026-09-07:** `production`'s pool contains exactly two users, `e2e-tests@example.com` and
`demo@mootmaker.com`, both Terraform-managed. There are no real signed-up accounts to lose. **That is a
fact about that day, not a standing property** — re-check immediately before running it.

Staging is otherwise conventional: ephemeral environment first, then `test`, then `production` through
`release.yml`. The schema changes are not backward-compatible for a deployed webapp, so API and webapp
must ship together — which the release pipeline already does.

## Risks

- **Everything is gone, deliberately** — meetings, rooms, people, and every Cognito account. Anyone who
  has signed up between now and the day this runs loses their login, not just their data, and finds out
  by being unable to sign in.
- **Recreating a Cognito user pool domain can stall.** `aws_cognito_user_pool_domain` uses
  `<prefix>-<account-id>`, globally unique across AWS. Destroying and immediately recreating the same
  domain is the one step in this teardown with a known tendency to fail or need a wait, and it sits on
  the critical path for the OAuth2 token endpoint the M2M clients use.
- **Reverting is a redeploy, not a rollback.** With no migration there is no reverse migration: going
  back means deploying the previous version against freshly recreated tables. Cheap, but the same data
  loss happens again in the other direction.
- **Broadcast visibility becomes load-bearing.** Subscriptions push to everyone matching the filter.
  Safe only while every user may see every meeting. **This design should not be built on if meeting
  privacy is anticipated.**
- **Write contention on a day item** is a new failure mode with no current analogue. Two concurrent
  creates can both observe 199 and both decide they fit; the conditional write on the version attribute
  resolves it, and the loser re-validates against the updated count rather than a stale read.
- **Write amplification.** Adding one meeting rewrites the whole day: at 1 WRU per KB, a full 400 KB day
  costs ~400 WRU per booking against roughly 10 today. At demo scale a day is ~20 KB and this barely
  matters, but it grows linearly and the last booking pays for every earlier one.
- **The day ceiling is a hard rejection.** Without enforced limits and a deliberate answer near
  capacity, the first symptom is a failed booking.

## Implementation plan

Five slices, each verifiable on its own ephemeral environment. Slices 2 and 3 must ship together — the
schema break is not backward-compatible for a deployed webapp.

**Slice 1 — the request template and selection-aware resolving.** Independently shippable and valuable
on its own: it removes an existing over-fetch where `meetings { id subject }` still batch-loads every
room and person. No schema change.

- [ ] Change the resolver request template to serialise `selectionSetList`, in whatever payload shape
      the new handlers want. It stops shipping every CloudFront request header to Lambda either way.
- [ ] Make `ListMeetingsHandler` selection-aware, with unit tests driven by recorded payloads including
      aliases and fragments.

**Slice 2 — storage, repositories and the guarantees.**

- [ ] `DayRepository`, `PersonRepository`, `RoomRepository` as init-constructed instances; `BatchLoader`
      absorbed and deleted.
- [ ] Day-keyed table, GSIs and `bucket` removed, `meeting-participants` and
      `RebuildMeetingParticipantsRepair` deleted, the `PTR#` pointer, the Terraform-initialised
      `CONFIG#retention` item **with `ignore_changes`**.
- [ ] The three size-guarantee layers, the limits, and the `MeetingError` cases.
- [ ] `custom:personId`: the Cognito attribute, read/write attribute lists, the PostConfirmation
      trigger, `CreateMissingPersonsRepair`, Persons and claims for the demo and e2e users,
      `cognitoSub-index` deleted, `cognitoSubs` added.
- [ ] `deleteMyAccount` by scan, Cognito users deleted last.

**Slice 3 — the composite schema and the webapp.** Ships with slice 2.

- [ ] `Query.workspace`, `Boundaries`, `createMeetings`, `meeting(id:)`.
- [ ] **Correct `StartMissaligned`/`EndMissaligned` to `StartMisaligned`/`EndMisaligned`** *(decided
      2026-09-09)*. A misspelling in the live enum, mirrored in the Java enum and rendered by the
      webapp. It is only free while the contract is already being broken and both environments are
      being rebuilt, so it happens here or it becomes permanent. Its own commit — it is unrelated to
      everything else in the slice.
- [ ] `apolloClient.ts` typePolicies; queries and mutations rewritten; the five pages; date navigation
      bounded in both directions; the router-state and `createdMeeting` workarounds deleted.
- [ ] `mootmaker-demo-data` one bulk call per seeded day.
- [ ] Resolve the `days` `merge`-versus-`read` sub-question first.

**Slice 4 — retention.**

- [ ] The cleanup Lambda, its EventBridge rule (enabled in `test`/`production` only), `dryRun`, and the
      acceptance tests including catch-up, idempotency and the on-boundary off-by-one.

**Slice 5 — real-time.**

- [ ] Answer everything under "Still to verify" empirically first.
- [ ] `publishDaysInvalidated` with `@aws_iam`, the IAM auth provider, the field-scoped role grant, the
      SigV4 call from the resolver.
- [ ] The subscription link in the webapp, the self-invalidation guard, the in-flight-race marker, and
      the reconnect/foreground resync.
- [ ] The two-context acceptance test asserting every row of the cross-client table.

**Not done by Claude:** destroying and rebuilding `test` and `production` (#67). It sits on the critical
path for a globally-unique Cognito domain with a known tendency to stall, and the pool's user list is a
judgement call about real accounts rather than a scripted step.

## Definition of done

The feature's own acceptance coverage — including the two-context real-time test, which asserts **every
row** of the cross-client table rather than only the happy path — is green; the existing acceptance suite
is still green on a real deployed environment; every touched repo's unit tests pass; no code remains that
exists only to preserve a shape from the previous design; and everything under Documentation impacts is
actually done.

Completed separately, by Geoff: both environments destroyed in full, redeployed from nothing and
repopulated by `mootmaker-demo-data`, with the result verified by direct DynamoDB and Cognito reads
rather than by exit codes.
