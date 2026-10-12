# Security incident

A credential may have leaked, unknown resources appeared in AWS, the bill jumped for no visible reason,
or the system is being misused. What protects the system is in [security](../overview/security.md).

Act in this order: **contain, then understand, then fix, then record.** Containing first is cheap and
reversible; understanding can take time.

## A credential leaked

| Credential | Contain | Then |
|---|---|---|
| `RELEASE_TAG_PAT` | Revoke it on GitHub at once | Check recent tags and pushes in the five repositories for anything unexpected; replace it ([how](expired-or-lost-credentials.md#release_tag_pat)) |
| GitHub account access (password, session, a token with `repo` scope) | Revoke sessions and tokens in GitHub settings; change the password; check 2FA | Anyone with push access to mootmaker-release's or mootmaker-ephemeral-envs' `main` could have assumed the AWS release role. Review recent commits there, and CloudTrail for `AssumeRoleWithWebIdentity` |
| AWS SSO session or role credentials | In Identity Center, sign the user out of all sessions | CloudTrail for the user's recent actions; `list-unmanaged-resources.sh` for anything created |
| Root credentials | Change the root password and MFA at once | CloudTrail in both accounts |
| The Android signing key | See [expired or lost credentials](expired-or-lost-credentials.md#the-android-signing-key) | |
| A machine-client secret | Replace the Cognito client (Terraform `-replace`) and release | It can do anything an admin can in that environment's data |

## Unknown resources or an unexplained bill

```bash
mootmaker-bootstrap-aws-accounts/list-unmanaged-resources.sh
aws cloudtrail lookup-events --max-results 50 \
  --lookup-attributes AttributeKey=EventName,AttributeValue=CreateFunction    # or RunInstances, CreateUser...
```

The SCPs limit the workload account to `us-east-1` and the services the system uses, so a leaked
credential cannot start EC2 instances or use other regions. Anything outside that list appearing in the
bill means the SCPs themselves were changed: check the management account.

## Misuse of the demo

The demo account is a public admin, so changing rooms and people is allowed, not an incident. Restore the
demo with [reset an environment](reset-an-environment.md). Signs of something worse:

- **A flood of sign-ups** (SES and Cognito costs climbing): look at recent users
  (`aws cognito-idp list-users --user-pool-id "$POOL" --filter 'status = "Enabled"'`, sorted by
  creation date). Delete them; consider whether the demo needs a sign-up limit.
- **Scripted API traffic** (AppSync and Lambda costs climbing): nothing logs the caller of each request
  today, since AppSync logs errors only. To find the source, raise the API's AppSync field log level to
  `ALL` for a short while (`field_log_level` in mootmaker-api's `appsync.tf`, or in the console as a
  recorded hand change), read the caller identities from `/aws/appsync/apis/<id>`, disable that account
  (`aws cognito-idp admin-disable-user`), and put the log level back.
- **Content that should not be public** (offensive meeting subjects, names or avatars visible to every
  visitor): delete it through the app as the demo admin, or reset.

## Record it

Open an issue (in the repository concerned, or the hub) describing what happened, when, what was exposed,
and what was done, unless the details themselves would help an attacker; then keep them private and
write a short public note. Update the [security overview](../overview/security.md#known-gaps) if this
revealed a gap.
