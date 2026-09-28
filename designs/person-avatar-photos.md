# Person avatar photos

## Summary

Replaces the initials-only `PersonAvatar` with a photo when a `Person` has one. **No upload feature
in this version** — the only source of photos is a small stock library bundled into
`mootmaker-webapp` itself, which `mootmaker-demo-data` assigns to ~90% of the people it generates,
guessing male/female from the first name to pick a plausible-looking photo from the library. Real
sign-ups always keep the initials fallback. `Person` gains one new nullable field, `photoUrl` — a
path relative to the webapp's own origin, not an externally hosted URL, so this piggybacks on the
webapp's existing S3+CloudFront static hosting rather than standing up any new asset infrastructure
in `mootmaker-api` (confirmed there is none today).

## Status

**Building** — 2026-09-28. Drafted and immediately built in one live session: Geoff specified the
key product decisions directly (stock library vs. upload, real-sign-ups-always-fall-back, the 10%
no-photo rate, guess-gender-from-name) rather than reviewing an async draft, which stands in for the
normal Drafting → Ready human gate on this one.

## Scope / non-goals

In scope:
- `Person.photoUrl: String` (nullable) on the schema, and an optional `photoUrl` argument on
  `createPerson`.
- A 24-photo stock library (12 male-presenting, 12 female-presenting), bundled as static files in
  `mootmaker-webapp`.
- `mootmaker-demo-data` assigning a gender-matched photo to ~90% of the people it creates, none to
  the rest.
- `PersonAvatar` rendering the photo when present, with the existing initials circle as the fallback
  — both when `photoUrl` is null and if a referenced file ever fails to load.

Out of scope, deliberately:
- **Any user-facing upload flow.** Real sign-ups get `photoUrl: null` unconditionally, matching
  today's initials-only experience exactly. `PersonAvatar.tsx`'s own doc comment already anticipated
  "user-uploadable photos" as later work; this is not that work.
- **A general name → gender heuristic.** `mootmaker-demo-data`'s `FIRST_NAMES` is a curated, closed
  list of 40 names the tool fully controls — tagging each one's gender directly is more accurate than
  guessing and adds no dependency, so that's what this does. See Trade-offs.
- **Retroactively giving existing demo people a photo.** `mootmaker-demo-data` never mutates a
  Person after creation (see `demo-data-component.md`) — the 90/10 split applies only to newly
  created people, same as every other property it assigns.
- **New S3/CloudFront infrastructure.** There is no asset bucket anywhere in `mootmaker-api` today;
  reusing the webapp's own static hosting avoids creating one for a fixed 24-file library.
- **Moderation/consent.** Doesn't arise in this version — nothing is user-uploaded.

## Trade-offs and decisions

- **`photoUrl` is a path relative to the webapp's own origin (e.g. `"avatars/female-07.jpg"`), not a
  full URL.** The alternative — hotlinking the stock photos' original source (pravatar.cc) at
  runtime — was rejected: depending on a third-party service at runtime for something rendered in a
  deployed product is fragile (rate limits, outages, or the service changing), and it would make
  every ephemeral/test/production environment's demo avatars depend on the same external host being
  up. Vendoring the 24 files into `mootmaker-webapp/webapp/public/avatars/` means they deploy with
  the SPA to its existing S3+CloudFront hosting, work identically on every environment with zero
  per-env configuration, and have no runtime dependency on pravatar.cc at all.
- **The stock photos are CC0** (pravatar.cc is explicitly branded "CC0 Avatar Placeholder"), so
  they're clear to vendor into the repo and deploy publicly, including on `production`.
- **Gender tagging, not a heuristic.** `mootmaker-demo-data`'s 40 `FIRST_NAMES` are a fixed, curated
  list the tool already owns end-to-end (see `SampleData.java`). Tagging each of the 40 with a gender
  directly (`FEMALE_FIRST_NAMES`, a 20-name subset) is strictly more accurate than a general
  name-parsing heuristic for this closed input space, needs no new dependency (the codebase already
  avoids Faker for exactly this kind of reason), and still delivers exactly what was asked: a
  plausible-looking photo per generated name, imperfect on genuinely ambiguous names being an
  accepted trade-off ("doesn't have to be 100% accurate").
- **`createPerson` gains the argument, not a new mutation.** It's the only Person-creation entry
  point `mootmaker-demo-data` calls (this repo never touches DynamoDB directly), and it's already
  admin-only, so an optional argument nobody but demo-data populates today is the smallest change
  that unblocks this.
- **Every "carries every field forward" handler must now carry `photoUrl` too.** `renamePerson`,
  `setPersonAdmin`, and `updateMyPreferences` (and `updateMyName`) each do a full `PutItem` replace of
  the Person record — `mootmaker-api#71` is on record for what forgetting a field in that
  reconstruction looks like (silently wiping it on the next unrelated edit). `photoUrl` joins
  `dateFormat`/`timeFormat`/`weekStart`/`isAdmin` in that list; no new pattern, just one more field in
  an existing one.
- **`PersonAvatar` falls back to initials on image load failure, not just on a null `photoUrl`.**
  There's nothing enforcing that `mootmaker-demo-data`'s filename list and `mootmaker-webapp`'s bundled
  files agree (see Risks) — an `onError` fallback means a drift between the two degrades to "shows
  initials for that person" rather than a broken image icon.

## Choices you had me make

- **Stock photo library now, real uploads later** — Geoff's call, in chat: build the demo-data
  library first; a real upload feature is future work, not part of this change.
- **Real sign-ups always fall back to initials** — explicit: no upload UI exists yet, so there is
  nothing else they could do.
- **10% of generated demo people get no avatar at all** — explicit rate, so the demo data doesn't
  look artificially complete.
- **Guess male/female from the first name, imperfect is fine** — explicit: "does not have to be 100%
  accurate... just don't want it to look silly all the time," which is what shaped the tagged-list
  approach over anything fancier.

## Open questions

None blocking. Worth flagging for whenever a real upload feature is designed: it will need to decide
whether an uploaded photo also becomes a same-shaped relative `photoUrl` (implying uploads land
somewhere the webapp serves statically, which the bundled-library approach here does not set up) or
whether `photoUrl` needs to become a full URL at that point, with the bundled library treated as a
special case. Not decided here — not this version's problem.

## Impacts on components

- **mootmaker-api**: `api/mootmaker.graphql` (`Person.photoUrl`, `createPerson`'s new argument),
  `Person.java` (new record component, `toItem`/`fromItem`/`toResponseMap`), `PersonRepository.java`
  (`createWithNewId` overload), `CreatePersonHandler.java`, and the four handlers that reconstruct a
  full `Person` (`RenamePersonHandler`, `UpdateMyNameHandler`, `SetPersonAdminHandler`,
  `UpdateMyPreferencesHandler`) — carrying `photoUrl` forward in each. Tests for all of the above.
- **mootmaker-demo-data**: `SampleData.java` (gender-tagged first names, the two 12-photo filename
  lists), `DemoData.java`'s `topUpPeople` (90/10 assignment, gendered pick, updated mutation
  document). No bundled image files here — only filename strings; the images live in the webapp.
- **mootmaker-webapp**: the 24 image files under `webapp/public/avatars/`, `PersonAvatar.tsx` (photo
  rendering + `onError` fallback), the `photoUrl` selection added to every Person-shaped GraphQL
  query/mutation (`queries.ts`, `mutations.ts`), regenerated `graphql/generated/`, and the 7 call
  sites that already pass `name`/`size` to `PersonAvatar` now also passing `photoUrl`.
- **mootmaker-android**: no app code exists yet — unaffected.

## Changes to the domain data model and data storage models

`Person` gains one optional attribute, `photoUrl` (string). DynamoDB is schemaless beyond the `id`
key, so no migration: existing items simply lack the attribute, and `fromItem` treats a missing
attribute as `null`, the same null-tolerant pattern already used for `cognitoSubs`/`cognitoEmails`
and (with a default instead of null) `dateFormat`/`timeFormat`/`weekStart`.

## Technical considerations

- **No new infrastructure.** The photo library is static files in the webapp's own bundle, served by
  its existing S3+CloudFront hosting. `mootmaker-api` gets a new nullable schema field and nothing
  else infrastructure-wise.
- **No package-size impact on `mootmaker-demo-data`.** It only ever emits a filename string over
  GraphQL — the image bytes never pass through it or get bundled into its Lambda jar.
- **Cross-repo filename convention.** `mootmaker-demo-data`'s photo-list strings
  (`avatars/male-01.jpg` … `avatars/female-12.jpg`) must match what `mootmaker-webapp` actually
  bundles, with nothing enforcing agreement — the same kind of cross-repo trust `mootmaker.graphql`
  and `webapp/types.ts` used to require before codegen, but with no generator here. Mitigated by
  `PersonAvatar`'s `onError` fallback (see Trade-offs) rather than solved outright.

## Testing impacts

- **mootmaker-api**: unit tests for `Person`'s new field (`toItem`/`fromItem`/`toResponseMap`), the
  `PersonRepository.createWithNewId` overload, `CreatePersonHandlerTest`, and updated expectations in
  `RenamePersonHandlerTest`/`UpdateMyNameHandlerTest`/`SetPersonAdminHandlerTest`/
  `UpdateMyPreferencesHandlerTest` confirming `photoUrl` survives each reconstruction.
- **mootmaker-demo-data**: a distribution test over a large sample confirming roughly 10% get no
  photo and each assigned photo matches the tagged gender of the first name.
- **mootmaker-webapp**: `PersonAvatar` unit/component tests for photo-present, photo-absent, and
  photo-fails-to-load (falls back to initials in all but the first).
- **Acceptance**: no expected impact — every existing test locates elements by role/accessible name,
  and the avatar stays `aria-hidden`. Worth a visual check against a real deployed environment since
  that's the whole point of this change.

## Documentation impacts

`mootmaker/docs/reference/data-model.md`'s `Person` entry gets a `photoUrl` line if it enumerates
fields. Each affected repo's README, if it documents the `Person` shape, gets the same one-line
addition.

## Rollout & migration

No migration. `mootmaker-api` deploys first (additive, backward-compatible: existing callers of
`createPerson` who don't pass `photoUrl` are unaffected). `mootmaker-webapp` deploys next (bundles
the photo library, starts rendering `photoUrl` when present — a no-op for every existing Person,
which all currently have `photoUrl: null`). `mootmaker-demo-data` deploys last and only then starts
assigning photos to newly created people.

## Risks

- **Filename drift between demo-data and webapp** — see Technical considerations. Mitigated, not
  eliminated, by the `onError` fallback.
- **The stock photos read as generic/repeated at scale** — 12 photos per gender means any demo
  environment with more than a couple dozen people will repeat photos. Accepted for v1: this is
  demo data, not a claim that this many named individuals exist.

## Implementation checklist

- [ ] `mootmaker-api`: schema, `Person.java`, `PersonRepository`, `CreatePersonHandler`, the four
      field-carrying handlers, and their tests.
- [ ] `mootmaker-webapp`: bundle the 24 photos, update `PersonAvatar.tsx`, add `photoUrl` to every
      Person-shaped query/mutation, regenerate codegen, thread the prop through all 7 call sites,
      component tests.
- [ ] `mootmaker-demo-data`: gender-tag `FIRST_NAMES`, add the two photo-filename lists, wire the
      90/10 assignment into `topUpPeople`, update its `createPerson` call, tests.
- [ ] Deploy all three to a shared ephemeral environment; run `mootmaker-demo-data` and confirm
      visually in the webapp.
- [ ] Update `data-model.md`/READMEs if they enumerate `Person` fields.
- [ ] Move this doc to Shipped once deployed and verified.

## Definition of done

Unit tests green in all three repos; `mootmaker-api`, `mootmaker-webapp`, and `mootmaker-demo-data`
deployed to one reused ephemeral environment; a demo-data top-up on that environment shows photos on
roughly 90% of newly created people, gender-plausible, the remaining 10% showing initials; a signed-up
(non-demo) person still shows initials; acceptance suite green on that environment.
