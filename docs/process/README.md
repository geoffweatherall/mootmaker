# How work is done on mootmaker

**This is the canonical description of how work happens here.** Every repository's `AGENTS.md`
points at this file. If you are an AI agent starting work in any mootmaker repository, read this
before doing anything beyond answering a question.

It is written to be followed by a human or by any AI tool — Claude Code, Google Antigravity, or
something that does not exist yet. Nothing here depends on a particular tool.

## The short version

1. **Work of any real size starts with a design document**, not with code. See
   [`../../designs/README.md`](../../designs/README.md).
2. **Bugs and small changes start with a GitHub issue**, in the repository they concern. Before
   fixing one, post an implementation plan as a comment and get it approved by a human. See
   [issues-and-board.md](issues-and-board.md).
3. **All work happens on a branch and lands via a pull request.** See
   [branching-and-prs.md](branching-and-prs.md).
4. **Testing against a real deployment is the quality gate**, not code review. See
   [principles.md](principles.md) and [`../reference/testing-strategy.md`](../reference/testing-strategy.md).
5. **Environments are production or ephemeral.** Nothing else is long-lived. See
   [environments.md](environments.md).
6. **Leave the documentation true.** If your change makes a document wrong, fixing it is part of
   the change, not a follow-up.

## The documents in this folder

| Document | What it settles |
|---|---|
| [principles.md](principles.md) | The constraints everything else is built on — cost, stack, and how much human review code actually gets |
| [branching-and-prs.md](branching-and-prs.md) | Branch naming, commit discipline, how a PR is reviewed and merged, and what to do about cross-repo changes |
| [issues-and-board.md](issues-and-board.md) | Where issues live, the label set, and the cross-repo project board |
| [environments.md](environments.md) | Which environments exist, how they are named, and the rules for tearing them down |
| [ai-collaboration.md](ai-collaboration.md) | Choosing a model, AI-reviewing-AI, and what makes a bug worth reasoning about versus instrumenting |

Related, elsewhere:

- [`../../designs/README.md`](../../designs/README.md) — the design-document pattern and its
  `Drafting → Ready → Building → Shipped` lifecycle.
- [`../roles/README.md`](../roles/README.md) — the "hats" a person wears here, and how a session in
  each one should start.
- [`../development/`](../development/) — how to get set up, how the system fits together, and how
  environments work mechanically.
- [`../reference/`](../reference/) — what is true today: data model, testing strategy, use cases,
  business functionality.

## Rules that apply to every piece of work

These are the ones most often got wrong, so they are stated here rather than buried.

**Read the repository's `README.md` first.** Each repo's README is load-bearing — it describes
architecture, scripts, and conventions, and is kept current deliberately. It is faster and more
reliable than inferring the same facts from code.

**Keep documentation true as you go.** This project treats documentation as something both humans
and agents read to orient themselves, so a stale document is a real defect. If your change makes a
README, a reference doc, or a design wrong, fix it in the same change.

**One piece of work, one commit.** Do not bundle unrelated changes because they happened in the
same session. If a single file's diff spans two pieces of work, split it. See
[branching-and-prs.md](branching-and-prs.md#commits).

**Verify against reality, not against your own output.** Do not report a deploy, a test run, or a
teardown as successful because a script exited zero — check the thing itself. Several defects in
this project's history were found precisely this way, and several were missed by not doing it.

**Say what actually happened.** If tests fail, say so and show the output. If you skipped a step,
say which. A confident summary that does not match reality is worse than no summary.

**If you install a tool that future work will need, add it to the workstation manifest**
([`../../tools/workstation/manifest.yaml`](../../tools/workstation/manifest.yaml)) as part of that
session's work. Not as a follow-up — it will not happen.

**Do not create long-lived environments.** See [environments.md](environments.md). Ephemeral
environments cost real money and have leaked before; tearing yours down is part of finishing.

## When something here is wrong

These documents describe the current agreement, not a permanent one. If following a rule produces a
worse outcome than breaking it, that is worth saying — in the PR, in the design, or in an issue.
The process is younger than the project and is expected to change.
