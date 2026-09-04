# Account security

**Deliberately a placeholder.** This exists so the work is not forgotten, and to hold the
groundwork a future session would otherwise have to re-derive. It is not a complete design and
should not be built from as-is.

## Summary

Modernise and validate how accounts are secured and recovered — across **two populations that are
easy to blur and shouldn't be**:

1. **MootMaker's own end-user accounts.** The Cognito user pool: how someone proves they are who
   they say (today a password, possibly a passkey tomorrow) and how they get back in when that
   fails (today a code emailed to a verified address, which is the only thing standing between an
   attacker with mailbox access and a full account takeover).
2. **The operator accounts that own the infrastructure.** GitHub, both AWS accounts' root users,
   AWS SSO, the domain registrar, and the email address underneath all of them. The question here
   is blunter: **if the phone is lost or destroyed, is everything recoverable — and has that ever
   been checked?**

They share a subject and almost nothing else. Population 1 is a product feature with acceptance
tests; population 2 is a personal operational risk with no code, no tests, and a much worse failure
mode — a locked-out root user cannot be fixed by shipping a patch. They are together here because
the answer to both is the same discipline, but they may well split into two documents once scope
is real.

"Validate" carries as much weight as "modernise" in both. Several properties below are believed
rather than demonstrated.

**Status:** Drafting — 2026-09-04. Placeholder; no work has started.

## Scope / non-goals

Not settled yet — the point of the placeholder. First pass at the boundary:

**Probably in scope**
- Passkeys (see Technical considerations for what they are and why they are the interesting option)
- MFA, which the user pool does not currently have in any form
- The password policy, currently loosened deliberately for the demo
- The recovery path end to end, including what happens when the email address itself is
  compromised or lost
- Cognito threat protection (the feature formerly called advanced security), currently not enabled
- Token lifetimes, currently left at Cognito's defaults with no deliberate choice recorded
- Session and sign-out behaviour across devices

**In scope, and the reason this design has a deadline**
- **Recovering every operator account after losing the phone.** MFA on a single device is a single
  point of failure for the whole project, and unlike everything else here it cannot be fixed after
  the fact. See "Operator account recovery" under Technical considerations for the inventory,
  including the accounts that are easy not to think of.

**Probably not in scope**
- Authorization — the `custom:class` standard/admin boundary is a separate concern and already has
  its own reasoning in `cognito.tf` and use-case section L
- Social sign-in, which is [`google-sign-in.md`](google-sign-in.md)'s job, though the two designs
  will need to agree on what "an account" means once one identity can have two sign-in methods
- Deleting an account, already shipped
  ([`archive/delete-my-account.md`](archive/delete-my-account.md))

## Trade-offs and decisions

None yet. Every real decision is still open.

One constraint that will shape all of them, recorded now so it is argued with rather than
forgotten: **MootMaker is a public demo whose sign-in details are published on its own home page.**
The password policy is loose *on purpose*. So the goal is not "make this as secure as a bank" —
it is to be deliberate about which weaknesses are chosen and which are merely inherited, and to
have evidence for the difference. A hardening pass that quietly breaks the ability of a stranger
to try the demo would have missed the point.

## Choices you had me make

- **The name.** "Account security" rather than something longer naming authentication and recovery
  separately. Recovery is genuinely half the subject and a short name risks it being forgotten, so
  the Summary leads with both halves to compensate. Rename freely if it reads wrong.
- **Placeholder shape.** I filled in the current-state facts (below) rather than leaving the whole
  document empty, on the grounds that the expensive part of picking this up later is rediscovering
  what is already configured — not writing prose. Everything requiring a judgement is left open.

## Open questions

### Blocking

- [ ] **What is the actual threat model for a public demo?** Nearly every decision below depends on
  it and none of them can be sensibly made first. The honest answer might be "protect the AWS bill
  and the ability to demo, nothing else", which would make several options below unnecessary — and
  that is a perfectly good outcome for this question to reach.
- [ ] **Is this about the demo, or about demonstrating competence?** A different question with a
  different answer. The demo does not need MFA. A portfolio piece that visibly reasons about
  authentication might. Worth being explicit, because the two justify very different amounts of
  work.
- [ ] **Which of the operator accounts actually exist, and where do their recovery factors point?**
  The inventory below is assembled from what this project demonstrably uses; only Geoff can confirm
  what is really registered against each, and whether the recovery email and phone are themselves
  recoverable. **This is the one blocking question with a clock on it** — every day it stays
  unanswered is a day the single-device risk is live.

*Note: the operator-recovery half does not need the threat-model question above answered first.
"Can I get back in?" has the same answer whatever the threat model is, so it should not wait behind
the product-side questions.*

### Non-blocking

- [ ] Do passkeys and the published shared demo account coexist sensibly, or does a passkey imply a
  per-person account in a way that conflicts with the demo model?
- [ ] Does anything here need to change for `mootmaker-android`, which has no code yet?

## Impacts on components

Not enumerated yet. The surface is at least:

- `mootmaker-api/deploy/terraform/cognito.tf` — the user pool, its policies, and the webapp client
- `mootmaker-webapp` — the sign-in, sign-up and forgot-password pages, and `AuthProvider`
- `mootmaker-email-testing` — the real-email pipeline the recovery tests depend on
- `docs/reference/use-cases.md` sections A, B and C

## Changes to the domain data model and data storage models

Unknown. Probably Cognito-side only (user pool attributes and configuration) with no DynamoDB
change, since `Person` is keyed off the Cognito sub and none of this changes that — but that should
be confirmed rather than assumed, especially if an identity can end up with more than one
credential.

## Technical considerations

### What passkeys are

A passkey is a **public-key credential stored on a device or in a password manager**, replacing the
password entirely rather than adding a second step to it. Sign-in works by the site sending a
challenge, the device signing it with a private key that never leaves the device (released only
after a local gesture — fingerprint, face, or device PIN), and the server verifying that signature
against the public key it registered earlier.

The properties that matter:

- **There is no shared secret to steal.** The server stores only a public key, so a breach of it
  yields nothing replayable.
- **They are bound to the site's origin**, which makes credential phishing structurally
  ineffective rather than merely discouraged — the device will not sign a challenge for a
  look-alike domain.
- **They typically sync** through the platform keychain (iCloud, Google Password Manager, 1Password
  and so on), which is what makes them usable rather than a lost-device disaster — and is also the
  part with the most nuance, because it moves the trust to the sync provider.

The standards underneath are WebAuthn and FIDO2; "passkey" is the name for a discoverable,
usually-synced credential built on them.

**Why it is worth a look here specifically:** Cognito gained native passkey support (as "WebAuthn"
sign-in) as part of its managed-login work, so this may be a configuration and UI change rather
than a from-scratch implementation. That needs verifying against current AWS documentation rather
than trusted from this paragraph — Cognito's authentication features have moved a lot, and some
require the newer managed login pages rather than the SDK-driven flow this app uses today.

### Current state, verified against `cognito.tf` on 2026-09-04

Recorded so the next session starts from fact rather than from re-reading Terraform:

| Property | Today |
|---|---|
| Sign-in | Email as username, SRP (`ALLOW_USER_SRP_AUTH`) plus refresh tokens |
| MFA | **None.** `mfa_configuration` is not set at all, so the pool is `OFF` |
| Threat protection | **Not enabled.** No `user_pool_add_ons` block |
| Password policy | 10 characters, lowercase + number. No uppercase, no symbols — deliberately loose, and commented as such |
| Account recovery | `verified_email` only, priority 1 |
| User-existence leakage | `prevent_user_existence_errors = "ENABLED"` — already correct |
| Self-promotion to admin | Already prevented: `custom:class` is excluded from the client's `write_attributes` |
| Token lifetimes | Cognito defaults; never explicitly chosen |
| Pool deletion protection | Not set |
| Email delivery | SES via `mail.mootmaker.com`, not Cognito's default sender |

Two of those are already right and should not be "fixed" into something worse. The rest are open.

### Operator account recovery — "if I lose my phone"

The failure this half exists to prevent: **one device holds the second factor for everything, and
losing it locks the project's owner out of the project.** Unlike the product-side work, this
cannot be fixed retrospectively — the time to add a second recovery path is while the first one
still works.

The general principle, worth stating once rather than repeating per row: **every account needs at
least two independent ways in, and they must not share a single point of failure.** Two TOTP codes
in the same authenticator app on the same phone are one factor, not two. A recovery email that
itself requires the lost phone is not a recovery path.

**Inventory.** Assembled from what this project demonstrably uses — the ones marked *easy to miss*
are the point of writing it down, since the obvious accounts tend to get handled and the ones
underneath them do not:

| Account | Why losing it hurts | Recovery to verify |
|---|---|---|
| **AWS root — workload account (431071856068)** | Owns `test`, `production`, every Lambda, table, and the Terraform state bucket | Root MFA devices registered; root email reachable without the phone. AWS supports **multiple MFA devices per root user** — registering a second is the single highest-value action here |
| **AWS root — management account** | Owns the Organization, the SCP guardrails, and Identity Center itself | Same. Also: as the Organization management account, it can perform **centralized root access management** over member accounts, which is a recovery path *into* the workload account and worth knowing exists |
| **AWS IAM Identity Center (SSO)** | The daily driver — `aws sso login`. Losing it stops all deploys | Whether the SSO user's MFA is separate from root's, and whether a root user can restore it |
| **GitHub (`geoffweatherall`)** | All eleven repos, the release pipeline, `RELEASE_TAG_PAT` | **Recovery codes downloaded and stored somewhere that is not the phone** — the single most commonly skipped step. Also whether a second factor (security key) is registered |
| **The email address behind all of the above** | *Easy to miss.* It is the recovery root for everything else — whoever controls it can reset the rest | Its own 2FA and *its* recovery path. If it is Gmail and 2FA is the lost phone, this is the true single point of failure, not any individual account below it |
| **Domain registrar for `mootmaker.com`** | *Easy to miss.* Losing the domain loses the site, the SES identity, and `noreply@mail.mootmaker.com` — which is Cognito's sender, so end users' password recovery breaks too | Registrar login MFA and recovery. Also whether the registrar's contact email is one of the above |
| **Authenticator app itself** | *Easy to miss.* If TOTP seeds live only on the phone with no cloud backup, every TOTP-protected account above fails at once | Whether seeds are backed up or the app syncs; whether backup is encrypted with a key that is itself recoverable |
| **Password manager, if used** | *Easy to miss.* Its master credential is the root of everything stored in it | Emergency access / recovery kit, stored offline |
| **Anthropic / Claude account** | Not infrastructure, but this workflow depends on it | Recovery factors |

**The recurring shape** is worth naming because it is what makes this hard to reason about: these
accounts form a **graph, not a list**. The registrar's recovery goes to the email; the email's
recovery may go to the phone; AWS root's recovery goes to email *and* phone. A single lost device
can cascade through several of them at once, and checking each account in isolation will not reveal
that. The check that matters is *"assume the phone is gone — trace every path"*, not
*"does each account have MFA"*.

**Concrete actions that are almost certainly right regardless of how the open questions resolve** —
listed here rather than in the Implementation checklist because they need no design work, only
doing:

- Register a **second MFA device** on both AWS root users
- Download **GitHub recovery codes** and store them off-device
- Confirm the **root account email addresses** are current, monitored, and independently recoverable
- Check whether the **authenticator app's seeds survive the phone**
- Consider a **hardware security key** as the second factor — it is the one option that is neither
  on the phone nor dependent on the email graph above

### The recovery path is the weakest link, and is currently the *only* link

With `verified_email` as the sole recovery mechanism and no MFA, anyone with access to a user's
mailbox can take the account over completely. That is unremarkable for a demo and would be
unacceptable for anything else — the point of writing it down is that it should be a *decision*.

## Testing impacts

Not enumerated yet. Note that this area already has unusually good coverage to build on:
`forgot-password.spec.ts` exercises the real emailed code end to end against real SES→SNS→SQS, and
`sign-up.spec.ts` covers the wrong-code and weak-password paths. Any change here must keep those
green, and "validate" in the Summary largely means extending that suite rather than inventing a new
kind of test.

Worth knowing before touching it: that suite is where the release pipeline's flakiness has
concentrated, so a change here lands on ground that is already moving.

## Documentation impacts

At minimum `docs/reference/use-cases.md` sections A, B and C, plus whatever the decisions above
change in `mootmaker-api/README.md`'s account handling. To be filled in once scope is real.

## Rollout & migration

Unknown, and worth early thought rather than late: anything that changes how existing users
authenticate needs a path for people who already have accounts, and `production` has real ones.
Enrolling a passkey or a second factor cannot be a hard cutover without locking people out.

## Risks

- **Locking real users out of `production`.** The most serious and the most likely, since every
  change here is on the path between a person and their account.
- **Breaking the published demo account**, which would break the front page and the acceptance
  suite together.
- **Hardening theatre** — enabling features that look serious, cost money, and defend against a
  threat model nobody has articulated. The first blocking question exists to prevent this.
- **Being locked out of an operator account while "improving" its security.** Re-registering MFA,
  rotating a recovery email, or moving to a hardware key all involve a window where the old factor
  is gone and the new one is unproven. Every such change should be made with a *second* working
  path already in place, and verified by actually signing in again before the old factor is
  discarded — not assumed from the settings page saying it worked.
- Cognito changes that require pool replacement rather than in-place update. Some settings are
  immutable after creation; which ones needs checking before anything is promised, because
  replacing the pool means every existing user is gone.

## Implementation checklist

Empty by design — this is Drafting. Nothing here is build-from-able yet.

## Definition of done

Not meaningful until scope exists. The floor, whatever the scope turns out to be: the existing
acceptance suite still green against a real deployed environment, the demo account still usable by
a stranger from the home page, and every property claimed to be improved actually demonstrated
against live AWS rather than inferred from Terraform.

For the operator half the bar is different and simpler, and deliberately does not depend on
anything being built: **every account in the inventory has a second, independent way in that has
been used at least once** — actually signed in with, not just registered. A recovery path that has
never been exercised is a belief, not a capability, and this project's own principles already say
so about everything else.
