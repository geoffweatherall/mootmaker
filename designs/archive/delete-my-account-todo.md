# Delete my account — to-do list

See [delete-my-account.md](delete-my-account.md) for the reasoning behind every decision here.
**This entire piece of work is a prerequisite for [google-sign-in.md](../google-sign-in.md)
— do not start that list until this one reaches production.**

**Status as of 2026-08-28: DONE.** Implemented, deployed to `test` and `production` (full
`deploy.sh` each time, both repos), and manually verified in both environments by Geoff. This
piece of work is fully closed out — [google-sign-in.md](../google-sign-in.md) is now
unblocked to start.

Legend: **[Geoff]** = manual step. **[Claude]** = implementation step.

## Implementation — mootmaker-api

- [x] **[Claude] 1. Add `deleteMyAccount` mutation to `mootmaker.graphql`** — no arguments, derives
      the caller's own Person from the JWT `sub` (same pattern as `Query.myPerson`).
- [x] **[Claude] 2. Implement the handler** — `DeleteMyAccountHandler.java`:
      - Resolves the caller's Person via `PersonRepository.findByCognitoSub`.
      - Guards against reserved demo/e2e accounts via a `RESERVED_ACCOUNT_EMAILS` env var checked
        against the JWT's `email` claim (wired in `lambda.tf` from `aws_cognito_user.demo`/`.e2e`'s
        own usernames, so there's no duplicated literal to drift).
      - Calls Cognito `AdminDeleteUser` **first** (see the handler's javadoc for why this ordering
        was chosen over data-cleanup-first), then deletes every *upcoming* meeting this person
        organises and removes them from every *upcoming* meeting they're on but don't organise, then
        deletes the `Person` item.
- [x] **[Claude] 3. Handle the placeholder-name case** — `ListMeetingsHandler.resolvePerson` now
      substitutes a "Deleted user" placeholder instead of NPE-ing when a meeting's organiser/attendee
      id has no matching Person row (covered by a new test).
- [x] **[Claude] 4. Wire the resolver/permissions**: `deleteMyAccount` registered in
      `ResolverDispatchHandler` and `appsync.tf`; IAM updated (`dynamodb:DeleteItem` re-added,
      `cognito-idp:AdminDeleteUser` added). Self-service only, as decided — no id argument, always
      the caller's own account.
- [x] **[Claude] 5. Deploy mootmaker-api to `test`** (full `deploy.sh`) — done.

## Implementation — mootmaker-webapp

- [x] **[Claude] 6. Add a "Delete my account" action to `SettingsPage.tsx`** —
      `DeleteAccountSection`, with a simple confirmation dialog (decision 3 — no re-auth step) whose
      copy explicitly warns meetings the user organises will be cancelled (decision 1) before they
      confirm.
- [x] **[Claude] 7. On confirm**: calls `deleteMyAccount`, then `signOut()` and navigates to `/` —
      there's no session left to return to.
- [x] **[Claude] 8. Deploy webapp to `test`** (full `deploy.sh`) — done. Live at
      https://www.test.mootmaker.com.

## Manual testing in `test` — Geoff

- [ ] **[Geoff] 9. Delete an account with no meetings** — confirm clean removal: can't sign in again
      with the same credentials, `Person` gone from DynamoDB (or via the app — no longer visible in
      the people list).
- [ ] **[Geoff] 10. Delete an account that organises an upcoming meeting** — confirm the warning
      shows before confirming, and the meeting is gone afterward (check from another account that
      was an attendee — it should also disappear from their view).
- [ ] **[Geoff] 11. Delete an account that only attends (doesn't organise) an upcoming meeting** —
      confirm the meeting still exists for the organiser and other attendees, with this person
      simply removed from it.
- [ ] **[Geoff] 12. Check a past meeting involving a deleted account** — confirm it still loads, and
      shows a placeholder rather than breaking or showing a blank name.
- [ ] **[Geoff] 13. Confirm the demo/e2e accounts refuse deletion** (or the action is hidden/blocked
      for them, depending on how step 2's guard was implemented).

## Production rollout

- [x] **[Claude] 14. Deploy mootmaker-api to production.** Done — full `deploy.sh`, Geoff's manual
      test pass in `test` (steps 9–13) confirmed good first.
- [x] **[Claude] 15. Deploy mootmaker-webapp to production.** Done. Live at https://www.mootmaker.com.
- [x] **[Geoff] 16. Repeat the manual test pass (steps 9–13) against production.** Confirmed good.

## Then, and only then

Move on to [google-sign-in.md](../google-sign-in.md) — its manual GCP setup steps (1 onward)
have no dependency on this work and could technically start in parallel, but the sequencing
decision was to do this first, so hold off unless Geoff says otherwise.
