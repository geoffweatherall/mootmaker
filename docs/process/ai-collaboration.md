# Working with AI on mootmaker

This project is largely built by AI agents under human direction, which is the point of it. This
document records what has actually been learned about doing that well — not aspirations.

It is deliberately not Claude-specific. Claude Code is the primary tool and the one processes are
optimised around, but other agentic tools are expected here, and nothing in the process should have
to be rewritten to accommodate one.

## How an agent finds its instructions

Every repository has an **`AGENTS.md`** — the emerging cross-tool convention, read by Antigravity,
Cursor, Codex, Copilot and others. It carries repo-specific guidance plus a pointer to
[`README.md`](README.md) in this folder, which is the canonical description of how work is done.

**`CLAUDE.md` is a symlink to `AGENTS.md`** in each repository. Claude Code reads `CLAUDE.md`
automatically, so the symlink means both names resolve to one file: Claude loses nothing, every
other tool gets identical instructions, and there is exactly one copy to keep current.

The single source of truth is this folder. Repository `AGENTS.md` files stay short and point here
rather than duplicating, because duplication needs a generator and a CI check to stay honest, and
CI does not exist yet.

## Choosing a model

The useful question is not "which model is best" but **"can this work check itself against
reality?"**

**Instrumentable work** — where you can run it, observe real state, and iterate cheaply. Deploys,
Terraform, test failures, anything with a reproducible failure. Here the running system corrects
wrong turns for free on every loop, so **iteration speed matters more than depth of reasoning**. A
faster, cheaper model is genuinely the right tool, not a compromise.

**Non-instrumentable work** — where nothing external tells you that you are wrong. Original prose,
principles, architecture, a design nobody has built yet, a bug you cannot reproduce. Here every step
has to be right without correction, and **a deeper-reasoning model earns its cost**.

The failure mode that makes this matter: on non-instrumentable work, being wrong is *invisible*. A
mediocre principles document looks fine — it is simply bland, anticipates no objections, and never
gets consulted again. Nothing fails to tell you.

Practically:

- Default to the faster tier for a new bug. Treat "I have tried several things and I am not
  narrowing it down" as the signal to reach for deeper reasoning — not the bug's apparent difficulty
  up front, which is nearly impossible to judge before you start.
- Use the deeper tier for design documents, principles, and anything that becomes a source of truth.
- **An agent cannot switch its own model.** In Claude Code the session model is set by the human via
  `/model`. Guidance about which model suits which phase is therefore a note to the *human*, and a
  plan that assumes automatic switching mid-run is wrong.

`../showcase/debugging-techniques.md` works through this in detail, using a real race condition as
the example.

## AI reviewing AI

Having a second agent review the implementing agent's work is **available and encouraged, not
required** — see [branching-and-prs.md](branching-and-prs.md#ai-review).

The honest state of it: there is not yet evidence it earns its cost, and there is a structural
limitation — a second agent acts through the same GitHub account, so its review is
indistinguishable from the author's. Fixing that properly needs a separate machine identity, which
is deferred until AI review is actually being used enough to justify the maintenance.

## What works, and what does not

Distilled from [`../showcase/learnings.md`](../showcase/learnings.md) into operational advice.

**Let the agent be agentic.** Running tests, deploying, inspecting real AWS state, writing throwaway
scripts to check its own work — this is where most of the gain is. An agent restricted to suggesting
code forgoes it.

**The codebase is the style guide.** Agents follow patterns they find far more reliably than
instructions they are given. Keeping the code consistent does more than writing conventions down.

**Give it the design, not the task.** A design document is a better prompt than a description of
work, because it contains the decisions and the reasoning behind them. "Read `designs/<name>.md` and
build it" should be a sufficient instruction.

**Be specific about verification.** Agents will report success on a script's exit code if you let
them. Ask for the resource to be checked, the page loaded, the query run.

**Correct rather than restart.** Agents respond well to being told what is wrong. Pointing out the
specific mistake is almost always faster than re-prompting from scratch.

**Watch for confidently wrong.** The mistakes are plausible-looking, which is exactly what makes
test quality the place human attention pays best. See
[principles.md](principles.md#how-much-human-review-the-code-actually-gets).

**Some problems still need a human.** An agent got within one sentence of a Java cold-start fix and
could not make the final connection itself. Reading its summary carefully is often where the answer
is hiding.

## Context and long-running work

**Running out of context does not destroy work** — files persist. What is lost is knowledge of
*why* a half-finished decision was made and what is done versus in flight. So put that on disk:

- Commit within a piece of work, not only at the end.
- Tick a checklist item in the same commit as the work it describes.
- Add a progress note to any item spanning more than about half an hour.
- Treat a design as a running log, updated as reality diverges from plan.

**When resuming cold: verify before assuming.** An unticked checkbox does not reliably mean "not
started" — it may mean a session ended mid-item. Check the filesystem, the repositories, and AWS
before redoing anything, especially anything destructive or non-idempotent.
