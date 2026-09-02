# GraphQL schema sharing

## Summary

`mootmaker-api/api/mootmaker.graphql` is the one source of truth for the API contract.
`mootmaker-webapp/webapp/src/graphql/types.ts` is a hand-maintained TypeScript mirror of it, kept in
sync by a human (or an agent) remembering to update both when the schema changes. Nothing enforces
that they agree, and `mootmaker-android` will need the same schema a third time. This design
proposes publishing the schema as a versioned artifact — npm via npmjs.com, Maven via GitHub
Packages — so every consumer reads one file instead of re-typing it.

**Status:** Building — 2026-09-02

*(Promoted straight from `Drafting` to `Building` on Geoff's instruction to implement. The `Ready`
stamp was never applied — noted rather than glossed over, since `Ready` is the one human-gated
transition in the lifecycle. Every blocking question had already been answered on 2026-09-02.)*

---

## Scope / non-goals

### In scope

- Publishing `mootmaker.graphql` as a versioned artifact on merge to `main` in `mootmaker-api`.
- A consumption path for `mootmaker-webapp` (npm) and, when it exists, `mootmaker-android` (Maven).
- Evaluating whether to also generate TypeScript/Java types from the schema, or to publish the raw
  schema and leave typing to each consumer.

### Non-goals

- **Building this now.** This design is created and left at `Drafting`, per
  `designs/project-reorganisation.md`'s Decision 11 — it records the problem and the strongest
  candidate solution, and is picked up as its own piece of work later.
- **Choosing a GraphQL code-generation tool in depth.** Named as an open question, not resolved
  here — see Open questions.
- **Retrofitting `mootmaker.graphql` itself.** This is about *distributing* the schema, not changing
  its content or authoring workflow.
- **A schema registry with change-detection/breaking-change linting** (e.g. GraphQL Hive, Apollo
  Studio). Worth a mention as a fancier alternative (see Trade-offs), but out of scope for a schema
  this size (145 lines today) whose consumers do not yet release independently — see NB-4.
- **Converting the Java consumers to generated operations.** Deferred by Decision 9; the artifact
  they will use is published by this design, but adopting it is later work.

---

## Trade-offs and decisions

### 1. Distribution mechanism: npmjs.com for npm, GitHub Packages for Maven

**Decision (revised 2026-09-02):** publish the npm artifact to **npmjs.com** as
`@mootmaker/schema`, and the Maven artifact to **GitHub Packages**. The original decision put both
on GitHub Packages; research for NB-2 found a limitation that changes the answer for the npm half.

**What changed:** GitHub Packages requires an access token to *install* a package — **even a public
one**. Only its Container registry allows anonymous pulls; npm and Maven both demand authentication
regardless of visibility. So a stranger cloning `mootmaker-webapp` and running `npm install` gets a
401 until they create a personal access token and configure `.npmrc`. For a project whose
`production` environment exists to be looked at by prospective employers, making the front-end repo
unbuildable-on-clone is a real cost, and it is not one the original decision weighed.

npmjs.com has no such restriction: public scoped packages are free, installable anonymously, and
Dependabot understands them natively with no credential configuration — which matters, because
Decision 8's automated bump PR is what makes a declared version workable end to end.

The Maven half stays on GitHub Packages deliberately. Its consumers (`mootmaker-demo-data`,
`mootmaker-android`) are this project's own repositories, built by Geoff or by CI that already has a
`GITHUB_TOKEN`, so the token requirement costs nothing there — where the alternative, Maven Central,
costs GPG signing keys, a namespace claim, and a slower release ritual for no benefit this project
can currently use.

**The asymmetry is the point:** the artifact a stranger might install anonymously goes somewhere
anonymous; the artifact only this project consumes goes where it is free and already authenticated.

**Options weighed:**

| Option | Verdict |
|---|---|
| **npmjs.com (npm) + GitHub Packages (Maven)** | **Chosen 2026-09-02.** Anonymous install where it matters, free and already-authenticated where it does not. Costs one npm organisation and an `NPM_TOKEN` secret. |
| **GitHub Packages for both** | Originally chosen; rejected on the token-to-install finding above. One store rather than two is genuinely simpler, and remains right for Maven — but it would make the public webapp repo unbuildable without a PAT. |
| Maven Central for the Java half | Rejected. Anonymous like npmjs.com and has showcase value for a portfolio, but costs GPG signing keys, a namespace claim and a slower release ritual — real cost for a consumer set that is entirely this project's own repositories. |
| A versioned S3 object | Rejected as the primary path. Works, and mootmaker already has an S3-literate Terraform setup, but it's one more piece of infrastructure to provision and secure (bucket policy, versioning config) for a problem GitHub Packages already solves for free. Worth reconsidering only if GitHub Packages turns out to have a real limitation (see Open questions). |
| GitHub Releases assets | Rejected. Releases are a reasonable place for a human-facing changelog artifact, but neither `npm install` nor Maven has native support for resolving a dependency from a Release asset URL the way they do for a proper package registry — every consumer would need custom fetch logic instead of `npm install`/`<dependency>`. |
| A schema registry (Hive, Apollo Studio) | Rejected for now. Real value (breaking-change detection across consumers, a web UI, schema diffing) but real cost/complexity for a two-repo, 145-line schema. Revisit if the schema or the consumer count grows meaningfully — see Open questions. |

### 2. What gets published: the raw schema, not generated types — for now

**Decision:** publish `mootmaker.graphql` itself as the artifact content. Do not generate and
publish TypeScript/Java types as part of this design's first version.

**Reasoning:** publishing the raw schema is the smaller, more reversible first step, and it already
solves the actual problem stated in the summary — one file, not three hand-typed copies of the same
contract. Type generation is valuable but is a second decision (which codegen tool, per language)
layered on top; bundling it in risks the whole design stalling on a tool choice rather than shipping
the simpler win first.

### 3. Publish trigger: on merge to `main`, versioned

**Decision (revised 2026-09-02):** the schema is published by its **own standalone GitHub Actions
workflow** in `mootmaker-api`, triggered on merge to `main` when `api/mootmaker.graphql` changed.
It does **not** wait for `designs/ci-cd-pipeline.md`.

**Why the change:** the original decision made this a step inside a pipeline that does not exist —
and `ci-cd-pipeline.md` is still `Drafting` with three genuinely blocking questions needing Geoff's
judgement (approval-gate shape, ephemeral-per-PR, OIDC account/role scope). That would gate this
design behind a design gated on a person, for no technical reason: publishing a static file when it
changes is a dozen lines of YAML with no deployment concerns, no AWS credentials and no
environment targeting.

The dependency also pointed the wrong way round. A small, working publish workflow is something the
CI/CD design can **absorb** when it lands; a reserved step in an unbuilt pipeline is not something
this design can build against. Shipping the smaller thing first is what makes the bigger one
concrete.

**What this gives up:** for now, publishing and deploying are two workflows rather than one, so
there is a window where the schema is published and the API serving it is not yet deployed.
Decision 8 addresses the consequence that actually bites — the webapp's deploy-time introspection
gate — and that gate does not care which workflow published the schema. When the CI/CD design
lands, folding the publish step into the API's deploy pipeline closes the window properly.

---

## Choices you had me make

1. ~~**Chose GitHub Packages over S3 as the primary recommendation**~~ — **superseded 2026-09-02.**
   The "one store instead of two" argument was real but rested on an assumption that did not survive
   checking: that a public package could be installed without credentials. It cannot, on npm or
   Maven. S3 was not the answer either (neither package manager resolves from it natively); splitting
   the registries was. See Decision 1.
2. **Separated "publish the schema" from "generate types from it"** into two decisions rather than
   one, and scoped this design to only the first. Judgment call about what makes a reviewable,
   shippable first step; easy to disagree with.

---

### 4. The schema stays in `mootmaker-api`

**Decision (2026-09-01):** the schema is not pulled into its own repository. `mootmaker-api` remains
its home and publishes it; the webapp and Android consume the published package.

**Reasoning:** the schema is the API's *interface*, not an independent artifact. `appsync.tf`
reads it directly at deploy time (`schema = file(".../api/mootmaker.graphql")`), and adding a field
without adding a resolver produces a field that resolves to nothing — so schema and API change
together essentially always. A separate repository would create two repositories that must change
in lockstep while claiming to decouple them, and would make an API deploy depend on a package
registry being reachable to fetch its own contract.

The webapp and Android are genuinely different: they are downstream, change *after* the schema, and
can legitimately lag a version. That asymmetry is real, and a shared repository erases it by
treating all three consumers as equals when only two of them are.

**Revisit if** the schema starts changing without API changes, ownership of the contract separates
from the API, or contract changes need their own review gate.

### 5. Version: declared in the PR, enforced by registry immutability

**Decision (2026-09-01, unchanged 2026-09-02):** `api/package.json` — sitting beside
`mootmaker.graphql` — holds the version, and a human (or agent) bumps it in the same pull request
that changes the schema. That file is the single source of truth; the Maven `pom.xml` is generated
in CI from the same string, so one version means one thing in both registries — now npmjs.com and
GitHub Packages respectively (Decision 1). Both are immutable, so the safety argument below holds
across the split.

**What makes this safe without tooling:** package registries are immutable, so the failure mode you
would most expect — changing the schema and forgetting to bump — cannot silently succeed:

| Scenario | Outcome |
|---|---|
| Schema changed, version bumped | publishes |
| Schema changed, version forgotten | **build fails** — that version already exists |
| Schema unchanged | publish skipped; no spurious version |

The pipeline should check for an existing version *explicitly* rather than letting `npm publish`
throw, so the error reads "schema changed but package.json still says 1.4.0" instead of a raw 409.

**What this deliberately does not do:** nothing verifies the *classification*. A breaking change
published as a patch will publish happily, and a consumer on a caret range would take it
automatically. Accepted knowingly at this scale — a 145-line schema whose consumers all currently
release alongside the code they serve, where the pull request shows the schema diff and the version
bump side by side. **Revisit when the schema
stops being diffable by eye, or when whoever changes it is no longer the person reviewing the
consumers — realistically when Android lands.** `graphql-inspector` in CI then slots into the
existing existence-check step without changing anything else. This resolves **NB-3**.

### 6. Consumers generate their own types; codegen lives in the consuming repo

**Decision (2026-09-01):** the published artifact stays the raw `.graphql` file (Decision 2 stands),
and each consumer runs its own code generation — `types.ts` in `mootmaker-webapp`, Kotlin in
`mootmaker-android`. No generated-types package is published. This resolves **NB-1**.

**Evidence this is needed rather than theoretical:** implementing `date-time-format-settings`
required editing the schema, the Java model, *and* the hand-written `types.ts` mirror, with only
discipline keeping them aligned. That is the second data point NB-1 was waiting for.

Both npm and Maven artifacts are published from the start. This was originally justified only by
Android getting a complete version history rather than starting mid-stream — but that undersold it.
**The Maven artifact has a live consumer today**, which this design (and the discussion that
produced it) had missed:

| Consumer | Language | How it depends on the schema now | Gets the artifact via |
|---|---|---|---|
| `mootmaker-webapp` | TypeScript | hand-written `types.ts` mirror | npm |
| `mootmaker-demo-data` (`impl/`) | Java | hand-written GraphQL operation strings | Maven |
| `mootmaker-demo-data` (`verify/`) | Java | its own `GraphQlClient` and operation strings — **added 2026-09-02** with the demo-data component's acceptance suite | Maven |
| `mootmaker-api/verify` | Java | 16+ operation strings across 8 acceptance-test classes | the local file — same repo |
| `mootmaker-android` | Kotlin | does not exist yet | Maven |

**The consumer count is five, not the two this design was written against** — and it grew during
this design's own lifetime: `mootmaker-demo-data`'s acceptance suite (2026-09-02) added a fifth
hand-written client. That is the clearest evidence available that the duplication compounds rather
than holds steady.

`mootmaker-demo-data` writes exclusively through the GraphQL API (it touches DynamoDB in zero Java
files), building mutations like
`"mutation CreatePerson($person: PersonInput!) { createPerson(person: $person) { id name } }"` as
string literals. That is a **third hand-maintained mirror of the contract**, alongside the webapp's
`types.ts` and the API's own Java models — and the worst of the three, because a string literal
that no longer matches the schema fails at runtime against a deployed environment rather than at
compile time.

Every consumer generates typed, compile-checked operations from the schema rather than validating
hand-written strings against it (decided 2026-09-01, see NB-5) — the mechanism is each consumer's
own choice, the outcome is not. `mootmaker-api/verify` is the exception that needs no artifact: it
lives in the same repository as the schema and can generate from the file directly.

### 7. Local development reads the sibling checkout

**Decision (2026-09-01):** codegen resolves the schema from `../../mootmaker-api/api/mootmaker.graphql`
locally and from `node_modules/@mootmaker/schema/` in CI — one differing config value.

**Reasoning:** a CI runner checks out one repository, so the sibling path does not exist there and
the published artifact is the only mechanism. Locally the reverse is true: the sibling layout is
already mandated (`mootmaker/CLAUDE.md`, and `mootmaker-webapp/deploy.sh` resolves
`../mootmaker-api` today), so a path needs no install step, no publish round trip, and no state
outside the repository. `npm link` was considered and rejected for this: it is global machine state
invisible to the repository, and any later `npm install` silently reverts it, so a developer can
stop building against their local schema without noticing.

The general principle: **published versions are for reproducible CI builds and pinning; the sibling
path is for developing.** That is the same split Maven SNAPSHOTs provide, implemented with a path
because the artifact is a single static file with no dependencies to resolve.

### 8. One pipeline, and a deploy-time gate on the consumer

**Decision (2026-09-01):** a single merge-to-`main` pipeline in `mootmaker-api` publishes the schema
*only when `mootmaker.graphql` changed*, then deploys the API — so what production serves and what
was published cannot drift.

```
merge to main
  |- schema changed?  -> check version unused -> npm publish -> mvn deploy
  |- always           -> deploy the API
```

**Consumer uptake** is by automated bump pull request (Dependabot or Renovate) against
`mootmaker-webapp`: a publish opens a PR, CI runs codegen and the type check, and a green PR is
evidence the change is additive and safe to take. A red one is the signal that the schema change
needs webapp work. This is what makes a declared version workable end to end — without it the
webapp's lockfile pins the old version indefinitely and nothing signals that the contract moved.

**The webapp's pipeline verifies before deploying** that the target environment's API actually
serves the schema it was built against (introspection, refuse on mismatch). Two independent
pipelines have no ordering guarantee, and building against version 1.5 proves only that the webapp
*compiles* — not that production serves 1.5. This is not hypothetical: during
`date-time-format-settings`, `mootmaker-webapp#10` was merged before `mootmaker-api#8`, and the
webapp's `myPerson` query selects fields that did not yet exist in the deployed schema. Because
`AuthProvider` runs that query on load, the result would have been a broken sign-in rather than a
degraded page. The gate turns that into a failed deploy.

### 9. Webapp adopts codegen first; the Java consumers follow later

**Decision (2026-09-02):** this design's first implementation converts **`mootmaker-webapp` only**.
Both artifacts are published from the start (Decision 6), but the Java consumers keep their
hand-written operation strings until a later piece of work adopts codegen for them.

**Reasoning:** the two sides are not equal work, and pretending otherwise is how this stalls.
TypeScript codegen from a GraphQL schema is well-trodden (`graphql-code-generator`) and mostly
*replaces* a file that is already hand-maintained — `types.ts` stops being written by hand and
starts being generated, with no change to how the webapp talks to the API. The Java side is a
different shape of change: `mootmaker-demo-data` builds operations as string literals passed to its
own `GraphQlClient`, so adopting generated operations changes **how it talks to the API**, not just
where its types come from — and Java GraphQL client codegen has fewer well-worn options.

Doing the webapp first also proves the published artifact actually works — that it resolves,
versions, and regenerates — before a larger consumer commits to it. If something about the
publishing mechanism is wrong, it is much cheaper to find out against the consumer that was already
going to be easiest.

**The Maven artifact is still published from day one**, even though no Java consumer reads it yet.
It costs almost nothing once the npm publish exists, and it means `mootmaker-android` and
`mootmaker-demo-data` inherit a complete version history rather than starting mid-stream — which is
the whole reason a version history is worth having.

---

## Open questions

### Blocking

**None.** Every question that gated `Ready` was answered on 2026-09-02 and folded into the decisions
above. What remains below is recorded for the reader, not outstanding.

### Non-blocking

- ~~**NB-1**~~ — **resolved 2026-09-01, see Decision 6.** Raw file published; each consumer runs
  its own codegen, in its own repository. The second data point it was waiting for arrived:
  `date-time-format-settings` required hand-editing the schema, the Java model and `types.ts`
  together.
- ~~**NB-2**~~ — **resolved 2026-09-02, and it was not the five-minute check this expected.**
  Storage and bandwidth are a non-issue: GitHub Packages is free for public packages, and the
  published quotas (500 MB / 1 GB on the Free plan) apply only to private ones. But the check found
  a different limitation with real consequences: **GitHub Packages requires an access token to
  install even a public package.** Only its Container registry allows anonymous pulls; npm and Maven
  both demand authentication regardless of visibility. A stranger cloning `mootmaker-webapp` would
  get a 401 from `npm install`. That moved the npm artifact to npmjs.com — see Decision 1.
- ~~**NB-3**~~ — **resolved 2026-09-01, see Decision 5.** Semver, declared in the pull request.
  A commit SHA was rejected for a reason not visible when this was written: SHA versions have no
  ordering, so **no range expression is possible** and every consumer must pin exactly and bump by
  hand on every schema change — replacing "hand-edit `types.ts`" with "hand-edit a version string".
  Semver plus a caret range plus automated bump PRs is what removes the manual step, not the
  human-readability of the number.
- **NB-4 — Revisit the schema-registry option (Hive/Apollo Studio) if the consumer count grows.**
  Written assuming two consumers; the real count is **five** (webapp, `mootmaker-demo-data`'s `impl/`
  and `verify/`, `mootmaker-api/verify` in-repo, and Android to come). **Confirmed 2026-09-02 that
  this does not change the verdict yet, and neither does the earlier `graphql-inspector` trigger:
  both stay as written, revisited when Android lands.**

  The reasoning that survives the higher count: a registry's value is breaking-change detection
  across consumers with *independent release cadences*, and four of the five have none — the two
  `verify/` suites and demo-data's `impl/` all release with the code they test or call. Android is
  the first genuinely independent consumer, which is why it remains the trigger for both this and
  Decision 5's `graphql-inspector`. Until then the schema is 145 lines, the pull request shows the
  schema diff and the version bump side by side, and the person changing the schema is the person
  reviewing the consumers.

- ~~**NB-5**~~ — **resolved 2026-09-01: codegen, for every consumer.** Validation-only was the
  cheaper option and was rejected deliberately. Both catch a stale operation, but they report it
  differently: validation fails a build step with a message about a schema mismatch, whereas codegen
  makes it a **compiler error at the exact line that is wrong** — which is easier for a human to
  spot and act on, and lands in the editor rather than in CI output. The mechanism each consumer
  uses stays its own choice; the outcome (generated, compile-checked operations rather than string
  literals) is common to all of them.

  **Worth knowing before implementation:** the two sides are not equal work. TypeScript codegen from
  a GraphQL schema is a well-trodden path (`graphql-code-generator`) and mostly replaces a file that
  is already hand-maintained. The Java side is a larger change: `mootmaker-demo-data` currently
  builds operations as string literals passed to its own `GraphQlClient`, so adopting generated
  operations means changing how it talks to the API, not just where its types come from — and Java
  GraphQL client codegen has fewer well-worn options than the TypeScript ecosystem. Worth sequencing
  the webapp first, both because it is cheaper and because it proves the published artifact works
  before a bigger consumer commits to it.

---

## Impacts on components

| Repository | Impact |
|---|---|
| `mootmaker-api` | Gains the publish step in its CI/CD pipeline (once that exists); `api/mootmaker.graphql` becomes a published artifact, not just a checked-in file |
| `mootmaker-webapp` | `webapp/src/graphql/types.ts`'s hand-maintenance is replaced by consuming the published schema — exact mechanism (raw schema + local codegen, vs. a published types package) depends on NB-1 |
| `mootmaker-android` | Gains a consumption path for the same schema from day one, rather than starting a third hand-maintained mirror |
| `mootmaker` (hub) | `docs/development/architecture.md`'s "hand-maintained mirror" note is corrected once this ships; `designs/ci-cd-pipeline.md`'s reserved publish step gets a real implementation to point at |

---

## Changes to the domain data model and data storage models

**N/A.** This is a distribution mechanism for an existing schema, not a change to it or to any
persisted data.

---

## Technical considerations

- **GitHub Packages needs authentication even to read a public package — confirmed, and it is the
  reason the npm artifact is on npmjs.com** (Decision 1). This bullet originally flagged it as worth
  checking; the check found it is real for both npm and Maven, and exempt only for the Container
  registry. Practical consequences of the split that remains: `npm install` needs nothing anywhere,
  including a stranger's clone; a Maven consumer needs a `GITHUB_TOKEN` (which GitHub Actions
  provides to its own repository's workflows automatically) or a PAT with `read:packages` in
  `~/.m2/settings.xml` locally. Because the Maven consumers are all this project's own repositories,
  nobody outside the project ever needs a credential.
- **A cross-repository Maven consumer needs the package granted access to it.** A workflow's
  automatic `GITHUB_TOKEN` is scoped to its own repository, so `mootmaker-demo-data` reading a
  package published from `mootmaker-api` needs that repository added under the package's own access
  settings. Cheap, but invisible until it 404s.
- **The schema is small today (145 lines).** Whatever mechanism is chosen should stay simple in
  proportion — this is explicitly why Decision 2 deferred codegen rather than building a heavier
  pipeline for a contract this size.
- **No longer depends on `designs/ci-cd-pipeline.md`** (Decision 3, revised 2026-09-02). The
  standalone workflow this bullet described as an interim step is now the plan outright — publishing
  a static file when it changes needs no deployment machinery, and waiting would gate this design
  behind one that is itself blocked on unanswered questions.
- **`npm publish` needs an `NPM_TOKEN`; the Maven publish does not.** The npm half needs an
  automation token from npmjs.com stored as a repository secret in `mootmaker-api`. The Maven half
  uses the workflow's own `GITHUB_TOKEN`. That asymmetry is worth stating because it is the one
  piece of manual setup this design requires.

---

## Testing impacts

- **A consumer reading a stale or wrong schema version should fail loudly, not silently** — whatever
  mechanism is chosen, verify that a version mismatch between `mootmaker-api`'s deployed schema and
  what `mootmaker-webapp`/`mootmaker-android` consume produces a clear build-time or type-check
  error, not a runtime surprise.
- **No change to existing test layers** — this replaces a manual-sync step, not test coverage.

---

## Documentation impacts

- `docs/development/architecture.md`'s "Contract between API and frontends" section — rewrite once
  a mechanism ships, since it currently describes the hand-maintained-mirror problem this design
  solves.
- `mootmaker-api`'s own README — document the publish step once it exists.
- `mootmaker-webapp`'s README — document how `types.ts` (or its replacement) is now obtained.

---

## Rollout & migration

No data migration and no user-visible change: this alters how the contract is distributed, not what
the API serves.

1. **Publish first, consume nothing.** Land the publish workflow and cut `1.0.0` from the schema as
   it stands. Nothing depends on it yet, so a mistake here costs a version number.
2. **Convert the webapp** (Decision 9). `types.ts` stops being hand-written and becomes generated
   output; codegen resolves the sibling checkout locally and the published package in CI
   (Decision 7). The migration is complete when the hand-maintained file is deleted rather than
   merely unused — a stale mirror left in the tree is worse than one being maintained, because
   nothing signals it is dead.
3. **Prove the loop** by making a real schema change and watching the bump PR open, CI regenerate,
   and the type check pass. Until that has happened once end to end, the automated-uptake half of
   Decision 8 is a plan rather than a mechanism.
4. **Java consumers later**, as their own piece of work — the artifact is already published and
   versioned by then.

Reversible throughout: until step 2 deletes `types.ts`, nothing depends on the artifact and reverting
is deleting a workflow. After step 2, reverting means restoring a hand-written file from git
history.

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **This sits at `Drafting` indefinitely and the hand-maintained mirrors keep drifting in the meantime.** | Low–Medium | The underlying pain (schema/mirror drift) is exactly what the existing testing strategy already partially catches via integration tests against the real schema shape; this design reduces but isn't the only defense against drift in the meantime. |
| ~~**GitHub Packages authentication friction turns out to be worse than expected**~~ | — | **Materialised, and was worse than expected**: a token is required to install even a public package. Caught by NB-2's check before `Ready`, which is what the risk existed to do. Mitigated by moving the npm artifact to npmjs.com (Decision 1); the residual risk is that a Maven consumer 404s until the package is granted access to its repository. |

---

## Implementation checklist

Ordered; each step depends on the one before it.

**Prerequisites — Geoff, before anything else can run**

1. `[Geoff]` ~~Create a free npm organisation~~ **Done 2026-09-03** — `mootmaker` was created as a
   npm *user* rather than an organisation, which works identically for this: every npm user owns
   the scope matching their username, so `@mootmaker/schema` is publishable as declared. The only
   difference is team management, which a solo project does not need.
2. `[Geoff]` ~~Generate an npm automation token and add it as `NPM_TOKEN`~~ **Superseded
   2026-09-03 — no token at all.** npm revoked classic tokens on 2025-12-09, and the granular
   tokens that replaced them are capped at 90 days for write access and stop working for publishing
   in January 2027. Instead: **OIDC trusted publishing**, where the workflow authenticates as
   itself. Nothing to store, nothing to rotate, and the package gets a provenance attestation.

   Because npm requires a package to exist before a trusted publisher can be attached to it (unlike
   PyPI), this splits into:

   - 2a. `[Geoff]` Publish `1.0.0` once by hand: `npm login` as `mootmaker`, then
     `npm publish` from `mootmaker-api/api/`.
   - 2b. `[Geoff]` On npmjs.com → `@mootmaker/schema` → Settings, add a trusted publisher for
     `geoffweatherall/mootmaker-api`, workflow `publish-schema.yml`.

**Publishing**

3. `[Claude]` Add `api/package.json` beside `mootmaker.graphql`: name `@mootmaker/schema`, version
   `1.0.0`, `files` limited to the schema itself, `publishConfig.access: "public"` (scoped packages
   default to restricted, and a restricted publish would silently undo Decision 1's whole point).
4. `[Claude]` Add the standalone publish workflow to `mootmaker-api`: on merge to `main`, if
   `api/mootmaker.graphql` changed — check the declared version is unused, fail with a readable
   message if it is not (Decision 5), then `npm publish` to npmjs.com and `mvn deploy` to GitHub
   Packages with a `pom.xml` generated from the same version string.
5. `[Claude]` Verify both halves: `npm install @mootmaker/schema` from a clean directory **with no
   credentials configured** (the anonymous-install property Decision 1 exists for), and a Maven
   resolve with a token. Then prove the workflow's own OIDC publish works by shipping `1.0.1`
   through it, since the hand-published `1.0.0` proves nothing about the automated path.
6. `[Geoff]` Grant `mootmaker-demo-data` and, later, `mootmaker-android` read access to the Maven
   package under its own package settings — a workflow's `GITHUB_TOKEN` is scoped to its own
   repository.

**Webapp adoption (Decision 9)**

7. `[Claude]` Add `graphql-code-generator` to `mootmaker-webapp`, configured to read the sibling
   checkout locally and `node_modules/@mootmaker/schema/` in CI (Decision 7).
8. `[Claude]` Generate `types.ts`, confirm the output type-checks against existing code, and
   **delete the hand-maintained file** — the migration is not done while a stale mirror survives in
   the tree.
9. `[Claude]` Add the deploy-time introspection gate to the webapp's deploy (Decision 8): refuse to
   deploy if the target environment's API does not serve the schema the bundle was built against.
10. `[Geoff]` Enable Dependabot (or Renovate) on `mootmaker-webapp` for the npm package, so a
    publish opens a bump PR.
11. `[Claude]` Prove the loop end to end with one real schema change — bump PR opens, CI
    regenerates, type check passes. Until this has happened once, automated uptake is a plan rather
    than a mechanism.

**Not in this piece of work**

- Java consumers adopting codegen (`mootmaker-demo-data`'s `impl/` and `verify/`,
  `mootmaker-api/verify`) — deferred by Decision 9, tracked as its own future work.
- `graphql-inspector` breaking-change detection and any schema registry — both deliberately
  triggered by Android landing, not by this design (Decision 5, NB-4).

---

## Definition of done

Scoped to what Decision 9 actually converts — the Java consumers are explicitly not part of this
piece of work, so "every consumer" is not the bar.

- `@mootmaker/schema` publishes on merge when the schema changes, and **installs anonymously** from
  a clean directory with no credentials configured. That last property is the whole reason Decision 1
  moved the npm artifact off GitHub Packages, so it is the one worth asserting rather than assuming.
- The Maven artifact publishes at the same version, and resolves from `mootmaker-demo-data` with its
  workflow token.
- Forgetting to bump the version **fails the build with a readable message**, not a raw 409
  (Decision 5).
- `mootmaker-webapp` generates its types from the schema, the hand-maintained `types.ts` is
  **deleted**, and the webapp's existing unit, integration and acceptance suites are still green on
  a real deployed environment — the project's usual bar for work of this size.
- The deploy-time introspection gate refuses a webapp deploy against an environment whose API serves
  an older schema, demonstrated deliberately rather than assumed.
- One real schema change has been through the full loop: publish, bump PR, regenerate, type check.
- Everything under "Documentation impacts" is done — including `docs/development/architecture.md`'s
  "hand-maintained mirror" note, which becomes false the moment `types.ts` is deleted.
