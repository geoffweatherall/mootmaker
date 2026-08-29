# Environments

**There are exactly two kinds: `production`, and ephemeral. Nothing else is long-lived.**

This replaced an earlier model that also had a standing `test` environment, retired on 2026-08-29.

## production

The public demo at [www.mootmaker.com](https://www.mootmaker.com). The only long-lived environment.

It is a demo, not a business: sign-in details for a shared account are published on the home page,
the password policy is deliberately loose, and the data is disposable — `sample-data-topup` refills
it weekly on a schedule. Shipping something imperfect here is cheap, which is the point.

It is still the thing a prospective employer will look at, so it should work.

## Ephemeral environments

Created for a specific piece of work and destroyed when that work is done. A complete, isolated copy
of the stack — its own Lambdas, DynamoDB tables, Cognito pool, S3 bucket, CloudFront distribution
and AppSync API — created by `mootmaker-test-infra/create-ephemeral-env.sh`.

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
or not anyone remembers what it was for. Nothing enforces this yet; a scheduled sweep is a stated
requirement handed to the CI/CD design.

```bash
mootmaker-test-infra/teardown-ephemeral-env.sh <name>
mootmaker-test-infra/cleanup-stale-envs.sh          # find what has been left behind
```

**Known gap — `teardown-ephemeral-env.sh` does not tear down everything.** It undeploys
`mootmaker-webapp` and `mootmaker-api` only, and deliberately removes only those two state objects.
Its caution is correct: deleting a state object it did not itself destroy would orphan live
infrastructure with nothing tracking it. But the consequence is that **an environment with tools
deployed is not fully torn down by the script named "tear down this environment"** — the tools must
be undeployed separately first, and their emptied state objects removed by hand. Tracked as an issue
in `mootmaker-test-infra`.

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

## Deployment to production

Currently a local `./deploy.sh production` from a developer's machine. This is a known weak point:
it depends on one machine's credentials and toolchain, and has no gate beyond the person running it.

Moving production deployment into a pipeline — merge to `main` being the only path to production —
is designed but not built. See `../../designs/ci-cd-pipeline.md`.
