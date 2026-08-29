#!/usr/bin/env bash
# Reports which mootmaker prerequisites are installed on this machine, and how to install the ones
# that are not. Reads manifest.yaml - see the rule at the top of that file about keeping it current.
#
# Usage:
#   ./tools/workstation/check.sh              check everything
#   ./tools/workstation/check.sh --required   skip tools marked optional
#   ./tools/workstation/check.sh --install    print a single command that installs everything missing
#
# Exit status: 0 when nothing required is missing, 1 otherwise - so it can gate a script.
set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
manifest="${script_dir}/manifest.yaml"

if [[ ! -f "${manifest}" ]]; then
  echo "Cannot find ${manifest}" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is needed to read the manifest: sudo apt install -y python3" >&2
  exit 1
fi
if ! python3 -c "import yaml" >/dev/null 2>&1; then
  echo "PyYAML is needed to read the manifest: sudo apt install -y python3-yaml" >&2
  exit 1
fi

mode="check"
case "${1:-}" in
  --required) mode="required" ;;
  --install) mode="install" ;;
  "") ;;
  *) echo "Unknown option '${1}'. See the comment at the top of this script." >&2; exit 1 ;;
esac

# Emit one record per tool, unit-separator delimited, so bash can loop over it without parsing
# YAML itself. NOT tab-separated: bash treats tab as whitespace in IFS, so consecutive tabs collapse
# into one and an empty field silently shifts every later column left. That bug caused a tool's
# install command to land in the version column and then be evaluated - which actually installed
# software during what was meant to be a read-only check.
records="$(python3 - "${manifest}" <<'PY'
import sys, yaml
with open(sys.argv[1]) as fh:
    data = yaml.safe_load(fh)
for tool in data.get("tools", []):
    fields = [
        tool.get("name", ""),
        " ".join((tool.get("check") or "").split()),
        " ".join((tool.get("version") or "").split()),
        " ".join((tool.get("install") or "").split()),
        "yes" if tool.get("optional") else "no",
        " ".join((tool.get("notes") or "").split()),
    ]
    print("\x1f".join(f.replace("\x1f", " ") for f in fields))
PY
)" || { echo "Failed to read ${manifest}" >&2; exit 1; }

missing_required=0
missing_any=0
declare -a install_cmds=()

if [[ "${mode}" != "install" ]]; then
  printf '%-22s %s\n' "TOOL" "STATUS"
  printf '%-22s %s\n' "----" "------"
fi

while IFS=$'\x1f' read -r name check version install optional notes; do
  [[ -z "${name}" ]] && continue
  if [[ "${mode}" == "required" && "${optional}" == "yes" ]]; then
    continue
  fi

  if eval "${check}" >/dev/null 2>&1; then
    if [[ "${mode}" == "install" ]]; then
      continue
    fi
    detail=""
    if [[ -n "${version}" ]]; then
      detail="$(eval "${version}" 2>&1 | head -1 | sed 's/\x1b\[[0-9;]*m//g')"
    fi
    printf '%-22s ok        %s\n' "${name}" "${detail}"
  else
    missing_any=1
    install_cmds+=("${install}")
    if [[ "${optional}" == "yes" ]]; then
      if [[ "${mode}" != "install" ]]; then
        printf '%-22s MISSING   (optional) %s\n' "${name}" "${install}"
      fi
    else
      missing_required=1
      if [[ "${mode}" != "install" ]]; then
        printf '%-22s MISSING   %s\n' "${name}" "${install}"
      fi
    fi
    if [[ -n "${notes}" && "${mode}" != "install" ]]; then
      printf '%-22s           note: %s\n' "" "${notes}"
    fi
  fi
done <<< "${records}"

if [[ "${mode}" == "install" ]]; then
  if [[ ${#install_cmds[@]} -eq 0 ]]; then
    echo "# Nothing missing."
  else
    echo "# Run these to install what is missing:"
    printf '%s\n' "${install_cmds[@]}"
  fi
  exit 0
fi

echo
if [[ ${missing_required} -eq 0 && ${missing_any} -eq 0 ]]; then
  echo "Everything in the manifest is installed."
elif [[ ${missing_required} -eq 0 ]]; then
  echo "Everything required is installed; some optional tools are missing (see above)."
else
  echo "Some required tools are missing. Run with --install to get the commands."
fi

# gh's project scope is a common gap that a presence check cannot catch - the binary is installed
# and authenticated, but the board is still unreachable. Worth surfacing here rather than letting
# it fail later in Phase 3 work.
if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    if ! gh auth status 2>&1 | grep -q "project"; then
      echo
      echo "gh is authenticated but lacks the 'project' scope, so the project board is unreachable."
      echo "  Fix: gh auth refresh -s project"
    fi
  else
    echo
    echo "gh is installed but not authenticated. Fix: gh auth login"
  fi
fi

exit "${missing_required}"
