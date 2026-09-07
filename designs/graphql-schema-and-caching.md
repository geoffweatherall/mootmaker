# GraphQL schema and caching

## Summary

The API's entry points are shaped like REST endpoints: three unrelated top-level list fields that a
client must call separately, with the client supplying its own identity as a filter argument. This
design reshapes them around a single unit — **the day** — so that one key identifies a DynamoDB
item, an AppSync fetch, an Apollo cache entity, and a subscription filter. It also makes resolvers
selection-aware so a query that asks for less does less work, and adds real-time updates so one
user's booking appears on another's screen without a refetch.

## Status

**Drafting** — 2026-09-07.

## Highlights

The main changes, each considerable on its own. **Decided** means settled by discussion and recorded
under Trade-offs; **Open** means it still needs an answer.

1. **One DynamoDB item per day** *(Decided)* — meetings for a date live in a single item, read by
   primary key. Buys `ConsistentRead`, which removes the read-after-write class of bug outright. Costs
   write amplification and read-modify-write contention, and imposes a hard ceiling of roughly 1,000
   meetings per day.
2. **The shape of the top-level query** *(Open)* — three sibling root fields in one document, or one
   composite entity carrying people, rooms and a date range of meetings. See "What requires a server
   round trip" below, which exists to inform this.
3. **Selection-aware resolvers** *(Decided)* — a query asking for `attendees { id }` does no Person
   lookup; one asking for `{ id name }` does exactly one. Requires a request-template change first,
   and the alias behaviour makes the selection test something to get right deliberately.
4. **The server derives "mine" from the JWT** *(Decided)* — the client stops fetching its own id and
   handing it back as a filter argument. This is what removes the startup waterfall.
5. **Day-scoped bulk creation** *(Decided)* — `createMeetings(date:, meetings:)`. One operation, one
   item write, one subscription message, one filterable field. Also sidesteps the 100-item
   `TransactWriteItems` cap.
6. **Real-time updates via AppSync subscriptions** *(Decided)* — one user's booking appears on
   another's screen in tens of milliseconds. Costs pennies; the alternatives cost either ~$70/month
   or a connection registry of their own.
7. **Apollo cache built on day entities** *(Decided)* — `Day` keyed by `date`, so an empty day and an
   unfetched day are distinguishable. Mutation results are written into the cache directly.
8. **No cache persistence across refresh** *(Decided)* — see below; a refresh is a deliberate
   stateless restart the user can always reach for.
9. **Both meetings GSIs and the person index are deleted** *(Decided)* — every user-facing query
   carries a date range, so no index is needed to serve one. A **maximum booking horizon** replaces
   the one unbounded query. See "No person index" below.
10. **`meeting(id:)` gains a real entry point** *(Decided)* — a dedicated field backed by an id → date
    pointer, replacing today's full-table scan.
11. **Enforced size limits, with an oversized item made unreachable** *(Decided; the numbers have a
    conflict to resolve)* — an absolute cap on meetings per day, a per-organiser daily cap, an
    attendee cap, and a **maximum subject length, which does not exist today**. Enforced at three
    layers so that no input a user can construct produces an item over 400 KB. See "The item-size
    guarantee".
12. **Destroy and rebuild both environments** *(Decided)* — no migration, Cognito pools included.
13. **Reset becomes a mutation, behind RBAC** *(Decided; the RBAC model is a follow-up)* — it stops
    being a side door, so it broadcasts like any other write. Putting a destructive operation in the
    public schema has auth consequences the current flat admin role does not cover.

## What requires a server round trip

Every point at which the webapp needs data it does not have. This is the input to Highlight 2 — the
top-level query shape should be chosen against this list, not against the current page structure.

**On load and authentication**

| Trigger | Data needed | Today |
|---|---|---|
| Any page load or refresh, signed in | Cognito claims, then the caller's Person | `MyPerson`, `network-only`, on every load |
| Sign in | Same | Same, via `loadSession()` |
| Sign up / confirm | None from the client | The PostConfirmation trigger creates the Person server-side |

**Per page**

| Page | Data needed | Today |
|---|---|---|
| Home (signed in) | My meetings, today → +2 days | `ListMeetings`, blocked until `MyPerson` resolves |
| Home (signed out) | None | Demo credentials come from runtime config |
| About | None | — |
| Person calendar | All people, all rooms, one person's meetings across a 40-day span (30 displayed; weekends are in the range but not shown) | Three queries; rooms and people `cache-first` |
| Room availability | All rooms, all meetings for one date | Two queries |
| Add meeting | All rooms, all people | Two queries, in parallel |
| Meeting details | **One meeting** | `ListMeetings` **with no filter at all** — every meeting ever stored, then `.find()` client-side. There is no `meeting(id:)` field in the schema |
| Settings | The caller's Person | From auth context |
| Settings, admin sections | All rooms, all people | Two queries, both gated so neither section renders until both land |

**On user action**

| Action | Round trip |
|---|---|
| "Suggest a room" | `suggestRoom(startTime, endTime, requiredCapacity)` |
| Create meeting | `createMeeting` |
| Rename self | `updatePerson` |
| Change date/time preferences | `updateMyPreferences` |
| Create or edit a room | `createRoom` / `updateRoom`, plus a refetch **and** a direct cache write |
| Create or edit a person | `createPerson` / `updatePerson`, same pattern |
| Delete my account | `deleteMyAccount` |

**Caused by someone else**

| Event | Today |
|---|---|
| Another user creates a meeting | Nothing. Stale until something refetches |
| The daily `mootmaker-demo-data` run (18:00 NZT) | Nothing |
| A database reset | Nothing, and the client keeps showing deleted data |

Three observations fall out of this list. **Rooms and people are wanted by four of the seven pages
and change rarely** — they are the strongest candidates for fetching once. **Meetings are always
wanted as a date range**, and the ranges differ per page (3 days, 1 day, 40 days), which is precisely
what day-keyed entities make composable. And **meeting details is the one lookup that is not a date
range at all** — it is a single meeting by id, and it is currently served by scanning the entire
table.

## Scope / non-goals

**In scope:** the shape of `Query`'s entry points; selection-aware fetching in the resolver Lambda;
day-keyed meeting storage in DynamoDB; the Apollo `InMemoryCache` policy; a bulk meeting-creation
mutation; GraphQL subscriptions for cross-client updates.

**Not in scope:**

- `mootmaker-android` — it does not exist yet and should not constrain this.
- Any change to the privacy model. Today every signed-in user can see every meeting, and this
  design assumes that stays true (see Risks — subscriptions make it load-bearing).
- Meeting update and delete. Neither exists today; adding them is a separate design.
- Pagination beyond day ranges.
- Changes to the Cognito user pool's *configuration*. The pool is destroyed and recreated as part of
  the rollout (see Rollout & migration), but its Terraform definition is unchanged, except for the
  optional `personId` claim recorded as a non-blocking open question.

## Trade-offs and decisions

**No data migration. The whole environment is destroyed and rebuilt.** Not just the tables — `test`
and `production` are torn down in full and redeployed from nothing, Cognito user pools included.
This is a demo system; `mootmaker-demo-data` repopulates it, and the cost of a migration path — plus
the reverse path needed to make it reversible — buys nothing. It removes the largest risk and the
longest phase from the rollout, and it removes the question of what to do about Cognito-linked
Persons by removing both sides of the link at once.

This is a rehearsed operation, not a novel one: both environments were destroyed and rebuilt from
nothing by the pipeline on 2026-09-06 as `v1.0.0`, and Cognito is part of `mootmaker-api`'s
Terraform, so the pools went with them.

**No decision is carried forward for compatibility's sake.** The finished code and schema should
look as though they were designed this way on day one. Where a shape exists only because of how the
current design evolved, it is replaced rather than adapted, and the cost of doing so is not a factor
in the choice. Concretely this deletes rather than preserves: `MeetingRecord` and
`MeetingParticipant`, the constant `bucket = "ALL"` attribute, both meetings GSIs, the
router-state handoff between `AddMeetingPage` and `RoomAvailabilityPage`, and the resolver payload
shape that today's handlers read. It also settles what would otherwise be a blocking question — see
"one composite field" below.

**The meetings item is already normalised; the redundancy is elsewhere.** `MeetingRecord.toItem()`
stores `roomId`, `organiserId` and `attendeeIds` as bare ids — no names, no capacities. The
duplication is in the two `projection_type = "ALL"` GSIs on the meetings table and the
`meeting-participants` join table. A meeting with four attendees is physically stored **eight
times** (1 base + 2 GSI copies + 5 participant rows). Any "remove denormalisation" work should aim
there, not at the item.

**Concurrent root fields do not double cold-start latency.** AppSync resolves a query's root fields
in parallel, so the client waits `max(restore + work)`, not the sum. What they do cost is
*execution environments*: three root fields create three, each paying its own SnapStart restore and
each holding a concurrency slot.

The account concurrency limit was raised from 10 to 1,000 on 2026-09-07 (mootmaker#72), which
**weakens this argument rather than strengthening it**. Three parallel root fields no longer come
close to saturating the account, so collapsing them is now justified by total compute and by the
number of SnapStart restores paid per page load — not by a ceiling. It is worth being honest that
this is a smaller prize than it looked while the limit was 10.

**`info.selectionSetList` is not in the resolver payload today.** This was verified empirically, not
read from documentation. Decoding `$util.toJson($ctx)` — the exact expression in `appsync.tf`'s
shared `direct_lambda_request_template` — from a live AppSync response gives:

```json
"info": { "fieldName": "probe", "parentTypeName": "Query", "variables": {} }
```

No `selectionSetList`, no `selectionSetGraphQL`. AWS documents this ("the values that
`selectionSetGraphQL` and `selectionSetList` return are not serialized by default"); they appear
only when referenced explicitly. **Selection-aware resolving therefore requires a template change
before any handler work.**

**There is no depth limit on `selectionSetList`.** Verified to five levels on a throwaway AppSync
API — `l1/l2/l3/l4/l5/name` came back flattened. `meetings/attendees/name` is three levels, so the
design's central assumption holds comfortably.

**Aliased fields appear under the alias only.** Also verified: querying `aliasedName: name` yields
`l1/l2/l3/l4/aliasedName` and *no* entry for `name`. A resolver testing for specific field names
would conclude the client did not want the name and return a stub — and because `name: String!` is
non-null, GraphQL would null the attendee, then the list, then potentially the meeting. Selection
tests must therefore **fail toward fetching**: treat any selection beyond the known-free fields as
"fetch", rather than enumerating the fields that require a lookup.

**One selection-aware resolver, not per-field resolvers.** Attaching resolvers to `Person.name` and
`Person.dateFormat` would fire them independently — two invocations and two DynamoDB round trips for
two fields that live on the same item. Keeping the existing single resolver and reading nested paths
from `selectionSetList` gives one invocation and one (or zero) `BatchGetItem`, and preserves the
request-scoped deduplication `ListMeetingsHandler` already does. A resolver on `Meeting.attendees`
with `max_batch_size` remains the fallback if the fat handler's projection logic becomes unwieldy;
it costs one extra invocation per batched field and would require `ResolverDispatchHandler` to
handle a `List` event rather than a `Map`.

**The server should derive "mine", not the client.** `meetings(filter: { personId })` makes the
client fetch its own id and hand it back, which is what creates the entire startup waterfall
(`MyPerson` must resolve before `ListMeetings` can start). A `mine: true` filter lets the server
resolve the caller from `identity.sub`, as `MyPersonHandler` already does. This also dodges a
consistency hazard: `cognitoSub-index` is a GSI and GSIs reject `ConsistentRead`.

**The cache-slot objection to a composite field is void.** The argument against one composite entity
was that it moves `rooms` from `ROOT_QUERY.rooms` to `ROOT_QUERY.workspace.rooms`, missing every
existing `cache-first` reader and forcing a permanent `cache.writeQuery` mirror. That argument is
entirely about not disturbing client code that is now being rewritten. It no longer applies, and
should not be weighed. The choice itself remains open — see Open questions.

**No cache persistence across a refresh.** `InMemoryCache` starts empty on every page load and will
stay that way: no `apollo3-cache-persist`, no localStorage rehydration. This is not a concession, it
is the point — **a refresh is a guaranteed stateless restart the user can always reach for**, and
that escape hatch is worth more than saving one round trip on a cold load. It also removes an entire
invalidation problem: persisted caches have to answer what happens to data written by the 18:00 NZT
demo-data run while the tab was closed, and this design never has to.

**A dedicated `meeting(id:)` entry point.** Meeting details is the only need that is not a date
range, and today it is served by fetching every meeting ever stored and filtering client-side — which
the schema's own documentation warns against. Day-keyed storage has no id index, so this needs a
deliberate one: an id → date pointer written alongside the day item, letting `meeting(id:)` resolve
in two reads. Chosen over putting the date in the URL because a details link then works from
anywhere — bookmarked, shared, or refreshed — without assuming what loaded first.

**No person index, and a maximum booking horizon instead.** Every user-facing query for a person's
meetings already carries a date range: the home page asks for three days, the calendar for forty.
There is exactly one path that does not — `DeleteMyAccountHandler` queries the participants table for
the caller and filters `startTime >= now`, i.e. *every upcoming meeting*, unbounded in the future
direction. That single operation is the only thing the index exists for.

Rather than keep a whole join table to serve one rare operation, the design adds a **maximum booking
horizon**: a meeting cannot be created more than a fixed period ahead. "Every upcoming meeting" then
becomes a bounded, enumerable set of date keys that can be read with `BatchGetItem`, and the index
disappears along with `meeting-participants`, its transactional writes, and
`RebuildMeetingParticipantsRepair`.

**Reset becomes a mutation behind RBAC.** Routing reset through GraphQL means it broadcasts like any
other write, so connected clients evict instead of silently showing deleted data. It also puts a
destructive operation into the public schema, which the current authorisation model is not shaped
for: `Identity.requireAdmin` recognises one flat admin role, so "can add a room" and "can destroy the
database" would be the same permission. **The RBAC model is a follow-up in its own right** — recorded
separately rather than designed here.

**Day limits: 200 meetings, 20 attendees.** Roughly 49% of the 400 KB item cap at worst case, biased
toward large meetings rather than many. See Technical considerations for the conflict this creates
with the current room count.

**A per-organiser daily limit, separate from the absolute one.** A user may organise at most a fixed
number of meetings on any one date. This is a fairness and abuse control, not a size control, and the
distinction matters: *N* organisers each at their own limit can still exceed the day cap, so the
per-organiser rule provides no bound on the item. Only the absolute day cap does. Both exist, for
different reasons.

Its useful range is bounded by physics: an organiser cannot be in two meetings at once, and business
hours of 08:00–17:00 on 15-minute boundaries mean one person can organise at most **36 meetings in a
day**. A limit at or above 36 is inert. `mootmaker-demo-data` will not trip any sane value —
`MeetingScheduler` caps rooms at two meetings a day each and never double-books a participant.

**Maximum subject length — a rule that does not exist today.** `CreateMeetingHandler` checks only
that `subject` is non-blank. There is no upper bound, so a single meeting can carry a subject of any
size and blow the item on its own, regardless of how few meetings the day holds. **No count-based
limit can deliver the "no oversized item" guarantee while this term is unbounded.** The limit is in
**bytes, not characters** — a subject of emoji is four bytes per character, so a character count
would understate the true size fourfold.

**The day is the unit.** One day is a DynamoDB partition key, an AppSync fetch unit, an Apollo cache
entity keyed by `date`, and a subscription filter value. This alignment is what makes the caching
tractable: an Apollo cache keyed by day can distinguish "no meetings that day" (entity present,
empty list) from "never fetched that day" (entity absent) — an ambiguity that a merged canonical
list with `keyArgs: false` cannot resolve without hand-rolled range tracking.

**Bulk creation is scoped to one day.** `@aws_subscribe` pushes the mutation's return value and
filters match against fields on it. A bulk result spanning many days has no single `date` to filter
on, so subscribers would receive everything and filter client-side — re-creating the fan-out
multiplier. `createMeetings(date: String!, meetings: [MeetingInput!]!)` gives one day, one item
write, one subscription message, one filterable field. It also sidesteps `TransactWriteItems`'
100-item cap, which a cross-day bulk of 100 meetings with attendees (~500 items) would exceed.

**Subscriptions over the alternatives.** AppSync subscriptions need no new infrastructure, reuse the
existing Cognito authoriser, and need no connection registry. SSE would mean a Lambda holding an
idle connection and being billed wall-clock: 512 MB × 900 s is ~450 GB-s per connection per
15-minute window, about **$0.03 per connected browser-hour**, or ~$70/month for ten users on an
eight-hour day. The same traffic in AppSync connection-minutes is ~$0.0004. API Gateway WebSockets
avoid the idle billing but rebuild what AppSync already provides. Rates verified against the
published pricing and confirmed against the actual bill: August's 27,474 requests cost $0.109896,
which is exactly `requests × $4/million`. **The free tier is not being applied to this account** —
budget without it.

## Choices you had me make

- **`Day` keyed by `date` rather than an opaque id.** A human-readable, client-derivable cache key
  means the webapp can construct `Day:2026-09-14` without a round trip to discover it.
- **A payload shaped for the new handlers, not for the current ones.** An earlier draft proposed
  building the payload field by field specifically so that `info.fieldName`, `info.parentTypeName`
  and `identity` stayed where they are and `ResolverDispatchHandler` and `Identity` went untouched.
  That reasoning is void under "no decision carried forward": the template should carry exactly what
  the handlers need in whatever shape reads best, and the handlers change to match. It stops
  shipping every CloudFront request header to Lambda on every call either way.
- **Day-scoped bulk over enhanced subscription filters.** `setSubscriptionFilter` with a `contains`
  operator over a `dates` array would work, but the payload still carries every meeting — it filters
  who is woken, not how much they receive.

## Open questions

### Blocking

**The day limit conflicts with the room count.** 200 meetings per day is below what 10 rooms can
physically hold — see Technical considerations. Needs one of: raise the day limit, lower the attendee
limit, or accept that bookings are refused while rooms sit empty.

**The booking horizon's length.** The maximum-booking-horizon rule is decided; the number is not.

**The per-organiser daily limit's value, and the maximum subject length.** Both rules are decided;
neither number is. The organiser limit is meaningful only in 1–36 (above that it is inert). The
subject limit needs to be small enough that `dayLimit × subjectMaxBytes` is a minor term — at a
200-meeting day, every 100 bytes of subject allowance costs 20 KB of the item's budget.

**The shape of the top-level query.** Either three sibling root fields in one document — one HTTP
request, three Lambda invocations, cache slots that map one-to-one onto the entities — or a single
composite entity carrying people, rooms and a date range of meetings, giving one invocation. The
cache-slot argument that previously made this urgent is void (see Trade-offs), so this is now a
straight choice between invocation count and schema shape, with no legacy pressure either way. "What
requires a server round trip" above is the evidence to decide it against.

### Non-blocking

- **`personId` as a Cognito claim.** Removes the waterfall's dependency but not the `myPerson` call,
  since `name`, `dateFormat` and `timeFormat` are all mutable and must not be baked into a token.
  Custom attributes cannot be removed or renamed once added to a pool, and M2M client-credentials
  tokens have no user behind them, so the fallback path is permanent.
- **A past-booking rule.** Nothing in `MeetingError` rejects a booking in the past, so history is
  not immutable and cannot be cached permanently. Adding the rule would make past days safely
  cacheable forever.
- **`graphql-ws` protocol support.** Determines whether the client is a stock `GraphQLWsLink` or a
  hand-rolled link.

## Impacts on components

Scope here is "everything the new design touches", not "the smallest set of files that could
work" — see the second decision above.

**`mootmaker-api`** — `api/mootmaker.graphql` (new `Day` type, composite query, `createMeetings`,
`Subscription`; the `personId` filter argument goes away with the client that needed it);
`deploy/terraform/appsync.tf` (request template, subscription resolvers, `@aws_subscribe`);
`deploy/terraform/dynamodb.tf` (day-keyed meetings table, both GSIs and the `bucket` attribute
removed). `MeetingRecord` and `MeetingParticipant` are deleted; `ListMeetingsHandler`,
`CreateMeetingHandler`, `ResolverDispatchHandler` and `DatabaseReset` are rewritten against the new
shapes rather than adapted.

**`mootmaker-webapp`** — `apolloClient.ts` (`typePolicies`, designed around the composite shape from
scratch); `graphql/queries.ts` and `mutations.ts` rewritten rather than edited; `HomePage`,
`RoomAvailabilityPage`, `PersonCalendarPage`, `AddMeetingPage`, `SettingsPage`. The router-state
workaround in `AddMeetingPage` and the paired `createdMeeting` merge in `RoomAvailabilityPage` are
**deleted** — they exist only to work around a read-after-write window that day-keyed reads with
`ConsistentRead` remove entirely.

**`mootmaker-demo-data`** — `DemoData.java`'s `runInParallel(meetings, …createMeeting…)` becomes one
bulk call per seeded day.

**`mootmaker-release`** — no change expected, but the acceptance suite it gates changes materially.

## Changes to the domain data model and data storage models

The delta against `docs/reference/data-model.md`:

- **Meetings table re-keyed by day.** Partition key becomes the date; a day's meetings live in one
  item as a list. Adds a version attribute for optimistic locking.
- **Both meetings GSIs removed.** `bucket-startTime-index` and `roomId-startTime-index` exist to
  answer range and per-room queries that a day key answers directly. Removing them also removes the
  constant `bucket = "ALL"` attribute, which exists solely to give the GSI a partition key.
- **`meeting-participants` is deleted**, along with `RebuildMeetingParticipantsRepair`. Every
  user-facing query carries a date range, and the one that did not is replaced by the booking
  horizon.
- **A new id → date pointer** backing `meeting(id:)`. Small, written in the same transaction as the
  day item, and the only secondary lookup structure the design keeps.
- **A maximum booking horizon** becomes a business rule, bounding how far ahead a meeting may be
  created.
- **No Cognito change**, unless the `personId` claim is adopted later.
- **Storing ids as binary** (16 bytes) rather than 36-char strings would raise the per-day ceiling
  from ~1,000 to ~1,545 meetings; UUIDs are 63% of the payload. Not proposed, recorded as available
  headroom.

## Technical considerations

- **The template change is a prerequisite**, not a detail — nothing selection-aware works until
  `selectionSetList` is explicitly serialised.
- **Treat the resolver layer as a rewrite, not a refactor.** `MeetingRecord`'s split from `Meeting`
  exists to model "id-only as persisted" against "resolved for the response"; with day items and
  selection-aware fetching, that distinction is drawn in a different place, and the types should be
  redrawn rather than adapted. The same applies to `ResolverDispatchHandler`'s routing key and to
  `BatchLoader`'s interface.
- **Aliases defeat naive field matching.** Fail toward fetching. Unit-test the selection logic
  against recorded `selectionSetList` payloads, not only through end-to-end queries.
- **Non-null propagation turns a stub/selection mismatch into silent data loss**, not a degraded
  response.
- **Subject length is currently unbounded, and so are room and person names.** Only `subject` sits
  inside the day item, so it is the one that threatens the size guarantee — but the same absence of a
  bound applies to `RoomInput.name` and `PersonInput.name`, and closing all three together is
  cheaper than revisiting the question later.
- **The chosen day limit binds before room capacity does.** `production` has **10 rooms**, and
  business hours of 08:00–17:00 on 15-minute boundaries give 36 slots per room — a physical capacity
  of **360 meetings per day**. A limit of 200 therefore refuses bookings while rooms are still free,
  which is a confusing failure to explain to a user.
  The item cap is not what forces this. A meeting costs roughly `258 + 37 × attendees` bytes, so a
  physically-full day of 360 meetings at 20 attendees is ~359 KB — it *fits*, at 88% of the cap with
  little headroom. Resolving this means picking one of: raise the day limit to at least `rooms × 36`
  and accept the tighter margin; keep 200 and accept that it binds first; or lower the attendee limit
  (at 80% of the cap and 10 rooms, the arithmetic allows ~17 attendees). Recorded as an open question
  rather than decided unilaterally.
- **The limits need their own error codes.** `MeetingError` gains cases for the absolute day limit,
  the per-organiser daily limit, the attendee limit, the subject length limit, and the booking
  horizon. All are validation failures a client must be able to render, not exceptions — a user who
  hits one should see a sentence, never a 500.

### The item-size guarantee

The requirement is absolute: **there must be no input a user can construct that produces a DynamoDB
item over 400 KB.** Meeting it needs the limits to be provably consistent with each other, not merely
individually sensible. The invariant is:

```
dayLimit × (perMeetingBase + 37 × attendeeLimit + subjectMaxBytes) + overhead  ≤  safetyFraction × 400 KB
```

Enforced at three layers, because any one of them alone can be defeated by a later change:

1. **At deploy.** The handler asserts the invariant during initialisation and refuses to start if the
   configured limits cannot fit. SnapStart makes this land in exactly the right place: publishing a
   version *executes init*, so an inconsistent set of limits fails the **deploy**, not a user's
   booking. This is what stops the guarantee decaying when someone later raises a limit, or adds a
   field to the persisted meeting shape without revisiting the arithmetic.
2. **At validation.** Per-request checks on day count, organiser count, attendee count, subject
   bytes, and horizon, each returning a `MeetingError`.
3. **At write.** The serialised item is measured immediately before `PutItem` and rejected if it
   exceeds the safety threshold. This is the backstop that holds even if the byte model itself is
   wrong — and it will drift, because the model is an estimate of DynamoDB's own accounting.

Without layer 1 the guarantee is a comment; without layer 3 it depends on an estimate being exact.

- **The day-count check is a read-modify-write.** Two concurrent creates can both observe 199 and both
  decide they fit. The conditional write on the day item's version attribute resolves it: the loser
  retries and re-validates against the updated count, rather than re-validating against a stale read.
- **Write amplification.** Adding one meeting rewrites the whole day: on-demand billing is 1 WRU per
  KB, so a full 400 KB day costs ~400 WRU per booking against roughly 10 today. At demo scale a day
  is ~20 KB and this barely matters, but it grows linearly and the last booking pays for every
  earlier one.
- **Write contention is the sharper risk.** One item per day means read-modify-write with a version
  attribute and conditional-write retry, replacing today's lock-free independent `PutItem`s.
  `DemoData`'s parallel creates would collide immediately — which the day-scoped bulk mutation
  resolves.
- **The 15-second Lambda timeout** needs checking against a bulk create; validation should get
  faster (load the day once, check overlaps in memory) but that is an assumption to measure.
- **Subscriptions bill per delivery, per subscriber.** Filtering to the days a client is displaying
  is a cost control, not just a correctness one.
- **What this leaves behind.** Subscriptions add AppSync real-time connection logging to the existing
  log group, which already has a retention policy — no new unbounded store. The day items replace
  per-meeting items rather than adding to them. Nothing in this design creates a new class of
  artefact that accumulates without a bound.

## Testing impacts

- **Cross-user real-time tests are new machinery.** No spec under `webapp/tests/` currently uses
  `browser.newContext()`; every test runs in the single storage state from `auth.setup.ts`. Testing
  that user A's booking appears on user B's screen needs two contexts with separate storage states,
  asserting B's DOM updates with no navigation or reload. Both users already exist —
  `e2e_user_email` and `demo_user_email` are Terraform outputs — so no new Cognito plumbing.
- **Existing acceptance tests change, not just grow.** Anything that depends on `ListMeetings`
  argument shapes or on the `createdMeeting` router-state handoff will need rewriting.
- **The size guarantee needs tests that assert the guarantee, not the limits.** Specifically: build a
  day at *every* cap simultaneously — the day limit's worth of meetings, each with the attendee limit
  and a maximum-length subject — then serialise it and assert the real byte size is inside budget.
  That test fails if anyone adds a field to the persisted meeting shape without revising the limits,
  which is the actual regression to guard against.
- **Boundary tests on each rule**: at the limit succeeds, one past it returns the right
  `MeetingError` rather than an exception. Including the per-organiser limit, which needs a second
  organiser in the same day to prove it is scoped per person and not per day.
- **A multi-byte subject test.** A subject of emoji at the character limit but four times the byte
  limit must be rejected — this is the test that proves the limit counts bytes, and it is the one
  most likely to be missed.
- **A test that the deploy-time assertion actually fires** on a deliberately inconsistent set of
  limits, since it is the layer that keeps the guarantee true over time.
- **An acceptance test that a user hitting the organiser limit sees a rendered message**, not a
  server error.
- **Unit coverage for selection parsing**, driven by recorded payloads including aliases and
  fragments.
- **`DatabaseReset` interacts with connected subscribers** — see the blocking open question.

## Documentation impacts

- `docs/reference/data-model.md` — day-keyed storage, GSI removal, participants table outcome.
- `mootmaker-api/api/` schema documentation strings, which are extensive and load-bearing.
- `mootmaker-api/testing-strategy.md` and `mootmaker-webapp`'s equivalent — the multi-context test
  layer.
- `docs/reference/running-costs.md` — real-time charges are a new line item.
- Note: `designs/README.md` currently states "there is no longer a long-lived `test` environment",
  which stopped being true on 2026-09-03. Worth fixing, though not part of this design.

## Rollout & migration

**No migration. `test` and `production` are destroyed in full and redeployed.** Every table, every
Cognito user pool, every user. No backfill, no dual-read period, no reverse-migration path.

Destroying the pools resolves the Person/Cognito linkage question by removing both sides of it. What
comes back is created by Terraform:

- `aws_cognito_user.e2e` and `aws_cognito_user.demo` are recreated automatically, with **new
  passwords** from their `random_password` resources. Those flow to the webapp through Terraform
  outputs, so nothing needs updating by hand.
- The acceptance-test M2M client secret rotates too. `mootmaker-demo-data` reads its credentials from
  the SSM parameters `mootmaker-api` publishes under `/mootmaker/<environment>/demo-data/`, so the
  api deploy must complete before demo-data runs — which the pipeline already orders correctly.
- No user pool carries `deletion_protection`, so nothing blocks the destroy.

**Verified 2026-09-07:** `production`'s pool contains exactly two users, `e2e-tests@example.com` and
`demo@mootmaker.com` — both Terraform-managed. There are currently no real signed-up accounts to
lose. That is a fact about today, not a guarantee about the day this runs.

Staging is otherwise conventional: ephemeral environment first, then `test`, then `production`
through `release.yml`. The schema changes are not backward-compatible for a deployed webapp, so API
and webapp must ship together — which the release pipeline already does.

## Risks

- **Everything is gone, deliberately** — meetings, rooms, people, and every Cognito account. Anyone
  who has signed up between now and the day this runs loses their login, not just their data, and
  finds out by being unable to sign in. Re-check the pool's user list immediately before running it;
  two Terraform-managed users is the current state, not a standing property.
- **Recreating a Cognito user pool domain can stall.** `aws_cognito_user_pool_domain` uses
  `<prefix>-<account-id>`, which is globally unique across AWS. Destroying and immediately recreating
  the same domain name is the one step in this teardown with a known tendency to fail or need a wait,
  and it sits on the critical path for the OAuth2 token endpoint the M2M clients use.
- **Reverting is a redeploy, not a rollback.** With no migration there is also no reverse migration:
  going back means deploying the previous version against freshly recreated tables. Cheap, but not
  transparent — the same data loss happens again in the other direction.
- **Broadcast visibility becomes load-bearing.** Subscriptions push to everyone matching the filter.
  That is safe only while every user may see every meeting. This design should not be built on if
  meeting privacy is anticipated.
- **Write contention on a day item** is a new failure mode with no current analogue.
- **The day ceiling is a hard rejection.** Without enforced limits and a deliberate answer at ~80%
  capacity, the first symptom is a failed booking.

## Implementation checklist

Sparse while Drafting — to be filled in properly before this reaches Ready.

- [ ] `[Geoff]` Choose the top-level query shape — the only substantial question still open.
- [ ] `[Geoff]` Resolve the day-limit / room-capacity conflict, and set the booking horizon's length.
- [ ] `[Claude]` Change the resolver request template to serialise `selectionSetList`, in whatever
      payload shape the new handlers want.
- [ ] `[Claude]` Make `ListMeetingsHandler` selection-aware, with unit tests driven by recorded
      payloads including aliases. Independently shippable and valuable on its own — it removes an
      existing over-fetch where `meetings { id subject }` still batch-loads every room and person.

## Definition of done

The feature's own acceptance coverage — including the two-context real-time test — is green; the
existing acceptance suite is still green on a real deployed environment; every touched repo's unit
tests pass; both environments have been destroyed in full, redeployed from nothing and repopulated
by `mootmaker-demo-data`, with the result verified by direct DynamoDB and Cognito reads rather than
by exit codes; no code remains that
exists only to preserve a shape from the previous design; and everything under Documentation impacts
is actually done.
