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
  repository that has them, run on every pull request. Unchanged from the first draft.
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
fine-grained PAT, reviewed and rotated periodically, is the pragmatic choice. Flagged in Open
questions in case that trade-off doesn't hold up.

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

**Where this code lives — open, see Open questions:** most likely a new `smoke/` directory in
`mootmaker-webapp` (it already owns `acceptance/` and the Playwright tooling this would reuse), but
this spans all three components conceptually and a case could be made for `mootmaker-ephemeral-envs`
instead.

### 10. Rollback: redeploy the previous version; attempt it automatically on a failed production smoke test

**Decision:** unchanged from the first draft in mechanism — rolling back means re-running the deploy
step against the previous release's tag, not `terraform destroy` or a bespoke rollback path. New:
if the **production** smoke test fails, the pipeline **automatically** redeploys the previous
version's artifacts to `production` and re-runs the production smoke test against that, rather than
leaving a known-bad `production` up while waiting for a human.

**Reasoning:** `test` passing and `production` still failing implies something environment-specific
to `production` (data shape, a config difference, a race) rather than a code defect `test` should
have caught — which is exactly the scenario an automatic revert is safe for, since the previous
version is known-good by construction (it was itself a release that reached `production`). Left as
an open question below whether "automatic" is actually the right call versus pausing for a human —
recorded as a decision here because a design needs *a* default, not because the trade-off is
one-sided.

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
4. **Automatic rollback on a failed production smoke test** (Decision 10), rather than pausing for a
   human to decide. Named as the more debatable of the two failure-handling defaults — see Open
   questions.

---

## Open questions

### Blocking

- [ ] **OQ-1 — Where does the smoke-test code live?** `mootmaker-webapp/smoke/` (reuses existing
  Playwright + SES test-infra tooling) is the working assumption in Decision 9, but this is
  genuinely cross-component and `mootmaker-ephemeral-envs` is a defensible alternative home. Needs a
  choice before Implementation checklist can be filled in properly.
- [ ] **OQ-2 — Is automatic rollback on a failed production smoke test actually wanted**, or should
  the pipeline instead stop and page/notify, leaving `production` in its failed state until a human
  decides? Decision 10 assumes automatic; this is the more consequential of the two failure defaults
  and deserves an explicit answer rather than inheriting the default by not objecting to it.
- [ ] **OQ-3 — Fine-grained PAT vs. a GitHub App** for the cross-repo tag push in Decision 3. PAT is
  simpler to set up for a solo project; a GitHub App installation token is shorter-lived and scoped
  by permission rather than by the token-holder's own access, which is a better match for "no
  long-lived credentials" but meaningfully more setup. Needs a decision before Rollout step 1.
- [ ] **OQ-4 — The OIDC deploy role's CloudFormation (from the first draft's OQ-3) still needs
  writing and a `[Geoff]` manual apply**, now scoped to three deploy targets instead of one
  (per-release ephemeral, `test`, `production`) plus `mootmaker-demo-data`'s own resources. Not a new
  question, but the scope changed enough to re-flag as blocking rather than assume the first draft's
  version still applies unmodified.

### Non-blocking

- **NB-1 — Should `test`'s Terraform state ever be reset from scratch** (rather than left to
  accumulate release after release, same as `production`), and on what trigger, if ever? Currently
  no plan to — `production` never gets this either — but worth a deliberate "no" rather than silence.
- **NB-2 — Does demo-data need an explicit one-off seed invocation after deploying to `test`**, or is
  waiting for its own weekly schedule acceptable? The smoke test's "view some data" step needs
  *something* to be there; see Technical considerations.
- **NB-3 — Should branch protection require PR checks to pass before merge**, carried over unresolved
  from the first draft (NB-1 there). Still not reconsidered.
- **NB-4 — Does the schema-publish step (now already live in `mootmaker-api`) need any coordination
  with the release version**, e.g. tagging the published schema artifact with the same release
  version? Not addressed here; worth a look once this pipeline exists.

---

## Impacts on components

| Repository | Impact |
|---|---|
| `mootmaker` (hub) | No `release.yml` here (Decision 1, revised) — impact is docs-only. `docs/process/principles.md`'s "`test` was retired... could not justify its standing cost" line needs rewriting to reflect Decision 6's reasoning, not deleting the history but adding the reversal and why. `docs/process/environments.md`'s "exactly two kinds" becomes three. |
| `mootmaker-release` (new repo) | Gains `release.yml` (the orchestrator, `workflow_dispatch`-triggered), the PAT secret (OQ-3), the cross-component smoke-test suites (OQ-1, tentatively), and publishes the GitHub Release (Decision 5). Scaffolded 2026-09-03; `release.yml` itself not yet built. |
| `mootmaker-api` | Gains a reusable `release-build.yml` (`on: workflow_call`) doing build + unit test + acceptance-against-fresh-ephemeral + artifact upload, called by `mootmaker-release`'s `release.yml` per release. |
| `mootmaker-webapp` | Same shape as `mootmaker-api`. Also: `mootmaker-webapp#3` — fixed 2026-09-03 (PR [#17](https://github.com/geoffweatherall/mootmaker-webapp/pull/17), not yet merged), unblocking Decision 8. Possibly gains `smoke/` (OQ-1). |
| `mootmaker-demo-data` | Same shape as the other two — first time it's included in an automated pipeline. |
| `mootmaker-ephemeral-envs` (renamed from `mootmaker-test-infra` 2026-09-03) | `create-ephemeral-env.sh`/`teardown-ephemeral-env.sh` unchanged in mechanism; docs updated to describe `test` as a second protected, standing name (the scripts already treat it as one, per Decision 6). |
| `mootmaker-email-testing` (split from `mootmaker-test-infra` 2026-09-03) | No direct pipeline changes — the standing `test` environment's smoke test reads from its persistent SQS queue the same way `mootmaker-webapp`'s existing `e2e`/`acceptance` suites already do. |
| `mootmaker-bootstrap-aws-accounts` | Gains the OIDC identity provider + deploy role (OQ-4), scoped to three deploy targets. |

---

## Changes to the domain data model and data storage models

**N/A.** This design changes how deployment and release happen, not what is deployed or stored.

---

## Technical considerations

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
- **PR checks are unchanged** from the first draft — unit + mocked-integration only, no AWS access,
  still deliberately not full acceptance-on-PR (OQ-2 in the first draft, not reopened here).

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
   build-once-promote means anything for the webapp.
2. **`[Geoff]`** Resolve OQ-1 through OQ-4.
3. **`[Claude]`** Write the OIDC provider + deploy role CloudFormation in
   `mootmaker-bootstrap-aws-accounts`, scoped to the three deploy targets (OQ-4).
4. **`[Geoff]`** Apply that stack via the CloudFormation console as root in the management account —
   not something Claude can do. Blocks any real deploy stage, not PR checks.
5. **`[Claude/Geoff, per OQ-3]`** Create the PAT (or GitHub App) and store it as a `mootmaker`
   Actions secret.
6. **`[Claude]`** Build each component's `release-build.yml` (reusable, build + unit + acceptance +
   artifact upload) and prove each one standalone before wiring up the orchestrator.
7. **`[Claude]`** Build `mootmaker-release/release.yml`: version computation, tagging, calling each
   component's `release-build.yml`, deploy-to-`test`, smoke-test-`test`, deploy-to-`production`,
   smoke-test-`production`, GitHub Release publish, rollback-on-failure.
8. **`[Claude]`** Build the smoke-test suites (OQ-1's location).
9. **`[Geoff]` + `[Claude]`** Stand up `test` as a real environment for the first time under this
   design (it does not currently exist — it was fully torn down 2026-08-29) and run the pipeline
   against it end to end at least once before it touches `production`.
10. **`[Claude]`** Cut over: retire `./deploy.sh production` run by hand as the sanctioned path for
    `production`, same as the first draft's plan, now via `release.yml` instead of merge-to-`main`.
11. **`[Claude]`** Ephemeral sweep (unchanged from the first draft): report-only first, automatic
    teardown only after a clean trial period. Independent of the rest of this rollout and can proceed
    in parallel.

No data migration beyond standing `test` back up from nothing.

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **`test` drifts from `production`'s shape over time** (the exact failure mode that got it retired once already). | Medium | `test`'s state changes only through the release pipeline, same as `production`'s; demo-data seeds it the same way (NB-2 pending); no ad hoc interactive use — ephemeral environments exist for that. |
| **A failed `test`-stage smoke test leaves `test` broken, blocking the next release's deploy-to-`test` step** until fixed by hand. | Medium, accepted knowingly | This is Decision 6a's entire point — the alternative is finding out in `production`. Named here so it isn't mistaken for a bug later. |
| **PAT compromise** (Decision 3) reaches four repos with write access. | Medium | Scope strictly to `contents: write`, nothing broader; review OQ-3 (GitHub App may be worth the extra setup after all). |
| **Automatic production rollback (Decision 10) masks a data-shape problem** that a redeploy of old code doesn't actually fix, giving false confidence that "rollback succeeded." | Medium | OQ-2 — worth deciding whether automatic is right before building it, not after. |
| **Over-broad OIDC role scope**, carried over from the first draft, now covering three deploy targets instead of one. | High | Same mitigation as before: least privilege, reviewed CFN, expect iteration during bring-up. |
| **A scheduled ephemeral sweep and a release race on Terraform state.** | Low | State locking already exists; unchanged from the first draft. |

---

## Implementation checklist

Not filled in with the same confidence as the first draft's was — several blocking Open questions
above are new and unresolved as of 2026-09-03. Status stays `Drafting`.

- [ ] `[Geoff]` Resolve OQ-1 through OQ-4.
- [ ] `[Claude]` Fix `mootmaker-webapp#3`.
- [ ] `[Claude]` Write the OIDC provider + deploy role CloudFormation (scoped to three targets).
- [ ] `[Geoff]` Apply that stack via the CloudFormation console.
- [ ] `[Claude/Geoff]` Create and store the cross-repo tag-push credential (OQ-3).
- [ ] `[Claude]` Build each component's `release-build.yml`.
- [ ] `[Claude]` Build `mootmaker-release/release.yml` end to end.
- [ ] `[Claude]` Build the smoke-test suites.
- [ ] `[Geoff]`/`[Claude]` Stand `test` back up and run the full pipeline against it at least once
      before it ever reaches `production`.
- [ ] `[Claude]` Cut `production` over to the release pipeline as the sanctioned path.
- [ ] `[Claude]` Build the scheduled ephemeral sweep (unchanged from the first draft).
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
- A production rollback (whichever OQ-2 resolves to) has been exercised at least once, deliberately.
- The ephemeral sweep has been running in report-only mode for its stated trial period with no false
  positives, or has graduated to automatic teardown.
- No AWS access key or long-lived AWS credential is stored anywhere in GitHub. The one accepted
  exception (the tag-push PAT, OQ-3) is documented as such, not incidental.
