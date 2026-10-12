# Reset an environment

Start an environment's data again from scratch: after the demo has been vandalised, when test data has
got into a confusing state, or before a test run that needs a clean slate. What a reset deletes is in
[data](../overview/data.md#resetting-and-repairing-an-environment).

## What it does

| | Outside `production` | In `production` |
|---|---|---|
| Rooms and meetings | All deleted | All deleted |
| Cognito accounts | All deleted except `demo@mootmaker.com` and the test fixture users | **Untouched** |
| People | Only those linked to a surviving account are kept | Every Person linked to any account is kept; guests are deleted |
| Avatars | Kept for surviving people only | Same |
| Test fixture users | Recreated or repaired to their known state | n/a (they do not exist) |
| The retention boundary | Reset to its natural position | Same |

It is not reachable through the API; it needs AWS credentials. It cannot be undone, and there are no
backups.

**In `production`** a reset removes every meeting real visitors have booked, and every room. The demo
is a demo and this is allowed, but say you are doing it, and why, in an issue first.

## Steps

```bash
# 1. Reset (takes up to a few minutes)
aws lambda invoke --function-name $ENV-mootmaker-database-reset \
  --cli-read-timeout 900 --payload '{}' /dev/stdout

# 2. Refill, where demo-data is deployed (production, test, or an environment created --with-demo-data)
aws lambda invoke --function-name $ENV-mootmaker-demo-data \
  --cli-read-timeout 900 --payload '{}' /dev/stdout
```

The first command prints a summary of what it deleted. Between the two steps the environment has no
rooms or meetings at all; in `production` run them back to back.

Check the result by signing in with the demo login: the home page should show today's and tomorrow's
meetings and the calendar should be populated.

## If the reset fails

- **Timeout on the CLI side** without `--cli-read-timeout 900`: the reset carries on in the
  background. Check its log before running it again:
  `aws logs tail /aws/lambda/$ENV-mootmaker-database-reset --since 30m`.
- **AccessDenied**: your credentials cannot invoke it. Use the `WorkloadAdministrator` SSO role.
- **An error part-way**: reset is safe to run again. It works from what is there now.

## Starting an ephemeral environment again

For an ephemeral environment it is often quicker to tear it down and create a new one; see
[ephemeral environment problems](ephemeral-environment-problems.md).
