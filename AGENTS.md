# mootmaker — the hub repository

This repository holds no deployed code. It is the home for how the mootmaker project is designed,
documented, and worked on.

**If you are here to do work anywhere in mootmaker, start with
[`docs/process/README.md`](docs/process/README.md).** It is the canonical description of how work
happens across every repository, and every other repo's `AGENTS.md` points at it.

## What is where

| Path | What |
|---|---|
| [`docs/overview/`](docs/overview/) | How the system works, as built: one page per topic, starting with [system.md](docs/overview/system.md) |
| [`docs/runbooks/`](docs/runbooks/README.md) | What to do when something is wrong, by symptom |
| [`docs/process/`](docs/process/) | How work is done: principles, branching and PRs, issues, working with AI, Java style |
| [`designs/`](designs/) | One design per feature or change. [The pattern](designs/README.md) explains the lifecycle; [archive/](designs/archive/README.md) holds completed ones |
| [`docs/reference/`](docs/reference/) | Use cases, what the system does, glossary, data model |
| [`docs/development/`](docs/development/) | Getting started and the workstation |
| [`docs/showcase/`](docs/showcase/) | Learnings, talks, branding, marketing. Dated writing, not maintained |
| [`tools/`](tools/) | Link checking, the workstation manifest, the workspace config installer |

[docs/README.md](docs/README.md) lists every document.

## Working in this repository

**Almost everything here is prose that becomes a source of truth.** That changes what care means:
there is no test suite to catch a wrong statement, and a document that is confidently wrong is worse
than one that is missing. Check claims against the actual code, the actual AWS state, or the actual
git history before writing them down.

**Do not let documents drift.** If you change something in another repository that makes a document
here wrong, fixing it is part of that change.

**Write as built, in one place.** Describe the system as it is now, not how it got here: git history,
designs and issues hold the history. Each fact lives in one document; the overviews here explain how
things fit together and link to each component's own README for detail, rather than repeating it. The
same applies to code comments: say what and why, never what used to be.

**Do not edit Geoff's dated writing** beyond fixing links: every design, `docs/showcase/learnings.md`,
`docs/showcase/debugging-techniques.md`, the four `docs/showcase/live-updates-*` documents, and
`docs/process/ai-collaboration.md`.

**Diagrams are Mermaid**, inside the Markdown, so GitHub renders them. Render them before committing:
GitHub shows a parse error in place of a broken diagram. Avoid `#` and `;` in labels, and the words
`end`, `call` and `click` as node ids.

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
