#!/usr/bin/env python3
"""Rewrite markdown links after the Phase 1 hub reorganisation.

The subtlety this exists to handle: a file that *moved* had its outgoing relative links
written relative to its **old** directory. Naively resolving them against the new location
gives the wrong answer. So every link is resolved against the file's old path, mapped, and
then re-emitted relative to the file's new path.

Handles three link forms:

1. **Relative links inside the hub repo** - resolved against the file's old directory,
   mapped through MOVES, re-emitted relative to the file's new directory.
2. **Absolute GitHub links into the hub repo** - `https://github.com/geoffweatherall/mootmaker/blob/<ref>/<path>`
   and `.../tree/<ref>/<path>`. The path is mapped and the URL re-emitted. These appear in
   every other repo, which is how the sweep reaches them.
3. **Anchor-specific redirects** - links to a `README.md#section` whose *section* moved to a
   different file even though README.md itself did not. Without this, such links resolve to a
   file that still exists and would be silently left pointing at content that is no longer there.

Usage:  tools/rewrite-links.py <workspace-root> [--dry-run]
"""

import os
import re
import sys
from pathlib import Path

HUB = "mootmaker"

# old repo-root-relative path -> new repo-root-relative path.
# Directory entries act as prefixes (branding/x -> docs/showcase/branding/x).
MOVES = {
    "testing-strategy.md": "docs/reference/testing-strategy.md",
    "use-cases.md": "docs/reference/use-cases.md",
    "functionality/business-functionality.md": "docs/reference/business-functionality.md",
    "designs/data-model.md": "docs/reference/data-model.md",
    "debugging-techniques.md": "docs/showcase/debugging-techniques.md",
    "features/features-overview.md": "docs/showcase/features-overview.md",
    "privacy-policy-draft.md": "docs/showcase/privacy-policy-draft.md",
    "branding": "docs/showcase/branding",
    "resources": "docs/showcase/resources",
    "image.png": "docs/showcase/resources/claude-code-session.png",
    "Mootmaker marketing brochure.pdf": "docs/showcase/marketing/Mootmaker marketing brochure.pdf",
    "google-sign-in.md": "designs/archive/google-sign-in.md",
    "google-sign-in-todo.md": "designs/archive/google-sign-in-todo.md",
    "meeting-picker-dropdowns-todo.md": "designs/archive/meeting-picker-dropdowns-todo.md",
    "delete-my-account.md": "designs/archive/delete-my-account.md",
    "delete-my-account-todo.md": "designs/archive/delete-my-account-todo.md",
}

# (old path, anchor) -> "new path#anchor". For sections that moved out of a file that stayed.
ANCHOR_MOVES = {
    ("README.md", "i-should-vibe-more"): "docs/showcase/learnings.md#i-should-vibe-more",
    ("README.md", "impacts-on-the-test-pyramid"): "docs/showcase/learnings.md#impacts-on-the-test-pyramid",
    ("README.md", "multi-environment-deployments"): "docs/development/environments.md#multi-environment-deployments",
    # The To Do section was deleted; its items became GitHub Issues in Phase 3.
    ("README.md", "to-do"): "https://github.com/geoffweatherall/mootmaker/issues",
}

LINK_RE = re.compile(r"(\[[^\]]*\]\()([^)\s]+)((?:\s+\"[^\"]*\")?\))")
GITHUB_RE = re.compile(
    r"^(https://github\.com/geoffweatherall/" + HUB + r")/(blob|tree)/([^/]+)/([^#?]*)(.*)$"
)
SKIP_DIRS = {".git", "node_modules", "target", "dist", "build", ".terraform", "test-results"}

# new path -> old path, so a moved file's links resolve against where they were written.
REVERSE = {v: k for k, v in MOVES.items()}


def map_path(old: str) -> str:
    """Map an old repo-root-relative path through MOVES, honouring directory prefixes."""
    if old in MOVES:
        return MOVES[old]
    for src, dst in MOVES.items():
        if "." not in Path(src).name and old.startswith(src + "/"):
            return dst + old[len(src):]
    return old


def old_path_of(new_rel: str) -> str:
    """Where this file used to live, so its links resolve as originally written."""
    if new_rel in REVERSE:
        return REVERSE[new_rel]
    for new_dir, old_dir in ((v, k) for k, v in MOVES.items() if "." not in Path(k).name):
        if new_rel.startswith(new_dir + "/"):
            return old_dir + new_rel[len(new_dir):]
    return new_rel


def rewrite_target(target: str, file_old_rel: str, file_new_rel: str, in_hub: bool) -> str:
    path_part, sep, anchor = target.partition("#")

    # Form 2: absolute GitHub link into the hub.
    m = GITHUB_RE.match(target)
    if m:
        base, kind, ref, sub, tail = m.groups()
        new_sub = map_path(sub.rstrip("/"))
        if new_sub == sub.rstrip("/"):
            return target
        return f"{base}/{kind}/{ref}/{new_sub}{tail}"

    if target.startswith(("http://", "https://", "mailto:", "tel:")) or not path_part:
        return target
    if not in_hub:
        return target  # relative links in other repos don't point into the hub

    # Resolve against the file's OLD directory.
    old_dir = os.path.dirname(file_old_rel)
    resolved_old = os.path.normpath(os.path.join(old_dir, path_part)) if old_dir else os.path.normpath(path_part)

    # Form 3: an anchor whose section moved out of a file that stayed put.
    if anchor and (resolved_old, anchor) in ANCHOR_MOVES:
        dest = ANCHOR_MOVES[(resolved_old, anchor)]
        if dest.startswith("http"):
            return dest
        dest_path, _, dest_anchor = dest.partition("#")
        rel = os.path.relpath(dest_path, os.path.dirname(file_new_rel) or ".")
        return f"{rel}#{dest_anchor}" if dest_anchor else rel

    # Form 1: ordinary relative link.
    resolved_new = map_path(resolved_old)
    rel = os.path.relpath(resolved_new, os.path.dirname(file_new_rel) or ".")
    # os.path.relpath strips a trailing slash; keep it, since it signals "directory" to a reader.
    if path_part.endswith("/") and not rel.endswith("/"):
        rel += "/"
    return f"{rel}{sep}{anchor}" if sep else rel


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    dry_run = "--dry-run" in sys.argv

    # THIS SCRIPT IS ONE-SHOT AND MUST NOT BE RUN TWICE.
    # For a file that moved, every relative link has to be re-resolved against the file's OLD
    # directory. After a successful run those links are correct for the NEW directory - so a
    # second run resolves already-correct links against the old directory again and walks the
    # "../" prefix one level further out each time. There is no way to distinguish "already
    # migrated" from "not yet migrated" by inspecting a link, so the guard is external.
    marker = Path(__file__).parent / ".links-rewritten"
    if marker.exists() and not dry_run:
        print(
            f"Refusing to run: {marker} exists, so the sweep has already been applied.\n"
            "Re-running would corrupt relative links by re-resolving them against the old\n"
            "directory layout. Delete the marker only if you have reset the tree to the\n"
            "pre-sweep state.",
            file=sys.stderr,
        )
        return 1
    changes = 0
    touched = []

    for repo in sorted(d for d in workspace.iterdir() if d.is_dir() and (d / ".git").exists()):
        in_hub = repo.name == HUB
        for dirpath, dirnames, filenames in os.walk(repo):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if not name.endswith((".md", ".sh")):
                    continue
                f = Path(dirpath) / name
                new_rel = str(f.relative_to(repo))
                old_rel = old_path_of(new_rel) if in_hub else new_rel
                text = f.read_text(encoding="utf-8")

                def sub(m):
                    nonlocal changes
                    pre, target, post = m.groups()
                    new_target = rewrite_target(target, old_rel, new_rel, in_hub)
                    if new_target != target:
                        changes += 1
                    return f"{pre}{new_target}{post}"

                new_text = LINK_RE.sub(sub, text)
                # Bare GitHub URLs outside markdown link syntax (e.g. in shell comments).
                new_text = GITHUB_RE.sub(
                    lambda m: f"{m.group(1)}/{m.group(2)}/{m.group(3)}/{map_path(m.group(4).rstrip('/'))}{m.group(5)}",
                    new_text,
                )
                if new_text != text:
                    touched.append(str(f.relative_to(workspace)))
                    if not dry_run:
                        f.write_text(new_text, encoding="utf-8")

    for t in sorted(set(touched)):
        print(f"  {t}")
    print(f"\n{len(set(touched))} file(s) {'would be ' if dry_run else ''}updated, {changes} link(s) rewritten.")
    if not dry_run:
        marker.write_text(
            "The Phase 1 link sweep has been applied. See the one-shot warning in "
            "rewrite-links.py.\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
