# mootmaker — the hub repository

This repository holds no deployed code. It is the home for how the mootmaker project is designed,
documented, and worked on.

**If you are here to do work anywhere in mootmaker, start with
[`docs/process/README.md`](docs/process/README.md).** It is the canonical description of how work
happens across every repository, and every other repo's `AGENTS.md` points at it.

## What is where

| Path | What |
|---|---|
| [`docs/process/`](docs/process/) | How work is done: principles, branching and PRs, issues, environments, working with AI |
| [`designs/`](designs/) | One design document per feature or change. [The pattern](designs/README.md) explains the lifecycle |
| [`docs/reference/`](docs/reference/) | What is true today: data model, testing strategy, use cases, business functionality |
| [`docs/development/`](docs/development/) | Getting set up, the cross-repo architecture, environment mechanics |
| [`docs/roles/`](docs/roles/) | The "hats" — which kind of work you are doing, and how a session in each starts |
| [`docs/showcase/`](docs/showcase/) | Learnings, debugging techniques, branding, marketing |
| [`tools/`](tools/) | Link checking, the workstation manifest, the agent installer |

## Working in this repository

**Almost everything here is prose that becomes a source of truth.** That changes what care means:
there is no test suite to catch a wrong statement, and a document that is confidently wrong is worse
than one that is missing. Check claims against the actual code, the actual AWS state, or the actual
git history before writing them down.

**Do not let documents drift.** If you change something in another repository that makes a document
here wrong, fixing it is part of that change.

**Verify links before committing.** Documents here are heavily cross-linked and moves break things
silently:

```bash
python3 tools/check-links.py ..
```

**Design documents have a lifecycle** — `Drafting → Ready → Building → Shipped`. Only Geoff moves a
design to `Ready`. Do not self-promote a design because it looks thorough; see
[`designs/README.md`](designs/README.md).

**Keep the README readable cold.** It is the project's front door for someone deciding whether the
developer is worth talking to. It should stay around 100 lines, lead with substance, and link out
for depth.

## Repository layout expectations

Every mootmaker repository expects the others as **siblings in one directory**. Scripts resolve
paths like `../mootmaker-api`, and the tooling here walks `..` to find every checkout. A nested or
renamed layout will break things in confusing ways.

---

## Project-wide rules

This repository is part of the mootmaker project. The workflow rules that apply everywhere live in
[`docs/process/README.md`](docs/process/README.md) — read it before doing any non-trivial work.

The short version: work of any size starts with a design; bugs start with an issue in the repository
they concern; everything lands via a pull request; a green acceptance run against a real deployment
is the definition of working; and if your change makes a document wrong, fixing it is part of the
change.
