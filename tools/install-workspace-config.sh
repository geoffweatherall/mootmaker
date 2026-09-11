#!/usr/bin/env bash
# Links this repo's versioned workspace configuration into the places the tooling actually reads it
# from, and installs the VS Code extensions that configuration depends on, so a second machine needs
# one command rather than a hand-rebuilt setup.
#
# The problem this solves: the directory holding all the mootmaker checkouts is itself inside no git
# repository, so anything written to its .claude/ folder is unversioned, invisible to review, and
# does not exist on another machine. The canonical copies therefore live here, in the hub repo, and
# are symlinked into place. Same pattern as install-agents.sh, and as the CLAUDE.md -> AGENTS.md
# symlink in every repo.
#
# Symlinks rather than copies: editing the versioned file takes effect immediately, with no
# re-install step to forget and no silent drift between the committed file and the live one.
#
# Usage:
#   ./tools/install-workspace-config.sh            link it (refuses to clobber anything unexpected)
#   ./tools/install-workspace-config.sh --list     show what would be linked, change nothing
#   ./tools/install-workspace-config.sh --force    replace an existing real file
#   ./tools/install-workspace-config.sh --uninstall  remove only the links this script created
#
# Extensions are installed on a plain run, skipped by --list and --uninstall. `code
# --install-extension` is idempotent, so re-running costs a second and changes nothing.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
workspace_root="$(cd "${repo_root}/.." && pwd)"

# source (relative to this repo) -> destination (relative to the workspace directory)
links=(
  "workspace-config/settings.json:.claude/settings.json"
  "workspace-config/vscode-settings.json:.vscode/settings.json"
)

# Extensions the linked VS Code settings depend on. Without the formatter extension, settings.json
# names a default formatter that does not exist and Java files silently stop being formatted.
vscode_extensions=(
  "redhat.java"
  "JoseVSeb.google-java-format-for-vs-code"
)

for entry in "${links[@]}"; do
  if [[ ! -f "${repo_root}/${entry%%:*}" ]]; then
    echo "Cannot find ${repo_root}/${entry%%:*} - run this from the mootmaker checkout." >&2
    exit 1
  fi
done

# Guard against being run somewhere that isn't actually the workspace: the sibling repos should be
# there. Getting this wrong would scatter a .claude/ directory somewhere meaningless.
if [[ ! -d "${workspace_root}/mootmaker-api" ]]; then
  echo "Expected sibling checkouts (e.g. mootmaker-api) in ${workspace_root}." >&2
  echo "This script links config into the workspace directory holding all the mootmaker repos;" >&2
  echo "it looks like this checkout isn't in one. See docs/development/getting-started.md." >&2
  exit 1
fi

mode="install"
case "${1:-}" in
  --list) mode="list" ;;
  --force) mode="force" ;;
  --uninstall) mode="uninstall" ;;
  "") ;;
  *) echo "Unknown option '${1}'. See the comment at the top of this script." >&2; exit 1 ;;
esac

if [[ "${mode}" == "list" ]]; then
  echo "Would link:"
  for entry in "${links[@]}"; do
    echo "  ${workspace_root}/${entry#*:}"
    echo "    -> ${repo_root}/${entry%%:*}"
  done
  echo "Would install VS Code extensions:"
  printf '  %s\n' "${vscode_extensions[@]}"
  exit 0
fi

if [[ "${mode}" == "uninstall" ]]; then
  # Only ever remove a symlink pointing at our own copy - never a real file someone wrote.
  # Extensions are left installed: this script did not create them from nothing and removing
  # them could break other work.
  for entry in "${links[@]}"; do
    src="${repo_root}/${entry%%:*}"
    dest="${workspace_root}/${entry#*:}"
    if [[ -L "${dest}" && "$(readlink -f "${dest}")" == "$(readlink -f "${src}")" ]]; then
      rm "${dest}"
      echo "removed  ${dest}"
    else
      echo "nothing to remove - ${dest} is not our symlink (left alone)."
    fi
  done
  exit 0
fi

for entry in "${links[@]}"; do
  src="${repo_root}/${entry%%:*}"
  dest="${workspace_root}/${entry#*:}"
  mkdir -p "$(dirname "${dest}")"

  if [[ -L "${dest}" && "$(readlink -f "${dest}")" == "$(readlink -f "${src}")" ]]; then
    echo "ok       already linked: ${dest}"
    continue
  fi

  if [[ -e "${dest}" || -L "${dest}" ]]; then
    if [[ "${mode}" != "force" ]]; then
      echo "REFUSING to replace ${dest} - it exists and is not our link." >&2
      echo "Inspect it first; if its contents are worth keeping, fold them into" >&2
      echo "${src} (which is versioned) rather than leaving them only on this machine." >&2
      echo "Then re-run with --force." >&2
      exit 1
    fi
    rm -f "${dest}"
  fi

  ln -s "${src}" "${dest}"
  echo "linked   ${dest}"
  echo "         -> ${src}"
done

# The linked VS Code settings name a formatter extension by id. If it is missing, VS Code reports no
# error - Java files just stop being formatted on save, and the mismatch only shows up when CI
# rejects the push. So installing it is part of installing the settings, not a separate step.
if command -v code >/dev/null 2>&1; then
  echo
  for ext in "${vscode_extensions[@]}"; do
    if code --list-extensions 2>/dev/null | grep -qix "${ext}"; then
      echo "ok       extension present: ${ext}"
    else
      echo "installing extension: ${ext}"
      code --install-extension "${ext}" --force >/dev/null 2>&1 \
        && echo "installed ${ext}" \
        || echo "FAILED to install ${ext} - install it from the Extensions view." >&2
    fi
  done
else
  echo
  echo "NOTE: the 'code' command is not on PATH, so VS Code extensions were not installed." >&2
  echo "      Needed: ${vscode_extensions[*]}" >&2
  echo "      In VS Code: Command Palette -> 'Shell Command: Install code command in PATH'." >&2
fi

echo
echo "Restart Claude Code (or start a new session) for permission changes to take effect."
echo "Note: settings.local.json, if present, still layers on top of this and stays machine-local."
