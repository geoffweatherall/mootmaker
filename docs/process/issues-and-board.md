# Issues and the project board

## Where issues live

**An issue is filed in the repository whose code it concerns.** A webapp bug goes in
`mootmaker-webapp`; a Terraform state question goes in the repo that owns that state.

The reason is `Closes #12`. GitHub only auto-closes an issue from a commit or PR in the *same*
repository, and that automatic link — issue to fix to commit — is the thing that makes the history
traceable without anyone maintaining it by hand. Centralising every issue in the hub would gain one
tidy list and lose that.

**Cross-repo work is unified by the project board, not by where issues are filed.**

## The board

One GitHub Project spans every mootmaker repository, giving the single view that per-repo issues
otherwise lack.

| Field | Values | For |
|---|---|---|
| Status | Backlog, Ready, In progress, In review, Done | Where the work is |
| Hat | Developer, Product owner, Marketer, Operator, Author | Which [role](../roles/README.md) the work belongs to |
| Size | S, M, L | Rough effort, not an estimate |
| Design | Link | The design document this implements, if any |

Everything open should be on the board. An issue that is not on it is invisible.

Reading and updating the board from the CLI needs the `project` scope, which is **not** included by
default:

```bash
gh auth refresh -s project      # one-off, interactive, opens a browser
gh project list --owner geoffweatherall
```

## What makes a good issue here

Issues are read by humans *and* used as prompts by AI agents — possibly an agent from a different
tool, months later, with no memory of the conversation that produced the issue. That is a higher bar
than "a note to remind myself".

A good issue records:

- **What was observed**, concretely. Real error output, not a paraphrase.
- **What has been ruled out**, and how. This is the part people skip and the part that saves the
  most time later — "checked this, wasn't it" is as valuable as the answer.
- **The working theory**, clearly labelled as a theory rather than a diagnosis.
- **Where to look** — specific files, config, and prior art.
- **Suggested next steps**, ideally with options and a recommendation.

When an issue is resolved, close it with the reasoning and a link to the commit or PR. A closed
issue that only says "fixed" throws away most of its value.

## Labels

The same set exists in every repository, so a filter behaves consistently across the board.

| Label | For |
|---|---|
| `bug` | Something does not work |
| `enhancement` | New capability or improvement |
| `infra` | Infrastructure, deployment, Terraform |
| `docs` | Documentation |
| `flaky-test` | Intermittent test failure — distinct from `bug`, because the triage is different |
| `tech-debt` | Known compromise worth revisiting |
| `hat:developer`, `hat:product`, `hat:marketing`, `hat:operator`, `hat:author` | Which role owns it |
| `blocked` | Waiting on something external |

## Issues versus designs

Not everything needs a design document, and not everything fits in an issue.

**Use an issue** for a bug, a small self-contained improvement, or something noticed in passing that
should not be lost.

**Use a [design](../../designs/README.md)** when the work needs decisions made before it starts,
touches more than one repository, or changes the data model, the process, or a user-visible
behaviour in a way worth thinking through first.

**They compose.** A design's implementation checklist can become issues; an issue that turns out to
be bigger than it looked should spawn a design and link to it. If you are unsure, start with an
issue — promoting it later is cheap, and a design nobody is building rots.
