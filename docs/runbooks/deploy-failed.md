# Deploy failed

A component's `deploy.sh` failed, run by hand or inside a release. Each deploy is a `terraform apply`
for one component in one environment; the error is in the Terraform output.

| Error contains | Cause | Fix |
|---|---|---|
| `Error acquiring the state lock` | Another apply of the same component and environment is running, or one was killed and left its lock file | Check nothing else is deploying it (releases, the sweep, another session). Only then: `terraform force-unlock <lock-id>` in that component's `deploy/terraform`, with `TF_DATA_DIR=.terraform-<env>` |
| `AccessDenied ... with an explicit deny in a service control policy` | The change uses an AWS service or region the SCPs do not allow | Add the service to `pAllowedServiceActions` in **both** `scp-guardrails.yaml` and `identity-center.yaml`, and apply both from the management account. See [AWS accounts](../overview/aws-accounts.md#guardrails) |
| `AccessDenied` for `mootmaker-release-github-actions-deploy` or `mootmaker-ephemeral-github-actions-deploy` (in CI only) | The deploy role lacks a permission a new resource needs | Add it to the shared `mootmaker-deploy-*` policies in `github-actions-deploy-role.yaml`, apply with `deploy-stack.sh`. A local deploy works because `WorkloadAdministrator` is broader |
| `ExpiredToken`, `NoCredentials` | The SSO session ended | `aws sso login`. See [AWS access problems](aws-access-problems.md) |
| `ResourceAlreadyExistsException` for a log group | Something (usually Lambda, invoking the function) created the group before Terraform | `terraform import` it (see `deploy/import-log-groups.sh` in mootmaker-api), or delete the empty group and apply again |
| Certificate validation never finishes | The `mootmaker.com` zone's delegation is broken, so ACM cannot see its validation record | `dig +short NS mootmaker.com` must return the Route 53 nameservers. Fix the delegation at Porkbun |
| `environment must contain only lowercase letters, digits, and hyphens` / a name refused | The environment name is invalid, or starts with `prod` without being `production` | Use a valid name. Ephemeral names are `<kind>-<YYMMDD>-<rand4>` |
| A name longer than 64 characters (Lambda) or 63 (S3, Cognito domain) | The environment name is too long | Keep environment names to 22 characters or fewer |
| `LimitExceededException` (user pools, APIs, distributions) or `TooManyRequests` | Too many environments at once, or an AWS rate limit | Tear down unused ephemeral environments; wait and retry |
| The web app refuses to deploy: missing fields | The API in that environment does not serve a field the web app needs | Deploy (or release) the API first. See [API contract](../overview/api-contract.md#not-breaking-what-is-already-out-there) |
| `Missing parameter` from SSM in the web app or demo-data deploy | The API has not been deployed to that environment | Deploy mootmaker-api first |
| `Error: Unsupported Terraform Core version` | Terraform older than 1.10 | Upgrade Terraform; see the workstation manifest |

## After a failed deploy

- A failed apply leaves the environment **partly** updated. Running the deploy again after fixing the
  cause finishes it; Terraform applies what is still missing.
- In `test` or `production`, do not fix it with a hand deploy unless the pipeline itself is broken. Fix the
  cause on `main` and release again. See [failed release](failed-release.md).
- If you deleted or imported anything by hand, run
  `mootmaker-bootstrap-aws-accounts/list-unmanaged-resources.sh` afterwards to check nothing is left
  that no state claims.
