# Cost reduction

## Summary

The AWS bill went from US$1.26 in August to US$6.11 in September and US$7.52 for 1–10 October.
Almost all of it is driven by releases and ephemeral environments, not by production use. This
design collects the measures that cut it, one section per measure. Measure 1 stops ephemeral
environments from publishing their hostnames to the public certificate logs, which is what drives
the growth in Route 53 query charges. Measure 2, moving SES to à-la-carte pricing, is done.
Measure 3 stops parallel release builds once one has failed, and has shipped. Later measures are listed
but not yet designed.

## Status

**Drafting** — 2026-10-11. This covers the document as a whole, and Measure 1 in particular.
Measure 2 is done. Measure 3 shipped in v5.10.12 on 2026-10-11; its own section gives its state.

## Where the money goes

Cost Explorer for the workload account, which is effectively the whole organisation bill (the
management account was US$0.01 in October). Days are UTC.

| October 1–10 | US$ | Driver |
|---|---|---|
| Cognito M2M token requests | 3.71 | US$2.25 per 1,000 tokens; 1,030 on 1 October alone |
| Tax | 0.98 | GST, booked on the 1st for the month |
| SES (outbound at the Essentials rate, plus inbound) | 0.73 | Acceptance-test email; see Measure 2 |
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

## Measure 2: SES on à-la-carte pricing (done)

**Done 2026-10-11 09:23 NZDT** with `aws sesv2 put-account-pricing-attributes --plan NONE`. Check
it with `aws sesv2 get-account --query PricingAttributes`, which should report
`"CurrentPlan": "NONE"`. The setting is account-wide. It is not in Terraform, because nothing here
manages it, so this section is the record of it.

**Why.** The account was on SES's Essentials plan. That is the default for accounts since
2026-07-21, not something we chose. Essentials charges US$0.16 per 1,000 outbound emails, while
à-la-carte charges US$0.10. Neither has a monthly fee. We use nothing that Essentials bundles:

- **Virtual Deliverability Manager:** not enabled (`VdmAttributes` is null).
- **Mail Manager:** not used. Inbound mail goes through a classic receipt rule (`catch-all` on
  `mail.mootmaker.com` → SNS), which is billed at the à-la-carte inbound rate either way.

AWS's pricing page says a first move from the default Essentials plan to à-la-carte takes effect
immediately and carries no commitment. Moving back is an upgrade, which is also immediate.

**Effect.** Outbound email costs 37% less. On 1–10 October that was 2,872 emails, US$0.46 on
Essentials, which would have been US$0.29 on à-la-carte. At October's pace that saves about
US$0.50 a month. Inbound (US$0.10 per 1,000) is unchanged.

**Considered and not chosen: sending fewer test emails.** Nearly all of the mail is the acceptance
suites mailing themselves. Each `freshTestAccount` sign-up makes Cognito send a verification email
to `mail.mootmaker.com`, and SES receives it back, so each one is billed twice. Only sign-up,
forgot-password and the release smoke test need the real email path. The other tests could get
pre-confirmed accounts and roughly halve the volume, saving about US$0.30 a month. The tests stay
as they are. Creating accounts through the real sign-up path is a deliberate choice (see
`FixtureUsers` in mootmaker-api), and a saving this small does not justify changing it. Test speed
would be the stronger reason, since each email wait polls for up to 60 seconds, but that is a
separate decision.

**Loose end.** Outbound exceeds inbound by about 200 messages in October, so some mail goes
somewhere other than `mail.mootmaker.com`. The apex has no MX record, so mail to
`demo@mootmaker.com` would bounce, and bounces count against the account's sending reputation.
Worth identifying, though it costs nothing.

## Measure 3: stop parallel release builds once one fails (done)

**State:** released in v5.10.12 on 2026-10-11 (release run 38087864625, 10:30–11:24 NZDT). All
four builds installed the action, passed every `fail-fast check` gate and ran their wrapped
acceptance suites to success, so the normal path is proven in a real release. The stopping path is
proven in a real Actions run (see "Verification"). The first release with a failing build will be
its first use in anger.

### The problem

A release's four component builds (`build-api`, `build-webapp`, `build-demo-data`,
`build-android`) run in parallel. Each deploys its own ephemeral environment and runs an acceptance
suite against real AWS. `tag` only runs if all four pass, so once one fails the release is lost,
but nothing told the others. They ran to the end, spending time and AWS cost on a result nobody
could use.

On 7–8 October, 7 release runs failed in a build. After the first failing step in each run, the
other builds kept running for 154 minutes between them, mostly `build-webapp`'s 35-minute suite.
That figure includes their teardowns, which still have to happen. In the worst case (run
37599925866), `build-android` failed after two minutes and `build-webapp` ran for another 31.

### What was built

A composite action, `mootmaker-release/.github/actions/fail-fast`, that each component's
`release-build.yml` installs. It provides one command with two forms:

- **`fail-fast check`** exits 1 if another job in this run attempt has failed. It is the first
  line of every deploy step, so a build that has not deployed yet never starts to.
- **`fail-fast run -- CMD`** runs the acceptance-test command in its own process group, checks
  the run's jobs every 60 seconds, and stops the whole group if another job has failed. That means
  SIGTERM first, then SIGKILL after 60 seconds. Teardown then runs as normal, because it is
  `if: always()`.

It reads `GET /actions/runs/{id}/attempts/{n}/jobs`. Inside a called workflow, the run id and
attempt are the caller's, and it ignores its own job by matching `runner_name`. A job counts as
failed when any of its **steps** has failed, not just when the job has concluded. A failing build
runs its teardown, about 10 minutes for Android, before its job concludes, and waiting for the job
would give most of the saving away.

`record-outcome` reports a build that was stopped this way as "stopped early (another build
failed)" rather than `failure`. It finds them by the "Stopped early" annotation the stopped step
leaves. This is display only: every decision still uses the raw job results.

### Decisions

- **Cooperative stopping, not cancelling the run.** `gh run cancel` would be simpler, but it
  interrupts whatever is running, including `terraform apply`. A Terraform process killed mid-apply
  can leave its state lock held, and then the `if: always()` teardown fails and strands the
  environment until the 48-hour sweep. So only test commands are ever interrupted. Deploys are
  only ever gated before they start. A run that fails also still concludes `failure`, not
  `cancelled`, which keeps "did someone cancel this?" a meaningful question.
- **Any failed job in the attempt stops the others**, not only the build jobs. During the build
  stage only builds are running, and the rule needs no list of job names to keep in step with
  `release.yml`.
- **The watcher never fails a build on its own account.** If the GitHub API cannot be read, the
  command carries on as if the watcher were not there.
- **A 60-second poll interval.** Four builds polling cost about 240 API requests an hour, well
  inside `GITHUB_TOKEN`'s 1,000 per hour per repository, and a minute's delay is noise against
  10–30-minute savings.

### Choices you had me make

- **Which item this was.** The request was to "add 2 to the design and then do it". The list it
  referred to numbered its rows 1, 3, 4, 5…, because SES had been item 2, so I took the second
  row, "fail releases earlier".
- **The mechanism**: the cooperative check-and-wrap above, not cancelling the run, not running
  the builds in sequence (which would make every release slower), and not reordering them.
- **Android's PR acceptance run uses it too**, because it calls the same `release-build.yml`. In
  that workflow the only other job runs after the build, so in practice it never triggers there.

### Effect

- **AWS:** stopping roughly 100 minutes of acceptance testing across those 7 failed runs would have
  saved about US$0.30. At October's failure rate that is a few tens of cents a month: it is
  proportional to how often releases fail.
- **Time, the bigger win:** a failed release now ends about when the failing build's teardown
  ends, not when the slowest sibling's suite does. That is typically 10–30 minutes sooner, so a
  fix-and-retry loop is shorter.
- **No effect on a release that passes.**

### Verification

- **Script tests:** `.github/actions/fail-fast/test.sh` in mootmaker-release has 15 cases, all
  passing. They cover pass-through of exit status and output, a failed sibling step or job, a
  timed-out sibling, ignoring its own job, refusing to start after a failure, stopping a running
  command and its child processes, killing a command that ignores SIGTERM, and carrying on when
  the API cannot be read.
- **Against real past runs:** `fail-fast check` run as run 37599925866's webapp job reports
  `build-android / build: Build and sign`. Against an unreadable run it carries on.
- **A real Actions run, without a release** (mootmaker-release PR #88, closed unmerged; run
  38084556227):
  - A job failed its step at 60 seconds, then spent 3 minutes in its own teardown.
  - A called workflow shaped like a component build, using the action remotely as the components
    do, had its 10-minute command stopped 62 seconds after that failure. That was three minutes
    before the failing job concluded, and its `always()` teardown still ran.
  - A third build that finished before the failure passed through as success.
  - `record-outcome`'s helper reported the stopped build as "stopped early (another build
    failed)".
- **In a real release:** v5.10.12 passed with every build gated and wrapped. A real release with a
  failing build has not happened yet.

### Changes

- **mootmaker-release:**
  - `.github/actions/fail-fast/` (the action, its script and its tests).
  - `release.yml`: `actions: read` on the four build jobs, because a called workflow gets no more
    than its caller grants. `record-outcome` gains `actions: read`, `checks: read` and the
    stopped-early display.
  - The README.
- **mootmaker-api, mootmaker-webapp, mootmaker-demo-data, mootmaker-android:**
  `release-build.yml` gets `actions: read`, installs the action, adds `fail-fast check` before
  each deploy or create, and wraps the test commands. Android's emulator script has two: Gradle's
  connected tests and Maestro.
- **mootmaker-android `acceptance.yml`:** `actions: read`, for the same caller rule.

## Further measures (not yet designed)

To be written up as later sections, each with its own numbers:

4. **SOA negative-cache TTL.** It is 900 seconds. A longer value could reduce repeated NXDOMAIN
   queries, but public resolvers may not respect it.
5. **Hourly cost data.** Enable it in the management account if daily resolution proves too
   coarse.
6. **Watch Cognito MAU.** Both standing pools are on Cognito's Essentials tier, and every fresh
   test account in every environment counts against the account-wide 10,000-MAU free allowance.
   September was 3,469. Above the allowance, Essentials costs US$0.015 per MAU and Lite
   US$0.0055, so check whether any Essentials-only feature is in use before it matters.
7. **Longer TTLs on the mail records** (MX, DKIM, SES verification; 600 seconds now). Worth cents,
   probably not worth doing.

## Scope / non-goals

The template sections from here on are for Measure 1. Measures 2 and 3 record their own decisions,
choices and verification in their sections above.

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
