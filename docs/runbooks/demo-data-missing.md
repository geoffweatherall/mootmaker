# Demo data missing or wrong

The public demo looks empty, has no meetings in the coming weeks, the demo account's calendar is bare,
or someone has vandalised it (the demo login is a public admin). How demo data works is in
[demo data](../overview/demo-data.md).

## Is the daily run happening?

```bash
aws events describe-rule --name production-mootmaker-demo-data-schedule --query '{state:State,when:ScheduleExpression}'
aws logs tail /aws/lambda/production-mootmaker-demo-data --since 2d | tail -40
```

| Finding | Fix |
|---|---|
| Rule `DISABLED` | Something changed it by hand. A release re-applies it; or `aws events enable-rule --name ...` |
| No log output in two days | The rule is not firing or the Lambda is not being invoked; check the rule's target |
| Errors about SSM parameters | mootmaker-api's published parameters are missing; a release recreates them |
| Errors about tokens or 401 | The demo-data Cognito client or its secret changed; a release re-applies both |
| `TimeRangeUnavailable` or "skipped" lines | Normal: a guaranteed demo-account meeting found no free slot that day and skipped it |
| `Rate exceeded` / `TooManyRequestsException` on invoke | A run was already in progress (concurrency is reserved at 1). Wait and retry |

## Top it up now

Safe at any time: it only adds what is missing.

```bash
aws lambda invoke --function-name $ENV-mootmaker-demo-data \
  --cli-read-timeout 900 --payload '{}' /dev/stdout
```

`--cli-read-timeout 900` matters: without it the CLI gives up after 60 seconds and reports a failure
while the Lambda carries on and finishes.

## The demo has been vandalised

Anyone can sign in as the admin demo account, so rooms can be renamed or deleted, people deleted,
meetings cancelled. demo-data only fills gaps; it does not undo renames, and a deleted room's meetings
are gone. To start the data again from scratch, see [reset an environment](reset-an-environment.md).
In `production` that keeps real visitors' accounts and Persons, and removes all rooms and meetings,
which demo-data then regenerates.

## The demo account's calendar is empty

demo-data books at least one meeting for the demo account on every weekday in its window, but only if
it knows the account's Person id, from `/mootmaker/<env>/demo-data/guaranteed-person-ids`:

```bash
aws ssm get-parameter --name /mootmaker/$ENV/demo-data/guaranteed-person-ids --query Parameter.Value
```

If that is empty, or names a Person that no longer exists (the demo Person was deleted and recreated),
a release of mootmaker-api rewrites it. Then run demo-data again.

## Not enough people

demo-data counts *every* Person towards its target of 100, including real visitors who signed up. It
cannot tell them apart. In a busy environment it may create no demo people at all; that is expected.
