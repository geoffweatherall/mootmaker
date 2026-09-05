# CI/CD pipeline

## Summary

Mootmaker has no CI and deploys to production from a developer's own machine, by hand. This design
proposes GitHub Actions for two things: automated checks on every pull request (unchanged from the
first draft), and a **specifically-initiated release pipeline** — triggered by a human or an AI via
`gh workflow run`, never by merging to `main` — that versions, builds, and tests `mootmaker-api`,
`mootmaker-webapp` and `mootmaker-demo-data` together, proves them in a standing `test` environment,
and only then promotes the same artifacts to `production`.

**Status:** Building — 2026-09-04. Supersedes this doc's own 2026-08-29 draft on the trigger model
and the standing-`test` question; see "What changed since the last draft" below.

It stayed at Drafting through the whole build-out, which was simply wrong — Geoff authorized
building from it on 2026-09-03 (see "Execution authorization for this build-out"), which is the
Ready transition, and implementation started immediately. The Implementation checklist below is now
fully ticked and eight of the nine Definition-of-done items are met. It moves to **Shipped**, and
into [`archive/`](archive/), when the ninth does: the ephemeral sweep's report-only trial period,
whose length is asked in [#51](https://github.com/geoffweatherall/mootmaker/issues/51).

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

**Concurrent triggers, guarded (confirmed 2026-09-03):** nothing about `workflow_dispatch` itself
stops two release runs from overlapping — a human and an AI both starting one, or a double-click —
which could race on reading "the current version," on tagging, or on deploying to the same standing
`test`/`production`. `release.yml` declares `concurrency: { group: release, cancel-in-progress:
false }`: a second trigger queues behind the first rather than running alongside it or killing it
mid-deploy. Queuing, not cancelling, is the deliberate half of that — cancelling a release mid-`terraform
apply` is a worse outcome than making the second trigger simply wait.

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
component's commit SHA and tag, links to every stage's Actions run, a pass/fail per stage
(build+acceptance / deploy-to-test / smoke-test-test / deploy-to-production /
smoke-test-production), and — resolved 2026-09-03, NB-4 — the `@mootmaker/schema` npm package
version published from `mootmaker-api`'s tagged commit.

**NB-4 resolved 2026-09-03: traceability only, no coupling.** The schema (`api/mootmaker.graphql`)
already publishes independently on every merge to `mootmaker-api`'s `main`, versioned by its own
semver in `api/package.json` (see that repo's README, "The schema is published as a package") —
that mechanism is unrelated to this pipeline and stays unrelated: this design does not gate
tagging on it, does not wait for it, and does not make the two version numbers match. All this adds
is a lookup — `npm view @mootmaker/schema version` (or the GitHub Packages equivalent) for the exact
commit SHA being tagged as `mootmaker-api`'s side of the release, recorded as one more field in
`record-outcome`'s Release body — so a human or AI looking at a release later, debugging something
that smells like a schema mismatch, can see which schema version shipped with it without cross-
referencing `api`'s own commit history separately. Rejected: gating the release on publish-schema.yml
having succeeded — that makes this pipeline depend on a workflow with its own independent trigger
and timing, for a check that a webapp build already effectively performs itself (it fails to build
against a schema version its generated code doesn't match).

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

**NB-1 resolved 2026-09-03: `test`'s Terraform state is never reset from scratch, automatically or
on a schedule** — confirmed, not just left silent by default. It is treated identically to
`production` in this respect: state accumulates release after release, indefinitely. This is a
deliberate consequence of Decision 6's own reasoning — the entire value of `test` is that its state
history looks like `production`'s (an ever-updated, never-fresh apply target); resetting it on any
schedule would periodically hand it back the ephemeral environments' "always a create" character
that `test` exists specifically to not have. If a reset is ever genuinely needed (state corruption
beyond what Decision 6a's manual-inspection path can fix), that's a deliberate, manual, one-off
action outside the pipeline — not something this design builds automation for.

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

**Confirmed 2026-09-03: a GitHub Actions artifact is the right, and final, home for this stage's
output — it does not also ship to CloudWatch (Decision 11).** Considered and deliberately rejected,
not an oversight: Decision 11's whole reason for existing is that a release's summary (Decision 5)
needs durable, queryable detail behind it once a version has actually been claimed. Stage 1 runs
*before* any tag exists — a failed Stage 1 attempt claims no version at all, so there is nothing
for its logs to be *the detail behind*. The same reasoning extends to **everything else this stage
produces**, confirmed the same day: the ephemeral environment's own Lambda/AppSync logs, and the
Terraform apply/destroy output that stands the environment up and tears it down in the first
place — none of it is pulled out and shipped to CloudWatch. Whatever `verify`/`acceptance` output
already captures as a workflow artifact is sufficient for a stage this transient; the "every
Terraform stage" language in Decision 11 means every stage *after* a version is tagged, not
literally every `terraform apply` anywhere in the pipeline.

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
- **`production`-stage smoke test:** narrower, and — corrected 2026-09-03 — **strictly read-only,
  no exceptions**: sign in as the published demo user, navigate around the app, confirm data reads
  from the database and displays correctly. No new-account signup, no deletion, no password reset,
  and (this design's own first draft got this wrong) **no meeting creation either** — production
  gets no writes from this stage at all, only `test`'s smoke test mutates data.

**Reasoning:** matches what was asked for directly — a human-tester-shaped check, not acceptance
testing twice. Reusing the existing SES-based test-infra email support for the `test`-stage signup
flow avoids building new email-verification plumbing. The asymmetry between the two stages is
deliberate, confirmed 2026-09-03: `test` mutating data (signup, meeting creation, password reset,
account deletion) is fine — that's exactly what closes the "does a write actually work" gap this
whole layer exists for — but `production`'s smoke test verifying *only* reads means it can never be
the thing that leaves stray data behind release after release, so there's no accumulation question
to solve here the way there was for logs.

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
console text: `terraform apply -json` for every Terraform stage *after a version is tagged*
(deploy-to-`test`, deploy-to-`production`, the rollback redeploy — not Stage 1's own ephemeral
create/destroy, see Decision 7), Playwright's JSON reporter for the
smoke tests, and each component's Stage 1 build-and-unit-test output (Maven's Surefire reports for
`mootmaker-api`/`mootmaker-demo-data`, Vitest's own structured output for `mootmaker-webapp`) —
this last one **only for the release pipeline's own `release-build.yml` run, never for PR checks**
(Decision 12): a PR isn't tied to a release version, has no natural field to tag it with, and
GitHub's own Checks tab is already a fine home for it — shipping it here would just be noise with
nothing to correlate it against. Consistent fields across everything shipped (`version`, `stage`,
`component`, `outcome`) are what make this queryable rather than just archived.

**Deliberately not shipped here, confirmed 2026-09-03: Stage 1's *acceptance*-test output** (as
opposed to its unit-test output, which is shipped), **the ephemeral build environment's own
Lambda/AppSync logs, and the Terraform apply/destroy that stands it up and tears it down** — same
underlying reason as excluding PR checks, not a separate exception. Stage 1 runs before any tag
exists; if it fails, no version was ever claimed, so there's no release for this detail to sit
behind. A GitHub Actions artifact (Decision 7) is the right, and final, home for it.

**Other AWS services surveyed and deliberately left out (confirmed 2026-09-03), so their absence
reads as a decision, not a gap found later:**

- **SNS delivery-status logging** (`mootmaker-email-testing`'s topic) — opt-in, off today; the
  SQS-consumption path it would corroborate is already exercised by the e2e/acceptance suites
  separately.
- **S3/CloudFront access logs** (`mootmaker-webapp`'s site bucket/distribution) — a genuinely
  different destination (S3 or Kinesis, not CloudWatch Logs), out of step with this design's whole
  Logs-Insights-centric approach; would need a separate pipeline, not a tag/discovery tweak.
- **Route53 Resolver query logging** — opt-in, DNS resolution activity is not useful signal for
  release troubleshooting specifically.
- **CloudTrail** (the account-wide API-call audit log) — considered and left fully out of scope: a
  security/audit-trail concern, not a release-troubleshooting one, and account-wide rather than
  release-scoped. A different design's job if ever wanted.
- **DynamoDB and Cognito** — checked, not applicable rather than excluded: neither has a native
  CloudWatch Logs group the way Lambda/AppSync do (DynamoDB exposes metrics/streams only; Cognito
  user-pool operations have no equivalent log group). Auth outcomes already surface indirectly
  through AppSync's own logs.
- **The scheduled ephemeral sweep's own `terraform destroy` output** (a separate, periodic
  workflow, not part of any one release run) — same reasoning as excluding PR checks: no release
  version to tag it with.

**If the shipping step itself fails (confirmed 2026-09-03): non-fatal.** A `aws logs put-log-events`
call that errors (a transient throttle, a permission gap) should not fail the release stage it's
attached to — logging is diagnostic infrastructure, not the release's actual purpose, and a release
that deployed cleanly and passed its smoke tests shouldn't be blocked or rolled back because a log
call hiccupped. Each shipping step should be written so a failure there is caught and reported (not
silently swallowed — that would defeat troubleshooting a genuinely broken shipping path) without
propagating to the stage's own exit code.

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
and staying consistent with this project's existing loose-coupling preference. **Worth being
explicit rather than assumed: `test` and `production` each get their own tagged log group per
Lambda** (different names — `test-mootmaker-resolvers` vs. `production-mootmaker-resolvers`, since
the function names themselves are environment-prefixed) — this falls out naturally from declaring
the `aws_cloudwatch_log_group` resource in the same per-environment Terraform the Lambda itself is
in, applied once per environment as that Terraform already is; it is not one shared resource, and
needs no separate work beyond what's already planned. Needs one small IAM
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

**`mootmaker-release` itself considered and deliberately left out of this requirement (confirmed
2026-09-03)** — not an oversight, despite it holding the highest-blast-radius code in this whole
design (tag push, deploy, rollback). It isn't a "deployable component" the same way the other three
are — a different, lighter check would fit it better than duplicating this one — and isn't scoped
in here.

**Bring-up specifics for required status checks (added 2026-09-03, so none of this gets discovered
against an already-locked repository):**

- **Enable protection only after the check has reported at least once.** Branch protection matches a
  required check by its exact context name, and naming one that has never run leaves every PR stuck
  on "Expected — waiting for status" with no way to merge. Order it: merge `pr-checks.yml` while
  `main` is still unprotected, let it run, read the exact name from `gh pr checks`, then enable
  protection with that string copied verbatim, never hand-typed. Once protection references a job's
  `name:`, that name is frozen — renaming it later reproduces the same lock-out.
- **`enforce_admins: false`.** This decision's "cannot be merged, full stop, including by Claude" is
  honoured by behaviour — Claude never passes `--admin` — rather than by configuration. Chosen over
  `enforce_admins: true` so that a stuck required check cannot lock the repository for Geoff too,
  recoverable only by editing protection under pressure. The weaker guarantee is accepted knowingly;
  revisit if self-merge discipline ever slips.
- **No required pull-request reviews.** This decision asks for status checks only. On a
  solo-developer repository a required review is unsatisfiable — Geoff cannot approve his own PR —
  and would block `main` permanently. It is easy to tick by accident in the UI, so it is named here.
- **Enable repository auto-merge** (`allow_auto_merge`, verified `false` on all three components as
  of 2026-09-03) so Claude can use `gh pr merge --squash --auto`: GitHub queues the merge and
  completes it when checks pass, instead of an unattended run either failing on "checks pending" or
  busy-waiting through a multi-minute Maven or Playwright job. Set `delete_branch_on_merge: true` at
  the same time (also currently `false` everywhere) so branch cleanup needs no extra command.
- **Tag pushes are unaffected by branch protection**, so Decision 3's PAT tagging flow keeps working.
  Do not add *tag* protection rules — that would break it.
- All three component repositories are **public**, so branch protection and Actions minutes are both
  free and no plan constraint applies — consistent with Decision 2's finding that the binding
  constraint is AWS spend, not Actions minutes.

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
  **Drafted 2026-09-03, applied and since corrected** — `workload-account/github-actions-deploy-role.yaml`
  in `mootmaker-bootstrap-aws-accounts`
  ([PR #5](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts/pull/5)): a fresh
  OIDC provider (verified none existed) and a deploy role, applied by Geoff in the **workload**
  account (431071856068, not the management account — this role deploys `test`/`production`, which
  live there).
  **The draft's central scoping claim did not survive contact with AWS.** It conditioned trust on
  `job_workflow_ref` so that only a run of one specific reusable-workflow file could assume the
  role. AWS supports only `sub` and `aud` as OIDC condition keys — an unsupported key is not
  rejected when written, it silently evaluates as absent, so the condition never matched and every
  assume-role was denied. That is how the first real proving run failed
  ([bootstrap#9](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts/issues/9)).
  Trust is now keyed on `sub`: repository — by **immutable numeric ID**, which survives a rename —
  and ref pattern. **Pinning to a specific workflow file is not available in AWS at all**, so the
  compensating controls are the ref patterns (components only at `refs/tags/v*`, the orchestrator
  and the sweep only at `refs/heads/main`) plus branch protection, not workflow-file identity. Any
  workflow in those repos at a matching ref can assume the role. That is a weaker boundary than
  this question assumed when it was written, and worth knowing rather than inheriting the
  draft's wording.

### Non-blocking

- **NB-1 — Resolved 2026-09-03: no**, never reset automatically or on a schedule — `test`'s state
  accumulates indefinitely, identically to `production`. See Decision 6.
- **NB-2 — Resolved 2026-09-03: yes**, an explicit invocation, not the weekly schedule. A freshly
  created `test` (or one just reset) has had zero prior weekly ticks, so `test`-stage's own smoke
  test — "view existing (demo) data" — would find nothing on exactly the runs where the environment
  is newest. Deploy-to-`test` invokes `mootmaker-demo-data`'s Lambda once, synchronously, right
  after deploying it and before the smoke test runs. Same treatment isn't needed for `production` —
  the corrected `production`-stage smoke test (Decision 9) is read-only and never depends on
  freshly-generated data existing.
- **NB-3 — Resolved 2026-09-03: yes**, required, for the three deployable components — see Decision
  12. Carried over unresolved from the first draft (NB-1 there) until reconsidered on review.
- **NB-4 — Resolved 2026-09-03: traceability only**, not coupling. The release record (Decision 5)
  now includes the `@mootmaker/schema` version published from the tagged `mootmaker-api` commit;
  publishing itself stays fully independent (own trigger, own semver, no gating).

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
- **`test` needs demo-data seeded, explicitly, on every deploy-to-`test`** (NB-2, resolved) — an
  explicit post-deploy Lambda invocation, not the weekly schedule alone, since a freshly created or
  reset `test` has had no prior tick.
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

## Execution authorization for this build-out

**Geoff has explicitly authorized proceeding through the remainder of the Implementation checklist
below without stopping to ask — added 2026-09-03, read this before starting work here.** This
overrides, for this design's build-out specifically, both the project's normal review boundaries
(`docs/process/principles.md`'s five always-human-reviewed categories) and Claude's own general
default of confirming before hard-to-reverse or production-affecting actions:

- **Self-merge every PR this build-out produces**, including ones that would normally stay held —
  the smoke-test suites (normally "tests"), the CloudWatch logging Terraform, and any OIDC
  deploy-role CFN fix (normally "IAM/Terraform permissions"; the narrow-additive-fix delegation is
  already recorded in the Risks table below). `release.yml`/`release-build.yml` were already cleared
  for ordinary self-merge.
- **Trigger the release pipeline against real `test` → `production` without asking first** — the
  first run and every run after it. Geoff's own reasoning: mootmaker is a demo system with no real
  production data or users, so a bad production deploy here doesn't carry the weight it would for an
  actual business — finishing the build without stalling on a checkpoint matters more than a
  checkpoint that exists to protect something this project doesn't have.
- **Scope: this design's build-out only**, not a standing change to how mootmaker or Claude operates
  more broadly. A future design gets the normal review boundaries again unless Geoff says otherwise.
- **Not overridden by this:** the PAT's actual token value still never passes through a Claude
  session or conversation — Geoff creates and stores it himself (Rollout step 5). That's about not
  leaking a live credential into chat/session history, unrelated to the review-process boundary
  being relaxed here, and stands regardless of which machine or session is doing this work.
- If you are a session picking this work up fresh (possibly on a different machine, per Geoff's own
  note that local classifier/permission settings are machine-specific) — this is standing
  authorization to act on, not something to re-derive or ask Geoff to repeat.

### Local tooling permissions granted for unattended runs

**Added 2026-09-03**, after a dry run established that the previous configuration would have stalled
an unattended session. Verified empirically rather than assumed: `gh pr merge` was refused by Claude
Code's auto-mode classifier on three of four attempts before the change, and merged without a prompt
after it.

Geoff has granted the following on his development machine (user scope, `~/.claude/settings.json`,
`permissions.allow`) so Claude does not stop to ask mid-build:

- `gh pr:*`, `gh workflow:*`, `gh run:*`, `gh release:*`, `gh api:*`, `gh repo view:*`,
  `gh secret list:*` — opening, merging and closing PRs, triggering and watching release runs,
  publishing GitHub Releases, and setting branch protection.
- `git:*` — including `rebase`, `clean`, `restore` and `branch -D`. The last matters: `git branch -d`
  refuses a squash-merged branch, so ordinary post-merge hygiene needs `-D`.
- `terraform:*`, `aws:*`, `mvn:*`, `npm:*`, `npx:*` — component builds and environment work.
- `rm:*`, `mkdir:*`, `mv:*`, `cp:*` — ordinary file manipulation.

**Why allow rules rather than classifier guidance:** `permissions.allow` short-circuits the auto-mode
classifier deterministically, whereas `permissions.autoMode.allow` only advises it and proved
context-sensitive under test — the same `gh pr merge` invocation was permitted once and refused three
times. An unattended run needs the deterministic form. The `autoMode.allow`/`soft_deny`/`hard_deny`
block is still set and still governs anything the allow rules do not name.

**Deliberately still gated** (`permissions.ask` — these prompt, and will stall an unattended run,
which is the intent): `git push --force`, `git push -f`, `git reset --hard`, `git commit --amend`,
`git commit --no-verify`. A step that genuinely needs one of these is a signal to stop and think, not
to widen the rules.

**Not overridden by any of this:** the `RELEASE_TAG_PAT` value still never passes through a Claude
session (also recorded as a `hard_deny`), and hand-deploying or destroying `test`/`production` from a
developer machine remains a `soft_deny` — those environments change through the release pipeline.

**Scope caveat, accepted knowingly:** these are user-scope rules, so they apply to every project on
that machine, not only mootmaker. The narrower option was unavailable — the workspace-scope
`mootmaker-workspace/.claude/settings.json` allow list was found not to be applied at all, because
the workspace root is not a git repository. That is why its `Bash(gh *)`, `Bash(terraform *)` and
`Bash(aws *)` entries never took effect and every such command was falling through to the classifier.
Anyone reading that file should not trust it to be in force.

**Python is required too.** This repository's own link check — `python3 tools/check-links.py ..`, see
[`CLAUDE.md`](../CLAUDE.md) — is mandatory before committing prose changes, and several build-out
steps need small scripts. `Bash(python3:*)` and `Bash(python:*)` therefore belong in the same
user-scope allow list. Noted explicitly because a bare `python3` is a broader grant than the others
here: unlike `git` or `terraform`, it executes arbitrary code, so it is the one entry on this list
that widens what Claude can do rather than just which known tool it may reach. Accepted as the cost
of an unattended run that can satisfy this repository's own documented pre-commit step.

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
5. **`[Geoff]`** Create the PAT (OQ-3: PAT, not a GitHub App) and store it as a `mootmaker-release`
   Actions secret. **Done 2026-09-03** — fine-grained PAT, `contents: write` only, scoped to exactly
   the four repos named in Decision 3, stored as the `RELEASE_TAG_PAT` secret on `mootmaker-release`.
   `release.yml` should reference this exact secret name when built.
6. **`[Claude]`** Build each component's `release-build.yml` (reusable, build + unit + acceptance +
   artifact upload) and prove each one standalone before wiring up the orchestrator.
7. **`[Claude]`** Build `mootmaker-release/release.yml`: `concurrency: { group: release,
   cancel-in-progress: false }` (NB confirmed 2026-09-03 — queue overlapping triggers, don't cancel
   mid-deploy); version computation, tagging, calling each component's `release-build.yml`,
   deploy-to-`test` (including the explicit demo-data seed invocation, NB-2), smoke-test-`test`,
   deploy-to-`production`, smoke-test-`production`, GitHub Release publish, rollback-on-failure.
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
| **Over-broad OIDC role scope**, carried over from the first draft, now covering three deploy targets instead of one. | High | Same mitigation as before: least privilege, reviewed CFN, expect iteration during bring-up. **Bring-up execution model, decided 2026-09-03:** when a real workflow run fails on a missing permission, Claude may apply a narrow, additive-only fix to this one stack directly (no per-instance wait for Geoff) — Geoff reviews the resulting diff after the fact rather than before. Chosen deliberately over the alternative (Geoff applies every fix himself) to keep long unattended implementation stretches from stalling on a permission gap; revisit if an additive fix ever turns out not to be narrow in practice. |
| **A scheduled ephemeral sweep and a release race on Terraform state.** | Low | State locking already exists; unchanged from the first draft. |
| **The acceptance suites become a release gate, so pre-existing flakiness starts failing releases** for reasons unrelated to the change being released. | High — **materialised, and was the single largest cost of this build-out** | Not anticipated by this design, and worth recording as its most expensive surprise. Making the suites a gate did not *create* flakiness; it made existing flakiness *matter*, and it ran them consistently enough to expose bugs that ad hoc local runs had hidden for months. Every one turned out to be a real defect rather than test noise — see "What the gate exposed" below. |
| **Troubleshooting a release older than 120 days finds no CloudWatch detail**, only the GitHub Release's summary. | Low, accepted knowingly | The whole point of the retention policy added 2026-09-03 — permanence was never the goal, staying within scale-to-zero was. Bump `var.log_retention_days` per repo if 120 days ever proves too short in practice. |
| **`terraform apply` fails on `test`/`production` when Decision 11's log-group resources are first introduced**, since the Lambda/AppSync log groups they name already exist (auto-created, unmanaged). | Medium, if missed | `terraform import` each one first — named explicitly in Rollout step 12 so it isn't discovered mid-apply against a real environment. |

---

## What the gate exposed

Recorded because it was the largest unplanned cost of this build-out, and because the conclusion is
the opposite of the usual one about flaky tests.

**Making the acceptance suites a release gate did not create flakiness. It made existing flakiness
matter**, and — more usefully — it ran the suites *consistently, against consistently fresh
environments*, which is what turned intermittent noise into reproducible evidence. Ad hoc local runs
against a reused environment had hidden all of this for months.

**Every flake traced to a real defect. None was test noise.** That is the finding worth carrying
forward, because the instinct with an intermittent test is to quarantine or retry it, and here that
instinct would have been wrong four times out of four.

| Symptom | Actual cause |
|---|---|
| One test per run failing on `expect(getByText(name)).toBeVisible()` after a create, a different test almost every time | **DynamoDB `Scan` defaults to eventually consistent.** The webapp refetches once after a mutation and never again, so a stale read renders a list *permanently* missing the new row. Fixed with `consistentRead(true)` on six table Scans ([mootmaker-api#31](https://github.com/geoffweatherall/mootmaker-api/pull/31)) |
| Three meeting tests failing together | The room-availability schedule reads through a **GSI**, and DynamoDB rejects `ConsistentRead` on an index. Fixed client-side by carrying the created meeting through navigation state ([mootmaker-webapp#35](https://github.com/geoffweatherall/mootmaker-webapp/pull/35)) |
| F.53 failing on retry with a confusing wrong-room assertion | **The retry could never pass.** `SuggestRoomHandler` breaks capacity ties by name and `uniqueId()` is `Date.now()`-based, so the *failed* attempt's room always won the tiebreak. A retry in a state-accumulating suite converted a recoverable timeout into a certain failure ([mootmaker-webapp#30](https://github.com/geoffweatherall/mootmaker-webapp/issues/30)) |
| demo-data acceptance asserting "nothing to do" against data that existed | An SDK socket timeout at 30s against a ~35s cold start, so the SDK silently retried and the test read the *retry's* result ([demo-data#16](https://github.com/geoffweatherall/mootmaker-demo-data/issues/16)) |

**Two second-order lessons, both about diagnosis rather than the bugs themselves:**

**Playwright's failure artifacts never left the runner.** A flake could only be guessed at from a log
line saying an element was not found. Two wrong guesses were made before the capture existed; the
business-hours/timezone bug was diagnosed within minutes of adding it. Now uploaded on failure
([mootmaker-webapp#36](https://github.com/geoffweatherall/mootmaker-webapp/pull/36)).

**A single green run proves nothing about an intermittent fault.** Three releases went green *before*
either consistency fix existed. Frequency data — repeated runs against one environment — is the only
thing that distinguishes "fixed" from "did not fire this time", and it is worth the wall-clock cost.

**One genuine trade-off surfaced and got the wrong answer first.** `retries: 1` was set globally in
response to the F.53 finding; the very next release then failed on a *different* test that a retry
would rightly have absorbed. The correct shape is per-file: retries off only for the suite that
reasons about accumulated state, on everywhere else. Generalising from one test to a whole suite was
the mistake, and it took a release to catch.

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
- [x] `[Geoff]` Create and store the cross-repo tag-push PAT as a `mootmaker-release` secret. **Done
      2026-09-03** — stored as `RELEASE_TAG_PAT`.
- [x] `[Claude]` Build each component's `release-build.yml`. **Done 2026-09-03**, and proven
      standalone against real AWS at a throwaway `v*` tag rather than only reviewed:
      `mootmaker-api` 40 acceptance tests, `mootmaker-demo-data` 10, `mootmaker-webapp` 106
      Playwright tests against a real CloudFront distribution and real Cognito emails — each
      uploading its promotable artifact, each leaving no resources behind (verified with
      `aws … list-*`, not from the workflow's exit code).
      **Twelve real defects surfaced getting there, none of which review had caught.** They are
      worth recording because most were in the pre-existing bootstrap and product code, not in the
      new workflows:
      - **`terraform` is not preinstalled on GitHub runners.** Every `deploy.sh`/`undeploy.sh` call
        needs `hashicorp/setup-terraform@v3` first. Missed initially in all three workflows.
      - **`job_workflow_ref` cannot be used as an AWS IAM condition key** — GitHub's own AWS guide
        states "Support for custom claims for OIDC is unavailable in AWS"; only `sub` and `aud`
        work. The trust policy as written could never have matched, and an unsupported key fails
        *silently* as a generic authorization denial
        ([bootstrap-aws-accounts#9](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts/issues/9)).
      - **This account uses GitHub's immutable subject claim**, so `sub` carries numeric owner and
        repo IDs (`repo:geoffweatherall@1743794/mootmaker-api@1285433321:ref:…`). The conventional
        `repo:owner/name:ref:…` pattern every tutorial shows does not match. Pinning the IDs is now
        deliberate: they survive a rename, so a repo renamed away cannot carry this trust with it.
      - **Eight missing IAM permissions on the deploy role**, all sharing one cause: the policy was
        written for *apply-time* actions and omitted the reads Terraform performs during *refresh*
        (`route53:GetHostedZone`/`ListHostedZones`/`ListTagsForResource`,
        `ses:GetIdentityVerificationAttributes`, `dynamodb:DescribeContinuousBackups`,
        `iam:ListRolePolicies`, `ssm:DescribeParameters`, `lambda:ListVersionsByFunction`, the S3
        bucket-property reads, `s3:ListBucketVersions`), plus two runtime ones the deploy path never
        needed (`lambda:InvokeFunction` for the acceptance suites' `database-reset` call, and
        `sqs:ReceiveMessage` on the email-testing queue).
        **The consequence is worse than a failed deploy:** `terraform destroy` refreshes first, so a
        missing *read* strands infrastructure. Four separate runs left live DynamoDB tables, Lambdas
        and an S3 bucket that had to be destroyed by hand. Decision 7's "always torn down" guarantee
        depends on the deploy role's read permissions, not just its write ones — worth stating,
        because it is not obvious.
      - **`mootmaker-demo-data`'s acceptance suite was asserting on a silent SDK retry**
        ([demo-data#16](https://github.com/geoffweatherall/mootmaker-demo-data/issues/16)).
        `apiCallTimeout`/`apiCallAttemptTimeout` do not reach the HTTP client's socket read timeout,
        which defaults to 30s; a cold-start seed takes ~35s, so the socket was torn down, the SDK
        retried, and the retry correctly reported "nothing to do" against data the first invocation
        had already created. Pre-existing, and invisible when run by hand against a reused
        environment — the pipeline is simply the first thing to exercise a consistently cold one.
      **Diagnostic gap found along the way:** `cloudtrail:LookupEvents` is denied under the
      `WorkloadAdministrator` permission set, so an OIDC denial cannot be diagnosed the normal way.
      The claims had to be printed from inside the workflow instead. Worth granting before the next
      piece of OIDC work.
- [x] `[Claude]` Build `mootmaker-release/release.yml` end to end. **Done 2026-09-04**, and proven
      by a complete release (`v0.0.9`) rather than by review: version computed, all three components
      tagged, built and acceptance-tested, deployed to `test`, smoke-tested, deployed to
      `production`, smoke-tested, and published as a GitHub Release. Verified against live AWS, not
      job status — production's Lambdas re-dated to 2026-09-04, `www.mootmaker.com` and
      `www.test.mootmaker.com` both serving, no stranded ephemeral resources.
      **Deviation from this entry:** the three component builds run **sequentially**, not in
      parallel. Three simultaneous `mootmaker-api` deploys (the webapp and demo-data builds each
      deploy it too) failed with published Lambda versions stuck in `Failed`/`FunctionError` against
      an account concurrency quota of 10 — see [mootmaker#41](https://github.com/geoffweatherall/mootmaker/issues/41),
      and [mootmaker-release#11](https://github.com/geoffweatherall/mootmaker-release/issues/11) for
      restoring two-way parallelism.
      **Correction to Decision 10 found while building it:** `record-outcome` publishes a failed
      attempt as a *prerelease*, so "the previous release" and "the last release that actually
      reached production" are different questions. Rollback now targets the latter
      (`--exclude-pre-releases`); targeting the former would have restored a version that never
      deployed, inverting the property Decision 10 relies on.
      Original scope, all built: `concurrency: { group: release,
      cancel-in-progress: false }` (NB confirmed 2026-09-03 — queue overlapping triggers, don't
      cancel mid-deploy); version computation, tagging, calling each component's `release-build.yml`,
      deploy-to-`test` (including the explicit demo-data seed invocation, NB-2), smoke-test-`test`,
      deploy-to-`production`, smoke-test-`production`, GitHub Release publish, rollback-on-failure;
      including the `record-outcome`
      job (Decision 5) — `if: always()`, branching on the tag-push job's own output, not on
      whether later jobs succeeded. All three of Decision 5's cases were exercised for real during
      bring-up: a success, a tagged-then-failed prerelease, and a never-tagged attempt.
- [x] `[Claude]` Build the smoke-test suites in `mootmaker-release`, including its Node/Playwright
      setup from scratch. **Done 2026-09-04.** 6 test-stage tests (real signup through the
      SES→SNS→SQS pipeline, sign in, demo-data read, meeting created, password reset with a real
      emailed code, self-deletion) and 3 strictly read-only production tests. Proven against the
      live `test` environment.
      **Two defects worth recording, both invisible to review:** the meeting read-back asserted on a
      page that renders only business hours (08:00–17:00), while the form defaults a meeting to
      *now* in the browser's timezone — so it passed at UTC+12 and failed on UTC runners, looking
      like a failed write when the write had succeeded. And `waitForVerificationCode` long-polls for
      60s inside what was a 30s test timeout, which could never have completed on a slow email.
      Both now fixed; the suite is verified under `TZ=UTC`, the condition that was failing.
- [x] `[Geoff]`/`[Claude]` Stand `test` back up and run the full pipeline against it at least once
      before it ever reaches `production`. **Done 2026-09-04.** `test` was created **by the pipeline
      itself** rather than by hand — `terraform apply` is create-or-update, and standing it up
      interactively would have broken Decision 6's mitigation ("`test`'s state changes only through
      the release pipeline") on its first day. Verified seeded against DynamoDB directly: 532
      meetings, 40 people, 10 rooms.
- [x] `[Claude]` Cut `production` over to the release pipeline as the sanctioned path.
      **Done 2026-09-04** — [mootmaker#49](https://github.com/geoffweatherall/mootmaker/pull/49)
      plus the same rule in all ten repos' `AGENTS.md`.
      **Deliberately documented rather than enforced**, which is a decision this checklist item
      did not pre-settle: `./deploy.sh production` still works. There is no gate a person holding
      production credentials cannot get around, so a block would buy the appearance of a
      guarantee rather than the guarantee; and the case for the pipeline is that it does more, not
      that the alternative was removed. What the docs now do instead is state the actual cost of a
      hand-deploy — it skips the tag, the `test` rehearsal, both smoke tests and the rollback, and
      because the pipeline *promotes* one build rather than rebuilding per environment, it is not
      even the same artifact. If that turns out to be too weak a rail, adding one is a small
      change; unwinding a rail that blocks a genuine recovery is not.
- [x] `[Claude]` Build the scheduled ephemeral sweep (unchanged from the first draft).
      **Done 2026-09-04** —
      [mootmaker-ephemeral-envs#10](https://github.com/geoffweatherall/mootmaker-ephemeral-envs/pull/10),
      `sweep-stale-envs.sh` + `.github/workflows/sweep.yml`, daily at 06:00 UTC, report-only.
      `cleanup-stale-envs.sh` stays as the interactive counterpart; neither replaces the other.
      Three independent guards keep an unattended `--destroy` off a running build: the
      `<kind>-<YYMMDD>-<rand4>` name check (which `test` and `production` cannot pass), a `.tflock`
      object under the state prefix meaning Terraform holds the lock right now, and a 12-hour
      staleness threshold — beyond GitHub's 6-hour job cap.
      **The first report, against live AWS: 0 stranded, 37 leftover state objects, 238 orphaned
      ephemeral log groups, 40 from retired `production`/`test` functions.** Two things worth
      reading out of that. Zero stranded environments means the manual cleanups during this
      build-out did hold. And [#47](https://github.com/geoffweatherall/mootmaker/issues/47) was a
      significant undercount — it found eleven orphaned groups in `production`, but the account-wide
      figure is 278, because *every ephemeral environment ever created* leaked its Lambda groups,
      not just the retired production functions. That is noise rather than spend (11.5 MB of log
      storage account-wide), but 283 of the account's 296 groups retain forever. The ongoing leak
      is already closed by step 12's change — the newest release environments no longer appear.
      **Two bugs found by running it in CI rather than trusting the local run**, both worth
      recording. `lambda:ListFunctions` was missing from the deploy role: it had been verified
      locally under an SSO admin session, not under the role CI assumes — the second time in this
      build-out that testing under different credentials than production's hid a permissions gap.
      And the run reported **green having swept nothing**, because `script | tee report.txt` gives
      the step `tee`'s exit status; `set -o pipefail` fixes that. The green-on-nothing half was the
      worse of the two, and is exactly what `docs/process/principles.md`'s "a script exiting zero
      is not evidence" warns about.
- [x] `[Claude]` Build the tagged, 120-day-retention Lambda log groups (`mootmaker-api`/
      `mootmaker-demo-data`), `mootmaker-api`'s AppSync logging (`log_config` + its own adopted,
      tagged, 120-day-retention log group + wildcard-scoped logging role), `mootmaker-release`'s own
      120-day-retention log group + `QueryDefinition`(s), and the two IAM additions to the OIDC
      deploy role (Decision 11). Remember `terraform import` for each pre-existing log group on
      `test`/`production` — independent of the rest, can proceed any time. **Done 2026-09-04**, and
      verified against live AWS rather than from Terraform's own output, which this item's
      Definition-of-done counterpart insists on:
      - the **saved query itself** — not one written for the occasion — returns **2,376 records**
        for `v0.0.12`, with `stage`, `component`, `environment` and `outcome` as separately
        filterable fields, from all eight streams the release shipped
      - **both AppSync log groups now exist at 120 days**. They did not exist at import time, which
        is itself the point: without `log_config` AppSync logs nothing at all, so a GraphQL error
        rejected before reaching a resolver left no trace anywhere
      - every Terraform-managed Lambda group reads **120** (`aws logs describe-log-groups`)
      - the imports worked: `terraform plan` against `test` and `production` shows the adopted
        groups **updated in-place, 0 to destroy** — without the import those would have been
        creations against names already taken, which is the failure this entry warns about
      **A bug this surfaced, worth recording because it is counter-intuitive:** naming a log group
      from `aws_lambda_function.*.function_name` makes the group depend on the *function*, so
      Terraform creates the function first — and SnapStart publishes a version by *executing the
      function's init*, which makes Lambda auto-create the group. Terraform's own create then fails
      with `ResourceAlreadyExistsException` **on a supposedly empty ephemeral environment**. Names
      are now derived from `resource_prefix` with `depends_on` inverting the order. The same
      SnapStart behaviour behind [#41](https://github.com/geoffweatherall/mootmaker/issues/41)
      caused this by an entirely different route.
      **The full lifecycle is now verified end to end on a genuinely fresh environment
      (2026-09-05)**, which is what makes the orphan cleanup durable rather than a one-off:
      - **On create**, an ephemeral environment's four Lambda groups *and* its AppSync group appear
        at **120 days** — Terraform-managed from the start, not auto-created with no expiry.
      - **On `terraform destroy`**, all five are **removed**. The account returned to exactly its
        14 baseline groups, with none left behind and none lacking retention.
      Both halves matter. Creation alone would still have leaked on teardown; teardown alone would
      not exist, since an auto-created group is not in state to destroy.
      **Also found, and not covered by this design:** eleven production log groups whose Lambda no
      longer exists, all retaining forever — leftovers from the per-field-resolver consolidation and
      the `sample-data-*` merge, since `terraform destroy` removes a function but not its
      auto-created group. [#47](https://github.com/geoffweatherall/mootmaker/issues/47).
- [x] `[Claude]` Build `pr-checks.yml` for `mootmaker-api`/`mootmaker-webapp`/`mootmaker-demo-data`
      (Decision 12) and enable required status checks on each — independent of the rest, can proceed
      any time. **Done 2026-09-03** —
      [mootmaker-api#17](https://github.com/geoffweatherall/mootmaker-api/pull/17) (`unit-tests`,
      138 tests), [mootmaker-demo-data#10](https://github.com/geoffweatherall/mootmaker-demo-data/pull/10)
      (`unit-tests`, 41 tests),
      [mootmaker-webapp#21](https://github.com/geoffweatherall/mootmaker-webapp/pull/21)
      (`pr-checks`; lint, `tsc -b`, 50 unit, codegen, 27 MSW-mocked Playwright). Each check was run
      locally, then confirmed green in CI, and only then required via branch protection — the
      ordering the bring-up notes above insist on, so no repo could require a context that never
      reports. `allow_auto_merge` and `delete_branch_on_merge` enabled on all three at the same time.
      **The Definition of done's deliberate-failure requirement is satisfied for all three**: a PR
      carrying a failing test was opened against each, every one reached `mergeStateStatus: BLOCKED`,
      `gh pr merge` was refused with "the base branch policy prohibits the merge" — GitHub's own
      enforcement, not a local permission gate — and each was then closed rather than merged
      (`mootmaker-api#18`, `mootmaker-demo-data#11`, `mootmaker-webapp#22`). `--admin` was offered by
      `gh` each time and deliberately not used.
      **Deviation to note:** `strict` (require branches up to date before merging) is set to `false`,
      not `true`. `true` matches this design's "`main` stays green" premise more strictly, but
      deadlocks an unattended run — when `main` moves, GitHub demands a branch update that
      auto-merge will not perform on its own. With sequential single-PR merges the practical
      difference is small. Flip it if that trade is wrong.
- [x] `[Claude]` Update the documentation named in Documentation impacts. **Done 2026-09-04** —
      [mootmaker#49](https://github.com/geoffweatherall/mootmaker/pull/49) for
      `docs/process/environments.md` (two kinds to three, with a `test` section saying which
      property is load-bearing), `docs/process/principles.md` (the retirement kept and the
      reinstatement explained, rather than reverting to pre-retirement wording),
      `docs/process/README.md` and `docs/development/environments.md`; plus one PR per repo for the
      shared rules block. **The scope was larger than this design assumed** — Documentation impacts
      names "each of the three component repos' `AGENTS.md`", but the "Environments are
      `production` or ephemeral" line is part of the *shared* project-wide rules block duplicated
      into all ten repos, so it was wrong in ten places, not three. The three deployable components
      additionally got the `release.yml`-not-`deploy.sh` bullet this section asks for.

---

## Definition of done

**Status as at 2026-09-04: every item below is met except the ephemeral sweep's trial period,
which is inherently time-based and has just started.** Evidence is recorded against each; the
Implementation checklist above carries the detail.

- ✅ `gh workflow run release.yml` (or the Actions UI equivalent) is the only way `test` or
  `production` change — no `./deploy.sh test|production` run by hand as the sanctioned path.
  Documented rather than technically enforced; see step 10 for why that was the right shape.
- ✅ A release has gone all the way through: version computed, all three components tagged, built,
  acceptance-tested, deployed to `test`, smoke-tested, deployed to `production`, smoke-tested, and
  recorded as a GitHub Release — at least once, for real. `v0.0.9` first, `v0.0.12` again with the
  logging in place. Eleven attempts preceded `v0.0.9`, each failing on a distinct genuine defect.
- ✅ A `test`-stage smoke-test failure has been deliberately exercised at least once, confirming the
  release correctly stops before `production` and leaves `test` inspectable.
- ✅ The automatic production rollback (Decision 10) has been exercised at least once, deliberately.
- ⏳ **The only item still open.** The ephemeral sweep has been running in report-only mode for its
  stated trial period with no false positives, or has graduated to automatic teardown. Built and
  running daily as of 2026-09-04; two runs so far, identical results, all three guards observed
  firing. The trial period's length was never actually stated anywhere — that, and what to do with
  the 278 orphaned log groups it found, are asked in
  [#51](https://github.com/geoffweatherall/mootmaker/issues/51).
  **The concurrency case is now observed, not just argued.** A sweep was deliberately dispatched
  while a release was mid-apply against `rel-api-260904-eb13`, and the report placed that
  environment under *"In use (Terraform holds the lock)"* — so the `.tflock` guard fired, on a real
  concurrent `terraform apply`, ahead of the staleness threshold that would also have caught it.
  That was the one piece of this design's safety argument resting on construction rather than
  evidence, and it no longer is.
- ✅ No AWS access key or long-lived AWS credential is stored anywhere in GitHub. The one accepted
  exception (the tag-push PAT, OQ-3) is documented as such, not incidental. Verified by listing
  every secret in all five repos that hold workflows: `RELEASE_TAG_PAT` in `mootmaker-release` is
  the only secret that exists anywhere.
- ✅ All three deployable components have a required, branch-protection-enforced PR check (Decision
  12) — deliberately exercised at least once each by a PR that fails it, confirming merge is
  actually blocked, not just that the check runs.
- ✅ A completed release's logs — at least one Terraform apply and one smoke-test run — are actually
  findable in CloudWatch via the saved query (Decision 11), including the relevant Lambda execution
  logs *and* AppSync's own request/resolver logs alongside them, not just theoretically wired up.
  The saved definition itself returns 2,376 records for `v0.0.12` across all eight streams.
- ✅ Every log group Decision 11 creates or adopts has its retention verified as actually set to 120
  days against live AWS (`aws logs describe-log-groups`), not just declared in Terraform and assumed.
  All five managed Lambda groups, both AppSync groups and `/mootmaker/release-pipeline` read 120.
