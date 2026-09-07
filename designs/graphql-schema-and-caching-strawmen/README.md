# Straw men: two shapes for the top-level query

Supporting material for [`../graphql-schema-and-caching.md`](../graphql-schema-and-caching.md),
whose one substantial open question is the shape of the entry points. These are two complete,
readable versions of it rather than a description of one.

| File | What |
|---|---|
| [`shared-types.graphql`](shared-types.graphql) | Everything not under comparison. **Identical in both.** |
| [`option-a-composite.graphql`](option-a-composite.graphql) | One composite `workspace` entry point |
| [`option-a-client.graphql`](option-a-client.graphql) | What the webapp sends under A, including mutations |
| [`option-b-root-fields.graphql`](option-b-root-fields.graphql) | Sibling root fields |
| [`option-b-client.graphql`](option-b-client.graphql) | What the webapp sends under B |

The mutations are byte-identical between the two — they are not what is being compared, and both
options want the same answer there. A diff of the two schema files shows only `Query`.

## The difference in one line

Both send **one HTTP request**. Option A costs **one Lambda invocation**; Option B costs **one per
root field**, resolved in parallel.

## Invocations per scenario

| Scenario | Option A | Option B |
|---|---|---|
| Page load | **1** | **5** |
| Calendar, page back a week | 1 | 1 |
| Room availability, change day | 1 | 1 |
| Open Add Meeting | **0** | **0** |
| Suggest a room | 1 | 1 |
| Create a meeting | 1 | 1 |
| Open a meeting link | 1 | 1 |

They differ in exactly one place: **the first request of a session.** Everything after it asks for
one kind of thing, and one root field is one invocation either way.

That matters less than it did. The concurrency quota went from 10 to 1,000 on 2026-09-07, so five
parallel invocations no longer approach saturation. What remains is five SnapStart restores instead
of one on a cold API, and five times the compute for the same page.

## Where each is ugly

**Option B** pays five invocations and five SnapStart restores for the one request that most decides
perceived load speed, and splits `me`, `boundaries`, `rooms` and `people` across four handlers doing
four trivial things.

**Option A** had one wart — `rooms` and `people` hanging off a field that required a `dates`
argument, so a reference-data-only refresh had to pass an invented empty list. **Making `dates`
optional deletes it**: omitting the argument means no days are wanted, and the resolver skips that
work exactly as it skips people and rooms when they are not selected. With that fixed, A has no
remaining wart that B does not also have.

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

That has a consequence for how components are written. The query result now contains **only the
missing days**, so the calendar cannot render from it — it renders from the cache, one entity per
cell:

```ts
const { data } = useFragment({ __typename: 'Day', from: `Day:${date}`, fragment: DAY_FIELDS })
```

Which is a gain, not a tax: each cell is independently reactive, so a subscription updating one day
re-renders one cell rather than the grid.

## What each needs from the Apollo cache

**Both** need `Day` normalised on `date` — the decision that makes an empty day distinguishable from
an unfetched one, and the thing the gap check above reads:

```ts
Day: { keyFields: ['date'] }
```

**Both** also need `keyArgs: false` on the day-bearing field, for a reason that is easy to miss:
every distinct `dates` array is otherwise its own `ROOT_QUERY` entry. Because the array now varies
with every navigation, those slots accumulate — junk that never gets read, since rendering happens
through `useFragment`. Collapsing them to one slot is garbage control rather than a read strategy.

**Option B** — one field policy, and that is all:

```ts
Query: {
  fields: {
    days: {
      keyArgs: false,                        // one slot, not one per date array
      merge(existing = [], incoming, { readField }) {
        const byDate = new Map(existing.map((d) => [readField('date', d), d]))
        for (const d of incoming) byDate.set(readField('date', d), d)
        return [...byDate.values()]
      },
    },
  },
}
```

`rooms`, `people`, `me` and `boundaries` need nothing — they take no arguments, so each is already a
single stable cache field.

**Option A** — the same idea on `workspace`, but one `merge` has to handle four sub-fields with
different semantics: `days` accumulates, while `people`, `rooms`, `me` and `boundaries` replace.

```ts
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

Without `keyArgs: false` here, every distinct date array gets its own `workspace` slot and the same
rooms and people are cached repeatedly under each.

## Subscriptions: identical in both, and constrained

The payload is the same either way — `Subscription` is a root type in both options, and the mutations
are byte-identical. But two AppSync constraints shape it, and an earlier draft of these files got
both wrong.

**`@aws_subscribe` pushes the mutation's return value, and the subscription field's type must match
the mutation's return type.** A subscription typed `Day` against a mutation returning
`CreateMeetingResult` does not deliver.

**A rejected `createMeeting` still returns successfully at the GraphQL level** — validation failures
are a typed `errors` array in the payload, not a transport error. So a subscription attached directly
to `createMeeting` broadcasts failed bookings too.

Two ways out, written out in the schema files:

| | Subscribe to the wrapper | A publish-only mutation |
|---|---|---|
| Payload | `CreateMeetingResult`, clients select `day` | `Day` |
| Broadcasts failures | Yes | No |
| Covers `createMeetings` too | No — different result type | Yes, one channel |
| Cost | None | An IAM-signed call from the resolver back to AppSync, and a mutation clients must not call |

**The publish-only mutation is recommended.** It is deferred either way: history deletion
deliberately does not broadcast, so nothing in the first cut depends on settling this.

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

## Recommendation: Option A

Reversed from an earlier draft of this file, which recommended B. Three arguments were doing that
work and none of them survives contact:

**"B parallelises across invocations."** So does A, inside one. `ListMeetingsHandler` already runs
its rooms and people loads concurrently with `CompletableFuture`, and these are I/O-bound DynamoDB
calls, so threads blocked on network parallelise fine even at 512 MB where a Lambda has well under a
full vCPU. B's five invocations do the same concurrent work in five execution environments, paying
five SnapStart restores and five times the compute for the same wall clock.

**"B's cache configuration is materially simpler."** Overstated. A's merge is one extra object
spread:

```ts
merge(existing = {}, incoming) {
  return { ...existing, ...incoming, days: unionByDate(existing.days, incoming.days) }
}
```

Both need the same `unionByDate` and the same `keyArgs: false`. That is not a material difference.

**"B is the shape a public API would take."** There is one known client, and the design explicitly
refuses to carry decisions for hypothetical consumers. This should not have been weighed at all.

What is left for B is that each entry point reads independently, which is aesthetic, against A's one
invocation and one restore on the request that decides how fast the app feels. A also keeps the door
open to sharing work inside the invocation if a screen ever does want nested names alongside the
collections — five handlers cannot share anything.

**Honest caveat**, since it is the one thing A gives up: a single invocation holds the whole response
in memory and has one 15-second timeout for all of it, where B has 15 seconds each. At the design's
worst case — 40 days at 320 meetings — that is a large object. At production's real shape, ~20
meetings a day, it is nothing. Worth measuring rather than assuming, but not a reason to prefer B.
