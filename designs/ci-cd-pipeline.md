# CI/CD pipeline

## Summary

Mootmaker has no CI and deploys to production from a developer's own machine, by hand. This design
proposes GitHub Actions for both: automated checks on every pull request, and a pipeline that
deploys to `production` on merge to `main`, replacing the local `./deploy.sh production` habit.
Both are free to run — every mootmaker repo is public, and GitHub Actions has unlimited minutes on
public repositories.

**Status:** Drafting — 2026-08-29

---

## Scope / non-goals

### In scope

- PR checks (build, unit tests, and — where meaningful — the mocked/integration layer) for every
  repository that has them, run on every pull request.
- A deploy-on-merge-to-`main` pipeline for `mootmaker-api` and `mootmaker-webapp` targeting
  `production`.
- AWS authentication for GitHub Actions via OIDC — no long-lived AWS credentials stored in GitHub,
  consistent with the project's existing no-long-lived-credentials principle.
- A rollback story for a bad deploy.
- The scheduled ephemeral-environment sweep this reorganisation's Phase 0/environments.md already
  named as a requirement handed to this design.
- Reserving, but not necessarily implementing in the first version, a step to publish the GraphQL
  schema artifact on merge — the provision `designs/project-reorganisation.md` promised to
  `graphql-schema-sharing.md`.

### Non-goals

- **Deploying `mootmaker-tools`' successor, `mootmaker-domain`, or the bootstrap repos through this
  pipeline in its first version.** `mootmaker-demo-data` could follow the same pattern once
  `mootmaker-api`/`mootmaker-webapp` prove it out; `mootmaker-domain` and the
  bootstrap repos deploy rarely enough that automating them is low value. Named as a likely fast
  follow, not built here.
- **Ephemeral-environment-per-PR.** Attractive (see NB-4 in the reorganisation design) but a real
  cost and lifecycle question of its own. **Decided 2026-08-29: deferred** — PR checks stay
  unit + mocked-integration only, with no AWS access. Revisit once the pipeline exists and there is
  real evidence about how often something reaches `main` that acceptance-on-PR would have caught.
- **Deploying `mootmaker-android`** — no code exists yet.
- **Building the GraphQL schema-sharing mechanism itself.** That's `graphql-schema-sharing.md`'s
  job; this design only reserves the pipeline step that would invoke it.
- **A staging/pre-prod environment.** The reorganisation retired `test` deliberately
  (`docs/process/environments.md`); this design does not reintroduce one.

---

## Trade-offs and decisions

### 1. Merge to `main` is the only path to production

**Decision:** once this ships, `./deploy.sh production` run by hand is retired. The only way
`production` changes is a merge to `main` triggering the pipeline.

**Reasoning:** this is the entire point of the exercise — a local deploy depends on one machine's
credentials, toolchain state, and the deployer remembering every step correctly. It has no review
gate beyond whoever's fingers are on the keyboard, and it leaves no record of *why* a given
production state exists beyond git history for the code (not the deploy). A pipeline makes "what's
in production" answerable from `main`'s HEAD, always.

**Consequence, accepted knowingly:** this makes the pipeline a single point of failure for shipping
anything. If it breaks, production is stuck until it's fixed — there's deliberately no "just deploy
by hand this once" escape hatch, because that escape hatch is exactly the thing being retired. See
Risks for how this is mitigated.

### 2. AWS authentication: OIDC, no stored credentials

**Decision:** GitHub Actions assumes an AWS IAM role via OpenID Connect (GitHub's own OIDC
provider), scoped to exactly the resources the pipeline needs to touch. No AWS access key is ever
stored as a GitHub secret.

**Reasoning:** matches the project's existing principle (`docs/process/principles.md`) that nothing
uses long-lived credentials — local development already uses SSO for exactly this reason. Storing a
static AWS key in GitHub Actions would be the one place that principle was quietly abandoned.

### 3. PR checks and deploy are separate workflows

**Decision:** a `pr-checks.yml` (or per-repo equivalent) runs on every pull request and never
touches AWS. A separate `deploy.yml` runs only on push to `main` and is the only workflow with the
OIDC role's credentials.

**Reasoning:** keeps the blast radius of a compromised or misbehaving PR check at zero — a PR from
anywhere (including, eventually, a fork, if this project ever takes outside contributions) can never
reach AWS credentials. It also means CI failing on a PR never blocks or confuses the deploy path.

### 4. Rollback: redeploy the previous commit, not `terraform destroy`

**Decision:** rolling back means re-running the deploy pipeline against the last known-good commit
on `main`, not reverting infrastructure by hand or destroying and recreating resources.

**Reasoning:** Terraform's `apply` is idempotent against a given configuration — redeploying an
older commit converges infrastructure back to what that commit describes. This is simpler and safer
than any bespoke rollback mechanism, and it reuses the exact same pipeline path being built anyway
(no separate "rollback workflow" to build and keep correct).

**What this doesn't cover:** a data migration that isn't reversible (Terraform can rebuild schema
but can't un-delete data). No mootmaker deploy currently does destructive data migrations as part of
`terraform apply` — `database-reset`/`database-repair` are separate, deliberately-invoked tools, not
part of the deploy path — so this gap is currently theoretical. Worth restating if that ever changes.

### 5. The scheduled ephemeral-environment sweep lives here

**Decision:** a scheduled GitHub Actions job (e.g. daily) implements the sweep
`docs/process/environments.md` already requires: anything matching the ephemeral naming convention
and older than 24 hours gets flagged, and — once the detection has proven itself reliable — torn
down automatically.

**Reasoning:** this was explicitly deferred here by the reorganisation design (Risks: "hand the
scheduled-sweep requirement to the CI/CD design"). It's a natural fit for a scheduled Action: no
infrastructure of its own beyond the job, and free like everything else on a public repo.

**Sequencing within this design:** report-only first (open an issue or fail a scheduled job's own
run, without deleting anything), and only move to automatic teardown after that has run cleanly for
a while — see Rollout & migration. This also depends on
[`mootmaker-test-infra#2`](https://github.com/geoffweatherall/mootmaker-test-infra/issues/2) being
fixed first: a sweep built on the current `teardown-ephemeral-env.sh` would leak in exactly the same
way that issue describes (silently leaving tool state behind while reporting success).

---

## Choices you had me make

1. **Named `mootmaker-demo-data`, `mootmaker-domain`, and the bootstrap
   repos as a deliberate non-goal for v1**, rather than trying to cover every deployable repo at
   once. Flagged as a likely fast follow rather than scoped in, to keep this design reviewable.
2. **Chose "redeploy the previous commit" as the rollback mechanism** over a more elaborate
   blue/green or canary approach, on the grounds that mootmaker's traffic and blast radius don't
   currently justify the extra complexity. Revisit if that changes.
3. **Sequenced the ephemeral sweep as report-first, not destroy-first**, even though the
   reorganisation's own Phase 0 found four leaked environments in one day — the cost of a false
   positive (destroying something someone is actively using) is worse than a day's delay in
   automating the fix.

---

## Open questions

### Blocking

**All three resolved by Geoff on 2026-08-29.** Nothing now blocks this design moving to `Ready`
once its Implementation checklist is filled in.

- [x] **OQ-1 — merge-to-`main` deploys production, with no gate.** Confirmed: the PR itself is the
  review, and `main`'s HEAD should always answer "what is in production". Decision 1 above stands as
  written — no manual promote step, no GitHub Environments approval rule, no tag-triggered release.
  The consequence named in Decision 1 is accepted knowingly: there is deliberately no by-hand escape
  hatch for production once this ships.
- [x] **OQ-2 — deferred, not adopted.** PR checks stay unit + mocked-integration only, with no AWS
  access, exactly as this design's v1 scope already assumes. Revisit once the pipeline exists and
  there is real evidence about how often something reaches `main` that acceptance-on-PR would have
  caught — a decision worth making from experience rather than in advance. NB-4 in the
  reorganisation design stays open on that basis.
- [x] **OQ-3 — a new, narrowly-scoped deploy role in the workload account** (`431071856068`),
  trusted by GitHub's OIDC provider, defined as CloudFormation in `mootmaker-bootstrap-aws-accounts`
  alongside the existing guardrails. Explicitly *not* the broad WorkloadAdministrator-equivalent
  option — least privilege wins here, accepting that a missing permission may surface mid-deploy
  during bring-up and need iterating on.

  **Practical consequence worth stating plainly:** per
  [[reference-cloudformation-stack-naming]] and that repo's own README, CloudFormation stacks there
  are applied by Geoff manually via the console as the root user in the **management** account
  (`339140804537`). Claude only ever holds workload-account credentials. So the role's CFN template
  can be written and reviewed here, but **standing it up is a `[Geoff]` step**, and the pipeline
  cannot be tested end to end until that has happened. Sequenced accordingly in Rollout & migration.

### Non-blocking

- **NB-1 — Should PR checks require passing before merge is even allowed** (branch protection), or
  stay advisory? The reorganisation deliberately left branch protection off project-wide (see
  `docs/process/branching-and-prs.md`) because there's no approval step to gate on. A required
  status check is a different, narrower kind of gate that doesn't have that problem — worth
  reconsidering once this pipeline exists.
- **NB-2 — Does the schema-publish step land in v1 of this pipeline, or wait for
  `graphql-schema-sharing.md` to actually be built?** Reserved as a step either way; whether it's a
  no-op placeholder or a real publish depends on that design's own timeline.

---

## Impacts on components

| Repository | Impact |
|---|---|
| `mootmaker-api` | Gains `.github/workflows/pr-checks.yml` (build + unit tests) and `deploy.yml` (deploy to `production` on merge to `main`) |
| `mootmaker-webapp` | Same two workflows; `pr-checks.yml` also runs the mocked-integration layer (`webapp/tests/`) |
| `mootmaker-test-infra` | Gains the scheduled sweep workflow; depends on `teardown-ephemeral-env.sh`'s completeness gap ([#2](https://github.com/geoffweatherall/mootmaker-test-infra/issues/2)) being fixed first |
| `mootmaker-bootstrap-aws-accounts` | Gains the OIDC identity provider + IAM role(s) GitHub Actions assumes |
| `mootmaker` (hub) | `docs/process/branching-and-prs.md` and `environments.md` gain a description of what CI now does; `docs/process/environments.md`'s "known gap" note about manual production deploys gets removed once this ships |

---

## Changes to the domain data model and data storage models

**N/A.** This design changes how deployment happens, not what is deployed or stored.

---

## Technical considerations

- **GitHub Actions is free with unlimited minutes on public repositories** (verified during the
  reorganisation, Decision 2) — there is no cost reason to defer this further.
- **OIDC trust policy scope matters more than it looks.** The IAM role GitHub Actions assumes should
  be scoped narrowly — ideally to exactly the resources `mootmaker-api`/`mootmaker-webapp`'s
  Terraform touches in `production`, following the same "least privilege" instinct
  `mootmaker-bootstrap-aws-accounts` already applies to human SSO access. Getting this wrong is a
  bigger blast radius than a local deploy ever had, since it's now reachable by anything that can
  open a PR against a workflow file (mitigated by requiring a maintainer's review on any change to
  `.github/workflows/deploy.yml`, once GitHub's own protections for that are configured).
- **Terraform state locking already exists** (`use_lockfile = true` in every `backend.hcl`), so
  concurrent runs — a scheduled sweep and a deploy overlapping, for instance — fail safely rather
  than corrupting state. Worth confirming this holds under Actions' own concurrency model
  specifically, not just locally.
- **The webapp's build-time environment configuration is a known blocker worth resolving first.**
  [`mootmaker-webapp#3`](https://github.com/geoffweatherall/mootmaker-webapp/issues/3) (API config
  baked in at build time rather than read at page load) means a pipeline can't currently build the
  webapp once and deploy the same artifact anywhere — it would need to rebuild per environment,
  which works for a single-target (`production`-only) pipeline but blocks the more general
  build-once-promote-anywhere shape most CD systems assume. Not blocking for this design's v1 scope
  (production only), but worth resolving before broadening this pipeline to other environments.
- **`mootmaker-webapp/webapp` and the repo root have separate `package.json` files** — a documented
  trap (`docs/development/getting-started.md`) that a CI workflow must get right (`npm install` in
  both places) or it will fail in a way that looks unrelated to the actual cause.

---

## Testing impacts

- **PR checks are new test infrastructure**, not a change to existing test layers — they run the
  same unit/mocked-integration suites that already exist, just automatically.
- **The acceptance/e2e layers (real deployment required) are not run on every PR** — settled by
  OQ-2, not merely pending. They stay a deliberate, human-triggered step against an ephemeral
  environment. If ephemeral-per-PR is adopted later, this section needs revisiting.
- **The deploy pipeline itself needs its own smoke test** — a minimal post-deploy check (e.g. the
  home page returns 200) before considering a deploy successful, distinct from the full acceptance
  suite.

---

## Documentation impacts

- `docs/process/branching-and-prs.md` — describe what PR checks actually run, once built.
- `docs/process/environments.md` — remove the "currently a local `./deploy.sh production`" known-gap
  note once the pipeline replaces it.
- Each repo's `AGENTS.md`/`README.md` — note that production deploys happen via merge to `main`, not
  by running `deploy.sh production` locally, once this ships (that script likely keeps working for
  ephemeral environments, just not for `production`).

---

## Rollout & migration

1. **`[Claude]`** Write the CloudFormation for the OIDC provider and the narrow deploy role
   (OQ-3), in `mootmaker-bootstrap-aws-accounts`, following that repo's stack-name-matches-filename
   convention.
2. **`[Geoff]`** Apply that stack manually via the CloudFormation console as root in the management
   account — Claude holds workload-account credentials only and cannot do this step. **Everything
   downstream is blocked until this lands**, so it is worth doing early rather than at the point of
   first use.
3. Build and merge `pr-checks.yml` for `mootmaker-api` and `mootmaker-webapp` — lowest risk, no AWS
   access at all, and **not blocked on step 2**, so it can proceed in parallel.
4. Build `deploy.yml`, test it thoroughly against an ephemeral environment (pointing the same
   workflow at a non-production target) before ever pointing it at `production`. Expect to iterate
   on the role's permissions here — a deliberately narrow policy (OQ-3) will surface missing
   permissions during bring-up, and each one is a CFN change needing another `[Geoff]` console
   apply. That friction is the accepted cost of least privilege, not a sign the approach is wrong.
5. Cut over: retire local `./deploy.sh production` as the sanctioned path once `deploy.yml` has a
   proven track record — a handful of successful ephemeral-environment runs at minimum before the
   first real production deploy through the pipeline.
6. Ephemeral sweep: report-only first, automatic teardown only after that's run cleanly for a
   stated period (a week is a reasonable starting bar, adjustable once there's real data).

No data migration — this changes deployment mechanics only.

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **The pipeline breaks and there's no manual escape hatch**, per Decision 1. | Medium | Keep `deploy.sh` scripts working for ephemeral environments (already true) so the mechanics can always be debugged and verified outside the pipeline, even though `production` itself only moves through Actions. |
| **An over-broad OIDC role scope** turns "anyone who can open a PR touching a workflow file" into a bigger blast radius than local deploys ever had. | High | Scope the IAM role narrowly (Technical considerations); require review on workflow-file changes once GitHub's protections for that are configured. |
| **Automatic ephemeral-environment teardown deletes something someone is actively using.** | Medium | Report-only phase before any automatic deletion (Decision 5, Rollout step 5); fix the known teardown-completeness gap first. |
| **A scheduled sweep and a deploy race on Terraform state.** | Low | State locking already exists (Technical considerations); verify it holds under Actions specifically before relying on it. |

---

## Implementation checklist

All three blocking questions are answered (see Open questions), so this is now filled in properly.
Status stays `Drafting` until Geoff promotes it — a design does not self-promote to `Ready`.

- [x] `[Geoff]` Resolve OQ-1, OQ-2, OQ-3. **Done 2026-08-29.**
- [ ] `[Claude]` Write the OIDC provider + narrow deploy-role CloudFormation in
      `mootmaker-bootstrap-aws-accounts`.
- [ ] `[Geoff]` Apply that stack via the CloudFormation console as root in the management account —
      not something Claude can do. Blocks `deploy.yml` bring-up (but not `pr-checks.yml`).
- [ ] `[Claude]` Build and merge `pr-checks.yml` for `mootmaker-api` and `mootmaker-webapp`.
- [ ] `[Claude]` Build `deploy.yml`; prove it against an ephemeral environment before production.
- [ ] `[Claude]` Cut production over; retire local `./deploy.sh production` as the sanctioned path.
- [ ] `[Claude]` Build the scheduled ephemeral sweep, report-only first (depends on
      `mootmaker-test-infra#2` being fixed).
- [ ] `[Claude]` Move to automatic sweep teardown once report-only has run cleanly for a stated
      period.
- [ ] `[Claude]` Update the documentation named in Documentation impacts.

---

## Definition of done

- PR checks run automatically on every PR to `mootmaker-api` and `mootmaker-webapp`, with no AWS
  access.
- A merge to `main` in either repo deploys to `production` with no human running a script by hand.
- A rollback (redeploying a previous commit) has been exercised at least once, deliberately, to
  prove the mechanism works before it's ever needed for real.
- The ephemeral sweep has been running in report-only mode for its stated trial period with no false
  positives, or has graduated to automatic teardown.
- No AWS access key is stored anywhere in GitHub.
