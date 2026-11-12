---
name: context-audit
description: Audit and clean up what Claude Code loads into every session — CLAUDE.md/memory files, skills, agents, slash commands, plugins, MCP servers, hooks — and show how much context each costs per request and how often it was actually used. Use when the user wants to tidy, slim down, check or "aufräumen/bereinigen" their Claude Code setup, asks why sessions start with so much context, or asks what is loaded each session. Audits first, reports, and changes nothing until the user approves each item.
---

# Context audit

Goal: show the user, item by item, what sits in the context of every request, what it costs, whether it is used, and what is safe to remove — then remove only what they approve.

Reply in the user's language. Phases 1–3 are read-only. Never change anything before phase 4.

## Phase 1 — Measure (read-only)

1. **Live breakdown of this session.** If a tool like `mcp__ccd_session_mgmt__get_usage` exists, call it: its `context.categories` give the real token totals (system tools, MCP tools, system prompt, skills, memory files, messages). In the terminal CLI the user can run `/context` for the same breakdown — ask them to paste it if no tool is available. Without either, rely on the estimates from step 2.
2. **Inventory script.** Run:
   ```bash
   python3 -I "<this skill's directory>/scripts/audit.py" --cwd "<project dir or current dir>" --days 90
   ```
   It is stdlib-only and read-only. It prints memory files, skills, agents, commands, plugins, MCP servers (with running process counts), hooks, model/effort settings and clutter, each with a token estimate (~4 chars/token) and real usage counts mined from `~/.claude/projects/**/*.jsonl` transcripts. Use `--no-usage` if the scan is too slow, `--json FILE` (in your scratchpad) for machine-readable output.
3. **MCP tool cost from your own context.** Config files cannot reveal tool schemas. Look at your own tool list: for each MCP server, note whether its tools are loaded up front (full JSON schema in context — expensive) or only deferred (name only — cheap), and whether the server injects an instructions block. Estimate per server and reconcile with the "MCP tools" total from step 1. Servers that appear in transcripts but not in config files are app built-ins, claude.ai connectors or plugin servers; the script lists them under "other MCP servers seen in transcripts". Map opaque ids (a UUID-named server) to their display name from your own context.

## Phase 2 — Classify

For every item decide one of: **keep**, **remove**, **slim**, **fix**, or **not changeable here**. Rules of thumb:

- **remove**: loaded every request AND 0 uses in the window (skills, agents, user/plugin MCP servers, plugins); duplicates; hooks whose output is ignored; clutter (backups, unreferenced hook scripts, empty dirs, plugin trash).
- **slim**: large CLAUDE.md sections about tools that are gone or rarely used; very long skill/agent descriptions (only the description is paid every request — the body costs only when invoked); project rules that duplicate each other.
- **fix**: hooks pointing at missing scripts; MCP servers failing or stuck in needs-auth; contradictions between CLAUDE.md and settings (e.g. CLAUDE.md says one model/effort, `settings.json` or `modelSettings` says another); CLAUDE.md referencing servers, agents or skills that no longer exist; many leftover stdio server processes (count per server from the script).
- **keep**: used regularly, or cheap and plausibly useful.
- **not changeable here**: system tools and the app's built-in servers (e.g. `ccd_*`), managed/org policy settings. Say so instead of proposing a change.

Weigh cost against value: a 40-token skill nobody uses is low priority; a hook that injects text on every Bash call or a 3k-token CLAUDE.md section for an unused tool is high priority. Hooks cost twice: their run time on every matching tool call and their injected output (the script reports total hook-injected tokens in the window).

Who can change what:
- **Local files** (`~/.claude/…`, project `.claude/…`, `CLAUDE.md`, `.mcp.json`, `~/.claude.json`): you, after approval.
- **claude.ai account items** (paths containing `/synced/`, connectors): the user, in the UI — see "UI paths" below.
- **Desktop app toggles** (built-in browser, Claude in Chrome, computer use): the user, in the app settings.

## Phase 3 — Report

Lead with the total: roughly how many tokens every request starts with, and how much of it is removable. Then one table, most expensive first:

| Item | Source | ~Tokens per request | Usage (calls / sessions / last) | Recommendation | How |
|---|---|---|---|---|---|

Notes to include briefly:
- Prompt caching makes repeated context cheaper but it still fills the context window, still counts on the first turn of every session and in every subagent, and still dilutes attention.
- Estimates are ~4 chars/token; the live breakdown from phase 1 is authoritative for totals.
- Separate "you can do this" (local) from "user must click this" (account/app).

End with a short numbered list of the decisions you need, recommendation first. Do not change anything yet.

## Phase 4 — Apply (only what the user approved)

Before each change, look at the exact target. Then:
- **MCP server**: `claude mcp remove <name> -s <user|local|project>` (never hand-edit `~/.claude.json` when the CLI can do it). Verify with `claude mcp get <name>`.
- **settings.json** (hooks, permissions, plugins): edit atomically with a small script that loads JSON, removes only the approved keys/entries and writes back preserving everything else and the file mode; print the result.
- **CLAUDE.md**: cut whole sections by heading; keep generally useful rules that were embedded in a removed section (move them to a fitting section) and say so.
- **Files** (backups, hook scripts, empty dirs): check first whether a copy exists elsewhere (e.g. in a git repo) and mention it; delete only the named files; never follow symlinks out.
- **Processes** of a removed stdio server: list them with parent pid. Leave processes owned by other live sessions alone (they end with those sessions); stop only true orphans (parent pid 1) and only with the user's OK.
- **Never touch**: transcripts/session history (`~/.claude/projects/**/*.jsonl`), credentials, `.env` files, app-managed state (`sessions/`, `session-env/`, `shell-snapshots/`, `file-history/`, caches), other sessions' work.

Afterwards re-run the script, compare before/after (tokens and disk), and tell the user that changes take effect in new sessions.

## UI paths (verify in a browser if one is available — UIs change)

- claude.ai → **Customize / Anpassungen** → **Skills** → **Yours / Meine** → "…" next to a skill → **Remove / Entfernen**. Only skills listed there are removable.
- Same page → **Connectors / Konnektoren** → Yours, and **Plugins** → Yours.
- Built-in document skills (docx, pptx, xlsx, pdf) are tied to Settings → **Capabilities / Funktionen** → code execution & file creation; switching that off also removes file creation in chat — usually keep.
- First-party app servers and connectors without a global switch can still be toggled per session in the desktop app's connector menu.

## Cleanup

Delete any JSON output or temp files you wrote during the audit; leave nothing running.
