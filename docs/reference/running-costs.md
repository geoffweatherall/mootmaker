# Running costs

What this system actually costs to run, measured rather than estimated, and why the number stays
flat under constant usage.

This exists to make [principles.md](../process/principles.md)'s "nothing accumulates without a
bound" checkable. A principle that can't be verified against a bill is a slogan.

All figures below are from AWS Cost Explorer for the workload account (`431071856068`) on
**2026-09-05**. They are unblended costs in USD.

## The short version

**About $0.60 a month at rest, plus roughly $0.10 per acceptance run.**

```
monthly cost  ≈  $0.60  +  $0.10 × (number of full acceptance runs)
```

The important property is what's *absent* from that model: no term for elapsed time, stored data
volume, or accumulated history. Cost is a function of how much the system is *used*, not of how long
it has existed. That is the whole point of scale-to-zero, and the numbers below are what confirm it
rather than assert it.

## Monthly trend

| Service | Jun 2026 | Jul 2026 | Aug 2026 | Sep 2026 (5 days) |
|---|---|---|---|---|
| Route 53 | 0.0000 | 0.0000 | 0.5676 | 0.5717 |
| Cognito | 0.0000 | 0.0473 | 0.1103 | 0.4500 |
| SES | 0.0000 | 0.0000 | 0.1360 | 0.2791 |
| AppSync | 0.0000 | 0.0275 | 0.1099 | 0.1857 |
| DynamoDB | 0.0000 | 0.0214 | 0.0894 | 0.1302 |
| S3 | 0.0000 | 0.0107 | 0.0822 | 0.0540 |
| Tax | 0.0000 | 0.0200 | 0.1600 | 0.2500 |
| **Total** | **0.0000** | **0.1268** | **1.2553** | **1.9208** |

September's five days already exceed all of August. **That is not a leak** — it is the CI/CD
build-out running the full acceptance suite dozens of times. It is the cost of deliberate activity,
and it stops when the activity stops, which is exactly the behaviour we want. Read it as evidence
the model works, not as a warning.

Route 53 first appears in August, when the domain and hosted zone were created.

## Daily shape

The clearest evidence sits in the daily numbers across the transition into the CI/CD work:

| Date | Cost | |
|---|---|---|
| 2026-08-20 | 0.0012 | idle |
| 2026-08-21 | 0.0013 | idle |
| 2026-08-25 | 0.0011 | idle |
| 2026-08-26 | 0.0751 | build-out begins |
| 2026-08-28 | 0.1377 | |
| 2026-09-01 | 0.7579 | includes the $0.50 monthly hosted-zone charge |
| 2026-09-03 | 0.4212 | heavy release testing |
| 2026-09-04 | 0.6161 | ~10 full acceptance runs |

**An idle day costs about a tenth of a cent.** Not "cheap" — genuinely close to zero. Everything
above that line is something we chose to run.

## Where the money goes

Broken down by usage type over 2026-08-26 to 2026-09-05:

| Usage type | Cost | Fixed or variable |
|---|---|---|
| Route 53 `HostedZone` | 0.5000 | **Fixed** — $0.50/month regardless of use |
| Cognito `CUPM2MTokenRequestsFull` | 0.5198 | Variable — measured at **$0.00225 per request** |
| AppSync `GraphQLInvocation` | 0.2734 | Variable |
| SES `Essentials-Outbound-Email` | 0.2617 | Variable |
| SES `Message` | 0.1507 | Variable |
| Route 53 `DNS-Queries` | 0.1117 | Variable |

Charged at **$0.00** across the whole window: **Lambda, CloudFront, CloudWatch, KMS**. Lambda is the
component doing the actual work, and it is free at this volume.

### The one fixed cost

The Route 53 hosted zone is $0.50/month and does not scale to zero — a hosted zone costs the same
whether it serves one query or none. That is the floor, and it is the correct trade: it is what
makes every environment addressable by name, including ephemeral ones.

Domain registration is annual and billed separately from this account's usage.

### The largest variable cost

Cognito machine-to-machine token requests, at **$0.00225 each**, are the most expensive single unit
in the system — more than a GraphQL invocation or an email. Usage tracks release activity precisely:

| Date | M2M token requests | Cost |
|---|---|---|
| 2026-08-30 | 0 | 0.0000 |
| 2026-09-02 | 20 | 0.0450 |
| 2026-09-03 | 68 | 0.1530 |
| 2026-09-04 | 111 | 0.2497 |

Checked, because a per-request token fetch would be exactly the kind of silent multiplier this
document exists to catch: **tokens are cached, not re-fetched per call.** `mootmaker-api`'s
acceptance `GraphQlClient` holds a `synchronized` cached token; `mootmaker-demo-data`'s Lambda
fetches once per invocation. The count scales with *runs*, not with requests-within-a-run, which is
the shape it should be.

## What this does not prove

Being honest about the limits of the measurement:

- **Free-tier reliance is not separated out.** Lambda, CloudFront and CloudWatch showing $0.00 means
  they fell inside free-tier allowances at this volume. Some AWS free tiers are permanent and some
  expire twelve months after account creation. A future bill could show non-zero lines here without
  anything having changed in the system. Worth re-reading this document against the bill rather than
  assuming these stay at zero.
- **Volume is low enough that unit economics are untested.** Nothing here says what happens at 100×
  the traffic. It says the system is *proportional*, not that the constant is small at any scale.
- **Tax is a pass-through** and tracks the rest; it is listed for completeness, not analysis.

## Checking it yourself

Cost Explorer is readable from the `WorkloadAdministrator` SSO role in the workload account — no
management-account access needed:

```bash
aws ce get-cost-and-usage \
  --time-period Start=2026-09-01,End=2026-09-06 \
  --granularity DAILY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE --region us-east-1
```

Swap `Key=SERVICE` for `Key=USAGE_TYPE`, and add `--filter` on a service, to get the unit-level
breakdown that the tables above come from.

**Each Cost Explorer API call costs $0.01.** That is not a rounding error against a $2 monthly bill —
polling this would be a meaningful fraction of what it measures. Query it deliberately, not on a
schedule.

## What would change the picture

Things that would break the "flat under constant usage" property, worth watching for:

- **Any log group, metric or bucket without an expiry.** The reason retention is set everywhere —
  see the CloudWatch retention decision in `designs/ci-cd-pipeline.md`.
- **A token, connection or client fetched per request rather than per session.** Cognito M2M is the
  place this would show first, given it is the priciest unit.
- **Environments that outlive their purpose.** The ephemeral sweep exists for this; a stranded
  environment holds a hosted-zone-adjacent footprint and keeps its Lambdas warm-able indefinitely.
- **Retained data growing without bound**, since DynamoDB is charged partly on storage. Today's
  volumes are demo-scale and the reset tooling keeps them there.
