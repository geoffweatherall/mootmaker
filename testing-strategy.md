# Testing strategy

This document records the overall testing strategy across this project's repositories —
[mootmaker-api](https://github.com/geoffweatherall/mootmaker-api),
[mootmaker-webapp](https://github.com/geoffweatherall/mootmaker-webapp), and
[mootmaker-e2e](https://github.com/geoffweatherall/mootmaker-e2e) — and, specifically, how
developing this project largely by "vibe coding" with Claude (see this README's
["I should vibe more"](README.md#i-should-vibe-more) and ["Impacts on the test
pyramid"](README.md#impacts-on-the-test-pyramid)) shapes that strategy differently than it would
for a conventionally hand-reviewed codebase.

Each repository also has its own `testing-strategy.md` with the detail specific to it:

- [mootmaker-api/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-api/blob/main/testing-strategy.md)
- [mootmaker-webapp/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/testing-strategy.md)
- [mootmaker-e2e/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-e2e/blob/main/testing-strategy.md)

This document is the map between them: the overall layering, the decisions that cut across repos
(ephemeral environments, how verification-code emails get read in tests), and the "vibe coding"
reasoning behind it.

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
| Integration tests against a mocked API | mootmaker-webapp (Playwright + MSW) | none (mocked GraphQL, mocked auth) | seconds | fully deterministic | page-level wiring: right query fires, validation errors render, success navigates, `RequireAuth` gates correctly |
| Full-stack e2e | mootmaker-e2e (new) | real deployed AWS, ephemeral or special-purpose | minutes | least deterministic, especially the real-email cases | real Cognito email delivery, DNS/certs, CloudFront/S3 serving, cross-service integration nothing else can see |

**Built 2026-08-15**: the webapp's Vitest and MSW-mocked-integration layers exist now (30 unit
tests, 27 integration tests, both independently verified green) — see
[mootmaker-webapp/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/testing-strategy.md).
The old live-API Playwright suite was **replaced in place**, not kept alongside the new one (an
explicit choice): `webapp/tests/*.spec.ts` now needs no live AWS environment, deployed API, or real
Cognito user at all. mootmaker-e2e (full-stack, deployed-webapp-against-deployed-API) remains not
yet built — see that repo's own `testing-strategy.md`.

## Reading Cognito's emails in tests

Sign-up and forgot-password both require entering a code Cognito emails to the user — automating
either flow end-to-end means reading that email somehow, or avoiding needing to.

**Reading the real email (SES → SNS → SQS)** is the only mechanism for tests where a genuinely
real code matters. A subdomain's MX record points at Amazon SES; a receipt rule publishes the
message to an SNS topic (SES receipt rules can't deliver to SQS directly), which an SQS queue is
subscribed to; the test long-polls the queue and parses the code out of the real email body. Slower
and less deterministic than a bypass would have been (real mail delivery, a real network hop), but
it's the only thing that actually proves Cognito's email sending is configured and working.
Reserved for a small number of full-stack e2e tests in mootmaker-e2e whose specific purpose is
proving that path works — never needed anywhere the code itself is the only thing under test (see
below).

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
live in [mootmaker-e2e](https://github.com/geoffweatherall/mootmaker-e2e) (test-only
infrastructure). Both are deployed once and left running, not tied to any single ephemeral
environment's lifecycle.

**Blocked as of 2026-08-15**: this project's account-wide Service Control Policy
([mootmaker-bootstrap-aws-accounts](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts)'s
`scp-guardrails.yaml`) allows only an explicit service list, and `ses`/`sns`/`sqs` aren't on it —
Cognito currently sends email via its own default sending rather than SES, so none of the three
have ever been needed before. The Terraform is written but deliberately left unapplied until that
allow-list is updated (Claude doesn't modify SCPs — that change needs the organization management
account, `339140804537`, which Claude only ever has credentials to the workload account,
`431071856068`, for anyway).

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
  so they're identifiable and machine-cleanable:
  - `claude-<YYMMDD>-<rand4>` — Claude's own interactive dev-session environments (e.g.
    `claude-260815-x7q2`).
  - `e2e-<YYMMDD>-<rand4>` — automated e2e test-run environments (e.g. `e2e-260815-x7q2`).

  Separate prefixes so a cleanup pass (or a human glancing at the AWS console) can tell a stale dev
  sandbox apart from an in-progress e2e run without needing extra metadata. The timestamp is
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
- **Scripts** (built and verified end-to-end 2026-08-15): three separate bash scripts, living in
  [mootmaker-e2e](https://github.com/geoffweatherall/mootmaker-e2e) alongside the other
  cross-cutting test infrastructure — see
  [mootmaker-e2e/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-e2e/blob/main/testing-strategy.md#ephemeral-environment-scripts)
  for the full design and reasoning. Naming ended up `claude-<YYMMDD>-<rand4>` (day-only, no
  time-of-day) rather than the originally-designed `<YYMMDD>-<HHmm>-<rand4>` — real deployment
  testing found the longer form 1 character over a Lambda function-name limit. In short:
  - `create-ephemeral-env.sh` — generates a name and calls each project's own `deploy.sh` in
    sequence.
  - `teardown-ephemeral-env.sh <name>` — calls each project's own `undeploy.sh` for one specific,
    already-known environment (what the commit-time cleanup prompt above uses).
  - `cleanup-stale-envs.sh` — the batch sweep, for anything left behind by an interrupted session.
    Discovers every `claude-*`/`e2e-*` environment via the shared Terraform state bucket
    ([mootmaker-bootstrap-terraform](https://github.com/geoffweatherall/mootmaker-bootstrap-terraform))
    — every project's state key is `<environment>/<project-name>/terraform.tfstate`, so listing
    that bucket's keys and grouping by the first path segment gives a reliable, centralised list of
    every environment across every project, with no separate registry needed — then lists
    everything it finds and asks for confirmation before tearing down each one, matching
    `undeploy.sh`'s own always-interactive, no-`-auto-approve` safety pattern rather than an age
    threshold or a pick-list menu.

  All three are thin orchestrators over the existing per-project `deploy.sh`/`undeploy.sh` — none
  of the actual deploy mechanics get duplicated.

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
- **SCP update needed for real-email reading** (see [Reading Cognito's emails in
  tests](#reading-cognitos-emails-in-tests) above): `ses`, `sns`, and `sqs` all need adding to
  `pAllowedServiceActions` in **both**
  `mootmaker-bootstrap-aws-accounts/management-account/scp-guardrails.yaml` **and**
  `identity-center.yaml` (they're required to stay in sync — see the description on that parameter
  in either file). Deployed via CloudFormation in the organization management account
  (`339140804537`), logged in as the account root user — see that repo's
  `management-account/README.md#deploying-scp-guardrailsyaml`. The Terraform is written and
  validated, ready to apply once this lands.
