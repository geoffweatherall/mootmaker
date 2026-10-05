# PR-time smoke verification

## Summary

Run mootmaker-release's smoke-test suite against a real deployed environment as part of
mootmaker-webapp's pull request checks, so a UI change that breaks it is caught at PR review time
instead of during an actual release. Prompted by a 2026-09-20 mootmaker release in which a webapp
redesign PR merged cleanly through `pr-checks.yml` but then broke `mootmaker-release`'s smoke suite
twice during the release itself, requiring two extra release attempts to fix.

## Status

**Drafting** — 2026-10-05. Both blocking questions answered by Geoff on 2026-10-05 (see "Trade-offs
and decisions"); left at Drafting for Geoff to re-read before moving it to Ready.

## Scope / non-goals

In scope: mootmaker-webapp pull requests trigger a deploy of that PR's built `webapp/dist` (plus
`mootmaker-api`'s current `main`) to a fresh ephemeral environment, then run
`mootmaker-release`'s `smoke/tests/test-stage.spec.ts` against it, then tear the environment down —
regardless of outcome.

Not in scope, deliberately deferred rather than rejected (see "Open questions"):

- Extending the same mechanism to `mootmaker-api` or `mootmaker-demo-data` pull requests. The
  2026-09-20 release's smoke-suite failures were both caused by webapp changes; the release also hit
  a `demo-data` acceptance-suite failure, but that was `demo-data`'s **own** verify suite (already
  runs at release time regardless) and looked probabilistic, not something PR-time smoke
  verification would touch.
- Running mootmaker-webapp's own `acceptance/` suite in this same PR-time ephemeral deploy. That
  suite already exists, already deploys to a real environment, and already would have caught one of
  the two smoke failures (it needed the identical collapsed-card fix independently) — but it
  currently runs only in `release-build.yml`, at release time, same as the smoke suite. Whether to
  also move it earlier is a related but separate decision, raised in discussion and left open here
  rather than bundled in.
- A general framework for any repo's tests to run against any other repo's PR. This doc is one
  direction only: mootmaker-webapp PR → mootmaker-release's smoke suite.

## Trade-offs and decisions

- **Reuse `release-build.yml`'s existing deploy mechanics** (`deploy.sh` for `mootmaker-api` then
  for webapp with `--skip-build`, teardown via `undeploy.sh --yes` in an `if: always()` step, the
  `rel-web-<date>-<rand>`-style naming `cleanup-stale-envs.sh` already recognises) rather than
  inventing a new deploy path. It is already proven in CI, already OIDC-wired to the release
  account's deploy role, and already handles the case of a hung run needing to still tear down.
- **Trigger direction: mootmaker-webapp's own PR workflow checks out `mootmaker-release` as a
  sibling and runs its smoke suite directly**, rather than webapp firing a `repository_dispatch`
  that a workflow in `mootmaker-release` listens for. This mirrors the sibling-checkout convention
  `release-build.yml` already uses for `mootmaker-api`/`mootmaker-ephemeral-envs`/
  `mootmaker-email-testing`, and keeps the trigger, the deploy, and the pass/fail result in one
  workflow run rather than splitting state across two workflows connected only by an
  eventually-consistent webhook. Not confirmed with Geoff — see "Choices you had me make".
- **A required, merge-blocking check, not advisory** (decided by Geoff, 2026-10-05). The failure it
  exists to catch is a webapp PR that merged green and then broke the release. An advisory check
  can be merged past, which is exactly how that happened. Flakiness is a real cost of a required
  gate, and the answer to it is fixing the flaky test, as with mootmaker-webapp#119, rather than
  making the check optional.
- **The ephemeral environment deploys `mootmaker-api` from `main`** (decided by Geoff, 2026-10-05),
  the same as `release-build.yml`. A release takes everything on `main`, so that is the API the
  webapp change will actually ship with; the latest release tag would miss API changes merged but
  not yet released. The workflow should print the API commit it deployed, since a webapp reviewer
  has no other way to know.
- **Cost is treated as acceptable but called out explicitly, not assumed silently.** An ephemeral
  deploy-and-teardown per PR push is real AWS spend and several minutes of wall time on top of
  `pr-checks.yml`'s current zero-AWS gate. Ephemeral environments are already established as cheap
  enough to create/tear down without per-instance approval; this is a new *recurring* cost (one per
  PR push, potentially several per PR) rather than a one-off, which is the reason it's named here
  rather than folded silently into "ephemeral envs are cheap."

## Choices you had me make

- The trigger direction above (webapp's workflow owns this, via sibling checkout, versus
  mootmaker-release owning it via `repository_dispatch`). Flag to override if the opposite
  direction is actually preferred — e.g. mootmaker-release owning it would let `mootmaker-api` and
  `mootmaker-demo-data` reuse the same dispatched workflow later without duplicating the trigger
  into three repos, if the deferred extension in "Scope" above is later taken up.

## Open questions

Blocking: none. Both were answered on 2026-10-05 and are recorded under "Trade-offs and decisions":
a required gate, deploying `mootmaker-api` from `main`.

Non-blocking:

- Whether to later extend this to `mootmaker-api`/`mootmaker-demo-data` PRs, and/or to also run
  webapp's own `acceptance/` suite in the same PR-time deploy — both raised in the 2026-09-20
  discussion that produced this doc, both deferred rather than decided.
- The two repos' test suites duplicate some of the same locator/journey assumptions (the identical
  "expand the collapsed card before asserting" fix was needed independently in both webapp's
  `acceptance/tests/add-meeting.spec.ts` and mootmaker-release's `smoke/tests/test-stage.spec.ts`
  during the same release). Whether that duplication is worth extracting into a shared helper is a
  related question, also raised and deferred.

## Impacts on components

- **mootmaker-webapp**: new (or extended) GitHub Actions workflow — deploys the PR's built bundle
  plus `mootmaker-api`'s `main` into a fresh ephemeral environment, checks out `mootmaker-release`
  as a sibling, runs its `smoke-test-test` suite, tears the environment down in an `if: always()`
  step.
- **mootmaker-release**: no code change required under the chosen trigger direction — its smoke
  suite is consumed as-is by webapp's workflow. Would change if the `repository_dispatch` direction
  were chosen instead (see "Choices you had me make").

## Changes to the domain data model and data storage models

N/A — no persisted-state changes, purely CI/CD.

## Technical considerations

- Reuse `cleanup-stale-envs.sh`'s naming convention for the ephemeral environment (as
  `release-build.yml` already does with its `rel-web-…` prefix) so a run that dies before teardown
  is still swept by the scheduled sweep rather than stranded.
- Leaves behind nothing beyond the ephemeral environment's own lifetime (torn down in an
  `if: always()` step); on-failure diagnostics (Playwright trace/error-context) should follow
  `release-build.yml`'s existing 30-day artifact retention precedent rather than a new policy.

- **The release deploy role cannot be assumed from a pull request today** (found 2026-10-05).
  `mootmaker-release-github-actions-deploy`'s trust policy (mootmaker-bootstrap-aws-accounts,
  `workload-account/github-actions-deploy-role.yaml`) accepts mootmaker-webapp only for
  `ref:refs/tags/v*`. A `pull_request` workflow presents the OIDC subject
  `repo:geoffweatherall/mootmaker-webapp:pull_request`, so building this needs a trust-policy
  change: either that subject on the existing role, or a narrower role of its own. It must not
  extend to pull requests from forks. GitHub withholds OIDC tokens from fork PRs by default, and
  that default is what keeps a stranger's PR from deploying into this account.

## Testing impacts

This doc's entire purpose is a testing-process change; no separate impact beyond itself.

## Documentation impacts

`mootmaker-webapp/CLAUDE.md` and `pr-checks.yml`'s own header comment (which currently states the
acceptance/e2e suites deliberately don't run there) need updating once implemented, to describe the
new check and where it lives.

## Rollout & migration

N/A — new CI workflow, no migration of existing state.

## Risks

- **Cross-repo CI coupling.** A change to `mootmaker-release`'s smoke suite (its structure,
  dependencies, or the sibling checkouts it itself expects) could break webapp's PR gate without an
  obviously-related diff in the webapp PR under review, which may confuse a webapp-only
  contributor. Mitigate with a clearly-named job/step pointing at `mootmaker-release` as the source.
- **AWS spend and wall-clock time grow with PR push frequency** — see the cost trade-off above.

## Definition of done

N/A at Drafting — to be filled in once the blocking open questions above are resolved and this
moves to Ready.
