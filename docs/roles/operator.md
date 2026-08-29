# The operator hat

**The question this role answers: is it running, is it safe, and what does it cost?**

The hat that notices things nobody asked about. Almost everything this role catches is something
that was quietly wrong for a while — a leaked environment, an over-broad IAM policy, a bill that
crept up — because nothing fails loudly when infrastructure is merely wasteful rather than broken.

Security and privacy live here too, rather than in a hat of their own.

## Responsibilities

- Keeping `production` up and behaving.
- Environment lifecycle: creation, teardown, and noticing what has leaked.
- Cost: keeping scale-to-zero true rather than aspirational.
- AWS account guardrails — SCPs, IAM Identity Center, billing alerts.
- Security: authentication configuration, IAM scope, credential handling.
- Privacy: keeping [`privacy-policy-draft.md`](../showcase/privacy-policy-draft.md) accurate to what
  the system actually does.
- Admin tooling for repairing or resetting a deployed environment.

## Owns

| Artifact | Where |
|---|---|
| Environment policy | [`../process/environments.md`](../process/environments.md) |
| Environment mechanics | [`../development/environments.md`](../development/environments.md) |
| Account guardrails | `mootmaker-bootstrap-aws-accounts` |
| Terraform remote state | `mootmaker-bootstrap-terraform` |
| DNS and mail identity | `mootmaker-domain` |
| Environment lifecycle scripts | `mootmaker-test-infra` |
| Admin and demo-data tooling | `mootmaker-tools` |
| Privacy policy | [`../showcase/privacy-policy-draft.md`](../showcase/privacy-policy-draft.md) |

## Starting a session in this role

1. [`../process/environments.md`](../process/environments.md) — the model and the teardown rules.
2. [`../process/principles.md`](../process/principles.md) — the cost section is this hat's mandate.
3. `aws sso login`, then check what is actually deployed. Do not reason from documentation about
   what exists in AWS; look.

```bash
aws s3 ls s3://remote-state-<account-id>/            # every environment with state
aws lambda list-functions --query 'length(Functions)'
mootmaker-test-infra/cleanup-stale-envs.sh           # what has been left behind
```

## Standing checks

Worth doing periodically rather than only when something breaks:

**Has anything leaked?** Any ephemeral environment older than 24 hours is a leak. Four leaked in a
single day in August 2026 and were found the following morning; nothing automated catches this yet.

**Does the bill match the model?** Scale to zero means near-zero when idle. A non-trivial idle bill
means something is running that should not be, and the state bucket is the fastest way to find it.

**Is `production` actually up?** It is the portfolio piece. `curl -o /dev/null -w '%{http_code}'
https://www.mootmaker.com` is the whole check.

**Are there long-lived credentials anywhere?** There should be none. SSO locally, OIDC for anything
automated.

**Does the privacy policy still describe reality?** It was written against the data model as of
2026-08-28 and needs re-checking whenever data handling changes.

## Blast radius

This hat holds the destructive tools, so it carries the rules about using them.

**`database-reset` and `database-repair` can destroy production data.** Production is a demo and its
data is replaceable, which makes this survivable rather than safe. Know which environment you are
pointed at before running either.

**Teardown scripts refuse non-ephemeral names by design.** `teardown-ephemeral-env.sh` will not act
on anything that is not `<kind>-<YYMMDD>-<rand4>`. That rail exists so a typo cannot reach
`production`; do not work around it. Retiring a long-lived environment is a deliberate, manual act.

**Verify teardown against live AWS, not the script's exit code.** And note the known gap: the
teardown script does not remove tools deployed into an environment, so those must be undeployed
separately.

## Definition of done

- No ephemeral environment older than 24 hours exists.
- `terraform plan` shows no unexpected drift for anything long-lived.
- No credentials in the repository, in an environment variable, or in a Terraform variable file.
- Anything changed here is reflected in `environments.md` or the relevant repository README —
  infrastructure knowledge that lives only in someone's head is the failure mode this hat exists to
  prevent.
