# Realistic demo meeting scheduling

## Summary

`mootmaker-demo-data`'s meeting generator currently gives each room at most two meetings a day,
each room scheduled independently from a single random start point with no relation to the time of
day, under a strict "nobody is ever in two overlapping meetings" rule for every organiser and
attendee. The result reads as artificial: rooms never visibly overlap, density is flat and low
across the business day, and there's no size variety for testing the UI. This redesigns the
generator to produce a bimodal ("double hump") time-of-day distribution per room, per-room
occupancy tiers (some rooms busy up to ~60% of the day), a relaxed person-conflict rule — attendees,
but not organisers, can hold genuinely overlapping invites, matching what per-attendee RSVP status
already models — and a ~20% share of meetings sized near a room's full capacity for visual testing.

## Status

**Building** — 2026-09-22. Approved by Geoff; implementation started same day.

## Scope / non-goals

In scope:

- Rewriting `MeetingScheduler`'s placement algorithm: weighted time-of-day sampling in place of a
  single random start plus forward walk; per-room occupancy targets in place of the current flat
  0–2-meeting cap; a relaxed attendee-conflict rule.
- Raising `TARGET_PEOPLE` to support the resulting volume.
- Correcting this repo's README, whose description of guaranteed-meeting placement is stale (see
  "Trade-offs and decisions" #6) — no code change needed there.
- Updating this repo's unit tests and its acceptance-suite invariants to match the new rules.
- A one-time, deliberate `database-reset` + repopulate of `test` and `production` as part of
  rollout, so the new distribution is visible immediately rather than rolling forward day by day
  over the next six weeks.

Explicitly not in scope:

- Changing `TARGET_ROOMS` (stays 10) or the room capacity range (stays 4–20) — only how densely
  those rooms get filled.
- Any change to the Meetings GraphQL API, DynamoDB schema, or the `AttendeeStatus` enum. This is
  purely a change to what data the generator writes, not what the API accepts — see "Changes to the
  domain data model" below.
- A reset/backfill mechanism inside `mootmaker-demo-data` itself. Still explicitly out of bounds per
  the component's own founding design
  ([`archive/demo-data-component.md`](archive/demo-data-component.md)): "This tool never deletes
  anything, and must not learn how." Rollout uses the existing separate `database-reset` tool, same
  as any other manual reset.
- Splitting meeting generation across multiple Lambda invocations (e.g. one per week). See
  "Trade-offs and decisions" below for why this was considered and dropped.

## Trade-offs and decisions

1. **Person-conflict rule relaxed for attendees, not organisers.** An organiser can never be
   double-booked, as organiser or attendee, at an overlapping time — running two meetings at once
   isn't something an RSVP can resolve. An attendee can be invited into up to **2** concurrent
   overlapping meetings, since per-attendee RSVP status (`Going`/`NotGoing`/`Maybe`/`NoResponse`)
   already models exactly this: a real conflicting invite that gets accepted for one and declined
   for the other. Discussed and confirmed with Geoff directly.

   **RSVP resolution for a genuinely overlapping pair** (confirmed with Geoff): people mostly
   resolve a conflict correctly, but not always.
   - **95%** of the time, exactly one of the pair resolves to `Going`, chosen at random between
     the two; the other is drawn from `NotGoing`/`Maybe`/`NoResponse` using those three statuses'
     existing relative weights, renormalised (roughly even across the three).
   - **5%** of the time, **both** resolve to `Going` — the deliberate "over-promised, double-booked,
     failed to meet an expectation" mistake, not a vaguer unresolved outcome.
   - This only applies to the subset of invites that are actually part of an overlapping pair for
     that person. Every other invite — the large majority, since most people aren't double-booked
     on a given day — keeps today's behaviour unchanged: an independent draw from the existing
     `ATTENDEE_STATUS_CUMULATIVE_WEIGHTS` (60% `Going`, ~13.3% each for the rest).

2. **Single Lambda invocation, not split per-week.** Considered splitting the 6-week backfill into
   weekly chunks to stay clear of the Lambda's execution-time ceiling. Dropped: that ceiling
   (`lambda.tf`'s `timeout = 900`) is already AWS's hard maximum for Lambda — not a value that can
   be raised further — and the longest real invocation found in `production`'s logs (2026-09-20, a
   full cold-start backfill: 40 people, 10 rooms, 526 meetings across all 35 weekdays in the
   7-days-past/6-weeks-ahead window) took **32.26s**. The volume increase this design targets is
   roughly 1.5–2x that (see "Technical considerations"), which extrapolates to well under a minute —
   nowhere close to 900s. Splitting the invocation would add real complexity (partial-state
   tracking across invocations, a second code path, idempotency across the split) to solve a
   constraint that isn't actually binding. Revisit only if a real timed run against an ephemeral
   environment comes back surprisingly close to the ceiling.

3. **Definition of done is a manual three-environment visual review, not "acceptance suite green."**
   This project's usual bar (`docs/process/README.md`) is a green acceptance run against a real
   deployment. For this specific change, Geoff wants to eyeball the actual room-availability pages
   before committing to a release: stand up three ephemeral environments once the algorithm looks
   right locally, hand over their URLs, and only proceed to release once he's happy with what he
   sees. The acceptance suite (`verify/*IT.java`) still gets updated to match the new invariants and
   still has to pass — it just isn't the thing that gates moving to release for this change. See
   "Definition of done" below.

4. **Time-of-day placement becomes weighted sampling, not a sequential forward walk.** The current
   algorithm can't produce a bimodal curve at all: it picks one random start per room-day, places a
   meeting, then walks forward from wherever that meeting ends. To get several meetings a day
   clustered around two peaks with a lunch trough, each candidate start time needs to be drawn from
   a density function over the business day (high 09:00–12:00, low 12:00–13:00, high again
   13:00–~15:00 tailing off to 17:00), with rejection/resampling when a candidate collides with
   that room's existing bookings or isn't feasible on people availability. This is a genuine rewrite
   of `generateForRoomDay`/`findAndPlaceMeeting`, not a constant tweak.

5. **Room occupancy is a fixed per-room trait, not re-rolled daily.** Confirmed with Geoff: certain
   rooms (e.g. the big ones near reception) should be consistently in higher demand across the whole
   demo, not randomly busy on some days and quiet on others. Since the generator has no persisted
   state between invocations beyond what's already in the domain model, this has to be a **pure,
   deterministic function of the room's existing `id`** (see "Technical considerations") rather than
   a new stored field.

6. **Guaranteed-meeting placement needs no fix.** The first draft of this doc assumed
   `DemoData.pickFreeSlot` required a wholly-empty room, per this repo's own README ("placed in a
   room with no bookings at all that day"). Reading `DemoData.java` directly during implementation
   found that's stale: `pickFreeSlot` already searches per-room, per-hour candidate slots (9 hours ×
   every room) and only requires that specific room-hour slot to be free, plus a free attendee — the
   "search slots, not whole free rooms" fix its own javadoc already describes as a lesson from an
   earlier, abandoned attempt. Nothing in the code changes; only the README's prose does (see
   "Documentation impacts"). Whether guaranteed-meeting success rate stays acceptable once rooms are
   routinely busier is worth watching during the ephemeral-environment review, not a reason to change
   the algorithm pre-emptively.

## Choices you had me make

These weren't discussed directly; flagged here so they're cheap to override rather than buried in
code:

- **Starting tier proposal**: ~20% of rooms "high-demand" (~55–60% busy), ~50% "typical" (~25–35%
  busy), ~30% "quiet" (~10–15% busy). A starting point for the fast local-tuning loop described in
  "Testing impacts" below, not a final number.
- **Starting `TARGET_PEOPLE` = 100** (from 40). Back-of-envelope sizing for the new volume — see
  "Technical considerations" — to be tuned against real generated stats before it's treated as
  correct.
- **Room-tier assignment mechanism**: a stable hash of the room's `id`, bucketed into the three
  tiers above, computed fresh every run rather than stored anywhere. Deterministic without any
  data-model change.
- **Density curve shape**: peaks around 10:00 and 14:00, a non-zero floor through 12:00–13:00 (a
  small chance of a lunch meeting, per Geoff's preference over a hard cutoff) at roughly 5–10% of
  peak density.
- **Large-meeting sizing**: ~20% of meetings sized to 80–100% of the room's capacity (per Geoff's
  "near full capacity" answer), the remaining ~80% keeping the existing small/medium weighted split
  (`SMALL_MEETING_ATTENDEE_COUNT_CUMULATIVE_WEIGHTS`), unchanged.

## Open questions

**Blocking**: none currently — every open decision above is flagged as a cheap-to-override choice,
not something that needs resolving before this can reach Ready.

**Non-blocking**:

- The exact tier percentages and `TARGET_PEOPLE` value are provisional pending the fast unit-test
  tuning loop; the numbers actually used at Ready time may differ from the draft values above.
- `testing-strategy.md`'s existing note that "business hours are exactly the range generated data
  fills, so in a seeded environment no time slot is free by construction" should still hold after
  this change (density goes up, but not to 100%) — worth a quick re-check once real numbers exist,
  since any acceptance or e2e test that relies on finding a free time slot (rather than a free room)
  depends on it.
- **Guaranteed-meeting success rate** under the new density — `pickFreeSlot` doesn't need a code
  change (see "Trade-offs and decisions" #6), but worth watching during the ephemeral-environment
  review whether its 9-hours × every-room search still reliably finds a slot once rooms are
  routinely busier.

## Impacts on components

- **`mootmaker-demo-data`** (the only repo touched):
  - `impl/src/main/java/com/mootmaker/demodata/MeetingScheduler.java` — the placement rewrite
    described above.
  - `impl/src/main/java/com/mootmaker/demodata/DemoData.java` — `TARGET_PEOPLE` default only; no
    change to `pickFreeSlot` itself (see "Trade-offs and decisions" #6).
  - `impl/src/test/` — new/updated unit tests (see "Testing impacts").
  - `verify/` — updated acceptance-invariant assertions.
  - `README.md`, `testing-strategy.md` — updated description of generated-data behaviour and
    asserted invariants.
- **No changes** to `mootmaker-api`, `mootmaker-webapp`, or `mootmaker-android` — all read whatever
  the existing GraphQL API accepts, unchanged.

## Changes to the domain data model and data storage models

N/A. No schema, attribute, or index changes. Room "reputation" is computed at generation time from
the room's existing `id`; nothing new is persisted.

## Technical considerations

- **Room-tier hashing**: a deterministic function like `tier = stableHash(room.id()) % 100`, bucket
  boundaries mapped to the tier proposal above. Must be stable across JVM runs and across the
  language's default `Object.hashCode()` (which is not guaranteed stable) — use an explicit stable
  hash (e.g. a fixed-seed string hash), not `String.hashCode()`.
- **Weighted sampling with rejection**: for a room-day, repeatedly sample a 15-minute-aligned
  candidate start from the density curve (renormalised over remaining, non-overlapping time), check
  it against that room's already-placed meetings and person availability, place or resample, until
  the room's occupancy target for the day is met or a retry budget is exhausted. This replaces
  `findAndPlaceMeeting`'s current pure forward-walk search.
- **`TARGET_PEOPLE` sizing**: current defaults (40 people, 10 rooms, `LARGE_MEETING_PROBABILITY` ≈
  0.65) produce 526 meetings across a 35-weekday backfill window. The tier proposal above works out
  to roughly 1.5–2x that volume; organisers are the tighter constraint post-relaxation (still
  require full availability), so `TARGET_PEOPLE` needs headroom beyond a flat volume-proportional
  scale-up. 100 is a starting point, not a derived number — confirm against real generated stats.
- **Lambda timeout**: `deploy/terraform/lambda.tf` already sets `timeout = 900`, AWS's hard ceiling
  — not a value that can be raised. Not a real constraint given the 32.26s baseline and projected
  volume (see "Trade-offs and decisions" #2), but worth stating plainly since it was raised as a
  possible lever during discussion and isn't one.
- **RSVP status assignment moves to a post-placement pass.** Today, `pickAttendeeStatus` is called
  inline the moment an attendee is added to a meeting. That no longer works for the conflict-
  resolution rule above: the first meeting of an overlapping pair is placed, and its attendee
  statuses drawn, before its overlap partner exists to be paired against. Placement therefore stays
  structural and status-free; once every meeting for the batch is placed, a separate pass groups
  each person's attendee-invites by genuine time-overlap (max pair size 2, since
  `MAX_CONCURRENT_ATTENDEE_INVITES` caps it there) and assigns statuses — the 95/5 rule for any
  overlapping pair, the existing independent draw for everything else.
- **Gap semantics are unchanged**: the existing post-meeting "gap" (`GAP_AFTER_MEETING_PROBABILITY`,
  `GAP_MINUTES_OPTIONS`) is a per-person availability construct, not a room-timeline one, and stays
  that way — it affects when a person becomes reschedulable, not when a room's own next meeting can
  start.
- **Idempotency means this only affects days that are still empty when it ships.** Days already
  populated under the old algorithm keep the old shape indefinitely — `topUpMeetings` skips any day
  that already has a meeting, and this component still can't delete. That's exactly why rollout
  (below) includes a deliberate reset rather than relying on the window to roll forward.

## Testing impacts

- **Unit tests** (`impl/src/test/`, no AWS): where the bulk of tuning happens — fast and free.
  New/updated statistical and invariant assertions over `MeetingScheduler.generate()` with fixed
  seeds: an hour-bucketed histogram showing the two peaks and the lunch trough; per-tier room
  occupancy percentages landing near target; ~20% of meetings sized near capacity; no attendee ever
  exceeds 2 concurrent overlapping invites; no organiser is ever double-booked as organiser or
  attendee; across many overlapping pairs, roughly 95% resolve to exactly one `Going`, roughly 5%
  resolve to both `Going`, and non-overlapping invites keep the original ~60/13.3/13.3/13.3 status
  distribution. Existing tests asserting the old blanket "nobody double-booked, ever" invariant get
  updated to the new organiser-only rule.
- **Acceptance tests** (`verify/*IT.java`, against a real deployed environment via `./verify.sh`):
  the existing "nobody is in two overlapping meetings" assertion is now wrong and must change to "no
  organiser is double-booked, as organiser or attendee; no attendee exceeds the concurrent-invite
  cap" — otherwise this suite goes permanently red the moment the change ships. It still runs as
  part of implementation and still has to pass, but per "Trade-offs and decisions" #3, it is not
  what gates moving to release for this specific change — the three-ephemeral-environment visual
  review is.
- **`mootmaker-webapp` e2e/acceptance suites**: not directly impacted (no API/schema change), but
  worth a quick check for any test that assumes a specific or low meeting count per room-day, since
  overall volume roughly doubles.
- **Release pipeline smoke suite** (`mootmaker-release/smoke/`): not impacted — it asserts
  structure, not specific meeting content.

## Documentation impacts

- `mootmaker-demo-data/README.md` — the "What a run does" table's description of the Meetings
  concern's behaviour.
- `mootmaker-demo-data/testing-strategy.md` — the "What the acceptance tests assert" bullet list.
- `MeetingScheduler.java`'s own class-level javadoc — code documentation, updated as part of
  implementation rather than tracked separately here.

## Rollout & migration

1. Build and tune locally against the fast unit-test loop (no AWS) until the distribution looks
   right against the invariant assertions above.
2. Stand up three ephemeral environments — `./create-ephemeral-env.sh claude --with-demo-data`,
   run three times (each auto-seeds once on creation with distinct, randomly-suffixed names) —
   cheap under this project's scale-to-zero architecture, so no need to economise on how many are
   created. Give Geoff the three webapp URLs to review the room-availability pages directly.
3. On Geoff's approval: release through the normal pipeline (`release.yml`, test then production),
   then a **deliberate, explicit** `database-reset` + repopulate invocation against both `test` and
   `production` — not left to roll forward naturally over the following six weeks — so the new
   distribution is visible immediately.
4. Tear down the three review environments once approved, or once superseded by a later tuning
   round.

## Risks

- **`database-reset` against `production` is destructive** to demo data specifically (distinct
  DynamoDB items from any real signed-up user's data — see README's "people target counts all
  people" note — but still a real, irreversible production action). Should stay a deliberate,
  explicitly-confirmed step, never folded silently into the release pipeline itself.
- **Raising `TARGET_PEOPLE` materially increases visible headcount** across the whole demo (people
  list, attendee pickers, etc.) — purely additive and harmless, but worth knowing it isn't only a
  scheduling-internals change.

## Implementation checklist

1. [Claude] Rewrite `MeetingScheduler`: room-tier hashing, weighted time-of-day sampling with
   rejection, relaxed attendee-conflict rule, near-capacity large-meeting sizing.
2. [Claude] Update `DemoData.java`: raise `TARGET_PEOPLE`.
3. [Claude] Update/add unit tests for all invariants listed under "Testing impacts"; iterate
   constants against them until the distribution looks right.
4. [Claude] Update `verify/*IT.java`'s overlap assertion; correct `README.md`'s stale guaranteed-
   meeting description and update `testing-strategy.md`.
5. [Claude] Stand up three ephemeral environments with demo data seeded; confirm `verify.sh` passes
   against at least one of them; report the three URLs.
6. [Geoff] Review each environment's room-availability pages; approve, or send back for another
   tuning round (back to step 3).
7. [Claude] On approval: release via the normal pipeline to `test` then `production`.
8. [Claude] Invoke `database-reset` then `mootmaker-demo-data` against `test`, then against
   `production`, each as an explicit, confirmed step.
9. [Claude] Tear down the three review environments.

## Definition of done

Explicitly different from this project's usual default, per Geoff's instruction for this change:

1. Unit tests green, including the new statistical/invariant assertions.
2. Acceptance suite (`verify/*IT.java`) updated and green against at least one ephemeral
   environment.
3. **[Geoff] Visual approval** of the room-availability pages across three populated ephemeral
   environments — this, not "acceptance suite green," is what gates moving to release.
4. Released to `test` then `production` via the normal pipeline.
5. Deliberate `database-reset` + repopulate completed against both `test` and `production`.
6. Everything under "Documentation impacts" actually done, not just planned.
