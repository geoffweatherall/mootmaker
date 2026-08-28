# Sign in with Google — to-do list

> **Superseded by [designs/google-sign-in.md](designs/google-sign-in.md)** (2026-08-28) — the
> unified, current design doc, including this checklist's content. This file is preserved as
> historical detail; treat the new file as the source of truth for status and next steps.

See [google-sign-in.md](google-sign-in.md) for the reasoning behind every decision referenced here.
This file exists so work can resume mid-stream without re-reading the whole conversation — keep it
up to date as steps complete.

**Status as of 2026-08-28: planning complete, zero code/infra changes made yet.** Nothing below has
started.

**Prerequisite satisfied**: [delete-my-account-todo.md](delete-my-account-todo.md) is done — deployed
to and manually verified in both `test` and `production` as of 2026-08-28. This work is now clear to
start.

Legend: **[Geoff]** = manual step, only you can do it. **[Claude]** = implementation step. Steps
are ordered by dependency — an item's "depends on" line names what must be done first.

## Resolved decisions (2026-08-28, round 2)

- GCP project: **new, dedicated project.**
- Consent screen display name: **"Mootmaker."**
- Privacy policy: going to production ASAP — draft written, see
  [privacy-policy-draft.md](privacy-policy-draft.md). Still needs: a real support/contact email
  filled in, an effective date, Geoff's read-through/sign-off, and an app logo (check
  `mootmaker/branding/` first).
- Scopes: **`openid email profile` only — Calendar explicitly deferred**, not requested now (see
  google-sign-in.md decision 4 for why). Revisit only when an actual calendar-insert feature is
  being built, as its own incremental-auth request.

## Manual (GCP) setup

- [ ] **[Geoff] 1. Create the new GCP project.**
- [ ] **[Geoff] 1a. Find/produce an app logo** for the consent screen (check
      `mootmaker/branding/` first for something reusable).
- [ ] **[Geoff] 1b. Get `privacy-policy-draft.md` read, filled in (contact email, date), and hosted
      at a real URL** — this needs a page in mootmaker-webapp (a new route, e.g. `/privacy`) before
      it can be linked from the consent screen. Depends on: Geoff's sign-off on the draft content;
      implementation is a small addition to the webapp step list below (not yet itemized — add a
      step there once the content is finalized).
- [ ] **[Geoff] 2. Configure the OAuth consent screen** (app name "Mootmaker", support email, logo
      from 1a, scopes `openid`/`email`/`profile` only, privacy policy URL from 1b). Depends on:
      steps 1, 1a, 1b.
- [ ] **[Claude] 3. Look up each environment's Cognito hosted domain**, to hand you exact redirect
      URIs for step 4. Run per environment: `terraform output cognito_token_url` (in
      `mootmaker-api/deploy/terraform`), take the host, and:
      - test → `https://<host>/oauth2/idpresponse`
      - production → `https://<host>/oauth2/idpresponse`
      Depends on: AWS SSO access to both environments (already pre-approved).
- [ ] **[Geoff] 4. Create the OAuth 2.0 Client ID** (Web application type) in that consent screen,
      with both redirect URIs from step 3 registered on it. Depends on: steps 1–3.
- [ ] **[Geoff] 5. Put the Client ID/Secret into SSM by hand**, one `SecureString` parameter each,
      per environment (`test` and `production`) — e.g.
      `aws ssm put-parameter --name /mootmaker/<env>/google-oauth-client-id --type SecureString --value ...`
      and the same for `google-oauth-client-secret`. No new repo, no Terraform resource for this —
      it's a one-time manual step, same spirit as step 4. Depends on: step 4.

## Implementation — mootmaker-api (Cognito + trigger)

- [ ] **[Claude] 6. Add `aws_cognito_identity_provider` (Google)** to `cognito.tf`, reading the
      Client ID/Secret via a `data "aws_ssm_parameter"` lookup against step 5's parameters (same
      loose-coupling pattern already used there for the SES domain identity), mapping
      `email`/`name`/`sub`. Depends on: step 5.
- [ ] **[Claude] 7. Add OAuth config to `aws_cognito_user_pool_client.webapp`**: `allowed_oauth_flows`,
      `allowed_oauth_scopes`, `callback_urls` (webapp's own `/auth/google/callback`, per
      environment), `logout_urls`, `supported_identity_providers`. Depends on: step 6.
- [ ] **[Claude] 8. Write the new `pre_sign_up` Lambda trigger**: linking branch
      (`AdminLinkProviderForUser` when a native user with matching verified email exists) and
      new-federated-user branch (create `Person`, set `custom:class = standard`, mirroring
      `PostConfirmationCreatePersonHandler`). Verify the actual `PreSignUp_ExternalProvider` event
      shape while building this — see google-sign-in.md's open item 4. Depends on: step 6 (needs
      the identity provider to exist so this trigger source can actually fire in dev/test).
- [ ] **[Claude] 9. Wire the new trigger into the user pool's `lambda_config`** and the matching
      `aws_lambda_permission`. Depends on: step 8.
- [ ] **[Claude] 10. Deploy to `test`** (full `deploy.sh`, per this workspace's "always full-deploy"
      convention). Depends on: steps 6–9.

## Implementation — mootmaker-webapp

- [ ] **[Claude] 10a. Add a `/privacy` route/page** using the finalized content from step 1b. This
      can happen independently of everything else here (no dependency on Cognito/OAuth work) and
      should happen *before* step 2, since step 2 needs a real URL to link to.
- [ ] **[Claude] 11. Add the `/auth/google/callback` route** and PKCE (code_verifier/code_challenge)
      generation before redirecting out. Depends on: step 7 (needs real callback URL registered).
- [ ] **[Claude] 12. Add the `/oauth2/token` authorization_code exchange** on the callback route.
      Depends on: step 11.
- [ ] **[Claude] 13. Add dual-source session handling to `cognito.ts`**: the `mootmaker.authMode`
      localStorage marker, written once at token-acquisition time (native sign-in/confirm, or
      Google callback exchange), read on every `currentSession()`/`currentIdToken()` call. Depends
      on: step 12.
- [ ] **[Claude] 14. Add the "Sign in with Google" button** to `SignInPage.tsx`, feature-detected
      behind a deploy-time env var (hidden when unset — this is what keeps ephemeral/acceptance
      environments unaffected without special-casing). Depends on: step 13.
- [ ] **[Claude] 15. Add reverse-case UX to `SignUpPage.tsx`**: catch the "email already exists"
      error from a native sign-up attempt and show "this email already has an account — try signing
      in with Google" instead of a generic failure. Depends on: step 6 (the case only exists once
      Google identities exist in the pool).
- [ ] **[Claude] 16. Deploy webapp to `test`**. Depends on: steps 11–15, and step 10 (needs the
      API-side identity provider + trigger already live).

## Manual testing in `test` — Geoff

These need a real Google account (or two) and can't be scripted (Google blocks automated sign-in).
Do these after step 16.

- [ ] **[Geoff] 17. New-user case**: sign in with Google using an email that has never touched
      mootmaker before. Confirm: a `Person` is created, `custom:class` is `standard`, display name
      populates from Google's profile.
- [ ] **[Geoff] 18. Linking case**: sign up natively (email/password) with email A, confirm the
      account, sign out. Then sign in with Google using an account whose email is also A. Confirm:
      you land back on the *same* `Person` (same name, same existing bookings) — not a second,
      empty one.
- [ ] **[Geoff] 19. Reverse case**: sign in with Google using a brand-new email B (creates a
      Google-only account per step 17). Sign out. Try to sign up natively with the same email B.
      Confirm: you get the "already has an account, try Google" message from step 15, not a
      confusing generic error.
- [ ] **[Geoff] 20. Session persistence**: sign in with Google, refresh the page, close and reopen
      the tab — confirm you're still signed in (dual-source session check in step 13 is working,
      not just working immediately after the redirect).
- [ ] **[Geoff] 21. Sign-out**: sign out of a Google-linked session, confirm both the native and
      federated markers are cleared (no stale `mootmaker.authMode`, no accidental auto-resignin).
- [ ] **[Geoff] 22. Confirm ephemeral/acceptance environments are unaffected**: spin up (or check an
      existing) ephemeral environment and confirm the Google button is absent, native sign-in still
      works normally.

## Production rollout

- [ ] **[Geoff] 23. Confirm production readiness**: consent screen out of Testing mode (if not
      already), privacy policy resolved. Depends on: open questions above being settled for real,
      not just for `test`.
- [ ] **[Claude] 24. Deploy mootmaker-api to production** (adds the Google identity provider +
      trigger there too — same Terraform, different environment). Depends on: step 23.
- [ ] **[Claude] 25. Deploy mootmaker-webapp to production**. Depends on: step 24.
- [ ] **[Geoff] 26. Repeat the manual test pass (steps 17–21) against production.**
