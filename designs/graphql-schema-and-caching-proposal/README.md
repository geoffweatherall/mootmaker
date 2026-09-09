# The proposed GraphQL schema and cache

Supporting material for [`../graphql-schema-and-caching.md`](../graphql-schema-and-caching.md).
This is a complete, readable version of the proposal rather than a description of one.

| File | What |
|---|---|
| [`schema.graphql`](schema.graphql) | The server schema — types, `Query`, `Mutation`, `Subscription` |
| [`client-operations.graphql`](client-operations.graphql) | Every operation the webapp sends, with its cache behaviour |

Until 2026-09-09 this directory held **two** straw men — a composite entry point and sibling root
fields — written out in full so the choice could be made against something readable. The composite
shape won; the other has been deleted rather than kept as a footnote, per the design's "no decision
is carried forward". "Why this shape" below records what the choice cost, since that is the part
worth keeping.

## The entry point in one line

**One composite `workspace` field**, so a page load is one HTTP request, one Lambda invocation and
one SnapStart restore — against five for the sibling-root-field shape it replaced.

| Scenario | Invocations |
|---|---|
| Page load | 1 |
| Calendar, page back a week | 1 |
| Room availability, change day | 1 |
| **Open Add Meeting** | **0** — rooms and people are already cached |
| Suggest a room | 1 |
| Create a meeting | 1 |
| Open a meeting link | 1 |

## Fetching only what is missing

`days` takes an **explicit list of dates, not a range**. A range cannot express a discontiguous set,
and a discontiguous set is exactly what a warm cache asks for: if Tuesday and Thursday are already
held, the client wants Mon/Wed/Fri and nothing else.

**Apollo will not work that out.** A cache `read` returns either a complete result or `undefined`,
and on `undefined` the query goes to the network **with the variables as given**. There is no
mechanism to rewrite variables to fetch a subset. So the client computes the gap:

```ts
const wanted  = weekdaysOf(visibleWeeks)                       // e.g. Mon..Fri
const missing = wanted.filter((date) =>
  !cache.readFragment({ id: `Day:${date}`, fragment: DAY_FIELDS }))

useQuery(DAYS, { variables: { dates: missing }, skip: missing.length === 0 })
```

**Cache presence must be the only record of what has been fetched.** If the client also keeps a
"dates I've already asked for" set in React state, an invalidation clears the cache but not the set,
the gap check concludes the day is still held, and that client is stale forever — on one machine
only, with no error. Deriving the gap from the cache alone, as above, makes that unrepresentable.

That has a consequence for how components are written. The query result now contains **only the
missing days**, so the calendar cannot render from it — it renders from the cache, one entity per
cell:

```ts
const { data } = useFragment({ __typename: 'Day', from: `Day:${date}`, fragment: DAY_FIELDS })
```

Which is a gain, not a tax: each cell is independently reactive, so a subscription updating one day
re-renders one cell rather than the grid.

## How the Apollo cache actually works here

Worth stating from the ground up, because `apolloClient.ts` is currently a bare `new InMemoryCache()`
with no `typePolicies` at all — everything below is new.

**The model.** The cache is one flat map, not a store of query results. Any object carrying
`__typename` and `id` becomes an **entity** at `<__typename>:<id>` — `Room:abc`, `Person:def`.
Anything without an id is stored **inline in its parent**. Lists become lists of `{__ref: …}`. That
is why a `Room` returned from a mutation updates it on every screen with no work — and why it does
*not* appear in the cached `rooms` list, which is a separate thing entirely.

**Root fields are keyed by their arguments.** `ROOT_QUERY` holds one slot per field *per argument
set*. That is why today's calendar shares nothing between weeks: a new date range is a new slot.

**Three policies carry this design.**

```ts
Day: { keyFields: ['date'] },                // → cache key "Day:2026-09-14"
Workspace: { keyFields: false },             // not an entity; inline under ROOT_QUERY
Query: {
  fields: {
    workspace: {
      keyArgs: false,                        // ONE workspace, not one per date array
      merge(existing = {}, incoming) {
        return {
          ...existing,
          ...incoming,                       // replace me/people/rooms/boundaries when present
          days: unionByDate(existing.days, incoming.days),
        }
      },
    },
  },
}
```

`Day: { keyFields: ['date'] }` is the decision the whole design rests on. A human-readable,
client-derivable key means the webapp can construct `Day:2026-09-14` without a round trip to
discover it — and an entity that is present but empty is distinguishable from one that was never
fetched, which a merged canonical list cannot express without hand-rolled range tracking.

`keyArgs: false` is easy to miss and expensive to omit: without it, **every distinct `dates` array
gets its own `workspace` slot**, and the same rooms and people are cached again under each. Because
the array changes on every navigation, those slots accumulate as junk that is never read — rendering
happens through `useFragment`. Getting this wrong produces a cache that silently refetches
everything on every navigation: slower, not broken, so tests still pass. It deserves its own test.

**One sub-question still open.** `days` is written above as an accumulating `merge`. The alternative
is a `read` policy that maps `args.dates` onto constructed refs:

```ts
days: { read: (_, { args, toReference }) =>
  args.dates.map((date) => toReference({ __typename: 'Day', date })) }
```

That never accumulates, leaves no dangling references after an eviction, and makes
`workspace.days` mean "the days I asked for" rather than "every day this session has ever seen". The
`merge` version is the one written up and it works; the `read` version looks better and has not been
tried. Worth resolving before the cache work starts, not during it.

## Subscriptions

**The broadcast carries invalidated dates, never data.** AppSync caps a subscription payload at
240 KB against 5 MB for a resolver response, and a worst-case `Day` is ~618 KB of JSON — so a
broadcast cannot carry a day even though a mutation response can. Beyond fitting the cap: the
payload is uniform and tiny whatever the day holds, one channel serves every kind of change, and it
is idempotent, where merging the same meeting twice would need deduplication.

**Delivered by a publish-only mutation**, not by subscribing to `createMeeting` directly. Two
AppSync constraints force this, and an earlier draft of these files got both wrong:

- `@aws_subscribe` pushes the **mutation's return value**, and the subscription field's type must
  match the mutation's return type. So one subscription cannot cover `createMeeting` and
  `createMeetings`, whose result types differ.
- **A rejected `createMeeting` still returns successfully** — validation failures are a typed
  `errors` array, not a transport error. Subscribing to it directly would broadcast failed bookings.

`publishDaysInvalidated` sidesteps both, at the cost of an IAM-signed call from the resolver back to
AppSync and a mutation clients must not call.

**Reference-data invalidation is deferred.** A new Room or Person will not appear on anyone's open
page until they refresh. `Invalidation` is a wrapper object specifically so `rooms`/`people` flags
can be added later — adding a field to a GraphQL output type is backward compatible, where typing
the subscription as a bare `[String!]!` would have made it a breaking change. That is the one thing
locked in now; everything else about it can wait.

**The hazard worth designing for.** A writes at t0; B's fetch for that date was issued at t−1 and
lands at t+1 carrying pre-write data, *after* B evicted at t0. B is now stale with nothing left to
trigger a refetch. A per-date "last invalidated at" marker, re-evicting when a response was
requested before it, closes it. This is the shape of bug that surfaces as an intermittent
cross-client test failure rather than a reproducible one.

## Mutation payloads, and what actually updates the cache

The thing worth looking at hardest, and where I got something wrong first time.

**Apollo auto-merges entities, not lists.** A mutation returning a `Room` updates `Room:<id>`
everywhere it is referenced. A mutation returning a *list* of rooms normalises its members but does
**not** append them to `ROOT_QUERY.rooms`, which is a different cache field.

So there are two classes of mutation here, and only one is free.

### Meetings — genuinely update-function-free

`createMeeting` returns the whole affected `Day`. Because `Day` is a normalised entity keyed by
`date`, and `meetings` is a field *on* that entity, writing the returned Day **replaces the cached
day's meeting list outright**. No `update`, no `refetchQueries`, no client code that knows a meeting
belongs to a day.

It also removes the read-after-write hazard by construction: the response *is* the new state, so
nothing is re-read. Both existing workarounds — the router-state handoff in `AddMeetingPage` and the
`createdMeeting` merge in `RoomAvailabilityPage` — delete outright.

**Three payload shapes, and why the middle one wins:**

| Returns | Size (typical day) | Size (worst case) | Client code |
|---|---|---|---|
| `meeting { id }` | ~50 B | ~50 B | An `update` that finds the day and appends |
| **`day { … }`** | **~4 KB** | ~290 KB | **None** |
| whole `workspace` | ~30 KB | — | None, and wasteful |

Typical is production's real shape: ~20 meetings a day, each with id, subject, two timestamps and
three id references. Worst case is a day at the 320-meeting limit with 20 attendees each — reachable
only at 89% of the building's physical capacity.

And on the path that matters it is not extra data at all: `AddMeetingPage` navigates to the room
availability view **for that date** on success, which needs exactly this day. Returning it is the
next screen's query arriving early.

A caller with nowhere to navigate simply does not select `day`, and the selection-aware resolver does
not build it. One mutation, two costs, chosen by the caller.

### Rooms and people — a one-line update, no refetch

These return the whole collection, and still need an `update` — but a trivial one, because
everything it needs is already in the response:

```ts
update(cache, { data }) {
  cache.writeQuery({ query: ROOMS, data: { rooms: data.createRoom.rooms } })
}
```

Still strictly better than today's `SettingsPage`, which merges a single item into the cached list
*and* fires a refetch because the merge alone is not sufficient. Here the server's list is
authoritative and replaces the cached one wholesale: no refetch, no merge logic, no race between the
two.

## Why this shape, and what it gives up

The composite field was chosen over sibling root fields on 2026-09-09, reversing an earlier draft of
this file that recommended the siblings. Three arguments were doing that work and none survived
contact:

**"Siblings parallelise across invocations."** So does the composite, inside one.
`ListMeetingsHandler` already runs its rooms and people loads concurrently with `CompletableFuture`,
and these are I/O-bound DynamoDB calls, so threads blocked on network parallelise fine even at
512 MB where a Lambda has well under a full vCPU. Five invocations do the same concurrent work in
five execution environments, paying five SnapStart restores and five times the compute for the same
wall clock.

**"The cache configuration is materially simpler."** Overstated as an argument about the *queries* —
the difference there is one object spread. But it was not wrong about the *cache*: `keyArgs: false`
plus the merge above is genuinely the load-bearing part of this design's client work, and it is
where the composite shape spends what it saves. Sibling fields would each have been a single stable
cache slot needing nothing.

**"It is the shape a public API would take."** There is one known client, and the design explicitly
refuses to carry decisions for hypothetical consumers. This should not have been weighed at all.

**Two things given up, both accepted deliberately:**

**Partial failure.** One non-null field erroring nulls the whole `Workspace`, so a `days` overflow
loses `rooms` and `people` with it, where sibling fields would have degraded. Accepted because the
client constructs the request: `maxDates` (42) is a bound a well-behaved client never trips, and
`maxMeetingsPerResponse` (2,000) is a backstop that should be unreachable against production's 508
meetings in total. Wrapping `days` in a result type to buy this back was considered and rejected as
not worth the schema cost.

**One timeout for the whole response.** A single invocation holds the whole response in memory and
has one budget for all of it — 25 s, set below AppSync's unadjustable 30 s so the Lambda fails first
with a diagnosable error rather than being orphaned. At the design's worst case that is a large
object; at production's real shape, ~20 meetings a day, it is nothing. Worth measuring rather than
assuming.
