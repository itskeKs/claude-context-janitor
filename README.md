# claude-context-janitor

A Claude Code skill that checks everything your setup loads into **every** session — `CLAUDE.md` and memory files, skills, agents, slash commands, plugins, MCP servers and hooks. For each item it shows:

- how many tokens it adds to the context of every request,
- how often you actually used it (counted from your local transcripts),
- whether it is worth keeping, and how to remove it.

Phases 1–3 only read. Nothing changes until you approve each item.

## Why

Over time a Claude Code setup piles up skills you never call, MCP servers from old experiments, hooks that add text to every tool call, and `CLAUDE.md` sections about tools you no longer use. Every one of them takes up context on every turn and in every subagent. In a real setup this audit found:

- a hook-driven MCP offload that took ~1.5k tokens per request and nudged the model ~500 times, but was used only 33 times;
- 36 stdio server processes still running for that server;
- a `CLAUDE.md` that disagreed with `settings.json` about model effort.

## Install

As a plugin (recommended):

```
/plugin marketplace add itskeKs/claude-context-janitor
/plugin install context-janitor@claude-context-janitor
```

Or copy the skill by hand:

```bash
git clone https://github.com/itskeKs/claude-context-janitor
cp -R claude-context-janitor/plugins/context-janitor/skills/context-janitor ~/.claude/skills/
```

Start a new session afterwards.

## Use

Ask Claude something like *"audit my Claude Code setup"* or *"what gets loaded every session and what can go?"*. You can also call the skill directly: `/context-janitor` (manual install) or `/context-janitor:context-janitor` (plugin install).

The skill runs in four phases:

1. **Measure.** It reads the live context breakdown when it is available (the `/context` command in the CLI, or the session-usage tool in the desktop app). It also runs the bundled script and checks which MCP servers load full tool schemas and which load names only.
2. **Classify.** Each item gets a verdict: *keep*, *remove*, *slim*, *fix*, or *not changeable here*. The report also says who can change it: Claude for local files, you for your claude.ai account or the app's settings.
3. **Report.** You get the total per-request cost, a table sorted by cost (tokens per request, usage, recommendation, how to remove), and a short list of decisions for you.
4. **Apply, only what you approve.** Claude makes the changes with safe methods: `claude mcp remove`, atomic JSON edits, and a check for copies before anything is deleted. Then it re-runs the audit and compares before and after. It never touches session history, credentials, or processes that belong to other live sessions.

## The script

`plugins/context-janitor/skills/context-janitor/scripts/audit.py` uses only the Python standard library and never changes anything. You can run it on its own:

```bash
python3 -I audit.py --cwd /path/to/project --days 90 [--json out.json] [--no-usage]
```

It checks:

- **Memory:** `~/.claude/CLAUDE.md`, rules, the project's `CLAUDE.md` / `CLAUDE.local.md` up the directory tree, `@imports`, and the head of the auto-memory index.
- **Skills:** user, project, plugin and claude.ai-synced skills. It reports the per-request listing cost (name + description) apart from the cost of the full body, which is paid only when the skill is invoked.
- **Agents and slash commands:** listing cost, plus model and effort.
- **Plugins:** installed ones and those synced from your claude.ai account.
- **MCP servers:** user, local and project `.mcp.json`, plugins, and the Claude Desktop config, with the number of running processes and orphans for each.
- **Hooks:** missing scripts, script size, and the total context hooks injected during the time window.
- **Usage:** calls, sessions and last use for every MCP server, skill and agent, read from `~/.claude/projects/**/*.jsonl`.
- **Clutter:** backup files, hook scripts no settings file references, empty directories, and removed plugin versions.

Token counts are estimates (~4 characters per token). Use the live `/context` breakdown for exact totals. Tool schemas of MCP servers are not stored in any config file, so the skill estimates them from the tools it can see in the live session.

## Requirements

- Claude Code (CLI, desktop app or IDE extension)
- Python 3.8+ on `PATH` as `python3`
- macOS or Linux. On Windows everything except the process count works.

## Renamed from context-audit

This project used to be called `claude-context-audit`. GitHub redirects the old URL. If you installed the old plugin, remove it and install the new one:

```
/plugin uninstall context-audit@claude-context-audit
/plugin marketplace remove claude-context-audit
/plugin marketplace add itskeKs/claude-context-janitor
/plugin install context-janitor@claude-context-janitor
```

## License

MIT
