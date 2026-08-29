# Delete my account — design & decisions

Status: **planning only — no code changes made yet.**

## Why this exists, and why it comes first

This is now a **prerequisite for Sign in with Google** (see
[google-sign-in.md](google-sign-in.md)/[google-sign-in-todo.md](google-sign-in-todo.md)), decided
2026-08-28: self-service account deletion should exist before Google sign-in ships, rather than
after. Two concrete reasons this ordering matters, beyond just "it's good to have":

- [privacy-policy-draft.md](../../docs/showcase/privacy-policy-draft.md) currently states deletion is a manual,
  support-request process. Shipping Google sign-in first would mean publishing that policy (needed
  for Google's consent screen) with a known gap already baked in, when it doesn't have to be.
- Once Google-linked accounts exist, `AdminDeleteUser` conveniently removes a Cognito user and
  *all* linked identities (native + any federated provider) in one call — so building this now,
  before linked identities exist, doesn't lose anything, and the deletion logic doesn't need to
  think about "which identity/identities" at all. It's Cognito-user-shaped either way.

## What's actually there today

- `Person(id, name, cognitoSub)` — `cognitoSub` links a Person to its Cognito user; null for guests
  with no login (see `Person.java`).
- `PersonRepository.findByCognitoSub` — the only lookup that exists; there's no delete method on
  any repository in the codebase.
- No GraphQL mutation deletes anything, for any type. `deletePerson`/`deleteAccount` would be the
  first delete mutation in the API — there's no existing pattern to mirror, so its permission model,
  error shape, etc. need deciding from scratch (though `updatePerson`'s existing permission rule —
  "the caller's own linked Person, or admin for anyone" — is a reasonable model to reuse).
- A person can be a **meeting organiser** or an **attendee** (`Meeting.organiser`/`Meeting.attendees`).
  Deleting a Person who's referenced by existing meetings is the real design problem here — it's not
  just a single-row delete.
- The **demo user** (`aws_cognito_user.demo`, Terraform-managed) is publicly known and linked to a
  Person created directly by Terraform, not through sign-up. If it were deleted via a self-service
  flow, the public demo login would break until someone reapplies Terraform — worth explicitly
  guarding against.

## Decisions (2026-08-28, round 2)

1. **Meetings you organised**: cancelled (deleted) as part of account deletion. The confirmation
   dialog (see decision 3) must explicitly warn the user this will happen *before* they confirm —
   "All meetings you organised will be cancelled" or equivalent, not a surprise after the fact.
   - **Interpretation I'm applying, not separately re-asked**: "cancelled" sensibly only applies to
     *upcoming* meetings — a past meeting already happened and isn't meaningfully cancellable. Past
     meetings you organised remain as historical records (see the placeholder-name requirement
     below for how they display once your `Person` row is gone). Flag if this reading is wrong —
     easy to change before implementation.
   - **Deferred to a future piece of work, explicitly not part of this one**: notifying attendees
     when a meeting they're on is changed or cancelled. There's no notification mechanism for
     meeting changes anywhere in the app today (the only emails sent today are sign-up
     verification/password-reset, both via Cognito/SES) — this would be new infrastructure, and is
     out of scope for delete-my-account itself. Recorded here so it isn't lost; will get its own
     design pass when picked up rather than being designed as a side effect of this one.
2. **Meetings you only attend**: not addressed by decision 1 (that's about meetings you organise).
   Natural default, not separately asked: remove you from the attendee list of upcoming meetings;
   past meetings retain the historical attendee record (with a placeholder name, same as above).
3. **Confirmation friction**: a simple confirmation dialog — no re-authentication step, no
   type-to-confirm phrase. Matches the lack of any such flow elsewhere in the app today. The dialog
   copy must carry the organiser-meetings warning from decision 1.
4. **Scope**: self-service only. No admin-initiated deletion of other people in this piece of work
   — `deletePerson(id)` for admins is explicitly out of scope here, left for later if ever needed.
   This settles the mutation shape too: `deleteMyAccount` (no `id` argument — derives the caller's
   own Person the same way `myPerson` does, via the JWT's `sub`), not `deletePerson(id: ID!)`.
5. **Last admin**: left unhandled. An admin can delete their own account even if they're the only
   admin, potentially leaving the deployment with nobody able to manage rooms/people. Accepted as an
   edge case for now.
6. **Hard delete, not anonymize.** Removes the person's data from both systems: the Cognito user
   (via `AdminDeleteUser` — removes the native credential and any linked federated identity in one
   call) and the DynamoDB `Person` item. No scrubbed-but-retained record left behind. Matches the
   privacy policy draft's wording ("removed") rather than the weaker anonymize-in-place alternative.
   Resolves cleanly against decisions 1–2 above: upcoming meetings you organised are deleted
   outright (no dangling reference possible — the meeting's gone too); upcoming meetings you attend
   just drop you from the attendee list (no dangling reference). The only remaining dangling
   reference is **past** meetings (organiser or attendee) that outlive your deleted `Person` row —
   these must resolve to a placeholder ("Deleted user" or similar) rather than an unhandled null or
   an unloadable meeting. This is an implementation requirement, not an open question.

## Implementation notes — settled, not open questions

- The **demo/e2e Terraform-managed users must be explicitly excluded** from self-service deletion,
  regardless of everything above — there's no reasonable case for letting the public demo login (or
  the Playwright e2e user) be deletable through this flow. Likely a check against a known
  reserved-username set, or simply the absence of `PostConfirmation`-driven creation as a signal —
  needs a concrete mechanism decided during implementation, but the requirement itself isn't up for
  debate.
- Mutation shape: `deleteMyAccount` (see decision 4) — no arguments, resolves the caller's own
  `Person` via the JWT's `sub`, same pattern as `Query.myPerson`.
