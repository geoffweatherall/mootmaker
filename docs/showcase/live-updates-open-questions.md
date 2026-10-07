# Live updates: answers to the open questions

The [live-updates talk](live-updates-talk.md) ends with four questions for discussion. These are
suggested answers, with the reasoning and evidence behind each, to bring to that discussion. They are
recommendations, not decisions: none of them has been agreed or built.

The [companion write-up](live-updates-deep-dive.md) explains every mechanism mentioned here.

| Question | Short answer |
|---|---|
| [1. Is 5 seconds the right own-write window?](#1-is-5-seconds-the-right-own-write-window) | It's a reasonable heuristic. Its failure modes are mild. Replace it with an origin id when the schema next changes |
| [2. Is it OK that every signed-in client receives every broadcast?](#2-is-it-ok-that-every-signed-in-client-receives-every-broadcast) | Yes, on privacy and on cost, for the foreseeable future. Partition by organisation if that ever exists |
| [3. Is `refetchQueries({ include: 'active' })` too broad?](#3-is-refetchqueries-include-active--too-broad) | For broadcasts, yes, and Apollo can narrow it with no new bookkeeping (verified). Keep it broad for reconnects and tab returns |
| [4. Should room and people changes be broadcast too?](#4-should-room-and-people-changes-be-broadcast-too) | Yes, cheaply, using the extension point the `Invalidation` type was designed with |

Answering them also turned up one gap that wasn't a matter of opinion, now fixed: deleting a person
changed meetings without broadcasting. See [Found while answering](#found-while-answering).

---

## 1. Is 5 seconds the right own-write window?

**The question.** A tab ignores broadcasts for dates it has just written, for 5 seconds
(`OWN_WRITE_GRACE_MS` in
[daysInvalidated.ts](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/webapp/src/realtime/daysInvalidated.ts)).
The guard is set just before the request is sent. During those 5 seconds the tab also ignores a
genuine change by *someone else* to the same date.

**Answer: 5 seconds is a reasonable number, because both ways of getting it wrong are mild. But a
time window is the wrong shape. An origin id would remove the trade-off, and should replace it the
next time the schema changes.**

### What the window has to cover

The guard is set before the request leaves. The tab's own broadcast arrives after the server has
committed the write and published, and the API publishes *before* it responds. So the window has to
cover the whole server-side request:

- **Usually about 1 to 3 seconds.** In the two-user probe of 2026-10-01
  ([mootmaker-webapp#137](https://github.com/geoffweatherall/mootmaker-webapp/issues/137)), changes
  made over the API took 1.2 to 2.7 s end to end, and the broadcast reached the other tab within
  about 100 ms of the change.
- **Occasionally longer.** A cold Lambda, DynamoDB retrying a version conflict (up to 5 attempts in
  `DayRepository`), or the publish itself, which may take up to its 2-second timeout.

### What each kind of mistake costs

| Window too short (the request outlasts it) | Window too long |
|---|---|
| The tab handles its own broadcast like anyone else's: it evicts, refetches, and shows a progress bar over the last-known content | Someone else's change to the same date in that window is ignored |
| Costs one wasted round trip and a brief progress bar. **Nothing false is shown**, because every view keeps last-known content while refreshing | The tab is stale until the next broadcast for that date, a tab return or a reconnect. Usually seconds, but unbounded on a quiet day |

So "too short" is the cheaper mistake. That argues against raising the number. A slow request costs
a progress bar, while a longer window hides real changes more often.

### The better shape: an origin id

A time window guesses which broadcast is "mine". The broadcast could simply say so:

1. Each tab generates a random id when it loads and sends it as a request header.
2. The resolver passes it through: `publishDaysInvalidated(dates, origin)`.
3. `Invalidation` gains an `origin: String` field. This is an **additive, non-breaking** change,
   which is exactly why `Invalidation` is a wrapper object rather than a bare list (see the
   [caching design](../../designs/archive/graphql-schema-and-caching.md)).
4. A tab ignores broadcasts whose `origin` is its own, and **never ignores anyone else's**.

This removes the trade-off rather than tuning it. Ignoring is exact, slow requests don't matter, and
another person's change is never swallowed. Two tabs of the same user still behave as two users,
which the design requires (row 7 of its cross-client table).

What it costs: a schema change across the API and webapp, one more argument on an IAM-only
mutation, and a header that must survive the AppSync-to-Lambda hop.

**Recommendation:** keep 5 s for now. Do the origin id alongside the next schema change, rather
than on its own.

---

## 2. Is it OK that every signed-in client receives every broadcast?

**The question.** Every connected client gets every `daysInvalidated` message, whether or not it
holds that day, and whether or not the meeting has anything to do with its user.

**Answer: yes, on both privacy and cost, for the foreseeable future. If it ever needs partitioning,
partition by organisation, not by date or by user.**

### Privacy: nothing new is revealed

- The payload is **only a list of dates**: no meeting ids, subjects, people or rooms.
- **Every signed-in user can already read every meeting.** `workspace(dates:)` returns every
  meeting on a day, and Home filters to "mine" on the client. The caching design states this as
  an assumption it depends on ("Every signed-in user can see every meeting").
- Subscribing needs a valid Cognito token, so anonymous visitors receive nothing.

A broadcast tells a user that "something changed on 8 October", and they could already read 8
October themselves. If the privacy model ever changes, for example private meetings, this needs
revisiting. A dates-only payload is about the smallest possible leak, though.

### Cost: tiny now, and linear when it grows

AppSync's prices for GraphQL APIs ([AWS pricing page](https://aws.amazon.com/appsync/pricing/),
checked 2026-10-07):

| Item | Price | Our usage |
|---|---|---|
| Real-time updates | **US$2.00 per million**, counted per subscriber, per 5 KB | one per subscriber per write. A broadcast is tens of bytes |
| Queries and mutations | US$4.00 per million | the refetches a broadcast triggers, in tabs holding that day |
| Connection time | US$0.08 per million minutes | negligible |

A worked example, for a busy single organisation far beyond today's demo load: **100 people
connected all working day, making 2,000 meeting changes a day**, over 22 working days a month.

- **Deliveries:** 2,000 × 100 × 22 = 4.4 million real-time updates, or **US$8.80 a month**.
- **Refetches:** suppose a fifth of tabs hold the changed day. 4.4 M × 0.2 = 0.88 million
  refetches, or about **US$3.50 a month** if each refetch is a single query. Narrowing the refetch
  (question 3) matters here, because a broad refetch multiplies this by the number of active
  queries.
- **Connections:** 100 × 8 h × 60 × 22 = 1.06 million minutes, about **US$0.08**.

That totals about US$12.40, or roughly **NZ$21 a month** at about 1.7 NZD to the USD, for a load
well beyond anything mootmaker sees. For scale, AppSync's whole bill for August 2026 was US$0.11
([running-costs.md](../reference/running-costs.md)), recorded before subscriptions shipped, so
there's no measured real-time figure yet. The cost grows as writes × connected clients, so it stays
proportional rather than surprising.

### If it ever needs partitioning

- **By organisation: yes.** If mootmaker ever becomes multi-tenant, add an organisation argument:
  `daysInvalidated(orgId: ID!)`, with `orgId` in the payload. Equality on a top-level scalar is the
  one subscription filter the caching design measured as **working correctly**. It cuts deliveries
  by the number of tenants, and it's the privacy boundary you'd need anyway.
- **By date: no.** A tab holds a changing set of days, so it would have to keep re-subscribing as
  the user navigates, and a reconnect would have to re-establish all of them. Filtering on a
  *list* of dates is exactly the combination the design found **silently matches everything**.
- **By user: no.** Users see each other's meetings, so a change to someone else's meeting is
  relevant to everyone viewing that day.

**Recommendation:** leave it as it is. Revisit only with multi-tenancy or a change to who can see
what.

---

## 3. Is `refetchQueries({ include: 'active' })` too broad?

**The question.** After a broadcast evicts something, `useDaysInvalidated` refetches **every
active query** on the page, not only the ones that read the evicted day.

**Answer: for broadcasts, yes, and Apollo can do the narrowing itself, with no new bookkeeping.
After a reconnect or tab return, keep it broad, deliberately.**

### What "broad" costs today

Every query a mounted component is watching goes back to the server, whether or not it read the
evicted day. On Room Availability that's three queries, `BOUNDARIES`, `REFERENCE_DATA` and `DAYS`,
when only `DAYS` reads a day. Across a page's life that is two wasted requests per broadcast, in
every tab holding the day. That multiplier is what drives the refetch line in question 2's costs.

### The narrow version is built into Apollo

Apollo's `refetchQueries` can evict and refetch in one step, and it calls you back only for queries
**whose cached result the eviction actually changed**:

```ts
await apolloClient.refetchQueries({
  updateCache(cache) {
    dayInvalidations.invalidate(dates)          // the same evictions as today
  },
  onQueryUpdated(observableQuery) {
    return observableQuery.refetch()            // only reached for queries that read evicted data
  },
})
```

**Verified, not assumed.** Our `workspace` field reads days through a custom `read` policy, using
`toReference` and `canRead`, so it was worth checking that Apollo's dependency tracking sees through
it. A script ran Apollo 4.2.5 with the webapp's real type policies and three watched queries: a
two-day `DAYS` query, a `REFERENCE_DATA`-style rooms query, and a `meeting(id)` query.

| Evicted | `onQueryUpdated` called for | `include: 'active'` refetches |
|---|---|---|
| one of the two days, and its meeting | **the days query only** | all three |
| a day nobody holds | **nothing** | all three |
| the meeting held by `meeting(id)` | **the `meeting(id)` query only** | all three |

It picks out exactly the right queries, including the "complete minus one day" case (where the
query reads back complete but with one day fewer), which is the reason we refetch at all.

### Keep it broad after a reconnect or a tab return

There, `invalidateEverything()` evicts every day, so most day-reading queries would be selected
anyway. More importantly, **rooms and people aren't broadcast** (question 4). Today a tab return
is one of the few things that refreshes an active `REFERENCE_DATA` query. Narrowing that path would
quietly remove that until question 4 is done.

### One thing to keep

`reconcileLink`'s re-eviction (the in-flight race) also calls `refetchQueries`. That can be
narrowed the same way, since it evicts specific dates.

**Recommendation:** narrow the broadcast and race paths with
`updateCache` + `onQueryUpdated`. Keep `include: 'active'` for reconnect and tab return. Add a test
like the experiment above, which drives a real `ApolloClient` with the real type policies, so a
future Apollo version that tracks dependencies differently fails a test instead of silently
over- or under-fetching.

---

## 4. Should room and people changes be broadcast too?

**The question.** Only meeting changes are broadcast. When an admin creates, renames or deletes a
room or a person, other clients don't find out.

**Answer: yes. It's cheap, it was planned for, and the current staleness is long-lived even though
it's mild.**

### How stale, and how much it matters

Rooms and people are read with `cache-first`, fetched once per session. Other clients see a change
only after:

- a full page reload, or
- a tab return or reconnect, *if* a component watching `REFERENCE_DATA` happens to be mounted,
  because the broad refetch includes it, or
- a broadcast for some held day, for the same reason.

The visible effects are: a new room missing from the booking form's room list and from Room
Availability, a renamed room or person showing the old name, and a deleted person still offered as
an attendee. A booking against a deleted room or person is still rejected correctly by the API, so
nothing is corrupted. It is wrong or missing information, sometimes for a whole working day.

### It was designed for

The caching design deferred this deliberately, and shaped the payload for it: *"`Invalidation` is a
wrapper object, not a bare `[String!]!`… so deferred reference-data flags (`rooms`, `people`) can
be added later without breaking a deployed client."*

1. Add `rooms: Boolean` and `people: Boolean` to `Invalidation`, defaulting to false. An old client
   ignores them.
2. Have the room and person handlers publish with the matching flag after a successful write. These
   are `createRoom`, `updateRoom`, `deleteRoom`, `createPerson`, `renamePerson`, `setPersonAdmin`,
   `deletePerson` and the avatar mutations.
3. On the client, refetch `REFERENCE_DATA` when a flag is set.

Admin changes are rare, so this adds almost nothing to the costs in question 2.

**Recommendation:** do it. It is also what makes question 3's "narrow the broadcast path"
safe, because reference data would then have a refresh trigger of its own.

---

## Found while answering

Question 4 meant listing which handlers broadcast. At the time, only five did: `createMeeting`,
`createMeetings`, `updateMeeting`, `cancelMeeting` and `respondToMeeting`.

**`deletePerson` and `deleteMyAccount` changed meetings without broadcasting.** Both cancel every
upcoming meeting the person organises, and remove them from every upcoming meeting they attend,
through `UpcomingMeetings.cancelUpcomingMeetingsFor`, which never published. Other clients kept
showing those meetings until something else refreshed the day. `deleteRoom` was fine: it refuses to
delete a room with upcoming meetings rather than cascading.

That was a gap, not a design choice, so it was filed as
[mootmaker-api#107](https://github.com/geoffweatherall/mootmaker-api/issues/107) and fixed in
[mootmaker-api#108](https://github.com/geoffweatherall/mootmaker-api/pull/108). The cascade now
returns the dates it changed, and both handlers publish them straight after the meeting writes.
That also means the person handlers already publish, which question 4's room and person flags would
build on.
