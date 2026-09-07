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
- Cognito changes, except the optional `personId` claim recorded as a non-blocking open question.

## Trade-offs and decisions

**The meetings item is already normalised; the redundancy is elsewhere.** `MeetingRecord.toItem()`
stores `roomId`, `organiserId` and `attendeeIds` as bare ids — no names, no capacities. The
duplication is in the two `projection_type = "ALL"` GSIs on the meetings table and the
`meeting-participants` join table. A meeting with four attendees is physically stored **eight
times** (1 base + 2 GSI copies + 5 participant rows). Any "remove denormalisation" work should aim
there, not at the item.

**Concurrent root fields do not double cold-start latency.** AppSync resolves a query's root fields
in parallel, so the client waits `max(restore + work)`, not the sum. What they do cost is
*execution environments*: three root fields create three, each paying its own SnapStart restore and
each holding a concurrency slot. With the account limit at 10, roughly three simultaneous users on
`PersonCalendarPage` saturate the account. The quota increase is requested (mootmaker#72); the
argument for collapsing is environment count and total compute, not user-visible latency.

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
- **Explicit payload construction in the request template** rather than wrapping `$util.toJson($ctx)`
  in a new envelope. Wrapping would break every handler's `event.get("info")` access; building the
  payload field by field keeps `info.fieldName`, `info.parentTypeName` and `identity` exactly where
  they are, so `ResolverDispatchHandler` and `Identity` are untouched. It also stops shipping every
  CloudFront request header to Lambda on every call.
- **Day-scoped bulk over enhanced subscription filters.** `setSubscriptionFilter` with a `contains`
  operator over a `dates` array would work, but the payload still carries every meeting — it filters
  who is woken, not how much they receive.

## Open questions

### Blocking

**Database reset.** `DatabaseReset` deletes straight through `DynamoDbClient`, bypassing AppSync
entirely. That is already unsatisfying; this design makes it worse in two specific ways. No
subscription fires, so every connected client keeps a cache of data that no longer exists — and
acceptance tests reset between runs, so this is the first thing a long-lived subscription in a test
will hit. Options include: routing reset through a mutation so it broadcasts; adding a
`resetGeneration` counter that clients compare and use to evict; having tests tear down browser
contexts around resets; or accepting staleness and making reset visibly non-real-time. **Geoff has
flagged the current approach as unsatisfactory independently of this design, so this wants deciding
on its own merits, not just as a subscription detail.**

**Chosen limits for meetings per day and attendees per meeting.** The 400 KB item cap allows roughly
**1,000 meetings per day** at four attendees each (~406 bytes per meeting; ~1,590 at zero attendees,
~410 at twenty). Business hours of 08:00–17:00 on 15-minute boundaries give 36 slots per room, so
1,000 meetings means 28 rooms fully booked all day. The failure mode is a hard `PutItem` rejection,
not degradation — a day becomes unbookable for a reason unrelated to room availability. Explicit,
enforced limits turn that into a testable worst case.

**Whether `meeting-participants` survives.** It answers "which meetings is this person in" in a
single Query. With day-items there is no such index, so a six-week person calendar would fetch 42
day items and filter in the Lambda. Keeping it means keeping a join table in sync with day items;
dropping it means accepting the scan.

**Composite field or sibling root fields.** One composite field gives one Lambda invocation but moves
`rooms` from `ROOT_QUERY.rooms` to `ROOT_QUERY.workspace.rooms`, missing every existing
`cache-first` reader; the fix is an explicit `cache.writeQuery` mirror, which is a permanent tax.
Sibling root fields in one document keep cache slots canonical and cost one HTTP request, but three
invocations. This decision is cheap to defer and expensive to reverse once clients depend on it.

### Non-blocking

- **`personId` as a Cognito claim.** Removes the waterfall's dependency but not the `myPerson` call,
  since `name`, `dateFormat` and `timeFormat` are all mutable and must not be baked into a token.
  Custom attributes cannot be removed or renamed once added to a pool, and M2M client-credentials
  tokens have no user behind them, so the fallback path is permanent.
- **Cache persistence across reloads.** `InMemoryCache` starts empty on every page load. Persisting
  it needs `apollo3-cache-persist` and its own invalidation story.
- **A past-booking rule.** Nothing in `MeetingError` rejects a booking in the past, so history is
  not immutable and cannot be cached permanently. Adding the rule would make past days safely
  cacheable forever.
- **`graphql-ws` protocol support.** Determines whether the client is a stock `GraphQLWsLink` or a
  hand-rolled link.

## Impacts on components

**`mootmaker-api`** — `api/mootmaker.graphql` (new `Day` type, `days` query, `mine` filter,
`createMeetings`, `Subscription`); `deploy/terraform/appsync.tf` (request template, subscription
resolvers, `@aws_subscribe`); `deploy/terraform/dynamodb.tf` (day-keyed meetings table, GSI
removal); `ListMeetingsHandler`, `CreateMeetingHandler`, `MeetingRecord`, `MeetingParticipant`,
`ResolverDispatchHandler`, `DatabaseReset`.

**`mootmaker-webapp`** — `apolloClient.ts` (`typePolicies`); `graphql/queries.ts` and `mutations.ts`;
`HomePage`, `RoomAvailabilityPage`, `PersonCalendarPage`, `AddMeetingPage`, `SettingsPage`. The
router-state workaround in `AddMeetingPage` and the paired `createdMeeting` merge in
`RoomAvailabilityPage` should both be retired by proper cache writes.

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
- **`meeting-participants` status unresolved** — see Open questions.
- **No Cognito change**, unless the `personId` claim is adopted later.
- **Storing ids as binary** (16 bytes) rather than 36-char strings would raise the per-day ceiling
  from ~1,000 to ~1,545 meetings; UUIDs are 63% of the payload. Not proposed, recorded as available
  headroom.

## Technical considerations

- **The template change is a prerequisite**, not a detail — nothing selection-aware works until
  `selectionSetList` is explicitly serialised.
- **Aliases defeat naive field matching.** Fail toward fetching. Unit-test the selection logic
  against recorded `selectionSetList` payloads, not only through end-to-end queries.
- **Non-null propagation turns a stub/selection mismatch into silent data loss**, not a degraded
  response.
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
- **The chosen day limits become a worst case that can actually be tested** — a full day at the
  attendee cap, which is not covered today.
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

**This needs a real data migration.** Existing per-meeting items must be read and rewritten as day
items, and the GSIs dropped only after that succeeds. `production` holds real demo data;
`test` can be rebuilt from nothing, which makes it the rehearsal.

The staging is otherwise conventional: ephemeral environment first, then `test`, then `production`
through `release.yml`. The schema changes are not backward-compatible for a deployed webapp, so API
and webapp must ship together — which the release pipeline already does.

## Risks

- **The migration is harder to reverse than a normal deploy.** Once meetings are day-items and the
  GSIs are gone, rolling back means migrating in the opposite direction. `database-repair` already
  has precedent for rebuilding derived data, and something equivalent should exist before the
  forward migration runs.
- **Broadcast visibility becomes load-bearing.** Subscriptions push to everyone matching the filter.
  That is safe only while every user may see every meeting. This design should not be built on if
  meeting privacy is anticipated.
- **Write contention on a day item** is a new failure mode with no current analogue.
- **The day ceiling is a hard rejection.** Without enforced limits and a deliberate answer at ~80%
  capacity, the first symptom is a failed booking.

## Implementation checklist

Sparse while Drafting — to be filled in properly before this reaches Ready.

- [ ] `[Geoff]` Resolve the four blocking open questions, database reset first.
- [ ] `[Claude]` Change the resolver request template to serialise `selectionSetList`; confirm no
      handler reads `request.headers` or `stash` before dropping the full `$ctx`.
- [ ] `[Claude]` Make `ListMeetingsHandler` selection-aware, with unit tests driven by recorded
      payloads including aliases. Independently shippable and valuable on its own — it removes an
      existing over-fetch where `meetings { id subject }` still batch-loads every room and person.

## Definition of done

The feature's own acceptance coverage — including the two-context real-time test — is green; the
existing acceptance suite is still green on a real deployed environment; every touched repo's unit
tests pass; the migration has run against `test` and `production` with meeting counts verified
before and after by direct DynamoDB reads rather than by exit codes; and everything under
Documentation impacts is actually done.
