# Person avatar upload refactor

## Summary

Avatar photos are currently a static library bundled into mootmaker-webapp, pointed at by a
free-string `Person.photoUrl` that mootmaker-demo-data fills in by convention. This replaces that
with a real upload path owned by the API: a presigned S3 upload, a confirm step that validates and
normalises the image, and a content-addressed object served from an API-owned bucket. The stock
photos move into mootmaker-demo-data, which uploads them through the same API calls a future
webapp upload feature will use. It also fixes the carry-forward problem underneath, by moving
`PersonRepository` off whole-record `PutItem`.

## Status

**Drafting** — 2026-09-29.

## Scope / non-goals

**In scope**

- A two-step upload API (`requestPersonPhotoUpload` / `confirmPersonPhotoUpload`) plus removal.
- A new API-owned S3 bucket for staging and serving person photos, reachable through the webapp's
  existing CloudFront distribution under a dedicated path.
- Server-side validation and normalisation of uploaded images.
- Content-addressed served keys, enabling immutable caching and letting demo-data tell which stock
  photos are already in use.
- Moving the stock photo library out of mootmaker-webapp and into mootmaker-demo-data, grown to
  cover a whole environment without repeats.
- Removing `photoUrl` as an argument to `createPerson`.
- Replacing whole-record `PutItem` in `PersonRepository` with attribute-level `UpdateItem`.

**Explicit non-goals**

- **No webapp upload UI.** The API is designed so the webapp can add one later without a second
  redesign, but no picker, cropper or settings control is built here.
- **No per-person photo history.** One current photo; replacing it simply repoints `photoUrl`.
- **No image CDN features** — no on-the-fly resizing, no format negotiation, no WebP/AVIF. One
  canonical derivative, described below.
- **No change to the initials fallback.** `PersonAvatar` keeps rendering initials when `photoUrl`
  is null or the image fails, unchanged.
- **No avatar for real sign-ups.** `PostConfirmationCreatePersonHandler` still creates people
  without a photo; `me` still does not select `photoUrl`.

## Trade-offs and decisions

These were settled in discussion on 2026-09-29 and should not be re-litigated without new
information.

### Photos are served through the webapp's existing CloudFront distribution

A new API-owned bucket is added as a **second origin** on mootmaker-webapp's existing distribution,
with an ordered cache behaviour for `/person-photos/*`. The alternative — a dedicated distribution
on `photos.<env>.mootmaker.com` — was rejected because it adds a CloudFront distribution and an
ACM certificate to the create-and-destroy cycle of every ephemeral environment, which is a cost
paid every working session. Presigned GET URLs were rejected outright: a URL that changes per
request destroys both browser caching and Apollo's normalised cache identity.

`photoUrl` therefore stays an **origin-relative path**, which is what the webapp already handles.

**The known wart:** `custom_error_response` is distribution-wide, so a photo object that is missing
still returns `index.html` at status 200 rather than a 404 — the same silent failure that produced
the bug this refactor follows. It is much less dangerous now, because the API generates and stores
the exact key it wrote, so there is no longer a hand-written convention duplicated across two repos
that can drift. It is not eliminated. See Risks.

### Cache headers are set by the API, not by the distribution

The API sets `Cache-Control: public, max-age=31536000, immutable` on each served object at
`PutObject` time. The webapp's cache behaviour must use a policy that **honours origin
`Cache-Control`** rather than imposing its own TTL (the AWS managed `CachingOptimized` policy does
this — its default TTL applies only when the origin sends no caching headers).

This is deliberate: how long a photo may be cached follows from how the API names and stores it, so
it is the API's decision. No other component should have to know or assume the storage and naming
strategy in order to get caching right.

### Served keys are content-addressed, on the hash of the *source* bytes

The served object is `person-photos/v1/<sha256-of-uploaded-bytes>.jpg`.

This single choice does three jobs:

1. **`immutable` is honest.** A different image is a different key, so a cached URL can never go
   stale. Replacing a person's photo needs no invalidation.
2. **demo-data can read back what is in use.** It hashes its own bundled file and knows exactly
   what `photoUrl` that file would produce. It fetches every existing person's `photoUrl` and
   excludes the ones already taken. Crucially this depends only on the *source* bytes, which
   demo-data holds — **not** on server-side processing being byte-for-byte reproducible, which
   would have been brittle across an image-library upgrade.
3. **Storage dedupes itself.** Two people with the same photo share one object.

The `v1/` segment is the **processing version**, and exists precisely because the key is the hash
of the input rather than the output. If normalisation ever changes (different dimensions, encoder,
quality), bump to `v2/`: existing URLs keep serving the bytes they always served, and new uploads
get new keys. Without it, `immutable` would be a lie the first time the resize changed.

### Upload is a presigned PUT with a synchronous confirm

Three calls: `requestPersonPhotoUpload` returns a presigned URL; the client PUTs the bytes straight
to S3; `confirmPersonPhotoUpload` validates, normalises, stores and sets `photoUrl`, returning
errors synchronously in the project's usual `errors: [...]` result shape.

Fully async processing (S3 event → processor → subscription) was rejected as disproportionate. For
a ≤2 MiB avatar the decode-and-resize is milliseconds against a 15 s timeout, and rejection
feedback would otherwise have to travel back over a subscription or live in a status field on
`Person` — materially more API surface for no gain at this size.

The existing `daysInvalidated` subscription precedent (carry a signal, let the client refetch) is
noted and deliberately not used here: there is nothing to signal, because the mutation returns.

### `createPerson` loses its `photoUrl` argument

Setting a photo becomes the upload flow's job, and only the upload flow's job. This restores
`createPerson(name: String!)` to its original shape and removes the one place where an unvalidated
client-supplied path could reach storage. demo-data creates a person and then uploads, exactly as
the webapp would.

### `PersonRepository` moves from `PutItem` to `UpdateItem`

This was raised as possibly redundant once photos have a dedicated mutation. It is not. Today every
handler that changes a person rebuilds the whole `Person` record and `PutItem`s it, so
`RenamePersonHandler`, `UpdateMyNameHandler`, `SetPersonAdminHandler` and
`UpdateMyPreferencesHandler` each carry a hand-written `current.get().photoUrl()` purely to avoid
erasing a field they have no interest in. A dedicated photo mutation removes one instance of that
problem and adds another — the photo mutation would itself have to carry `name`, `isAdmin` and all
three preferences forward.

Switching to attribute-level `UpdateItem` expressions eliminates the entire class structurally, for
every field added from here on, and is what makes the new mutation safe to write at all. This is
the fix; the dedicated mutation is not a substitute for it.

### Stock photos are synthetic faces, stored in mootmaker-demo-data

Generated portraits depict no real person, so there is no personality or publicity right to
consider. That is a separate exposure from copyright, and a permissive licence does not address it:
using an identifiable real person's photograph to represent a fictional employee in a product demo
is a different thing from reusing their photo. Synthetic faces also scale to any pool size and are
easier to keep consistent in crop and framing.

They live in mootmaker-demo-data because that is the only component that uses them. Bundling them
into the webapp was what created the cross-repo filename convention that broke.

### An avatar is never reused within an environment

demo-data assigns each new person a stock photo not already in use anywhere in that environment,
determined by the read-back described above. It throws rather than repeating — mirroring the
existing `SampleData.personNames` behaviour, which already fails loudly when asked for more
distinct names than the curated lists can produce. The pool must therefore be larger than any
plausible `TARGET_PEOPLE`.

## Choices you had me make

Cheap to override — flagged because I picked them rather than asking.

1. **Presigned PUT with pinned `Content-Type` and `Content-Length`, not presigned POST.** POST
   supports a `content-length-range` policy that S3 enforces, which is slightly stronger. PUT with
   both headers signed gets exact enforcement of a value the client declared up front, and is far
   easier to call from Java's `HttpClient` — which matters, because demo-data must use the same
   mechanism the browser will.
2. **One `personId`-shaped mutation pair, authorised as "admin, or the caller's own person".** This
   diverges from the established precedent of separate self and admin mutations
   (`updateMyName`/`renamePerson`). A split would double a three-call surface; say so if you'd
   rather keep the precedent.
3. **JPEG-only output at 256×256.** Matches today's images and is comfortably above 2× the largest
   rendered size. Transparency is lost, which does not matter under a circular mask.
4. **Accepted input types are JPEG and PNG only.** Both are handled by `javax.imageio` in the JDK.
   WebP would need a third-party decoder, and this codebase has previously declined a 2 MB
   dependency for one method call.
5. **2 MiB upload ceiling, minimum 64×64, maximum 4096×4096.**
6. **A pool of 120 photos (60 male, 60 female)** against a default `TARGET_PEOPLE` of 100.
7. **The photos bucket policy grants CloudFront by account, not by distribution ARN**
   (`AWS:SourceAccount` plus a distribution wildcard). Naming the exact distribution would make the
   API repo depend on mootmaker-webapp's Terraform state, which this project deliberately avoids.
8. **`database-reset` also empties the photos bucket.**

## Open questions

### Blocking

1. **Where do the 120 synthetic faces come from, and does the licence permit redistribution in a
   public repository?** I cannot generate images myself, so this needs either a source you're happy
   with or a local generation step. mootmaker-demo-data is public, so whatever licence applies must
   permit redistribution, not merely use. This blocks the demo-data half of the work; the API half
   can proceed without it.
2. **Does `Person.photoUrl` stay a bare `String`?** Now that only the API ever writes it, it could
   become a narrower type. Keeping `String` is the smaller change and is probably right, but it is
   worth one sentence of agreement rather than assumption.

### Non-blocking

3. **Unreferenced served objects are never deleted.** Content-addressed objects are shared, so
   removing one person's photo cannot safely delete the object. For demo environments this is
   bounded by the pool (~120 × ~15 KB). For real uploads it is unbounded, which conflicts with
   "nothing accumulates without a bound". A reaper comparing bucket contents against live
   `photoUrl`s is the obvious answer, and is not needed until real users can upload.
4. **Should the missing-photo case be made loud?** Options: a CloudFront Function on the photos
   behaviour rewriting a `text/html` 200 back to 404, or accepting it and relying on the
   `naturalWidth` acceptance coverage tracked in mootmaker-webapp#131.
5. **Deploy ordering between the two repos.** mootmaker-webapp's Terraform references the API
   bucket by deterministic name, so the API must be deployed first into a new environment. Worth
   confirming `create-ephemeral-env.sh` already does that ordering.
6. **Should `removePersonPhoto` ship now** or wait for the upload UI that would use it?

## Impacts on components

### mootmaker-api

- `api/mootmaker.graphql` — three new mutations, new result/error types, `photoUrl` removed from
  `createPerson`. Version bump in `api/package.json` (the publish workflow fails otherwise — this
  has bitten twice).
- `impl/.../handler/` — new `RequestPersonPhotoUploadHandler`, `ConfirmPersonPhotoUploadHandler`,
  `RemovePersonPhotoHandler`; registered in `ResolverDispatchHandler`, and constructed eagerly in
  its constructor so they are captured in the SnapStart snapshot.
- `impl/.../handler/CreatePersonHandler.java` — drops the `photoUrl` argument.
- `impl/.../dynamo/PersonRepository.java` — `PutItem` → attribute-level `UpdateItem`; new
  `updatePhotoUrl`.
- `RenamePersonHandler`, `UpdateMyNameHandler`, `SetPersonAdminHandler`,
  `UpdateMyPreferencesHandler` — each loses its hand-written carry-forward.
- New image validation/normalisation class, and a small S3 wrapper.
- `impl/.../handler/DatabaseResetHandler.java` — also empties the photos bucket.
- `deploy/terraform/` — new `s3.tf` for the photos bucket (versioning off, public access blocked,
  lifecycle rule expiring `uploads/` after 1 day, bucket policy granting CloudFront), plus
  `s3:PutObject`/`GetObject`/`DeleteObject` on the resolver and reset roles. Resolver Lambda needs
  the bucket name as an environment variable.

### mootmaker-webapp

- `webapp/public/avatars/` — **deleted** (24 files).
- `deploy/terraform/cloudfront.tf` — second origin plus `ordered_cache_behavior` for
  `/person-photos/*` with a cache policy honouring origin headers, and an OAC for that origin.
- `webapp/src/graphql/` — regenerate after the schema change; `@mootmaker/schema` bump.
- `webapp/src/testSupport/mocks/fixtures.ts` and `webapp/tests/person-avatar.spec.ts` — fixture
  paths move from `/avatars/...` to `/person-photos/v1/...`.
- `webapp/src/components/PersonAvatar.tsx` — unchanged. `originRelative()` stays as defence in
  depth even though the API now always emits a leading slash.

### mootmaker-demo-data

- `impl/src/main/resources/avatars/` — new, 120 images (~1.8 MB into a 12 MB shaded jar).
- `SampleData.java` — `FEMALE_AVATAR_PHOTOS`/`MALE_AVATAR_PHOTOS` become classpath resource names;
  `avatarPhotoFor` takes the set already in use and returns an unused resource or null.
- `DemoData.java` — `topUpPeople` creates the person, then requests, PUTs and confirms.
- `GraphQlClient.java` — needs a plain binary PUT alongside its GraphQL POST.

## Changes to the domain data model and data storage models

Delta against [`../docs/reference/data-model.md`](../docs/reference/data-model.md):

- **DynamoDB `People` table** — no new attributes. `photoUrl` already exists and keeps its meaning
  and nullability; only its *format* narrows, from an arbitrary path to
  `/person-photos/v1/<sha256>.jpg`, and only the API may now write it. Writes change from full-item
  `PutItem` to attribute-level `UpdateItem`, which is a storage-access change rather than a shape
  change — no migration.
- **Cognito** — unaffected.
- **New: S3.** One bucket per environment, `<env>-mootmaker-person-photos-<account>`, with two
  prefixes: `uploads/<personId>/<uploadId>` (private staging, expired after 1 day by lifecycle
  rule) and `person-photos/v1/<sha256>.jpg` (served, `immutable`).
- **No backfill.** Existing `photoUrl` values point at webapp-bundled files that this change
  deletes. They are demo data only, and the rollout is a reset-and-reseed, so nothing is migrated.

## Technical considerations

- **Decompression bombs.** `ImageIO.read` allocates for the *decoded* dimensions, so a small file
  can demand a large heap. Read dimensions from the header via `ImageReader` and reject over
  4096×4096 **before** decoding, not after. The 2 MiB ceiling alone does not protect against this.
- **Re-encoding is the sanitiser.** Never serve uploaded bytes. Decoding and re-encoding neutralises
  polyglot files and strips EXIF, which will carry GPS and device data once real users upload.
- **A signed `Content-Length` is enforced exactly**, not as a maximum — the client's declared size
  must match the bytes. That is stricter than a range and worth stating in the schema description.
- **Content type is still client-asserted** at request time. S3 enforces the header matches the
  signature, not that the bytes match the header; only the decode in confirm proves it is an image.
- **`confirmPersonPhotoUpload` must be idempotent.** The key is a pure function of the bytes, so a
  repeat is a no-op overwrite of identical content.
- **Lambda needs S3 in the SnapStart snapshot.** Build the S3 client eagerly, in the constructor,
  like every other handler dependency.
- **The webapp's deploy invalidates `/*`**, which includes the photos path. Harmless — objects
  refetch from S3 — but it is the webapp's deploy touching API-owned cached objects.
- **`aws s3 sync --delete` is safe**: the photos live in a different bucket from the site.
- **What this leaves behind:** staging uploads (bounded by the 1-day lifecycle rule); served photo
  objects (bounded per environment by the demo pool, unbounded once real uploads exist — open
  question 3); no new logs or metrics beyond normal Lambda output.
- **Cost:** ~2 MB of S3 per environment and a negligible request volume. No new distribution or
  certificate. Well under NZ$1; no recurring charge worth flagging.

## Testing impacts

**Unit (mootmaker-api)** — the natural home for validation, because it is pure logic over bytes
with no deployment needed: reject a non-image, a too-large dimension, a mismatched declared length,
an unsupported type; confirm the key is the source hash and is stable across runs; confirm EXIF does
not survive. Plus the `UpdateItem` refactor: each of the four existing carry-forward regression
tests (including the two `regressionMootmakerApi71...` ones) should keep asserting the same
outcomes, but now pass because the repository cannot clobber rather than because a handler
remembered.

**Unit (mootmaker-demo-data)** — the existing `DemoDataTopUpTest` cases for the 10% rate and the
gender tagging stay. `everyAssignedPhotoIsOriginRelative` is superseded: the path is no longer
demo-data's to construct. New: never assigns a photo already in use given a set of existing
`photoUrl`s; throws rather than repeating when the pool is exhausted; every bundled resource is
actually loadable from the classpath (cheap, and catches a resource that did not make it into the
shaded jar).

**Mocked integration (mootmaker-webapp)** — `person-avatar.spec.ts` keeps its three cases with
updated fixture paths. The nested-route regression case stays: it guards `PersonAvatar`'s
resolution rule, which is unchanged and still worth holding. No new cases — there is no UI here.

**Acceptance (mootmaker-webapp)** — this is the layer that would have caught the original bug and
did not, and it is the right layer for the round trip, because it is the only one where demo-data's
upload and the webapp's render meet on real infrastructure. One case: sign in, go to a route deeper
than one segment, and assert `naturalWidth > 0` on the rendered avatars rather than merely that they
are present. Present-ness proves nothing — MUI falls back to initials on failure, and the SPA
answers an unmatched path with 200. This closes mootmaker-webapp#131 and needs a use-case number
allocated in `docs/reference/use-cases.md`.

**Acceptance (mootmaker-api)** — one case against a deployed environment covering the full three
call round trip, plus one asserting a rejected upload returns a structured error rather than a 500.
Chosen here rather than at the unit layer because presigning, the S3 PUT and IAM are exactly the
parts a unit test has to fake.

**Not impacted:** mootmaker-release's smoke suite. It does not assert on avatars, and this changes
no copy or structure it looks at. Explicitly considered, no change needed.

## Documentation impacts

- `docs/reference/data-model.md` — narrow `photoUrl`'s described format; add the S3 bucket and its
  two prefixes.
- `docs/reference/use-cases.md` — one new numbered case for the acceptance test above.
- `mootmaker-api/README.md` — the photos bucket, the upload flow, and `database-reset`'s widened
  remit.
- `mootmaker-webapp/README.md` — avatars are no longer bundled; the second CloudFront origin.
- `mootmaker-demo-data/README.md` — the bundled photo library and the create-then-upload sequence.
- `designs/archive/person-avatar-photos.md` — add a line pointing at this document as its successor.
- This document moves to `archive/` at Shipped.

## Rollout & migration

No backfill and no feature flag. Existing `photoUrl` values reference files this change deletes, so
every environment is reset and reseeded, which is already the established procedure from the
previous avatar rollout.

Order matters, because the webapp's Terraform references the API's bucket by name:

1. mootmaker-api — schema, handlers, bucket. Must land and deploy first.
2. mootmaker-webapp — CloudFront behaviour, schema bump, deleted images.
3. mootmaker-demo-data — photo library and upload flow.
4. Per environment: deploy all three, `database-reset`, then invoke demo-data.

Reversibility is good up to the point the images are deleted from mootmaker-webapp; after that a
revert also needs a reseed. Nothing is destroyed that is not demo data.

## Risks

- **A missing photo object still fails silently** (`index.html` at 200 → initials). Much less
  likely now that keys are server-generated, but not impossible — a reset that empties the bucket
  without reseeding produces exactly this. The acceptance coverage above is the guard. See open
  question 4.
- **Cross-repo deploy ordering** is a new way for a fresh environment to half-work: the webapp's
  Terraform will fail, or worse silently point at a missing origin, if the API has not deployed.
- **The schema version bump gets forgotten.** This has already happened twice in this feature's
  history, both times failing `publish-schema.yml` after merge and then breaking the webapp's
  `codegen:check`. Bump `api/package.json` in the same commit as any schema edit, including a
  description-only edit.
- **`UpdateItem` is a broad change to a core repository.** It touches every person-mutating path,
  including ones unrelated to avatars. Worth its own commit and its own careful read.
- **Image licensing** is the one risk that is awkward rather than merely expensive to reverse: once
  120 images are committed to a public repository, a licence problem means a history rewrite, not
  just a deletion. Blocking question 1 exists for this reason.

## Implementation checklist

Filled in properly once this reaches Ready; sparse while Drafting.

1. `[Geoff]` Decide blocking questions 1 and 2.
2. `[Geoff]` Provide or approve the source of 120 synthetic face images.
3. `[Claude]` mootmaker-api: `PersonRepository` `PutItem` → `UpdateItem`, and strip the four
   handlers' carry-forward. Own commit, own PR — independently valuable and independently
   reviewable.
4. `[Claude]` mootmaker-api: photos bucket Terraform and IAM.
5. `[Claude]` mootmaker-api: schema, three handlers, validation/normalisation, version bump.
6. `[Claude]` mootmaker-api: `database-reset` empties the bucket.
7. `[Claude]` mootmaker-webapp: CloudFront second origin and behaviour.
8. `[Claude]` mootmaker-webapp: schema bump, codegen, delete `public/avatars/`, update fixtures.
9. `[Claude]` mootmaker-demo-data: bundle images, rework `SampleData`/`DemoData`, add the PUT.
10. `[Claude]` Acceptance coverage in both repos; allocate the use-case number.
11. `[Claude]` Documentation updates listed above.
12. `[Claude]` Deploy all three to one ephemeral environment, reset, reseed, full acceptance run.

## Definition of done

- Every repo's unit suite green.
- A single ephemeral environment with all three components deployed, reset and reseeded, where
  100 demo people hold **100 distinct** photos (90 with, 10 without) and no two share an image.
- The new acceptance case proves `naturalWidth > 0` from a route deeper than one segment, and the
  existing acceptance suite is still green on that environment.
- A served photo responds with `Cache-Control: public, max-age=31536000, immutable`, verified
  against the deployed distribution rather than inferred from Terraform.
- Every item under Documentation impacts actually done.
- mootmaker-webapp#131 closed by the acceptance case, not by a comment.
