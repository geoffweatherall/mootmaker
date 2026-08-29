# Setting up a machine

Development targets **Ubuntu**. Nothing here is tested on macOS or Windows.

## Check what you have

```bash
mootmaker/tools/workstation/check.sh
```

Reports every prerequisite as present or missing, with the command to install each missing one. It
exits non-zero only when something **required** is missing, so it can gate a script; optional tools
are reported but do not fail the check.

```bash
tools/workstation/check.sh --required   # skip optional tools
tools/workstation/check.sh --install    # just print the install commands
```

## How it works

[`tools/workstation/manifest.yaml`](../../tools/workstation/manifest.yaml) is the list. Each entry
records what a tool is, **why mootmaker needs it**, a cheap command that proves it is present, how
to install it on Ubuntu, and any non-obvious notes. `check.sh` reads that file — it has no built-in
knowledge of the toolchain.

The "why" field matters more than it looks. It lets a reader judge whether they need a given tool
for the task in front of them, rather than installing everything on principle.

## The rule

**If you install something during a session that future work will need, add it to the manifest as
part of that session's work.** Not as a follow-up — it will not happen.

This applies to AI agents as much as to people. An agent that hits a missing tool, installs it, and
moves on has fixed the symptom on one machine and left the next machine to rediscover it.

## Workspace configuration (the second machine problem)

Claude Code permission rules for this workspace are **versioned** in
[`workspace-config/settings.json`](../../workspace-config/settings.json) and symlinked into the
workspace root:

```bash
mootmaker/tools/install-workspace-config.sh          # link it
mootmaker/tools/install-workspace-config.sh --list   # show what it would do
```

**Why a symlink rather than just a file in the right place:** the directory holding all the
mootmaker checkouts is itself inside no git repository, so anything written to its `.claude/`
folder is unversioned, invisible to review, and does not exist on your other machine. Keeping the
real file in this repo and linking to it means one source of truth, and edits take effect
immediately with no re-install step to forget. Same pattern as
[`install-agents.sh`](../../tools/install-agents.sh) and the `CLAUDE.md` → `AGENTS.md` symlink in
every repo.

`check.sh` verifies the link exists, so a machine that has not run this is *told* rather than
silently behaving differently — which is exactly how this problem was found in the first place
(mysterious permission prompts on one machine and not the other).

**What lives where**, deliberately:

| File | Scope | Versioned? |
|---|---|---|
| `mootmaker/workspace-config/settings.json` | mootmaker permission rules, including `production` deploy guards | **Yes** — this repo |
| `~/.claude/settings.json` | Genuinely global: destructive-git guards that should apply to *every* project, your model and notification preferences, `additionalDirectories` | No — machine-local by nature |
| `<workspace>/.claude/settings.local.json` | Anything you want on this machine only | No — gitignored by Claude Code convention |

Note that a rule in the global `ask` list still overrides a project-scoped `allow`. That is
deliberate and load-bearing: it is what lets the universal git guards apply everywhere while
mootmaker's own config stays permissive for routine work.

**Never put a credential in any of these files.** Claude Code records approved one-off commands
verbatim, so an approved `curl ... -H 'x-api-key: ...'` becomes a permanent, plaintext rule. Two
such rules (a dead AppSync key and a test-account password) were found and removed on 2026-08-29 —
before the file was versioned into a **public** repo, which would have published them.

## What it cannot check

**Authentication.** A tool being installed says nothing about being logged in. Two that bite:

- `aws sso login` — SSO tokens expire during long sessions. Re-run it.
- `gh auth login`, plus `gh auth refresh -s project` for the project board. `check.sh` does flag a
  `gh` that is installed but unauthenticated, or authenticated without the `project` scope, because
  that gap is invisible to a presence check and only surfaces later as a confusing failure.

**Versions.** The check proves a tool exists, not that it is new enough. Where a minimum matters —
Java must be 25 or later, Node 20 or later — it is recorded in the manifest's notes, and the
installed version is printed next to each `ok` so a mismatch is at least visible.

**Sudo.** An AI agent cannot install anything: `sudo` needs an interactive password it has no way to
supply. So the agent's job is to *tell you precisely what to run*, which is what `--install` is for.
