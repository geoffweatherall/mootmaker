# Branching, commits, and pull requests

## Branches

`main` is the default branch in every repository and is always deployable. Work happens on a branch
and lands via a pull request.

| Prefix | For | Example |
|---|---|---|
| `design/<name>` | Writing or revising a design document | `design/project-reorganisation` |
| `feature/<name>` | Implementing a design | `feature/date-time-format-settings` |
| `fix/<issue>-<slug>` | A bug fix, referencing its issue number | `fix/1-flaky-settings-dialog` |
| `docs/<name>` | Documentation-only changes | `docs/testing-strategy-refresh` |
| `chore/<name>` | Tooling, dependencies, housekeeping | `chore/bump-playwright` |

**A feature branch is named after the design it implements**, not after the part of it you happen
to be doing. `designs/date-time-format-settings.md` is implemented on
`feature/date-time-format-settings` — in every repository the design touches. See
[Cross-repo changes](#cross-repo-changes).

**Always cut a design's branches fresh from `main`. Never continue a design's work on a branch that
already exists**, and never stack it on an unrelated in-flight branch. **Whatever branch a working
copy happens to have checked out when you arrive is not a signal** — a checkout is left over from
whatever was done last, it is not an instruction, and it carries no claim on the next piece of work.
Check out `main`, pull, and branch from there, in each repository, before writing anything.

This is not a judgement call and it is not worth asking about. Two pieces of work sharing a branch
means neither can be reviewed or merged on its own, and one PR then carries a diff nobody asked for.
The only exception is a design that genuinely *depends* on unmerged work in another branch — and
then the dependency belongs in the design document and in both PR descriptions, stated explicitly,
not left implicit in a branch point.

**Branch protection is deliberately not enabled.** With one developer it would mostly obstruct.
The discipline here is convention, and the review that matters is described below.

## Commits

**One piece of work, one commit.** Do not bundle unrelated changes because they landed in the same
session. If a single file's diff spans two pieces of work, split it — revert one set of hunks,
commit, reapply, commit again. This is more work and it is worth it: each commit should be
independently meaningful and independently revertible.

**Write commit messages that explain why, not what.** The diff already says what changed. The
message should say what problem it solves and what was considered — a future reader (or agent)
reconstructing a decision has nothing else to go on.

**Reference issues.** `Closes #12` in a commit or PR body closes the issue automatically when
merged. This is the main reason issues live in the repository they concern — see
[issues-and-board.md](issues-and-board.md).

**Commit within a phase, not only at the end of one.** For long pieces of work, commit each
logically complete unit as it lands. A session that runs out of context mid-task should leave
behind a readable trail, not a giant uncommitted diff.

**Attribution.** Commits made with AI assistance carry a `Co-Authored-By` trailer naming the model.
This is the honest record of who wrote what.

## Pull requests

Every change lands via a PR, including documentation. The PR is the unit of review and the thing
that gets linked from an issue or a design.

**A PR description should say what changed and why**, call out anything the author is unsure
about, and explicitly flag any deviation from the design it implements. Deviations are normal —
silently deviating is not.

### Review and merge

**There is no approval step, and there cannot be.** GitHub blocks approving your own pull request,
and every PR here is authored by the account that would approve it — including PRs an AI agent
opens, since agents act through `gh` authenticated as Geoff. Designing a gate around a button that
can never be pressed would be broken by construction.

So:

- **Reading the diff is the review. Merging is the approval.** Nothing is lost, because branch
  protection is not enabled and self-merge is expected.
- **For a design, the real gate is elsewhere**: the `Drafting → Ready` promotion in the design's own
  `Status:` line, which is Geoff's alone. That is deliberately recorded in the artifact rather than
  in GitHub's review state, so any tool can read it.
- **Merging and promoting are separate acts.** Merging a design PR puts the document on `main`; it
  does not make the design build-from-able.

How much of the diff actually gets read is set by the review boundary in
[principles.md](principles.md#how-much-human-review-the-code-actually-gets) — design and tests
properly, security/data/IAM/cost changes properly, everything else skimmed.

### AI review

A second AI reviewing the implementing agent's work is **available and encouraged, not required.**
Run it when a change is large, subtle, or in one of the always-reviewed categories. Record the
findings as a PR comment so there is a trail of what it caught.

It is not mandatory because there is no evidence yet that it earns its cost, and mandating it would
bake in an untested assumption. Note also that a second agent currently acts through the same GitHub
account, so its review is indistinguishable from the author's — a genuine limitation, tracked as
NB-7 in [`../../designs/archive/project-reorganisation.md`](../../designs/archive/project-reorganisation.md).

## Cross-repo changes

Mootmaker is many repositories, and a single design often touches several. **A pull request cannot
span repositories**, so one logical change becomes several PRs.

**Every design must name the repositories it touches**, in its "Impacts on components" section.
That list is what tells an implementer how many branches and PRs the work needs.

**Create the branch in every repository the change touches, with the same name in each, before
starting the implementation.** Take the name from the design (`feature/<design-doc-slug>`) and
create one in each repository its "Impacts on components" section names — including repositories
whose change is only a line of documentation. Do this up front rather than branch-by-branch as you
reach each repo: it means the whole set is discoverable by name alone, with no tracking document,
and it stops work landing on `main` in the repo you touched last and least deliberately.

A repository that turns out to need no change after all is fine — delete its unused branch, or
leave it; an empty branch costs nothing and its absence would be ambiguous.

**Sequence merges by dependency.** If the API change must land before the webapp change works,
merge in that order. If they must land together, say so in both PR descriptions — there is no
mechanism to enforce it, so it relies on the description being read.

**This is a real cost of the multi-repo layout**, accepted deliberately when the topology was
chosen. If it becomes genuinely obstructive rather than merely tedious, that is evidence worth
recording — it argues for revisiting the repository split, not for quietly skipping the PRs.
