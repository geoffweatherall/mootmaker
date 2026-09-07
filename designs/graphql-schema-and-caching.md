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
11. **Retention of at least 30 days, against a stored Monday-aligned boundary** *(Decided)* — deleted
    by a weekly scheduled Lambda, with **no TTL anywhere**, so it can broadcast cache invalidation and
    delete each day with its pointers in one transaction. The boundary advances *before* anything is
    deleted, so what is advertised is never more permissive than what exists. See "Retention".
12. **Enforced size limits, with an oversized item made unreachable** *(Decided)* — **320 meetings
    per day, 20 attendees per meeting, 280-byte subjects.** Enforced at three layers so that no input
    a user can construct produces an item over 400 KB. See "The item-size guarantee".
13. **Destroy and rebuild both environments** *(Decided)* — no migration, Cognito pools included.
14. **Whether reset becomes a mutation** *(Reopened)* — it was decided, on the grounds that a mutation
    broadcasts. History deletion has since dropped its own notification, and `Mutation.reset` turns
    out to have been deliberately removed because any signed-in user could call it. See Open
    questions.

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

**Reset becomes a mutation behind RBAC — but this now needs revisiting.** The reason for routing reset
through GraphQL was that it would then broadcast, so connected clients evict instead of silently
showing deleted data.

Two things undercut it. First, history deletion has since dropped its own notification on complexity
grounds; the same reasoning applies here. Second, and more seriously, **`Mutation.reset` already
existed and was deliberately removed.** Per `mootmaker-api`'s README, it was *"callable by any signed
-in user, which the business functionality doc called out as a known gap"*, and replacing it with the
IAM-authenticated `database-reset` Lambda closed that gap *"since invoking it needs an explicit AWS
permission grant rather than just being signed in to the product"*.

Reintroducing it as a mutation would undo that, and an in-product RBAC role is a **weaker** boundary
than requiring an AWS permission grant. Recorded as a blocking open question rather than left as a
decision that quietly reverses prior work.

**Maximum subject length — a rule that does not exist today.** `CreateMeetingHandler` checks only
that `subject` is non-blank. There is no upper bound, so a single meeting can carry a subject of any
size and blow the item on its own, regardless of how few meetings the day holds. **No count-based
limit can deliver the "no oversized item" guarantee while this term is unbounded.**

**280 bytes, taking a tweet as the anchor and measuring in UTF-8.** UTF-8 because **DynamoDB itself
sizes string attributes in UTF-8 bytes** — validating in the same unit the storage bills in makes the
limit and the item cost the same quantity, rather than two numbers that can drift apart. Plain
English text gets the full 280 characters; a subject written in simple emoji gets 70, because each
costs four bytes. This is a
deliberate trade: measuring characters instead would mean budgeting 1,120 bytes for every meeting on
the chance that one of them is emoji, which costs roughly 40% of the day's entire capacity to buy a
promise almost nobody exercises. The user-facing counter should count down in the same units it
enforces, so someone pasting emoji sees the budget fall faster rather than being rejected on submit.

**Day limits: 320 meetings, 20 attendees.** A meeting costs `212 + 37 × attendees + subjectBytes`, so
the worst case is `212 + 740 + 280 = 1,232` bytes and a full day is ~394 KB, or **96% of the 400 KB
cap**. That is deliberately tight: the write-time byte measurement (layer 3 below) measures the
*actual* serialised item, so an error in this byte model produces a clean "day is full" rejection
rather than a DynamoDB failure. Headroom buys nothing that layer 3 does not already provide.

**No per-organiser limit.** Considered and dropped: the absolute day cap is the only rule that bounds
the item, and a per-organiser cap would have been a fairness control rather than a safety one. One
user filling a day is an acceptable outcome on a demo system.

**The day cap can still bind before the rooms are full, but only just.** Ten rooms across 36
fifteen-minute slots give a physical capacity of 360 meetings a day, so 320 refuses a booking with
rooms free — but only once the building is 89% full, against 53% under the earlier 200-meeting
figure. Closing the gap entirely is possible by lowering the attendee limit to 16, which makes a
physically-full 360-meeting day fit at 95%; that trade is available if the cap ever actually binds.
In practice it will not: `production` holds **508 meetings in total** and `mootmaker-demo-data`
creates roughly 20 a day.

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

- **320 meetings per day, at 96% of the item cap.** You said headroom was not needed given how
  accurate the test is, and the arithmetic allows up to 332. I took 320 as a round number under that.
  Raising it to 330 is defensible; the write-time byte check makes either safe.
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

**Should reset become a mutation at all?** See Trade-offs. Its only benefit was broadcasting, which
history deletion has now dropped for itself, and it would reverse a deliberate hardening: reset was
moved *out* of GraphQL precisely because any signed-in user could call it. Leaving it as an
IAM-invoked Lambda keeps the stronger boundary and makes #76's RBAC work valuable on its own terms
rather than a prerequisite. If reset stays IAM-only, connected clients are not told about a reset —
the same accepted gap as history deletion.

**The booking horizon's length.** Retention is set at 30 days; the horizon is not set. Together they
fix the hard bound on how many day items can exist, so the horizon is the last number the storage
bound is waiting on.

*(The cleanup job's broadcast question is settled — see "Retention". It does not broadcast, for now.)*

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
- **The day limit is a real cap, and its failure must read as such.** Physical capacity is 360
  meetings a day against a limit of 320, so a user can be refused while a room stands free. The
  `MeetingError` needs to say the *day* is full, not the room — otherwise it is an unexplainable
  rejection.
- **Subject length must be measured in UTF-8 bytes, not `String.length()`.** Java strings are UTF-16,
  so `length()` counts code *units*: an emoji outside the Basic Multilingual Plane counts as 2 there
  and 4 in UTF-8. Neither number is the other. `subject.getBytes(UTF_8).length` is the only correct
  measure, and it is the one the size budget is built on.
- **Normalise to NFC before measuring and storing.** "é" is either one code point (2 bytes) or "e"
  plus a combining accent (3 bytes), depending on the writer's keyboard and OS. Without
  normalisation two visually identical subjects have different byte counts and one can be rejected,
  which is unexplainable to the user. The contract is therefore *280 bytes of NFC-normalised UTF-8*.
- **Reject, never truncate.** Cutting a string at a byte boundary can split a character mid-sequence
  and produce mojibake. A client-side counter must truncate on grapheme boundaries, not bytes.
- **"How many emoji fit" has no single answer.** A simple emoji is 4 bytes, but 👨‍👩‍👧‍👦 is four of them
  joined by three zero-width joiners — 25 bytes — and skin-tone modifiers add 4 each. So the range is
  roughly 70 down to 11. This does not threaten the budget at all: 280 bytes is 280 bytes whatever it
  holds, so the item arithmetic stays exact and the variability lands on the user's character
  counter, which is the right place for it.
- **The limits need their own error codes.** `MeetingError` gains cases for the day limit, the
  attendee limit, the subject length limit, and the booking horizon. All are validation failures a client must be able to render, not exceptions — a user who
  hits one should see a sentence, never a 500.

### Retention: the bill stays flat under steady usage

`principles.md`'s **"Nothing accumulates without a bound"** requires that under steady usage the bill
is flat. Meeting history is the one place mootmaker currently breaks it — meetings are written and
never deleted, so storage grows with time rather than with usage.

**Historic meetings are kept for at least 30 days**, bounded by a **stored** earliest-retained date
rather than one computed from the clock.

The date is held as a config item in the meetings table, always aligned to a **Monday**, and read
with `ConsistentRead`. Consistency is not incidental: an eventually-consistent read could return a
stale, *more permissive* boundary, which is exactly the failure the ordering below exists to prevent.

Monday alignment means the calendar's week windows and the boundary are the same kind of thing, so
"is this week reachable" is an exact comparison rather than a straddling judgement. The cost is that
retention becomes a range — between 30 and 37 days depending on where in the week the job falls — so
**the storage bound uses 37 as its worst case**.

#### The cleanup order, and why it is that way

Each run, in this order:

1. **Advance the stored date** to the appropriate Monday.
2. *(Deferred)* **Notify clients**, on the same subscription channel as every other write, so they
   evict `Day` entities before the new boundary.
3. **Delete the data** before it — day items and their `id → date` pointers, transactionally.

(Step 2 is deferred — see "It does not notify clients" below. The ordering of 1 and 3 is what
matters, and it stands on its own.)

The invariant this protects is that **the advertised boundary must never be more permissive than
reality**. Deleting first would open a window where the stored date still promises data that is
already gone, and clients asking for those days get empty results indistinguishable from "nothing was
booked". Advancing first opens the opposite window — data that still exists but is no longer
advertised — which is harmless. The ordering holds even if the job dies between steps, which is the
real test of it.

It is also catch-up safe: a job that has not run for weeks advances to the correct Monday and deletes
everything before it, in one pass, with one notification.

**Deletion is an explicit weekly operation, not a DynamoDB TTL.** TTL is the obvious answer and it is
the wrong one here, for four reasons:

0. **TTL bakes the policy into the data.** The expiry attribute is written per item, so changing the
   retention window means rewriting every existing item to correct a value that is now wrong. A
   scheduled job reads the policy at run time, so changing retention is a config change. The
   attribute's value is also a function of the *meeting's* date rather than the write time, which is
   one more thing to compute correctly on a path where getting it wrong deletes real data.

1. **TTL cannot tell anyone.** A connected client holding `Day:2026-08-08` learns nothing when that
   day disappears. An operation can broadcast on the same subscription channel as every other write,
   which is the same argument that makes reset a mutation rather than a side door.
2. **TTL is not atomic across items.** The day item and its `id → date` pointers would expire
   independently, so `meeting(id:)` can resolve a pointer whose day is already gone. An operation
   deletes the day and its pointers in one transaction, so the inconsistency window does not exist.
3. **TTL is not even a read boundary.** Deletion is best-effort within roughly 48 hours of expiry,
   and — the part that is easy to miss — **expired-but-not-yet-deleted items are still returned by
   reads**. "Older than 30 days is gone" would therefore be false in the data, and every read path
   would need to filter on the expiry attribute anyway. Application-level filtering plus TTL is
   strictly more code than an explicit delete, for a weaker guarantee.

TTL's real advantage is that deletes cost zero WCU. That matters when expiring millions of rows; here
it is **seven day items and their pointers per week**, so the saving is nil.

**No TTL at all, not even as a backstop.** An earlier draft kept one at a longer window to protect the
bill if the job broke. That is worse than it looks: a backstop that silently covers for a failed job
means **the failure is never discovered** — the bill stays flat and nothing surfaces. It would also
need a window strictly longer than 37 days or it would delete data the stored boundary still
advertises, breaking the very invariant the ordering exists to protect.

The principle is instead held by **one mechanism plus a check**: if the cleanup has not succeeded
within a defined window, that is a fault to be raised, not absorbed.

**The stored boundary is its own dead-man's switch.** If the job has not run, `earliestRetainedDate`
has not advanced, so "is the stored date within 37 days of today?" detects the exact failure using a
value the system already holds and already returns to clients. No metric, no alarm, no new resource,
no cost. A CloudWatch alarm would add only *automatic* notification, and it is not free — $0.10 per
alarm metric per month, a standing charge that does not scale to zero, against an account currently
running zero alarms and $0 of CloudWatch spend. For a weekly job whose failure mode is gradual
storage growth, the recurring check in #77 is the proportionate answer; an alarm is an optional
convenience to be decided on its own merits.

**Cadence: weekly, on an EventBridge scheduled rule.** It pairs with Monday alignment — one run, one
Monday, one week of data — and the work per run is bounded by construction.

The shape is already proven here: `mootmaker-demo-data`'s `schedule.tf` is an
`aws_cloudwatch_event_rule` with a cron expression, an `aws_cloudwatch_event_target`, and an
`aws_lambda_permission` scoped to that rule with `events.amazonaws.com` as principal. **It costs
nothing** — scheduled rules targeting an AWS service directly are not billed, only publishing custom
events is, and the invocation falls inside Lambda's always-free tier. Confirmed against the bill:
EventBridge does not appear as a line item at all despite demo-data running daily.

Two details worth carrying across. The target should set `input = jsonencode({})` explicitly rather
than letting EventBridge send its own event envelope, so the handler's payload is a contract rather
than an accident. And the rule's `state` should be enabled in `test` and `production` but not in
ephemeral environments, which never live long enough to accumulate anything.

**The cleanup Lambda is simpler than demo-data**, because it talks to DynamoDB rather than the API:
no SSM parameters, no M2M credentials, no Cognito token endpoint. An IAM role with permissions on the
meetings table is the whole dependency list.

**Deployed everywhere, scheduled only where it matters.** The function is deployed in every
environment including ephemeral ones; only the EventBridge rule's `state` differs. Acceptance tests
invoke it directly, exactly as `DatabaseReset` already invokes `database-reset` — `LambdaClient` with
the test runner's IAM credentials, function name from an environment variable `verify.sh` computes
the same deterministic way Terraform names it. Leaving the rule disabled in ephemeral is not only a
cost decision: a schedule firing mid-run would make acceptance tests nondeterministic.

**The job takes an explicit boundary in its payload.** An ephemeral environment created this morning
has nothing 30 days old, so a test cannot exercise the real code path by waiting. Passing the target
Monday in the invoke payload makes the test deterministic and independent of the calendar — and
independent of whether past-dated bookings stay legal, which is itself an open question. This follows
`database-repair`, which already takes `{"dryRun": true}`; a `dryRun` here would likewise let a test
assert what *would* be deleted before anything is. When invoked with no payload, the job computes the
boundary itself, which is what the schedule does.

**It does not notify clients — for now.** Broadcasting would mean either routing the deletion through
a mutation (pulling it into the public schema and the RBAC work in #76) or a separate
broadcast-only call, and neither earns its complexity yet. The consequence is bounded: the ordering
still protects every reader who fetches the boundary *after* it advances, which is every new page
load. Only a session already in flight keeps a stale boundary, and it can then navigate to a
just-deleted week and see it as empty. A refresh corrects it completely — which is exactly the
stateless restart the no-cache-persistence decision guarantees. Worth revisiting once subscriptions
exist and the marginal cost is one more channel.

Retention composes with the booking horizon already decided. The horizon bounds how far *forward* day
items can exist; retention bounds how far *back*. Together the table holds at most
`horizon + retention` items — **a hard upper bound on row count, not merely a cap on the growth
rate.**

Cognito is the one component that legitimately grows, since MAUs track users rather than time —
constant usage keeps it flat, so there is nothing to bound.

**Two consequences the UI has to answer.**

The person calendar's "Previous week" control has **no lower bound** — `setFirstMonday(current =>
current.subtract(7, 'day'))` pages backwards indefinitely. With retention it will walk into weeks
that are empty because the data was deleted rather than because nothing was booked, which is
indistinguishable to the user. It needs a floor at the retention boundary.

**The server publishes that boundary; the client never computes it.** The top-level query returns the
stored `earliestRetainedDate`, and the client disables "Previous week" against it. The alternative —
having the client work out "30 days before today" for itself — puts **two authorities on one fact**:
the deletion job uses the server's date, the browser uses the user's. A user in UTC+13, or with a
skewed clock, then asks for a day the server already considers expired. Padding the client's limit by
a day would hide that disagreement rather than remove it, and a test would not catch it, because the
test would encode the same assumption the code does. Because the date is stored and Monday-aligned,
the comparison is exact rather than exact-if-the-clocks-agree.

**A client already viewing a week that falls out of retention is not moved.** The invalidation
notification updates the boundary and empties the affected days; it does not navigate anyone. Moving
a viewport in response to a background event the user did not cause is the same family of defect as
the layout shifts behind webapp#44, #46 and #50 — the fix for which was, in every case, to stop
things moving underneath the user. The control disables itself where they stand and the empty week
says why. In practice this is close to unreachable anyway: the boundary advances once a week, so a
user would have to be viewing the oldest retained week at the moment the job runs.

A bookmarked or shared link to a meeting older than 30 days stops resolving, and **`meeting(id:)`
simply returns not-found** — the same answer as an id that never existed. No distinct "expired"
result: it is one less state for every caller to handle, and it avoids confirming that a given id was
once valid, which a separate expired response would. The page renders its ordinary not-found state.

### The item-size guarantee

The requirement is absolute: **there must be no input a user can construct that produces a DynamoDB
item over 400 KB.** Meeting it needs the limits to be provably consistent with each other, not merely
individually sensible. The invariant is:

```
dayLimit × (perMeetingBase + 37 × attendeeLimit + subjectMaxBytes) + overhead  ≤  safetyFraction × 400 KB

  320       × (212            + 37 × 20            + 280)           + overhead  ≈  394 KB  (96%)
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
  `MeetingError` rather than an exception.
- **Multi-byte subject tests, in both directions.** 280 ASCII characters is accepted and 281 is
  rejected; **70 emoji is accepted and 71 is rejected**, because each is four bytes. A test using
  only ASCII passes just as happily against a `String.length()` implementation, which is the bug
  this is here to catch.
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
