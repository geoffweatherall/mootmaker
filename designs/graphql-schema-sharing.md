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

## Open questions

### Blocking

None — this document is deliberately left at `Drafting` with no expectation of being picked up
immediately, so there's nothing that needs resolving before it can sit in that state. The questions
below need answers before it can move to `Ready`.

### Non-blocking

- **NB-1 — Publish the raw `.graphql` file, or a codegen'd artifact per language, or both?**
  Decision 2 picked "raw file" for a first version; whether to add generated TypeScript/Java types
  later (and which tool — `graphql-code-generator` for TS, an existing Java GraphQL codegen plugin)
  is open. Worth deciding once there's a second data point on how painful the hand-maintained
  mirrors actually are to keep in sync with a raw-schema-only artifact in place.
- **NB-2 — Does GitHub Packages' free tier have a real limitation worth knowing about up front**
  (storage caps, retention, bandwidth) for a project this size? Likely irrelevant at mootmaker's
  scale, but worth a five-minute check against GitHub's current published limits before
  implementation starts rather than assumed.
- **NB-3 — Semantic versioning, or just the commit SHA?** A SHA-based version is simpler and always
  traceable to an exact schema state; semver communicates breaking-vs-additive changes to consumers
  at a glance but needs someone (or something) to actually classify each change correctly. Worth
  deciding once there are real consumers to feel the difference.
- **NB-4 — Revisit the schema-registry option (Hive/Apollo Studio) if the consumer count grows.**
  Two consumers (webapp, soon Android) don't obviously justify it; three or more with independent
  release cadences might. Not a decision to make now, just a trigger condition worth remembering.

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
