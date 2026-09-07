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

**Option A** has no clean way to ask for reference data alone. `rooms` and `people` hang off a field
that requires a `dates` argument, so a refresh of just those two has to pass an invented empty range
(`option-a-client.graphql` §4). It is a small wart on a rare call, but it is the honest cost of
hoisting arguments up to the composite field — which itself is not optional, because AppSync gives a
resolver its *own* arguments typed and nested field arguments only as raw GraphQL text.

**Option B** pays five invocations for the one request that matters most for perceived speed, and
`me`, `boundaries`, `rooms` and `people` are four separate handlers doing four separate trivial
things.

## What each needs from the Apollo cache

This is the real complexity difference, and it is larger than the schemas suggest.

**Both** need `Day` normalised on `date` — the decision that makes an empty day distinguishable from
an unfetched one:

```ts
Day: { keyFields: ['date'] }
```

**Option B** then needs one more field policy, so that separately-fetched ranges accumulate into one
canonical set of days rather than one cache entry per range:

```ts
Query: {
  fields: {
    days: {
      keyArgs: false,                       // one slot, not one per DateRange
      merge(existing = [], incoming, { readField }) {
        const byDate = new Map(existing.map((d) => [readField('date', d), d]))
        for (const d of incoming) byDate.set(readField('date', d), d)
        return [...byDate.values()]
      },
      read(all, { args, toReference }) {
        // Missing date => cache miss => fetch. A present-but-empty Day is a hit.
        const wanted = datesIn(args.dates)
        const refs = wanted.map((date) => toReference({ __typename: 'Day', date }))
        return refs.every(Boolean) ? refs : undefined
      },
    },
  },
}
```

`rooms`, `people`, `me` and `boundaries` need nothing at all — they take no arguments, so each is
already a single stable cache field.

**Option A** needs the same treatment on `workspace`, but harder, because one merge function has to
handle four sub-fields with different semantics: `days` accumulates, while `people`, `rooms`, `me`
and `boundaries` replace.

```ts
Workspace: { keyFields: false },            // not an entity; inline under ROOT_QUERY
Query: {
  fields: {
    workspace: {
      keyArgs: false,                       // ONE workspace, not one per DateRange
      merge(existing = {}, incoming) {
        return {
          ...existing,
          ...incoming,                      // replace me/people/rooms/boundaries when present
          days: unionByDate(existing.days, incoming.days),
        }
      },
    },
  },
}
```

Without `keyArgs: false` here, every distinct date range gets its own `workspace` slot and the same
rooms and people are cached repeatedly under each — the "empty vs unfetched" trap in a new costume.

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

## Recommendation, held loosely

**Option B**, on three grounds:

1. The invocation difference applies to **one request per session**, and the quota rise removed the
   argument that made it urgent.
2. Its cache configuration is materially simpler — one field policy against one that has to treat
   four sub-fields differently — and cache configuration is where this design is most likely to go
   subtly wrong.
3. It has no equivalent of the invented empty date range.

The case for **Option A** is real and worth weighing: one invocation on the request that decides
perceived load speed, one SnapStart restore instead of five, and a schema that says plainly "this is
what a screen needs". If cold-start latency on first paint turns out to be the thing users notice, A
is the better answer and B cannot be tuned into it.

What would settle it: measure a cold page load both ways. That is a real experiment, not a
preference — and it is cheap now that an ephemeral environment can be stood up without fighting a
concurrency limit.
