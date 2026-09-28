# Person avatar upload refactor

## Summary

Avatars are currently a static library bundled into mootmaker-webapp, pointed at by a free-string
`Person.photoUrl` that mootmaker-demo-data fills in by convention. This replaces that with a real
upload path owned by the API: a presigned S3 upload, a confirm step that validates and normalises
the image, and a content-addressed object served from an API-owned bucket behind the API's own
CloudFront distribution and subdomain. The field is renamed to `avatarUrl` in the same change. The
image library moves into mootmaker-demo-data, which uploads it through the same API calls a future
webapp upload feature will use. It also fixes the carry-forward problem underneath, by moving
`PersonRepository` off whole-record
`PutItem`.

## Status

**Building** — 2026-09-29. Approved to **Ready** by Geoff on 2026-09-29 and moved straight to
Building the same day, as implementation started immediately.

Revised through the day before approval: avatars get their own CloudFront distribution
and subdomain rather than riding the webapp's, so mootmaker-api stays independently deployable;
photorealistic images were split out to
[photorealistic-demo-avatars.md](photorealistic-demo-avatars.md); `photoUrl` was renamed
`avatarUrl`; and objects became per-person rather than globally content-addressed, so an avatar can
be deleted with its person and a person can hold at most one.

## Scope / non-goals

**In scope**

- A two-step upload API (`requestAvatarUpload` / `confirmAvatarUpload`) plus removal.
- A new API-owned S3 bucket for staging and serving person photos, behind a CloudFront distribution
  and subdomain that mootmaker-api owns outright.
- Server-side validation and normalisation of uploaded images.
- Content-addressed served keys, enabling immutable caching and letting demo-data tell which stock
  photos are already in use.
- Moving the avatar image library out of mootmaker-webapp and into mootmaker-demo-data, grown to
  cover a whole environment without repeats.
- The procedural CC0 avatar pool and the script that regenerates it.
- Removing `avatarUrl` as an argument to `createPerson`.
- Replacing whole-record `PutItem` in `PersonRepository` with attribute-level `UpdateItem`.

**Explicit non-goals**

- **No webapp upload UI.** The API is designed so the webapp can add one later without a second
  redesign, but no picker, cropper or settings control is built here.
- **No per-person photo history.** One current photo; replacing it simply repoints `avatarUrl`.
- **No image CDN features** — no on-the-fly resizing, no format negotiation, no WebP/AVIF. One
  canonical derivative, described below.
- **No change to the initials fallback.** `PersonAvatar` keeps rendering initials when `avatarUrl`
  is null or the image fails, unchanged.
- **No avatar for real sign-ups.** `PostConfirmationCreatePersonHandler` still creates people
  without a photo; `me` still does not select `avatarUrl`.
- **Photorealistic avatars.** Split out to
  [photorealistic-demo-avatars.md](photorealistic-demo-avatars.md): different hardware, no
  structural overlap, and nothing here depends on it.

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
half-working system. An origin-relative `avatarUrl` compounds it, because it is the API implicitly
asserting that it is served from the webapp's origin.

So avatars get `avatars.<environment>.mootmaker.com`, a distribution and certificate owned by
mootmaker-api. This follows an existing pattern rather than inventing one:
`mootmaker-domain/deploy/terraform/acm.tf` already states that hostnames "get their own certificate
from mootmaker-api/mootmaker-webapp's own Terraform, validated against the zone this project
creates".

More than that, **mootmaker-api already does exactly this.** `mootmaker-api/deploy/terraform/domain.tf`
owns `api.<environment>.mootmaker.com` today, with its own ACM certificate, DNS validation against a
`data "aws_route53_zone"` lookup, and a Route53 alias — the whole pattern, already in this repo and
already working. Adding a second hostname is extending a file, not introducing a capability. (An
earlier draft of this document claimed this would be the API's first custom domain and that it only
exposed AppSync's AWS-provided URL. Both were wrong.)

Note the production naming rule that file establishes: production drops the environment segment
entirely (`api.mootmaker.com`, matching the webapp's `www.mootmaker.com`), so avatars are served
from `avatars.mootmaker.com` in production and `avatars.<environment>.mootmaker.com` everywhere
else.

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

### `avatarUrl` is stored as a path and resolved to an absolute URL on read

DynamoDB stores **`v1/<personId>/<sha256>`**. The API prepends its own avatar host and appends the
extension when building a response, so `Person.avatarUrl` reaches the client as a fully-resolved
`https://avatars.<environment>.mootmaker.com/v1/<personId>/<sha256>.jpg` —
`https://avatars.mootmaker.com/v1/…` in production, which drops the environment segment the same way
`api.mootmaker.com` and `www.mootmaker.com` already do.

The `v1/` stays in the *stored* value rather than becoming configuration, and that distinction is
load bearing: the processing version is per-avatar state, not a global setting. If normalisation
ever changes, records written under v1 must keep resolving to the v1 objects they actually wrote,
while new uploads go to v2. A version held only in config would silently repoint every existing
avatar at an object that was never written.

The `<personId>` is deliberately redundant with the record it sits on — see the ownership section
below for why the object is keyed per person at all. Carrying it in the stored value keeps
read-resolution a pure prefix-and-suffix operation with no dependence on the surrounding context,
which is less code and fewer ways to be wrong than reassembling it from whichever record is being
read. It costs eight bytes.

Neither end of that is arbitrary. Storing the absolute URL would bake an environment's hostname into
the data, so a production snapshot restored into an ephemeral environment would serve production's
photos. Returning a bare path would push host knowledge onto every client — the implicit coupling
this revision exists to remove. Storing the path and resolving on read keeps stored data portable
and clients ignorant, and the API needs nothing from any other repository to do it.

Consequence for the webapp: `originRelative()` in `PersonAvatar.tsx` is **deleted**, and `src` is
used exactly as the API gave it.

Consequence for demo-data: its read-back must compare on the **path portion** of a returned
`avatarUrl`, not the whole string, so the comparison stays environment-agnostic.

### Every object belongs to exactly one person, and carries the hash of its *source* bytes

The served object is `avatars/v1/<personId>/<sha256-of-uploaded-bytes>.jpg` in the bucket, reachable
at `/v1/<personId>/<sha256>.jpg` on the distribution — see the note on `origin_path` below for why
those differ.

**This reverses an earlier draft**, which keyed purely on the content hash so that two people with
the same image shared one object. That was elegant and it is now wrong, because of two requirements
added on 2026-09-29: deleting a person must delete their avatar, and a person may have at most one
avatar. Neither is expressible over a shared object. Deleting the object behind person A's avatar
would silently break person B's, and "at most one" is a statement about a person, not about a blob.
Reference counting would fix it and is far more machinery than an avatar deserves.

Scoping the key by person makes both requirements structural rather than enforced by care:

1. **Deletion is safe.** A person's avatar is theirs alone, so removing it is deleting a prefix
   nothing else can reach.
2. **"At most one" is enforceable.** The prefix is the invariant: after a successful set, exactly
   one object exists under it.

Keeping the content hash *inside* that key preserves everything the earlier design used it for:

3. **`immutable` stays honest.** Different bytes mean a different key, so a cached URL can never go
   stale, and replacing an avatar needs no invalidation.
4. **demo-data can still read back what is in use.** It hashes its own bundled file and looks for
   that hash among the returned `avatarUrl`s. It must now extract the **hash segment** rather than
   compare whole paths, since the same image under two people yields two different URLs. This still
   depends only on the *source* bytes, which demo-data holds — never on server-side processing being
   byte-for-byte reproducible, which would have been brittle across a library upgrade.

What is given up is deduplication: the same image under two people is now two objects. At ~15 KB
each against a pool of 200, that is not worth a moment's thought — and it buys the disappearance of
the "unreferenced objects accumulate forever" problem entirely, since every object now has exactly
one owner and dies with them.

The `v1/` segment is the **processing version**, and exists precisely because the key holds the hash
of the input rather than the output. If normalisation ever changes (different dimensions, encoder,
quality), bump to `v2/`: existing URLs keep serving the bytes they always served, and new uploads
get new keys. Without it, `immutable` would be a lie the first time the resize changed.

### An avatar is deleted with its person, and replaced atomically enough

**On person deletion.** All three paths that remove a person — `deletePerson` (admin),
`deleteMyAccount` (self) and `database-reset` — delete everything under `avatars/v1/<personId>/`.
The first two are prefix deletes; `database-reset` already empties the whole bucket, so it is
covered by construction.

**On setting an avatar.** `confirmAvatarUpload` writes the new object, updates the record, then
deletes every *other* object under the person's prefix. That order is deliberate: a crash midway
leaves a harmless orphan that the next set will sweep up, whereas deleting first would leave a
person with a record pointing at an object that no longer exists — a broken avatar rather than a
wasted 15 KB. The sweep must exclude the key just written, since re-uploading the same image
produces the same key and deleting it would erase the avatar that was just set.

Note this makes `removeAvatar` cheap and obvious rather than a special case: it is the same prefix
delete with the record set to null.

### Upload is a presigned PUT with a synchronous confirm

Three calls: `requestAvatarUpload` returns a presigned URL; the client PUTs the bytes straight
to S3; `confirmAvatarUpload` validates, normalises, stores and sets `avatarUrl`, returning
errors synchronously in the project's usual `errors: [...]` result shape.

Fully async processing (S3 event → processor → subscription) was rejected as disproportionate. For
a ≤2 MiB avatar the decode-and-resize is milliseconds against a 15 s timeout, and rejection
feedback would otherwise have to travel back over a subscription or live in a status field on
`Person` — materially more API surface for no gain at this size.

The existing `daysInvalidated` subscription precedent (carry a signal, let the client refetch) is
noted and deliberately not used here: there is nothing to signal, because the mutation returns.

### `avatarUrl` stays a bare `String`

AppSync permits no arbitrary custom scalars — only its own fourteen — so the realistic alternatives
were `AWSURL`, an `Avatar` object type, a field with a `size` argument, or a union over avatar
kinds. Every other field in this schema is already a bare `String` with a precise description, down
to `linkedEmails: [String!]!` rather than `AWSEmail` and ISO date-times rather than `AWSDateTime`.

`AWSURL` had the strongest case, and not merely for tidiness: `avatarUrl` is composed at read time
from a Lambda environment variable, so a misconfigured host would hand every client a broken URL
that fails as an initials fallback — precisely the silent failure this refactor exists because of.

It was still rejected, because the guard it offers is weaker than the one already planned.
Well-formedness is not reachability: `https://` followed by nonsense is a perfectly valid URL. The
acceptance check in Definition of done fetches the URL and asserts it returns `image/jpeg`, which
proves the bytes are genuinely there. Buying a weaker check at the cost of the schema's consistency
is a bad trade.

Note for anyone revisiting this: the absence of AWS scalars elsewhere is *not* evidence they were
rejected on principle. `AWSDateTime` demands a time-zone offset that this codebase's naive local
times do not have, which is a real semantic conflict — it does not generalise to `AWSURL`.

An `Avatar` object type remains the right shape if alt text or a placeholder image ever appears.
Today it would carry one real field and two constants.

### The GraphQL surface says "avatar", not "photo"

`Person.photoUrl` becomes **`Person.avatarUrl`**, and the mutations are `requestAvatarUpload`,
`confirmAvatarUpload` and `removeAvatar`.

"Avatar" is the general concept — the thing shown next to a person's name, whatever it is made of.
"Photo" is one possible kind, and deliberately not the kind this design ships: calling a generated
vector cartoon a photo would be plainly wrong. Keeping the general name now leaves room for a
genuine `photo` concept later without a second rename, which is the reasoning Geoff gave for the
choice. Every other part of the project already says avatar — `PersonAvatar.tsx`,
`designs/archive/person-avatar-photos.md`, this document's own title — so this removes the outlier
rather than introducing a new word.

The cost is a breaking schema change and a stored-attribute rename. Both are cheap **only because
of when this happens**: the schema is already being versioned in this change, every client is ours,
and the rollout is a reset-and-reseed that discards existing values anyway. The same rename in six
months would need a migration and a deprecation window.

### `createPerson` loses its `avatarUrl` argument

Setting a photo becomes the upload flow's job, and only the upload flow's job. This restores
`createPerson(name: String!)` to its original shape and removes the one place where an unvalidated
client-supplied path could reach storage. demo-data creates a person and then uploads, exactly as
the webapp would.

### `PersonRepository` moves from `PutItem` to `UpdateItem`

This was raised as possibly redundant once photos have a dedicated mutation. It is not. Today every
handler that changes a person rebuilds the whole `Person` record and `PutItem`s it, so
`RenamePersonHandler`, `UpdateMyNameHandler`, `SetPersonAdminHandler` and
`UpdateMyPreferencesHandler` each carry a hand-written `current.get().avatarUrl()` purely to avoid
erasing a field they have no interest in. A dedicated photo mutation removes one instance of that
problem and adds another — the photo mutation would itself have to carry `name`, `isAdmin` and all
three preferences forward.

Switching to attribute-level `UpdateItem` expressions eliminates the entire class structurally, for
every field added from here on, and is what makes the new mutation safe to write at all. This is
the fix; the dedicated mutation is not a substitute for it.

### The avatar images ship in two phases: procedural first, photorealistic later

Whatever the images are, they are **never photographs of real people**. A permissive licence covers
copyright but says nothing about personality and publicity rights, and using an identifiable real
person's photograph to represent a fictional employee in a product demo is a different act from
reusing their photo. They also live in mootmaker-demo-data rather than the webapp, because that is
the only component that uses them — bundling them into the webapp is what created the cross-repo
filename convention that broke.

**This design ships procedural vector avatars.**
[DiceBear](https://www.dicebear.com/licenses/) publishes **42 CC0 1.0** styles — public domain, no
attribution, commercial use and redistribution both explicitly permitted, so nothing to reason about
for a public repository. No GPU, no model, no generation run, no model licence.

Licences are **per style**, and the split matters: 42 are CC0, **14 are CC BY 4.0** (Adventurer, Big
Ears, Big Smile, Croodles, Dylan, Fun Emoji, Glyphs, Micah, Miniavs, Personas, Toon Head and their
Neutral variants) and would oblige us to carry visible designer credit; Icons is MIT; and Avataaars
and Bottts carry the artist's own terms. Only the CC0 set is in scope here.

Most of those 42 are abstract — rings, shapes, waves, planets. The styles that actually depict a
person, and so are real candidates, are **Lorelei, Notionists, Open Peeps and Pixel Art**, each of
which also has a **Neutral** variant. `Initials` is CC0 too but is precisely what the existing
fallback already draws, so it would be a no-op.

The DiceBear **library code** is MIT (Copyright 2026 Florian Körner). That obligation attaches to
redistributing the library, which this design never does — the CLI is used once at authoring time
and only its output images are committed. Worth noting in case that ever changes.

Photorealistic avatars are a **separate design** —
[photorealistic-demo-avatars.md](photorealistic-demo-avatars.md) — because they need a GPU machine
this one does not assume, and because they change nothing here. The upload path, the bucket, the
distribution and every handler are identical either way: demo-data uploads through the same three
API calls whatever the bytes are. That design replaces a directory of images and reseeds. Nothing in
this document waits on it, and if it never happens, what ships here is a complete, working feature
rather than half of one.

### The pool is pre-generated and committed, not generated in Java at seed time

A Java-native generator — roughly 200–300 lines of `java.awt` composing shapes from a hash of the
person's name — was considered and rejected. It would delete the pool, the read-back, the exhaustion
check and the Node build-time dependency, and scale past any `TARGET_PEOPLE`, which is a real
simplification. Against it: the output is bespoke art whose quality rests on shape composition
rather than on a designer's work, and the pool machinery has to exist anyway for
[photorealistic-demo-avatars.md](photorealistic-demo-avatars.md) — so removing it here would only
mean building it there. DiceBear gives proven artwork under CC0 for the cost of a build-time CLI
whose output is committed.

### The pool-and-read-back mechanism is genuinely needed, not deferred

Worth recording because the first instinct was wrong. Procedural avatars are deterministic from a
seed, so seeding on a person's name — already unique by construction via `SampleData.personNames` —
appears to make uniqueness free and delete the pool, the read-back and the exhaustion check outright.

It does not, because generation cannot happen at seed time. DiceBear is a JavaScript library and
mootmaker-demo-data is a Java Lambda; calling `api.dicebear.com` during a run would put a
third-party service on the critical path of seeding an environment. So the images are pre-generated
with the DiceBear CLI at authoring time and committed as classpath resources, which makes them a
**pool** exactly like photographs would be.

That is a good outcome rather than a concession: the uniqueness machinery a photorealistic pool
would need anyway gets built and proven here, so a later swap touches no structure. The pool is
sized generously (see below) precisely because these images are free to regenerate.

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
3. **JPEG-only output at 256×256.** Comfortably above 2× the largest rendered size. Transparency is
   lost, which does not matter under a circular mask — but note it means the vector avatars
   are rasterised and flattened onto a background rather than served as SVG, which is the price of
   one canonical derivative for every image regardless of origin.
4. **Accepted input types are JPEG and PNG only.** Both are handled by `javax.imageio` in the JDK.
   WebP would need a third-party decoder, and this codebase has previously declined a 2 MB
   dependency for one method call. DiceBear's CLI renders PNG, so no SVG support is needed.
5. **2 MiB upload ceiling, minimum 64×64, maximum 4096×4096.**
6. **A pool of 200**, against a default `TARGET_PEOPLE` of 100. Larger than the 120 first proposed
   because procedural images cost nothing to generate, so headroom is free.
7. **Notionists Neutral**, a CC0 style. Clean line-drawn people that read as professional rather
   than playful, which suits a meeting-booking tool, and which sit next to a name without competing
   with it. The Neutral variant carries no gender cues — which is what makes choice 11 possible.
   The CC-BY styles (Adventurer, Big Smile, Micah, Personas and others) are usable but require
   visible designer credit, meaning a UI attribution surface this feature does not otherwise need.
8. **The subdomain is `avatars.<environment>.mootmaker.com`** (`avatars.mootmaker.com` in
   production), sitting alongside the existing `api.` and `www.`. `media.` or `assets.` would read
   as more general and invite unrelated content onto a distribution designed around immutable
   content-addressed objects.
9. **`database-reset` also empties the avatars bucket.**
10. **The distribution defines no `default_root_object` and no custom error responses**, so a
    request to the bare host gets S3's own 403 unchanged. Nothing legitimate ever asks for this
    host's root — every real URL is `/v1/<personId>/<hash>.jpg` — so anything landing there is a bug
    or a probe, and both are better served by a plain refusal than by a redirect that would put
    webapp knowledge back into the API's infrastructure. Stated explicitly rather than left to
    CloudFront's defaults, because the bug this refactor follows came precisely from an unexamined
    default quietly rewriting 403/404 to `index.html` at status 200.
11. **Gender matching is dropped here, and `FEMALE_FIRST_NAMES` deleted with it.** DiceBear styles
    are seeded from a string and take no gender, so matching would mean biasing per-style options —
    suppressing facial hair on one half, say — which is both fiddly and a stereotype written into
    code. A Neutral variant sidesteps it entirely. The tagging set is removed rather than left
    unused, since dead code that exists "for a future design" is dead forever if that design never
    lands; [photorealistic-demo-avatars.md](photorealistic-demo-avatars.md) re-adds it, where it
    genuinely earns its place.

## Open questions

**None.** Every question this design raised has been answered and moved into Trade-offs or Choices
above, on 2026-09-29:

| Was | Settled as |
|---|---|
| Image sourcing | Procedural CC0 avatars; photorealistic split to its own design |
| `avatarUrl`'s type | A bare `String` |
| DiceBear style | Notionists Neutral |
| Distribution root behaviour | Explicit 403, no root object, no custom error responses |
| Gender matching | Deferred to [photorealistic-demo-avatars.md](photorealistic-demo-avatars.md) |
| Pool vs Java-native generation | Pre-generated DiceBear pool |

The only remaining unknowns are implementation details that resolve themselves in the doing, not
decisions anyone is waiting on.

## Impacts on components

### mootmaker-api

- `api/mootmaker.graphql` — three new mutations, new result/error types, `avatarUrl` removed from
  `createPerson`. Version bump in `api/package.json` (the publish workflow fails otherwise — this
  has bitten twice).
- `impl/.../handler/` — new `RequestAvatarUploadHandler`, `ConfirmAvatarUploadHandler`,
  `RemoveAvatarHandler`; registered in `ResolverDispatchHandler`, and constructed eagerly in
  its constructor so they are captured in the SnapStart snapshot.
- `impl/.../handler/CreatePersonHandler.java` — drops the `avatarUrl` argument.
- `impl/.../handler/DeletePersonHandler.java` and the `deleteMyAccount` path — each deletes
  everything under `avatars/v1/<personId>/` as part of the existing cascade.
- `impl/.../dynamo/PersonRepository.java` — `PutItem` → attribute-level `UpdateItem`; new
  `updatePhotoUrl`.
- `RenamePersonHandler`, `UpdateMyNameHandler`, `SetPersonAdminHandler`,
  `UpdateMyPreferencesHandler` — each loses its hand-written carry-forward.
- New image validation/normalisation class, and a small S3 wrapper.
- `impl/.../handler/DatabaseResetHandler.java` — also empties the avatars bucket.
- `deploy/terraform/` — new `s3.tf` for the avatars bucket (versioning off, public access blocked,
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
  values become absolute `https://avatars.…` URLs.
- `webapp/src/components/PersonAvatar.tsx` — `originRelative()` deleted; `src` used as given.

### mootmaker-demo-data

- `impl/src/main/resources/avatars/` — new, 200 PNGs (~3 MB into a 12 MB shaded jar).
- `SampleData.java` — `FEMALE_AVATAR_PHOTOS`/`MALE_AVATAR_PHOTOS` collapse into one pool of
  classpath resource names, and `FEMALE_FIRST_NAMES` is deleted;
  `avatarPhotoFor` takes the set already in use and returns an unused resource or null.
- `DemoData.java` — `topUpPeople` creates the person, then requests, PUTs and confirms.
- `GraphQlClient.java` — needs a plain binary PUT alongside its GraphQL POST.
- A committed generation script plus a short README note recording the DiceBear style, the seeds and
  the CLI invocation used, so the pool is reproducible rather than a pile of mystery bytes. This is
  authoring-time tooling; nothing at runtime depends on Node or on DiceBear.

## Changes to the domain data model and data storage models

Delta against [`../docs/reference/data-model.md`](../docs/reference/data-model.md):

- **DynamoDB `People` table** — the `photoUrl` attribute is **renamed to `avatarUrl`**, keeping its
  meaning and nullability. Its *format* also narrows, to `v1/<personId>/<sha256>`, and only the API
  may now write it. The stored value is deliberately **not** what the API returns — host and
  extension are added on read, so stored data carries no environment hostname and no boilerplate.
  Writes change from full-item `PutItem` to attribute-level `UpdateItem`, a storage-access change
  rather than a shape change.
- **The attribute rename needs no migration, but only because of the rollout.** Nothing reads
  `photoUrl` after this ships, and every existing value points at a webapp-bundled file the change
  deletes, so the old attribute is simply abandoned rather than copied forward. That is safe here
  and would not be for an attribute holding data anyone cared about — worth stating, because "we
  renamed a DynamoDB attribute with no migration" is otherwise a dangerous precedent to copy.
  Stray `photoUrl` attributes disappear with the reset.
- **Cognito** — unaffected.
- **New: S3.** One bucket per environment, `<env>-mootmaker-avatars-<account>`, with two
  prefixes: `uploads/<personId>/<uploadId>` (private staging, expired after 1 day by lifecycle
  rule) and `avatars/v1/<personId>/<sha256>.jpg` (served, `immutable`, one object per person).
- **New: DNS.** One `avatars.<environment>.mootmaker.com` A/AAAA record pair per environment in the
  `mootmaker.com` hosted zone that mootmaker-domain owns, plus a per-environment ACM certificate.
- **No backfill.** Existing values are demo data only, and the rollout is a reset-and-reseed, so
  nothing is migrated.

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
- **`confirmAvatarUpload` must be idempotent.** The key is a pure function of the bytes, so a
  repeat is a no-op overwrite of identical content.
- **Lambda needs S3 in the SnapStart snapshot.** Build the S3 client eagerly, in the constructor,
  like every other handler dependency.
- **The avatar host must be configuration, never derived.** The resolver Lambda reads it from an
  environment variable set by this repo's own Terraform. Reconstructing it from the environment name
  in code would reintroduce, in string concatenation, exactly the implicit coupling this revision
  removes — and would get production wrong on the first try, since production drops the environment
  segment.
- **The distribution uses `origin_path = "/avatars"`**, so the public URL carries no path prefix and
  `https://avatars.mootmaker.com/avatars/v1/...` does not stutter. That is the cosmetic reason. The
  substantive one is that `origin_path` makes the `uploads/` prefix **unreachable through
  CloudFront at all**: staging objects cannot be fetched publicly even by an exact-key guess, which
  is a stronger guarantee than a bucket policy that has to be read correctly to be trusted.
- **`database-reset` must empty the bucket, not delete it.** The bucket is a Terraform resource; a
  reset that removed it would put Terraform and reality out of step.
- **Certificate validation is the slow part of a first deploy.** ACM DNS validation against the
  hosted zone typically takes a few minutes, and Terraform blocks on it. This lands on the critical
  path of creating an ephemeral environment.
- **The DiceBear CLI needs Node and is authoring-time only.** It runs once to produce the pool,
  whose output is committed; nothing in the build, the jar or the Lambda depends on it afterwards.
  Per the process rules it still belongs in
  [`../tools/workstation/manifest.yaml`](../tools/workstation/manifest.yaml) as a tool future work
  will need.
- **Vector art is rasterised.** DiceBear renders SVG; the pool is PNG, and the API then
  normalises to JPEG at 256×256. Flattening happens twice, so the source PNGs should be generated at
  256×256 or larger with an opaque background, not scaled up from something smaller.
- **What this leaves behind:** staging uploads (bounded by the 1-day lifecycle rule); served photo
  objects (bounded per environment by the demo pool, unbounded once real uploads exist — open
  question 3); one Route53 record pair and one certificate per environment, both destroyed with the
  environment; no new logs or metrics beyond normal Lambda output.
- **Cost:** ~2 MB of S3 per environment, a negligible request volume, one free ACM certificate and
  one CloudFront distribution with no fixed charge. Well under NZ$1; no recurring charge worth
  flagging. The real cost is minutes of ephemeral environment turnaround, not dollars.

## Testing impacts

**Unit (mootmaker-api)** — the natural home for validation and for the ownership rules, because
both are logic with no deployment needed. The ownership cases matter most: setting an avatar twice
leaves exactly one object under the person's prefix; re-uploading the *same* image does not delete
the avatar it just set (the key is identical, so a naive "delete everything else" sweep would erase
it); and deleting a person removes their prefix while leaving another person's identical image
untouched — the case that global content-addressing would have got wrong. Then validation, which is
pure logic over bytes: reject a non-image, a too-large dimension, a mismatched declared length,
an unsupported type; confirm the key is the source hash and is stable across runs; confirm EXIF does
not survive. Plus the `UpdateItem` refactor: each of the four existing carry-forward regression
tests (including the two `regressionMootmakerApi71...` ones) should keep asserting the same
outcomes, but now pass because the repository cannot clobber rather than because a handler
remembered.

**Unit (mootmaker-demo-data)** — the existing `DemoDataTopUpTest` case for the 10%-no-avatar rate
stays. Two are **deleted**: `everyAssignedPhotoIsOriginRelative`, because the path is no longer
demo-data's to construct, and `everyAssignedPhotoMatchesTheFirstNamesTaggedGender`, because gender
matching moves to [photorealistic-demo-avatars.md](photorealistic-demo-avatars.md). New: never assigns a photo already in use given a set of existing
`avatarUrl`s; throws rather than repeating when the pool is exhausted; every bundled resource is
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

- `docs/reference/data-model.md` — narrow `avatarUrl`'s described format, note that the stored value
  is a path and the returned value absolute; add the S3 bucket, its two prefixes, and the subdomain.
- `docs/reference/use-cases.md` — one new numbered case for the acceptance test above.
- `docs/development/` — the cross-repo architecture gains a second custom domain; mootmaker-api is
  no longer AppSync-URL-only.
- `mootmaker-api/README.md` — the avatars bucket, distribution and subdomain, the upload flow, and
  `database-reset`'s widened remit.
- `mootmaker-webapp/README.md` — avatars are no longer bundled or served by this component at all.
- `mootmaker-demo-data/README.md` — the bundled photo library and the create-then-upload sequence.
- `mootmaker-domain/README.md` — if it enumerates which hostnames exist, `avatars.<env>` joins them.
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
3. mootmaker-demo-data — avatar library and upload flow.
4. Per environment: deploy all three, `database-reset`, then invoke demo-data.

Between steps 1 and 2 the webapp renders initials for everyone: it is still selecting `photoUrl`,
which no longer exists. A visibly degraded but not broken state, and short-lived — but note this is
a **hard** break rather than a soft one, because the field is renamed rather than merely reformatted.
The webapp's `codegen:check` will fail until step 2 lands, which is the intended behaviour and not
a reason to delay step 1.

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
- **Image licensing** is the one risk that is awkward rather than merely expensive to reverse: once
  images are committed to a public repository, a licence problem means a history rewrite, not a
  deletion. CC0 styles reduce this close to zero, being public domain — but
  DiceBear licences are **per style**, not library-wide, so picking a CC-BY style by mistake would
  reintroduce an attribution obligation. Verify the chosen style's licence at the point of
  generation, not from memory.
- **[photorealistic-demo-avatars.md](photorealistic-demo-avatars.md) quietly not happening** would
  leave the product on cartoon avatars indefinitely. That is a legitimate outcome — nothing here is
  incomplete without it — but it should be closed deliberately rather than left drifting.
  Non-blocking question 3 notes the cheaper design that would then be right.
- **Retiring the nested-route regression test** removes a guard that caught a real shipped bug. It
  is only safe because the rule it guarded ceases to exist; if absolute URLs are ever walked back,
  that test must come back with them.

## Implementation checklist

Filled in properly once this reaches Ready; sparse while Drafting.

1. `[Geoff]` Move this design to **Ready** if it is. Nothing is blocked and no `[Geoff]` items
   remain — every open question is answered and recorded above. Note the field rename means steps 4
   and 7 are no longer deployable in either order: the webapp must follow the API, not precede it.
2. `[Claude]` mootmaker-api: `PersonRepository` `PutItem` → `UpdateItem`, and strip the four
   handlers' carry-forward. Own commit, own PR — independently valuable and independently
   reviewable, and does not depend on anything else here. **This can start immediately.**
3. `[Claude]` mootmaker-api: photos bucket, distribution, certificate, DNS, IAM.
4. `[Claude]` mootmaker-api: schema, three handlers, validation/normalisation, host resolution on
   read, version bump.
5. `[Claude]` mootmaker-api: `database-reset` empties the bucket.
6. `[Claude]` Deploy and verify mootmaker-api **on its own**, with no webapp — proving the
   independence this design is built around, before anything downstream moves.
7. `[Claude]` mootmaker-webapp: schema bump, codegen, delete `public/avatars/`, remove
   `originRelative()`, update fixtures, retire the nested-route case.
8. `[Claude]` Generate the 200-image Notionists Neutral pool with the DiceBear CLI and commit it
   with its regeneration script, then mootmaker-demo-data: bundle it, collapse the two gendered
   pools into one, delete `FEMALE_FIRST_NAMES`, and add the binary PUT.
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
  100 demo people hold **90 distinct** avatars and 10 none, with no image shared by two people —
  checked by comparing the returned `avatarUrl`s, not by trusting the assignment code.
- The new acceptance case proves `naturalWidth > 0`, and the existing acceptance suite is still
  green on that environment.
- A served photo responds with `Cache-Control: public, max-age=31536000, immutable` and a real
  404 for a missing key, both verified against the deployed distribution rather than inferred from
  Terraform.
- Teardown of that environment leaves no certificate or DNS record behind, confirmed by looking.
- Every item under Documentation impacts actually done.
- mootmaker-webapp#131 closed by the acceptance case, not by a comment.
