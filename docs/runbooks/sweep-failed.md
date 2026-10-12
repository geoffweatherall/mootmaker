# Sweep failed

The daily `sweep.yml` run in mootmaker-ephemeral-envs went red (GitHub emails the failure). The sweep does
three things, and any of them can fail it:

1. Destroys ephemeral environments idle for 48 hours that are not kept.
2. Deletes log groups whose Lambda or AppSync API no longer exists.
3. Runs `check-accumulation.sh` from mootmaker-bootstrap-aws-accounts, which fails if anything is growing
   with time rather than use.

```bash
gh run list -R geoffweatherall/mootmaker-ephemeral-envs -w sweep.yml --limit 3
gh run view <run-id> -R geoffweatherall/mootmaker-ephemeral-envs --log-failed | tail -80
```

Each run's report is also kept as an artifact for 90 days.

## The accumulation check failed

```bash
mootmaker-bootstrap-aws-accounts/check-accumulation.sh
```

| It says | Cause | Fix |
|---|---|---|
| A log group has no retention | Something created a log group outside Terraform (a hand-made Lambda, a new service) | Set retention: `aws logs put-retention-policy --log-group-name <name> --retention-in-days 120`, and bring whatever created it under Terraform |
| A Lambda has more than four published versions | `prune-lambda-versions.sh` did not run after a deploy (it runs at the end of mootmaker-api's `deploy.sh`) | Run `mootmaker-api/deploy/prune-lambda-versions.sh <env>` |
| history-cleanup has stopped advancing | The weekly job is failing or its rule is disabled | `aws logs tail /aws/lambda/<env>-mootmaker-history-cleanup --since 14d`; `aws events describe-rule --name <env>-mootmaker-history-cleanup` |

## A teardown failed

The sweep tried to destroy an environment and could not. See
[ephemeral environment problems](ephemeral-environment-problems.md#teardown-failed-or-stuck). A teardown
blocked by a state lock is normal while a release or a person is deploying that environment; the next
day's sweep tries again.

## The run could not reach AWS

`Could not assume role` or `Not authorized to perform sts:AssumeRoleWithWebIdentity` means the OIDC trust
for mootmaker-ephemeral-envs at `main` is broken: the deploy-role stack was changed, or the repository was
recreated with a new id. See [AWS access problems](aws-access-problems.md#github-actions-cannot-assume-the-role).
