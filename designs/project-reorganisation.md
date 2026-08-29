# Project reorganisation — structure, process, and ways of working

## Summary

Mootmaker has grown organically from a code-generation experiment into a multi-repo system with
real architecture, a real test pyramid, and (as of this week) design docs and issue tracking. The
process around it has not kept pace: there is no agreed home for cross-cutting documentation, no
branch/PR discipline, no CI, no written statement of the project's principles, and nothing that
tells a *non-Claude* AI agent how work is done here. This design establishes that layer — a hub
repo with a deliberate documentation structure, a written set of principles, a branch/PR/review
flow, GitHub Issues plus a cross-repo Project board, per-repo `AGENTS.md` files, role ("hat")
definitions with templates and agent configs, a machine-readable workstation manifest, and a
sharper repo split — while explicitly *not* building CI/CD or artifact sharing yet.

**Status:** Ready — 2026-08-29 (approved by Geoff; build from this as written)

---

## Scope / non-goals

### In scope

- Restructuring the `mootmaker` hub repo: README, `docs/` tree, doc relocations.
- Writing the project's principles and constraints down for the first time.
- Branching, PR, and review process across all repos.
- Migrating the README To Do list into GitHub Issues, and creating a cross-repo Project board.
- Per-repo `AGENTS.md` (tool-agnostic agent instructions), with `CLAUDE.md` reduced to a pointer.
- Role/"hat" definitions, document templates, and Claude Code agent definitions per hat.
- Workstation prerequisite manifest + check script.
- Splitting `mootmaker-tools` by blast radius: `mootmaker-demo-data` and `mootmaker-admin-tools`.
- Retiring the long-lived `test` environment in favour of production + ephemeral only.
- Writing down (not building) the intended CI/CD approach and the cross-repo artifact-sharing
  approach, each as its own `Drafting` design doc.

### Non-goals

- **Building any CI/CD pipeline.** No GitHub Actions workflows are created by this work. The
  approach is designed and recorded; implementation is a separate design.
  (*Decision 2 below.*)
- **Building GraphQL schema sharing.** Same treatment — the problem and candidate solutions are
  written into a design stub; no artifact publishing is implemented.
  (*Decision 11 below.*)
- **Any application feature work.** No changes to API behaviour, webapp behaviour, or the data
  model.
- **Rewriting the two older paired design docs** (`delete-my-account.md` / `-todo.md`). They get a
  new home and a status, not a rewrite — same treatment `google-sign-in.md` already received.
- **A monorepo.** Considered and rejected — see Decision 1.
- **Deleting any repo.** No repo is removed; the split renames one and adds one.
- **Rewriting git history** in any repo, beyond the history-preserving extraction needed for the
  tools split.

---

## Trade-offs and decisions

These were decided together on 2026-08-29 and should not be re-litigated without a reason to
re-open them.

### 1. Repo topology: split further (10 repos), not consolidate, and not a monorepo

**Decision:** keep the multi-repo shape and sharpen it, ending at 10 repos.

**Options weighed:**

| Option | Verdict |
|---|---|
| Monorepo (1 repo) | **Rejected.** It genuinely dissolves several stated problems — cross-repo branching, schema sharing, doc homing, one CI pipeline, whole-system context for an AI agent in one checkout. But it is a much larger change than the reorganisation described, it discards the clean independent-deployable boundaries that already work, and it removes the very coordination problem that is interesting to learn about. |
| Consolidate to 7 (merge the three foundation repos) | **Rejected.** Lower coordination cost, but merges three genuinely distinct lifecycles (Terraform state bucket, AWS account guardrails, DNS/mail identity) for tidiness alone. |
| Keep 8 unchanged | **Rejected.** Leaves `mootmaker-tools` mixing production demo-data tooling with tooling that can wipe production. |
| **Split further (10)** | **Chosen.** Sharpens the one boundary that is actually wrong (blast radius inside `mootmaker-tools`) and keeps every other boundary as-is. |

**Consequence, accepted knowingly:** more repos means cross-repo coordination matters *more*, not
less. This is why every design doc must name the repos it touches, why the Project board is a
requirement rather than a nicety, and why `AGENTS.md` distribution (Decision 6) is load-bearing.

**Correction to the original premise:** the sample-data tools were suspected of not being deployed
to production. They already are — `mootmaker-tools/deploy-all.sh <environment>` deploys all four
tools per-environment as individual Lambdas, and `sample-data-topup` already runs weekly in
production on an EventBridge schedule. So `-api` / `-webapp` / tools-deployed-everywhere is the
existing shape, not a change. The real defect is different: **`database-reset` and
`database-repair` can destroy production data and sit in the same repo, with the same deploy
script, as tooling that legitimately ships as part of the production demo.** That is the split.

### 2. CI/CD: designed now, built later

**Decision:** this reorganisation writes down the CI/CD approach and creates
`designs/ci-cd-pipeline.md` at `Drafting`. It creates **no** workflow files.

**Reasoning:** the reorganisation is already large, and a deploy pipeline needs AWS OIDC roles, a
rollback story, and a decision about ephemeral-env-per-PR cost — each of which deserves its own
review rather than riding along inside a structural change.

**Useful finding for that future design:** every mootmaker repo is public, and **GitHub Actions is
free with unlimited minutes on public repositories.** CI here has no marginal cost, which removes
the usual reason a hobby project skips it.

### 3. Environments: production + ephemeral only

**Decision:** retire the long-lived `test` environment. Two kinds of environment exist:

- **`production`** — the public demo. Also the only long-lived environment.
- **ephemeral** — created per piece of work, torn down when it merges.

**Reasoning:** `test` costs money continuously to be a staging gate that a solo developer with a
green acceptance suite does not need. It has also already caused real problems: it accumulates
state, and this week a stale `test` environment produced acceptance failures that were environment
contamination rather than defects.

**What is actually deployed today** (verified 2026-08-29 against `remote-state-431071856068` and
live AWS):

| Environment | Contents |
|---|---|
| `production` | API, webapp, all four tools — the public demo |
| `test` | API, webapp, all four tools — **retired 2026-08-29**, 73 resources destroyed |
| `claude-260828-006t` | API + webapp — leaked; **torn down 2026-08-29** |
| `claude-260828-2flz` | API + webapp — leaked; **torn down 2026-08-29** |
| `claude-260828-92oq` | API + webapp + 2 tools — leaked; **torn down 2026-08-29** |
| `claude-260828-u3ou` | API + webapp — leaked; **torn down 2026-08-29** |
| `domain`, `bootstrap` | Shared/persistent, not environments — unaffected |
| `mootmaker-e2e-email` | SES email pipeline — see the naming note in Technical considerations |

**A process gap this exposed, and the decision it forced.** Four ephemeral environments from a
single session on 2026-08-28 were found still running — 10 Lambdas and 16 DynamoDB tables, plus the
Cognito pools, S3 buckets, CloudFront distributions and AppSync APIs that go with each (all torn
down on 2026-08-29). The ephemeral workflow's teardown step is convention only, and convention lost
four times in one day. That directly contradicts the scale-to-zero principle this project claims.

So Decision 3 carries a second obligation beyond retiring `test`: **ephemeral environments need a
teardown guarantee that does not depend on a session remembering.** `mootmaker-test-infra` already
has `cleanup-stale-envs.sh`, but nothing runs it. `docs/process/environments.md` must define a
maximum ephemeral lifetime and a scheduled sweep that enforces it — the natural home for which is
the CI/CD design (a scheduled GitHub Actions job), making this a concrete requirement handed to
that design rather than a vague aspiration.

**A gap in `teardown-ephemeral-env.sh`, found while doing the teardown.** The script undeploys only
`mootmaker-webapp` and `mootmaker-api`, and deliberately removes only those two state objects —
its comments explain, correctly, that deleting a state object it did not itself destroy would
orphan real infrastructure. But the consequence is that **an environment with tools deployed is not
fully torn down by the script named "tear down this environment"**. `claude-260828-92oq` had
`database-reset` and `sample-data-generator` deployed; both had to be undeployed by hand first, and
their emptied state objects removed separately, or the environment would have kept showing up in
`cleanup-stale-envs.sh`'s discovery forever with nothing left to clean.

The safety reasoning is sound and should not be discarded. The fix is to make the script
*discover* what is deployed under the environment's state prefix and either handle each project or
refuse to claim success — rather than silently handling two of them. Raised as an issue; relevant
to the CI/CD sweep too, since an automated sweep with this gap would leak exactly the same way.

**Ephemeral naming convention** (extends what already exists):

| Prefix | Purpose | Lifetime |
|---|---|---|
| `claude-<ts>-<rand>` | An AI session's working environment | The session |
| `e2e-<ts>-<rand>` | An automated e2e/acceptance run | The run |
| `<name>-<slug>` | A human's manual testing for a specific piece of work (e.g. `geoff-datefmt`) | Until the work merges |

**Consequence:** manual testing of a feature happens in an ephemeral environment created for that
feature, not in a shared one. The stale-memory note reserving `test` for Geoff's manual testing
becomes obsolete and must be updated (checklist Phase 5).

### 4. Issues: per-repo, unified by one cross-repo Project board

**Decision:** an issue is filed in the repo whose code it concerns. One GitHub Project spanning all
mootmaker repos provides the single view.

**Reasoning:** filing in-repo preserves native `Closes #N` auto-linking from commits and PRs, which
is the mechanism that makes "issue → fix → commit → closed" traceable without manual bookkeeping.
Centralising every issue in the hub would gain one list and lose that. The Project board recovers
the single view without giving up the linking.

**Requires:** `gh auth refresh -s project` (one-off, interactive, browser-based). The current token
has `gist, read:org, repo, workflow` — enough for issues, labels, PRs, repo renames, and repo
creation, but **not** for Projects. Confirmed by `gh project list` failing with
`missing required scopes [read:project]`.

### 5. Hub landing page: showcase-first, depth in `docs/`

**Decision:** `mootmaker/README.md` becomes a ~100-line landing page that leads with what mootmaker
is and the headline learnings, then links out. The full essay, developer onboarding, environment
mechanics, and reference material all move into `docs/`.

**Reasoning:** the README currently does three incompatible jobs for three different audiences —
portfolio essay (~160 lines), developer entry point, and todo list. A prospective employer and a
developer starting work want different first screens. Leading with the showcase serves the
portfolio goal; everything else is one click away.

### 6. Agent instructions: short `AGENTS.md` per repo, pointing at the hub

**Decision:** every repo gets an `AGENTS.md` containing repo-specific guidance plus a pointer to the
hub's `docs/process/`. `CLAUDE.md` becomes a symlink to `AGENTS.md` in each repo.

**Reasoning:** `AGENTS.md` is the emerging cross-tool convention — Antigravity, Cursor, Codex, and
Copilot all read it, while Claude Code reads `CLAUDE.md`. A symlink means both names resolve to one
file, so Claude Code loses nothing (it loads the full content directly, no indirection) and every
other tool gets the same instructions. One canonical copy per repo, no sync machinery.

**Why not full duplication of the hub rules into each repo:** it needs a generator plus a CI
staleness check to stay honest, and CI does not exist yet (Decision 2). Revisit once CI does.

**Accepted risk:** an agent working in a lone checkout without the hub may not follow the pointer.
Mitigated by each `AGENTS.md` stating the expectation explicitly and by the fact that all repos are
checked out together in this workspace. Flagged as a thing to watch when Antigravity is first used
(*Open question NB-1*).

### 7. Roles: full per-hat structure

**Decision:** each hat gets a role doc, document templates, and a Claude Code agent definition.

**The hats:**

| Hat | Owns | Primary artifacts |
|---|---|---|
| **Developer** | Designs, code, tests, PRs, technical issues | `designs/`, all code repos, `docs/reference/testing-strategy.md` |
| **Product owner** | What the system should do and in what order | `docs/reference/business-functionality.md`, `docs/reference/use-cases.md`, issue triage and priority |
| **Marketer** | How the system is positioned and presented | `docs/showcase/features-overview.md`, brochure, `docs/showcase/branding/` |
| **Operator** | Environments, deploys, cost, incidents, guardrails | `docs/process/environments.md`, the bootstrap repos, `mootmaker-admin-tools` |
| **Author** | The learning record and the portfolio narrative | `docs/showcase/learnings.md`, `debugging-techniques.md`, the README's showcase content |

**On the fifth hat:** *Author* was not on the original list. It is proposed because it is a real,
distinct job on this project — the learnings essay and the debugging-techniques document are
deliberate outputs serving the showcase goal, and writing them is not developer work. Reject it if
it feels like over-fitting (*Open question NB-2*).

**On the missing sixth:** security/privacy work (the privacy policy draft, Cognito configuration,
IAM guardrails) is deliberately **folded into Operator** rather than given its own hat, on the
grounds that one person wearing six hats is a filing system rather than a process. Revisit if
security work starts feeling homeless.

### 8. Review model: human review required, AI review encouraged

**Decision:** every PR gets Geoff's review before self-merge. A second-AI review pass is documented
as an available, recommended step with a defined way to run it and record findings — but it is
per-PR judgement, not a gate.

**Reasoning:** making AI review mandatory before there is any evidence about whether it earns its
cost would bake in an untested assumption. Documenting it properly and using it selectively
generates that evidence. Revisit after ~10 PRs (*Open question NB-3*).

**"Review" here does not mean GitHub's Approve button — it cannot.** Claude has no GitHub identity;
it acts through `gh` authenticated as Geoff, so every branch, commit, and PR it creates is authored
by Geoff. GitHub blocks approving your own pull request, so on a solo project the formal Approve
review is permanently unavailable. This was found the practical way, on this design's own PR.

That is fine, and the process must not pretend otherwise:

- **Reading the diff is the review. Merging is the approval.** Branch protection is deliberately not
  enabled (see "GitHub, outside any repo"), so a self-authored PR merges without an approving
  review. No gate is lost.
- **The real human gate lives in the artifact, not in GitHub.** For a design, it is the
  `Drafting → Ready` promotion in the doc's own Status line — explicitly Geoff's alone, recorded
  where any tool can read it. That is strictly better than GitHub's review state for this project,
  because it is tool-agnostic: Antigravity can read a `Status:` line without being taught GitHub's
  review API.
- **Merging and promoting are two separate acts.** Merging a design PR puts the document safely on
  `main`; it does not make the design build-from-able. Only the explicit Status change does. Keeping
  them separate means a design can live on `main` while still being chewed over.

**Attribution stays honest as-is.** Commits already carry `Co-Authored-By: Claude Opus 5`, which
accurately records who wrote what. Making PRs *appear* to come from a Claude identity would
misrepresent accountability — Geoff owns and merges the work — so it is not done for cosmetic
reasons. See NB-7 for the one case where a distinct identity would genuinely earn its keep.

### 9. Human review boundary: design, tests, and the risky categories

**Decision, and the project's stated position on "how much vibe coding is acceptable":**

- **Always reviewed properly by a human:** the design doc before work starts; the test cases (unit
  and acceptance) after; and *any* diff touching authentication/Cognito, persisted data or
  migrations, IAM/Terraform permissions, or anything with a cost implication.
- **Skim-only:** everything else. Read where something looks off; otherwise the tests and a green
  acceptance run against a real deployed environment are the gate.

This is the first time this boundary has been written down. It goes in
`docs/process/principles.md` and is expected to move as evidence accumulates — it is a hypothesis
about where the line sits, not a permanent rule.

### 10. Workstation prerequisites: machine-readable manifest + check script

**Decision:** `tools/workstation/manifest.yaml` (one entry per tool: name, why it is needed, how to
check for it, how to install it on Ubuntu, extra notes) plus `tools/workstation/check.sh` that
reads it and reports present/missing with install commands. A human-readable
`docs/development/workstation.md` explains the system and links to it.

**The standing rule, to be stated in `docs/process/README.md`:** if a session installs a tool that
future work will need, adding it to the manifest is part of that session's work — not a follow-up.

**Reasoning:** prose alone cannot be mechanically checked; a bare install script hides *why* each
tool is needed and cannot run unattended anyway (`sudo` needs an interactive password, as this
week's `gh` install demonstrated). The manifest gives an AI something to inventory against and a
human something to read.

### 11. GraphQL schema sharing: recorded, not built

**Decision:** create `designs/graphql-schema-sharing.md` at `Drafting` capturing the problem and
candidate solutions. Build nothing.

**The problem, stated precisely:** `mootmaker-api/api/mootmaker.graphql` is the source of truth.
`mootmaker-webapp/webapp/src/graphql/types.ts` is a hand-maintained mirror of it. Nothing prevents
them drifting, and `mootmaker-android` will need the same schema again.

**Finding for that design:** GitHub Packages hosts **both** npm and Maven artifacts, from the same
account, free for public repos. That directly answers the "Java/Maven and JS/npm need to share one
file" constraint with one store rather than two, and is the strongest candidate to evaluate first
(alternatives: a versioned S3 object, or GitHub Releases assets).

**Provision made by this reorganisation:** the CI/CD design reserves a "publish the schema artifact
on merge" step, so the pipeline design does not have to be reopened to accommodate it later.

### 12. Packaging: one design, phased execution

**Decision:** this single document is reviewed once and approved as a whole, then executed in the
five phases in the Implementation checklist, pausing between phases for a check-in.

---

## Choices you had me make

Decisions taken unilaterally while drafting, because they were not worth blocking on. Each is cheap
to override.

1. **`CLAUDE.md` becomes a git symlink to `AGENTS.md`** rather than a one-line text pointer. Loses
   nothing for Claude Code and avoids maintaining two files. Ubuntu-only development makes the
   usual Windows symlink objection moot. If any tool chokes on it, the fallback is a one-line
   `CLAUDE.md` saying "See AGENTS.md."
2. **`designs/` stays at the hub root, not under `docs/`.** It is a first-class, frequently-touched
   artifact and already lives there; burying it a level down would make the most-used folder the
   hardest to reach.
3. **`designs/data-model.md` moves to `docs/reference/data-model.md`.** It is explicitly a standing
   reference rather than a design, by its own header and by `designs/README.md`'s description of
   it. `designs/README.md` gets updated to point at the new location.
4. **Proposed the "Author" hat** (Decision 7) — flagged there as reviewable.
5. **Folded security/privacy into the Operator hat** rather than creating a sixth (Decision 7).
6. **Role agent definitions are stored in the repo and installed, not stored where the tool wants
   them.** Canonical tool-agnostic markdown lives in `docs/roles/agents/`; a small
   `tools/install-agents.sh` links them into `~/.claude/agents/`. See Technical considerations for
   why this matters more than it sounds.
7. **Kept `mootmaker-android` as-is** — an empty repo gets only an `AGENTS.md` placeholder. Not
   worth deciding its shape before it exists.
8. **Todo-list migration is a triage pass, not a bulk import.** Several unchecked README items look
   already done (per-Person calendar, per-Room availability, webapp unit tests) and several are
   duplicates of each other (two separate DynamoDB-GSI entries). Each item is checked against
   reality before an issue is raised. Completed `[x]` items are not migrated — git history already
   records them.
9. **No repo is made private and none is archived.** Everything stays public, consistent with the
   showcase goal.

---

## Open questions

### Blocking

**No unanswered design questions** — every decision needed to start Phase 1 is made.

**All four pending actions from Geoff were resolved on 2026-08-29.** Nothing now blocks execution.

1. ~~Approve this design → Status `Ready`~~ — **done**, Status promoted 2026-08-29.
2. ~~Run `gh auth refresh -s project`~~ — **done**. Token scopes are now
   `gist, project, read:org, repo, workflow`, and `gh project list` succeeds. Phase 3's board is
   unblocked.
3. ~~Choose an option in
   [`mootmaker-tools#1`](https://github.com/geoffweatherall/mootmaker-tools/issues/1)~~ —
   **done: option B**, migrate the state keys to the new repo names. Chosen over the suggested
   option C; recorded on the issue.
4. ~~Decide when to tear down `test`~~ — **done: immediately**, before Phase 1, rather than during
   Phase 4. See Decision 3.

A fifth, not on the critical path but needed before any genuinely unattended run: **enable mobile
push in `/config`**. Verified disabled 2026-08-29, which means a blocked session currently stops
with nobody informed. See "When to notify" under Working conventions.

Two further gates (reviewing a written `AGENTS.md` and confirming the issue triage) cannot be
front-loaded because they need their artifacts to exist first — see the Human gates table.

### Non-blocking

- **NB-1 — Does the `AGENTS.md`-pointer approach actually work for Antigravity?** Unknown until
  Antigravity is used here for the first time. If it ignores the pointer and works only from what
  is in the repo it is opened in, revisit Decision 6 and move to generated full copies.
- **NB-2 — Is the "Author" hat real or over-fitting?** Judgement call; easy to remove.
- **NB-3 — Does AI-reviewing-AI earn its cost?** Revisit Decision 8 after roughly ten PRs with
  notes on which reviews found something a human review would have missed.
- **NB-4 — Should ephemeral environments be created automatically per PR?** Attractive, and a
  natural fit with Decision 3, but it has a real cost profile and belongs in the CI/CD design.
- **NB-5 — Does `docs/reference/use-cases.md` need per-frontend tagging?** Its own header flags
  this gap ("isn't yet tagged per-frontend"). Out of scope here; worth an issue.
- **NB-6 — Where should the workspace-level `.claude/settings.local.json` live?** It is currently
  in `mootmaker-workspace/.claude/`, which is inside no repo and therefore unversioned and not
  reproducible on another machine. Noted in Technical considerations; a fix is proposed but the
  right long-term answer may be different.
- **NB-7 — Does the AI-review experiment need a separate GitHub identity?** Tied to NB-3. A second
  agent leaving a PR review would also act as Geoff via `gh`, making it a self-review with the same
  block described in Decision 8 — so the reviewer would be indistinguishable from the author, which
  defeats most of the point of the experiment. A machine account or GitHub App would fix that
  properly and make the review visibly independent. Deliberately deferred: it is an account and a
  token to maintain, and it only pays off once AI review is actually being run. Decide alongside
  NB-3 rather than before it.

---

## Impacts on components

### The hub: `mootmaker`

Target structure:

```
mootmaker/
  README.md                          showcase-first landing, ~100 lines
  AGENTS.md                          hub's own agent entry point
  CLAUDE.md                       -> AGENTS.md (symlink)
  designs/
    README.md                        the design-doc pattern (exists; updated)
    project-reorganisation.md        this document
    date-time-format-settings.md     (exists)
    google-sign-in.md                (exists)
    delete-my-account.md             migrated from the root pair
    ci-cd-pipeline.md                NEW, Drafting
    graphql-schema-sharing.md        NEW, Drafting
  docs/
    process/
      README.md                      canonical workflow rules; AGENTS.md files point here
      principles.md                  NEW - constraints, stack, review boundary
      branching-and-prs.md           NEW
      issues-and-board.md            NEW - labels, board fields, conventions
      environments.md                production + ephemeral model
      ai-collaboration.md            NEW - model choice, AI review, instrumentability
    roles/
      README.md                      the hats index
      developer.md  product-owner.md  marketer.md  operator.md  author.md
      templates/                     one-pager, marketing brief, release note, incident note
      agents/                        canonical agent definitions (tool-agnostic)
    development/
      getting-started.md             NEW - first 30 minutes on a new machine
      architecture.md                NEW - cross-repo system overview
      workstation.md                 NEW - prerequisites, explains the manifest
    reference/
      data-model.md                  from designs/
      testing-strategy.md            from root
      use-cases.md                   from root
      business-functionality.md      from functionality/
      glossary.md                    NEW
    showcase/
      learnings.md                   the essay, from README
      debugging-techniques.md        from root
      features-overview.md           from features/
      privacy-policy-draft.md        from root
      branding/                      from root
      marketing/                     brochure PDF, image.png
      resources/                     from root (screenshots)
  tools/
    workstation/manifest.yaml        NEW
    workstation/check.sh             NEW
    install-agents.sh                NEW
```

Removed from the hub root by these moves: `testing-strategy.md`, `use-cases.md`,
`debugging-techniques.md`, `privacy-policy-draft.md`, `branding/`, `features/`, `functionality/`,
`resources/`, the brochure PDF, `image.png`, `delete-my-account.md`, `delete-my-account-todo.md`,
`google-sign-in.md`, `google-sign-in-todo.md`, `meeting-picker-dropdowns-todo.md`, and the README's
To Do section.

**Redirect obligation:** several of these are linked from other repos by URL
(`testing-strategy.md` and `use-cases.md` especially — `mootmaker-webapp`, `mootmaker-api`, and
`mootmaker-test-infra` all link to them). Every inbound link must be updated in the same phase as
the move. See Risks.

### `mootmaker-tools` → `mootmaker-demo-data`, plus new `mootmaker-admin-tools`

| Tool | Destination | Why |
|---|---|---|
| `sample-data-generator` | `mootmaker-demo-data` | Seeds the production demo; part of the product |
| `sample-data-topup` | `mootmaker-demo-data` | Runs weekly in production; part of the product |
| `database-reset` | `mootmaker-admin-tools` | Deletes all rooms/meetings/people — destructive |
| `database-repair` | `mootmaker-admin-tools` | Writes directly to Cognito/DynamoDB — destructive |

`mootmaker-tools` is **renamed** to `mootmaker-demo-data` (keeping history and issue numbers with
the half that ships to production), and `mootmaker-admin-tools` is created new, receiving the two
admin tools with their history extracted.

**Dependency that survives the split and must be handled:** `sample-data-generator` invokes
`database-reset` Lambda-to-Lambda as the first step of every run, via its own IAM role. After the
split this becomes a **cross-repo deploy-order dependency** — `mootmaker-admin-tools` must be
deployed to an environment before `mootmaker-demo-data` is deployed or run against it. It is
already documented as an ordering constraint within one repo; it now needs documenting in both
repos' READMEs and in `docs/development/getting-started.md`. `mootmaker-api`'s acceptance tests
share the dependency.

`deploy-all.sh` / `undeploy-all.sh` split into a two-tool version in each repo.

### Every code repo

`mootmaker-api`, `mootmaker-webapp`, `mootmaker-android`, `mootmaker-demo-data`,
`mootmaker-admin-tools`, `mootmaker-test-infra`, `mootmaker-domain`,
`mootmaker-bootstrap-terraform`, `mootmaker-bootstrap-aws-accounts`:

- Gain `AGENTS.md`; existing `CLAUDE.md` content folds in and `CLAUDE.md` becomes a symlink.
  (Only `-api`, `-webapp`, and `-tools` currently have a `CLAUDE.md` at all — the other five have
  none, which is itself a gap this closes.)
- Any link to a relocated hub document is updated.
- References to the `test` environment in scripts, READMEs, and testing-strategy docs are reviewed
  against Decision 3.
- Standard label set applied.

### `mootmaker-webapp` specifically

`testing-strategy.md` and `README.md` both link into hub docs that move. `acceptance/run.sh` and
`e2e/run.sh` reference environments and need checking against Decision 3.

### GitHub, outside any repo

- One Project ("Mootmaker") spanning all repos, with fields: Status, Hat, Repo, Size, Design.
- A standard label set replicated across all repos.
- Issues created from the triaged README To Do list.
- Branch protection is **not** enabled (Decision 8 makes PRs a convention, and required status
  checks cannot be configured before CI exists).

---

## Changes to the domain data model and data storage models

**N/A.** This work touches no application code, no GraphQL schema, no Cognito configuration, and no
DynamoDB table, index, or attribute. `docs/reference/data-model.md` moves file location but its
content is unchanged.

---

## Technical considerations

- **Agent definitions cannot live where the tool looks for them.** Claude Code reads subagents from
  `.claude/agents/` in the project directory or `~/.claude/agents/` at user level. The natural
  project directory here is `mootmaker-workspace/`, which is **not inside any git repository** —
  so anything put there is unversioned and lost when moving to another machine. Hence Decision 6 in
  "Choices you had me make": canonical definitions are versioned in
  `mootmaker/docs/roles/agents/`, and `tools/install-agents.sh` symlinks them into
  `~/.claude/agents/`. This keeps them in git, makes them available from any repo checkout, and
  keeps the canonical form plain markdown that another tool can be pointed at.
- **The same problem already exists for `mootmaker-workspace/.claude/settings.local.json`** — it is
  unversioned and would not exist on the PC. Recorded as NB-6.
- **History-preserving extraction for the tools split.** `git filter-repo --path database-reset
  --path database-repair` against a fresh clone produces `mootmaker-admin-tools` with real history;
  the corresponding paths are then removed from the renamed `mootmaker-demo-data`. `git subtree
  split` is the fallback if `git filter-repo` is not installed (it will be added to the workstation
  manifest either way). Do **not** copy files without history — the commit trail is part of what
  this project is demonstrating.
- **GitHub redirects renamed repos automatically.** `mootmaker-tools` → `mootmaker-demo-data` keeps
  working for existing clones and links. Local remotes should still be updated explicitly rather
  than relying on the redirect, exactly as was done for the `mootmaker-e2e` → `mootmaker-test-infra`
  rename.
- **`gh` scope refresh is a hard prerequisite for Phase 3.** `gh auth refresh -s project` is
  interactive and browser-based, so it must be done by Geoff — an AI session cannot complete it.
- **The tools split is much safer than it first appears — tracked as
  [`mootmaker-tools#1`](https://github.com/geoffweatherall/mootmaker-tools/issues/1).** An initial
  read suggested renaming the repo would orphan Terraform state and risk duplicate AWS resources.
  Investigation on 2026-08-29 showed that is wrong. Three separate layers carry a name here, and
  only one contains `mootmaker-tools`:

  | Layer | Value | Contains `tools`? | Defined in |
  |---|---|---|---|
  | AWS resource names | `<env>-mootmaker-<tool>` | **No** | `var.project_name` default in `variables.tf`, via `resource_prefix` in `locals.tf` |
  | Terraform state key | `<env>/mootmaker-tools-<tool>/terraform.tfstate` | **Yes** | Hardcoded literal in each `deploy.sh` |
  | Repo name | `mootmaker-tools` | **Yes** | GitHub |

  Consequences: **no deployed AWS resource is affected by the rename** (resource names never
  contained `tools`, so nothing can be orphaned or duplicated), and **nothing breaks if this is
  ignored** — the state key simply keeps saying `mootmaker-tools` forever. This is a naming-hygiene
  decision, not a correctness problem. State exists under three environment prefixes
  (`production`, `test`, and the leaked `claude-260828-92oq`); the issue records the migrate-vs-pin
  options and a recommendation.

- **The cross-tool coupling survives the split untouched.** `sample-data-generator` invokes
  `database-reset` Lambda-to-Lambda by computing `"${var.environment}-mootmaker-database-reset"` as
  a deterministic string, deliberately *not* by reading the other project's Terraform state. Moving
  that tool to a different repo therefore changes nothing about the invocation. Only the deploy
  *order* dependency needs re-documenting, now as a cross-repo one.

- **There is already precedent for the state-key drift, unresolved.** The key
  `mootmaker-e2e-email/terraform.tfstate` still carries the *old* `mootmaker-e2e` repo name, which
  was renamed to `mootmaker-test-infra`. The rename was done correctly at the GitHub and checkout
  level and the state key was simply left behind — harmless, but empirical proof that this drift is
  silent and permanent by default. Worth settling alongside `mootmaker-tools#1`.
- **Tech stack, as actually deployed today** (verified 2026-08-29, for `docs/process/principles.md`):
  Java 25 on Lambda (`maven.compiler.release` 25, runtime `java25`), AppSync GraphQL, DynamoDB,
  Cognito, S3 + CloudFront, Route 53, SES; Terraform with S3 remote state; React 19.2, TypeScript
  6.0, MUI 9.2, Apollo Client 4.2, Vite 8.1, Vitest 4.1, Playwright; bash for all orchestration.
- **AWS SSO tokens expire mid-session** and refresh requires `aws sso login`. Any phase touching AWS
  should check credentials first rather than discovering it partway through.

---

## Testing impacts

There is no application code change, so no unit, integration, e2e, or acceptance test needs to
change *behaviourally*. The impacts are structural:

- **Path and link updates in test documentation.** `mootmaker-webapp/testing-strategy.md`,
  `mootmaker-api/testing-strategy.md`, and `mootmaker-test-infra/testing-strategy.md` all link to
  the hub's `testing-strategy.md` and `use-cases.md`, both of which move to `docs/reference/`.
- **Environment references.** Any test script or config defaulting to or documenting the `test`
  environment must be updated for Decision 3.
- **The tools split changes an acceptance-test prerequisite.** `mootmaker-api`'s acceptance tests
  depend on `database-reset` being deployed. The instruction for satisfying that prerequisite
  changes repo, and every place that documents it must change with it.
- **Verification for this work is different in kind.** The done condition for a normal change is a
  green acceptance run. Here the meaningful verification is: every repo still deploys, the
  acceptance suite still passes end to end against a fresh ephemeral environment *after* the tools
  split, and no documentation link is broken. A link check across all repos is part of the
  definition of done.
- **Existing known flakiness is unrelated and stays open.** `geoffweatherall/mootmaker-webapp#1`
  (intermittent `createRoom`/`createPerson` timeouts, ~1–2 per full run) is expected to keep
  occurring during verification runs and must not be mistaken for reorganisation damage.

---

## Documentation impacts

This work is *almost entirely* documentation, so rather than list what needs updating afterwards,
this section records what must not be missed:

- **Every inbound link to a moved hub document**, across all repos, in both markdown and script
  comments. Non-negotiable; a broken doc tree is worse than the current untidy one.
- **`designs/README.md`** — the `data-model.md` location reference, and the "Migrating older docs"
  section once `delete-my-account.md` is migrated.
- **`mootmaker-tools`'s README** splits into two, each documenting its own tools plus the new
  cross-repo deploy-order dependency.
- **`mootmaker-api`'s README** — the acceptance-test prerequisite now names a different repo.
- **Every repo's README** — the project index at the top of each links to sibling repos; two names
  change and one is new.
- **The hub README's To Do section** is deleted, replaced by a link to the Project board.
- **Claude Code's persistent memory** — `feedback_test_env_data_wipes_ok` and
  `feedback_ephemeral_env_workflow` both describe the `test` environment convention that Decision 3
  retires, and `project_repo_reorganization_2026_08` describes this work as pending. All three need
  updating when the relevant phase lands.

---

## Rollout & migration

No user-facing change and no data migration. The rollout risk is entirely about not breaking the
working development setup partway through.

**Phasing principle:** each phase leaves every repo in a working, deployable state. No phase
depends on a later phase to be coherent.

**Phase 4 (the tools split) is the only phase touching deployed AWS state rather than only files**,
so it stays last, after the documentation and process layers are settled — done in isolation and
verified with a full deploy plus acceptance run. It is, however, **less risky than originally
assessed**: investigation for
[`mootmaker-tools#1`](https://github.com/geoffweatherall/mootmaker-tools/issues/1) established that
no deployed AWS resource name contains `mootmaker-tools`, so the rename cannot orphan or duplicate
infrastructure, and the Lambda-to-Lambda coupling between the two new repos is a computed string
with no cross-project state dependency. The remaining state question is cosmetic.

**Rollback:** Phases 1–3 are documentation, GitHub metadata, and file moves — revertible by `git
revert` and by deleting issues/labels. In Phase 4 a repo rename is reversible via GitHub, and the
state work is only awkward if option B or C in `mootmaker-tools#1` is chosen — in which case take a
state backup first. Choosing option A (pin the keys) makes Phase 4 fully revertible too.

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Terraform state-key drift from the tools rename.** State keys hardcode `mootmaker-tools`; after the split they name a repo that no longer exists. **Downgraded from High to Low on investigation** — AWS resource names never contained `tools`, so nothing can be orphaned or duplicated, and ignoring it breaks nothing. Cosmetic, but silent and permanent by default (as `mootmaker-e2e-email` already demonstrates). | Low | Tracked as [`mootmaker-tools#1`](https://github.com/geoffweatherall/mootmaker-tools/issues/1) with options and a recommendation. Decide deliberately in Phase 4; if migrating, back up state and require `terraform plan` to show no changes before any apply. |
| **Leaked ephemeral environments keep accruing cost.** Four are live right now from one session; the teardown step is convention only and it failed four times in a day. | Medium | Tear down the current four immediately (Phase 0). Define a maximum ephemeral lifetime in `docs/process/environments.md` and hand the scheduled-sweep requirement to the CI/CD design. |
| **Broken documentation links across repos** after the hub restructure. | Medium | Update inbound links in the same phase as each move; run a link check across all repos as a definition-of-done item. |
| **`database-reset` deployed against production during split verification.** It deletes all rooms and meetings. Production is a demo, so the data is replaceable — but it is the public showcase. | Medium | Verify the split only against ephemeral environments. Re-seed production from `sample-data-generator` only deliberately. |
| **Losing the value of the README essay** by moving it somewhere nobody reads. | Medium | The README keeps headline learnings inline with prominent links; the move is only of the long-form detail. Judge the result by reading the new README cold. |
| **Process weight exceeding the value it adds.** Five hats, templates, agent definitions, manifests, and a board is a lot of structure for one person. | Medium | Everything created here is markdown and cheap to delete. NB-2 and NB-3 are explicit review points. If a piece of structure is not being used in a month, remove it rather than maintaining it. |
| **Agent instructions ignored by a non-Claude tool** (NB-1). | Low | Detectable on first Antigravity use; Decision 6 has a defined fallback. |
| **Issue migration importing stale work.** Several README todos appear already done. | Low | Triage against reality rather than bulk-importing (choice 8). |

---

## Working conventions for execution

Most of this work will be done unattended, across sessions that may run out of context partway
through a phase. This section exists so that is a non-event rather than a recovery problem.

**The core fact:** running out of context does not destroy work — files on disk persist. What is
lost is *context*: why a half-finished decision was made, and what is done versus in flight. The
conventions below exist to keep that knowledge on disk rather than in a session.

### Commit and checkpoint discipline

- **Commit within phases, not only at phase boundaries.** Every logically complete unit of work
  gets its own commit, following the project's existing convention of separate commits per piece of
  work rather than bundled ones.
- **Tick the checkbox in the same commit as the work it describes.** The checklist is the resume
  point; a tick that lands in a later commit than its work is worse than no tick.
- **Any checkbox spanning more than ~30 minutes gets a progress note appended in place**, in the
  same commit, e.g. `- [ ] … (done: api, webapp, test-infra; remaining: 5 repos)`. A cold session
  cannot otherwise tell whether a coarse item is 10% or 90% complete.
- **Push at every phase boundary at minimum, and more often when running unattended.** An
  unpushed commit is invisible from another machine.
- **Treat this document as a running log, not a frozen plan.** When reality diverges from the
  design — and it will — update the design rather than silently working around it. A design doc
  describes the current plan.
- **Git operations are pre-approved.** Branch, commit, push, open and merge PRs without pausing to
  ask (confirmed 2026-08-29). Stopping an unattended run for routine git mechanics buys nothing —
  the work is reviewed at the PR, and git is recoverable by design. Genuinely destructive history
  operations (force-pushing over someone else's commits, discarding changes that were not yours)
  still warrant a word first.

### Pull requests for this reorganisation

Yes, this work uses PRs — but **a PR is per-repo, and this work spans up to 10 repos**, so "one PR
per phase" is not achievable. Taken literally it would mean one PR per repo per phase: roughly
twenty across Phases 1 and 2 alone, most of them a single mechanical file. The rule instead:

| Scope | PR approach |
|---|---|
| **Hub (`mootmaker`)** | **One PR per phase.** All the judgment-dense work is here — README, principles, process and role docs. Real review value, and a natural checkpoint. |
| **Satellite repos** | **One PR each for the whole reorganisation**, opened when that repo's changes are complete (end of Phase 2 for most; Phase 4 for the two tools repos). Their changes are mechanical and script-generated — `AGENTS.md`, the `CLAUDE.md` symlink, link updates — and are reviewed via the generating script's diff rather than file by file. Still gives a record and a clean revert point, without ten near-empty PRs. |
| **Phase 3** | **No PR — none is possible.** Labels, issues, and the Project board are GitHub state, not repository content; there is nothing to branch. Its review gate is the `[Geoff]` triage confirmation already in the checklist. |
| **Repo create / rename / archive (Phase 4)** | **Not PR-able either.** Done directly, with the verification steps in that phase standing in for review. |

Review and merge follow Decision 8: read the diff, merge it, and — for a design — promote Status
separately. There is no approval step to wait for.

**This is the first real cost of choosing 10 repos over consolidation** (Decision 1): every
cross-cutting change is now N pull requests instead of one. Worth watching honestly during
execution — if it becomes genuinely obstructive rather than merely tedious, that is evidence to
revisit the topology, not a reason to quietly stop opening PRs.

### Resuming a cold session

In order, without skipping:

1. Read this document top to bottom. It is the authoritative context.
2. Find the first unticked checkbox — that is nominally where work resumes.
3. Read `git log` for the repos that phase touches, to see what actually landed.
4. **Verify against reality before assuming.** An unticked box does not reliably mean "not
   started"; it may mean a session ended mid-item. Check the filesystem, the repos, and AWS before
   redoing anything, especially anything destructive or non-idempotent.

### Prefer scripts over per-file reasoning

For any repetitive sweep — link updates across repos, label creation, placing `AGENTS.md` files,
checking for broken links — write a script, run it, and review its diff, rather than reasoning
file-by-file. This is more reliable, produces a reviewable artifact, and saves substantially more
context than any model-tier choice does. It is the single biggest efficiency lever in this plan.

### Model selection per phase

The phases differ enormously in what they demand, and the split follows the same instrumentability
logic set out in `docs/showcase/debugging-techniques.md`: where the work can cheaply check itself
against reality, fast iteration beats deep reasoning; where it cannot, the reasoning has to be
right the first time.

| Phase | Model | Why |
|---|---|---|
| **0** Prerequisites | Sonnet | Mechanical: auth checks, teardown, verification. |
| **1** Hub restructure | **Opus** for the README rewrite; Sonnet for the moves and link sweep | The README is the portfolio front door and the one document a stranger judges the project by. The moves are mechanical and better scripted. |
| **2** Process, principles, roles | **Opus** — the phase worth paying for | Judgment-dense original prose that becomes the project's source of truth. The failure mode is *invisible*: a mediocre `principles.md` looks fine, it is simply bland, anticipates no objections, and never gets consulted again. Nothing here can be checked against reality cheaply, which is exactly the non-instrumentable case. |
| **3** Issues and board | **Opus** for the triage; Sonnet for issue creation | Deciding whether a README todo is genuinely already done requires real understanding of the codebase, and several look done but are not. Borderline — the triage *is* checkable by grepping and running tests — but the cost of filing wrong or duplicate issues is paid later by everyone reading the board. |
| **4** Repo split and environments | Sonnet | Highly instrumentable. `terraform plan` says immediately and cheaply when you are wrong, and deploys either work or do not. Fast iteration beats deep reasoning here. |
| **5** Follow-on designs and memory | **Opus** for the two design stubs; Sonnet for the memory updates | The stubs are seeds that future designs grow from; a weak framing there propagates. Memory edits are mechanical. |

Roughly a third of the work sits on Opus. **Honest caveat:** for the prose-heavy phases the
difference is real but genuinely hard to measure — it shows up as documents that make connections
nobody asked for, versus competent template-fills. For the mechanical phases there is no measurable
difference and paying for it is waste.

**Operational constraint: Claude cannot switch its own model.** The session model is set by Geoff
via `/model` (or the `model` setting); an AI session has no way to change it mid-run. The table
above is therefore *guidance for Geoff*, not something that happens automatically — and a plan that
assumed per-phase switching during an unattended run would be wrong.

How to reconcile that with running unattended:

- **Run Phases 1–2 on Opus in one go, and do not try to switch.** The README rewrite and all of
  Phase 2 are the Opus-worthy bulk. The Sonnet-suited parts are a minority *and* are supposed to be
  done with a script (see "Prefer scripts over per-file reasoning") — reviewing a generated diff is
  cheap on any model, so model choice barely matters for exactly the work Sonnet was suggested for.
  The scripting convention largely dissolves this problem.
- **Take the clean break before Phase 4**, which is different in kind (terraform, deploys,
  verification — highly instrumentable) and follows a `[Geoff]` gate at the end of Phase 3 anyway.
  That is the one switch genuinely worth making.
- `opusplan` (a `/model` option pairing Opus planning with Sonnet execution) may suit this work,
  but how it decides which is which has not been verified here — investigate before relying on it.

### When to notify, and when to just keep going

Notification reaches a phone via Remote Control. **Verified 2026-08-29: mobile push is currently
disabled in `/config` and must be enabled before any genuinely unattended run** — otherwise a
blocked session simply stops with nobody informed.

**Notify when:**
- Blocked on one of the human gates below and unable to proceed with anything else.
- A destructive or hard-to-reverse step needs confirmation that was not pre-authorised.
- Something has failed repeatedly and is not converging.
- A phase completed while running unattended.

**Do not notify for:** routine progress, individual commits, or anything discoverable by reading
the checklist later.

Before notifying and stopping, **do everything else that is not blocked first** — a gate on Phase 3
should not idle work that Phase 1 or 2 could still complete.

### Human gates

Five points require Geoff. Three can be answered up front; if they are, Phases 1 and 2 run
unattended end to end.

| Gate | Phase | Front-loadable? |
|---|---|---|
| ~~`gh auth refresh -s project`~~ | 0 (needed by 3) | ✅ Done 2026-08-29 |
| ~~Approve this design → Status `Ready`~~ | 0 | ✅ Done 2026-08-29 |
| ~~Choose an option in [`mootmaker-tools#1`](https://github.com/geoffweatherall/mootmaker-tools/issues/1)~~ | 4 | ✅ Done 2026-08-29 — option B |
| ~~Decide when to tear down `test`~~ | 4 | ✅ Done 2026-08-29 — immediately |
| Sanity-check one `AGENTS.md` + `principles.md` | 2 | No — needs the documents to exist |
| Confirm the issue triage | 3 | No — needs the triage to exist |

The last two are unavoidable stopping points, and are precisely where notification matters.

---

## Implementation checklist

Five phases, each leaving every repo working. Pause for a check-in between phases. Each phase notes
its recommended model — see "Model selection per phase" above for the reasoning.

### Phase 0 — Prerequisites
*Model: Sonnet.*

- [x] `[Geoff]` Run `gh auth refresh -s project` (interactive, browser). **Done 2026-08-29** —
      scopes now `gist, project, read:org, repo, workflow`; `gh project list` succeeds.
- [x] `[Geoff]` Approve this design — move Status to `Ready`. **Done 2026-08-29.**
- [x] `[Geoff]` Choose the `mootmaker-tools#1` state option. **Done 2026-08-29 — option B**
      (migrate keys to the new repo names). Applied in Phase 4.
- [x] `[Geoff]` Decide when to tear down `test`. **Done 2026-08-29 — immediately**, before Phase 1.
- [ ] `[Claude]` Tear down `test` (tools, then webapp, then API — `teardown-ephemeral-env.sh`
      refuses non-ephemeral names by design, so this is manual `undeploy.sh` calls). Confirm no
      `test-` resources or state remain.
- [ ] `[Claude]` Confirm `aws sso login` is valid before any AWS-touching step.
- [ ] `[Claude]` Confirm `git filter-repo` availability; if missing, note it for the manifest and
      plan the `git subtree split` fallback.
- [x] `[Geoff]` Approve tearing down the four leaked ephemeral environments
      (`claude-260828-006t`, `-2flz`, `-92oq`, `-u3ou`) — **confirmed 2026-08-29**, none still
      needed.
- [x] `[Claude]` Tear them down and confirm no `claude-*` state or resources remain.
      **Done 2026-08-29.** 228 AWS resources destroyed: 55 per environment (45 API + 10 webapp)
      across all four, plus 8 tool resources in `claude-260828-92oq` (`database-reset` and
      `sample-data-generator`, undeployed separately — see the note below). All four teardowns
      exited 0. Verified against live AWS, not just the logs: zero remaining `claude-`-prefixed
      Lambdas, DynamoDB tables, Cognito user pools, AppSync APIs, or S3 buckets. State bucket now
      holds only `bootstrap`, `domain`, `mootmaker-e2e-email`, `production`, and `test`.
- [ ] `[Claude]` Raise an issue in `mootmaker-test-infra` for the teardown-reliability gap, and one
      for `list-ephemeral-envs.sh` taking over two minutes to return (it timed out at 120s during
      this investigation and had to be replaced with direct AWS queries).
- [ ] `[Claude]` Raise an issue in `mootmaker-test-infra` for the teardown-completeness gap found
      while doing the above — see "A gap in `teardown-ephemeral-env.sh`" under Decision 3.

### Phase 1 — Hub restructure
*Model: **Opus** for the README rewrite; Sonnet for the moves and link sweep.*

- [x] `[Claude]` Create the `docs/` tree and move every document to its target location, using
      `git mv` so history follows. **Done** — all moves recorded by git as renames, so history
      follows each file. The unreferenced 5MB `image.png` turned out to be a Claude Code session
      screenshot from when this project was called `room-booking`; it is filed with the other
      session screenshots under a descriptive name rather than in marketing.
- [x] `[Claude]` Split `README.md`: extract the Learnings essay to `docs/showcase/learnings.md`;
      rewrite the README as the ~100-line showcase-first landing page; delete the To Do section
      (its content is captured for Phase 3 first). **Done** — README is 89 lines; the essay moved
      intact with no editing of Geoff's writing; the multi-environment mechanics moved to
      `docs/development/environments.md`; the 24 open and 7 completed To Do items are captured for
      Phase 3 triage.
- [x] `[Claude]` Move `designs/data-model.md` to `docs/reference/data-model.md` and update
      `designs/README.md`. **Done** — `designs/README.md` also needed prose fixes the link sweep
      could not catch, since they were backticked paths rather than markdown links.
- [x] `[Claude]` ~~Migrate `delete-my-account.md` / `-todo.md` into `designs/delete-my-account.md`
      under the template~~ — **deliberately not done; plan changed.** Both files are archived to
      `designs/archive/` instead. Writing a template-shaped design for a feature nobody is currently
      building produces a document that rots before it is used, and the archived pair is already the
      most detailed record of that thinking. `designs/README.md` now states the rule this follows:
      when an archived doc is picked up for real work, write a fresh design under the current
      template then, and leave the original as history — which is exactly what happened with
      `google-sign-in`.
- [x] `[Claude]` Write a link-rewrite script (old path → new path) rather than editing file by
      file; keep it in `tools/` until the sweep is done so the work is reviewable and repeatable.
      **Done** — `tools/rewrite-links.py`. It resolves each link against the file's *old* directory
      before mapping, which is what makes a moved file's outgoing links come out right. It is
      one-shot and refuses to re-run: a second pass re-resolves already-correct links and walks the
      `../` prefix one level further out each time, which happened during development and was caught
      by the checker.
- [x] `[Claude]` Run the sweep and review its diff, per repo — tick each as it lands:
  - [x] `mootmaker` (internal links, the largest set)
  - [x] `mootmaker-api`
  - [x] `mootmaker-webapp`
  - [x] `mootmaker-test-infra`
  - [x] `mootmaker-tools`
  - [x] `mootmaker-domain`
  - [x] `mootmaker-bootstrap-terraform` — no inbound links, nothing to change
  - [x] `mootmaker-bootstrap-aws-accounts` — no inbound links, nothing to change
- [x] `[Claude]` Write and run a link checker across all repos; fix anything it finds. No broken
      relative or GitHub links anywhere. **Done** — `tools/check-links.py`; 0 broken links across 58
      markdown files in all eight repos, down from 171 immediately after the moves.
- [ ] `[Claude]` Commit as separate commits per piece of work; open the hub PR for this phase. Leave
      satellite-repo branches open — they get one PR each at the end of Phase 2 (see "Pull requests
      for this reorganisation").

### Phase 2 — Process, principles, roles, and agent instructions
*Model: **Opus** throughout — this is the phase worth paying for.*

- [x] `[Claude]` Write `docs/process/README.md` — the canonical workflow rules that every
      `AGENTS.md` points to.
- [x] `[Claude]` Write `docs/process/principles.md`, including the verified tech stack and the
      review boundary from Decision 9.
- [x] `[Claude]` Write the remaining process docs — tick each:
  - [x] `docs/process/branching-and-prs.md` (must state the review-then-merge reality from
        Decision 8 explicitly — there is no Approve step on a solo project — and the per-repo PR
        strategy from "Working conventions")
  - [x] `docs/process/issues-and-board.md`
  - [x] `docs/process/environments.md` (including the ephemeral lifetime limit from Decision 3)
  - [x] `docs/process/ai-collaboration.md` (model choice, AI review, instrumentability — draw on
        `docs/showcase/debugging-techniques.md` and the "Working conventions" section above)
- [x] `[Claude]` Write `docs/roles/` — tick each:
  - [x] `README.md` (the hats index)
  - [x] `developer.md`
  - [x] `product-owner.md`
  - [x] `marketer.md`
  - [x] `operator.md`
  - [x] `author.md`
  - [x] `templates/` (one-pager, marketing brief, release note, incident note)
- [x] `[Claude]` Write `docs/roles/agents/` definitions (one per hat) and `tools/install-agents.sh`.
- [x] `[Claude]` Write `docs/development/` — tick each:
  - [x] `getting-started.md`
  - [x] `architecture.md`
  - [x] `workstation.md`
- [x] `[Claude]` Write `tools/workstation/manifest.yaml` and `check.sh`; seed the manifest from what
      this workspace actually needs (git, gh + scopes, aws cli + SSO, terraform, java 25, maven,
      node/npm, playwright browsers, jq, git-filter-repo).
- [x] `[Claude]` Run `check.sh` on this machine and fix anything it gets wrong.
- [x] `[Claude]` Add `AGENTS.md` to every repo; fold in existing `CLAUDE.md` content (only `-api`,
      `-webapp`, and `-tools` have one today); replace `CLAUDE.md` with a symlink. Tick each:
  - [x] `mootmaker` (hub)
  - [x] `mootmaker-api`
  - [x] `mootmaker-webapp`
  - [x] `mootmaker-tools`
  - [x] `mootmaker-test-infra`
  - [x] `mootmaker-domain`
  - [x] `mootmaker-bootstrap-terraform`
  - [x] `mootmaker-bootstrap-aws-accounts`
  - [x] `mootmaker-android` (placeholder — repo is empty)
- [x] `[Claude]` Open the hub PR for this phase, and one PR per satellite repo covering all its
      reorganisation changes from Phases 1 and 2 together.
- [ ] `[Geoff]` Sanity-check one `AGENTS.md` and the principles doc — these are the two documents
      that most need to reflect what you actually think.

### Phase 3 — Issues and the Project board
*Model: **Opus** for the triage; Sonnet for issue and label creation.*

- [ ] `[Claude]` Create the standard label set in every repo.
- [ ] `[Claude]` Triage the captured README To Do list against reality: confirm which items are
      already done, merge duplicates, and identify which repo each belongs to. Present the triage
      before creating anything.
- [ ] `[Geoff]` Confirm the triage.
- [ ] `[Claude]` Create issues from the triaged list in the correct repos.
- [ ] `[Claude]` Raise issues for the gaps found while drafting this design: NB-5 (use-cases
      per-frontend tagging), NB-6 (unversioned workspace `.claude/` config).
- [ ] `[Claude]` Create the "Mootmaker" Project with the agreed fields; add all open issues,
      including `mootmaker-webapp#1`.
- [ ] `[Claude]` Link the board from the hub README and `docs/process/issues-and-board.md`.

### Phase 4 — Repo split and environment change
*Model: Sonnet — highly instrumentable, `terraform plan` corrects you cheaply.*

- [ ] `[Claude]` Back up Terraform state for the affected environments before touching anything.
- [ ] `[Claude]` Create `mootmaker-admin-tools`; extract `database-reset` and `database-repair`
      with history.
- [ ] `[Claude]` Rename `mootmaker-tools` → `mootmaker-demo-data` on GitHub; update the local
      checkout directory and remote; remove the admin tools from it.
- [x] `[Geoff]` Choose an option in
      [`mootmaker-tools#1`](https://github.com/geoffweatherall/mootmaker-tools/issues/1).
      **Done 2026-08-29 — option B**, migrate the keys to the new repo names.
- [ ] `[Claude]` Apply option B: copy each state object from `<env>/mootmaker-tools-<tool>/` to
      `<env>/mootmaker-demo-data-<tool>/` or `<env>/mootmaker-admin-tools-<tool>/` as appropriate,
      update the `key=` literal in each `deploy.sh`, verify, then delete the old objects. Back up
      state first and require `terraform plan` to show **no changes** before any apply. Only
      `production` remains affected now that `test` is torn down. Close the issue with the
      reasoning and a commit link.
- [ ] `[Claude]` Settle the pre-existing `mootmaker-e2e-email` state-key mismatch the same way,
      while this machinery is open.
- [ ] `[Claude]` Split `deploy-all.sh` / `undeploy-all.sh`; write both READMEs including the new
      cross-repo deploy-order dependency; add `AGENTS.md` to the new repo.
- [ ] `[Claude]` Update every reference to `mootmaker-tools` across all repos.
- [ ] `[Claude]` Write `docs/process/environments.md`'s production+ephemeral model; update every
      script/doc referencing the `test` environment.
- [x] `[Geoff]` Decide when to tear down the `test` environment. **Done 2026-08-29 — immediately**,
      before Phase 1 rather than here. Executed in Phase 0.
- [ ] `[Claude]` Full verification: fresh ephemeral environment, deploy everything from both new
      repos plus API and webapp, run the acceptance suite green.

### Phase 5 — Follow-on designs and memory
*Model: **Opus** for the two design stubs; Sonnet for the memory updates.*

- [ ] `[Claude]` Write `designs/ci-cd-pipeline.md` (Drafting), including the free-Actions-on-public-
      repos finding, AWS OIDC, and the reserved schema-publish step.
- [ ] `[Claude]` Write `designs/graphql-schema-sharing.md` (Drafting), including the GitHub Packages
      finding.
- [ ] `[Claude]` Update Claude Code memory: retire the `test`-environment conventions, update the
      ephemeral workflow memory, and update the reorganisation memory to reflect the new structure.
- [ ] `[Claude]` Move this document's Status to `Shipped`.

---

## Definition of done

- All five phases complete, merged per the PR strategy in "Working conventions" — a hub PR per
  phase, one PR per satellite repo, and no PR for Phase 3 (nothing to branch). Each read and merged
  by Geoff; no approval step, per Decision 8.
- Every repo deploys cleanly to a fresh ephemeral environment, and the `mootmaker-webapp` acceptance
  suite is green against it — allowing for the known, separately-tracked flakiness in
  `mootmaker-webapp#1`.
- `tools/workstation/check.sh` runs on this laptop and correctly reports the current toolchain.
- No broken documentation link in any repo, verified by an actual link check, not by inspection.
- The hub README reads well cold, as a landing page a stranger would land on.
- Every repo has an `AGENTS.md` that a fresh agent session could work from.
- The Project board shows every open issue across every repo, including `mootmaker-webapp#1`.
- The README To Do list no longer exists, and nothing in it was lost — every live item is an issue.
- Claude Code memory reflects the new environment model and structure rather than the old one.
