# Cost reduction

## Summary

The AWS bill went from US$1.26 in August to US$6.11 in September and US$7.52 for 1–10 October.
Almost all of it is driven by releases and ephemeral environments, not by production use. This
design collects the measures that cut it, one section per measure. Measure 1 stops ephemeral
environments from publishing their hostnames to the public certificate logs, which is what drives
the growth in Route 53 query charges. Later measures are listed but not yet designed.

## Status

**Drafting** — 2026-10-11.

## Where the money goes

Cost Explorer for the workload account, which is effectively the whole organisation bill (the
management account was US$0.01 in October). Days are UTC.

| October 1–10 | US$ | Driver |
|---|---|---|
| Cognito M2M token requests | 3.71 | US$2.25 per 1,000 tokens; 1,030 on 1 October alone |
| Tax | 0.98 | GST, booked on the 1st for the month |
| SES (outbound plus Essentials plan surcharge) | 0.73 | Acceptance-test email |
| AppSync | 0.60 | Acceptance-test GraphQL |
| Route 53 hosted zone | 0.50 | Fixed, monthly |
| Route 53 DNS queries | 0.39 | See Measure 1 |
| DynamoDB | 0.33 | Acceptance-test reads and writes |
| S3 | 0.25 | Mostly PUTs when ephemeral environments deploy the webapp |

- **1 and 2 October cost US$5.24 between them.** That was 11 release runs before the per-run M2M
  token cache shipped in v5.8.1 (webapp#154, release#73, api#103). Tokens per release fell from
  about 130 to about 20 after it.
- **A release now costs about US$0.12.** 4, 5 and 10 October had one release each and cost
  US$0.12–0.15.
- **A day with no releases costs about US$0.02**, nearly all of it DNS queries.
- **Failed release runs cost nearly as much as successful ones.** 7 October had 13 runs, 8 of them
  failed, and cost US$1.02.

Cost Explorer only offers daily granularity in this organisation. Hourly data is an opt-in in the
management account's Cost Explorer settings. Route 53 query logging (on since 2026-10-03, 14-day
retention, log group `/aws/route53/mootmaker.com`) gives per-query detail for DNS.

## Measure 1: stop publishing ephemeral hostnames

### The problem

Every ephemeral environment issues three ACM certificates, one per hostname:

| Hostname | Built in |
|---|---|
| `www.<env>.mootmaker.com` | `mootmaker-webapp/deploy/terraform/domain.tf` |
| `api.<env>.mootmaker.com` | `mootmaker-api/deploy/terraform/domain.tf` |
| `avatars.<env>.mootmaker.com` | `mootmaker-api/deploy/terraform/avatars.tf` |

ACM logs every certificate to the public Certificate Transparency (CT) logs. Scanners watch those
logs and query every name they find, and they keep querying long after the environment is torn
down. A release creates three environments (`rel-api-*`, `rel-web-*`, `rel-demo-*`), so it
publishes nine new names. The query logs for 3–10 October show:

- **901k queries in total, of which 785k (87%) are for ephemeral-environment names.** None of those
  environments exist now. The zone currently has no ephemeral records at all.
- **About 30% of those queries are for bare `<env>.mootmaker.com` names that never had a record.**
  The scanners derive them from the published names.
- **The traffic decays but does not stop.** On 9–10 October, names from environments created in
  the previous week drew about 98k queries a day. Names more than a week old drew about 32k a day,
  going back to environments created on 15 August.
- **Queries arrive through Google and Cloudflare public resolvers**, not from anything of ours.

The volume tracks releases. Idle days ran at 50–55k queries a day, while 7–9 October, after 18
release runs, ran at 170–210k. At US$0.40 per million that is about US$0.06 a day now, roughly
US$2 a month, and it grows with every release.

### Options considered

**A. One wildcard certificate for all non-production environments (recommended).** A certificate
wildcard matches exactly one label, so `*.mootmaker.com` cannot cover `api.<env>.mootmaker.com`.
The hostnames have to flatten to one level:

| Now | Proposed |
|---|---|
| `www.<env>.mootmaker.com` | `<env>.mootmaker.com` |
| `api.<env>.mootmaker.com` | `<env>-api.mootmaker.com` |
| `avatars.<env>.mootmaker.com` | `<env>-avatars.mootmaker.com` |

One `*.mootmaker.com` certificate, owned by `mootmaker-domain`, then serves every non-production
environment. CloudFront accepts wildcard certificates. AppSync custom domains accept one too, as
long as it is in `us-east-1`, which everything here already is. After the change an environment
publishes nothing to the CT logs. Its names can still be guessed, but nothing announces them.

**B. Turn off CT logging on the per-environment certificates (rejected).** ACM allows it per
certificate (`CertificateTransparencyLoggingPreference = DISABLED`). Chrome rejects publicly trusted
certificates that are not in the CT logs, so the webapp, and the API calls it makes, would fail in
Chrome and in the Chromium-based Playwright suites.

**C. A wildcard DNS alias record for the names already published (a separate experiment, not part
of this measure).** Route 53 does not bill queries answered by an alias record that points at an
AWS resource such as CloudFront. A wildcard `*.mootmaker.com` A/AAAA alias would match names at
any depth below the zone, including `api.<deleted-env>.mootmaker.com`. That would make 70% of the
ephemeral-name queries free (A 422k plus AAAA 124k of 785k). The catches:

- Other query types, such as NS, TXT, CNAME, MX and CAA, would get a billed empty answer instead
  of a billed NXDOMAIN.
- Every typo or deleted hostname would resolve to a CloudFront address, which fails at TLS instead
  of failing at DNS. That is less clear when debugging, and it might draw more probing than an
  NXDOMAIN does.
- Alias answers to CloudFront carry a 60-second TTL. NXDOMAIN answers are cached for 900 seconds
  (the SOA minimum), so resolvers would ask more often, even though those queries would be free.

It is the only option that touches names already published, so it is worth recording. On its own
merits it should be an experiment with a measured before and after, not part of this change.

### Why not every query can be free

Route 53 can only make alias targets of AWS resources such as CloudFront, ELB, API Gateway and S3
websites, and only for A/AAAA answers in this setup. SES is not an alias target. The
`mail.mootmaker.com` MX record (`10 inbound-smtp.us-east-1.amazonaws.com`, TTL 600) and the DKIM,
SPF and verification records are plain records, so queries for them are always billed. On 7–9
October that was about 5k MX queries for `mail.mootmaker.com` and 8k for the apex, which has no
MX record. These are small. Raising their TTLs is the only lever, and it belongs to a different
measure.

### What it achieves, at most

- **New names published per release: from about nine to zero.** This includes Claude and Android
  test environments, not just releases.
- **DNS queries fall back towards the idle floor of 40–60k a day**, which is about US$0.50–0.70 a
  month, against US$2+ at last week's release rate. The saving is about US$1–2 a month at that
  rate, and it grows as release frequency grows.
- **The names already published are unaffected.** Their traffic keeps decaying slowly. Option C is
  the only thing that reaches them.
- **Deploys get faster and simpler.** Each environment skips issuing three certificates and
  waiting for their DNS validation, and the zone stops collecting `_<token>` validation CNAMEs.
  Those drew 21k queries on 3–10 October. The time saved has not been measured.
- **No effect on the hosted-zone charge, Cognito, SES, AppSync or DynamoDB**, which are most of
  the bill.

## Further measures (not yet designed)

To be written up as later sections, each with its own numbers:

2. **Fail releases earlier.** A failed run costs nearly what a successful one does.
3. **SES pricing plan.** The account is on the Essentials plan, which adds a surcharge per email.
4. **SOA negative-cache TTL.** It is 900 seconds. A longer value could reduce repeated NXDOMAIN
   queries, but public resolvers may not respect it.
5. **Hourly cost data.** Enable it in the management account if daily resolution proves too
   coarse.

## Scope / non-goals

- Measure 1 changes non-production hostnames only. Production keeps `www`, `api` and `avatars`
  under `mootmaker.com`, with their existing certificates.
- It does not try to remove names already in the CT logs. They cannot be removed.
- It does not change the Cognito hosted domain, which is under `amazoncognito.com`, not ours.

## Trade-offs and decisions

- **Flattened hostnames over a second zone or other workarounds.** A one-level wildcard is the
  constraint. Any scheme that keeps `api.<env>` needs one certificate per environment, which is
  the thing that publishes the names.
- **CT opt-out rejected.** It breaks Chrome (option B).
- **The wildcard DNS alias kept separate.** It has different risks and a different benefit
  (option C).

## Choices you had me make

- **The `<env>-api` / `<env>-avatars` suffix form**, rather than `api-<env>`. It keeps one
  environment's names together when sorted, and the bare `<env>` name stays the webapp.
- **Production keeps its own certificates.** Its names are already public, so moving it gains
  nothing, and it avoids coupling production to a certificate shared with throwaway environments.
- **The wildcard certificate lives in `mootmaker-domain`**, next to the apex certificate. That repo
  is persistent and owns the zone.

## Open questions

**Blocking**

- Is the flattened naming scheme acceptable? It also renames the long-lived `test` environment to
  `test.mootmaker.com`, `test-api.mootmaker.com` and `test-avatars.mootmaker.com`.

**Non-blocking**

- Whether to run the wildcard-alias experiment (option C) afterwards.
- Whether to measure how long certificate issuance currently adds to an ephemeral deploy, to put
  a number on the deploy-time benefit.

## Impacts on components

- **mootmaker-domain:** a new `aws_acm_certificate` for `*.mootmaker.com` with DNS validation,
  alongside `deploy/terraform/acm.tf`.
- **mootmaker-api:**
  - `deploy/terraform/domain.tf`: `local.api_domain` becomes `<env>-api.mootmaker.com` outside
    production. The certificate and its validation records are created only in production.
    Elsewhere, `aws_appsync_domain_name` uses the wildcard certificate, found with a
    `data "aws_acm_certificate"` lookup.
  - `deploy/terraform/avatars.tf`: the same for `local.avatars_domain` and the avatars CloudFront
    distribution.
  - Comments in `deploy.sh` and the `outputs.tf` description.
- **mootmaker-webapp:** `deploy/terraform/domain.tf` changes the same way, plus the comment in
  `deploy.sh`.
- **Everything downstream reads the hostnames from Terraform outputs and SSM.** That covers
  `graphql-url`, the webapp URL, the avatars base URL and Android's `mobile-config.json`, so
  nothing else should need editing. The grep found no hard-coded `www.<env>` patterns in
  `mootmaker-release`, `mootmaker-ephemeral-envs` or `mootmaker-email-testing`. Recheck this during
  implementation.

## Changes to the domain data model and data storage models

N/A. Stored avatar paths are origin-relative, and the host is prepended from configuration.

## Technical considerations

- **Two environments cannot claim the same name on CloudFront or AppSync.** Environment names are
  already unique, and the suffix form keeps them unique.
- **DNS labels are limited to 63 characters.** The longest current pattern, `rel-demo-261008-ad41`
  plus `-avatars`, is 28.
- **An environment deployed before the change and redeployed after it renames its hostnames.**
  Terraform destroys its old certificates. Ephemeral environments are short-lived, and `test` is
  redeployed by every release.
- **What this leaves behind:** less than today. There is one long-lived certificate, which ACM
  renews automatically while its validation record stays in the zone, instead of three certificates
  and three validation records per environment.

## Testing impacts

- **Unit:** not impacted. Unit tests use production URLs (for example `AvatarUrlsTest`), and those
  do not change.
- **Mocked integration / e2e:** not impacted. They do not depend on deployed hostnames.
- **Acceptance:** no new cases. A full acceptance run on an ephemeral environment built after the
  change is the proof, since every test resolves the new hostnames from configuration.
- **Release smoke suite:** not impacted beyond running against the renamed `test` hosts, which it
  reads from configuration.
- **New check:** after deploying an ephemeral environment, confirm that no certificate for its
  names was issued (`aws acm list-certificates`) and that the environment serves the wildcard.

## Documentation impacts

Pages that describe the `www.<env>` / `api.<env>` pattern:

- `mootmaker-webapp/README.md`
- `mootmaker-api/README.md`
- `mootmaker-domain/README.md` and `AGENTS.md`
- `docs/reference/data-model.md`
- `docs/showcase/learnings.md`, which may be worth a learning entry about CT logs and DNS scanners

## Rollout & migration

1. Deploy `mootmaker-domain` first, so the wildcard certificate is issued before anything looks
   it up.
2. Then deploy api and webapp together, through a normal release. No data migration is needed.

## Risks

- **A typo in the lookup or in the hostnames breaks every non-production environment at once.**
  An ephemeral acceptance run before release catches it.
- **The certificate becomes a shared dependency.** If its validation record is deleted, ACM cannot
  renew it, and every non-production environment fails together about 13 months later. Keep the
  record in Terraform, where it is easy to see.
- **Reversing is cheap:** restore the per-environment certificates and hostnames.

## Implementation checklist

Filled in once Ready.

## Definition of done

- The wildcard certificate is issued and used by a new ephemeral environment, and no
  per-environment certificates are created.
- A clean acceptance run on that environment, and a successful release.
- Unit tests are green in each touched repository.
- The documentation listed above is updated.
- A week of query logs after the change shows ephemeral-name queries declining, not growing,
  across releases.
