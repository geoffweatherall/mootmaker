# Sign in with Google

## Summary

Add Google sign-in as an *additional* sign-in method in mootmaker-webapp, alongside the existing
native email/password Cognito flow (which is unchanged) — for `test` and `production` only, never
ephemeral or acceptance/e2e environments. This doc consolidates planning captured on 2026-08-28 in
`../google-sign-in.md`/`../google-sign-in-todo.md` (predating this folder's template) into one
unified design; those two files gained a pointer here and are otherwise left as detailed historical
notes.

## Status

**Drafting** — as of 2026-08-28. Content-wise this reads as close to Ready (a full,
dependency-ordered implementation checklist already exists, and there's no unresolved question that
blocks *starting*), but per this folder's own rule that Status → Ready is a Geoff-gated transition,
it stays Drafting until that's explicit — see "Choices you had me make" below.

**Prerequisite met**: `../delete-my-account-todo.md` is done (deployed and manually verified in
both `test` and `production`) — this work was gated on that and is now clear to start.

## Scope / non-goals

In scope: Google as a second sign-in method, `test` + `production` only. Explicitly **not**
extended to ephemeral environments or the acceptance/e2e Playwright suites — two independent
reasons, either alone would be enough: every ephemeral environment deploys its own fresh Cognito
user pool with a unique hosted domain, which would mean registering/deregistering a redirect URI on
the Google OAuth client on every environment create/teardown; and Google actively blocks
scripted/headless sign-in (reCAPTCHA, "this browser may not be secure"), so Playwright could never
drive the real flow regardless. The webapp feature-detects whether Google sign-in is configured for
the pool it's talking to (a deploy-time env var, same pattern as surfacing the demo user's
password) and hides the button when it isn't — ephemeral/acceptance environments need no
special-casing beyond "don't set that var."

Also out of scope, deliberately: **Google Calendar access**. Considered and rejected requesting the
Calendar scope pre-emptively for a possible future "insert meetings into your calendar" feature —
see Technical considerations for the full reasoning. Revisit only once that feature is actually
being built, as its own incremental-authorization request.

Not building a general federated-identity abstraction for multiple future providers either — a
dedicated `mootmaker-identity-providers` repo was considered and rejected; Google only, for now,
living directly in `mootmaker-api`/`mootmaker-webapp`.

## Trade-offs and decisions

**GCP is two infrastructure layers, only one of which is Terraform-managed.** GCP (Google Cloud)
itself — one project, one OAuth consent screen, one OAuth 2.0 Client ID (Web application type) with
two authorized redirect URIs (one per environment's Cognito hosted domain) — is **created manually
in the GCP Console**, not via Terraform. There is no reliable, fully-supported Terraform resource
for this specific kind of OAuth client; `google_iap_brand`/`google_iap_client` can be repurposed (a
known community workaround) but a GCP project can only ever have one brand, ever, and it can't be
deleted — not worth the permanence risk for what's otherwise a one-time manual step. This is a
single shared GCP identity across both environments, not one per environment.

**No new repo, no Terraform resource for the secret either.** mootmaker-api is the only consumer of
the resulting Client ID/Secret — it's only ever read by `cognito.tf`'s
`aws_cognito_identity_provider` resource. Since it's a single consumer, the secret is stored via a
one-time manual `aws ssm put-parameter --type SecureString` (per environment), with `cognito.tf`
reading it back via a plain `data "aws_ssm_parameter"` lookup — the same loose-coupling pattern
already used there for the SES domain identity.

**AWS/Cognito changes, per persistent environment** (`mootmaker-api/deploy/terraform/cognito.tf`):
an `aws_cognito_identity_provider` (type `Google`, mapping Google's `email`/`name`/`sub` claims);
OAuth config added to `aws_cognito_user_pool_client.webapp` (`allowed_oauth_flows = ["code"]`,
`allowed_oauth_scopes = ["openid", "email", "profile"]`, `callback_urls`, `logout_urls`,
`supported_identity_providers = ["COGNITO", "Google"]`); a new `pre_sign_up` Lambda trigger (see
next).

**Account linking — link at Cognito, not in our own data model.** Chosen over maintaining a
Person-to-multiple-Cognito-users mapping ourselves, because `MyPersonHandler`/`PersonRepository`
already resolve strictly off the JWT's `sub` via `cognitoSub` (see
[data-model.md](data-model.md)'s Cross-references section) — this needs zero changes to that
resolution logic, and reuses Cognito's own `identities` bookkeeping instead of inventing a new one.
Mechanism: a new `pre_sign_up` trigger, handling `triggerSource == "PreSignUp_ExternalProvider"`,
looks up whether a native Cognito user already exists with the incoming email. If found *and*
Google's `email_verified` claim is `true`, it calls `AdminLinkProviderForUser` to link the Google
identity onto that existing user's `sub` — no new Cognito user, no new Person, the existing one is
reused automatically once linked. If not found, this is a genuinely new, federation-only user (see
next). Trusting `email_verified` is safe specifically because Google guarantees it (never hands
back an unverified address) — see Risks for why this must not be copied to a future IdP without
re-checking that guarantee.

**Reverse case already mostly handled by existing Cognito config.** A Google-only user later trying
native sign-up with the same email: `username_attributes = ["email"]` already means Cognito
enforces pool-wide email uniqueness, so the native sign-up attempt fails automatically
(`UsernameExistsException`, possibly masked to a generic message by
`prevent_user_existence_errors`). Needs a **frontend UX change only** — catch that specific case in
`SignUpPage.tsx` and show "this email already has an account — try signing in with Google" instead
of a generic error.

**New federated user needs Person creation outside `post_confirmation`.** Cognito does not fire
`post_confirmation` for federated sign-in at all — it suppresses the confirmation step entirely for
third-party IdPs, only firing for `PostConfirmation_ConfirmSignUp`. That trigger is what
`PostConfirmationCreatePersonHandler` currently relies on (see data-model.md). A brand-new
Google-only user would otherwise sign in successfully with no linked Person. Plan: the same new
`pre_sign_up` trigger's "not found" branch also creates the Person and sets
`custom:class = "standard"` directly, mirroring what `PostConfirmationCreatePersonHandler` does
today.

**Frontend session handling — dual-source check, not a shared storage format.** Deliberately *not*
writing OAuth-obtained tokens into `amazon-cognito-identity-js`'s internal localStorage format
(fragile — undocumented, version-coupled). Instead `cognito.ts` tracks which of two sources the
current session came from: a single small marker (`mootmaker.authMode` = `"native" | "federated"`)
written once, at the moment tokens are first obtained (right after native sign-in/confirm, or right
after the Google callback's code exchange), cleared on sign-out. That marker is read on *every*
session check, not just once at sign-in — matching how `currentIdToken()` already gets called by
Apollo's `SetContextLink` on every GraphQL request rather than being cached, and `loadSession()`
already re-derives everything from storage on every app mount. Cognito refresh tokens aren't tied to
how they were issued, so refreshing goes through the same `InitiateAuth`/`REFRESH_TOKEN_AUTH` call
for both native and federated sessions — only the *first* token acquisition differs between the two
paths.

**Resolved planning decisions (round 2):**
- New, dedicated GCP project — not folded into an existing one.
- Consent screen display name: "Mootmaker."
- Privacy policy: go past Testing mode as soon as possible. A draft has been written
  (`../privacy-policy-draft.md`), accurate to what the app actually collects today (name/email,
  password only for native sign-up, booking data the user creates; no analytics/tracking in the
  webapp; no Google data beyond basic profile). Still needs: a real contact email, an effective
  date, Geoff's read-through/sign-off, an app logo, and a hosted `/privacy` page before it can be
  linked from the consent screen.
- Scopes: staying at `openid email profile` only.

## Choices you had me make

- Keeping Status at Drafting rather than Ready, even though the source planning docs called
  themselves "planning complete" — per this folder's rule that only Geoff moves a doc to Ready.
  Flagging it explicitly since the gating reason here is procedural (a rule from this new template),
  not a real gap in the plan itself — cheap to override if you'd rather just call it Ready now.
- Reorganizing two existing, already-detailed files into this template's shape rather than treating
  either as more authoritative than the other — no content was dropped, only reorganized; both
  originals are still linked at the top for full detail (especially the manual GCP click-by-click
  steps, which read more naturally as prose than forced into this template's sections).

## Open questions

**Blocking**: none — nothing here blocks *starting* the manual GCP prerequisite steps.

**Non-blocking**:
- Whether `sub` is reliably present on the actual `PreSignUp_ExternalProvider` event payload the
  way it is on `PostConfirmation`'s — needs verifying against the real event shape during
  implementation of the trigger (step 8 below), not assumed from documentation alone.

## Impacts on components

- **GCP** (manual, not code) — new project, OAuth consent screen, OAuth 2.0 Client ID with two
  redirect URIs.
- **`mootmaker-api`** — `deploy/terraform/cognito.tf`: new `aws_cognito_identity_provider`, OAuth
  config on `aws_cognito_user_pool_client.webapp`; new `pre_sign_up` Lambda trigger + handler +
  `aws_lambda_permission`, wired into the user pool's `lambda_config`.
- **`mootmaker-webapp`** — new `/auth/google/callback` route with PKCE
  (code_verifier/code_challenge) generation before redirecting out; the `/oauth2/token`
  authorization_code exchange on that route; dual-source session handling added to `cognito.ts`; a
  "Sign in with Google" button on `SignInPage.tsx`, feature-detected behind the deploy-time env var;
  reverse-case UX on `SignUpPage.tsx`; a new `/privacy` route/page (needed before the GCP consent
  screen can link to it, so this specifically should land *before* the manual consent-screen
  configuration step, not after).

## Changes to the domain data model and data storage models

See [`data-model.md`](data-model.md). No DynamoDB schema changes — federated sign-up produces the
exact same `Person` item shape as native sign-up always has. Changes are all on the Cognito side:
a new `aws_cognito_identity_provider` (Google), OAuth flow config added to the existing `webapp`
user pool client, and — worth calling out specifically since it's easy to miss — a **second Lambda
trigger path that creates a `Person` and sets `custom:class`**, alongside the existing
`post_confirmation` one (`pre_sign_up`'s "not found" branch does the same two things
`PostConfirmationCreatePersonHandler` does, for the federated-signup case that never reaches
`post_confirmation` at all). `data-model.md`'s Cognito Lambda-trigger entry needs a new row for this
once shipped. Also new: per-environment SSM `SecureString` parameters holding the Google OAuth
Client ID/Secret — a small addition to the "data storage" surface beyond DynamoDB/Cognito proper,
worth noting in `data-model.md` too once shipped.

## Technical considerations

- **Two distinct redirect URIs, easy to conflate**: (1) on the *Google* OAuth client — Cognito's
  own hosted-domain callback,
  `https://<cognito-domain>.auth.<region>.amazoncognito.com/oauth2/idpresponse` (where Google sends
  the user back to; Cognito receives it here — one per environment, both registered on the same
  Google client); (2) on the *Cognito app client*'s `callback_urls` — the webapp's own route,
  `https://www.<env>.mootmaker.com/auth/google/callback` (where Cognito redirects the user back to
  *after* its own processing). The exact `<cognito-domain>` for each environment is available via
  `terraform output cognito_token_url` (same host as the token endpoint, swap the path).
- Trusting `email_verified` for account linking is safe specifically because Google guarantees it —
  **this pattern must not be generalised to a future IdP without re-checking that guarantee**,
  otherwise it becomes an account-takeover primitive (sign up via that IdP with a victim's email,
  get linked into their existing account).
- Calendar scope was considered and rejected for now: it's classified **sensitive** by Google,
  requiring a manual verification review (video walkthrough, business justification, days-to-weeks)
  before the app can leave Testing mode *at all* — gating the entire consent screen, not just a
  calendar feature, directly conflicting with the "go to production ASAP" privacy-policy decision
  above. Google's reviewers also check that a requested scope is actually exercised by visible
  functionality, so there's no such thing as safely "reserving" it early — and it would show a
  scarier consent screen to every user, not just ones who'd use a future calendar feature. Request
  it later, as its own incremental authorization, when there's a real feature to demo.

## Testing impacts

This is largely **not automatable end-to-end** — Google actively blocks scripted/headless sign-in,
so Playwright can never drive the real OAuth flow (at most it could assert a redirect URL). The
actual test strategy here is a manual pass (see Implementation checklist) covering: a brand-new
Google-only user creates a Person correctly; linking an existing native account to Google lands on
the *same* Person, not a duplicate; the reverse-case error message shows correctly; session
persists across reload/tab-reopen; sign-out clears both native and federated markers; ephemeral/
acceptance environments remain genuinely unaffected.

One slice *is* automatable and worth adding as real acceptance coverage rather than leaving purely
manual: the **feature-detection behaviour itself** — the "Sign in with Google" button's
presence/absence based on the deploy-time env var doesn't require actually driving Google's flow,
just asserting DOM state. Add a case confirming the button is absent on an ephemeral/acceptance
environment (where the var is never set) and present once configured — this protects the one part
of this feature that acceptance environments legitimately share code with, without trying to fake
the parts Google itself blocks.

## Documentation impacts

- `mootmaker-api/README.md` — authentication section, once the `pre_sign_up` trigger and identity
  provider exist.
- `mootmaker-webapp/README.md` — authentication section (dual-source session handling, the new
  callback route).
- `designs/data-model.md` — update the Cognito section once shipped (see above).
- `../privacy-policy-draft.md` → finalized and hosted at `/privacy` before the consent screen can
  link to it (blocks the manual consent-screen configuration step).

## Rollout & migration

No migration needed for existing accounts — this is a purely additive sign-in method; native
accounts are completely unaffected. Rollout is inherently staged by the implementation checklist's
own dependency order: manual GCP setup → `test` (API, then webapp) → manual verification in `test`
→ production readiness check (consent screen out of Testing mode, privacy policy resolved) →
production (API, then webapp) → repeat manual verification in production. Deliberately **never**
rolled out to ephemeral or acceptance/e2e environments at all — that's a permanent scope boundary
(see Scope/non-goals), not a "not yet" phase.

## Risks

- The manual GCP steps are a real bottleneck in the dependency chain — several `[Claude]`
  implementation steps can't start until Geoff completes specific manual steps first (see
  Implementation checklist's dependency notes).
- The OAuth client itself is **not Terraform-managed** — a deliberate decision (see Trade-offs), but
  it means no drift detection or infrastructure-as-code record of its exact configuration; losing
  track of it or misconfiguring it by hand has no automated safety net.
- Account-linking trust in `email_verified` is a real account-takeover primitive if ever
  copy-pasted to a future IdP without re-verifying that guarantee holds for that provider too (see
  Technical considerations) — worth a code comment at the point of implementation, not just this
  doc, so a future change doesn't miss the caveat.
- Production rollout is gated on Google's consent-screen review process for leaving Testing mode —
  the exact timeline for that isn't fully within this project's control, even though the chosen
  scopes (`openid email profile`) avoid the slower *sensitive*-scope review path Calendar access
  would have required.

## Implementation checklist

Legend: **[Geoff]** = manual step, only Geoff can do it. **[Claude]** = implementation step. Ordered
by dependency.

**Manual (GCP) setup:**
1. [Geoff] Create the new GCP project.
2. [Geoff] Find/produce an app logo for the consent screen (check `mootmaker/branding/` first).
3. [Geoff] Get the privacy policy read, filled in (contact email, date), and hosted at a real URL —
   depends on Geoff's sign-off on the draft content, and on the `/privacy` webapp route existing
   (a `[Claude]` step, independent of everything else here — should happen early).
4. [Geoff] Configure the OAuth consent screen (name "Mootmaker", support email, logo, scopes
   `openid`/`email`/`profile` only, privacy policy URL). Depends on: 1-3.
5. [Claude] Look up each environment's Cognito hosted domain (`terraform output cognito_token_url`
   in `mootmaker-api/deploy/terraform`, per environment) to hand Geoff exact redirect URIs.
6. [Geoff] Create the OAuth 2.0 Client ID (Web application type), with both redirect URIs from step
   5 registered on it. Depends on: 1-5.
7. [Geoff] Put the Client ID/Secret into SSM by hand, one `SecureString` parameter each, per
   environment. Depends on: 6.

**API (`mootmaker-api`):**
8. [Claude] Add `aws_cognito_identity_provider` (Google) to `cognito.tf`, reading the Client
   ID/Secret via `data "aws_ssm_parameter"`. Depends on: 7.
9. [Claude] Add OAuth config to `aws_cognito_user_pool_client.webapp`. Depends on: 8.
10. [Claude] Write the new `pre_sign_up` trigger (linking branch + new-federated-user branch) —
    verify the actual `PreSignUp_ExternalProvider` event shape while building this (see Open
    questions). Depends on: 8.
11. [Claude] Wire the trigger into the user pool's `lambda_config` + matching
    `aws_lambda_permission`. Depends on: 10.
12. [Claude] Deploy to `test`. Depends on: 8-11.

**Webapp (`mootmaker-webapp`):**
13. [Claude] Add the `/privacy` route/page (can happen independently, before step 4 needs it).
14. [Claude] Add the `/auth/google/callback` route and PKCE generation. Depends on: 9.
15. [Claude] Add the `/oauth2/token` authorization_code exchange on that route. Depends on: 14.
16. [Claude] Add dual-source session handling to `cognito.ts`. Depends on: 15.
17. [Claude] Add the "Sign in with Google" button to `SignInPage.tsx`, feature-detected. Depends
    on: 16.
18. [Claude] Add reverse-case UX to `SignUpPage.tsx`. Depends on: 8 (Google identities must exist
    in the pool for the case to be reachable).
19. [Claude] Add the automatable button-visibility acceptance case (see Testing impacts).
20. [Claude] Deploy webapp to `test`. Depends on: 14-19, and 12 (API-side must already be live).

**Manual testing in `test`:**
21. [Geoff] New-user case (Person created, `custom:class = standard`, name from Google profile).
22. [Geoff] Linking case (native sign-up email A → sign out → Google sign-in same email A → same
    Person, same bookings).
23. [Geoff] Reverse case (Google sign-in email B → sign out → native sign-up email B → the "try
    Google" message).
24. [Geoff] Session persistence (reload, close/reopen tab, still signed in).
25. [Geoff] Sign-out clears both markers, no stale `mootmaker.authMode`.
26. [Geoff] Confirm ephemeral/acceptance environments remain unaffected (button absent, native
    sign-in works normally).

**Production rollout:**
27. [Geoff] Confirm production readiness (consent screen out of Testing mode, privacy policy
    resolved).
28. [Claude] Deploy `mootmaker-api` to production. Depends on: 27.
29. [Claude] Deploy `mootmaker-webapp` to production. Depends on: 28.
30. [Geoff] Repeat the manual test pass (21-25) against production.

## Definition of done

- Steps 1-30 above all complete, including both manual test passes (`test` and `production`).
- Existing native sign-in/sign-up/forgot-password flows verified unaffected (regression check, not
  just "didn't touch that code").
- Ephemeral and acceptance/e2e environments confirmed unaffected (step 26).
- Documentation impacts above are actually done.
