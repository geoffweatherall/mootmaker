# AWS access problems

Commands or deploys fail with credential or permission errors. How access works is in
[AWS accounts](../overview/aws-accounts.md#getting-access).

## On a workstation

```bash
aws sts get-caller-identity
```

| Result | Cause | Fix |
|---|---|---|
| `ExpiredToken`, `NoCredentials`, `Token has expired` | The SSO session ended | `aws sso login` |
| Works in the CLI but a Node or Java tool says the token expired | Those SDKs do not renew the SSO token themselves; the CLI does when it next fetches credentials | Run any CLI command (`aws sts get-caller-identity`) before a long test run. Do not delete `~/.aws/cli/cache` |
| Account `339140804537` | The wrong profile; that is the management account | Use the `[default]` profile. Check `AWS_PROFILE` is not set |
| `Unable to parse config file` | A duplicate `[default]` section in `~/.aws/config` | Merge them; see the config in [AWS accounts](../overview/aws-accounts.md#getting-access) |
| `The SSO session associated with this profile has expired or is otherwise invalid` | As above | `aws sso login` |

### Access denied

| Message mentions | Cause | Fix |
|---|---|---|
| `explicit deny in a service control policy` | The service or region is not allowed in the workload account | Use `us-east-1`. A new service has to be added to the SCPs; see [deploy failed](deploy-failed.md) |
| `ce:` or Cost Explorer with the default profile | Fine: Cost Explorer for the workload account works with `WorkloadAdministrator`. For the organisation's bill use `--profile mootmaker-billing` | |
| A management-account stack | Changing it needs `with-management-credentials.sh` and the separate `geoff-management` user | See mootmaker-bootstrap-aws-accounts' README |

### Lost MFA device or locked out of Identity Center

The fallback is the **root user** of the management account (`339140804537`), in the console. From
there, Identity Center can reset the user's MFA. Root's own credentials and MFA must be kept somewhere
safe and offline; without them there is no way back in short of AWS support.

## GitHub Actions cannot assume the role

A workflow fails at "Configure AWS credentials" with `Not authorized to perform
sts:AssumeRoleWithWebIdentity`.

| Cause | Check |
|---|---|
| The workflow runs from a ref the role does not trust | Components are trusted only at `v*` tags (or through mootmaker-release's call); mootmaker-release and mootmaker-ephemeral-envs only at `main`; android and webapp only for `pull_request`. A `workflow_dispatch` from a branch is refused |
| The repository was recreated, so its numeric id changed | `gh api repos/geoffweatherall/<repo> --jq .id` against the ids in `workload-account/github-actions-deploy-role.yaml`. Update and apply the stack |
| A pull request from a fork | Forks get no OIDC token. Expected |
| The job lacks `permissions: id-token: write` | Add it to the job |

A permission error *after* assuming the role is a missing permission on the role; see
[deploy failed](deploy-failed.md).
