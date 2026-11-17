# Agent notes for claude-context-janitor

This repository is a Claude Code plugin marketplace with one plugin, `context-janitor`: a skill that
audits what Claude Code loads into every session, and the read-only script it runs. This file is the
contract for every agent and human working in this checkout. It holds the rules and says where to
read; the detail lives in the files it names.

## Rules (read first)

1. **The audit changes nothing.** `audit.py` reads files and runs `ps`. Its only write is the file
   named by `--json`. Code added to it never writes, deletes or kills.
2. **Nothing is changed before approval.** Phases 1 to 3 of the skill only read; phase 4 touches only
   what the user approved, item by item. A change to `SKILL.md` must not weaken that.
3. **An existing install is the owner's.** If `~/.claude/skills/context-janitor` already exists,
   report it and ask before replacing it.
4. **Standard library only, Python 3.8 or newer,** run as `python3 -I`. No syntax or stdlib API
   newer than 3.8.
5. **One name, one version.** Plugin name, version and description are stated in
   `.claude-plugin/marketplace.json` and in `plugins/context-janitor/.claude-plugin/plugin.json`;
   they change together, and a release bumps the version in both. The skill directory, the `name`
   in the `SKILL.md` frontmatter and the plugin name are the same word.
6. **The frontmatter description is loaded into every request of every user.** Keep it short.
7. **Nothing from a real machine is committed:** no audit output, transcripts, settings, paths or
   server names. Examples are anonymized.
8. **English in all files, commits, issues and pull requests.** The skill itself replies in the
   user's language.
9. **Green before commit:** `make check`.
10. **Clean up after yourself:** temp files (also `--json` output) and processes you started are
    gone before you hand over.

## Which job are you here for?

### A. Installing or using the skill

Two install forms, both in [README.md](README.md#install): the plugin (slash commands the owner
types in a Claude Code session) or a copy of the skill directory into `~/.claude/skills/`. Run
`make doctor` first; it is read-only and says whether Python is fit and whether an installed copy
exists and differs from this checkout. Run the copy form only when no copy exists or the owner said
to replace it (rule 3), then tell the owner to start a new session. The skill then does the audit,
and [SKILL.md](plugins/context-janitor/skills/context-janitor/SKILL.md) is the procedure: follow its
phases in order and ask before phase 4.

### B. Changing the plugin

- **`audit.py`:** rules 1 and 4. Test a change with a throw-away `HOME` and an empty `--cwd`, never
  against the real `~/.claude`.
- **`SKILL.md`:** rules 2, 5 and 6. When the script gains or loses an option or a check, update the
  skill text and the README section "The script" to match.
- **Manifests:** rule 5. `make check` compares them.
- **README:** keep it the short description of the current state; do not rewrite sections you were
  not asked to change.
- **Installed copies are separate.** A copy made by `cp -R` or by `/plugin install` does not follow
  this checkout; a change reaches it only after a reinstall or plugin update.
- **Scope.** Change what was asked; name what you noticed instead of fixing it in passing.

## Where to read

| When you | Read |
| --- | --- |
| run the audit | [SKILL.md](plugins/context-janitor/skills/context-janitor/SKILL.md): phase 1 measure, 2 classify, 3 report, 4 apply |
| need the script's options | `python3 -I plugins/context-janitor/skills/context-janitor/scripts/audit.py --help` |
| need the install forms, what the audit covers, the requirements | [README.md](README.md) |
| change name, version or description | [marketplace.json](.claude-plugin/marketplace.json) and [plugin.json](plugins/context-janitor/.claude-plugin/plugin.json) |

## Commands

```bash
make help     # list the targets
make doctor   # read-only: python3 3.8+, installed copies of the skill compared with this checkout
make check    # manifests, SKILL.md frontmatter, audit.py smoke run in a temp HOME, doctor.sh smoke run
```

## Agent host integrations

Claude Code reads `CLAUDE.md`, which is a symlink to this file. Codex, Cursor and other tools that
know `AGENTS.md` read this file directly. Keep the substance here; never turn `CLAUDE.md` into a copy.

The working copy of the skill is linked into this checkout: `.claude/skills/context-janitor` is a
relative symlink to `plugins/context-janitor/skills/context-janitor`, so a session opened here can
invoke it. A copy installed under the same name elsewhere may answer instead; check the skill
directory it ran from (`SKILL.md` calls it `<this skill's directory>`). Edit the files under
`plugins/`, never replace the link with a copy.
