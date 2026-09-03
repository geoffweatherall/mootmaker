# Architecture

How the pieces fit together, across repositories. For what the system *does*, see
[`../reference/business-functionality.md`](../reference/business-functionality.md); for the data,
[`../reference/data-model.md`](../reference/data-model.md).

## Shape

```
  Browser
     |  HTTPS
  CloudFront  ->  S3            static React bundle          [mootmaker-webapp]
     |
     |  GraphQL (authenticated with a Cognito ID token)
  AppSync                                                     [mootmaker-api]
     |
  Lambda (Java 25)  ->  DynamoDB                              [mootmaker-api]
     |
  Cognito           ->  post_confirmation Lambda -> DynamoDB   [mootmaker-api]
     |
  SES                   sign-up and password-reset mail       [mootmaker-domain]
```

Everything is serverless and scales to zero. Nothing costs money while idle, which is a hard
constraint rather than a preference — see [`../process/principles.md`](../process/principles.md).

## Repositories and what they own

| Repository | Owns |
|---|---|
| `mootmaker` | Designs, process, reference docs, showcase. No deployed code. |
| `mootmaker-api` | GraphQL schema, Java Lambda handlers, DynamoDB tables, Cognito user pool, and the `database-reset`/`database-repair` admin Lambdas (destructive — see [operator.md](../roles/operator.md)) |
| `mootmaker-webapp` | React SPA, its S3 bucket and CloudFront distribution |
| `mootmaker-android` | A second frontend on the same API. Not started. |
| `mootmaker-demo-data` | Per-environment Lambdas that seed and top up demo data — ships as part of the product |
| `mootmaker-ephemeral-envs` | Ephemeral environment lifecycle scripts |
| `mootmaker-email-testing` | The persistent SES pipeline that lets tests read real email |
| `mootmaker-release` | Release pipeline that ships the deployable components to `test` and `production` |
| `mootmaker-domain` | Route 53 zone, ACM certificate, SES domain identity. Shared across environments. |
| `mootmaker-bootstrap-terraform` | The S3 bucket holding everyone's Terraform state |
| `mootmaker-bootstrap-aws-accounts` | Account guardrails: SCPs, IAM Identity Center, billing alerts |

## Environments

Any number of complete, isolated copies coexist in one AWS account. An environment is just a name
passed to each repository's scripts — there is no registry.

Three mechanisms keep them apart:

- **Resource naming.** Every resource derives from `resource_prefix = "<environment>-<project>"`, so
  nothing collides.
- **State keys.** Terraform state lives at `<environment>/<project>/terraform.tfstate` in the shared
  bucket. The bucket and region are static in a checked-in `backend.hcl`; the key is supplied at
  `terraform init` time.
- **Local Terraform metadata.** Each script sets `TF_DATA_DIR=.terraform-<environment>`, so two
  environments can be worked on concurrently from one checkout without clobbering each other.

There is no default environment. Every script requires the name explicitly and validates it, since
it ends up in resource names and state keys.

See [`../process/environments.md`](../process/environments.md) for policy and
[environments.md](environments.md) for the full mechanics.

## How the webapp reaches the API

The webapp needs values that only exist after the API is deployed — the GraphQL URL, the Cognito
user pool and client IDs. `mootmaker-api/authenticate.sh` reads them from that environment's
Terraform outputs, and the webapp's `deploy.sh` passes the environment name straight through. So an
API and a webapp deployed with the same environment name are wired together automatically.

This is why `mootmaker-api` must be a sibling checkout, and why it must be deployed first.

## Contract between API and frontends

`mootmaker-api/api/mootmaker.graphql` is the source of truth for the schema, and is published as
`@mootmaker/schema` (npmjs.com) and `com.mootmaker:mootmaker-schema` (GitHub Packages) whenever it
changes on `main`.

`mootmaker-webapp` **generates** its types and operations from it (`npm run codegen`), reading the
sibling `mootmaker-api` checkout locally and the published package in CI — so a field that no longer
exists is a compile error rather than a runtime surprise. Its deploy additionally refuses to ship
against an API that does not serve the schema the build expects, since the two deploy independently.

`mootmaker-demo-data` and `mootmaker-api/verify` still build GraphQL operations as hand-written
strings; converting them is deliberately later work. See
`../../designs/graphql-schema-sharing.md`.

Error handling follows a deliberate pattern: the GraphQL schema defines an error enum per entity
(`RoomError`, `PersonError`, `MeetingError`) with a Java enum of exactly matching constant names.
Adding a case means changing both in step.

## Deployment order

1. `mootmaker-bootstrap-terraform` — once per AWS account, creates the state bucket
2. `mootmaker-bootstrap-aws-accounts` — once per account, the guardrails
3. `mootmaker-domain` — once, shared across environments
4. `mootmaker-api` — per environment, first; its own Terraform includes `database-reset`, so nothing
   further needs deploying before the next step depends on it
5. `mootmaker-webapp` — per environment, reads the API's outputs
6. `mootmaker-demo-data` — per environment, optional outside `production`; reads its credentials
   from SSM parameters created by step 4, so that must already exist

## Testing layers

| Layer | Where | Against |
|---|---|---|
| Unit | `impl/src/test`, `webapp/src/**/*.test.ts` | Nothing external |
| Integration | `webapp/tests/` | A mocked API (MSW) |
| e2e | `e2e/` | A real deployed environment |
| Acceptance | `acceptance/` | A real deployed environment, from the use-case catalogue |

A green acceptance run against a real deployment is the project's definition of working. See
[`../reference/testing-strategy.md`](../reference/testing-strategy.md).
