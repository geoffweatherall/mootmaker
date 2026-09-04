# Environments

**There are three kinds: `production`, `test`, and ephemeral.**

`test` was retired on 2026-08-29 and brought back on 2026-09-03 — for a different reason than it
existed for the first time, which is why this is not simply an undo. See
[`../../designs/ci-cd-pipeline.md`](../../designs/ci-cd-pipeline.md) Decision 6.

## production

The public demo at [www.mootmaker.com](https://www.mootmaker.com). The only long-lived environment.

It is a demo, not a business: sign-in details for a shared account are published on the home page,
the password policy is deliberately loose, and the data is disposable — `mootmaker-demo-data` refills
it weekly on a schedule. Shipping something imperfect here is cheap, which is the point.

It is still the thing a prospective employer will look at, so it should work.

## test

A full copy of the stack that the release pipeline deploys to **before** `production`, so a release
that is going to fail fails somewhere nobody is looking.

The first `test` environment was a place to poke at things by hand between releases, and it drifted
into a second production nobody maintained — which is what got it retired. This one is different in
the way that matters: **its state changes only through the release pipeline**, exactly like
`production`'s. No `./deploy.sh test` by hand as a sanctioned path, no ad hoc interactive use —
ephemeral environments exist for that. `mootmaker-demo-data` seeds it the same way it seeds
`production`, so its data shape cannot silently drift from what the smoke tests expect.

Two consequences worth knowing before you meet them:

- **It is never reset from scratch**, on a schedule or otherwise. State accumulates release after
  release, indefinitely, the same as `production`. That is the whole point: `test` is valuable
  precisely because its state history looks like `production`'s. Resetting it periodically would
  hand it back the "always a fresh create" character of an ephemeral environment, which is what it
  exists *not* to have.
- **A failed smoke test leaves `test` broken, and the next release's deploy to it will fail** until
  someone fixes it. That is deliberate, not a bug. A broken `test` is a diagnostic asset — the
  alternative is finding out in `production`.

The sweep (below) will not touch it: `test` cannot match the ephemeral name pattern, and the
teardown script refuses anything that does not.

## Ephemeral environments

Created for a specific piece of work and destroyed when that work is done. A complete, isolated copy
of the stack — its own Lambdas, DynamoDB tables, Cognito pool, S3 bucket, CloudFront distribution
and AppSync API — created by `mootmaker-ephemeral-envs/create-ephemeral-env.sh`.

### Naming

`<kind>-<YYMMDD>-<rand4>`, e.g. `claude-260829-x7q2`. The teardown script enforces this shape as a
hard safety rail: it refuses any name that does not match, so a typo can never reach `production`.

| Kind | For |
|---|---|
| `claude` | An AI session's working environment |
| `e2e`, `web-e2e`, `web-acc` | An automated test run |
| `<name>` | A person's own manual testing, e.g. `geoff-260829-a1b2` |

### Tearing them down

**Tearing down your environment is part of finishing the work, not a tidy-up afterwards.**

An environment left running contradicts the scale-to-zero principle directly and costs real money.
This is not hypothetical: on 2026-08-28 four ephemeral environments leaked from a single session and
were found the next day still running — 10 Lambdas and 16 DynamoDB tables between them, plus each
one's Cognito pool, S3 bucket, CloudFront distribution and AppSync API.

**Maximum lifetime: 24 hours.** Anything older than that is a leak and should be destroyed, whether
or not anyone remembers what it was for.

A scheduled sweep now backs that up —
[`mootmaker-ephemeral-envs/.github/workflows/sweep.yml`](https://github.com/geoffweatherall/mootmaker-ephemeral-envs/blob/main/.github/workflows/sweep.yml),
daily at 06:00 UTC. It **reports and changes nothing** until it has run clean for a trial period;
graduating it to automatic teardown is a flag. It will not touch an environment Terraform holds a
lock on, or one written to in the last 12 hours, so a running build is safe from it.

```bash
mootmaker-ephemeral-envs/create-ephemeral-env.sh claude [--with-demo-data]
mootmaker-ephemeral-envs/teardown-ephemeral-env.sh <name>
mootmaker-ephemeral-envs/cleanup-stale-envs.sh          # interactive: asks about each one
mootmaker-ephemeral-envs/sweep-stale-envs.sh            # what the schedule runs; report-only
```

`sweep-stale-envs.sh` also finds two kinds of debris a teardown leaves behind even when it
succeeds. `terraform destroy` empties a state file without deleting the S3 object, and it removes a
Lambda without removing the log group Lambda auto-created for it — so both accumulate silently.

`--with-demo-data` also deploys `mootmaker-demo-data` and seeds the environment with it. It is
opt-in here and always-on in `production`: demo is a core part of MootMaker, but most ephemeral work
does not need ~500 generated meetings. Teardown needs no matching flag — it discovers what is there.

`teardown-ephemeral-env.sh` **discovers** what is deployed by listing the environment's own state
prefix in S3, rather than assuming a fixed set of components, and asserts at the end that the prefix
is empty. A component it does not recognise stops it, loudly, rather than being silently skipped —
carrying on would delete the state it does know about while leaving real infrastructure running with
nothing tracking it. (Until 2026-09-02 it knew only about `mootmaker-webapp` and `mootmaker-api`, so
an environment with demo tooling deployed was not fully torn down by the script named "tear down
this environment", and said so nowhere.)

After any teardown, verify against live AWS rather than trusting the script's exit code:

```bash
aws lambda list-functions   --query "length(Functions[?starts_with(FunctionName,'<name>-')])"
aws dynamodb list-tables    --query "length(TableNames[?starts_with(@,'<name>-')])"
aws s3 ls s3://remote-state-<account-id>/          # the environment prefix should be gone
```

## How it works mechanically

Environments are just a name passed to each repository's scripts — there is no registry, and any
name works. Each gets its own Terraform state key and its own uniquely-prefixed AWS resources, so
environments never collide.

For the mechanics — resource prefixing, per-environment state keys, `TF_DATA_DIR` isolation, and
the full stand-up/tear-down walkthrough — see
[`../development/environments.md`](../development/environments.md).

## Deploying to test and production

**`gh workflow run release.yml` in
[mootmaker-release](https://github.com/geoffweatherall/mootmaker-release) is the only sanctioned way
either changes.** One release builds all three components once, tags them, deploys to `test`, smoke
tests it, deploys to `production`, smoke tests that, and publishes a GitHub Release — rolling
`production` back automatically if its smoke test fails.

`./deploy.sh <name>` still works and is still the right tool for an ephemeral environment. What it
is no longer is the way `test` or `production` get updated. Running it against either by hand
bypasses the tag, the `test` rehearsal, the smoke tests and the rollback, and leaves the deployed
artifact untraceable to any release — the pipeline promotes one build through both environments
rather than rebuilding, so a hand-deploy is not even the same binary.

It is deliberately not blocked. There is no gate a person with production credentials cannot get
around anyway, and the honest case for using the pipeline is that it does more, not that the
alternative was taken away. If a deploy by hand is ever genuinely needed — recovering from a broken
pipeline, say — that is a considered exception, not the normal path.

See [`../../designs/ci-cd-pipeline.md`](../../designs/ci-cd-pipeline.md).
