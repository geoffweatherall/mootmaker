# Ideas

Half-formed things. **Nothing here is a design**, and nothing here is committed to — an entry
existing means someone thought it was worth writing down, not that it will happen.

An idea graduates by becoming a document in [`../designs/`](../designs/) at Status `Drafting`,
at which point its entry here is deleted rather than left to rot as a second, staler copy.

Geoff's own text is unattributed. Claude's commentary is marked **C:** so the two never blur —
the point of this file is to keep a raw thought raw, not to have it quietly rewritten into
something more confident than it was.

---

## Packaging of the tools and sample data generation

*Raised 2026-08-31. Not yet explored.*

The general shape: how `mootmaker-admin-tools` and `mootmaker-demo-data` are packaged, deployed
and versioned.

**C:** One concrete thing to design around, found while confirming how reset/repair run:
`mootmaker-demo-data`'s sample-data-generator invokes the `database-reset` Lambda *directly*
(`DatabaseResetInvoker`, AWS SDK, IAM auth), and that Lambda is owned and deployed by
`mootmaker-admin-tools`. So there is a live cross-repo runtime dependency, coupled by a function
name convention (`<env>-mootmaker-database-reset`) that is written out separately in a Java class,
a shell script and a Terraform config. Whatever packaging story gets chosen has to say something
about that, because it constrains how independently the two repos can be released.

---

## Merge sample-data-generator and sample-data-topup into one Lambda

*Raised 2026-08-31.*

One Lambda, run daily on a schedule or ad hoc, with logic to top up:

- the number of users
- the number of rooms
- meetings for any day (excluding Sat/Sun) in the next 6 weeks that has no meetings

**C: Most of the meetings half already exists.** `SampleDataTopUp` today looks ahead
`WEEKS_AHEAD = 6`, skips Saturday and Sunday, finds business days with no meetings and populates
only those. It is already a Lambda, and already on an EventBridge schedule —
`cron(0 6 ? * MON *)`, weekly on Mondays. So the new work is narrower than it sounds: topping up
*people* and *rooms* is genuinely new, weekly→daily is a variable, and the merge is refactoring.

**C: The merge is independently justified.** The two tools duplicate `GraphQlClient`,
`MeetingScheduler` and `SampleData` — deliberately, documented as "separate Maven projects with no
shared-code mechanism". But `MeetingScheduler` has already drifted 53 lines apart, because topup
takes an explicit `List<LocalDate>` of empty days while the generator takes a contiguous offset
range. That is one algorithm forked in two places. Merging deletes the fork instead of maintaining
it twice.

**C: Concerns worth resolving before this becomes a design.**

1. *The two halves have opposite risk profiles.* The generator invokes database-reset — it
   destroys data first. Topup is purely additive. One Lambda that can do both is one misfired
   daily invoke away from wiping an environment. If merged, the destructive path must be
   unreachable from the scheduled trigger: an explicit mode in the event payload, defaulting to
   additive, never inferred.
2. *"Top up users" collides with reset's Cognito rule.* Reset deliberately preserves people linked
   to a Cognito account; the generator creates 40 unlinked demo people. A people-topup needs a
   target it can actually measure — total people, or unlinked demo people only — or it will either
   fight the preservation rule or drift upward forever as real signups accumulate. Rooms have the
   same question with a far smaller blast radius.
3. *Daily against a 6-week window is a no-op almost every run.* Once the window is full each run
   finds one newly-entered day. Fine and cheap, but it means the interesting path — filling thirty
   days — is exercised rarely, so a regression there could sit undetected for weeks. Worth keeping
   the full-window path easy to run deliberately.
4. *Idempotency is currently structural, not enforced.* Topup is safe to re-run because "this day
   has no meetings" is a natural guard. People and rooms need guards of their own, and two
   concurrent runs (scheduled plus ad hoc) could both observe 30 rooms and both create 10.

**C: A shape that addresses those** — one Lambda with three independently-toggleable top-up
concerns (people, rooms, meetings), plus reset as a separate mode the schedule cannot reach;
`sample-data-generator` reduced to a thin caller that invokes reset and then the topup Lambda in
full-window mode, rather than carrying its own copy of the scheduler.

**Open, for Geoff:** what does "top up users" count against — total people, or only unlinked demo
people? And should reset live inside the merged Lambda at all, or stay a separate tool it calls?

---

## Loose threads

Small things noticed in passing. Not ideas so much as unfinished business — each is probably an
issue rather than a design, but they are recorded here so they are not lost.

- **Nothing enforces the webapp's own code formatting.** Every acceptance spec is formatted as
  `prettier --single-quote --no-semi --print-width 120`, but there is no `.prettierrc`, prettier
  is not a dependency, and no CI check runs it. The style survives on habit alone. Ten of the
  acceptance specs already do not match it. **C:** this is not hypothetical — running a bare
  `npx prettier --write` on two files during the date/time work silently rewrote them to double
  quotes and semicolons, matching nothing around them, because there was no config to read.
- **Empty leftover directories from the repo split.** `mootmaker-demo-data/database-reset/` and
  `mootmaker-demo-data/database-repair/` exist on this workstation with zero files and zero git
  entries. Harmless, but they make it look as though those tools live in both repos.
- **No home for pre-design ideas until now.** The issue board's Backlog holds concrete issues and
  `designs/` starts at `Drafting`; there was no place for a thought that is not yet either. This
  file is that place, which means [`../docs/process/`](process/) does not describe it yet.
- **The acceptance suite must run against a fresh environment, and nothing said so.** Re-running it
  against a reused one produced ten failures that all read as real regressions (empty state, room
  ranking, calendar contents) and none were. Now documented in
  `mootmaker-webapp/acceptance/README.md`. **C:** the deeper point is that the failure mode points
  at the code rather than at the environment, so the investigation goes to the wrong place. Worth
  asking whether the suite could *detect* a dirty environment and say so — a preflight check on
  `00-room-availability-empty`'s own precondition would have turned ten misleading failures into
  one accurate message.
- **E.35 looks flaky.** It failed once (room not appearing after creation) and then passed on every
  subsequent run, including two clean full runs. Not reproduced since. **C:** worth watching rather
  than chasing — but note the catalog already flags F.53/F.54/F.57 as intermittently failing, so
  this may be a fourth instance of one underlying cause rather than its own thing. If a pattern
  emerges across those four, that is a real issue rather than a set of separate flakes.
