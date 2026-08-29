#!/usr/bin/env bash
# Links the role agent definitions in docs/roles/agents/ into ~/.claude/agents/, so they are
# available from any repository checkout rather than only from this one.
#
# Symlinks rather than copies: editing a definition here takes effect immediately, with no
# re-install step to forget. The canonical copies stay in git, which is the whole point - the
# workspace directory containing the mootmaker checkouts is inside no git repository, so anything
# written to a .claude/ folder there would be unversioned and would not exist on another machine.
#
# Usage:
#   ./tools/install-agents.sh            link them (asks before replacing anything unexpected)
#   ./tools/install-agents.sh --list     show what would be linked, change nothing
#   ./tools/install-agents.sh --force    replace existing files without asking
#   ./tools/install-agents.sh --uninstall  remove only the links this script created
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src_dir="${script_dir}/../docs/roles/agents"
dest_dir="${HOME}/.claude/agents"

if [[ ! -d "${src_dir}" ]]; then
  echo "Cannot find ${src_dir} - run this from the mootmaker checkout." >&2
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

# README.md documents the folder; it is not an agent definition.
mapfile -t definitions < <(find "${src_dir}" -maxdepth 1 -name '*.md' ! -name 'README.md' | sort)

if [[ ${#definitions[@]} -eq 0 ]]; then
  echo "No agent definitions found in ${src_dir}." >&2
  exit 1
fi

if [[ "${mode}" == "list" ]]; then
  echo "Would link into ${dest_dir}:"
  for def in "${definitions[@]}"; do
    echo "  $(basename "${def}")"
  done
  exit 0
fi

mkdir -p "${dest_dir}"

for def in "${definitions[@]}"; do
  name="$(basename "${def}")"
  target="${dest_dir}/${name}"
  src="$(cd "$(dirname "${def}")" && pwd)/${name}"

  if [[ "${mode}" == "uninstall" ]]; then
    # Only remove a symlink that points at our copy - never touch a real file someone wrote.
    if [[ -L "${target}" && "$(readlink -f "${target}")" == "$(readlink -f "${src}")" ]]; then
      rm "${target}"
      echo "removed  ${name}"
    fi
    continue
  fi

  if [[ -e "${target}" || -L "${target}" ]]; then
    if [[ -L "${target}" && "$(readlink -f "${target}")" == "$(readlink -f "${src}")" ]]; then
      echo "ok       ${name} (already linked)"
      continue
    fi
    if [[ "${mode}" != "force" ]]; then
      echo "SKIPPED  ${name} - ${target} exists and is not our link. Re-run with --force to replace it." >&2
      continue
    fi
    rm -f "${target}"
  fi

  ln -s "${src}" "${target}"
  echo "linked   ${name}"
done

if [[ "${mode}" == "uninstall" ]]; then
  echo "Done. Any file that was not one of our symlinks was left alone."
else
  echo "Done. Agents are available from any checkout - try /agents in Claude Code."
fi
