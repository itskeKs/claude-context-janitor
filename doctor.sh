#!/usr/bin/env bash
# Check that this machine can run the audit script and whether installed copies of the skill match
# this checkout. Strictly read-only: creates, changes and deletes nothing. Bash 3.2 compatible.
# The messages quote commands in backticks; none of it is meant to expand.
# shellcheck disable=SC2016
set -euo pipefail

usage() {
    printf '%s\n' 'Usage: doctor.sh [-h|--help]' '' \
        '  Required   python3 3.8 or newer on PATH; a missing item makes the exit status 1' \
        '  Installed  the manual and any plugin install of the skill, compared with this checkout;' \
        '             a difference or a missing copy is a note, never a failure' \
        '' 'Strictly read-only. HOME is honored.'
}

if [[ $# -gt 0 ]]; then
    case "$1" in
        -h | --help) usage; exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
fi

unset CDPATH
case "$0" in
    */*) script_dir=${0%/*} ;;
    *) script_dir=. ;;
esac
src="$(cd "$script_dir" && pwd -P)/plugins/context-janitor/skills/context-janitor"
home=${HOME:?HOME is not set}
required_missing=0

# report STATUS TEXT: one line, the status word padded to 8 columns.
report() { printf '%-8s %s\n' "$1" "$2"; }

# The home directory is written as ~ in the output.
display() {
    local rest
    case "$1" in
        "$home"/*) rest=${1#"$home"}; printf '~%s' "$rest" ;;
        *) printf '%s' "$1" ;;
    esac
}

# check_copy DIR FIX: ok when DIR holds the same SKILL.md and scripts/audit.py as this checkout.
check_copy() {
    if cmp -s "$src/SKILL.md" "$1/SKILL.md" && cmp -s "$src/scripts/audit.py" "$1/scripts/audit.py"; then
        report ok "$(display "$1")"
    else
        report note "$(display "$1") differs from this checkout — reinstall to update: $2"
    fi
}

printf 'Required\n'
py_version=''
if command -v python3 > /dev/null 2>&1; then
    py_version=$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2> /dev/null || true)
fi
if [[ -z "$py_version" ]]; then
    report MISSING 'python3 — not found or not working; install Python 3.8 or newer, for example from python.org or your package manager'
    required_missing=1
elif python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2> /dev/null; then
    report ok "python3 $py_version"
else
    report MISSING "python3 $py_version — too old, the audit script needs 3.8 or newer; install a newer Python and put it first on PATH"
    required_missing=1
fi

printf '\nInstalled copies of the skill\n'
cp_fix="\`cp -R \"$src\" ~/.claude/skills/\`"
plugin_cmd='`/plugin install context-janitor@claude-context-janitor`'
found=0
if [[ -d "$home/.claude/skills/context-janitor" ]]; then
    found=1
    check_copy "$home/.claude/skills/context-janitor" "$cp_fix"
fi
# A plugin install keeps the skill below a marketplace and version directory, so match the tail only.
while IFS= read -r dir; do
    found=1
    check_copy "$dir" "$plugin_cmd (README.md, Install)"
done < <(find -H "$home/.claude/plugins" -maxdepth 8 -type d -path '*/skills/context-janitor' 2> /dev/null | sort)
if [[ "$found" -eq 0 ]]; then
    report note "no installed copy of the skill — see README.md, Install: \`/plugin marketplace add\`, then $plugin_cmd, or run $cp_fix"
fi

printf '\n'
if [[ "$required_missing" -eq 0 ]]; then
    printf 'doctor: ready\n'
else
    printf 'doctor: %d required item(s) missing\n' "$required_missing"
    exit 1
fi
