# Sign in with Google — design & decisions

Status: **planning only — no code changes made yet.** This document records what was decided in
planning discussion on 2026-08-28, so implementation can start (or resume) without re-deriving it.
See [google-sign-in-todo.md](google-sign-in-todo.md) for the actual step-by-step checklist.

## Scope

Google sign-in is added **alongside** the existing native (email/password) Cognito sign-in in
mootmaker-webapp — it does not replace it, and the existing native sign-in/sign-up/forgot-password
code paths are not changed.

**Environments**: only the two persistent environments — `test` (`www.test.mootmaker.com`) and
`production` (`www.mootmaker.com`). Ephemeral environments (`mootmaker-test-infra/create-ephemeral-env.sh`)
and the acceptance/e2e (Playwright) suites deliberately do **not** get Google sign-in wired up:

- Every ephemeral environment deploys its own fresh Cognito user pool with its own unique hosted
  domain, which would mean registering/deregistering a redirect URI on the Google OAuth client on
  every environment create/teardown.
- Google actively blocks scripted/headless sign-in (reCAPTCHA, "this browser may not be secure"),
  so Playwright could never drive the real flow anyway — at most it could assert a redirect URL.

The webapp will feature-detect whether Google sign-in is configured for the pool it's talking to
(an env var supplied at deploy time, the same pattern already used for surfacing the demo user's
password) and simply hide the button when it isn't — so ephemeral/acceptance environments need no
special-casing beyond "don't set that var."

## Architecture: two infrastructure layers

**GCP (Google Cloud) — created once, shared across test + production:**
- One GCP project
- One OAuth consent screen ("brand": app name, support email; needs a privacy policy URL once out
  of Testing mode — mootmaker doesn't have one today)
- One OAuth 2.0 Client ID (Web application type), with **two** authorized redirect URIs registered
  on it — one per environment's Cognito hosted domain (see "Redirect URIs" below)

Not per-environment: one Google identity, registered with both environments' Cognito domains as
redirect targets.

**Known gap**: there is no reliable, fully-supported Terraform resource for this specific kind of
OAuth Client ID (the classic API Console "Web application" OAuth client). `google_iap_brand`/
`google_iap_client` can be repurposed for this (a known community workaround) but a GCP project can
only ever have one brand, ever, and it can't be deleted — not worth the permanence risk for what is
otherwise a one-time manual step. **Decision: create the consent screen and OAuth client manually
in the GCP Console.**

**No new repo** — mootmaker-api is the only consumer of the resulting Client ID/Secret (it's only
ever read by `cognito.tf`'s `aws_cognito_identity_provider` resource), and everything else in this
feature is forced to live in mootmaker-api/mootmaker-webapp anyway (the identity provider resource
and the `pre_sign_up` trigger reference the user pool directly; the callback route and session
handling are inherently webapp code). A dedicated repo (`mootmaker-identity-providers`) was
considered on the assumption that more federated IdPs were coming, but the decision was reversed —
Google only, for now.

Since it's a single consumer, no Terraform resource is needed to hold the secret either — just a
one-time manual `aws ssm put-parameter --type SecureString` (per environment), run right alongside
the manual Google Console step, with `cognito.tf` reading it back via a plain
`data "aws_ssm_parameter"` lookup — the same loose-coupling pattern already used there for the SES
domain identity (`data "aws_ses_domain_identity"`). No changes to `deploy.sh`, no secret passed as a
`-var` on every deploy.

**AWS/Cognito — per persistent environment, in `mootmaker-api/deploy/terraform/cognito.tf`:**
- `aws_cognito_identity_provider` (type `Google`), mapping Google's `email`/`name`/`sub` claims
- `aws_cognito_user_pool_client.webapp` gains OAuth config: `allowed_oauth_flows = ["code"]`,
  `allowed_oauth_scopes = ["openid", "email", "profile"]`, `callback_urls`, `logout_urls`, and
  `supported_identity_providers = ["COGNITO", "Google"]` (today it only does
  `ALLOW_USER_SRP_AUTH`/native)
- A new `pre_sign_up` Lambda trigger (see "Account linking" below)

**Webapp:**
- A new callback route (e.g. `/auth/google/callback`)
- PKCE (code_verifier/code_challenge) generation before redirecting out, since the webapp is a
  public client (no secret) — same as today
- A call to Cognito's `/oauth2/token` endpoint with `grant_type=authorization_code` (the same
  endpoint the acceptance-tests' `client_credentials` client already uses, just a different grant)
- Dual-source session handling in `cognito.ts` (see below)

## Redirect URIs — two different URIs, easy to conflate

There are two distinct redirect registrations, each on a different side:

1. **On the Google OAuth client** ("Authorized redirect URIs"): Cognito's own hosted-domain
   callback, `https://<cognito-domain>.auth.<region>.amazoncognito.com/oauth2/idpresponse` — this
   is where Google sends the user back to; Cognito itself receives it here. One per environment
   (test's domain and production's domain), both registered on the same Google client.
   The exact `<cognito-domain>` for each environment can be read from that environment's own
   Terraform state: `terraform output cognito_token_url` already exposes
   `https://<cognito-domain>.auth.<region>.amazoncognito.com/oauth2/token` — same host, swap the
   path for `/oauth2/idpresponse`.
2. **On the Cognito app client** (`callback_urls` in `cognito.tf`): the webapp's own route,
   `https://www.mootmaker.com/auth/google/callback` (production) /
   `https://www.test.mootmaker.com/auth/google/callback` (test) — this is where Cognito redirects
   the user back to *after* it's done its own processing.

## Decision: account linking — Option A (link at Cognito)

Chosen over maintaining our own multiple-Cognito-users-per-Person mapping. Rationale: it requires
no changes at all to `MyPersonHandler`/`PersonRepository` (both already resolve strictly off the
JWT's `sub` via `findByCognitoSub` — see `mootmaker-api/impl/src/main/java/com/mootmaker/handler/MyPersonHandler.java`),
and it reuses Cognito's own bookkeeping (the `identities` attribute) rather than inventing a new
one.

New `pre_sign_up` Lambda trigger, handling `triggerSource == "PreSignUp_ExternalProvider"`:
- Look up whether a native Cognito user already exists with the incoming email.
- If found **and** Google's `email_verified` claim on the incoming identity is `true`: call
  `AdminLinkProviderForUser` to link the Google identity onto that existing native user's `sub`.
  No new Cognito user, no new `Person` — the existing one is reused automatically once linked.
- If not found: this is a genuinely new, federation-only user. See "New federated user" below.

Trusting `email_verified` is safe specifically because Google guarantees it (it won't hand back an
unverified address). This pattern should not be generalised to a future IdP without re-checking
that guarantee — otherwise it becomes an account-takeover primitive (sign up via that IdP with a
victim's email, get linked into their existing account).

**Reverse case** (Google-only user later tries native sign-up with the same email): already
handled by existing Cognito behaviour — `username_attributes = ["email"]` means Cognito enforces
pool-wide email uniqueness, so the native sign-up attempt fails automatically
(`UsernameExistsException`, possibly masked to a generic message by `prevent_user_existence_errors`).
This needs a **frontend UX change only**: catch that specific case in `SignUpPage.tsx` and show
"this email already has an account — try signing in with Google" instead of a generic sign-up
error.

## Decision: new federated user needs Person creation outside PostConfirmation

Cognito does **not** fire the `PostConfirmation` trigger for federated sign-in (it suppresses the
confirmation step entirely for third-party IdPs) — only for `PostConfirmation_ConfirmSignUp`. That
trigger is what `PostConfirmationCreatePersonHandler` currently relies on to create the `Person`
and set `custom:class = standard`. A brand-new Google-only user (the "not found" branch above)
would otherwise sign in successfully with no linked `Person` at all.

**Plan**: the same new `pre_sign_up` trigger's "not found" branch also creates the `Person` and
sets `custom:class = standard` directly, mirroring what `PostConfirmationCreatePersonHandler` does
today. This needs verifying against the actual `PreSignUp_ExternalProvider` event payload during
implementation (specifically: is `sub` reliably present at this point, the way it is in the
`PostConfirmation` event) — flagged in the todo list as something to confirm while building, not a
settled fact yet.

## Decision: frontend session handling — dual-source check, not shared storage format

Confirmed approach: **don't** write OAuth-obtained tokens into `amazon-cognito-identity-js`'s
internal localStorage format (fragile — undocumented, version-coupled). Instead, `cognito.ts`
tracks which of two sources the current session came from, and both are read on every session
check.

**How the "which source" decision behaves — confirmed, this was an open question during planning:**
A single small marker (a dedicated localStorage key, e.g. `mootmaker.authMode` =
`"native" | "federated"`) is **written once** — at the moment tokens are first obtained, either
right after a native `signIn`/`confirmSignUp`, or right after the Google callback's code exchange.
It is cleared on `signOut`, alongside everything else.

That marker is then **read on every session check**, not just once per sign-in — because that's
already how the existing code behaves: `currentIdToken()` is called by Apollo's `SetContextLink`
on **every single GraphQL request** (see `apolloClient.ts`), not cached across the session, and
`loadSession()` re-derives everything from storage on every app mount too. The dual-source check
follows the same pattern: reading one extra localStorage key on each call is cheap (no network
call), and real network calls only happen when a token actually needs refreshing — same cadence as
today. Cognito refresh tokens aren't tied to how they were issued, so refreshing can go through the
same `InitiateAuth`/`REFRESH_TOKEN_AUTH` call for both native and federated sessions regardless of
which flow originally produced the token — only the *first* token acquisition differs between the
two paths.

## Decisions (2026-08-28, round 2)

1. **GCP project**: new, dedicated project for this — not folded into an existing one.
2. **Consent screen branding**: "Mootmaker" as the display name.
3. **Privacy policy**: go past Testing mode as soon as possible. A draft privacy policy page has
   been written — see [privacy-policy-draft.md](privacy-policy-draft.md) — accurate to what the app
   actually collects and does today (name/email, password only for native sign-up, booking data the
   user creates; no analytics/tracking found in the webapp; no Google data beyond basic profile
   accessed). It has two placeholders (contact email, effective date) and flags one real gap worth
   knowing about: account deletion is currently a manual/support-request process, not self-service —
   the draft states that honestly rather than overpromising. See that file's "Notes for Geoff"
   section for the other things Testing→production needs: an app logo, authorized-domain
   verification via Search Console (reduces Google's "unverified app" warning, not strictly
   required for these scopes), and confirmation that Terms of Service is optional (only the privacy
   policy is required).
4. **Scopes: staying at `openid email profile` — Calendar access explicitly deferred, not requested
   now.** Considered and rejected requesting Google Calendar scope pre-emptively for a possible
   future "insert meetings into your calendar" feature, because:
   - Calendar scopes are classified **sensitive** by Google, which requires a manual verification
     review (video walkthrough, business justification, can take days-to-weeks) before the app can
     leave Testing at all — directly conflicting with decision 3's "ASAP" goal, since that review
     would gate the *entire* consent screen, not just the calendar feature.
   - Google's reviewers check that a requested scope is actually exercised by visible functionality
     — requesting Calendar access with no calendar feature built yet is a plausible rejection, not a
     way to "reserve" the scope early. There's no such thing as safely requesting it ahead of need.
   - It would also show a scarier consent screen (asking to manage your calendar) to every user
     signing in, not just the ones who'd use a future calendar feature — hurting trust/conversion on
     the ordinary sign-in path for a feature that doesn't exist yet.
   - **Recommended path when that feature actually gets built**: request the Calendar scope then,
     as a separate, incremental authorization (Google explicitly supports requesting additional
     scopes later, scoped to just that feature, without re-doing the base sign-in) — and go through
     verification review at that point, when there's a real feature to demo.
