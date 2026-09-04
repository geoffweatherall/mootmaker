# Environments — how multi-environment deployment works

The mechanics of how mootmaker runs multiple independent copies of the stack, and how to stand up
and tear down your own. Moved here from the project README during the 2026-08 reorganisation.

> **Note (updated 2026-09-04):** the long-lived environments are **production** and **test**, plus
> short-lived **ephemeral** ones. `test` was retired on 2026-08-29 and reinstated on 2026-09-03 with
> a narrower job — the release pipeline's rehearsal stage, deployed to only by that pipeline. The
> mechanics on this page never depended on which names exist and are still accurate throughout; the
> `test` examples below read correctly again. For the *policy* — which environments exist, why, and
> what may deploy to them — see [`../process/environments.md`](../process/environments.md).


### Overview

Multiple independent copies of the stack (API + webapp) can run in the same AWS account at once, each identified by an arbitrary **environment** name — `test`, `production`, or a developer's own name for a personal sandbox (e.g. `bob`). There's no fixed list of environments to register anywhere; the name is just an argument passed to each project's scripts. Every environment gets:

- its own Terraform state, held in the shared bucket created by [mootmaker-bootstrap-terraform](https://github.com/geoffweatherall/mootmaker-bootstrap-terraform), and
- its own uniquely-named AWS resources (Lambdas, DynamoDB tables, Cognito user pool, S3 bucket, CloudFront distribution, etc.),

so environments can be created and destroyed independently without touching each other.

### Tricky issues and how they're solved

- **AWS resource names would collide across environments.** Every resource name used to derive from a single `project_name` variable, which is fine with one deployment but would clash the moment `test` and `production` (or `bob`) tried to create identically-named Lambdas/tables/etc. in the same account. Fix: each project computes a `resource_prefix = "<environment>-<project_name>"` local and names every resource from that instead.
- **Terraform state needs to be per-environment, in one shared bucket.** The state key now includes the environment: `<environment>/<project-name>/terraform.tfstate` (e.g. `test/mootmaker-api/terraform.tfstate`). The bucket/region/locking config stays static in a checked-in `backend.hcl`, but the `key` is supplied at `terraform init` time by each script, computed from the environment argument — so any environment name works without editing any file.
- **Switching environments in the same checkout could corrupt Terraform's local cache.** Terraform records which backend it's configured for in a local `.terraform/` directory; reusing that between environments (or running two environments concurrently from one checkout) risked one clobbering the other's cached config. Fix: each script sets `TF_DATA_DIR` to a per-environment directory (`.terraform-<environment>/`), so each environment's local metadata is fully isolated.
- **The webapp needs values (Cognito ids, GraphQL URL) from the API's deployment, per environment.** `authenticate.sh` now takes the environment name as an argument and re-initialises itself against that environment's state before reading outputs, so it always reads the right environment's values. The webapp's `deploy.sh` takes the same environment name and passes it straight through to `authenticate.sh`, so an API and webapp deployed with the same environment name are automatically wired together.
- **Accidentally deploying to the wrong place.** There's no default environment — every script requires the name to be passed explicitly, and validates it against a safe character set (lowercase letters, digits, hyphens) since it ends up embedded in AWS resource names and S3 state keys. `undeploy.sh` also still requires interactive confirmation (no `-auto-approve`), regardless of environment.

## Overall How-to: set up, test, and tear down your own environment

Prerequisites: the shared state bucket already exists (one-time setup, see [mootmaker-bootstrap-terraform](https://github.com/geoffweatherall/mootmaker-bootstrap-terraform)'s README), and you have `mootmaker-api` and `mootmaker-webapp` checked out as sibling directories.

Pick a name nobody else is using — your own name works well (this example uses `bob`):

```bash
# 1. Deploy the API
cd mootmaker-api
./deploy.sh bob

# 2. Try it out / run the acceptance tests against your environment
./verify.sh bob

# 3. Deploy the webapp, pointed at the same environment's API
cd ../mootmaker-webapp
./deploy.sh bob
# prints a site URL - open it and try the app for real

# 4. When you're done, tear both down (order doesn't matter)
./undeploy.sh bob
cd ../mootmaker-api
./undeploy.sh bob
```

Each `./deploy.sh`/`./undeploy.sh` prompts you through anything it needs (AWS credentials, a sibling API checkout, etc.) and fails fast with a clear message if a prerequisite is missing. Since `bob` gets entirely separate AWS resources and Terraform state from `test`/`production`, you can iterate freely without any risk of touching a shared environment.

