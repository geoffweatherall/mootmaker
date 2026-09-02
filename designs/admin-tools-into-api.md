# Move database-reset and database-repair into mootmaker-api

## Summary

`database-reset` and `database-repair` move out of `mootmaker-admin-tools` and become two more
Lambda functions built and deployed by `mootmaker-api` itself — new handler classes in `impl/`,
new resources in `deploy/terraform/`, no separate repo, no separate deploy step. This removes the
cross-repo release coupling ideas.md flagged (`mootmaker-demo-data` and `mootmaker-api`'s own
acceptance tests both depend on `database-reset` being deployed first, purely by convention) and
merges the two duplicated `Person`/`MeetingParticipant` models back into one. It also gives `reset`
a new, more thorough job: wiping the Cognito user pool (production excepted) as well as DynamoDB,
so a reset environment is genuinely indistinguishable from a freshly deployed one.

## Status

**Ready** — 2026-09-02.

## Scope / non-goals

In scope: relocating both tools' code, Terraform, and deploy/undeploy mechanics into
`mootmaker-api`; extending `reset` to also clear the Cognito user pool (except the two
Terraform-managed reserved accounts) in every environment except `production`; closing the
"stray Person" gap as a consequence of that; updating every cross-repo reference
(`mootmaker-demo-data`, `mootmaker-api/verify`, the hub repo's docs) to the new location; retiring
`mootmaker-admin-tools`' `run.sh` wrappers in favour of direct `aws lambda invoke`.

Explicitly **not** in scope:

- **Reusing a long-lived environment for the webapp acceptance suite.** That idea (`docs/ideas.md`'s
  "Loose threads" — Q7) is exactly what a Cognito-clean `reset` unlocks, but changing
  `mootmaker-webapp/acceptance/run.sh`'s always-fresh-environment convention is a separate decision
  with its own trade-offs (preflight cleanliness checks, run-time savings vs. shared-environment
  flakiness) that deserves its own design once this one has shipped and been used for a while.
- **Merging `sample-data-generator`/`sample-data-topup`** (a separate, still-open idea in
  `docs/ideas.md`) or moving `mootmaker-demo-data` anywhere. That repo keeps invoking `reset`
  exactly as it does today — only the Lambda's address changes, not the calling convention.
- **A storage-model shared library.** Already decided against in `docs/ideas.md` — merging these
  two tools into `impl/` removes the only real duplicate (`Person.java`) without needing one.
- **Reseeding or otherwise changing what data `production` carries.** This design tears production
  down and rebuilds it as part of rollout (see Rollout & migration), but that's purely about
  clearing the ground for the new Lambda names — whatever normally happens to `production` after a
  fresh deploy today keeps happening the same way; this design doesn't add or change any seeding
  step.

## Trade-offs and decisions

Resolved directly with Geoff via upfront questions before drafting:

- **Code moves into `impl/`, not a new independent Maven module.** `post_confirmation_create_person`
  already establishes the precedent this follows exactly: a second (and here, third/fourth) Lambda
  function, its own handler class, deployed from the *same* shaded jar (`impl/target/mootmaker-api.jar`)
  as the resolvers function — no new build step, no new `pom.xml`. The concrete payoff: `reset` and
  `repair` can call `com.mootmaker.model.Person.fromItem`/`toItem` directly instead of maintaining
  the hand-mirrored subset copy each tool has today, so this move deletes two duplicate `Person.java`
  files and two duplicate `MeetingParticipant.java` files, not just relocates code.
- **`reset`'s Cognito wipe preserves the two reserved accounts by email, deletes every other user.**
  Rejected the more literal "delete everyone including demo/e2e, then recreate them" reading of
  ideas.md's "reinstate the default users," because recreating a Cognito user is not idempotent in
  the way that phrase implies: Cognito assigns a fresh, unpredictable `sub` on every `AdminCreateUser`
  call, which would leave the demo Person's `cognitoSub` (set once, by Terraform, at first deploy —
  see `deploy/terraform/cognito.tf`'s `aws_dynamodb_table_item.demo_person`) pointing at a user that
  no longer exists, breaking the demo login until something relinked it. It would also fight
  Terraform, which believes it owns `aws_cognito_user.demo`/`.e2e` and would see a resource it
  didn't change disappear and reappear with a different identity underneath. Preserving them instead
  costs nothing (nobody's asking to reset the demo account specifically) and buys three things at
  once: no password-reproducibility problem to solve, no `sub`-relinking problem, and it reuses a
  list that already exists — `RESERVED_ACCOUNT_EMAILS`, defined in `deploy/terraform/lambda.tf`'s
  `resolver_lambda_env_vars` local today purely to stop `DeleteMyAccountHandler` from self-deleting
  either account. `reset` gets the same env var, same source of truth, one more consumer.
- **In `production`, `reset` still cleans DynamoDB — it just skips the Cognito step.** Matches
  `database-reset`'s current, explicitly documented behaviour ("safe to run against production").
  Refusing the whole operation in production would be a real regression: production has never had a
  real signed-up user, precisely because it's a public demo, so periodically clearing the rooms and
  meetings a stranger created is a real, currently-used capability. Only the *new* Cognito-wipe
  capability needs the hard guard — DynamoDB cleanup already has one (only-delete-if-unlinked).
- **No wrapper script.** `run.sh` goes away entirely; both Lambdas are invoked with plain
  `aws lambda invoke`, the same way a human or an AI would invoke anything else. `mootmaker-api`'s
  own acceptance tests already do this — `verify/src/test/java/com/mootmaker/verify/DatabaseReset.java`
  calls the Lambda via the AWS SDK directly, no shell script in between — so this isn't a new
  pattern, it's extending an existing one to the one remaining caller (a developer's terminal) that
  still went through a script.
- **Function names don't change.** `mootmaker-api`'s existing `resource_prefix` local already
  evaluates to `<environment>-mootmaker` (`deploy/terraform/locals.tf`), so naming the new resources
  `${local.resource_prefix}-database-reset` / `-database-repair` reproduces
  `<environment>-mootmaker-database-reset` / `-database-repair` exactly — the same deterministic name
  `mootmaker-demo-data/sample-data-generator` and `verify.sh` already compute today. **Neither of
  those needs to change how it names the function** — only the Terraform stack that owns it changes.
- **DynamoDB/Cognito Terraform data-source reads across repos disappear.** Today,
  `mootmaker-admin-tools/*/deploy.sh` reads `mootmaker-api`'s Terraform outputs to discover table
  names and the Cognito pool ID before it can deploy. Once the resources are defined in the same
  Terraform state, this becomes a direct local reference (`aws_dynamodb_table.rooms.arn`,
  `aws_cognito_user_pool.this.id`, etc.) — one whole category of cross-repo deploy-time dependency
  removed, not just the Lambda-invoke one ideas.md originally flagged.
- **`mootmaker-admin-tools` is deleted outright**, not archived and not kept as a placeholder.
  Nothing else is expected to land there — the "destructive admin tooling" category this repo was
  named for turned out to have exactly two members, and both move here — so an empty repo with a
  stale README would be pure maintenance liability for no benefit.
- **Rolling out to `production` means a full, deliberate outage: tear the whole deployed stack down
  and redeploy it from scratch**, rather than the more surgical "undeploy just the two old Lambdas,
  then deploy the new ones into the gap" sequencing an earlier draft of this design used. Geoff's
  call: `production` is a public demo, not a real business system with real uptime expectations, and
  a short outage is a straightforwardly simpler and safer release than trying to choreograph a
  zero-gap cutover between two separate Terraform states around a Lambda-function-name collision.
  This removes essentially every migration-sequencing risk in this design at the cost of the demo
  site being briefly unreachable — a trade this project has made before for exactly this reason
  (`deploy.sh` itself calls `terraform apply -auto-approve` unattended because getting the trade-off
  wrong here doesn't cost anything real).
- **Both Lambdas' timeout is set to 900 seconds — the AWS Lambda maximum — not the 300 s each tool
  configures today.** There's no reason to guess a smaller number: the concurrency design in both
  (`runInParallel`, bounded at 8) already exists specifically to stay "comfortably inside a Lambda
  invocation's 15-minute hard ceiling as stored data volume grows" (both tools' own READMEs use
  almost that exact phrase), so the real ceiling worth configuring against is the ceiling itself.
  Raising the configured timeout costs nothing — Lambda bills for actual duration, not the timeout
  setting — and removes a number (300s) that was never derived from an actual worst-case estimate.
- **`database-repair`'s `--dry-run` is kept**, expressed the same way it already partly is in the
  Lambda's own contract — an invoke payload field, `{"dryRun": true}` — rather than a script flag.
  `aws lambda invoke --function-name <env>-mootmaker-database-repair --payload '{"dryRun": true}'
  --cli-binary-format raw-in-base64-out out.json` replaces `./run.sh <environment> --dry-run`.
- **`reset` logs the email address of every Cognito user it deletes**, not just a count — one line
  per deletion, to CloudWatch, the same style `CreateMissingPersonsRepair` already uses for its own
  per-user log lines (`"  demo@mootmaker.com -> creating Person 'demo'"`). This is what "say what it
  deleted" (ideas.md) actually means for the highest-consequence deletion this Lambda does.
- **`runInParallel`/`MAX_CONCURRENT_REQUESTS` gets merged into one shared helper inside
  `mootmaker-api`**, used by both `reset` and `repair` once they're both handler classes in the same
  module — the two copies becoming one is a direct consequence of them landing in the same repo, not
  a new library. **`sample-data-generator`'s own copy in `mootmaker-demo-data` stays exactly as
  duplicated as it is today** — that repo gets no dependency on `mootmaker-api`, matching the
  storage-model decision above (no shared code *between* repos, only *within* one). Lives in a new
  package, `com.mootmaker.concurrent`, alongside `handler`/`model`/`dynamo`/`cognito`.
- **`reset`'s JSON response reports a count of deleted Cognito users, not the full email list.**
  Keeps the response shape consistent with the existing DynamoDB counts (`roomsDeleted`, etc.); the
  full list stays a CloudWatch Logs query away for anyone who needs to know exactly which accounts
  were removed.

## Choices you had me make

- **Each Lambda keeps its own dedicated, narrowly-scoped IAM role**, rather than reusing the shared
  `aws_iam_role.lambda_exec` every resolver already uses. The shared role already has
  `dynamodb:Scan`/`DeleteItem` on all four tables (so reusing it would technically work), but
  `database-reset`'s own README calls out its narrow role as deliberately "narrower than what the
  shared Lambda execution role inside mootmaker-api used to need for this" — reusing the shared role
  would quietly undo a least-privilege property that was engineered on purpose. The two new roles are
  close copies of `mootmaker-admin-tools`' existing `iam.tf` files, just pointed at local resources
  instead of remote-state ARNs. Worth revisiting if the per-function-role pattern ever feels like
  ceremony rather than protection.
- **The production/Cognito-wipe guard is a Terraform-computed environment variable
  (`ALLOW_COGNITO_WIPE = environment != "production"`), not an invoke-payload flag.** `reset`'s
  payload is `{}` today and this keeps it that way — whether wiping Cognito is allowed is a property
  of *which environment this Lambda is deployed to*, decided once at deploy time, the same way
  `deploy.sh` itself decides `production`-ness from the environment argument rather than trusting
  whatever the caller passes at invoke time.
- **The wipe removes every non-reserved user regardless of confirmation status** — `UNCONFIRMED`
  users included, unlike `database-repair`'s `CreateMissingPersonsRepair`, which deliberately skips
  them. Abandoned, never-verified sign-up attempts are exactly the kind of accumulated cruft a
  "make this environment fresh again" operation should clear; there is no Person to protect for a
  user who never confirmed.
- **`reset` looks up the two reserved users' actual `sub`s via `ListUsers` at run time**, rather than
  trusting the `cognitoSub` already stored on their Person records, before deciding which People
  survive. This is what closes the "stray Person" gap (see next section) — the previous logic only
  ever checked "does this Person have *a* `cognitoSub`", never "does that Cognito user still exist".

## Open questions

None remain, blocking or non-blocking. The two blocking questions that existed while drafting
(`mootmaker-admin-tools`'s fate, and what to do with the superseded parts of `docs/ideas.md`) are
resolved above and in `docs/ideas.md` itself (struck through with a pointer back to this doc, rather
than deleted outright, since the surrounding "Packaging of the tools and sample data generation"
entry also covers `mootmaker-demo-data` packaging/versioning questions this design doesn't touch).
The two non-blocking questions raised afterward (whether `reset`'s response lists deleted emails,
and where the merged concurrency helper lives) are resolved in Trade-offs and decisions above.

## Impacts on components

**`mootmaker-api`:**

- `impl/src/main/java/com/mootmaker/handler/` gains `DatabaseResetHandler` and
  `DatabaseRepairHandler`; a new `com.mootmaker.reset`/`com.mootmaker.repair` package (or similar)
  gains the actual logic (`DatabaseReset`, `CreateMissingPersonsRepair`,
  `RebuildMeetingParticipantsRepair`) — ported from `mootmaker-admin-tools`, adapted to import
  `com.mootmaker.model.Person`/`MeetingParticipant`/`MeetingRecord` instead of each tool's own copy.
  A new `com.mootmaker.concurrent` package gains the merged `runInParallel`/`MAX_CONCURRENT_REQUESTS`
  helper (see Trade-offs and decisions), used by both handlers instead of each keeping its own copy.
- `impl/src/test/java/...` gains the corresponding test classes (`DatabaseResetTest`,
  `DatabaseResetHandlerConcurrencyTest`, `CreateMissingPersonsRepairTest`,
  `RebuildMeetingParticipantsRepairTest`, `DatabaseRepairHandlerConcurrencyTest`, plus fakes
  `FakeDynamoDbClient`/`FakeCognitoIdentityProviderClient`).
- `impl/pom.xml` needs no new dependency — `cognitoidentityprovider` is already there (for
  `UpdatePersonHandler`/`PostConfirmationCreatePersonHandler`), and so is `dynamodb`.
- `deploy/terraform/` gains a new file (e.g. `admin-tools.tf`) with the two `aws_lambda_function`
  resources, their `aws_iam_role`/`aws_iam_role_policy` pairs, and the `ALLOW_COGNITO_WIPE` /
  `RESERVED_ACCOUNT_EMAILS` env vars. Both get `timeout = 900` (the Lambda maximum — see Trade-offs
  and decisions), up from the 300s each configures today. No `aws_lambda_alias`/SnapStart needed —
  unlike the resolvers and post-confirmation functions, nothing invokes these frequently enough for
  cold-start latency to matter.
- `deploy.sh`/`undeploy.sh` need **no changes** — they already build the one jar and apply the one
  Terraform state; the new resources just come along for the ride.
- `verify.sh`/`verify/.../DatabaseReset.java` — the function-name computation
  (`$1-mootmaker-database-reset`) doesn't change, so no code change; the class's doc comment
  referencing `mootmaker-admin-tools/database-reset` needs updating to point at `mootmaker-api`
  itself.
- `README.md`: rewrite "Reset and real user accounts" (describes the new Cognito behaviour and the
  production guard), add `database-reset`/`database-repair` to the directory-structure and
  "How it is implemented" sections, update the "Build, test, deploy" section's tool list.
- `AGENTS.md`/`CLAUDE.md`: likely a short addition noting these two Lambdas live here now and are
  invoked by raw `aws lambda invoke`, not a script — mirroring how it already documents other
  cross-repo facts.

**`mootmaker-admin-tools`:** the whole repo is deleted, on GitHub as well as locally, once its
Lambdas have been undeployed from every environment that has them — see Rollout & migration.

**`mootmaker-demo-data`:** `sample-data-generator`'s `deploy/terraform/locals.tf`
(`database_reset_function_name`/`_arn` computation) and `iam.tf`
(`invoke_database_reset` policy) don't need to *change their values* — the computed ARN is identical
— but their comments explicitly say "now in `../mootmaker-admin-tools`" and need updating to say
`mootmaker-api` instead, and the README's "A dependency this split did not remove" section (in
`mootmaker-admin-tools`, being deleted) has no new home unless it's folded into
`mootmaker-demo-data`'s own README or `mootmaker-api`'s. `DatabaseResetInvoker`'s `LambdaClient`
also needs its client-side call timeout raised to match `database-reset`'s new 900s Lambda timeout
(see Technical considerations) — a small, genuine code change, not just a doc-comment fix.

**Hub repo (`mootmaker`):**

- `docs/reference/data-model.md`'s "Known gap" line ("a stray Person record ... has no repair; not
  even `database-reset` today") needs rewriting — the gap is closed going forward (see Technical
  considerations for the caveat about *existing* strays).
- `docs/ideas.md` — the reset/repair-relevant parts of "Packaging of the tools and sample data
  generation" and one bullet under "Loose threads" are already struck through, pointing back here.
- Any other doc referencing `mootmaker-admin-tools` by name for these two tools (a repo-wide link
  check via `tools/check-links.py` after the docs change would catch stragglers).

**`mootmaker-webapp`:** no code change. Its acceptance suite doesn't invoke `reset` today (see Scope)
so nothing here breaks or needs updating beyond an incidental mention if any exists.

## Changes to the domain data model and data storage models

No new DynamoDB attributes, no new Cognito attributes — the shapes in
`docs/reference/data-model.md` are unchanged. What changes is a *behaviour* the reference document
describes:

- The "Known gap" note under Cross-references (a stray Person with a dangling `cognitoSub` "has no
  repair; not even `database-reset` today") stops being true for any reset that runs after this
  ships, in every non-production environment: `reset` now determines survivorship from Cognito's
  actual current user list, not from whether a `cognitoSub` attribute happens to be present, so a
  Person whose Cognito account is gone no longer survives just because the attribute wasn't cleared.
  This needs rewriting in `data-model.md`, and should note the caveat below rather than claim the gap
  is fully closed everywhere.

## Technical considerations

- **Two different Person-survival rules, by environment, and getting them backwards would be
  serious.** When the Cognito wipe runs (every environment except `production`): a Person survives
  only if its `cognitoSub` matches the demo user's actual current `sub` (looked up fresh via
  `ListUsers`/`RESERVED_ACCOUNT_EMAILS` — the e2e user has no Person to begin with, so it never
  enters this check). When the wipe is skipped (`production`): fall back to today's rule — a Person
  survives if it has *any* non-null `cognitoSub`, full stop, exactly as `database-reset` does now.
  Using the non-production rule in production would delete real signed-up users' Person records the
  moment their account happened not to be `demo@mootmaker.com`.
- **Existing strays aren't retroactively cleaned.** Any Person already carrying a dangling
  `cognitoSub` from before this ships stays exactly as stray as it is today — this design closes the
  gap for reset going forward, it doesn't backfill. If any are known to exist, they still need
  deleting directly via DynamoDB once, same as today.
- **Cognito IAM additions.** The reset Lambda's role needs `cognito-idp:ListUsers` (new — today's
  `database-reset` role has none) and `cognito-idp:AdminDeleteUser` (already precedented — the
  shared resolver role already grants this to `DeleteMyAccountHandler`, scoped to the whole pool
  ARN since Cognito IAM actions don't support per-user resource scoping — the *code*, not IAM, is
  what stops it deleting a reserved account).
- **`ListUsers` pagination.** `database-repair`'s `CreateMissingPersonsRepair` already has a working
  pagination loop (60-per-page, follows `paginationToken`) — `reset`'s wipe should reuse that same
  shape rather than reinvent it, now that both live in the same module.
- **`RESERVED_ACCOUNT_EMAILS` becomes a second-consumer env var.** It's currently wired only to the
  resolvers Lambda (for `DeleteMyAccountHandler`) in `lambda.tf`'s `resolver_lambda_env_vars` local;
  the new reset function needs the same value, read from the same Terraform expression, so the two
  functions can never disagree about which accounts are reserved.
- **`sample-data-generator` must not be affected mid-migration.** Because its function-name
  computation is unchanged, it will start working again the moment `mootmaker-api`'s replacement
  Lambda exists under the same name — no `mootmaker-demo-data` *deploy* is needed as part of this
  migration, only the doc-comment corrections and the client-timeout change noted below.
- **Raising the Lambda's own timeout to 900s only helps if every caller's *client-side* timeout is
  raised to match, or a legitimately-long run gets reported as a failure while the Lambda quietly
  keeps running (or even succeeds) in the background.** Three callers, three places to check: the
  AWS CLI defaults `--cli-read-timeout` to 60s (needs raising, e.g. `--cli-read-timeout 900`, or `0`
  for no timeout, in every documented example command); `verify/.../DatabaseReset.java`'s
  `LambdaClient` needs an explicit `ClientOverrideConfiguration` with an `apiCallTimeout` of at least
  900s (the SDK default is shorter); `sample-data-generator`'s own `DatabaseResetInvoker` needs the
  same client-side timeout raised, a small addition to `mootmaker-demo-data` prompted by this
  migration even though none of its invocation *logic* changes. Easy to overlook because the
  failure it causes is confusing — a client-reported timeout for an invocation that actually
  succeeded — rather than an obvious break.

## Testing impacts

- **Unit tests move with the code** (see Impacts on components) and gain the same fakes-based
  coverage they have today (`FakeDynamoDbClient`, `FakeCognitoIdentityProviderClient`) — no test
  currently exercises real AWS, so none of this changes how they run, only where they live.
- **New unit coverage needed** for the two behaviours that don't exist yet: the Cognito-wipe pass
  itself (deletes every non-reserved user, preserves the two reserved ones by email, works across
  a paginated `ListUsers` result, logs each deleted user's email), and the environment-gated skip
  (`ALLOW_COGNITO_WIPE=false` results in the DynamoDB-only, cognitoSub-presence-based cleanup path,
  not the Cognito-driven one). Also needs coverage for the merged `runInParallel` helper now serving
  two callers instead of one each.
- **`mootmaker-api`'s acceptance suite** (`verify/`) already resets via this Lambda before most
  tests — worth adding one acceptance test that specifically signs up a real (throwaway) user,
  invokes reset, and asserts that user's Person is gone and the demo/e2e accounts still work
  afterward — proof the production-adjacent logic (survivorship-by-actual-Cognito-state) behaves
  correctly against a real deployed pool, not just the fakes.
- **A manual pass against `production`'s existing reset behaviour** before/after this ships, since
  `production` is the one environment where a regression (the whole operation refusing to run, or
  the DynamoDB-only path accidentally deleting a real signed-up demo visitor's account) would be
  publicly visible and is exactly the risk this design's production guard is meant to prevent.

## Documentation impacts

- `mootmaker-api/README.md` — "Reset and real user accounts" section rewritten for the new Cognito
  behaviour, the production guard, and that deletions are logged by email; directory structure and
  "Build, test, deploy" sections gain the two tools, with an example `aws lambda invoke` command for
  each (including `--cli-read-timeout` and, for `database-repair`, the `{"dryRun": true}` payload).
- `mootmaker-api/CLAUDE.md`/`AGENTS.md` — short addition: these two Lambdas live here, invoked via
  raw `aws lambda invoke`, not a script.
- `mootmaker-admin-tools/README.md`/`AGENTS.md` — deleted along with the rest of the repo.
- `mootmaker-demo-data`'s `sample-data-generator/README.md` and `DatabaseResetInvoker`'s doc comment
  — update the "which repo owns database-reset" cross-reference.
- `mootmaker/docs/reference/data-model.md` — the "Known gap" line, as above.
- `mootmaker/docs/ideas.md` — already struck through (see Impacts on components above); re-check
  once implementation is done in case anything else in that file turns out to reference these tools.
- Run `python3 tools/check-links.py ..` from the hub repo after all doc edits, per its own `CLAUDE.md`.

## Rollout & migration

`production` already has `database-reset`/`database-repair` deployed under `mootmaker-admin-tools`'
own Terraform state, using the exact function names `mootmaker-api`'s new Terraform is about to try
to create. Rather than choreograph a gap-free handover between two separate states around that
naming collision, **`production` is fully torn down and redeployed from scratch as part of this
rollout**:

1. **`[Geoff]` Undeploy `production` entirely, in dependency order**: `mootmaker-webapp`, then
   `mootmaker-api`, then both `mootmaker-admin-tools` tools. Every one of these prompts for
   interactive confirmation (none of the `undeploy.sh` scripts pass `-auto-approve`), so this is a
   human-at-the-keyboard step, not automatable. **This is a deliberate, real outage** — the public
   demo site is offline from this point until step 3 finishes. Acceptable because `production` here
   is a demo, not a system with real uptime expectations, and it keeps this rollout simple rather
   than clever.
2. **`[Claude]` Delete the `mootmaker-admin-tools` repository** (GitHub and any local checkout) —
   there is nothing left pointing at it once `production`, and every other environment that had it
   deployed, no longer references its Terraform state.
3. **`[Claude]` Deploy `production` fresh**, in the normal dependency order: `mootmaker-api` (now
   including `database-reset`/`database-repair`), then `mootmaker-webapp`. The new Lambda functions
   are created under the same names the old ones had, in a Terraform state that has never heard of
   `mootmaker-admin-tools`.
4. **`[Geoff]` Confirm `production` is back**: the site loads, the demo and e2e logins work, and a
   manual `aws lambda invoke` against the new `database-reset` function succeeds.
5. Any ephemeral environment that happened to have these tools deployed is simply torn down and not
   recreated (ephemeral environments are disposable by definition — see
   `mootmaker-test-infra/list-ephemeral-envs.sh` to check whether any exist first). No environment's
   *data* is migrated anywhere — this only ever moves tooling, never stored rooms/meetings/people.

## Risks

- **A planned `production` outage** — see Rollout & migration above. Accepted deliberately rather
  than mitigated: the alternative (a gap-free two-state cutover) trades a bounded, known outage
  window for real sequencing complexity, on a system where an outage costs nothing but the site
  being briefly unreachable. The one thing that *would* turn this into a real problem is the
  redeploy (step 3) failing partway and leaving `production` down for longer than intended — normal
  `deploy.sh` failure modes apply here, nothing new to this design.
- **The Cognito-wipe survivor list is the single highest-consequence piece of logic in this design.**
  A bug that computes `RESERVED_ACCOUNT_EMAILS` incorrectly, or that runs the wipe against an
  environment the guard should have caught, deletes real Cognito users irreversibly. Mitigated by:
  the guard being a Terraform-computed env var rather than trusted invoke input; reusing the
  already-proven `RESERVED_ACCOUNT_EMAILS` mechanism rather than inventing a new one; and the new
  unit + acceptance coverage called out above specifically targeting this path.
- **Broader IAM surface on the reset Lambda** — it gains `cognito-idp:ListUsers`/`AdminDeleteUser`
  where today it has no Cognito access at all. Scoped to exactly this Lambda's own dedicated role
  (see "Choices you had me make"), not the shared resolver role, so this doesn't broaden what any
  *other* function can do.
- **Not easily reversible once shipped and used.** Once `mootmaker-admin-tools` is deleted and a
  few resets have run against real environments under the new Cognito-wipe behaviour, reverting
  to the old split-repo, DynamoDB-only design would mean re-splitting merged model classes back out
  — cheap in git terms (revert the PR), just worth naming as "not free" rather than "trivial."

## Implementation checklist

1. `[Claude]` Port `database-reset`'s and `database-repair`'s logic into `mootmaker-api/impl/`,
   merging `Person`/`MeetingParticipant`/`MeetingRecord` onto the existing model classes; port unit
   tests and fakes.
2. `[Claude]` Implement the Cognito-wipe pass in `reset` (list users, filter `RESERVED_ACCOUNT_EMAILS`,
   delete the rest) and the `ALLOW_COGNITO_WIPE` environment gate; implement the two
   Person-survival code paths described under Technical considerations.
3. `[Claude]` Add the new unit tests called out under Testing impacts (wipe behaviour, gate behaviour).
4. `[Claude]` Add the two `aws_lambda_function` + dedicated-role resources to
   `mootmaker-api/deploy/terraform/`, wired to `RESERVED_ACCOUNT_EMAILS` and `ALLOW_COGNITO_WIPE`.
5. `[Claude]` Update `mootmaker-demo-data`'s doc comments/README cross-references and raise
   `DatabaseResetInvoker`'s client-side call timeout to match `database-reset`'s new 900s Lambda
   timeout; confirm `sample-data-generator` still runs against a redeployed ephemeral environment.
6. `[Claude]` Add the new acceptance test (sign up, reset, assert survivors) to `mootmaker-api/verify/`.
7. `[Claude]` Update all documentation impacts listed above; run `tools/check-links.py`.
8. `[Geoff]` Undeploy `production` entirely — `mootmaker-webapp`, then `mootmaker-api`, then both
   `mootmaker-admin-tools` tools — accepting the outage this causes. Interactive, needs a human.
9. `[Claude]` Delete the `mootmaker-admin-tools` repository.
10. `[Claude]` Redeploy `production` from scratch — `mootmaker-api` (with the new Lambdas included),
    then `mootmaker-webapp`.
11. `[Geoff]` Confirm `production` is back: site loads, demo/e2e logins work, a manual
    `aws lambda invoke` against the new `database-reset` succeeds.

## Definition of done

- `mootmaker-api`'s full unit suite (`mvn -f impl/pom.xml test`) green, including the new
  reset/repair/Cognito-wipe coverage.
- `mootmaker-api`'s acceptance suite (`./verify.sh <environment>`) green on a freshly deployed
  ephemeral environment, including the new sign-up/reset/survivor test.
- `production` fully torn down and redeployed from scratch, confirmed working (site, demo/e2e
  logins, a manual `database-reset` invoke) by Geoff; `mootmaker-admin-tools` deleted entirely.
- `mootmaker-demo-data/sample-data-generator` confirmed still working against a fresh ephemeral
  environment, with only its client-side invoke timeout changed.
- Every item under Documentation impacts actually edited, not just planned, and `tools/check-links.py`
  clean.
