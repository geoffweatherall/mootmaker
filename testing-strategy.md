# Testing strategy

This document records the overall testing strategy across this project's repositories —
[mootmaker-api](https://github.com/geoffweatherall/mootmaker-api),
[mootmaker-webapp](https://github.com/geoffweatherall/mootmaker-webapp) (and, later,
`mootmaker-android`), and [mootmaker-test-infra](https://github.com/geoffweatherall/mootmaker-test-infra)
(the shared test infrastructure any frontend depends on) — and, specifically, how developing this
project largely by "vibe coding" with Claude (see this README's ["I should vibe
more"](README.md#i-should-vibe-more) and ["Impacts on the test
pyramid"](README.md#impacts-on-the-test-pyramid)) shapes that strategy differently than it would
for a conventionally hand-reviewed codebase.

Each repository also has its own `testing-strategy.md` with the detail specific to it:

- [mootmaker-api/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-api/blob/main/testing-strategy.md)
- [mootmaker-webapp/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/testing-strategy.md) —
  including its `e2e/` and `acceptance/` suites; each frontend owns its own, not shared centrally.
- [mootmaker-test-infra/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-test-infra/blob/main/testing-strategy.md) —
  only the pieces genuinely shared across frontends (ephemeral-environment lifecycle, the SES
  email-reading pipeline). Formerly `mootmaker-e2e`, which also used to own a full-stack test suite
  itself — see that repo's README for the 2026-08-19 rename/restructure.

This document is the map between them: the overall layering, the decisions that cut across repos
(ephemeral environments, how verification-code emails get read in tests), and the "vibe coding"
reasoning behind it. [mootmaker/use-cases.md](use-cases.md) is the client-agnostic scenario list
each frontend's own `acceptance/` suite draws on.

## Goals

Two goals shape every decision below, and they pull in different directions:

1. **Find real system failures** — not just logic bugs, but the failures that only show up once
   the pieces are actually wired together: a Terraform misconfiguration, an IAM permission gap, a
   Cognito trigger that silently doesn't fire, a GraphQL schema mismatch between API and webapp, a
   cold-start timing issue, an email that never arrives.
2. **Stay fast enough that Claude actually uses it while developing**, not just in CI after the
   fact. See [How "vibe coding" shapes this strategy](#how-vibe-coding-shapes-this-strategy) below
   — this is the newer, less obvious of the two goals, and the one most likely to be
   under-weighted by default.

Every layer below trades these off against each other: real infrastructure catches real failures
but is slow, costly, and non-deterministic; mocks and unit tests are fast and free but can't see a
wiring mistake between two systems that were never actually connected during the test.

## Layers

| Layer | Repo | Environment | Speed | Determinism | Best at catching |
|---|---|---|---|---|---|
| Unit tests | mootmaker-api (`impl/`) | none (JVM) | seconds | fully deterministic | validation rule bugs, DynamoDB query construction, capacity/overlap math |
| Acceptance tests | mootmaker-api (`verify/`) | real deployed AWS, ephemeral | ~minutes deploy + seconds | mostly deterministic (real Cognito M2M, no email) | IAM/permission gaps, Terraform misconfig, AppSync↔Lambda wiring, GSI/table design, server-side auth boundaries |
| Lint + typecheck | mootmaker-webapp | none | seconds | fully deterministic | dead code, type drift |
| Unit tests | mootmaker-webapp (Vitest) | none | seconds | fully deterministic | pure logic: date/time formatting, error-message mapping, suggested-room caching, organiser/attendee filtering, room-colour assignment |
| Integration tests | mootmaker-webapp (Playwright + MSW) | none (mocked GraphQL, mocked auth) | seconds | fully deterministic | page-level wiring: right query fires, validation errors render, success navigates, `RequireAuth` gates correctly |
| e2e | mootmaker-webapp (`e2e/`) | real deployed AWS, ephemeral | minutes | least deterministic, especially the real-email cases | real Cognito email delivery, DNS/certs, CloudFront/S3 serving, cross-service integration nothing else can see |
| Acceptance tests | mootmaker-webapp (`acceptance/`) | real deployed AWS, ephemeral | minutes | least deterministic, especially the real-email cases | use cases in [use-cases.md](use-cases.md) actually being satisfied end to end through the real UI, not just that the infrastructure behind them works |

Each frontend (`mootmaker-webapp`, later `mootmaker-android`) owns its own `e2e`/`acceptance` pair
in its own repo, using whatever's idiomatic for that platform — nothing here is shared *test code*
across frontends, only the infrastructure in
[mootmaker-test-infra](https://github.com/geoffweatherall/mootmaker-test-infra) (ephemeral-env
lifecycle, the SES email pipeline) is.

**Built 2026-08-15**: the webapp's Vitest and MSW-mocked-integration layers exist now (30 unit
tests, 27 integration tests, both independently verified green) — see
[mootmaker-webapp/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/testing-strategy.md).
The old live-API Playwright suite was **replaced in place**, not kept alongside the new one (an
explicit choice): `webapp/tests/*.spec.ts` now needs no live AWS environment, deployed API, or real
Cognito user at all.

**Built 2026-08-19**: `mootmaker-webapp/e2e/` (three specs: sign-up, forgot-password, smoke — moved
from the old `mootmaker-e2e` repo, unchanged in behaviour) and a first thin slice of
`mootmaker-webapp/acceptance/` (two use cases: sign-up with a real emailed code, add-a-meeting with
the demo user). The other ~97 use cases in `use-cases.md` remain a checklist, not yet automated —
see `mootmaker-webapp/acceptance/README.md` for the pattern to follow when adding more.

## Reading Cognito's emails in tests

Sign-up and forgot-password both require entering a code Cognito emails to the user — automating
either flow end-to-end means reading that email somehow, or avoiding needing to.

**Reading the real email (SES → SNS → SQS)** is the only mechanism for tests where a genuinely
real code matters. A subdomain's MX record points at Amazon SES; a receipt rule publishes the
message to an SNS topic (SES receipt rules can't deliver to SQS directly), which an SQS queue is
subscribed to; the test long-polls the queue and parses the code out of the real email body. Slower
and less deterministic than a bypass would have been (real mail delivery, a real network hop), but
it's the only thing that actually proves Cognito's email sending is configured and working.
Reserved for a small number of e2e/acceptance tests in each frontend (e.g.
`mootmaker-webapp/e2e/sign-up.spec.ts`) whose specific purpose is proving that path works — never
needed anywhere the code itself is the only thing under test (see below).

This infrastructure is **one persistent, shared pipeline** — deployed once, like
mootmaker-domain's hosted zone, not created and destroyed per ephemeral environment. AWS SES only
allows one *active* receipt rule set per region per account, so standing up a fresh rule set for
every ephemeral e2e run would mean concurrent runs fighting over which one is active; a single
always-on rule set matching everything under one subdomain avoids that entirely. Each e2e run
instead sends its Cognito sign-up/reset to a **uniquely-tagged address** under that shared
subdomain and filters the SQS queue for messages addressed to its own tag, ignoring anyone else's
— so concurrent runs don't see each other's mail even though the pipeline itself is shared.

It's split across two repos by what it actually is: the domain identity and MX record live in
[mootmaker-domain](https://github.com/geoffweatherall/mootmaker-domain) (DNS, shared and
persistent, alongside the rest of that zone), while the receipt rule, SNS topic, and SQS queue
live in [mootmaker-test-infra](https://github.com/geoffweatherall/mootmaker-test-infra) (test-only
infrastructure, shared across every frontend). Both are deployed once and left running, not tied to
any single ephemeral environment's lifecycle.

**Deployed 2026-08-15**: the account's SCP allow-list
([mootmaker-bootstrap-aws-accounts](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts)'s
`scp-guardrails.yaml` and `identity-center.yaml`) was updated to include `ses`/`sns`/`sqs`, and both
mootmaker-domain's SES domain identity and mootmaker-test-infra's (then still `mootmaker-e2e`'s)
receipt rule/SNS/SQS pipeline are now live. `mail.mootmaker.com` genuinely receives mail, and this
pipeline is now exercised end-to-end by `mootmaker-webapp/e2e/sign-up.spec.ts` and
`forgot-password.spec.ts` (built 2026-08-19).

**Bypassing the code requirement entirely**, for tests that don't care about exercising the
real code-entry UI step (most don't — only "correct code succeeds" scenarios do; a "wrong code is
rejected" test can submit any wrong value without knowing the real one): Cognito's Admin API lets
a caller with `cognito-idp` permissions skip the code requirement outright —
`AdminConfirmSignUp` confirms a sign-up with no code at all, and `AdminSetUserPassword` sets a
password with no reset code at all. No new infrastructure needed for this at all (`cognito-idp:*`
is already SCP-allowed, and both are plain AWS SDK calls test code can make directly) — but neither
actually exercises the real code-entry UI, so it's not a substitute for reading the real email
where that specifically matters, only a way to avoid needing *any* code-reading mechanism for tests
that just need a working account.

**Dropped, 2026-08-15**: a `CustomEmailSender`-trigger-based bypass (decrypting Cognito's real code
via a KMS-encrypted delivery, no real email needed) was built, unit-tested, and `terraform
validate`-clean, but removed before ever being applied. It was blocked by the same SCP gap (`kms`
wasn't allowed either), and once that was understood, the cost stopped making sense: a
customer-managed KMS key is billed a flat $1/month *per key* regardless of use — unlike everything
else in this project, which is pure pay-per-request — and as designed would have been created per
ephemeral environment rather than shared, plus the AWS Encryption SDK dependency it needed took the
shared Lambda jar (every function in mootmaker-api ships from one jar) from ~7.2 MB to ~24 MB. Not
worth carrying for a feature that was never going to be free to run and still needed an SCP change
either way. See mootmaker-api's own `testing-strategy.md` for the detail.

## Environments

Three kinds of environment now exist, each with a distinct purpose (see mootmaker's own
[Multi-environment deployments](README.md#multi-environment-deployments) for the underlying
mechanism — this section only adds the policy on top of it):

- **`production`** — the real, long-lived public deployment.
- **`test`** — now reserved for **human manual testing only**. Automated tooling, Claude included,
  no longer deploys to or runs tests against it.
- **Ephemeral environments** — created and destroyed freely, one per purpose, named by convention
  so they're identifiable and machine-cleanable: `<kind>-<YYMMDD>-<rand4>`, where `kind` identifies
  exactly what created the environment, not just that it's ephemeral:
  - `claude-<YYMMDD>-<rand4>` — Claude's own interactive dev-session environments (e.g.
    `claude-260815-x7q2`), reused for a whole session rather than per-task.
  - `<frontend>-<tier>-<YYMMDD>-<rand4>` — an automated test suite's own run, e.g.
    `web-e2e-<YYMMDD>-<rand4>` / `web-acc-<YYMMDD>-<rand4>` for `mootmaker-webapp`'s `e2e/run.sh` /
    `acceptance/run.sh`. `and-e2e-*`/`and-acc-*` expected once `mootmaker-android` gains the same
    pattern. **Changed 2026-08-19** — previously a single generic `e2e-<YYMMDD>-<rand4>` covered
    every automated run regardless of which frontend or test tier created it; that stopped being
    distinguishable the moment a second frontend needed the same pattern. See
    [mootmaker-test-infra/testing-strategy.md#naming-convention](https://github.com/geoffweatherall/mootmaker-test-infra/blob/main/testing-strategy.md#naming-convention)
    for the full detail, including the character budget this leaves under the ceiling below.

  Naming by creator/purpose (rather than one shared prefix) so a cleanup pass (or a human glancing
  at the AWS console) can tell a stale dev sandbox apart from a specific automated suite's
  in-progress run without needing extra metadata. The timestamp is
  deliberately compact (day only, no time-of-day) and the random suffix short (4 chars) to leave
  headroom under AWS resource-name length limits once `<environment>-<project-name>-...` is
  assembled. The original design (`<YYMMDD>-<HHmm>-<rand4>`, 1 character longer) guessed S3 bucket
  names/Cognito domain prefixes (63 chars) would be the tightest constraint — real deployment
  testing on 2026-08-15 found otherwise: mootmaker-api's longest Lambda function name
  (`mootmaker-post-confirmation-create-person`, 64-char hard limit) is the actual binding one, at
  22 characters max for the environment name. The day-only form (18/15 characters) clears that with
  margin to spare.

### Ephemeral environment lifecycle

- **Creation**: Claude creates a fresh `claude-*` environment at the start of a session where it's
  about to write code, deploy, or run tests that need a live environment — not for a docs-only or
  read-only conversation. It reuses that same environment for the rest of the session rather than
  creating a new one per task.
- **Cleanup prompt**: when Claude is about to make a commit, it asks whether the ephemeral
  environment currently in use should be torn down, rather than silently leaving it running or
  silently destroying it. (This is recorded as a standing instruction for Claude — see the note
  below.)
- **Scripts** (built and verified end-to-end 2026-08-15; a fourth added 2026-08-19): four separate bash scripts, living in
  [mootmaker-test-infra](https://github.com/geoffweatherall/mootmaker-test-infra) alongside the
  other cross-cutting test infrastructure — see
  [mootmaker-test-infra/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-test-infra/blob/main/testing-strategy.md#ephemeral-environment-scripts)
  for the full design and reasoning. Naming ended up `claude-<YYMMDD>-<rand4>` (day-only, no
  time-of-day) rather than the originally-designed `<YYMMDD>-<HHmm>-<rand4>` — real deployment
  testing found the longer form 1 character over a Lambda function-name limit. In short:
  - `create-ephemeral-env.sh` — generates a name and calls each project's own `deploy.sh` in
    sequence.
  - `teardown-ephemeral-env.sh <name>` — calls each project's own `undeploy.sh` for one specific,
    already-known environment (what the commit-time cleanup prompt above uses), then removes that
    environment's now-empty state files from the shared state bucket so it stops showing up in
    `cleanup-stale-envs.sh`'s discovery afterward.
  - `cleanup-stale-envs.sh` — the batch sweep, for anything left behind by an interrupted session.
    Discovers every environment matching the `<kind>-<YYMMDD>-<rand4>` convention (any recognized
    `kind`, not just `claude`/`e2e`) via the shared Terraform state bucket
    ([mootmaker-bootstrap-terraform](https://github.com/geoffweatherall/mootmaker-bootstrap-terraform))
    — every project's state key is `<environment>/<project-name>/terraform.tfstate`, so listing
    that bucket's keys and grouping by the first path segment gives a reliable, centralised list of
    every environment across every project, with no separate registry needed — then lists
    everything it finds and asks for confirmation before tearing down each one, matching
    `undeploy.sh`'s own always-interactive, no-`-auto-approve` safety pattern rather than an age
    threshold or a pick-list menu.
  - `list-ephemeral-envs.sh` (added 2026-08-19) — read-only, destroys/deletes nothing. For every
    discovered environment's state files, counts the resources actually tracked inside; empty ones
    are a completed teardown's leftover state object, safe to delete directly. For nonzero counts,
    cross-checks against real AWS via `terraform plan -refresh-only` — distinguishing benign drift
    (tags, ACM validation finishing, etc. — still genuinely deployed) from resources actually
    confirmed gone, rather than treating any refresh difference as "gone" (an early version did
    exactly that and was corrected after testing against a real environment showed it produced
    false positives — see
    [mootmaker-test-infra/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-test-infra/blob/main/testing-strategy.md#ephemeral-environment-scripts)
    for the detail). Complements `cleanup-stale-envs.sh` by making the distinction visible up front.

  The first three are thin orchestrators over the existing per-project `deploy.sh`/`undeploy.sh` —
  none of the actual deploy mechanics get duplicated.

> **Note to Claude, in future sessions**: this workflow (create a `claude-*` environment when
> starting dev/deploy work; ask before a commit whether to tear down the one in use; never deploy
> to or test against `test`) is also recorded in memory under `ephemeral-env-workflow`, so it
> persists even if this file isn't re-read.

## How "vibe coding" shapes this strategy

This project is built by prompting Claude rather than by hand-writing and meticulously reviewing
every line (see the main README's ["I should vibe more"](README.md#i-should-vibe-more) and
Claude's own pushback on it). That changes what a test suite is *for*, not just what it covers, in
a few concrete ways:

**Tests are closer to the spec than the prose is.** When code isn't getting line-by-line human
review, the test suite is doing more of the work review used to do — catching "this doesn't do
what was actually asked" before it ships, not after. `functionality/business-functionality.md` is
already this project's closest thing to a source-of-truth spec (see the README's own note that
this becomes the more valuable asset once code and tests are both cheap to regenerate); the tests
are what keep the running system honest against it. Practically: updating or adding a test
alongside any behaviour change is treated as close to mandatory, not optional polish — especially
for anything covered by the API's validation-rules table, the kind of implicit spec that's easy
for either Geoff or Claude to silently drift from without something pinning it down.

**Feedback-loop speed determines what actually gets used while developing, versus what only runs
at the end.** The fast, free, deterministic layers (lint, typecheck, unit tests, mocked-API
integration tests) are the ones Claude should run constantly — many times per task, after nearly
every change. The slow, costly, real-infrastructure layers (API acceptance tests, full-stack e2e)
should run once per feature, not once per edit: a Terraform deploy takes minutes and costs real,
if small, money, and a flaky failure there is expensive to triage mid-iteration. If the fast layers
are thin, Claude ends up leaning on the slow layer far more than intended — the opposite of the
goal, and the main reason the webapp's mocked-API layer is worth investing in early rather than
treating as optional.

**A flaky test is worse for an agent than for a human.** A human skims a red CI run and thinks "eh,
flaky, rerun it." Claude doesn't have that judgement by default — a nondeterministic failure either
gets misdiagnosed as a real regression (wasted cycles chasing a ghost) or, worse, trains a pattern
of learning to ignore red tests. That's the concrete reason real-Cognito/real-email tests are kept
in the smallest, least-frequently-run tier (see [Reading Cognito's emails in
tests](#reading-cognitos-emails-in-tests) above) rather than spread through the suite: the
webapp's own mocked-auth layer already covers "correct code succeeds" scenarios deterministically
(the mock invents and accepts its own fake code, no real Cognito involved at all), the Admin-API
bypass covers anything else that just needs a working account, and real email delivery is only
exercised by the few full-stack tests whose specific job is proving that path works.

**Ephemeral infrastructure needs an explicit authority boundary, not just a capability.** Claude
having latitude to run Terraform and wipe sandbox data was already established; standing up a
whole named environment is a step further — real AWS resources that need reliable teardown, where
an interrupted session could leave one orphaned. The policy above (create at the start of
dev/deploy sessions, ask before tearing down at commit time, never touch `test`) exists
specifically so that latitude doesn't turn into unbounded AWS resource sprawl across sessions.

## Known gaps / future work

- **Webapp contract drift**: nothing today catches "the webapp's hand-maintained GraphQL types
  (`graphql/types.ts`) have drifted from the API's actual schema" cheaply — only a live e2e
  failure would surface it, too late to be useful. The fix is GraphQL codegen straight from
  `mootmaker-api/api/mootmaker.graphql`, but that's deferred until CI/CD pipelines exist, since
  codegen is most useful wired into a pipeline step rather than run ad hoc. Tracked in
  [mootmaker's to-do list](README.md#to-do).
- Everything under "planned" in each per-repo `testing-strategy.md` — this document only records
  the strategy; check each repo's own file for current build status.
- ~~SCP update needed for real-email reading~~ — done 2026-08-15 (see [Reading Cognito's emails in
  tests](#reading-cognitos-emails-in-tests) above). ~~mootmaker-e2e's full-stack test suite itself~~
  — done 2026-08-19, moved into `mootmaker-webapp/e2e/` (see that repo's testing-strategy.md).
- **Only two of ~99 use cases in `use-cases.md` are automated** (in
  `mootmaker-webapp/acceptance/`) — a deliberate thin first slice, not full coverage. See that
  suite's own README for the pattern to follow when adding more.
- `mootmaker-test-infra`'s `create-ephemeral-env.sh` still unconditionally deploys mootmaker-api
  *and* mootmaker-webapp together — fine today, but `mootmaker-android`'s tests will only need the
  API half. Not solved yet; see that repo's own testing-strategy.md.
