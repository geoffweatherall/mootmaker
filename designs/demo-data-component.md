# demo-data as a first-class component: one Lambda, one deployable

## Summary

`sample-data-generator` and `sample-data-topup` merge into a single Lambda in a restructured
`mootmaker-demo-data` repo, laid out like `mootmaker-api` (`impl/`, `verify/`, `deploy/terraform/`,
`deploy.sh`/`undeploy.sh`/`verify.sh`). That leaves the project with exactly **three deployable
components — api, webapp, demo-data** — one per repo, one Terraform state key each. demo-data is
always deployed to `production` (demo is a core part of MootMaker, not test scaffolding) and is
opt-in for ephemeral environments. It gains its own Cognito M2M app client instead of borrowing the
acceptance tests', and its own acceptance suite that asserts the *invariants* generated data must
satisfy rather than exact values.

## Status

**Drafting** — 2026-09-02.

## Scope / non-goals

In scope: merging the two tools into one Lambda with three independently-toggleable top-up concerns
(people, rooms, meetings); restructuring `mootmaker-demo-data` to mirror `mootmaker-api`'s shape;
giving demo-data its own M2M app client and a secret-delivery mechanism that keeps the secret out of
Terraform state and Lambda environment variables; adding a `verify/` acceptance suite; making
demo-data the third component in `create-ephemeral-env.sh` (opt-in) and
`teardown-ephemeral-env.sh` (discovery-driven, per the [2026-09-01 decision in
`../docs/ideas.md`](../docs/ideas.md)).

Explicitly **not** in scope:

- **Reset, in any form.** Settled by Geoff on 2026-09-01: the merged tool will never reset the
  database. `DatabaseResetInvoker` and its test are deleted outright, not carried over. Clearing and
  repopulating an environment stays two deliberate manual steps — invoke `database-reset` (now in
  `mootmaker-api`, see [`archive/admin-tools-into-api.md`](archive/admin-tools-into-api.md)), then
  invoke demo-data. This removes the single most dangerous property either tool has today: that
  `sample-data-generator/run.sh`, an innocuously-named script, destroys data as its first action.
- **Moving deployment into pipelines.** Raised alongside this in `ideas.md` and worth doing, but it
  is [`ci-cd-pipeline.md`](ci-cd-pipeline.md)'s problem. This design keeps scripts as the primitive
  so a pipeline can later call them — it does not pre-empt that decision.
- **A shared Java library between demo-data and the api.** Dropped on 2026-09-01 after checking:
  demo-data touches DynamoDB in zero Java files. It writes exclusively through the GraphQL API, so
  there is no storage model to share. See `ideas.md`'s "the storage-model library is dropped".
- **The acceptance suite's own preflight cleanliness check.** Still open in `ideas.md`, belongs to
  the webapp suite, unaffected either way by this design.

## Trade-offs and decisions

### One Lambda, not two — and the duplication it deletes

The two tools duplicate `GraphQlClient` (110 lines, byte-identical), `SampleData` and
`MeetingScheduler`. `MeetingScheduler` is the one that matters: **the two copies have already
drifted**, because topup takes an explicit `List<LocalDate>` of empty days while the generator takes
a contiguous `startDayOffset`/`endDayOffsetInclusive` range. That is one scheduling algorithm forked
across two repositories' worth of build, deploy and test, maintained twice by discipline alone.
Merging deletes the fork rather than documenting it.

The merged signature is topup's: an explicit list of days. The generator's contiguous range is
simply "every business day in the window", which the caller can compute — so the general form
absorbs the specific one with no loss.

### Seeding and topping up are the same operation, not two modes

This is the decision that makes the merge simple. The generator's job was "fill a 8-week window";
topup's job is "fill any business day in a 6-week window that has no meetings". On a freshly-deployed
environment *every* day in the window is empty, so topup's rule already produces a full seed. There
is no "seed mode" to add and no mode flag to get wrong — one code path, whose behaviour differs only
because the data it finds differs.

This also answers `ideas.md`'s concern that "daily against a 6-week window is a no-op almost every
run, so the interesting path is exercised rarely": the full-window path is exactly what runs against
a fresh environment, which is exactly what the new acceptance suite does on every run. The rarely-
exercised path becomes the continuously-tested one.

### Three top-up concerns, each with its own guard

| Concern | Target | Guard (what makes it idempotent) |
|---|---|---|
| People | `TARGET_PEOPLE` (default 40) | Create `max(0, target - current)`. No-op once at target. |
| Rooms | `TARGET_ROOMS` (default 10) | Create `max(0, target - current)`. No-op once at target. |
| Meetings | every weekday in `WEEKS_AHEAD` (default 6) | A day with any existing meeting is skipped — today's rule, unchanged. |

Each is independently toggleable via the invoke payload (`{"people": false}`), all defaulting to
enabled, so a scheduled run with an empty payload does all three.

### Concurrency is handled structurally, not in code

`ideas.md` flags that two concurrent runs could both observe 30 rooms and both create 10. Rather than
add locking, set the Lambda's **reserved concurrency to 1**. A second overlapping invocation is
throttled by Lambda itself — visibly, with a 429 for a synchronous caller and EventBridge's own retry
for the scheduled one. It costs nothing, cannot be forgotten, and needs no code. The existing
in-process bounded parallelism (`MAX_CONCURRENT_REQUESTS = 8`) is unaffected; that is parallelism
*within* one run.

### demo-data gets its own M2M identity

Today demo-data authenticates as `COGNITO_TEST_CLIENT_ID` — **the acceptance tests' app client** —
with its secret read from `mootmaker-api`'s Terraform outputs at deploy time, passed through
`TF_VAR_`, and written into the Lambda's plaintext environment variables. Three separate problems:

1. **Wrong identity.** Two unrelated consumers share one credential, so neither can be rotated or
   revoked without breaking the other, and CloudTrail cannot tell them apart.
2. **The secret lands in two places it should not be.** Lambda environment variables are readable by
   anyone with `lambda:GetFunctionConfiguration`, and the value is also persisted in demo-data's own
   Terraform state.
3. **A deploy-time coupling to another repo's Terraform state.** `deploy.sh` sources
   `../mootmaker-api/authenticate.sh`, which runs `terraform init`/`output` against the api's state.
   Every other cross-repo reference in this project is deliberately loose — a deterministic name
   (`database-reset`), or a `data` source (`aws_ses_domain_identity`, `aws_route53_zone`).

The fix, in the same loose-coupling style: `mootmaker-api` defines a **`<prefix>-demo-data` app
client** with the `execute` and `admin` scopes, and writes its id and secret to SSM Parameter Store
**SecureString** parameters at deterministic paths:

```
/mootmaker/<environment>/demo-data/client-id
/mootmaker/<environment>/demo-data/client-secret
```

demo-data's Lambda reads them **at runtime** with `ssm:GetParameter` (plus `kms:Decrypt` on the
AWS-managed `alias/aws/ssm` key), so the secret never enters demo-data's Terraform state, never
appears in an environment variable, and the deploy no longer needs the api's state at all — only the
environment name, which it already has. Standard-tier SSM parameters and the AWS-managed SSM key are
both free, which matters: a customer-managed KMS key would be $1/month per key per environment, the
exact cost that killed the email-bypass design in `mootmaker-api/testing-strategy.md`.

### `production` gets demo-data always; ephemeral gets it on request

Geoff's framing settles this: demo is a core part of MootMaker, so on the one long-lived environment
it is not optional. Ephemeral environments are created for a specific piece of work, and most of that
work does not need 600 generated meetings — so it is opt-in there, via a flag on
`create-ephemeral-env.sh`.

The flag was contested. I argued it manufactures a detection problem for teardown; Geoff kept it and
asked for the underlying teardown bug fixed properly instead (decided 2026-09-01). That is the more
thorough answer, and this design implements it: **teardown discovers what is deployed** by listing
the environment's state prefix in S3, rather than iterating a hardcoded list. `list-ephemeral-envs.sh`
already does exactly this discovery correctly — it found all four components of a live environment on
2026-08-29, including the two teardown does not know about — so the logic exists and just needs to be
what teardown drives from.

Collapsing to three components is what makes discovery tractable: the mapping from state key to
undeploy script becomes a three-entry table, and **any key not in that table is a hard failure**, not
a silent skip. That is the property today's script lacks, and why it reported success while leaving
`database-reset` and `sample-data-generator` state orphaned in S3.

**An environment is only "gone" when its state prefix is empty.** That becomes teardown's final
assertion, rather than trusting that the right scripts were called.

### The schedule is disabled by default outside `production`

`var.schedule_enabled` already exists. Defaulting it to `var.environment == "production"` means a
leaked ephemeral environment does not also sit there invoking a Lambda daily against an API that may
itself be half-torn-down. It can be enabled deliberately for a test.

## Choices you had me make

- **Component name and resource prefix: `mootmaker-demo-data`**, so the Lambda is
  `<env>-mootmaker-demo-data` and the state key `<env>/mootmaker-demo-data/terraform.tfstate`. Three
  components, three repo names, three state keys, all matching. Cheap to change now, annoying later.
- **`run.sh` wrappers are retired** in favour of documented `aws lambda invoke` commands in the
  README — following the precedent
  [`archive/admin-tools-into-api.md`](archive/admin-tools-into-api.md) set for the same reason. This
  is the choice most worth overriding if you disagree: a `run.sh <environment>` is genuinely handier
  here than it was for the admin tools, because this is a thing you will run casually against
  ephemeral environments.
- **Daily schedule, not weekly** (`cron(0 6 * * ? *)`). The cost difference is about six cents a year
  (see below), so this is a data-freshness decision, not an economic one — and a daily run keeps the
  far edge of the 6-week window populated more evenly.
- **Targets are Terraform variables, not payload fields.** Keeping `TARGET_PEOPLE`/`TARGET_ROOMS` out
  of the invoke payload means a mistyped ad hoc invoke cannot create 4,000 people. Toggles are in the
  payload; magnitudes are in the deployment.
- **`verify/` uses JUnit `*IT.java` and `verify.sh <environment>`**, mirroring `mootmaker-api`
  exactly rather than inventing a second convention.

## Open questions

**Blocking**

1. **What does "top up people" count against?** `ideas.md` raised this and it is still open — but
   checking the schema turned it from a preference into a constraint. **`Person` does not expose
   `cognitoSub` or any linked/unlinked indicator**, and demo-data reaches the system only through
   GraphQL. So "top up to 40 *unlinked demo* people" is not implementable as things stand; it would
   need either a new schema field (exposing account-linkage publicly, for a demo tool's benefit) or
   direct DynamoDB access (which resurrects the shared-storage-model problem deliberately dropped on
   2026-09-01).

   **My recommendation: count total people.** No schema change, no DynamoDB access, and the failure
   mode is benign — in an environment where real sign-ups have pushed the count past 40, demo people
   are not needed, because there are already enough bookable people. The consequence to accept is
   that on `production`, real signed-up users are already booked into generated demo meetings today
   (`query { people { id } }` returns everyone), and this keeps that true. If that is not acceptable,
   the answer changes to a schema field and this becomes a bigger design.

**Non-blocking**

2. **Should `WEEKS_AHEAD` also backfill the past?** The generator seeds 7 days of history
   (`DAYS_IN_PAST = 7`); topup is forward-only. A freshly-seeded environment under the merged tool
   would have an empty past, which changes what the webapp's calendar looks like on day one. Easy to
   add as a fourth concern; needs deciding before the acceptance suite asserts either way.
3. **Where does demo-data's acceptance suite run in a future pipeline?** It needs a deployed api, so
   it cannot run on every push cheaply. Deferred to [`ci-cd-pipeline.md`](ci-cd-pipeline.md).

## Impacts on components

**`mootmaker-demo-data`** — restructured to mirror `mootmaker-api`:

```
mootmaker-demo-data/
  AGENTS.md, CLAUDE.md -> AGENTS.md, README.md, testing-strategy.md
  deploy.sh  undeploy.sh  verify.sh
  impl/          DemoDataHandler, DemoDataTopUp, MeetingScheduler, SampleData, GraphQlClient, SsmSecrets
  verify/        acceptance ITs (see Testing impacts)
  deploy/terraform/   lambda.tf iam.tf schedule.tf locals.tf variables.tf outputs.tf provider.tf versions.tf backend.hcl
```

Deleted: both `sample-data-*/` trees, `deploy-all.sh`, `undeploy-all.sh`, both `run.sh`, both
`undeploy.sh`, `DatabaseResetInvoker.java` + `DatabaseResetInvokerTest.java` + `FakeLambdaClient.java`,
and one full copy each of `GraphQlClient`/`MeetingScheduler`/`SampleData`. Also the two empty
leftover `database-reset/`/`database-repair/` directories noted in `ideas.md`.

**`mootmaker-api`** — `deploy/terraform/cognito.tf` gains the `demo-data` app client; a new
`deploy/terraform/demo-data-credentials.tf` (or an addition to `cognito.tf`) writes the two SSM
SecureString parameters. `authenticate.sh` is unchanged — demo-data simply stops calling it.

**`mootmaker-test-infra`** — `create-ephemeral-env.sh` gains `--with-demo-data`;
`teardown-ephemeral-env.sh` is rewritten around state-prefix discovery and gains the
empty-prefix assertion; this closes `mootmaker-test-infra#2`.

**`mootmaker`** (hub) — `docs/process/environments.md`'s "Known gap" section is deleted once teardown
is fixed; `docs/reference/testing-strategy.md` and `docs/development/` gain demo-data as a third
component; `docs/ideas.md`'s "Merge sample-data-generator and sample-data-topup" section is marked
superseded by this design.

## Changes to the domain data model and data storage models

**N/A** — no new tables, attributes, indexes or Cognito user-pool schema changes. The one new
persisted thing is two SSM parameters, which are configuration, not domain data.

Worth stating explicitly because it is load-bearing for the blocking open question above: this design
**relies on** the existing property that `Person` has no publicly-exposed link to a Cognito account.
See [`../docs/reference/data-model.md`](../docs/reference/data-model.md) for the storage-level
`cognitoSub` attribute that is deliberately not surfaced in the schema.

## Technical considerations

- **Fetch the M2M token once per run, not per request.** Cognito M2M token requests are billed with
  no free tier (see below). One token per run is ~$0.81/year; one per GraphQL call would be ~600×
  that on a seed run. `GraphQlClient.fromEnvironment()` already gets this right — the merged class
  must keep it right.
- **`ALLOW_USER_SRP_AUTH` only.** The webapp Cognito client permits no `USER_PASSWORD_AUTH`, so
  nothing can obtain a *user's* token programmatically without implementing SRP. demo-data must stay
  M2M-only; it can never act "as" a demo user.
- **Business hours are 08:00–17:00, exactly the range generated data fills**, so in a populated
  environment no slot is free by construction. Relevant to any acceptance assertion about
  availability — assert over a room that happens to be free, never a fixed time.
- **The Lambda timeout must exceed a full-window seed.** Today's topup is 300s at 512MB; a seed
  creating ~600 meetings at 8-way concurrency fits comfortably, but follow `admin-tools.tf`'s
  precedent and set the AWS maximum (900s) rather than a guessed number — Lambda bills actual
  duration, so a high ceiling costs nothing.
- **`terraform destroy` still evaluates `lambda_jar_hash`**, hence the existing
  `fileexists(...) ? ... : null` guard. Carry it over; `undeploy.sh` must work without a built jar.
- **`TF_DATA_DIR=".terraform-${environment}"` isolation** is load-bearing for concurrent deploys from
  one checkout. Carry it over unchanged.

## Testing impacts

**Unit** (`impl/src/test/`) — the existing `MeetingSchedulerTest`, `SampleDataTopUpTest` and the
concurrency test survive the merge, deduplicated to one copy. New coverage needed for the
people/rooms top-up arithmetic (`max(0, target - current)`, including the already-at-target and
over-target cases) and for payload toggle parsing, including the default-everything-on case.

**Acceptance** (`verify/`, new) — this is the layer that does not exist today, and `ideas.md` already
identified what it should assert: **invariants, not exact values**. Against a freshly-deployed
environment, seeded by one real invocation of the Lambda:

- every business day in the window has at least one meeting;
- no room is double-booked;
- no person is in two overlapping meetings;
- no meeting falls outside 08:00–17:00, and none on a Saturday or Sunday;
- room and person counts equal their targets;
- **a second invocation is a near-no-op** — the idempotency guard, and the one assertion that would
  have caught a regression in any of the three new guards.

These are the rules `MeetingScheduler` claims to enforce, asserted against real data the API actually
accepted — so the suite is meaningful rather than a restatement of the implementation.

**On the api dependency**: demo-data's acceptance suite needs a deployed `mootmaker-api`, exactly as
`mootmaker-webapp`'s does. That is an accepted shape in this project, not a new compromise — it is
the cost of testing a component whose entire job is to call another component. The practical
consequence is that demo-data's suite is the slowest to stand up, so it should be able to run against
an **existing** ephemeral environment rather than always creating its own (`verify.sh <environment>`
already takes an environment name, so this is usage, not code).

**Existing tests that change**: none in other repos. `mootmaker-api`'s own acceptance suite is
unaffected — it uses its own app client, and this design stops demo-data borrowing it.

## Documentation impacts

- `mootmaker-demo-data/README.md` — rewritten: one component, one Lambda, no reset, `aws lambda
  invoke` examples, the M2M/SSM auth model, and an explicit "this tool never destroys data" statement
  to replace today's buried warning that `run.sh` resets first.
- `mootmaker-demo-data/AGENTS.md` — new structure and the three-component picture.
- `mootmaker-demo-data/testing-strategy.md` — new file, mirroring `mootmaker-api/testing-strategy.md`.
- `mootmaker-api/README.md` — the new `demo-data` app client and SSM parameters, alongside the
  existing acceptance-test client documentation.
- `mootmaker/docs/process/environments.md` — delete the "Known gap" paragraph; document
  `--with-demo-data` and discovery-based teardown.
- `mootmaker/docs/reference/testing-strategy.md`, `mootmaker/README.md` — three components, not two
  plus tools.
- `mootmaker/docs/ideas.md` — mark the merge section superseded by this design, in the established
  strikethrough-plus-pointer style.

## Rollout & migration

No data migration and no transition state — this replaces tooling, not stored data.

1. **Ephemeral first.** Stand up an environment, deploy api + demo-data from the feature branches,
   run the new acceptance suite. This is the real test of the merge, the new app client and the SSM
   secret path together.
2. **Teardown rewrite is validated on the same environment** — tear it down, then assert the state
   prefix is empty, which is the bug being fixed.
3. **`production` last, and in a specific order**: deploy `mootmaker-api` (creating the app client and
   SSM parameters) *before* `mootmaker-demo-data`, or the new Lambda has no credentials to read. Then
   destroy the two old tools' resources and remove their now-empty state objects.

Reversible: the old tools are two Terraform roots and a jar; reverting is a `git revert` plus a
redeploy. The one thing that is not reversible for free is deleting the old state objects — do that
only after the new component is confirmed working.

## Risks

- **Deleting the old state objects too early** orphans live Lambdas with nothing tracking them —
  precisely the failure this design fixes elsewhere. Undeploy first, confirm empty, then delete.
- **The `production` ordering trap** above: deploying demo-data before the api's new app client
  exists gives a Lambda that fails on every invocation with an SSM `ParameterNotFound`. Low blast
  radius, but confusing if unexpected.
- **Real users appear in generated demo meetings.** True today, and the recommended answer to the
  blocking question keeps it true. On a public demo environment this is arguably fine — arguably even
  desirable — but it is a deliberate choice, not an oversight.
- **One Lambda for three concerns means one failure blast radius.** A bug in the people top-up now
  runs in the same invocation as meetings. The toggles mean a broken concern can be switched off
  without redeploying, which is most of the mitigation.
- **`ideas.md`'s original concern #1 is designed out, not mitigated.** The destructive path is not
  "unreachable from the schedule" — it does not exist in this component at all. Worth stating because
  it is the single most important property of this design, and any future "just add a reset flag"
  request should be read against it.

## Implementation checklist

*(Sparse while Drafting — filled in properly before Ready, per the process.)*

1. `[Claude]` `mootmaker-api`: add the `demo-data` app client and the two SSM SecureString
   parameters; deploy to an ephemeral environment and confirm the parameters resolve.
2. `[Claude]` `mootmaker-demo-data`: restructure to the api-mirroring layout; merge the two impls
   into one, deduplicating `GraphQlClient`/`MeetingScheduler`/`SampleData`; delete the reset path.
3. `[Claude]` Add the people/rooms top-up concerns, the payload toggles, and reserved concurrency 1.
4. `[Claude]` Port and deduplicate the unit tests; add the new arithmetic/toggle coverage.
5. `[Claude]` Write `verify/` and `verify.sh`; get a green run against a fresh ephemeral environment.
6. `[Claude]` `mootmaker-test-infra`: `--with-demo-data`, discovery-based teardown, empty-prefix
   assertion; close `mootmaker-test-infra#2`.
7. `[Claude]` Documentation sweep per "Documentation impacts".
8. `[Geoff]` Deploy to `production` in the stated order, then decommission the two old tools.

## Definition of done

- The merged component's own unit tests and the new acceptance suite are green against a real,
  freshly-deployed ephemeral environment, and `mootmaker-api`'s and `mootmaker-webapp`'s existing
  suites are still green on that same environment.
- A full lifecycle works end to end: `create-ephemeral-env.sh --with-demo-data`, seed, verify, then
  `teardown-ephemeral-env.sh` leaving the environment's state prefix **empty** — checked against live
  AWS, not the script's exit code.
- `production` runs the merged Lambda on schedule, the two old Lambdas and their state objects are
  gone, and no credential for demo-data remains in any Lambda environment variable or Terraform state.
- Everything under "Documentation impacts" is actually done.

## Appendix: cost impact

Rates checked 2026-09-02 against AWS's published pricing (us-east-1).

### Steady-state `production`, daily schedule

| Line | Volume/month | Cost |
|---|---|---|
| Lambda requests | 30 | $0 — 1M/month always-free |
| Lambda compute (512 MB, ~10 s/run) | ~150 GB-s | $0 — 400,000 GB-s/month always-free (~$0.0025 without it) |
| EventBridge scheduled rule → Lambda | 30 | $0 — scheduled rules targeting an AWS service directly are not billed |
| SSM Parameter Store (standard, AWS-managed key) | 60 reads | $0 |
| AppSync operations (~25/run incremental) | ~750 | ~$0.003 at $4.00/million |
| **Cognito M2M token requests** | **30** | **~$0.07 — $0.00225 each, no free tier** |

**Under $0.10/month, dominated by the one line that is never free.** Cognito M2M has no free tier at
all, so it is the only cost that exists from the first invocation. At one token per run it is
~$0.81/year; the discipline that keeps it there is fetching the token once per run rather than per
GraphQL call.

Daily versus weekly is a difference of roughly **six cents a year**. Choose the cadence on data
freshness, not cost.

### Per ephemeral environment (opt-in)

**Standing cost: zero.** An idle Lambda, an IAM role and a disabled EventBridge rule are all free —
demo-data adds nothing to the cost of a leaked environment, which remains driven by the api's and
webapp's DynamoDB tables, CloudFront distribution and AppSync API.

A one-off full seed is ~650 AppSync operations plus one token — under a cent. The real cost of the
new acceptance suite is **time, not money**: it needs a deployed api, so a run is a ~15–20 minute
stand-up. That is the argument for pointing `verify.sh` at an existing environment rather than
creating one per run.

### What the merge saves

One Lambda function, one IAM role, one EventBridge rule, one Terraform state object, one deploy
step — and ~370 lines of duplicated Java that had already drifted. None of that is a meaningful
dollar saving; the saving is in what no longer has to be kept in sync, and in a teardown that can
enumerate three components instead of guessing at four.

### Caveat

AppSync's 250,000-operation free tier applies only for 12 months after account creation and may
already have expired for this account; the table above assumes it has, and prices AppSync at the
standard rate. Every other $0 line is an always-free tier with no expiry.
