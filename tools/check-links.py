#!/usr/bin/env python3
"""Check markdown links across every mootmaker repo.

Four things are checked:

1. **Relative links**, resolved against the containing file's directory.
2. **GitHub links into a mootmaker repo at `main`** (`https://github.com/<owner>/<repo>/blob/main/<path>`
   and `.../tree/main/<path>`), resolved against the *sibling checkout* of that repo rather than the
   network, so the check works offline and catches a path that moved locally. Links pinned to a
   commit or tag are permalinks to history and are not checked.
3. **Anchors** (`#section`) on links to markdown files, against the target's headings using
   GitHub's slug rules, plus explicit `<a id="...">` anchors.
4. **Bare-text `<repo>/<path>.md` references in source comments and prose**, such as
   `// mootmaker/docs/reference/use-cases.md, section F` in a `.ts`, `.java`, `.tf` or `.sh` file.
   Limited to `.md` targets: wider matching flags strings that only look like paths, such as the
   Terraform state keys (`<environment>/mootmaker-api/terraform.tfstate`). Archived designs are
   skipped, since they mention old paths as history.

Usage:  tools/check-links.py [workspace-root]
Exit:   0 when every link resolves, 1 when any link is broken.
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# Markdown inline links: [text](target). Also catches image links, which share the syntax.
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
GITHUB_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)"
    r"(?:/(?:blob|tree)/(?P<ref>[^/]+)/(?P<path>[^#?]*))?"
)
CHECKED_REFS = {"main", "HEAD"}
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
EXPLICIT_ANCHOR_RE = re.compile(r'<a (?:id|name)="([^"]+)"')
SKIP_DIRS = {".git", "node_modules", "target", "dist", "build", ".terraform", "test-results"}

# Files that can carry a bare-text doc reference in a comment. Markdown is included too: a
# reference inside a fenced code block or in prose is just as invisible to LINK_RE.
SOURCE_EXTS = {".md", ".sh", ".java", ".ts", ".tsx", ".tf", ".py", ".yml", ".yaml"}

# A bare `<repo>/<path>.md`, optionally written as `../<repo>/...` - the sibling-checkout form
# every AGENTS.md uses, which resolves to the same workspace path.
#
# The lookbehind alternation is what keeps this off URLs and owner-qualified paths while still
# allowing `../`: in `https://github.com/geoffweatherall/mootmaker/blob/main/x.md` the repo name
# is preceded by `/` and not by `../`, so neither branch matches and it never starts a match.
BARE_RE = re.compile(
    r"(?:(?<=\.\./)|(?<![\w./-]))"
    r"(?P<repo>mootmaker(?:-[a-z0-9-]+)?)/(?P<path>[\w./-]+\.md)"
)
URL_RE = re.compile(r"https?://\S+")


_anchor_cache: dict[Path, set[str]] = {}


def anchors_of(md: Path) -> set[str]:
    """The anchors GitHub generates for a markdown file's headings, plus explicit ones."""
    if md in _anchor_cache:
        return _anchor_cache[md]
    found: set[str] = set()
    counts: dict[str, int] = {}
    in_fence = False
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        found.update(EXPLICIT_ANCHOR_RE.findall(line))
        m = HEADING_RE.match(line)
        if not m:
            continue
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(2).strip()).replace("`", "")
        slug = re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")
        n = counts.get(slug, 0)
        counts[slug] = n + 1
        found.add(slug if n == 0 else f"{slug}-{n}")
    _anchor_cache[md] = found
    return found


def missing_anchor(target: Path, anchor: str) -> bool:
    if not anchor or target.suffix != ".md" or not target.is_file():
        return False
    return unquote(anchor) not in anchors_of(target)


def repo_checkouts(workspace: Path) -> dict[str, Path]:
    """Map repo name -> local checkout, for every sibling directory that is a git repo."""
    return {
        d.name: d
        for d in sorted(workspace.iterdir())
        if d.is_dir() and (d / ".git").exists()
    }


def markdown_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".md"):
                yield Path(dirpath) / name


def source_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1] in SOURCE_EXTS:
                yield Path(dirpath) / name


def check_bare_refs(src: Path, repo_root: Path, checkouts: dict[str, Path]) -> list[str]:
    """Find bare-text <repo>/<path>.md references that no longer resolve."""
    problems = []
    if "designs/archive" in src.as_posix():
        return problems
    try:
        text = src.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []  # binary or unreadable: kind 1/2 already reports unreadable markdown

    for lineno, line in enumerate(text.splitlines(), 1):
        # Spans already handled elsewhere, or not path references at all. Reporting a
        # markdown link twice would be worse than not reporting it here.
        masked = [m.span() for m in URL_RE.finditer(line)]
        masked += [m.span() for m in LINK_RE.finditer(line)]

        for m in BARE_RE.finditer(line):
            if any(start <= m.start() < end for start, end in masked):
                continue
            repo = m.group("repo")
            if repo not in checkouts:
                continue
            target = checkouts[repo] / m.group("path")
            if not target.exists():
                rel = f"{repo_root.name}/{src.relative_to(repo_root)}" if repo_root in src.parents else src
                problems.append(
                    f"{rel}:{lineno}: bare-text reference to missing path "
                    f"{repo}/{m.group('path')}"
                )
    return problems


def check_file(md: Path, repo_root: Path, checkouts: dict[str, Path]) -> list[str]:
    problems = []
    try:
        text = md.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return [f"{md}: could not read ({exc})"]
    rel = f"{repo_root.name}/{md.relative_to(repo_root)}" if repo_root in md.parents else md

    for lineno, line in enumerate(text.splitlines(), 1):
        for target in LINK_RE.findall(line):
            path_part, _, anchor = target.partition("#")
            if path_part.startswith(("mailto:", "tel:")):
                continue
            if not path_part:
                if missing_anchor(md, anchor):
                    problems.append(f"{rel}:{lineno}: no heading for anchor #{anchor}")
                continue

            if path_part.startswith("http://") or path_part.startswith("https://"):
                m = GITHUB_RE.match(path_part)
                if not m:
                    continue  # external, not ours to verify
                repo = m.group("repo")
                sub = m.group("path")
                if repo not in checkouts or not sub or m.group("ref") not in CHECKED_REFS:
                    continue  # not ours locally, the repo itself, or a permalink to history
                resolved = checkouts[repo] / unquote(sub)
                if not resolved.exists():
                    problems.append(f"{md}:{lineno}: GitHub link to missing path {repo}/{sub}")
                elif missing_anchor(resolved, anchor):
                    problems.append(f"{md}:{lineno}: no heading for anchor {repo}/{sub}#{anchor}")
                continue

            resolved = (md.parent / unquote(path_part)).resolve()
            if not resolved.exists():
                problems.append(f"{rel}:{lineno}: broken relative link -> {path_part}")
            elif missing_anchor(resolved, anchor):
                problems.append(f"{rel}:{lineno}: no heading for anchor {path_part}#{anchor}")

    return problems


def main() -> int:
    workspace = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    checkouts = repo_checkouts(workspace)
    if not checkouts:
        print(f"No git checkouts found under {workspace}", file=sys.stderr)
        return 1

    all_problems = []
    checked = 0
    scanned = 0
    for name, root in checkouts.items():
        for md in markdown_files(root):
            checked += 1
            all_problems.extend(check_file(md, root, checkouts))
        for src in source_files(root):
            scanned += 1
            all_problems.extend(check_bare_refs(src, root, checkouts))

    for problem in all_problems:
        print(problem)

    print(
        f"\n{checked} markdown files checked across {len(checkouts)} repos "
        f"({scanned} files also scanned for bare-text doc references); "
        f"{len(all_problems)} broken link(s).",
        file=sys.stderr,
    )
    return 1 if all_problems else 0


if __name__ == "__main__":
    sys.exit(main())
