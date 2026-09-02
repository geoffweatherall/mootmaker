# GraphQL schema sharing

## Summary

`mootmaker-api/api/mootmaker.graphql` is the one source of truth for the API contract.
`mootmaker-webapp/webapp/src/graphql/types.ts` is a hand-maintained TypeScript mirror of it, kept in
sync by a human (or an agent) remembering to update both when the schema changes. Nothing enforces
that they agree, and `mootmaker-android` will need the same schema a third time. This design
proposes publishing the schema as a versioned artifact via GitHub Packages, so every consumer reads
one file instead of re-typing it.

**Status:** Drafting — 2026-08-29

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
  Studio). Worth a mention as a fancier alternative (see Trade-offs), but out of scope for a
  two-consumer schema this size (145 lines today).

---

## Trade-offs and decisions

### 1. Distribution mechanism: GitHub Packages

**Decision:** publish the schema via GitHub Packages, which hosts both **npm** and **Maven**
artifacts from the same GitHub account, free for public repositories.

**Options weighed:**

| Option | Verdict |
|---|---|
| **GitHub Packages** | **Chosen.** One store answers the "Java/Maven and JS/npm need to share one file" constraint directly — no second system to run or pay for. Free on public repos. Authentication for consumers is the same GitHub token they likely already have for other purposes (`gh`, git itself). |
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

**Decision:** the schema artifact is published as part of `mootmaker-api`'s CI/CD pipeline
(`designs/ci-cd-pipeline.md`, which already reserves this exact step), on every merge to `main`,
tagged with a version derived from the merge (e.g. the short commit SHA, or a semantic version if
`mootmaker-api` adopts one).

**Reasoning:** ties schema publication to the same event that deploys the API serving that schema,
so "what schema does production actually implement" and "what artifact is published" never drift
apart. Consistent with the CI/CD design's existing shape rather than inventing a separate trigger.

---

## Choices you had me make

1. **Chose GitHub Packages over S3 as the primary recommendation**, rather than presenting both as
   equally weighted. The "one store instead of two" argument for the Java/npm split is strong enough
   that a default is more useful than an open menu — flagged here so it's easy to override if the
   trade-off looks different once implementation actually starts.
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

**Decision (2026-09-01):** `api/package.json` — sitting beside `mootmaker.graphql` — holds the
version, and a human (or agent) bumps it in the same pull request that changes the schema. That
file is the single source of truth; the Maven `pom.xml` is generated in CI from the same string, so
one version means one thing in both registries.

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
automatically. Accepted knowingly at this scale — a 145-line schema with two consumers, where the
pull request shows the schema diff and the version bump side by side. **Revisit when the schema
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
| `mootmaker-demo-data` (generator + topup) | Java | **8 hand-written GraphQL operation strings** | Maven |
| `mootmaker-api/verify` | Java | 16+ operation strings across 8 acceptance-test classes | the local file — same repo |
| `mootmaker-android` | Kotlin | does not exist yet | Maven |

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

---

## Open questions

### Blocking

None — this document is deliberately left at `Drafting` with no expectation of being picked up
immediately, so there's nothing that needs resolving before it can sit in that state. The questions
below need answers before it can move to `Ready`.

### Non-blocking

- ~~**NB-1**~~ — **resolved 2026-09-01, see Decision 6.** Raw file published; each consumer runs
  its own codegen, in its own repository. The second data point it was waiting for arrived:
  `date-time-format-settings` required hand-editing the schema, the Java model and `types.ts`
  together.
- **NB-2 — Does GitHub Packages' free tier have a real limitation worth knowing about up front**
  (storage caps, retention, bandwidth) for a project this size? Likely irrelevant at mootmaker's
  scale, but worth a five-minute check against GitHub's current published limits before
  implementation starts rather than assumed.
- ~~**NB-3**~~ — **resolved 2026-09-01, see Decision 5.** Semver, declared in the pull request.
  A commit SHA was rejected for a reason not visible when this was written: SHA versions have no
  ordering, so **no range expression is possible** and every consumer must pin exactly and bump by
  hand on every schema change — replacing "hand-edit `types.ts`" with "hand-edit a version string".
  Semver plus a caret range plus automated bump PRs is what removes the manual step, not the
  human-readability of the number.
- **NB-4 — Revisit the schema-registry option (Hive/Apollo Studio) if the consumer count grows.**
  Written assuming two consumers; the real count is already **three** (webapp, `mootmaker-demo-data`,
  and `mootmaker-api/verify` in-repo), with Android a fourth. That does not change the verdict yet —
  the registry's value is breaking-change detection across consumers with independent release
  cadences, and demo-data plus verify both currently release with the API. It does mean the trigger
  is closer than this note assumed. See also Decision 5's revisit condition, which arrives first and
  is cheaper (`graphql-inspector` in CI).

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

- **GitHub Packages needs authentication even to read a public package** in most client
  configurations (`npm`/Maven both typically want a token for the registry even when the underlying
  repo is public) — worth confirming exactly what a consuming CI job and a local developer each need
  before implementation, so this doesn't become a surprise blocker partway through.
- **The schema is small today (145 lines).** Whatever mechanism is chosen should stay simple in
  proportion — this is explicitly why Decision 2 deferred codegen rather than building a heavier
  pipeline for a contract this size.
- **This depends on `designs/ci-cd-pipeline.md` existing in some real form** for the "publish on
  merge" trigger to have somewhere to live; until that pipeline is built, publishing would need its
  own standalone trigger (a separate workflow, still free on GitHub Actions) as an interim step.

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

Not applicable while `Drafting` — to be filled in once this design is picked up, informed by
whichever answer NB-1 lands on (a bigger migration if generated types replace `types.ts` outright,
a smaller one if the raw schema is simply consumed alongside the existing hand-maintained file as a
verification check first).

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **This sits at `Drafting` indefinitely and the hand-maintained mirrors keep drifting in the meantime.** | Low–Medium | The underlying pain (schema/mirror drift) is exactly what the existing testing strategy already partially catches via integration tests against the real schema shape; this design reduces but isn't the only defense against drift in the meantime. |
| **GitHub Packages authentication friction turns out to be worse than expected** (Technical considerations). | Low | Caught early by NB-2/the auth check, before committing to the mechanism in `Ready`. |

---

## Implementation checklist

Empty while `Drafting`, per the design-doc template — this section gets filled in once the design
is promoted to `Ready` and someone is actually building it.

---

## Definition of done

Not applicable while `Drafting`. When this is picked up: every consumer (webapp, and Android once it
exists) reads the schema from the published artifact rather than a hand-maintained copy, a schema
version mismatch fails loudly at build/type-check time, and the documentation named above reflects
the new mechanism.
