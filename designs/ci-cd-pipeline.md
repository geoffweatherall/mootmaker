# CI/CD pipeline

## Summary

Mootmaker has no CI and deploys to production from a developer's own machine, by hand. This design
proposes GitHub Actions for two things: automated checks on every pull request (unchanged from the
first draft), and a **specifically-initiated release pipeline** — triggered by a human or an AI via
`gh workflow run`, never by merging to `main` — that versions, builds, and tests `mootmaker-api`,
`mootmaker-webapp` and `mootmaker-demo-data` together, proves them in a standing `test` environment,
and only then promotes the same artifacts to `production`.

**Status:** Drafting — 2026-09-03. Supersedes this doc's own 2026-08-29 draft on the trigger model
and the standing-`test` question; see "What changed since the last draft" below.

---

## What changed since the last draft

The 2026-08-29 draft (still readable in git history) had merge-to-`main` deploy straight to
`production`, no version numbers, and explicitly declined to reintroduce `test`. Discussion on
2026-09-03 reversed all three:

1. **Release is explicitly initiated, not merge-triggered.** A merge to `main` now does nothing
   beyond what PR checks already did before the merge. Releasing is a deliberate act — `gh workflow
   run release.yml -f bump=patch` — that a human or an AI performs when `main` across all three
   repos is believed ready to ship, and it releases everything currently on each repo's `main` at
   once.
2. **`test` is reintroduced, deliberately, as a standing environment** — not because the 2026-08-29
   reasoning for retiring it was wrong (it wasn't: a continuously-running environment that
   accumulates undetected state drift is a real cost and a real risk), but because it solves a
   *different* problem than the one this pipeline needs solved. See Decision 6.
3. **Releases are versioned**, with one semver number spanning all three deployable components.
4. **The orchestrator moved out of the hub, into a new dedicated repo, `mootmaker-release`.** This
   same 2026-09-03 discussion also surfaced that `mootmaker-test-infra` combined two unrelated
   things (ephemeral-environment scripts, a persistent email pipeline) under one name — split into
   `mootmaker-ephemeral-envs` and `mootmaker-email-testing` the same day, independently of this
   design but referenced throughout it. See Decision 1 for the repo-topology reasoning.

The rest of the 2026-08-29 draft's reasoning — OIDC over stored credentials, PR checks never
touching AWS, redeploy-not-destroy for rollback, the scheduled ephemeral sweep — stands unchanged
and isn't repeated in full below except where the new release flow changes it.

---

## Scope / non-goals

### In scope

- PR checks (build, unit tests, and — where meaningful — the mocked/integration layer) for every
  repository that has them, run on every pull request.
- **PR checks become a required gate, not just advisory** (resolves NB-3), for the three deployable
  components specifically — `mootmaker-api`, `mootmaker-webapp`, `mootmaker-demo-data`. See Decision
  12 for exactly what each runs.
- A **release pipeline**, triggered by `workflow_dispatch`, covering all three deployable
  components: `mootmaker-api`, `mootmaker-webapp`, and `mootmaker-demo-data`. Demo-data is in scope
  from the start this time — its 2026-09-02 restructuring gave it the same `deploy.sh`/`verify.sh`
  shape as the other two, so treating it as the odd one out no longer reflects the codebase.
- Semantic versioning, auto-incrementing patch by default, with a `bump` input to jump major or
  minor deliberately.
- A **standing `test` environment**, brought back into the release flow as a promotion gate between
  build and `production`.
- A new **smoke-test** layer, distinct from the existing acceptance suites, run against `test` and
  again (in a lighter form) against `production`.
- AWS authentication via OIDC — unchanged principle, now covering three kinds of deploy target
  (per-release ephemeral build environments, `test`, `production`) instead of one.
- A rollback story for a bad deploy, extended to cover an automatic attempt on a failed production
  smoke test.
- A durable, greppable release record — both for troubleshooting and because it's now the source of
  truth for "what version is `test`/`production` running."
- **Consolidated CloudWatch logging** for the release process — Terraform output, smoke-test
  output, each component's Stage 1 build-and-unit-test output, the relevant Lambda execution logs,
  and AppSync's own request/resolver logs, queryable together and durable beyond GitHub Actions'
  90-day retention. PR checks (Decision 12) deliberately don't ship here — no release version to
  tag them with. See Decision 11.
- The scheduled ephemeral-environment sweep, unchanged from the first draft, and now explicitly
  scoped to never touch `test` (see Technical considerations — the teardown script already refuses
  to).

### Non-goals

- **Deploying `mootmaker-domain` or the bootstrap repos through this pipeline.** `mootmaker-domain`
  has no code yet; the bootstrap repos deploy rarely enough, and touch account-level IAM/SSO
  guardrails sensitively enough, that automating them is low value and higher risk than benefit.
- **Deploying `mootmaker-android`** — no code exists yet.
- **Building the GraphQL schema-sharing mechanism itself** — that's `graphql-schema-sharing.md`'s
  job. Its schema-publish step (already live in `mootmaker-api/.github/workflows/publish-schema.yml`
  as of the 2026-09-02 pull) is orthogonal to this design and isn't touched here.
- **CI/CD for the management account.** Stays a manual, `[Geoff]`-only process via the CloudFormation
  console, exactly as before. This pipeline's OIDC role lives in the **workload** account
  (`431071856068`) only.
- **Ephemeral-environment-per-PR.** Still deferred, for the same reason as before: no evidence yet
  that PR-time acceptance testing would catch something the release pipeline's own build-time
  acceptance run doesn't.
- **Adding a Java linter/formatter to `mootmaker-api`/`mootmaker-demo-data`.** Neither has one today
  (verified — no Checkstyle/PMD/SpotBugs/Spotless in either `pom.xml`). Spotless is the intended
  choice when this does happen (a formatter, not a rules engine — fits "the codebase is the style
  guide" better than Checkstyle would, especially for a mostly-AI-written codebase), named as a
  fast follow, not built as part of this design. Consequence, accepted knowingly: the two Java
  components' required PR check (Decision 12) covers build + unit tests only, not lint — genuinely
  asymmetric with `mootmaker-webapp`'s, not an oversight.

---

## Trade-offs and decisions

### 1. Release is explicitly initiated via `workflow_dispatch`

**Decision:** the release pipeline lives in a **new, dedicated repo, `mootmaker-release`**, as
`release.yml`, triggered only by `on: workflow_dispatch`, with one input: `bump` (`patch` | `minor`
| `major`, default `patch`). Nothing runs it automatically. A merge to `main` in any component repo
changes nothing until someone — Geoff, or Claude via `gh workflow run release.yml -f bump=patch` —
deliberately starts a release.

**Reasoning:** GitHub Actions supports this natively — `workflow_dispatch` is a first-class trigger
type, firable from the Actions UI, `gh workflow run`, or the REST API, and it accepts typed inputs
(a `choice` input is exactly right for `bump`). This is a different shape than CodePipeline's
manual-approval *stage*, which pauses a pipeline already in flight — here the whole pipeline simply
doesn't exist until dispatched, which maps cleanly onto "a release is a deliberate act," not "code
merged is code shipped."

**Why a dedicated repo, not the hub or one of the components (revised 2026-09-03):** this design
originally proposed the hub repo (`mootmaker`). Reconsidered on the grounds that `mootmaker`'s own
`AGENTS.md` states it "holds no deployed code" — a `release.yml` that actually pulls the trigger on
`test`/`production` is deployed-code-adjacent in a way the hub's docs/process content isn't, and
blending the two blurs a boundary the hub otherwise holds deliberately. One of the three component
repos (`mootmaker-api`/`mootmaker-webapp`/`mootmaker-demo-data`) was the other option, and is worse
for a different reason: it would mean arbitrarily picking one of the three to coordinate the other
two. `mootmaker-release` avoids both problems at the cost of one more repo — accepted deliberately, the
same way `docs/process/branching-and-prs.md`'s "Cross-repo changes" section already names the
multi-repo layout's cost as "accepted deliberately when the topology was chosen," not a hidden one.
Each component repo still owns its own
build-and-deploy logic as a *reusable* workflow (`on: workflow_call`) that `mootmaker-release`'s
`release.yml` calls — see Decision 3 — so this repo coordinates, it doesn't duplicate.

### 2. Free tier — the constraint is AWS spend, not GitHub Actions minutes

**Decision:** state this plainly in the design rather than let "stay in free tier" imply GitHub
billing is the reason releases aren't automatic.

**Reasoning:** every mootmaker repo is public, so GitHub Actions minutes are already free and
*unlimited* regardless of trigger frequency — running the full release pipeline on every merge to
`main` would cost nothing in GitHub billing terms. The actual cost avoided by requiring an explicit
trigger is **AWS spend and noise**: every release build-and-test stage stands up a full ephemeral
stack (Lambdas, DynamoDB, Cognito, AppSync, CloudFront) per component, and the standing `test`
environment itself now costs money continuously by design (Decision 6). Gating on an explicit
release, rather than every merge, keeps that AWS spend proportional to actual releases instead of
every commit.

### 3. Cross-repo orchestration: `workflow_call` for logic, a narrowly-scoped PAT only for tagging

**Decision:** `release.yml` in `mootmaker-release` calls each component repo's own reusable workflow
directly — `uses: geoffweatherall/mootmaker-api/.github/workflows/release-build.yml@<tag>` — rather
than triggering separate workflow runs via `repository_dispatch`. This needs no cross-repo
credential at all: a reusable workflow called this way runs with the caller's own token and
permissions, and public-repo `uses:` references need no PAT. The **one** place a cross-repo write
is unavoidable is pushing the version tag itself into each component repo's `main` (and
`mootmaker-release`'s own, per Decision 4) — that needs a fine-grained PAT (`contents: write`,
scoped to exactly `mootmaker-release`, `mootmaker-api`, `mootmaker-webapp`, `mootmaker-demo-data`,
nothing else — the hub, `mootmaker`, needs no write access here at all now), stored as a
`release.yml`-only secret.

**Reasoning:** this is narrower than the first draft's implicit assumption (a PAT or GitHub App with
broad `actions:write` to dispatch remote workflows). `workflow_call` avoids needing that entirely —
the only genuine cross-repo *write* left is the tag push, so that's the only place a non-OIDC,
longer-lived credential is justified. Worth naming explicitly: this is a real, if narrow, exception
to "no long-lived credentials anywhere" (`docs/process/principles.md`), and should be recorded as
one rather than quietly matching the letter of the principle while missing its spirit. A GitHub App
installation token would be the more "correct" version of this (short-lived, scoped by permission
rather than by PAT-holder's own access) but is meaningfully more setup for a project this size — a
fine-grained PAT, reviewed and rotated periodically, is the pragmatic choice.

**Confirmed 2026-09-03 (OQ-3):** PAT, not a GitHub App. Kept the review deliberately, not because
the trade-off resolved differently, but because the exception is worth restating plainly: this PAT
is checked-in-to-nothing (a repo secret), scoped narrowly, and its one job is a tag push — a GitHub
App's extra correctness doesn't earn its setup cost at this project's scale.

### 4. Versioning: one semver number, computed and recorded via GitHub Releases

**Decision:** a single version (`vMAJOR.MINOR.PATCH`) spans all three components for one release.
The **source of truth for "what's the current version"** is `mootmaker-release`'s own GitHub
Releases list (`gh release list --limit 1`) — not a version file, not inspecting tags in one of the
component repos. `release.yml` reads it, computes the next version from `bump`, and — only once
Stage 1 (build + acceptance, all three components) is fully green — tags that exact commit in each
of `mootmaker-api`, `mootmaker-webapp`, and `mootmaker-demo-data` with it, and tags its own current
`main` HEAD too (bookkeeping: `mootmaker-release` has no deployable artifact of its own either, but
it's where the GitHub Release itself is published — see Decision 5 — so keeping its own tag and
that Release on the same repo is simpler than splitting them across two).

**Reasoning:** tagging only after the build-and-test stage passes means a tag is always a marker of
a commit that was actually proven, never a commit that failed. If a release attempt fails at any
later stage, the version number it claimed is simply not reused — the next attempt computes a fresh
one. This is normal semver practice (npm, for instance, does the same on a failed publish) and
avoids ever needing to "unwind" a tag. Using `mootmaker`'s GitHub Releases (not a component repo's
tags) as the one source of truth avoids the ambiguity of "which of the three repos do we ask" — and
a GitHub Release is also the natural home for the durable release record (Decision 5), so this reuses
one mechanism for two needs rather than building a second one.

**Consequence, accepted knowingly:** every release bumps the version in all three repos, even one
where only `mootmaker-demo-data` actually changed. Matches "everything in `main` will be released"
as stated — this pipeline does not support releasing one component independently of the others.

### 5. The release record is a GitHub Release, not just Actions logs

**Decision:** the final step of a release — success or failure — publishes a GitHub Release (or, for
a failed attempt that never reached `production`, a clearly-marked draft/failed Release, or an issue
if no version was ever tagged) on `mootmaker-release`, containing: the version, the `bump` used, each
component's commit SHA and tag, links to every stage's Actions run, and a pass/fail per stage
(build+acceptance / deploy-to-test / smoke-test-test / deploy-to-production /
smoke-test-production).

**Reasoning:** Actions run logs are the obvious first source but default to a 90-day retention
window and aren't searchable outside the Actions UI/API. A GitHub Release is permanent, browsable
without any special tooling, and — because it's plain text — grep-able by an AI session
troubleshooting a failure long after the run itself has aged out of retention. It also directly
answers "what version is running where" without needing to query Actions history at all, which is
exactly what Decision 4 needs.

**Mechanism, spelled out (found missing on review 2026-09-03):** the three-way "success / marked-
failed / issue" branch above only actually happens if something *guarantees* it runs even when an
earlier stage fails outright — a normal GitHub Actions job just stops on failure, it doesn't fall
through to a later step by default. So `release.yml` needs a dedicated final job — call it
`record-outcome` — with `if: always()`, run after every other job regardless of their outcome. The
tag-push step (Decision 4) sets a job output (e.g. `tag_pushed: true`, plus the version string) the
moment the tags land; `record-outcome` reads that output to decide which of the three cases applies
— **not** by re-deriving it from whether later jobs succeeded, since a run can fail *after* tagging
in ways that have nothing to do with whether the tag itself is real. Without this, the risk named
below is exactly what happens: tags exist naming a version, and nothing on GitHub says so.

### 6. `test` is reintroduced as a standing environment — for a different reason than before

**Decision:** `test` returns as the second long-lived environment, alongside `production`. Every
release deploys to it before `production`, and — unlike the per-component build-stage ephemeral
environments (Decision 7) — it is never torn down between releases.

**Reasoning, and why this doesn't just undo the 2026-08-29 decision:** that decision retired `test`
because a standing environment cost money continuously without earning its keep for a solo
developer with a green acceptance suite, and because it had already caused a real bug (stale-state
contamination producing false acceptance failures). Both of those are still true reasons to be
wary of a standing environment. But they argue against a standing environment used *as ephemeral
environments already are* — a target for arbitrary interactive testing that accumulates state
nobody's tracking. They don't address the specific gap this pipeline has: **an ephemeral
environment is always created fresh, so `terraform apply` against it is always a *create*. It never
exercises Terraform's *update* path** — modifying an existing resource, a state migration, a
provider quirk that only shows up when a resource already exists. `production` is the only place
that path has ever been exercised, which means the first time any release's Terraform changes hit
the update path for real is in production itself. A standing `test`, updated release after release
exactly like `production` will be, closes that gap: it's structurally the same *kind* of apply
`production` gets, which no amount of "more ephemeral tests" can substitute for.

**What keeps this from becoming the same trap:** `test` isn't a place for ad hoc interactive
poking between releases (ephemeral environments already serve that need) — its state changes only
through the release pipeline, the same as `production`'s does. Demo-data seeds it the same way it
seeds `production` (see Technical considerations), so its data shape doesn't silently drift from
what smoke tests expect. And a broken `test` — say, a Terraform apply that half-succeeded — is a
diagnostic asset here, not a bug to route around: see Decision 6a below.

**A safety rail this already has, for free:** `mootmaker-ephemeral-envs/teardown-ephemeral-env.sh`
already refuses to run against anything that isn't shaped like `<kind>-<YYMMDD>-<rand4>`, and its
own error message already says so in terms of `test`: *"this script only ever touches ephemeral
environments, never 'test' or 'production'"* — written before this reversal, evidently anticipating
it. No change needed there; `test` is already a protected name in the tooling.

### 6a. A failed `test`-stage smoke test halts the release and leaves `test` exactly as it is

**Decision:** if the smoke-test-against-`test` stage fails, the release stops there. It does not
proceed to `production`, and `test` is **not** rolled back, reset, or torn down automatically.

**Reasoning:** this is the entire point of Decision 6 — catching a bad Terraform update (or any
other test-stage failure) here, in a persistent environment a human or AI can actually inspect,
instead of in `production`. Automatically reverting `test` would destroy the exact evidence the
environment exists to preserve.

**Consequence, accepted knowingly:** the *next* release attempt's deploy-to-`test` stage may itself
fail again, loudly, until whatever's wrong is fixed by hand (or by an AI session, but not
automatically by the pipeline). This is intentional — it mirrors what would otherwise have happened
in `production`, just somewhere recoverable. Named as a risk below, not treated as a defect to
design away.

### 7. Per-component build-and-test still uses fresh ephemeral environments — always torn down

**Decision:** the build-and-acceptance-test stage (Stage 1, before any tag exists) still runs each
component's own acceptance suite against a **freshly created ephemeral environment** — via the
existing `mootmaker-ephemeral-envs/create-ephemeral-env.sh` / `undeploy.sh`, exactly as it works today —
and that environment is torn down immediately after, regardless of whether the tests passed. Logs
and test reports are captured as workflow artifacts before teardown.

**Reasoning:** this stage is answering a different question than `test` is ("does this component
work at all, in isolation, right now") and doesn't need persistence to answer it — a fresh
create-and-destroy cycle is exactly right here, and reuses infrastructure that already exists and
already works. Always tearing down (pass or fail) keeps this stage's AWS cost bounded to its own
runtime, consistent with the scale-to-zero principle that `test` is a deliberate, named exception
to.

**`mootmaker-webapp`'s `acceptance/` suite needed a real fix before running here unattended (found
on review 2026-09-03, fixed same day —
[mootmaker-webapp#19](https://github.com/geoffweatherall/mootmaker-webapp/pull/20)):** its config
was written assuming purely local, manual invocation — `trace: 'on'`/`screenshot: 'on'`
unconditionally, plus an `html` reporter bundling every attachment into itself, together capable of
producing ~800MB for one run. Fine on a developer's own machine; not something to run unattended,
once per release, in GitHub Actions. Now branches on `process.env.CI` (set automatically, no
workflow wiring needed): local behaviour is untouched, CI gets one retry (smooths transient
real-AWS flakiness with nobody watching to re-run manually), no `html` reporter, and
trace/screenshot only on failure. The `json` reporter stays in both — it references trace/screenshot
files by path rather than embedding them, so it's small either way, which is what makes it the
right thing to eventually ship to CloudWatch (Decision 11) without needing this fix repeated there.

### 8. Build once, promote the same artifact to `test` then `production`

**Decision:** each component's build-and-test stage uploads its build output (`mootmaker-api` and
`mootmaker-demo-data`'s Lambda jars; `mootmaker-webapp`'s `dist/`) as a workflow artifact
(`actions/upload-artifact`). The deploy-to-`test` and deploy-to-`production` stages download that
same artifact (`actions/download-artifact`) and deploy it unmodified — they do not rebuild from
source.

**Reasoning:** this is what makes "the thing that passed acceptance in the build stage is the exact
thing that reaches `test`, and the exact thing that reaches `production`" true, rather than merely
implied. Rebuilding per environment (what the first draft's Technical considerations flagged as a
known blocker) would mean a `test` pass proves nothing about the artifact `production` actually
gets — a subtly different build could pass or fail independently at each stage. Artifacts persist
for the life of the workflow run, well within a single release's timeframe, so no separate storage
(S3, an artifact registry) is needed for this.

**Blocking dependency:** `mootmaker-webapp#3` (API/Cognito config baked into the bundle at build
time) has to be fixed first — as written today, a webapp build is tied to one environment's config,
which defeats build-once-promote for exactly the one component most likely to need it. The issue's
own suggested fix (a small `config.json` fetched at page load, written by `deploy.sh` from the
target environment's Terraform outputs) is the right shape and is now a prerequisite for this
design, not an unrelated nice-to-have. Sequenced in Rollout & migration.

### 9. Smoke tests are a new, deliberately small test layer

**Decision:** two new smoke-test suites, distinct from the existing unit/mocked-integration/
acceptance layers:

- **`test`-stage smoke test:** sign up a new account (exercises SES via the existing test-infra
  email-reading support), sign in, create a meeting, view existing (demo) data, reset a password,
  delete the account just created. Roughly what a human tester would actually click through in five
  minutes — explicitly *not* a re-run of the full acceptance suite.
- **`production`-stage smoke test:** narrower still — sign in as the published demo user, look
  around, create one more meeting for the demo user, spot-check that data looks sane. No new-account
  signup, no deletion, no password reset — production is a demo, and the demo user is the thing that
  matters there.

**Reasoning:** matches what was asked for directly — a human-tester-shaped check, not acceptance
testing twice. Reusing the existing SES-based test-infra email support for the `test`-stage signup
flow avoids building new email-verification plumbing.

**Output config, deliberately the low end (added 2026-09-03):** `reporter: 'json'`,
`use: { trace: 'off', video: 'off', screenshot: 'off' }`. Playwright's reporter output (test/step
names, pass/fail, timing, error text on failure) and its trace/video/screenshot artifacts are
separate config axes — the former is what makes Decision 11's CloudWatch shipping human- and
AI-readable at a few KB per run; the latter is what can balloon into hundreds of MB per run (a full
DOM+network+screenshot recording per test, not log text), and is deliberately off entirely here,
screenshots included. That heavier tracing already exists, deliberately, in the acceptance suite —
smoke tests are a five-minute human-tester-shaped check, not another place to reproduce it.

**Where this code lives (resolved 2026-09-03, OQ-1):** `mootmaker-release`, not `mootmaker-webapp` or
`mootmaker-ephemeral-envs`. Neither of those was quite right: `mootmaker-webapp` would have owned
tests that assert on `mootmaker-api` and `mootmaker-demo-data` behaviour too, and
`mootmaker-ephemeral-envs`'s whole identity post-split (Decision 1) is ephemeral-environment
lifecycle specifically, not smoke testing. `mootmaker-release` is where the release pipeline itself
already lives and is *already* the cross-component home — the smoke tests are a natural part of
what it orchestrates, not a new category of thing bolted on. Consequence: `mootmaker-release` needs
its own Playwright + Node setup (it currently has none — just `README.md`/`AGENTS.md`), separate
from `mootmaker-webapp`'s.

### 10. Rollback: redeploy the previous version; attempt it automatically on a failed production smoke test

**Decision:** unchanged from the first draft in mechanism — rolling back means re-running the deploy
step against the previous release's tag, not `terraform destroy` or a bespoke rollback path. New:
if the **production** smoke test fails, the pipeline **automatically** redeploys the previous
version's artifacts to `production` and re-runs the production smoke test against that, rather than
leaving a known-bad `production` up while waiting for a human.

**Reasoning:** `test` passing and `production` still failing implies something environment-specific
to `production` (data shape, a config difference, a race) rather than a code defect `test` should
have caught — which is exactly the scenario an automatic revert is safe for, since the previous
version is known-good by construction (it was itself a release that reached `production`).

**Confirmed 2026-09-03 (OQ-2):** automatic is the right default. The masking risk named as the
counterargument (an automatic redeploy hiding a data-shape problem that redeploying old code
doesn't actually fix) is accepted knowingly — the alternative, leaving `production` visibly broken
while waiting on a human, is worse for a public demo, and the GitHub Release (Decision 5) still
records that a rollback happened and why, so the masking is never silent.

### 11. Consolidated CloudWatch logging: durable full detail behind Decision 5's summary

**Decision (added 2026-09-03):** Decision 5's GitHub Release solves "what happened, roughly" but
only *links* to Actions logs, which age out at ~90 days — the raw detail (Terraform's own output,
the smoke test's assertions) has no durable home. `mootmaker-release` gains one new CloudWatch Log
Group (e.g. `/mootmaker/release-pipeline`) — its first real piece of Terraform, deployed once,
persistent, no environment argument, the same shape `mootmaker-domain` already uses for shared
infra. Every stage that produces meaningful output ships it there in **structured** form, not raw
console text: `terraform apply -json` for every Terraform stage, Playwright's JSON reporter for the
smoke tests, and each component's Stage 1 build-and-unit-test output (Maven's Surefire reports for
`mootmaker-api`/`mootmaker-demo-data`, Vitest's own structured output for `mootmaker-webapp`) —
this last one **only for the release pipeline's own `release-build.yml` run, never for PR checks**
(Decision 12): a PR isn't tied to a release version, has no natural field to tag it with, and
GitHub's own Checks tab is already a fine home for it — shipping it here would just be noise with
nothing to correlate it against. Consistent fields across everything shipped (`version`, `stage`,
`component`, `outcome`) are what make this queryable rather than just archived.

**Mechanism, since GitHub Actions has no native path into CloudWatch on its own:** a step at the
end of each job — `if: always()`, so a failure ships too, not just a pass — uses the same
OIDC-derived credentials already present for deploying, and pushes the captured, structured output
via `aws logs create-log-stream` (if needed) + `aws logs put-log-events`. A plain script, matching
this project's own bash-over-third-party-actions convention, not a marketplace action.

**Only reporter/output text ever ships here — never trace, video, or screenshot artifacts (found on
review 2026-09-03, see Decision 9's own output config).** Not just a cost preference: those are
binary and can run to hundreds of MB per run (a full DOM/network/screenshot recording, not log
text), and `PutLogEvents` caps a single log event at 256KB regardless — the wrong tool for that kind
of artifact even before cost enters into it. If a failed smoke test ever needs a screenshot, that's
a GitHub Actions artifact upload, a separate mechanism with its own lifecycle, not part of this log
group at all.

A `AWS::Logs::QueryDefinition` (`aws_cloudwatch_query_definition` in Terraform) is the saved,
reusable query over this — unaffected in shape by CloudWatch's December 2024 addition of two more
query languages (OpenSearch SQL and PPL, alongside the original Logs Insights QL) beyond the
console change itself: `QueryDefinition` simply gained a `QueryLanguage` property
(`CWLI`/`SQL`/`PPL`, defaulting to the original). Classic Logs Insights QL is the right choice here
— this doesn't need SQL's or PPL's extra power, just `fields`/`filter`/`stats` over structured
fields. `QueryDefinition` also supports named `Parameters` (placeholder variables filled in at run
time), so one saved query with a `version` parameter covers every release, rather than one saved
query per release.

**Including the Lambda logs from the smoke test's own API calls — yes, and how:** every Lambda
already logs to its own `/aws/lambda/<function-name>` group automatically; CloudWatch Logs Insights
queries can span multiple log groups in one query. So the same saved query can pull together the
pipeline's own shipped logs *and* `mootmaker-api`/`mootmaker-demo-data`'s Lambda execution logs for
the same time window — a genuine "what the smoke test asserted, and what the Lambda actually did
while handling it" view, not two separate places to look.

**How `mootmaker-release`'s Terraform knows which Lambda log groups to include — tag-based
discovery, not a naming convention and not a cross-repo state export.** A naming convention
(`/aws/lambda/<environment>-mootmaker-<function>`) would work today but silently goes stale the
moment a Lambda is renamed or added, with no build-time signal. Reading `mootmaker-api`'s Terraform
state directly (`terraform_remote_state`) was considered and rejected — it's exactly the "hard
remote-state dependency" this project already avoids elsewhere (`mootmaker-api/cognito.tf` finds
`mootmaker-domain`'s SES identity via a `data` source specifically instead of one; same reasoning
for the Route53 zone). Instead: `mootmaker-api` and `mootmaker-demo-data` gain **explicit**
`aws_cloudwatch_log_group` resources for their Lambdas (neither has one today — verified, both rely
entirely on the auto-created default, with no retention set either way, which this also fixes),
tagged consistently (e.g. `mootmaker:release-logs = "true"`). `mootmaker-release`'s Terraform
discovers them dynamically via `data "aws_resourcegroupstaggingapi_resources"` filtered on that
tag, rather than listing names anywhere — self-updating as Lambdas are added, removed, or renamed,
and staying consistent with this project's existing loose-coupling preference. Needs one small IAM
addition to the OIDC deploy role: `tag:GetResources`, alongside the `logs:*` write access the
pipeline's own shipped logs need — same incremental-growth pattern as every other addition to that
role's policy so far.

**AppSync's own request/resolver logs are included too — but this needs two new pieces, not just
tagging (found on review 2026-09-03).** `mootmaker-api`'s `aws_appsync_graphql_api` has no
`log_config` block today — AppSync CloudWatch logging isn't enabled at all yet, verified against
the actual resource, not assumed. Two additions:

1. **Turn logging on**: a `log_config` block (`field_log_level = "ALL"`, a new
   `cloudwatch_logs_role_arn` for the IAM role AppSync assumes to write). This is the GraphQL-level
   complement to the Lambda's own execution logs — which operation was called, auth outcome,
   resolver timing/mapping errors — not a duplicate of them.
2. **Adopt its log group for tagging**, the same way as the Lambda ones, with one real wrinkle:
   AppSync always writes to a fixed-convention name, `/aws/appsync/apis/<api-id>` — not redirectable
   — and the API ID is only known *after* `aws_appsync_graphql_api.this` is created, unlike a
   Lambda's function name (which is set by the config, so knowable before applying). Still fine
   within one apply — `resource "aws_cloudwatch_log_group" "appsync" { name =
   "/aws/appsync/apis/${aws_appsync_graphql_api.this.id}" ... }`, Terraform's dependency graph
   creates the API first and the log group second, same tag applied.

**Near-circular dependency, resolved with an accepted `Resource: "*"`-style wildcard:** if the
logging IAM role's policy tried to scope `logs:PutLogEvents` to the *exact* log group ARN, that
would depend on the API's ID, while the API resource's own `log_config` depends on that IAM role's
ARN — a genuine cycle. Broken by scoping that one policy statement to a static wildcard pattern
instead (`arn:aws:logs:*:*:log-group:/aws/appsync/apis/*`), known at plan time with no dependency on
the API resource at all. Confirmed acceptable rather than assumed — this is a narrower, one-purpose
exception (breaking a real dependency cycle for one logging role), not a broadening of the OIDC
deploy role itself.

**Relationship to Decision 5, kept deliberately distinct:** the GitHub Release stays the index —
version, SHAs, pass/fail per stage, "what happened at a glance." CloudWatch becomes the thing it
points *into* for full detail, not a replacement for it. The Release can embed a direct Logs
Insights query URL (pre-filled with that release's `version` parameter), so a human — or an AI
session with plain `aws logs start-query`/`get-query-results` CLI access, nothing special needed —
lands straight in the relevant slice of logs instead of hunting through Actions history.

**Cost:** negligible at this project's volume — CloudWatch Logs ingestion/storage pricing is small
per GB, and a handful of releases a month producing a few MB each doesn't approach a dollar. Bounded
further, and deliberately, by the retention policy below.

**Every log group this design creates or adopts gets an explicit retention — 120 days, to start
(added 2026-09-03, per the project's scale-to-zero principle: nothing accumulates forever, logs
included).** No exceptions, and no relying on CloudWatch's own default (which is "never expire"
unless set — the same gap already found and being fixed for the Lambda log groups applies to every
log group named in this Decision):

- `mootmaker-release`'s own `/mootmaker/release-pipeline` group.
- `mootmaker-api`'s Lambda log groups — **all four** (`resolvers`, `post_confirmation_create_person`,
  `database_reset`, `database_repair`), not just the two a smoke test actually invokes. Retention is
  a blanket commitment now; the `mootmaker:release-logs` *discovery* tag (which log groups the
  saved query pulls in) stays scoped to what's actually relevant to a smoke test — a query that
  found zero matching lines in a tagged-but-irrelevant group would cost nothing to include, but
  there's no reason to widen the query's scope just because retention widened.
- `mootmaker-api`'s new AppSync log group.
- `mootmaker-demo-data`'s Lambda log group.

Each repo's own Terraform declares its own retention value (`var.log_retention_days`, default
`120`) rather than any single shared source — this project has no cross-repo Terraform variable
mechanism without reintroducing the coupling Decision 11 already rejected once (the
`terraform_remote_state` discussion above), so "the same starting number, set independently in each
repo, tunable independently later" is the honest shape, not a shared config file pretending
otherwise.

**Implication worth stating plainly: Decision 11's logs are not actually permanent, only
longer-lived than GitHub's.** 120 days is a deliberate ~30-day buffer past GitHub Actions' own
90-day default, not an accident — but it means troubleshooting a release from five months ago will
find the GitHub Release (Decision 5) — version, SHAs, pass/fail per stage — genuinely forever, while
the CloudWatch detail behind it is already gone. That asymmetry is accepted, not a gap: Decision 5's
summary is cheap to keep forever (a handful of GitHub Releases, not GBs of log data); Decision 11's
detail trades permanence for being useful *now*, close to when a release actually happened, which is
when troubleshooting it is overwhelmingly likely to happen anyway. If 120 days ever proves too
short in practice, it's a one-line `var.log_retention_days` change per repo, not a redesign.

**A real rollout gotcha, not just a Terraform nicety:** `test` and `production` already have all
five Lambdas (and, once enabled, AppSync) running today, which means their log groups **already
exist**, auto-created and Terraform-unmanaged. `aws_cloudwatch_log_group`'s `CreateLogGroup` call
fails with `ResourceAlreadyExistsException` against a name that already exists — so simply adding
these resources and running `terraform apply` will error on `test`/`production` (though it'd work
cleanly against a fresh ephemeral environment, where nothing exists yet). Each pre-existing log
group needs a `terraform import` before the first apply that introduces it, not a plain create —
worth sequencing explicitly in Rollout rather than discovering it mid-apply.

### 12. PR checks become a required gate, scoped per component's actual tech

**Decision (added 2026-09-03, resolves NB-3):** for the three deployable components —
`mootmaker-api`, `mootmaker-webapp`, `mootmaker-demo-data` — PR checks move from advisory to a
**required status check** (GitHub branch protection: "Require status checks to pass before
merging"). A PR that fails its checks cannot be merged, full stop, including by Claude. Each
repo's check is scoped to what actually exists in it today, verified rather than assumed:

- **`mootmaker-api` / `mootmaker-demo-data`** (same shape — Maven, an `impl/` module plus a
  separate `verify/` acceptance module): `mvn -f impl/pom.xml test`. **Never `verify/`** — that
  module needs a real deployed AWS environment, and PR checks never touch AWS (unchanged principle
  from the first draft). No lint/format step yet — see the new Non-goal below.
- **`mootmaker-webapp`**: `npm run lint` (oxlint), the typecheck half of `npm run build` (`tsc -b`),
  `npm run test:unit` (Vitest), `npm run codegen:check` (already required as of the other machine's
  work on `graphql-schema-sharing.md` — folded in here rather than duplicated), and `npm run
  test:integration` (Playwright against MSW — no live AWS, fast, deterministic).

**Reasoning:** NB-1 in the first draft (renumbered NB-3 here) left this advisory deliberately,
reasoning that branch protection would "mostly obstruct" a solo developer with no approval step to
gate on — true for *review* gates, but a status check is a different kind of gate, and one that
matters more now than it did at the first draft: self-merge (including by Claude) is already the
norm here, and the release pipeline's whole premise — "everything currently on `main` gets
released" — depends on `main` actually staying green between releases, not just usually being
green. `mootmaker-webapp`'s check is deliberately fuller than the two Java repos' right now, not
symmetric — see the Non-goals addition on Spotless for why.

**Not built as part of this design's own implementation work** (no workflow files, no branch
protection settings changed yet) — scoped in for Geoff to review as part of this design reaching
`Ready`, matching everything else in the Implementation checklist.

---

## Choices you had me make

Repo topology (`mootmaker-release` as a new dedicated repo, and splitting `mootmaker-test-infra`
into `mootmaker-ephemeral-envs`/`mootmaker-email-testing`) was decided together, not unilaterally —
see Decision 1 and Technical considerations, not this list.

1. **`workflow_call` over `repository_dispatch`/a PAT with `actions:write`** for invoking each
   component's build-and-deploy logic, to keep the PAT's scope down to `contents: write` for tagging
   only. Flagged in Decision 3 as worth reviewing given it's still a documented exception to the
   no-long-lived-credentials principle.
2. **GitHub Releases (on `mootmaker-release`) as both the version source of truth and the durable
   release log**, rather than a separate version file plus a separate logging mechanism. Chose this
   to reuse one artifact for two needs.
3. **Tag after build-and-test passes, not before**, so a tag never marks a commit that failed. The
   user's original description tagged first; reordered here because it removes any need to ever
   "unwind" a tag, at the cost of the tagged commit being implicitly "whatever `main` was at trigger
   time" rather than a name fixed before the build starts. Worth confirming this reordering is fine.

---

## Open questions

**All four blocking questions resolved by Geoff on 2026-09-03.** Nothing now blocks this design
moving to `Ready` once its Implementation checklist is filled in accordingly.

### Blocking (resolved)

- [x] **OQ-1 — Where does the smoke-test code live?** Resolved: `mootmaker-release` — see Decision
  9. Neither of the two options originally offered (`mootmaker-webapp/smoke/`,
  `mootmaker-ephemeral-envs`) was quite right; `mootmaker-release` is where the release pipeline
  already lives, so the smoke tests it runs belong there too.
- [x] **OQ-2 — Automatic rollback confirmed**, not stop-and-notify — see Decision 10. The masking
  risk (an automatic redeploy hiding a data-shape problem) is accepted knowingly: leaving
  `production` visibly broken while waiting on a human is worse for a public demo, and the GitHub
  Release still records that a rollback happened and why.
- [x] **OQ-3 — Fine-grained PAT confirmed**, not a GitHub App — see Decision 3. The extra
  correctness a GitHub App would bring doesn't earn its setup cost at this project's scale; the
  exception to the no-long-lived-credentials principle is accepted and recorded, not hidden.
- [x] **OQ-4 — Draft the OIDC deploy role's CloudFormation now**, rather than waiting for the other
  three questions — it doesn't depend on any of them and sits on the critical path (Rollout step 1).
  **Drafted 2026-09-03** — `workload-account/github-actions-deploy-role.yaml` in
  `mootmaker-bootstrap-aws-accounts` ([PR #5](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts/pull/5),
  not yet applied): a fresh OIDC provider (verified none existed) and a deploy role whose trust
  condition is scoped to `job_workflow_ref`, not just `repository` — only a run of one of the four
  specific reusable-workflow files this design describes (none of which exist yet) can assume it.
  Still needs a `[Geoff]` manual apply in the **workload** account (431071856068, not the
  management account — this role deploys `test`/`production`, which live there) before anything
  downstream can be tested end to end.

### Non-blocking

- **NB-1 — Should `test`'s Terraform state ever be reset from scratch** (rather than left to
  accumulate release after release, same as `production`), and on what trigger, if ever? Currently
  no plan to — `production` never gets this either — but worth a deliberate "no" rather than silence.
- **NB-2 — Does demo-data need an explicit one-off seed invocation after deploying to `test`**, or is
  waiting for its own weekly schedule acceptable? The smoke test's "view some data" step needs
  *something* to be there; see Technical considerations.
- **NB-3 — Resolved 2026-09-03: yes**, required, for the three deployable components — see Decision
  12. Carried over unresolved from the first draft (NB-1 there) until reconsidered on review.
- **NB-4 — Does the schema-publish step (now already live in `mootmaker-api`) need any coordination
  with the release version**, e.g. tagging the published schema artifact with the same release
  version? Not addressed here; worth a look once this pipeline exists.

---

## Impacts on components

| Repository | Impact |
|---|---|
| `mootmaker` (hub) | No `release.yml` here (Decision 1, revised) — impact is docs-only. `docs/process/principles.md`'s "`test` was retired... could not justify its standing cost" line needs rewriting to reflect Decision 6's reasoning, not deleting the history but adding the reversal and why. `docs/process/environments.md`'s "exactly two kinds" becomes three. |
| `mootmaker-release` (new repo) | Gains `release.yml` (the orchestrator, `workflow_dispatch`-triggered), the PAT secret, the cross-component smoke-test suites (resolved home, OQ-1), and publishes the GitHub Release (Decision 5). Also gains its **first real Terraform** (Decision 11): the `/mootmaker/release-pipeline` CloudWatch Log Group and its `QueryDefinition`(s), deployed once like `mootmaker-domain`'s pattern. Scaffolded 2026-09-03; none of this built yet. |
| `mootmaker-api` | Gains a reusable `release-build.yml` (`on: workflow_call`) doing build + unit test + acceptance-against-fresh-ephemeral + artifact upload, called by `mootmaker-release`'s `release.yml` per release. Also gains a required `pr-checks.yml` (Decision 12): `mvn -f impl/pom.xml test`, branch protection enabled. And explicit, tagged `aws_cloudwatch_log_group` resources for its Lambdas (Decision 11) — none exist today, so this also fixes an unset-retention gap along the way. Also gains AppSync CloudWatch logging (Decision 11) — not enabled today — plus a tagged log group adopting it and the IAM role/policy that turns it on. |
| `mootmaker-webapp` | Same shape as `mootmaker-api`. Its required `pr-checks.yml` (Decision 12) additionally runs **`npm run codegen:check`** — see Technical considerations; "build and unit tests" does not cover it — plus lint, typecheck, and the mocked integration suite. Also: `mootmaker-webapp#3` — fixed 2026-09-03 (PR [#17](https://github.com/geoffweatherall/mootmaker-webapp/pull/17)), unblocking Decision 8. `acceptance/`'s config made CI-aware (Decision 7) — `mootmaker-webapp#19` (PR [#20](https://github.com/geoffweatherall/mootmaker-webapp/pull/20), open). No Lambdas, so Decision 11's log-group tagging doesn't apply here. |
| `mootmaker-demo-data` | Same shape as `mootmaker-api` — first time it's included in an automated pipeline, and gains both the required `pr-checks.yml` shape (Decision 12) and the tagged Lambda log group treatment (Decision 11). |
| `mootmaker-ephemeral-envs` (renamed from `mootmaker-test-infra` 2026-09-03) | `create-ephemeral-env.sh`/`teardown-ephemeral-env.sh` unchanged in mechanism; docs updated to describe `test` as a second protected, standing name (the scripts already treat it as one, per Decision 6). |
| `mootmaker-email-testing` (split from `mootmaker-test-infra` 2026-09-03) | No direct pipeline changes — the standing `test` environment's smoke test reads from its persistent SQS queue the same way `mootmaker-webapp`'s existing `e2e`/`acceptance` suites already do. |
| `mootmaker-bootstrap-aws-accounts` | Gains the OIDC identity provider + deploy role (OQ-4), scoped to three deploy targets. Its policy needs two more additions for Decision 11: `logs:*` scoped to the new release-pipeline log group, and `tag:GetResources` for the tag-based Lambda-log-group discovery. |

---

## Changes to the domain data model and data storage models

**N/A.** This design changes how deployment and release happen, not what is deployed or stored.

---

## Technical considerations

- **`mootmaker-webapp`'s PR checks need `npm run codegen:check`, which is neither a build nor a unit
  test.** Since `designs/archive/graphql-schema-sharing.md` shipped, `webapp/src/graphql/generated/`
  is generated from the API's schema and committed. Codegen reads the **sibling `mootmaker-api`
  checkout when present** and the published `@mootmaker/schema` package otherwise — which is what
  makes local development against an unpublished schema work, and is also what lets `main` go
  inconsistent without anything noticing.

  The failure mode is concrete. A coordinated schema change is developed locally, so the committed
  generated code reflects the *new* schema while `package.json` still pins the *old* published
  version. Merge that and anyone cloning fresh — no sibling checkout — regenerates from the pinned
  version, gets a diff, and `tsc` fails on fields that no longer exist. `codegen:check` regenerates
  and fails on any diff, which catches exactly this; today nothing runs it, so it depends on a human
  remembering.

  Ordering matters within the check: `codegen:check` before `tsc`, so a drift failure reports "the
  generated types are stale" rather than a pile of downstream type errors that do not name the
  cause.
- **`workflow_call` across repos needs no PAT for public repos** — `uses:
  owner/repo/.github/workflows/file.yml@ref` runs with the caller's own token; only the tag push
  (Decision 3) needs one.
- **Artifacts (`actions/upload-artifact`/`download-artifact`) live for the life of the workflow
  run** — comfortably long enough for one release, no separate artifact store needed.
- **GitHub Actions log retention defaults to around 90 days** — the GitHub Release (Decision 5) is
  what outlives that, not the raw logs; link to the run from the Release rather than relying on the
  run itself staying available.
- **`test` needs demo-data seeded the same way `production` gets it**, or the smoke test's "view some
  data" step has nothing to look at. Whether that's the weekly schedule alone or an explicit
  post-deploy invocation is NB-2.
- **`teardown-ephemeral-env.sh` already refuses to touch `test` or `production`** by name-shape
  (Decision 6) — no change needed there, but worth a docs pointer so nobody re-derives this from
  scratch.
- **Terraform state locking (`use_lockfile = true`) already exists** per environment — relevant now
  that `test` is a second standing environment a release pipeline and (in principle) a person could
  both touch; unchanged from the first draft's note, just more load-bearing with two standing
  environments instead of one.
- **`mootmaker-webapp/webapp` and the repo root have separate `package.json` files** — unchanged trap
  from the first draft, still applies to the new reusable workflow.

---

## Testing impacts

- **New layer: smoke tests**, distinct from unit/mocked-integration/acceptance (Decision 9). Two
  variants — full-ish against `test`, minimal against `production`.
- **Acceptance suites now run at release time, not just on demand** — each component's existing
  acceptance suite runs in Stage 1 (build-and-test) against a fresh ephemeral environment, per
  release. This is new automated usage of test infrastructure that previously only ran when someone
  chose to run it.
- **PR checks are required now, scoped differently per repo** (Decision 12, NB-3) — still unit +
  mocked-integration only, no AWS access, still deliberately not full acceptance-on-PR (OQ-2 in the
  first draft, not reopened here). What's new is that a failing check blocks merge, and
  `mootmaker-api`/`mootmaker-demo-data` don't yet have a lint step (no Java formatter configured;
  see the Non-goals addition on Spotless) while `mootmaker-webapp` does — an intentional, temporary
  asymmetry, not an oversight.

---

## Documentation impacts

- `docs/process/principles.md` — the "`test` was retired... could not justify its standing cost"
  line under Cost needs to say what's still true (a standing environment must justify itself) and
  record that `test` came back for a specific, different reason (Decision 6), not silently revert to
  the pre-retirement wording.
- `docs/process/environments.md` — "exactly two kinds: `production`, and ephemeral" becomes three;
  add a `test` section describing its lifecycle (updated only by the release pipeline, never torn
  down, never ad hoc).
- `docs/development/environments.md` — mechanics section, if it enumerates environment kinds
  anywhere.
- Each of the three component repos' `AGENTS.md`/`README.md` — note that release (not just
  production deploy) happens via `release.yml`, and that `deploy.sh <environment>` by hand still
  works for ephemeral work but is no longer how `test` or `production` get updated.

---

## Rollout & migration

1. **`[Claude]`** Fix `mootmaker-webapp#3` (Decision 8's blocking dependency) — needed before
   build-once-promote means anything for the webapp. **Done 2026-09-03** (PR
   [mootmaker-webapp#17](https://github.com/geoffweatherall/mootmaker-webapp/pull/17)).
2. **`[Geoff]`** Resolve OQ-1 through OQ-4. **Done 2026-09-03.**
3. **`[Claude]`** Write the OIDC provider + deploy role CloudFormation in
   `mootmaker-bootstrap-aws-accounts`, scoped to the three deploy targets (OQ-4). **Done
   2026-09-03** — [PR #5](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts/pull/5).
4. **`[Geoff]`** Apply that stack via the CloudFormation console in the **workload** account
   (431071856068, not the management account — this role deploys `test`/`production`). **Done
   2026-09-03** — applied via CLI with Geoff's own SSO session (workload-account stacks don't need
   root); one bug found and fixed along the way (`ThumbprintList` truncated by one character —
   [mootmaker-bootstrap-aws-accounts#6](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts/issues/6)),
   `CREATE_COMPLETE` confirmed against live AWS, not just stack status.
5. **`[Claude/Geoff]`** Create the PAT (OQ-3: PAT, not a GitHub App) and store it as a
   `mootmaker-release` Actions secret.
6. **`[Claude]`** Build each component's `release-build.yml` (reusable, build + unit + acceptance +
   artifact upload) and prove each one standalone before wiring up the orchestrator.
7. **`[Claude]`** Build `mootmaker-release/release.yml`: version computation, tagging, calling each
   component's `release-build.yml`, deploy-to-`test`, smoke-test-`test`, deploy-to-`production`,
   smoke-test-`production`, GitHub Release publish, rollback-on-failure.
8. **`[Claude]`** Build the smoke-test suites in `mootmaker-release` (OQ-1), including its Node/
   Playwright setup from scratch — the repo has none yet.
9. **`[Geoff]` + `[Claude]`** Stand up `test` as a real environment for the first time under this
   design (it does not currently exist — it was fully torn down 2026-08-29) and run the pipeline
   against it end to end at least once before it touches `production`.
10. **`[Claude]`** Cut over: retire `./deploy.sh production` run by hand as the sanctioned path for
    `production`, same as the first draft's plan, now via `release.yml` instead of merge-to-`main`.
11. **`[Claude]`** Ephemeral sweep (unchanged from the first draft): report-only first, automatic
    teardown only after a clean trial period. Independent of the rest of this rollout and can proceed
    in parallel.
12. **`[Claude]`** Consolidated CloudWatch logging (Decision 11): the tagged, 120-day-retention
    Lambda log groups in `mootmaker-api`/`mootmaker-demo-data`; `mootmaker-api`'s AppSync
    `log_config` + its own adopted, tagged, 120-day-retention log group + the logging IAM role
    (wildcard-scoped to break the cycle); `mootmaker-release`'s own 120-day-retention log group +
    `QueryDefinition`(s); the two IAM additions to the OIDC deploy role. **On `test`/`production`
    specifically, `terraform import` each pre-existing Lambda/AppSync log group before the first
    apply that introduces its `aws_cloudwatch_log_group` resource** — they already exist, and a
    plain create fails against a name that's already taken; a fresh ephemeral environment has no
    such issue since nothing exists there yet. Independent of the release pipeline itself — no PAT,
    no `release.yml` dependency — can proceed any time, same as the ephemeral sweep and the
    PR-checks work.
13. **`[Claude]`** Build the three components' `pr-checks.yml` (Decision 12) and enable required
    status checks (branch protection) on each. Independent of the release pipeline itself — no PAT,
    no OIDC role, no `mootmaker-release` dependency — and can proceed in parallel with the rest of
    this rollout, same as the ephemeral sweep.

No data migration beyond standing `test` back up from nothing.

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **`test` drifts from `production`'s shape over time** (the exact failure mode that got it retired once already). | Medium | `test`'s state changes only through the release pipeline, same as `production`'s; demo-data seeds it the same way (NB-2 pending); no ad hoc interactive use — ephemeral environments exist for that. |
| **A failed `test`-stage smoke test leaves `test` broken, blocking the next release's deploy-to-`test` step** until fixed by hand. | Medium, accepted knowingly | This is Decision 6a's entire point — the alternative is finding out in `production`. Named here so it isn't mistaken for a bug later. |
| **PAT compromise** (Decision 3) reaches four repos with write access. | Medium | Scope strictly to `contents: write`, nothing broader. Accepted per OQ-3 rather than switching to a GitHub App — revisit if this ever proves too narrow a mitigation in practice. |
| **Tags exist naming a version with no corresponding GitHub Release** if the run fails between the tag push (Decision 4) and the final record-publish step, and that step isn't guaranteed to run. | Medium, found on review 2026-09-03 | The `record-outcome` job (Decision 5) must run with `if: always()` and branch on a job output set at tag-push time, not on later jobs' own success — spelled out in Decision 5 specifically so this doesn't get built as an afterthought. |
| **Automatic production rollback (Decision 10) masks a data-shape problem** that a redeploy of old code doesn't actually fix, giving false confidence that "rollback succeeded." | Medium | Accepted per OQ-2 — the GitHub Release still records that a rollback happened, so the masking is never silent even though it is automatic. |
| **Over-broad OIDC role scope**, carried over from the first draft, now covering three deploy targets instead of one. | High | Same mitigation as before: least privilege, reviewed CFN, expect iteration during bring-up. |
| **A scheduled ephemeral sweep and a release race on Terraform state.** | Low | State locking already exists; unchanged from the first draft. |
| **Troubleshooting a release older than 120 days finds no CloudWatch detail**, only the GitHub Release's summary. | Low, accepted knowingly | The whole point of the retention policy added 2026-09-03 — permanence was never the goal, staying within scale-to-zero was. Bump `var.log_retention_days` per repo if 120 days ever proves too short in practice. |
| **`terraform apply` fails on `test`/`production` when Decision 11's log-group resources are first introduced**, since the Lambda/AppSync log groups they name already exist (auto-created, unmanaged). | Medium, if missed | `terraform import` each one first — named explicitly in Rollout step 12 so it isn't discovered mid-apply against a real environment. |

---

## Implementation checklist

All four blocking questions are answered (see Open questions), so this is now filled in properly.
Status stays `Drafting` until Geoff promotes it — a design does not self-promote to `Ready`.

- [x] `[Geoff]` Resolve OQ-1 through OQ-4. **Done 2026-09-03.**
- [x] `[Claude]` Fix `mootmaker-webapp#3`. **Done 2026-09-03**
      ([PR #17](https://github.com/geoffweatherall/mootmaker-webapp/pull/17)).
- [x] `[Claude]` Write the OIDC provider + deploy role CloudFormation (scoped to three targets).
      **Done 2026-09-03** ([PR #5](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts/pull/5)).
- [x] `[Geoff]` Apply that stack via the CloudFormation console in the workload account. **Done
      2026-09-03**, verified against live AWS.
- [ ] `[Claude/Geoff]` Create and store the cross-repo tag-push PAT as a `mootmaker-release` secret.
- [ ] `[Claude]` Build each component's `release-build.yml`.
- [ ] `[Claude]` Build `mootmaker-release/release.yml` end to end, including the `record-outcome`
      job (Decision 5) — `if: always()`, branching on the tag-push job's own output, not on
      whether later jobs succeeded.
- [ ] `[Claude]` Build the smoke-test suites in `mootmaker-release`, including its Node/Playwright
      setup from scratch.
- [ ] `[Geoff]`/`[Claude]` Stand `test` back up and run the full pipeline against it at least once
      before it ever reaches `production`.
- [ ] `[Claude]` Cut `production` over to the release pipeline as the sanctioned path.
- [ ] `[Claude]` Build the scheduled ephemeral sweep (unchanged from the first draft).
- [ ] `[Claude]` Build the tagged, 120-day-retention Lambda log groups (`mootmaker-api`/
      `mootmaker-demo-data`), `mootmaker-api`'s AppSync logging (`log_config` + its own adopted,
      tagged, 120-day-retention log group + wildcard-scoped logging role), `mootmaker-release`'s own
      120-day-retention log group + `QueryDefinition`(s), and the two IAM additions to the OIDC
      deploy role (Decision 11). Remember `terraform import` for each pre-existing log group on
      `test`/`production` — independent of the rest, can proceed any time.
- [ ] `[Claude]` Build `pr-checks.yml` for `mootmaker-api`/`mootmaker-webapp`/`mootmaker-demo-data`
      (Decision 12) and enable required status checks on each — independent of the rest, can proceed
      any time.
- [ ] `[Claude]` Update the documentation named in Documentation impacts.

---

## Definition of done

- `gh workflow run release.yml` (or the Actions UI equivalent) is the only way `test` or
  `production` change — no `./deploy.sh test|production` run by hand as the sanctioned path.
- A release has gone all the way through: version computed, all three components tagged, built,
  acceptance-tested, deployed to `test`, smoke-tested, deployed to `production`, smoke-tested, and
  recorded as a GitHub Release — at least once, for real.
- A `test`-stage smoke-test failure has been deliberately exercised at least once, confirming the
  release correctly stops before `production` and leaves `test` inspectable.
- The automatic production rollback (Decision 10) has been exercised at least once, deliberately.
- The ephemeral sweep has been running in report-only mode for its stated trial period with no false
  positives, or has graduated to automatic teardown.
- No AWS access key or long-lived AWS credential is stored anywhere in GitHub. The one accepted
  exception (the tag-push PAT, OQ-3) is documented as such, not incidental.
- All three deployable components have a required, branch-protection-enforced PR check (Decision
  12) — deliberately exercised at least once each by a PR that fails it, confirming merge is
  actually blocked, not just that the check runs.
- A completed release's logs — at least one Terraform apply and one smoke-test run — are actually
  findable in CloudWatch via the saved query (Decision 11), including the relevant Lambda execution
  logs *and* AppSync's own request/resolver logs alongside them, not just theoretically wired up.
- Every log group Decision 11 creates or adopts has its retention verified as actually set to 120
  days against live AWS (`aws logs describe-log-groups`), not just declared in Terraform and assumed.
