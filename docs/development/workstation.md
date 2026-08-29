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
