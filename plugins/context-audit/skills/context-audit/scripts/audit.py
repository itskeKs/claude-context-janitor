#!/usr/bin/env python3
"""Read-only audit of everything Claude Code loads into a session.

Inventories memory files, skills, agents, commands, plugins, MCP servers and
hooks; estimates how many tokens each puts into the context of EVERY request;
counts how often each was actually used in recent transcripts; flags clutter.
Never writes, deletes or kills anything. Stdlib only.

Usage: python3 -I audit.py [--cwd DIR] [--days N] [--json OUT] [--no-usage]
"""
import argparse, glob, json, os, re, subprocess, sys, time
from collections import Counter, defaultdict
from pathlib import Path

HOME = Path.home()
CLAUDE = HOME / ".claude"


def tok(chars):  # rough: ~4 chars per token (prose/code mix)
    return int(round(chars / 4.0))


def read(p):
    try:
        return Path(p).read_text(errors="ignore")
    except Exception:
        return ""


def load_json(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def frontmatter(text):
    """Minimal YAML frontmatter reader: top-level scalar keys, incl. > and | blocks."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    if not m:
        return {}
    out, key, block = {}, None, []
    for line in m.group(1).splitlines():
        top = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top and not line.startswith(" "):
            if key and block:
                out[key] = " ".join(s.strip() for s in block).strip()
            key, val, block = top.group(1), top.group(2).strip(), []
            if val in (">", "|", ">-", "|-", ""):
                continue
            out[key] = val.strip("'\"")
            key = None
        elif key is not None:
            block.append(line)
    if key and block:
        out[key] = " ".join(s.strip() for s in block).strip()
    return out


def rel(p):
    s = str(p)
    return "~" + s[len(str(HOME)):] if s.startswith(str(HOME)) else s


# ---------------------------------------------------------------- memory
def memory_files(cwd):
    found, seen = [], set()

    def add(p, kind):
        p = Path(p)
        if p.is_file() and p.resolve() not in seen:
            seen.add(p.resolve())
            t = read(p)
            found.append({"path": rel(p), "kind": kind, "chars": len(t), "tokens": tok(len(t))})
            for imp in re.findall(r"(?:^|\s)@((?:~|\.{1,2})?/?[\w.\-/]+\.md)\b", t):
                ip = Path(os.path.expanduser(imp))
                if not ip.is_absolute():
                    ip = p.parent / ip
                add(ip, "import from " + p.name)

    add(CLAUDE / "CLAUDE.md", "user")
    for r in sorted(glob.glob(str(CLAUDE / "rules" / "**" / "*.md"), recursive=True)):
        add(r, "user rule")
    d = Path(cwd).resolve()
    chain = [d] + list(d.parents)
    for c in reversed(chain):
        if c == HOME.parent or len(c.parts) <= 1:
            continue
        for name in ("CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md"):
            add(c / name, "project" if c != HOME else "home")
        for r in sorted(glob.glob(str(c / ".claude" / "rules" / "**" / "*.md"), recursive=True)):
            add(r, "project rule")
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(d))
    mem = CLAUDE / "projects" / slug / "memory" / "MEMORY.md"
    if mem.is_file():
        lines = read(mem).splitlines()[:200]  # only the head of the index is auto-loaded
        t = "\n".join(lines)
        found.append({"path": rel(mem), "kind": "auto-memory index", "chars": len(t), "tokens": tok(len(t))})
    return found


# ---------------------------------------------------------------- plugins
def plugins():
    res = []
    inst = load_json(CLAUDE / "plugins" / "installed_plugins.json") or {}
    entries = inst.get("plugins", {}) if isinstance(inst, dict) else {}
    enabled = {}
    for sp in settings_paths(None):
        s = load_json(sp) or {}
        enabled.update(s.get("enabledPlugins") or {})
    for name, val in entries.items():
        for e in (val if isinstance(val, list) else [val]):
            if isinstance(e, dict) and e.get("installPath"):
                res.append({"name": name, "path": e["installPath"], "source": "installed",
                            "enabled": enabled.get(name, True), "scope": e.get("scope", "user")})
    for man in glob.glob(str(CLAUDE / "plugins" / "synced" / "*" / "manifest.json")):
        m = load_json(man) or {}
        for p in m.get("plugins", []):
            n = p.get("name")
            cand = [d for d in glob.glob(str(Path(man).parent / (n + "*"))) if os.path.isdir(d)]
            res.append({"name": n, "path": cand[0] if cand else None, "source": "claude.ai account (synced)",
                        "enabled": p.get("installationPreference") != "disabled",
                        "preference": p.get("installationPreference")})
    return res


def settings_paths(cwd):
    ps = [CLAUDE / "settings.json", CLAUDE / "settings.local.json"]
    if cwd:
        for c in [Path(cwd).resolve()] + list(Path(cwd).resolve().parents):
            if c == HOME:
                break
            ps += [c / ".claude" / "settings.json", c / ".claude" / "settings.local.json"]
    for m in ("/Library/Application Support/ClaudeCode/managed-settings.json", "/etc/claude-code/managed-settings.json"):
        ps.append(Path(m))
    return [p for p in ps if p.is_file()]


# ---------------------------------------------------------------- skills / agents / commands
def skills(cwd, plugs):
    out = []

    def scan(root, source, prefix=""):
        for sk in sorted(glob.glob(str(Path(root) / "**" / "SKILL.md"), recursive=True)):
            if "/.trash/" in sk or "/node_modules/" in sk:
                continue
            fm = frontmatter(read(sk))
            name = fm.get("name") or Path(sk).parent.name
            desc = fm.get("description", "")
            body = len(read(sk))
            src = source
            if "/synced/" in sk:
                src = "claude.ai account (synced)"
            out.append({"name": prefix + name, "source": src, "path": rel(Path(sk).parent),
                        "listing_tokens": tok(len(name) + len(desc) + 4), "body_tokens_on_use": tok(body)})

    scan(CLAUDE / "skills", "user")
    for c in [Path(cwd).resolve()] + list(Path(cwd).resolve().parents):
        if c == HOME:  # ~/.claude/skills was scanned above as "user"
            break
        if (c / ".claude" / "skills").is_dir():
            scan(c / ".claude" / "skills", "project " + rel(c))
    for p in plugs:
        if p["path"] and p["enabled"] and p.get("source") == "installed":
            scan(p["path"], "plugin " + p["name"], p["name"].split("@")[0] + ":")
    # synced plugins are only listed when the account marks them installed; report them separately
    return out


def md_defs(dirs, kind):
    out = []
    for d, source in dirs:
        for f in sorted(glob.glob(str(Path(d) / "**" / "*.md"), recursive=True)):
            fm = frontmatter(read(f))
            if kind == "agent" and "description" not in fm:
                continue
            name = fm.get("name") or Path(f).stem
            desc = fm.get("description", "")
            out.append({"name": name, "source": source, "path": rel(f), "model": fm.get("model"),
                        "effort": fm.get("effort"), "listing_tokens": tok(len(name) + len(desc) + 4)})
    return out


# ---------------------------------------------------------------- MCP
def mcp_servers(cwd, plugs):
    out = []
    cj = load_json(HOME / ".claude.json") or {}
    for n, c in (cj.get("mcpServers") or {}).items():
        out.append(dict(name=n, scope="user (~/.claude.json)", **_mcp_desc(c)))
    projects = cj.get("projects") or {}
    cur = projects.get(str(Path(cwd).resolve())) or {}
    for n, c in (cur.get("mcpServers") or {}).items():
        out.append(dict(name=n, scope="local (this project)", **_mcp_desc(c)))
    other = {p: list((v.get("mcpServers") or {}).keys()) for p, v in projects.items()
             if v.get("mcpServers") and p != str(Path(cwd).resolve())}
    disabled = set(cur.get("disabledMcpjsonServers") or [])
    for c in [Path(cwd).resolve()] + list(Path(cwd).resolve().parents):
        mj = load_json(c / ".mcp.json")
        if mj:
            for n, cfg in (mj.get("mcpServers") or {}).items():
                out.append(dict(name=n, scope="project " + rel(c / ".mcp.json") + (" [disabled]" if n in disabled else ""), **_mcp_desc(cfg)))
        if c == HOME:
            break
    for p in plugs:
        if not p["path"] or not p["enabled"]:
            continue
        if p.get("source") != "installed" and p.get("preference") != "installed":
            continue
        mj = load_json(Path(p["path"]) / ".mcp.json") or {}
        for n, cfg in (mj.get("mcpServers") or mj).items():
            if isinstance(cfg, dict):
                out.append(dict(name=n, scope="plugin " + p["name"], **_mcp_desc(cfg)))
    for dc in (HOME / "Library/Application Support/Claude/claude_desktop_config.json",
               HOME / ".config/Claude/claude_desktop_config.json",
               Path(os.environ.get("APPDATA", "/nonexistent")) / "Claude" / "claude_desktop_config.json"):
        d = load_json(dc) or {}
        for n, cfg in (d.get("mcpServers") or {}).items():
            out.append(dict(name=n, scope="Claude Desktop chat config", **_mcp_desc(cfg)))
    return out, other


def _mcp_desc(c):
    t = c.get("type") or ("http" if c.get("url") else "stdio")
    target = c.get("url") or " ".join([c.get("command", "")] + list(c.get("args") or []))
    return {"transport": t, "target": target.strip()}


def mcp_processes(servers):
    try:
        ps = subprocess.run(["ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return {}
    res = {}
    for s in servers:
        if s["transport"] != "stdio" or not s["target"]:
            continue
        parts = s["target"].split()
        needle = next((a for a in reversed(parts) if "/" in a or "." in a), parts[0])
        rows = [l.split(None, 2) for l in ps.splitlines() if needle in l and "audit.py" not in l]
        if rows:
            res[s["name"]] = {"processes": len(rows), "orphans": sum(1 for r in rows if r[1] == "1")}
    return res


# ---------------------------------------------------------------- hooks / settings
def hooks_and_settings(cwd):
    hooks, notes = [], []
    for sp in settings_paths(cwd):
        s = load_json(sp) or {}
        for ev, groups in (s.get("hooks") or {}).items():
            for g in groups or []:
                for h in g.get("hooks", []):
                    cmd = h.get("command", "")
                    scripts = [w for w in cmd.split() if "/" in w and not w.startswith("/usr/bin") and not w.startswith("/bin")]
                    missing = [w for w in scripts if not Path(os.path.expanduser(w)).exists()]
                    hooks.append({"settings": rel(sp), "event": ev, "matcher": g.get("matcher", "*"),
                                  "command": cmd, "missing_scripts": missing,
                                  "script_kb": round(sum(Path(os.path.expanduser(w)).stat().st_size for w in scripts if Path(os.path.expanduser(w)).is_file()) / 1024, 1)})
        for k in ("model", "effortLevel", "modelSettings", "outputStyle", "enabledPlugins", "env"):
            if k in s:
                notes.append({"settings": rel(sp), "key": k, "value": s[k]})
    return hooks, notes


# ---------------------------------------------------------------- usage from transcripts
def usage(days):
    root = CLAUDE / "projects"
    cutoff = time.time() - days * 86400
    calls, sessions, last = Counter(), defaultdict(set), {}
    hook_ctx_n, hook_ctx_chars, nfiles, hook_last = 0, 0, 0, ""
    for f in glob.glob(str(root / "**" / "*.jsonl"), recursive=True):
        try:
            if os.path.getmtime(f) < cutoff:
                continue
            fh = open(f, errors="ignore")
        except Exception:
            continue
        nfiles += 1
        with fh:
            for line in fh:
                if '"hook_additional_context"' in line:
                    try:
                        dd = json.loads(line)
                        a = dd.get("attachment") or {}
                        if a.get("type") == "hook_additional_context":
                            hook_last = max(hook_last, dd.get("timestamp", "")[:10])
                            hook_ctx_n += 1
                            hook_ctx_chars += len(json.dumps(a.get("content", "")))
                    except Exception:
                        pass
                    continue
                if '"tool_use"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                content = (d.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for b in content:
                    if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                        continue
                    n, inp = b.get("name", ""), b.get("input") or {}
                    if n.startswith("mcp__"):
                        key = "mcp:" + n.split("__")[1]
                    elif n == "Skill":
                        key = "skill:" + str(inp.get("skill") or inp.get("command"))
                    elif n in ("Agent", "Task"):
                        key = "agent:" + str(inp.get("subagent_type") or "general-purpose")
                    elif n.startswith("SlashCommand"):
                        key = "command:" + str(inp.get("command"))
                    else:
                        continue
                    calls[key] += 1
                    sessions[key].add(f)
                    ts = d.get("timestamp", "")
                    if ts > last.get(key, ""):
                        last[key] = ts
    return {"files": nfiles, "days": days,
            "items": {k: {"calls": v, "sessions": len(sessions[k]), "last": last.get(k, "")[:10]} for k, v in calls.most_common()},
            "hook_context": {"injections": hook_ctx_n, "tokens_total": tok(hook_ctx_chars), "last": hook_last}}


# ---------------------------------------------------------------- clutter
APP_DIRS = {"projects", "sessions", "session-env", "spares", "telemetry", "todos", "statsig", "shell-snapshots",
            "file-history", "plans", "ide", "debug", "cache", "backups", "uploads", "chrome", "scheduled-tasks",
            "plugins", "skills", "agents", "commands", "hooks", "rules", "output-styles", "downloads"}


def clutter(hooks):
    out = []
    pats = ["*.bak", "*.bak-*", "*.bak.*", "*.orig", "*~", "*.old"]
    for d in (CLAUDE, CLAUDE / "agents", CLAUDE / "skills", CLAUDE / "hooks", CLAUDE / "commands"):
        for p in pats:
            for f in glob.glob(str(d / p)):
                out.append({"path": rel(f), "why": "backup copy", "kb": round(os.path.getsize(f) / 1024, 1)})
    referenced = " ".join(h["command"] for h in hooks)
    for f in glob.glob(str(CLAUDE / "hooks" / "*")):
        if os.path.isfile(f) and Path(f).name not in referenced and not f.endswith((".bak",)):
            out.append({"path": rel(f), "why": "hook script not referenced by any settings file", "kb": round(os.path.getsize(f) / 1024, 1)})
    for d in sorted(CLAUDE.iterdir()) if CLAUDE.is_dir() else []:
        if d.is_dir() and not d.is_symlink() and not any(d.iterdir()) and d.name not in APP_DIRS:
            out.append({"path": rel(d), "why": "empty directory (the app may recreate it)", "kb": 0})
    trash = CLAUDE / "plugins" / ".trash"
    if trash.is_dir() and any(trash.iterdir()):
        size = sum(f.stat().st_size for f in trash.rglob("*") if f.is_file() and not f.is_symlink())
        out.append({"path": rel(trash), "why": "removed plugin versions", "kb": round(size / 1024, 1)})
    return out


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--json")
    ap.add_argument("--no-usage", action="store_true")
    a = ap.parse_args()

    plugs = plugins()
    mem = memory_files(a.cwd)
    sk = skills(a.cwd, plugs)
    agent_dirs = [(CLAUDE / "agents", "user")] + [(Path(a.cwd) / ".claude" / "agents", "project")]
    agents = md_defs([d for d in agent_dirs if Path(d[0]).is_dir()], "agent")
    cmd_dirs = [(CLAUDE / "commands", "user"), (Path(a.cwd) / ".claude" / "commands", "project")]
    cmds = md_defs([d for d in cmd_dirs if Path(d[0]).is_dir()], "command")
    servers, other_proj = mcp_servers(a.cwd, plugs)
    procs = mcp_processes(servers)
    hooks, notes = hooks_and_settings(a.cwd)
    use = None if a.no_usage else usage(a.days)
    junk = clutter(hooks)

    rep = {"cwd": a.cwd, "memory": mem, "skills": sk, "agents": agents, "commands": cmds,
           "plugins": plugs, "mcp_servers": servers, "mcp_processes": procs,
           "mcp_other_projects": other_proj, "hooks": hooks, "settings": notes,
           "usage": use, "clutter": junk}
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1, default=str))

    U = (use or {}).get("items", {})

    def u(key):
        x = U.get(key)
        if not x and key.startswith("skill:"):  # plugin/account skills are invoked as "<plugin>:<name>"
            hits = [v for k, v in U.items() if k.startswith("skill:") and k.endswith(":" + key[6:])]
            if hits:
                x = {"calls": sum(h["calls"] for h in hits), "sessions": sum(h["sessions"] for h in hits),
                     "last": max(h["last"] for h in hits)}
        return f"{x['calls']} calls / {x['sessions']} sess / last {x['last']}" if x else "0 calls"

    P = print
    P(f"# Context audit — cwd {rel(a.cwd)}")
    if use:
        P(f"Usage window: last {use['days']} days, {use['files']} transcripts scanned.\n")
    P("Token figures are estimates (~4 chars/token). 'Per request' = sits in the context of every turn.\n")

    tot_mem = sum(m["tokens"] for m in mem)
    P(f"## Memory files (always loaded) — ~{tot_mem} tok")
    for m in mem:
        P(f"- {m['path']} [{m['kind']}] ~{m['tokens']} tok")

    tot_sk = sum(s["listing_tokens"] for s in sk)
    P(f"\n## Skills (name+description listed every request) — ~{tot_sk} tok")
    for s in sorted(sk, key=lambda s: -s["listing_tokens"]):
        P(f"- {s['name']} [{s['source']}] ~{s['listing_tokens']} tok listing, ~{s['body_tokens_on_use']} tok when invoked — usage: {u('skill:' + s['name'])}")

    if agents:
        P(f"\n## Agents (descriptions listed every request) — ~{sum(x['listing_tokens'] for x in agents)} tok")
        for x in agents:
            P(f"- {x['name']} [{x['source']}] model={x['model']} effort={x['effort']} ~{x['listing_tokens']} tok — usage: {u('agent:' + x['name'])}")
    if cmds:
        P(f"\n## Slash commands — ~{sum(x['listing_tokens'] for x in cmds)} tok")
        for x in cmds:
            P(f"- /{x['name']} [{x['source']}] ~{x['listing_tokens']} tok")

    P("\n## Plugins")
    for p in plugs or []:
        P(f"- {p['name']} [{p['source']}] enabled={p['enabled']}" + (f" preference={p.get('preference')}" if p.get("preference") else ""))
    if not plugs:
        P("- none")

    P("\n## MCP servers (tool schemas: full when loaded up front, ~name only when deferred)")
    for s in servers:
        pr = procs.get(s["name"])
        extra = f" — running processes: {pr['processes']} (orphans {pr['orphans']})" if pr else ""
        P(f"- {s['name']} [{s['scope']}, {s['transport']}] {s['target'][:90]} — usage: {u('mcp:' + s['name'])}{extra}")
    if not servers:
        P("- none configured in files (app/account-provided servers are not visible here; check the live session)")
    if other_proj:
        P("- only in other projects: " + "; ".join(f"{rel(k)}: {', '.join(v)}" for k, v in other_proj.items()))
    if use:
        app = [(k, v) for k, v in U.items() if k.startswith("mcp:") and k[4:] not in {s["name"] for s in servers}]
        if app:
            P("- other MCP servers seen in transcripts (app built-ins, claude.ai connectors, plugins): " +
              "; ".join(f"{k[4:]} {v['calls']}×/{v['sessions']} sess, last {v['last']}" for k, v in app))

    P("\n## Hooks (run on every matching tool call; their output lands in context)")
    for h in hooks:
        miss = f" MISSING: {h['missing_scripts']}" if h["missing_scripts"] else ""
        P(f"- {h['event']}:{h['matcher']} [{h['settings']}] {h['command'][:100]} ({h['script_kb']} KB){miss}")
    if not hooks:
        P("- none")
    if use:
        hc = use["hook_context"]
        P(f"- hook-injected context in window: {hc['injections']} injections, ~{hc['tokens_total']} tok total, last {hc['last'] or '-'}")

    P("\n## Model / effort / other settings")
    for n in notes:
        P(f"- {n['settings']}: {n['key']} = {json.dumps(n['value'])[:160]}")

    P("\n## Clutter (not loaded, only disk)")
    for j in junk:
        P(f"- {j['path']} — {j['why']} ({j['kb']} KB)")
    if not junk:
        P("- none")


if __name__ == "__main__":
    sys.exit(main())
