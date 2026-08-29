# Agent definitions

One agent definition per [hat](../README.md). They are plain markdown with YAML frontmatter — the
frontmatter is Claude Code's format, and the body is the instructions, which any tool can use.

## Why they live here rather than in the tool's config

Claude Code reads subagents from `.claude/agents/` in the project directory or `~/.claude/agents/`
at user level. The natural project directory for this workspace is the folder containing all the
mootmaker checkouts — which **is not inside any git repository**. Anything written there is
unversioned, invisible to review, and does not exist on another machine.

So the canonical copies live here, in git, and are installed by symlink:

```bash
tools/install-agents.sh          # link into ~/.claude/agents/
tools/install-agents.sh --list   # show what would be linked
```

`~/.claude/agents/` is user-level, so they are available from any repository checkout, not just this
one. Symlinks rather than copies means editing the file here takes effect immediately, with no
re-install step to forget.

For a tool that is not Claude Code, point it at the body of the relevant file. Nothing in the
instructions depends on Claude Code specifically.
