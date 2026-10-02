# CloudFormation from the command line via SSO

## Summary

Stop applying [mootmaker-bootstrap-aws-accounts](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts)'s
CloudFormation by hand in the console as the root user. Apply it from the command line using
IAM Identity Center (SSO) credentials instead, in both accounts. The workload account needs
almost nothing new: `WorkloadAdministrator` can already do it. The management account gets two
new, narrow permission sets. One is a **stack operator** that can change only the three existing
management stacks, and only through a CloudFormation service role. The other is **billing
read-only**, so Claude can read the organisation-wide bill. Management write credentials are
never present by default. Getting them is a deliberate step that ends in one-hour credentials
that do not renew. Separately, the SSO session limit goes from 18 to 24 hours.

## Status

**Drafting**, as of 2026-10-03. Nothing has been changed in AWS. Geoff has answered every
blocking question: management write access goes to a second Identity Center user (D7), and the
session length is 24 hours for everything (D8). No blocking questions remain. Content-wise it is
ready for Geoff to promote to Ready. Even after that, AWS changes still need Geoff's explicit
go-ahead (see Implementation checklist).

## How SSO credentials actually work

This section comes before the design because three of the requirements depend on it, and the
behaviour is not obvious.

There are **three different lifetimes**, set in three different places:

| Thing | What it is | Where it is set | Today |
|---|---|---|---|
| **SSO session** | How long one sign-in (`aws sso login`, or the access portal in a browser) stays valid. While it lasts, the CLI can keep getting new role credentials without asking you. | Identity Center **Settings → Authentication**, in the management account. Console only. **One value for the whole Identity Center instance**: every user, every account and every permission set shares it. | 18 hours |
| **SSO access token** | The local proof of that session, cached in `~/.aws/sso/cache/`. Expires after about an hour and is **renewed silently** with the cached refresh token until the session ends. | Not configurable | ~1 hour, auto-renews |
| **Role credentials** | The actual AWS keys for one role in one account, obtained by calling `sso:GetRoleCredentials` with the access token. | Each permission set's `SessionDuration` (1 to 12 hours) | `PT1H` for `WorkloadAdministrator` |

Three consequences follow, and they shape this design:

1. **The "18 hours" is the SSO session, not anything about the workload account.** Raising it to
   24 hours raises it for every account the user can reach. There is no per-account session
   length. "24 hours for workload, 1 hour for management" cannot be done as a session setting.
   The design gets the same effect another way (see decision D4).
2. **A one-hour permission set does not limit you to one hour.** The CLI fetches new role
   credentials whenever the old ones expire, for as long as the SSO session lasts. That is why
   `WorkloadAdministrator` at `PT1H` already works for 18-hour runs. Giving the management
   permission set `PT1H` on its own would still allow 24 hours of renewals.
3. **An access token is not tied to one account.** It belongs to a *user*, and it can get role
   credentials for **every account and permission set that user is assigned**. If your normal
   user is assigned to the management account, then the token cached by your everyday
   `aws sso login` can get management credentials. This is true whatever `~/.aws/config` says.
   `config` only decides what the CLI does *automatically*. Anything that can read
   `~/.aws/sso/cache/` can call `aws sso get-role-credentials` directly, and that includes
   Claude, which runs as you.

**Two credentials at once** is normal and well supported. Each named profile in `~/.aws/config`
points at an account and a role, and `--profile` or `AWS_PROFILE` picks one per command. The
`[default]` profile is used when neither is given, which is why every `deploy.sh` in this
workspace reaches the workload account without any flags. Adding management profiles does not
change what `[default]` does.

## Scope / non-goals

**In scope**

- Applying all six existing templates from the CLI: three in each account.
- Two new management-account permission sets (stack operator, billing read-only) and the
  CloudFormation service role the stack operator works through.
- A wrapper script for applying a stack safely: change set, review, then execute.
- A helper script for getting short-lived management credentials.
- Raising the SSO session duration from 18 to 24 hours.
- Local guardrails that keep Claude away from management write credentials.

**Non-goals**

- **Automating these stacks in CI.** Account guardrails stay human-applied. This removes the
  root login, not the human.
- **Removing root as break-glass.** Root stays the fallback if Identity Center breaks, as both
  account READMEs already say. Root also stays the *only* way to change management-account
  access itself (see D3). That is deliberate.
- **Moving Identity Center administration to a delegated member account.** AWS recommends this for
  larger organisations. Here it would add a third account to defend, and permission sets assigned
  to the management account can only be managed from the management account anyway.
- **Getting the console-only settings into templates.** The session duration and the IAM billing
  access toggle have no CloudFormation resource and stay one-off manual steps.
- **A management console role for general use.** Both new permission sets work in the console
  too, but nothing here is designed for browsing the management account.

## Trade-offs and decisions

**D1. Workload account: use `WorkloadAdministrator` as it is.** Its allow-list already includes
everything the three workload templates touch (`cloudformation`, `iam`, `lambda`, `events`, `sns`,
`logs`, `budgets`). `workload-account/README.md` already says "root isn't required for this". All
three workload stacks are in `us-east-1`, inside the region lock (checked read-only 2026-10-03).
None of them uses a service role. No permission change is planned. If the first CLI update hits a
denial, the fix is to add to the allow-list in both `scp-guardrails.yaml` and
`identity-center.yaml`, as for any other new service.

**D2. Management account: the stack operator changes things only through CloudFormation.** The
permission set `ManagementStackOperator` gets:

- `cloudformation:*` limited to the ARNs of the three existing stacks (`scp-guardrails`,
  `billing-alert`, `identity-center`), plus account-wide read for validation, `DescribeStacks`
  and `GetTemplate`;
- `iam:PassRole` on exactly one role, `mootmaker-management-cloudformation` (described below);
- **no** `organizations`, `sso`, `identitystore`, `budgets` or `iam` write of its own.

The changes are made by the **service role**, `mootmaker-management-cloudformation`, an IAM role
in the management account that only `cloudformation.amazonaws.com` can assume. It holds only the
write actions those three templates need: Organizations policy management (create, update, attach,
detach and delete policies), Identity Center permission sets and account assignments, Identity
Store groups and memberships, and Budgets view and modify. The exact list is in Technical
considerations.

Why use a service role instead of putting the write permissions on the permission set:

- **Every management change goes through a stack.** That means a template in git and a reviewed
  change set. You cannot make one-off console or CLI edits as the operator, and that kind of edit
  is how the console stacks and git could drift apart.
- **A leaked set of operator credentials can do very little.** It can update three stacks. It
  cannot call `organizations:*` or `sso:*` directly.
- This matches the user's request: the role supports "what is needed for CloudFormation updates",
  and nothing beyond that.

**D3. Neither role can change who has access to the management account.** Whoever can edit
permission sets in an organisation can grant themselves anything. That is built into Identity
Center. The service role therefore carries explicit denies:

- `sso:CreateAccountAssignment`, `sso:DeleteAccountAssignment` and `sso:ProvisionPermissionSet`
  are denied on the resource `arn:aws:sso:::account/339140804537`. A stack cannot grant,
  provision or remove anything in the management account.
- All `sso:*PermissionSet*` actions are denied on the ARNs of the two new management permission
  sets. Their policies cannot be edited.

The two new permission sets, their assignments and the service role go in a **new stack,
`management-access.yaml`**. It is not added to `identity-center.yaml`. The operator's
`cloudformation:*` scope does not include this stack, and it also has an explicit deny on it. So
`management-access` can only be created or changed by root, in the console, the same way as
today. This happens rarely and keeps root involved where it matters.

What this leaves possible, and accepts: the operator can still widen `WorkloadAdministrator` or
loosen the SCPs. Either change only affects the workload account, which is exactly what those
stacks are for. Root can already do the same today, with much more besides.

**D4. "One hour for management" means one-hour credentials that do not renew.** The session
length is shared across the instance (see "How SSO credentials actually work"), so the one-hour
limit comes from how management credentials are obtained:

- Both management permission sets use `SessionDuration: PT1H`.
- The stack operator is **not** in `~/.aws/config` at all. A helper script,
  `with-management-credentials.sh <command…>`, does the following:
  1. Signs in using a throwaway `HOME` (a temporary directory holding a minimal AWS config), so
     the management token never reaches `~/.aws/sso/cache/`.
  2. Exports one set of one-hour role credentials into the environment of `<command>` only.
  3. Runs `aws sso logout` inside that throwaway `HOME`. This ends that sign-in on the server,
     not just locally. Then it deletes the directory.

  The credentials then expire within an hour, nothing can renew them, and nothing persists
  afterwards. Getting them again means signing in again in the browser, with MFA. That is the
  "specific step" the user asked for.
- The SSO session duration goes to **24 hours** for everyday workload use. Because the helper ends
  its own sign-in straight away, the 24-hour limit never applies to it.

**D5. Billing read-only is a separate permission set from the stack operator.** The two are used in
very different ways. The operator is used rarely, by Geoff, with deliberate steps. Billing read is
meant for Claude to use during normal sessions. If they were combined, Claude would need the
deliberate step every time it checked the bill, or the operator would lose its protection.
`ManagementBillingReadOnly` is assigned to Geoff's **normal** user and sits in `~/.aws/config` as
a named profile, `mootmaker-billing`, which is never `[default]`. It renews within the normal
session like any other profile. That is fine for a role that cannot change anything.

It is a custom inline policy, not the AWS-managed `AWSBillingReadOnlyAccess`. The managed policy
also grants payment methods, tax registrations and account contact details. None of those help
explain the bill, and payment details are exactly what should not be readable from a token on a
laptop. Granted: Cost Explorer read (`ce:Get*`, `ce:Describe*`, `ce:List*`), Budgets view, Free
Tier usage (`freetier:Get*`), and bills and invoices read (`billing:Get*`, `invoicing:Get*`,
`invoicing:List*`). Not granted: `payments:*`, `tax:*`, `account:*` and anything that writes.

What it adds over the workload account's own `ce:*`: organisation-wide consolidated cost, the
management account's own spend, the actual invoice, and **Free Tier usage, which AWS tracks at the
organisation (payer) level**. The free-tier questions from the October cost investigation (Cognito
MAU, for example) can only be answered properly from the management account.

Claude may query billing **without asking first**, because a normal check is a handful of
US$0.01 calls. Afterwards it states roughly what the check cost. It asks before any check expected
to take more than about 20 calls. *Decided by Geoff, 2026-10-03.*

**D6. A wrapper applies every stack: change set, review, execute.** `deploy-stack.sh <template>`
in the bootstrap repo:

- uses the template's filename (without `.yaml`) as the stack name, matching the existing
  convention;
- runs `aws cloudformation deploy --no-execute-changeset`, prints the change set, and asks for
  confirmation before executing it;
- in the management account, always passes `--role-arn` for the service role;
- passes `--capabilities CAPABILITY_NAMED_IAM` only for templates that need it;
- never overrides parameters unless asked to. `aws cloudformation deploy` keeps an existing stack's
  current parameter values when they are not given. This matters because `identity-center.yaml`'s
  instance ARN, identity store ID and user ID have no defaults.

It works out which account it is targeting from the template's directory, `management-account/`
or `workload-account/`. It refuses to run if `aws sts get-caller-identity` reports a different
account. That catches running a management template with workload credentials, or the reverse.

**D7. The stack operator belongs to a second Identity Center user.** *Decided by Geoff,
2026-10-03.* This follows from point 3 of "How SSO credentials actually work": a token can reach
every assignment its user has. Under this design:

- `ManagementStackOperator` is assigned **only** to a second user, `geoff-management`, email
  `geoff.weatherall+mootmaker-management@gmail.com`. Identity Center needs each user's email to be
  unique; the plus-address still delivers to the same inbox.
- Your everyday user, and so its cached token, has no route to management write access. AWS
  enforces that, not convention. Anything running as you, Claude included, cannot get operator
  credentials from `~/.aws/sso/cache/`.
- MFA is a second TOTP entry in the authenticator app you already use. It is cloud-synced, so it
  inherits the same recovery as everything else. Passkeys were considered and rejected: they would
  add a device dependency for one rarely used user.
- `ManagementBillingReadOnly` stays on your normal user (D5).
- You stay signed in as your normal user all day. The management user is signed in only for the
  moment `with-management-credentials.sh` needs it, in a **private window** (one browser profile
  holds one access portal sign-in at a time). On the command line both sign-ins exist side by side.
  The management one is signed out as soon as its one set of credentials has been taken (D4).
- **Only Geoff runs the helper.** Claude prepares the exact command and Geoff runs it. A Claude
  Code deny rule makes sure of that (Technical considerations). The browser MFA would be a gate on
  its own, but Claude holding management write credentials for the length of a command is
  avoidable, so it is avoided.

**D8. The SSO session is 24 hours, everywhere.** *Decided by Geoff, 2026-10-03.* It is one setting
for the whole instance, so it also covers the browser access portal and console access to
everything your normal user is assigned. Under D7 that no longer includes management write access.
The management user's own sign-ins never last that long, because the helper ends them straight
away (D4).

## Choices you had me make

- **Splitting billing read and stack operator into two permission sets** (D5). You described one
  role. Merging them back is cheap. I split them because one is meant to be used constantly by
  Claude and the other rarely and deliberately, and a single role cannot suit both.
- **A CloudFormation service role, not write permissions on the permission set** (D2). This costs
  one extra IAM role, and the first update of each existing stack has to be made with
  `--role-arn`.
- **A separate `management-access.yaml` stack that only root can change** (D3). This means root
  logs in for any future change to management-account access. That is rare, and I think it is
  the right place to keep root.
- **The narrow custom billing policy instead of `AWSBillingReadOnlyAccess`** (D5). If Claude turns
  out to need something it leaves out, that gets added specifically.
- **Names:** `geoff-management`, `ManagementStackOperator`, `ManagementBillingReadOnly`,
  `mootmaker-management-cloudformation`, profile `mootmaker-billing`, scripts `deploy-stack.sh`
  and `with-management-credentials.sh`. All of these are easy to change before implementation.
- **The workload account gets no service role** (D1). `WorkloadAdministrator` is already an admin
  role bounded by the SCPs, so a service role would add a step without protecting anything.

## Open questions

### Blocking

None. The two that were here, a second user and the session length, are now D7 and D8.

### Non-blocking

1. **Does the Cost Explorer API need the root-only "IAM user and role access to Billing
   information" setting?** That setting definitely controls the Billing *console* for roles in the
   management account. Whether it also controls the `ce` API is to be confirmed on first use. The
   plan is to turn it on anyway, because the bill and invoice views need it.
2. **Exact service-role actions.** The list in Technical considerations comes from the three
   templates' resource types and is a first draft. Expect one or two additions on the first real
   update, as happened with the GitHub Actions deploy role.

## Impacts on components

**mootmaker-bootstrap-aws-accounts** (the only repo with code changes)

- `management-account/management-access.yaml`, **new**. Contains the
  `mootmaker-management-cloudformation` service role, the `ManagementStackOperator` and
  `ManagementBillingReadOnly` permission sets, and their assignments to the management account
  (the operator to `geoff-management`, billing read to your normal user). Creating it needs `CAPABILITY_NAMED_IAM`.
  Root deploys it.
- `management-account/identity-center.yaml`, **unchanged**. Its stack starts being updated by the
  operator through the service role.
- `scp-guardrails.yaml`, `management-account/billing-alert.yaml` and all of `workload-account/`,
  **unchanged**.
- `deploy-stack.sh`, **new**, at the repo root (D6).
- `management-account/with-management-credentials.sh`, **new** (D4).
- `README.md`, `management-account/README.md` and `workload-account/README.md` are rewritten from
  "log in as root, upload in the console" to "run `deploy-stack.sh`". Root steps stay only for
  `management-access.yaml` and the console-only settings.

**Identity Center (console only, management account):** session duration changes from 18 to 24
hours. The second user, `geoff-management`, is created and registers MFA (D7).

**Management account settings (console only, root):** "IAM user and role access to Billing
information" is activated.

**Local workstation (each machine):** `~/.aws/config` gains a `[profile mootmaker-billing]`
section that uses the existing `mootmaker` sso-session. `[default]` does not change. No management
write profile is added, because the helper script carries its own config.

**Claude Code configuration:** a permission deny rule for `with-management-credentials.sh` and for
`sso get-role-credentials` (see Technical considerations). Memory files are updated (see
Documentation impacts).

**Other repos:** none. No `deploy.sh`, Terraform or application code is affected.

## Changes to the domain data model and data storage models

N/A. Account infrastructure only. No Cognito or DynamoDB changes.

## Technical considerations

**Service role actions (first draft, for non-blocking Open question 2):**

- *scp-guardrails:* `organizations:CreatePolicy`, `UpdatePolicy`, `DeletePolicy`,
  `DescribePolicy`, `AttachPolicy`, `DetachPolicy`, `ListPolicies`, `ListTargetsForPolicy`,
  `ListPoliciesForTarget`, `TagResource`, `UntagResource`, `ListTagsForResource`,
  `DescribeOrganization`, `ListRoots`. Deliberately **not** granted: anything to do with accounts,
  delegated administrators, handshakes, `EnablePolicyType`/`DisablePolicyType` or leaving the
  organisation.
- *identity-center:* `sso:` create, describe, update and delete for permission sets; put, get and
  delete for inline policies; attach, detach and list for managed policies;
  `ProvisionPermissionSet` and its status calls; create, delete and list account assignments and
  their status calls; tagging. `identitystore:` create, describe, update and delete groups; create,
  describe, delete and list group memberships; `GetGroupMembershipId`. Account assignment also
  needs `organizations:DescribeAccount` and `ListAccounts`. Provisioning into a *member* account
  happens through that account's Identity Center service-linked role, so the service role needs no
  `iam:` actions. Only provisioning into the management account itself would need them, and D3
  denies that.
- *billing-alert:* `budgets:ViewBudget`, `budgets:ModifyBudget` and budgets tagging.
- **Denies** as in D3. The permission set ARNs are only known after `management-access` exists, so
  the deny on them is filled in with a stack parameter on a second root update, or with
  `!GetAtt` if the role and the permission sets are in the same template. The single-template
  `!GetAtt` route is the plan.

**`aws sso logout` scope.** Normally it signs out *every* cached session. That is why the helper
runs it inside a throwaway `HOME`: there, the only cached session is the management one, so the
everyday workload session is left alone. To verify when the helper is built: after it runs,
`aws sts get-caller-identity` in the default profile should still succeed.

**Region.** All management stacks stay in `us-east-1`, which is Identity Center's home region.
`identity-center.yaml` must be updated in the home region. SCPs do not apply to the management
account, so nothing in the management account is limited by `pAllowedRegions`.

**Existing stacks have no service role yet.** The first CLI update of each management stack
attaches `mootmaker-management-cloudformation`, and CloudFormation keeps using it after that. If
the role is missing or broken, updates fail with a clear error. Root can still update the stack
without a role in the console, so this is never a lockout.

**Before the first CLI update of any stack, compare what is deployed with git.** These stacks have
only ever been applied through the console. Check them with `aws cloudformation get-template`
against the file in git, and run drift detection, before trusting a change set. A difference means
the console had something git did not, and that has to be resolved before the first update, not
discovered from its change set.

**Cost.** Identity Center, IAM roles and CloudFormation are free. **Cost Explorer API calls are
US$0.01 each**, including each page of a paginated response. A normal "how does the bill look"
check is a few calls, so a few cents. A careless loop of queries would not be. The billing
console and invoice reads are free. No recurring charge is added.

**What this leaves behind.** Changes are recorded as CloudFormation stack events and change sets
(change sets accumulate on stacks if they are created and not executed, so the wrapper deletes a
change set you decline). Sign-ins and role use are recorded in CloudTrail event history, which AWS
keeps for 90 days and then discards, at no cost. No trail or log storage is added. The helper's
throwaway `HOME` is deleted on exit, including on Ctrl-C, using `trap`.

**Guardrails for Claude.** These are a backstop, on top of D3 and D7:

- A deny rule in Claude Code settings for running `with-management-credentials.sh` and for
  `aws sso get-role-credentials`. Claude has no legitimate reason to use either.
- The "Terraform/AWS pre-approved" memory is narrowed: its pre-approval covers the default
  profile and `mootmaker-billing` only.

With D7 the deny rule is a second layer: the everyday token cannot reach the operator anyway.

## Testing impacts

There is no application code, so the unit, mocked-integration, e2e and acceptance layers in each
repo's `testing-strategy.md` are **not affected**. The mootmaker-release smoke suite is **not
affected**: nothing it touches changes.

Verification is a set of manual checks against the real accounts. That is the only meaningful
layer for IAM, because the behaviour under test *is* AWS's policy evaluation:

- **Positive:**
  - A no-op `deploy-stack.sh` run against each of the six stacks produces an empty change set.
  - `mootmaker-billing` can run `ce get-cost-and-usage` and `freetier get-free-tier-usage`.
  - The workload default profile still works after the helper has run and logged out.
- **Negative, each must fail:**
  - Operator credentials calling `organizations:CreatePolicy` and `sso:CreatePermissionSet`
    directly (D2).
  - The operator updating `management-access` (D3).
  - A test change set that adds an assignment to account 339140804537, run through the service
    role (D3).
  - `mootmaker-billing` calling `budgets:ModifyBudget` and `payments:ListPaymentInstruments` (D5).
  - The everyday token calling `get-role-credentials` for
    `ManagementStackOperator`.
- **Expiry:** an hour after running the helper, its credentials fail, and no file for that session
  remains in `~/.aws/sso/cache/`.

## Documentation impacts

- **mootmaker-bootstrap-aws-accounts:**
  - `README.md`: the "Configuring AWS access" section gains the `mootmaker-billing` profile and
    corrects the session length.
  - `management-account/README.md`: all three "Deploying" sections become CLI steps; a new section
    covers `management-access.yaml` (root only, and why); the "Do I still need a break-glass IAM
    role?" section is reworded to say what root is still needed for.
  - `workload-account/README.md`: "Deploying" becomes CLI steps.
  - `AGENTS.md`: the "Working here" section notes that management changes go through
    `deploy-stack.sh` and the service role, and that agents never run the management credentials
    helper.
- **`identity-center.yaml`'s `pSessionDurationIso8601` description** mentions the session length
  only indirectly. Check its wording still holds at 24 hours.
- **Claude memory:**
  - `reference_cloudformation_stack_naming` still says these stacks are console-only, root-run and
    "not something to run via CLI". Rewrite it.
  - `project_sso_session_18h_autorefresh` changes to 24 hours and gets a pointer to this design's
    explanation of the three lifetimes.
  - `feedback_terraform_aws_preapproved` is narrowed as described in Technical considerations.

## Rollout & migration

There are no environments involved; this is applied once, to the two real accounts. Order matters,
because each step depends on the one before:

1. Make the console-only changes (session duration, billing access toggle, and the second user
   for D7). Each takes effect immediately and can be undone on its own.
2. Root creates `management-access` in the console. This is the last routine root deployment.
3. Verify the new access using read-only operations first (`DescribeStacks`, Cost Explorer).
4. Compare each deployed stack with git (Technical considerations), then do a no-op CLI update of
   each one. For the management stacks, this is also what attaches the service role.
5. Run the negative checks from Testing impacts.
6. Rewrite the READMEs. From then on, the console root path is documented only for
   `management-access` and break-glass.

Nothing is migrated, and the existing stacks keep their names and parameters. Reversing it is
cheap: delete the `management-access` stack and carry on with root in the console as today.

## Risks

| Risk | Likelihood | Effect | Mitigation |
|---|---|---|---|
| The service role lacks an action, so a stack update fails part-way and rolls back | Medium, the first time | Update rolls back; no lockout | CloudFormation rolls back automatically. Add the action through a root update of `management-access`. |
| A bad `identity-center` update breaks `WorkloadAdministrator` | Low | Workload CLI access is lost until it is fixed | The operator lives in a different stack and belongs to a different user, so it can still fix `identity-center`. Root is the fallback. |
| A bad `management-access` update breaks the operator itself | Low | The CLI path is lost | Only root changes that stack, and root is the fallback. This is the same position as today. |
| A token on the workstation gets management write access | Low | Changes to SCPs and the workload permission set, but not to management access (D3) | D3, D7, the helper's logout, and the Claude deny rule. |
| The 24-hour session widens exposure from a stolen laptop session | Low | Six extra hours of workload access | Accepted for convenience. Workload is bounded by the SCPs, and management write access is outside the session (D7). |
| Cost Explorer queries add up | Low | Cents per check | Covered by the spending memory. A per-call cost is noted for Claude. |

Nothing here is hard to reverse. The one step that gets close is the second Identity Center user,
and deleting that user undoes it.

## Implementation checklist

Do not start until Status is Ready **and** Geoff has given explicit instructions for the AWS
changes.

1. [Geoff] Promote Status to Ready.
2. [Claude] Write `management-access.yaml`, `deploy-stack.sh` and
   `with-management-credentials.sh` on `feature/cloudformation-from-cli-via-sso` in
   mootmaker-bootstrap-aws-accounts. Lint with `cfn-lint`. Run
   `aws cloudformation validate-template` from the workload account, which is read-only.
3. [Claude] Read-only: compare the workload stacks' deployed templates with git (`get-template`)
   and report any differences.
4. [Geoff] Console, management account, root: set the session duration to 24 hours and activate
   IAM billing access. Create `geoff-management` with its plus-address email, then sign in once in
   a private window to set its password and add a TOTP entry in the existing authenticator app.
5. [Geoff] Console, root: create the `management-access` stack (`CAPABILITY_NAMED_IAM`). It takes
   `geoff-management`'s user ID for the operator assignment and your normal user ID for billing.
6. [Geoff] Add `[profile mootmaker-billing]` to `~/.aws/config` on each machine.
7. [Claude] Verify `mootmaker-billing` positive and negative checks (step 3 of Rollout).
8. [Geoff + Claude] Run `with-management-credentials.sh` and compare the management stacks with
   git. Claude prepares the commands and Geoff runs them: Claude does not run the helper.
9. [Geoff] No-op `deploy-stack.sh` of each management stack, which attaches the service role.
10. [Claude, after Geoff's go-ahead] No-op `deploy-stack.sh` of each workload stack.
11. [Geoff + Claude] Negative checks from Testing impacts.
12. [Claude] Documentation impacts: READMEs, `AGENTS.md`, the Claude Code deny rule and the memory
    updates.
13. [Claude] Status → Shipped, then move this design to `archive/`.

## Definition of done

- All six stacks have had a CLI update with an empty change set, made through `deploy-stack.sh`.
  The three management stacks were updated through the service role.
- Every positive and negative check in Testing impacts has been run, and its result recorded in
  the PR.
- The SSO session duration is confirmed at 24 hours, by a session still valid after 18.
- The helper's one-hour expiry and the survival of the workload session have both been checked.
- The READMEs, `AGENTS.md`, the Claude Code deny rule and the memory files are updated, not just
  planned.
- No root login is needed for any of the three existing management stacks.
