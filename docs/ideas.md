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

**Superseded 2026-09-02** by [`../designs/archive/admin-tools-into-api.md`](../designs/archive/admin-tools-into-api.md)
for everything below about `database-reset`/`database-repair` specifically — struck through rather
than deleted, since the design doesn't cover the `mootmaker-demo-data` packaging/versioning question
this entry was originally raised for. That half stays live.

~~The general shape: how `mootmaker-admin-tools` and `mootmaker-demo-data` are packaged, deployed
and versioned.~~

~~**C:** One concrete thing to design around, found while confirming how reset/repair run:
`mootmaker-demo-data`'s sample-data-generator invokes the `database-reset` Lambda *directly*
(`DatabaseResetInvoker`, AWS SDK, IAM auth), and that Lambda is owned and deployed by
`mootmaker-admin-tools`. So there is a live cross-repo runtime dependency, coupled by a function
name convention (`<env>-mootmaker-database-reset`) that is written out separately in a Java class,
a shell script and a Terraform config. Whatever packaging story gets chosen has to say something
about that, because it constrains how independently the two repos can be released.~~

~~**Geoff Response**
i want to move the database reset function and database repair to be lambdas that are deployed as part of the api.  They will only ever be invoked via a lambda invoke, so IAM credentials protect them from missuse.  These tools have migrated from being run on a workstation with cognitio credentials to their current state, and so things like the scripts to support them authenticate.~~

~~I also want to configure them on deployment to find the resources they need via lambda environment variables.  I don't see any need for terraform output to use used for this (I think this is historic left over from when this was an api call).  So now anyone who wants to reset a database (either an acceptance test or Claude while developing) just invoke the lambda.  Consider the costs and benefits of making this a sync or async process.~~

~~**C:** Agreed on all of it, with one correction and one real trade-off.~~

~~*The correction:* the Lambdas already read their tables from their own environment variables —
`database-reset/run.sh` says so explicitly, and sources `authenticate.sh` only for `AWS_REGION`.
The terraform-output dependency you are remembering lives in the *scripts around* them (the
acceptance suite and sample-data-generator resolving `GRAPHQL_API_URL`, Cognito ids and so on),
not in the Lambdas. So this part is mostly already where you want it; what moving them into the
API deployment actually buys is that **every environment that has an API automatically has a
reset**, which removes the deploy-order coupling that bit us today: seeding this session's
environment meant deploying `mootmaker-admin-tools/database-reset` first, purely because
`sample-data-generator` invokes it.~~

~~*Sync vs async.* Recommend **synchronous**, and I think it is close to clear-cut:~~

- ~~Every caller needs to know reset *finished* before doing anything else — an acceptance run
  seeding data, or a developer repopulating. Async turns that into a completion-signalling
  problem (poll a status, or a second "is it done" call) invented to solve nothing.~~
- ~~The current run takes seconds at demo scale. The 15-minute Lambda ceiling is the only real
  argument for async, and it is nowhere near.~~
- ~~Sync keeps errors attached to the invocation. Async means a failed reset is discovered later,
  by something else, with no obvious owner.~~

~~Async only earns its place if reset ever has to handle production-scale data. Which raises:~~

~~**Q1:** is reset only ever expected to run against demo-scale data (hundreds of meetings), or
should it be designed for a production table that has grown large? That single answer decides
sync vs async, and whether it needs paging/batching at all.~~

~~**Q2:** does "deployed as part of the api" mean *in the mootmaker-api repo*, or deployed by the
api's Terraform while living in `mootmaker-admin-tools`? The first removes the cross-repo
coupling entirely; the second keeps admin tooling out of the product repo but leaves two repos
that must be released together. I lean to the first for reset specifically — it is infrastructure
for the API's own data, not a general admin tool.~~

### Decided 2026-09-01

~~- **Demo scale.** Reset stays synchronous, no batching, no paging, no completion signalling.
  Revisit only if data volume ever stops being demo-shaped.~~
~~- **Reset and repair move into `mootmaker-api`.** Not merely deployed by its Terraform — the code
  moves. This removes the cross-repo release coupling entirely, and has a second effect worth
  noticing: it merges the two duplicate `Person.java` models (see the storage-model note below).~~
~~- **Wiping the Cognito user pool becomes part of reset**, contrary to my recommendation of keeping
  it separate. Geoff's call, and the payoff is real — one operation makes an environment
  genuinely indistinguishable from a fresh deploy, which is what lets the acceptance suite reuse
  an environment. Since it is now reachable casually, the guard has to be load-bearing rather than
  advisory. Minimum bar for the design:~~
  - ~~**Refuse `production` outright**, the way `deploy.sh` already refuses anything starting with
    `prod` that is not exactly `production`. A check that can be passed by argument alone is not
    enough; this should be structurally impossible, not merely discouraged.~~
  - ~~**Reinstate the default users** as part of the same operation, or the environment is not
    "fresh" but broken: the demo user, and the e2e user which deliberately has *no* linked Person
    because several specs depend on that. Their passwords need a reproducible source.~~
  - ~~**Say what it deleted.** A silent pool wipe is the worst version of this.~~

---

## Merge sample-data-generator and sample-data-topup into one Lambda

*Raised 2026-08-31.* **Now being designed** in [`../designs/demo-data-component.md`](../designs/demo-data-component.md) (Drafting, 2026-09-02) — the decisions recorded below are carried into it, so refine them there rather than here.

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

**Geoff Response**
The topup tool will never reset the database.  It's indended usage will be to create some data in a freshly deployed ephemeral environment, or to keep production toped up with test data.  If for some reason the developer wants to clear and repopulate a database they will run the database reset and then populate as two distinct manual steps.

The data topup tool should become a first class deployable component alongside the api and the webapp.  We need to consider our deployment process as well, might be time to move from scripts to pipelines.  But we want to make it easy for Claude to deploy emphemerial environments.  Maybe an optional commandline para to the deploy script to say whether to deploy demo data.  But undeploy would need to pick up whether it had been deployed to get a clean undeploy in all cases.  Consider testing needed for the data topup tool.  Remember that demo is a core part of mootmaker, not just a sideline for testing.

**C:** "Demo is a core part of mootmaker" is the load-bearing sentence here, and I think it
answers the flag question against you.

*Drop the optional flag.* You have identified its cost yourself — undeploy would have to work out
whether demo data was deployed. That detection problem is not hypothetical: tearing down this
session's environment today, the teardown script removed the api and webapp state and left
`database-reset` and `sample-data-generator` state orphaned in S3, because it only knows about
two components. I removed those by hand. A flag creates exactly that class of bug, to save a
couple of minutes of deploy time. If demo is core, deploy it always and let undeploy be
unconditional — there is then no state to detect, because there is no "maybe".

If you do keep the flag, the fix is for teardown to *discover* what exists (list the state prefix)
rather than assume a fixed component list. That is worth doing regardless, since it is the general
form of the bug.

*Scripts vs pipelines.* Worth being careful about what the scripts currently are: they are the
shared interface that a human, CI, and Claude all use. A pipeline that reimplements deploy logic
in YAML would take that away — I could no longer stand up an ephemeral environment on demand
without a GitHub Actions round trip, which is a real loss to how this project actually gets built.
The version that keeps both: **pipelines call the scripts**. The script stays the primitive and
single source of truth; the pipeline adds triggering, gating and an audit trail.

*Testing.* `sample-data-topup` already has unit coverage (`MeetingSchedulerTest`,
`SampleDataTopUpTest`, plus a concurrency test). What it has no coverage of is the thing most
likely to break — that it produces *plausible* data against a real deployed API. Cheapest strong
signal: run topup against a fresh ephemeral environment, then assert invariants rather than exact
values (every business day in the window has at least one meeting; no room double-booked; no
person in two overlapping meetings; nothing outside business hours). Those are the same rules the
scheduler claims to enforce, so the test is meaningful rather than a restatement.

**Q3:** is there any environment where you would *not* want the demo tooling deployed? If the
answer is none, that settles the flag question immediately.

### Decided 2026-09-01

**The flag stays; teardown gets fixed properly.** Also contrary to my recommendation — I argued
the flag manufactures the detection problem, Geoff kept it and asked for the underlying bug fixed
instead. That is the more thorough answer: discovery-based teardown is worth having regardless,
because the current failure mode is silent. Today's teardown removed api and webapp state and left
`database-reset` and `sample-data-generator` state orphaned in S3, reporting success throughout.

What the design needs to specify:
- **Teardown discovers components** by listing the environment's state prefix, rather than
  iterating a hardcoded list of two. Then a component nobody remembered is still torn down.
- **`list-ephemeral-envs.sh` already does this correctly** — it found all four components today,
  including the two the teardown script does not know about. So the discovery logic exists and
  just needs to be the thing teardown drives from.
- **An environment is only "gone" when its state prefix is empty.** That is the check worth
  asserting at the end, rather than trusting that the right scripts were called.

---

** graphql sharing **
I want to share the graphql schema between the api and webapp (and later Android) by some more explicit and standard means.   We have a design for this.  I also want to share the storage model/ cognito database shape (come up with a name for this) between the api and the demo data tool.  I guess this means a java library project that publishes versions into somewhere.  Suggest this somewhere I think the schema design says there are GitHub options.  I'd also want to both have build pipelines publish new versions, but when developing be able to use snapshot versions to have changes to both the storage model and other repos before cutting versions.  I'd want the storage model (or whatever we call it) to be it's own repo, rather than having demo data repo depend on the api.  Consider versioning for this, for breaking and non-breaking, and the conventions that would need to be documented so Claude   

**C:** These are two genuinely different problems wearing one hat, and I think they want different
answers.

*The GraphQL half is a code-generation problem, not a library problem.* The schema is already a
single file that the API owns. What is duplicated is the **hand-written mirror** of it —
`webapp/src/graphql/types.ts`, which `mootmaker-webapp/CLAUDE.md` explicitly warns must be updated
by hand whenever the schema changes. That is the pain, and it bit this very feature: adding two
fields meant editing the schema, the Java model, *and* the TypeScript mirror, with nothing but
discipline keeping them aligned. So: publish `mootmaker.graphql` as the artefact, and have each
client **generate** its types from it (GraphQL Code Generator for the webapp, Apollo Kotlin for
Android). No shared Java library needed for this half, and Android gets it free.

*The storage-model half is a real shared library*, and your instinct that it should be its own
repo rather than demo-data depending on the api is right — otherwise a demo tool drags the whole
API in as a dependency.

On the name, three candidates:

| Name | Why | Against |
|---|---|---|
| `mootmaker-data-contract` | "Contract" carries the compatibility obligation, which is the whole point of versioning it. Covers DynamoDB item shapes *and* Cognito attributes without either word in the name. | Slightly abstract |
| `mootmaker-storage-model` | Plain, matches how you already describe it | "Model" understates that breaking it breaks other repos |
| `mootmaker-persistence` | Conventional Java naming | Sounds like a DAO layer, which it is not |

I would take **`mootmaker-data-contract`**, mainly because the name itself tells a future reader
that changing it has obligations.

*Publishing.* GitHub Packages (Maven) is the obvious host — everything is already on GitHub,
auth is `GITHUB_TOKEN`, no new infrastructure. Maven Central is the alternative and has genuine
showcase value for a public portfolio project, at the cost of signing keys and a slower release
ritual. For the develop-across-repos case you describe, note you may not need SNAPSHOT publishing
at all: `mvn install` puts a local build in `~/.m2` and every sibling checkout picks it up
immediately, with zero infrastructure. SNAPSHOTs matter once CI or another machine needs the
in-progress version.

*Versioning.* Semver, with the interesting work being what counts as breaking for each half:

- **Storage:** adding an optional attribute is non-breaking; making an existing one required is
  breaking; renaming is breaking; *changing a default* is subtly breaking, because readers that
  substitute a default disagree about what an absent attribute means. That last one is exactly
  what `Person.fromItem` does today.
- **Schema:** adding a nullable field is non-breaking for readers but breaking for writers if it
  is required in an input. This feature made both fields non-null on purpose — that decision would
  have been a major version bump under these rules, which is a useful sanity check that the rules
  are drawn in the right place.

**Q4:** is the goal to *stop duplication* or to *enforce a contract*? They pull apart: stopping
duplication is served by a shared utility library and a `mvn install` workflow, while enforcing a
contract means versioned releases, compatibility rules, and accepting that a version bump is
sometimes a multi-repo change. The second is more work and buys real safety once Android exists.

### Decided 2026-09-01 — and one factual correction

**The storage-model library is dropped.** The premise did not survive checking: `mootmaker-demo-data`
uses DynamoDB in **zero** Java files. It writes exclusively through the GraphQL API
(`createPerson`, `createRoom`, `createMeeting`, authenticated with OAuth2 client credentials), so
it consumes the *API* model, not the storage model. The real duplicate `Person.java` is between
`mootmaker-api` and `mootmaker-admin-tools/database-repair` — and moving reset and repair into
`mootmaker-api` (decided above) merges those two into one file in one repo.

So there is no second consumer left, and therefore nothing to share, version, or give a repo to.
The name `mootmaker-data-contract` is parked rather than needed.

**Worth keeping in view:** demo-data going through the API is a feature, not an accident — it means
generated demo data is proof the API's own validation accepts it. Moving demo-data to direct
DynamoDB writes would be faster and would let it construct states the API rejects, but it would
also let it generate data the API would never have allowed. If that trade is ever made, the
storage-model library comes straight back.

**The GraphQL half is already designed.** [`../designs/graphql-schema-sharing.md`](../designs/graphql-schema-sharing.md)
(Drafting, 2026-08-29) settles the distribution mechanism — GitHub Packages, hosting npm and Maven
from one account, chosen over versioned S3 objects, Release assets and a schema registry — and
decides to publish the raw `.graphql` file rather than generated types **for a first version**.
My "publish the schema, let each client generate" suggestion is its **NB-1**, deliberately left
open pending evidence of how painful the hand-maintained mirror is with a raw-schema artifact in
place. This feature is that evidence: adding two fields meant editing the schema, the Java model
*and* the TypeScript mirror by hand, with only discipline keeping them aligned.

Its **NB-3** (semver versus commit SHA) is the versioning question raised here, also left open
pending real consumers. Two notes for whoever picks it up: the design assumes the CI/CD pipeline
design lands first, since publishing is a pipeline step; and this feature's non-null
`dateFormat`/`timeFormat` would have been a major bump under semver, which is a useful test that
the classification rules are drawn in the right place.

*Found it, so Q5 withdrawn:* [`../designs/graphql-schema-sharing.md`](../designs/graphql-schema-sharing.md)
(Status `Drafting`, 2026-08-29). Worth reading before either half of this becomes its own design —
if it already settles the publishing question, the storage-model half may just need to follow the
same convention rather than invent a second one.

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
Geoff: suggest a changes, I want consistancy imposed, both in linting if possible so a human and claude are constrained.
  **C:** Concretely, four things, smallest to largest:
  1. Check in a `.prettierrc` with the options the codebase already follows
     (`singleQuote`, `semi: false`, `printWidth: 120` — verified by checking existing files
     against them), and add prettier as a devDependency so it is pinned rather than whatever
     version `npx` happens to fetch. This alone would have prevented the incident above.
  2. Add `format` and `format:check` scripts, and a one-off normalising commit for the ten
     acceptance specs that currently do not conform.
  3. Make it *fail* somewhere, or it will drift again — a pre-commit hook constrains both of us
     equally and gives instant feedback; a CI check is harder to bypass but slower. Both is
     normal: hook for speed, CI as the backstop.
  4. Extend oxlint beyond the current single warning-level rule if you want lint (not just
     format) enforced — that is a bigger conversation about which rules earn their place.

  **Q6:** hook, CI, or both? A hook is the one that actually constrains Claude, since I commit
  from this machine; CI is the one that constrains anything else.

  **Decided 2026-09-01: both.** Pre-commit hook for instant feedback and to constrain Claude
  directly, CI as the backstop that `--no-verify` cannot bypass. Note the hook needs an install
  step that a fresh clone actually runs, or it silently protects nobody.

- **Empty leftover directories from the repo split.** `mootmaker-demo-data/database-reset/` and
  `mootmaker-demo-data/database-repair/` exist on this workstation with zero files and zero git
  entries. Harmless, but they make it look as though those tools live in both repos.
  Geoff: clean up left overs likes this, it's ok to delete empty directory locally.
- **No home for pre-design ideas until now.** The issue board's Backlog holds concrete issues and
  `designs/` starts at `Drafting`; there was no place for a thought that is not yet either. This
  file is that place, which means [`../docs/process/`](process/) does not describe it yet.
  Geoff: lets keep trying this and come up with a formalised process after we have leant what works and what does not a little more.
- **The acceptance suite must run against a fresh environment, and nothing said so.** Re-running it
  against a reused one produced ten failures that all read as real regressions (empty state, room
  ranking, calendar contents) and none were. Now documented in
  `mootmaker-webapp/acceptance/README.md`. **C:** the deeper point is that the failure mode points
  at the code rather than at the environment, so the investigation goes to the wrong place. Worth
  asking whether the suite could *detect* a dirty environment and say so — a preflight check on
  `00-room-availability-empty`'s own precondition would have turned ten misleading failures into
  one accurate message.
  Geoff: what counts as dirty?  Would running the database reset Lambda before running acceptance tools be enough?  Remember we have data in Cognito as well.  Maybe reset should clean up the user pool (and insert the required default users)?
  **C:** This is the most valuable idea in the file, because of what it unlocks: if reset made an
  environment genuinely indistinguishable from a freshly deployed one, the acceptance suite could
  **reuse a long-lived environment** instead of building and destroying one per run. That turns a
  45-60 minute cycle into roughly 25, which changes how often it is worth running.

  What "dirty" means today, concretely, from the ten failures:
  - **Rooms exist.** `00-room-availability-empty` needs zero rooms, and rooms are never deleted
    through the app. Reset already deletes all rooms, so this one is solved by reset.
  - **Meetings exist** on days a spec expects empty, and room capacities skew the suggest-a-room
    rankings. Reset deletes all meetings, so also solved.
  - **Cognito accumulates**, which reset does *not* touch — and you are right that this is the
    gap. Every run creates fresh sign-up accounts that never go away, plus their linked Persons,
    which reset deliberately preserves.

  So yes: reset cleaning the user pool and reinserting the defaults would close it. Three things
  that need deciding if you go there:
  - ~~**A hard production guard.** Deleting Cognito users is the most destructive thing in this
    codebase. Reset currently protects Cognito-linked Persons precisely because they represent
    real people. Wiping the pool must be impossible against `production`, not merely discouraged.
    Arguably it should be a separate operation from reset, so nobody can reach it by accident.~~
    **Settled by [`../designs/archive/admin-tools-into-api.md`](../designs/archive/admin-tools-into-api.md):** the
    guard is structural (a Terraform-computed env var, not a runtime check), and pool-wiping stays
    *part of* reset rather than a separate operation — see Q7 below.
  - ~~**What "required default users" means** — the demo user certainly, the e2e user (which
    deliberately has *no* linked Person, and several specs depend on that), and their passwords
    have to come from somewhere reproducible.~~ **Settled, differently than framed here:** the design
    doesn't reinstate/recreate the default users at all — it never deletes them in the first place
    (preserved by email, alongside every other non-reserved user being removed), which sidesteps the
    password-reproducibility problem entirely rather than solving it.
  - **Whether the suite should verify cleanliness rather than assume it.** Even with a good reset,
    a preflight assertion would have turned today's ten misleading failures into one accurate
    message. That is worth having regardless of how the environment got clean. *Still open — not
    covered by the design above, which only makes reset itself Cognito-aware.*

  ~~**Q7:** should pool-wiping be part of `reset`, or its own operation that reset does not call?
  I lean to separate: reset is run casually, and this is the one action with no undo.~~ **Decided
  (both here on 2026-09-01 and again in the design): part of `reset`.**
- **E.35 looks flaky.** It failed once (room not appearing after creation) and then passed on every
  subsequent run, including two clean full runs. Not reproduced since. **C:** worth watching rather
  than chasing — but note the catalog already flags F.53/F.54/F.57 as intermittently failing, so
  this may be a fourth instance of one underlying cause rather than its own thing. If a pattern
  emerges across those four, that is a real issue rather than a set of separate flakes.
  Geoff: raise it as an issue now.

---

## Discoveries

Facts learned the hard way on 2026-08-31/09-01, none of which had an obvious home at the time.
These are not ideas — they are things that are **true about this project right now** and cost real
time to find out. Several belong in a repository's own docs eventually; where that is, it says so.

- **Deploy scripts use `terraform apply -auto-approve`; undeploy scripts deliberately do not.**
  `deploy.sh` runs unattended. `undeploy.sh` and `teardown-ephemeral-env.sh` prompt Terraform's
  interactive confirmation, so they fail with `error asking for approval: EOF` when run from a
  script or an agent with no stdin. That asymmetry is intentional and documented in the scripts'
  own comments — but it means **any unattended teardown needs `yes yes | ...` or an explicit
  authorisation from Geoff**, which is worth knowing before planning automation around them. It
  also interacts with the "move from scripts to pipelines" idea above: a pipeline has no stdin
  either.

- **A destructive tool sits behind an innocuous-looking script name.**
  `sample-data-generator/run.sh` **resets the database first** — it deletes all rooms, meetings and
  unlinked people before repopulating. On production, which is itself a demo environment, that is
  real data. Deploying the tool is safe; running it is not. The two were kept deliberately separate
  when production was deployed on 2026-09-01. If the generator and topup merge (see above), this
  distinction is the single most important thing the merged design has to get right.

- **The Cognito webapp client allows only `ALLOW_USER_SRP_AUTH` and `ALLOW_REFRESH_TOKEN_AUTH`.**
  There is no `USER_PASSWORD_AUTH` or `ADMIN_USER_PASSWORD_AUTH`, so **nothing can obtain a user's
  access token programmatically without implementing SRP** (or using `amazon-cognito-identity-js`,
  which does). This is why seeding a preset account on 2026-09-01 set its preference by writing to
  DynamoDB directly rather than by calling the mutation. Any future tooling that wants to act *as a
  user* rather than as the machine hits this wall. ~~Worth remembering when designing reset's
  "reinstate the default users" step.~~ Turned out not to matter there —
  [`../designs/archive/admin-tools-into-api.md`](../designs/archive/admin-tools-into-api.md) has reset *preserve*
  the demo/e2e accounts rather than delete-and-recreate them, so this constraint is never hit.

- **Business hours (08:00–17:00) are exactly the range sample-data fills**, so in a populated
  environment **no time slot is free by construction**. `MeetingScheduler` uses
  `BUSINESS_DAY_START_HOUR = 8` / `END_HOUR = 17`, and the webapp's own `businessHours.ts` agrees.
  A test that needs a bookable slot cannot simply pick a time — it has to pick a room that happens
  to be free, or retry across rooms. Each room gets only 0-2 generated meetings a day, so retrying
  finds one almost immediately. *Belongs in `mootmaker-webapp/acceptance/README.md` eventually.*

- **Playwright's `getByLabel` matches substrings, including on containers.**
  Giving a Settings section `aria-label="Your name"` made `getByLabel('Name')` ambiguous, because it
  matched both the Name field and the section. `aria-label="Date and time format"` would have
  collided with `getByLabel('Time format')` the same way. **Adding an accessible name to a container
  can break unrelated tests**, so scope by structure (`locator('section').filter({ has: heading })`)
  rather than by naming the container. *Belongs in `mootmaker-webapp/acceptance/README.md`
  eventually.*

- **Piping a test run through `tail`, `grep` or `head` discards its exit code.**
  A shell pipeline returns the *last* command's status, so `./run.sh | tail -60` reported success
  for a run with ten failures, and the buffering meant no progress output for 31 minutes. Redirect
  to a file and read it instead, or set `pipefail`. This cost more time tonight than any actual bug.
  *Belongs in the repo-level agent guidance eventually — it is a trap for humans too, but agents hit
  it constantly because they habitually pipe for brevity.*
