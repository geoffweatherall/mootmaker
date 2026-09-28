# Person avatar upload refactor

## Summary

Avatar photos are currently a static library bundled into mootmaker-webapp, pointed at by a
free-string `Person.photoUrl` that mootmaker-demo-data fills in by convention. This replaces that
with a real upload path owned by the API: a presigned S3 upload, a confirm step that validates and
normalises the image, and a content-addressed object served from an API-owned bucket behind the
API's own CloudFront distribution and subdomain. The stock photos move into mootmaker-demo-data,
which uploads them through the same API calls a future webapp upload feature will use. It also
fixes the carry-forward problem underneath, by moving `PersonRepository` off whole-record
`PutItem`.

## Status

**Drafting** — 2026-09-29. Revised the same day: photos now get their own CloudFront distribution
and subdomain rather than riding the webapp's, so mootmaker-api stays independently deployable.

## Scope / non-goals

**In scope**

- A two-step upload API (`requestPersonPhotoUpload` / `confirmPersonPhotoUpload`) plus removal.
- A new API-owned S3 bucket for staging and serving person photos, behind a CloudFront distribution
  and subdomain that mootmaker-api owns outright.
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

### Photos get mootmaker-api's own CloudFront distribution and subdomain

**Reversed on 2026-09-29**, within hours of the first draft. The original choice — a second origin
on mootmaker-webapp's existing distribution — is recorded here because the reasoning that killed it
is the important part.

That arrangement makes the two repos mutually dependent. mootmaker-webapp's Terraform would have to
reference the API's bucket, and the API's bucket policy would have to admit the webapp's
distribution. The second half can be fudged with an account-scoped wildcard, but the first cannot,
and the real damage is worse than either: **mootmaker-api could no longer be deployed and verified
on its own.** Photo serving would only work once the webapp existed, so an API-only environment —
which is exactly what `mootmaker-api/verify/`'s acceptance suite runs against — would be a
half-working system. An origin-relative `photoUrl` compounds it, because it is the API implicitly
asserting that it is served from the webapp's origin.

So photos get `photos.<environment>.mootmaker.com`, a distribution and certificate owned by
mootmaker-api. This follows an existing pattern rather than inventing one:
`mootmaker-domain/deploy/terraform/acm.tf` already states that hostnames "get their own certificate
from mootmaker-api/mootmaker-webapp's own Terraform, validated against the zone this project
creates", and `mootmaker-webapp/deploy/terraform/domain.tf` resolves that zone with a
`data "aws_route53_zone"` lookup rather than a cross-repo state reference. mootmaker-api copies that
shape exactly. It will be the API repo's first custom domain — today it only exposes AppSync's
AWS-provided URL.

**The cost, stated honestly:** one more CloudFront distribution and ACM certificate in every
environment's create-and-destroy cycle. Certificates are free and distributions carry no fixed
charge, but both add minutes to ephemeral environment turnaround, which is a cost paid every
working session. Accepted deliberately — it is the price of the components being independently
deployable, which is a property worth more than the minutes.

**Two things this buys back.** There is no SPA fallback on this distribution, so a missing object
returns a real 403/404 instead of `index.html` at status 200 — the silent-failure mode that produced
the bug this refactor follows is gone by construction, not merely made less likely. And cache
headers become trivially the API's own business: it sets
`Cache-Control: public, max-age=31536000, immutable` at `PutObject` time and configures its own
distribution to honour it, with no other component needing to know or assume the storage and naming
strategy.

Presigned GET URLs remain rejected: a URL that changes per request destroys both browser caching
and Apollo's normalised cache identity.

### `photoUrl` is stored as a path and resolved to an absolute URL on read

DynamoDB stores `person-photos/v1/<sha256>.jpg`. The API prepends its own photo host — a Lambda
environment variable set from its own Terraform — when building a response, so `Person.photoUrl`
reaches the client as a fully-resolved `https://photos.<environment>.mootmaker.com/...`.

Neither end of that is arbitrary. Storing the absolute URL would bake an environment's hostname into
the data, so a production snapshot restored into an ephemeral environment would serve production's
photos. Returning a bare path would push host knowledge onto every client — the implicit coupling
this revision exists to remove. Storing the path and resolving on read keeps stored data portable
and clients ignorant, and the API needs nothing from any other repository to do it.

Consequence for the webapp: `originRelative()` in `PersonAvatar.tsx` is **deleted**, and `src` is
used exactly as the API gave it.

Consequence for demo-data: its read-back must compare on the **path portion** of a returned
`photoUrl`, not the whole string, so the comparison stays environment-agnostic.

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

### Stock photos are synthetic faces, generated for this project, stored in mootmaker-demo-data

Generated portraits depict no real person, so there is no personality or publicity right to
consider. That is a separate exposure from copyright, and a permissive licence does not address it:
using an identifiable real person's photograph to represent a fictional employee in a product demo
is a different thing from reusing their photo. Synthetic faces also scale to any pool size and are
easier to keep consistent in crop and framing.

They live in mootmaker-demo-data because that is the only component that uses them. Bundling them
into the webapp was what created the cross-repo filename convention that broke.

Decided 2026-09-29 that they are **generated here rather than sourced** from an existing dataset,
which removes the redistribution-licence question entirely for the images themselves. It does not
remove it for the *model*: see the blocking question below, because I cannot currently do this.

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
7. **The subdomain is `photos.<environment>.mootmaker.com`**, matching `www.<environment>...`.
   `media.` or `assets.` would read as more general and invite non-photo content onto a
   distribution designed around immutable content-addressed objects.
8. **`database-reset` also empties the photos bucket.**

## Open questions

### Blocking

1. **How are the 120 faces actually generated?** The decision is "Claude generates them"; the
   obstacle is that I currently cannot.

   **Capability, stated plainly:** I have no image-generation tool, and this workstation has no GPU
   (no `nvidia-smi`), no `torch` or `diffusers`, and no hosted image-generation credentials. What it
   does have is 16 cores, ~7 GB free RAM and 741 GB of disk — enough to run a small diffusion model
   on CPU, but not something I will install unasked.

   **Model licence is the real constraint**, because the outputs get committed to a public
   repository. Stable Diffusion 1.5 (CreativeML OpenRAIL-M) and SDXL base 1.0 (OpenRAIL++-M) both
   permit commercial use and place no restriction on redistributing outputs. **SDXL-Turbo and SD3
   are non-commercial licences and must not be used here.** FLUX.1-schnell is Apache-2.0 and would
   be the cleanest, but at 12B parameters it will not fit in 7 GB of RAM.

   **Practical shape if approved:** SD 1.5 at 512×512, downscaled to 256×256. Face artifacts that
   would be glaring at full size are invisible at a 32–40 px avatar, which makes the weakest part of
   a small model irrelevant to this use. Expect roughly 1–2 minutes per image on 16 CPU cores, so
   2–4 hours for 120 — well suited to an unattended run. Install cost is ~3 GB of Python packages
   plus a ~2.5 GB checkpoint, which per the process rules belongs in
   [`../tools/workstation/manifest.yaml`](../tools/workstation/manifest.yaml).

   Needed: approval of the install and the model, or images supplied another way. This blocks the
   demo-data half only; the API half can proceed without it.

2. **Does `Person.photoUrl` stay a bare `String`?** Now that only the API ever writes it, and it is
   resolved to an absolute URL on read, it could become a narrower type. Keeping `String` is the
   smaller change and is probably right, but it is worth one sentence of agreement rather than
   assumption.

### Non-blocking

3. **Unreferenced served objects are never deleted.** Content-addressed objects are shared, so
   removing one person's photo cannot safely delete the object. For demo environments this is
   bounded by the pool (~120 × ~15 KB). For real uploads it is unbounded, which conflicts with
   "nothing accumulates without a bound". A reaper comparing bucket contents against live
   `photoUrl`s is the obvious answer, and is not needed until real users can upload.
4. **Should `removePersonPhoto` ship now** or wait for the upload UI that would use it?
5. **Does the photos distribution need its own `default_root_object` or index behaviour?** Almost
   certainly not — nothing should ever request its root — but an explicit 403 beats whatever the
   default turns out to be.

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
  lifecycle rule expiring `uploads/` after 1 day, bucket policy granting this repo's own
  distribution via OAC), new `cloudfront.tf` and `domain.tf` for the distribution, certificate and
  Route53 records — modelled on `mootmaker-webapp/deploy/terraform/domain.tf`, including the
  `data "aws_route53_zone"` lookup. Plus `s3:PutObject`/`GetObject`/`DeleteObject` on the resolver
  and reset roles. Resolver Lambda needs the bucket name **and the photo host** as environment
  variables.
- `verify/` — acceptance coverage for the round trip, which can now run against an API-only
  environment because nothing here depends on mootmaker-webapp.

### mootmaker-webapp

Much smaller than the first draft, now that the API owns its own hosting — **no Terraform changes
at all**.

- `webapp/public/avatars/` — **deleted** (24 files).
- `webapp/src/graphql/` — regenerate after the schema change; `@mootmaker/schema` bump.
- `webapp/src/testSupport/mocks/fixtures.ts` and `webapp/tests/person-avatar.spec.ts` — fixture
  values become absolute `https://photos.…` URLs.
- `webapp/src/components/PersonAvatar.tsx` — `originRelative()` deleted; `src` used as given.

### mootmaker-demo-data

- `impl/src/main/resources/avatars/` — new, 120 images (~1.8 MB into a 12 MB shaded jar).
- `SampleData.java` — `FEMALE_AVATAR_PHOTOS`/`MALE_AVATAR_PHOTOS` become classpath resource names;
  `avatarPhotoFor` takes the set already in use and returns an unused resource or null.
- `DemoData.java` — `topUpPeople` creates the person, then requests, PUTs and confirms.
- `GraphQlClient.java` — needs a plain binary PUT alongside its GraphQL POST.

## Changes to the domain data model and data storage models

Delta against [`../docs/reference/data-model.md`](../docs/reference/data-model.md):

- **DynamoDB `People` table** — no new attributes. `photoUrl` already exists and keeps its meaning
  and nullability; only its *format* narrows, to the host-less path `person-photos/v1/<sha256>.jpg`,
  and only the API may now write it. Note the stored value is deliberately **not** what the API
  returns — the host is prepended on read, so stored data carries no environment hostname. Writes
  change from full-item `PutItem` to attribute-level `UpdateItem`, which is a storage-access change
  rather than a shape change — no migration.
- **Cognito** — unaffected.
- **New: S3.** One bucket per environment, `<env>-mootmaker-person-photos-<account>`, with two
  prefixes: `uploads/<personId>/<uploadId>` (private staging, expired after 1 day by lifecycle
  rule) and `person-photos/v1/<sha256>.jpg` (served, `immutable`).
- **New: DNS.** One `photos.<environment>.mootmaker.com` A/AAAA record pair per environment in the
  `mootmaker.com` hosted zone that mootmaker-domain owns, plus a per-environment ACM certificate.
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
- **The photo host must be configuration, never derived.** The resolver Lambda reads it from an
  environment variable set by this repo's own Terraform. Reconstructing it from the environment name
  in code would reintroduce, in string concatenation, exactly the implicit coupling this revision
  removes.
- **`database-reset` must empty the bucket, not delete it.** The bucket is a Terraform resource; a
  reset that removed it would put Terraform and reality out of step.
- **Certificate validation is the slow part of a first deploy.** ACM DNS validation against the
  hosted zone typically takes a few minutes, and Terraform blocks on it. This lands on the critical
  path of creating an ephemeral environment.
- **What this leaves behind:** staging uploads (bounded by the 1-day lifecycle rule); served photo
  objects (bounded per environment by the demo pool, unbounded once real uploads exist — open
  question 3); one Route53 record pair and one certificate per environment, both destroyed with the
  environment; no new logs or metrics beyond normal Lambda output.
- **Cost:** ~2 MB of S3 per environment, a negligible request volume, one free ACM certificate and
  one CloudFront distribution with no fixed charge. Well under NZ$1; no recurring charge worth
  flagging. The real cost is minutes of ephemeral environment turnaround, not dollars.

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

**Mocked integration (mootmaker-webapp)** — `person-avatar.spec.ts` keeps its photo, initials and
load-failure cases with absolute-URL fixtures. The **nested-route regression case is retired**: it
guarded `originRelative()`, which this design deletes, so keeping it would be testing a rule that no
longer exists. That is a deliberate reduction in coverage, and it is safe only because absolute URLs
cannot resolve against the document at all — the failure mode it guarded is now unreachable rather
than merely unlikely.

**Acceptance (mootmaker-webapp)** — still the right layer for the end-to-end round trip, because it
is the only place demo-data's upload and the webapp's render meet on real infrastructure. One case:
sign in, and assert `naturalWidth > 0` on rendered avatars rather than merely that they are present
— MUI falls back to initials on failure, so present-ness proves nothing. Route depth no longer
matters, so the case can use any page showing people. Closes mootmaker-webapp#131 and needs a
use-case number allocated in `docs/reference/use-cases.md`.

**Acceptance (mootmaker-api)** — one case covering the full three-call round trip, plus one
asserting a rejected upload returns a structured error rather than a 500. Chosen here rather than at
the unit layer because presigning, the S3 PUT and IAM are exactly the parts a unit test has to fake.
Worth stating explicitly: because the API now owns its own hosting, this suite can prove photos are
genuinely *served* — fetch the returned URL, check it is `image/jpeg` and carries the immutable
`Cache-Control` — **against an API-only environment, with no webapp deployed**. That is the
practical payoff of the independence argument, not just an architectural nicety.

**Not impacted:** mootmaker-release's smoke suite. It does not assert on avatars, and this changes
no copy or structure it looks at. Explicitly considered, no change needed.

## Documentation impacts

- `docs/reference/data-model.md` — narrow `photoUrl`'s described format, note that the stored value
  is a path and the returned value absolute; add the S3 bucket, its two prefixes, and the subdomain.
- `docs/reference/use-cases.md` — one new numbered case for the acceptance test above.
- `docs/development/` — the cross-repo architecture gains a second custom domain; mootmaker-api is
  no longer AppSync-URL-only.
- `mootmaker-api/README.md` — the photos bucket, distribution and subdomain, the upload flow, and
  `database-reset`'s widened remit.
- `mootmaker-webapp/README.md` — avatars are no longer bundled or served by this component at all.
- `mootmaker-demo-data/README.md` — the bundled photo library and the create-then-upload sequence.
- `mootmaker-domain/README.md` — if it enumerates which hostnames exist, `photos.<env>` joins them.
- `designs/archive/person-avatar-photos.md` — add a line pointing at this document as its successor.
- This document moves to `archive/` at Shipped.

## Rollout & migration

No backfill and no feature flag. Existing `photoUrl` values reference files this change deletes, so
every environment is reset and reseeded, which is already the established procedure from the
previous avatar rollout.

The repos are now **independently deployable**, which is the point of the revision — mootmaker-api
can ship and be verified before either other repo moves. A sensible order is still:

1. mootmaker-api — schema, handlers, bucket, distribution, subdomain. Deployable and verifiable on
   its own.
2. mootmaker-webapp — schema bump, codegen, deleted images, `originRelative()` removed.
3. mootmaker-demo-data — photo library and upload flow.
4. Per environment: deploy all three, `database-reset`, then invoke demo-data.

Between steps 1 and 2 the webapp renders initials for everyone, because `photoUrl` comes back in a
form it has not yet been rebuilt for — a visibly degraded but not broken state, and short-lived.

Reversibility is good up to the point the images are deleted from mootmaker-webapp; after that a
revert also needs a reseed. Nothing is destroyed that is not demo data.

## Risks

- **A first deploy into a new environment now blocks on ACM DNS validation.** This is the main new
  failure surface: a certificate that will not validate leaves an environment half-created, and it
  is slower to diagnose than a Lambda error.
- **`UpdateItem` is a broad change to a core repository.** It touches every person-mutating path,
  including ones unrelated to avatars. Worth its own commit and its own careful read.
- **The schema version bump gets forgotten.** This has already happened twice in this feature's
  history, both times failing `publish-schema.yml` after merge and then breaking the webapp's
  `codegen:check`. Bump `api/package.json` in the same commit as any schema edit, including a
  description-only edit.
- **Teardown must remove the certificate and DNS records**, or ephemeral environments leave litter
  in a hosted zone shared with production. `mootmaker-ephemeral-envs`' teardown script already has a
  known gap with split-out components; this adds something new for it to miss.
- **Image licensing** remains awkward rather than merely expensive to reverse: once 120 images are
  committed to a public repository, a licence problem means a history rewrite, not a deletion.
  Generating rather than sourcing them narrows this to the model's own licence — see blocking
  question 1.
- **Retiring the nested-route regression test** removes a guard that caught a real shipped bug. It
  is only safe because the rule it guarded ceases to exist; if absolute URLs are ever walked back,
  that test must come back with them.

## Implementation checklist

Filled in properly once this reaches Ready; sparse while Drafting.

1. `[Geoff]` Decide blocking questions 1 and 2 — in particular, approve the image-generation install
   and model, or supply the images another way.
2. `[Claude]` mootmaker-api: `PersonRepository` `PutItem` → `UpdateItem`, and strip the four
   handlers' carry-forward. Own commit, own PR — independently valuable and independently
   reviewable, and does not depend on anything else here.
3. `[Claude]` mootmaker-api: photos bucket, distribution, certificate, DNS, IAM.
4. `[Claude]` mootmaker-api: schema, three handlers, validation/normalisation, host resolution on
   read, version bump.
5. `[Claude]` mootmaker-api: `database-reset` empties the bucket.
6. `[Claude]` Deploy and verify mootmaker-api **on its own**, with no webapp — proving the
   independence this design is built around, before anything downstream moves.
7. `[Claude]` mootmaker-webapp: schema bump, codegen, delete `public/avatars/`, remove
   `originRelative()`, update fixtures, retire the nested-route case.
8. `[Claude]` Generate the 120 images (blocked on step 1), then mootmaker-demo-data: bundle them,
   rework `SampleData`/`DemoData`, add the binary PUT.
9. `[Claude]` Acceptance coverage in both repos; allocate the use-case number.
10. `[Claude]` Documentation updates listed above.
11. `[Claude]` Deploy all three to one ephemeral environment, reset, reseed, full acceptance run,
    then confirm teardown removes the certificate and DNS records.

## Definition of done

- Every repo's unit suite green.
- **mootmaker-api verified standalone**: an environment with the API deployed and no webapp, where
  the three-call round trip works and the returned URL serves a real image. This is the design's
  central claim and should be proven directly, not inferred.
- A single ephemeral environment with all three components deployed, reset and reseeded, where
  100 demo people hold **100 distinct** photos (90 with, 10 without) and no two share an image.
- The new acceptance case proves `naturalWidth > 0`, and the existing acceptance suite is still
  green on that environment.
- A served photo responds with `Cache-Control: public, max-age=31536000, immutable` and a real
  404 for a missing key, both verified against the deployed distribution rather than inferred from
  Terraform.
- Teardown of that environment leaves no certificate or DNS record behind, confirmed by looking.
- Every item under Documentation impacts actually done.
- mootmaker-webapp#131 closed by the acceptance case, not by a comment.
